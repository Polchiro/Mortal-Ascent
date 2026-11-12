"""The Appearance page (/appearance): pick Male or Female. Rules in bot/appearance.py."""
import looks

from bot import db

from .profile import number


def appearance_view(conn, user_id):
    """Everything appearance.html shows, or None when there is no character yet."""
    p = db.get_player(conn, user_id)
    if p is None:
        return None
    current = looks.of_player(p)
    start = current or {"gender": looks.DEFAULT_GENDER}
    cost = looks.change_cost(p)
    return {
        "current": current, "start": start,
        "current_text": looks.describe(current) if current else None,
        "genders": [{"key": k, "name": n, "thumb": looks.face({"gender": k}), "art": looks.portrait({"gender": k})}
                    for k, n in looks.GENDERS.items()],
        "cost": cost, "pearls": p["moon_pearls"], "pearls_text": number(p["moon_pearls"]),
        "coins": number(p["lotus_coins"]), "can_pay": p["moon_pearls"] >= cost,
        "change_pearls": looks.CHANGE_PEARLS,
    }
