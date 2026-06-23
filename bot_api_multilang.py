"""
╔══════════════════════════════════════════════════════════════════╗
║   WoW Localization Engine — BOT API MULTILINGUE (bot_api_multilang.py) ║
╚══════════════════════════════════════════════════════════════════╝

Version multilingue de bot_api.py.
Ne modifie PAS bot_api.py original.
"""

import os
import time
import random
import json
import requests
import logging
import sys
import socket
import concurrent.futures
import collections
from datetime import datetime
from pathlib import Path

from moteur_multilang import MultiLangEngine, LANGUES_PROMPT, LOCALE_EMOJI
import config_manager

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

API_BASE_URL = config_manager.get("api", "base_url")

LOCALE = config_manager.get("general", "langue_defaut")

LIMIT               = 100
ENDPOINT_SUBMIT     = f"{API_BASE_URL}/api/v1/account/submissions"
ENDPOINT_BULK       = f"{API_BASE_URL}/api/v1/account/submissions/bulk"

SAUVEGARDE_INTERVAL = config_manager.get_int("traduction", "sauvegarde_interval", 50)
TIMEOUT_TRADUCTION  = config_manager.get_int("traduction", "timeout", 35)
BULK_SIZE           = config_manager.get_int("traduction", "bulk_size", 20)

RATE_LIMIT_MAX    = config_manager.get_int("api", "rate_limit_max", 28)
RATE_LIMIT_FENETRE = config_manager.get_int("api", "rate_limit_fenetre", 60)


class RateLimiter:
    def __init__(self, max_requetes=RATE_LIMIT_MAX, fenetre=RATE_LIMIT_FENETRE):
        self.max_requetes = max_requetes
        self.fenetre      = fenetre
        self.timestamps   = collections.deque()

    def attendre(self):
        maintenant = time.time()
        while self.timestamps and maintenant - self.timestamps[0] > self.fenetre:
            self.timestamps.popleft()
            
        if len(self.timestamps) >= self.max_requetes:
            attente = self.fenetre - (maintenant - self.timestamps[0]) + 0.5
            if attente > 0:
                logger.info(f"🚦 Rate limit ({self.max_requetes} POST/min) — pause de {attente:.1f}s...")
                time.sleep(attente)
        
        self.timestamps.append(time.time())


LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("API-Bot-ML")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _h = logging.FileHandler(LOGS_DIR / "api_production.log", encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s │ [API-ML] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(_h)



class WoWAPIApp:
    def __init__(self, credentials=None, locale: str = LOCALE):
        if credentials is None:
            credentials = {}

        self.locale       = locale
        self.engine       = MultiLangEngine(locale=locale)
        self.current_offset = 0
        self.processed_ids  = set()
        self.running        = True
        self.trads_reussies = 0
        self.rate_limiter   = RateLimiter()

        self.historique_trads = []
        self.start_time       = time.time()

        self.api_token   = credentials.get("token")
        self.webhook_url = credentials.get("webhook")
        self.wow_user    = credentials.get("user", "Inconnu")

        self.session = requests.Session()
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type":  "application/json",
            "Accept":        "application/json",
        }
        self.session.headers.update(self.headers)

        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.fichier_rapport = LOGS_DIR / f"Session_API_{self.locale}_{date_str}.txt"

        self._charger_parachute()

        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        lang  = LANGUES_PROMPT.get(self.locale, self.locale)
        logger.info(f"{emoji} Bot initialisé pour la locale : {self.locale} ({lang})")

    # ── Endpoints dynamiques ──────────────────────────────────────────────────
    @property
    def endpoint_get_base(self):
        return f"{API_BASE_URL}/api/v1/translations/untranslated?locale={self.locale}&limit={LIMIT}"

    @property
    def endpoint_glossary(self):
        return f"{API_BASE_URL}/api/v1/glossary/export?locale={self.locale}&format=flat_map&type=all&limit=200000"

    # ── Changement de locale à chaud ──────────────────────────────────────────
    def changer_locale(self, new_locale: str):
        old_locale = self.locale
        self.locale = new_locale
        self.engine.set_locale(new_locale)
        self.current_offset = 0
        self.processed_ids  = set()
        emoji = LOCALE_EMOJI.get(new_locale, "🌍")
        lang  = LANGUES_PROMPT.get(new_locale, new_locale)
        logger.info(f"🌍 Langue changée : {old_locale} → {new_locale} ({lang}) {emoji}")
        logger.info(f"🔄 Offset remis à 0 — IDs mémoire effacés")
        self._charger_glossaire()

    # ── Parachute ─────────────────────────────────────────────────────────────
    def _charger_parachute(self):
        parachute = BASE_DIR / f"parachute_{self.locale}.json"
        if not parachute.exists():
            logger.info(f"🆕 Aucun parachute pour {self.locale} — démarrage à zéro.")
            return
        try:
            with open(parachute, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.current_offset = data.get("offset", 0)
            self.processed_ids  = set(data.get("processed_ids", []))
            self.trads_reussies = data.get("trads_reussies", 0)
            saved_at            = data.get("saved_at", "?")
            logger.info(
                f"🪂 PARACHUTE [{self.locale}] — "
                f"Offset {self.current_offset} | "
                f"{len(self.processed_ids)} IDs | "
                f"{self.trads_reussies} trad. | "
                f"Sauvé le {saved_at}"
            )
        except Exception as e:
            logger.warning(f"⚠️ Parachute illisible ({self.locale}), démarrage à zéro : {e}")

    def _sauvegarder_parachute(self):
        parachute = BASE_DIR / f"parachute_{self.locale}.json"
        try:
            data = {
                "locale":        self.locale,
                "offset":        self.current_offset,
                "processed_ids": list(self.processed_ids),
                "trads_reussies": self.trads_reussies,
                "saved_at":      datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            with open(parachute, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(
                f"💾 Parachute [{self.locale}] — Offset: {self.current_offset} | IDs: {len(self.processed_ids)}"
            )
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde parachute : {e}")

    # ── Traduction avec timeout ───────────────────────────────────────────────
    def _traduire_avec_timeout(self, txt_en: str) -> str | None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.engine.translate, txt_en)
            try:
                return future.result(timeout=TIMEOUT_TRADUCTION)
            except concurrent.futures.TimeoutError:
                logger.error(
                    f"⏱️ TIMEOUT ({TIMEOUT_TRADUCTION}s) — Ollama ne répond plus ! Texte ignoré."
                )
                return None
            except Exception as e:
                logger.error(f"❌ Erreur inattendue traduction : {e}")
                return None

    def _duree_session(self):
        duree = int(time.time() - self.start_time)
        h, m  = duree // 3600, (duree % 3600) // 60
        return f"{h}h{m:02d}min" if h else f"{m}min"

    def enregistrer_traduction(self, txt_en, txt_trad):
        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        with open(self.fichier_rapport, "a", encoding="utf-8") as f:
            f.write(f"🇬🇧 {txt_en}\n{emoji} {txt_trad}\n{'-'*50}\n")

    def envoyer_rapport_discord(self):
        logger.info("📡 Préparation envoi rapport Discord...")
        if not self.webhook_url:
            return
        if not self.fichier_rapport.exists() or self.fichier_rapport.stat().st_size == 0:
            try:
                self.fichier_rapport.unlink()
            except:
                pass
            return
        pc_name = socket.gethostname()
        emoji   = LOCALE_EMOJI.get(self.locale, "🌍")
        lang    = LANGUES_PROMPT.get(self.locale, self.locale)
        try:
            with open(self.fichier_rapport, "rb") as f:
                contenu = f.read()
            files = {"file": (self.fichier_rapport.name, contenu, "text/plain")}
            dp    = self.trads_reussies * 0.1
            data  = {"content": (
                f"📁 **[{self.wow_user} | {pc_name}]** Session API [{emoji} {lang}] terminée.\n"
                f"✅ **{self.trads_reussies}** traductions  |  💰 **{dp:.2f} DP**  |  ⏱️ {self._duree_session()}"
            )}
            reponse = requests.post(self.webhook_url, data=data, files=files, timeout=15)
            if reponse.status_code in [200, 201, 204]:
                try:
                    self.fichier_rapport.unlink()
                except:
                    pass
        except Exception as e:
            logger.error(f"❌ Erreur Discord : {e}")

    # ── Requête blindée ───────────────────────────────────────────────────────
    def _requete_blindee(self, method, url, **kwargs):
        kwargs["timeout"] = 30 if method.upper() == "POST" else 15
        if "headers" in kwargs:
            del kwargs["headers"]
        for essai in range(3):
            try:
                if method.upper() == "GET":
                    return self.session.get(url, **kwargs)
                else:
                    return self.session.post(url, **kwargs)
            except Exception as e:
                logger.warning(f"⚠️ Erreur réseau {method} ({essai+1}/3) : {type(e).__name__} — {e}")
                time.sleep(5)
        raise Exception(f"Impossible de joindre l'API après 3 tentatives ({method}).")

    # ── Submit bulk ───────────────────────────────────────────────────────────
    def _soumettre_bulk(self, buffer: list) -> int:
        if not buffer:
            return 0

        payload = {
            "locale": self.locale,
            "items": [
                {"translation_id": item["translation_id"], "value": item["value"]}
                for item in buffer
            ],
        }

        self.rate_limiter.attendre()

        try:
            resp = self._requete_blindee("POST", ENDPOINT_BULK, json=payload)
        except Exception as e:
            logger.error(f"❌ Bulk POST échoué : {e} — {len(buffer)} items blacklistés.")
            for item in buffer:
                self.processed_ids.add(item["translation_id"])
            return 0

        if resp.status_code == 429:
            logger.warning("🛑 Rate limit 429 sur bulk — pause 10s et retry...")
            time.sleep(10)
            self.rate_limiter.attendre()
            try:
                resp = self._requete_blindee("POST", ENDPOINT_BULK, json=payload)
            except Exception as e:
                logger.error(f"❌ Retry bulk échoué : {e}")
                return 0

        acceptes = 0
        if resp.status_code in [200, 201, 202]:
            emoji = LOCALE_EMOJI.get(self.locale, "🌍")
            for item in buffer:
                self.processed_ids.add(item["translation_id"])
                self.enregistrer_traduction(item["en"], item["value"])
                self.historique_trads.append({
                    "en":     item["en"],
                    "fr":     item["value"],
                    "locale": self.locale,
                    "emoji":  emoji,
                })
                acceptes += 1
            if len(self.historique_trads) > 200:
                self.historique_trads = self.historique_trads[-200:]
            self.trads_reussies += acceptes
            logger.info(
                f"✅ Bulk [{self.locale}] — {acceptes}/{len(buffer)} acceptées | "
                f"Session : {self.trads_reussies}"
            )
            if self.trads_reussies % SAUVEGARDE_INTERVAL == 0:
                self._sauvegarder_parachute()
        else:
            logger.error(f"❌ Bulk rejeté (Code {resp.status_code}) : {resp.text[:200]}")
            for item in buffer:
                self.processed_ids.add(item["translation_id"])

        return acceptes

    # ── Chargement glossaire ──────────────────────────────────────────────────
    def _charger_glossaire(self):
        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        logger.info(f"📖 Chargement glossaire [{emoji} {self.locale}]...")
        try:
            resp = self._requete_blindee("GET", self.endpoint_glossary)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict):
                    entries = data.get("entries", data)
                    self.engine.api_glossary = {
                        k: v for k, v in entries.items()
                        if isinstance(k, str) and isinstance(v, str)
                        and k.lower() != v.lower()
                    }
                    logger.info(
                        f"✅ Glossaire [{self.locale}] — "
                        f"{len(self.engine.api_glossary)} paires injectées"
                    )
                else:
                    logger.warning(f"⚠️ Format inattendu glossaire : {type(data)}")
            else:
                logger.warning(f"⚠️ Glossaire non disponible (Code {resp.status_code})")
        except Exception as e:
            logger.warning(f"⚠️ Impossible de charger le glossaire : {e}")

    # ── Boucle principale ─────────────────────────────────────────────────────
    def run(self):
        if not self.api_token:
            logger.error("❌ ERREUR CRITIQUE : Aucun Token API fourni !")
            return

        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        lang  = LANGUES_PROMPT.get(self.locale, self.locale)
        logger.info(f"🚀 DÉMARRAGE BOT API MULTILINGUE [{self.wow_user}] {emoji} {lang}")
        logger.info(f"📍 Offset: {self.current_offset} | IDs mémoire: {len(self.processed_ids)}")
        logger.info(f"📦 Mode BULK activé — {BULK_SIZE} traductions par requête")

        self._charger_glossaire()

        try:
            while self.running:
                try:
                    fetch_url = f"{self.endpoint_get_base}&offset={self.current_offset}"
                    logger.info(
                        f"🔎 [{self.locale}] Recherche (Offset: {self.current_offset} | "
                        f"IDs: {len(self.processed_ids)})..."
                    )

                    response = self._requete_blindee("GET", fetch_url)

                    if response.status_code == 429:
                        logger.warning("⏳ [Anti-Spam] Pause 15s...")
                        time.sleep(15)
                        continue
                    if response.status_code != 200:
                        logger.warning(f"⚠️ Blocage API (Code {response.status_code})...")
                        time.sleep(5)
                        continue

                    data           = response.json()
                    total_restant  = data.get("missing_counts", {}).get(self.locale, "?") if isinstance(data, dict) else "?"
                    items_list     = data.get("rows", data) if isinstance(data, dict) else data

                    if not items_list:
                        logger.info(f"🔄 [{self.locale}] Base parcourue entièrement. Retour à l'offset 0.")
                        self.current_offset = 0
                        self._sauvegarder_parachute()
                        time.sleep(10)
                        continue

                    deja_traites = sum(1 for item in items_list if item.get("id") in self.processed_ids)
                    logger.info(
                        f"📊 [{self.locale}] LOT — {len(items_list)} textes | "
                        f"{deja_traites} déjà traités | "
                        f"{total_restant} restants | "
                        f"Session: {self.trads_reussies}"
                    )

                    if deja_traites == len(items_list):
                        logger.info("⏭️ Lot entièrement connu — avance offset.")
                        self.current_offset += LIMIT
                        continue

                    bulk_buffer = []

                    for item in items_list:
                        if not self.running:
                            break

                        text_id = item.get("id")
                        txt_en  = item.get("enUS")

                        if not txt_en or not text_id or text_id in self.processed_ids:
                            continue

                        traduction = self._traduire_avec_timeout(txt_en.strip())

                        if traduction is None:
                            self.processed_ids.add(text_id)
                            continue

                        if not traduction.strip():
                            traduction = txt_en

                        seuil = config_manager.get_int("traduction", "seuil_qualite", 90)
                        if config_manager.get_bool("traduction", "auto_evaluation"):
                            score = self.engine.auto_evaluer(txt_en.strip(), traduction)
                            if score < seuil:
                                logger.warning(
                                    f"🚫 Qualité insuffisante ({score}/100 < {seuil}) — "
                                    f"EN: {txt_en.strip()[:60]} → {traduction[:60]}"
                                )
                                self.processed_ids.add(text_id)
                                continue
                            elif score < 100:
                                logger.info(f"📊 Score qualité : {score}/100 — OK")

                        bulk_buffer.append({
                            "translation_id": text_id,
                            "value":          traduction,
                            "en":             txt_en.strip(),
                        })

                        if len(bulk_buffer) >= BULK_SIZE:
                            self._soumettre_bulk(bulk_buffer)
                            bulk_buffer = []

                    if bulk_buffer and self.running:
                        logger.info(f"📤 Envoi reste buffer ({len(bulk_buffer)} items)...")
                        self._soumettre_bulk(bulk_buffer)

                    self.current_offset += LIMIT

                except Exception as e:
                    logger.error(f"🔥 Erreur inattendue : {e}")
                    self._sauvegarder_parachute()
                    time.sleep(5)

        finally:
            logger.info(f"🛑 Arrêt [{self.locale}] — Sauvegarde finale...")
            self._sauvegarder_parachute()
            self.envoyer_rapport_discord()


if __name__ == "__main__":
    WoWAPIApp({"token": "TEST", "user": "TestUser"}, locale="frFR").run()
