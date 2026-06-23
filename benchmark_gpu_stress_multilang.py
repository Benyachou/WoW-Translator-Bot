#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║   WoW Translator — BENCHMARK GPU STRESS MULTILINGUE                        ║
║   200 vrais strings WoW × 5 locales — IA pure (sans lookup glossaire)      ║
║   Détection exhaustive des défauts · Auto-patch moteur_multilang.py        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage:
    python benchmark_gpu_stress_multilang.py              → benchmark complet (200 textes × 5 locales)
    python benchmark_gpu_stress_multilang.py --quick      → 40 textes × 5 locales (test rapide)
    python benchmark_gpu_stress_multilang.py --apply      → benchmark + applique patches auto
    python benchmark_gpu_stress_multilang.py esES deDE    → locales spécifiques
    python benchmark_gpu_stress_multilang.py --no-qwen    → mistral-nemo seulement
"""

import sys
import re
import time
import json
import random
import threading
import concurrent.futures
from pathlib import Path
from datetime import datetime
from collections import defaultdict

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _detecter_gpu_label() -> str:
    try:
        import os as _os
        log_path = Path(_os.environ.get("LOCALAPPDATA", "")) / "Ollama" / "server.log"
        if log_path.exists():
            txt = log_path.read_text(encoding="utf-8", errors="ignore")[-8000:]
            m = re.search(r'library=(\w+).*?name=(\S+).*?total="([^"]+)"', txt)
            if m and m.group(1).lower() == "vulkan":
                return f"GPU: {m.group(2)} ({m.group(3)}) [Vulkan]"
            elif m:
                return f"CPU ({m.group(1)})"
    except Exception:
        pass
    return "CPU"

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from moteur_multilang import (
    MultiLangEngine, CORRECTIONS_PAR_LOCALE,
    MODELE_PAR_LOCALE,
)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

LOCALES_DISPO = ["esES", "deDE", "ruRU", "esMX", "zhCN"]

EMOJI = {
    "esES": "🇪🇸", "deDE": "🇩🇪", "ruRU": "🇷🇺",
    "esMX": "🇧🇷", "zhCN": "🇨🇳", "frFR": "🇫🇷",
}

W = 96

# ═══════════════════════════════════════════════════════════════════════════════
# CORPUS — strings WoW réels depuis wow_dictionnaire.json
# ═══════════════════════════════════════════════════════════════════════════════

CORPUS_CRAFTED = [
    # ── Pronoms — test vosotros / Ihr / вы / você ──────────────────────────────
    {"id": "P01", "cat": "pronoun", "en": "You must prove your worth before I trust you."},
    {"id": "P02", "cat": "pronoun", "en": "Your dedication has not gone unnoticed."},
    {"id": "P03", "cat": "pronoun", "en": "Can you hear me? Your power is needed here."},
    {"id": "P04", "cat": "pronoun", "en": "I need you to gather your allies and fight."},
    {"id": "P05", "cat": "pronoun", "en": "You have proven yourself a true hero."},
    {"id": "P06", "cat": "pronoun", "en": "Do you understand what must be done?"},
    {"id": "P07", "cat": "pronoun", "en": "Your courage in the face of darkness is remarkable."},
    {"id": "P08", "cat": "pronoun", "en": "Will you accept this burden, $N?", "has_tag": True},
    # ── Format codes ──────────────────────────────────────────────────────────
    {"id": "F01", "cat": "format", "en": "%s slays %s in glorious combat.", "has_pct": True},
    {"id": "F02", "cat": "format", "en": "%s has joined the guild!", "has_pct": True},
    {"id": "F03", "cat": "format", "en": "%s bows before you.", "has_pct": True},
    {"id": "F04", "cat": "format", "en": "Increases your damage by %d.", "has_pct": True},
    {"id": "F05", "cat": "format", "en": "%s makes a promise to %s.", "has_pct": True},
    # ── Multi-lignes $B ───────────────────────────────────────────────────────
    {"id": "B01", "cat": "multiline", "en": "Binds when picked up$BTwo-Handed Sword$BDurability 120/120", "has_dollar_B": True},
    {"id": "B02", "cat": "multiline", "en": "Increases your spell power by 150.$BIncreases critical strike by 2%.", "has_dollar_B": True},
    {"id": "B03", "cat": "multiline", "en": "(2) Set: Increases damage by 5%.$B(4) Set: Grants Pyromaniac.", "has_dollar_B": True},
    # ── Dialogs lore ──────────────────────────────────────────────────────────
    {"id": "D01", "cat": "dialog", "en": "Citizens of Stormwind! Stand united or fall divided."},
    {"id": "D02", "cat": "dialog", "en": "The Burning Legion has returned. Prepare your defenses."},
    {"id": "D03", "cat": "dialog", "en": "Greetings, $N. We have much to discuss.", "has_tag": True},
    {"id": "D04", "cat": "dialog", "en": "The time has come to reclaim our honor, $N.", "has_tag": True},
    {"id": "D05", "cat": "dialog", "en": "Well done! You have proven your valor to us all."},
    # ── Items / spells ────────────────────────────────────────────────────────
    {"id": "I01", "cat": "item", "en": "An ancient weapon forged in the fires of the Firelands."},
    {"id": "I02", "cat": "item", "en": "Increases your chance to dodge by 2%."},
    {"id": "I03", "cat": "item", "en": "Hurls a fiery ball causing 500 to 600 Fire damage."},
    {"id": "I04", "cat": "item", "en": "Heals a friendly target for 1200 to 1400 health."},
    {"id": "I05", "cat": "item", "en": "Collect 10 Fel Crystals from demons in the Blasted Lands."},
    # ── UI / système ──────────────────────────────────────────────────────────
    {"id": "U01", "cat": "ui", "en": "Accept Quest"},
    {"id": "U02", "cat": "ui", "en": "You have been disconnected from the server."},
    {"id": "U03", "cat": "ui", "en": "Your inventory is full."},
    {"id": "U04", "cat": "ui", "en": "You do not have enough mana."},
]

def charger_corpus_wow(n_total: int = 170, quick: bool = False) -> list[dict]:
    """Charge n_total strings EN réels depuis wow_dictionnaire.json."""
    dict_path = BASE_DIR / "wow_dictionnaire.json"
    if not dict_path.exists():
        print("  ⚠ wow_dictionnaire.json non trouvé — corpus réduit")
        return []

    print(f"  Chargement wow_dictionnaire.json…", end=" ", flush=True)
    with open(dict_path, encoding="utf-8") as f:
        data = json.load(f)
    print(f"{len(data):,} paires", flush=True)

    # Filtre : clés EN pures
    FR_PAT = re.compile(r'[àâäéèêëîïôùûüçœæ\xa0]|(\bde\b|\bdu\b|\bdes\b|\ble\b|\bla\b|\bles\b|\bau\b|\baux\b)', re.I)
    EN_PAT = re.compile(
        r'\b(the|of|and|from|in|a|an|to|with|for|by|your|you|spell|quest|item|armor|weapon|'
        r'damage|healing|power|strike|fire|frost|shadow|holy|nature|arcane|death|blood|'
        r'void|fel|light|dark|iron|silver|steel|bone|stone|crystal|flame|thunder|storm|'
        r'mount|beast|wolf|bear|dragon|demon|orc|elf|human|dwarf|night|undead|troll|'
        r'paladin|warrior|rogue|hunter|mage|warlock|priest|shaman|monk|druid|knight|'
        r'arena|raid|dungeon|heroic|mythic|normal|honor|achievement|passive|active|'
        r'requires|binds|equip|use|level|class|set|bonus|enchant|gem)\b', re.I
    )

    def is_en(k: str) -> bool:
        if not (4 <= len(k) <= 80):      return False
        if FR_PAT.search(k):              return False
        if not re.search(r'[a-zA-Z]', k): return False
        if re.match(r'^[A-Z0-9_\-/\s]+$', k): return False  # codes internes
        if re.search(r'\d{3,}', k):       return False
        if re.search(r'[\[\]<>]', k):     return False
        return bool(EN_PAT.search(k)) or bool(re.match(r'^[A-Z][a-z]', k))

    candidates = [k for k in data.keys() if is_en(k)]

    random.seed(2026)
    if quick:
        n_total = min(40, n_total)

    # Stratification par longueur
    short = [k for k in candidates if len(k.split()) <= 2]
    med   = [k for k in candidates if 3 <= len(k.split()) <= 5]
    long_ = [k for k in candidates if len(k.split()) >= 6]

    n_s = min(n_total // 4, len(short))
    n_m = min(n_total // 2, len(med))
    n_l = min(n_total - n_s - n_m, len(long_))

    sampled = (
        random.sample(short, n_s) +
        random.sample(med,   n_m) +
        random.sample(long_, n_l)
    )
    random.shuffle(sampled)

    corpus = []
    for i, k in enumerate(sampled):
        corpus.append({
            "id":  f"W{i+1:03d}",
            "cat": "wow_real",
            "en":  k,
        })

    print(f"  → {len(corpus)} strings WoW réels (court:{n_s} | moyen:{n_m} | long:{n_l})")
    return corpus


# ═══════════════════════════════════════════════════════════════════════════════
# ENGINES — une instance par locale, glossaire VIDE (test IA pure)
# ═══════════════════════════════════════════════════════════════════════════════

_engine_cache: dict[str, MultiLangEngine] = {}
_engine_lock = threading.Lock()

def get_engine(locale: str) -> MultiLangEngine:
    with _engine_lock:
        if locale not in _engine_cache:
            eng = MultiLangEngine(locale=locale, dict_path=BASE_DIR / "wow_dictionnaire.json")
            # Vider le glossaire → force chemin IA (sinon lookup retournerait du FR)
            eng.api_glossary = {}
            _engine_cache[locale] = eng
        return _engine_cache[locale]


# ═══════════════════════════════════════════════════════════════════════════════
# TRADUCTION — avec timeout et mesure de durée
# ═══════════════════════════════════════════════════════════════════════════════

def traduire_entry(entry: dict, locale: str) -> dict:
    eng = get_engine(locale)
    t0  = time.time()
    try:
        trad = eng.translate(entry["en"])
    except Exception as exc:
        trad = f"[ERREUR: {exc}]"
    duree = round(time.time() - t0, 2)
    return {
        "id":     entry["id"],
        "cat":    entry["cat"],
        "locale": locale,
        "en":     entry["en"],
        "trad":   trad,
        "duree":  duree,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SCORING — détection exhaustive des défauts de traduction
# ═══════════════════════════════════════════════════════════════════════════════

# Mots anglais communs qui ne doivent PAS rester dans la trad
EN_RESIDUALS = re.compile(
    r'\b(the|and|you|your|with|that|this|have|will|our|can|from|for|are|not|all|has|been|must|'
    r'when|but|them|their|they|which|who|been|into|upon|also|more|some|then|each|over|after|'
    r'before|every|those|these|there|here|shall|would|could|should|might|shall|where|while|'
    r'collect|defeat|slay|kill|gather|bring|travel|complete|destroy|find|return|speak|meet|'
    r'quest|item|armor|weapon|damage|healing|power|spell|dungeon|raid|guild|hero|level)\b',
    re.IGNORECASE
)

# Patterns CJK
CJK_PAT = re.compile(r'[\u4e00-\u9fff\u3040-\u30ff\u3400-\u4dbf]')


def scorer(entry: dict, locale: str) -> dict:
    en   = entry["en"]
    trad = entry["trad"]
    cats = entry.get("cat", "")
    issues = []
    scores = {}

    # ── Erreur brute ──────────────────────────────────────────────────────────
    if trad.startswith("[ERREUR:"):
        return {"global": 0.0, "scores": {"erreur": 0.0}, "issues": [trad], "fatal": True}

    # ── Traduction vide ou trop courte ────────────────────────────────────────
    if not trad.strip():
        return {"global": 0.0, "scores": {"vide": 0.0}, "issues": ["traduction vide"], "fatal": True}

    # Pour zhCN : 1 caractère CJK ≈ 3 chars EN → normaliser avant comparaison
    if locale == "zhCN":
        cjk_n = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', trad))
        lat_n = len(trad) - cjk_n
        ratio = (cjk_n * 3 + lat_n) / max(len(en), 1)
    else:
        ratio = len(trad) / max(len(en), 1)
    if ratio < 0.15:
        scores["longueur"] = 0.0
        issues.append(f"trop courte (ratio={ratio:.2f})")
    elif ratio < 0.30:
        scores["longueur"] = 0.4
        issues.append(f"ratio suspect ({ratio:.2f})")
    elif ratio > 4.0:
        scores["longueur"] = 0.5
        issues.append(f"trop longue (ratio={ratio:.2f})")
    else:
        scores["longueur"] = 1.0

    # ── Tags préservés ────────────────────────────────────────────────────────
    tags_src = re.findall(r'\$[BbNn]|%s|%d|\|[TtHhcX][^|]*\|', en)
    if tags_src:
        ok = sum(1 for t in tags_src if t in trad)
        scores["tags"] = ok / len(tags_src)
        lost = [t for t in tags_src if t not in trad]
        if lost:
            issues.append(f"tags perdus: {lost}")
    else:
        scores["tags"] = 1.0

    # ── Anglais résiduel ──────────────────────────────────────────────────────
    # Exclure les noms propres WoW (non-traduits intentionnellement)
    trad_no_proper = re.sub(r"[A-Z][a-z]{2,}", "", trad)
    residuals = EN_RESIDUALS.findall(trad_no_proper)
    scores["no_english"] = max(0.0, 1.0 - len(residuals) * 0.15)
    if residuals:
        issues.append(f"anglais résiduel: {list(set(residuals))[:4]}")

    # ── Répétitions anormales ─────────────────────────────────────────────────
    words = trad.split()
    if len(words) > 5:
        bigrams = [(words[i], words[i+1]) for i in range(len(words)-1)]
        reps = len(bigrams) - len(set(map(str, bigrams)))
        if reps > 4:
            scores["repetition"] = max(0.0, 1.0 - reps * 0.08)
            issues.append(f"répétitions ({reps}×)")
        else:
            scores["repetition"] = 1.0
    else:
        scores["repetition"] = 1.0

    # ── Meta-commentaires IA ──────────────────────────────────────────────────
    if re.search(r'\b(Note|Remarque|Translation|Translated|Please provide|I understand)\b', trad):
        scores["no_meta"] = 0.0
        issues.append("méta-commentaire IA détecté")
    else:
        scores["no_meta"] = 1.0

    # ──────────────────────────────────────────────────────────────────────────
    # Checks SPÉCIFIQUES par locale
    # ──────────────────────────────────────────────────────────────────────────

    if locale == "esES":
        # 1. Pas de formes tú/usted si "you" dans EN
        if re.search(r'\byou\b', en, re.I):
            bad = re.findall(r'\b(tú|usted|tienes|eres|puedes|te\b|tu\b)\b', trad, re.I)
            scores["vosotros"] = max(0.0, 1.0 - len(bad) * 0.3)
            if bad:
                issues.append(f"formes tú/usted: {bad[:4]}")
            else:
                # Vosotros présent ?
                has_vos = bool(re.search(
                    r'\b(vosotros|vuestro|vuestra|vuestros|vuestras|os\b|tenéis|podéis|'
                    r'debéis|sois|habéis|iréis|haréis|recibiréis|sabéis|queréis|venís|'
                    r'seguís|hacéis|vais)\b',
                    trad, re.I
                ))
                if not has_vos:
                    scores["vosotros"] = 0.5
                    issues.append("aucune forme vosotros détectée (attendu si 'you')")
                else:
                    scores["vosotros"] = 1.0
        # 2. CJK parasite
        if CJK_PAT.search(trad):
            scores["no_cjk"] = 0.0
            issues.append("CJK parasite")
        else:
            scores["no_cjk"] = 1.0

    elif locale == "deDE":
        # 1. Pas de du/dich/dein si "you" dans EN
        if re.search(r'\byou\b', en, re.I):
            bad = re.findall(r'\b(du\b|dich\b|dein|deine|deinen|deiner|deinem|dir\b|bist\b)\b', trad, re.I)
            scores["ihr_form"] = max(0.0, 1.0 - len(bad) * 0.35)
            if bad:
                issues.append(f"formes du/dich/dein: {bad[:4]}")
            else:
                # Ihr/Euch/Euer présent ?
                has_ihr = bool(re.search(r'\b(Ihr\b|Euch\b|Euer\b|Eure\b|Euren\b|Eurer\b|Eurem\b|habt\b|seid\b|könnt\b|müsst\b|wisst\b|wollt\b)\b', trad))
                if not has_ihr:
                    scores["ihr_form"] = 0.5
                    issues.append("aucune forme Ihr/Euch détectée (attendu si 'you')")
                else:
                    scores["ihr_form"] = 1.0
        # 2. Capitalisation nominale : vérifie les noms communs connus, pas le ratio brut
        # (le ratio est biaisé car les verbes/adj/prép sont légitimement en minuscule en DE)
        _DE_NOUNS_LOWER = {
            "schaden", "heilung", "zauber", "fähigkeit", "quest", "gebiet", "feind",
            "held", "kraft", "magie", "waffe", "rüstung", "kampf", "dungeon", "horde",
            "allianz", "spieler", "charakter", "belohnung", "aufgabe", "gilde",
            "trank", "geist", "stärke", "ausdauer", "gegner", "monster", "boss",
            "segen", "fluch", "talent", "kammer", "festung", "turm", "grotte",
        }
        mots_all = trad.split()
        nouns_wrong = [m for m in mots_all if m.lower() in _DE_NOUNS_LOWER and m[0].islower()]
        if nouns_wrong:
            pen = min(1.0, len(nouns_wrong) * 0.15)
            scores["noun_caps"] = max(0.0, 1.0 - pen)
            issues.append(f"noms non capitalisés: {nouns_wrong[:4]}")
        else:
            scores["noun_caps"] = 1.0
        # 3. CJK
        if CJK_PAT.search(trad):
            scores["no_cjk"] = 0.0
            issues.append("CJK parasite")
        else:
            scores["no_cjk"] = 1.0

    elif locale == "ruRU":
        # 1. Script cyrillique dominant
        cyr  = len(re.findall(r'[а-яА-ЯёЁ]', trad))
        lat  = len(re.findall(r'[a-zA-Z]', trad))
        tot  = cyr + lat
        if tot == 0:
            scores["cyrillique"] = 0.0
            issues.append("aucun texte")
        else:
            scores["cyrillique"] = cyr / tot
            if scores["cyrillique"] < 0.75:
                issues.append(f"trop de latin ({lat} vs {cyr} cyrillique)")
        # 2. CJK parasite
        if CJK_PAT.search(trad):
            scores["no_cjk"] = 0.0
            issues.append("CJK parasite")
        else:
            scores["no_cjk"] = 1.0
        # 3. Formes вы si "you" dans EN
        if re.search(r'\byou\b', en, re.I):
            bad = re.findall(r'\b(ты|тебя|тебе|твой|твоя|твоих|твоим)\b', trad)
            if bad:
                scores["vy_form"] = max(0.0, 1.0 - len(bad) * 0.4)
                issues.append(f"formes ты (informel): {bad[:3]}")
            else:
                scores["vy_form"] = 1.0

    elif locale == "esMX":
        # 1. PT-BR : você/seu présent si "you" dans EN
        if re.search(r'\byou\b', en, re.I):
            has_ptbr = bool(re.search(r'\b(você|seu|sua|seus|suas|pode|deve|tem|vai|sabe|está|é)\b', trad, re.I))
            scores["ptbr"] = 1.0 if has_ptbr else 0.3
            if not has_ptbr:
                issues.append("aucune forme PT-BR détectée (attendu si 'you')")
        # 2. Pas d'espagnol résiduel
        esp = re.findall(r'\b(tienes|eres|puedes|vuestro|vuestra|usted|vosotros|hola|gracias)\b', trad, re.I)
        scores["no_espagnol"] = max(0.0, 1.0 - len(esp) * 0.35)
        if esp:
            issues.append(f"espagnol résiduel: {esp[:3]}")
        # 3. CJK
        if CJK_PAT.search(trad):
            scores["no_cjk"] = 0.0
            issues.append("CJK parasite")
        else:
            scores["no_cjk"] = 1.0

    elif locale == "zhCN":
        # 1. CJK dominant
        cjk  = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', trad))
        lat  = len(re.findall(r'[a-zA-Z]', trad))
        scores["cjk_present"] = 1.0 if cjk > 3 else (0.4 if cjk > 0 else 0.0)
        if cjk == 0:
            issues.append("aucun caractère chinois")
        # 2. Caractères traditionnels (mauvais pour zhCN)
        trad_chars = re.findall(r'[\u4e00-\u9fff]', trad)
        if trad_chars and cjk > 0:
            scores["simplified"] = 1.0  # difficult to check without dict
        else:
            scores["simplified"] = 1.0 if cjk == 0 else 1.0

    # ── Score global ──────────────────────────────────────────────────────────
    global_score = sum(scores.values()) / len(scores) if scores else 0.5
    return {
        "global":  round(global_score, 3),
        "scores":  {k: round(v, 3) for k, v in scores.items()},
        "issues":  issues,
        "fatal":   False,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# AFFICHAGE
# ═══════════════════════════════════════════════════════════════════════════════

_print_lock = threading.Lock()

def pr(*args, **kwargs):
    with _print_lock:
        print(*args, **kwargs)

def ligne(c="─", w=W): pr(c * w)

def barre(score: float, w: int = 14) -> str:
    f = int(score * w)
    sym = "█" if score >= 0.85 else ("▓" if score >= 0.65 else "░")
    return sym * f + "·" * (w - f) + f" {score*100:5.1f}%"

def couleur_score(score: float) -> str:
    if score >= 0.90: return "✅"
    if score >= 0.70: return "⚠️ "
    return "❌"


# ═══════════════════════════════════════════════════════════════════════════════
# WORKER LOCALE — tourne dans un thread dédié
# ═══════════════════════════════════════════════════════════════════════════════

def worker_locale(locale: str, corpus: list[dict], verbose: bool = True) -> list[dict]:
    """Traite toutes les entrées du corpus pour une locale donnée."""
    emoji  = EMOJI.get(locale, "🌍")
    modele = MODELE_PAR_LOCALE.get(locale, "mistral-nemo")
    results = []

    pr(f"\n  {emoji} [{locale}] démarrage — {len(corpus)} strings — modèle: {modele}")
    t_locale_start = time.time()

    for i, entry in enumerate(corpus):
        res = traduire_entry(entry, locale)
        sc  = scorer(res, locale)
        res.update({"score": sc["global"], "scores": sc["scores"],
                    "issues": sc["issues"], "fatal": sc.get("fatal", False)})
        results.append(res)

        # Affichage progressif
        if verbose:
            flag = couleur_score(sc["global"])
            short_en   = entry["en"][:50].ljust(50)
            short_trad = res["trad"][:50].ljust(50)
            issues_str = " | ".join(sc["issues"])[:40] if sc["issues"] else ""
            pr(f"  {emoji} [{i+1:3d}/{len(corpus)}] {flag} {barre(sc['global'])}  {res['duree']:4.1f}s")
            if sc["issues"]:
                pr(f"      EN  : {short_en}")
                pr(f"      OUT : {short_trad}")
                pr(f"      ⚠   : {issues_str}")

    t_elapsed = time.time() - t_locale_start
    n_ok   = sum(1 for r in results if r["score"] >= 0.85)
    n_warn = sum(1 for r in results if 0.65 <= r["score"] < 0.85)
    n_fail = sum(1 for r in results if r["score"] < 0.65)
    avg    = sum(r["score"] for r in results) / len(results) if results else 0

    pr(f"\n  {emoji} [{locale}] TERMINÉ — {t_elapsed:.0f}s | moy: {avg*100:.1f}%"
       f" | ✅{n_ok} ⚠️{n_warn} ❌{n_fail}")
    return results


# ═══════════════════════════════════════════════════════════════════════════════
# ANALYSE DES DÉFAUTS — par locale, par type d'issue
# ═══════════════════════════════════════════════════════════════════════════════

def analyser_defauts(all_results: list[dict]) -> dict:
    """Agrège les défauts par locale et génère des suggestions de patches."""
    par_locale = defaultdict(list)
    for r in all_results:
        if r["issues"]:
            par_locale[r["locale"]].append(r)

    analyse = {}
    for locale, fails in par_locale.items():
        issue_types = defaultdict(list)
        for r in fails:
            for issue in r["issues"]:
                key = re.split(r'[:=\(]', issue)[0].strip()
                issue_types[key].append({
                    "en":    r["en"],
                    "trad":  r["trad"],
                    "issue": issue,
                    "score": r["score"],
                })
        analyse[locale] = dict(issue_types)

    return analyse


# ═══════════════════════════════════════════════════════════════════════════════
# GÉNÉRATION DE PATCHES AUTO
# ═══════════════════════════════════════════════════════════════════════════════

def generer_patches(analyse: dict) -> dict[str, list[tuple]]:
    """
    Génère des nouvelles règles regex pour CORRECTIONS_PAR_LOCALE
    en s'appuyant sur les patterns d'échec observés.
    Retourne {locale: [(pattern, remplacement), ...]}
    """
    patches: dict[str, list[tuple]] = defaultdict(list)

    for locale, issues in analyse.items():

        if locale == "esES":
            # Vérifier si des formes tú/usted passent quand même
            if "formes tú/usted" in issues:
                fails = issues["formes tú/usted"]
                # Patterns jamais couverts
                bad_forms = set()
                for f in fails:
                    found = re.findall(r'\b(tú|usted|tienes|eres|puedes|te\b|tu\b)\b', f["trad"], re.I)
                    bad_forms.update(found)
                for form in bad_forms:
                    already = any(form.lower() in p[0].lower() for p in CORRECTIONS_PAR_LOCALE.get("esES", []))
                    if not already:
                        patches["esES"].append((rf'\b{re.escape(form)}\b', "vosotros"))

        elif locale == "deDE":
            if "formes du/dich/dein" in issues:
                fails = issues["formes du/dich/dein"]
                bad_forms = set()
                for f in fails:
                    found = re.findall(r'\b(du|dich|dein|deine|deinen|deiner|deinem|dir)\b', f["trad"], re.I)
                    bad_forms.update(found)
                for form in bad_forms:
                    already = any(form.lower() in p[0].lower() for p in CORRECTIONS_PAR_LOCALE.get("deDE", []))
                    if not already:
                        mapping = {"du": "Ihr", "dich": "Euch", "dir": "Euch",
                                   "dein": "Euer", "deine": "Eure",
                                   "deinen": "Euren", "deiner": "Eurer", "deinem": "Eurem"}
                        rep = mapping.get(form.lower(), "Euch")
                        patches["deDE"].append((rf'\b{re.escape(form)}\b', rep))
            # Mots courants non capitalisés
            if "capitalisation nominale faible" in issues:
                common_nouns = [
                    "schaden", "heilung", "zauber", "fähigkeit", "quest", "gebiet",
                    "feind", "freund", "held", "kraft", "magie", "waffe", "rüstung",
                    "kampf", "dungeon", "horde", "allianz", "schlachtzug", "aufgabe",
                    "belohnung", "fähigkeiten", "verbündeter", "spieler", "charakter",
                    "auftrag", "bereich", "monster", "gegner", "boss", "kristall",
                    "kammer", "turm", "festung", "tempel", "grotte", "schlucht",
                ]
                for n in common_nouns:
                    already = any(n in p[0] for p in CORRECTIONS_PAR_LOCALE.get("deDE", []))
                    if not already:
                        patches["deDE"].append((rf'\b{n}\b', n.capitalize()))

        elif locale == "ruRU":
            if "anglais résiduel" in issues:
                fails = issues["anglais résiduel"]
                en_words = set()
                for f in fails:
                    found = re.findall(r'\b(you|your|quest|damage|healing|item|spell|guild|level)\b', f["trad"], re.I)
                    en_words.update(found)
                mapping = {
                    "quest": "задание", "damage": "урон", "healing": "исцеление",
                    "item": "предмет", "spell": "заклинание", "guild": "гильдия",
                    "level": "уровень",
                }
                for w in en_words:
                    if w.lower() in mapping:
                        already = any(w.lower() in p[0].lower() for p in CORRECTIONS_PAR_LOCALE.get("ruRU", []))
                        if not already:
                            patches["ruRU"].append((rf'\b{re.escape(w)}\b', mapping[w.lower()]))

        elif locale == "esMX":
            if "espagnol résiduel" in issues:
                fails = issues["espagnol résiduel"]
                esp_words = set()
                for f in fails:
                    found = re.findall(r'\b(tienes|eres|puedes|vuestro|vuestra|usted|vosotros|hola)\b', f["trad"], re.I)
                    esp_words.update(found)
                mapping = {
                    "tienes": "tem", "eres": "és", "puedes": "pode",
                    "usted": "você", "vosotros": "vocês",
                    "vuestro": "seu", "vuestra": "sua",
                }
                for w in esp_words:
                    if w.lower() in mapping:
                        already = any(w.lower() in p[0].lower() for p in CORRECTIONS_PAR_LOCALE.get("esMX", []))
                        if not already:
                            patches["esMX"].append((rf'\b{re.escape(w)}\b', mapping[w.lower()]))

    return dict(patches)


# ═══════════════════════════════════════════════════════════════════════════════
# APPLICATION DES PATCHES dans moteur_multilang.py
# ═══════════════════════════════════════════════════════════════════════════════

def appliquer_patches(patches: dict[str, list[tuple]], dry_run: bool = True) -> list[str]:
    """
    Insère les nouvelles règles dans CORRECTIONS de wow_rules_{locale}.py.
    dry_run=True → affiche seulement, sans modifier le fichier.
    Retourne la liste des insertions effectuées.
    """
    insertions = []

    if not patches:
        return insertions

    for locale, rules in patches.items():
        if not rules:
            continue

        rules_path = BASE_DIR / f"wow_rules_{locale}.py"
        if not rules_path.exists():
            pr(f"  ⚠️ wow_rules_{locale}.py introuvable — patches {locale} ignorés")
            continue

        code = rules_path.read_text(encoding="utf-8")

        for (pat, rep) in rules:
            if pat not in code:
                insertions.append(f"{locale} | CORRECTIONS += ({pat!r}, {rep!r})")
                if not dry_run:
                    marker = f"    # auto-patché le {datetime.now().strftime('%Y-%m-%d')}\n"
                    line = f"    (r'{pat}',{' ' * max(1, 16 - len(pat))}'{rep}'),\n"
                    idx = code.rfind("]")
                    if idx != -1:
                        code = code[:idx] + marker + line + code[idx:]

        if not dry_run and any(pat not in rules_path.read_text(encoding="utf-8") for pat, _ in rules):
            rules_path.write_text(code, encoding="utf-8")

    if not dry_run and insertions:
        pr(f"\n  ✅ {len(insertions)} règle(s) insérées dans wow_rules_*.py")

    return insertions


# ═══════════════════════════════════════════════════════════════════════════════
# RAPPORT FINAL
# ═══════════════════════════════════════════════════════════════════════════════

def rapport(all_results: list[dict], analyse: dict, patches: dict,
            t_total: float, corpus_size: int, apply: bool):
    ligne("═")
    pr(f"\n  RAPPORT FINAL — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    pr(f"  Corpus : {corpus_size} strings WoW  |  Durée totale : {t_total:.0f}s")
    ligne()

    # Tableau par locale
    locales = sorted(set(r["locale"] for r in all_results))
    pr(f"\n  {'Locale':<10} {'Score moy':>9}  {'✅':>5}  {'⚠️':>5}  {'❌':>5}  {'Issues top'}")
    ligne()

    for locale in locales:
        recs = [r for r in all_results if r["locale"] == locale]
        avg  = sum(r["score"] for r in recs) / len(recs)
        n_ok  = sum(1 for r in recs if r["score"] >= 0.85)
        n_warn= sum(1 for r in recs if 0.65 <= r["score"] < 0.85)
        n_fail= sum(1 for r in recs if r["score"] < 0.65)
        emoji = EMOJI.get(locale, "🌍")

        # Top issues
        issue_counts = defaultdict(int)
        for r in recs:
            for iss in r["issues"]:
                k = re.split(r'[:=\(]', iss)[0].strip()
                issue_counts[k] += 1
        top_issues = sorted(issue_counts.items(), key=lambda x: -x[1])[:3]
        top_str = " | ".join(f"{k}×{n}" for k, n in top_issues) or "—"

        pr(f"  {emoji} {locale:<8} {avg*100:>8.1f}%  {n_ok:>5}  {n_warn:>5}  {n_fail:>5}  {top_str}")

    ligne()

    # Échecs les plus graves (score < 0.5)
    grave = sorted([r for r in all_results if r["score"] < 0.50], key=lambda x: x["score"])
    if grave:
        pr(f"\n  ÉCHECS GRAVES (score < 50%) — {len(grave)} cas :")
        for r in grave[:15]:
            pr(f"    {EMOJI.get(r['locale'],'🌍')} [{r['locale']}] {r['score']*100:4.0f}%  {r['en'][:55]!r}")
            pr(f"       → {r['trad'][:70]!r}")
            pr(f"       issues: {' | '.join(r['issues'])}")

    # Patches proposés
    if patches:
        pr(f"\n  PATCHES AUTO GÉNÉRÉS :")
        for locale, rules in patches.items():
            if rules:
                pr(f"\n  {EMOJI.get(locale,'🌍')} {locale} — {len(rules)} nouvelles règle(s) :")
                for pat, rep in rules[:10]:
                    pr(f"    + {pat!r:40s} → {rep!r}")
        if apply:
            applied = appliquer_patches(patches, dry_run=False)
            pr(f"\n  ✅ {len(applied)} règle(s) appliquées dans moteur_multilang.py")
        else:
            pr(f"\n  ℹ  Lance avec --apply pour appliquer ces patches automatiquement.")
    else:
        pr("\n  ✅ Aucun patch nécessaire — moteur_multilang.py est optimal.")

    # Statistiques GPU
    pr(f"\n  STATISTIQUES GPU :")
    total_traductions = len(all_results)
    t_moy = t_total / total_traductions if total_traductions else 0
    tps_par_locale = {}
    for locale in locales:
        recs = [r for r in all_results if r["locale"] == locale]
        t_loc = sum(r["duree"] for r in recs)
        tps_par_locale[locale] = t_loc / len(recs) if recs else 0
    for locale in locales:
        pr(f"    {EMOJI.get(locale,'🌍')} {locale} : {tps_par_locale[locale]:.1f}s/trad")
    pr(f"    Total  : {total_traductions} traductions en {t_total:.0f}s  ({t_moy:.1f}s/trad)")

    ligne("═")


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    args    = sys.argv[1:]
    quick   = "--quick"  in args
    apply   = "--apply"  in args
    no_qwen = "--no-qwen" in args
    verbose = "--quiet" not in args

    # --n5000, --n1000, --n500, etc. → taille du corpus WoW
    n_corpus = 170  # défaut
    for a in args:
        m = re.match(r'^--n(\d+)$', a)
        if m:
            n_corpus = int(m.group(1))
    args = [a for a in args if not a.startswith("--")]

    locales = [a for a in args if a in LOCALES_DISPO] or LOCALES_DISPO

    if no_qwen:
        from moteur_multilang import MODELE_PAR_LOCALE as mpl
        for loc in locales:
            mpl[loc] = "mistral-nemo"

    # ── En-tête ───────────────────────────────────────────────────────────────
    pr("═" * W)
    pr(f"  WoW Translator — BENCHMARK GPU STRESS MULTILINGUE")
    pr(f"  {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  {_detecter_gpu_label()}")
    pr(f"  Locales : {' | '.join(locales)}")
    pr(f"  Mode    : {'RAPIDE (quick)' if quick else f'COMPLET ({n_corpus} strings/locale)'} {'| APPLY PATCHES' if apply else ''}")
    ligne("═")

    # ── Construction du corpus ────────────────────────────────────────────────
    pr("\n  Construction du corpus…")
    corpus_wow = charger_corpus_wow(n_total=n_corpus, quick=quick)
    corpus_all = corpus_wow + CORPUS_CRAFTED
    if quick:
        corpus_all = corpus_wow[:40] + CORPUS_CRAFTED

    pr(f"  CORPUS TOTAL : {len(corpus_all)} strings ({len(corpus_wow)} WoW réels + {len(CORPUS_CRAFTED)} crafted)")
    ligne()

    # ── Pré-chargement des engines (1 par locale) ─────────────────────────────
    pr("\n  Initialisation des moteurs IA…")
    for locale in locales:
        try:
            eng = get_engine(locale)
            pr(f"  {EMOJI.get(locale,'🌍')} {locale} → {eng.modele_ia} ✅")
        except Exception as e:
            pr(f"  {EMOJI.get(locale,'🌍')} {locale} → ❌ {e}")
            locales = [l for l in locales if l != locale]
    ligne()

    if not locales:
        pr("❌ Aucune locale disponible. Vérifie Ollama.")
        sys.exit(1)

    # ── Lancement parallèle (un thread par locale) ────────────────────────────
    pr(f"\n  Lancement {len(locales)} locale(s) en parallèle sur GPU…\n")
    t_start     = time.time()
    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(locales)) as pool:
        futures = {
            pool.submit(worker_locale, locale, corpus_all, verbose): locale
            for locale in locales
        }
        for fut in concurrent.futures.as_completed(futures):
            locale = futures[fut]
            try:
                results = fut.result()
                all_results.extend(results)
            except Exception as exc:
                pr(f"  ❌ {locale} — erreur worker : {exc}")

    t_total = time.time() - t_start

    # ── Analyse ───────────────────────────────────────────────────────────────
    analyse = analyser_defauts(all_results)
    patches = generer_patches(analyse)

    # ── Rapport ───────────────────────────────────────────────────────────────
    rapport(all_results, analyse, patches, t_total, len(corpus_all), apply)

    # ── Sauvegarde JSON ───────────────────────────────────────────────────────
    out = BASE_DIR / "benchmark_stress_results.json"
    payload = {
        "date":    datetime.now().isoformat(),
        "gpu":     _detecter_gpu_label(),
        "locales": locales,
        "corpus":  len(corpus_all),
        "duree_s": round(t_total, 1),
        "recap": {
            loc: {
                "score_moy": round(
                    sum(r["score"] for r in all_results if r["locale"] == loc) /
                    max(1, sum(1 for r in all_results if r["locale"] == loc)) * 100, 1
                ),
                "n_ok":    sum(1 for r in all_results if r["locale"] == loc and r["score"] >= 0.85),
                "n_warn":  sum(1 for r in all_results if r["locale"] == loc and 0.65 <= r["score"] < 0.85),
                "n_fail":  sum(1 for r in all_results if r["locale"] == loc and r["score"] < 0.65),
            }
            for loc in locales
        },
        "patches_proposes": {
            loc: [(p, r) for p, r in rules]
            for loc, rules in patches.items()
        },
        "details": [
            {
                "id":     r["id"],
                "cat":    r["cat"],
                "locale": r["locale"],
                "en":     r["en"],
                "trad":   r["trad"],
                "score":  round(r["score"] * 100, 1),
                "duree":  r["duree"],
                "issues": r["issues"],
            }
            for r in sorted(all_results, key=lambda x: (x["locale"], x["id"]))
        ],
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    pr(f"\n  JSON → {out.name}")
    ligne("═")


if __name__ == "__main__":
    main()
