"""
Placing and resetting Strength / Vitality / Spirit points. docs/attributes.md.

How many points a player has comes from their realm and layer (player.attribute_points); only the placed ones
are stored. Both /attributes in Discord and the website's profile go through these two functions.
"""
import stats

from . import db
from . import player as rules


def place(conn, user_id, strength=0, vitality=0, spirit=0):
    """Put unspent points into Strength, Vitality and Spirit. Returns (ok, message)."""
    try:
        s, v, sp = int(strength), int(vitality), int(spirit)
    except (TypeError, ValueError):
        return False, "Pick how many points to place."
    if s < 0 or v < 0 or sp < 0 or s + v + sp == 0:
        return False, "Pick how many points to place."
    p = db.get_player(conn, user_id)
    if p is None:
        return False, "No character yet."
    free = rules.unspent_points(p)
    if s + v + sp > free:
        return False, f"You only have **{free}** point{'s' if free != 1 else ''} to place."
    with conn:                           # only if nobody placed points in between (two clicks at once)
        done = conn.execute("UPDATE players SET strength = strength + ?, vitality = vitality + ?, spirit = spirit + ? "
                            "WHERE user_id = ? AND strength = ? AND vitality = ? AND spirit = ?",
                            (s, v, sp, user_id, p["strength"], p["vitality"], p["spirit"])).rowcount
    if not done:
        return False, "Your points changed in the meantime. Try again."
    parts = [x for x in (f"+{s} Strength" if s else "", f"+{v} Vitality" if v else "",
                         f"+{sp} Spirit" if sp else "") if x]
    return True, "You place " + (", ".join(parts[:-1]) + " and " + parts[-1] if len(parts) > 1 else parts[0]) + "."


def reset_cost(player):
    """Moon Pearls the next reset costs (0 while free resets are left)."""
    return 0 if (player.get("attribute_resets") or 0) < stats.FREE_ATTRIBUTE_RESETS else stats.ATTRIBUTE_RESET_PEARLS


def reset(conn, user_id):
    """Take every placed point back. The first is free, then it costs Moon Pearls. Returns (ok, message)."""
    p = db.get_player(conn, user_id)
    if p is None:
        return False, "No character yet."
    if not (p["strength"] or p["vitality"] or p["spirit"]):
        return False, "You have no placed points to reset."
    cost = reset_cost(p)
    if cost and p["moon_pearls"] < cost:
        return False, f"A reset costs **{cost} Moon Pearls**. You have {p['moon_pearls']}."
    with conn:                           # clear first, only if nothing changed (two clicks can't pay twice)
        done = conn.execute("UPDATE players SET strength = 0, vitality = 0, spirit = 0, "
                            "attribute_resets = attribute_resets + 1 WHERE user_id = ? AND strength = ? AND vitality = ? "
                            "AND spirit = ? AND attribute_resets = ?",
                            (user_id, p["strength"], p["vitality"], p["spirit"], p["attribute_resets"])).rowcount
    if not done:
        return False, "Your points changed in the meantime. Try again."
    if cost and db.spend(conn, user_id, "moon_pearls", cost, "Attribute reset") is None:
        db.update_player(conn, user_id, strength=p["strength"], vitality=p["vitality"], spirit=p["spirit"],
                         attribute_resets=p["attribute_resets"])          # the pearls went elsewhere: undo
        return False, f"A reset costs **{cost} Moon Pearls**."
    back = p["strength"] + p["vitality"] + p["spirit"]
    paid = f" for {cost} Moon Pearls" if cost else " (your free reset)"
    return True, f"Your body is remade{paid}: **{back}** points are free to place again."
