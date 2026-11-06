"""
Gear passives (docs/forge.md): where they are stored and how the rules read them. Every number comes from forge.py.

A weapon, armor or artifact keeps its passives in item data["passives"]: one entry per slot
(forge.PASSIVE_SLOTS), a passive key or None for an empty slot.

Worn artifact passives reach the rules through the player dict, like artifact effects: db.get_player() puts
{passive key: fx dict} under "artifact_passives", and artifact_passive(player, key, fx) reads one number.
"""
import forge

GEAR_KIND = {"weapons": "weapon", "armor": "armor", "artifacts": "artifact"}


def gear_kind(item):
    return GEAR_KIND.get(item["category"])


def slots(item):
    """The item's passive slots: a list as long as its tier allows, None for empty."""
    n = forge.PASSIVE_SLOTS[item["grade"]]["slots"]
    have = list((item.get("data") or {}).get("passives") or [])
    return (have + [None] * n)[:n]


def spec(item, key):
    return forge.PASSIVES[gear_kind(item)][key]


def worn_passives(items):
    """Every passive on these worn items, each counted once (no duplicates on one character)."""
    out = []
    for it in items:
        if not gear_kind(it):
            continue
        for k in slots(it):
            if k and k not in out:
                out.append(k)
    return out


def artifact_passives(artifacts):
    """{passive key: fx} for worn artifacts, each passive once."""
    out = {}
    for a in artifacts:
        for k in slots(a):
            if k and k not in out:
                out[k] = forge.PASSIVES["artifact"][k]["fx"]
    return out


def artifact_passive(player, key, fx=None):
    """The number a worn artifact passive gives (0 when not worn). fx: which number of the passive (default: its
    first one)."""
    got = (player or {}).get("artifact_passives", {}).get(key)
    if not got:
        return 0
    return got[fx] if fx else next(iter(got.values()))


def has_artifact_passive(player, key):
    return key in (player or {}).get("artifact_passives", {})


def label(key, gear):
    p = forge.PASSIVES[gear][key]
    return f"{forge.RARITY_EMOJI[p['rarity']]} {p['name']}"
