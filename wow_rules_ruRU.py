# wow_rules_ruRU.py
# ─────────────────────────────────────────────────────────────────────────────
# Règles de traduction WoW — Locale RU-RU (Russie)
# Modèle optimal  : qwen2.5:14b (benchmark 99.7% vs mistral-nemo 95.9%, +3.8%)
# Correction 2e pers : вы/ваш (formel, jamais ты/твой)
# Particularités   : cyrillique UNIQUEMENT, déclinaisons, translittérations interdites
# ─────────────────────────────────────────────────────────────────────────────

MODELE_IA = "qwen2.5:14b"
LANG_NAME  = "Russian"

# ── Règles injectées dans le prompt système ───────────────────────────────────
LANG_RULES = [
    # Règle 1 — Cyrillique obligatoire
    "RULE 1 — CYRILLIC ONLY: Output ONLY Cyrillic script. "
    "NEVER use Latin transliteration. NEVER leave English words untranslated. "
    "NEVER mix Latin and Cyrillic in the same word or sentence.",

    # Règle 2 — Vouvoiement formel
    "RULE 2 — FORMAL YOU: Use 'вы/ваш/вам/вас/вами' for 'you/your'. NEVER ты/твой/тебя/тебе. "
    "Examples: 'You must' → 'Вы должны' | 'Your quest' → 'Ваше задание' | "
    "'I need you' → 'Мне нужны вы' | 'Your power' → 'Ваша сила'.",

    # Règle 3 — Terminologie WoW
    "RULE 3 — WoW TERMS: Quest→задание | damage→урон | healing→исцеление | "
    "guild→гильдия | spell→заклинание | ability→умение | item→предмет | "
    "dungeon→подземелье | raid→рейд | enemy→враг | ally→союзник | "
    "level→уровень | power→сила | mana→мана | buff→усиление | debuff→ослабление | "
    "cooldown→перезарядка | tank→танк | healer→целитель.",

    # Règle 4 — Syntaxe possessifs
    "RULE 4 — POSSESSIVES: 'Khadgar' + possessive → 'Посох Кадгара' (genitive case). "
    "Use official Blizzard RU-RU WoW terminology and declensions.",

    # Règle 5 — Anti-hallucination STRICTE
    "RULE 5 — NO EXPLANATIONS: NEVER write 'Примечание:', 'Замечание:', 'Пояснение:', 'Перевод:'. "
    "NEVER explain your reasoning. NEVER mention rules or instructions. "
    "NEVER add meta-commentary or translator notes. Output ONLY the translation, nothing else. "
    "If the input is a short phrase, output ONLY the short translated phrase.",

    # Règle 6 — Realm First!
    "RULE 6 — REALM FIRST: Translate 'Realm First!' as 'Первый на сервере!' (official Blizzard RU).",

    # Règle 7 — Terminologie étendue
    "RULE 7 — EXTRA TERMS: Rarespawn→Редкое порождение | Prestige→Престиж | "
    "Hardcore→Режим хардкор | Achievement→Достижение | Battleground→Поле битвы | "
    "Arena→Арена | Trinket→Аксессуар | Mount→Средство передвижения | "
    "Pet→Питомец | Reputation→Репутация | Honor→Честь | Talent→Талант | "
    "Armor→Броня | Weapon→Оружие | Shield→Щит | Stamina→Выносливость | "
    "Intellect→Интеллект | Agility→Ловкость | Strength→Сила | Spirit→Дух | "
    "Haste→Скорость | Critical→Критический удар | Dodge→Уклонение | "
    "Parry→Парирование | Block→Блокирование.",

    # Règle 8 — Pas de mélange de langues
    "RULE 8 — NO LANGUAGE MIXING: NEVER mix French, English, or any non-Russian words. "
    "Words like 'Tranchantes', 'Mythique', 'de', 'le', 'la' are FORBIDDEN in output. "
    "Every word must be in Cyrillic Russian.",
]

# ── Post-corrections regex (ruRU) ─────────────────────────────────────────────
# Appliquées après la traduction IA pour nettoyer le Latin résiduel
CORRECTIONS = [
    # Anglais résiduel — pronoms
    (r'\byou\b',            'вы'),
    (r'\bYou\b',            'Вы'),
    (r'\byour\b',           'ваш'),
    (r'\bYour\b',           'Ваш'),
    (r'\bI\b(?=\s)',        'я'),
    (r'\bwe\b',             'мы'),
    (r'\bWe\b',             'Мы'),
    # Anglais résiduel — termes WoW fréquents
    (r'\bquest\b',          'задание'),
    (r'\bQuest\b',          'Задание'),
    (r'\bhealing\b',        'исцеление'),
    (r'\bHealing\b',        'Исцеление'),
    (r'\bspell\b',          'заклинание'),
    (r'\bSpell\b',          'Заклинание'),
    (r'\bguild\b',          'гильдия'),
    (r'\bGuild\b',          'Гильдия'),
    (r'\blevel\b',          'уровень'),
    (r'\bLevel\b',          'Уровень'),
    (r'\bitem\b',           'предмет'),
    (r'\bItem\b',           'Предмет'),
    (r'\bdamage\b',         'урон'),
    (r'\bDamage\b',         'Урон'),
    (r'\bdungeon\b',        'подземелье'),
    (r'\bDungeon\b',        'Подземелье'),
    (r'\braid\b',           'рейд'),
    (r'\bRaid\b',           'Рейд'),
    (r'\benemy\b',          'враг'),
    (r'\bEnemy\b',          'Враг'),
    (r'\bally\b',           'союзник'),
    (r'\bAlly\b',           'Союзник'),
    (r'\bpower\b',          'сила'),
    (r'\bPower\b',          'Сила'),
    (r'\bmana\b',           'мана'),
    (r'\bMana\b',           'Мана'),
    (r'\btank\b',           'танк'),
    (r'\bTank\b',           'Танк'),
    (r'\bhealer\b',         'целитель'),
    (r'\bHealer\b',         'Целитель'),
    (r'\bbuff\b',           'усиление'),
    (r'\bBuff\b',           'Усиление'),
    (r'\bdebuff\b',         'ослабление'),
    (r'\bDebuff\b',         'Ослабление'),
    (r'\bcooldown\b',       'перезарядка'),
    (r'\bCooldown\b',       'Перезарядка'),
    # Ты/твой → вы/ваш (si le modèle déraille)
    (r'\bты\b',             'вы'),
    (r'\bТы\b',             'Вы'),
    (r'\bтвой\b',           'ваш'),
    (r'\bТвой\b',           'Ваш'),
    (r'\bтвоя\b',           'ваша'),
    (r'\bТвоя\b',           'Ваша'),
    (r'\bтвоё\b',           'ваше'),
    (r'\bТвоё\b',           'Ваше'),
    (r'\bтвои\b',           'ваши'),
    (r'\bТвои\b',           'Ваши'),
    (r'\bтебя\b',           'вас'),
    (r'\bТебя\b',           'Вас'),
    (r'\bтебе\b',           'вам'),
    (r'\bТебе\b',           'Вам'),
    # Français résiduel — mots français qui fuient dans la sortie russe
    (r'\bde\b(?=\s[a-zà-ÿ])', ''),
    (r'\ble\b(?=\s)',       ''),
    (r'\bla\b(?=\s[a-zà-ÿ])', ''),
    (r'\bles\b(?=\s)',      ''),
    (r'\bdu\b(?=\s)',       ''),
    (r'\bdes\b(?=\s)',      ''),
    (r'\bun\b(?=\s)',       ''),
    (r'\bune\b(?=\s)',      ''),
    (r'\bet\b(?=\s)',       ''),
    (r'\bTranchantes?\b',   ''),
    (r'\bMythique\b',       'Эпохальный'),
    # Anglais résiduel supplémentaire
    (r'\bachievement\b',    'достижение'),
    (r'\bAchievement\b',    'Достижение'),
    (r'\bbattleground\b',   'поле битвы'),
    (r'\bBattleground\b',   'Поле битвы'),
    (r'\barena\b',          'арена'),
    (r'\bArena\b',          'Арена'),
    (r'\btrinket\b',        'аксессуар'),
    (r'\bTrinket\b',        'Аксессуар'),
    (r'\bmount\b',          'средство передвижения'),
    (r'\bMount\b',          'Средство передвижения'),
    (r'\bpet\b',            'питомец'),
    (r'\bPet\b',            'Питомец'),
    (r'\btalent\b',         'талант'),
    (r'\bTalent\b',         'Талант'),
    (r'\barmor\b',          'броня'),
    (r'\bArmor\b',          'Броня'),
    (r'\bweapon\b',         'оружие'),
    (r'\bWeapon\b',         'Оружие'),
    (r'\bshield\b',         'щит'),
    (r'\bShield\b',         'Щит'),
    (r'\bRealm First!\b',   'Первый на сервере!'),
    # Anti-hallucination — supprimer préfixes explicatifs
    (r'^Примечание\s*:\s*', ''),
    (r'^Замечание\s*:\s*',  ''),
    (r'^Пояснение\s*:\s*',  ''),
    (r'^Перевод\s*:\s*',    ''),
    (r'^Note\s*:\s*',       ''),
    # Latin/Cyrillic mélangé — lettres latines courantes dans des mots cyrilliques
    (r'(?<=[а-яА-ЯёЁ])a(?=[а-яА-ЯёЁ])', 'а'),
    (r'(?<=[а-яА-ЯёЁ])e(?=[а-яА-ЯёЁ])', 'е'),
    (r'(?<=[а-яА-ЯёЁ])o(?=[а-яА-ЯёЁ])', 'о'),
    (r'(?<=[а-яА-ЯёЁ])p(?=[а-яА-ЯёЁ])', 'р'),
    (r'(?<=[а-яА-ЯёЁ])c(?=[а-яА-ЯёЁ])', 'с'),
    (r'(?<=[а-яА-ЯёЁ])x(?=[а-яА-ЯёЁ])', 'х'),
    (r'(?<=[а-яА-ЯёЁ])A(?=[а-яА-ЯёЁ])', 'А'),
    (r'(?<=[а-яА-ЯёЁ])E(?=[а-яА-ЯёЁ])', 'Е'),
    (r'(?<=[а-яА-ЯёЁ])O(?=[а-яА-ЯёЁ])', 'О'),
    (r'(?<=[а-яА-ЯёЁ])P(?=[а-яА-ЯёЁ])', 'Р'),
    (r'(?<=[а-яА-ЯёЁ])C(?=[а-яА-ЯёЁ])', 'С'),
]
