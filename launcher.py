"""
╔══════════════════════════════════════════════════════════════════╗
║          WoW Localization Engine — LAUNCHER PRO EDITION          ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import threading
import socket
import os
import time
import subprocess
import zipfile
import requests
import base64
import glob
import json
import logging
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext, messagebox
import uuid

import ctypes
import pystray
from PIL import Image, ImageDraw, ImageTk

# Icône indépendante de python.exe dans la barre des tâches
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("WoWTranslator.Bot.1")
except: pass

from gui_login import lancer_fenetre_connexion
from bot_api_multilang import WoWAPIApp
from bot_auto_firefox_multilang import WoWApp as FirefoxApp
from bot_verify_multilang import WoWVerifyApp
from selenium.webdriver.support.ui import WebDriverWait
from moteur_multilang import LANGUES_PROMPT, LOCALE_EMOJI, ModeleManquantError, MODELE_PAR_LOCALE
import config_manager
import ia_provider

# ==========================================
# ⚙️ CONFIGURATION & IDENTITÉ
# ==========================================

CURRENT_VERSION = "v0.9.30"
GITHUB_REPO = "Benyachou/WoW-Translator-Bot"

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

LOGS_DIR   = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)
LOG_FILE   = LOGS_DIR / "api_production.log"

logger = logging.getLogger("Launcher")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _lh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    _lh.setFormatter(logging.Formatter("%(asctime)s │ [LAUNCHER] %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(_lh)

ICON_PATH  = BASE_DIR / "icon.ico"
STATS_FILE = BASE_DIR / "stats.json"

# Taux DP par traduction soumise
DP_PAR_API    = 0.1
DP_PAR_PUZZLE = 0.5

with open(LOG_FILE, "w", encoding="utf-8") as f:
    f.write(f"=== WoW Translator {CURRENT_VERSION} ===\n")

# ANTI-CLONAGE
try:
    instance_lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    instance_lock.bind(("127.0.0.1", 47512))
except socket.error:
    print("❌ Le logiciel tourne déjà en arrière-plan (regardez l'icône) !")
    sys.exit(0)

# ==========================================
# 🌍 GLOBALES
# ==========================================
bot_api               = None
bot_puzzle            = None
bot_verify            = None
thread_api            = None
thread_puzzle         = None
thread_verify         = None
thread_notif          = None
notif_running         = False
notif_rejets_count    = 0
notif_repaired_count  = 0
moniteur_fenetre      = None
app_icon              = None
utilisateur_actuel    = "Non connecté"
GLOBAL_CREDENTIALS    = {}
stats_lock            = threading.Lock()
bot_api_start_time    = None
bot_puzzle_start_time = None
bot_verify_start_time = None
_puzzle_restart_gen   = 0   # incrémenté à chaque arrêt manuel — invalide les restarts obsolètes
_verify_restart_gen   = 0

# ── Langue active ─────────────────────────────────────────────────────────────
LOCALE_ACTUELLE = "frFR"

LANGUES_MENU = [
    ("🇫🇷  Français",           "frFR"),
    ("🇪🇸  Espagnol (Espagne)",  "esES"),
    ("🇩🇪  Allemand",            "deDE"),
    ("🇷🇺  Russe",               "ruRU"),
    ("🇲🇽  Espagnol (Amérique latine)",  "esMX"),
    ("🇨🇳  Mandarin simplifié",  "zhCN"),
]

def nettoyer_vieux_rapports():
    patterns = [
        str(BASE_DIR / "Session_*.txt"),
        str(BASE_DIR / "rapport_erreurs_*.txt"),
        str(LOGS_DIR / "Session_*.txt"),
        str(LOGS_DIR / "rapport_erreurs_*.txt"),
    ]
    for pattern in patterns:
        for fichier in glob.glob(pattern):
            try: os.remove(fichier)
            except: pass

nettoyer_vieux_rapports()

# ==========================================
# 🎉 MESSAGE DE BIENVENUE (premier lancement)
# ==========================================
def afficher_message_bienvenue():
    s = charger_stats() if STATS_FILE.exists() else {}
    if s.get("bienvenue_affiche"):
        return
    win = tk.Tk()
    win.withdraw()
    win.attributes("-topmost", True)
    messagebox.showinfo(
        "WoW Translator — Bienvenue !",
        "👋  Bienvenue sur WoW Translator !\n\n"
        "⚠️  Si Windows t'a affiché un message\n"
        "      \"Application non reconnue\" ou\n"
        "      \"Windows a protégé votre PC\" :\n\n"
        "      ✅  Clique sur  \"Informations complémentaires\"\n"
        "      ✅  Puis  \"Exécuter quand même\"\n\n"
        "C'est tout à fait normal pour un logiciel\n"
        "sans certificat officiel. Le bot est sûr.\n\n"
        "Ce message n'apparaîtra qu'une seule fois.",
        parent=win
    )
    win.destroy()
    with stats_lock:
        s2 = charger_stats() if STATS_FILE.exists() else {}
        s2["bienvenue_affiche"] = True
        try:
            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(s2, f, ensure_ascii=False, indent=2)
        except: pass

# ==========================================
# 📊 STATS PERSISTANTES (cumul entre sessions)
# ==========================================
def charger_stats() -> dict:
    try:
        if STATS_FILE.exists():
            with open(STATS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except: pass
    return {"total_api": 0, "total_puzzle": 0}

def sauvegarder_stats(api_ajout: int = 0, puzzle_ajout: int = 0):
    with stats_lock:
        s = charger_stats()
        s["total_api"]    = s.get("total_api", 0)    + api_ajout
        s["total_puzzle"] = s.get("total_puzzle", 0) + puzzle_ajout
        try:
            with open(STATS_FILE, 'w', encoding='utf-8') as f:
                json.dump(s, f, ensure_ascii=False, indent=2)
        except: pass

# ==========================================
# 🔑 HELPERS SECRETS
# ==========================================
def get_discord_url():
    return os.environ.get("DISCORD_WEBHOOK_URL", "")

def get_github_token():
    return os.environ.get("GITHUB_TOKEN", "")

def get_hwid():
    """Génère un HWID unique et stable basé sur le UUID de la carte mère (Windows)."""
    if os.name == 'nt':
        # PowerShell (Windows 11+) — wmic est supprimé depuis Win11
        try:
            output = subprocess.check_output(
                ['powershell', '-NoProfile', '-Command',
                 '(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID'],
                creationflags=subprocess.CREATE_NO_WINDOW, timeout=10
            ).decode().strip()
            if output and '-' in output:
                return output
        except Exception:
            pass
        # Fallback wmic (Windows 10 et antérieur)
        try:
            output = subprocess.check_output('wmic csproduct get uuid', shell=True).decode().split('\n')
            for line in output:
                if '-' in line:
                    return line.strip()
        except Exception:
            pass

    mac_num = hex(uuid.getnode()).replace('0x', '').upper()
    mac = '-'.join(mac_num[i:i+2] for i in range(0, len(mac_num), 2))
    return mac

def send_to_discord(message):
    webhook_url = get_discord_url()
    if not webhook_url: return
    mon_hwid = get_hwid()
    entete = f"{utilisateur_actuel} | HWID: {mon_hwid}"
    payload = {"username": "WoW-Moniteur", "content": f"🖥️ **[{entete}]** : {message}"}
    try: requests.post(webhook_url, json=payload, timeout=3)
    except: pass

# ==========================================
# 🛑 KILL SWITCH
# ==========================================
def verifier_acces(username):
    if username.lower().strip() == "zaraki":
        return True
    token = get_github_token()
    if not token or token == "METS_TON_CODE_GITHUB_BASE64_ICI":
        return False
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.raw"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/blocklist.json"
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = json.loads(resp.text)
            mon_hwid   = get_hwid()
            user_lower = username.lower().strip()
            blocked_u  = [u.lower().strip() for u in data.get("blocked_users", [])]
            blocked_h  = [h.upper().strip() for h in data.get("blocked_hwids", [])]
            if user_lower in blocked_u or mon_hwid in blocked_h:
                return False
            return True
        return False
    except:
        return False

# ==========================================
# 👥 SUIVI UTILISATEURS
# ==========================================
def enregistrer_lancement(username):
    """Enregistre le lancement dans users_log.json sur GitHub (username + HWID + infos machine)."""
    token = get_github_token()
    if not token: return
    import socket as _sock
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/users_log.json"

    sha     = None
    entries = []
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data    = resp.json()
            sha     = data.get("sha")
            raw     = base64.b64decode(data["content"].replace("\n", "")).decode("utf-8")
            entries = json.loads(raw)
        elif resp.status_code != 404:
            return
    except: return

    hwid     = get_hwid()
    hostname = ""
    ip       = ""
    try: hostname = _sock.gethostname()
    except: pass
    try: ip = _sock.gethostbyname(hostname) if hostname else ""
    except: pass

    now = time.strftime("%Y-%m-%d %H:%M:%S")
    key = f"{username.lower()}|{hwid}"

    existing = next((e for e in entries if e.get("_key") == key), None)
    if existing:
        existing["last_seen"]     = now
        existing["launch_count"]  = existing.get("launch_count", 0) + 1
        existing["ip"]            = ip
        existing["hostname"]      = hostname
    else:
        entries.append({
            "_key":         key,
            "username":     username,
            "hwid":         hwid,
            "hostname":     hostname,
            "ip":           ip,
            "first_seen":   now,
            "last_seen":    now,
            "launch_count": 1
        })

    try:
        encoded = base64.b64encode(json.dumps(entries, ensure_ascii=False, indent=2).encode()).decode()
        payload = {"message": f"launch: {username} ({hwid})", "content": encoded}
        if sha: payload["sha"] = sha
        requests.put(url, headers=headers, json=payload, timeout=10)
    except: pass


def lire_users_log():
    """Lit users_log.json depuis GitHub et retourne la liste."""
    token = get_github_token()
    if not token: return []
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.raw"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/users_log.json"
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            return json.loads(resp.text)
    except: pass
    return []


def modifier_blocklist(username, hwid, bloquer=True):
    """Ajoute ou retire un utilisateur/HWID de la blocklist.json sur GitHub."""
    token = get_github_token()
    if not token: return False
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/blocklist.json"
    try:
        resp = requests.get(url, headers=headers, timeout=5)
        sha = None
        data = {"blocked_users": [], "blocked_hwids": []}
        if resp.status_code == 200:
            resp_json = resp.json()
            sha = resp_json.get("sha")
            raw_content = base64.b64decode(resp_json["content"].replace("\n", "")).decode("utf-8")
            data = json.loads(raw_content)
            
        u_lower = username.lower().strip()
        h_upper = hwid.upper().strip()
        
        users = data.get("blocked_users", [])
        hwids = data.get("blocked_hwids", [])
        
        if bloquer:
            if u_lower and u_lower not in users: users.append(u_lower)
            if h_upper and h_upper not in hwids: hwids.append(h_upper)
        else:
            if u_lower in users: users.remove(u_lower)
            if h_upper in hwids: hwids.remove(h_upper)
            
        data["blocked_users"] = users
        data["blocked_hwids"] = hwids
        
        encoded = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
        payload = {"message": f"{'Block' if bloquer else 'Unblock'}: {username}", "content": encoded}
        if sha: payload["sha"] = sha
        
        r = requests.put(url, headers=headers, json=payload, timeout=10)
        return r.status_code in [200, 201]
    except Exception as e:
        return False


def afficher_users_log():
    """Ouvre une fenêtre listant tous les utilisateurs enregistrés."""
    win = tk.Toplevel()
    win.title("👥 Utilisateurs enregistrés")
    win.geometry("900x480")
    win.configure(bg="#0d0d1a")
    win.resizable(True, True)
    win.minsize(600, 300)
    try:
        if ICON_PATH.exists(): win.iconbitmap(str(ICON_PATH))
    except: pass

    tk.Label(win, text="👥  Utilisateurs enregistrés", bg="#0d0d1a",
             fg="#bc8c14", font=("Consolas", 12, "bold")).pack(anchor=tk.W, padx=16, pady=(14, 2))
    tk.Label(win, text="Chargement depuis GitHub…", bg="#0d0d1a",
             fg="#444466", font=("Consolas", 9)).pack(anchor=tk.W, padx=16)

    cols = ("username", "hwid", "hostname", "ip", "first_seen", "last_seen", "launch_count")
    labels = ("Compte", "HWID (MAC)", "Hostname", "IP", "1ère connexion", "Dernière connexion", "Lancements")

    from tkinter import ttk as _ttk
    style = _ttk.Style(win)
    style.theme_use("clam")
    style.configure("Users.Treeview",
                    background="#070710", foreground="#aaaacc",
                    fieldbackground="#070710", rowheight=22,
                    font=("Consolas", 9))
    style.configure("Users.Treeview.Heading",
                    background="#1a1a3a", foreground="#8888cc",
                    font=("Consolas", 9, "bold"))
    style.map("Users.Treeview", background=[("selected", "#2233aa")])

    frame_tree = tk.Frame(win, bg="#0d0d1a")
    frame_tree.pack(fill=tk.BOTH, expand=True, padx=16, pady=(8, 4))

    vsb = _ttk.Scrollbar(frame_tree, orient="vertical")
    vsb.pack(side=tk.RIGHT, fill=tk.Y)
    hsb = _ttk.Scrollbar(frame_tree, orient="horizontal")
    hsb.pack(side=tk.BOTTOM, fill=tk.X)

    tree = _ttk.Treeview(frame_tree, columns=cols, show="headings", style="Users.Treeview",
                         yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.config(command=tree.yview)
    hsb.config(command=tree.xview)

    widths = (120, 160, 140, 110, 140, 140, 80)
    for col, lbl, w in zip(cols, labels, widths):
        tree.heading(col, text=lbl)
        tree.column(col, width=w, minwidth=60, anchor=tk.W)
    tree.pack(fill=tk.BOTH, expand=True)

    menu_actions = tk.Menu(win, tearoff=0, bg="#1a1a2a", fg="#aaaaee", font=("Consolas", 9))
    
    def action_bloquer():
        sel = tree.selection()
        if not sel: return
        item = tree.item(sel[0])['values']
        username, hwid = item[0], item[1]
        if messagebox.askyesno("Bloquer", f"Voulez-vous bloquer {username} ({hwid}) ?", parent=win):
            if modifier_blocklist(username, hwid, bloquer=True):
                messagebox.showinfo("Succès", f"{username} a été bloqué !", parent=win)
            else:
                messagebox.showerror("Erreur", "Erreur lors de la mise à jour de la blocklist.", parent=win)

    def action_debloquer():
        sel = tree.selection()
        if not sel: return
        item = tree.item(sel[0])['values']
        username, hwid = item[0], item[1]
        if messagebox.askyesno("Débloquer", f"Voulez-vous débloquer {username} ({hwid}) ?", parent=win):
            if modifier_blocklist(username, hwid, bloquer=False):
                messagebox.showinfo("Succès", f"{username} a été débloqué !", parent=win)
            else:
                messagebox.showerror("Erreur", "Erreur lors de la mise à jour de la blocklist.", parent=win)

    menu_actions.add_command(label="🚫 Bloquer l'utilisateur", command=action_bloquer)
    menu_actions.add_command(label="✅ Débloquer l'utilisateur", command=action_debloquer)

    def afficher_menu(event):
        item = tree.identify_row(event.y)
        if item:
            tree.selection_set(item)
            menu_actions.tk_popup(event.x_root, event.y_root)

    tree.bind("<Button-3>", afficher_menu)

    frame_actions = tk.Frame(win, bg="#0d0d1a")
    frame_actions.pack(fill=tk.X, padx=16, pady=(0, 10))

    lbl_count = tk.Label(frame_actions, text="", bg="#0d0d1a", fg="#445566", font=("Consolas", 8))
    lbl_count.pack(side=tk.LEFT)

    btn_bloquer = tk.Button(frame_actions, text="🚫 Bloquer (Sélection)", bg="#3a1a1a", fg="#cc8888",
                            font=("Consolas", 9), relief="flat", cursor="hand2", command=action_bloquer)
    btn_bloquer.pack(side=tk.RIGHT, padx=5)

    btn_debloquer = tk.Button(frame_actions, text="✅ Débloquer (Sélection)", bg="#1a3a2a", fg="#88cc88",
                              font=("Consolas", 9), relief="flat", cursor="hand2", command=action_debloquer)
    btn_debloquer.pack(side=tk.RIGHT)

    def charger():
        entries = lire_users_log()
        if not win.winfo_exists(): return
        for row in tree.get_children(): tree.delete(row)
        for e in sorted(entries, key=lambda x: x.get("last_seen", ""), reverse=True):
            tree.insert("", tk.END, values=(
                e.get("username", ""),
                e.get("hwid", ""),
                e.get("hostname", ""),
                e.get("ip", ""),
                e.get("first_seen", ""),
                e.get("last_seen", ""),
                e.get("launch_count", 0)
            ))
        lbl_count.config(text=f"{len(entries)} utilisateur(s) enregistré(s)")
        # Mettre à jour le label "Chargement…"
        for w in win.winfo_children():
            if isinstance(w, tk.Label) and "Chargement" in (w.cget("text") or ""):
                w.config(text="")

    threading.Thread(target=charger, daemon=True).start()

    btn_refresh = tk.Button(win, text="🔄 Rafraîchir", bg="#1a1a2a", fg="#8888cc",
                            font=("Consolas", 9), relief="flat", cursor="hand2",
                            command=lambda: threading.Thread(target=charger, daemon=True).start())
    btn_refresh.pack(pady=(0, 10))


def surveillance_active():
    while True:
        time.sleep(120)
        if not verifier_acces(utilisateur_actuel):
            send_to_discord("💥 **ÉJECTION EN DIRECT** : L'accès a été révoqué en pleine session !")
            for inst in [bot_api, bot_puzzle, bot_verify]:
                if inst:
                    inst.running = False
                    if hasattr(inst, 'driver'):
                        try: inst.driver.quit()
                        except: pass
            os._exit(0)

# ==========================================
# 📖 SYNC DICTIONNAIRES DEPUIS GITHUB
# ==========================================
DICTIONNAIRES = [
    "wow_dictionnaire.json",
    "wow_dictionnaire_deDE.json",
    "wow_dictionnaire_esES.json",
    "wow_dictionnaire_esMX.json",
    "wow_dictionnaire_frFR.json",
    "wow_dictionnaire_ruRU.json",
    "wow_dictionnaire_zhCN.json",
]

def sync_dictionnaires():
    token = get_github_token()
    if not token:
        return
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    for nom in DICTIONNAIRES:
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{nom}"
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                continue
            meta = resp.json()
            remote_sha = meta.get("sha", "")
            local_path = BASE_DIR / nom
            if local_path.exists():
                import hashlib
                with open(local_path, "rb") as f:
                    contenu = f.read()
                blob = b"blob " + str(len(contenu)).encode() + b"\0" + contenu
                local_sha = hashlib.sha1(blob).hexdigest()
                if local_sha == remote_sha:
                    continue
            dl_url = meta.get("download_url", "")
            if not dl_url:
                continue
            r = requests.get(dl_url, timeout=30)
            if r.status_code == 200:
                with open(local_path, "wb") as f:
                    f.write(r.content)
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"\n📖 Dictionnaire synchronisé : {nom}\n")
        except Exception:
            continue

# ==========================================
# 🔄 AUTO-UPDATER
# ==========================================
def check_for_updates():
    token = get_github_token()
    if not token: return None, None
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200: return None, None
        data = response.json()
        latest_version = data.get("tag_name", "")
        if not latest_version or latest_version == CURRENT_VERSION: return None, None
        for asset in data.get("assets", []):
            if asset["name"].endswith(".zip"):
                send_to_discord(f"🆕 Mise à jour : {CURRENT_VERSION} → {latest_version}. Téléchargement...")
                return latest_version, asset["url"]
    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n⚠️ Vérification MàJ échouée : {e}\n")
    return None, None

def apply_update(asset_url: str):
    token    = get_github_token()
    zip_path = BASE_DIR / "update_temp.zip"
    new_exe  = BASE_DIR / "WoW_Translator_new.exe"
    bat_path = BASE_DIR / "updater.bat"
    try:
        headers_dl = {"Authorization": f"token {token}", "Accept": "application/octet-stream"}
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n⬇️ Téléchargement MàJ depuis : {asset_url}\n")
        r = requests.get(asset_url, headers=headers_dl, allow_redirects=True, stream=True, timeout=120)
        if r.status_code != 200:
            send_to_discord(f"❌ Échec téléchargement MàJ (code {r.status_code}).")
            return
        taille_recue = 0
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
                    taille_recue += len(chunk)
        if taille_recue == 0:
            send_to_discord("❌ Fichier de mise à jour vide. Annulation.")
            return
        send_to_discord(f"✅ Téléchargement terminé ({taille_recue // 1024} Ko).")
        import zipfile as zf
        exe_trouve = False
        with zf.ZipFile(zip_path, 'r') as archive:
            for nom_fichier in archive.namelist():
                if nom_fichier.endswith(".exe"):
                    data = archive.read(nom_fichier)
                    if new_exe.exists(): new_exe.unlink()
                    new_exe.write_bytes(data)
                    exe_trouve = True
                elif nom_fichier.startswith("wow_dictionnaire") and nom_fichier.endswith(".json"):
                    dict_dest = BASE_DIR / nom_fichier
                    dict_dest.write_bytes(archive.read(nom_fichier))
                    with open(LOG_FILE, "a", encoding="utf-8") as f:
                        f.write(f"\n📖 Dictionnaire mis à jour : {nom_fichier}\n")
        zip_path.unlink(missing_ok=True)
        if not exe_trouve or new_exe.stat().st_size < 100_000:
            send_to_discord("❌ Exe introuvable ou corrompu dans le zip. Annulation.")
            new_exe.unlink(missing_ok=True)
            return
        exe_actuel = Path(sys.executable).name if getattr(sys, 'frozen', False) else "WoW_Translator.exe"
        bat_content = (
            "@echo off\necho Mise a jour en cours...\ntimeout /t 3 /nobreak > NUL\n"
            f"del /f /q \"{exe_actuel}\"\nmove /y \"WoW_Translator_new.exe\" \"{exe_actuel}\"\n"
            f"start \"\" \"{exe_actuel}\"\ndel /f /q \"%~f0\"\n"
        )
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat_content)
        send_to_discord("🔄 Redémarrage pour appliquer la mise à jour...")
        subprocess.Popen([str(bat_path)], shell=True, cwd=str(BASE_DIR), creationflags=subprocess.CREATE_NEW_CONSOLE)
        for inst in [bot_api, bot_puzzle]:
            if inst: inst.running = False
        instance_lock.close()
        sys.exit(0)
    except Exception as e:
        send_to_discord(f"❌ Erreur mise à jour : {e}")
        zip_path.unlink(missing_ok=True)
        new_exe.unlink(missing_ok=True)

# ==========================================
# 🦙 OLLAMA — VÉRIFICATION AU DÉMARRAGE
# ==========================================
def _ollama_repond():
    ollama_host = config_manager.get("ollama", "host")
    ollama_port = config_manager.get_int("ollama", "port", 11434)
    import socket
    try:
        s = socket.create_connection((ollama_host, ollama_port), timeout=1)
        s.close()
        return True
    except Exception:
        return False

def verifier_demarrer_ollama():
    def _check():
        if _ollama_repond():
            return

        OLLAMA_EXE = config_manager.get_ollama_exe()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n🦙 Ollama non détecté — démarrage automatique ({OLLAMA_EXE})...\n")

        try:
            env = config_manager.get_ollama_env()
            subprocess.Popen(
                [OLLAMA_EXE],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True,
                env=env,
            )
        except Exception as e:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"❌ Impossible de démarrer Ollama : {e}\n")
            return

        for i in range(20):
            time.sleep(1)
            if _ollama_repond():
                with open(LOG_FILE, "a", encoding="utf-8") as f:
                    f.write(f"✅ Ollama prêt ({i+1}s)\n")
                return

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("⚠️ Ollama n'a pas répondu après 20s.\n")

    threading.Thread(target=_check, daemon=True).start()


# ==========================================
# 🤖 MOTEURS
# ==========================================
def _running(inst): return bool(inst and getattr(inst, 'running', False))

def est_api_arrete(item):    return not _running(bot_api)
def est_puzzle_arrete(item): return not _running(bot_puzzle)
def est_api_marche(item):    return _running(bot_api)
def est_puzzle_marche(item): return _running(bot_puzzle)

def _proposer_installation_modele(modele: str, locale: str, callback_relancer=None):
    """
    Affiche une popup proposant d'installer le modèle Ollama manquant.
    Si l'utilisateur accepte, ouvre une fenêtre de progression et lance 'ollama pull'.
    Doit être appelé depuis le thread principal (via fenetre.after).
    """
    import ollama as _ollama

    lang_nom = LANGUES_PROMPT.get(locale, locale)
    oui = messagebox.askyesno(
        "Modèle IA manquant",
        f"La langue « {lang_nom} » ({locale}) requiert le modèle :\n\n"
        f"    {modele}\n\n"
        f"Ce modèle n'est pas encore installé sur votre machine.\n"
        f"Voulez-vous l'installer maintenant ? (peut prendre quelques minutes)",
        icon="warning"
    )
    if not oui:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n⚠️ Installation refusée pour {modele} ({locale})\n")
        return

    # ── Fenêtre de progression ────────────────────────────────────────────────
    win = tk.Toplevel(fenetre)
    win.title(f"Installation : {modele}")
    win.geometry("480x200")
    win.resizable(True, True)
    win.minsize(400, 160)
    win.configure(bg="#1a1a2e")
    win.grab_set()

    tk.Label(win, text=f"Téléchargement de {modele}...",
             bg="#1a1a2e", fg="#aaaaee",
             font=("Segoe UI", 11, "bold")).pack(pady=(20, 5))

    lbl_status = tk.Label(win, text="Démarrage...", bg="#1a1a2e", fg="#888888",
                          font=("Segoe UI", 9))
    lbl_status.pack()

    import tkinter.ttk as ttk
    bar = ttk.Progressbar(win, length=420, mode="determinate")
    bar.pack(pady=12, padx=20)

    lbl_pct = tk.Label(win, text="0 %", bg="#1a1a2e", fg="#44dd88",
                       font=("Segoe UI", 10, "bold"))
    lbl_pct.pack()

    def _pull():
        try:
            for prog in _ollama.pull(modele, stream=True):
                status  = prog.status or ""
                total   = prog.total or 0
                complet = prog.completed or 0
                if total and complet:
                    pct = int(complet / total * 100)
                    win.after(0, lambda p=pct, s=status: (
                        bar.config(value=p),
                        lbl_pct.config(text=f"{p} %"),
                        lbl_status.config(text=s[:60])
                    ))
                elif status:
                    win.after(0, lambda s=status: lbl_status.config(text=s[:60]))
            # Succès
            win.after(0, _installation_ok)
        except Exception as exc:
            win.after(0, lambda: _installation_erreur(str(exc)))

    def _installation_ok():
        win.destroy()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n✅ Modèle {modele} installé avec succès.\n")
        messagebox.showinfo("Installation réussie",
                            f"✅ {modele} installé avec succès !\n\nLe bot va redémarrer.")
        if callback_relancer:
            fenetre.after(500, callback_relancer)

    def _installation_erreur(msg):
        win.destroy()
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n❌ Échec installation {modele} : {msg}\n")
        messagebox.showerror("Échec d'installation",
                             f"❌ Impossible d'installer {modele} :\n\n{msg}\n\n"
                             f"Essayez manuellement : ollama pull {modele}")

    threading.Thread(target=_pull, daemon=True).start()


def _run_api():
    global bot_api
    try:
        bot_api = WoWAPIApp(GLOBAL_CREDENTIALS, locale=LOCALE_ACTUELLE)
        bot_api.run()
    except ModeleManquantError as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n⚠️ Modèle manquant pour {e.locale} : {e.modele}\n")
        if fenetre:
            modele, locale = e.modele, e.locale
            fenetre.after(0, lambda: _proposer_installation_modele(
                modele, locale, callback_relancer=start_api_direct
            ))
    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(f"\n❌ CRASH API : {e}\n")
        send_to_discord(f"🔥 **CRASH API** : {e}")
    finally:
        nb = getattr(bot_api, 'trads_reussies', 0) if bot_api else 0
        if nb: sauvegarder_stats(api_ajout=nb)
        if bot_api: bot_api.running = False

def _run_puzzle():
    global bot_puzzle
    try:
        bot_puzzle = FirefoxApp(GLOBAL_CREDENTIALS, locale=LOCALE_ACTUELLE)
        bot_puzzle.run()
    except ModeleManquantError as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n⚠️ Modèle manquant pour {e.locale} : {e.modele}\n")
        if fenetre:
            modele, locale = e.modele, e.locale
            fenetre.after(0, lambda: _proposer_installation_modele(
                modele, locale, callback_relancer=start_puzzle_direct
            ))
    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(f"\n❌ CRASH PUZZLE : {e}\n")
        send_to_discord(f"🔥 **CRASH PUZZLE** : {e}")
    finally:
        nb = getattr(bot_puzzle, 'trads_reussies', 0) if bot_puzzle else 0
        if nb: sauvegarder_stats(puzzle_ajout=nb)
        if bot_puzzle: bot_puzzle.running = False

def _run_verify():
    global bot_verify
    try:
        bot_verify = WoWVerifyApp(GLOBAL_CREDENTIALS, locale=LOCALE_ACTUELLE)
        bot_verify.run()
    except ModeleManquantError as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n⚠️ Modèle manquant pour {e.locale} : {e.modele}\n")
        if fenetre:
            modele, locale = e.modele, e.locale
            fenetre.after(0, lambda: _proposer_installation_modele(
                modele, locale, callback_relancer=start_verify_direct
            ))
    except Exception as e:
        with open(LOG_FILE, "a", encoding="utf-8") as f: f.write(f"\n❌ CRASH VERIFY : {e}\n")
        send_to_discord(f"🔥 **CRASH VERIFY** : {e}")
    finally:
        if bot_verify: bot_verify.running = False

# ── Contrôle direct (depuis le moniteur) ─────────────────────────────────────
def _notifier(titre, message):
    try:
        if app_icon: app_icon.notify(message, titre)
    except: pass

def start_api_direct():
    global thread_api, bot_api_start_time
    if _running(bot_api): return
    send_to_discord("⚡ Démarrage du Mode **API**")
    bot_api_start_time = time.time()
    thread_api = threading.Thread(target=_run_api, daemon=True)
    thread_api.start()
    _notifier("WoW Translator", "⚡ Mode API démarré")

def stop_api_direct():
    if bot_api:
        send_to_discord("🛑 Arrêt manuel du Mode **API**")
        bot_api.running = False
    _notifier("WoW Translator", "🛑 Mode API arrêté")

def start_puzzle_direct():
    global thread_puzzle, bot_puzzle_start_time
    if _running(bot_puzzle): return
    send_to_discord("🧩 Démarrage du Mode **Puzzle**")
    bot_puzzle_start_time = time.time()
    thread_puzzle = threading.Thread(target=_run_puzzle, daemon=True)
    thread_puzzle.start()
    _notifier("WoW Translator", "🧩 Mode Puzzle démarré")

def stop_puzzle_direct():
    global _puzzle_restart_gen
    _puzzle_restart_gen += 1   # invalide tout thread _restart_apres_arret en cours
    if bot_puzzle:
        send_to_discord("🛑 Arrêt manuel du Mode **Puzzle**")
        bot_puzzle.running = False
        if hasattr(bot_puzzle, 'driver') and bot_puzzle.driver:
            try:
                bot_puzzle.driver.quit()
            except: pass
            bot_puzzle.driver = None
    _notifier("WoW Translator", "🛑 Mode Puzzle arrêté")

def start_verify_direct():
    global thread_verify, bot_verify_start_time
    if _running(bot_verify): return
    send_to_discord("✔️ Démarrage du Mode **Verify**")
    bot_verify_start_time = time.time()
    thread_verify = threading.Thread(target=_run_verify, daemon=True)
    thread_verify.start()
    _notifier("WoW Translator", "✔️ Mode Verify démarré")

def stop_verify_direct():
    global _verify_restart_gen, bot_verify
    _verify_restart_gen += 1
    if bot_verify:
        send_to_discord("🛑 Arrêt manuel du Mode **Verify**")
        bot_verify.running = False
        if hasattr(bot_verify, 'driver') and bot_verify.driver:
            try: bot_verify.driver.quit()
            except: pass
            bot_verify.driver = None
    _notifier("WoW Translator", "🛑 Mode Verify arrêté")

# ── Vérification des notifications (rejets) ──────────────────────────────────

API_BASE_URL = config_manager.get("api", "base_url")

NOTIF_INTERVAL = 300  # vérification auto toutes les 5 minutes

def _check_notifications_loop():
    time.sleep(15)
    while True:
        _check_notifications_once()
        time.sleep(NOTIF_INTERVAL)

def _check_notifications_once():
    global notif_running, notif_rejets_count, notif_repaired_count
    if notif_running:
        return
    notif_rejets_count   = 0
    notif_repaired_count = 0
    notif_running = True
    logger.info("🔔 Vérification des notifications — rejets en cours...")

    try:
        # ── 1. Vérification API : soumissions rejetées ────────────────────────
        token = GLOBAL_CREDENTIALS.get("token")
        if token:
            try:
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                }
                resp = requests.get(
                    f"{API_BASE_URL}/api/v1/account/submissions?status=rejected&limit=100",
                    headers=headers, timeout=15
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("rows", data) if isinstance(data, dict) else data
                    if isinstance(items, list):
                        notif_rejets_count = len(items)
                        if notif_rejets_count > 0:
                            logger.info(f"🔔 API : {notif_rejets_count} traduction(s) rejetée(s) trouvée(s)")
                            for item in items:
                                tid = item.get("translation_id") or item.get("id", "?")
                                reason = item.get("reject_reason") or item.get("reason", "")
                                txt = item.get("value", "")[:60]
                                logger.info(f"   ❌ ID {tid} : {txt}... {f'({reason})' if reason else ''}")

                            if _running(bot_api) and bot_api:
                                _repair_via_api(items)
                        else:
                            logger.info("✅ API : aucune traduction rejetée")
                    else:
                        logger.info("✅ API : aucune traduction rejetée")
                else:
                    logger.warning(f"⚠️ API rejets : code {resp.status_code}")
            except Exception as e:
                logger.warning(f"⚠️ Vérification API échouée : {e}")
        else:
            logger.warning("⚠️ Pas de token API — vérification API ignorée")

        # ── 2. Vérification Puzzle : cloche de notifications ──────────────────
        # Utiliser le bot puzzle s'il tourne, sinon lancer un bot temporaire
        active_bot = None
        temp_bot = None

        if _running(bot_puzzle) and bot_puzzle and hasattr(bot_puzzle, 'driver') and bot_puzzle.driver:
            active_bot = bot_puzzle
        elif _running(bot_api) and bot_api and hasattr(bot_api, 'driver') and bot_api.driver:
            active_bot = bot_api
        else:
            # Lancer un bot temporaire pour vérifier les notifications
            logger.info("🔔 Aucun bot actif — lancement d'un navigateur temporaire...")
            try:
                temp_bot = FirefoxApp(GLOBAL_CREDENTIALS, locale="frFR")
                temp_bot._init_driver()
                temp_bot.wait = WebDriverWait(temp_bot.driver, 15)
                temp_bot.driver.get(f"{API_BASE_URL}/login")
                time.sleep(3)
                if "login" in temp_bot.driver.current_url:
                    temp_bot._faire_login()
                    time.sleep(2)
                active_bot = temp_bot
            except Exception as e:
                logger.warning(f"⚠️ Impossible de lancer le navigateur temporaire : {e}")

        if active_bot:
            try:
                repaired = active_bot._verifier_notifications_et_reparer()
                if repaired:
                    notif_repaired_count += 1
                    logger.info("🔧 Puzzle : rejets corrigés via Revisit in Puzzle")
                else:
                    logger.info("✅ Puzzle : aucune notification de rejet")
            except Exception as e:
                logger.warning(f"⚠️ Vérification Puzzle échouée : {e}")
            finally:
                if temp_bot:
                    try:
                        temp_bot.driver.quit()
                    except Exception:
                        pass
        else:
            logger.warning("⚠️ Impossible de vérifier les notifications (pas de navigateur)")

    finally:
        notif_running = False
        total = notif_rejets_count + notif_repaired_count
        if total > 0:
            msg = f"🔔 **{notif_rejets_count}** rejet(s) API, **{notif_repaired_count}** corrigé(s)"
            logger.info(f"🔔 Résultat : {notif_rejets_count} rejet(s) API, {notif_repaired_count} corrigé(s) Puzzle")
            _notifier("WoW Translator", f"🔔 {total} rejet(s) trouvé(s)")
            send_to_discord(msg)
        else:
            logger.info("✅ Aucun rejet détecté (API + Puzzle)")
            _notifier("WoW Translator", "✅ Aucun rejet détecté")


def _repair_via_api(rejected_items):
    global notif_repaired_count
    if not bot_api:
        return
    for item in rejected_items:
        if not notif_running:
            break
        txt_en = item.get("enUS") or item.get("original", "")
        tid = item.get("translation_id") or item.get("id")
        if not txt_en or not tid:
            continue
        try:
            new_trad = bot_api._traduire_avec_timeout(txt_en.strip())
            if new_trad and new_trad.strip() and new_trad.strip() != txt_en.strip():
                payload = {"locale": bot_api.locale, "items": [{"translation_id": tid, "value": new_trad}]}
                resp = bot_api._requete_blindee("POST",
                    f"{API_BASE_URL}/api/v1/account/submissions/bulk", json=payload)
                if resp.status_code in [200, 201, 202]:
                    notif_repaired_count += 1
                    logger.info(f"   🔧 ID {tid} re-traduit et soumis")
                else:
                    logger.warning(f"   ⚠️ ID {tid} re-soumission échouée (code {resp.status_code})")
        except Exception as e:
            logger.warning(f"   ⚠️ ID {tid} erreur re-traduction : {e}")


def start_notif_check():
    """Lancement manuel via le bouton — force une vérification immédiate."""
    if notif_running:
        return
    threading.Thread(target=_check_notifications_once, daemon=True).start()


# ── Contrôle depuis le tray (wrapping) ───────────────────────────────────────
def start_bot_api(icon, item):
    start_api_direct()
    icon.update_menu()

def start_bot_puzzle(icon, item):
    start_puzzle_direct()
    icon.update_menu()

def stop_api(icon, item):
    stop_api_direct()
    icon.update_menu()

def stop_puzzle(icon, item):
    stop_puzzle_direct()
    icon.update_menu()

def surveiller_inactivite():
    """Alerte Discord si aucune traduction depuis 10 min alors que le bot tourne."""
    SEUIL = 10 * 60
    prev       = {"api": 0, "puzzle": 0, "verify": 0}
    last_chg   = {"api": time.time(), "puzzle": time.time(), "verify": time.time()}
    alerte_ok  = {"api": False, "puzzle": False, "verify": False}

    while True:
        time.sleep(60)
        for mode, bot, key in [
            ("API",    bot_api,    "api"),
            ("Puzzle", bot_puzzle, "puzzle"),
            ("Verify", bot_verify, "verify"),
        ]:
            if _running(bot):
                count = getattr(bot, 'trads_reussies', 0) or getattr(bot, 'verifs_reussies', 0)
                if count > prev[key]:
                    prev[key]      = count
                    last_chg[key]  = time.time()
                    alerte_ok[key] = False
                elif time.time() - last_chg[key] > SEUIL and not alerte_ok[key]:
                    send_to_discord(
                        f"⚠️ **BOT {mode} INACTIF** depuis 10+ min — "
                        f"Ollama planté ou rate limit prolongé ?"
                    )
                    alerte_ok[key] = True
            else:
                prev[key]      = 0
                last_chg[key]  = time.time()
                alerte_ok[key] = False

def afficher_moniteur(icon=None, item=None):
    global moniteur_fenetre
    if moniteur_fenetre:
        try:
            moniteur_fenetre.deiconify()
            moniteur_fenetre.lift()
            moniteur_fenetre.focus_force()
        except: pass

def quit_app(icon=None, item=None):
    send_to_discord("❌ Fermeture complète de l'application.")
    stop_api_direct()
    stop_puzzle_direct()
    stop_verify_direct()
    if icon:
        try: icon.stop()
        except: pass
    elif app_icon:
        try: app_icon.stop()
        except: pass
    global moniteur_fenetre
    if moniteur_fenetre:
        try: moniteur_fenetre.after(0, moniteur_fenetre.destroy)
        except: pass
    try: instance_lock.close()
    except: pass

# ==========================================
# 🎨 ICÔNE
# ==========================================
def _build_icon_image(size=256):
    """Deux bulles de dialogue EN (bleue) + FR (dorée)."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    dc  = ImageDraw.Draw(img)
    s   = size / 256

    def sc(v): return int(v * s)

    dc.rounded_rectangle([0, 0, size, size], radius=sc(52), fill=(10, 12, 28))
    dc.rounded_rectangle([sc(4), sc(4), size-sc(4), size-sc(4)],
                         radius=sc(48), outline=(190, 148, 22), width=max(2, sc(5)))
    b1 = (55, 145, 215)
    dc.rounded_rectangle([sc(16), sc(20), sc(196), sc(128)], radius=sc(26), fill=b1)
    dc.polygon([(sc(28), sc(124)), (sc(12), sc(162)), (sc(62), sc(124))], fill=b1)
    for x in [sc(68), sc(100), sc(132)]:
        dc.ellipse([x, sc(64), x+sc(22), sc(86)], fill=(255, 255, 255))
    b2 = (210, 155, 20)
    dc.rounded_rectangle([sc(60), sc(120), sc(240), sc(228)], radius=sc(26), fill=b2)
    dc.polygon([(sc(194), sc(224)), (sc(244), sc(248)), (sc(228), sc(224))], fill=b2)
    for x in [sc(112), sc(144), sc(176)]:
        dc.ellipse([x, sc(162), x+sc(22), sc(184)], fill=(255, 255, 255))

    return img.convert('RGB')

def _generate_ico():
    try:
        base  = _build_icon_image(256)
        sizes = [(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)]
        imgs  = [base.resize(s, Image.LANCZOS) for s in sizes]
        imgs[0].save(str(ICON_PATH), format="ICO", sizes=sizes, append_images=imgs[1:])
    except: pass

def create_default_icon():
    return _build_icon_image(64)

# ==========================================
# ⚙️ FENÊTRE PARAMÈTRES
# ==========================================
def afficher_parametres():
    cfg = config_manager.charger_config()

    win = tk.Toplevel()
    win.title("⚙️ Paramètres")
    win.geometry("660x720")
    win.configure(bg="#0d0d1a")
    win.resizable(True, True)
    win.minsize(500, 400)
    try:
        if ICON_PATH.exists(): win.iconbitmap(str(ICON_PATH))
    except: pass

    canvas = tk.Canvas(win, bg="#0d0d1a", highlightthickness=0)
    scrollbar = tk.Scrollbar(win, orient="vertical", command=canvas.yview)
    frame_main = tk.Frame(canvas, bg="#0d0d1a")

    frame_main.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas_window = canvas.create_window((0, 0), window=frame_main, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.bind("<Configure>", lambda e: canvas.itemconfig(canvas_window, width=e.width))

    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    canvas.bind_all("<MouseWheel>",
        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

    tk.Label(frame_main, text="⚙️  Paramètres", bg="#0d0d1a",
             fg="#bc8c14", font=("Consolas", 14, "bold")).pack(anchor=tk.W, padx=16, pady=(14, 10))

    entries = {}

    def add_section(title, color="#2255aa"):
        tk.Frame(frame_main, bg="#222233", height=1).pack(fill=tk.X, padx=16, pady=(10, 4))
        tk.Label(frame_main, text=title, bg="#0d0d1a",
                 fg=color, font=("Consolas", 10, "bold")).pack(anchor=tk.W, padx=16, pady=(4, 4))

    def add_field(section, key, label, show=""):
        frame = tk.Frame(frame_main, bg="#0d0d1a")
        frame.pack(fill=tk.X, padx=24, pady=2)
        tk.Label(frame, text=label, bg="#0d0d1a", fg="#8888aa",
                 font=("Consolas", 9), width=30, anchor=tk.W).pack(side=tk.LEFT)
        entry = tk.Entry(frame, bg="#12122a", fg="#aaaadd", insertbackground="#aaaadd",
                         font=("Consolas", 9), width=40, show=show)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        val = cfg.get(section, key, fallback="")
        entry.insert(0, val)
        entries[(section, key)] = entry

    # IA Backend
    add_section("🤖  BACKEND IA", "#ff8833")

    frame_backend = tk.Frame(frame_main, bg="#0d0d1a")
    frame_backend.pack(fill=tk.X, padx=24, pady=2)
    tk.Label(frame_backend, text="Backend IA", bg="#0d0d1a", fg="#8888aa",
             font=("Consolas", 9), width=30, anchor=tk.W).pack(side=tk.LEFT)

    from tkinter import ttk as _ttk_cfg
    backend_var = tk.StringVar(value=cfg.get("ia", "backend", fallback="ollama"))
    combo_backend = _ttk_cfg.Combobox(
        frame_backend, textvariable=backend_var,
        values=["ollama", "gemini", "openai", "claude"],
        state="readonly", width=37, font=("Consolas", 9))
    combo_backend.pack(side=tk.LEFT, fill=tk.X, expand=True)
    entries[("ia", "backend")] = type('', (), {'get': lambda s=backend_var: s.get()})()

    add_field("ia", "model_name", "Modèle (vide = auto)")
    add_field("ia", "api_key", "Clé API (Gemini/OpenAI/Claude)", show="*")
    add_field("ia", "api_url", "URL custom (vide = défaut)")

    # Aide contextuelle
    tk.Label(frame_main, text="   ollama = local  |  gemini/openai/claude = API externe (clé requise)",
             bg="#0d0d1a", fg="#555566", font=("Consolas", 8)).pack(anchor=tk.W, padx=24)

    # Bouton test connexion
    frame_test = tk.Frame(frame_main, bg="#0d0d1a")
    frame_test.pack(fill=tk.X, padx=24, pady=(4, 2))
    lbl_test = tk.Label(frame_test, text="", bg="#0d0d1a", fg="#888888", font=("Consolas", 8))
    lbl_test.pack(side=tk.LEFT, padx=(0, 10))

    def tester_ia():
        lbl_test.config(text="⏳ Test en cours...", fg="#ffaa44")
        win.update()
        try:
            import ia_provider
            ok, msg = ia_provider.test_connection()
            lbl_test.config(text=f"{'✅' if ok else '❌'} {msg}", fg="#44dd88" if ok else "#ff4444")
        except Exception as e:
            lbl_test.config(text=f"❌ {e}", fg="#ff4444")

    tk.Button(frame_test, text="🔌 Tester la connexion IA", bg="#1a1a2a", fg="#ff8833",
              font=("Consolas", 8), relief="flat", cursor="hand2",
              activebackground="#252540", activeforeground="#ffaa55",
              command=tester_ia).pack(side=tk.RIGHT)

    # Ollama (visible si backend=ollama)
    add_section("🦙  OLLAMA (local)", "#44aa66")
    add_field("ollama", "exe_path", "Chemin Ollama (auto = détection)")
    add_field("ollama", "host", "Adresse du serveur")
    add_field("ollama", "port", "Port")
    add_field("ollama", "gpu_vulkan", "GPU Vulkan (1=oui, 0=non)")

    # Traduction
    add_section("🌍  TRADUCTION", "#4488cc")
    add_field("traduction", "seuil_qualite", "Seuil qualité (0-100)")
    add_field("traduction", "auto_evaluation", "Auto-évaluation (true/false)")
    add_field("traduction", "timeout", "Timeout traduction (sec)")
    add_field("traduction", "bulk_size", "Taille des lots (bulk)")
    add_field("traduction", "sauvegarde_interval", "Intervalle sauvegarde")

    # API
    add_section("🌐  API TRANSLATION HUB", "#aa8822")
    add_field("api", "base_url", "URL de base")
    add_field("api", "rate_limit_max", "Limite requêtes / fenêtre")
    add_field("api", "rate_limit_fenetre", "Fenêtre rate limit (sec)")

    # Général
    add_section("📋  GÉNÉRAL", "#888888")
    add_field("general", "langue_defaut", "Langue par défaut")

    # Boutons
    frame_btns = tk.Frame(frame_main, bg="#0d0d1a")
    frame_btns.pack(fill=tk.X, padx=16, pady=(16, 16))

    lbl_status = tk.Label(frame_btns, text="", bg="#0d0d1a", fg="#44dd88", font=("Consolas", 9))
    lbl_status.pack(side=tk.LEFT, padx=(0, 10))

    def sauver():
        new_cfg = config_manager.charger_config()
        for (section, key), entry in entries.items():
            if section not in new_cfg:
                new_cfg[section] = {}
            new_cfg[section][key] = entry.get().strip()
        config_manager.sauvegarder_config(new_cfg)
        lbl_status.config(text="✅ Paramètres sauvegardés !", fg="#44dd88")
        win.after(3000, lambda: lbl_status.config(text=""))

    tk.Button(frame_btns, text="💾  Sauvegarder", bg="#0e3320", fg="#44dd88",
              font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
              activebackground="#1a5a35", activeforeground="#88ffaa",
              command=sauver).pack(side=tk.RIGHT, padx=5)

    tk.Button(frame_btns, text="❌  Fermer", bg="#3a0d0d", fg="#ff6666",
              font=("Segoe UI", 10, "bold"), relief="flat", cursor="hand2",
              activebackground="#5a1515", activeforeground="#ff9999",
              command=win.destroy).pack(side=tk.RIGHT, padx=5)


_ip_safe_window = None

def afficher_ip_safe():
    global _ip_safe_window
    if _ip_safe_window and _ip_safe_window.winfo_exists():
        _ip_safe_window.lift()
        _ip_safe_window.focus_force()
        return

    try:
        from ip_safe import IPSafeApp
        top = tk.Toplevel()
        try:
            if ICON_PATH.exists():
                top.iconbitmap(str(ICON_PATH))
        except Exception:
            pass
        _ip_safe_window = top
        IPSafeApp(top)
    except Exception as e:
        messagebox.showerror("IP Safe", f"Impossible de lancer IP Safe :\n{e}")


# ==========================================
# 🖥️ MONITEUR PRINCIPAL
# ==========================================
def lancer_moniteur_principal():
    global moniteur_fenetre

    # Chargement des stats historiques (sessions précédentes)
    stats_prev = charger_stats()

    fenetre = tk.Tk()
    fenetre.title(f"WoW Translator {CURRENT_VERSION} — Moniteur")
    fenetre.geometry("980x760")
    fenetre.configure(bg="#0d0d1a")
    fenetre.minsize(760, 600)

    try:
        if ICON_PATH.exists():
            fenetre.iconbitmap(str(ICON_PATH))
    except: pass

    # Fermer → masquer dans le tray
    def a_la_fermeture():
        fenetre.withdraw()

    fenetre.protocol("WM_DELETE_WINDOW", a_la_fermeture)

    # ── HEADER ───────────────────────────────────────────────────────────────
    frame_header = tk.Frame(fenetre, bg="#0d0d1a")
    frame_header.pack(fill=tk.X, padx=16, pady=(14, 0))

    tk.Label(frame_header, text="WoW Translator", bg="#0d0d1a",
             fg="#bc8c14", font=("Consolas", 13, "bold")).pack(side=tk.LEFT)
    tk.Label(frame_header, text=f"  {CURRENT_VERSION}", bg="#0d0d1a",
             fg="#444466", font=("Consolas", 10)).pack(side=tk.LEFT, pady=2)

    # Indicateur GPU Vulkan
    def _detecter_gpu():
        try:
            import subprocess, re as _re
            log_path = Path(os.environ.get("LOCALAPPDATA","")) / "Ollama" / "server.log"
            if log_path.exists():
                txt = log_path.read_text(encoding="utf-8", errors="ignore")[-8000:]
                # Cherche la dernière occurrence d'inference compute
                m = _re.search(r'library=(\w+).*?name=(\S+).*?total="([^"]+)"', txt)
                if m and m.group(1).lower() == "vulkan":
                    return f"⚡ GPU: {m.group(2)} ({m.group(3)})"
                elif m:
                    return f"🖥 CPU ({m.group(1)})"
        except Exception:
            pass
        return "🖥 CPU"

    gpu_txt = _detecter_gpu()
    gpu_color = "#22cc44" if "GPU" in gpu_txt else "#886644"
    tk.Label(frame_header, text=f"  {gpu_txt}", bg="#0d0d1a",
             fg=gpu_color, font=("Consolas", 9)).pack(side=tk.LEFT, pady=2)

    tk.Label(frame_header, text=utilisateur_actuel, bg="#0d0d1a",
             fg="#556677", font=("Consolas", 9)).pack(side=tk.RIGHT)

    tk.Button(frame_header, text="🛡️ IP Safe",
              bg="#1a1a2a", fg="#3fb950",
              font=("Consolas", 8), relief="flat", cursor="hand2",
              activebackground="#252540", activeforeground="#66dd77",
              command=afficher_ip_safe).pack(side=tk.RIGHT, padx=(0, 6))

    tk.Button(frame_header, text="⚙️ Paramètres",
              bg="#1a1a2a", fg="#aa8822",
              font=("Consolas", 8), relief="flat", cursor="hand2",
              activebackground="#252540", activeforeground="#ddaa44",
              command=afficher_parametres).pack(side=tk.RIGHT, padx=(0, 6))

    if utilisateur_actuel.lower().strip() == "zaraki":
        tk.Button(frame_header, text="👥 Utilisateurs",
                  bg="#1a1a2a", fg="#7777aa",
                  font=("Consolas", 8), relief="flat", cursor="hand2",
                  activebackground="#252540", activeforeground="#aaaadd",
                  command=afficher_users_log).pack(side=tk.RIGHT, padx=(0, 10))

    tk.Frame(fenetre, bg="#222233", height=1).pack(fill=tk.X, padx=16, pady=(8, 0))

    # ── SÉLECTEUR DE LANGUE ───────────────────────────────────────────────────
    frame_lang = tk.Frame(fenetre, bg="#0a0a18", pady=10, padx=16,
                          highlightbackground="#2a2a44", highlightthickness=1)
    frame_lang.pack(fill=tk.X, padx=16, pady=(10, 0))

    tk.Label(frame_lang, text="🌍  LANGUE CIBLE", bg="#0a0a18",
             fg="#556688", font=("Consolas", 8, "bold")).pack(anchor=tk.W, pady=(0, 6))

    frame_flags = tk.Frame(frame_lang, bg="#0a0a18")
    frame_flags.pack(fill=tk.X)

    _LOCALE_COLORS = {
        "frFR": "#2255cc", "esES": "#cc4422", "deDE": "#ddaa22",
        "ruRU": "#3366aa", "esMX": "#228844", "zhCN": "#cc2244",
    }
    _lang_buttons = {}
    langue_var = tk.StringVar(value=LOCALE_ACTUELLE)

    def _select_langue(loc):
        langue_var.set(next(lbl for lbl, l in LANGUES_MENU if l == loc))
        for l, btn in _lang_buttons.items():
            if l == loc:
                btn.config(bg=_LOCALE_COLORS.get(l, "#2255cc"), fg="white",
                           relief="sunken", font=("Segoe UI", 10, "bold"))
            else:
                btn.config(bg="#12122a", fg="#667788",
                           relief="flat", font=("Segoe UI", 10))
        lbl_lang_info.config(
            text=f"{LOCALE_EMOJI.get(loc, '')}  {LANGUES_PROMPT.get(loc, loc)}",
            fg=_LOCALE_COLORS.get(loc, "#aaaaee"))
        # Déclencher le changement de langue via le même event
        combo_langue_event(loc)

    for lbl, loc in LANGUES_MENU:
        emoji = LOCALE_EMOJI.get(loc, "🌍")
        short = loc[:2].upper()
        is_active = (loc == LOCALE_ACTUELLE)
        btn = tk.Button(
            frame_flags, text=f"{emoji} {short}",
            bg=_LOCALE_COLORS.get(loc, "#2255cc") if is_active else "#12122a",
            fg="white" if is_active else "#667788",
            font=("Segoe UI", 10, "bold") if is_active else ("Segoe UI", 10),
            relief="sunken" if is_active else "flat",
            cursor="hand2", padx=10, pady=4,
            activebackground=_LOCALE_COLORS.get(loc, "#2255cc"),
            activeforeground="white",
            command=lambda l=loc: _select_langue(l),
        )
        btn.pack(side=tk.LEFT, padx=(0, 4))
        _lang_buttons[loc] = btn

    lbl_lang_info = tk.Label(frame_lang, text="", bg="#0a0a18",
                             fg="#aaaaee", font=("Consolas", 9))
    lbl_lang_info.pack(anchor=tk.W, pady=(6, 0))

    def combo_langue_event(nouvelle_locale):
        """Appelé par les boutons drapeaux."""
        on_langue_changee(forced_locale=nouvelle_locale)

    def on_langue_changee(event=None, forced_locale=None):
        global LOCALE_ACTUELLE
        if forced_locale:
            nouvelle_locale = forced_locale
        else:
            selection = langue_var.get()
            nouvelle_locale = next((loc for lbl, loc in LANGUES_MENU if lbl == selection), None)
        if not nouvelle_locale or nouvelle_locale == LOCALE_ACTUELLE:
            return

        # ── Vérifier si le modèle requis est installé ─────────────────────────
        modele_requis = MODELE_PAR_LOCALE.get(nouvelle_locale, "mistral-nemo")
        modele_actuel = MODELE_PAR_LOCALE.get(LOCALE_ACTUELLE, "mistral-nemo")
        if modele_requis != modele_actuel:
            try:
                import ollama as _ol
                modeles_norm = [m.model.split(":")[0] for m in _ol.list().models if m.model]
                if modele_requis.split(":")[0] not in modeles_norm:
                    # Revenir visuellement au choix précédent
                    _select_langue(LOCALE_ACTUELLE)
                    def _relancer_apres_install(nl=nouvelle_locale):
                        _select_langue(nl)
                    _proposer_installation_modele(
                        modele_requis, nouvelle_locale,
                        callback_relancer=_relancer_apres_install
                    )
                    return
            except Exception:
                pass  # Ollama inaccessible → on laisse passer, le bot détectera au démarrage

        ancienne_locale = LOCALE_ACTUELLE
        LOCALE_ACTUELLE = nouvelle_locale
        emoji = LOCALE_EMOJI.get(nouvelle_locale, "🌍")
        lang  = LANGUES_PROMPT.get(nouvelle_locale, nouvelle_locale)

        msg = f"🌍 Langue changée : {ancienne_locale} → {nouvelle_locale} ({lang})"
        lbl_lang_info.config(text=f"{emoji} {lang}", fg="#aaaaee")

        # Log dans le fichier
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n{msg}\n")

        send_to_discord(f"🌍 Langue changée : **{ancienne_locale}** → **{nouvelle_locale}** ({emoji} {lang})")

        # Si le bot API tourne → le redémarrer avec la nouvelle locale
        if _running(bot_api):
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"🔄 Redémarrage du bot API pour la locale {nouvelle_locale}...\n")
            stop_api_direct()
            fenetre.after(1500, start_api_direct)

        # Si le bot Puzzle tourne → le redémarrer
        if _running(bot_puzzle):
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"🔄 Redémarrage du bot Puzzle pour la locale {nouvelle_locale}...\n")
            stop_puzzle_direct()
            # Attendre que l'ancien thread soit mort avant de démarrer le nouveau
            # (évite 2 Firefox sur le même profil → crash marionette)
            locale_cible = nouvelle_locale
            gen_actuelle = _puzzle_restart_gen
            def _restart_apres_arret():
                if thread_puzzle and thread_puzzle.is_alive():
                    thread_puzzle.join(timeout=25)
                # Annuler si l'utilisateur a fait un arrêt manuel entre-temps
                if _puzzle_restart_gen != gen_actuelle:
                    return
                # Annuler si compte désactivé
                try:
                    with open(LOG_FILE, "r", encoding="utf-8") as _f:
                        if "Compte désactivé" in _f.read()[-500:]:
                            return
                except:
                    pass
                if not _running(bot_puzzle):
                    fenetre.after(0, start_puzzle_direct)
            threading.Thread(target=_restart_apres_arret, daemon=True).start()

        # Si le bot Verify tourne → le redémarrer avec la nouvelle locale
        if _running(bot_verify):
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"🔄 Redémarrage du bot Verify pour la locale {nouvelle_locale}...\n")
            gen_ver_actuelle = _verify_restart_gen
            stop_verify_direct()
            def _restart_verify_apres_arret():
                if thread_verify and thread_verify.is_alive():
                    thread_verify.join(timeout=25)
                if _verify_restart_gen != gen_ver_actuelle:
                    return
                if not _running(bot_verify):
                    fenetre.after(0, start_verify_direct)
            threading.Thread(target=_restart_verify_apres_arret, daemon=True).start()

    # Initialiser le label info
    _init_emoji = LOCALE_EMOJI.get(LOCALE_ACTUELLE, "🌍")
    _init_lang  = LANGUES_PROMPT.get(LOCALE_ACTUELLE, LOCALE_ACTUELLE)
    lbl_lang_info.config(text=f"{_init_emoji}  {_init_lang}",
                         fg=_LOCALE_COLORS.get(LOCALE_ACTUELLE, "#aaaaee"))

    # ── COMPTEUR DP & TOTAL ───────────────────────────────────────────────────
    frame_dp = tk.Frame(fenetre, bg="#120f00", pady=10, padx=18,
                        highlightbackground="#3a2800", highlightthickness=1)
    frame_dp.pack(fill=tk.X, padx=16, pady=(10, 0))

    # DP session (gros, à gauche)
    lbl_dp_session = tk.Label(frame_dp, text="💰  0.00 DP  cette session",
                               bg="#120f00", fg="#f0c030",
                               font=("Consolas", 20, "bold"))
    lbl_dp_session.pack(side=tk.LEFT)

    # Détail DP (petit, à gauche sous le gros)
    frame_dp_right = tk.Frame(frame_dp, bg="#120f00")
    frame_dp_right.pack(side=tk.RIGHT, anchor=tk.E)

    lbl_dp_detail = tk.Label(frame_dp_right, text="API : 0.00 DP   |   Puzzle : 0.00 DP",
                              bg="#120f00", fg="#7a6010",
                              font=("Consolas", 9))
    lbl_dp_detail.pack(anchor=tk.E)

    total_prev = stats_prev.get("total_api", 0) + stats_prev.get("total_puzzle", 0)
    lbl_total = tk.Label(frame_dp_right,
                          text=f"📊  {total_prev:,} traductions au total (toutes sessions)",
                          bg="#120f00", fg="#556644",
                          font=("Consolas", 9))
    lbl_total.pack(anchor=tk.E, pady=(4, 0))

    # ── PANNEAU DE CONTRÔLE : API + PUZZLE ───────────────────────────────────
    frame_controle = tk.Frame(fenetre, bg="#0d0d1a")
    frame_controle.pack(fill=tk.X, padx=16, pady=(12, 0))
    frame_controle.columnconfigure(0, weight=1)
    frame_controle.columnconfigure(1, weight=1)
    frame_controle.columnconfigure(2, weight=1)
    frame_controle.columnconfigure(3, weight=1)

    # — Panneau API (bleu) —
    frame_api = tk.Frame(frame_controle, bg="#07111f", pady=12, padx=16,
                         highlightbackground="#1a4a8a", highlightthickness=1)
    frame_api.grid(row=0, column=0, sticky="nsew", padx=(0, 6))

    tk.Label(frame_api, text="⚡  MODE API", bg="#07111f",
             fg="#2255aa", font=("Consolas", 8, "bold")).pack(anchor=tk.W)

    lbl_api_statut = tk.Label(frame_api, text="⏸  Arrêté", bg="#07111f",
                               fg="#336699", font=("Consolas", 14, "bold"))
    lbl_api_statut.pack(anchor=tk.W, pady=(4, 0))

    lbl_api_detail = tk.Label(frame_api, text="En attente de démarrage...", bg="#07111f",
                               fg="#334455", font=("Consolas", 8))
    lbl_api_detail.pack(anchor=tk.W)

    btn_api = tk.Button(
        frame_api,
        text="🚀  Démarrer Mode API",
        bg="#0e3320", fg="#44dd88",
        font=("Segoe UI", 10, "bold"),
        relief="flat", cursor="hand2",
        pady=7, padx=10,
        activebackground="#1a5a35", activeforeground="#88ffaa",
        command=lambda: (start_api_direct() if not _running(bot_api) else stop_api_direct())
    )
    btn_api.pack(fill=tk.X, pady=(10, 0))

    # — Panneau Puzzle (violet) —
    frame_puz = tk.Frame(frame_controle, bg="#110720", pady=12, padx=16,
                         highlightbackground="#5a1a8a", highlightthickness=1)
    frame_puz.grid(row=0, column=1, sticky="nsew", padx=(3, 3))

    tk.Label(frame_puz, text="🧩  MODE PUZZLE", bg="#110720",
             fg="#6633aa", font=("Consolas", 8, "bold")).pack(anchor=tk.W)

    lbl_puz_statut = tk.Label(frame_puz, text="⏸  Arrêté", bg="#110720",
                               fg="#553388", font=("Consolas", 14, "bold"))
    lbl_puz_statut.pack(anchor=tk.W, pady=(4, 0))

    lbl_puz_detail = tk.Label(frame_puz, text="En attente de démarrage...", bg="#110720",
                               fg="#334455", font=("Consolas", 8))
    lbl_puz_detail.pack(anchor=tk.W)

    btn_puz = tk.Button(
        frame_puz,
        text="🚀  Démarrer Mode Puzzle",
        bg="#1e0d38", fg="#bb66ff",
        font=("Segoe UI", 10, "bold"),
        relief="flat", cursor="hand2",
        pady=7, padx=10,
        activebackground="#2d1255", activeforeground="#dd99ff",
        command=lambda: (start_puzzle_direct() if not _running(bot_puzzle) else stop_puzzle_direct())
    )
    btn_puz.pack(fill=tk.X, pady=(10, 0))

    # — Panneau Verify (bleu clair) —
    frame_ver = tk.Frame(frame_controle, bg="#0a1a2a", pady=12, padx=16,
                         highlightbackground="#1a5a8a", highlightthickness=1)
    frame_ver.grid(row=0, column=2, sticky="nsew", padx=(6, 0))

    tk.Label(frame_ver, text="✔️  MODE VERIFY", bg="#0a1a2a",
             fg="#33aaff", font=("Consolas", 8, "bold")).pack(anchor=tk.W)

    lbl_ver_statut = tk.Label(frame_ver, text="⏸  Arrêté", bg="#0a1a2a",
                               fg="#335588", font=("Consolas", 14, "bold"))
    lbl_ver_statut.pack(anchor=tk.W, pady=(4, 0))

    lbl_ver_detail = tk.Label(frame_ver, text="En attente de démarrage...", bg="#0a1a2a",
                               fg="#334455", font=("Consolas", 8))
    lbl_ver_detail.pack(anchor=tk.W)

    btn_ver = tk.Button(
        frame_ver,
        text="🚀  Démarrer Mode Verify",
        bg="#0d2a4a", fg="#66bbff",
        font=("Segoe UI", 10, "bold"),
        relief="flat", cursor="hand2",
        pady=7, padx=10,
        activebackground="#123a6a", activeforeground="#99ddff",
        command=lambda: (start_verify_direct() if not _running(bot_verify) else stop_verify_direct())
    )
    btn_ver.pack(fill=tk.X, pady=(10, 0))

    # — Panneau Notifications (orange) —
    frame_notif = tk.Frame(frame_controle, bg="#1a1200", pady=12, padx=16,
                           highlightbackground="#8a5a1a", highlightthickness=1)
    frame_notif.grid(row=0, column=3, sticky="nsew", padx=(6, 0))

    tk.Label(frame_notif, text="🔔  NOTIFICATIONS", bg="#1a1200",
             fg="#aa6622", font=("Consolas", 8, "bold")).pack(anchor=tk.W)

    lbl_notif_statut = tk.Label(frame_notif, text="⏸  En attente", bg="#1a1200",
                                 fg="#886633", font=("Consolas", 14, "bold"))
    lbl_notif_statut.pack(anchor=tk.W, pady=(4, 0))

    lbl_notif_detail = tk.Label(frame_notif, text="Cliquez pour vérifier les rejets", bg="#1a1200",
                                 fg="#554422", font=("Consolas", 8))
    lbl_notif_detail.pack(anchor=tk.W)

    btn_notif = tk.Button(
        frame_notif,
        text="🔔  Vérifier les rejets",
        bg="#2a1a00", fg="#ffaa44",
        font=("Segoe UI", 10, "bold"),
        relief="flat", cursor="hand2",
        pady=7, padx=10,
        activebackground="#3a2500", activeforeground="#ffcc77",
        command=start_notif_check
    )
    btn_notif.pack(fill=tk.X, pady=(10, 0))

    # ── COMPTEUR SESSION ─────────────────────────────────────────────────────
    lbl_compteur = tk.Label(fenetre, text="✅  0  traductions cette session",
                             bg="#0d0d1a", fg="#336655",
                             font=("Consolas", 11, "bold"))
    lbl_compteur.pack(anchor=tk.E, padx=20, pady=(8, 0))

    tk.Frame(fenetre, bg="#222233", height=1).pack(fill=tk.X, padx=16, pady=(8, 0))

    # ── TRADUCTIONS RÉCENTES ──────────────────────────────────────────────────
    tk.Label(fenetre, text="  ▸ TRADUCTIONS EN COURS", bg="#0d0d1a",
             fg="#444466", font=("Consolas", 8, "bold")).pack(
        anchor=tk.W, padx=16, pady=(8, 2))

    txt_trads = scrolledtext.ScrolledText(
        fenetre, bg="#07070f", fg="#ffffff",
        font=("Consolas", 10), wrap=tk.WORD,
        state=tk.DISABLED, height=10)
    txt_trads.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 4))
    txt_trads.tag_config("en",     foreground="#4d9fff", font=("Consolas", 10))
    txt_trads.tag_config("fr",     foreground="#44dd88", font=("Consolas", 10, "bold"))
    txt_trads.tag_config("sep",    foreground="#1a1a2a")
    txt_trads.tag_config("lbl_en", foreground="#1a3a66", font=("Consolas", 9))
    txt_trads.tag_config("lbl_fr", foreground="#1a4433", font=("Consolas", 9))

    # ── LOGS TECHNIQUES ───────────────────────────────────────────────────────
    tk.Label(fenetre, text="  ▸ LOGS TECHNIQUES", bg="#0d0d1a",
             fg="#333344", font=("Consolas", 8, "bold")).pack(
        anchor=tk.W, padx=16, pady=(4, 2))

    txt_logs = scrolledtext.ScrolledText(
        fenetre, bg="#040408", fg="#445566",
        font=("Consolas", 8), height=7, wrap=tk.WORD)
    txt_logs.pack(fill=tk.X, padx=16, pady=(0, 14))

    # ── BOUCLE D'ACTUALISATION ────────────────────────────────────────────────
    position_log       = [0]
    nb_trads_affichees = [0]

    def actualiser():
        if not fenetre.winfo_exists(): return
        try:
            api_on    = _running(bot_api)
            puzzle_on = _running(bot_puzzle)
            verify_on = _running(bot_verify)

            # ── Compteur DP ──────────────────────────────────────────────────
            nb_api_sess = getattr(bot_api,    'trads_reussies', 0) if bot_api    else 0
            nb_puz_sess = getattr(bot_puzzle, 'trads_reussies', 0) if bot_puzzle else 0
            nb_ver_sess = getattr(bot_verify, 'verifs_reussies', 0) if bot_verify else 0
            dp_api  = nb_api_sess * DP_PAR_API
            dp_puz  = nb_puz_sess * DP_PAR_PUZZLE
            dp_sess = dp_api + dp_puz
            lbl_dp_session.config(text=f"💰  {dp_sess:.2f} DP  cette session")
            lbl_dp_detail.config(
                text=f"API : {dp_api:.2f} DP  ({nb_api_sess} trad.)   |   "
                     f"Puzzle : {dp_puz:.2f} DP  ({nb_puz_sess} trad.)"
            )
            total_all = (stats_prev.get("total_api", 0) + nb_api_sess +
                         stats_prev.get("total_puzzle", 0) + nb_puz_sess)
            lbl_total.config(text=f"📊  {total_all:,} traductions au total (toutes sessions)")

            # Panneau API
            if api_on:
                nb_api = getattr(bot_api, 'trads_reussies', 0)
                offset = getattr(bot_api, 'current_offset', '—')
                nb_ids = len(getattr(bot_api, 'processed_ids', set()))
                speed_api = ""
                if bot_api_start_time:
                    elapsed_h = (time.time() - bot_api_start_time) / 3600
                    if elapsed_h > 0.01:
                        speed_api = f"   |   ~{int(nb_api / elapsed_h)} trad/h"
                lbl_api_statut.config(text=f"🟢  {nb_api} traductions", fg="#4d9fff")
                lbl_api_detail.config(text=f"Offset : {offset}   |   IDs : {nb_ids}{speed_api}")
                frame_api.config(highlightbackground="#2266cc")
                btn_api.config(text="🛑  Arrêter Mode API",
                               bg="#3a0d0d", fg="#ff6666",
                               activebackground="#5a1515", activeforeground="#ff9999")
            else:
                nb_api = getattr(bot_api, 'trads_reussies', 0) if bot_api else 0
                lbl_api_statut.config(text="⏸  Arrêté", fg="#336699")
                lbl_api_detail.config(text=f"{nb_api} traductions cette session" if nb_api else "En attente de démarrage...")
                frame_api.config(highlightbackground="#1a4a8a")
                btn_api.config(text="🚀  Démarrer Mode API",
                               bg="#0e3320", fg="#44dd88",
                               activebackground="#1a5a35", activeforeground="#88ffaa")

            # Panneau Puzzle
            if puzzle_on:
                nb_puz = getattr(bot_puzzle, 'trads_reussies', 0)
                nav    = getattr(bot_puzzle, 'navigateur', '?')
                speed_puz = ""
                if bot_puzzle_start_time:
                    elapsed_h = (time.time() - bot_puzzle_start_time) / 3600
                    if elapsed_h > 0.01:
                        speed_puz = f"   |   ~{int(nb_puz / elapsed_h)} trad/h"
                lbl_puz_statut.config(text=f"🟢  {nb_puz} traductions", fg="#bb66ff")
                lbl_puz_detail.config(text=f"Navigateur : {nav}{speed_puz}")
                frame_puz.config(highlightbackground="#8833cc")
                btn_puz.config(text="🛑  Arrêter Mode Puzzle",
                               bg="#1e0633", fg="#dd77ff",
                               activebackground="#330a55", activeforeground="#eeb3ff")
            else:
                nb_puz = getattr(bot_puzzle, 'trads_reussies', 0) if bot_puzzle else 0
                lbl_puz_statut.config(text="⏸  Arrêté", fg="#553388")
                lbl_puz_detail.config(text=f"{nb_puz} traductions cette session" if nb_puz else "En attente de démarrage...")
                frame_puz.config(highlightbackground="#5a1a8a")
                btn_puz.config(text="🚀  Démarrer Mode Puzzle",
                               bg="#1e0d38", fg="#bb66ff",
                               activebackground="#2d1255", activeforeground="#dd99ff")

            # Panneau Verify
            if verify_on:
                nb_ver = getattr(bot_verify, 'verifs_reussies', 0)
                nav_ver = getattr(bot_verify, 'navigateur', '?')
                lbl_ver_statut.config(text=f"🟢  {nb_ver} vérifications", fg="#33aaff")
                lbl_ver_detail.config(text=f"Navigateur : {nav_ver}")
                frame_ver.config(highlightbackground="#1a5a8a")
                btn_ver.config(text="🛑  Arrêter Mode Verify",
                               bg="#061e33", fg="#77ddff",
                               activebackground="#0a3355", activeforeground="#b3eeff")
            else:
                nb_ver = getattr(bot_verify, 'verifs_reussies', 0) if bot_verify else 0
                lbl_ver_statut.config(text="⏸  Arrêté", fg="#335588")
                lbl_ver_detail.config(text=f"{nb_ver} vérifications cette session" if nb_ver else "En attente de démarrage...")
                frame_ver.config(highlightbackground="#1a3a5a")
                btn_ver.config(text="🚀  Démarrer Mode Verify",
                               bg="#0d1e38", fg="#66bbff",
                               activebackground="#122d55", activeforeground="#99ddff")

            # Panneau Notifications
            if notif_running:
                lbl_notif_statut.config(text="🔄  Vérification...", fg="#ffaa44")
                lbl_notif_detail.config(text="Analyse des rejets en cours...")
                frame_notif.config(highlightbackground="#cc8833")
                btn_notif.config(text="🔄  Vérification en cours...",
                                 bg="#3a2500", fg="#ffcc77",
                                 activebackground="#3a2500", activeforeground="#ffcc77")
            else:
                total_rejets = notif_rejets_count + notif_repaired_count
                if total_rejets > 0:
                    lbl_notif_statut.config(text=f"🔔  {total_rejets} rejet(s)", fg="#ff8833")
                    lbl_notif_detail.config(text=f"API: {notif_rejets_count} | Corrigés: {notif_repaired_count}")
                    frame_notif.config(highlightbackground="#cc6600")
                else:
                    lbl_notif_statut.config(text="✅  Aucun rejet", fg="#886633")
                    lbl_notif_detail.config(text="Cliquez pour vérifier les rejets")
                    frame_notif.config(highlightbackground="#8a5a1a")
                btn_notif.config(text="🔔  Vérifier les rejets",
                                 bg="#2a1a00", fg="#ffaa44",
                                 activebackground="#3a2500", activeforeground="#ffcc77")

            # Compteur session
            total_sess = nb_api_sess + nb_puz_sess + nb_ver_sess
            lbl_compteur.config(text=f"✅  {total_sess}  actions cette session")

            # Nouvelles traductions
            tous = []
            for inst in [bot_api, bot_puzzle, bot_verify]:
                if inst:
                    tous += getattr(inst, 'historique_trads', [])
            total_hist = len(tous)
            if total_hist > nb_trads_affichees[0]:
                nouvelles = tous[nb_trads_affichees[0]:]
                txt_trads.config(state=tk.NORMAL)
                for t in nouvelles:
                    en        = t['en'][:200].replace('\n', ' ')
                    fr        = t['fr'][:200].replace('\n', ' ')
                    flag_trad = t.get('emoji', LOCALE_EMOJI.get(LOCALE_ACTUELLE, "🌍"))
                    txt_trads.insert(tk.END, "🇬🇧 ", "lbl_en")
                    txt_trads.insert(tk.END, en + "\n", "en")
                    txt_trads.insert(tk.END, f"{flag_trad} ", "lbl_fr")
                    txt_trads.insert(tk.END, fr + "\n", "fr")
                    txt_trads.insert(tk.END, "─" * 90 + "\n", "sep")
                txt_trads.see(tk.END)
                txt_trads.config(state=tk.DISABLED)
                nb_trads_affichees[0] = total_hist

            # Logs techniques
            if LOG_FILE.exists():
                with open(LOG_FILE, 'r', encoding='utf-8') as f:
                    f.seek(position_log[0])
                    lignes = f.readlines()
                    position_log[0] = f.tell()
                if lignes:
                    for ligne in lignes:
                        txt_logs.insert(tk.END, ligne)
                    txt_logs.see(tk.END)
        except: pass

        fenetre.after(500, actualiser)

    actualiser()

    moniteur_fenetre = fenetre
    return fenetre

# ==========================================
# 🎛️ MENU TRAY (simplifié — contrôle dans le moniteur)
# ==========================================
menu = pystray.Menu(
    pystray.MenuItem("📊 Afficher le Moniteur", lambda icon, item: afficher_moniteur()),
    pystray.Menu.SEPARATOR,
    pystray.MenuItem(f"Version : {CURRENT_VERSION}", lambda: None, enabled=False),
    pystray.MenuItem("❌ Quitter", quit_app)
)

# ==========================================
# 🚀 DÉMARRAGE
# ==========================================
_generate_ico()

# Message de bienvenue (premier lancement uniquement)
afficher_message_bienvenue()

# Vérification mise à jour avant le login
new_v, asset_url = check_for_updates()
if new_v and asset_url:
    apply_update(asset_url)

# Sync dictionnaires depuis GitHub
try:
    sync_dictionnaires()
except Exception:
    pass

# Fenêtre de connexion
identifiants_memoire = lancer_fenetre_connexion(BASE_DIR, version=CURRENT_VERSION)
if identifiants_memoire is None:
    sys.exit(0)

utilisateur_actuel = identifiants_memoire.get("user", "Inconnu")

# Sécurité compte Zaraki : HWID unique obligatoire
if utilisateur_actuel.lower().strip() == "zaraki" and get_hwid() not in ["8EFF04FB-761A-8C81-993B-F02F741F235E"]:
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showerror("Accès Refusé", "Vous n'êtes pas le véritable Zaraki ! (HWID invalide)")
    send_to_discord(f"🚨 **ALERTE SÉCURITÉ** : Tentative d'usurpation du compte Zaraki par l'HWID {get_hwid()}.")
    sys.exit(0)

# Kill switch
if not verifier_acces(utilisateur_actuel):
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showerror("Accès Bloqué", "L'accès à ce logiciel a été suspendu pour ce compte ou cet ordinateur.")
    send_to_discord("🚨 **ALERTE SÉCURITÉ** : Tentative de connexion bloquée par la Blocklist.")
    sys.exit(0)

GLOBAL_CREDENTIALS = identifiants_memoire
GLOBAL_CREDENTIALS["webhook"] = get_discord_url()

# Enregistrement du lancement (username + HWID + machine)
threading.Thread(target=enregistrer_lancement, args=(utilisateur_actuel,), daemon=True).start()

# Surveillance kill switch + inactivité
threading.Thread(target=surveillance_active, daemon=True).start()
threading.Thread(target=surveiller_inactivite, daemon=True).start()

# Vérification / démarrage d'Ollama
verifier_demarrer_ollama()

# Vérification automatique des rejets (toutes les 5 min)
threading.Thread(target=_check_notifications_loop, daemon=True).start()

# Tray en arrière-plan
app_icon = pystray.Icon("WoWBot", create_default_icon(), "WoW Translator", menu)
threading.Thread(target=app_icon.run, daemon=True).start()

# Moniteur en thread principal (bloquant)
fenetre = lancer_moniteur_principal()
fenetre.mainloop()

sys.exit(0)
