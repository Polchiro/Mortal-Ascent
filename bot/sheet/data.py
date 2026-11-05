"""
Card data for the Character Sheet tabs, built from the database.

Each function returns a plain dict that one card in cards/ draws. Keeping the
game rules here and the drawing in cards/ means the cards can be tested (and
previewed by scripts/render_cards.py) with made-up data.
"""
import math
import time

import economy
import equipments
import technique

from .. import combat, db
from .. import player as rules
from . import attributes, items

BAG_COLS, BAG_ROWS = 4, 3
BAG_PER_PAGE = BAG_COLS * BAG_ROWS
TECH_PER_PAGE = 6

CURRENCY_STYLE = {"lotus_coins": ("lotus", (236, 176, 92)), "moon_pearls": ("pearl", (150, 186, 236))}


def technique_view(t):
    """One learned technique as the cards show it."""
    info = rules.TECH_BY_NAME.get(t["name"], {})
    table = technique.ATTACK_TECHNIQUE if t["type"] == "attack" else technique.DEFENSE_TECHNIQUE
    power, passive = table[t["grade"]]
    m = rules.mastery_mult(t)
    stage = rules.stage_of(t)
    cap = rules.mastery_cap(t)
    power_txt = (f"×{power * m:.2f} damage" if t["type"] == "attack"
                 else f"Blocks {min(technique.MAX_DAMAGE_BLOCKED, power * m):.0%}")
    return {
        "id": t["id"], "name": t["name"], "type": t["type"], "grade": t["grade"],
        "school": info.get("school", "Body"),
        "stage": stage, "stage_name": technique.MASTERY_STAGES[stage]["name"],
        "exp": t["mastery_exp"], "cap": cap, "trial_ready": rules.bar_full(t),
        "effect": items.technique_effect(info["effect"]) if info.get("effect") else "No special effect",
        "power": power_txt,
        "passive": f"+{passive * m:.1%} {'Attack' if t['type'] == 'attack' else 'Defense'}".replace(".0%", "%"),
        "cooldown": combat.cooldown_turns(t),
        "equipped": bool(t["equipped"]),
    }


def technique_slots(player, learned):
    """The equipped sockets (technique.md): Attack, Defense, and Flex from Martial Warrior."""
    equipped = [t for t in learned if t["equipped"]]
    atk = [t for t in equipped if t["type"] == "attack"]
    dfn = [t for t in equipped if t["type"] == "defense"]
    flex_open = rules.technique_slots(player["realm"]) >= 3
    extra = atk[1:] + dfn[1:]
    return [
        {"slot": "Attack", "icon": "fist", "tech": technique_view(atk[0]) if atk else None, "locked": False},
        {"slot": "Defense", "icon": "shield", "tech": technique_view(dfn[0]) if dfn else None, "locked": False},
        {"slot": "Flex", "icon": "star", "tech": technique_view(extra[0]) if (flex_open and extra) else None,
         "locked": not flex_open, "note": "Opens at Martial Warrior" if not flex_open else "Attack or defense"},
    ]


def weapon_view(weapon):
    if not weapon:
        return None
    return {"id": weapon["id"], "name": weapon["name"], "tier": weapon["grade"],
            "type": (weapon.get("data") or {}).get("type") or weapon["key"],
            "buffs": [f"+{v:.1%} {rules.STAT_LABELS[k]}".replace(".0%", "%")
                      for k, v in rules.weapon_buffs(weapon).items()]}


def header(player, username=None):
    return {"name": player["name"], "username": username, "talent": player["talent"], "realm": player["realm"],
            "phase": rules.phase_for(player["layer"]), "layer": player["layer"],
            "max_layer": rules.max_layer(player["realm"])}


def profile_data(conn, user_id, username=None, private=True, now=None):
    """private=False when someone else looks: their coins stay hidden."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    learned = db.get_techniques(conn, user_id, equipped_only=False)
    equipped = [t for t in learned if t["equipped"]]
    weapon = db.equipped_weapon(conn, user_id)
    return dict(
        header(p, username),
        rank=db.server_rank(conn, user_id, rules.REALM_ORDER),
        attributes=attributes.attribute_values(p, equipped, weapon),
        qi=attributes.qi_resource(p, equipped, now),
        hp=attributes.hp_resource(p, equipped, weapon, now),
        slots=technique_slots(p, learned),
        learned_count=len(learned),
        weapon=weapon_view(weapon),
        coins=p["lotus_coins"] if private else None,
        pearls=p["moon_pearls"] if private else None,
        beasts=p["beasts_slain"], breakthroughs=p["breakthroughs"], failed=p["failed_breakthroughs"],
        status=rules.status_text(p, now),
        avatar_bytes=None,
    )


def purse_data(conn, user_id, now=None):
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    currencies = []
    for key in db.CURRENCY_COLUMNS:            # only currencies that are live (economy.md hides the rest)
        c = economy.CURRENCIES[key]
        icon, color = CURRENCY_STYLE[key]
        currencies.append({"key": key, "name": c["name"], "amount": p[key], "icon": icon, "color": color,
                           "note": "Premium · tradeable" if c.get("premium") else "Main money · tradeable"})
    b = rules.active_blessing(p, now)
    return dict(
        header(p),
        currencies=currencies,
        blessing={"tier": b[0], "days_left": b[1], "perks": rules.blessing_perks(b[0])} if b else None,
        ledger=[{"currency": r["currency"], "delta": r["delta"], "balance": r["balance"], "reason": r["reason"],
                 "ago": ago(now - r["at"])} for r in db.ledger(conn, user_id, 8)],
    )


def ago(seconds):
    seconds = max(0, seconds)
    for size, unit in ((86400, "d"), (3600, "h"), (60, "m")):
        if seconds >= size:
            return f"{int(seconds // size)}{unit} ago"
    return "just now"


def bag_items(conn, user_id, category):
    return db.get_items(conn, user_id, category)


def bag_data(conn, user_id, category, page=1, selected_id=None):
    """Returns (data, items on this page, pages, selected item or None)."""
    p = db.get_player(conn, user_id)
    all_items = bag_items(conn, user_id, category)
    learned = {t["name"] for t in db.get_techniques(conn, user_id, equipped_only=False)}
    pages = max(1, math.ceil(len(all_items) / BAG_PER_PAGE))
    page = min(max(1, page), pages)
    page_items = all_items[(page - 1) * BAG_PER_PAGE: page * BAG_PER_PAGE]
    selected = next((i for i in page_items if i["id"] == selected_id), page_items[0] if page_items else None)
    tiles = []
    for it in page_items:
        label, key = items.rarity(it)
        tiles.append({"id": it["id"], "name": it["name"], "qty": it["qty"], "icon": items.item_icon(it),
                      "rarity": label, "rarity_key": key, "equipped": bool(it["equipped"]),
                      "learned": it["category"] == "manuals" and technique.TECHNIQUES[it["key"]]["name"] in learned,
                      "selected": selected is not None and it["id"] == selected["id"]})
    data = dict(header(p), category=category, categories=[(c.key, c.label, c.icon) for c in items.CATEGORIES.values()],
                counts=db.category_counts(conn, user_id), used=db.slots_used(conn, user_id),
                capacity=p["bag_capacity"], page=page, pages=pages, tiles=tiles,
                inspect=items.details(selected, p, learned) if selected else None)
    return data, page_items, pages, selected


def techniques_data(conn, user_id, page=1):
    p = db.get_player(conn, user_id)
    learned = db.get_techniques(conn, user_id, equipped_only=False)
    ordered = sorted(learned, key=lambda t: (not t["equipped"], t["type"], t["id"]))
    pages = max(1, math.ceil(len(ordered) / TECH_PER_PAGE))
    page = min(max(1, page), pages)
    equipped = [t for t in learned if t["equipped"]]
    return dict(header(p), slots=technique_slots(p, learned), slot_count=rules.technique_slots(p["realm"]),
                qi_bonus=rules.technique_qi_bonus(equipped), learned_count=len(learned),
                techniques=[technique_view(t) for t in ordered[(page - 1) * TECH_PER_PAGE: page * TECH_PER_PAGE]],
                page=page, pages=pages)


def equipment_data(conn, user_id):
    p = db.get_player(conn, user_id)
    equipped = db.get_techniques(conn, user_id)
    weapon = db.equipped_weapon(conn, user_id)
    spare = [w for w in db.get_items(conn, user_id, "weapons") if not w["equipped"]]
    w = weapon_view(weapon)
    if w:
        w["requires"] = equipments.TIER_REALM_REQUIREMENT[weapon["grade"]]
    return dict(header(p), weapon=w, attributes=attributes.attribute_values(p, equipped, weapon),
                spare=[weapon_view(x) for x in spare[:4]], spare_count=len(spare))
