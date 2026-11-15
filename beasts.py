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


# ── Death animations (website fight screen; docs/web.md, "The victory sequence") ──────────────────────────────
# One shared MOVEMENT per body category, not per beast, and no artwork: every beast goes down as its own picture.
# web/static/fight.js bends and lowers the beast's own picture through these frames, at the beast's own size.
# A new category (flying, serpentine ...) is one more row here, measured from a reference sheet by
# scripts/make_death_motion.py, and its beasts in DEATH_CATEGORY. A beast with no category tips over where it stands.
#   ms: how long each frame takes to reach the next (the last one stays).  impact: the frame that hits the ground
#   (dust).  motion: per frame, (how wide the body lies, how high its back stands at 12 points from tail to head),
#   as shares of the standing first frame. Measured from the eight frames of SHOAIB's wolf sheet: the head sinks
#   first, the legs give way, the body drops flat and settles.
DEATH_ANIMATIONS = {
    "quadruped": {"ms": [150, 120, 120, 130, 150, 140, 150, 0], "impact": 4, "motion": [
        (1.00, (1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00)),
        (0.94, (0.98, 1.02, 1.04, 1.03, 1.00, 0.93, 0.88, 0.88, 0.86, 0.81, 0.73, 0.65)),
        (0.99, (0.76, 0.82, 0.89, 0.93, 0.94, 0.92, 0.91, 0.92, 0.91, 0.86, 0.79, 0.72)),
        (1.02, (0.64, 0.72, 0.84, 0.90, 0.89, 0.82, 0.78, 0.79, 0.79, 0.75, 0.64, 0.53)),
        (1.03, (0.54, 0.58, 0.64, 0.69, 0.68, 0.62, 0.58, 0.59, 0.60, 0.57, 0.51, 0.44)),
        (1.04, (0.54, 0.58, 0.65, 0.72, 0.71, 0.65, 0.61, 0.61, 0.60, 0.56, 0.47, 0.39)),
        (1.03, (0.52, 0.56, 0.61, 0.65, 0.65, 0.61, 0.59, 0.60, 0.59, 0.53, 0.44, 0.34)),
        (1.01, (0.55, 0.59, 0.64, 0.67, 0.67, 0.62, 0.60, 0.61, 0.60, 0.55, 0.47, 0.39)),
    ]},
}
DEATH_CATEGORY = {
    "Iron-Hide Boar": "quadruped",
    "Red Fox": "quadruped",
    "Shadow Wolf": "quadruped",
    "Horned Stag": "quadruped",
    "Mountain Tiger": "quadruped",
}


# ── The roar (website fight screen; web/static/fight.js `roaring`, docs/web.md "The beast roar") ─────────────────────
# One shared MOVEMENT per body category, as the deaths above, and no artwork: every beast roars as its own picture,
# moved whole (never bent, stretched or cropped) about its hind feet, with the shared roar wave from its own mouth
# (art/beasts/heads.json). Measured from SHOAIB's quadruped roar video (a boar, scripts/make_roar_fx.py): it dips its
# head and crouches into the ground, rears its head up as the roar bursts out, holds it there trembling with its jaws
# wide, and settles back. The burst fills the scene as the video's does (fight.js `bigRoar`): a starburst and rings
# spreading past the whole beast, speed lines, a white flash, the camera punching in, dust rolling out. Keys, from rest:
#   ms: how long each key takes to reach the next.  burst: the key the roar wave and the dust go out on.
#   hold: the key held trembling.  keys: per key (lean toward the cultivator, as a share of the picture's width;
#   drop, a share of its height, down is +; tilt in degrees, head up is +).
ROAR_ANIMATIONS = {
    "quadruped": {"ms": [450, 150, 1500, 550], "burst": 2, "hold": 2, "keys": [
        (0.000, 0.000, 0.0),        # standing
        (0.030, 0.030, -5.0),       # the dip: head down, weight on the forelegs, gathering itself
        (-0.025, -0.020, 11.0),     # the roar: head flung up, thrown forward at you, jaws wide
        (-0.020, -0.016, 9.5),      # held, trembling, for as long as the video holds it
        (0.000, 0.000, 0.0),        # settled
    ], "swell": 0.08},              # it swells this much bigger as it roars (thrown toward you, as in the video)
}
# The 29 four-legged beasts (SHOAIB's redesign), all roaring with the quadruped movement.
QUADRUPEDS = ("Iron-Hide Boar", "Red Fox", "Shadow Wolf", "Horned Stag", "Mountain Tiger", "Wild Boar", "Grey Wolf",
              "Wild Ox", "Old Black Bear", "Bloodfang Wolf", "Armored Boar Chief", "White-Browed Tiger King",
              "Steel-Horn Bull", "Ironbark Bear", "Frost Wolf", "Wind Leopard", "Flame-Maned Lion",
              "Earth-Splitting Rhino", "Shadow Panther", "Cloud Leopard",
              "Nine-Tailed Fox", "Thunder Rhino", "Fire-Hoof Steed", "Sky Lynx", "Ancient Golden Ape",
              "Ghost-Fire Wolf", "Qiongqi, the Winged Tiger", "Ancient Flame Lion", "White Tiger")
ROAR_CATEGORY = {name: "quadruped" for name in QUADRUPEDS}


def roar_category(name):
    """The beast's roar movement (a ROAR_ANIMATIONS key), or None for the plain roar (it rears back a little)."""
    cat = ROAR_CATEGORY.get(name)
    return cat if cat in ROAR_ANIMATIONS else None


def death_category(name):
    """The beast's death animation category (a DEATH_ANIMATIONS key), or None for the plain fall."""
    cat = DEATH_CATEGORY.get(name)
    return cat if cat in DEATH_ANIMATIONS else None


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
