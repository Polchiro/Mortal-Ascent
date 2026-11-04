"""
Mastery EXP: gaining it (capped at a full bar) and mastery trials (docs/technique.md).

When a technique's EXP bar is full it stops gaining until the player passes a
trial: /spar against a stronger master. Passing raises the stage.
"""
import technique

from . import db
from . import player as rules


def gain(conn, player, tech, exp, bonus=True):
    """Give mastery EXP to `tech` (a techniques row dict, updated in place).
    Applies Blessing / Blessed Land bonuses when `bonus`. Returns (gained, note or None)."""
    if bonus:
        exp *= rules.mastery_bonus(player)
    exp = round(exp)
    cap = rules.mastery_cap(tech)
    if cap is not None:
        exp = max(0, min(exp, cap - tech["mastery_exp"]))
    if exp:
        db.add_mastery(conn, tech["id"], exp)
        tech["mastery_exp"] += exp
    note = None
    if rules.bar_full(tech):
        nxt = technique.MASTERY_STAGES[rules.stage_of(tech) + 1]["name"]
        note = f"🔔 **{tech['name']}** is ready for its trial to reach **{nxt}**. Use **/spar** on it."
    return exp, note


def pass_trial(conn, tech):
    tech["stage"] = rules.stage_of(tech) + 1
    db.set_mastery(conn, tech["id"], stage=tech["stage"])
    return technique.MASTERY_STAGES[tech["stage"]]["name"]
