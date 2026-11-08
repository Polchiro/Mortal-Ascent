"""
Plain data for the Forge Hall card (cards/forge.render_forge), built from a running Forge.

Only reads the game: it never changes a rule or a number. What the card shows of the hidden parts follows the
text the player sees: the fire follows the (maybe misleading) heat text, the metal glows at the shown colour,
and the Ignite safe zone is never drawn.
"""
import forge

from . import gear as gear_rules
from . import materials, passives
from .craft_card import plain

ACTION_WORD = {"enchant": "Enchant", "reroll": "Reroll", "replace": "Replace"}


def gear_icon(item):
    """The theme.icon kind for a weapon (its type), armor or artifact (its drawing)."""
    if item["category"] == "weapons":
        return item["key"]
    return gear_rules.icon_kind(item)


def _gear(plan):
    item = plan.item
    slots = passives.slots(item)
    if plan.action == "enchant":
        where = f"slot {slots.index(None) + 1}" if None in slots else ""
    elif plan.action == "replace":
        where = f"slot {plan.lock + 1} locked"
    else:
        where = "all slots" if len(slots) > 1 else ""
    sub = " · ".join(x for x in (f"{item['grade'].title()} {plan.gear}", ACTION_WORD[plan.action], where) if x)
    return {"name": item["name"], "tier": item["grade"], "icon": gear_icon(item), "sub": sub, "kind": plan.gear}


def _materials(plan):
    return [{"icon": "mat:" + key, "name": materials.MATERIALS[key]["name"], "qty": qty} for key, qty in plan.uses]


def _stages(g):
    out = []
    for i, key in enumerate(forge.STAGES):
        if key in g.points:
            state = "done"
        elif i == g.stage_i and not g.done:
            state = "current"
        else:
            state = "todo"
        out.append({"key": key, "state": state, "points": g.points.get(key)})
    return out


def _bonus(g):
    b = g.bonuses
    parts = []
    if b["fuel"] or b["steady"] or b["rank"]:
        deg = b["fuel"] + b["steady"] + b["rank"] * forge.RANK_RELIEF["zone_degrees"]
        parts.append(f"+{deg}° zone")
    if b["liquid"]:
        parts.append(f"+{b['liquid']}° quench")
    secs = b["swift"] + b["rank"] * forge.RANK_RELIEF["seconds_bonus"]
    if secs:
        parts.append(f"+{secs:g}s")
    return ", ".join(parts)


def _score(g):
    return {"total": g.score(), "fail_below": forge.FAIL_BELOW, "left": len(forge.STAGES) - len(g.points),
            "bonus": _bonus(g)}


def _cap(plan):
    grade = materials.MATERIALS[plan.essence]["grade"] if plan.essence else None
    return forge.rarity_cap(plan.tier, grade)


def _passive_forecast(plan):
    lines = [plain(materials.MATERIALS[plan.essence]["name"]) if plan.essence else "Any family",
             "Epic+ needs a fine rune"]
    return {"rarity": None, "cap": _cap(plan), "head": f"Up to {_cap(plan)}", "lines": lines}


WARNINGS = {
    "ignite": ("Keep the fire in the hidden safe zone", "Pump to heat, Vent to cool. Read the omen: gusts and draughts "
                                                         "move the heat after you act."),
    "heat": ("Pull the metal out at the right colour", "Too early or too late loses points. Past white, it burns."),
    "hammer": ("Read the metal before each strike", "Rings true: strike hard · dull thud: strike light · fading glow: "
                                                     "reheat."),
    "quench_choose": ("Choose the quench", "Water: narrow window, up to 20 points. Oil: wide window, up to 15."),
    "quench": ("Plunge at the right temperature", "Wait cools it a lot, Wait a breath a little. Too cold and the "
                                                  "quench fails."),
    "inscribe": ("Carve the strokes in order", "Inscribe counts most: Epic and above need a near-perfect rune."),
}


def card_data(plan, g, outcome=None, seed=None):
    """Plain data for render_forge. outcome: finish_forge's dict once the forge is over."""
    data = {
        "accent": "forge",
        "seed": seed if seed is not None else g.decisions + 1,
        "gear": _gear(plan),
        "stages": _stages(g),
        "materials": _materials(plan),
        "score": _score(g),
        "passive": _passive_forecast(plan),
        "done": g.done,
        "corner": {"seconds": f"{g.seconds:g}s to choose", "difficulty": g.diff["name"]},
        "warning_icon": "forge:anvil",
    }
    if g.done:
        return _result(plan, g, data, outcome or {})
    pr = g.prompt()
    st = pr.stage
    v = pr.view
    data["mode"] = st
    data["warning"] = WARNINGS[st]
    if g.log:                                     # the last decision's outcome goes on the bar
        data["warning"] = (plain(g.log[-1]), WARNINGS[st][0])
    if st == "ignite":
        data.update(heat=v["heat"], heat_state=v["state"], zone_width=g.zone_width)
        data["corner"]["label"] = f"ROUND {v['round'] + 1} / {v['rounds']}"
        data["warning_icon"] = "flame"
        if not g.log:
            data["warning"] = (plain(pr.lines[3]), WARNINGS[st][1])
    elif st == "heat":
        data.update(color=v["color"], target=v["target"], color_name=forge.HEAT_COLORS[v["color"]],
                    target_name=forge.HEAT_COLORS[v["target"]])
        data["corner"]["label"] = "HEAT"
        data["warning_icon"] = "forge:ingot"
    elif st == "hammer":
        data.update(metal=v["metal"], strike=v["strike"], strikes=v["strikes"],
                    hint=forge.HAMMER_STATES[v["metal"]]["hint"], struck=bool(g.log) and v["strike"] > 0)
        data["corner"]["label"] = f"STRIKE {v['strike'] + 1} / {v['strikes']}"
        data["warning_icon"] = "forge:hammer"
    elif st == "quench":
        data.update(temp=v["temp"], medium=v.get("medium"), target=v.get("target"), window=v.get("window"))
        data["corner"]["label"] = "QUENCH"
        data["warning_icon"] = "forge:quench"
        if v.get("medium") is None and not g.log:
            data["warning"] = WARNINGS["quench_choose"]
        elif not g.log:
            data["warning"] = WARNINGS["quench"]
    else:
        data.update(rune=v["rune"], clue=v["clue"], carved=len(v["carved"]), strokes=len(g.order),
                    carved_ok=list(g.carved_ok))
        data["corner"]["label"] = f"STROKE {len(v['carved']) + 1} / {len(g.order)}"
        data["warning_icon"] = "forge:chisel"
    return data


def _result(plan, g, data, outcome):
    data["corner"]["label"] = "DONE"
    data["corner"]["seconds"] = None
    exp = outcome.get("exp")
    rank = f" · {outcome['rank_up']} Blacksmith!" if outcome.get("rank_up") else ""
    if outcome.get("rarity"):
        data["mode"] = "success"
        changed = outcome.get("changed") or []
        first = forge.PASSIVES[plan.gear][changed[0][1]] if changed else None
        rarity = first["rarity"] if first else outcome["rarity"]
        data["result"] = {"rarity": rarity, "passive": first["name"] if first else None,
                          "text": first["text"] if first else "No new passive could take hold."}
        lines = []
        for _, key in changed[1:]:
            ps = forge.PASSIVES[plan.gear][key]
            lines.append(f"+ {ps['name']} ({ps['rarity']})")
        if first:
            lines.insert(0, plain(first["text"]))
        data["passive"] = {"rarity": rarity, "head": first["name"] if first else rarity, "lines": lines}
        article = "an" if rarity[0] in "AEIOU" else "a"
        data["warning"] = (f"The forge sings: {article} {rarity} passive!" if first else "The forge sang, but nothing "
                           "new took hold.", (f"+{exp:,} blacksmith EXP" if exp is not None else "") + rank)
        data["warning_icon"] = f"passive:{rarity}"
    else:
        data["mode"] = "failed"
        data["lost"] = not outcome.get("refunded")
        title = outcome.get("title") or "The forge failed"
        data["result"] = {"title": title.rstrip("."), "saved": "Second Chance saved the materials."
                          if outcome.get("refunded") else None}
        data["passive"] = {"rarity": None, "head": "No passive", "lines": ["The gear and its", "passives are safe."]}
        data["warning"] = (title, (f"+{exp:,} blacksmith EXP" if exp is not None else "") + rank)
        data["warning_icon"] = "skull"
    return data
