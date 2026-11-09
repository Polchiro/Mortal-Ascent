"""
Daily quest data. Design rules are explained in docs/quests.md.
"""

QUESTS_PER_DAY = 6          # picked from QUESTS each day (midnight UTC), the same for a player all day

FINE_PILL_PATTERNS = 5      # a "fine pill" has at least this many patterns

# key → the quest. event: what counts (bot/quests.py), n: how many, coins / pearls: the reward,
# weight: how often it is picked, icon: cards.theme icon kind (a painting when there is one).
QUESTS = {
    "train":     {"name": "Temper the Body",    "text": "Finish {n} /train sessions",         "event": "train",
                  "n": 5,  "coins": 220, "pearls": 6,  "weight": 3, "icon": "art:index/techniques_heaven"},
    "practice":  {"name": "Polish a Technique", "text": "/practice {n} times",                "event": "practice",
                  "n": 8,  "coins": 200, "pearls": 6,  "weight": 3, "icon": "art:index/techniques_mortal"},
    "spar":      {"name": "Cross Hands",        "text": "/spar with a master {n} times",      "event": "spar",
                  "n": 3,  "coins": 180, "pearls": 5,  "weight": 2, "icon": "art:index/weapons_spirit"},
    "spar_win":  {"name": "Best the Master",    "text": "Win {n} /spar bouts",                "event": "spar_win",
                  "n": 2,  "coins": 260, "pearls": 8,  "weight": 2, "icon": "art:index/weapons_treasure"},
    "explore":   {"name": "Into the Wilds",     "text": "Finish {n} /explore trips",          "event": "explore",
                  "n": 6,  "coins": 260, "pearls": 7,  "weight": 3, "icon": "art:index/ov_sources"},
    "beasts":    {"name": "Beast Slayer",       "text": "Defeat {n} beasts",                  "event": "beasts",
                  "n": 15, "coins": 300, "pearls": 8,  "weight": 3, "icon": "art:index/ov_normal"},
    "gather":    {"name": "Herb Picker",        "text": "Gather {n} herbs",                   "event": "gather",
                  "n": 40, "coins": 240, "pearls": 7,  "weight": 3, "icon": "art:index/ov_pick"},
    "old_herb":  {"name": "Old Roots",          "text": "Gather {n} herbs aged 100+ years",   "event": "old_herb",
                  "n": 2,  "coins": 320, "pearls": 9,  "weight": 2, "icon": "art:index/ov_old"},
    "craft":     {"name": "Light the Cauldron", "text": "Craft {n} pills in /craft",          "event": "craft",
                  "n": 6,  "coins": 240, "pearls": 7,  "weight": 2, "icon": "art:index/ov_rank"},
    "fine_pill": {"name": "Flawless Elixir",    "text": "Craft {n} pills with 5+ patterns",   "event": "fine_pill",
                  "n": 2,  "coins": 320, "pearls": 10, "weight": 1, "icon": "art:index/ov_patterns"},
    "forge":     {"name": "Strike the Anvil",   "text": "/forge {n} times",                   "event": "forge",
                  "n": 2,  "coins": 280, "pearls": 8,  "weight": 1, "icon": "art:index/weapons_divine"},
    "chest":     {"name": "Treasure Hunter",    "text": "Open {n} chests",                    "event": "chest",
                  "n": 3,  "coins": 200, "pearls": 6,  "weight": 2, "icon": "chest:rare"},
}

# Coin rewards grow with the realm: × (1 + COIN_STEP_PER_REALM × realm index). Mortal ×1, Martial Saint ×3.5.
COIN_STEP_PER_REALM = 0.25

# Finishing every quest of the day.
ALL_DONE_COINS = 600         # grows with the realm like the quest coins
ALL_DONE_PEARLS = 25
ALL_DONE_CHEST_CHANCE = 0.40
ALL_DONE_CHEST_TIERS = {     # weights of the chest when one drops
    "common": 55,
    "uncommon": 27,
    "rare": 12,
    "epic": 5,
    "legendary": 1,
}
