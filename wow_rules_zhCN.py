# wow_rules_zhCN.py
# ─────────────────────────────────────────────────────────────────────────────
# Règles de traduction WoW — Locale ZH-CN (Chine continentale, Mandarin simplifié)
# Modèle optimal  : qwen2.5:14b (meilleur corpus CJK, qualité supérieure)
# Correction 2e pers : 你 (informel joueur) / 您 (formel PNJ)
# Particularités   : caractères simplifiés UNIQUEMENT (pas traditionnels),
#                    ponctuation chinoise (，。！？), pas d'espaces entre caractères
# ─────────────────────────────────────────────────────────────────────────────

MODELE_IA = "qwen2.5:14b"
LANG_NAME  = "Simplified Mandarin Chinese"

# ── Règles injectées dans le prompt système ───────────────────────────────────
LANG_RULES = [
    # Règle 1 — Chinois simplifié exclusif
    "RULE 1 — SIMPLIFIED CHINESE: Output ONLY Simplified Chinese (简体字, Mainland China standard). "
    "NEVER use Traditional Chinese characters (繁體字). "
    "NEVER leave English words untranslated. NEVER mix Latin and Chinese characters.",

    # Règle 2 — Pronoms
    "RULE 2 — YOU: Use '你' for player address (informal, standard WoW CN). "
    "Use '您' only for very formal NPC speech. "
    "Examples: 'You must' → '你必须' | 'Your quest' → '你的任务' | "
    "'Your power' → '你的力量' | 'I need you' → '我需要你'.",

    # Règle 3 — Terminologie WoW officielle Blizzard CN
    "RULE 3 — WoW TERMS: Quest→任务 | damage→伤害 | healing→治疗量 | "
    "guild→公会 | spell→法术 | ability→技能 | item→物品 | "
    "dungeon→地下城 | raid→团队副本 | enemy→敌人 | ally→盟友 | "
    "level→等级 | power→力量 | mana→法力值 | buff→增益 | debuff→减益 | "
    "cooldown→冷却时间 | tank→坦克 | healer→治疗 | DPS→输出.",

    # Règle 4 — Syntaxe possessifs
    "RULE 4 — POSSESSIVES: 'Khadgar' + possessive → '卡德加的法杖' (use 的 particle). "
    "Use official Blizzard ZH-CN WoW terminology.",

    # Règle 5 — Ponctuation
    "RULE 5 — PUNCTUATION: Use Chinese punctuation marks: ，。！？；：. "
    "Do NOT add spaces between Chinese characters. "
    "Do NOT add spaces before Chinese punctuation.",

    # Règle 6 — Anti-hallucination
    "RULE 6 — NO EXPLANATIONS: NEVER write 注意, 注释, 翻译说明, 备注, 说明. "
    "NEVER explain your reasoning. NEVER add translator notes or meta-commentary. "
    "Output ONLY the translation, nothing else.",

    # Règle 7 — Realm First!
    "RULE 7 — REALM FIRST: Translate 'Realm First!' as '服务器首杀！' (official Blizzard CN).",

    # Règle 8 — Simplified enforcement
    "RULE 8 — SIMPLIFIED ENFORCEMENT: Common Traditional→Simplified corrections: "
    "東→东 | 書→书 | 開→开 | 門→门 | 見→见 | 長→长 | 車→车 | 馬→马 | "
    "語→语 | 點→点 | 電→电 | 國→国 | 學→学 | 與→与 | 對→对 | 發→发 | "
    "問→问 | 時→时 | 過→过 | 義→义 | 實→实 | 從→从 | 機→机 | 關→关 | "
    "頭→头 | 裝→装 | 備→备 | 護→护 | 傷→伤 | 種→种 | 隊→队.",

    # Règle 9 — Terminologie étendue
    "RULE 9 — EXTRA TERMS: Achievement→成就 | Battleground→战场 | Arena→竞技场 | "
    "Trinket→饰品 | Mount→坐骑 | Pet→宠物 | Reputation→声望 | Honor→荣誉 | "
    "Talent→天赋 | Armor→护甲 | Weapon→武器 | Shield→盾牌 | "
    "Stamina→耐力 | Intellect→智力 | Agility→敏捷 | Strength→力量 | Spirit→精神 | "
    "Haste→急速 | Critical→暴击 | Dodge→闪避 | Parry→招架 | Block→格挡.",
]

# ── Post-corrections regex (zhCN) ─────────────────────────────────────────────
# Appliquées après la traduction IA pour nettoyer le Latin résiduel
# (qwen2.5 laisse parfois des mots anglais non traduits en fin de phrase)
CORRECTIONS = [
    # Anglais résiduel — pronoms
    (r'\byou\b',            '你'),
    (r'\bYou\b',            '你'),
    (r'\byour\b',           '你的'),
    (r'\bYour\b',           '你的'),
    (r'\bI\b(?=\s|$)',      '我'),
    (r'\bwe\b',             '我们'),
    (r'\bWe\b',             '我们'),
    # Anglais résiduel — termes WoW fréquents
    (r'\bquest\b',          '任务'),
    (r'\bQuest\b',          '任务'),
    (r'\bdamage\b',         '伤害'),
    (r'\bDamage\b',         '伤害'),
    (r'\bhealing\b',        '治疗'),
    (r'\bHealing\b',        '治疗'),
    (r'\bspell\b',          '法术'),
    (r'\bSpell\b',          '法术'),
    (r'\bguild\b',          '公会'),
    (r'\bGuild\b',          '公会'),
    (r'\blevel\b',          '等级'),
    (r'\bLevel\b',          '等级'),
    (r'\bitem\b',           '物品'),
    (r'\bItem\b',           '物品'),
    (r'\bdungeon\b',        '地下城'),
    (r'\bDungeon\b',        '地下城'),
    (r'\braid\b',           '团队副本'),
    (r'\bRaid\b',           '团队副本'),
    (r'\benemy\b',          '敌人'),
    (r'\bEnemy\b',          '敌人'),
    (r'\bally\b',           '盟友'),
    (r'\bAlly\b',           '盟友'),
    (r'\bpower\b',          '力量'),
    (r'\bPower\b',          '力量'),
    (r'\bmana\b',           '法力值'),
    (r'\bMana\b',           '法力值'),
    (r'\btank\b',           '坦克'),
    (r'\bTank\b',           '坦克'),
    (r'\bhealer\b',         '治疗'),
    (r'\bHealer\b',         '治疗'),
    (r'\bbuff\b',           '增益'),
    (r'\bBuff\b',           '增益'),
    (r'\bdebuff\b',         '减益'),
    (r'\bDebuff\b',         '减益'),
    (r'\bcooldown\b',       '冷却'),
    (r'\bCooldown\b',       '冷却'),
    (r'\bability\b',        '技能'),
    (r'\bAbility\b',        '技能'),
    # Ponctuation latine → chinoise (après les mots)
    (r'(?<=[\u4e00-\u9fff]),',  '，'),
    (r'(?<=[\u4e00-\u9fff])\.',  '。'),
    (r'(?<=[\u4e00-\u9fff])!',   '！'),
    (r'(?<=[\u4e00-\u9fff])\?',  '？'),
    # Espaces parasites entre caractères CJK
    (r'([\u4e00-\u9fff])\s+([\u4e00-\u9fff])', r'\1\2'),
    # Anglais résiduel supplémentaire
    (r'\bachievement\b',    '成就'),
    (r'\bAchievement\b',    '成就'),
    (r'\bbattleground\b',   '战场'),
    (r'\bBattleground\b',   '战场'),
    (r'\barena\b',          '竞技场'),
    (r'\bArena\b',          '竞技场'),
    (r'\btrinket\b',        '饰品'),
    (r'\bTrinket\b',        '饰品'),
    (r'\bmount\b',          '坐骑'),
    (r'\bMount\b',          '坐骑'),
    (r'\bpet\b',            '宠物'),
    (r'\bPet\b',            '宠物'),
    (r'\btalent\b',         '天赋'),
    (r'\bTalent\b',         '天赋'),
    (r'\barmor\b',          '护甲'),
    (r'\bArmor\b',          '护甲'),
    (r'\bweapon\b',         '武器'),
    (r'\bWeapon\b',         '武器'),
    (r'\bshield\b',         '盾牌'),
    (r'\bShield\b',         '盾牌'),
    (r'\bthe\b',            ''),
    (r'\bThe\b',            ''),
    (r'\band\b',            '和'),
    (r'\bof\b',             '的'),
    (r'\bin\b',             '在'),
    (r'\bwith\b',           '与'),
    (r'\bfor\b',            '为'),
    (r'\bfrom\b',           '从'),
    (r'\bis\b',             '是'),
    (r'\bnot\b',            '不'),
    (r'\bbut\b',            '但'),
    (r'\bthis\b',           '这'),
    (r'\bthat\b',           '那'),
    (r'\bRealm First!\b',   '服务器首杀！'),
    # Anti-hallucination — supprimer préfixes explicatifs
    (r'^注意\s*[:：]\s*',    ''),
    (r'^注释\s*[:：]\s*',    ''),
    (r'^翻译说明\s*[:：]\s*', ''),
    (r'^备注\s*[:：]\s*',    ''),
    (r'^说明\s*[:：]\s*',    ''),
    (r'^Note\s*:\s*',       ''),
    # Caractères traditionnels courants → simplifiés
    ('東', '东'),
    ('書', '书'),
    ('開', '开'),
    ('門', '门'),
    ('見', '见'),
    ('長', '长'),
    ('車', '车'),
    ('馬', '马'),
    ('語', '语'),
    ('點', '点'),
    ('電', '电'),
    ('國', '国'),
    ('學', '学'),
    ('與', '与'),
    ('對', '对'),
    ('發', '发'),
    ('問', '问'),
    ('時', '时'),
    ('過', '过'),
    ('義', '义'),
    ('實', '实'),
    ('從', '从'),
    ('機', '机'),
    ('關', '关'),
    ('頭', '头'),
    ('裝', '装'),
    ('備', '备'),
    ('護', '护'),
    ('傷', '伤'),
    ('種', '种'),
    ('隊', '队'),
]
