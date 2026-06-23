# wow_rules_esES.py
# ─────────────────────────────────────────────────────────────────────────────
# Règles de traduction WoW — Locale ES-ES (Espagne)
# Modèle optimal  : qwen2.5:14b (meilleur score benchmark vs mistral-nemo +1.2%)
# Correction 2e pers : VOSOTROS obligatoire (jamais tú/usted)
# Particularités   : accord genre vuestro/vuestra, inversion verbes impératifs
# ─────────────────────────────────────────────────────────────────────────────

MODELE_IA = "qwen2.5:14b"
LANG_NAME  = "Spanish (Spain)"

# ── Règles injectées dans le prompt système ───────────────────────────────────
LANG_RULES = [
    # Règle principale — vosotros ABSOLU
    "ABSOLUTE RULE: ALWAYS use VOSOTROS form for 2nd person. NEVER tú, te, tu, usted, ti. "
    "Pronoun subject: tú→vosotros. "
    "Pronoun object: te→os. "
    "Possessives: tu→vuestro/vuestra | tus→vuestros/vuestras. "
    "Verbs: tienes→tenéis | puedes→podéis | eres→sois | sabes→sabéis | quieres→queréis | "
    "debes→debéis | vas→vais | vienes→venís | sigues→seguís | haces→hacéis. "
    "Future: recibirás→recibiréis | irás→iréis | harás→haréis | serás→seréis | "
    "tendrás→tendréis | podrás→podréis | encontrarás→encontraréis | llevarás→llevaréis | "
    "traerás→traeréis | vencerás→venceréis. "
    "Imperatives: ten→tened | ve→id | haz→haced | sé→sed | ven→venid | di→decid | "
    "trae→traed | lleva→llevad | mata→matad | coge→coged | recoge→recoged. "
    "Examples: 'You must' → 'Debéis' | 'Your reward' → 'Vuestra recompensa' | "
    "'I need you to' → 'Necesito que vosotros' | 'Can you' → 'Podéis'.",

    # Terminologie et syntaxe
    "Reorder possessives: 'Khadgar' + possessive → 'Bastón de Khadgar', NOT 'Khadgar' + s. "
    "Use official Blizzard ES-ES WoW terminology. "
    "Dungeon→mazmorra | Guild→hermandad | Quest→misión | Spell→hechizo | "
    "Damage→daño | Healing→curación | Item→objeto | Enemy→enemigo | Ally→aliado. "
    "Check noun gender: vuestro/vuestra MUST match the noun (vuestro poder, vuestra misión).",

    # Anti-hallucination
    "CRITICAL: Output ONLY the translation. NEVER write 'Nota:', 'Observación:', "
    "'Traducción:', 'NB:', or any meta-commentary. NEVER explain your reasoning. Just translate.",

    # Realm First!
    "Translate 'Realm First!' as '¡Primero del reino!' (official Blizzard ES-ES).",

    # Vosotros edge cases renforcés
    "VOSOTROS EDGE CASES: "
    "Subjunctive: puedas→podáis | quieras→queráis | tengas→tengáis | seas→seáis | "
    "hagas→hagáis | vayas→vayáis | vengas→vengáis | sepas→sepáis | digas→digáis. "
    "Past: tuviste→tuvisteis | pudiste→pudisteis | hiciste→hicisteis | fuiste→fuisteis | "
    "viniste→vinisteis | dijiste→dijisteis | supiste→supisteis. "
    "Conditional: tendrías→tendríais | podrías→podríais | serías→seríais | harías→haríais. "
    "Gerund reflexive: te estás→os estáis | te vas→os vais.",

    # Terminologie étendue
    "Extra WoW terms: Achievement→logro | Battleground→campo de batalla | Arena→arena | "
    "Trinket→abalorio | Mount→montura | Pet→mascota | Reputation→reputación | "
    "Honor→honor | Talent→talento | Armor→armadura | Weapon→arma | Shield→escudo | "
    "Buff→beneficio | Debuff→perjuicio | Cooldown→tiempo de reutilización | "
    "Tank→tanque | Healer→sanador | Mana→maná | Level→nivel | Power→poder.",
]

# ── Post-corrections regex (esES) ─────────────────────────────────────────────
# Appliquées après la traduction IA pour forcer vosotros si le modèle déraille
CORRECTIONS = [
    # Pronoms sujets tú → vosotros
    (r'\bTú\b',                'Vosotros'),
    (r'\btú\b',                'vosotros'),
    # Pronoms objets directs 2e pers.
    (r'\bTe\b(?=\s)',          'Os'),
    (r'\bte\b(?=\s)',          'os'),
    # Possessifs pluriel (invariables en genre)
    (r'\btus\b',               'vuestros'),
    (r'\bTus\b',               'Vuestros'),
    # Formes passives / auxiliaire haber (tú → vosotros)
    (r'\bhas sido\b',          'habéis sido'),
    (r'\bHas sido\b',          'Habéis sido'),
    (r'\bhas ganado\b',        'habéis ganado'),
    (r'\bHas ganado\b',        'Habéis ganado'),
    (r'\bhas completado\b',    'habéis completado'),
    (r'\bHas completado\b',    'Habéis completado'),
    (r'\bhas obtenido\b',      'habéis obtenido'),
    (r'\bHas obtenido\b',      'Habéis obtenido'),
    (r'\bhas derrotado\b',     'habéis derrotado'),
    (r'\bHas derrotado\b',     'Habéis derrotado'),
    (r'\bhas muerto\b',        'habéis muerto'),
    (r'\bHas muerto\b',        'Habéis muerto'),
    (r'\bhas fallado\b',       'habéis fallado'),
    (r'\bHas fallado\b',       'Habéis fallado'),
    (r'\bhas aprendido\b',     'habéis aprendido'),
    (r'\bHas aprendido\b',     'Habéis aprendido'),
    (r'\bhas alcanzado\b',     'habéis alcanzado'),
    (r'\bHas alcanzado\b',     'Habéis alcanzado'),
    (r'\bhas demostrado\b',    'habéis demostrado'),
    (r'\bHas demostrado\b',    'Habéis demostrado'),
    (r'\bhas recibido\b',      'habéis recibido'),
    (r'\bHas recibido\b',      'Habéis recibido'),
    (r'\bhas encontrado\b',    'habéis encontrado'),
    (r'\bHas encontrado\b',    'Habéis encontrado'),
    (r'\bfuiste\b',            'fuisteis'),
    (r'\bFuiste\b',            'Fuisteis'),
    (r'\bestás\b',             'estáis'),
    (r'\bEstás\b',             'Estáis'),
    (r'\b([Ff])ueras?\b',      r'\1uerais'),
    # Verbes fréquents formes tú → vosotros
    (r'\btienes\b',            'tenéis'),
    (r'\bTienes\b',            'Tenéis'),
    (r'\bpuedes\b',            'podéis'),
    (r'\bPuedes\b',            'Podéis'),
    (r'\beres\b',              'sois'),
    (r'\bEres\b',              'Sois'),
    (r'\bsabes\b',             'sabéis'),
    (r'\bSabes\b',             'Sabéis'),
    (r'\bquieres\b',           'queréis'),
    (r'\bQuieres\b',           'Queréis'),
    (r'\bdebes\b',             'debéis'),
    (r'\bDebes\b',             'Debéis'),
    (r'\bvas\b',               'vais'),
    (r'\bVas\b',               'Vais'),
    (r'\bvienes\b',            'venís'),
    (r'\bVienes\b',            'Venís'),
    (r'\bsigues\b',            'seguís'),
    (r'\bSigues\b',            'Seguís'),
    (r'\bhaces\b',             'hacéis'),
    (r'\bHaces\b',             'Hacéis'),
    (r'\brecibirás\b',         'recibiréis'),
    (r'\bRecibirás\b',         'Recibiréis'),
    (r'\birás\b',              'iréis'),
    (r'\bIrás\b',              'Iréis'),
    (r'\bharás\b',             'haréis'),
    (r'\bHarás\b',             'Haréis'),
    (r'\bserás\b',             'seréis'),
    (r'\bSerás\b',             'Seréis'),
    (r'\btendrás\b',           'tendréis'),
    (r'\bTendrás\b',           'Tendréis'),
    (r'\bpodrás\b',            'podréis'),
    (r'\bPodrás\b',            'Podréis'),
    (r'\bvendrás\b',           'vendréis'),
    (r'\bVendrás\b',           'Vendréis'),
    (r'\bquerrás\b',           'querréis'),
    (r'\bQuerrás\b',           'Querréis'),
    # Formes usted → vosotros
    (r'\bUsted\b',             'Vosotros'),
    (r'\busted\b',             'vosotros'),
    # Anglais résiduel
    (r'\byou\b',               'vosotros'),
    (r'\bYou\b',               'Vosotros'),
    (r'\byour\b',              'vuestro'),
    (r'\bYour\b',              'Vuestro'),
    # Terminologie Blizzard ES-ES
    (r'\bcalabozo\b',          'mazmorra'),
    (r'\bCalabozo\b',          'Mazmorra'),
    (r'\bgremio\b',            'hermandad'),
    (r'\bGremio\b',            'Hermandad'),
    # Vosotros — formes supplémentaires tú → vosotros
    (r'\bpuedas\b',            'podáis'),
    (r'\bPuedas\b',            'Podáis'),
    (r'\bquieras\b',           'queráis'),
    (r'\bQuieras\b',           'Queráis'),
    (r'\btengas\b',            'tengáis'),
    (r'\bTengas\b',            'Tengáis'),
    (r'\bseas\b',              'seáis'),
    (r'\bSeas\b',              'Seáis'),
    (r'\bhagas\b',             'hagáis'),
    (r'\bHagas\b',             'Hagáis'),
    (r'\bvayas\b',             'vayáis'),
    (r'\bVayas\b',             'Vayáis'),
    (r'\bvengas\b',            'vengáis'),
    (r'\bVengas\b',            'Vengáis'),
    (r'\bsepas\b',             'sepáis'),
    (r'\bSepas\b',             'Sepáis'),
    (r'\bdigas\b',             'digáis'),
    (r'\bDigas\b',             'Digáis'),
    (r'\btuviste\b',           'tuvisteis'),
    (r'\bTuviste\b',           'Tuvisteis'),
    (r'\bpudiste\b',           'pudisteis'),
    (r'\bPudiste\b',           'Pudisteis'),
    (r'\bhiciste\b',           'hicisteis'),
    (r'\bHiciste\b',           'Hicisteis'),
    (r'\bviniste\b',           'vinisteis'),
    (r'\bViniste\b',           'Vinisteis'),
    (r'\bdijiste\b',           'dijisteis'),
    (r'\bDijiste\b',           'Dijisteis'),
    (r'\btendrías\b',          'tendríais'),
    (r'\bTendrías\b',          'Tendríais'),
    (r'\bpodrías\b',           'podríais'),
    (r'\bPodrías\b',           'Podríais'),
    (r'\bserías\b',            'seríais'),
    (r'\bSerías\b',            'Seríais'),
    (r'\bharías\b',            'haríais'),
    (r'\bHarías\b',            'Haríais'),
    (r'\bnecesitas\b',         'necesitáis'),
    (r'\bNecesitas\b',         'Necesitáis'),
    (r'\bconsigues\b',         'conseguís'),
    (r'\bConsigues\b',         'Conseguís'),
    (r'\bencuentras\b',        'encontráis'),
    (r'\bEncuentras\b',        'Encontráis'),
    (r'\bmatas\b',             'matáis'),
    (r'\bMatas\b',             'Matáis'),
    (r'\bllevas\b',            'lleváis'),
    (r'\bLlevas\b',            'Lleváis'),
    (r'\btraes\b',             'traéis'),
    (r'\bTraes\b',             'Traéis'),
    # Terminologie WoW anglais résiduel
    (r'\bdamage\b',            'daño'),
    (r'\bDamage\b',            'Daño'),
    (r'\bhealing\b',           'curación'),
    (r'\bHealing\b',           'Curación'),
    (r'\bspell\b',             'hechizo'),
    (r'\bSpell\b',             'Hechizo'),
    (r'\bguild\b',             'hermandad'),
    (r'\bGuild\b',             'Hermandad'),
    (r'\bdungeon\b',           'mazmorra'),
    (r'\bDungeon\b',           'Mazmorra'),
    (r'\bquest\b',             'misión'),
    (r'\bQuest\b',             'Misión'),
    (r'\blevel\b',             'nivel'),
    (r'\bLevel\b',             'Nivel'),
    (r'\bitem\b',              'objeto'),
    (r'\bItem\b',              'Objeto'),
    (r'\bachievement\b',       'logro'),
    (r'\bAchievement\b',       'Logro'),
    (r'\bbattleground\b',      'campo de batalla'),
    (r'\bBattleground\b',      'Campo de batalla'),
    (r'\btrinket\b',           'abalorio'),
    (r'\bTrinket\b',           'Abalorio'),
    (r'\bRealm First!\b',      '¡Primero del reino!'),
    # Anti-hallucination
    (r'^Nota\s*:\s*',          ''),
    (r'^Traducción\s*:\s*',    ''),
    (r'^Observación\s*:\s*',   ''),
    (r'^Note\s*:\s*',          ''),
]
