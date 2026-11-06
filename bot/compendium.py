"""
/index pages as plain data: section → tiers → pages of item tiles.

Every number comes from the game data modules (beasts.py, technique.py, equipments.py,
explore.py, training.py, alchemy.py, talent.py, bot/loot.py, bot/gear.py), like the old embed pages.
cards/compendium.py draws a page; text_version() gives the same page as text for under the card.

A page is a dict:
  section, section_label, tier (a tier key or "overview"), tier_label, tier_word (add "TIER" after it),
  seal, color (RGB), subtitle, intro
  strip: [(key, seal, short label, color)]: every tier of the section, for the strip under the header
  tiles: [{"glyph", "cjk" (glyph is a character, else a cards.theme.icon kind), "color", "name",
           "lines": [1-3 short lines], "badge": (label, colour) or None, "group", "found": search hit}]
  footer: where to find this tier
  page, pages: position when one tier spans several pages
"""
import difflib
from functools import lru_cache

import alchemy
import beasts as beast_rules
import equipments
import explore
import talent as talent_rules
import technique
import training

from cards import theme as T
from cards.technique_icons import tech_kind

from . import gear, loot
from . import player as rules
from .expedition import MERCHANT_HERB_PRICE, MERCHANT_PILL_PRICE
from .sheet.items import herb_uses, technique_effect
from .views import SHOP_PILLS

PER_PAGE = 9
OVERVIEW = "overview"

# ── shared helpers ────────────────────────────────────────────────────


def pct(x):
    """0.25 → '25%', 0.005 → '0.5%', 0.0005 → '0.05%'."""
    v = x * 100
    return f"{v:.0f}%" if v >= 1 and v == int(v) else f"{v:g}%"


def odds_text(odds, label=str):
    return " · ".join(f"{label(k)} {pct(v)}" for k, v in odds.items())


TIER_LABEL = {"normal": "Normal", "elite": "Elite", "beast_king": "Beast King"}
ROLE_TRAIT = {"brute": "tough, slower", "hunter": "fragile, deadly", "swift": "15% dodge",
              "armored": "double DEF"}
# Drawn emblems (cards/emblems.py) instead of seal characters; the tiles, strip and header draw these kinds
GRADE_SEAL = {g: f"emblem:grade:{g}" for g in ("Mortal", "Yellow", "Mystic", "Earth", "Heaven")}
TIER_SEAL = {t: f"emblem:rarity:{t}" for t in ("ordinary", "refined", "spirit", "treasure", "divine")}
OVERVIEW_SEAL = "emblem:book"

REALM_SHORT = {"Mortal": "Mortal", "Martial Apprentice": "Apprentice", "Martial Warrior": "Warrior",
               "Martial Expert": "Expert", "Martial Master": "Master", "Grand Martial Master": "Grand Master",
               "Martial Grandmaster": "Grandmaster", "Martial King": "King", "Martial Emperor": "Emperor",
               "Martial Ancestor": "Ancestor", "Martial Saint": "Saint"}
REALM_COLOR = dict(zip(rules.REALM_ORDER, [
    (170, 160, 150), (150, 190, 120), (96, 196, 110), (82, 186, 170), (90, 160, 240), (120, 130, 240),
    (178, 110, 228), (232, 196, 80), (246, 150, 50), (236, 90, 60), (250, 226, 180)]))
RANK_COLOR = {"normal": T.ASH, "elite": (178, 110, 228), "beast_king": (246, 196, 70)}
ROLE_ICON = {"brute": "fist", "hunter": "sword", "swift": "gear:feather", "armored": "shield"}

# Pill kinds are the tiers of the Pills section
PILL_KINDS = {
    "qi":           ("Qi", "emblem:pill:qi:Mystic", (110, 170, 240)),
    "burst":        ("Qi Burst", "emblem:pill:burst:Yellow", T.LOTUS),
    "mending":      ("Mending", "emblem:pill:mending:Earth", T.JADE),
    "cleansing":    ("Cleansing", "emblem:pill:cleansing:Mortal", (196, 214, 226)),
    "breakthrough": ("Breakthrough", "emblem:pill:breakthrough:Heaven", T.GLOW),
}
HERB_ICON_COLOR = {"qi": (110, 170, 240), "healing": T.JADE, "purity": (196, 214, 226), "breakthrough": T.GLOW}
DECOY_COLOR = (150, 200, 70)
HEAVEN_DEFYING = "emblem:pill:breakthrough:Heaven"


def tile(glyph, color, name, lines, cjk=True, badge=None, group=None):
    return {"glyph": glyph, "cjk": cjk, "color": color, "name": name, "lines": [l for l in lines if l][:3],
            "badge": badge, "group": group, "found": False}


def gear_tier_label(tier):
    return equipments.TIER_DISPLAY[tier].split(" ", 1)[1]


def gear_strip():
    return [(t, TIER_SEAL[t], gear_tier_label(t), T.RARITY[t]) for t in equipments.TIERS]


def grade_strip():
    return [(g, GRADE_SEAL[g], g, T.RARITY[g]) for g in technique.GRADES]


def realm_list(realms):
    """'Mortal, Apprentice' with the short realm names."""
    return ", ".join(REALM_SHORT[r] for r in realms)


def chest_list(chests):
    return " · ".join(f"{loot.CHEST_NAMES[c]}" + (f" {pct(p)}" if p is not None else "")
                      for c, p in chests)


# ── Beasts ────────────────────────────────────────────────────────────

def beast_multipliers(tier, role):
    """(hp, attack, defense) as multiples of a player at the same realm and layer (beast.md)."""
    t, r = beast_rules.BEAST_TIERS[tier], beast_rules.ROLES[role]
    hp = t["hp"] * r.get("hp", 1.0)
    atk = t["attack"] * r.get("attack", 1.0)
    dfn = atk * beast_rules.BEAST_DEFENSE_RATIO * r.get("defense", 1.0)
    return hp, atk, dfn


def beast_rank_text(tier):
    team = beast_rules.BEAST_TIERS[tier]["team_size"]
    return "Solo" if team == 1 else f"Hunt with {team}+"


def beasts_strip():
    return [(r, f"emblem:realm:{r}", REALM_SHORT[r], REALM_COLOR[r]) for r in rules.REALM_ORDER]


def beasts_page(realm):
    tiles = []
    for name, tier, role in beast_rules.BEASTS[realm]:
        hp, atk, dfn = beast_multipliers(tier, role)
        element = beast_rules.element_of(name)
        tiles.append(tile(f"emblem:beast:{realm}:{element}", T.ELEMENT_ACCENTS[element].rim, name, [
            f"{role.title()} ({ROLE_TRAIT[role]}) · {element}",
            f"HP ×{hp:.2g}  ATK ×{atk:.2g}  DEF ×{dfn:.2g}",
            f"{beast_rank_text(tier)} · chest {pct(explore.BEAST_CHEST[tier]['chance'])}",
        ], badge=(TIER_LABEL[tier], RANK_COLOR[tier])))
    return dict(
        tier_label=realm, tier_word=False,
        subtitle=f"Met in /explore as a {realm}",
        intro="Strength is a multiple of a cultivator at the same realm and layer.",
        tiles=tiles,
        footer="Elites and Beast Kings are hunted as a team from lairs in /explore. "
               "/bestiary shows the exact numbers against you.")


def beasts_overview():
    tiles = []
    for tier, spec in explore.BEAST_CHEST.items():
        t = beast_rules.BEAST_TIERS[tier]
        tiles.append(tile(f"emblem:beast_tier:{tier}", RANK_COLOR[tier],
                          TIER_LABEL[tier] + ("" if tier == "beast_king" else " beasts"), [
                              f"HP ×{t['hp']:g} · ATK ×{t['attack']:g}",
                              beast_rank_text(tier),
                              f"Chest {pct(spec['chance'])}: " + odds_text(spec["tiers"], lambda c: loot.CHEST_NAMES[c]),
                          ]))
    for role, trait in ROLE_TRAIT.items():
        r = beast_rules.ROLES[role]
        mult = " · ".join(f"{rules.STAT_LABELS[k]} ×{v:g}" for k, v in r.items() if k in rules.STAT_LABELS)
        tiles.append(tile(ROLE_ICON[role], T.GOLD, role.title(), [trait.capitalize(), mult], cjk=False))
    return dict(subtitle="Every beast, realm by realm",
                intro="Pick a realm in the menu. Strength is a multiple of a cultivator at the same realm and layer.",
                tiles=tiles,
                footer="Normal beasts appear in /explore. Elites and Beast Kings are hunted as a team from lairs.")


# ── Techniques ────────────────────────────────────────────────────────

def manual_chests(grade):
    return [(c, explore.CHEST_MANUAL_CHANCE[c] * odds[grade])
            for c, odds in explore.CHEST_MANUAL_GRADE_ODDS.items() if grade in odds]


def techniques_page(grade):
    tiles = []
    for t in technique.TECHNIQUES.values():
        if t["grade"] != grade:
            continue
        kind = "Attack" if t["type"] == "attack" else "Defense"
        tiles.append(tile(tech_kind(t["name"], t["school"]), T.RARITY[grade], t["name"], [
            f"{kind} · {t['school']}",
            technique_effect(t["effect"]) if t.get("effect") else "No special effect",
        ], cjk=False))
    skill, atk_passive = technique.ATTACK_TECHNIQUE[grade]
    block, def_passive = technique.DEFENSE_TECHNIQUE[grade]
    start = [s["name"] for s in rules.starting_techniques()] if grade == "Mortal" else []
    chests = manual_chests(grade)
    return dict(
        subtitle=f"Learn from {technique.GRADES[grade]}",
        intro=(f"Attack: ×{skill:g} skill damage, +{pct(atk_passive)} ATK. Defense: blocks {pct(block)}, "
               f"+{pct(def_passive)} DEF. Mastery EXP ×{technique.GRADE_EXP_MULTIPLIER[grade]:g}."),
        tiles=tiles,
        footer=("Found in " + chest_list(chests) if chests else "Not yet in the world")
               + (f". Every cultivator starts with {' and '.join(start)}." if start else ""))


def techniques_overview():
    tiles = []
    for grade, realm in technique.GRADES.items():
        skill, atk_passive = technique.ATTACK_TECHNIQUE[grade]
        block, def_passive = technique.DEFENSE_TECHNIQUE[grade]
        tiles.append(tile(GRADE_SEAL[grade], T.RARITY[grade], f"{grade} Manuals", [
            f"Learn from {realm}",
            f"Attack ×{skill:g} · +{pct(atk_passive)} ATK",
            f"Defense blocks {pct(block)} · +{pct(def_passive)} DEF",
        ], cjk=False))
    return dict(subtitle="Manuals by grade",
                intro="Attack and Defense manuals. Higher grades hit harder and need more mastery EXP.",
                tiles=tiles, footer="Manuals drop from chests: open them in /inventory.")


# ── Weapons, Armor, Artifacts ─────────────────────────────────────────

def buff_text(buffs):
    return " · ".join(f"+{round(lo * 100)}–{round(hi * 100)}% {rules.STAT_LABELS[s]}" if lo != hi
                      else f"+{round(lo * 100)}% {rules.STAT_LABELS[s]}" for s, (lo, hi) in buffs.items())


def gear_chests(chance, tier_odds, tier):
    """[(chest, chance this tier comes out of it)]"""
    return [(c, chance[c] * odds[tier]) for c, odds in tier_odds.items() if tier in odds]


def weapons_page(tier):
    tiles = [tile(w, T.RARITY[tier], equipments.WEAPON_NAMES[tier][w],
                  [w.title(), buff_text(equipments.WEAPON_BUFFS[w][tier])], cjk=False)
             for w in equipments.WEAPON_TYPES]
    return dict(
        subtitle=f"Equip from {equipments.TIER_REALM_REQUIREMENT[tier]}",
        intro="One weapon at a time. Buffs roll inside the range: Flawless, Fine or Cracked.",
        tiles=tiles,
        footer="Found in " + chest_list(gear_chests(equipments.CHEST_WEAPON_CHANCE, equipments.CHEST_TIER_ODDS, tier)))


def armor_page(tier):
    tiles = [tile("gear:" + a, T.RARITY[tier], equipments.ARMOR_NAMES[tier][a],
                  [equipments.ARMOR_TYPE_DISPLAY[a][1], buff_text(equipments.ARMOR_BUFFS[a][tier])], cjk=False)
             for a in equipments.ARMOR_TYPES]
    return dict(
        subtitle=f"Wear from {equipments.TIER_REALM_REQUIREMENT[tier]}",
        intro="One armor at a time. Its buffs add to your weapon's and techniques'.",
        tiles=tiles,
        footer="Found in " + chest_list(gear_chests(equipments.CHEST_ARMOR_CHANCE, equipments.CHEST_TIER_ODDS, tier)))


def artifacts_page(tier):
    i = equipments.TIERS.index(tier)
    tiles = []
    for group, label in gear.GROUP_LABEL.items():
        for fam, spec in equipments.ARTIFACT_FAMILIES.items():
            if spec["group"] == group:
                tiles.append(tile("gear:" + fam, T.RARITY[tier], spec["names"][i], [
                    f"{label} · {fam.title()}",
                    gear.effect_text({"category": "artifacts", "key": fam, "grade": tier}),
                ], cjk=False, group=label))
    return dict(
        subtitle=f"Equip from {equipments.TIER_REALM_REQUIREMENT[tier]}",
        intro=f"{equipments.ARTIFACT_SLOTS} slots. One effect each; two of one family can't be worn together.",
        tiles=tiles,
        footer="Found in " + chest_list(gear_chests(equipments.CHEST_ARTIFACT_CHANCE,
                                                    equipments.CHEST_ARTIFACT_TIER_ODDS, tier)))


def gear_overview(kind):
    """Weapons and Armor: one tile per tier."""
    chance = equipments.CHEST_WEAPON_CHANCE if kind == "weapons" else equipments.CHEST_ARMOR_CHANCE
    names = equipments.WEAPON_NAMES if kind == "weapons" else equipments.ARMOR_NAMES
    tiles = []
    for tier in equipments.TIERS:
        chests = gear_chests(chance, equipments.CHEST_TIER_ODDS, tier)
        tiles.append(tile(TIER_SEAL[tier], T.RARITY[tier], gear_tier_label(tier), cjk=False, lines=[
            f"From {equipments.TIER_REALM_REQUIREMENT[tier]}",
            f"e.g. {next(iter(names[tier].values()))}",
            "Chests: " + ", ".join(loot.CHEST_NAMES[c].split()[0] for c, _ in chests),
        ]))
    if kind == "weapons":
        intro = "One weapon at a time. Buffs roll inside the range: Flawless, Fine or Cracked."
        footer = "Weapon chance per chest: " + chest_list(equipments.CHEST_WEAPON_CHANCE.items())
    else:
        intro = "One armor at a time. Its buffs add to your weapon's and techniques'."
        footer = "Armor chance per chest: " + chest_list(equipments.CHEST_ARMOR_CHANCE.items())
    return dict(subtitle="By tier, with buffs", intro=intro, tiles=tiles, footer=footer)


def weapons_overview():
    return gear_overview("weapons")


def armor_overview():
    return gear_overview("armor")


def artifacts_overview():
    tiles = []
    for group, label in gear.GROUP_LABEL.items():
        for fam, spec in equipments.ARTIFACT_FAMILIES.items():
            if spec["group"] == group:
                lo = gear.effect_text({"category": "artifacts", "key": fam, "grade": equipments.TIERS[0]}, tiny=True)
                hi = gear.effect_text({"category": "artifacts", "key": fam, "grade": equipments.TIERS[-1]}, tiny=True)
                tiles.append(tile("gear:" + fam, T.GOLD, f"{fam.title()} family", [
                    f"{label} · {spec['text']}", f"Ordinary {lo} · Divine {hi}"], cjk=False, group=label))
    return dict(
        subtitle="Every family, by tier",
        intro=(f"{equipments.ARTIFACT_SLOTS} artifact slots, open from the start. Same realm needs as weapons. "
               f"Combat ones work at {pct(equipments.DUEL_COMBAT_ARTIFACT_STRENGTH)} in Fair Duels."),
        tiles=tiles,
        footer="Artifact chance per chest: " + chest_list(equipments.CHEST_ARTIFACT_CHANCE.items())
               + " (Treasure and Divine only in Jade Chests)")


# ── Chests ────────────────────────────────────────────────────────────

def chests_strip():
    return [(c, "chest", loot.CHEST_NAMES[c].split()[0], T.RARITY[c]) for c in loot.CHEST_NAMES]


def chest_sources(tier):
    src = []
    if tier in explore.TREASURE_CHEST_TIER:
        src.append(f"treasure finds in /explore ({pct(explore.TREASURE_CHEST_TIER[tier])})")
    for beast_tier, spec in explore.BEAST_CHEST.items():
        if tier in spec["tiers"]:
            src.append("Beast Kings" if beast_tier == "beast_king" else f"{TIER_LABEL[beast_tier]} beasts")
    return ", ".join(src)


def chests_page(chest):
    color = T.RARITY[chest]
    lo, hi = loot.CHEST_COINS[chest]
    tiles = [
        tile("lotus", T.LOTUS, "Lotus Coins", [f"{lo}–{hi} coins at Mortal", "Doubles with each realm"], cjk=False),
        tile("scroll", color, "Technique Manual", [f"{pct(explore.CHEST_MANUAL_CHANCE[chest])} chance",
                                                   odds_text(explore.CHEST_MANUAL_GRADE_ODDS[chest])], cjk=False),
        tile("sword", color, "Weapon", [f"{pct(equipments.CHEST_WEAPON_CHANCE[chest])} chance",
                                        odds_text(equipments.CHEST_TIER_ODDS[chest], str.title)], cjk=False),
        tile("gear:plate", color, "Armor", [f"{pct(equipments.CHEST_ARMOR_CHANCE[chest])} chance",
                                            odds_text(equipments.CHEST_TIER_ODDS[chest], str.title)], cjk=False),
        tile("gear:compass", color, "Artifact", [f"{pct(equipments.CHEST_ARTIFACT_CHANCE[chest])} chance",
                                                 odds_text(equipments.CHEST_ARTIFACT_TIER_ODDS[chest], str.title)],
             cjk=False),
    ]
    if chest == "jade":
        tiles.append(tile(HEAVEN_DEFYING, T.RARITY["Heaven"], "Heaven-Defying Pill",
                          [f"{pct(talent_rules.HEAVEN_DEFYING_PILL['jade_chest_chance'])} chance",
                           "Raises your talent one rank"], cjk=False))
    return dict(tier_label=loot.CHEST_NAMES[chest], tier_word=False, subtitle="Open it from /inventory",
                intro="Every roll is separate, so one chest can hold several things.",
                tiles=tiles, footer="From " + chest_sources(chest))


def chests_overview():
    tiles = []
    for chest, name in loot.CHEST_NAMES.items():
        lo, hi = loot.CHEST_COINS[chest]
        tiles.append(tile("chest", T.RARITY[chest], name, [
            f"{lo}–{hi} Lotus Coins",
            f"Manual {pct(explore.CHEST_MANUAL_CHANCE[chest])} · Weapon {pct(equipments.CHEST_WEAPON_CHANCE[chest])}",
            "From " + chest_sources(chest),
        ], cjk=False))
    return dict(subtitle="What each chest holds",
                intro="Open chests from /inventory. Coins shown are for Mortal and double with each realm.",
                tiles=tiles, footer="Pick a chest in the menu to see every drop and its odds.")


# ── Pills ─────────────────────────────────────────────────────────────

RANK_NAMES = {1: "1st", 2: "2nd", 3: "3rd"}
CRAFT_SOURCE = "/craft"


def rank_name(n):
    return f"{RANK_NAMES.get(n, f'{n}th')} Grade"


def first_realm(tier):
    """The first realm that finds (and can use) herbs and pills of this grade."""
    return next(r for r in rules.REALM_ORDER if alchemy.HERB_TIER_BY_REALM[r] == tier)


def recipe_text(grade, recipe, core=None):
    parts = [f"{n} {alchemy.HERBS[grade][t][0]}" for t, n in recipe]
    if core:
        parts.append("1 Beast King Core" if core == "beast_king" else f"1 {TIER_LABEL[core]} Beast Core")
    return " + ".join(parts)


def age_text(min_age):
    return "any age" if min_age <= 10 else f"{min_age}-year+"


def pill_sources(grade):
    shop = {g for g, _ in SHOP_PILLS.values()}
    src = []
    if grade in shop:
        src.append("/shop")
    if grade in MERCHANT_PILL_PRICE:
        src.append(f"merchants ({MERCHANT_PILL_PRICE[grade]} coins)")
    return src + [CRAFT_SOURCE]


def _injury(s):
    return "cures any injury" if s["injury_minutes"] is None else \
        f"injury −{rules.fmt_duration(s['injury_minutes'] * 60)}"


# kind → (table, recipe, name(grade, spec), effect(grade, spec), sources(grade) or None, core key, intro)
PILLS = {
    "qi": (alchemy.QI_PILLS, alchemy.QI_PILL_RECIPE, lambda g, s: s["name"],
           lambda g, s: f"×{training.QI_PILLS[g]:g} Qi Rate · from {REALM_SHORT[first_realm(g)]}", pill_sources, None,
           f"Swallow one from /inventory for a faster Qi Rate for {training.QI_PILL_DURATION_HOURS} hours. "
           "Only one works at a time; below your realm's grade it gives half."),
    "burst": (alchemy.QI_BURST_PILLS, alchemy.QI_BURST_RECIPE, lambda g, s: f"{g} Qi Burst Pill",
              lambda g, s: f"+{s['hours']} hours of Qi Rate at once", None, None,
              "Instant Internal Qi: hours of your Qi Rate in one swallow. Below your realm's grade: half the Qi."),
    "mending": (alchemy.MENDING_PILLS, alchemy.MENDING_RECIPE, lambda g, s: f"{g} Mending Pill",
                lambda g, s: f"Heals {pct(s['heal'])} HP · {_injury(s)}", None, None,
                "Heal HP and shorten an injury, so you can explore again sooner."),
    "cleansing": (alchemy.CLEANSING_PILLS, alchemy.CLEANSING_RECIPE, lambda g, s: f"{g} Cleansing Pill",
                  lambda g, s: f"−{s['toxicity_removed']} toxicity", None, None,
                  "Remove pill toxicity. They add none themselves."),
    "breakthrough": (alchemy.BREAKTHROUGH_PILLS, alchemy.BREAKTHROUGH_RECIPE, lambda g, s: f"{g} Breakthrough Pill",
                     lambda g, s: f"+{pct(training.BREAKTHROUGH_PILLS[g])} breakthrough chance", None, "core",
                     "Raises the chance of a realm breakthrough. One per attempt, used up even on a failure."),
}


def pills_strip():
    return [(k, seal, label, color) for k, (label, seal, color) in PILL_KINDS.items()]


def pills_page(kind):
    table, recipe, name, effect, sources, core_key, intro = PILLS[kind]
    tiles = []
    for grade, spec in table.items():
        core = spec.get(core_key) if core_key else None
        tiles.append(tile(f"emblem:pill:{kind}:{grade}", T.RARITY[grade], name(grade, spec), [
            effect(grade, spec),
            recipe_text(grade, recipe, core),
            f"{age_text(spec['min_age'])} herbs · {rank_name(spec['rank'])} Alchemist",
        ], cjk=False))
    footer = "Craft them in /craft from herbs of the pill's grade."
    if sources:
        shop = [g for g in table if "/shop" in sources(g)]
        merchant = " · ".join(f"{g} {p}" for g, p in MERCHANT_PILL_PRICE.items() if g in table)
        footer = (f"Buy in /shop ({', '.join(shop)})" if shop else "") \
            + (f", from merchants ({merchant} coins)" if merchant else "") + ", or craft them in /craft."
    if kind == "breakthrough":
        footer += " Crafted one difficulty harder, with a Seal the Core stage."
    return dict(tier_label=PILL_KINDS[kind][0] + " Pills", tier_word=False, subtitle="Effect, recipe, alchemist rank",
                intro=intro, tiles=tiles, footer=footer)


def pills_overview():
    tox = " · ".join(f"{t}+: ×{m:g}" for t, m in training.PILL_TOXICITY_PENALTY if t)
    patterns = " · ".join(f"{pct(score)}+: {n}" for score, n in alchemy.SCORE_TO_PATTERNS[::2])
    ranks = " · ".join(f"{RANK_NAMES.get(r, f'{r}th')} {exp:,}" for r, exp in alchemy.ALCHEMIST_RANK_EXP.items() if r > 1)
    cores = " · ".join(f"{loot.CORE_NAMES[t].replace(' Beast', '')} {pct(c)}" for t, c in alchemy.BEAST_CORE_DROP.items())
    tiles = [
        tile("skull", T.GLOW, "Pill toxicity", [f"Toxicity {tox}",
                                                f"Drops by 1 every {training.TOXICITY_DECAY_HOURS} hours"], cjk=False),
        tile("emblem:pill:qi:Earth:9", T.GOLD, "Pill patterns", cjk=False, lines=[f"1–9 from the craft score: {patterns}",
                                             f"Below {pct(alchemy.EXPLODE_BELOW)} the cauldron explodes",
                                             f"Effect ×{alchemy.pattern_effect(1):.2f} … ×{alchemy.pattern_effect(9):.2f};"
                                             " 8+ patterns add no toxicity"]),
        tile("gear:furnace", T.GOLD, "Alchemist rank", ["Everyone starts at 1st Grade", f"Total EXP: {ranks}"],
             cjk=False),
        tile("gear:qi", T.MOON, "Beast Cores", cjk=False, lines=["Breakthrough pills need one of their grade",
                                           f"Drops: {cores}", "Elite and King cores from team hunts"]),
        tile(HEAVEN_DEFYING, T.RARITY["Heaven"], "Heaven-Defying Pill", cjk=False, lines=[
            f"Raises talent one rank (up to {talent_rules.HEAVEN_DEFYING_PILL['max_talent']})",
            f"Jade Chests {pct(talent_rules.HEAVEN_DEFYING_PILL['jade_chest_chance'])} · cannot be traded"]),
    ]
    return dict(subtitle="Toxicity, patterns and rare pills",
                intro="Every pill you swallow adds toxicity; too much weakens the next ones.",
                tiles=tiles, footer="Craft pills in /craft from herbs you /gather. Pick a pill kind in the menu.")


# ── Herbs ─────────────────────────────────────────────────────────────

def herb_realms():
    tiers = {}
    for realm, tier in alchemy.HERB_TIER_BY_REALM.items():
        tiers.setdefault(tier, []).append(realm)
    return tiers


def herbs_page(grade):
    tiles = []
    for type_, (name, desc) in alchemy.HERBS[grade].items():
        uses = herb_uses(type_)
        tiles.append(tile("herb", HERB_ICON_COLOR.get(type_, T.JADE), name,
                          [f"{loot.TYPE_LABEL[type_]} herb" + (f" · {', '.join(uses)}" if uses else ""), desc],
                          cjk=False))
    for name, desc in alchemy.DECOYS[grade]:
        tiles.append(tile("skull", DECOY_COLOR, name, ["Poisonous look-alike", desc], cjk=False,
                          badge=("Poison", DECOY_COLOR)))
    realms = herb_realms()[grade]
    return dict(subtitle=f"Found from {realms[0]}", intro=f"Every recipe for a {grade} grade pill uses these.",
                tiles=tiles, footer=f"Gathered in /gather by {realm_list(realms)}. Look-alikes differ in one detail.")


def herbs_overview():
    lo, hi = alchemy.HERB_PATCH_HERBS
    streak = " · ".join(f"{s}+: ×{m:g}" for s, m in reversed(alchemy.STREAK_BONUS) if m > 1)
    ages = " · ".join(f"{age}y {pct(a['chance'])}" for age, a in alchemy.HERB_AGES.items())
    tiles = [
        tile("herb", T.JADE, "Pick the right plant", ["The bot names a herb and describes it",
                                                      f"Look-alike: −{pct(alchemy.DECOY_HP_LOSS)} HP, nothing gathered",
                                                      "Too slow: nothing gathered"], cjk=False),
        tile("hourglass", T.GOLD, "Time to pick", [" · ".join(f"{t} {s}s" for t, s in alchemy.GATHER_SECONDS.items())],
             cjk=False),
        tile("star", T.LOTUS, "Herb age", [ages, "Older herbs: better craft score, more patterns"], cjk=False),
        tile("flame", T.GLOW, "Herbal Insight", [f"Right picks in a row: {streak}",
                                                 "A wrong pick or a timeout resets it"], cjk=False),
        tile("skull", DECOY_COLOR, "Old herbs fight back", [
            f"{alchemy.OLD_HERB_FROM_AGE}-year+: {alchemy.OLD_HERB_CHOICES} choices, "
            f"{alchemy.OLD_HERB_SECONDS_LESS}s less", "Miss and it escapes"], cjk=False),
        tile("gear:focus", T.MOON, "Wandering Spirit", cjk=False, lines=[
            f"Every {alchemy.SPIRIT_CHECK_EVERY[0]}–{alchemy.SPIRIT_CHECK_EVERY[1]} gathers it asks a question",
            f"Miss {alchemy.SPIRIT_CHECK_FAILS_TO_PAUSE} in a row: pause {alchemy.SPIRIT_CHECK_PAUSE_MINUTES} min"]),
        tile("herb", T.ASH, "Herb types", [" · ".join(f"{loot.TYPE_LABEL[t]} {pct(c)}"
                                                      for t, c in alchemy.HERB_TYPE_CHANCE.items())], cjk=False),
        tile("chest", T.LOTUS, "Other sources", [f"Herb Patches in /explore: {lo}–{hi} herbs of your tier",
                                                 f"Merchants sell 10-year herbs ({MERCHANT_HERB_PRICE} coins)"],
             cjk=False),
    ]
    tiers = herb_realms()
    return dict(subtitle="How to /gather",
                intro="Use /gather as long as you like. Poisonous look-alikes differ in one detail.",
                tiles=tiles,
                footer="Herb tier by realm: " + " · ".join(f"{t} {REALM_SHORT[r[0]]}+"
                                                           for t, r in tiers.items())
                       + f". {pct(alchemy.LOWER_TIER_CHANCE)} are one tier lower.")


# ── sections ──────────────────────────────────────────────────────────

# key → (menu label, emoji, menu description, strip builder, tier page builder, overview builder)
SECTIONS = {
    "beasts":     ("Beasts", "🐾", "Every beast, realm by realm", beasts_strip, beasts_page, beasts_overview),
    "techniques": ("Techniques", "📜", "Manuals by grade, with effects", grade_strip, techniques_page,
                   techniques_overview),
    "weapons":    ("Weapons", "⚔️", "Weapons by tier, with buffs", gear_strip, weapons_page, weapons_overview),
    "armor":      ("Armor", "🥋", "Armor by tier, with buffs", gear_strip, armor_page, armor_overview),
    "artifacts":  ("Artifacts", "🔮", "Every artifact family and its power by tier", gear_strip, artifacts_page,
                   artifacts_overview),
    "chests":     ("Chests", "📦", "What each chest holds", chests_strip, chests_page, chests_overview),
    "pills":      ("Pills", "💊", "Every pill: effects, recipes, where to get them", pills_strip, pills_page,
                   pills_overview),
    "herbs":      ("Herbs", "🌿", "How to /gather, and every herb and look-alike", grade_strip, herbs_page,
                   herbs_overview),
}


def tiers(section):
    """[(key, seal, label, colour)] for the tier menu (Overview comes first, separately)."""
    return SECTIONS[section][3]()


def paginate(tiles, per_page=PER_PAGE):
    """Split tiles into pages, keeping a group (artifact Combat / Cultivation / Exploration) together
    when it fits on one page."""
    groups = []
    for t in tiles:
        if groups and groups[-1][0] == t.get("group"):
            groups[-1][1].append(t)
        else:
            groups.append((t.get("group"), [t]))
    pages, cur = [], []
    for _, items in groups:
        if cur and len(cur) + len(items) > per_page:
            pages.append(cur)
            cur = []
        while len(items) > per_page:
            pages.append(items[:per_page])
            items = items[per_page:]
        cur += items
    if cur or not pages:
        pages.append(cur)
    return pages


def build(section, tier):
    _, _, _, _, page_fn, overview_fn = SECTIONS[section]
    return overview_fn() if tier == OVERVIEW else page_fn(tier)


def tier_page(section, tier=OVERVIEW, page=0, found=None):
    """One page as data (see the module docstring). found: a tile name to light up (from /index search)."""
    label = SECTIONS[section][0]
    strip = tiers(section)
    data = build(section, tier)
    if tier == OVERVIEW:
        seal, short, color = OVERVIEW_SEAL, "Overview", T.GOLD
    else:
        _, seal, short, color = next(s for s in strip if s[0] == tier)
    chunks = paginate(data["tiles"])
    page = min(max(0, page), len(chunks) - 1)
    tiles = [dict(t, found=found is not None and t["name"] == found) for t in chunks[page]]
    return dict(section=section, section_label=label, tier=tier, tier_label=data.get("tier_label", short),
                tier_word=data.get("tier_word", tier != OVERVIEW), seal=seal, color=color, strip=strip,
                subtitle=data["subtitle"], intro=data.get("intro"), tiles=tiles, footer=data["footer"],
                page=page + 1, pages=len(chunks))


def text_version(p):
    """The same page as text, for copying and searching (shown under the card)."""
    head = f"**{p['section_label']} · {p['tier_label']}** · {p['subtitle']}"
    if p["pages"] > 1:
        head += f" · page {p['page']} of {p['pages']}"
    lines = [head]
    if p.get("intro"):
        lines.append(p["intro"])
    for t in p["tiles"]:
        badge = f" [{t['badge'][0]}]" if t.get("badge") else ""
        mark = "▶ " if t.get("found") else "• "
        lines.append(f"{mark}**{t['name']}**{badge}: " + " · ".join(t["lines"]))
    lines.append(p["footer"])
    return "\n".join(lines)


# ── search ────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def search_index():
    """{lower-case name: (section, tier, page, tile name)} for every item on every tier page,
    plus chests and pill kinds by name (they open their own page)."""
    out = {}
    for section in SECTIONS:
        for key, _, _, _ in tiers(section):
            for n, chunk in enumerate(paginate(build(section, key)["tiles"])):
                for t in chunk:
                    out.setdefault(t["name"].lower(), (section, key, n, t["name"]))
    for chest, name in loot.CHEST_NAMES.items():
        out[name.lower()] = ("chests", chest, 0, None)
    for kind, (label, _, _) in PILL_KINDS.items():
        out.setdefault(f"{label} pills".lower(), ("pills", kind, 0, None))
    return out


def search(query):
    """The best match for `query`: the exact name, else the shortest name that starts with or contains it,
    else the closest spelling. Returns (section, tier, page, tile name) or None."""
    q = " ".join(query.lower().split())
    if not q:
        return None
    idx = search_index()
    if q in idx:
        return idx[q]
    hits = sorted((k for k in idx if q in k), key=lambda k: (not k.startswith(q), len(k), k))
    if not hits:
        hits = difflib.get_close_matches(q, list(idx), n=1, cutoff=0.6)
    return idx[hits[0]] if hits else None


def search_names(query, limit=25):
    """Names for the search autocomplete (Discord shows at most 25)."""
    q = query.lower().strip()
    idx = search_index()
    names = sorted({v[3] or k.title() for k, v in idx.items()})
    if q:
        names = [n for n in names if q in n.lower()]
        names.sort(key=lambda n: (not n.lower().startswith(q), n))
    return names[:limit]
