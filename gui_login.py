import tkinter as tk
from tkinter import ttk
import json
import base64
from pathlib import Path
from PIL import Image, ImageDraw, ImageTk

def lancer_fenetre_connexion(base_dir, version=""):
    config_file = base_dir / "config_user.json"
    identifiants = {"user": "", "pass": "", "token": ""}
    fenetre_validee = False

    def charger_sauvegarde():
        if config_file.exists():
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                    user = data.get("user", "")
                    token = data.get("token", "")
                    mdp = base64.b64decode(data.get("pass", "").encode()).decode() if data.get("pass") else ""
                    return user, mdp, token, data.get("remember", False)
            except: pass
        return "", "", "", False

    def sauvegarder_config(user, mdp, token, remember):
        if remember:
            mdp_cache = base64.b64encode(mdp.encode()).decode()
            data = {"user": user, "pass": mdp_cache, "token": token, "remember": True}
            with open(config_file, "w") as f: json.dump(data, f)
        else:
            if config_file.exists(): config_file.unlink()

    def valider_connexion():
        nonlocal fenetre_validee
        u = entry_user.get().strip()
        p = entry_pass.get().strip()
        t = entry_token.get().strip()

        if not u or not p:
            lbl_erreur.config(text="❌ L'identifiant et le mot de passe sont obligatoires !")
            return
        
        identifiants["user"] = u
        identifiants["pass"] = p
        identifiants["token"] = t
        
        sauvegarder_config(u, p, t, var_remember.get())
        fenetre_validee = True
        root.destroy()

    root = tk.Tk()
    root.title("WoW Translator - Connexion")
    root.geometry("400x450")
    root.configure(bg="#1e1e1e")
    root.resizable(False, False)
    root.eval('tk::PlaceWindow . center')

    # Icône personnalisée (.ico généré par launcher)
    try:
        ico = base_dir / "icon.ico"
        if ico.exists():
            root.iconbitmap(str(ico))
    except: pass

    style = ttk.Style()
    style.theme_use('clam')
    style.configure("TLabel", background="#1e1e1e", foreground="#ffffff", font=("Segoe UI", 10))
    style.configure("TCheckbutton", background="#1e1e1e", foreground="#ffffff")
    
    tk.Label(root, text="Connexion au Bot", font=("Segoe UI", 16, "bold"), bg="#1e1e1e", fg="#00a8ff").pack(pady=(20, 2))
    if version:
        tk.Label(root, text=version, font=("Segoe UI", 8), bg="#1e1e1e", fg="#555555").pack(pady=(0, 10))

    ttk.Label(root, text="Identifiant (Username) :").pack(anchor="w", padx=40)
    entry_user = ttk.Entry(root, width=40, font=("Segoe UI", 10))
    entry_user.pack(pady=5, padx=40)

    ttk.Label(root, text="Mot de passe :").pack(anchor="w", padx=40, pady=(10, 0))
    entry_pass = ttk.Entry(root, width=40, show="*", font=("Segoe UI", 10))
    entry_pass.pack(pady=5, padx=40)

    ttk.Label(root, text="Clé API (Optionnelle) :").pack(anchor="w", padx=40, pady=(10, 0))
    entry_token = ttk.Entry(root, width=40, font=("Segoe UI", 10))
    entry_token.pack(pady=5, padx=40)

    var_remember = tk.BooleanVar()
    chk_remember = ttk.Checkbutton(root, text="Se souvenir de moi", variable=var_remember)
    chk_remember.pack(pady=10, anchor="w", padx=40)

    lbl_erreur = tk.Label(root, text="", bg="#1e1e1e", fg="#ff4757", font=("Segoe UI", 9))
    lbl_erreur.pack(pady=5)

    btn_login = tk.Button(root, text="Lancer le Bot 🚀", bg="#00a8ff", fg="white", font=("Segoe UI", 12, "bold"), 
                          relief="flat", cursor="hand2", command=valider_connexion)
    btn_login.pack(pady=10, ipadx=20, ipady=5)

    # ⌨️ Binding Enter sur tous les champs pour valider sans cliquer
    for entry in (entry_user, entry_pass, entry_token):
        entry.bind("<Return>", lambda e: valider_connexion())

    u_save, p_save, t_save, r_save = charger_sauvegarde()
    if r_save:
        entry_user.insert(0, u_save)
        entry_pass.insert(0, p_save)
        entry_token.insert(0, t_save)
        var_remember.set(True)

    root.mainloop()
    if not fenetre_validee: return None
    return identifiants