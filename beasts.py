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
        ("Wind-Feather Falcon", "normal", "swift"),
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
    "Grandmaster": [
        ("Stone-Shell Tortoise", "normal", "armored"),
        ("Lightning Weasel", "normal", "swift"),
        ("Bone Vulture", "normal", "hunter"),
        ("Storm Eagle", "elite", "swift"),
        ("Jade-Scaled Crocodile", "elite", "armored"),
        ("Black Water Serpent", "beast_king", "brute"),
    ],
    "Martial Lord": [
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
    "Wind-Feather Falcon": ("Shadow", "bird"),
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
    # The flying beasts' screech, from SHOAIB's flying roar video (a crane): it rears up off the ground with its wings
    # spread and head thrown back, gathers glowing Qi into its throat, then snaps its head forward, beak wide, and
    # blasts a cone of sound rings at you along a beam (fight.js `screech`), holds it with feathers scattering, and
    # settles. style: which burst it plays; pivot: where its feet are, as a share of its picture's width.
    "flying": {"ms": [380, 620, 140, 1400, 520], "burst": 3, "hold": 3, "style": "screech", "pivot": 0.6, "keys": [
        (0.000, 0.000, 0.0),        # standing
        (-0.020, -0.060, 12.0),     # reared up off the ground, head thrown back, wings spread
        (-0.024, -0.070, 13.0),     # gathering, Qi swirling into its throat
        (0.040, -0.045, -4.0),      # the screech: head snapped forward at you, beak wide
        (0.034, -0.045, -3.0),      # held, trembling, blasting
        (0.000, 0.000, 0.0),        # settled
    ], "swell": 0.06},
    # The serpents' hiss, from SHOAIB's serpent roar video (a viper): it coils back, head low, then rears its head high
    # while Qi of its element swirls round its neck and a circle of runes with spinning golden rings flares up behind
    # it; then it lunges, jaws wide, and breathes a roaring stream of its element at you (fight.js `hiss`), mist rolling
    # out along the ground, holds it, and settles.
    "serpent": {"ms": [420, 640, 140, 1450, 520], "burst": 3, "hold": 3, "style": "hiss", "pivot": 0.55, "keys": [
        (0.000, 0.000, 0.0),        # standing
        (-0.030, 0.020, -4.0),      # coiled back, head low, gathering itself
        (-0.030, -0.020, 9.0),      # reared high, Qi swirling round its neck
        (0.045, 0.000, -3.0),       # the hiss: lunged at you, jaws wide, breathing its element
        (0.040, 0.000, -2.0),       # held, trembling, breathing
        (0.000, 0.000, 0.0),        # settled
    ], "swell": 0.07},
    # The amphibians' roar, from SHOAIB's amphibian roar video (the Thornback Lizard): it crouches low while Qi of its
    # element swirls round it, then throws its head up and roars, a golden starburst flaring at its jaws, its whole
    # body erupting in a nova of its element and a shockwave ring racing out along the ground with dust (fight.js
    # `quake`), holds, trembling, and settles.
    "amphibian": {"ms": [520, 560, 150, 1450, 520], "burst": 3, "hold": 3, "style": "quake", "pivot": 0.7, "keys": [
        (0.000, 0.000, 0.0),        # standing
        (0.000, 0.030, -2.0),       # crouched low, gathering itself
        (-0.015, 0.035, -4.0),      # crouched lower, head down, Qi swirling round it
        (0.025, -0.010, 10.0),      # the roar: head thrown up, body erupting
        (0.020, -0.008, 9.0),       # held, trembling
        (0.000, 0.000, 0.0),        # settled
    ], "swell": 0.06},
    # The dragons' roar, from SHOAIB's dragon roar video (the Flood Dragon): it draws its head back while ribbons of
    # Qi of its element coil up round its body, then rears and roars a blazing blast of its element at you, lightning
    # streaks fanning out round it; its whole body bursts into a sphere of light with spikes and rings, mist pools
    # at its base (fight.js `coil`, `storm`), holds, and settles.
    "dragon": {"ms": [460, 620, 150, 1500, 560], "burst": 3, "hold": 3, "style": "storm", "pivot": 0.6, "keys": [
        (0.000, 0.000, 0.0),        # standing
        (-0.020, 0.010, -3.0),      # head drawn back
        (-0.030, -0.015, 6.0),      # reared high, Qi coiling round it
        (0.040, -0.010, -2.0),      # the roar: thrust at you, jaws wide, blast
        (0.035, -0.008, -1.0),      # held, trembling
        (0.000, 0.000, 0.0),        # settled
    ], "swell": 0.06},
    # The primates' roar, from SHOAIB's primate roar video (the Silver Monkey): it crouches, rises onto its hind legs and
    # pounds its chest twice while a whirlwind of its element spirals round it, then roars, a sphere of its element
    # bursting round its body with streaks shooting out every way and shards flying (fight.js `vortex`, `beat`,
    # `pound`), holds, and settles.
    "primate": {"ms": [380, 420, 150, 150, 150, 160, 1450, 520], "burst": 6, "hold": 6, "style": "pound", "pivot": 0.8,
                "keys": [
        (0.000, 0.000, 0.0),        # standing
        (0.000, 0.030, -2.0),       # crouched
        (-0.015, -0.035, 5.0),      # risen on its hind legs, whirlwind spiralling round it
        (-0.010, -0.015, 2.0),      # first chest blow
        (-0.015, -0.035, 5.0),      # risen
        (-0.010, -0.015, 2.0),      # second chest blow
        (0.030, -0.025, -3.0),      # the roar: thrust at you, the sphere bursting
        (0.025, -0.022, -2.0),      # held, trembling
        (0.000, 0.000, 0.0),        # settled
    ], "swell": 0.07},
    # The insects' threat display, from SHOAIB's insect roar video (the Venom Scorpion): it crouches, then rears up with
    # its tail and pincers raised while venom drips and poison smoke gathers round it; then it hisses, jaws wide, and
    # erupts: a ring of purple and green venom flames round its body, a sphere of poison bursting out, and a cloud of
    # poison smoke left hanging over the ground (fight.js `venom`), and settles.
    "insect": {"ms": [380, 600, 150, 1450, 520], "burst": 3, "hold": 3, "style": "venom", "pivot": 0.7, "keys": [
        (0.000, 0.000, 0.0),        # standing
        (0.000, 0.025, -2.0),       # crouched, gathering
        (-0.015, -0.030, 7.0),      # reared up, tail and pincers raised, venom gathering
        (0.025, -0.010, -2.0),      # the hiss: thrust at you, jaws wide, the venom erupts
        (0.020, -0.008, -1.0),      # held, trembling
        (0.000, 0.000, 0.0),        # settled
    ], "swell": 0.06},
    # The crocodiles' roar, from SHOAIB's crocodile roar video (the Jade-Scaled Crocodile): it presses low to the ground,
    # then throws its head up high, jaws gaping, and bellows: rings of sound pulse out of its jaws, a burst of its
    # element flares round its head with spikes of light, and dust blasts up off the ground (fight.js `bellow`), and it
    # sinks back down.
    "crocodile": {"ms": [420, 520, 150, 1450, 560], "burst": 3, "hold": 3, "style": "bellow", "pivot": 0.82, "keys": [
        (0.000, 0.000, 0.0),        # lying
        (0.000, 0.020, -3.0),       # pressed low, gathering
        (-0.010, -0.005, 6.0),      # head lifting
        (0.015, -0.020, 16.0),      # the bellow: head thrown up high, jaws gaping
        (0.012, -0.018, 14.0),      # held, trembling
        (0.000, 0.000, 0.0),        # sinks back down
    ], "swell": 0.05},
    # The tortoises' roar, from SHOAIB's tortoise roar video (the Stone-Shell Tortoise): it braces, its shell's runes
    # light up and crackle with energy of its element, then it lifts its head and roars: a cone of sound rings blasts
    # out of its jaws at you, a great dome of its element swells up round its whole body like a shield, and mist rolls
    # out along the ground (fight.js `charged`, `shell`), and it settles.
    "tortoise": {"ms": [420, 700, 150, 1550, 560], "burst": 3, "hold": 3, "style": "shell", "pivot": 0.75, "keys": [
        (0.000, 0.000, 0.0),        # standing
        (0.000, 0.015, -1.0),       # braced, its shell's runes lighting up
        (-0.010, 0.005, 4.0),       # head drawn up, the shell crackling
        (0.015, -0.008, 7.0),       # the roar: head up and out, jaws wide, the dome swelling
        (0.012, -0.006, 6.0),       # held
        (0.000, 0.000, 0.0),        # settled
    ], "swell": 0.04},
}
# The 29 four-legged beasts (SHOAIB's redesign), all roaring with the quadruped movement.
QUADRUPEDS = ("Iron-Hide Boar", "Red Fox", "Shadow Wolf", "Horned Stag", "Mountain Tiger", "Wild Boar", "Grey Wolf",
              "Wild Ox", "Old Black Bear", "Bloodfang Wolf", "Armored Boar Chief", "White-Browed Tiger King",
              "Steel-Horn Bull", "Ironbark Bear", "Frost Wolf", "Wind Leopard", "Flame-Maned Lion",
              "Earth-Splitting Rhino", "Shadow Panther", "Cloud Leopard",
              "Nine-Tailed Fox", "Thunder Rhino", "Fire-Hoof Steed", "Sky Lynx",
              "Ghost-Fire Wolf", "Qiongqi, the Winged Tiger", "Ancient Flame Lion", "White Tiger")
# The 10 flying beasts (SHOAIB's redesign of the birds), all screeching with the flying movement.
FLYING = ("Spear-Beak Crane", "Thunder Hawk", "Bone Vulture", "Storm Eagle", "Iron-Feather Crow", "Crimson Fire Hawk",
          "Bifang Fire Crane", "Vermilion Bird", "Kun-Peng, Fish of the Northern Sea", "Wind-Feather Falcon")
# The 5 serpents (SHOAIB's redesign), all hissing with the serpent movement.
SERPENTS = ("Field Viper", "Rock Python", "Frost Python", "Black Water Serpent", "Void Serpent")
# The 3 amphibians (SHOAIB's redesign), all roaring with the amphibian movement.
AMPHIBIANS = ("Thornback Lizard", "Poison Toad", "Ember Lizard")
# The 2 dragons (SHOAIB's redesign), both roaring with the dragon movement.
DRAGONS = ("Flood Dragon (Jiao)", "Azure Dragon")
# The 4 primates (SHOAIB's redesign; the Ancient Golden Ape moved here from the four-legged beasts), all roaring with
# the primate movement.
PRIMATES = ("Silver Monkey", "Golden-Eyed Ape King", "Ancient Golden Ape", "Shanxiao Mountain Spirit")
# The 3 insects and arthropods (SHOAIB's redesign), all with the insect threat display.
INSECTS = ("Venom Scorpion", "Golden Silk Spider", "Thousand-Year Centipede")
# The 2 crocodiles (SHOAIB's redesign), both bellowing with the crocodile movement.
CROCODILES = ("Jade-Scaled Crocodile", "Abyss Crocodile")
# The 3 tortoises (SHOAIB's redesign), all roaring with the tortoise movement.
TORTOISES = ("Stone-Shell Tortoise", "Black Tortoise (Xuanwu)", "Primordial Dragon Turtle")
ROAR_CATEGORY = {**{name: "quadruped" for name in QUADRUPEDS}, **{name: "flying" for name in FLYING},
                 **{name: "serpent" for name in SERPENTS}, **{name: "amphibian" for name in AMPHIBIANS},
                 **{name: "dragon" for name in DRAGONS}, **{name: "primate" for name in PRIMATES},
                 **{name: "insect" for name in INSECTS}, **{name: "crocodile" for name in CROCODILES},
                 **{name: "tortoise" for name in TORTOISES}}


# Beasts that attack with claws: their M1 leaves three red claw marks (art/fx/claw_marks.webp); every other beast
# (hooves, horns, tusks, beaks, fangs, a weapon) cuts a single bright slash (art/fx/beast_slash.webp). SHOAIB's pictures.
CLAWED = frozenset((
    "Mountain Tiger", "White-Browed Tiger King", "Wind Leopard", "Flame-Maned Lion", "Shadow Panther", "Cloud Leopard",
    "Sky Lynx", "Pixiu", "Taotie, the Devourer", "Qiongqi, the Winged Tiger", "Ancient Flame Lion", "White Tiger",
    "Stray Dog Pack", "Grey Wolf", "Red Fox", "Shadow Wolf", "Bloodfang Wolf", "Frost Wolf", "Lightning Weasel",
    "Nine-Tailed Fox", "Tiangou, the Heavenly Hound", "Ghost-Fire Wolf",
    "Old Black Bear", "Ironbark Bear", "Silver Monkey", "Ancient Golden Ape",
    "Wind-Feather Falcon", "Thunder Hawk", "Bone Vulture", "Storm Eagle", "Iron-Feather Crow", "Crimson Fire Hawk",
    "Vermilion Bird", "Kun-Peng, Fish of the Northern Sea",
    "Thornback Lizard", "Ember Lizard", "Flood Dragon (Jiao)", "Azure Dragon",
))


def has_claws(name):
    return name in CLAWED


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
