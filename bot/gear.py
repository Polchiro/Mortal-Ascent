"""
Armor and artifacts (docs/equipment.md "Armor" and "Artifacts"). Every number comes from equipments.py.

Armor works like a weapon: one slot, rolled % buffs that add to the stats.md totals.
Artifacts: two slots, open from the start. Each belongs to a family with one effect and a fixed
value per tier; two artifacts of the same family can't be worn together.

Equipped artifacts reach the rules through the player dict: db.get_player() puts
{effect key: value} under "artifact_fx", and artifact_bonus(player, key) reads it. That way every
system that already has the player (Qi Rate, toxicity, /craft, /gather, mastery, /explore, coins,
cores and the fight engines) can apply its artifact without new plumbing.
"""
import equipments

ARMOR, ARTIFACTS, WEAPONS = "armor", "artifacts", "weapons"
GROUP_LABEL = {"combat": "Combat", "cultivation": "Cultivation", "exploration": "Exploration"}

# Short effect line for sockets and lists. {v} is the family's value for that tier (from equipments.py).
EFFECT_SHORT = {
    "strike_vs_break_damage": "+{pct} dmg when Strike beats Break",
    "charged_damage_reduction": "−{pct} charged attack damage",
    "guard_reflect": "Reflects {pct} of guarded damage",
    "break_stagger_chance": "{pct} chance Break staggers",
    "heal_per_turn": "Heals {pct} max HP each turn",
    "dodge_chance": "{pct} chance to dodge a hit",
    "cooldown_reset_chance": "{pct} chance a cooldown resets",
    "qi_rate": "+{pct} Internal Qi Rate",
    "toxicity_decay_faster": "Toxicity fades {pct} faster",
    "craft_zone_degrees": "+{deg} heat safe zone in /craft",
    "old_herb_chance": "+{pct} old herbs in /gather",
    "mastery_exp": "+{pct} technique mastery EXP",
    "explore_luck": "+{pct} better chests and rare finds",
    "lotus_coins": "+{pct} Lotus Coins from fights and chests",
    "beast_core_chance": "+{pct} Beast Core chance",
}
# Even shorter, for the Profile sockets
EFFECT_TINY = {
    "strike_vs_break_damage": "+{pct} Strike>Break",
    "charged_damage_reduction": "−{pct} charged dmg",
    "guard_reflect": "{pct} Guard reflect",
    "break_stagger_chance": "{pct} Break stagger",
    "heal_per_turn": "+{pct} HP/turn",
    "dodge_chance": "{pct} dodge",
    "cooldown_reset_chance": "{pct} cooldown reset",
    "qi_rate": "+{pct} Qi Rate",
    "toxicity_decay_faster": "{pct} faster detox",
    "craft_zone_degrees": "+{deg} heat zone",
    "old_herb_chance": "+{pct} old herbs",
    "mastery_exp": "+{pct} mastery EXP",
    "explore_luck": "+{pct} explore luck",
    "lotus_coins": "+{pct} Lotus Coins",
    "beast_core_chance": "+{pct} Beast Cores",
}


def _fmt(template, value):
    pct = f"{value * 100:g}%"
    return template.format(pct=pct, deg=f"{value:g}°")


def family(item):
    return (item.get("data") or {}).get("family") or item["key"]


def family_spec(item_or_family):
    key = item_or_family if isinstance(item_or_family, str) else family(item_or_family)
    return equipments.ARTIFACT_FAMILIES[key]


def artifact_value(item):
    return equipments.artifact_value(family(item), item["grade"])


def effect_text(item, tiny=False):
    """'+15% Internal Qi Rate' for an artifact item."""
    spec = family_spec(item)
    return _fmt((EFFECT_TINY if tiny else EFFECT_SHORT)[spec["effect"]], artifact_value(item))


def armor_type(item):
    return (item.get("data") or {}).get("type") or item["key"]


def armor_seal(item):
    return equipments.ARMOR_TYPE_DISPLAY[armor_type(item)][0]


def armor_label(item):
    return equipments.ARMOR_TYPE_DISPLAY[armor_type(item)][1]


def seal(item):
    """The character shown on an armor or artifact tile / socket."""
    return armor_seal(item) if item["category"] == ARMOR else family_spec(item)["seal"]


def icon_kind(item):
    """cards.theme.icon kind: the drawn armor type or artifact family (cards/gear_icons.py), e.g. 'gear:robe'."""
    return "gear:" + (armor_type(item) if item["category"] == ARMOR else family(item))


# ── Effects ───────────────────────────────────────────────────────────

def artifact_effects(artifacts, groups=None, scale=1.0):
    """{effect key: value} for these equipped artifacts. groups: only these families' groups.
    Each family can be worn once, so every effect appears at most once."""
    out = {}
    for a in artifacts:
        spec = family_spec(a)
        if groups and spec["group"] not in groups:
            continue
        out[spec["effect"]] = out.get(spec["effect"], 0) + artifact_value(a) * scale
    return out


def artifact_bonus(player, effect):
    """The value of an equipped artifact effect for this player (0 when none is worn)."""
    return (player or {}).get("artifact_fx", {}).get(effect, 0)


def combat_fx(player, scale=1.0):
    """Combat artifact effects for a fight; scale = equipments.DUEL_COMBAT_ARTIFACT_STRENGTH in Fair Duels."""
    combat = {spec["effect"] for spec in equipments.ARTIFACT_FAMILIES.values() if spec["group"] == "combat"}
    return {k: v * scale for k, v in (player or {}).get("artifact_fx", {}).items() if k in combat}


# ── Equipping ─────────────────────────────────────────────────────────

def can_wield(player, tier):
    """(ok, realm needed): same realm requirement per tier as weapons."""
    from . import player as rules
    need = equipments.TIER_REALM_REQUIREMENT[tier]
    return rules.realm_index(player["realm"]) >= rules.realm_index(need), need


def equip_problem(player, item, worn_artifacts):
    """Why this armor / artifact can't be equipped now, or None."""
    ok, need = can_wield(player, item["grade"])
    what = "armor" if item["category"] == ARMOR else "artifact"
    if not ok:
        return f"You must reach **{need}** to wear a {item['grade'].title()} {what}."
    if item["equipped"]:
        return f"**{item['name']}** is already equipped."
    if item["category"] == ARTIFACTS:
        fam = family(item)
        same = [a for a in worn_artifacts if family(a) == fam]
        if len(same) >= equipments.ARTIFACT_SAME_FAMILY_LIMIT:
            spec = family_spec(fam)
            return (f"You already wear a {spec['seal']} {fam.title()} artifact (**{same[0]['name']}**). "
                    "Two of the same family can't be worn together.")
        if len(worn_artifacts) >= equipments.ARTIFACT_SLOTS:
            return ("Both artifact slots are full. Unequip one first "
                    "(Equipment tab, or pick it in the Artifacts tab of your bag).")
    return None


def free_artifact_slot(worn_artifacts):
    used = {a["equipped"] for a in worn_artifacts}
    return next((s for s in range(1, equipments.ARTIFACT_SLOTS + 1) if s not in used), None)
