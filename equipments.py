"""
Weapon data. Design rules are explained in docs/equipment.md.
Buff values are fractions (0.05 = +5%). Ranges are (min, max), rolled on drop.
"""

TIERS = ["ordinary", "refined", "spirit", "treasure", "divine"]

TIER_DISPLAY = {
    "ordinary": "⚪ Ordinary",
    "refined":  "🟢 Refined",
    "spirit":   "🔵 Spirit",
    "treasure": "🟣 Treasure",
    "divine":   "🟠 Divine",
}

# Minimum realm to equip
TIER_REALM_REQUIREMENT = {
    "ordinary": "Mortal",
    "refined":  "Martial Apprentice",
    "spirit":   "Martial Expert",
    "treasure": "Grand Martial Master",
    "divine":   "Martial King",
}

WEAPON_TYPES = ["sword", "saber", "spear", "staff", "gauntlets"]

WEAPON_SLOTS = 1

# ── Names ─────────────────────────────────────────────────────────────

WEAPON_NAMES = {
    "ordinary": {
        "sword": "Iron Sword", "saber": "Iron Saber", "spear": "Wooden Spear",
        "staff": "Oak Staff", "gauntlets": "Leather Gauntlets",
    },
    "refined": {
        "sword": "Tempered Steel Sword", "saber": "Crescent Steel Saber", "spear": "Red-Tassel Spear",
        "staff": "Ironwood Staff", "gauntlets": "Bronze Knuckle Gauntlets",
    },
    "spirit": {
        "sword": "Azure Frost Sword", "saber": "Thunderclap Saber", "spear": "Wind-Chaser Spear",
        "staff": "Moonshadow Staff", "gauntlets": "Tiger-Bone Gauntlets",
    },
    "treasure": {
        "sword": "Seven Stars Sword", "saber": "Blood-Drinking Saber", "spear": "Dragon-Scale Spear",
        "staff": "Kunlun Jade Staff", "gauntlets": "Golden Crow Gauntlets",
    },
    "divine": {
        "sword": "Sword of the Nine Heavens", "saber": "Sun-Severing Saber", "spear": "Heaven-Piercing Spear",
        "staff": "Sea-Calming Pillar", "gauntlets": "Primordial Chaos Gauntlets",
    },
}

# ── Stat buffs: type → tier → stat → (min, max) ───────────────────────

WEAPON_BUFFS = {
    "sword": {
        "ordinary": {"attack": (0.02, 0.03), "defense": (0.01, 0.02)},
        "refined":  {"attack": (0.04, 0.06), "defense": (0.03, 0.04)},
        "spirit":   {"attack": (0.07, 0.10), "defense": (0.05, 0.06)},
        "treasure": {"attack": (0.11, 0.14), "defense": (0.07, 0.10)},
        "divine":   {"attack": (0.17, 0.21), "defense": (0.11, 0.14)},
    },
    "saber": {
        "ordinary": {"attack": (0.03, 0.05)},
        "refined":  {"attack": (0.07, 0.10)},
        "spirit":   {"attack": (0.12, 0.16)},
        "treasure": {"attack": (0.18, 0.24)},
        "divine":   {"attack": (0.28, 0.35)},
    },
    "spear": {
        "ordinary": {"attack": (0.02, 0.03), "hp": (0.01, 0.02)},
        "refined":  {"attack": (0.04, 0.06), "hp": (0.03, 0.04)},
        "spirit":   {"attack": (0.07, 0.10), "hp": (0.05, 0.06)},
        "treasure": {"attack": (0.11, 0.14), "hp": (0.07, 0.10)},
        "divine":   {"attack": (0.17, 0.21), "hp": (0.11, 0.14)},
    },
    "staff": {
        "ordinary": {"defense": (0.02, 0.03), "hp": (0.02, 0.03)},
        "refined":  {"defense": (0.04, 0.05), "hp": (0.04, 0.05)},
        "spirit":   {"defense": (0.06, 0.08), "hp": (0.06, 0.08)},
        "treasure": {"defense": (0.09, 0.12), "hp": (0.09, 0.12)},
        "divine":   {"defense": (0.14, 0.18), "hp": (0.14, 0.18)},
    },
    "gauntlets": {
        "ordinary": {"attack": (0.02, 0.03), "defense": (0.01, 0.01), "hp": (0.01, 0.01)},
        "refined":  {"attack": (0.04, 0.05), "defense": (0.02, 0.03), "hp": (0.02, 0.03)},
        "spirit":   {"attack": (0.06, 0.08), "defense": (0.03, 0.04), "hp": (0.03, 0.04)},
        "treasure": {"attack": (0.09, 0.12), "defense": (0.05, 0.06), "hp": (0.05, 0.06)},
        "divine":   {"attack": (0.14, 0.18), "defense": (0.07, 0.09), "hp": (0.07, 0.09)},
    },
}

# ── Quality (based on roll position within the range, 0.0–1.0) ────────
# Checked top to bottom; first match wins.

QUALITY_PREFIXES = [
    (0.95, "Flawless"),  # top 5%
    (0.75, "Fine"),      # top 25%
    (0.25, ""),          # middle — no prefix
    (0.00, "Cracked"),   # bottom 25%
]

# ── Drop rates ────────────────────────────────────────────────────────

CHEST_WEAPON_CHANCE = {
    "common":    0.02,
    "uncommon":  0.04,
    "rare":      0.08,
    "epic":      0.10,
    "legendary": 0.12,
    "mythic":    0.20,
}

# chest → tier → chance (each row sums to 1.0)
CHEST_TIER_ODDS = {
    "common":    {"ordinary": 0.99, "refined": 0.01},
    "uncommon":  {"ordinary": 0.90, "refined": 0.095, "spirit": 0.005},
    "rare":      {"refined": 0.85, "spirit": 0.14, "treasure": 0.01},
    "epic":      {"refined": 0.40, "spirit": 0.55, "treasure": 0.05},
    "legendary": {"spirit": 0.88, "treasure": 0.119, "divine": 0.001},
    "mythic":    {"spirit": 0.50, "treasure": 0.46, "divine": 0.04},
}

ANNOUNCE_TIERS = ["divine"]  # drops announced to the whole server


# ══ Armor ═════════════════════════════════════════════════════════════
# Rules: docs/equipment.md "Armor". Same tiers, realm requirements, quality prefixes
# and drop odds as weapons. Buff values are fractions, (min, max) rolled on drop.

ARMOR_SLOTS = 1
ARMOR_TYPES = ["robe", "plate", "hide", "vest"]

ARMOR_TYPE_DISPLAY = {
    "robe":  ("袍", "Martial Robe"),
    "plate": ("甲", "Iron Plate"),
    "hide":  ("皮", "Beast Hide"),
    "vest":  ("衣", "Silk Vest"),
}

ARMOR_NAMES = {
    "ordinary": {"robe": "Hemp Training Robe", "plate": "Iron Scale Vest",
                 "hide": "Wolf Hide Coat", "vest": "Cotton Wrap"},
    "refined":  {"robe": "Disciple's Cloud Robe", "plate": "Tempered Lamellar",
                 "hide": "Bear Pelt Mantle", "vest": "Black Silk Vest"},
    "spirit":   {"robe": "Moonweave Robe", "plate": "Azure Dragon-Scale Armor",
                 "hide": "Thunder Hawk Feather Cloak", "vest": "Spider Silk Vest"},
    "treasure": {"robe": "Robe of Drifting Clouds", "plate": "Golden Turtle Shell Armor",
                 "hide": "Qilin Hide Robe", "vest": "Vermilion Phoenix Vest"},
    "divine":   {"robe": "Robe of the Nine Heavens", "plate": "Armor of the Black Tortoise",
                 "hide": "Mantle of Kun-Peng", "vest": "Heavenly Silk of the Weaver"},
}

# type → tier → stat → (min, max)
ARMOR_BUFFS = {
    "robe": {    # HP + Defense, 50 / 50
        "ordinary": {"hp": (0.02, 0.03), "defense": (0.02, 0.03)},
        "refined":  {"hp": (0.04, 0.05), "defense": (0.04, 0.05)},
        "spirit":   {"hp": (0.06, 0.08), "defense": (0.06, 0.08)},
        "treasure": {"hp": (0.09, 0.12), "defense": (0.09, 0.12)},
        "divine":   {"hp": (0.14, 0.18), "defense": (0.14, 0.18)},
    },
    "plate": {   # Defense only
        "ordinary": {"defense": (0.03, 0.05)},
        "refined":  {"defense": (0.07, 0.10)},
        "spirit":   {"defense": (0.12, 0.16)},
        "treasure": {"defense": (0.18, 0.24)},
        "divine":   {"defense": (0.28, 0.35)},
    },
    "hide": {    # HP only
        "ordinary": {"hp": (0.03, 0.05)},
        "refined":  {"hp": (0.07, 0.10)},
        "spirit":   {"hp": (0.12, 0.16)},
        "treasure": {"hp": (0.18, 0.24)},
        "divine":   {"hp": (0.28, 0.35)},
    },
    "vest": {    # Defense + Attack, 60 / 40
        "ordinary": {"defense": (0.02, 0.03), "attack": (0.01, 0.02)},
        "refined":  {"defense": (0.04, 0.06), "attack": (0.03, 0.04)},
        "spirit":   {"defense": (0.07, 0.10), "attack": (0.05, 0.06)},
        "treasure": {"defense": (0.11, 0.14), "attack": (0.07, 0.10)},
        "divine":   {"defense": (0.17, 0.21), "attack": (0.11, 0.14)},
    },
}

# Armor uses the weapon odds: CHEST_ARMOR_CHANCE per chest, then CHEST_TIER_ODDS for the tier.
CHEST_ARMOR_CHANCE = dict(CHEST_WEAPON_CHANCE)


# ══ Artifacts ═════════════════════════════════════════════════════════
# Rules: docs/equipment.md "Artifacts". Each family has one effect; every tier has its own
# name and a fixed effect value (no quality roll). Same realm requirements as weapons.

ARTIFACT_SLOTS = 2                    # both open from the start
ARTIFACT_SAME_FAMILY_LIMIT = 1        # can't equip two artifacts of the same family
DUEL_COMBAT_ARTIFACT_STRENGTH = 0.5   # combat artifacts at half strength in Fair Duels

# family → seal, group, effect key, what it does, values by tier (ordinary → divine), names by tier
ARTIFACT_FAMILIES = {
    # ── combat ──
    "fang": {"seal": "牙", "group": "combat", "effect": "strike_vs_break_damage",
             "text": "Extra damage when your Strike beats a Break",
             "values": [0.05, 0.10, 0.15, 0.20, 0.25],
             "names": ["Wolf Fang Charm", "Tiger Fang Talisman", "Thunder Hawk Talon",
                       "Flood Dragon Fang", "Fang of the White Tiger"]},
    "bell": {"seal": "钟", "group": "combat", "effect": "charged_damage_reduction",
             "text": "Less damage from charged attacks",
             "values": [0.05, 0.10, 0.17, 0.24, 0.30],
             "names": ["Bronze Temple Bell", "Copper Warding Bell", "Moonsilver Chime",
                       "Bell of Ten Thousand Wards", "Chaos Bell of the Eastern Sovereign"]},
    "mirror": {"seal": "镜", "group": "combat", "effect": "guard_reflect",
               "text": "Reflects part of the damage you Guard",
               "values": [0.03, 0.06, 0.09, 0.12, 0.15],
               "names": ["Polished Bronze Mirror", "Jade Mirror", "Moonlit Mirror",
                         "Bagua Mirror", "Kunlun Mirror"]},
    "thunder": {"seal": "雷", "group": "combat", "effect": "break_stagger_chance",
                "text": "Chance your Break also staggers",
                "values": [0.05, 0.08, 0.12, 0.16, 0.20],
                "names": ["Flint Bead", "Thunderstone Bead", "Storm Pearl",
                          "Nine-Bolt Thunder Orb", "Drum of the Thunder Lord"]},
    "lotus": {"seal": "莲", "group": "combat", "effect": "heal_per_turn",
              "text": "Heals a share of max HP every turn",
              "values": [0.01, 0.015, 0.02, 0.03, 0.04],
              "names": ["Wooden Lotus Charm", "Lotus Heart Pendant", "Spring Dew Jade",
                        "Phoenix Feather Pendant", "Lotus of Rebirth"]},
    "feather": {"seal": "羽", "group": "combat", "effect": "dodge_chance",
                "text": "Chance to dodge a hit",
                "values": [0.03, 0.05, 0.07, 0.10, 0.12],
                "names": ["Sparrow Feather", "Swallow Wing Charm", "Crane Feather Fan",
                          "Cloud-Stepping Ribbon", "Wind-and-Fire Wheels"]},
    "focus": {"seal": "心", "group": "combat", "effect": "cooldown_reset_chance",
              "text": "Chance a technique's cooldown resets instantly",
              "values": [0.05, 0.08, 0.12, 0.16, 0.20],
              "names": ["Meditation Beads", "Sandalwood Prayer Beads", "Seal of Clear Mind",
                        "Sutra of Endless Breath", "Lamp of Eternal Insight"]},
    # ── cultivation and crafting ──
    "qi": {"seal": "聚", "group": "cultivation", "effect": "qi_rate",
           "text": "Internal Qi Rate",
           "values": [0.03, 0.05, 0.08, 0.12, 0.15],
           "names": ["Qi-Gathering Pebble", "Spirit-Gathering Bead", "Cloud Jade Disc",
                     "Dragon Vein Pearl", "Pearl of the Primordial Sea"]},
    "purity": {"seal": "玉", "group": "cultivation", "effect": "toxicity_decay_faster",
               "text": "Pill toxicity fades faster",
               "values": [0.05, 0.10, 0.15, 0.20, 0.25],
               "names": ["Smooth River Stone", "Calm Heart Jade", "Ice Soul Jade",
                         "Purifying Lotus Seal", "Jade of Ten Thousand Purities"]},
    "furnace": {"seal": "炉", "group": "cultivation", "effect": "craft_zone_degrees",
                "text": "Wider heat safe zone in /craft (degrees)",
                "values": [2, 3, 5, 6, 8],
                "names": ["Ember Stone", "Alchemist's Fire Crystal", "Earth Fire Core",
                          "Samadhi Flame Lamp", "Ember of the Eight Trigrams Furnace"]},
    "gourd": {"seal": "葫", "group": "cultivation", "effect": "old_herb_chance",
              "text": "Higher chance of old herbs in /gather",
              "values": [0.05, 0.10, 0.15, 0.20, 0.25],
              "names": ["Woven Herb Pouch", "Herb Spirit Gourd", "Dew-Collecting Vase",
                        "Purple Gold Gourd", "Jade Purity Vase"]},
    "insight": {"seal": "书", "group": "cultivation", "effect": "mastery_exp",
                "text": "Technique mastery EXP",
                "values": [0.03, 0.06, 0.09, 0.12, 0.15],
                "names": ["Torn Manual Page", "Old Master's Notes", "Scroll of Silent Insight",
                          "Jade Slip of a Fallen Grandmaster", "Heavenly Book of the Dao"]},
    # ── exploration and wealth ──
    "compass": {"seal": "罗", "group": "exploration", "effect": "explore_luck",
                "text": "Better chests and rare encounters in /explore",
                "values": [0.03, 0.06, 0.09, 0.12, 0.15],
                "names": ["Traveler's Compass", "Wanderer's Compass", "Star-Reading Disc",
                          "Luopan of Mountains and Rivers", "Map of Heaven and Earth"]},
    "fortune": {"seal": "财", "group": "exploration", "effect": "lotus_coins",
                "text": "More Lotus Coins from fights and chests",
                "values": [0.05, 0.10, 0.15, 0.20, 0.25],
                "names": ["Copper Coin Pouch", "Merchant's Abacus", "Golden Toad Charm",
                          "Treasure Bowl of Plenty", "Tree of Endless Wealth"]},
    "hunter": {"seal": "兽", "group": "exploration", "effect": "beast_core_chance",
               "text": "More Beast Cores from fights (share of the normal chance)",
               "values": [0.10, 0.20, 0.30, 0.40, 0.50],
               "names": ["Hunter's Bone Whistle", "Beast-Tracking Totem", "Blood Moon Lure",
                         "Beastmaster's Seal", "Banner of Ten Thousand Beasts"]},
}


def artifact_name(family, tier):
    return ARTIFACT_FAMILIES[family]["names"][TIERS.index(tier)]


def artifact_value(family, tier):
    return ARTIFACT_FAMILIES[family]["values"][TIERS.index(tier)]


# Artifacts are about twice as rare as weapons; Treasure and Divine only from Legendary and Mythic chests.
CHEST_ARTIFACT_CHANCE = {chest: chance / 2 for chest, chance in CHEST_WEAPON_CHANCE.items()}
CHEST_ARTIFACT_TIER_ODDS = {
    "common":    {"ordinary": 0.99, "refined": 0.01},
    "uncommon":  {"ordinary": 0.90, "refined": 0.095, "spirit": 0.005},
    "rare":      {"refined": 0.85, "spirit": 0.15},
    "epic":      {"refined": 0.40, "spirit": 0.60},
    "legendary": {"spirit": 0.88, "treasure": 0.119, "divine": 0.001},
    "mythic":    {"spirit": 0.50, "treasure": 0.46, "divine": 0.04},
}
