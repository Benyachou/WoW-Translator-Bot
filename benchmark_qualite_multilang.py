"""
╔══════════════════════════════════════════════════════════════════════╗
║   WoW Translator — BENCHMARK QUALITÉ MULTILINGUE                    ║
║   Tests stricts + détection automatique des erreurs                  ║
╚══════════════════════════════════════════════════════════════════════╝

Usage :
    python benchmark_qualite_multilang.py              → toutes locales
    python benchmark_qualite_multilang.py esES deDE    → locales ciblées
    python benchmark_qualite_multilang.py esES --fix   → benchmark + rapport détaillé
"""

import sys, re, time, json
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

import ollama

# ──────────────────────────────────────────────────────────────────────────────
# CORPUS DE TEST — 25 textes WoW couvrant tous les cas critiques
# ──────────────────────────────────────────────────────────────────────────────

CORPUS = [
    # ── Pronoms "you" simples ──────────────────────────────────────────────────
    {"id": "P01", "cat": "Pronom you simple",
     "en": "You have been chosen, $N."},
    {"id": "P02", "cat": "Pronom you possessif",
     "en": "Your courage will be rewarded."},
    {"id": "P03", "cat": "Pronoms multiples",
     "en": "You must gather your allies before you attempt this quest."},
    {"id": "P04", "cat": "Impératif (you implicite)",
     "en": "Come to me when you are ready to face your destiny."},
    {"id": "P05", "cat": "Adresse directe",
     "en": "I need you to deliver this message to Commander Voss. Can you do this for me?"},

    # ── Dialogues PNJ ─────────────────────────────────────────────────────────
    {"id": "D01", "cat": "Dialog PNJ quête",
     "en": "Greetings, $N. The Burning Legion threatens our world once more. You must be our champion."},
    {"id": "D02", "cat": "Dialog urgence",
     "en": "You have to leave NOW. They know you are here. Take your belongings and go!"},
    {"id": "D03", "cat": "Dialog récompense",
     "en": "You have proven yourself worthy. Your name will be remembered by all who fight for the Light."},
    {"id": "D04", "cat": "Dialog conditionnel",
     "en": "If you can defeat the Lich King, you will have your revenge. But beware — you are not strong enough yet."},
    {"id": "D05", "cat": "Dialog informatif long",
     "en": "The Burning Legion has returned, $N. You must gather your allies and prepare for the battle ahead. Return to me when you have completed your preparations, and I will give you everything you need."},

    # ── Descriptions d'objets avec $B ─────────────────────────────────────────
    {"id": "I01", "cat": "Item simple",
     "en": "Increases your critical strike rating by 22."},
    {"id": "I02", "cat": "Item avec tags $B",
     "en": "Khadgar's Ancient Staff$BBinds when picked up$BTwo-Hand Staff$BRequires Level 60"},
    {"id": "I03", "cat": "Item possessif 's",
     "en": "Onyxia's Scale Cloak$BBinds when equipped$BChest$BDurability 100 / 100"},
    {"id": "I04", "cat": "Item avec %s",
     "en": "When you deal damage, you have a chance to increase your attack power by %s for 10 sec."},
    {"id": "I05", "cat": "Item set bonus",
     "en": "Set: Your healing spells have a chance to mend your target for additional health.$B(2) Set: Increases your healing done by 35."},

    # ── Textes de combat / capacités ──────────────────────────────────────────
    {"id": "C01", "cat": "Sort description",
     "en": "Deals %s Fire damage to your target and burns them for %s additional damage over 8 sec."},
    {"id": "C02", "cat": "Aura passive",
     "en": "Your melee attacks have a chance to apply a poison that reduces your target's movement speed."},
    {"id": "C03", "cat": "Capacité active",
     "en": "Consumes your Holy Power to heal you or a friendly target for a large amount."},
    {"id": "C04", "cat": "Combat log",
     "en": "Your Fireball critically hits for 4,521 Fire damage."},

    # ── Quêtes ────────────────────────────────────────────────────────────────
    {"id": "Q01", "cat": "Objectif de quête",
     "en": "Kill 10 Defias Bandits and bring their stolen goods back to me."},
    {"id": "Q02", "cat": "Texte de remise",
     "en": "You have done well, $N. Your efforts have saved countless lives. I knew I could count on you."},
    {"id": "Q03", "cat": "Quête avec choix",
     "en": "Choose your reward wisely, $N. Each item you see before you is a testament to your hard work."},

    # ── Guildes / groupes ─────────────────────────────────────────────────────
    {"id": "G01", "cat": "Message de guilde",
     "en": "Welcome to the guild! You will find that your new family will always have your back."},
    {"id": "G02", "cat": "Raid instruction",
     "en": "When you see the green fire, move out of it immediately. Your survival depends on it."},

    # ── Cas difficiles / pièges ───────────────────────────────────────────────
    {"id": "X01", "cat": "Possessif nom propre",
     "en": "Arthas's Betrayal was the darkest moment in Azeroth's history."},
    {"id": "X02", "cat": "MAJUSCULES urgence",
     "en": "YOU MUST DEFEND THE GATE NOW OR ALL IS LOST!"},
]

# ──────────────────────────────────────────────────────────────────────────────
# DÉFINITIONS PAR LOCALE — règles de prompt + vérifications + corrections
# ──────────────────────────────────────────────────────────────────────────────

LOCALES_CONFIG = {

    "esES": {
        "nom": "Spanish (Spain)",
        "emoji": "🇪🇸",
        "modele": "qwen2.5:14b",

        "rules_prompt": (
            "ABSOLUTE RULE #1 — VOSOTROS: "
            "You MUST use the vosotros form for the 2nd person plural in EVERY sentence. "
            "This is NON-NEGOTIABLE. Examples: "
            "tú→vosotros | te→os | tu→vuestro/vuestra | tus→vuestros/vuestras | "
            "tienes→tenéis | puedes→podéis | eres→sois | sabes→sabéis | quieres→queréis | "
            "debes→debéis | vas→vais | vienes→venís | recibirás→recibiréis | "
            "irás→iréis | harás→haréis | serás→seréis | tendrás→tendréis. "
            "Imperatives: ten→tened | ve→id | haz→haced | sé→sed | ven→venid | di→decid. "
            "NEVER use tú, te, tu, usted — ALWAYS use vosotros forms. "
            "RULE #2 — POSSESSIVES: 'Khadgar's Staff' → 'Bastón de Khadgar'. "
            "RULE #3 — OFFICIAL TERMINOLOGY: Use Blizzard ES-ES WoW terms. "
            "RULE #4 — GENDER AGREEMENT: vuestro/vuestra must match noun gender."
        ),

        "checks": [
            # (regex_bad, message_erreur, severite)
            (r'\btú\b',          "CRITIQUE: 'tú' → doit être 'vosotros'",   "CRITIQUE"),
            (r'\bte\b(?!\s*[.!?,])',  "CRITIQUE: 'te' → doit être 'os'",   "CRITIQUE"),
            (r'\btu\b(?!\s*[A-Z])',  "CRITIQUE: 'tu' possessif → doit être 'vuestro/vuestra'", "CRITIQUE"),
            (r'\btienes\b',      "CRITIQUE: 'tienes' → doit être 'tenéis'", "CRITIQUE"),
            (r'\bpuedes\b',      "CRITIQUE: 'puedes' → doit être 'podéis'", "CRITIQUE"),
            (r'\beres\b',        "CRITIQUE: 'eres' → doit être 'sois'",     "CRITIQUE"),
            (r'\busted\b',       "CRITIQUE: 'usted' interdit",              "CRITIQUE"),
            (r'\bUsted\b',       "CRITIQUE: 'Usted' interdit",              "CRITIQUE"),
            (r'\bdebes\b',       "WARN: 'debes' → 'debéis'",               "WARN"),
            (r'\bvas\b(?!\s+a\s+[A-Z])', "WARN: 'vas' → 'vais'",          "WARN"),
            (r'\bserás\b',       "WARN: 'serás' → 'seréis'",               "WARN"),
            (r'\btendrás\b',     "WARN: 'tendrás' → 'tendréis'",           "WARN"),
            (r'\brecibirás\b',   "WARN: 'recibirás' → 'recibiréis'",       "WARN"),
            (r'\bsabes\b',       "WARN: 'sabes' → 'sabéis'",               "WARN"),
            (r'\bquieres\b',     "WARN: 'quieres' → 'queréis'",            "WARN"),
        ],

        # Vérification positive — au moins une forme vosotros quand "you" est dans l'EN
        "check_positive": {
            "trigger_en": r'\b(you|your)\b',
            "pattern_good": r'\b(vosotros|vuestra|vuestro|vuestros|vuestras|tenéis|podéis|sois|sabéis|queréis|debéis|vais|venís|os\b|habéis|iréis|haréis|seréis|tendréis|recibiréis|seguís|vuest)\b',
            "message": "CRITIQUE: 'you' dans EN mais aucune forme vosotros trouvée",
        },

        "post_corrections": [
            # Pronoms sujets
            (r'\bTú\b',           'Vosotros'),
            (r'\btú\b',           'vosotros'),
            # Pronoms objets directs — attention aux faux positifs
            (r'\bTe\b(?=\s+\w)',  'Os'),
            (r'\bte\b(?=\s+\w)',  'os'),
            # Possessifs
            (r'\btus\b',          'vuestros'),
            (r'\bTus\b',          'Vuestros'),
            (r'\btu\b(?=\s+[a-záéíóúñ])', 'vuestro'),
            (r'\bTu\b(?=\s+[a-záéíóúñA-ZÁÉÍÓÚÑ])', 'Vuestro'),
            # Verbes tú → vosotros
            (r'\btienes\b',       'tenéis'),
            (r'\bTienes\b',       'Tenéis'),
            (r'\bpuedes\b',       'podéis'),
            (r'\bPuedes\b',       'Podéis'),
            (r'\beres\b',         'sois'),
            (r'\bEres\b',         'Sois'),
            (r'\bsabes\b',        'sabéis'),
            (r'\bSabes\b',        'Sabéis'),
            (r'\bquieres\b',      'queréis'),
            (r'\bQuieres\b',      'Queréis'),
            (r'\bdebes\b',        'debéis'),
            (r'\bDebes\b',        'Debéis'),
            (r'\bvas\b',          'vais'),
            (r'\bVas\b',          'Vais'),
            (r'\bvienes\b',       'venís'),
            (r'\bVienes\b',       'Venís'),
            (r'\bsigues\b',       'seguís'),
            (r'\bSigues\b',       'Seguís'),
            (r'\brecibirás\b',    'recibiréis'),
            (r'\bRecibirás\b',    'Recibiréis'),
            (r'\birás\b',         'iréis'),
            (r'\bIrás\b',         'Iréis'),
            (r'\bharás\b',        'haréis'),
            (r'\bHarás\b',        'Haréis'),
            (r'\bserás\b',        'seréis'),
            (r'\bSerás\b',        'Seréis'),
            (r'\btendrás\b',      'tendréis'),
            (r'\bTendrás\b',      'Tendréis'),
            (r'\bpodrás\b',       'podréis'),
            (r'\bPodrás\b',       'Podréis'),
            (r'\bvencerás\b',     'venceréis'),
            (r'\bVencerás\b',     'Venceréis'),
            (r'\bmatarás\b',      'mataréis'),
            (r'\bMatarás\b',      'Mataréis'),
            (r'\bdarás\b',        'daréis'),
            (r'\bDarás\b',        'Daréis'),
            (r'\bllevarás\b',     'llevaréis'),
            (r'\bLlevarás\b',     'Llevaréis'),
            (r'\btraerás\b',      'traeréis'),
            (r'\bTraerás\b',      'Traeréis'),
            (r'\bencontrarás\b',  'encontraréis'),
            (r'\bEncontrarás\b',  'Encontraréis'),
            (r'\bvencerás\b',     'venceréis'),
            # Formes usted
            (r'\bUsted\b',        'Vosotros'),
            (r'\busted\b',        'vosotros'),
            # Impératifs tú → vosotros
            (r'\bten\b(?=\s)',     'tened'),
            (r'\bTen\b(?=\s)',     'Tened'),
            (r'\bhaz\b(?=\s)',     'haced'),
            (r'\bHaz\b(?=\s)',     'Haced'),
            (r'\bsé\b(?=\s)',      'sed'),
            (r'\bSé\b(?=\s)',      'Sed'),
            (r'\bdi\b(?=\s)',      'decid'),
            (r'\bDi\b(?=\s)',      'Decid'),
        ],
    },

    "deDE": {
        "nom": "German",
        "emoji": "🇩🇪",
        "modele": "mistral-nemo",

        "rules_prompt": (
            "RULE #1 — NOUNS: Capitalize EVERY noun. This is mandatory German grammar. "
            "All common nouns start with uppercase: Schaden, Heilung, Zauber, Quest, Feind, Held, etc. "
            "RULE #2 — FORMAL YOU: ALWAYS use 'Ihr/Euch/Euer/Eure' for 2nd person. "
            "NEVER use du/dich/dein/dir/deine. Examples: "
            "you→Ihr | you (obj)→Euch | your→Euer/Eure/Euer | "
            "have→habt | are→seid | can→könnt | must→müsst | know→wisst. "
            "RULE #3 — POSSESSIVES: 'Khadgar's Staff' → 'Khadgars Stab'. "
            "RULE #4 — BLIZZARD TERMS: Use official Blizzard DE-DE WoW terminology."
        ),

        "checks": [
            (r'\bdu\b',   "CRITIQUE: 'du' interdit → 'Ihr'",      "CRITIQUE"),
            (r'\bDu\b',   "CRITIQUE: 'Du' interdit → 'Ihr'",      "CRITIQUE"),
            (r'\bdich\b', "CRITIQUE: 'dich' interdit → 'Euch'",   "CRITIQUE"),
            (r'\bDich\b', "CRITIQUE: 'Dich' interdit → 'Euch'",   "CRITIQUE"),
            (r'\bdein\b', "CRITIQUE: 'dein' interdit → 'Euer'",   "CRITIQUE"),
            (r'\bDein\b', "CRITIQUE: 'Dein' interdit → 'Euer'",   "CRITIQUE"),
            (r'\bdeine\b',"CRITIQUE: 'deine' interdit → 'Eure'",  "CRITIQUE"),
            (r'\bDeine\b',"CRITIQUE: 'Deine' interdit → 'Eure'",  "CRITIQUE"),
            (r'\bdir\b',  "WARN: 'dir' → 'Euch'",                 "WARN"),
            (r'\bbist\b', "WARN: 'bist' → 'seid'",                "WARN"),
            (r'\bhast\b(?!\s+[A-Z])', "WARN: 'hast' → 'habt'",   "WARN"),
            (r'\bkannst\b', "WARN: 'kannst' → 'könnt'",           "WARN"),
            (r'\bmusst\b',  "WARN: 'musst' → 'müsst'",            "WARN"),
            (r'\bweißt\b',  "WARN: 'weißt' → 'wisst'",            "WARN"),
        ],

        "check_positive": {
            "trigger_en": r'\b(you|your)\b',
            "pattern_good": r'\b(Ihr|Euch|Euer|Eure|Eures|Eurem|Eurer|Euren|habt|seid|könnt|müsst|wisst|wollt)\b',
            "message": "CRITIQUE: 'you' dans EN mais aucune forme Ihr/Euch/Euer trouvée",
        },

        "post_corrections": [
            (r'\bdu\b',     'Ihr'),
            (r'\bDu\b',     'Ihr'),
            (r'\bdich\b',   'Euch'),
            (r'\bDich\b',   'Euch'),
            (r'\bdir\b',    'Euch'),
            (r'\bDir\b',    'Euch'),
            (r'\bdein\b',   'Euer'),
            (r'\bDein\b',   'Euer'),
            (r'\bdeine\b',  'Eure'),
            (r'\bDeine\b',  'Eure'),
            (r'\bdeinen\b', 'Euren'),
            (r'\bDeinen\b', 'Euren'),
            (r'\bdeiner\b', 'Eurer'),
            (r'\bDeiner\b', 'Eurer'),
            (r'\bdeinem\b', 'Eurem'),
            (r'\bDeinem\b', 'Eurem'),
            (r'\bbist\b',   'seid'),
            (r'\bBist\b',   'Seid'),
            (r'\bhast\b',   'habt'),
            (r'\bHast\b',   'Habt'),
            (r'\bkannst\b', 'könnt'),
            (r'\bKannst\b', 'Könnt'),
            (r'\bmusst\b',  'müsst'),
            (r'\bMusst\b',  'Müsst'),
            (r'\bweißt\b',  'wisst'),
            (r'\bWeißt\b',  'Wisst'),
            # Majuscules nominales courantes
            (r'\bschaden\b',     'Schaden'),
            (r'\bheilung\b',     'Heilung'),
            (r'\bzauber\b',      'Zauber'),
            (r'\bfähigkeit\b',   'Fähigkeit'),
            (r'\bquest\b',       'Quest'),
            (r'\bgebiet\b',      'Gebiet'),
            (r'\bfeind\b',       'Feind'),
            (r'\bverbündeter\b', 'Verbündeter'),
            (r'\bspieler\b',     'Spieler'),
            (r'\bcharakter\b',   'Charakter'),
            (r'\bheld\b',        'Held'),
            (r'\bkraft\b',       'Kraft'),
            (r'\bmagie\b',       'Magie'),
            (r'\bwaffe\b',       'Waffe'),
            (r'\brüstung\b',     'Rüstung'),
            (r'\bkrieger\b',     'Krieger'),
            (r'\bpriester\b',    'Priester'),
            (r'\bmagier\b',      'Magier'),
            (r'\bgott\b',        'Gott'),
            (r'\bkönig\b',       'König'),
            (r'\breich\b',       'Reich'),
            (r'\bschloss\b',     'Schloss'),
            (r'\bburg\b',        'Burg'),
            (r'\bstadt\b',       'Stadt'),
            (r'\bdorf\b',        'Dorf'),
            (r'\bwelt\b',        'Welt'),
            (r'\bzeit\b',        'Zeit'),
            (r'\bkampf\b',       'Kampf'),
            (r'\bsieg\b',        'Sieg'),
            (r'\bniederlage\b',  'Niederlage'),
            (r'\bbefehl\b',      'Befehl'),
            (r'\baufgabe\b',     'Aufgabe'),
            (r'\bbelohnung\b',   'Belohnung'),
            (r'\bgegenstand\b',  'Gegenstand'),
            (r'\brüstungswert\b','Rüstungswert'),
            (r'\bangriff\b',     'Angriff'),
            (r'\bverteidigung\b','Verteidigung'),
            (r'\bgeschwindigkeit\b', 'Geschwindigkeit'),
            (r'\bstärke\b',      'Stärke'),
            (r'\bstamina\b',     'Ausdauer'),
        ],
    },

    "ruRU": {
        "nom": "Russian",
        "emoji": "🇷🇺",
        "modele": "qwen2.5:14b",

        "rules_prompt": (
            "RULE #1 — CYRILLIC ONLY: Write ONLY in Cyrillic. NEVER use Latin transliteration. "
            "RULE #2 — FORMAL ADDRESS: Use 'вы/ваш/вам/вас' (plural/formal) for 'you/your'. NEVER use 'ты/твой'. "
            "RULE #3 — BLIZZARD TERMS: Use official Blizzard RU-RU WoW terminology. "
            "Examples: Quest→задание | damage→урон | healing→исцеление | "
            "guild→гильдия | spell→заклинание | item→предмет | zone→зона. "
            "RULE #4 — POSSESSIVES: 'Khadgar's Staff' → 'Посох Кадгара'. "
            "RULE #5 — TAGS: Keep all $B, $N, %s tags exactly as-is."
        ),

        "checks": [
            (r'\bты\b',      "CRITIQUE: 'ты' interdit → 'вы'",       "CRITIQUE"),
            (r'\bтебя\b',    "CRITIQUE: 'тебя' → 'вас'",             "CRITIQUE"),
            (r'\bтебе\b',    "CRITIQUE: 'тебе' → 'вам'",             "CRITIQUE"),
            (r'\bтвой\b',    "CRITIQUE: 'твой' → 'ваш'",             "CRITIQUE"),
            (r'\bтвоя\b',    "CRITIQUE: 'твоя' → 'ваша'",            "CRITIQUE"),
            (r'\bтвоё\b',    "CRITIQUE: 'твоё' → 'ваше'",            "CRITIQUE"),
            (r'\bтвои\b',    "CRITIQUE: 'твои' → 'ваши'",            "CRITIQUE"),
            (r'\byou\b',     "CRITIQUE: 'you' anglais résiduel",      "CRITIQUE"),
            (r'\bYou\b',     "CRITIQUE: 'You' anglais résiduel",      "CRITIQUE"),
            (r'\byour\b',    "CRITIQUE: 'your' anglais résiduel",     "CRITIQUE"),
            (r'\bquest\b',   "WARN: 'quest' latin → 'задание'",       "WARN"),
        ],

        "check_positive": {
            "trigger_en": r'\b(you|your)\b',
            "pattern_good": r'\b(вы|вас|вам|вашем|вашу|вашего|ваших|ваш|ваша|ваше|ваши|вашему|вашей|вашим|вашими)\b',
            "message": "CRITIQUE: 'you' dans EN mais aucune forme 'вы/ваш' trouvée",
        },

        "post_corrections": [
            (r'\bты\b',      'вы'),
            (r'\bТы\b',      'Вы'),
            (r'\bтебя\b',    'вас'),
            (r'\bТебя\b',    'Вас'),
            (r'\bтебе\b',    'вам'),
            (r'\bТебе\b',    'Вам'),
            (r'\bтобой\b',   'вами'),
            (r'\bТобой\b',   'Вами'),
            (r'\bтвой\b',    'ваш'),
            (r'\bТвой\b',    'Ваш'),
            (r'\bтвоя\b',    'ваша'),
            (r'\bТвоя\b',    'Ваша'),
            (r'\bтвоё\b',    'ваше'),
            (r'\bТвоё\b',    'Ваше'),
            (r'\bтвои\b',    'ваши'),
            (r'\bТвои\b',    'Ваши'),
            (r'\bтвоего\b',  'вашего'),
            (r'\bТвоего\b',  'Вашего'),
            (r'\bтвоей\b',   'вашей'),
            (r'\bТвоей\b',   'Вашей'),
            (r'\bтвоим\b',   'вашим'),
            (r'\bТвоим\b',   'Вашим'),
            (r'\byou\b',     'вы'),
            (r'\bYou\b',     'Вы'),
            (r'\byour\b',    'ваш'),
            (r'\bYour\b',    'Ваш'),
            (r'\bquest\b',   'задание'),
            (r'\bQuest\b',   'Задание'),
        ],
    },

    "esMX": {
        "nom": "Portuguese (Brazil)",
        "emoji": "🇧🇷",
        "modele": "qwen2.5:14b",

        "rules_prompt": (
            "RULE #1 — LANGUAGE: Translate into PORTUGUESE (Brazil), NOT Spanish. "
            "This is PT-BR, not ES. The output must be in Portuguese. "
            "RULE #2 — YOU: Use 'você' for 'you'. Use 'seu/sua/seus/suas' for 'your'. "
            "NEVER use Spanish words like: tú, usted, vosotros, tienes, eres, puedes, tu (Spanish). "
            "RULE #3 — POSSESSIVES: 'Khadgar's Staff' → 'Cajado de Khadgar'. "
            "RULE #4 — BLIZZARD TERMS: Use official Blizzard PT-BR WoW terminology. "
            "RULE #5 — VERBS: Use PT-BR verb conjugation: "
            "you have→você tem | you are→você é/está | you can→você pode | you must→você deve."
        ),

        "checks": [
            (r'\btienes\b',    "CRITIQUE: mot espagnol 'tienes' → PT-BR 'tem'",      "CRITIQUE"),
            (r'\bpuedes\b',    "CRITIQUE: mot espagnol 'puedes' → PT-BR 'pode'",     "CRITIQUE"),
            (r'\beres\b',      "CRITIQUE: mot espagnol 'eres' → PT-BR 'é/está'",     "CRITIQUE"),
            (r'\btú\b',        "CRITIQUE: mot espagnol 'tú' → PT-BR 'você'",         "CRITIQUE"),
            (r'\busted\b',     "CRITIQUE: mot espagnol 'usted' → PT-BR 'você'",      "CRITIQUE"),
            (r'\bvosotros\b',  "CRITIQUE: mot espagnol 'vosotros' → PT-BR 'vocês'",  "CRITIQUE"),
            (r'\bvuestro\b',   "CRITIQUE: mot espagnol 'vuestro' → PT-BR 'seu/vosso'","CRITIQUE"),
            (r'\bhaces\b',     "WARN: mot espagnol 'haces' → PT-BR 'faz'",           "WARN"),
            (r'\bdebes\b',     "WARN: mot espagnol 'debes' → PT-BR 'deve'",          "WARN"),
            (r'\bdeberás\b',   "WARN: mot espagnol 'deberás' → PT-BR 'deverá'",      "WARN"),
            (r'\btienes que\b',"CRITIQUE: 'tienes que' → PT-BR 'você tem que'",      "CRITIQUE"),
        ],

        "check_positive": {
            "trigger_en": r'\b(you|your)\b',
            "pattern_good": r'\b(você|vocês|seu|sua|seus|suas|vosso|vossa)\b',
            "message": "CRITIQUE: 'you' dans EN mais aucune forme 'você/seu' trouvée",
        },

        "post_corrections": [
            # Espagnol résiduel → PT-BR
            (r'\btienes que\b',  'você tem que'),
            (r'\btienes\b',      'tem'),
            (r'\bTienes\b',      'Tem'),
            (r'\bpuedes\b',      'pode'),
            (r'\bPuedes\b',      'Pode'),
            (r'\beres\b',        'é'),
            (r'\bEres\b',        'É'),
            (r'\bestás\b',       'está'),
            (r'\bEstás\b',       'Está'),
            (r'\btú\b',          'você'),
            (r'\bTú\b',          'Você'),
            (r'\busted\b',       'você'),
            (r'\bUsted\b',       'Você'),
            (r'\bvosotros\b',    'vocês'),
            (r'\bVosotros\b',    'Vocês'),
            (r'\bvuestro\b',     'seu'),
            (r'\bVuestro\b',     'Seu'),
            (r'\bvuestra\b',     'sua'),
            (r'\bVuestra\b',     'Sua'),
            (r'\bvuestros\b',    'seus'),
            (r'\bVuestros\b',    'Seus'),
            (r'\bvuestras\b',    'suas'),
            (r'\bVuestras\b',    'Suas'),
            (r'\bhaces\b',       'faz'),
            (r'\bHaces\b',       'Faz'),
            (r'\bdebes\b',       'deve'),
            (r'\bDebes\b',       'Deve'),
            (r'\bdeberás\b',     'deverá'),
            (r'\bDeberás\b',     'Deverá'),
            (r'\bpuedas\b',      'possa'),
            (r'\bPuedas\b',      'Possa'),
            (r'\btengas\b',      'tenha'),
            (r'\bTengas\b',      'Tenha'),
            (r'\bseas\b',        'seja'),
            (r'\bSeas\b',        'Seja'),
            # "tu" espagnol isolé → "seu"
            (r'\btu\b(?=\s+[a-záàâãéêíóôõúç])', 'seu'),
            (r'\bTu\b(?=\s+[a-záàâãéêíóôõúçA-Z])', 'Seu'),
        ],
    },

    "zhCN": {
        "nom": "Simplified Chinese",
        "emoji": "🇨🇳",
        "modele": "qwen2.5:14b",

        "rules_prompt": (
            "RULE #1 — SIMPLIFIED CHINESE: Output ONLY Simplified Chinese (Mainland China standard). "
            "Use Simplified characters (简体字), NEVER Traditional. "
            "RULE #2 — YOU: Use '你' for informal 'you' in WoW context, '您' for very formal NPC. "
            "RULE #3 — BLIZZARD TERMS: Use official Blizzard ZH-CN WoW terminology: "
            "Quest→任务 | damage→伤害 | healing→治疗量 | guild→公会 | "
            "spell→法术 | ability→技能 | item→物品 | dungeon→副本 | raid→团队副本. "
            "RULE #4 — POSSESSIVES: 'Khadgar's Staff' → '卡德加的法杖'. "
            "RULE #5 — PUNCTUATION: Use Chinese punctuation: ，。！？《》「」. "
            "RULE #6 — NO SPACES between Chinese characters."
        ),

        "checks": [
            # Vérifier présence de caractères CJK (pas de texte latin résiduel excessif)
            # Les checks pour le chinois sont plus qualitatifs
        ],

        "check_positive": {
            "trigger_en": r'.+',  # toujours vérifier
            "pattern_good": r'[\u4e00-\u9fff]',  # au moins un caractère CJK
            "message": "CRITIQUE: aucun caractère chinois dans la traduction",
        },

        "post_corrections": [],
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# MOTEUR DE TRADUCTION DU BENCHMARK
# ──────────────────────────────────────────────────────────────────────────────

LANG_CODE = {
    "esES": "ES",
    "deDE": "DE",
    "ruRU": "RU",
    "esMX": "PT",
    "zhCN": "ZH",
}

def traduire(texte: str, locale: str, cfg: dict) -> tuple[str, float]:
    """Traduit avec le moteur multilingue (post-corrections incluses)."""
    lang      = cfg["nom"]
    modele    = cfg["modele"]
    rules     = cfg["rules_prompt"]
    lang_code = LANG_CODE.get(locale, locale[:2].upper())

    # Masquage des tags WoW
    # ruRU/zhCN : masquer aussi %s/%d (le modèle les traduit sinon en CJK)
    # esES/deDE/esMX : ne pas masquer %s (le modèle confond [T0] avec du contenu en espagnol)
    if locale in ("ruRU", "zhCN"):
        tags = re.findall(r'\$[BbNn]|%s|%d|\|[TtHhc][^|]*\|', texte)
    else:
        tags = re.findall(r'\$[BbNn]|\|[TtHhc][^|]*\|', texte)
    masq = texte
    for i, t in enumerate(tags):
        masq = masq.replace(t, f"[T{i}]", 1)

    nb_tags = len(tags)
    tags_list = " ".join(f"[T{i}]" for i in range(nb_tags)) if nb_tags else ""

    # Rappel pour les [Tx] masqués
    tags_reminder = (
        f" CRITICAL: This text has {nb_tags} format code(s): {tags_list}. "
        f"Copy them EXACTLY. NEVER translate or omit: {tags_list}."
    ) if nb_tags > 0 else ""

    # Rappel supplémentaire pour %s/%d non masqués
    pct_s_count = texte.count("%s") + texte.count("%d")
    if pct_s_count > 0:
        pct_codes = " ".join(["%s"] * texte.count("%s") + ["%d"] * texte.count("%d"))
        tags_reminder += (
            f" ALSO: Keep these format codes EXACTLY as-is in your translation: {pct_codes}. "
            f"Do NOT translate, replace, or remove them."
        )

    sys_prompt = (
        f"You are an expert Blizzard WoW localization specialist. "
        f"Translate the following World of Warcraft text into {lang}. "
        f"{rules}"
        f"{tags_reminder} "
        f"$B, $N, %s and ALL format codes — copy exactly as-is. "
        f"Output ONLY the translated text. No comments, no notes, no explanations. "
        f"Translate the COMPLETE text. Leave NO English words untranslated."
    )

    prompt = f"{sys_prompt}\n\nEN: {masq}\n{lang_code}:"

    t0 = time.time()
    try:
        resp = ollama.chat(
            model=modele,
            messages=[{"role": "user", "content": prompt}],
            options={
                "temperature":    0.0,
                "num_gpu":        99,
                "num_ctx":        768,
                "repeat_penalty": 1.1,
                "num_predict":    320,
                # \n prefix : évite le déclenchement sur l'écho du prompt
                "stop":           ["\nEN:", f"\n{lang_code}:"],
            },
        )
        raw = resp["message"]["content"].strip()
    except Exception as e:
        return f"[ERREUR: {e}]", time.time() - t0

    duree = time.time() - t0

    # Supprimer le préfixe "XX: " si le modèle l'a répété
    raw = re.sub(rf'^{lang_code}:\s*', '', raw).strip()
    raw = re.sub(r'^[A-Z]{2}:\s*', '', raw).strip()

    # Nettoyage notes IA
    raw = re.sub(r"\s*\(Note\s*:[^)]*\)\.?\s*", " ", raw).strip()
    raw = re.sub(r"\n+Note\s*:.*", "", raw, flags=re.DOTALL).strip()
    raw = re.sub(r"\s*\(Nota\s*:[^)]*\)\.?\s*", " ", raw).strip()
    raw = re.sub(r"\s*\(Hinweis\s*:[^)]*\)\.?\s*", " ", raw).strip()

    # Retry si CJK détecté en non-zhCN (hallucination du modèle)
    if locale != "zhCN" and re.search(r'[\u4e00-\u9fff]', raw):
        # Retry avec température légèrement plus élevée pour briser le déterminisme
        lang_retry  = cfg["nom"]
        rules_retry = cfg["rules_prompt"]
        prompt_retry = (
            f"You are a {lang_retry} translator. "
            f"IMPORTANT: Write ONLY in {lang_retry}. Do NOT write any Chinese characters. "
            f"Do NOT mix languages. {rules_retry}"
            f" CRITICAL: ALL [Tx] format codes — copy verbatim. "
            f"Output ONLY {lang_retry} text.\n\nEN: {masq}\n{lang_code}:"
        )
        try:
            resp2 = ollama.chat(
                model=modele,
                messages=[{"role": "user", "content": prompt_retry}],
                options={
                    "temperature":    0.15,   # plus élevé pour briser la répétition CJK
                    "num_gpu":        99,
                    "num_ctx":        768,
                    "repeat_penalty": 1.2,
                    "num_predict":    320,
                    "stop":           ["\nEN:", f"\n{lang_code}:"],
                },
            )
            raw2 = resp2["message"]["content"].strip()
            raw2 = re.sub(rf'^{lang_code}:\s*', '', raw2).strip()
            raw2 = re.sub(r'^[A-Z]{2}:\s*', '', raw2).strip()
            if raw2 and not re.search(r'[\u4e00-\u9fff]', raw2):
                raw = raw2  # Remplacer par la version propre
        except Exception:
            pass

    trad = raw.replace('"', "")

    # Normalisation des masques renommés par le modèle ([Cx] → [Tx], etc.)
    trad = re.sub(r"\[([A-Z])(\d+)\]", r"[T\2]", trad)

    # Purge CJK parasite — supprimer TOUS les caractères CJK (pas seulement jusqu'à fin de ligne)
    if locale != "zhCN":
        # Couper au premier CJK (hallucination mid-phrase)
        trad = re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\u3000-\u303f].*', '', trad, flags=re.DOTALL).strip()
        # Supprimer aussi CJK isolés éparpillés dans le texte
        trad = re.sub(r'[\u4e00-\u9fff\u3040-\u30ff\u3000-\u303f]+', '', trad).strip()

    # Nettoyage notes IA
    trad = re.sub(r"\s*\(Note\s*:[^)]*\)\.?\s*", " ", trad).strip()
    trad = re.sub(r"\n+Note\s*:.*", "", trad, flags=re.DOTALL).strip()
    trad = re.sub(r"\s*\(Nota\s*:[^)]*\)\.?\s*", " ", trad).strip()
    trad = re.sub(r"\s*\(Hinweis\s*:[^)]*\)\.?\s*", " ", trad).strip()

    # Post-corrections spécifiques locale
    for pat, rep in cfg.get("post_corrections", []):
        trad = re.sub(pat, rep, trad)

    # ── Normalisation des masques renommés par le modèle ─────────────────────
    trad = re.sub(r"\[([A-Z])(\d+)\]", r"[T\2]", trad)

    # ── Recovery $B : si le modèle a remplacé [Tx] par des newlines ──────────
    if tags and all(t == '$B' for t in tags):
        nb_newlines = trad.count('\n')
        nb_tags_b   = len(tags)
        # Si tous les [Ti] ont été perdus mais les bons newlines sont là
        if nb_newlines == nb_tags_b and not any(f"[T{i}]" in trad for i in range(nb_tags_b)):
            trad = trad.replace('\n', '$B')

    # ── Restauration tags ─────────────────────────────────────────────────────
    for i, t in enumerate(tags):
        trad = trad.replace(f"[T{i}]", t)

    return trad, duree


# ──────────────────────────────────────────────────────────────────────────────
# SCORING
# ──────────────────────────────────────────────────────────────────────────────

def scorer(en: str, trad: str, cfg: dict) -> dict:
    """Score la traduction, retourne dict avec erreurs et score global."""
    erreurs_critiques = []
    erreurs_warn      = []
    ok                = True

    trad_lower = trad.lower()
    locale_nom = cfg.get("nom", "")

    # ── Langue corrompue — CJK dans trad non-zhCN ────────────────────────────
    if "Chinese" not in locale_nom:
        if re.search(r'[\u4e00-\u9fff]', trad):
            erreurs_critiques.append("CRITIQUE: Caractères CJK dans une trad non-zhCN (hallucination)")

    # ── Trad trop courte (< 4 chars) = échec probable ─────────────────────────
    if len(trad.strip()) < 4:
        erreurs_critiques.append("CRITIQUE: Traduction vide ou trop courte")

    # ── Anglais résiduel flagrant ──────────────────────────────────────────────
    mots_anglais = ["the", "and", "you", "your", "with", "that", "this",
                    "have", "will", "our", "can", "from", "for", "are",
                    "not", "all", "has", "been", "must", "when", "but"]
    if "Chinese" not in locale_nom:
        residuels = [m for m in mots_anglais if re.search(r'\b' + m + r'\b', trad_lower)]
        # "not" et "can" peuvent être dans les noms propres — ignorer pour DE/RU
        if residuels:
            # Tolérance pour RU (les tags comme $N restent en latin)
            residuels_filtres = [m for m in residuels if m not in ("the",) or
                                 not re.search(r'\$', en)]
            if residuels_filtres:
                erreurs_critiques.append(f"Anglais résiduel : {residuels_filtres[:4]}")

    # ── Checks spécifiques à la locale ────────────────────────────────────────
    for pat, msg, sev in cfg.get("checks", []):
        if re.search(pat, trad, re.IGNORECASE):
            if sev == "CRITIQUE":
                erreurs_critiques.append(msg)
            else:
                erreurs_warn.append(msg)

    # ── Check positif (ex. vosotros présent quand "you" dans EN) ──────────────
    cp = cfg.get("check_positive")
    if cp and re.search(cp["trigger_en"], en, re.IGNORECASE):
        if not re.search(cp["pattern_good"], trad, re.IGNORECASE):
            erreurs_critiques.append(cp["message"])

    # ── Tags préservés ─────────────────────────────────────────────────────────
    tags_en   = re.findall(r'\$[BbNn]|%s|%d|\|[TtHhc][^|]*\|', en)
    tags_trad = re.findall(r'\$[BbNn]|%s|%d|\|[TtHhc][^|]*\|', trad)
    perdus    = [t for t in tags_en if t not in tags_trad]
    if perdus:
        erreurs_critiques.append(f"Tags perdus : {perdus}")

    # ── Score global ──────────────────────────────────────────────────────────
    # CRITIQUE = 0, WARN = 0.5 de pénalité
    penalite = len(erreurs_critiques) * 1.0 + len(erreurs_warn) * 0.25
    score    = max(0.0, 1.0 - penalite * 0.25)

    return {
        "ok":      len(erreurs_critiques) == 0,
        "score":   score,
        "critiques": erreurs_critiques,
        "warns":   erreurs_warn,
    }


# ──────────────────────────────────────────────────────────────────────────────
# AFFICHAGE
# ──────────────────────────────────────────────────────────────────────────────

W = 92

def ligne(c="─"): print(c * W)
def titre(t, c="═"): print(f"\n{c*W}\n  {t}\n{c*W}")

def barre(score, w=18):
    filled = int(score * w)
    c = "🟩" if score >= 0.9 else "🟨" if score >= 0.6 else "🟥"
    return c * filled + "⬜" * (w - filled) + f" {score*100:.0f}%"

def print_resultat(item, locale, trad, scoring, duree):
    status = "✅" if scoring["ok"] else "❌"
    print(f"\n  {status} [{item['id']}] {item['cat']}")
    print(f"     EN : {item['en'][:85]}{'…' if len(item['en'])>85 else ''}")
    print(f"     {LOCALES_CONFIG[locale]['emoji']} : {trad[:85]}{'…' if len(trad)>85 else ''}")
    print(f"     Score : {barre(scoring['score'])}  ({duree:.1f}s)")
    for e in scoring["critiques"]:
        print(f"     ⛔ {e}")
    for w in scoring["warns"]:
        print(f"     ⚠️  {w}")


# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────

def main():
    args      = [a for a in sys.argv[1:] if not a.startswith("--")]
    save_json = "--save" in sys.argv or True  # toujours sauvegarder

    locales_cibles = [a for a in args if a in LOCALES_CONFIG]
    if not locales_cibles:
        locales_cibles = list(LOCALES_CONFIG.keys())

    # Vérifier modèles disponibles
    try:
        installes = [m.model.split(":")[0] for m in ollama.list().models if m.model]
    except Exception:
        print("❌ Ollama inaccessible.")
        sys.exit(1)

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    titre(f"BENCHMARK QUALITÉ MULTILINGUE — WoW Translator  ({now})")
    print(f"  Locales : {' | '.join(locales_cibles)}")
    print(f"  Corpus  : {len(CORPUS)} textes par locale")
    print(f"  Total   : {len(locales_cibles) * len(CORPUS)} traductions\n")

    resultats_globaux = {}
    all_results_json  = {}

    for locale in locales_cibles:
        cfg   = LOCALES_CONFIG[locale]
        emoji = cfg["emoji"]
        nom   = cfg["nom"]
        modele = cfg["modele"]

        if modele.split(":")[0] not in installes:
            print(f"\n  ⚠️  Modèle {modele} non installé — locale {locale} ignorée.")
            print(f"     Installe avec : ollama pull {modele}")
            continue

        titre(f"{emoji}  {nom} ({locale})  ·  {modele}")

        scores     = []
        n_ok       = 0
        n_critiques= 0
        resultats_json = []
        temps_total = 0.0

        for item in CORPUS:
            trad, duree = traduire(item["en"], locale, cfg)
            scoring     = scorer(item["en"], trad, cfg)

            scores.append(scoring["score"])
            temps_total += duree
            if scoring["ok"]:
                n_ok += 1
            else:
                n_critiques += len(scoring["critiques"])

            print_resultat(item, locale, trad, scoring, duree)

            resultats_json.append({
                "id":        item["id"],
                "cat":       item["cat"],
                "en":        item["en"],
                "trad":      trad,
                "score":     scoring["score"],
                "ok":        scoring["ok"],
                "critiques": scoring["critiques"],
                "warns":     scoring["warns"],
                "duree":     round(duree, 2),
            })

        score_moy  = sum(scores) / len(scores) if scores else 0.0
        pct_ok     = n_ok / len(CORPUS) * 100

        ligne("═")
        print(f"  {emoji} RÉSULTAT {locale} : {barre(score_moy)}")
        print(f"  Textes sans erreur : {n_ok}/{len(CORPUS)} ({pct_ok:.0f}%)")
        print(f"  Erreurs critiques  : {n_critiques}")
        print(f"  Temps total        : {temps_total:.0f}s  ({temps_total/len(CORPUS):.1f}s/trad)")
        ligne("═")

        resultats_globaux[locale] = {
            "score":       score_moy,
            "pct_ok":      pct_ok,
            "n_ok":        n_ok,
            "n_total":     len(CORPUS),
            "n_critiques": n_critiques,
        }
        all_results_json[locale] = resultats_json

    # ── Récapitulatif ──────────────────────────────────────────────────────────
    titre("RÉCAPITULATIF FINAL")
    print(f"  {'Locale':<10} {'Langue':<28} {'Score':<22} {'OK':<10} Critiques")
    ligne()
    total_ok = True
    for locale, res in resultats_globaux.items():
        cfg     = LOCALES_CONFIG[locale]
        status  = "✅" if res["pct_ok"] == 100 else "❌"
        total_ok = total_ok and (res["pct_ok"] == 100)
        print(f"  {status} {locale:<8} {cfg['nom']:<28} {barre(res['score'], 12):<24} "
              f"{res['n_ok']}/{res['n_total']}     {res['n_critiques']} critiques")
    ligne()

    if total_ok:
        print("\n  🏆 TOUTES LES LOCALES SONT IRRÉPROCHABLES ✅")
    else:
        print("\n  ⚠️  Des corrections sont nécessaires — voir détails ci-dessus")
        nb_fails = sum(1 for r in resultats_globaux.values() if r["pct_ok"] < 100)
        print(f"  {nb_fails} locale(s) avec erreurs")

    # ── Sauvegarde JSON ────────────────────────────────────────────────────────
    if save_json:
        out = BASE_DIR / "benchmark_qualite_results.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({
                "date":     now,
                "globaux":  resultats_globaux,
                "details":  all_results_json,
            }, f, ensure_ascii=False, indent=2)
        print(f"\n  💾 Résultats sauvegardés → {out.name}")

    ligne("═")


if __name__ == "__main__":
    main()
