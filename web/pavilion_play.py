"""
The Moon Pavilion (docs/web.md "The Moon Pavilion"): the Moon Pearl shop and the Heavenly Blessings on the website,
kept by Pavilion Keeper Yue in town. Everything is the bot's own (bot/shop.py, the same code as Discord's /shop and
/blessing): what is for sale, the prices (economy.py) and what a purchase does. The page only asks first, showing
the price and your pearls before and after, like Discord's confirm.
"""
import economy

from bot import db
from bot import player as rules
from bot import shop

from .profile import art_url

SOON = {"profile_theme"}            # shown, not sold yet (as on Discord)


def _rgb(c):
    return "#%02X%02X%02X" % tuple(c)


def view(conn, uid, now=None):
    p = db.get_player(conn, uid)
    if p is None:
        return None
    pearls = p["moon_pearls"]
    items = []
    for it in shop.shop_data(p)["items"]:
        price = it["min_price"]
        note = None
        if it["key"] == "inventory_expansion_20":
            note = f"Your bag: {p['bag_capacity']} → {p['bag_capacity'] + 20} slots"
        elif it["key"] == "heavenly_fate_reroll":
            note = f"Your talent now: {p['talent']}. The new roll is never lower"
        items.append({"key": it["key"], "name": it["name"], "text": it["text"], "price": it["price"],
                      "cost": price, "icon": art_url(it["icon"]), "soon": it.get("soon", False),
                      "afford": pearls >= price, "note": note, "asks_name": it["key"] == "name_change"})
    b = shop.blessing_data(p, now)
    active = b["active"]
    tiers = []
    for t in b["tiers"]:
        if active and active[0] == t["name"]:
            note = f"Adds {b['days']} days to your {t['name']} ({active[1]} days left now)"
        elif active:
            note = (f"Replaces your {active[0]} ({active[1]} days left) with a fresh {b['days']} days. "
                    "The days left are not refunded")
        else:
            note = f"{b['days']} days"
        tiers.append({"name": t["name"], "price": f"{t['price']:,}", "cost": t["price"], "perks": t["perks"],
                      "icon": art_url(t["icon"]), "color": _rgb(t["color"]), "active": t["active"],
                      "days_left": t["days_left"], "afford": pearls >= t["price"], "note": note,
                      "frame": list(economy.BLESSING_TIERS).index(t["name"])
                      >= list(economy.BLESSING_TIERS).index(economy.BLESSING_FRAME_FROM)})
    return {"pearls": pearls, "coins": p["lotus_coins"], "items": items, "tiers": tiers, "days": b["days"],
            "active": {"name": active[0], "days": active[1], "perks": rules.blessing_perks(active[0])} if active else None}


def buy(conn, uid, key, new_name=None):
    """(ok, message) through bot/shop.buy_shop_item. The talent announcement is Discord's; it is not sent from here."""
    if key not in economy.PEARL_SHOP or key in SOON:
        return False, "That isn't for sale."
    if key == "name_change" and not (new_name or "").strip():
        return False, "Please give a name."
    before = db.get_player(conn, uid)["moon_pearls"]
    msg, _ = shop.buy_shop_item(conn, uid, key, new_name)
    return db.get_player(conn, uid)["moon_pearls"] < before, msg


def bless(conn, uid, tier, now=None):
    if tier not in economy.BLESSING_TIERS:
        return False, "That blessing doesn't exist."
    before = db.get_player(conn, uid)["moon_pearls"]
    msg = shop.buy_blessing(conn, uid, tier, now)
    return db.get_player(conn, uid)["moon_pearls"] < before, msg
