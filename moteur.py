"""
╔══════════════════════════════════════════════════════════════════╗
║          WoW Localization Engine — CERVEAU CENTRAL (moteur.py)   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import re
import logging
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

try:
    from wow_rules import WOW_LEXICON, ERREURS_COMMUNES, RESIDUS_POST_MARQUEUR, STATS_FORMAT
except ImportError:
    print("❌ Erreur : Le fichier wow_rules.py est introuvable !")
    sys.exit(1)

# --- GESTION DES CHEMINS POUR LE .EXE ---
if getattr(sys, 'frozen', False):
    # Si on est un fichier .exe, on regarde le dossier où se trouve le .exe
    BASE_DIR = Path(sys.executable).parent
else:
    # Si on est un script Python normal, on regarde le dossier du script
    BASE_DIR = Path(__file__).parent

env_path = BASE_DIR / ".env"
# ... plus bas dans le code ...
DICT_FILE = BASE_DIR / "wow_dictionnaire.json"

load_dotenv(dotenv_path=env_path)

import ia_provider

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

timestamp = datetime.now().strftime("%d-%m-%Y_%Hh%M")
session_audit_file = LOGS_DIR / f"rapport_erreurs_{timestamp}.txt"

logging.basicConfig(level=logging.INFO, format="%(asctime)s │ %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("Moteur")

audit_logger = logging.getLogger("Audit-IA")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False 
audit_handler = logging.FileHandler(session_audit_file, encoding="utf-8")
audit_handler.setFormatter(logging.Formatter('%(message)s\n' + '-'*50))
audit_logger.addHandler(audit_handler)

with open(session_audit_file, "a", encoding="utf-8") as f:
    f.write(f"\n🚀 NOUVELLE SESSION - {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}\n{'='*50}\n")

class TranslationEngine:
    # ─── Compilé une seule fois au chargement de la classe ───────────────────
    _TAG_PATTERN = re.compile(
        r"("
        r"\$[gG]\s*[^:]+:[^;]+;"          # $g masculin:féminin;
        r"|\|T[^|]+\|\d*t"                 # |TInterface\Icons\...:20|t  (icônes)
        r"|\|H[^|]+\|h\[[^\]]*\]\|h"       # |Hspell:123|h[Nom Sort]|h  (hyperliens)
        r"|\|4[a-zA-ZÀ-ÿ]+:[a-zA-ZÀ-ÿ]+;" # |4seconde:secondes;         (pluriels Blizzard)
        r"|\|c[a-fA-F0-9]{8}"              # |cffFFFFFF                   (couleur début)
        r"|\|r"                             # |r                           (reset couleur)
        r"|\$[a-zA-Z]"                      # $N, $p, $B, $b — UN seul caractère
        r"|\%[sducfx]"                      # %s, %d, %u…
        r"|\\n"                             # \n littéral
        r"|\{[^}]+\}"                       # {variables}
        r")"
    )
    # ─────────────────────────────────────────────────────────────────────────

    def __init__(self, dict_path: Path = DICT_FILE):
        self.static_lexicon = WOW_LEXICON.copy()
        self.json_db = {}
        self.api_glossary = {}   # chargé dynamiquement depuis l'API au démarrage du bot
        try:
            with open(dict_path, encoding="utf-8") as f:
                self.json_db = json.load(f)
            logger.info(f"✅ Dictionnaire chargé ({len(self.json_db)} entrées).")
        except:
            logger.warning("⚠️ wow_dictionnaire.json non trouvé.")

    def _get_smart_context(self, text: str):
        """
        Retourne jusqu'à 15 règles de traduction pertinentes pour le texte.
        Priorité : lexique statique (WOW_LEXICON) > dictionnaire JSON.
        L'ordre est préservé (pas de set() qui mélange).
        """
        seen = {}  # clé EN → règle FR (évite les doublons en gardant le premier trouvé)
        text_lower = text.lower()

        # 1. Lexique statique en priorité
        for en, fr in self.static_lexicon.items():
            if en not in seen and en in text_lower:
                seen[en] = f"'{en.title()}'='{fr}'"

        # 2. Dictionnaire JSON local (entrées > 3 chars pour éviter le bruit)
        for en, fr in self.json_db.items():
            if en not in seen and len(en) > 3 and en.lower() in text_lower:
                seen[en] = f"'{en}'='{fr}'"

        # 3. Glossaire live de l'API (chargé au démarrage — priorité la plus basse)
        for en, fr in self.api_glossary.items():
            if en not in seen and len(en) > 2 and en.lower() in text_lower:
                seen[en] = f"'{en}'='{fr}'"

        return list(seen.values())[:15]

    def translate(self, text: str):
        original = text.strip()

        # ── Exact match dans le glossaire API (lookup direct, sans IA) ───────
        if self.api_glossary:
            hit = self.api_glossary.get(original)
            if hit is None:
                hit = self.api_glossary.get(original.lower())
            if hit is None:
                # recherche insensible à la casse
                orig_low = original.lower()
                for k, v in self.api_glossary.items():
                    if k.lower() == orig_low:
                        hit = v
                        break
            if hit:
                return hit

        lines = original.split('\n')
        translated_lines = []

        # Mots-clés qui ne nécessitent JAMAIS de traduction
        _NO_TRANSLATE = re.compile(
            r'^[A-Z0-9][A-Z0-9/\-]{0,4}$'  # PvP, NPC, AFK, GY, etc.
        )

        for line in lines:
            clean_line = line.strip()
            if not clean_line:
                translated_lines.append(""); continue

            # ── Masquage des tags WoW ──────────────────────────────────────
            tags = self._TAG_PATTERN.findall(clean_line)
            texte_masque = clean_line
            for i, t in enumerate(tags):
                texte_masque = texte_masque.replace(t, f"[T{i}]", 1)

            texte_sans_tags = re.sub(r'\[T\d+\]', '', texte_masque)
            texte_lettres = re.sub(r'[^a-zA-Z]', '', texte_sans_tags)

        # ── Skip si pas de contenu traduisible ────────────────────────
            if not texte_lettres:
                translated_lines.append(clean_line); continue
                
            # 🛑 NOUVEAU : On bloque les commandes macros (ex: /cancelform, /cast)
            # Si ça commence par un / et qu'il n'y a pas d'espace, on garde l'anglais !
            if clean_line.startswith('/') and ' ' not in clean_line:
                translated_lines.append(clean_line); continue

            if _NO_TRANSLATE.match(texte_lettres):
                translated_lines.append(clean_line); continue
            if len(texte_lettres) <= 3 and texte_lettres.isupper():
                translated_lines.append(clean_line); continue

            # ── Construction du prompt ────────────────────────────────────
            # ── Construction du prompt ────────────────────────────────────
            active_rules = self._get_smart_context(clean_line)
            sys_rules = (
                "You are a Blizzard localization expert. Translate naturally into French, "
                "respecting French syntax (Noun + Complement). "
                "CRITICAL RULES: "
                "1. NEVER invent text. "
                "2. Translate 'you' as 'vous', NEVER as 'votre personnage'. "
                "3. Translate 'healing done' as 'soins prodigués'. "
                "4. Reorder possessives ('Khadgar's Robe' -> 'Robe de Khadgar'). "
                "5. KEEP ALL inline quotation marks (\"\") exactly as they are in English. DO NOT use French quotes («»). "
                "6. $B, $b, $N, $n, %s and ALL [Tx] placeholders are UNTRANSLATABLE codes — copy them EXACTLY as-is. "
                "7. $B$B means paragraph break — translate the text before AND after it independently, keep the $B$B in place. "
                "8. French ONLY. No talk. Preserve exact punctuation. "
                "9. DO NOT correct English typos or spelling mistakes. "
                "10. Translate the ENTIRE sentence. NEVER leave untranslated English words in the output. "
                "11. PRESERVE EXACT CAPITALIZATION. Do not capitalize letters unless they are capitalized in the English text. "
                "12. NEVER add notes, comments, explanations or rules to your translation. Output ONLY the translated text. "
                "13. NEVER add $B or $b tags that are not present in the original English text. "
                "14. For compound names (e.g. 'Sky Vortex', 'Berserk Buff'), translate each word and keep logical French order."
            )
            if active_rules:
                sys_rules += " Mandatory terms: " + ", ".join(active_rules) + "."

            prompt = f"{sys_rules}\nEN: {texte_masque}\nFR:"

            # ── Appel IA avec retry (3 tentatives) ───────────────────────
            trad = None
            for tentative in range(3):
                try:
                    raw = ia_provider.chat(
                        model=ia_provider.get_model(override="mistral-nemo"),
                        messages=[{"role": "user", "content": prompt}],
                        options={"temperature": 0.0, "stop": ["EN:", "FR:"], "num_predict": 1024}
                    )
                    trad = raw.strip().replace('"', '')
                    break
                except Exception as e:
                    logger.warning(f"⚠️ Tentative IA {tentative+1}/3 échouée : {e}")
                    if tentative == 2:
                        logger.error(f"❌ IA indisponible après 3 tentatives. Ligne conservée en anglais.")
                        translated_lines.append(clean_line)
                        trad = None

            if trad is None:
                continue  # Fallback déjà ajouté dans la boucle retry

            # ── Réparation des masques corrompus par l'IA ────────────────
            # Cas 1 : T0] sans crochet ouvrant  → [T0]
            trad = re.sub(r'(?<!\[)\bT(\d+)\]', r'[T\1]', trad)
            # Cas 2 : [T0 sans crochet fermant  → [T0]
            trad = re.sub(r'\[T(\d+)(?!\])', r'[T\1]', trad)
            # Cas 3 : [ T0] ou [T 0] avec espace → [T0]
            trad = re.sub(r'\[\s*T\s*(\d+)\s*\]', r'[T\1]', trad)

            # 🗣️ GESTION DES CRIS (MAJUSCULES)
            # Si le texte source ne contient que des majuscules, on force la traduction en majuscules
            if texte_lettres and texte_lettres.isupper():
                trad = trad.upper()

            # ── Restauration des tags originaux ───────────────────────────
            for i, t in enumerate(tags):
                trad = trad.replace(f"[T{i}]", t)

            # ── Application des correctifs wow_rules ──────────────────────
            for err, corr in ERREURS_COMMUNES.items():
                trad = trad.replace(err, corr)
            for pat, rep in RESIDUS_POST_MARQUEUR:
                trad = re.sub(pat, rep, trad)
            for pat, rep in STATS_FORMAT:
                trad = re.sub(pat, rep, trad, flags=re.IGNORECASE)

            # ── Nettoyage typographique ───────────────────────────────────
            trad = trad.replace("…", "...")
            trad = re.sub(r'\s+([!?:;])', r'\1', trad)

            # ── Guillemets : "texte" → «texte» si l'original anglais utilisait "" ──
            # Seulement si le source EN avait des guillemets doubles encadrants
            if re.search(r'^"[^"]+"\s*$', clean_line) or re.search(r'(?<!\w)"([^"]+)"(?!\w)', clean_line):
                trad = re.sub(r'"([^"]+)"', r'«\1»', trad)

            # ── Suppression des notes/commentaires de l'IA ────────────────
            # L'IA ajoute parfois ses propres commentaires dans la traduction
            trad = re.sub(r'\s*\(Note\s*:[^)]*\)\.?\s*', ' ', trad).strip()
            trad = re.sub(r'\s*Règles appliquées\s*:.*', '', trad, flags=re.DOTALL).strip()
            trad = re.sub(r'\s*\(Remarque\s*:[^)]*\)\.?\s*', ' ', trad).strip()
            trad = re.sub(r'\n+Note\s*:.*', '', trad, flags=re.DOTALL).strip()

            # ── Suppression des $B$B inventés en début de ligne ───────────
            # Si l'original ne commence pas par $B/$b, la traduction ne doit pas
            if not clean_line.startswith('$'):
                trad = re.sub(r'^\$[Bb]\$[Bb]\s*', '', trad)

            # ── Cohérence des délimiteurs de début/fin ────────────────────
            if clean_line.startswith('<') and not trad.startswith('<'): trad = '<' + trad
            if clean_line.endswith('>') and not trad.endswith('>'): trad = trad + '>'
            if clean_line.startswith('"') and not trad.startswith('"'): trad = '"' + trad
            if clean_line.endswith('"') and not trad.endswith('"'): trad = trad + '"'

            # ── Cohérence de la ponctuation finale ────────────────────────
            punctuations = ["...", ".", "!", "?", '",', '"']
            if any(clean_line.endswith(p) for p in punctuations):
                for punct in punctuations:
                    if clean_line.endswith(punct):
                        trad = re.sub(r'[\.\:\!\?]+$', '', trad).strip()
                        if not trad.endswith(punct): trad += punct
                        break
            else:
                if not trad.endswith('>') and not trad.endswith('"'):
                    trad = re.sub(r'[\.\!\?]+$', '', trad).strip()

            translated_lines.append(trad)

        final = "\n".join(translated_lines)
        audit_logger.info(f"EN: {original}\nFR: {final}")
        return final