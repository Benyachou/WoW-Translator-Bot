import configparser
import os
import sys
import shutil
from pathlib import Path

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

CONFIG_PATH = BASE_DIR / "config.ini"

_DEFAULTS = {
    "ollama": {
        "exe_path": "auto",
        "host": "127.0.0.1",
        "port": "11434",
        "gpu_vulkan": "1",
    },
    "secrets": {
        "gemini_key": "",
    },
    "ia": {
        "backend": "ollama",
        "model_name": "",
        "api_key": "",
        "api_url": "",
    },
    "traduction": {
        "seuil_qualite": "90",
        "auto_evaluation": "true",
        "timeout": "35",
        "bulk_size": "20",
        "sauvegarde_interval": "50",
    },
    "api": {
        "base_url": "https://translation-hub.darkuniverse.work",
        "rate_limit_max": "28",
        "rate_limit_fenetre": "60",
    },
    "general": {
        "langue_defaut": "frFR",
        "discord_channel_id": "",
    },
}


def _ensure_config():
    if not CONFIG_PATH.exists():
        cfg = configparser.ConfigParser()
        for section, values in _DEFAULTS.items():
            cfg[section] = values
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            cfg.write(f)


def charger_config() -> configparser.ConfigParser:
    _ensure_config()
    cfg = configparser.ConfigParser()
    for section, values in _DEFAULTS.items():
        cfg[section] = dict(values)
    cfg.read(str(CONFIG_PATH), encoding="utf-8")
    return cfg


def sauvegarder_config(cfg: configparser.ConfigParser):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        cfg.write(f)


def get(section: str, key: str, fallback=None) -> str:
    cfg = charger_config()
    return cfg.get(section, key, fallback=fallback or _DEFAULTS.get(section, {}).get(key, ""))


def get_int(section: str, key: str, fallback=0) -> int:
    try:
        return int(get(section, key))
    except (ValueError, TypeError):
        return fallback


def get_bool(section: str, key: str, fallback=False) -> bool:
    val = get(section, key).lower().strip()
    return val in ("true", "1", "yes", "oui")


def set_value(section: str, key: str, value: str):
    cfg = charger_config()
    if section not in cfg:
        cfg[section] = {}
    cfg[section][key] = value
    sauvegarder_config(cfg)


def get_ollama_exe() -> str:
    path = get("ollama", "exe_path")
    if path and path.lower() != "auto":
        return path
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Ollama", "ollama.exe"),
        shutil.which("ollama") or "",
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return "ollama"


def get_ollama_host() -> str:
    host = get("ollama", "host")
    port = get("ollama", "port")
    return f"{host}:{port}"


def get_ollama_env() -> dict:
    env = os.environ.copy()
    host = get("ollama", "host")
    port = get("ollama", "port")
    env["OLLAMA_HOST"] = f"http://{host}:{port}"
    gpu = get("ollama", "gpu_vulkan")
    if gpu == "1":
        env["OLLAMA_VULKAN"] = "1"
    return env
