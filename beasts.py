"""
Beast data. Design rules are explained in docs/beast.md.
Stats are multipliers on a player of the same realm and layer (see stats.py).
"""

# ── Tiers ─────────────────────────────────────────────────────────────

BEAST_TIERS = {
    "normal":     {"hp": 1.0,  "attack": 0.8, "team_size": 1},
    "elite":      {"hp": 5.0,  "attack": 1.3, "team_size": 3},
    "beast_king": {"hp": 12.0, "attack": 1.6, "team_size": 5},
}
BEAST_DEFENSE_RATIO = 0.25          # Defense = Attack × this
EXTRA_PLAYER_HP_BONUS = 0.20        # per player beyond team_size

# ── Low-realm easing ──────────────────────────────────────────────────
# Players found early beasts too slow to kill and Elites near impossible, so the
# first realms get weaker beasts. Multipliers on HP and Attack per (realm, tier);
# realms not listed (and Beast Kings) use full strength.
LOW_REALM_EASE = {
    "Mortal":             {"normal": {"hp": 0.55, "attack": 0.75}, "elite": {"hp": 0.35, "attack": 0.50}},
    "Martial Apprentice": {"normal": {"hp": 0.55, "attack": 0.75}, "elite": {"hp": 0.35, "attack": 0.50}},
    "Martial Warrior":    {"normal": {"hp": 0.65, "attack": 0.80}, "elite": {"hp": 0.50, "attack": 0.70}},
    "Martial Expert":     {"normal": {"hp": 0.80, "attack": 0.90}, "elite": {"hp": 0.65, "attack": 0.80}},
    "Martial Master":     {"normal": {"hp": 0.90, "attack": 0.95}, "elite": {"hp": 0.80, "attack": 0.90}},
}
# One turn of damage may take this share of a low-realm Normal beast's HP
# (instead of the usual 30%), so it can fall in 3 turns instead of 4.
LOW_REALM_NORMAL_HIT_CAP = 0.40


def realm_ease(realm, tier):
    """{"hp", "attack"} multipliers for a beast of this tier met in this realm."""
    return LOW_REALM_EASE.get(realm, {}).get(tier, {"hp": 1.0, "attack": 1.0})


def hit_cap(realm, tier):
    """Largest share of the beast's max HP one turn of damage can take, or None for the usual cap."""
    return LOW_REALM_NORMAL_HIT_CAP if tier == "normal" and realm in LOW_REALM_EASE else None

# ── Roles ─────────────────────────────────────────────────────────────

ROLES = {
    "brute":   {"hp": 1.20, "attack": 0.90},
    "hunter":  {"hp": 0.85, "attack": 1.20},
    "swift":   {"dodge": 0.15},
    "armored": {"defense": 2.0},
}

# ── Special rules ─────────────────────────────────────────────────────

CHARGED_ATTACK_TIERS = ["elite", "beast_king"]   # telegraphed, ignores 30% cap
BREAK_STAGGER_SKIPS_TURN = True

# ── Roster: realm → list of (name, tier, role) ────────────────────────

BEASTS = {
    "Mortal": [
        ("Wild Boar", "normal", "brute"),
        ("Field Viper", "normal", "hunter"),
        ("Stray Dog Pack", "normal", "swift"),
        ("Grey Wolf", "elite", "hunter"),
        ("Wild Ox", "elite", "brute"),
        ("Old Black Bear", "beast_king", "brute"),
    ],
    "Martial Apprentice": [
        ("Iron-Hide Boar", "normal", "armored"),
        ("Red Fox", "normal", "swift"),
        ("Cave Bat Swarm", "normal", "swift"),
        ("Shadow Wolf", "elite", "hunter"),
        ("Horned Stag", "elite", "brute"),
        ("Mountain Tiger", "beast_king", "hunter"),
    ],
    "Martial Warrior": [
        ("Thornback Lizard", "normal", "armored"),
        ("Rock Python", "normal", "brute"),
        ("Spear-Beak Crane", "normal", "swift"),
        ("Bloodfang Wolf", "elite", "hunter"),
        ("Armored Boar Chief", "elite", "armored"),
        ("White-Browed Tiger King", "beast_king", "hunter"),
    ],
    "Martial Expert": [
        ("Venom Scorpion", "normal", "hunter"),
        ("Poison Toad", "normal", "brute"),
        ("Silver Monkey", "normal", "swift"),
        ("Thunder Hawk", "elite", "swift"),
        ("Steel-Horn Bull", "elite", "armored"),
        ("Golden-Eyed Ape King", "beast_king", "brute"),
    ],
    "Martial Master": [
        ("Ironbark Bear", "normal", "armored"),
        ("Frost Wolf", "normal", "hunter"),
        ("Ember Lizard", "normal", "swift"),
        ("Frost Python", "elite", "brute"),
        ("Wind Leopard", "elite", "swift"),
        ("Flame-Maned Lion", "beast_king", "hunter"),
    ],
    "Grand Martial Master": [
        ("Stone-Shell Tortoise", "normal", "armored"),
        ("Lightning Weasel", "normal", "swift"),
        ("Bone Vulture", "normal", "hunter"),
        ("Storm Eagle", "elite", "swift"),
        ("Jade-Scaled Crocodile", "elite", "armored"),
        ("Black Water Serpent", "beast_king", "brute"),
    ],
    "Martial Grandmaster": [
        ("Earth-Splitting Rhino", "normal", "armored"),
        ("Shadow Panther", "normal", "swift"),
        ("Iron-Feather Crow", "normal", "hunter"),
        ("Crimson Fire Hawk", "elite", "hunter"),
        ("Thousand-Year Centipede", "elite", "armored"),
        ("Flood Dragon (Jiao)", "beast_king", "brute"),
    ],
    "Martial King": [
        ("Cloud Leopard", "normal", "swift"),
        ("Shanxiao Mountain Spirit", "normal", "hunter"),
        ("Golden Silk Spider", "normal", "armored"),
        ("Nine-Tailed Fox", "elite", "swift"),
        ("Bifang Fire Crane", "elite", "hunter"),
        ("Qilin", "beast_king", "armored"),
    ],
    "Martial Emperor": [
        ("Thunder Rhino", "normal", "brute"),
        ("Fire-Hoof Steed", "normal", "swift"),
        ("Sky Lynx", "normal", "hunter"),
        ("Pixiu", "elite", "armored"),
        ("Tiangou, the Heavenly Hound", "elite", "hunter"),
        ("Taotie, the Devourer", "beast_king", "brute"),
    ],
    "Martial Ancestor": [
        ("Ancient Golden Ape", "normal", "brute"),
        ("Abyss Crocodile", "normal", "armored"),
        ("Ghost-Fire Wolf", "normal", "swift"),
        ("Vermilion Bird", "elite", "hunter"),
        ("Qiongqi, the Winged Tiger", "elite", "swift"),
        ("Black Tortoise (Xuanwu)", "beast_king", "armored"),
    ],
    "Martial Saint": [
        ("Primordial Dragon Turtle", "normal", "armored"),
        ("Void Serpent", "normal", "swift"),
        ("Ancient Flame Lion", "normal", "hunter"),
        ("Azure Dragon", "elite", "swift"),
        ("White Tiger", "elite", "hunter"),
        ("Kun-Peng, Fish of the Northern Sea", "beast_king", "brute"),
    ],
}

# ── Element and body type of every beast (docs/combat.md) ────────────
# element: Blood, Frost, Flame, Shadow, Thunder, Venom, Earth, Jade (palette + status, see battle.py)
# body: silhouette drawn when art/beasts/<slug>.png is missing:
#       cat, wolf, bird, serpent, ape, turtle, insect, dragon

ELEMENTS = ["Blood", "Frost", "Flame", "Shadow", "Thunder", "Venom", "Earth", "Jade"]
BODY_TYPES = ["cat", "wolf", "bird", "serpent", "ape", "turtle", "insect", "dragon"]

TRAITS = {
    # name: (element, body)
    "Wild Boar": ("Earth", "wolf"),
    "Field Viper": ("Venom", "serpent"),
    "Stray Dog Pack": ("Blood", "wolf"),
    "Grey Wolf": ("Frost", "wolf"),
    "Wild Ox": ("Earth", "wolf"),
    "Old Black Bear": ("Blood", "ape"),
    "Iron-Hide Boar": ("Earth", "wolf"),
    "Red Fox": ("Flame", "wolf"),
    "Cave Bat Swarm": ("Shadow", "bird"),
    "Shadow Wolf": ("Shadow", "wolf"),
    "Horned Stag": ("Jade", "wolf"),
    "Mountain Tiger": ("Blood", "cat"),
    "Thornback Lizard": ("Earth", "dragon"),
    "Rock Python": ("Venom", "serpent"),
    "Spear-Beak Crane": ("Frost", "bird"),
    "Bloodfang Wolf": ("Blood", "wolf"),
    "Armored Boar Chief": ("Earth", "wolf"),
    "White-Browed Tiger King": ("Frost", "cat"),
    "Venom Scorpion": ("Venom", "insect"),
    "Poison Toad": ("Venom", "turtle"),
    "Silver Monkey": ("Thunder", "ape"),
    "Thunder Hawk": ("Thunder", "bird"),
    "Steel-Horn Bull": ("Earth", "wolf"),
    "Golden-Eyed Ape King": ("Thunder", "ape"),
    "Ironbark Bear": ("Jade", "ape"),
    "Frost Wolf": ("Frost", "wolf"),
    "Ember Lizard": ("Flame", "dragon"),
    "Frost Python": ("Frost", "serpent"),
    "Wind Leopard": ("Thunder", "cat"),
    "Flame-Maned Lion": ("Flame", "cat"),
    "Stone-Shell Tortoise": ("Earth", "turtle"),
    "Lightning Weasel": ("Thunder", "wolf"),
    "Bone Vulture": ("Shadow", "bird"),
    "Storm Eagle": ("Thunder", "bird"),
    "Jade-Scaled Crocodile": ("Jade", "dragon"),
    "Black Water Serpent": ("Shadow", "serpent"),
    "Earth-Splitting Rhino": ("Earth", "wolf"),
    "Shadow Panther": ("Shadow", "cat"),
    "Iron-Feather Crow": ("Blood", "bird"),
    "Crimson Fire Hawk": ("Flame", "bird"),
    "Thousand-Year Centipede": ("Venom", "insect"),
    "Flood Dragon (Jiao)": ("Frost", "dragon"),
    "Cloud Leopard": ("Thunder", "cat"),
    "Shanxiao Mountain Spirit": ("Jade", "ape"),
    "Golden Silk Spider": ("Venom", "insect"),
    "Nine-Tailed Fox": ("Flame", "wolf"),
    "Bifang Fire Crane": ("Flame", "bird"),
    "Qilin": ("Jade", "cat"),
    "Thunder Rhino": ("Thunder", "wolf"),
    "Fire-Hoof Steed": ("Flame", "wolf"),
    "Sky Lynx": ("Frost", "cat"),
    "Pixiu": ("Jade", "cat"),
    "Tiangou, the Heavenly Hound": ("Shadow", "wolf"),
    "Taotie, the Devourer": ("Blood", "cat"),
    "Ancient Golden Ape": ("Earth", "ape"),
    "Abyss Crocodile": ("Shadow", "dragon"),
    "Ghost-Fire Wolf": ("Flame", "wolf"),
    "Vermilion Bird": ("Flame", "bird"),
    "Qiongqi, the Winged Tiger": ("Blood", "cat"),
    "Black Tortoise (Xuanwu)": ("Frost", "turtle"),
    "Primordial Dragon Turtle": ("Earth", "turtle"),
    "Void Serpent": ("Shadow", "serpent"),
    "Ancient Flame Lion": ("Flame", "cat"),
    "Azure Dragon": ("Jade", "dragon"),
    "White Tiger": ("Frost", "cat"),
    "Kun-Peng, Fish of the Northern Sea": ("Frost", "bird"),
}


def element_of(name):
    return TRAITS[name][0]


def body_of(name):
    return TRAITS[name][1]


def slug(name):
    """File name for beast art: art/beasts/<slug>.png ("Flood Dragon (Jiao)" -> "flood_dragon_jiao")."""
    out = "".join(c.lower() if c.isalnum() else "_" for c in name)
    while "__" in out:
        out = out.replace("__", "_")
    return out.strip("_")
