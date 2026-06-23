#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════╗
║   WoW Translator — STATS PAR LOCALE                 ║
║   Dashboard visuel des progrès de traduction        ║
╚══════════════════════════════════════════════════════╝

Usage :
    python stats_locales.py
    python stats_locales.py --token <TON_TOKEN>
    python stats_locales.py --json         → export JSON uniquement
"""

import sys
import json
import base64
import requests
import re
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent

try:
    import config_manager
    BASE_URL = config_manager.get("api", "base_url")
except ImportError:
    BASE_URL = "https://translation-hub.darkuniverse.work"

LOCALES = {
    "frFR": ("French",              "🇫🇷"),
    "esES": ("Spanish (Spain)",     "🇪🇸"),
    "deDE": ("German",              "🇩🇪"),
    "ruRU": ("Russian",             "🇷🇺"),
    "esMX": ("Spanish (Latin America)", "🇲🇽"),
    "zhCN": ("Simplified Chinese",  "🇨🇳"),
}

W = 52  # largeur de chaque carte


# ═══════════════════════════════════════════════════════
# AUTH
# ═══════════════════════════════════════════════════════

def charger_token() -> str | None:
    """Charge le token depuis config_user.json."""
    cfg_path = BASE_DIR / "config_user.json"
    if cfg_path.exists():
        try:
            return json.loads(cfg_path.read_text(encoding="utf-8")).get("token")
        except Exception:
            pass
    return None


def login(username: str, password: str) -> str | None:
    """Tente de récupérer un token frais via login."""
    for ep in ["/api/v1/auth/login", "/api/auth/login", "/api/login"]:
        try:
            r = requests.post(
                BASE_URL + ep,
                json={"username": username, "password": password},
                timeout=8,
            )
            if r.status_code == 200:
                data = r.json()
                tok = data.get("token") or data.get("access_token") or data.get("api_key")
                if tok:
                    return tok
        except Exception:
            pass
    return None


# ═══════════════════════════════════════════════════════
# API CALLS
# ═══════════════════════════════════════════════════════

def get_stats_locale(token: str, locale: str) -> dict | None:
    """
    Récupère les stats de traduction pour une locale.
    Retourne: {translated, total, remaining, pct}
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    # 1. Nombre de strings non-traduits (= remaining)
    remaining = None
    for ep in [
        f"/api/v1/translations/untranslated?locale={locale}&limit=1",
        f"/api/v1/translations?locale={locale}&status=untranslated&limit=1",
    ]:
        try:
            r = requests.get(BASE_URL + ep, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                remaining = data.get("total") or data.get("count")
                if remaining is not None:
                    break
        except Exception:
            pass

    # 2. Nombre de strings traduits (glossaire)
    translated = None
    for ep in [
        f"/api/v1/glossary/export?locale={locale}&format=flat_map&type=all&limit=1",
        f"/api/v1/translations?locale={locale}&status=translated&limit=1",
    ]:
        try:
            r = requests.get(BASE_URL + ep, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                # glossaire retourne directement un dict de paires
                if isinstance(data, dict) and "entries" not in data and "total" not in data:
                    translated = len(data)
                    break
                translated = data.get("total") or data.get("count")
                if translated is not None:
                    break
        except Exception:
            pass

    # 3. Stats dédiées si endpoint existe
    for ep in [
        f"/api/v1/stats?locale={locale}",
        f"/api/v1/translations/stats?locale={locale}",
        f"/api/v1/locale/{locale}/stats",
    ]:
        try:
            r = requests.get(BASE_URL + ep, headers=headers, timeout=8)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, dict):
                    translated = translated or data.get("translated") or data.get("done")
                    remaining  = remaining  or data.get("remaining") or data.get("untranslated")
                    break
        except Exception:
            pass

    if remaining is None and translated is None:
        return None

    total = (translated or 0) + (remaining or 0)
    pct   = (translated / total * 100) if total > 0 else 0

    return {
        "locale":     locale,
        "translated": translated or 0,
        "remaining":  remaining  or 0,
        "total":      total,
        "pct":        round(pct, 1),
    }


# ═══════════════════════════════════════════════════════
# LOCAL STATS (depuis fichiers locaux si API KO)
# ═══════════════════════════════════════════════════════

def stats_locales_fallback() -> dict:
    """Stats locales depuis les fichiers disponibles."""
    stats = {}

    # frFR : depuis wow_dictionnaire.json
    dict_path = BASE_DIR / "wow_dictionnaire.json"
    if dict_path.exists():
        with open(dict_path, encoding="utf-8") as f:
            d = json.load(f)
        stats["frFR"] = {
            "locale": "frFR", "translated": len(d),
            "remaining": 0, "total": len(d), "pct": 100.0,
            "source": "wow_dictionnaire.json (local)",
        }

    # Toutes locales : depuis benchmark_stress_results.json
    bench_path = BASE_DIR / "benchmark_stress_results.json"
    if bench_path.exists():
        bench = json.load(open(bench_path, encoding="utf-8"))
        for locale, rec in bench.get("recap", {}).items():
            if locale not in stats:
                stats[locale] = {
                    "locale":   locale,
                    "score":    rec.get("score_moy", 0),
                    "n_ok":     rec.get("n_ok", 0),
                    "n_warn":   rec.get("n_warn", 0),
                    "n_fail":   rec.get("n_fail", 0),
                    "source":   "benchmark_stress_results.json",
                }

    # Production : depuis parachute.json
    para_path = BASE_DIR / "parachute.json"
    if para_path.exists():
        p = json.load(open(para_path, encoding="utf-8"))
        if "frFR" in stats:
            stats["frFR"]["submitted"] = p.get("trads_reussies", 0)

    return stats


# ═══════════════════════════════════════════════════════
# AFFICHAGE — Cartes par locale
# ═══════════════════════════════════════════════════════

def barre_progress(pct: float, w: int = 38) -> str:
    """Barre de progression bleue/verte style image."""
    filled_b = int(min(pct / 100, 1.0) * w * 0.4)   # bleu = portion traduite
    filled_g = int(min(pct / 100, 1.0) * w * 0.6)   # vert = surplus qualité
    total_f  = filled_b + filled_g
    empty    = w - total_f
    return "━" * filled_b + "─" * filled_g + "·" * empty


def fmt_num(n: int) -> str:
    """Format nombre avec séparateurs milliers."""
    return f"{n:,}".replace(",", " ")


def afficher_carte_api(s: dict, lang: str, emoji: str):
    """Carte avec données API (total, remaining, %)."""
    print("┌" + "─" * W + "┐")
    print(f"│  {emoji}  {lang:<{W-6}}│")
    print("│" + " " * W + "│")
    # Grand nombre = traduit
    trad_str = fmt_num(s["translated"])
    print(f"│  \033[96m{trad_str}\033[0m{' ' * (W - 2 - len(trad_str))}│")
    total_str = f"of {fmt_num(s['total'])} total strings"
    print(f"│  {total_str:<{W-2}}│")
    print("│" + " " * W + "│")
    rem_str = f"{fmt_num(s['remaining'])} remaining"
    print(f"│  \033[1m{rem_str}\033[0m{' ' * (W - 2 - len(rem_str))}│")
    print("│" + " " * W + "│")
    # Barre de progression
    barre = barre_progress(s["pct"])
    print(f"│  \033[34m{barre[:int(len(barre)*0.4)]}\033[32m{barre[int(len(barre)*0.4):]}\033[0m  │")
    pct_str = f"{s['pct']:.1f}% complete"
    print(f"│  {pct_str:<{W-2}}│")
    print("└" + "─" * W + "┘")
    print()


def afficher_carte_bench(locale: str, s: dict, lang: str, emoji: str):
    """Carte avec données benchmark (score qualité IA)."""
    score = s.get("score", 0)
    n_ok   = s.get("n_ok",   0)
    n_warn = s.get("n_warn", 0)
    n_fail = s.get("n_fail", 0)
    n_total = n_ok + n_warn + n_fail

    print("┌" + "─" * W + "┐")
    print(f"│  {emoji}  {lang} ({locale}){' ' * (W - 6 - len(lang) - len(locale))}│")
    print("│" + " " * W + "│")
    score_str = f"{score:.1f}%"
    print(f"│  \033[96m{score_str}\033[0m  qualité IA (benchmark){' ' * (W - 28 - len(score_str))}│")
    print("│" + " " * W + "│")
    detail = f"✅ {n_ok}  ⚠  {n_warn}  ❌ {n_fail}  sur {n_total} strings"
    print(f"│  {detail:<{W-2}}│")
    print("│" + " " * W + "│")
    # Barre score qualité
    barre = barre_progress(score)
    print(f"│  \033[34m{barre[:int(len(barre)*0.4)]}\033[32m{barre[int(len(barre)*0.4):]}\033[0m  │")
    src = s.get("source", "")[:W-4]
    print(f"│  \033[90m{src:<{W-2}}\033[0m│")
    print("└" + "─" * W + "┘")
    print()


def afficher_carte_fr(s: dict, emoji: str):
    """Carte spéciale frFR avec données locales."""
    n = s.get("translated", 0)
    submitted = s.get("submitted", 0)

    print("┌" + "─" * W + "┐")
    print(f"│  {emoji}  French (frFR){' ' * (W - 16)}│")
    print("│" + " " * W + "│")
    print(f"│  \033[96m{fmt_num(n)}\033[0m{' ' * (W - 2 - len(fmt_num(n)))}│")
    print(f"│  {'paires EN→FR dans le glossaire local':<{W-2}}│")
    print("│" + " " * W + "│")
    if submitted:
        sub_str = f"⚡ {fmt_num(submitted)} soumissions en production"
        print(f"│  \033[93m{sub_str}\033[0m{' ' * (W - 2 - len(sub_str))}│")
    print("│" + " " * W + "│")
    barre = barre_progress(100.0)
    print(f"│  \033[34m{barre[:int(len(barre)*0.4)]}\033[32m{barre[int(len(barre)*0.4):]}\033[0m  │")
    print(f"│  {'100% — lookup exact (0 appel IA)':<{W-2}}│")
    print("└" + "─" * W + "┘")
    print()


# ═══════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════

def main():
    args      = sys.argv[1:]
    json_only = "--json" in args
    token_arg = None
    for i, a in enumerate(args):
        if a == "--token" and i + 1 < len(args):
            token_arg = args[i + 1]

    if not json_only:
        print("═" * (W + 2))
        print(f"  WoW Translator — STATS PAR LOCALE")
        print(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        print("═" * (W + 2))
        print()

    # ── Token ────────────────────────────────────────────
    token = token_arg or charger_token()
    api_ok = False

    if token:
        # Vérifier validité
        r = requests.get(
            f"{BASE_URL}/api/v1/translations/untranslated?locale=frFR&limit=1",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            timeout=8,
        )
        api_ok = r.status_code == 200
        if not api_ok and not json_only:
            print("  ⚠  Token expiré — affichage données locales uniquement.")
            print("  ℹ  Relance avec : python stats_locales.py --token <NOUVEAU_TOKEN>")
            print()

    # ── Collecte stats ────────────────────────────────────
    all_stats = {}

    if api_ok:
        if not json_only:
            print("  Récupération stats API…")
        for locale in LOCALES:
            s = get_stats_locale(token, locale)
            if s:
                all_stats[locale] = {**s, "source": "api"}
        if not json_only:
            print(f"  → {len(all_stats)} locales récupérées\n")

    # Compléter avec données locales
    local_stats = stats_locales_fallback()
    for locale, s in local_stats.items():
        if locale not in all_stats:
            all_stats[locale] = s

    # ── Export JSON ───────────────────────────────────────
    if json_only:
        print(json.dumps(all_stats, indent=2, ensure_ascii=False))
        return

    # ── Affichage cartes ──────────────────────────────────
    for locale, (lang, emoji) in LOCALES.items():
        s = all_stats.get(locale, {})
        if not s:
            print(f"  {emoji} {lang} ({locale}) — pas de données\n")
            continue

        source = s.get("source", "")
        if source == "api" and "translated" in s:
            afficher_carte_api(s, lang, emoji)
        elif locale == "frFR":
            afficher_carte_fr(s, emoji)
        else:
            afficher_carte_bench(locale, s, lang, emoji)

    # ── Résumé production ─────────────────────────────────
    bench_path = BASE_DIR / "benchmark_stress_results.json"
    if bench_path.exists():
        bench = json.load(open(bench_path, encoding="utf-8"))
        recap = bench.get("recap", {})
        print("═" * (W + 2))
        print("  RÉSUMÉ QUALITÉ IA (benchmark GPU stress — 5030 strings/locale)")
        print("─" * (W + 2))
        for locale, (lang, emoji) in LOCALES.items():
            if locale == "frFR":
                print(f"  {emoji} {locale:<6} — lookup exact 100% (glossaire API)")
                continue
            r = recap.get(locale, {})
            score = r.get("score_moy", "?")
            n_ok  = r.get("n_ok",   "?")
            n_fail= r.get("n_fail", "?")
            bar_w = 20
            if isinstance(score, (int, float)):
                filled = int(score / 100 * bar_w)
                bar = "█" * filled + "·" * (bar_w - filled)
                col = "\033[92m" if score >= 99 else ("\033[93m" if score >= 95 else "\033[91m")
                print(f"  {emoji} {locale:<6} {col}{bar}\033[0m {score:.1f}%  ✅{n_ok} ❌{n_fail}")
        print("═" * (W + 2))
        print(f"  Benchmark v2 — {bench.get('date', '?')[:16]}")
        print(f"  {bench.get('corpus', '?')} strings × 5 locales = {bench.get('corpus', 0) * 5:,} traductions")
        print("═" * (W + 2))


if __name__ == "__main__":
    main()
