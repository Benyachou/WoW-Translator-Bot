"""
╔══════════════════════════════════════════════════════════════════════╗
║  WoW Localization Engine — BOT VERIFY MULTILINGUE (bot_verify_multilang.py) ║
╚══════════════════════════════════════════════════════════════════════╝

Bot de vérification automatique utilisant Selenium.
Navigue sur /puzzle/verify, lit la traduction proposée et l'approuve ou 
donne "No Opinion" selon la similarité avec notre propre IA.
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
from difflib import SequenceMatcher

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait, Select

from moteur_multilang import MultiLangEngine, LANGUES_PROMPT, LOCALE_EMOJI
from bot_auto_firefox_multilang import WoWApp, SESSION_DIR
import config_manager

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

TARGET_URL    = f"{config_manager.get('api', 'base_url')}/puzzle/verify"
TIMEOUT_TRADUCTION = config_manager.get_int("traduction", "timeout", 35)

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logger = logging.getLogger("Verify-Bot-ML")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _h = logging.FileHandler(LOGS_DIR / "api_production.log", encoding="utf-8")
    _h.setFormatter(logging.Formatter("%(asctime)s │ [VERIFY-ML] %(message)s", datefmt="%H:%M:%S"))
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

import re

def similarite(a: str, b: str) -> float:
    clean_a = re.sub(r'[^\w\s]', '', a.lower()).strip()
    clean_a = re.sub(r'\s+', ' ', clean_a)
    clean_b = re.sub(r'[^\w\s]', '', b.lower()).strip()
    clean_b = re.sub(r'\s+', ' ', clean_b)
    if not clean_a and not clean_b:
        return 1.0
    if not clean_a or not clean_b:
        return 0.0
    return SequenceMatcher(None, clean_a, clean_b).ratio()

class WoWVerifyApp(WoWApp):
    def __init__(self, credentials, locale: str = "frFR"):
        super().__init__(credentials, locale)
        self.verifs_reussies = 0
        self.rejets = 0

    def _notif_discord_reject(self, txt_en, txt_prop, trad_ia, sim, raison):
        if not self.webhook_url:
            return
        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        msg = (
            f"🚫 **Vérification Rejetée** {emoji} `{self.locale}`\n"
            f"**EN :** {txt_en[:120]}\n"
            f"**Proposition :** {txt_prop[:120]}\n"
            f"**Notre IA :** {(trad_ia or 'N/A')[:120]}\n"
            f"**Raison :** {raison}\n"
            f"**Similarité :** {sim:.1f}%"
        )
        try:
            requests.post(self.webhook_url, json={"content": msg}, timeout=10)
        except Exception:
            pass

    def _changer_langue_verify(self):
        """
        Sélectionne la bonne langue dans le menu déroulant sur la page Verify.
        """
        emoji      = LOCALE_EMOJI.get(self.locale, "🌍")
        lang       = LANGUES_PROMPT.get(self.locale, self.locale)
        select_val = LOCALE_SELECT_VALUE.get(self.locale, self.locale)

        logger.info(f"{emoji} Sélection de la file d'attente → {self.locale} ({lang})...")

        for tentative in range(3):
            try:
                wait = WebDriverWait(self.driver, 10)
                
                # Le select "Queue locale"
                select_elem = wait.until(EC.presence_of_element_located((By.XPATH, "//select[contains(., 'All locales')]")))
                
                try:
                    Select(select_elem).select_by_value(select_val)
                except Exception:
                    self.driver.execute_script(
                        "arguments[0].value = arguments[1]; "
                        "arguments[0].dispatchEvent(new Event('change', {bubbles:true}));",
                        select_elem, select_val
                    )
                time.sleep(1.5)

                # Cliquer sur "Reload" en cherchant tous les boutons
                reload_btns = self.driver.find_elements(By.XPATH, "//button[contains(., 'Reload')]")
                for btn in reload_btns:
                    if btn.is_displayed():
                        try:
                            btn.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", btn)
                        break
                
                time.sleep(3)

                logger.info(f"✅ File d'attente chargée pour {self.locale}")
                return True

            except Exception as e:
                logger.warning(f"⚠️ Tentative {tentative+1}/3 changement langue verify : {e}")
                time.sleep(2)

        logger.error(f"❌ Impossible de changer la langue vers {self.locale}.")
        return False

    def run(self):
        self._init_driver()

        if not self.running:
            try:
                if self.driver: self.driver.quit()
            except: pass
            return

        self.wait = WebDriverWait(self.driver, 15)

        emoji = LOCALE_EMOJI.get(self.locale, "🌍")
        lang  = LANGUES_PROMPT.get(self.locale, self.locale)
        logger.info(f"🚀 DÉMARRAGE Vérification {emoji} {lang} sur {TARGET_URL} ({self.navigateur})")

        self.driver.get(TARGET_URL)
        time.sleep(3)

        if "login" in self.driver.current_url:
            ok = self._faire_login()
            if not ok:
                logger.error("❌ Impossible de se connecter — arrêt du bot.")
                self.running = False
                return
            self.driver.get(TARGET_URL)
            time.sleep(2)

        ok = self._changer_langue_verify()
        if not ok:
            self.running = False
            return

        self.last_action_time = time.time()
        last_identifiant = ""

        try:
            while self.running:
                if not self._browser_vivant():
                    if not self.running: break
                    self._relancer_navigateur()
                    if not self.running: break
                    self.driver.get(TARGET_URL)
                    time.sleep(2)
                    self._changer_langue_verify()
                    continue

                try:
                    if self._compte_desactive():
                        self.running = False
                        break

                    # 🛡️ Vérifier que la file d'attente n'a pas sauté sur "All locales"
                    try:
                        select_elems = self.driver.find_elements(By.XPATH, "//select[contains(., 'All locales')]")
                        if select_elems:
                            selected_option = Select(select_elems[0]).first_selected_option.text
                            if "All locales" in selected_option or self.locale not in select_elems[0].get_attribute("value"):
                                logger.info(f"🔄 La langue a sauté (actuel: {selected_option}), on la remet...")
                                self._changer_langue_verify()
                                continue
                    except Exception:
                        pass

                    # Lecture du texte original et de la traduction proposée
                    txt_en, txt_prop = "", ""
                    try:
                        # Stratégie 1: chercher par label
                        en_labels = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'English (enUS)')]")
                        prop_labels = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Proposed translation')]")
                        
                        if en_labels and prop_labels:
                            # Prendre l'élément parent le plus proche avec une bordure ou un padding
                            txt_en = en_labels[0].find_element(By.XPATH, "./following-sibling::* | ./..//div[contains(@class, 'p-4')] | ./..//textarea").text.strip()
                            txt_prop = prop_labels[0].find_element(By.XPATH, "./following-sibling::* | ./..//div[contains(@class, 'p-4')] | ./..//textarea").text.strip()
                            if not txt_en: txt_en = en_labels[0].find_element(By.XPATH, "./following-sibling::* | ./..//div[contains(@class, 'p-4')] | ./..//textarea").get_attribute("value").strip()
                            if not txt_prop: txt_prop = prop_labels[0].find_element(By.XPATH, "./following-sibling::* | ./..//div[contains(@class, 'p-4')] | ./..//textarea").get_attribute("value").strip()
                    except Exception as e:
                        logger.debug(f"Stratégie 1 échouée: {e}")

                    if not txt_en or not txt_prop:
                        # Stratégie 2: chercher 2 grands blocs de texte ou textareas
                        try:
                            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
                            if len(textareas) >= 2:
                                txt_en = textareas[0].get_attribute("value").strip()
                                txt_prop = textareas[1].get_attribute("value").strip()
                            else:
                                blocs = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'border') and contains(@class, 'p-4')]")
                                blocs_text = [b.text.strip() for b in blocs if len(b.text.strip()) > 3]
                                if len(blocs_text) >= 2:
                                    txt_en = blocs_text[0]
                                    txt_prop = blocs_text[1]
                        except Exception as e:
                            logger.debug(f"Stratégie 2 échouée: {e}")
                            
                    # Récupérer l'information de soumission (timestamp) pour différencier les doublons
                    submission_info = ""
                    try:
                        sub_elems = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'submitted ')]")
                        if sub_elems:
                            submission_info = sub_elems[0].text.strip()
                    except:
                        pass

                    if not txt_en or not txt_prop:
                        # Check rate limit ou queue vide
                        body = self.driver.find_element(By.TAG_NAME, "body").text
                        if "5 per 5 second" in body or "Too Many Requests" in body:
                            logger.warning("⏳ Rate limit serveur — pause 6s...")
                            time.sleep(6)
                            self.driver.refresh()
                            time.sleep(3)
                            continue
                        
                        if "Cannot vote" in body or "No items found" in body or "You cannot vote your own submission" in body:
                            logger.info("💤 Plus de traductions à vérifier ou ce sont les nôtres. Pause de 15s...")
                            time.sleep(15)
                            reload_btn = self.driver.find_elements(By.XPATH, "//button[contains(., 'Reload')]")
                            if reload_btn:
                                self.driver.execute_script("arguments[0].click();", reload_btn[0])
                            else:
                                self.driver.refresh()
                            time.sleep(3)
                            continue

                        logger.info("🔎 En attente des textes à vérifier (introuvables ou vides)...")
                        try:
                            with open(LOGS_DIR / "debug_verify_page.html", "w", encoding="utf-8") as f:
                                f.write(self.driver.page_source)
                            logger.info("📄 Code source HTML sauvegardé dans logs/debug_verify_page.html")
                        except: pass
                        time.sleep(2.5)
                        continue
                        
                    # Remplacer les retours à la ligne par des espaces pour le log
                    en_log = txt_en.replace('\n', ' ')
                    prop_log = txt_prop.replace('\n', ' ')
                    logger.info(f"📖 LU -> EN: {en_log[:80]}...")
                    logger.info(f"📖 LU -> PROPOSITION: {prop_log[:80]}...")

                    identifiant_actuel = f"{txt_en} | {txt_prop} | {submission_info}"

                    if identifiant_actuel == last_identifiant:
                        if time.time() - self.last_action_time > 60:
                            logger.info("🔄 Bloqué sur le même texte depuis 60s. Reload...")
                            self.driver.refresh()
                            self.last_action_time = time.time()
                            last_identifiant = ""
                            time.sleep(3)
                        else:
                            time.sleep(1.5)
                        continue

                    self.last_action_time = time.time()

                    # Traduire avec notre IA
                    trad_ia = self._traduire_avec_timeout(txt_en)
                    if trad_ia:
                        trad_log = trad_ia.replace('\n', ' ')
                        logger.info(f"🤖 IA -> TRAD: {trad_log[:80]}...")
                    
                    time.sleep(random.uniform(2.0, 5.0)) # Délai humain de lecture
                    
                    action_cliquee = ""
                    
                    def cliquer_bouton(nom):
                        try:
                            btns = self.driver.find_elements(By.XPATH, f"//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{nom.lower()}')]")
                            for btn in btns:
                                if btn.is_displayed() and btn.is_enabled():
                                    # Scroll to the button
                                    try:
                                        self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", btn)
                                        time.sleep(0.5)
                                    except: pass
                                    
                                    # Strategy 1: Native Click
                                    try:
                                        btn.click()
                                        logger.info(f"🖱️ Clic réussi sur le bouton '{nom}' (Natif)")
                                        return True
                                    except Exception as e1:
                                        logger.debug(f"Clic natif échoué: {e1}")
                                        # Strategy 2: ActionChains
                                        try:
                                            from selenium.webdriver.common.action_chains import ActionChains
                                            ActionChains(self.driver).move_to_element(btn).click().perform()
                                            logger.info(f"🖱️ Clic réussi sur le bouton '{nom}' (ActionChains)")
                                            return True
                                        except Exception as e2:
                                            logger.debug(f"Clic ActionChains échoué: {e2}")
                                            # Strategy 3: JS Click
                                            try:
                                                self.driver.execute_script("arguments[0].click();", btn)
                                                logger.info(f"🖱️ Clic réussi sur le bouton '{nom}' (JS)")
                                                return True
                                            except Exception as e3:
                                                logger.debug(f"Clic JS échoué: {e3}")
                                                
                            logger.error(f"❌ Aucun bouton '{nom}' visible/cliquable trouvé.")
                            return False
                        except Exception as e:
                            logger.error(f"❌ Impossible de cliquer sur le bouton '{nom}' : {e}")
                            return False

                    if trad_ia is None:
                        logger.warning("⚠️ IA a planté. Vote : No Opinion.")
                        cliquer_bouton("No Opinion")
                        action_cliquee = "No Opinion"
                    else:
                        sim = similarite(trad_ia, txt_prop)
                        logger.info(f"⚖️ Similarité IA vs Proposition: {(sim*100):.1f}%")
                        
                        hallucinations = [
                            "note:", "translation:", "ici la traduction", "corrected",
                            "attention :", "here is", "here's", "as an ai", "je suis", "我",
                            "примечание", "перевод:", "注意", "注:", "traducción:",
                            "übersetzung:", "hinweis:", "nota:", "aquí está", "voici la",
                        ]
                        if any(h in txt_prop.lower() for h in hallucinations):
                            logger.warning(f"🚫 Hallucination détectée ! Vote : Reject.")
                            cliquer_bouton("Reject")
                            action_cliquee = "Reject"
                            self.rejets += 1
                            self._notif_discord_reject(txt_en, txt_prop, trad_ia, sim*100, "Hallucination détectée")
                        elif sim >= 0.60 or trad_ia.lower() in txt_prop.lower() or txt_prop.lower() in trad_ia.lower():
                            logger.info(f"✅ Similaire ({sim*100:.1f}%). Vote : Approve.")
                            cliquer_bouton("Approve")
                            action_cliquee = "Approve"
                        else:
                            if sim < 0.35:
                                logger.info(f"❌ Trop différent ({sim*100:.1f}%). Vote : Reject.")
                                cliquer_bouton("Reject")
                                action_cliquee = "Reject"
                                self.rejets += 1
                                self._notif_discord_reject(txt_en, txt_prop, trad_ia, sim*100, f"Similarité trop faible ({sim*100:.1f}%)")
                            else:
                                logger.info(f"🤔 Différent de l'IA ({sim*100:.1f}%). Vote : No Opinion.")
                                cliquer_bouton("No Opinion")
                                action_cliquee = "No Opinion"

                    # Ajout pour l'affichage dans le moniteur de launcher.py
                    self.historique_trads.append({
                        "en": txt_en,
                        "fr": f"[{action_cliquee}] Proposition : {txt_prop}  (Notre IA : {trad_ia if trad_ia else 'N/A'})",
                        "locale": self.locale,
                        "emoji": LOCALE_EMOJI.get(self.locale, "🌍")
                    })
                    if len(self.historique_trads) > 200:
                        self.historique_trads = self.historique_trads[-200:]

                    time.sleep(random.uniform(1.0, 2.5)) # Délai après clic

                    last_identifiant = identifiant_actuel
                    self.verifs_reussies += 1

                    if self.verifs_reussies % 10 == 0:
                        logger.info(f"✅ [{self.locale}] {self.verifs_reussies} vérifications traitées.")

                except Exception as e:
                    if not self.running: break
                    logger.error(f"🔥 Erreur boucle Verify : {type(e).__name__} — {e}")
                    time.sleep(5)

        finally:
            emoji = LOCALE_EMOJI.get(self.locale, "🌍")
            logger.info(f"🛑 Arrêt Verify [{emoji} {self.locale}] — {self.verifs_reussies} vérifications traitées.")
            try:
                if self.driver: self.driver.quit()
            except: pass

if __name__ == "__main__":
    app = WoWVerifyApp({"token": "TEST", "user": "TestUser", "pass": "TestPass"}, locale="frFR")
    app.run()
