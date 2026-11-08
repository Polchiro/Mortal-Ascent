"""
Alchemy data — herbs, /gather, beast cores, pills, /craft, alchemist ranks.
Design rules are explained in docs/alchemy.md.
"""

import training

GRADES = ["Mortal", "Yellow", "Mystic", "Earth", "Heaven"]

# ── Herbs ─────────────────────────────────────────────────────────────

# Herb tier found at each realm
HERB_TIER_BY_REALM = {
    "Mortal": "Mortal",
    "Martial Apprentice": "Yellow",
    "Martial Warrior": "Yellow",
    "Martial Expert": "Mystic",
    "Martial Master": "Mystic",
    "Grand Martial Master": "Earth",
    "Martial Grandmaster": "Earth",
    "Martial King": "Heaven",
    "Martial Emperor": "Heaven",
    "Martial Ancestor": "Heaven",
    "Martial Saint": "Heaven",
}
# HERB_TIER_BY_REALM is the herb (and beast core) grade that belongs to a realm: pill strength and
# Beast Cores use it. It does NOT limit what /gather finds: every grade can be found at every realm.

# ── Herb rarity (what /gather and /explore herb patches find) ─────────
# Base weight of each grade. With no luck, the chance of a grade is its weight / the sum of all weights,
# so these are percentages for a Mortal: 80% Mortal, 15% Yellow, 3.5% Mystic, 1.1% Earth, 0.4% Heaven.
# Change these to rebalance; they don't need to add up to 100.
HERB_GRADE_WEIGHTS = {"Mortal": 80.0, "Yellow": 15.0, "Mystic": 3.5, "Earth": 1.1, "Heaven": 0.4}

# Realm luck: a grade's weight is multiplied by luck ** (how many grades above Mortal it is).
# 1.0 = the base table. Higher realms find rare herbs more often, but Mortal herbs never disappear.
REALM_HERB_LUCK = {
    "Mortal": 1.0,
    "Martial Apprentice": 1.1,
    "Martial Warrior": 1.2,
    "Martial Expert": 1.35,
    "Martial Master": 1.5,
    "Grand Martial Master": 1.7,
    "Martial Grandmaster": 1.9,
    "Martial King": 2.15,
    "Martial Emperor": 2.4,
    "Martial Ancestor": 2.7,
    "Martial Saint": 3.0,
}

# How a find of each grade is presented: (rarity word, emoji, line when it appears, line when you gather it)
HERB_RARITY = {
    "Mortal": ("Common", "🌿", "", ""),
    "Yellow": ("Uncommon", "🌾", "", ""),
    "Mystic": ("Rare", "🌟", "🌟 *A faint glimmer: this is a rare **Mystic** grade herb!*",
               "🌟 A rare Mystic grade herb!"),
    "Earth":  ("Very Rare", "💫", "💫 *The ground hums. A very rare **Earth** grade herb grows here!*",
               "💫 A very rare Earth grade herb! Few cultivators ever hold one."),
    "Heaven": ("Legendary", "🌈", "🌈 *Heavenly light pours down. A legendary **Heaven** grade herb!*",
               "🌈 **A LEGENDARY HEAVEN GRADE HERB!** The heavens themselves take note."),
}
# Finds of this grade and above are also announced in the channel
ANNOUNCE_FROM_GRADE = "Earth"


def herb_grade_odds(realm):
    """{grade: chance} of finding each herb grade at this realm (adds up to 1)."""
    luck = REALM_HERB_LUCK.get(realm, 1.0)
    weights = {g: w * luck ** GRADES.index(g) for g, w in HERB_GRADE_WEIGHTS.items()}
    total = sum(weights.values())
    return {g: w / total for g, w in weights.items()}


def is_announced(grade):
    return GRADES.index(grade) >= GRADES.index(ANNOUNCE_FROM_GRADE)


HERB_TYPE_CHANCE = {"qi": 0.30, "healing": 0.20, "purity": 0.35, "breakthrough": 0.15}

# tier → type → (name, description)
HERBS = {
    "Mortal": {
        "qi":           ("Spirit Grass", "Thin green blades that sway with no wind"),
        "healing":      ("Red Berry", "Small red berries with a sweet smell"),
        "purity":       ("Dew Leaf", "Broad leaf always holding a drop of dew"),
        "breakthrough": ("Iron Root", "Dark root, heavy as metal"),
    },
    "Yellow": {
        "qi":           ("Sun Ginseng", "Golden root, warm to the touch"),
        "healing":      ("Blood Flower", "Deep red petals with dark veins"),
        "purity":       ("Silver Moss", "Moss that glows faintly on north-facing stones"),
        "breakthrough": ("Stone Root", "Grey root that grows through solid rock"),
    },
    "Mystic": {
        "qi":           ("Moon Mushroom", "Pale blue cap that opens only at night"),
        "healing":      ("Heart Lotus", "Pink lotus with a heart-shaped center"),
        "purity":       ("Jade Lily", "Green-white lily, cool as jade"),
        "breakthrough": ("Thunder Root", "Black root found where lightning struck"),
    },
    "Earth": {
        "qi":           ("Golden Ginseng", "Root shaped like a sitting person, golden glow"),
        "healing":      ("Phoenix Flower", "Orange petals warm like embers"),
        "purity":       ("Snow Lily", "White lily that blooms only in snow"),
        "breakthrough": ("Mountain Root", "Massive root deep beneath mountain cliffs"),
    },
    "Heaven": {
        "qi":           ("Heaven Lotus", "Nine-leaf lotus floating above the water"),
        "healing":      ("Immortal Peach", "Glowing peach that smells of spring"),
        "purity":       ("Star Dew", "Dewdrops that shine like stars, even by day"),
        "breakthrough": ("Chaos Root", "Root that seems to shift colours as you look"),
    },
}

# tier → list of (name, description) poisonous look-alikes
DECOYS = {
    "Mortal": [("Ghost Grass", "Like Spirit Grass, but the blades are grey at the tips"),
               ("Bitter Nettle", "Red berries hidden under stinging leaves")],
    "Yellow": [("Fool's Ginseng", "Golden root, but cold to the touch"),
               ("Snake Moss", "Glowing moss on south-facing stones")],
    "Mystic": [("Shadow Mushroom", "Pale blue cap, but open in daylight"),
               ("Weeping Lily", "Green-white lily dripping dark sap")],
    "Earth":  [("Grave Ginseng", "Person-shaped root, but grows near bones"),
               ("Fire Thorn", "Orange petals hiding burning thorns")],
    "Heaven": [("Demon Lotus", "Nine-leaf lotus, but blood-red underneath"),
               ("Void Fruit", "Glowing fruit that casts no shadow")],
}

# herb or decoy name → its "look": what you SEE when it grows in front of you (the /gather choice cards).
# Written differently from the description on purpose, so finding the herb means reading, not matching words.
# A decoy's look differs from its herb's look in the same one detail as its description.
LOOKS = {
    # Mortal
    "Spirit Grass":    "Slender green blades swaying in still air",
    "Red Berry":       "A cluster of little red berries, sweetly scented",
    "Dew Leaf":        "A wide leaf cupping one round dewdrop",
    "Iron Root":       "A dull grey-black root, sunk deep and heavy",
    "Ghost Grass":     "Slender green blades swaying, their tips gone grey",
    "Bitter Nettle":   "Little red berries tucked under spiky leaves",
    # Yellow
    "Sun Ginseng":     "A golden root giving off warmth",
    "Blood Flower":    "A deep red bloom with dark lines on its petals",
    "Silver Moss":     "Faintly glowing moss on a stone facing north",
    "Stone Root":      "A grey root splitting a solid rock",
    "Fool's Ginseng":  "A golden root with frost creeping over it",
    "Snake Moss":      "Faintly glowing moss on a stone facing south",
    # Mystic
    "Moon Mushroom":   "A pale blue cap spread wide under the moon",
    "Heart Lotus":     "A pink lotus whose centre forms a heart",
    "Jade Lily":       "A green-white lily with a cool jade sheen",
    "Thunder Root":    "A black root in scorched, split earth",
    "Shadow Mushroom": "A pale blue cap spread wide under the sun",
    "Weeping Lily":    "A green-white lily with dark drops running down",
    # Earth
    "Golden Ginseng":  "A glowing golden root shaped like a seated man",
    "Phoenix Flower":  "Ember-orange petals throwing off sparks",
    "Snow Lily":       "A white lily open in the snow",
    "Mountain Root":   "A huge root clawing out under a cliff",
    "Grave Ginseng":   "A seated-man root among scattered bones",
    "Fire Thorn":      "Ember-orange petals over a nest of thorns",
    # Heaven
    "Heaven Lotus":    "A nine-leaf lotus hovering over still water",
    "Immortal Peach":  "A glowing peach, its shadow on the ground",
    "Star Dew":        "Dewdrops twinkling like stars in daylight",
    "Chaos Root":      "A root shimmering through every colour",
    "Demon Lotus":     "A nine-leaf lotus with a blood-red underside",
    "Void Fruit":      "A glowing fruit with no shadow beneath it",
}

# ── Herb age ──────────────────────────────────────────────────────────
# age: chance, craft score bonus, max pill patterns, extras

HERB_AGES = {
    10:   {"chance": 0.7800, "score_bonus": 0.00, "max_patterns": 5},
    50:   {"chance": 0.1800, "score_bonus": 0.05, "max_patterns": 6},
    100:  {"chance": 0.0360, "score_bonus": 0.10, "max_patterns": 7},
    500:  {"chance": 0.0038, "score_bonus": 0.15, "max_patterns": 8, "mistakes_forgiven": 1},
    1000: {"chance": 0.0002, "score_bonus": 0.25, "max_patterns": 9, "explode_below": 0.30},
}
# A recipe uses the average age tier of its herbs (rounded down).

# ── /gather ───────────────────────────────────────────────────────────

GATHER_CHOICES = 4
GATHER_SECONDS = {"Mortal": 10, "Yellow": 9, "Mystic": 8, "Earth": 7, "Heaven": 6}
DECOY_HP_LOSS = 0.05            # never below 1 HP

OLD_HERB_FROM_AGE = 100         # 100-year+ herbs fight back
OLD_HERB_CHOICES = 6
OLD_HERB_SECONDS_LESS = 3
OLD_HERB_MIN_SECONDS = 4

# (minimum streak, multiplier on 50-year+ chances) — checked top to bottom
STREAK_BONUS = [(50, 3.0), (25, 2.0), (10, 1.5), (0, 1.0)]

# Anti-macro
SPIRIT_CHECK_EVERY = (15, 25)   # gathers between checks (random in range)
SPIRIT_CHECK_FAILS_TO_PAUSE = 3
SPIRIT_CHECK_PAUSE_MINUTES = 60
FLAG_AVG_REACTION_SECONDS = 0.3
FLAG_AVG_OVER_GATHERS = 50
FLAG_CONTINUOUS_HOURS = 12
MERCHANT_BUYS_HERBS = False

HERB_PATCH_HERBS = (1, 3)       # /explore Herb Patch

# ── Beast cores ───────────────────────────────────────────────────────

BEAST_CORE_DROP = {"normal": 0.05, "elite": 0.15, "beast_king": 0.50}
# A core's grade = HERB_TIER_BY_REALM of the beast's realm

# ── Pills ─────────────────────────────────────────────────────────────
# recipe: list of (herb type, count); herbs must be of the pill's grade
# rank: alchemist rank needed; min_age: minimum average herb age

QI_PILLS = {
    "Mortal": {"name": "Ember Dantian Pill",    "rank": 1, "min_age": 10},
    "Yellow": {"name": "Clear Meridian Pill",   "rank": 3, "min_age": 10},
    "Mystic": {"name": "Jade Marrow Pill",      "rank": 5, "min_age": 10},
    "Earth":  {"name": "Thousand Rivers Pill",  "rank": 7, "min_age": 50},
    "Heaven": {"name": "Heaven-Devouring Pill", "rank": 9, "min_age": 50},
}
QI_PILL_RECIPE = [("qi", 2), ("purity", 1)]
# Qi Rate multipliers and duration: training.QI_PILLS, training.QI_PILL_DURATION_HOURS
BELOW_REALM_EFFECT = 0.5        # Qi and Burst pills below your realm's grade: half bonus

QI_BURST_PILLS = {
    # grade: hours of Qi Rate given instantly
    "Mortal": {"hours": 2, "rank": 2, "min_age": 50},
    "Yellow": {"hours": 3, "rank": 4, "min_age": 50},
    "Mystic": {"hours": 4, "rank": 6, "min_age": 50},
    "Earth":  {"hours": 5, "rank": 8, "min_age": 100},
    "Heaven": {"hours": 6, "rank": 9, "min_age": 100},
}
QI_BURST_RECIPE = [("qi", 3), ("purity", 1)]

MENDING_PILLS = {
    # grade: heal % of max HP, injury minutes removed (None = cures)
    "Mortal": {"heal": 0.30, "injury_minutes": 30,   "rank": 1, "min_age": 10},
    "Yellow": {"heal": 0.40, "injury_minutes": 60,   "rank": 3, "min_age": 10},
    "Mystic": {"heal": 0.50, "injury_minutes": 120,  "rank": 5, "min_age": 10},
    "Earth":  {"heal": 0.65, "injury_minutes": 180,  "rank": 7, "min_age": 10},
    "Heaven": {"heal": 0.80, "injury_minutes": None, "rank": 9, "min_age": 10},
}
MENDING_RECIPE = [("healing", 2), ("purity", 1)]

CLEANSING_PILLS = {
    "Mortal": {"toxicity_removed": 1, "rank": 2, "min_age": 10},
    "Yellow": {"toxicity_removed": 1, "rank": 4, "min_age": 10},
    "Mystic": {"toxicity_removed": 2, "rank": 6, "min_age": 10},
    "Earth":  {"toxicity_removed": 2, "rank": 8, "min_age": 50},
    "Heaven": {"toxicity_removed": 3, "rank": 9, "min_age": 50},
}
CLEANSING_RECIPE = [("purity", 3)]
CLEANSING_ADDS_TOXICITY = False

# Breakthrough chance per grade: training.BREAKTHROUGH_PILLS
BREAKTHROUGH_PILLS = {
    "Mortal": {"core": "normal",     "rank": 2, "min_age": 50},
    "Yellow": {"core": "elite",      "rank": 4, "min_age": 100},
    "Mystic": {"core": "elite",      "rank": 6, "min_age": 100},
    "Earth":  {"core": "beast_king", "rank": 8, "min_age": 500},
    "Heaven": {"core": "beast_king", "rank": 9, "min_age": 500},
}
BREAKTHROUGH_RECIPE = [("breakthrough", 2), ("purity", 1)]   # + 1 Beast Core
BREAKTHROUGH_PILLS_PER_ATTEMPT = 1

# ── Toxicity ──────────────────────────────────────────────────────────
# Penalty and decay: training.PILL_TOXICITY_PENALTY, training.TOXICITY_DECAY_HOURS

# ── /craft ────────────────────────────────────────────────────────────

CRAFT_COOLDOWN_MINUTES = 0      # herbs are the limit

DIFFICULTY = {
    # grade: difficulty settings
    "Mortal": {"name": "Normal",     "stages": [1, 4],       "rounds": 3, "seconds": 6.0, "zone": 30, "misleading": 0.00, "wild_herbs": False},
    "Yellow": {"name": "Hard",       "stages": [1, 2, 4],    "rounds": 4, "seconds": 5.0, "zone": 25, "misleading": 0.00, "wild_herbs": False},
    "Mystic": {"name": "Very Hard",  "stages": [1, 2, 3, 4], "rounds": 5, "seconds": 4.0, "zone": 20, "misleading": 0.15, "wild_herbs": False},
    "Earth":  {"name": "Extreme",    "stages": [1, 2, 3, 4], "rounds": 6, "seconds": 3.5, "zone": 15, "misleading": 0.25, "wild_herbs": True},
    "Heaven": {"name": "Super Hard", "stages": [1, 2, 3, 4], "rounds": 7, "seconds": 3.0, "zone": 12, "misleading": 0.35, "wild_herbs": True},
}
BREAKTHROUGH_DIFFICULTY_STEP = 1    # breakthrough pills use the next grade's difficulty (max Heaven)
SEAL_CORE_STAGE = 5
SEAL_CORE_MOVES = 3

# Alchemist rank relief, per rank above the pill's required rank (max 3 counted)
RANK_RELIEF = {
    "zone_bonus": 0.10,         # +10% safe zone width per rank
    "seconds_bonus": 0.5,
    "hints_per_rank": 1,        # Stage 2 hints
    "forgive_from_ranks": 2,    # 1 mistake forgiven at 2+ ranks above
    "max_ranks_counted": 3,
}

# Batch crafting: refine several pills of one recipe in a single minigame (docs/alchemy.md, "Batch crafting").
# Every pill in the batch gets the same patterns; an explosion loses every herb in the cauldron.
BATCH_BY_RANK = {1: 1, 2: 2, 3: 2, 4: 3, 5: 3, 6: 4, 7: 4, 8: 5, 9: 5}   # most pills per craft at each rank
# Each pill beyond the first makes the minigame harder (applied after rank relief and artifacts):
BATCH_PENALTY = {
    "seconds": 0.5,             # −0.5s per decision per extra pill...
    "min_seconds": 2.5,         # ...never below this
    "zone": 0.15,               # heat safe zone −15% of its width per extra pill...
    "min_zone": 6,              # ...never narrower than 6°
    "balance_tolerance": 1,     # Yin/Yang "perfect" window (50 ± 5) shrinks by 1 per extra pill...
    "min_balance_tolerance": 2,
    "seal_pass": 2,             # Seal the Core passes at imbalance ≤ 12, 2 less per extra pill...
    "min_seal_pass": 6,
}


def batch_cap(rank):
    return BATCH_BY_RANK.get(rank, max(BATCH_BY_RANK.values()))


# (minimum score, patterns) — checked top to bottom; below the last = explosion
SCORE_TO_PATTERNS = [
    (0.95, 9), (0.90, 8), (0.85, 7), (0.77, 6), (0.70, 5),
    (0.62, 4), (0.55, 3), (0.47, 2), (0.40, 1),
]
EXPLODE_BELOW = 0.40
NINE_PATTERN_NEEDS_TRIBULATION = True
TRIBULATION_FAIL_PATTERNS = 8

def pattern_effect(patterns):
    """Effect multiplier: 1 pattern ×0.85 … 9 patterns ×1.25."""
    return 0.80 + 0.05 * patterns

# (minimum patterns, toxicity added)
PATTERN_TOXICITY = [(8, 0), (4, 1), (1, 2)]

# ── Alchemist rank ────────────────────────────────────────────────────

ALCHEMIST_RANK_EXP = {   # total EXP needed to reach each rank
    1: 0, 2: 100, 3: 400, 4: 1200, 5: 3200, 6: 8200, 7: 20200, 8: 50200, 9: 120200,
}
CRAFT_BASE_EXP = {"Mortal": 10, "Yellow": 25, "Mystic": 60, "Earth": 150, "Heaven": 400}
BREAKTHROUGH_EXP_MULTIPLIER = 2
EXPLOSION_EXP = 0.20
# (minimum ranks above the pill's required rank, EXP multiplier)
RANK_EXP_PENALTY = [(3, 0.1), (1, 0.5), (0, 1.0)]

def craft_exp(grade, patterns, breakthrough=False, ranks_above=0):
    base = CRAFT_BASE_EXP[grade]
    if patterns == 0:                       # explosion
        exp = base * EXPLOSION_EXP
    else:
        exp = base * (0.5 + 0.1 * patterns)
    if breakthrough:
        exp *= BREAKTHROUGH_EXP_MULTIPLIER
    for min_above, mult in RANK_EXP_PENALTY:
        if ranks_above >= min_above:
            return exp * mult
    return exp
