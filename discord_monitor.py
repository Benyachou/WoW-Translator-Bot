"""
Lecteur de logs Discord - Extraction utilisateurs + HWIDs
Permet d'ajouter directement à la blocklist GitHub
"""

import os
import json
import base64
import re
import requests
import config_manager

BOT_TOKEN    = config_manager.get("secrets", "discord_bot_token", fallback="")
CHANNEL_ID   = config_manager.get("general", "discord_channel_id")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO  = "Benyachou/WoW-Translator-Bot"

DISCORD_HEADERS = {"Authorization": f"Bot {BOT_TOKEN}"}
GITHUB_HEADERS  = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}


def get_messages(limit=100):
    url = f"https://discord.com/api/v10/channels/{CHANNEL_ID}/messages?limit={limit}"
    resp = requests.get(url, headers=DISCORD_HEADERS)
    resp.raise_for_status()
    return resp.json()


def extraire_users_hwids(messages):
    pattern = r"\[(.+?)\s*\|\s*HWID:\s*([A-F0-9\-]+)\]"
    vus = {}
    for msg in messages:
        content = msg.get("content", "")
        match = re.search(pattern, content)
        if match:
            user = match.group(1).strip()
            hwid = match.group(2).strip()
            if user not in vus:
                vus[user] = hwid
    return vus


def get_blocklist():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/blocklist.json"
    resp = requests.get(url, headers={**GITHUB_HEADERS, "Accept": "application/vnd.github.v3.raw"})
    resp.raise_for_status()
    return resp.json()


def get_blocklist_sha():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/blocklist.json"
    resp = requests.get(url, headers=GITHUB_HEADERS)
    resp.raise_for_status()
    return resp.json()["sha"]


def bloquer_user(username=None, hwid=None):
    data = get_blocklist()
    sha  = get_blocklist_sha()

    if username and username.lower() not in [u.lower() for u in data["blocked_users"]]:
        data["blocked_users"].append(username)
    if hwid and hwid.upper() not in [h.upper() for h in data["blocked_hwids"]]:
        data["blocked_hwids"].append(hwid)

    content_b64 = base64.b64encode(json.dumps(data, indent=2).encode()).decode()
    payload = {
        "message": f"blocklist: ajout {username or hwid}",
        "content": content_b64,
        "sha": sha,
        "branch": "main"
    }
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/blocklist.json"
    resp = requests.put(url, headers=GITHUB_HEADERS, json=payload)
    resp.raise_for_status()
    print("  Bloque avec succes !")


def afficher_blocklist():
    data = get_blocklist()
    print("\n=== BLOCKLIST ACTUELLE ===")
    print(f"  Users bloques  : {data['blocked_users'] or 'aucun'}")
    print(f"  HWIDs bloques  : {data['blocked_hwids'] or 'aucun'}")


def main():
    print("=== DISCORD MONITOR - WoW Translator ===")
    print("Recuperation des messages...\n")

    try:
        messages = get_messages(100)
    except Exception as e:
        print(f"Erreur Discord : {e}")
        return

    users = extraire_users_hwids(messages)

    if not users:
        print("Aucun utilisateur detecte dans les logs.")
    else:
        print(f"{len(users)} utilisateur(s) detecte(s) :\n")
        liste = list(users.items())
        for i, (user, hwid) in enumerate(liste):
            print(f"  [{i+1}] {user}  |  HWID: {hwid}")

    afficher_blocklist()

    print("\n--- OPTIONS ---")
    print("  [numero] Bloquer un utilisateur de la liste")
    print("  [b]      Bloquer un user/HWID manuellement")
    print("  [q]      Quitter")

    while True:
        choix = input("\nChoix : ").strip().lower()

        if choix == "q":
            break

        elif choix == "b":
            u = input("  Username (laisser vide si aucun) : ").strip() or None
            h = input("  HWID (laisser vide si aucun)     : ").strip() or None
            if u or h:
                bloquer_user(username=u, hwid=h)
                afficher_blocklist()

        elif choix.isdigit():
            idx = int(choix) - 1
            if 0 <= idx < len(liste):
                user, hwid = liste[idx]
                print(f"  Blocage de {user} (HWID: {hwid})...")
                bloquer_user(username=user, hwid=hwid)
                afficher_blocklist()
            else:
                print("  Numero invalide.")
        else:
            print("  Commande inconnue.")


if __name__ == "__main__":
    main()
