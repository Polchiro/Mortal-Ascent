"""
Talent data. Design rules are explained in docs/talent.md.
Qi Rate bonus per talent lives in training.TALENT_QI_BONUS.
"""

TALENTS = ["Ordinary", "Gifted", "Genius", "Prodigy", "Heavenly", "Saint", "Divine"]

TALENT_ROLL_ODDS = {
    "Ordinary":  0.350,
    "Gifted":    0.280,
    "Genius":    0.170,
    "Prodigy":   0.100,
    "Heavenly":  0.060,
    "Saint":     0.030,
    "Divine":    0.010,
}

# Reduction in manual comprehension time
TALENT_COMPREHENSION_BONUS = {
    "Ordinary": 0.00,
    "Gifted":   0.10,
    "Genius":   0.15,
    "Prodigy":  0.25,
    "Heavenly": 0.30,
    "Saint":    0.40,
    "Divine":   0.50,
}

ANNOUNCE_TALENTS = ["Saint", "Divine"]

TALENT_LOCKED_TO_ACCOUNT = True   # restarting a character keeps the talent

# ── Rerolls (same odds as TALENT_ROLL_ODDS) ───────────────────────────

FATE_REROLL = {
    "currency": "lotus_coins",
    "cost": 7500,                # flat price, the same every time
    "can_go_lower": True,
}

HEAVENLY_FATE_REROLL = {
    "currency": "premium",       # name and price set in the premium shop
    "can_go_lower": False,       # result is never below current talent
}

HEAVEN_DEFYING_PILL = {
    "rank_increase": 1,
    "max_talent": "Divine",
    "chest_chance": {"legendary": 0.0005, "mythic": 0.005},   # per chest of that tier
    "tradeable": False,
}
