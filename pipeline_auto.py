"""
╔══════════════════════════════════════════════════════════════════╗
║     WoW Translator — Pipeline Automatique                        ║
║                                                                  ║
║  Toutes les 12/24h :                                             ║
║    1. Récupère les rapports de session depuis Discord            ║
║    2. Analyse les traductions EN→FR avec Gemini                  ║
║    3. Met à jour wow_rules.py (lexique + corrections)            ║
║    4. Obfusque avec PyArmor                                      ║
║    5. Compile avec PyInstaller                                   ║
║    6. Crée une GitHub Release avec le nouveau .exe               ║
║    7. Tes amis reçoivent la mise à jour au prochain lancement    ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os
import json
import re
import requests
import subprocess
import shutil
import sys
import io
from pathlib import Path
from datetime import datetime

# Force UTF-8 sur le terminal Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ══════════════════════════════════════════════════════════════════
# ⚙️  CONFIGURATION (chargée depuis config.ini)
# ══════════════════════════════════════════════════════════════════
import config_manager

# Secrets chargés depuis l'environnement (cf. .env.example) — jamais en dur.
BOT_TOKEN       = os.environ.get("DISCORD_BOT_TOKEN", "")
CHANNEL_ID      = os.environ.get("DISCORD_CHANNEL_ID", "")
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO     = "Benyachou/WoW-Translator-Bot"
GEMINI_KEY      = os.environ.get("GEMINI_API_KEY", "")
GEMINI_URL      = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

BASE_DIR     = Path(__file__).parent
LOGS_DIR     = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
STATE_FILE   = BASE_DIR / "pipeline_state.json"

FICHIERS_PYARMOR = [
    "launcher.py", "gui_login.py",
    "moteur.py",         "moteur_multilang.py",
    "wow_rules.py",      "crypto_utils.py",
    "config_manager.py", "ia_provider.py",
    "bot_api_multilang.py",
    "bot_auto_firefox_multilang.py",
    "bot_verify_multilang.py",
]

FICHIERS_DICTIONNAIRES = [
    "wow_dictionnaire.json",
    "wow_dictionnaire_deDE.json",
    "wow_dictionnaire_esES.json",
    "wow_dictionnaire_esMX.json",
    "wow_dictionnaire_frFR.json",
    "wow_dictionnaire_ruRU.json",
    "wow_dictionnaire_zhCN.json",
]

FICHIERS_SENSIBLES_EXCLUS = [
    ".secrets.json",
    "config_user.json",
    "config.ini",
    "hwid_backup.json",
    "users_log.json",
    "pipeline_state.json",
    "ipsafe_state.json",
]

DISCORD_HEADERS = {"Authorization": f"Bot {BOT_TOKEN}"}
GITHUB_HEADERS  = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

# ══════════════════════════════════════════════════════════════════
# 📋  LOGGING
# ══════════════════════════════════════════════════════════════════
def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOGS_DIR / "pipeline.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")

def notifier_discord(msg):
    try:
        requests.post(
            DISCORD_WEBHOOK,
            json={"username": "Pipeline-Bot", "content": msg},
            timeout=5
        )
    except Exception:
        pass

# ══════════════════════════════════════════════════════════════════
# 💾  ÉTAT  (évite de retraiter les mêmes messages Discord)
# ══════════════════════════════════════════════════════════════════
def charger_etat():
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"dernier_message_id": None}

def sauvegarder_etat(etat):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(etat, f, indent=2)

# ══════════════════════════════════════════════════════════════════
# 📡  ÉTAPE 1 : RAPPORTS DISCORD
# ══════════════════════════════════════════════════════════════════
def telecharger_rapports(dernier_id=None):
    """
    Lit les 50 derniers messages du channel Discord et télécharge
    les fichiers Session_*.txt attachés aux nouveaux messages.
    """
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit=50"
    resp = requests.get(url, headers=DISCORD_HEADERS, timeout=15)
    resp.raise_for_status()
    messages = resp.json()

    rapports = []
    nouveau_dernier_id = dernier_id

    for msg in messages:
        msg_id = msg["id"]

        # Discord trie du plus récent au plus ancien — on skip les déjà traités
        if dernier_id and msg_id <= dernier_id:
            continue

        if nouveau_dernier_id is None or msg_id > nouveau_dernier_id:
            nouveau_dernier_id = msg_id

        for att in msg.get("attachments", []):
            nom = att.get("filename", "")
            if nom.startswith("Session_") and nom.endswith(".txt"):
                r = requests.get(att["url"], timeout=15)
                if r.status_code == 200:
                    rapports.append(r.text)
                    log(f"    ✅ Téléchargé : {nom}")

    return rapports, nouveau_dernier_id

# ══════════════════════════════════════════════════════════════════
# 🔍  ÉTAPE 2 : PARSER LES PAIRES EN/FR
# ══════════════════════════════════════════════════════════════════
def parser_paires(rapports):
    """
    Extrait les paires EN/FR des fichiers Session_*.txt.
    Format attendu dans les fichiers :
        🇬🇧 texte anglais
        🇫🇷 texte français
        --------------------------------------------------
    """
    paires = []
    vus = set()

    for contenu in rapports:
        lignes = contenu.splitlines()
        i = 0
        while i < len(lignes) - 1:
            l = lignes[i].strip()
            # Détection de la ligne EN (avec ou sans l'emoji en UTF-8)
            if l.startswith("🇬🇧") or l.startswith("\U0001f1ec\U0001f1e7"):
                en = re.sub(r"^[\U0001f1ec\U0001f1e7🇬🇧\s]+", "", l).strip()
                fr_ligne = lignes[i + 1].strip() if i + 1 < len(lignes) else ""
                fr = re.sub(r"^[\U0001f1eb\U0001f1f7🇫🇷\s]+", "", fr_ligne).strip()
                if en and fr and en != fr and en not in vus:
                    vus.add(en)
                    paires.append({"en": en, "fr": fr})
                i += 3  # saute EN + FR + séparateur
            else:
                i += 1

    return paires

# ══════════════════════════════════════════════════════════════════
# 🤖  ÉTAPE 3 : ANALYSE GEMINI
# ══════════════════════════════════════════════════════════════════
def analyser_avec_gemini(paires):
    """
    Envoie un échantillon de paires à Gemini 1.5 Flash.
    Retourne une liste de corrections détectées.
    """
    if not paires:
        return []

    echantillon = paires[:60]
    texte_paires = "\n".join(f"EN: {p['en']}\nFR: {p['fr']}" for p in echantillon)

    prompt = f"""Tu es expert en localisation WoW (World of Warcraft / WoW Ascension).
Analyse ces traductions EN→FR. Identifie UNIQUEMENT les problèmes clairs et réels.

Retourne UNIQUEMENT un tableau JSON (sans markdown, sans commentaire) :
[
  {{"type": "lexicon", "en": "terme anglais", "fr": "traduction correcte"}},
  {{"type": "erreur", "avant": "texte mal traduit dans la FR", "apres": "texte corrigé"}}
]

- "lexicon" : terme WoW devant toujours avoir la même traduction officielle
- "erreur"  : remplacement textuel d'une faute récurrente de l'IA

Si tout est correct → []

Paires à analyser :
{texte_paires}"""

    try:
        resp = requests.post(
            GEMINI_URL,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.1}
            },
            timeout=30
        )
        resp.raise_for_status()
        brut = resp.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
        # Nettoyer les balises markdown que Gemini ajoute parfois
        brut = re.sub(r"^```(?:json)?\s*", "", brut)
        brut = re.sub(r"\s*```$", "", brut)
        return json.loads(brut)
    except Exception as e:
        log(f"    ⚠️ Gemini erreur : {e}")
        return []

# ══════════════════════════════════════════════════════════════════
# 📝  ÉTAPE 4 : MISE À JOUR WOW_RULES.PY
# ══════════════════════════════════════════════════════════════════
def mettre_a_jour_wow_rules(corrections):
    """
    Injecte les nouvelles entrées dans WOW_LEXICON et ERREURS_COMMUNES.
    Utilise des ancres regex stables dans le fichier (les titres de section).
    """
    if not corrections:
        log("    ℹ️ Aucune correction à appliquer.")
        return False

    path = BASE_DIR / "wow_rules.py"
    with open(path, "r", encoding="utf-8") as f:
        contenu = f.read()

    ajouts_lexicon = []
    ajouts_erreurs = []

    for c in corrections:
        ctype = c.get("type", "")

        if ctype == "lexicon":
            en = c.get("en", "").lower().strip()
            fr = c.get("fr", "").strip()
            # Ne pas ajouter si déjà présent
            if en and fr and f'"{en}"' not in contenu and f"'{en}'" not in contenu:
                ajouts_lexicon.append(f'    "{en}": "{fr}",  # auto-pipeline')

        elif ctype == "erreur":
            avant = c.get("avant", "").strip()
            apres = c.get("apres", "").strip()
            if avant and apres and f'"{avant}"' not in contenu and f"'{avant}'" not in contenu:
                ajouts_erreurs.append(f'    "{avant}": "{apres}",  # auto-pipeline')

    modifie = False

    if ajouts_lexicon:
        # Insère juste avant la fermeture de WOW_LEXICON
        # Ancre : }\n\n# ====\n# 2. LA DOUANE
        bloc = "\n    # --- Auto Pipeline " + datetime.now().strftime("%d/%m/%Y") + " ---\n"
        bloc += "\n".join(ajouts_lexicon) + "\n"
        contenu = re.sub(
            r"(}\n\n# =+\n# 2\.)",
            bloc + r"\1",
            contenu,
            count=1
        )
        modifie = True
        log(f"    ✅ {len(ajouts_lexicon)} terme(s) ajouté(s) au WOW_LEXICON")

    if ajouts_erreurs:
        # Insère juste avant la fermeture de ERREURS_COMMUNES
        # Ancre : }\n\n# ====\n# 3. REGEX
        bloc = "\n    # --- Auto Pipeline " + datetime.now().strftime("%d/%m/%Y") + " ---\n"
        bloc += "\n".join(ajouts_erreurs) + "\n"
        contenu = re.sub(
            r"(}\n\n# =+\n# 3\.)",
            bloc + r"\1",
            contenu,
            count=1
        )
        modifie = True
        log(f"    ✅ {len(ajouts_erreurs)} correction(s) ajoutée(s) aux ERREURS_COMMUNES")

    if modifie:
        with open(path, "w", encoding="utf-8") as f:
            f.write(contenu)

    if not modifie:
        log("    ℹ️ Tous les termes détectés étaient déjà présents.")

    return modifie

# ══════════════════════════════════════════════════════════════════
# 🔢  ÉTAPE 5 : BUMP VERSION
# ══════════════════════════════════════════════════════════════════
def bump_version():
    """
    Incrémente le patch de version dans launcher.py.
    Ex : v1.0.3  →  v1.0.4
    """
    path = BASE_DIR / "launcher.py"
    with open(path, "r", encoding="utf-8") as f:
        contenu = f.read()

    match = re.search(r'CURRENT_VERSION\s*=\s*"v(\d+)\.(\d+)\.(\d+)"', contenu)
    if not match:
        log("    ❌ CURRENT_VERSION introuvable dans launcher.py")
        return None

    maj, min_, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))
    ancienne = f"v{maj}.{min_}.{patch}"
    nouvelle = f"v{maj}.{min_}.{patch + 1}"

    contenu = re.sub(
        r'(CURRENT_VERSION\s*=\s*)"v\d+\.\d+\.\d+"',
        f'\\1"{nouvelle}"',
        contenu
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(contenu)

    log(f"    ✅ {ancienne} → {nouvelle}")
    return nouvelle

# ══════════════════════════════════════════════════════════════════
# 🔒  ÉTAPE 6 : PYARMOR
# ══════════════════════════════════════════════════════════════════
def run_pyarmor():
    """Obfusque tous les fichiers source dans dossier_securise/."""
    securise = BASE_DIR / "dossier_securise"
    if securise.exists():
        shutil.rmtree(securise)

    cmd = ["pyarmor", "gen", "-O", "dossier_securise"] + FICHIERS_PYARMOR
    log(f"    Commande : {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=BASE_DIR, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"    ❌ PyArmor ERREUR :\n{result.stderr}")
        return False

    log("    ✅ Obfuscation terminée")
    return True

# ══════════════════════════════════════════════════════════════════
# 📦  ÉTAPE 7 : PYINSTALLER
# ══════════════════════════════════════════════════════════════════
def _regenerer_secrets_enc():
    """Regénère secrets.enc depuis .secrets.json avant le build."""
    src = BASE_DIR / ".secrets.json"
    dst = BASE_DIR / "secrets.enc"
    if not src.exists():
        log("    ⚠️ .secrets.json introuvable — secrets.enc non mis à jour")
        return dst.exists()
    from crypto_utils import encrypt_secrets
    import json as _json
    with open(src, "r", encoding="utf-8") as f:
        secrets = _json.load(f)
    encrypted = encrypt_secrets(secrets)
    with open(dst, "wb") as f:
        f.write(encrypted)
    log("    ✅ secrets.enc regénéré")
    return True


def run_pyinstaller(src_dir=None):
    """Compile en un seul .exe depuis src_dir (dossier_securise ou BASE_DIR en fallback)."""
    if src_dir is None:
        src_dir = BASE_DIR / "dossier_securise"

    ico_src = BASE_DIR / "icon.ico"
    ico_dst = src_dir / "icon.ico"
    if ico_src.exists() and src_dir != BASE_DIR:
        shutil.copy2(ico_src, ico_dst)
    ico_flag = ["--icon", str(ico_src)] if ico_src.exists() else []

    cmd = [
        "pyinstaller", "--noconfirm", "--onefile", "--windowed",
        *ico_flag,
        "--collect-all", "selenium",
        "--collect-all", "webdriver_manager",
        "--hidden-import=tkinter",
        "--hidden-import=tkinter.ttk",
        "--hidden-import=tkinter.messagebox",
        "--hidden-import=tkinter.scrolledtext",
        "--hidden-import=PIL",
        "--hidden-import=PIL.Image",
        "--hidden-import=PIL.ImageDraw",
        "--hidden-import=pystray",
        "--hidden-import=ollama",
        "--hidden-import=requests",
        "--hidden-import=uuid",
        "--hidden-import=dotenv",
        "--hidden-import=wow_rules",
        "--hidden-import=moteur",
        "--hidden-import=moteur_multilang",
        "--hidden-import=config_manager",
        "--hidden-import=ia_provider",
        "--hidden-import=bot_auto_firefox_multilang",
        "--hidden-import=bot_api_multilang",
        "--hidden-import=bot_verify_multilang",
        "--hidden-import=gui_login",
        "launcher.py"
    ]

    log("    Compilation en cours (peut prendre quelques minutes)...")
    result = subprocess.run(cmd, cwd=str(src_dir), capture_output=True, text=True)

    if result.returncode != 0:
        log(f"    ❌ PyInstaller ERREUR :\n{result.stderr[-3000:]}")
        return None

    exe = src_dir / "dist" / "launcher.exe"
    if not exe.exists():
        log("    ❌ launcher.exe introuvable après compilation")
        return None

    taille_mo = exe.stat().st_size // 1024 // 1024
    log(f"    ✅ .exe compilé ({taille_mo} Mo) → {exe}")
    return exe

# ══════════════════════════════════════════════════════════════════
# 🚀  ÉTAPE 8 : GITHUB RELEASE
# ══════════════════════════════════════════════════════════════════
def creer_github_release(version, exe_path):
    """Crée une release GitHub et y attache le .exe compilé."""

    # 1. Créer la release
    payload = {
        "tag_name":   version,
        "name":       f"WoW Translator {version}",
        "body":       f"Mise à jour automatique — {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        "draft":      False,
        "prerelease": False
    }
    resp = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases",
        headers=GITHUB_HEADERS,
        json=payload,
        timeout=15
    )
    if resp.status_code not in [200, 201]:
        log(f"    ❌ Création release échouée ({resp.status_code}) : {resp.text[:300]}")
        return False

    upload_url = resp.json()["upload_url"].replace("{?name,label}", "")
    log(f"    ✅ Release {version} créée sur GitHub")

    # 2. Emballer le .exe + dictionnaires + secrets.enc dans un .zip
    import zipfile
    zip_path = exe_path.parent / "WoW_Translator.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe_path, "WoW_Translator.exe")
        for dict_file in FICHIERS_DICTIONNAIRES:
            dict_path = BASE_DIR / dict_file
            if dict_path.exists():
                zf.write(dict_path, dict_file)
                log(f"    + {dict_file}")
    log(f"    ✅ .zip créé ({zip_path.stat().st_size // 1024 // 1024} Mo)")

    # 3. Upload le .zip
    log("    Upload du .zip en cours...")
    with open(zip_path, "rb") as f:
        contenu_zip = f.read()

    headers_upload = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Content-Type":  "application/zip"
    }
    resp = requests.post(
        f"{upload_url}?name=WoW_Translator.zip",
        headers=headers_upload,
        data=contenu_zip,
        timeout=180
    )
    zip_path.unlink(missing_ok=True)
    if resp.status_code not in [200, 201]:
        log(f"    ❌ Upload .zip échoué ({resp.status_code})")
        return False

    log("    ✅ WoW_Translator.zip uploadé sur GitHub")
    return True

# ══════════════════════════════════════════════════════════════════
# 🎯  MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    log("═" * 60)
    log("  WoW Translator — Pipeline Automatique")
    log(f"  {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
    log("═" * 60)

    etat = charger_etat()
    erreur = False

    try:
        # ── 1-4. Rapports Discord + Gemini (optionnel) ─────────
        nb_rapports = 0
        corrections = []
        nouveau_id = etat.get("dernier_message_id")
        try:
            log("\n[1/9] Récupération des rapports Discord...")
            rapports, nouveau_id = telecharger_rapports(etat.get("dernier_message_id"))
            nb_rapports = len(rapports)
            log(f"    {nb_rapports} nouveau(x) rapport(s) trouvé(s)")

            log("\n[2/9] Extraction des traductions...")
            paires = parser_paires(rapports)
            log(f"    {len(paires)} paires EN/FR uniques extraites")

            log("\n[3/9] Analyse avec Gemini AI...")
            corrections = analyser_avec_gemini(paires) if paires else []
            log(f"    {len(corrections)} correction(s) suggérée(s)")

            log("\n[4/9] Mise à jour wow_rules.py...")
            mettre_a_jour_wow_rules(corrections)
        except Exception as e:
            log(f"    ⚠️ Étapes Discord/Gemini ignorées : {e}")
            log("    Continuation avec build + release...")

        # ── 5. Bump version ─────────────────────────────────────
        log("\n[5/8] Incrémentation de la version...")
        nouvelle_version = bump_version()
        if not nouvelle_version:
            raise RuntimeError("Impossible de lire/modifier la version dans launcher.py")

        # ── 6. PyArmor ──────────────────────────────────────────
        log("\n[6/8] Obfuscation PyArmor...")
        pyarmor_ok = run_pyarmor()
        if not pyarmor_ok:
            log("    ⚠️  PyArmor indisponible — fallback compilation directe")

        # ── 7. PyInstaller ──────────────────────────────────────
        log("\n[7/8] Compilation PyInstaller...")
        src = (BASE_DIR / "dossier_securise") if pyarmor_ok else BASE_DIR
        exe_path = run_pyinstaller(src_dir=src)
        if not exe_path:
            raise RuntimeError("PyInstaller a échoué")

        # ── 9. GitHub Release ───────────────────────────────────
        log("\n[8/8] Publication GitHub Release...")
        if not creer_github_release(nouvelle_version, exe_path):
            raise RuntimeError("Création de la release GitHub échouée")

        # ── Sauvegarde état ─────────────────────────────────────
        etat["dernier_message_id"] = nouveau_id
        sauvegarder_etat(etat)

        msg = (
            f"✅ **Pipeline terminé !** `{nouvelle_version}`\n"
            f"📊 Rapports analysés : `{nb_rapports}` | "
            f"Corrections appliquées : `{len(corrections)}`\n"
            f"🔄 Les utilisateurs recevront la mise à jour au prochain lancement."
        )

    except Exception as e:
        erreur = True
        msg = f"❌ **Pipeline ÉCHOUÉ** : {e}"
        log(f"\n{msg}")

    log("\n" + "═" * 60)
    log(msg)
    log("═" * 60)
    notifier_discord(msg)

    sys.exit(1 if erreur else 0)


if __name__ == "__main__":
    main()
