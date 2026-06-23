# wow_rules_deDE.py
# ─────────────────────────────────────────────────────────────────────────────
# Règles de traduction WoW — Locale DE-DE (Allemagne)
# Modèle optimal  : mistral-nemo (benchmark 98.3% vs qwen 96.9%, +30% vitesse)
# Correction 2e pers : Ihr/Euch/Euer/Eure (formel, jamais du/dich/dein)
# Particularités   : majuscules nominales OBLIGATOIRES, umlauts (ä/ö/ü/ß)
# ─────────────────────────────────────────────────────────────────────────────

MODELE_IA = "mistral-nemo"
LANG_NAME  = "German"

# ── Règles injectées dans le prompt système ───────────────────────────────────
LANG_RULES = [
    # Règle 1 — Vouvoiement formel Ihr/Euch
    "RULE 1 — FORMAL YOU: ALWAYS use 'Ihr/Euch/Euer/Eure' for 2nd person. "
    "NEVER du, dich, dein, deine, dir. "
    "Conjugation: du→Ihr | dich→Euch | dein→Euer | deine→Eure | deinen→Euren | "
    "deiner→Eurer | deinem→Eurem | dir→Euch | bist→seid | hast→habt | "
    "kannst→könnt | musst→müsst | weißt→wisst | willst→wollt. "
    "Examples: 'Your power' → 'Eure Macht' | 'You must' → 'Ihr müsst' | "
    "'I give you' → 'Ich gebe Euch'.",

    # Règle 2 — Majuscules nominales
    "RULE 2 — NOUN CAPITALIZATION: Capitalize EVERY noun without exception. "
    "Examples: schaden→Schaden | heilung→Heilung | zauber→Zauber | quest→Quest | "
    "held→Held | kraft→Kraft | feind→Feind | verbündeter→Verbündeter | "
    "waffe→Waffe | rüstung→Rüstung | kampf→Kampf | fähigkeit→Fähigkeit | "
    "dungeon→Dungeon | gilde→Gilde | krieger→Krieger | priester→Priester.",

    # Règle 3 — Syntaxe et terminologie
    "RULE 3 — POSSESSIVES: 'Khadgar' + possessive → 'Khadgars Robe' (NO apostrophe). "
    "Use official Blizzard DE-DE WoW terminology. "
    "Quest→Aufgabe | Dungeon→Verlies | Raid→Schlachtzug | Spell→Zauber | "
    "Ability→Fähigkeit | Damage→Schaden | Healing→Heilung | "
    "Guild→Gilde | Enemy→Feind | Ally→Verbündeter.",

    # Règle 4 — Anti-hallucination
    "RULE 4 — NO EXPLANATIONS: Output ONLY the translation. NEVER write 'Anmerkung:', "
    "'Hinweis:', 'Übersetzung:', 'Notiz:', or any meta-commentary. "
    "NEVER explain your reasoning or mention translation rules. Just translate.",

    # Règle 5 — Realm First!
    "RULE 5 — REALM FIRST: Translate 'Realm First!' as 'Realm First!' (kept in English, official Blizzard DE).",

    # Règle 6 — Terminologie étendue
    "RULE 6 — EXTRA TERMS: Achievement→Erfolg | Battleground→Schlachtfeld | "
    "Arena→Arena | Trinket→Schmuckstück | Mount→Reittier | Pet→Begleiter | "
    "Reputation→Ruf | Honor→Ehre | Talent→Talent | Armor→Rüstung | "
    "Weapon→Waffe | Shield→Schild | Stamina→Ausdauer | Intellect→Intelligenz | "
    "Agility→Beweglichkeit | Strength→Stärke | Spirit→Willenskraft | "
    "Haste→Tempo | Critical→Kritisch | Dodge→Ausweichen | Parry→Parieren | "
    "Block→Blocken | Mana→Mana | Buff→Stärkungszauber | Debuff→Schwächungszauber | "
    "Cooldown→Abklingzeit | Tank→Tank | Healer→Heiler | DPS→Schadensausteiler | "
    "Item→Gegenstand | Power→Macht | Level→Stufe.",
]

# ── Post-corrections regex (deDE) ─────────────────────────────────────────────
# Appliquées après la traduction IA pour corriger les oublis de majuscules nominales
# et les formes du/dich qui échappent au prompt
CORRECTIONS = [
    # Termes core WoW — majuscules nominales
    (r'\bschaden\b',        'Schaden'),
    (r'\bheilung\b',        'Heilung'),
    (r'\bzauber\b',         'Zauber'),
    (r'\bfähigkeit\b',      'Fähigkeit'),
    (r'\bfähigkeiten\b',    'Fähigkeiten'),
    (r'\bquest\b',          'Quest'),
    (r'\baufgabe\b',        'Aufgabe'),
    (r'\bgebiet\b',         'Gebiet'),
    (r'\bbereich\b',        'Bereich'),
    (r'\bfeind\b',          'Feind'),
    (r'\bgegner\b',         'Gegner'),
    (r'\bverbündeter\b',    'Verbündeter'),
    (r'\bverbündete\b',     'Verbündete'),
    (r'\bspieler\b',        'Spieler'),
    (r'\bcharakter\b',      'Charakter'),
    (r'\bheld\b',           'Held'),
    (r'\bkraft\b',          'Kraft'),
    (r'\bmagie\b',          'Magie'),
    (r'\bwaffe\b',          'Waffe'),
    (r'\brüstung\b',        'Rüstung'),
    (r'\bwelt\b',           'Welt'),
    (r'\bkrieger\b',        'Krieger'),
    (r'\bpriester\b',       'Priester'),
    (r'\bmagier\b',         'Magier'),
    (r'\bgott\b',           'Gott'),
    (r'\bkönig\b',          'König'),
    (r'\breich\b',          'Reich'),
    (r'\bfreund\b',         'Freund'),
    (r'\bkampf\b',          'Kampf'),
    (r'\bdungeon\b',        'Dungeon'),
    (r'\bhorde\b',          'Horde'),
    (r'\ballianz\b',        'Allianz'),
    (r'\bschlachtzug\b',    'Schlachtzug'),
    (r'\bbelohnung\b',      'Belohnung'),
    (r'\bauftrag\b',        'Auftrag'),
    (r'\bmonster\b',        'Monster'),
    (r'\bboss\b',           'Boss'),
    (r'\bkristall\b',       'Kristall'),
    (r'\bkammer\b',         'Kammer'),
    (r'\bturm\b',           'Turm'),
    (r'\bfestung\b',        'Festung'),
    (r'\btempel\b',         'Tempel'),
    (r'\bgrotte\b',         'Grotte'),
    (r'\bschlucht\b',       'Schlucht'),
    (r'\bstärke\b',         'Stärke'),
    (r'\bausdauer\b',       'Ausdauer'),
    (r'\bintelligenz\b',    'Intelligenz'),
    (r'\bgeist\b',          'Geist'),
    (r'\bgeschick\b',       'Geschick'),
    (r'\bverzauberung\b',   'Verzauberung'),
    (r'\btrank\b',          'Trank'),
    (r'\btränke\b',         'Tränke'),
    (r'\bgegenstand\b',     'Gegenstand'),
    (r'\bgegenstände\b',    'Gegenstände'),
    (r'\bgilde\b',          'Gilde'),
    (r'\bgildenmitglied\b', 'Gildenmitglied'),
    (r'\bzauberspruch\b',   'Zauberspruch'),
    (r'\bzaubersprüche\b',  'Zaubersprüche'),
    (r'\bsegen\b',          'Segen'),
    (r'\bfluch\b',          'Fluch'),
    (r'\btalent\b',         'Talent'),
    (r'\btalente\b',        'Talente'),
    (r'\bwürde\b',          'Würde'),
    # Vouvoiement formel — cas les plus fréquents
    (r'\bDein\b',           'Euer'),
    (r'\bdein\b',           'euer'),
    (r'\bDeine\b',          'Eure'),
    (r'\bdeine\b',          'eure'),
    (r'\bDich\b',           'Euch'),
    (r'\bdich\b',           'euch'),
    (r'\bDir\b',            'Euch'),
    (r'\bdir\b',            'euch'),
    # Anglais résiduel
    (r'\byou\b',            'Ihr'),
    (r'\bYou\b',            'Ihr'),
    (r'\byour\b',           'Euer'),
    (r'\bYour\b',           'Euer'),
    (r'\bdamage\b',         'Schaden'),
    (r'\bDamage\b',         'Schaden'),
    (r'\bhealing\b',        'Heilung'),
    (r'\bHealing\b',        'Heilung'),
    (r'\bspell\b',          'Zauber'),
    (r'\bSpell\b',          'Zauber'),
    (r'\bguild\b',          'Gilde'),
    (r'\bGuild\b',          'Gilde'),
    (r'\blevel\b',          'Stufe'),
    (r'\bLevel\b',          'Stufe'),
    (r'\bquest\b',          'Aufgabe'),
    (r'\bQuest\b',          'Aufgabe'),
    # Termes WoW supplémentaires — majuscules nominales
    (r'\berfolg\b',          'Erfolg'),
    (r'\bschlachtfeld\b',    'Schlachtfeld'),
    (r'\barena\b',           'Arena'),
    (r'\bschmuckstück\b',    'Schmuckstück'),
    (r'\breittier\b',        'Reittier'),
    (r'\bbegleiter\b',       'Begleiter'),
    (r'\bruf\b',             'Ruf'),
    (r'\behre\b',            'Ehre'),
    (r'\bschild\b',          'Schild'),
    (r'\bmacht\b',           'Macht'),
    (r'\btempo\b',           'Tempo'),
    (r'\babklingzeit\b',     'Abklingzeit'),
    (r'\bheiler\b',          'Heiler'),
    (r'\bschwert\b',         'Schwert'),
    (r'\baxt\b',             'Axt'),
    (r'\bbogen\b',           'Bogen'),
    (r'\bdolch\b',           'Dolch'),
    (r'\bstab\b',            'Stab'),
    (r'\bring\b',            'Ring'),
    (r'\bkette\b',           'Kette'),
    (r'\bhelm\b',            'Helm'),
    (r'\bmantel\b',          'Mantel'),
    (r'\bhandschuhe\b',      'Handschuhe'),
    (r'\bstiefel\b',         'Stiefel'),
    (r'\bgürtel\b',          'Gürtel'),
    (r'\bumhang\b',          'Umhang'),
    (r'\bbeweglichkeit\b',   'Beweglichkeit'),
    (r'\bwillenskraft\b',    'Willenskraft'),
    # Anglais résiduel supplémentaire
    (r'\bachievement\b',     'Erfolg'),
    (r'\bAchievement\b',     'Erfolg'),
    (r'\bbattleground\b',    'Schlachtfeld'),
    (r'\bBattleground\b',    'Schlachtfeld'),
    (r'\btrinket\b',         'Schmuckstück'),
    (r'\bTrinket\b',         'Schmuckstück'),
    (r'\bmount\b',           'Reittier'),
    (r'\bMount\b',           'Reittier'),
    (r'\bpet\b',             'Begleiter'),
    (r'\bPet\b',             'Begleiter'),
    (r'\barmor\b',           'Rüstung'),
    (r'\bArmor\b',           'Rüstung'),
    (r'\bweapon\b',          'Waffe'),
    (r'\bWeapon\b',          'Waffe'),
    (r'\bshield\b',          'Schild'),
    (r'\bShield\b',          'Schild'),
    (r'\btalent\b',          'Talent'),
    (r'\bTalent\b',          'Talent'),
    (r'\bbuff\b',            'Stärkungszauber'),
    (r'\bBuff\b',            'Stärkungszauber'),
    (r'\bdebuff\b',          'Schwächungszauber'),
    (r'\bDebuff\b',          'Schwächungszauber'),
    (r'\bcooldown\b',        'Abklingzeit'),
    (r'\bCooldown\b',        'Abklingzeit'),
    (r'\benemy\b',           'Feind'),
    (r'\bEnemy\b',           'Feind'),
    (r'\bally\b',            'Verbündeter'),
    (r'\bAlly\b',            'Verbündeter'),
    (r'\bpower\b',           'Macht'),
    (r'\bPower\b',           'Macht'),
    (r'\bmana\b',            'Mana'),
    (r'\bMana\b',            'Mana'),
    (r'\btank\b',            'Tank'),
    (r'\bTank\b',            'Tank'),
    (r'\bitem\b',            'Gegenstand'),
    (r'\bItem\b',            'Gegenstand'),
    # Anti-hallucination — supprimer préfixes explicatifs
    (r'^Anmerkung\s*:\s*',   ''),
    (r'^Hinweis\s*:\s*',     ''),
    (r'^Übersetzung\s*:\s*',  ''),
    (r'^Notiz\s*:\s*',       ''),
    (r'^Note\s*:\s*',        ''),
]
