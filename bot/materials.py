"""
Forging materials (docs/forge.md section 4): building material items and rolling every drop source.

Materials are bag items of category "materials" (like Beast Cores) keyed by their forge key
(base:weapon:3, binding:2, essence:blood:shard, fuel:1, liquid:4, seal) and stack by type.
They don't use bag slots (forge.MATERIALS_USE_BAG_SLOTS). Every number comes from forge.py.

Every roll_* function returns a list of material items (possibly empty). `bonus` is the Prospector
artifact passive: every chance is raised by that share (Part 4 passes it in).
"""
import random

import beasts
import equipments
import forge

from . import loot

MATERIALS = forge.all_materials()
KIND_EMOJI = {"base": "⛏️", "binding": "🦴", "essence": "✨", "fuel": "🔥", "liquid": "💧", "seal": "🔏"}
GROUPS = [("base", "Base"), ("binding", "Bindings"), ("essence", "Essences"), ("fuel_liquid", "Fuel & Liquids")]


def is_forge_material(item):
    return item["category"] == "materials" and item["key"] in MATERIALS


def group_of(key):
    """Inventory group: base / binding / essence / fuel_liquid (the Seal Stone sits with fuel and liquids)."""
    kind = MATERIALS[key]["kind"]
    return "fuel_liquid" if kind in ("fuel", "liquid", "seal") else kind


def material(key, qty=1):
    """A material item ready for loot.store."""
    m = MATERIALS[key]
    grade = m.get("grade") or (str(m["tier"]) if "tier" in m else None)
    return {"category": "materials", "key": key, "name": m["name"], "grade": grade, "qty": qty,
            "data": {k: v for k, v in m.items() if k != "name"}}


def icon_kind(key):
    """cards.theme.icon kind of a material."""
    return "mat:" + key


def _chance(p, bonus):
    return p * (1 + bonus)


def _grade_roll(odds, rng, bonus):
    """odds: {grade: chance} checked in the order given (rarest first). Returns a grade or None."""
    for grade, p in odds.items():
        if rng.random() < _chance(p, bonus):
            return grade
    return None


def _count(lo_hi, rng):
    lo, hi = lo_hi
    return rng.randint(lo, hi)


# ── sources ───────────────────────────────────────────────────────────

def roll_ore_vein(realm, rng=random, bonus=0.0):
    """⛏️ Ore Vein in /explore: 2–4 weapon metal of your tier, maybe a fuel and a Metal Shard."""
    t, spec = forge.tier_for_realm(realm), forge.ORE_VEIN
    out = [material(forge.material_key("base", t, gear="weapon"), _count(spec["metal"], rng))]
    if rng.random() < _chance(spec["fuel_chance"], bonus):
        out.append(material(forge.material_key("fuel", t)))
    if rng.random() < _chance(spec["metal_shard_chance"], bonus):
        out.append(material(forge.material_key("essence", family="metal", grade="shard")))
    return out


def family_of_element(element):
    return next((f for f, s in forge.FAMILIES.items() if s["element"] == element), None)


def roll_beast(beast_tier, realm, beast_name=None, rng=random, bonus=0.0):
    """A beaten beast: bindings and armor materials of the beast's realm tier, and maybe an essence of its element."""
    t, spec = forge.tier_for_realm(realm), forge.BEAST_DROPS[beast_tier]
    out = []
    for part, key in (("binding", forge.material_key("binding", t)),
                      ("armor", forge.material_key("base", t, gear="armor"))):
        chance, qty = spec[part]
        if rng.random() < _chance(chance, bonus):
            out.append(material(key, _count(qty, rng)))
    family = family_of_element(beasts.element_of(beast_name)) if beast_name else None
    if family:
        grade = _grade_roll(spec["essence"], rng, bonus)
        if grade:
            out.append(material(forge.material_key("essence", family=family, grade=grade)))
    return out


def roll_gather(realm, rng=random, bonus=0.0):
    """A correct /gather pick: maybe a spring's quench liquid of your tier, maybe a Jade Shard."""
    t = forge.tier_for_realm(realm)
    out = []
    if rng.random() < _chance(forge.GATHER_SPRING_CHANCE, bonus):
        out.append(material(forge.material_key("liquid", t)))
    if rng.random() < _chance(forge.GATHER_JADE_SHARD_CHANCE, bonus):
        out.append(material(forge.material_key("essence", family="jade", grade="shard")))
    return out


def roll_chest(chest_tier, rng=random, bonus=0.0):
    """Extra chest contents: artifact jade (tier rolled like gear), Fortune Coin essence, Seal Stone."""
    out = []
    chance, qty = forge.CHEST_JADE[chest_tier]
    if rng.random() < _chance(chance, bonus):
        tier = equipments.TIERS.index(loot.pick(equipments.CHEST_TIER_ODDS[chest_tier], rng)) + 1
        out.append(material(forge.material_key("base", tier, gear="artifact"), _count(qty, rng)))
    grade = _grade_roll(forge.CHEST_FORTUNE[chest_tier], rng, bonus)
    if grade:
        out.append(material(forge.material_key("essence", family="fortune", grade=grade)))
    if rng.random() < _chance(forge.CHEST_SEAL_STONE[chest_tier], bonus):
        out.append(material("seal"))
    return out


def craft_ash(patterns):
    """Cauldron Ash from a finished pill (none from an explosion)."""
    if patterns <= 0:
        return []
    for min_patterns, grade, qty in forge.CRAFT_ASH:
        if patterns >= min_patterns:
            return [material(forge.material_key("essence", family="cauldron_ash", grade=grade), qty)]
    return []


def roll_practice_ink(rng=random, bonus=0.0):
    if rng.random() < _chance(forge.PRACTICE_INK_CHANCE, bonus):
        return [material(forge.material_key("essence", family="insight", grade="shard"))]
    return []


def duplicate_manual_ink(manual_grade):
    grade = forge.DUPLICATE_MANUAL_INK[manual_grade]
    return [material(forge.material_key("essence", family="insight", grade=grade))]


def roll_training_dew(rng=random, bonus=0.0):
    if rng.random() < _chance(forge.TRAINING_DEW_CHANCE, bonus):
        return [material(forge.material_key("essence", family="spirit_dew", grade="shard"))]
    return []


def breakthrough_dew(kind):
    """kind: 'phase' or 'realm' (a successful breakthrough)."""
    return [material(forge.material_key("essence", family="spirit_dew", grade=forge.BREAKTHROUGH_DEW[kind]))]


def lines(items):
    """Story lines for found materials."""
    return [f"{KIND_EMOJI[MATERIALS[i['key']]['kind']]} **{i['name']}**" + (f" ×{i['qty']}" if i["qty"] > 1 else "")
            for i in items]
