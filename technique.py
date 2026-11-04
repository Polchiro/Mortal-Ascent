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

# Daily diminishing returns: (sessions at this rate, EXP rate)
PRACTICE_DAILY_RATES = [(5, 1.0), (5, 0.5), (None, 0.1)]
SPAR_DAILY_RATES = [(3, 1.0), (None, 0.5)]

STARTING_TECHNIQUES = [
    {"type": "attack",  "grade": "Mortal"},
    {"type": "defense", "grade": "Mortal"},
]
