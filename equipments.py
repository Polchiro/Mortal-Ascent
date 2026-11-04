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
    "wooden": 0.02,
    "bronze": 0.04,
    "silver": 0.08,
    "jade":   0.12,
}

# chest → tier → chance (each row sums to 1.0)
CHEST_TIER_ODDS = {
    "wooden": {"ordinary": 0.99, "refined": 0.01},
    "bronze": {"ordinary": 0.90, "refined": 0.095, "spirit": 0.005},
    "silver": {"refined": 0.85, "spirit": 0.14, "treasure": 0.01},
    "jade":   {"spirit": 0.88, "treasure": 0.119, "divine": 0.001},
}

ANNOUNCE_TIERS = ["divine"]  # drops announced to the whole server
