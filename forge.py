"""
Forging data: /forge (the blacksmith minigame), passives on gear, forging materials, blacksmith ranks.
Design rules are explained in docs/forge.md. Every forging number lives in this file.

Gear tiers are equipments.TIERS (ordinary → divine). Material tiers are 1–5 and line up with them:
tier 1 = Ordinary gear, tier 5 = Divine gear.
Values marked DEFAULT were not in the design and were picked by the bot; change them freely.
"""

import random as _random

import alchemy
import equipments

TIERS = equipments.TIERS
GEAR_KINDS = ["weapon", "armor", "artifact"]
GEAR_CATEGORY = {"weapon": "weapons", "armor": "armor", "artifact": "artifacts"}   # db item categories

# ══ Rarities and passive slots ════════════════════════════════════════

RARITIES = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythical"]
RARITY_EMOJI = {"Common": "⚪", "Uncommon": "🟢", "Rare": "🔵", "Epic": "🟣", "Legendary": "🟠", "Mythical": "🔴"}
# Colours for cards and emblems (r, g, b). DEFAULT colours.
RARITY_COLORS = {
    "Common":    (196, 190, 178),
    "Uncommon":  (96, 196, 112),
    "Rare":      (82, 150, 236),
    "Epic":      (170, 102, 236),
    "Legendary": (246, 160, 52),
    "Mythical":  (240, 64, 72),
}
GLOW_RARITIES = ["Mythical"]        # name glows on cards
ANNOUNCE_RARITIES = ["Mythical"]    # forged passives announced to the server

# Same for weapons, armor and artifacts
PASSIVE_SLOTS = {
    "ordinary": {"slots": 1, "max_rarity": "Rare"},
    "refined":  {"slots": 1, "max_rarity": "Epic"},
    "spirit":   {"slots": 1, "max_rarity": "Epic"},
    "treasure": {"slots": 2, "max_rarity": "Legendary"},
    "divine":   {"slots": 2, "max_rarity": "Mythical"},
}

# ══ Essence families ══════════════════════════════════════════════════
# key → name, seal (decoration only), which gear it forges, beast element that drops it (None = no beast),
# colour key for the drawn icons (cards ACCENTS / element colours; Part 2 adds the 4 artifact colours)

FAMILIES = {
    "metal":        {"name": "Metal",        "seal": "金", "gear": ["weapon"],          "element": None,      "color": "gold"},
    "blood":        {"name": "Blood",        "seal": "血", "gear": ["weapon"],          "element": "Blood",   "color": "blood"},
    "thunder":      {"name": "Thunder",      "seal": "雷", "gear": ["weapon"],          "element": "Thunder", "color": "thunder"},
    "flame":        {"name": "Flame",        "seal": "炎", "gear": ["weapon"],          "element": "Flame",   "color": "flame"},
    "shadow":       {"name": "Shadow",       "seal": "影", "gear": ["weapon", "armor"], "element": "Shadow",  "color": "shadow"},
    "earth":        {"name": "Earth",        "seal": "土", "gear": ["armor"],           "element": "Earth",   "color": "earth"},
    "jade":         {"name": "Jade",         "seal": "木", "gear": ["armor"],           "element": "Jade",    "color": "jade"},
    "frost":        {"name": "Frost",        "seal": "霜", "gear": ["armor"],           "element": "Frost",   "color": "frost"},
    "venom":        {"name": "Venom",        "seal": "毒", "gear": ["armor"],           "element": "Venom",   "color": "venom"},
    "spirit_dew":   {"name": "Spirit Dew",   "seal": "气", "gear": ["artifact"],        "element": None,      "color": "spirit_dew"},
    "fortune":      {"name": "Fortune Coin", "seal": "福", "gear": ["artifact"],        "element": None,      "color": "fortune"},
    "cauldron_ash": {"name": "Cauldron Ash", "seal": "丹", "gear": ["artifact"],        "element": None,      "color": "cauldron_ash"},
    "insight":      {"name": "Insight Ink",  "seal": "悟", "gear": ["artifact"],        "element": None,      "color": "insight"},
}

# Essence grade → the highest rarity it can give
ESSENCE_GRADES = {
    "shard":   {"name": "Shard",   "max_rarity": "Uncommon"},
    "crystal": {"name": "Crystal", "max_rarity": "Epic"},
    "heart":   {"name": "Heart",   "max_rarity": "Mythical"},
}

# ══ Passives ══════════════════════════════════════════════════════════
# gear kind → key → name, rarity, family, text, numbers (read by bot/passives.py in Part 4).
# Percent values are fractions (0.03 = 3%).

PASSIVES = {
    "weapon": {
        # Common
        "keen_edge":       {"name": "Keen Edge", "rarity": "Common", "family": "metal",
                            "text": "+3% Attack", "fx": {"attack": 0.03}},
        "weighted":        {"name": "Weighted", "rarity": "Common", "family": "metal",
                            "text": "+2% Attack, +1% HP", "fx": {"attack": 0.02, "hp": 0.01}},
        "balanced":        {"name": "Balanced", "rarity": "Common", "family": "metal",
                            "text": "+2% Attack, +1% Defense", "fx": {"attack": 0.02, "defense": 0.01}},
        "hunters_edge":    {"name": "Hunter's Edge", "rarity": "Common", "family": "shadow",
                            "text": "+4% damage against beasts", "fx": {"damage_vs_beasts": 0.04}},
        "duelists_edge":   {"name": "Duelist's Edge", "rarity": "Common", "family": "shadow",
                            "text": "+3% damage in duels", "fx": {"damage_in_duels": 0.03}},
        # Uncommon
        "opening_strike":  {"name": "Opening Strike", "rarity": "Uncommon", "family": "flame",
                            "text": "+10% damage on turn 1", "fx": {"damage_turn_1": 0.10}},
        "breaker":         {"name": "Breaker", "rarity": "Uncommon", "family": "flame",
                            "text": "+8% Break damage", "fx": {"break_damage": 0.08}},
        "pursuit":         {"name": "Pursuit", "rarity": "Uncommon", "family": "shadow",
                            "text": "+6% damage against a staggered target", "fx": {"damage_vs_staggered": 0.06}},
        "executioner":     {"name": "Executioner", "rarity": "Uncommon", "family": "flame",
                            "text": "+8% damage against targets under 30% HP",
                            "fx": {"damage_vs_low_hp": 0.08, "low_hp_below": 0.30}},
        "rhythm":          {"name": "Rhythm", "rarity": "Uncommon", "family": "thunder",
                            "text": "Each Strike in a row +4% damage (max 3 stacks)",
                            "fx": {"strike_streak_damage": 0.04, "max_stacks": 3}},
        # Rare
        "lifesteal":       {"name": "Lifesteal", "rarity": "Rare", "family": "blood",
                            "text": "Heal 4% of the damage you deal", "fx": {"heal_of_damage": 0.04}},
        "armor_crack":     {"name": "Armor Crack", "rarity": "Rare", "family": "metal",
                            "text": "Each hit lowers the target's Defense by 3% (max 5 stacks)",
                            "fx": {"defense_down_per_hit": 0.03, "max_stacks": 5}},
        "bleeding_cut":    {"name": "Bleeding Cut", "rarity": "Rare", "family": "blood",
                            "text": "Strikes make the target bleed 2% max HP for 2 turns",
                            "fx": {"bleed_max_hp": 0.02, "turns": 2}},
        "riposte":         {"name": "Riposte", "rarity": "Rare", "family": "shadow",
                            "text": "After a successful Guard, your next Strike +15%", "fx": {"strike_after_guard": 0.15}},
        "flash_step":      {"name": "Flash Step", "rarity": "Rare", "family": "thunder",
                            "text": "5% chance to strike twice (second hit 50%)",
                            "fx": {"chance": 0.05, "second_hit": 0.50}},
        # Epic
        "thunder_edge":    {"name": "Thunder Edge", "rarity": "Epic", "family": "thunder",
                            "text": "10% chance to stun: the target can't Guard next turn", "fx": {"chance": 0.10}},
        "blood_frenzy":    {"name": "Blood Frenzy", "rarity": "Epic", "family": "blood",
                            "text": "+1% Attack for every 5% HP you are missing",
                            "fx": {"attack_per_step": 0.01, "missing_hp_step": 0.05}},
        "sunder":          {"name": "Sunder", "rarity": "Epic", "family": "metal",
                            "text": "Ignore 10% of the target's Defense", "fx": {"ignore_defense": 0.10}},
        "combo_master":    {"name": "Combo Master", "rarity": "Epic", "family": "thunder",
                            "text": "Combo techniques: 30% chance of +1 hit", "fx": {"chance": 0.30, "extra_hits": 1}},
        # Legendary
        "heaven_splitting": {"name": "Heaven-Splitting", "rarity": "Legendary", "family": "metal",
                             "text": "Once per fight, a Strike can't be Guarded", "fx": {"uses_per_fight": 1}},
        "undying_blade":   {"name": "Undying Blade", "rarity": "Legendary", "family": "blood",
                            "text": "Once per fight, survive a lethal hit at 1 HP", "fx": {"uses_per_fight": 1, "survive_hp": 1}},
        "dragons_wrath":   {"name": "Dragon's Wrath", "rarity": "Legendary", "family": "flame",
                            "text": "12% chance to deal ×1.5 damage", "fx": {"chance": 0.12, "mult": 1.5}},
        # Mythical
        "sword_heart":     {"name": "Sword Heart", "rarity": "Mythical", "family": "shadow",
                            "text": "Every 3rd turn your technique has no cooldown", "fx": {"every_turns": 3}},
        "ten_thousand_swords": {"name": "Ten Thousand Swords Return", "rarity": "Mythical", "family": "thunder",
                                "text": "After 5 turns, your next hit deals ×2", "fx": {"after_turns": 5, "mult": 2.0}},
        "devouring_edge":  {"name": "Devouring Edge", "rarity": "Mythical", "family": "blood",
                            "text": "Heal 10% of the damage you deal and steal 5% of the target's Attack for the fight",
                            "fx": {"heal_of_damage": 0.10, "steal_attack": 0.05}},
    },
    "armor": {
        # Common
        "sturdy":          {"name": "Sturdy", "rarity": "Common", "family": "earth",
                            "text": "+3% Defense", "fx": {"defense": 0.03}},
        "thick_hide":      {"name": "Thick Hide", "rarity": "Common", "family": "jade",
                            "text": "+3% HP", "fx": {"hp": 0.03}},
        "padded":          {"name": "Padded", "rarity": "Common", "family": "earth",
                            "text": "+2% HP, +1% Defense", "fx": {"hp": 0.02, "defense": 0.01}},
        "beastward":       {"name": "Beastward", "rarity": "Common", "family": "venom",
                            "text": "−4% damage from beasts", "fx": {"damage_taken_from_beasts": 0.04}},
        "duel_guard":      {"name": "Duel Guard", "rarity": "Common", "family": "shadow",
                            "text": "−3% damage taken in duels", "fx": {"damage_taken_in_duels": 0.03}},
        # Uncommon
        "steadfast":       {"name": "Steadfast", "rarity": "Uncommon", "family": "frost",
                            "text": "−10% damage taken on turn 1", "fx": {"damage_taken_turn_1": 0.10}},
        "second_wind":     {"name": "Second Wind", "rarity": "Uncommon", "family": "jade",
                            "text": "Once per fight, heal 5% when you drop below 50% HP",
                            "fx": {"heal": 0.05, "below_hp": 0.50, "uses_per_fight": 1}},
        "iron_will":       {"name": "Iron Will", "rarity": "Uncommon", "family": "frost",
                            "text": "−5% damage from Break", "fx": {"damage_taken_from_break": 0.05}},
        "thorns":          {"name": "Thorns", "rarity": "Uncommon", "family": "venom",
                            "text": "Reflect 3% of damage taken", "fx": {"reflect": 0.03}},
        "recovery":        {"name": "Recovery", "rarity": "Uncommon", "family": "jade",
                            "text": "Heal 1% HP every turn", "fx": {"heal_per_turn": 0.01}},
        # Rare
        "bulwark":         {"name": "Bulwark", "rarity": "Rare", "family": "earth",
                            "text": "Guard blocks 10% more", "fx": {"guard_block": 0.10}},
        "spiked_plates":   {"name": "Spiked Plates", "rarity": "Rare", "family": "venom",
                            "text": "Reflect 6% of damage taken", "fx": {"reflect": 0.06}},
        "evasive":         {"name": "Evasive", "rarity": "Rare", "family": "shadow",
                            "text": "5% chance to dodge", "fx": {"dodge": 0.05}},
        "unshaken":        {"name": "Unshaken", "rarity": "Rare", "family": "frost",
                            "text": "50% chance to resist Stagger", "fx": {"stagger_resist": 0.50}},
        "fortified":       {"name": "Fortified", "rarity": "Rare", "family": "earth",
                            "text": "−10% damage from charged attacks", "fx": {"charged_damage_taken": 0.10}},
        # Epic
        "golden_body":     {"name": "Golden Body", "rarity": "Epic", "family": "frost",
                            "text": "The first hit each fight deals −50%", "fx": {"first_hit_taken": 0.50}},
        "stone_skin":      {"name": "Stone Skin", "rarity": "Epic", "family": "earth",
                            "text": "+1% Defense every turn (max +10%)", "fx": {"defense_per_turn": 0.01, "max": 0.10}},
        "vital_flow":      {"name": "Vital Flow", "rarity": "Epic", "family": "jade",
                            "text": "Healing +25%", "fx": {"healing": 0.25}},
        "unbreakable_will": {"name": "Unbreakable Will", "rarity": "Epic", "family": "frost",
                             "text": "Immune to Stagger", "fx": {"stagger_resist": 1.0}},
        # Legendary
        "phoenix_rebirth": {"name": "Phoenix Rebirth", "rarity": "Legendary", "family": "jade",
                            "text": "Once per fight, revive at 20% HP", "fx": {"revive_hp": 0.20, "uses_per_fight": 1}},
        "mountain_stance": {"name": "Mountain Stance", "rarity": "Legendary", "family": "earth",
                            "text": "No single hit can take more than 20% of your max HP", "fx": {"max_hit": 0.20}},
        "mirror_shell":    {"name": "Mirror Shell", "rarity": "Legendary", "family": "venom",
                            "text": "Once per fight, a charged attack deals 0 and goes back to the attacker",
                            "fx": {"uses_per_fight": 1}},
        # Mythical
        "immortal_body":   {"name": "Immortal Body", "rarity": "Mythical", "family": "jade",
                            "text": "Heal 3% max HP every turn; immune to bleed and poison",
                            "fx": {"heal_per_turn": 0.03, "immune": ["bleed", "poison"]}},
        "black_tortoise_shell": {"name": "Black Tortoise's Shell", "rarity": "Mythical", "family": "earth",
                                 "text": "Every 4th hit against you is fully blocked", "fx": {"every_hits": 4}},
        "heavenly_aegis":  {"name": "Heavenly Aegis", "rarity": "Mythical", "family": "shadow",
                            "text": "In team hunts, allies take −10% damage", "fx": {"team_damage_taken": 0.10}},
    },
    "artifact": {    # stack on top of the artifact's own effect
        # Common
        "qi_flow":         {"name": "Qi Flow", "rarity": "Common", "family": "spirit_dew",
                            "text": "+2% Qi Rate", "fx": {"qi_rate": 0.02}},
        "lucky_coin":      {"name": "Lucky Coin", "rarity": "Common", "family": "fortune",
                            "text": "+2% Lotus Coins", "fx": {"lotus_coins": 0.02}},
        "herbalist":       {"name": "Herbalist", "rarity": "Common", "family": "cauldron_ash",
                            "text": "+3% old-herb chance in /gather", "fx": {"old_herb_chance": 0.03}},
        "swift_hands":     {"name": "Swift Hands", "rarity": "Common", "family": "insight",
                            "text": "+0.5s per decision in /gather, /craft and /forge", "fx": {"decision_seconds": 0.5}},
        # Uncommon
        "scholar":         {"name": "Scholar", "rarity": "Uncommon", "family": "insight",
                            "text": "+4% mastery EXP", "fx": {"mastery_exp": 0.04}},
        "pill_affinity":   {"name": "Pill Affinity", "rarity": "Uncommon", "family": "cauldron_ash",
                            "text": "Pills +5% stronger", "fx": {"pill_effect": 0.05}},
        "prospector":      {"name": "Prospector", "rarity": "Uncommon", "family": "fortune",
                            "text": "+5% forging material drops", "fx": {"forge_material_drops": 0.05}},
        "clear_head":      {"name": "Clear Head", "rarity": "Uncommon", "family": "spirit_dew",
                            "text": "Pill toxicity fades 10% faster", "fx": {"toxicity_decay_faster": 0.10}},
        # Rare
        "deep_pockets":    {"name": "Deep Pockets", "rarity": "Rare", "family": "fortune",
                            "text": "5% chance of an extra chest roll", "fx": {"extra_chest_roll": 0.05}},
        "steady_hand":     {"name": "Steady Hand", "rarity": "Rare", "family": "cauldron_ash",
                            "text": "/craft and /forge safe zones +2°", "fx": {"safe_zone_degrees": 2}},
        "keen_eye":        {"name": "Keen Eye", "rarity": "Rare", "family": "insight",
                            "text": "/explore clues 10% less likely to lie", "fx": {"misleading_clue_less": 0.10}},
        "spirit_bond":     {"name": "Spirit Bond", "rarity": "Rare", "family": "insight",
                            "text": "+10% Beast Core chance", "fx": {"beast_core_chance": 0.10}},
        # Epic
        "second_chance":   {"name": "Second Chance", "rarity": "Epic", "family": "cauldron_ash",
                            "text": "Once a day, a failed craft or forge keeps its materials", "fx": {"uses_per_day": 1}},
        "insightful":      {"name": "Insightful", "rarity": "Epic", "family": "insight",
                            "text": "+10% mastery EXP from /practice", "fx": {"practice_mastery_exp": 0.10}},
        "fortunes_favor":  {"name": "Fortune's Favor", "rarity": "Epic", "family": "fortune",
                            "text": "+8% rare /explore encounters", "fx": {"rare_encounters": 0.08}},
        # Legendary
        "heavens_favor":   {"name": "Heaven's Favor", "rarity": "Legendary", "family": "spirit_dew",
                            "text": "+5% realm breakthrough chance", "fx": {"breakthrough_chance": 0.05}},
        "alchemy_sage":    {"name": "Alchemy Sage", "rarity": "Legendary", "family": "cauldron_ash",
                            "text": "Pills can reach 1 pattern beyond the herb-age limit", "fx": {"extra_patterns": 1}},
        "treasure_sense":  {"name": "Treasure Sense", "rarity": "Legendary", "family": "fortune",
                            "text": "Jade Chests 20% more likely", "fx": {"jade_chest_chance": 0.20}},
        # Mythical
        "dao_heart":       {"name": "Dao Heart", "rarity": "Mythical", "family": "spirit_dew",
                            "text": "+10% Qi Rate; pill toxicity can never go above 5",
                            "fx": {"qi_rate": 0.10, "max_toxicity": 5}},
        "fate_weaver":     {"name": "Fate Weaver", "rarity": "Mythical", "family": "fortune",
                            "text": "Once a week, reroll one chest's contents", "fx": {"uses_per_week": 1}},
    },
}

# ── Balance rules (applied in Part 4) ─────────────────────────────────
PER_HIT_CAP_STILL_APPLIES = True    # the 30% per-hit cap (stats.md / battle.py) is never lifted by a passive
NO_DUPLICATE_PASSIVES = True        # one passive can't be on two items a character wears
DUEL_PASSIVE_STRENGTH = 0.5         # passives at half strength in Fair Duels (like combat artifacts)
REFLECT_CAP = 0.20                  # all reflect together (Thorns, Spiked Plates, Mirror artifact) ≤ 20%

# ══ Materials ═════════════════════════════════════════════════════════
# Tier 1 → 5, lined up with gear tiers Ordinary → Divine.

BASE_MATERIALS = {
    "weapon":   ["Iron Ore", "Black Iron", "Spirit Silver", "Star Iron", "Heavenly Gold"],
    "armor":    ["Rough Hide", "Iron Shell", "Spirit Silk", "Dragon Scale", "Qilin Hide"],
    "artifact": ["Green Jade", "White Jade", "Spirit Jade", "Star Jade", "Primordial Jade"],
}
BINDINGS = ["Beast Bone", "Tough Sinew", "Spirit Fang", "Dragon Tendon", "Chaos Crystal"]
FUELS = ["Charcoal", "Black Coal", "Spirit Coal", "Fire Beast Core", "Sunflame Stone"]
QUENCH_LIQUIDS = ["Spring Water", "Beast Oil", "Spirit Spring Water", "Dragon Blood", "Heavenly Dew"]
SEAL_STONE = "Seal Stone"
MATERIALS_USE_BAG_SLOTS = False     # DEFAULT: forging materials sit in a pouch and don't fill bag slots

# Recipe per forge, by gear tier: base material and binding of the SAME tier as the gear
RECIPE = {
    "ordinary": {"base": 3, "binding": 2},
    "refined":  {"base": 4, "binding": 2},
    "spirit":   {"base": 5, "binding": 3},
    "treasure": {"base": 6, "binding": 3},
    "divine":   {"base": 8, "binding": 4},
}
OPTIONAL_PER_FORGE = {"essence": 1, "fuel": 1, "liquid": 1}

# Fuel widens the Ignite safe zone (degrees) by fuel tier 1 → 5. DEFAULT
FUEL_ZONE_BONUS = [2, 3, 4, 5, 6]
# Quench liquid widens the Quench safe window (degrees) by liquid tier 1 → 5. DEFAULT
LIQUID_WINDOW_BONUS = [4, 6, 8, 10, 12]


def material_key(kind, tier=None, family=None, grade=None, gear=None):
    """The inventory key of a material, e.g. base:weapon:1, binding:3, essence:metal:shard, fuel:2, liquid:5, seal."""
    if kind == "base":
        return f"base:{gear}:{tier}"
    if kind == "essence":
        return f"essence:{family}:{grade}"
    if kind == "seal":
        return "seal"
    return f"{kind}:{tier}"


def essence_name(family, grade):
    return f"{FAMILIES[family]['name']} {ESSENCE_GRADES[grade]['name']}"


def all_materials():
    """Every material type: key → {name, kind, tier, gear, family, grade}."""
    out = {}
    for gear, names in BASE_MATERIALS.items():
        for t, name in enumerate(names, 1):
            out[material_key("base", t, gear=gear)] = {"name": name, "kind": "base", "tier": t, "gear": gear}
    for kind, names in (("binding", BINDINGS), ("fuel", FUELS), ("liquid", QUENCH_LIQUIDS)):
        for t, name in enumerate(names, 1):
            out[material_key(kind, t)] = {"name": name, "kind": kind, "tier": t}
    for fam in FAMILIES:
        for grade in ESSENCE_GRADES:
            out[material_key("essence", family=fam, grade=grade)] = {
                "name": essence_name(fam, grade), "kind": "essence", "family": fam, "grade": grade}
    out["seal"] = {"name": SEAL_STONE, "kind": "seal"}
    return out


# ══ Drop sources ══════════════════════════════════════════════════════
# Material tier from a realm: the herb/core tier of that realm (alchemy.HERB_TIER_BY_REALM), as for Beast Cores.
# Material tier in a chest: a roll on equipments.CHEST_TIER_ODDS for that chest, as for gear.

def tier_for_realm(realm):
    return alchemy.GRADES.index(alchemy.HERB_TIER_BY_REALM[realm]) + 1


# ⛏️ Ore Vein encounter in /explore
ORE_VEIN_ENCOUNTER_CHANCE = 0.06    # DEFAULT; taken out of the common encounters so the total stays 1.0
ORE_VEIN = {"metal": (2, 4), "fuel_chance": 0.30, "metal_shard_chance": 0.10}

# Beasts: bindings + armor materials; essence of the beast's element
BEAST_DROPS = {
    "normal":     {"binding": (0.30, (1, 1)), "armor": (0.30, (1, 1)),     # DEFAULT (chance, (min, max))
                   "essence": {"shard": 0.08}},
    "elite":      {"binding": (0.60, (1, 2)), "armor": (0.60, (1, 2)),     # DEFAULT
                   "essence": {"crystal": 0.05}},
    "beast_king": {"binding": (1.00, (2, 3)), "armor": (1.00, (2, 3)),     # DEFAULT
                   "essence": {"heart": 0.02, "crystal": 0.20}},            # checked Heart first, then Crystal
}

# /gather: springs give quench liquid of your herb tier; Jade Shards
GATHER_SPRING_CHANCE = 0.08         # DEFAULT, per correct pick
GATHER_JADE_SHARD_CHANCE = 0.03     # DEFAULT, per correct pick

# Chests: artifact jades, Fortune Coin essence, Seal Stones
CHEST_JADE = {   # chance, (min, max) — tier rolled from equipments.CHEST_TIER_ODDS. DEFAULT
    "wooden": (0.15, (1, 2)), "bronze": (0.25, (1, 3)), "silver": (0.35, (2, 4)), "jade": (0.50, (3, 5)),
}
CHEST_FORTUNE = {   # grade → chance, checked Heart → Crystal → Shard. DEFAULT
    "wooden": {"shard": 0.05},
    "bronze": {"crystal": 0.01, "shard": 0.08},
    "silver": {"crystal": 0.04, "shard": 0.10},
    "jade":   {"heart": 0.01, "crystal": 0.10, "shard": 0.10},
}
CHEST_SEAL_STONE = {"wooden": 0.00, "bronze": 0.01, "silver": 0.03, "jade": 0.08}   # DEFAULT

# /craft: Cauldron Ash, more from higher-pattern pills. (min patterns, grade, qty), top to bottom. DEFAULT
CRAFT_ASH = [(9, "heart", 1), (7, "crystal", 1), (4, "shard", 2), (1, "shard", 1)]

# /practice and duplicate manuals: Insight Ink. DEFAULT
PRACTICE_INK_CHANCE = 0.15          # Insight Ink Shard per /practice session
DUPLICATE_MANUAL_INK = {"Mortal": "shard", "Yellow": "shard", "Mystic": "crystal", "Earth": "crystal", "Heaven": "heart"}

# /train and breakthroughs: Spirit Dew. DEFAULT
TRAINING_DEW_CHANCE = 0.15          # Spirit Dew Shard per /train session
BREAKTHROUGH_DEW = {"phase": "shard", "realm": "crystal"}   # on a successful breakthrough

# Seal Stones in the Moon Pearl shop
SEAL_STONE_PEARLS = 30              # DEFAULT

# ══ The /forge minigame ═══════════════════════════════════════════════

STAGES = ["ignite", "heat", "hammer", "quench", "inscribe"]
STAGE_NAMES = {"ignite": "🔥 Ignite the Forge", "heat": "🌡️ Heat the Metal", "hammer": "🔨 Hammer",
               "quench": "💧 Quench", "inscribe": "✨ Inscribe"}
STAGE_MAX_POINTS = 20               # 5 stages × 20 = 100
FAIL_BELOW = 50

# (minimum score, rarity), top to bottom
SCORE_TO_RARITY = [(98, "Mythical"), (93, "Legendary"), (85, "Epic"), (75, "Rare"), (65, "Uncommon"), (50, "Common")]

# "Inscribe counts most toward rarity": the top rarities also need a good inscription (points out of 20). DEFAULT
INSCRIBE_NEEDED = {"Epic": 12, "Legendary": 16, "Mythical": 19}

# Difficulty by gear tier. seconds: per decision · zone: Ignite safe zone (degrees) · misleading: chance a hint lies
# heat_rounds: Ignite rounds · strikes: hammer strikes · quench_window: Quench safe window (degrees)
# strokes: rune strokes to carve
DIFFICULTY = {
    "ordinary": {"name": "Normal",     "seconds": 6.0, "zone": 30, "misleading": 0.00, "heat_rounds": 3,
                 "strikes": 3, "quench_window": 40, "strokes": 3},
    "refined":  {"name": "Hard",       "seconds": 5.0, "zone": 25, "misleading": 0.00, "heat_rounds": 4,
                 "strikes": 4, "quench_window": 34, "strokes": 3},
    "spirit":   {"name": "Very Hard",  "seconds": 4.0, "zone": 20, "misleading": 0.15, "heat_rounds": 5,
                 "strikes": 5, "quench_window": 28, "strokes": 4},
    "treasure": {"name": "Extreme",    "seconds": 3.5, "zone": 15, "misleading": 0.25, "heat_rounds": 6,
                 "strikes": 6, "quench_window": 22, "strokes": 4},
    "divine":   {"name": "Super Hard", "seconds": 3.0, "zone": 12, "misleading": 0.35, "heat_rounds": 7,
                 "strikes": 7, "quench_window": 16, "strokes": 5},
}

# Stage 2: the metal's colours as it heats, and the colour each gear tier needs. DEFAULT targets
HEAT_COLORS = ["dull red", "cherry red", "orange", "yellow", "white"]
HEAT_TARGET = {"ordinary": "cherry red", "refined": "orange", "spirit": "orange", "treasure": "yellow",
               "divine": "white"}
HEAT_POINTS_BY_MISS = {0: 20, 1: 10}    # colours away from the target → points (further = 0). DEFAULT

# Stage 4: Water is fast and risky, Oil slow and safe. DEFAULT
QUENCH = {
    "water": {"max_points": 20, "window_mult": 0.7},
    "oil":   {"max_points": 15, "window_mult": 1.3},
}

# ── Stage rules (bot/forging.py plays them). DEFAULT numbers, tune freely ──
TIMER_GRACE_SECONDS = 1.0           # Discord round-trip allowance per decision, as in /craft
IDLE_TIMEOUT_SECONDS = 300

# 1 Ignite: heat 0–100, keep it inside a hidden safe zone of DIFFICULTY["zone"] degrees (+ fuel, rank, Steady Hand)
IGNITE = {"pump": 12, "vent": -12, "calm_drift": 5, "spike": (12, 18), "spike_chance": 0.30,
          "zone_from": 20, "zone_to": 85}

# 2 Heat: the metal starts dull red; each "keep heating" moves it one colour (past white it burns: 0 points)

# 3 Hammer: each strike the metal is in one state; the right answer for each
HAMMER_STATES = {
    "true":    {"hint": "The metal rings true under the hammer.", "answer": "hard"},
    "dull":    {"hint": "A dull thud: the metal is soft and spreading.", "answer": "light"},
    "cooling": {"hint": "It's cooling, the glow is fading.", "answer": "reheat"},
}

# 4 Quench: the blade cools from START each decision, by STEP (Wait) or SMALL_STEP (Wait a breath);
# plunge near the target temperature
QUENCH_TEMPS = {"start": (820, 900), "step": (30, 60), "small_step": (6, 12), "target": (420, 620)}
QUENCH_HALF_POINTS = 0.5            # inside the window but not its middle half: half the points
QUENCH_MISS_POINTS = 2              # outside the window

# 5 Inscribe: carve the rune stroke by stroke (DIFFICULTY["strokes"]); each pick shows 4 strokes
STROKES = ["horizontal", "vertical", "sweep", "press", "dot", "hook"]
STROKE_CHOICES = 4
RUNES = ["Sharpness", "Endurance", "Fortune", "Vitality", "Storms", "Shadows", "Rebirth", "Heaven"]

# ══ Blacksmith rank ═══════════════════════════════════════════════════

BLACKSMITH_RANK_EXP = dict(alchemy.ALCHEMIST_RANK_EXP)   # same curve as alchemist ranks
RANK_NEEDED = {"ordinary": 1, "refined": 2, "spirit": 4, "treasure": 6, "divine": 8}
RANK_RELIEF = {           # per rank above the requirement
    "seconds_bonus": 0.5,
    "zone_degrees": 2,    # Ignite zone and Quench window
    "max_ranks_counted": alchemy.RANK_RELIEF["max_ranks_counted"],
}
FORGE_BASE_EXP = dict(zip(TIERS, alchemy.CRAFT_BASE_EXP.values()))   # 10 / 25 / 60 / 150 / 400, as /craft
FAILED_FORGE_EXP = 0.20             # share of base EXP for a failed forge (like a /craft explosion)
RARITY_EXP_STEP = 0.10              # success: base × (1 + 0.1 × rarity step, Common = 0). DEFAULT
RANK_EXP_PENALTY = alchemy.RANK_EXP_PENALTY


def forge_exp(tier, rarity=None, ranks_above=0):
    """Blacksmith EXP for one forge. rarity None = failed."""
    base = FORGE_BASE_EXP[tier]
    exp = base * FAILED_FORGE_EXP if rarity is None else base * (1 + RARITY_EXP_STEP * RARITIES.index(rarity))
    for min_above, mult in RANK_EXP_PENALTY:
        if ranks_above >= min_above:
            return exp * mult
    return exp


# ══ Enchant / Reroll / Replace / Fail ═════════════════════════════════

ACTIONS = ["enchant", "reroll", "replace"]
# Enchant: fill an empty slot. Materials only. DEFAULT (the design gives coin costs for Reroll)
ENCHANT_COINS = {t: 0 for t in TIERS}
# Reroll: forge again, every slot gets a new random passive
REROLL_COINS = {"ordinary": 500, "refined": 2_000, "spirit": 8_000, "treasure": 30_000, "divine": 100_000}
# Replace: lock one slot with a Seal Stone and reroll the other (2-slot gear only)
REPLACE_TIERS = ["treasure", "divine"]
REPLACE_SEAL_STONES = 1
REPLACE_COIN_MULT = 2
FAIL_LOSES_ALL_MATERIALS = True     # essence, fuel and liquid included; the gear and its passives stay


def forge_coins(action, tier):
    if action == "enchant":
        return ENCHANT_COINS[tier]
    if action == "replace":
        return REROLL_COINS[tier] * REPLACE_COIN_MULT
    return REROLL_COINS[tier]


# ══ Picking the passive ═══════════════════════════════════════════════

def rarity_for_score(score, inscribe=STAGE_MAX_POINTS):
    """The rarity a score earns before caps; None = failed. A weak inscription holds back the top rarities."""
    rarity = next((r for need, r in SCORE_TO_RARITY if score >= need), None)
    while rarity in INSCRIBE_NEEDED and inscribe < INSCRIBE_NEEDED[rarity]:
        rarity = RARITIES[RARITIES.index(rarity) - 1]
    return rarity


def rarity_cap(tier, essence_grade=None):
    """Highest rarity for this gear tier and essence grade."""
    cap = RARITIES.index(PASSIVE_SLOTS[tier]["max_rarity"])
    if essence_grade:
        cap = min(cap, RARITIES.index(ESSENCE_GRADES[essence_grade]["max_rarity"]))
    return RARITIES[cap]


def capped_rarity(rarity, tier, essence_grade=None):
    if rarity is None:
        return None
    return RARITIES[min(RARITIES.index(rarity), RARITIES.index(rarity_cap(tier, essence_grade)))]


def essence_fits(gear, family):
    return gear in FAMILIES[family]["gear"]


def candidates(gear, rarity, family=None, exclude=()):
    """Passive keys of exactly this rarity (and family, if an essence is used), minus the excluded ones."""
    return [k for k, p in PASSIVES[gear].items()
            if p["rarity"] == rarity and (family is None or p["family"] == family) and k not in exclude]


def pick_passive(gear, tier, rarity, essence=None, exclude=(), rng=_random):
    """The passive a successful forge gives, or None if nothing fits.
    rarity: from rarity_for_score. essence: (family, grade) or None. exclude: passives the character already has
    (no duplicates). With an essence the passive comes only from its family; if the family has nothing left at the
    capped rarity, it falls to the best rarity below that does (never above)."""
    family, grade = essence if essence else (None, None)
    top = RARITIES.index(capped_rarity(rarity, tier, grade))
    for i in range(top, -1, -1):
        pool = candidates(gear, RARITIES[i], family, exclude)
        if pool:
            return rng.choice(pool)
    return None


def usable_essence(gear, tier, family, grade):
    """True when this essence can give at least one passive on this gear (e.g. a Blood Shard can't on weapons)."""
    if not essence_fits(gear, family):
        return False
    top = RARITIES.index(rarity_cap(tier, grade))
    return any(candidates(gear, RARITIES[i], family) for i in range(top + 1))
