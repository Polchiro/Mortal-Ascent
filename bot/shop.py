"""
The Moon Pearl shop and Heavenly Blessings without Discord: what is for sale, and buying it. Discord's /shop and
/blessing (bot/views.py) and the website's Moon Pavilion (web/pavilion_play.py) both use these, so a purchase is the
same everywhere. Prices and perks live in economy.py.
"""
import random
import time

import alchemy
import economy
import talent as talent_rules
import training

from . import db, loot
from . import player as rules


SHOP_ITEMS = {
    # key in economy.PEARL_SHOP: (label, description)
    "heavenly_fate_reroll":   ("🌟 Heavenly Fate Reroll", "Reroll your talent; it never goes lower"),
    "mortal_qi_pill_x3":      (f"💊 {alchemy.QI_PILLS['Mortal']['name']} ×3",
                               f"×{training.QI_PILLS['Mortal']:g} Qi Rate for {training.QI_PILL_DURATION_HOURS}h each"),
    "yellow_qi_pill_x3":      (f"💊 {alchemy.QI_PILLS['Yellow']['name']} ×3",
                               f"×{training.QI_PILLS['Yellow']:g} Qi Rate for {training.QI_PILL_DURATION_HOURS}h each"),
    "mystic_qi_pill_x1":      (f"💊 {alchemy.QI_PILLS['Mystic']['name']} ×1",
                               f"×{training.QI_PILLS['Mystic']:g} Qi Rate for {training.QI_PILL_DURATION_HOURS}h"),
    "inventory_expansion_20": ("🎒 Inventory Expansion", "+20 bag slots"),
    "name_change":            ("✏️ Name Change", "Change the name on your cards"),
    "seal_stone":             ("🔏 Seal Stone", "Locks one passive slot when you Replace in /forge"),
}
SHOP_PILLS = {"mortal_qi_pill_x3": ("Mortal", 3), "yellow_qi_pill_x3": ("Yellow", 3), "mystic_qi_pill_x1": ("Mystic", 1)}
SHOP_CARD_TEXT = {      # the short line under each item on the shop card
    "heavenly_fate_reroll": "Reroll your talent. It never goes lower",
    "inventory_expansion_20": "+20 bag slots",
    "name_change": "Change the name on your cards",
    "seal_stone": "Locks a passive slot in /forge Replace",
}


def shop_data(p):
    """The data for the shop card (cards/shop.py)."""
    items = []
    for key, (label, desc) in SHOP_ITEMS.items():
        name = label.split(" ", 1)[1]                    # drop the emoji
        text = SHOP_CARD_TEXT.get(key, desc)
        if key in SHOP_PILLS:
            grade, n = SHOP_PILLS[key]
            name = alchemy.QI_PILLS[grade]["name"]
            text = (f"{n} pills · " if n > 1 else "") + f"×{training.QI_PILLS[grade]:g} Qi Rate for " \
                f"{training.QI_PILL_DURATION_HOURS}h" + (" each" if n > 1 else "")
        price = economy.PEARL_SHOP[key]
        items.append({"key": key, "name": name, "price": f"{price:,}", "min_price": price,
                      "text": text, "icon": f"art:shop/{key}"})
    lo, hi = economy.PEARL_SHOP["profile_theme"]
    items.append({"key": "profile_theme", "name": "Profile Card Themes", "price": f"{lo}–{hi}", "min_price": lo,
                  "text": "New looks for your profile card", "icon": "art:shop/profile_theme", "soon": True})
    return {"pearls": p["moon_pearls"], "items": items}


def buy_shop_item(conn, user_id, key, new_name=None, rng=random):
    """Spend Moon Pearls on a shop item. Returns (message, announcement or None)."""
    p = db.get_player(conn, user_id)
    price = economy.PEARL_SHOP[key]
    if p["moon_pearls"] < price:
        return f"You need 🌙 {price:,} Moon Pearls but have 🌙 {p['moon_pearls']:,}.", None
    if key == "name_change" and not (new_name or "").strip():
        return "Please give a name.", None
    # Pay first: the spend fails (and nothing is given) if the pearls are gone by now.
    if db.spend(conn, user_id, "moon_pearls", price, f"Shop: {SHOP_ITEMS[key][0].split(' ', 1)[1]}") is None:
        return f"You need 🌙 {price:,} Moon Pearls but have 🌙 {p['moon_pearls']:,}.", None
    news = None
    if key in SHOP_PILLS:
        grade, qty = SHOP_PILLS[key]
        if not db.add_item(conn, user_id, **dict(loot.pill(grade), qty=qty)):
            db.change_currency(conn, user_id, "moon_pearls", price, "Refund: bag full")
            return "Your bag is full.", None
        msg = f"💊 {qty}× **{alchemy.QI_PILLS[grade]['name']}** added to your bag."
    elif key == "seal_stone":
        from . import materials
        loot.store(conn, user_id, [materials.material("seal")])
        msg = "🔏 A **Seal Stone** goes into your materials pouch."
    elif key == "inventory_expansion_20":
        db.update_player(conn, user_id, bag_capacity=p["bag_capacity"] + 20)
        msg = f"🎒 Your bag now holds **{p['bag_capacity'] + 20}** slots."
    elif key == "name_change":
        new_name = new_name.strip()[:32]
        db.update_player(conn, user_id, name=new_name)
        msg = f"✏️ You are now known as **{new_name}**."
    else:   # heavenly_fate_reroll
        new = rules.reroll_talent(p["talent"], talent_rules.HEAVENLY_FATE_REROLL["can_go_lower"], rng)
        db.update_player(conn, user_id, talent=new)
        msg = (f"🌟 The Aptitude Stone glows... **{new} Talent!**" if new != p["talent"]
               else f"🌟 The stone flickers and settles. You remain **{new}** (it never goes lower).")
        if new != p["talent"]:
            news = loot.talent_announcement(p["name"], new)
    return msg + f"\n🌙 −{price:,} Moon Pearls", news


BLESSING_EMOJI = {"Gentle Breeze": "🍃", "Spring Rain": "🌧️", "Bright Moon": "🌕", "Blazing Sun": "☀️",
                  "Rolling Thunder": "⚡", "Starfall": "🌠", "Heavenly Dragon": "🐉", "Eternal Dao": "☯️"}


def buy_blessing(conn, user_id, tier, now=None):
    """Same tier adds 30 days; a different tier replaces the current one with a fresh 30 days."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    price = economy.BLESSING_TIERS[tier]["price"]
    if p["moon_pearls"] < price:
        return f"You need 🌙 {price:,} Moon Pearls but have 🌙 {p['moon_pearls']:,}."
    days = economy.BLESSING_DURATION_DAYS * 86400
    current = rules.active_blessing(p, now)
    if current and current[0] == tier:
        expires = p["blessing_expires"] + days
        msg = f"{BLESSING_EMOJI[tier]} Your **{tier}** blessing is extended by {economy.BLESSING_DURATION_DAYS} days."
    else:
        expires = now + days
        msg = f"{BLESSING_EMOJI[tier]} Heaven smiles on you: **{tier}** for {economy.BLESSING_DURATION_DAYS} days!"
        if current:
            msg += f" (It replaces {current[0]}.)"
    if db.spend(conn, user_id, "moon_pearls", price, f"Blessing: {tier}") is None:
        return f"You need 🌙 {price:,} Moon Pearls but have 🌙 {p['moon_pearls']:,}."
    db.update_player(conn, user_id, blessing_tier=tier, blessing_expires=expires)
    return msg + f"\n🌙 −{price:,} Moon Pearls"


BLESSING_COLOR = {"Gentle Breeze": (120, 220, 190), "Spring Rain": (140, 190, 240), "Bright Moon": (240, 226, 160),
                  "Blazing Sun": (250, 160, 70), "Rolling Thunder": (250, 140, 60), "Starfall": (170, 140, 250),
                  "Heavenly Dragon": (90, 210, 130), "Eternal Dao": (190, 160, 250)}


def blessing_data(p, now=None):
    """The data for the blessings card (cards/blessings.py)."""
    from cards.art_icons import slug
    b = rules.active_blessing(p, now)
    short = {"Lotus Coins": "Coins", "Mastery EXP": "Mastery", "Chest Drops": "Chests", "Comprehension": "Insight"}
    def perks(tier):
        text = rules.blessing_perks(tier).replace("  ·  ", " · ")
        for k, v in short.items():
            text = text.replace(k, v)
        return text
    tiers = [{"name": tier, "price": t["price"], "perks": perks(tier),
              "icon": f"art:blessings/{slug(tier)}", "color": BLESSING_COLOR.get(tier, (220, 200, 140)),
              "active": bool(b and b[0] == tier), "days_left": b[1] if b and b[0] == tier else None}
             for tier, t in economy.BLESSING_TIERS.items()]
    return {"pearls": p["moon_pearls"], "active": b, "tiers": tiers, "days": economy.BLESSING_DURATION_DAYS}
