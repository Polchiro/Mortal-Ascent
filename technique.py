TECHNIQUE_TYPES = ["attack", "defense"]

GRADES = {
    # grade: minimum realm to learn
    "Mortal": "Mortal",
    "Yellow": "Martial Apprentice",
    "Mystic": "Martial Expert",
    "Earth":  "Grand Martial Master",
    "Heaven": "Martial King",
}

MASTERY_STAGES = [
    {"name": "Glimpsing the Gate",    "multiplier": 1.00, "exp_to_reach": 0},
    {"name": "Entering the Hall",     "multiplier": 1.10, "exp_to_reach": 500},
    {"name": "Pure Flame",            "multiplier": 1.20, "exp_to_reach": 2000},
    {"name": "Divine Transformation", "multiplier": 1.35, "exp_to_reach": 6000},
    {"name": "Return to Simplicity",  "multiplier": 1.50, "exp_to_reach": 15000},
]

# Mastery EXP needed is multiplied by this per grade
GRADE_EXP_MULTIPLIER = {
    "Mortal": 1.0,
    "Yellow": 2.0,
    "Mystic": 3.0,
    "Earth":  5.0,
    "Heaven": 8.0,
}

ATTACK_TECHNIQUE = {
    # grade: (skill damage multiplier, passive attack %)
    "Mortal": (1.20, 0.02),
    "Yellow": (1.35, 0.04),
    "Mystic": (1.50, 0.06),
    "Earth":  (1.70, 0.09),
    "Heaven": (2.00, 0.12),
}

DEFENSE_TECHNIQUE = {
    # grade: (damage blocked when used, passive defense %)
    "Mortal": (0.20, 0.02),
    "Yellow": (0.25, 0.04),
    "Mystic": (0.30, 0.06),
    "Earth":  (0.40, 0.09),
    "Heaven": (0.50, 0.12),
}

MAX_DAMAGE_BLOCKED = 0.80

# Bonus to realm training EXP; only the best equipped technique counts
TRAINING_EXP_BONUS = {
    "Mortal": 0.05,
    "Yellow": 0.10,
    "Mystic": 0.15,
    "Earth":  0.25,
    "Heaven": 0.40,
}

# ── Mastery training ──────────────────────────────────────────────────

# /practice — uses the shared challenge pool (config/challenges.py)
# Difficulty tier = mastery stage index + 1
PRACTICE_BASE_EXP = 40
PRACTICE_COOLDOWN_MINUTES = 30

# /spar — training fight vs master NPC
SPAR_EXP_PER_TIMED_USE = 30
SPAR_WIN_EXP = 100
SPAR_COOLDOWN_MINUTES = 120

# Mastery trial — master strength to reach each stage (index = target stage)
TRIAL_MASTER_STRENGTH = [None, 1.2, 1.4, 1.7, 2.0]
TRIAL_FAIL_COOLDOWN_HOURS = 24

# Real fights (beasts, PvP)
COMBAT_EXP_PER_USE = 20

# Technique cooldowns in every fight (spar, trials, explore, hunts, future PvP).
# After a technique is used it rests for this many of your turns; basic
# Strike / Guard / Break are always available. Stronger grades rest longer.
TECHNIQUE_COOLDOWN_TURNS = {
    "Mortal": 1,
    "Yellow": 1,
    "Mystic": 2,
    "Earth":  2,
    "Heaven": 3,
}
HEAVY_EXTRA_COOLDOWN = 1   # Heavy techniques rest one turn longer

# Daily diminishing returns: (sessions at this rate, EXP rate)
PRACTICE_DAILY_RATES = [(5, 1.0), (5, 0.5), (None, 0.1)]
SPAR_DAILY_RATES = [(3, 1.0), (None, 0.5)]

STARTING_TECHNIQUES = [
    {"type": "attack",  "grade": "Mortal"},
    {"type": "defense", "grade": "Mortal"},
]

# ── Technique list (see technique.md) ─────────────────────────────────
# effect: None, or (kind, value)
#   combo:       (hits, damage per hit)
#   pierce:      share of defender's Defense ignored
#   stagger:     next block weakened by this share; 1.0 = can't Guard next turn
#   heavy:       damage multiplier (rests HEAVY_EXTRA_COOLDOWN turn longer)
#   counter:     share of blocked damage reflected
#   recover:     share of max HP healed on block
#   unbreakable: None (Break moves deal half damage)
#   evade:       chance to take no damage


def _t(name, type_, grade, school, effect=None):
    return {"name": name, "type": type_, "grade": grade, "school": school, "effect": effect}


TECHNIQUES = {
    # Mortal
    "iron_fist":             _t("Iron Fist", "attack", "Mortal", "Fist"),
    "twin_palm_strike":      _t("Twin Palm Strike", "attack", "Mortal", "Palm", ("combo", (2, 0.60))),
    "crescent_sweep":        _t("Crescent Sweep", "attack", "Mortal", "Leg", ("stagger", 0.15)),
    "horse_stance_guard":    _t("Horse Stance Guard", "defense", "Mortal", "Body", ("recover", 0.02)),
    "parrying_arm":          _t("Parrying Arm", "defense", "Mortal", "Body", ("counter", 0.10)),
    "calm_breath_stance":    _t("Calm Breath Stance", "defense", "Mortal", "Body", ("recover", 0.03)),
    # Yellow
    "fierce_tiger_claw":     _t("Fierce Tiger Claw", "attack", "Yellow", "Fist", ("stagger", 0.25)),
    "swift_swallow_kick":    _t("Swift Swallow Kick", "attack", "Yellow", "Leg", ("pierce", 0.15)),
    "raging_bull_fist":      _t("Raging Bull Fist", "attack", "Yellow", "Fist", ("heavy", 1.2)),
    "iron_cloth_body":       _t("Iron Cloth Body", "defense", "Yellow", "Body", ("unbreakable", None)),
    "flowing_stream_palm":   _t("Flowing Stream Palm", "defense", "Yellow", "Palm", ("recover", 0.05)),
    "crane_wing_deflection": _t("Crane Wing Deflection", "defense", "Yellow", "Palm", ("counter", 0.15)),
    # Mystic
    "rolling_thunder_palm":  _t("Rolling Thunder Palm", "attack", "Mystic", "Palm", ("stagger", 0.50)),
    "viper_fang_finger":     _t("Viper Fang Finger", "attack", "Mystic", "Finger", ("pierce", 0.25)),
    "autumn_wind_kick":      _t("Autumn Wind Kick", "attack", "Mystic", "Leg", ("combo", (3, 0.40))),
    "moon_mirror_palm":      _t("Moon Mirror Palm", "defense", "Mystic", "Palm", ("counter", 0.25)),
    "drifting_mist_steps":   _t("Drifting Mist Steps", "defense", "Mystic", "Body", ("evade", 0.25)),
    "rooted_mountain_stance": _t("Rooted Mountain Stance", "defense", "Mystic", "Body", ("unbreakable", None)),
    # Earth
    "mountain_shattering_fist":  _t("Mountain-Shattering Fist", "attack", "Earth", "Fist", ("heavy", 1.3)),
    "thousand_shadow_palm":      _t("Thousand Shadow Palm", "attack", "Earth", "Palm", ("combo", (3, 0.45))),
    "river_splitting_finger":    _t("River-Splitting Finger", "attack", "Earth", "Finger", ("pierce", 0.30)),
    "golden_bell_cover":         _t("Golden Bell Cover", "defense", "Earth", "Body", ("unbreakable", None)),
    "ancient_turtle_shell_art":  _t("Ancient Turtle Shell Art", "defense", "Earth", "Body", ("recover", 0.08)),
    "thousand_hands_deflection": _t("Thousand Hands Deflection", "defense", "Earth", "Palm", ("counter", 0.30)),
    # Heaven
    "heaven_rending_palm":         _t("Heaven-Rending Palm", "attack", "Heaven", "Palm", ("pierce", 0.40)),
    "nine_dragons_ascending_fist": _t("Nine Dragons Ascending Fist", "attack", "Heaven", "Fist", ("stagger", 1.0)),
    "meteor_falling_kick":         _t("Meteor-Falling Kick", "attack", "Heaven", "Leg", ("heavy", 1.5)),
    "void_mirror_stance":          _t("Void Mirror Stance", "defense", "Heaven", "Palm", ("counter", 0.40)),
    "immortal_lotus_body":         _t("Immortal Lotus Body", "defense", "Heaven", "Body", ("recover", 0.12)),
    "cloud_walking_shadow":        _t("Cloud-Walking Shadow", "defense", "Heaven", "Body", ("evade", 0.40)),
}
