"""
The inventory page's data. docs/web.md, "The inventory page".

Same bag as the bot's /inventory: the tabs, items and Inspect details all come from bot/sheet
(items.CATEGORIES, data.bag_items, items.details), so the website and Discord always agree.
This module only adds picture links and the counts per tab. Viewing only for now.
"""
import os

from bot import db
from bot.sheet import data as sheet
from bot.sheet import items

from .profile import ART_ROOT, art_url, number

RARITY_COLOR = {                       # the bag's rarity colours (cards/theme.py RARITY), as CSS
    "common": "#C9D2E6", "uncommon": "#6FD9B0", "rare": "#6FA8FF", "epic": "#B57BFF", "legendary": "#F5C35C",
    "mythic": "#FF6B6B", "mythical": "#FF6B6B",
    "ordinary": "#C9D2E6", "refined": "#6FD9B0", "spirit": "#6FA8FF", "treasure": "#B57BFF", "divine": "#F5C35C",
    "mortal": "#C9D2E6", "yellow": "#F5D04A", "mystic": "#6FA8FF", "earth": "#B57BFF", "heaven": "#F5C35C",
}
NOTE_COLOR = {"jade": "#7FE3BD", "red": "#FF9B90", "gold": "#F5DCA6"}


def item_picture(item):
    """The painted picture of a bag item, or None (the page then shows the category's emblem)."""
    if item["category"] == "chests":
        path = os.path.join(ART_ROOT, "chests", f"{item['key']}.png")
        return f"/art/chests/{item['key']}.png" if os.path.exists(path) else None
    if item["category"] == "manuals":
        return art_url(f"tech:{item['key']}")
    return art_url(items.item_icon(item))


def color(key):
    return RARITY_COLOR.get(str(key or "").lower(), "#C9D2E6")


def inventory_view(conn, user_id, category="weapons", selected_id=None):
    """Everything inventory.html shows, or None when this Discord account has no character yet."""
    p = db.get_player(conn, user_id)
    if p is None:
        return None
    if category.partition(":")[0] not in items.CATEGORIES:
        category = items.ORDER[0]
    found = sheet.bag_items(conn, user_id, category)
    learned = {t["name"] for t in db.get_techniques(conn, user_id, equipped_only=False)}
    counts = db.category_counts(conn, user_id)
    tiles = []
    for it in found:
        label, key = items.rarity(it)
        tiles.append({"id": it["id"], "name": it["name"], "qty": it["qty"], "picture": item_picture(it),
                      "rarity": label, "color": color(key), "equipped": bool(it["equipped"]),
                      "selected": it["id"] == selected_id})
    chosen = next((it for it in found if it["id"] == selected_id), found[0] if found else None)
    for t in tiles:
        t["selected"] = chosen is not None and t["id"] == chosen["id"]
    inspect = None
    if chosen:
        d = items.details(chosen, p, learned)
        inspect = {"name": d["name"], "qty": d["qty"], "rarity": d["rarity"], "color": color(d["rarity_key"]),
                   "kind": d["kind"], "lines": d["lines"], "effects": d["effects"],
                   "notes": [(text, NOTE_COLOR.get(tone, "#F5DCA6")) for text, tone in d["notes"]],
                   "picture": item_picture(chosen)}
    tabs = [{"key": c.key, "label": c.label, "count": counts.get(c.key, 0), "active": c.key == category,
             "picture": tab_picture(c.key)} for c in items.CATEGORIES.values()]
    return {"name": p["name"], "coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"]),
            "category": category, "label": items.CATEGORIES[category].label, "tabs": tabs, "tiles": tiles,
            "inspect": inspect, "used": db.slots_used(conn, user_id), "capacity": p["bag_capacity"]}


TAB_ART = {"chests": "/art/chests/rare.png", "weapons": "index/weapons_spirit", "armor": "index/armor_spirit",
           "artifacts": "index/artifacts_spirit", "herbs": "index/herbs_mystic", "materials": "index/materials_refined",
           "pills": "index/pills_qi", "manuals": "tech/iron_fist"}


def tab_picture(key):
    art = TAB_ART.get(key)
    if not art:
        return None
    if art.startswith("/"):
        return art
    return art_url(f"art:{art}")
