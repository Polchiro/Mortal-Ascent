"""The Appearance page (/appearance): pick gender, hairstyle and hair colour. Rules in bot/appearance.py."""
import looks

from bot import db

from .profile import number


def appearance_view(conn, user_id):
    """Everything appearance.html shows, or None when there is no character yet."""
    p = db.get_player(conn, user_id)
    if p is None:
        return None
    current = looks.of_player(p)
    start = current or {"gender": "male", "hair": looks.HAIRSTYLES["male"][0][0], "color": "silver"}
    cost = looks.change_cost(p)
    return {
        "current": current, "start": start,
        "current_text": looks.describe(current) if current else None,
        "genders": list(looks.GENDERS.items()),
        "hairs": {g: [{"key": k, "name": n, "thumb": f"/look/{g}_{k}_silver_face.png"} for k, n in hs]
                  for g, hs in looks.HAIRSTYLES.items()},
        "colors": [{"key": k, "name": n, "swatch": "#%02x%02x%02x" % (rgb or (200, 200, 204))}
                   for k, (n, rgb) in looks.COLORS.items()],
        "cost": cost, "pearls": p["moon_pearls"], "pearls_text": number(p["moon_pearls"]),
        "coins": number(p["lotus_coins"]), "can_pay": p["moon_pearls"] >= cost,
        "change_pearls": looks.CHANGE_PEARLS,
    }
