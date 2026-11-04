"""
Training data — Internal Qi. Design rules are explained in docs/training.md.
"""

# ── Internal Qi Rate (Qi per hour) ────────────────────────────────────

BASE_QI_RATE = {
    "Mortal": 2.5,
    "Martial Apprentice": 5,
    "Martial Warrior": 10,
    "Martial Expert": 20,
    "Martial Master": 40,
    "Grand Martial Master": 80,
    "Martial Grandmaster": 160,
    "Martial King": 320,
    "Martial Emperor": 640,
    "Martial Ancestor": 1280,
    "Martial Saint": 2560,
}

TALENT_QI_BONUS = {
    "Ordinary": 0.00,
    "Gifted": 0.10,
    "Genius": 0.20,
    "Prodigy": 0.35,
    "Heavenly": 0.50,
    "Saint": 0.75,
    "Divine": 1.00,
}

# Heavenly Blessing Qi bonus comes from economy.BLESSING_TIERS[tier]["qi_rate"]
# Technique bonus comes from technique.TRAINING_EXP_BONUS

# ── /train ────────────────────────────────────────────────────────────

TRAIN_REWARD_HOURS = 4          # reward = Final Qi Rate × this × score
TRAIN_COOLDOWN_MINUTES = 60

# ── Passive Qi & /meditate ────────────────────────────────────────────

PASSIVE_MAX_STORED_HOURS = 12

# ── Seclusion ─────────────────────────────────────────────────────────

SECLUSION_MIN_HOURS = 8
SECLUSION_MAX_HOURS = 24
SECLUSION_QI_MULTIPLIER = 2.0

# ── Blessed Lands ─────────────────────────────────────────────────────

BLESSED_LANDS = {
    "spirit_spring": {"qi_multiplier": 2.0, "mastery_multiplier": 1.0},
    "lotus_grove":   {"qi_multiplier": 2.0, "mastery_multiplier": 2.0},
    "dragon_vein":   {"qi_multiplier": 3.0, "mastery_multiplier": 3.0},
}
BLESSED_LAND_DURATION_MINUTES = (20, 30)
BLESSED_LAND_COOLDOWN_MULTIPLIER = 0.5

# ── Pills ─────────────────────────────────────────────────────────────

QI_PILLS = {
    # grade: Qi Rate multiplier
    "Mortal": 1.2,
    "Yellow": 1.4,
    "Mystic": 1.7,
    "Earth":  2.0,
    "Heaven": 2.5,
}
QI_PILL_DURATION_HOURS = 4

BREAKTHROUGH_PILLS = {
    # grade: added success chance
    "Yellow": 0.10,
    "Mystic": 0.20,
    "Earth":  0.30,
    "Heaven": 0.40,
}

# (minimum toxicity, pill effect multiplier) — checked top to bottom
PILL_TOXICITY_PENALTY = [
    (6, 0.25),
    (4, 0.50),
    (0, 1.00),
]
TOXICITY_DECAY_HOURS = 24

# ── Qi needed per layer (Early phase) ─────────────────────────────────

QI_PER_LAYER = {
    "Mortal": 10,
    "Martial Apprentice": 20,
    "Martial Warrior": 80,
    "Martial Expert": 320,
    "Martial Master": 1120,
    "Grand Martial Master": 3520,
    "Martial Grandmaster": 11520,
    "Martial King": 35840,
    "Martial Emperor": 110080,
    "Martial Ancestor": 327680,
    "Martial Saint": 972800,
}

PHASE_QI_MULTIPLIER = {
    "Early Phase": 1.0,
    "Middle Phase": 1.2,
    "Late Phase": 1.5,
    "Peak Phase": 2.0,
}

# ── Breakthroughs ─────────────────────────────────────────────────────

PHASE_BOTTLENECK_SUCCESS = 0.90
REALM_BREAKTHROUGH_SUCCESS = 0.70
BREAKTHROUGH_FAIL_QI_LOSS = 0.20
INJURY_HOURS = 6

REALM_REQUIREMENTS = {
    "Martial Master": {"technique_mastery": ("any", "Entering the Hall")},
    "Martial King":   {"technique_mastery": ("Mystic", "Pure Flame"), "beast_king_kill": "own_realm"},
    "Martial Saint":  {"technique_mastery": ("Earth", "Divine Transformation"), "beast_king_kill": "Martial Ancestor"},
}
