"""
Choosing and changing a character's look (looks.py, docs/appearance.md). The first choice is free; every
change after that costs Moon Pearls. The look is a picture only: no stat, fight or reward depends on it.
"""
import looks

from . import db


def choose(conn, user_id, gender, hair, color):
    """Save a new look. Returns (ok, message)."""
    look = looks.clean(gender, hair, color)
    if look is None:
        return False, "Pick a gender, a hairstyle and a hair colour."
    p = db.get_player(conn, user_id)
    if p is None:
        return False, "No character yet."
    if looks.of_player(p) == look:
        return False, "That is already your look."
    cost = looks.change_cost(p)
    if cost and p["moon_pearls"] < cost:
        return False, f"Changing your look costs **{cost} Moon Pearls**. You have {p['moon_pearls']}."
    with conn:                           # only if nothing changed in between (two clicks can't pay twice)
        done = conn.execute("UPDATE players SET appearance = ?, appearance_changes = appearance_changes + 1 "
                            "WHERE user_id = ? AND appearance_changes = ?",
                            (looks.dump(look), user_id, p["appearance_changes"])).rowcount
    if not done:
        return False, "Your look changed in the meantime. Try again."
    if cost and db.spend(conn, user_id, "moon_pearls", cost, "Appearance change") is None:
        db.update_player(conn, user_id, appearance=p["appearance"],
                         appearance_changes=p["appearance_changes"])    # the pearls went elsewhere: undo
        return False, f"Changing your look costs **{cost} Moon Pearls**."
    paid = f" for {cost} Moon Pearls" if cost else ""
    return True, f"Your new look is set{paid}: {looks.describe(look)}."
