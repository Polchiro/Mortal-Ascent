"""
Bag categories, item details for the Inspect panel, and which actions each item allows.

Adding a category later (Beast Cores, Rare Treasures, ...) means one entry in
CATEGORIES plus its details in `details()`. Actions only exist where the game
has rules for them:

    Open (chests) · Learn (manuals) · Take (Qi pills, Heaven-Defying Pill)
    Equip / Unequip (weapons, armor, artifacts) · Discard (anything not equipped, after a confirm)

Herbs and Beast Cores go into pills through /craft, so in the bag they can only be inspected or
discarded.
"""
from dataclasses import dataclass

import alchemy
import equipments
import explore
import technique
import training

from .. import combat, db, gear, loot
from .. import player as rules


@dataclass(frozen=True)
class Category:
    key: str
    label: str
    icon: str          # cards.theme.icon kind
    use_verb: str      # button label for the main action ("" = none)


CATEGORIES = {
    "chests": Category("chests", "Chests", "chest", "Open"),
    "manuals": Category("manuals", "Manuals", "scroll", "Learn"),
    "weapons": Category("weapons", "Weapons", "sword", "Equip"),
    "armor": Category("armor", "Armor", "seal:甲", "Equip"),
    "artifacts": Category("artifacts", "Artifacts", "seal:宝", "Equip"),
    "pills": Category("pills", "Pills", "pill", "Take"),
    "herbs": Category("herbs", "Herbs", "herb", ""),
    "materials": Category("materials", "Materials", "herb", ""),
}
ORDER = list(CATEGORIES)
GEAR = ("weapons", "armor", "artifacts")      # items you wear: Equip / Unequip

TIER_LABEL = {"wooden": "Wooden", "bronze": "Bronze", "silver": "Silver", "jade": "Jade"}
CHEST_ORDER = ["wooden", "bronze", "silver", "jade"]


def rarity(item):
    """(label, key into cards.theme.RARITY)."""
    cat, grade = item["category"], item.get("grade")
    if cat in GEAR:
        return grade.title(), grade
    if cat == "chests":
        return TIER_LABEL.get(item["key"], item["key"].title()), item["key"]
    if cat in ("manuals", "pills"):
        return f"{grade} Grade", grade
    if cat == "materials" and grade:
        return f"{grade} Grade", grade
    if cat == "herbs":
        return f"{(item.get('data') or {}).get('age', 10)}-year", grade
    return "Common", None


def item_icon(item):
    if item["category"] == "weapons":
        return (item.get("data") or {}).get("type") or item["key"]
    if item["category"] in ("armor", "artifacts"):
        return gear.icon_kind(item)
    return CATEGORIES[item["category"]].icon


def actions(item):
    """Action keys this item allows: use, unequip, discard."""
    out = []
    if item["category"] in GEAR and item["equipped"]:
        out.append("unequip")
    elif CATEGORIES[item["category"]].use_verb:
        out.append("use")
    if not item["equipped"]:
        out.append("discard")
    return out


def use_label(item):
    return CATEGORIES[item["category"]].use_verb


def details(item, player, learned_names=()):
    """What the Inspect panel shows: {name, qty, rarity, rarity_key, icon, kind, lines, effects, notes}."""
    cat = item["category"]
    label, key = rarity(item)
    lines, effects, notes = [], [], []
    if cat == "manuals":
        t = technique.TECHNIQUES[item["key"]]
        kind = f"{t['school']} {t['type']} manual"
        table = technique.ATTACK_TECHNIQUE if t["type"] == "attack" else technique.DEFENSE_TECHNIQUE
        power, passive = table[t["grade"]]
        lines.append(f"Teaches {t['name']}, a {t['grade']} grade {t['type']} technique of the {t['school']} school.")
        effects.append(f"×{power:.2f} damage when used" if t["type"] == "attack" else f"Blocks {power:.0%} when used")
        effects.append(f"+{passive:.0%} {'Attack' if t['type'] == 'attack' else 'Defense'} while equipped")
        if t.get("effect"):
            effects.append(technique_effect(t["effect"]))
        cd = combat.cooldown_turns(dict(t, stage=0))
        effects.append(f"Rests {cd} turn{'s' if cd > 1 else ''} after use")
        need = technique.GRADES[t["grade"]]
        if t["name"] in learned_names:
            notes.append(("Already learned: reading it again gives mastery EXP", "jade"))
        if rules.realm_index(player["realm"]) < rules.realm_index(need):
            notes.append((f"Needs {need} to comprehend", "red"))
    elif cat == "weapons":
        wtype = (item.get("data") or {}).get("type") or item["key"]
        kind = f"{wtype.title()} weapon"
        lines.append(f"A {label.lower()} tier {wtype}. Weapons only give stat buffs.")
        effects += [f"+{v:.1%} {rules.STAT_LABELS[k]}".replace(".0%", "%") for k, v in rules.weapon_buffs(item).items()]
        need = equipments.TIER_REALM_REQUIREMENT[item["grade"]]
        if item["equipped"]:
            notes.append(("Equipped", "gold"))
        if rules.realm_index(player["realm"]) < rules.realm_index(need):
            notes.append((f"Needs {need} to wield", "red"))
    elif cat == "armor":
        kind = f"{gear.armor_label(item)} armor"
        lines.append(f"A {label.lower()} tier {gear.armor_label(item).lower()}. Armor only gives stat buffs, "
                     "added to your weapon's and techniques'.")
        effects += [f"+{v:.1%} {rules.STAT_LABELS[k]}".replace(".0%", "%") for k, v in rules.weapon_buffs(item).items()]
        ok, need = gear.can_wield(player, item["grade"])
        if item["equipped"]:
            notes.append(("Equipped", "gold"))
        if not ok:
            notes.append((f"Needs {need} to wear", "red"))
    elif cat == "artifacts":
        spec = gear.family_spec(item)
        kind = f"{gear.GROUP_LABEL[spec['group']]} artifact · {gear.family(item).title()} family"
        lines.append(f"{spec['text']}. Every rarity of the {gear.family(item).title()} family has its "
                     "own name and a fixed power.")
        effects.append(gear.effect_text(item))
        if spec["group"] == "combat":
            effects.append(f"Fair Duels: {equipments.DUEL_COMBAT_ARTIFACT_STRENGTH:.0%} strength")
        effects.append("One artifact of each family at a time")
        ok, need = gear.can_wield(player, item["grade"])
        if item["equipped"]:
            notes.append((f"Equipped · artifact slot {item['equipped']}", "gold"))
        if not ok:
            notes.append((f"Needs {need} to wear", "red"))
    elif cat == "pills" and item["key"] == "heaven_defying":
        kind = "Fate-changing pill"
        lines.append("An ultra rare pill that defies the heavens themselves.")
        effects.append("Raises your talent by one rank (up to Divine)")
        notes.append(("Bound: cannot be traded", "gold"))
    elif cat == "pills":
        from ..crafting import KINDS, pill_info, pill_spec, toxicity_for
        pkind, grade, patterns = pill_info(item)
        e = alchemy.pattern_effect(patterns) if patterns else 1.0
        kind = KINDS[pkind][0] + (f" · {patterns} patterns" if patterns else "")
        spec = pill_spec(pkind, grade)
        if pkind == "qi":
            lines.append("Swallow it to speed up how fast your Internal Qi gathers.")
            effects.append(f"×{1 + (training.QI_PILLS[grade] - 1) * e:.2f} Qi Rate for "
                           f"{training.QI_PILL_DURATION_HOURS} hours")
        elif pkind == "burst":
            lines.append("Swallow it for a rush of Internal Qi at once.")
            effects.append(f"+{spec['hours'] * e:.1f} hours of your Qi Rate, instantly")
        elif pkind == "mending":
            lines.append("Knits wounds and shortens an injury.")
            effects.append("Cures any injury" if spec["injury_minutes"] is None
                           else f"Injury −{rules.fmt_duration(spec['injury_minutes'] * 60 * e)}")
        elif pkind == "cleansing":
            lines.append("Washes pill toxins out of the meridians.")
            effects.append(f"−{max(1, int(spec['toxicity_removed'] * e))} toxicity (adds none)")
        else:
            lines.append("Used automatically by /breakthrough at a realm gate, even if the attempt fails.")
            effects.append(f"+{training.BREAKTHROUGH_PILLS[grade] * e:.1%} realm breakthrough chance")
        if pkind in ("qi", "burst", "mending"):
            effects.append(f"+{toxicity_for(patterns) if patterns else 1} pill toxicity"
                           + (" (one Qi pill at a time)" if pkind == "qi" else ""))
        if pkind in ("qi", "burst") and grade != alchemy.HERB_TIER_BY_REALM[player["realm"]] and \
                alchemy.GRADES.index(grade) < alchemy.GRADES.index(alchemy.HERB_TIER_BY_REALM[player["realm"]]):
            notes.append(("Below your realm's grade: half effect", "red"))
    elif cat == "chests":
        tier = item["key"]
        kind = "Treasure chest"
        lines.append("Dropped by beasts. Open it for Lotus Coins and a chance at rarer finds.")
        effects.append(f"{explore.CHEST_MANUAL_CHANCE[tier]:.0%} chance of a technique manual")
        effects.append(f"{equipments.CHEST_WEAPON_CHANCE[tier]:.0%} chance of a weapon")
        effects.append(f"{equipments.CHEST_ARMOR_CHANCE[tier]:.0%} armor · {equipments.CHEST_ARTIFACT_CHANCE[tier]:.0%} artifact")
        lo, hi = loot.CHEST_COINS[tier]
        scale = rules.realm_scale(player["realm"])
        effects.append(f"{lo * scale:,}–{hi * scale:,} Lotus Coins")
    elif cat == "herbs":
        h = item.get("data") or {}
        type_, age, tier = h.get("type", "qi"), h.get("age", 10), h.get("tier", item.get("grade") or "Mortal")
        kind = f"{tier} {loot.TYPE_LABEL[type_]} herb"
        lines.append(alchemy.HERBS[tier][type_][1] + ".")
        uses = herb_uses(type_)
        effects.append("Goes into: " + ("every pill recipe" if len(uses) == len(PILL_KINDS) else ", ".join(uses)))
        a = alchemy.HERB_AGES[age]
        effects.append(f"{age}-year: " + (f"+{a['score_bonus']:.0%} craft score, " if a["score_bonus"] else "")
                       + f"up to {a['max_patterns']} pill patterns")
        notes.append(("Refine it with /craft", "jade"))
        notes.append(("The merchant does not buy herbs", "red"))
    elif item["key"].startswith("core:"):
        kind = "Beast Core"
        lines.append("The crystallised essence of a slain beast. Breakthrough pills need a core of their grade.")
        effects.append(f"Goes into: {item['grade']} Breakthrough pills")
    else:
        kind = "Material"
        lines.append("A crafting material.")
    return {"name": item["name"], "qty": item["qty"], "rarity": label, "rarity_key": key, "icon": item_icon(item),
            "kind": kind, "lines": lines, "effects": effects, "notes": notes,
            "equipped": bool(item["equipped"])}


PILL_KINDS = [("Qi pills", alchemy.QI_PILL_RECIPE), ("Qi Burst pills", alchemy.QI_BURST_RECIPE),
              ("Mending pills", alchemy.MENDING_RECIPE), ("Cleansing pills", alchemy.CLEANSING_RECIPE),
              ("Breakthrough pills", alchemy.BREAKTHROUGH_RECIPE)]


def herb_uses(type_):
    """Which kinds of pill use a herb of this type (alchemy.py recipes)."""
    return [name for name, recipe in PILL_KINDS if any(t == type_ for t, _ in recipe)]


def technique_effect(eff):
    kind, val = eff
    if kind == "combo":
        return f"Combo: {val[0]} hits × {val[1]:.0%}"
    if kind == "stagger":
        return "Stagger: opponent can't Guard next turn" if val >= 1 else f"Stagger: next block −{val:.0%}"
    if kind == "heavy":
        return f"Heavy ×{val} (rests 1 turn longer)"
    if kind == "unbreakable":
        return "Unbreakable: Break moves deal half damage"
    return f"{kind.title()} {val:.0%}"


def discard(conn, user_id, item_id, qty=1):
    """Throw away up to `qty` of an item. Returns (ok, message). Equipped items can't be discarded."""
    item = db.get_item(conn, user_id, item_id)
    if not item:
        return False, "That item is no longer in your bag."
    if item["equipped"]:
        return False, f"Unequip **{item['name']}** before discarding it."
    qty = min(qty, item["qty"])
    if not db.discard_item(conn, user_id, item_id, qty):
        return False, "That item changed in the meantime. Nothing was discarded."
    return True, f"🗑️ You discarded **{item['name']}**" + (f" ×{qty}" if qty > 1 else "") + "."
