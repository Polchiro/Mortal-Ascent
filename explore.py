"""
Exploration data. Design rules are explained in docs/explore.md.
"""
import forge

EXPLORE_COOLDOWN_MINUTES = 30
MAX_STEPS = 5
PATHS = ["left", "middle", "right"]

# Chance a path clue is misleading, by difficulty tier (see challenges.REALM_TIER)
MISLEADING_CLUE_CHANCE = {1: 0.0, 2: 0.05, 3: 0.10, 4: 0.15, 5: 0.20}

# ── Push your luck ────────────────────────────────────────────────────

# Multiplier on uncommon-and-rarer encounter chances, by step (1–5)
RARE_CHANCE_BY_STEP = {1: 1.00, 2: 1.25, 3: 1.50, 4: 1.75, 5: 2.00}
BEAST_STAT_BONUS_PER_STEP = 0.10   # step 2 = +10%, step 5 = +40%

DEFEAT_LOOT_LOSS = 0.50            # coins and materials only
DEFEAT_INJURY_HOURS = 1

# ── Encounters (base chances, sum to 1.0) ─────────────────────────────

ENCOUNTERS = {
    "wild_beast":        {"chance": 0.320, "rare": False},
    "treasure_chest":    {"chance": 0.150, "rare": False},
    "herb_patch":        {"chance": 0.100, "rare": False},
    "peaceful_clearing": {"chance": 0.090, "rare": False},
    "ore_vein":          {"chance": forge.ORE_VEIN_ENCOUNTER_CHANCE, "rare": False},   # forging metal (docs/forge.md)
    "hazard":            {"chance": 0.070, "rare": True},
    "bandits":           {"chance": 0.060, "rare": True},
    "wandering_merchant":{"chance": 0.040, "rare": True},
    "injured_stranger":  {"chance": 0.040, "rare": True},
    "stone_tablet":      {"chance": 0.030, "rare": True},
    "elite_lair":        {"chance": 0.025, "rare": True},
    "blessed_land":      {"chance": 0.010, "rare": True},
    "wandering_hermit":  {"chance": 0.003, "rare": True},
    "beast_king_den":    {"chance": 0.002, "rare": True},
}
# When step multipliers raise "rare" chances, common chances are scaled down
# so the total stays 1.0.

PEACEFUL_CLEARING_HEAL = 0.25
HAZARD_FAIL_HP_LOSS = 0.15
BANDIT_COIN_LOSS = 0.10
INJURED_STRANGER_GRATEFUL = 0.70   # otherwise an ambush
STONE_TABLET_PRACTICE_SESSIONS = 2  # mastery EXP = this × /practice base
ELITE_LAIR_OPEN_MINUTES = 30
BEAST_KING_DEN_OPEN_MINUTES = 60

TREASURE_CHEST_TIER = {"common": 0.58, "uncommon": 0.30, "rare": 0.10, "epic": 0.02}

BLESSED_LAND_TYPE = {"spirit_spring": 0.60, "lotus_grove": 0.35, "dragon_vein": 0.05}

# ── Chests from beasts ────────────────────────────────────────────────

BEAST_CHEST = {
    "normal":     {"chance": 0.30, "tiers": {"common": 0.70, "uncommon": 0.30}},
    "elite":      {"chance": 0.60, "tiers": {"uncommon": 0.45, "rare": 0.45, "epic": 0.10}},
    "beast_king": {"chance": 1.00, "tiers": {"rare": 0.35, "epic": 0.20, "legendary": 0.40, "mythic": 0.05}},
}
CHEST_ROLL_PER_PLAYER = True

# ── Manuals in chests ─────────────────────────────────────────────────

CHEST_MANUAL_CHANCE = {"common": 0.05, "uncommon": 0.10, "rare": 0.15, "epic": 0.20, "legendary": 0.25, "mythic": 0.40}

CHEST_MANUAL_GRADE_ODDS = {
    "common":    {"Mortal": 1.0},
    "uncommon":  {"Mortal": 0.80, "Yellow": 0.20},
    "rare":      {"Yellow": 0.70, "Mystic": 0.28, "Earth": 0.02},
    "epic":      {"Yellow": 0.30, "Mystic": 0.62, "Earth": 0.08},
    "legendary": {"Mystic": 0.80, "Earth": 0.198, "Heaven": 0.002},
    "mythic":    {"Mystic": 0.40, "Earth": 0.55, "Heaven": 0.05},
}

ANNOUNCE_MANUAL_GRADES = ["Heaven"]

# Weapon drops from chests: see equipment.CHEST_WEAPON_CHANCE / CHEST_TIER_ODDS
