"""
Data for the /breakthrough result card (cards/breakthrough.py).
"""
import training

from . import player as rules

GOLD, JADE, RED, ASH, MOON = (244, 206, 120), (120, 230, 180), (255, 120, 100), (200, 210, 230), (186, 214, 255)


def card_data(name, before, after, kind, target, success, chance, pill=None, dew=None, avatar=None, seed=None):
    """before / after: the player dict before and after the attempt. pill: the Breakthrough pill used (or None).
    dew: the materials a success gave."""
    if kind == "realm":
        frm, to = before["realm"], target
    else:
        frm, to = rules.phase_for(before["layer"]), target
    facts = []
    if success:
        facts.append(("emblem:realm:" + after["realm"] if kind == "realm" else "star",
                      f"{rules.ordinal(after['layer'])} Layer", f"{after['realm']}"))
        carried = before["qi"] - rules.qi_needed(before["realm"], before["layer"]) + rules.overflow(before)
        if carried >= 1:
            facts.append(("flame", f"+{carried:,.0f} Qi", "flooded in"))
        for d in dew or []:
            facts.append(("mat:" + d["key"], d["name"].replace(" Essence", ""), "Heaven's dew"))
    else:
        lost = before["qi"] * training.BREAKTHROUGH_FAIL_QI_LOSS
        facts.append(("flame", f"−{lost:,.0f} Qi", "lost to the backlash" if kind == "realm" else "scattered"))
        if kind == "realm":
            facts.append(("heart", f"{training.INJURY_HOURS}h injury", "no explore or spar"))
        facts.append(("star", f"{rules.breakthrough_chance(after) or chance:.0%}", "chance next time"))
    if pill:
        facts.append(("emblem:pill:breakthrough:" + (pill.get("grade") or "Mortal"), pill["name"].replace(" Pill", ""),
                      "dissolved into your meridians" if success else "used up"))
    color = {True: GOLD if kind == "realm" else JADE, False: RED if kind == "realm" else ASH}[success]
    return {"name": name, "kind": kind, "success": success, "chance": chance, "from": frm, "to": to,
            "facts": [(i, v, l, color) for i, v, l in facts[:3]], "avatar": avatar,
            "seed": seed if seed is not None else int(before.get("breakthroughs", 0) * 7 + before["layer"])}
