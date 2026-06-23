# wow_rules_frFR.py
# ─────────────────────────────────────────────────────────────────────────────
# Règles de traduction WoW — Locale FR-FR (France)
# Modèle optimal  : mistral-nemo (langues latines)
# Correction 2e pers : vous/votre (formel)
# Particularités   : ordre nom+complément, accents, guillemets français
# Pipeline auto    : injecte dans wow_rules.py (WOW_LEXICON + ERREURS_COMMUNES)
# ─────────────────────────────────────────────────────────────────────────────

MODELE_IA = "mistral-nemo"
LANG_NAME  = "French"

# ── Règles injectées dans le prompt système ───────────────────────────────────
LANG_RULES = [
    "Translate 'you' as 'vous', NEVER as 'votre personnage'.",
    "Translate 'healing done' as 'soins prodigués'.",
    "Reorder possessives: 'Khadgar' + possessive → 'Robe de Khadgar', NOT 'Khadgar' + s.",
    "Respect French syntax: Noun + de + Complement (NOT English order).",
    "Use official Blizzard FR-FR WoW terminology.",
    "Output ONLY French. No English words left untranslated.",

    # Anti-hallucination
    "CRITICAL: Output ONLY the translation. NEVER write notes, explanations, comments, "
    "or meta-commentary. NEVER start with 'Note:', 'Remarque:', 'Traduction:', 'NB:'. "
    "NEVER explain your reasoning or mention translation rules. Just translate.",

    # Realm First!
    "Translate 'Realm First!' as 'Premier du royaume !' (official Blizzard FR achievement prefix).",

    # Terminologie WoW étendue
    "Additional WoW terms: Battleground→Champ de bataille | Arena→Arène | "
    "Trinket→Bijou | Achievement→Haut fait | Dungeon→Donjon | Raid→Raid | "
    "Spell→Sort | Ability→Compétence | Damage→Dégâts | Healing→Soins | "
    "Guild→Guilde | Enemy→Ennemi | Ally→Allié | Tank→Tank | Healer→Soigneur | "
    "Buff→Amélioration | Debuff→Affaiblissement | Cooldown→Temps de recharge | "
    "Mana→Mana | Level→Niveau | Item→Objet | Power→Puissance | "
    "Talent→Talent | Armor→Armure | Weapon→Arme | Shield→Bouclier | "
    "Mount→Monture | Pet→Familier | Reputation→Réputation | Honor→Honneur | "
    "Stamina→Endurance | Intellect→Intelligence | Agility→Agilité | "
    "Strength→Force | Spirit→Esprit | Haste→Hâte | Critical→Critique | "
    "Dodge→Esquive | Parry→Parade | Block→Blocage.",
]

# ── Post-corrections regex (frFR) ─────────────────────────────────────────────
# NOTE : Les corrections littérales (ERREURS_COMMUNES) et les regex de balises
# (RESIDUS_POST_MARQUEUR, STATS_FORMAT) restent dans wow_rules.py pour que
# pipeline_auto.py puisse y injecter dynamiquement de nouvelles entrées.
# Ce fichier contient uniquement les corrections regex complémentaires.
CORRECTIONS = [
    # Anglais résiduel après traduction
    (r'\bSlay\b',          'Tuez'),
    (r'\bSlay ',           'Tuez '),
    (r'\bslayez\b',        'tuez'),
    (r'\byou\b',           'vous'),
    (r'\bYou\b',           'Vous'),
    (r'\byour\b',          'votre'),
    (r'\bYour\b',          'Votre'),
    # Doubles pronoms fréquents
    (r'\bVous Vous\b',     'Vous'),
    (r'\bNous Nous\b',     'Nous'),
    (r'\bIl Il\b',         'Il'),
    (r'\bElle Elle\b',     'Elle'),
    (r'\bJe Je\b',         'Je'),
    # Guillemets typographiques → droits (format WoW)
    (r'\u00AB\s*',         '"'),
    (r'\s*\u00BB',         '"'),
    # Points de suspension
    (r'\u2026',            '...'),
    # Anglais résiduel — mots courants
    (r'\bthe\b',           'le'),
    (r'\bThe\b',           'Le'),
    (r'\band\b',           'et'),
    (r'\bAnd\b',           'Et'),
    (r'\bof\b',            'de'),
    (r'\bOf\b',            'De'),
    (r'\bquest\b',         'quête'),
    (r'\bQuest\b',         'Quête'),
    (r'\bin\b',            'dans'),
    (r'\bIn\b',            'Dans'),
    (r'\bwith\b',          'avec'),
    (r'\bWith\b',          'Avec'),
    (r'\bfor\b',           'pour'),
    (r'\bFor\b',           'Pour'),
    (r'\bfrom\b',          'de'),
    (r'\bFrom\b',          'De'),
    (r'\bis\b',            'est'),
    (r'\bare\b',           'sont'),
    (r'\bhas\b',           'a'),
    (r'\bhave\b',          'ont'),
    (r'\bwas\b',           'était'),
    (r'\bwere\b',          'étaient'),
    (r'\bnot\b',           'pas'),
    (r'\bbut\b',           'mais'),
    (r'\bthis\b',          'ce'),
    (r'\bthat\b',          'ce'),
    (r'\bspell\b',         'sort'),
    (r'\bSpell\b',         'Sort'),
    (r'\bdamage\b',        'dégâts'),
    (r'\bDamage\b',        'Dégâts'),
    (r'\bhealing\b',       'soins'),
    (r'\bHealing\b',       'Soins'),
    (r'\bguild\b',         'guilde'),
    (r'\bGuild\b',         'Guilde'),
    (r'\blevel\b',         'niveau'),
    (r'\bLevel\b',         'Niveau'),
    (r'\bitem\b',          'objet'),
    (r'\bItem\b',          'Objet'),
    (r'\bdungeon\b',       'donjon'),
    (r'\bDungeon\b',       'Donjon'),
    (r'\benemy\b',         'ennemi'),
    (r'\bEnemy\b',         'Ennemi'),
    (r'\bally\b',          'allié'),
    (r'\bAlly\b',          'Allié'),
    (r'\bpower\b',         'puissance'),
    (r'\bPower\b',         'Puissance'),
    (r'\bbuff\b',          'amélioration'),
    (r'\bBuff\b',          'Amélioration'),
    (r'\bdebuff\b',        'affaiblissement'),
    (r'\bDebuff\b',        'Affaiblissement'),
    (r'\bRealm First!\b',  'Premier du royaume !'),
    # Anti-hallucination — supprimer les préfixes explicatifs
    (r'^Note\s*:\s*',      ''),
    (r'^Remarque\s*:\s*',  ''),
    (r'^Traduction\s*:\s*', ''),
    (r'^NB\s*:\s*',        ''),
]
