"""
╔══════════════════════════════════════════════════════════════════════╗
║   WoW Translator — BENCHMARK MULTILINGUE (benchmark_multilang.py)   ║
║   Compare mistral-nemo vs qwen2.5:14b sur toutes les locales         ║
╚══════════════════════════════════════════════════════════════════════╝

Usage :
    python benchmark_multilang.py              → toutes les locales
    python benchmark_multilang.py esES deDE    → locales spécifiques
    python benchmark_multilang.py --no-qwen    → mistral-nemo seulement
"""

import sys
import re
import time
import ollama
from pathlib import Path
from datetime import datetime

# Force UTF-8 sur la console Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

MODELES_TESTER = ["mistral-nemo", "qwen2.5:14b"]

LOCALES_DISPO = {
    "frFR": "French",
    "esES": "Spanish (Spain)",
    "deDE": "German",
    "ruRU": "Russian",
}

# Textes de test WoW — variété de types et difficultés
TEXTES_TEST = [
    {
        "id": "T01",
        "type": "Dialog simple",
        "en": "Greetings, $N. We have much to discuss.",
    },
    {
        "id": "T02",
        "type": "Dialog avec 'you'",
        "en": "You must prove your worth before I can trust you with this task.",
    },
    {
        "id": "T03",
        "type": "Quête (long)",
        "en": "The Burning Legion has returned, $N. You must gather your allies and prepare for the battle ahead. Return to me when you have completed your preparations.",
    },
    {
        "id": "T04",
        "type": "Description objet",
        "en": "Khadgar's Ancient Staff$BBinds when picked up$BTwo-Hand Staff$B$BDurability 120 / 120$BRequires Level 60",
    },
    {
        "id": "T05",
        "type": "Dialog possessif",
        "en": "Your dedication to our cause has not gone unnoticed. Your companions speak highly of you, and your reputation precedes you throughout the land.",
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# SCORING AUTOMATIQUE
# ═══════════════════════════════════════════════════════════════════════════════

def score_traduction(en: str, trad: str, locale: str) -> dict:
    """Retourne un dict de scores (0.0–1.0) pour différents critères."""
    scores = {}
    raisons = []

    # 1. Tags préservés ($B, $N, %s, |T…)
    tags_en   = re.findall(r'\$[BbNn]|%s|\|[TtHhc][^|]*\||{\d+}', en)
    tags_trad = re.findall(r'\$[BbNn]|%s|\|[TtHhc][^|]*\||{\d+}', trad)
    if not tags_en:
        scores["tags"] = 1.0
    else:
        ok = sum(1 for t in tags_en if t in tags_trad)
        scores["tags"] = ok / len(tags_en)
        if scores["tags"] < 1.0:
            raisons.append(f"tags perdus: {[t for t in tags_en if t not in tags_trad]}")

    # 2. Pas d'anglais résiduel évident
    mots_en_communs = ["the", "and", "you", "your", "with", "that", "this",
                        "have", "will", "our", "can", "from", "for", "are",
                        "not", "all", "has", "been", "must", "when", "but"]
    trad_lower = trad.lower()
    anglais_trouves = [m for m in mots_en_communs if re.search(r'\b' + m + r'\b', trad_lower)]
    scores["no_english"] = max(0.0, 1.0 - len(anglais_trouves) * 0.2)
    if anglais_trouves:
        raisons.append(f"anglais résiduel: {anglais_trouves[:3]}")

    # 3. Longueur cohérente (ratio 0.4–3.0 par rapport à l'EN)
    ratio = len(trad) / max(len(en), 1)
    if 0.4 <= ratio <= 3.0:
        scores["longueur"] = 1.0
    elif ratio < 0.2:
        scores["longueur"] = 0.0
        raisons.append(f"trop court (ratio {ratio:.2f})")
    else:
        scores["longueur"] = 0.7
        raisons.append(f"ratio longueur suspect ({ratio:.2f})")

    # 4. Vérifications spécifiques par locale
    if locale == "esES":
        # Pas de formes tú/usted
        formes_incorrectes = re.findall(r'\b(tú|usted|tienes|eres\b(?!\s+de)|puedes|recibirás)\b',
                                        trad, re.IGNORECASE)
        scores["pronoms"] = max(0.0, 1.0 - len(formes_incorrectes) * 0.3)
        if formes_incorrectes:
            raisons.append(f"formes tú/usted: {formes_incorrectes[:3]}")
        # Présence de vosotros/vuestro
        has_vosotros = bool(re.search(r'\b(vosotros|vuestra|vuestro|tenéis|podéis|os\b|habéis)\b',
                                       trad, re.IGNORECASE))
        scores["vosotros"] = 1.0 if has_vosotros or "you" not in en.lower() else 0.5

    elif locale == "deDE":
        # Majuscules nominales (heuristique : au moins 20% de mots commençant par majuscule hors début de phrase)
        mots = [m for m in trad.split() if len(m) > 3]
        if mots:
            majuscules = sum(1 for m in mots if m[0].isupper() and not m.isupper())
            scores["majuscules"] = min(1.0, majuscules / len(mots) * 2.5)
            if scores["majuscules"] < 0.4:
                raisons.append(f"majuscules nominales insuffisantes ({majuscules}/{len(mots)})")
        else:
            scores["majuscules"] = 1.0
        # Pas de 'du/dein/dich'
        formes_incorrectes = re.findall(r'\b(du\b|dein|dich|dir\b|bist\b(?!\s+du))\b',
                                        trad, re.IGNORECASE)
        scores["pronoms"] = max(0.0, 1.0 - len(formes_incorrectes) * 0.3)
        if formes_incorrectes:
            raisons.append(f"formes du/dein: {formes_incorrectes[:3]}")

    elif locale == "ruRU":
        # Texte cyrillique présent
        cyrillic = len(re.findall(r'[а-яА-ЯёЁ]', trad))
        latin    = len(re.findall(r'[a-zA-Z]', trad))
        if cyrillic + latin == 0:
            scores["cyrillique"] = 0.0
            raisons.append("pas de texte")
        else:
            scores["cyrillique"] = cyrillic / (cyrillic + latin)
            if scores["cyrillique"] < 0.7:
                raisons.append(f"trop de latin ({latin} chars Latin vs {cyrillic} Cyrillique)")

    elif locale == "frFR":
        # Pas de 'you/your' non traduit
        you_restant = re.findall(r'\b(you|your)\b', trad, re.IGNORECASE)
        scores["no_you"] = max(0.0, 1.0 - len(you_restant) * 0.5)
        if you_restant:
            raisons.append(f"'you' non traduit: {len(you_restant)}x")

    # Score global (moyenne pondérée)
    global_score = sum(scores.values()) / len(scores) if scores else 0.0

    return {
        "scores":  scores,
        "global":  global_score,
        "raisons": raisons,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# TRADUCTION
# ═══════════════════════════════════════════════════════════════════════════════

LANGUES_REGLES = {
    "frFR": "Translate 'you' as 'vous'. Reorder possessives: 'Khadgar's Robe' → 'Robe de Khadgar'. Respect French syntax.",
    "esES": "CRITICAL: Use ONLY vosotros form. NEVER tú or usted. tienes→tenéis, eres→sois, tu→vuestro, recibirás→recibiréis. Reorder possessives.",
    "deDE": "Capitalize ALL nouns. Use Ihr/Euch/Euer for 'you'. NEVER du/dein/dich. Reorder possessives.",
    "ruRU": "Use Cyrillic ONLY. Use вы (formal). Official Blizzard RU terminology.",
}

LANGUES_NOM = {
    "frFR": "French", "esES": "Spanish (Spain)",
    "deDE": "German", "ruRU": "Russian",
}

def traduire(texte: str, locale: str, modele: str) -> tuple[str, float]:
    """Retourne (traduction, temps_secondes)."""
    lang       = LANGUES_NOM.get(locale, locale)
    rules      = LANGUES_REGLES.get(locale, "")
    lang_code  = locale[:2].upper()

    # Masquage des tags
    tags  = re.findall(r'\$[BbNn]|%s|\|[TtHhc][^|]*\|', texte)
    masq  = texte
    for i, t in enumerate(tags):
        masq = masq.replace(t, f"[T{i}]", 1)

    prompt = (
        f"You are a Blizzard WoW localization expert. "
        f"Translate naturally into {lang}. "
        f"RULES: {rules} "
        f"Keep [Tx] placeholders exactly as-is. "
        f"Output ONLY the translation, no comments.\n"
        f"EN: {masq}\n{lang_code}:"
    )

    t0 = time.time()
    try:
        resp = ollama.chat(
            model=modele,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0, "stop": ["EN:", f"{lang_code}:"]},
        )
        trad = resp["message"]["content"].strip().replace('"', "")
    except Exception as e:
        return f"[ERREUR: {e}]", time.time() - t0

    # Restauration tags
    for i, t in enumerate(tags):
        trad = trad.replace(f"[T{i}]", t)

    return trad, time.time() - t0


# ═══════════════════════════════════════════════════════════════════════════════
# AFFICHAGE
# ═══════════════════════════════════════════════════════════════════════════════

W = 90  # largeur console

def ligne(char="─", w=W): print(char * w)
def titre(txt, char="═"): print(f"\n{char*W}\n  {txt}\n{char*W}")

EMOJI_LOCALE = {"frFR": "🇫🇷", "esES": "🇪🇸", "deDE": "🇩🇪", "ruRU": "🇷🇺"}

def barre_score(score: float, w=20) -> str:
    filled = int(score * w)
    color  = "🟩" if score >= 0.8 else "🟨" if score >= 0.6 else "🟥"
    return color * filled + "⬜" * (w - filled) + f" {score*100:.0f}%"

def afficher_resultat(texte_id, type_txt, en, locale, modele, trad, scoring, duree):
    print(f"\n  [{texte_id}] {type_txt}")
    print(f"  EN : {en[:80]}{'…' if len(en)>80 else ''}")
    print(f"  {EMOJI_LOCALE.get(locale,'🌍')} : {trad[:80]}{'…' if len(trad)>80 else ''}")
    print(f"  Score : {barre_score(scoring['global'])}  ({duree:.1f}s)")
    if scoring["raisons"]:
        print(f"  ⚠️  {' | '.join(scoring['raisons'])}")
    details = "  Détail : " + "  ".join(
        f"{k}={v*100:.0f}%" for k, v in scoring["scores"].items()
    )
    print(details)


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    args = sys.argv[1:]
    no_qwen   = "--no-qwen"   in args
    args      = [a for a in args if not a.startswith("--")]

    # Locales à tester
    locales_cibles = [a for a in args if a in LOCALES_DISPO]
    if not locales_cibles:
        locales_cibles = list(LOCALES_DISPO.keys())

    # Modèles disponibles
    try:
        installes = [m.model.split(":")[0] for m in ollama.list().models if m.model]
    except Exception:
        print("❌ Ollama inaccessible — lance Ollama d'abord.")
        sys.exit(1)

    modeles_dispo = [m for m in MODELES_TESTER if m.split(":")[0] in installes]
    if no_qwen:
        modeles_dispo = [m for m in modeles_dispo if "qwen" not in m]

    if not modeles_dispo:
        print(f"❌ Aucun modèle disponible parmi {MODELES_TESTER}")
        print(f"   Installés : {installes}")
        sys.exit(1)

    # En-tête
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    titre(f"BENCHMARK MULTILINGUE — WoW Translator  ({now})")
    print(f"  Locales   : {' | '.join(locales_cibles)}")
    print(f"  Modèles   : {' | '.join(modeles_dispo)}")
    print(f"  Textes    : {len(TEXTES_TEST)}")
    print(f"  Total     : {len(locales_cibles) * len(modeles_dispo) * len(TEXTES_TEST)} traductions")

    # Résultats globaux : {locale: {modele: [scores]}}
    resultats = {loc: {mod: [] for mod in modeles_dispo} for loc in locales_cibles}
    temps_tot = {loc: {mod: 0.0 for mod in modeles_dispo} for loc in locales_cibles}

    for locale in locales_cibles:
        emoji = EMOJI_LOCALE.get(locale, "🌍")
        lang  = LOCALES_DISPO[locale]

        for modele in modeles_dispo:
            titre(f"{emoji} {lang} ({locale})  ·  Modèle : {modele}", char="─")

            for t in TEXTES_TEST:
                trad, duree = traduire(t["en"], locale, modele)
                scoring     = score_traduction(t["en"], trad, locale)

                resultats[locale][modele].append(scoring["global"])
                temps_tot[locale][modele] += duree

                afficher_resultat(
                    t["id"], t["type"], t["en"],
                    locale, modele, trad, scoring, duree
                )

    # ── Tableau récapitulatif ──────────────────────────────────────────────────
    titre("RÉCAPITULATIF — Scores moyens par locale et modèle")

    col_w = 22
    header = f"{'Locale':<16}" + "".join(f"{m[:col_w]:<{col_w}}" for m in modeles_dispo)
    print(f"  {header}")
    ligne()

    gagnant_count = {m: 0 for m in modeles_dispo}

    for locale in locales_cibles:
        emoji = EMOJI_LOCALE.get(locale, "🌍")
        lang  = LOCALES_DISPO[locale]
        scores_par_modele = {
            m: sum(resultats[locale][m]) / len(resultats[locale][m])
            for m in modeles_dispo
        }
        meilleur = max(scores_par_modele, key=scores_par_modele.get)
        gagnant_count[meilleur] += 1

        row = f"  {emoji} {lang:<13}"
        for modele in modeles_dispo:
            s    = scores_par_modele[modele]
            t    = temps_tot[locale][modele]
            flag = " ✅" if modele == meilleur and len(modeles_dispo) > 1 else ""
            row += f"{s*100:5.1f}%  ({t:.0f}s){flag:<3}  "
        print(row)

    ligne()

    if len(modeles_dispo) > 1:
        print(f"\n  VERDICT :")
        for modele in modeles_dispo:
            print(f"    {modele:<20} → gagne sur {gagnant_count[modele]}/{len(locales_cibles)} locale(s)")

    # Recommandations
    titre("RECOMMANDATIONS")
    for locale in locales_cibles:
        if len(modeles_dispo) > 1:
            scores_par_modele = {
                m: sum(resultats[locale][m]) / len(resultats[locale][m])
                for m in modeles_dispo
            }
            meilleur = max(scores_par_modele, key=scores_par_modele.get)
            diff = max(scores_par_modele.values()) - min(scores_par_modele.values())
            emoji = EMOJI_LOCALE.get(locale, "🌍")
            lang  = LOCALES_DISPO[locale]
            if diff < 0.05:
                print(f"  {emoji} {lang:<20} → équivalent (diff {diff*100:.1f}%) — garder {meilleur} (plus rapide si applicable)")
            else:
                print(f"  {emoji} {lang:<20} → utiliser {meilleur} (+{diff*100:.1f}%)")

    print(f"\n  Rapport généré le {now}")
    ligne("═")


if __name__ == "__main__":
    main()
