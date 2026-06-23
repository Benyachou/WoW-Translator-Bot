"""
╔══════════════════════════════════════════════════════════════════╗
║   WoW Translator — IA Provider (abstraction multi-backend)      ║
║                                                                  ║
║   Backends supportés :                                           ║
║     • ollama   — modèle local via Ollama (défaut)                ║
║     • gemini   — Google Gemini API                               ║
║     • openai   — OpenAI ChatGPT API                              ║
║     • claude   — Anthropic Claude API                            ║
╚══════════════════════════════════════════════════════════════════╝
"""

import re
import json
import logging
import requests

import config_manager

logger = logging.getLogger("IA-Provider")

_BACKEND_URLS = {
    "gemini":  "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
    "openai":  "https://api.openai.com/v1/chat/completions",
    "claude":  "https://api.anthropic.com/v1/messages",
}

_DEFAULT_MODELS = {
    "ollama":  "mistral-nemo",
    "gemini":  "gemini-2.0-flash",
    "openai":  "gpt-4o-mini",
    "claude":  "claude-sonnet-4-20250514",
}


def get_backend() -> str:
    return config_manager.get("ia", "backend", fallback="ollama").lower().strip()


def get_model(override: str = None) -> str:
    if override:
        return override
    model = config_manager.get("ia", "model_name", fallback="").strip()
    if model:
        return model
    return _DEFAULT_MODELS.get(get_backend(), "mistral-nemo")


def get_api_key() -> str:
    return config_manager.get("ia", "api_key", fallback="").strip()


def get_api_url() -> str:
    return config_manager.get("ia", "api_url", fallback="").strip()


_ollama_client = None
_ollama_client_url = None


def _get_ollama_client():
    global _ollama_client, _ollama_client_url
    import ollama as _ollama

    host = config_manager.get("ollama", "host")
    port = config_manager.get("ollama", "port")
    url = f"http://{host}:{port}"

    if _ollama_client is None or _ollama_client_url != url:
        try:
            _ollama_client = _ollama.Client(host=url)
            _ollama_client_url = url
        except Exception:
            _ollama_client = None
            _ollama_client_url = None

    return _ollama_client


def list_ollama_models() -> list:
    import ollama as _ollama
    client = _get_ollama_client()
    _list_fn = client.list if client else _ollama.list
    return [m.model for m in _list_fn().models]


def _chat_ollama(model: str, messages: list, options: dict) -> str:
    import ollama as _ollama

    client = _get_ollama_client()
    try:
        _chat_fn = client.chat if client else _ollama.chat
        resp = _chat_fn(model=model, messages=messages, options=options)
        return resp["message"]["content"].strip()
    except Exception:
        resp = _ollama.chat(model=model, messages=messages, options=options)
        return resp["message"]["content"].strip()


def _chat_gemini(model: str, messages: list, options: dict) -> str:
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Clé API Gemini manquante — configurez-la dans Paramètres > IA")

    custom_url = get_api_url()
    if custom_url:
        url = custom_url
    else:
        url = _BACKEND_URLS["gemini"].format(model=model, api_key=api_key)

    prompt_text = "\n".join(
        f"{m.get('role', 'user')}: {m['content']}" if len(messages) > 1
        else m["content"]
        for m in messages
    )

    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": options.get("temperature", 0.0),
            "maxOutputTokens": options.get("num_predict", 1024),
        }
    }

    # Safety settings permissifs pour la traduction
    payload["safetySettings"] = [
        {"category": c, "threshold": "BLOCK_NONE"}
        for c in [
            "HARM_CATEGORY_HARASSMENT",
            "HARM_CATEGORY_HATE_SPEECH",
            "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "HARM_CATEGORY_DANGEROUS_CONTENT",
        ]
    ]

    resp = requests.post(url, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError(f"Gemini n'a retourné aucun résultat : {data}")

    return candidates[0]["content"]["parts"][0]["text"].strip()


def _chat_openai(model: str, messages: list, options: dict) -> str:
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Clé API OpenAI manquante — configurez-la dans Paramètres > IA")

    custom_url = get_api_url()
    url = custom_url if custom_url else _BACKEND_URLS["openai"]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": options.get("temperature", 0.0),
        "max_tokens": options.get("num_predict", 1024),
    }

    stop = options.get("stop")
    if stop:
        payload["stop"] = stop[:4]

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    return data["choices"][0]["message"]["content"].strip()


def _chat_claude(model: str, messages: list, options: dict) -> str:
    api_key = get_api_key()
    if not api_key:
        raise ValueError("Clé API Claude manquante — configurez-la dans Paramètres > IA")

    custom_url = get_api_url()
    url = custom_url if custom_url else _BACKEND_URLS["claude"]

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }

    # Claude utilise un format différent : system séparé des messages
    system_text = None
    claude_messages = []
    for m in messages:
        role = m.get("role", "user")
        if role == "system":
            system_text = m["content"]
        else:
            claude_messages.append({"role": role, "content": m["content"]})

    if not claude_messages:
        claude_messages = [{"role": "user", "content": messages[0]["content"]}]

    payload = {
        "model": model,
        "messages": claude_messages,
        "max_tokens": options.get("num_predict", 1024),
        "temperature": options.get("temperature", 0.0),
    }

    if system_text:
        payload["system"] = system_text

    stop = options.get("stop")
    if stop:
        payload["stop_sequences"] = stop[:4]

    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    return data["content"][0]["text"].strip()


_BACKENDS = {
    "ollama": _chat_ollama,
    "gemini": _chat_gemini,
    "openai": _chat_openai,
    "claude": _chat_claude,
}


def chat(model: str, messages: list, options: dict = None) -> str:
    """
    Point d'entrée unique pour tous les backends IA.

    Args:
        model:    nom du modèle (ex: "mistral-nemo", "gemini-2.0-flash", "gpt-4o-mini")
        messages: liste de dicts [{"role": "user", "content": "..."}]
        options:  dict d'options (temperature, num_predict, stop, etc.)

    Returns:
        Texte de la réponse du modèle.
    """
    if options is None:
        options = {}

    backend = get_backend()
    handler = _BACKENDS.get(backend)

    if not handler:
        raise ValueError(
            f"Backend IA inconnu : '{backend}'. "
            f"Valeurs acceptées : {', '.join(_BACKENDS.keys())}"
        )

    logger.debug(f"IA call → backend={backend}, model={model}")
    return handler(model, messages, options)


def is_local() -> bool:
    return get_backend() == "ollama"


def test_connection() -> tuple:
    """
    Teste la connexion au backend configuré.
    Returns: (success: bool, message: str)
    """
    backend = get_backend()

    try:
        if backend == "ollama":
            host = config_manager.get("ollama", "host")
            port = config_manager.get("ollama", "port")
            resp = requests.get(f"http://{host}:{port}/api/tags", timeout=5)
            resp.raise_for_status()
            models = [m["name"] for m in resp.json().get("models", [])]
            return True, f"Ollama OK — {len(models)} modèle(s) : {', '.join(models[:5])}"

        elif backend == "gemini":
            api_key = get_api_key()
            if not api_key:
                return False, "Clé API Gemini non configurée"
            result = chat(get_model(), [{"role": "user", "content": "Reply with OK"}],
                         {"temperature": 0, "num_predict": 5})
            return True, f"Gemini OK — réponse: {result[:30]}"

        elif backend == "openai":
            api_key = get_api_key()
            if not api_key:
                return False, "Clé API OpenAI non configurée"
            result = chat(get_model(), [{"role": "user", "content": "Reply with OK"}],
                         {"temperature": 0, "num_predict": 5})
            return True, f"OpenAI OK — réponse: {result[:30]}"

        elif backend == "claude":
            api_key = get_api_key()
            if not api_key:
                return False, "Clé API Claude non configurée"
            result = chat(get_model(), [{"role": "user", "content": "Reply with OK"}],
                         {"temperature": 0, "num_predict": 5})
            return True, f"Claude OK — réponse: {result[:30]}"

        else:
            return False, f"Backend inconnu : {backend}"

    except Exception as e:
        return False, f"Erreur {backend} : {e}"
