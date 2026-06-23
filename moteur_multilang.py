"""
╔══════════════════════════════════════════════════════════════════╗
║   WoW Localization Engine — MOTEUR MULTILINGUE (moteur_multilang.py) ║
╚══════════════════════════════════════════════════════════════════╝

Étend TranslationEngine pour supporter plusieurs langues cibles.
Ne modifie PAS moteur.py original.
"""

import re
import logging
import importlib
from pathlib import Path

import config_manager
import ia_provider
from moteur import TranslationEngine
from wow_rules import ERREURS_COMMUNES, RESIDUS_POST_MARQUEUR, STATS_FORMAT

logger = logging.getLogger("Moteur-ML")


class ModeleManquantError(Exception):
    """Levée quand le modèle Ollama requis n'est pas installé."""
    def __init__(self, modele: str, locale: str):
        self.modele = modele
        self.locale = locale
        super().__init__(f"Modèle manquant : {modele} (requis pour {locale})")

# ── Chargement dynamique des règles depuis wow_rules_{locale}.py ──────────────
# Chaque fichier locale expose : MODELE_IA, LANG_NAME, LANG_RULES, CORRECTIONS
_LOCALES_SUPPORTEES = ["frFR", "esES", "deDE", "ruRU", "esMX", "zhCN"]

LANGUES_PROMPT         = {}   # locale → nom langue (prompt)
MODELE_PAR_LOCALE      = {}   # locale → modèle Ollama
LANGUES_REGLES         = {}   # locale → liste de règles prompt
CORRECTIONS_PAR_LOCALE = {}   # locale → [(regex, remplacement), ...]

for _loc in _LOCALES_SUPPORTEES:
    try:
        _mod = importlib.import_module(f"wow_rules_{_loc}")
        LANGUES_PROMPT[_loc]         = getattr(_mod, "LANG_NAME",   "French")
        MODELE_PAR_LOCALE[_loc]      = getattr(_mod, "MODELE_IA",   "mistral-nemo")
        LANGUES_REGLES[_loc]         = getattr(_mod, "LANG_RULES",  [])
        CORRECTIONS_PAR_LOCALE[_loc] = getattr(_mod, "CORRECTIONS", [])
        logger.debug(f"wow_rules_{_loc}.py chargé — modèle:{MODELE_PAR_LOCALE[_loc]}")
    except ImportError:
        logger.warning(f"wow_rules_{_loc}.py introuvable — locale {_loc} ignorée")

# (MODELE_PAR_LOCALE, LANGUES_REGLES, CORRECTIONS_PAR_LOCALE sont désormais
#  chargés dynamiquement depuis les fichiers wow_rules_{locale}.py ci-dessus)

# ── Emoji drapeaux par locale ─────────────────────────────────────────────────
LOCALE_EMOJI = {
    "frFR": "🇫🇷",
    "esES": "🇪🇸",
    "deDE": "🇩🇪",
    "ruRU": "🇷🇺",
    "esMX": "🇲🇽",
    "zhCN": "🇨🇳",
}

# ── Langues pour lesquelles on applique les post-corrections wow_rules ─────────
LOCALES_POST_CORRECTIONS = {"frFR"}



class MultiLangEngine(TranslationEngine):
    """
    TranslationEngine étendu avec support multilingue.
    Usage : engine = MultiLangEngine(locale="deDE")
    """

    def __init__(self, locale: str = "frFR", dict_path=None):
        self._ia_backend = ia_provider.get_backend()

        if self._ia_backend != "ollama":
            logger.info(f"Backend IA : {self._ia_backend} (modèle externe)")

        _base = Path(__file__).parent
        if dict_path is not None:
            _resolved = Path(dict_path)
        else:
            _locale_dict = _base / f"wow_dictionnaire_{locale}.json"
            _generic_dict = _base / "wow_dictionnaire.json"
            _resolved = _locale_dict if _locale_dict.exists() else _generic_dict
        super().__init__(dict_path=_resolved)
        self.locale          = locale
        self.target_language = LANGUES_PROMPT.get(locale, "French")
        self.lang_rules      = LANGUES_REGLES.get(locale, [])
        self.modele_ia       = MODELE_PAR_LOCALE.get(locale, "mistral-nemo")
        self._cache          = {}   # cache mémoire : texte_en → trad (par locale)
        logger.info(f"MultiLangEngine initialisé — locale: {locale} → {self.target_language} [{self.modele_ia}] (dict: {_resolved.name})")
        self._verifier_modele()

    def _verifier_modele(self):
        if self._ia_backend != "ollama":
            logger.info(f"Backend {self._ia_backend} — vérification modèle ignorée (API externe)")
            return
        try:
            modeles_installes = ia_provider.list_ollama_models()
            # Normaliser : "mistral-nemo:latest" et "mistral-nemo" sont le même modèle
            modeles_norm = [m.split(":")[0] for m in modeles_installes if m]
            modele_base  = self.modele_ia.split(":")[0]

            if modele_base not in modeles_norm:
                logger.error(
                    f"❌ MODÈLE MANQUANT : {self.modele_ia} "
                    f"(requis pour {self.locale} / {self.target_language}). "
                    f"Installés : {', '.join(modeles_installes) or 'aucun'}"
                )
                raise ModeleManquantError(self.modele_ia, self.locale)
            else:
                logger.info(f"✅ Modèle {self.modele_ia} disponible.")
        except ModeleManquantError:
            raise
        except Exception as e:
            logger.warning(f"⚠️ Impossible de vérifier les modèles Ollama : {e} — on continue.")

    def set_locale(self, locale: str):
        """Change la langue cible à chaud."""
        old = self.locale
        self.locale          = locale
        self.target_language = LANGUES_PROMPT.get(locale, "French")
        self.lang_rules      = LANGUES_REGLES.get(locale, [])
        self.modele_ia       = MODELE_PAR_LOCALE.get(locale, "mistral-nemo")
        self._cache          = {}   # vider le cache lors du changement de locale
        logger.info(f"Langue changée : {old} → {locale} ({self.target_language}) [{self.modele_ia}]")
        self._verifier_modele()

    def translate(self, text: str) -> str:
        original = text.strip()

        # ── Cache mémoire session ──────────────────────────────────────────────
        cache_key = f"{self.locale}:{original}"
        if cache_key in self._cache:
            logger.debug(f"Cache hit : {original[:40]!r}")
            return self._cache[cache_key]

        # ── Exact match dans le glossaire API ─────────────────────────────────
        if self.api_glossary:
            hit = self.api_glossary.get(original)
            if hit is None:
                hit = self.api_glossary.get(original.lower())
            if hit is None:
                orig_low = original.lower()
                for k, v in self.api_glossary.items():
                    if k.lower() == orig_low:
                        hit = v
                        break
            if hit:
                return hit

        lines            = original.split("\n")
        translated_lines = []

        _NO_TRANSLATE = re.compile(r"^[A-Z0-9][A-Z0-9/\-]{0,4}$")

        for line in lines:
            clean_line = line.strip()
            if not clean_line:
                translated_lines.append("")
                continue

            # ── Masquage des tags WoW ──────────────────────────────────────────
            # frFR : masquage complet (pattern TranslationEngine)
            # ruRU/zhCN : masquer aussi %s/%d → sinon qwen traduit %s en CJK mid-phrase
            # esES/deDE/esMX : ne pas masquer %s → sinon [T0] = "chance" traduit en CJK (esES)
            if self.locale == "frFR":
                tags = self._TAG_PATTERN.findall(clean_line)
            elif self.locale in ("ruRU", "zhCN"):
                tags = re.findall(r'\$[BbNn]|%s|%d|\|[TtHhcX][^|]*\|', clean_line)
            else:
                # esES, deDE, esMX : $B, $N et tags pipe uniquement — %s reste visible
                tags = re.findall(r'\$[BbNn]|\|[TtHhcX][^|]*\|', clean_line)
            texte_masque = clean_line
            for i, t in enumerate(tags):
                texte_masque = texte_masque.replace(t, f"[T{i}]", 1)

            texte_sans_tags = re.sub(r"\[T\d+\]", "", texte_masque)
            texte_lettres   = re.sub(r"[^a-zA-Z]", "", texte_sans_tags)

            if not texte_lettres:
                translated_lines.append(clean_line)
                continue
            if clean_line.startswith("/") and " " not in clean_line:
                translated_lines.append(clean_line)
                continue
            if _NO_TRANSLATE.match(texte_lettres):
                translated_lines.append(clean_line)
                continue
            if len(texte_lettres) <= 3 and texte_lettres.isupper():
                translated_lines.append(clean_line)
                continue

            # ── Construction du prompt ─────────────────────────────────────────
            # Chaque locale a maintenant son propre dictionnaire wow_dictionnaire_LOCALE.json
            active_rules = self._get_smart_context(clean_line)

            lang_specific = " ".join(self.lang_rules)

            sys_rules = (
                f"You are an expert Blizzard WoW localization specialist. "
                f"Translate the following World of Warcraft text into {self.target_language}. "
                f"MANDATORY RULES — follow ALL of them without exception: "
                f"RULE 1. {lang_specific} "
                f"RULE 2. ALL [T0] [T1] [T2] placeholders are UNTRANSLATABLE — copy them verbatim, never change or rename them. "
                f"RULE 3. $B, $b, $N, $n, %s and ALL format codes — copy exactly as-is. "
                f"RULE 4. Output in {self.target_language} ONLY. No English words left untranslated. "
                f"RULE 5. Output ONLY the translated text. No notes, no comments, no explanations. "
                f"RULE 6. Translate the ENTIRE text completely."
            )
            if active_rules:
                sys_rules += " Mandatory WoW terms: " + ", ".join(active_rules) + "."

            # Map locale → code langue pour le prompt
            _LANG_CODE_MAP = {
                "frFR": "FR", "esES": "ES", "deDE": "DE",
                "ruRU": "RU", "esMX": "ES", "zhCN": "ZH",
            }
            lang_code = _LANG_CODE_MAP.get(self.locale, self.locale[:2].upper())
            # Rappel CRITIC dans le prompt pour les placeholders [Tx]
            nb_tags = len(tags)
            tags_list = " ".join(f"[T{i}]" for i in range(nb_tags)) if nb_tags else ""
            tags_reminder = (
                f" CRITICAL REMINDER: This text contains {nb_tags} format code(s): {tags_list}. "
                f"They are NOT words — they are untouchable game placeholders. "
                f"Output them EXACTLY as written: {tags_list}. "
                f"NEVER translate, replace, or omit them."
            ) if nb_tags > 0 else ""
            prompt = f"{sys_rules}{tags_reminder}\n\nEN: {texte_masque}\n{lang_code}:"

            # ── Appel IA ───────────────────────────────────────────────────────
            trad       = None
            cjk_retry  = False   # True après 1er retry anti-CJK
            len_retry   = False   # True si la traduction précédente était trop courte
            # Seuil min de longueur : 20% des caractères source (hors tags)
            _min_len = max(3, int(len(texte_lettres) * 0.20))
            for tentative in range(4):  # 4 tentatives : +1 pour retry longueur
                try:
                    # Sur un retry anti-CJK : ajouter instruction + température=0.05
                    prompt_courant = prompt
                    temp_courant   = 0.0
                    num_predict    = 1024
                    if cjk_retry:
                        prompt_courant = (
                            f"CRITICAL: Write ONLY in {self.target_language}. "
                            f"Do NOT write any Chinese, Japanese, or Russian characters. "
                            f"Output MUST be in {self.target_language} script only.\n"
                        ) + prompt
                        temp_courant = 0.05
                    if len_retry:
                        # Trad trop courte — forcer une sortie complète
                        prompt_courant = (
                            f"IMPORTANT: Your previous translation was INCOMPLETE. "
                            f"Translate the ENTIRE text — do NOT stop after a few words.\n"
                        ) + prompt
                        temp_courant = 0.05
                        num_predict  = 1024  # plus de tokens pour ne pas tronquer

                    ia_options = {
                            "temperature":    temp_courant,
                            "num_gpu":        99,
                            "num_ctx":        768,
                            "repeat_penalty": 1.1 + (0.05 if (cjk_retry or len_retry) else 0),
                            "num_predict":    num_predict,
                            "stop":           ["\nEN:", f"\n{lang_code}:", "\nNote:", "\nCorrected Final Translation:", "\n注意", "\n所以正确的翻译应该是：", "Translation:", "\nПримечание:", "\nПеревод:", "\nNota:", "\nHinweis:"],
                        }
                    ia_model = ia_provider.get_model(override=self.modele_ia) if ia_provider.is_local() else ia_provider.get_model()
                    raw = ia_provider.chat(
                        model=ia_model,
                        messages=[{"role": "user", "content": prompt_courant}],
                        options=ia_options,
                    )
                    raw = re.sub(rf'^{lang_code}:\s*', '', raw).strip()
                    raw = re.sub(r'^[A-Z]{2}:\s*', '', raw).strip()
                    trad = raw.replace('"', "")

                    # Anti-hallucination : couper si le modèle commence à expliquer
                    _HALLUC = [
                        "note:", "примечание:", "注意:", "nota:", "hinweis:",
                        "translation:", "перевод:", "traducción:", "übersetzung:",
                        "here is", "here's", "voici", "aquí está",
                        "as an ai", "je suis", "в предоставленных правилах",
                        "corrected final", "so the correct translation",
                    ]
                    trad_check = trad.lower()
                    for marker in _HALLUC:
                        pos = trad_check.find(marker)
                        if pos != -1:
                            cleaned = trad[:pos].strip().rstrip(".,;:—-")
                            if cleaned:
                                logger.warning(f"⚠️ Hallucination coupée à '{marker}' — gardé : {cleaned[:50]}")
                                trad = cleaned
                            else:
                                trad = None
                            break
                    if trad is None:
                        if tentative < 3:
                            continue
                        translated_lines.append(clean_line)
                        continue

                    # Détecter CJK parasite dans les locales non-CJK
                    if self.locale != "zhCN" and re.search(r'[\u4e00-\u9fff\u3040-\u30ff]', trad):
                        logger.warning(f"⚠️ CJK parasite ({self.locale}) — tentative {tentative+1}/4")
                        if tentative < 3:
                            cjk_retry = True
                            trad = None
                            continue
                        else:
                            # Dernière tentative : nettoyer agressivement
                            trad = re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\u3000-\u303f].*', '', trad, flags=re.DOTALL).strip()
                            trad = re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\u3000-\u303f]+', '', trad).strip()

                    # Détecter traduction trop courte (troncature du modèle)
                    trad_lettres = re.sub(r"[^a-zA-ZÀ-ÿа-яА-ЯёЁ\u4e00-\u9fff]", "", trad)
                    if len(trad_lettres) < _min_len and len(texte_lettres) >= 8:
                        logger.warning(
                            f"⚠️ Trad trop courte ({self.locale}) — "
                            f"{len(trad_lettres)} chars vs {_min_len} min — tentative {tentative+1}/4"
                        )
                        if tentative < 3:
                            len_retry = True
                            trad = None
                            continue

                    break
                except Exception as e:
                    logger.warning(f"Tentative IA {tentative+1}/4 échouée : {e}")
                    if tentative == 3:
                        translated_lines.append(clean_line)
                        trad = None

            if trad is None:
                continue

            # ── Réparation masques corrompus ───────────────────────────────────
            # Formes malformées : T0] ou [T0 ou [ T 0 ]
            trad = re.sub(r"(?<!\[)\bT(\d+)\]", r"[T\1]", trad)
            trad = re.sub(r"\[T(\d+)(?!\])",     r"[T\1]", trad)
            trad = re.sub(r"\[\s*T\s*(\d+)\s*\]", r"[T\1]", trad)
            # Cas : modèle a renommé [Tx] → [Cx], [Nx], [Ax], [Bx] etc. (qwen2.5)
            trad = re.sub(r"\[([A-Z])(\d+)\]",   r"[T\2]", trad)
            # Cas : modèle a écrit [Tx] littéralement (x générique) avec 1 seul tag
            if len(tags) == 1 and "[Tx]" in trad and "[T0]" not in trad:
                trad = trad.replace("[Tx]", "[T0]")

            # ── Recovery $B : si mistral-nemo a remplacé [Tx] par des newlines ──
            if tags and all(t == '$B' for t in tags):
                nb_nl = trad.count('\n')
                if nb_nl == len(tags) and not any(f"[T{i}]" in trad for i in range(len(tags))):
                    trad = trad.replace('\n', '$B')

            # ── Cris (MAJUSCULES) ──────────────────────────────────────────────
            if texte_lettres and texte_lettres.isupper():
                trad = trad.upper()

            # ── Restauration des tags ──────────────────────────────────────────
            for i, t in enumerate(tags):
                trad = trad.replace(f"[T{i}]", t)

            # ── Récupération tags totalement perdus ────────────────────────────
            # Si après restauration un tag original est absent, on le réappend
            for i, t in enumerate(tags):
                if t in (r"$N", r"$n") and t not in trad:
                    # $N est généralement en fin/début de phrase — on l'injecte
                    pass  # Pas d'injection automatique, trop risqué pour le sens

            # ── Post-corrections frFR (wow_rules) ────────────────────────────
            if self.locale in LOCALES_POST_CORRECTIONS:
                for err, corr in ERREURS_COMMUNES.items():
                    trad = trad.replace(err, corr)
                for pat, rep in RESIDUS_POST_MARQUEUR:
                    trad = re.sub(pat, rep, trad)
                for pat, rep in STATS_FORMAT:
                    trad = re.sub(pat, rep, trad, flags=re.IGNORECASE)

            # ── Post-corrections spécifiques à la locale (esES, deDE…) ──────────
            if self.locale in CORRECTIONS_PAR_LOCALE:
                for pat, rep in CORRECTIONS_PAR_LOCALE[self.locale]:
                    trad = re.sub(pat, rep, trad)

            # ── Nettoyage typographique ────────────────────────────────────────
            trad = trad.replace("…", "...")
            trad = re.sub(r"\s+([!?:;])", r"\1", trad)

            # ── Notes/commentaires IA (nettoyage renforcé) ───────────────────
            # Blocs "Note:", "Note que", "Remarque:", "Corrected:", "[Note:...]"
            trad = re.sub(r"\s*\(Note\s*:[^)]*\)\.?\s*",     " ", trad).strip()
            trad = re.sub(r"\s*\[Note\s*:[^\]]*\]\.?\s*",     " ", trad).strip()
            trad = re.sub(r"\s*\(Remarque\s*:[^)]*\)\.?\s*",  " ", trad).strip()
            trad = re.sub(r"\n+Note\s*:.*",                   "",  trad, flags=re.DOTALL).strip()
            trad = re.sub(r"\n+\[Note\s*:.*",                 "",  trad, flags=re.DOTALL).strip()
            trad = re.sub(r"\n+Note\s+que\s.*",               "",  trad, flags=re.DOTALL).strip()
            trad = re.sub(r"\n+Nota\s*:.*",                   "",  trad, flags=re.DOTALL).strip()
            trad = re.sub(r"\n+Nota\s+que\s.*",               "",  trad, flags=re.DOTALL).strip()
            trad = re.sub(r"\n+Corrected\s*:.*",              "",  trad, flags=re.DOTALL).strip()
            trad = re.sub(r"\n+Correction\s*:.*",             "",  trad, flags=re.DOTALL).strip()
            trad = re.sub(r"\n+Translation\s*:.*",            "",  trad, flags=re.DOTALL).strip()
            trad = re.sub(r"\n+PT-BR\s*:.*",                  "",  trad, flags=re.DOTALL).strip()
            trad = re.sub(r"\n+ZH\s*:.*",                     "",  trad, flags=re.DOTALL).strip()
            # Blocs multilignes après une ligne vide (ex: "\n\n[Note: ..." ou "\n\nNote que...")
            trad = re.sub(r"\n{2,}[\[\(]?[A-Z][^:]{0,30}:.*","",  trad, flags=re.DOTALL).strip()
            # Phrases parasites en fin : "Since there's no...", "There is no text...", etc.
            trad = re.sub(
                r"\s*(Since|There is|There are|The original|Please provide|As there|"
                r"Note that|Keep in mind|I should|I will|I cannot)[^.]*\.?",
                "", trad, flags=re.IGNORECASE
            ).strip()

            # ── $B$B inventés ──────────────────────────────────────────────────
            if not clean_line.startswith("$"):
                trad = re.sub(r"^\$[Bb]\$[Bb]\s*", "", trad)

            # ── Cohérence délimiteurs ──────────────────────────────────────────
            if clean_line.startswith("<") and not trad.startswith("<"):
                trad = "<" + trad
            if clean_line.endswith(">") and not trad.endswith(">"):
                trad = trad + ">"
            if clean_line.startswith('"') and not trad.startswith('"'):
                trad = '"' + trad
            if clean_line.endswith('"') and not trad.endswith('"'):
                trad = trad + '"'

            # ── Ponctuation finale ─────────────────────────────────────────────
            punctuations = ["...", ".", "!", "?", '",', '"']
            if any(clean_line.endswith(p) for p in punctuations):
                for punct in punctuations:
                    if clean_line.endswith(punct):
                        trad = re.sub(r"[\.\:\!\?]+$", "", trad).strip()
                        if not trad.endswith(punct):
                            trad += punct
                        break
            else:
                if not trad.endswith(">") and not trad.endswith('"'):
                    trad = re.sub(r"[\.\!\?]+$", "", trad).strip()

            translated_lines.append(trad)

        result = "\n".join(translated_lines)

        # ── Mise en cache (max 2000 entrées pour éviter fuite mémoire) ────────
        if len(self._cache) >= 2000:
            keys_to_delete = list(self._cache.keys())[:200]
            for k in keys_to_delete:
                del self._cache[k]
        self._cache[cache_key] = result

        return result

    def auto_evaluer(self, texte_en: str, texte_traduit: str) -> int:
        """
        Demande au modèle d'évaluer sa propre traduction entre 0 et 100.
        Retourne le score estimé ou 100 si l'évaluation échoue.
        """
        if not config_manager.get_bool("traduction", "auto_evaluation", False):
            return 100

        if not texte_en.strip() or not texte_traduit.strip():
            return 100

        lettres_en = re.sub(r"[^a-zA-Z]", "", texte_en)
        if len(lettres_en) <= 5:
            return 100

        prompt_eval = (
            f"You are a World of Warcraft localization quality reviewer.\n"
            f"Rate the following translation from English to {self.target_language} "
            f"on a scale of 0 to 100.\n"
            f"Consider: accuracy, natural flow, WoW terminology, abbreviations preserved.\n"
            f"If the original is an abbreviation or proper noun that should NOT be translated, "
            f"and the translation changed it, score it below 50.\n"
            f"Reply with ONLY a number between 0 and 100.\n\n"
            f"English: {texte_en}\n"
            f"{self.target_language}: {texte_traduit}\n"
            f"Score:"
        )

        try:
            eval_model = ia_provider.get_model(override=self.modele_ia) if ia_provider.is_local() else ia_provider.get_model()
            raw = ia_provider.chat(
                model=eval_model,
                messages=[{"role": "user", "content": prompt_eval}],
                options={
                    "temperature": 0.0,
                    "num_gpu": 99,
                    "num_ctx": 512,
                    "num_predict": 8,
                },
            )
            score = int(re.search(r"\d+", raw).group())
            return max(0, min(100, score))
        except Exception as e:
            logger.warning(f"Auto-évaluation échouée : {e}")
            return 100
