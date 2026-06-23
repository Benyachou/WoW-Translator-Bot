"""
╔══════════════════════════════════════════════════════════════════════╗
║  WoW Localization Engine — BOT PUZZLE MULTILINGUE (bot_auto_firefox_multilang.py) ║
╚══════════════════════════════════════════════════════════════════════╝

Version multilingue de bot_auto_firefox.py.
Navigue sur /profile pour changer la langue avant de rejoindre /puzzle.
Ne modifie PAS bot_auto_firefox.py original.
"""

import os
import time
import random
import logging
import sys
import socket
import requests
import concurrent.futures
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select

from moteur_multilang import MultiLangEngine, LANGUES_PROMPT, LOCALE_EMOJI
import config_manager

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

_api_base = config_manager.get("api", "base_url")
TARGET_URL    = f"{_api_base}/puzzle"
PROFILE_URL   = f"{_api_base}/profile"
SESSION_DIR   = BASE_DIR / "session_production"
TIMEOUT_TRADUCTION = config_manager.get_int("traduction", "timeout", 35)

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("Puzzle-Bot-ML")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _h = logging.FileHandler(LOGS_DIR / "api_production.log", encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s │ [PUZZLE-ML] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(_h)

# Map locale → valeur dans le select HTML du site
LOCALE_SELECT_VALUE = {
    "frFR": "frFR",
    "esES": "esES",
    "deDE": "deDE",
    "ruRU": "ruRU",
    "esMX": "esMX",
    "zhCN": "zhCN",
}

# Détection inverse : valeur select → locale
LOCALE_SELECT_MAP = {v: k for k, v in LOCALE_SELECT_VALUE.items()}

# Détection par nom de langue affiché sur la page
_LANG_DETECT = {
    "frFR": "french",
    "esES": "spanish",
    "deDE": "german",
    "ruRU": "russian",
    "esMX": "spanish (latin",
    "zhCN": "chinese",
}


class WoWApp:
    def __init__(self, credentials, locale: str = "frFR"):
        self.locale    = locale
        self.engine    = MultiLangEngine(locale=locale)
        self.running   = True
        self.driver    = None
        self.navigateur = "?"

        self.wow_user    = credentials.get("user")
        self.wow_pass    = credentials.get("pass")
        self.webhook_url = credentials.get("webhook")

        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.fichier_rapport = LOGS_DIR / f"Session_Firefox_{self.locale}_{date_str}.txt"

        SESSION_DIR.mkdir(parents=True, exist_ok=True)

        self.last_en_text     = ""
        self.last_action_time = time.time()
        self.trads_reussies   = 0
        self.historique_trads = []
        self.start_time       = time.time()

        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        lang  = LANGUES_PROMPT.get(self.locale, self.locale)
        logger.info(f"{emoji} Puzzle Bot initialisé — locale: {self.locale} ({lang})")

    # ─────────────────────────────────────────────────────────────────
    # 🌐 INITIALISATION DU NAVIGATEUR
    # ─────────────────────────────────────────────────────────────────
    def _init_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

        # Essai 1 : Edge
        try:
            from selenium.webdriver.edge.service import Service as EdgeService
            from selenium.webdriver.edge.options import Options as EdgeOptions
            from webdriver_manager.microsoft import EdgeChromiumManager

            opts = EdgeOptions()
            edge_profile = SESSION_DIR / "edge"
            edge_profile.mkdir(exist_ok=True)
            opts.add_argument(f"--user-data-dir={edge_profile}")
            opts.add_argument("--profile-directory=Default")
            opts.add_experimental_option("excludeSwitches", ["enable-logging"])

            self.driver    = webdriver.Edge(service=EdgeService(EdgeChromiumManager().install()), options=opts)
            self.navigateur = "Edge"
            logger.info("🌐 Navigateur : Microsoft Edge")
            return
        except Exception as e:
            logger.warning(f"Edge indisponible ({type(e).__name__}) — essai Chrome...")

        # Essai 2 : Chrome
        try:
            from selenium.webdriver.chrome.service import Service as ChromeService
            from selenium.webdriver.chrome.options import Options as ChromeOptions
            from webdriver_manager.chrome import ChromeDriverManager

            opts = ChromeOptions()
            chrome_profile = SESSION_DIR / "chrome"
            chrome_profile.mkdir(exist_ok=True)
            opts.add_argument(f"--user-data-dir={chrome_profile}")
            opts.add_experimental_option("excludeSwitches", ["enable-logging"])

            self.driver    = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=opts)
            self.navigateur = "Chrome"
            logger.info("🌐 Navigateur : Google Chrome")
            return
        except Exception as e:
            logger.warning(f"Chrome indisponible ({type(e).__name__}) — fallback Firefox...")

        # Fallback : Firefox
        from selenium.webdriver.firefox.service import Service as FirefoxService
        from webdriver_manager.firefox import GeckoDriverManager
        from selenium.webdriver.firefox.firefox_profile import FirefoxProfile

        firefox_profile_dir = SESSION_DIR / "firefox"
        firefox_profile_dir.mkdir(exist_ok=True)

        # Profil persistant avec cookies sauvegardés
        ff_profile = FirefoxProfile(str(firefox_profile_dir))
        ff_profile.set_preference("network.cookie.cookieBehavior", 0)       # accepter tous les cookies
        ff_profile.set_preference("network.cookie.lifetimePolicy", 0)        # garder jusqu'à expiration
        ff_profile.set_preference("browser.sessionstore.resume_from_crash", True)
        ff_profile.set_preference("browser.sessionstore.privacy_level", 0)

        opts = webdriver.FirefoxOptions()
        opts.profile = ff_profile

        self.driver    = webdriver.Firefox(service=FirefoxService(GeckoDriverManager().install()), options=opts)
        self.navigateur = "Firefox"
        logger.info("🌐 Navigateur : Firefox")

    def _browser_vivant(self):
        try:
            _ = self.driver.current_url
            return True
        except:
            return False

    # ─────────────────────────────────────────────────────────────────
    # 🔐 LOGIN
    # ─────────────────────────────────────────────────────────────────
    def _faire_login(self) -> bool:
        """Gère le login. Retourne True si connecté avec succès."""
        from selenium.webdriver.common.action_chains import ActionChains

        for tentative in range(4):
            try:
                # Rafraîchir la page login entre chaque essai (évite que les champs disparaissent)
                if tentative > 0:
                    self.driver.get(f"{_api_base}/login")
                    time.sleep(2)

                wait_login = WebDriverWait(self.driver, 15)

                user_box = wait_login.until(EC.presence_of_element_located((By.NAME, "username")))
                pass_box = wait_login.until(EC.presence_of_element_located((By.NAME, "password")))

                # Vider + remplir via ActionChains (plus fiable que JS inject)
                user_box.clear()
                time.sleep(0.5)
                user_box.click()
                time.sleep(0.2)
                for char in self.wow_user:
                    user_box.send_keys(char)
                    time.sleep(0.05)
                time.sleep(0.5)

                pass_box.clear()
                time.sleep(0.5)
                pass_box.click()
                time.sleep(0.2)
                for char in self.wow_pass:
                    pass_box.send_keys(char)
                    time.sleep(0.05)
                time.sleep(0.5)

                # Clic sur le bouton login
                try:
                    btn = wait_login.until(EC.element_to_be_clickable(
                        (By.XPATH, "//button[@type='submit'] | //button[contains(.,'Login')] | //button[contains(.,'Continue')]")
                    ))
                    btn.click()
                except:
                    pass_box.send_keys(Keys.RETURN)

                time.sleep(3)

                if "login" not in self.driver.current_url:
                    logger.info(f"🔐 Login OK — {self.driver.current_url}")
                    return True

                logger.warning(f"⚠️ Login tentative {tentative+1}/4 — encore sur /login, retry...")
                time.sleep(2)

            except Exception as e:
                logger.warning(f"⚠️ Erreur login tentative {tentative+1}/4 : {e}")
                time.sleep(2)

        logger.error("❌ Login échoué après 4 tentatives")
        return False

    # ─────────────────────────────────────────────────────────────────
    # 🚫 DÉTECTION COMPTE DÉSACTIVÉ
    # ─────────────────────────────────────────────────────────────────
    def _compte_desactive(self) -> bool:
        try:
            body = self.driver.find_element(By.TAG_NAME, "body").text
            if "Account Deactivated" in body or "account has been deactivated" in body.lower():
                logger.error(f"🚫 Compte désactivé pour cette locale ({self.locale}) — arrêt.")
                return True
        except:
            pass
        return False

    # ─────────────────────────────────────────────────────────────────
    # 🌍 CHANGEMENT DE LANGUE SUR LA PAGE PUZZLE
    # ─────────────────────────────────────────────────────────────────
    def _changer_langue_profil(self):
        """
        Navigue sur /profile, change Default Translation Language, clique Save,
        puis retourne sur /puzzle.
        """
        from selenium.webdriver.common.action_chains import ActionChains

        emoji      = LOCALE_EMOJI.get(self.locale, "🌍")
        lang       = LANGUES_PROMPT.get(self.locale, self.locale)
        select_val = LOCALE_SELECT_VALUE.get(self.locale, self.locale)

        logger.info(f"{emoji} Changement langue profil → {self.locale} ({lang})...")

        succes = False
        for tentative in range(3):
            try:
                self.driver.get(PROFILE_URL)
                time.sleep(2)
                wait = WebDriverWait(self.driver, 10)

                # Fermer toute popup/overlay qui bloquerait les clics
                try:
                    self.driver.execute_script(
                        "document.querySelectorAll('dialog,[role=dialog],[class*=modal],[class*=overlay]')"
                        ".forEach(el => el.remove());"
                    )
                except Exception:
                    pass

                # Select par id
                select_elem = wait.until(EC.presence_of_element_located((By.ID, "preferred-language")))

                # Sélection via JS (contourne les overlays)
                self.driver.execute_script(
                    "arguments[0].value = arguments[1]; "
                    "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                    select_elem, select_val
                )
                time.sleep(0.5)

                valeur_actuelle = select_elem.get_attribute("value")
                logger.info(f"🔍 Valeur select : {valeur_actuelle} (cible : {select_val})")

                if valeur_actuelle != select_val:
                    raise ValueError(f"Select n'a pas changé : {valeur_actuelle} ≠ {select_val}")

                # Cliquer Save via JS pour éviter les problèmes d'overlay
                save_btn = self.driver.find_element(
                    By.XPATH,
                    "//form[@action='/profile/preferences']//button[@type='submit']"
                )
                self.driver.execute_script("arguments[0].click();", save_btn)
                time.sleep(2)

                logger.info(f"✅ Langue profil sauvegardée → {self.locale} ({lang})")
                succes = True
                break

            except Exception as e:
                logger.warning(f"⚠️ Tentative {tentative+1}/3 changement langue profil : {e}")
                time.sleep(2)

        if not succes:
            logger.error(f"❌ Impossible de changer la langue profil vers {self.locale} après 3 tentatives — arrêt du bot.")
            self.running = False
            return

        # Retour sur /puzzle
        logger.info(f"🧩 Retour sur {TARGET_URL}...")
        self.driver.get(TARGET_URL)
        time.sleep(2)

    def _relancer_navigateur(self):
        if not self.running:
            return
        logger.warning(f"🔄 Navigateur fermé — redémarrage ({self.navigateur})...")
        try:
            self._init_driver()
            self.wait = WebDriverWait(self.driver, 15)
            self.driver.get(TARGET_URL)
            self.last_action_time = time.time()
            logger.info("✅ Navigateur relancé.")
        except Exception as e:
            logger.error(f"❌ Impossible de relancer le navigateur : {e}")
            time.sleep(10)

    # ─────────────────────────────────────────────────────────────────
    # 🧠 TRADUCTION AVEC TIMEOUT
    # ─────────────────────────────────────────────────────────────────
    def _traduire_avec_timeout(self, txt_en: str) -> str | None:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.engine.translate, txt_en)
            try:
                return future.result(timeout=TIMEOUT_TRADUCTION)
            except concurrent.futures.TimeoutError:
                logger.error(f"⏱️ TIMEOUT ({TIMEOUT_TRADUCTION}s) — Ollama ne répond plus !")
                return None
            except Exception as e:
                logger.error(f"❌ Erreur traduction : {e}")
                return None

    def enregistrer_traduction(self, txt_en, txt_trad):
        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        with open(self.fichier_rapport, "a", encoding="utf-8") as f:
            f.write(f"🇬🇧 {txt_en}\n{emoji} {txt_trad}\n{'-'*50}\n")

    def _duree_session(self):
        duree = int(time.time() - self.start_time)
        h, m  = duree // 3600, (duree % 3600) // 60
        return f"{h}h{m:02d}min" if h else f"{m}min"

    def envoyer_rapport_discord(self):
        if not self.webhook_url:
            return
        if not self.fichier_rapport.exists() or self.fichier_rapport.stat().st_size == 0:
            return
        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        lang  = LANGUES_PROMPT.get(self.locale, self.locale)
        try:
            with open(self.fichier_rapport, "rb") as f:
                contenu = f.read()
            files = {"file": (self.fichier_rapport.name, contenu, "text/plain")}
            dp    = self.trads_reussies * 0.5
            data  = {"content": (
                f"📁 **[{self.wow_user} | {socket.gethostname()}]** "
                f"Session Puzzle [{emoji} {lang}] terminée.\n"
                f"✅ **{self.trads_reussies}** traductions  |  💰 **{dp:.2f} DP**  |  ⏱️ {self._duree_session()}"
            )}
            requests.post(self.webhook_url, data=data, files=files, timeout=15)
            logger.info("✅ Rapport Discord envoyé.")
        except Exception as e:
            logger.error(f"❌ Erreur Discord : {e}")

    def _ouvrir_cloche(self):
        script = """
        let bell = document.getElementById('alert-bell');
        if (bell) { bell.click(); return true; }
        bell = document.querySelector('[title="Notifications"], [title="Notification"]');
        if (bell) { bell.click(); return true; }
        bell = document.querySelector('[class*="bell"], [aria-label*="Notification" i]');
        if (bell) { bell.closest('button') ? bell.closest('button').click() : bell.click(); return true; }
        return false;
        """
        return self.driver.execute_script(script)

    def _detecter_locale_page(self):
        """Détecte la locale depuis l'URL (?locale=ruRU) ou le sélecteur Language sur la page."""
        import re as _re
        url = self.driver.current_url
        m = _re.search(r'locale=([a-zA-Z]{4})', url)
        if m:
            return m.group(1)
        try:
            selects = self.driver.find_elements(By.TAG_NAME, "select")
            for sel in selects:
                val = sel.get_attribute("value") or ""
                if val in LOCALE_SELECT_MAP:
                    return LOCALE_SELECT_MAP[val]
                text = sel.text.lower()
                for locale, name in _LANG_DETECT.items():
                    if name in text:
                        return locale
        except Exception:
            pass
        return None

    def _verifier_notifications_et_reparer(self):
        """Vérifie la cloche, scanne tous les rejets, groupe par locale, charge 1 dico à la fois, corrige et soumet."""
        repaired = 0
        try:
            current_url = self.driver.current_url
            home_url = _api_base

            # ── Phase 1 : Scanner toutes les notifications et collecter les URLs ──
            self.driver.get(home_url)
            time.sleep(2)

            if not self._ouvrir_cloche():
                logger.info("🔔 Cloche non trouvée")
                self.driver.get(current_url)
                return False

            time.sleep(1.5)

            # Récupérer les liens "Revisit in Puzzle" avec leurs hrefs
            revisit_links = self.driver.find_elements(By.XPATH,
                "//a[contains(., 'Revisit in Puzzle')]")
            revisit_buttons = self.driver.find_elements(By.XPATH,
                "//button[contains(., 'Revisit in Puzzle')]")

            urls_to_fix = []
            for link in revisit_links:
                href = link.get_attribute("href")
                if href:
                    urls_to_fix.append(href)

            if not urls_to_fix and not revisit_buttons:
                logger.info("✅ Aucun rejet dans les notifications")
                self._ouvrir_cloche()
                self.driver.get(current_url)
                return False

            # Si on n'a pas de hrefs (boutons sans liens), fallback : cliquer un par un
            if not urls_to_fix:
                urls_to_fix = [None] * len(revisit_buttons)

            total = len(urls_to_fix)
            logger.info(f"🔔 {total} rejet(s) trouvé(s) dans les notifications")

            if self.webhook_url:
                try:
                    requests.post(self.webhook_url,
                        json={"content": f"🔔 **{total}** rejet(s) détecté(s) — correction en cours..."},
                        timeout=10)
                except Exception:
                    pass

            # ── Phase 2 : Grouper par locale ──────────────────────────────────────
            import re as _re
            from collections import defaultdict
            grouped = defaultdict(list)

            for url in urls_to_fix:
                if url:
                    m = _re.search(r'locale=([a-zA-Z]{4})', url)
                    locale = m.group(1) if m else "unknown"
                    grouped[locale].append(url)
                else:
                    grouped["unknown"].append(None)

            logger.info(f"🔔 Répartition : {dict({k: len(v) for k, v in grouped.items()})}")

            # ── Phase 3 : Traiter locale par locale (1 dico en RAM à la fois) ─────
            original_engine = self.engine
            original_locale = self.locale

            for locale, locale_urls in grouped.items():
                if not self.running:
                    break

                # Charger le moteur pour cette locale
                if locale != "unknown" and locale != self.locale:
                    try:
                        logger.info(f"🔄 Chargement moteur {locale}...")
                        self.engine = MultiLangEngine(locale=locale)
                        self.locale = locale
                    except Exception as e:
                        logger.warning(f"⚠️ Impossible de charger le moteur {locale} : {e}")
                        continue
                elif locale == "unknown":
                    logger.warning(f"⚠️ {len(locale_urls)} rejet(s) sans locale détectée — utilisation de {self.locale}")

                for idx, url in enumerate(locale_urls):
                    if not self.running:
                        break
                    try:
                        # Vérifier que le navigateur est vivant
                        if not self._browser_vivant():
                            logger.warning(f"⚠️ Navigateur mort — relance...")
                            self._relancer_navigateur()
                            time.sleep(3)
                            # Re-login si nécessaire
                            if "login" in self.driver.current_url:
                                self._faire_login()
                                time.sleep(2)

                        # Naviguer vers le puzzle
                        if url:
                            self.driver.get(url)
                        else:
                            self.driver.get(home_url)
                            time.sleep(2)
                            if not self._ouvrir_cloche():
                                break
                            time.sleep(1.5)
                            btns = self.driver.find_elements(By.XPATH,
                                "//a[contains(., 'Revisit in Puzzle')] | //button[contains(., 'Revisit in Puzzle')]")
                            if not btns:
                                break
                            self.driver.execute_script("arguments[0].click();", btns[0])

                        time.sleep(3)

                        # Détecter la locale depuis la page si inconnue
                        if locale == "unknown":
                            detected = self._detecter_locale_page()
                            if detected and detected != self.locale:
                                try:
                                    self.engine = MultiLangEngine(locale=detected)
                                    self.locale = detected
                                except Exception:
                                    pass

                        # Lire le texte EN
                        try:
                            areas = WebDriverWait(self.driver, 10).until(
                                EC.presence_of_all_elements_located((By.TAG_NAME, "textarea")))
                            txt_en = areas[0].get_attribute("value").strip()
                        except Exception:
                            logger.warning(f"⚠️ [{locale}] Rejet {idx+1} : impossible de lire le texte")
                            continue

                        if not txt_en:
                            continue

                        # Traduire avec le bon moteur/dico
                        traduction = self._traduire_avec_timeout(txt_en)
                        if not traduction or not traduction.strip():
                            logger.warning(f"⚠️ [{locale}] Rejet {idx+1} : traduction échouée")
                            continue

                        # Anti-hallucination : vérifier avant de soumettre
                        trad_lower = traduction.lower()
                        _hall_markers = [
                            "примечание", "перевод:", "note:", "translation:",
                            "here is", "voici", "注意", "hinweis:", "nota:",
                        ]
                        is_halluc = (
                            any(m in trad_lower for m in _hall_markers)
                            or len(traduction) > len(txt_en) * 4
                        )
                        if is_halluc:
                            logger.warning(f"⚠️ [{locale}] Rejet {idx+1} : hallucination détectée, skip")
                            continue

                        # Remplir et soumettre
                        areas[1].clear()
                        time.sleep(0.3)
                        for char in traduction:
                            areas[1].send_keys(char)
                            if random.random() < 0.05:
                                time.sleep(random.uniform(0.01, 0.05))

                        time.sleep(random.uniform(1.5, 3.0))

                        btn_submit = self.driver.find_element(By.XPATH, "//button[contains(., 'Submit')]")
                        self.driver.execute_script("arguments[0].click();", btn_submit)
                        time.sleep(random.uniform(1.5, 3.0))

                        repaired += 1
                        emoji = LOCALE_EMOJI.get(locale, "🌍")
                        logger.info(f"🔧 [{emoji} {locale}] Corrigé : '{txt_en[:50]}' → '{traduction[:50]}'")

                    except Exception as e:
                        logger.warning(f"⚠️ [{locale}] Rejet {idx+1} erreur : {e}")
                        continue

                # Décharger le moteur de cette locale
                if locale != original_locale:
                    del self.engine
                    import gc
                    gc.collect()

            # Restaurer le moteur original
            self.engine = original_engine
            self.locale = original_locale

            if repaired > 0 and self.webhook_url:
                try:
                    requests.post(self.webhook_url,
                        json={"content": f"✅ **{repaired}/{total}** rejet(s) corrigé(s) automatiquement"},
                        timeout=10)
                except Exception:
                    pass

            self.driver.get(current_url)
            time.sleep(2)

        except Exception as e:
            logger.warning(f"⚠️ Erreur vérification notifications : {e}")

        return repaired > 0

    # ─────────────────────────────────────────────────────────────────
    # 🚀 BOUCLE PRINCIPALE
    # ─────────────────────────────────────────────────────────────────
    def run(self):
        self._init_driver()

        # Arrêt demandé pendant l'init (race condition changement de langue)
        if not self.running:
            try:
                if self.driver: self.driver.quit()
            except: pass
            return

        self.wait = WebDriverWait(self.driver, 15)

        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        lang  = LANGUES_PROMPT.get(self.locale, self.locale)
        logger.info(f"🚀 DÉMARRAGE Puzzle {emoji} {lang} sur {TARGET_URL} ({self.navigateur})")

        # Navigation initiale + login avant le changement de langue
        self.driver.get(TARGET_URL)
        time.sleep(3)

        if "login" in self.driver.current_url:
            ok = self._faire_login()
            if not ok:
                logger.error("❌ Impossible de se connecter — arrêt du bot.")
                self.running = False
                return

        # Si on est sur la home ou ailleurs, aller sur puzzle
        if TARGET_URL not in self.driver.current_url:
            self.driver.get(TARGET_URL)
            time.sleep(2)

        # Changer la langue dans le profil (maintenant connecté)
        self._changer_langue_profil()
        self.last_action_time = time.time()

        try:
            while self.running:
                if not self._browser_vivant():
                    if not self.running:
                        break
                    self._relancer_navigateur()
                    if not self.running:
                        break
                    continue

                try:
                    # Compte désactivé pour cette locale
                    if self._compte_desactive():
                        send_to_discord = getattr(self, '_send_discord', None)
                        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
                        msg = f"🚫 Compte désactivé pour {emoji} {self.locale} — toutes les traductions sont complètes pour cette langue."
                        logger.error(msg)
                        if self.webhook_url:
                            try:
                                import requests as _req
                                _req.post(self.webhook_url, json={"content": msg}, timeout=10)
                            except: pass
                        self.running = False
                        break

                    # Rate limit serveur
                    try:
                        body = self.driver.find_element(By.TAG_NAME, "body").text
                        if "5 per 5 second" in body or "Too Many Requests" in body:
                            logger.warning("⏳ Rate limit serveur — pause 6s...")
                            time.sleep(6)
                            self.driver.refresh()
                            time.sleep(2)
                            continue
                    except:
                        pass

                    # Reconnexion auto
                    if "login" in self.driver.current_url:
                        logger.info("🔐 Login détecté — reconnexion...")
                        ok = self._faire_login()
                        if ok:
                            self.driver.get(TARGET_URL)
                            time.sleep(2)
                        continue

                    # Lecture du texte
                    areas  = self.wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "textarea")))
                    txt_en = areas[0].get_attribute("value").strip()

                    if not txt_en:
                        time.sleep(1.5)
                        continue

                    # 🛡️ STEALTH : Vérifier les notifications aléatoirement (1 chance sur 15) pour réparer les rejets
                    if random.randint(1, 15) == 1:
                        if self._verifier_notifications_et_reparer():
                            self.last_en_text = "" # Forcer la lecture de la nouvelle page réparée
                            continue

                    if txt_en == self.last_en_text:
                        if time.time() - self.last_action_time > 300:
                            logger.info("🔄 Texte inchangé 5 min — nouveau texte...")
                            try:
                                self.driver.find_element(By.XPATH, "//button[contains(., 'Another random')]").click()
                            except:
                                self.driver.refresh()
                            self.last_action_time = time.time()
                            time.sleep(3)
                        else:
                            time.sleep(1.5)
                        continue
                        
                    # 🛡️ STEALTH : Ignorer les textes trop complexes, bourrés de code ou trop longs (pot de miel potentiel)
                    import re
                    is_junk = False
                    if re.search(r'(?i)\b(do not use|test spell|placeholder|qa test|dev spell|ph)\b', txt_en):
                        is_junk = True
                    if re.search(r'(?i)\bspell\s*\d+\b', txt_en):
                        is_junk = True
                    if "reloaded" in txt_en.lower():
                        is_junk = True
                    
                    if len(txt_en) > 800 or txt_en.count("<") > 8 or "Interface\\" in txt_en or is_junk:
                        if is_junk:
                            logger.warning(f"⚠️ Junk Data détecté — Marquage 'Does not need translating'")
                            try:
                                comment_box = self.driver.find_element(By.XPATH, "//input[contains(@placeholder, 'source links or add notes')]")
                                comment_box.clear()
                                comment_box.send_keys("Developer spell / Internal data")
                                time.sleep(0.5)
                                btn_dnt = self.driver.find_element(By.XPATH, "//button[contains(., 'Does not need translating')]")
                                self.driver.execute_script("arguments[0].click();", btn_dnt)
                                self.last_en_text = txt_en
                                self.enregistrer_traduction(txt_en, "[MARKED AS DNT]")
                                self.trads_reussies += 1
                                time.sleep(random.uniform(2.0, 4.0))
                                continue
                            except Exception as e:
                                logger.warning("Impossible de cliquer DNT, fallback sur Another random.")
                        
                        # Fallback / Trop complexe
                        logger.warning(f"⚠️ Texte complexe ({len(txt_en)} chars) — Skip (Another random)")
                        self.last_en_text = txt_en
                        try:
                            btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Another random')]")
                            self.driver.execute_script("arguments[0].click();", btn)
                        except:
                            self.driver.refresh()
                        time.sleep(random.uniform(2.0, 4.0))
                        continue

                    self.last_action_time = time.time()

                    traduction = self._traduire_avec_timeout(txt_en)
                    if traduction is None:
                        logger.warning(f"⚠️ Traduction échouée ou annulée — Skip (Another random)")
                        self.last_en_text = txt_en
                        try:
                            btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Another random')]")
                            self.driver.execute_script("arguments[0].click();", btn)
                        except:
                            self.driver.refresh()
                        time.sleep(random.uniform(2.0, 4.0))
                        continue
                        
                    # Validation stricte POST-IA (Hallucinations)
                    trad_lower = traduction.lower()
                    if any(h in trad_lower for h in [
                        "here is", "here's", "translation:", "note:", "as an ai", "corrected",
                        "我", "je suis", "ici la traduction", "voici la",
                        "примечание", "перевод:", "注意", "注:", "traducción:",
                        "übersetzung:", "hinweis:", "nota:", "aquí está",
                    ]) or len(traduction) > len(txt_en) * 4:
                        logger.warning(f"⚠️ Hallucination IA détectée dans le résultat — Skip (Another random)")
                        self.last_en_text = txt_en
                        try:
                            btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Another random')]")
                            self.driver.execute_script("arguments[0].click();", btn)
                        except:
                            self.driver.refresh()
                        time.sleep(random.uniform(2.0, 4.0))
                        continue

                    if not traduction.strip():
                        traduction = txt_en

                    self.enregistrer_traduction(txt_en, traduction)

                    emoji_loc = LOCALE_EMOJI.get(self.locale, "🌍")
                    self.historique_trads.append({
                        "en":     txt_en,
                        "fr":     traduction,
                        "locale": self.locale,
                        "emoji":  emoji_loc,
                    })
                    if len(self.historique_trads) > 200:
                        self.historique_trads = self.historique_trads[-200:]

                    # Saisie
                    areas[1].clear()
                    self.wait.until(lambda d: areas[1].get_attribute("value") == "")
                    
                    # Simulation de frappe humaine et délais variables
                    for char in traduction:
                        areas[1].send_keys(char)
                        if random.random() < 0.05: # 5% de chance de taper un peu plus lentement
                            time.sleep(random.uniform(0.01, 0.05))
                    
                    time.sleep(random.uniform(1.5, 4.5)) # Temps d'hésitation humain avant de valider

                    # Soumission
                    btn = self.driver.find_element(By.XPATH, "//button[contains(., 'Submit')]")
                    self.driver.execute_script("arguments[0].click();", btn)
                    time.sleep(random.uniform(1.0, 2.5)) # Délai avant de passer au prochain

                    self.last_en_text   = txt_en
                    self.trads_reussies += 1

                    if self.trads_reussies % 10 == 0:
                        logger.info(
                            f"✅ [{self.locale}] {self.trads_reussies} traductions validées cette session."
                        )

                except TimeoutException:
                    if not self.running:
                        break
                    if not self._browser_vivant():
                        self._relancer_navigateur()
                    else:
                        logger.warning("⏱️ Timeout Selenium — rafraîchissement...")
                        self.driver.refresh()
                        time.sleep(5)

                except WebDriverException as e:
                    if not self.running:
                        break
                    logger.warning(f"🔄 WebDriverException : {e}")
                    if not self._browser_vivant():
                        self._relancer_navigateur()
                    else:
                        time.sleep(5)

                except Exception as e:
                    if not self.running:
                        break
                    logger.error(f"🔥 Erreur inattendue : {type(e).__name__} — {e}")
                    time.sleep(5)

        finally:
            emoji = LOCALE_EMOJI.get(self.locale, "🌍")
            logger.info(f"🛑 Arrêt Puzzle [{emoji} {self.locale}] — {self.trads_reussies} traductions.")
            try:
                if self.driver:
                    self.driver.quit()
            except:
                pass
            self.envoyer_rapport_discord()
