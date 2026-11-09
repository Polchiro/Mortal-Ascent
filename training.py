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

# Passive Qi gathers at the Final Qi Rate with no storage limit; the bot banks it every minute
# (bot/passive.py), so there is nothing to collect.

# ── Blessed Lands ─────────────────────────────────────────────────────

BLESSED_LANDS = {
    "spirit_spring": {"qi_multiplier": 2.0, "mastery_multiplier": 1.0},
    "lotus_grove":   {"qi_multiplier": 2.0, "mastery_multiplier": 2.0},
    "dragon_vein":   {"qi_multiplier": 3.0, "mastery_multiplier": 3.0},
}
BLESSED_LAND_DURATION_MINUTES = (20, 30)
BLESSED_LAND_COOLDOWN_MULTIPLIER = 0.5

# ── Pills ─────────────────────────────────────────────────────────────

# Pill names, recipes and crafting live in alchemy.py (docs/alchemy.md)
QI_PILLS = {
    # grade: Qi Rate multiplier
    "Mortal": 1.3,
    "Yellow": 1.5,
    "Mystic": 1.8,
    "Earth":  2.2,
    "Heaven": 2.8,
}
QI_PILL_DURATION_HOURS = 2

BREAKTHROUGH_PILLS = {
    # grade: added success chance (hard to craft — see alchemy.py)
    "Mortal": 0.05,
    "Yellow": 0.07,
    "Mystic": 0.10,
    "Earth":  0.12,
    "Heaven": 0.15,
}

# (minimum toxicity, pill effect multiplier) — checked top to bottom
PILL_TOXICITY_PENALTY = [
    (6, 0.25),
    (4, 0.50),
    (0, 1.00),
]
TOXICITY_DECAY_HOURS = 8

# ── Qi needed per layer (Early phase) ─────────────────────────────────

QI_PER_LAYER = {
    "Mortal": 8,
    "Martial Apprentice": 16,
    "Martial Warrior": 64,
    "Martial Expert": 260,
    "Martial Master": 900,
    "Grand Martial Master": 2850,
    "Martial Grandmaster": 9300,
    "Martial King": 29000,
    "Martial Emperor": 89000,
    "Martial Ancestor": 265000,
    "Martial Saint": 790000,
}

PHASE_QI_MULTIPLIER = {
    "Early Phase": 1.0,
    "Middle Phase": 1.2,
    "Late Phase": 1.5,
    "Peak Phase": 2.0,
}

# ── Breakthroughs ─────────────────────────────────────────────────────

# Gates get harder the higher you climb.
# Phase bottleneck (3rd→4th, 6th→7th, 9th→10th layer), by the realm you are in:
PHASE_BOTTLENECK_SUCCESS = {
    "Martial Apprentice":   0.8,
    "Martial Warrior":      0.7,
    "Martial Expert":       0.6,
    "Martial Master":       0.5,
    "Grand Martial Master": 0.42,
    "Martial Grandmaster":  0.35,
    "Martial King":         0.28,
    "Martial Emperor":      0.22,
    "Martial Ancestor":     0.17,
    "Martial Saint":        0.12,
}
# Realm gate, by the realm you break INTO (Mortal → Martial Apprentice always works):
REALM_BREAKTHROUGH_SUCCESS = {
    "Martial Apprentice":   1.0,
    "Martial Warrior":      0.5,
    "Martial Expert":       0.35,
    "Martial Master":       0.25,
    "Grand Martial Master": 0.18,
    "Martial Grandmaster":  0.12,
    "Martial King":         0.08,
    "Martial Emperor":      0.05,
    "Martial Ancestor":     0.03,
    "Martial Saint":        0.015,
}
# Breakthrough pills and artifacts add to a realm gate's chance, but never past this.
BREAKTHROUGH_CHANCE_CAP = 0.95
BREAKTHROUGH_FAIL_QI_LOSS = 0.20
INJURY_HOURS = 6

REALM_REQUIREMENTS = {
    "Martial Master": {"technique_mastery": ("any", "Entering the Hall")},
    "Martial King":   {"technique_mastery": ("Mystic", "Pure Flame"), "beast_king_kill": "own_realm"},
    "Martial Saint":  {"technique_mastery": ("Earth", "Divine Transformation"), "beast_king_kill": "Martial Ancestor"},
}
