"""
Daily quest data. Design rules are explained in docs/quests.md.
"""

QUESTS_PER_DAY = 4          # picked from QUESTS each day (midnight UTC), the same for a player all day

# key → the quest. event: what counts (bot/quests.py EVENTS), n: how many, coins / pearls: the reward,
# weight: how often it is picked, icon: cards.theme icon kind (a painting when there is one).
QUESTS = {
    "train":    {"name": "Temper the Body",    "text": "Finish {n} /train sessions",  "event": "train",
                 "n": 2,  "coins": 80,  "pearls": 3, "weight": 3, "icon": "art:index/techniques_heaven"},
    "practice": {"name": "Polish a Technique", "text": "/practice {n} times",         "event": "practice",
                 "n": 3,  "coins": 70,  "pearls": 3, "weight": 3, "icon": "art:index/techniques_mortal"},
    "spar":     {"name": "Cross Hands",        "text": "/spar with a master once",    "event": "spar",
                 "n": 1,  "coins": 60,  "pearls": 3, "weight": 2, "icon": "art:index/weapons_spirit"},
    "explore":  {"name": "Into the Wilds",     "text": "Finish {n} /explore trips",   "event": "explore",
                 "n": 2,  "coins": 90,  "pearls": 3, "weight": 3, "icon": "art:index/ov_sources"},
    "beasts":   {"name": "Beast Slayer",       "text": "Defeat {n} beasts",           "event": "beasts",
                 "n": 3,  "coins": 100, "pearls": 4, "weight": 3, "icon": "art:index/ov_normal"},
    "gather":   {"name": "Herb Picker",        "text": "Gather {n} herbs",            "event": "gather",
                 "n": 10, "coins": 80,  "pearls": 3, "weight": 3, "icon": "art:index/ov_pick"},
    "craft":    {"name": "Light the Cauldron", "text": "Craft {n} pills in /craft",   "event": "craft",
                 "n": 2,  "coins": 90,  "pearls": 4, "weight": 2, "icon": "art:index/ov_rank"},
}

# Coin rewards grow with the realm: × (1 + COIN_STEP_PER_REALM × realm index). Mortal ×1, Martial Saint ×3.5.
COIN_STEP_PER_REALM = 0.25

# Finishing every quest of the day.
ALL_DONE_COINS = 150         # grows with the realm like the quest coins
ALL_DONE_PEARLS = 8
ALL_DONE_CHEST_CHANCE = 0.60
ALL_DONE_CHEST_TIERS = {     # weights of the chest when one drops
    "common": 40,
    "uncommon": 30,
    "rare": 18,
    "epic": 9,
    "legendary": 3,
}
