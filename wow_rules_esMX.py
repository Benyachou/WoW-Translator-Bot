# wow_rules_esMX.py
# ─────────────────────────────────────────────────────────────────────────────
# Règles de traduction WoW — Locale ES-MX (Mexique / Amérique Latine)
# Modèle optimal  : qwen2.5:14b (benchmark 100% vs mistral-nemo 96.7%, +3.3%)
# Correction 2e pers : tú/usted selon contexte (JAMAIS vosotros)
# Particularités   : calabozo (pas mazmorra), gremio (pas hermandad),
#                    reliquia (pas objeto singular), espagnol informel/LatAm
# ─────────────────────────────────────────────────────────────────────────────

MODELE_IA = "qwen2.5:14b"
LANG_NAME  = "Spanish (Latin America)"

# ── Règles injectées dans le prompt système ───────────────────────────────────
LANG_RULES = [
    # Règle 1 — Langue et registre
    "RULE 1 — LANGUAGE: Translate into SPANISH (Latin America), NOT European Spanish. "
    "Output must be ES-MX. NEVER use 'vosotros' — it is NOT used in Latin America. "
    "Use 'tú' (informal, for player) or 'usted' (formal, NPC→player respect) as appropriate.",

    # Règle 2 — Vouvoiement
    "RULE 2 — YOU FORMS: "
    "Informal (tú): tienes | puedes | eres | sabes | quieres | debes | vas. "
    "Formal (usted): tiene | puede | es | sabe | quiere | debe | va. "
    "NEVER: tenéis | podéis | sois | sabéis | queréis | debéis | vais. "
    "Examples: 'Your courage' → 'Tu valentía' | 'You must' → 'Debes' | "
    "'I need you' → 'Te necesito' | 'Your power' → 'Tu poder'.",

    # Règle 3 — Syntaxe possessifs
    "RULE 3 — POSSESSIVES: 'Khadgar' + possessive → 'Toga de Khadgar'. "
    "Use official Blizzard ES-MX WoW terminology (different from ES-ES).",

    # Règle 4 — Terminologie ES-MX officielle Blizzard
    "RULE 4 — BLIZZARD ES-MX TERMS: "
    "Quest→misión | Dungeon→calabozo | Raid→banda | Spell→hechizo | "
    "Ability→habilidad | Damage→daño | Healing→sanación | "
    "Guild→gremio | Enemy→enemigo | Ally→aliado | Item→objeto | "
    "Trinket→reliquia | Battleground→campo de batalla | Arena→arena.",

    # Règle 5 — Anti-hallucination
    "RULE 5 — NO EXPLANATIONS: Output ONLY the translation. NEVER write 'Nota:', "
    "'Observación:', 'Traducción:', 'NB:', or any meta-commentary. "
    "NEVER explain your reasoning or mention translation rules. Just translate.",

    # Règle 6 — Realm First!
    "RULE 6 — REALM FIRST: Translate 'Realm First!' as '¡Primero del reino!' (official Blizzard ES-MX).",

    # Règle 7 — Terminologie étendue
    "RULE 7 — EXTRA TERMS: Achievement→logro | Mount→montura | Pet→mascota | "
    "Reputation→reputación | Honor→honor | Talent→talento | Armor→armadura | "
    "Weapon→arma | Shield→escudo | Buff→beneficio | Debuff→perjuicio | "
    "Cooldown→tiempo de reutilización | Tank→tanque | Healer→sanador | "
    "Mana→maná | Level→nivel | Power→poder | Stamina→aguante | "
    "Intellect→intelecto | Agility→agilidad | Strength→fuerza | Spirit→espíritu | "
    "Haste→celeridad | Critical→crítico | Dodge→esquivar | Parry→parar | Block→bloquear.",
]

# ── Post-corrections regex (esMX) ─────────────────────────────────────────────
CORRECTIONS = [
    # Terminologie ES-ES incorrecte → ES-MX
    (r'\bmazmorra\b',       'calabozo'),
    (r'\bMazmorra\b',       'Calabozo'),
    (r'\bhermandad\b',      'gremio'),
    (r'\bHermandad\b',      'Gremio'),
    (r'\bobjeto singular\b','reliquia'),
    (r'\bObjeto singular\b','Reliquia'),
    # Vosotros résiduel → tú
    (r'\bvosotros\b',       'tú'),
    (r'\bVosotros\b',       'Tú'),
    (r'\bvuestro\b',        'tu'),
    (r'\bVuestro\b',        'Tu'),
    (r'\bvuestra\b',        'tu'),
    (r'\bVuestra\b',        'Tu'),
    (r'\bvuestros\b',       'tus'),
    (r'\bVuestros\b',       'Tus'),
    (r'\btendréis\b',       'tendrás'),
    (r'\bTendréis\b',       'Tendrás'),
    (r'\bpodréis\b',        'podrás'),
    (r'\bPodréis\b',        'Podrás'),
    (r'\brecibiréis\b',     'recibirás'),
    (r'\bRecibiréis\b',     'Recibirás'),
    (r'\btenéis\b',         'tienes'),
    (r'\bTenéis\b',         'Tienes'),
    (r'\bpodéis\b',         'puedes'),
    (r'\bPodéis\b',         'Puedes'),
    (r'\bsois\b',           'eres'),
    (r'\bSois\b',           'Eres'),
    (r'\bdebéis\b',         'debes'),
    (r'\bDebéis\b',         'Debes'),
    # Anglais résiduel
    (r'\byou\b',            'tú'),
    (r'\bYou\b',            'Tú'),
    (r'\byour\b',           'tu'),
    (r'\bYour\b',           'Tu'),
    (r'\bdamage\b',         'daño'),
    (r'\bDamage\b',         'Daño'),
    (r'\bhealing\b',        'sanación'),
    (r'\bHealing\b',        'Sanación'),
    (r'\bspell\b',          'hechizo'),
    (r'\bSpell\b',          'Hechizo'),
    (r'\bguild\b',          'gremio'),
    (r'\bGuild\b',          'Gremio'),
    (r'\bdungeon\b',        'calabozo'),
    (r'\bDungeon\b',        'Calabozo'),
    (r'\bquest\b',          'misión'),
    (r'\bQuest\b',          'Misión'),
    # Anglais résiduel supplémentaire
    (r'\blevel\b',          'nivel'),
    (r'\bLevel\b',          'Nivel'),
    (r'\bitem\b',           'objeto'),
    (r'\bItem\b',           'Objeto'),
    (r'\benemy\b',          'enemigo'),
    (r'\bEnemy\b',          'Enemigo'),
    (r'\bally\b',           'aliado'),
    (r'\bAlly\b',           'Aliado'),
    (r'\bpower\b',          'poder'),
    (r'\bPower\b',          'Poder'),
    (r'\bmana\b',           'maná'),
    (r'\bMana\b',           'Maná'),
    (r'\btank\b',           'tanque'),
    (r'\bTank\b',           'Tanque'),
    (r'\bbuff\b',           'beneficio'),
    (r'\bBuff\b',           'Beneficio'),
    (r'\bdebuff\b',         'perjuicio'),
    (r'\bDebuff\b',         'Perjuicio'),
    (r'\bcooldown\b',       'tiempo de reutilización'),
    (r'\bCooldown\b',       'Tiempo de reutilización'),
    (r'\bachievement\b',    'logro'),
    (r'\bAchievement\b',    'Logro'),
    (r'\bbattleground\b',   'campo de batalla'),
    (r'\bBattleground\b',   'Campo de batalla'),
    (r'\btrinket\b',        'reliquia'),
    (r'\bTrinket\b',        'Reliquia'),
    (r'\bmount\b',          'montura'),
    (r'\bMount\b',          'Montura'),
    (r'\bpet\b',            'mascota'),
    (r'\bPet\b',            'Mascota'),
    (r'\btalent\b',         'talento'),
    (r'\bTalent\b',         'Talento'),
    (r'\barmor\b',          'armadura'),
    (r'\bArmor\b',          'Armadura'),
    (r'\bweapon\b',         'arma'),
    (r'\bWeapon\b',         'Arma'),
    (r'\bshield\b',         'escudo'),
    (r'\bShield\b',         'Escudo'),
    (r'\braid\b',           'banda'),
    (r'\bRaid\b',           'Banda'),
    (r'\bRealm First!\b',   '¡Primero del reino!'),
    # Anti-hallucination
    (r'^Nota\s*:\s*',       ''),
    (r'^Traducción\s*:\s*', ''),
    (r'^Observación\s*:\s*',''),
    (r'^Note\s*:\s*',       ''),
]
