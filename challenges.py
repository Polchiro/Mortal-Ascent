COUNTERS = {
    # stance: correct counter
    "strike": "guard",
    "guard": "break",
    "break": "strike",
}

# ── Difficulty tiers ──────────────────────────────────────────────────

# /practice: tier = mastery stage index + 1
# /train: tier by realm
REALM_TIER = {
    "Mortal": 1,
    "Martial Apprentice": 1,
    "Martial Warrior": 1,
    "Martial Expert": 2,
    "Martial Master": 2,
    "Grand Martial Master": 3,
    "Martial Grandmaster": 3,
    "Martial King": 4,
    "Martial Emperor": 4,
    "Martial Ancestor": 5,
    "Martial Saint": 5,
}

CHALLENGES_BY_TIER = {
    1: ["read_the_master", "endless_waves"],
    2: ["read_the_master", "endless_waves", "ambush", "find_the_weakness"],
    3: ["read_the_master", "endless_waves", "ambush", "find_the_weakness",
        "rhythm_of_the_blade", "sword_formation"],
    4: ["read_the_master", "endless_waves", "ambush", "find_the_weakness",
        "rhythm_of_the_blade", "sword_formation"],
    5: ["read_the_master", "endless_waves", "ambush", "find_the_weakness",
        "rhythm_of_the_blade", "sword_formation"],
}

# (min, max) conditions rolled per session
CONDITIONS_PER_TIER = {1: (0, 0), 2: (0, 1), 3: (1, 1), 4: (1, 2), 5: (2, 2)}

# ── Challenges (values indexed by tier: 1–5, None = not available) ────

READ_THE_MASTER = {
    "steps":            {1: 4,   2: 5,   3: 6,    4: 7,    5: 8},
    "seconds_per_step": {1: 3.0, 2: 2.5, 3: 2.0,  4: 1.75, 5: 1.5},
    "deceptive_chance": {1: 0.0, 2: 0.0, 3: 0.10, 4: 0.20, 5: 0.30},
}

RHYTHM_OF_THE_BLADE = {
    "pattern_length":       {3: 3,  4: 4,  5: 5},
    "total_steps":          {3: 10, 4: 11, 5: 12},
    "foresight_multiplier": 2.0,
}

ENDLESS_WAVES = {
    "start_stamina": 100,
    "counter_cost": 10,
    "fast_counter_refund": 5,
    "technique_strike_cost": 30,
    "technique_strike_multiplier": 2.0,
    "target_waves": {1: 5, 2: 6, 3: 7, 4: 8, 5: 10},
}

AMBUSH = {
    "player_hp": 3,
    "strong_opponent_damage": 2,
    "normal_opponent_damage": 1,
    "target_rounds": {2: 5, 3: 6, 4: 7, 5: 8},
}

FIND_THE_WEAKNESS = {
    "sequence_length": {2: 3, 3: 4, 4: 4, 5: 5},
    "tries_allowed":   {2: 8, 3: 8, 4: 7, 5: 6},
}

SWORD_FORMATION = {
    "sequence_length": {3: 5,  4: 6,  5: 7},
    "rule_count":      {3: 3,  4: 4,  5: 5},
    "time_limit_s":    {3: 60, 4: 50, 5: 40},
}

# ── Conditions ────────────────────────────────────────────────────────

CONDITION_EXP_BONUS = 0.15

CONDITIONS = {
    "heavy_rain":     {"timer_multiplier": 0.75},
    "old_injury":     {"strike_stamina_multiplier": 2.0, "strike_points_multiplier": 0.5},
    "drunken_master": {"unreliable_tell_chance": 0.5},
    "night_training": {"reveal_at_timer_fraction": 0.40},
}

# ── Surprise events ───────────────────────────────────────────────────

EVENTS = {
    "wandering_hermit": {"chance": 0.01, "exp_multiplier": 5.0, "extra_conditions": 2},
    "epiphany":         {"chance": 0.02, "exp_bonus": 0.50},
    "rival_disciple":   {"chance": 0.02, "win_exp_multiplier": 2.0},
}

# ── EXP ───────────────────────────────────────────────────────────────

LOW_SCORE_THRESHOLD = 0.50   # below this score...
LOW_SCORE_EXP_RATE = 0.10    # ...only 10% of EXP
