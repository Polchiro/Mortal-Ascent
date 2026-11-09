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

from .. import combat, db, gear, passives
from .. import player as rules
from . import attributes, items
from cards.technique_icons import tech_kind

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
        "icon": tech_kind(t["name"], info.get("school", "Body")),
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
            "type": (weapon.get("data") or {}).get("type") or weapon["key"], "icon": items.item_icon(weapon),
            "buffs": [f"+{v:.1%} {rules.STAT_LABELS[k]}".replace(".0%", "%")
                      for k, v in rules.weapon_buffs(weapon).items()],
            "passives": passives.slot_views(weapon, "weapon")}


def armor_view(armor):
    if not armor:
        return None
    return {"id": armor["id"], "name": armor["name"], "tier": armor["grade"], "type": gear.armor_type(armor),
            "type_label": gear.armor_label(armor), "seal": gear.armor_seal(armor), "icon": items.item_icon(armor),
            "requires": equipments.TIER_REALM_REQUIREMENT[armor["grade"]],
            "buffs": [f"+{v:.1%} {rules.STAT_LABELS[k]}".replace(".0%", "%")
                      for k, v in rules.weapon_buffs(armor).items()],
            "passives": passives.slot_views(armor, "armor")}


def artifact_view(a):
    if not a:
        return None
    spec = gear.family_spec(a)
    return {"id": a["id"], "name": a["name"], "tier": a["grade"], "family": gear.family(a), "seal": spec["seal"],
            "icon": items.item_icon(a), "group": spec["group"], "group_label": gear.GROUP_LABEL[spec["group"]],
            "requires": equipments.TIER_REALM_REQUIREMENT[a["grade"]], "slot": a["equipped"],
            "effect": gear.effect_text(a), "effect_short": gear.effect_text(a, tiny=True), "text": spec["text"],
            "passives": passives.slot_views(a, "artifact")}


GEAR_EMPTY = {"weapon": "Weapons drop from chests", "armor": "Armor drops from chests",
              "artifact": "Artifacts drop from chests"}


def worn(conn, user_id):
    """(weapon, armor, [artifact slot 1, artifact slot 2]) items; empty artifact slots are None."""
    arts = {a["equipped"]: a for a in db.equipped_artifacts(conn, user_id)}
    return (db.equipped_weapon(conn, user_id), db.equipped_armor(conn, user_id),
            [arts.get(s) for s in range(1, equipments.ARTIFACT_SLOTS + 1)])


def gear_sockets(weapon, armor, artifacts):
    """The Profile tab's Gear row: weapon, armor, artifact 1, artifact 2.
    Each: {slot, label, icon, tier, name, line} or an empty socket {slot, label, empty}."""
    out = []
    w = weapon_view(weapon)
    out.append({"slot": "weapon", "label": "Weapon", "icon": w["icon"], "tier": w["tier"], "name": w["name"],
                "line": rules.buff_text(rules.weapon_buffs(weapon)).replace("  ·  ", " · ")} if w else
               {"slot": "weapon", "label": "Weapon", "empty": GEAR_EMPTY["weapon"]})
    a = armor_view(armor)
    out.append({"slot": "armor", "label": "Armor", "icon": a["icon"], "tier": a["tier"], "name": a["name"],
                "line": rules.buff_text(rules.weapon_buffs(armor)).replace("  ·  ", " · ")} if a else
               {"slot": "armor", "label": "Armor", "empty": GEAR_EMPTY["armor"]})
    for i, art in enumerate(artifacts, 1):
        v = artifact_view(art)
        out.append({"slot": f"artifact{i}", "label": f"Artifact {i}", "icon": v["icon"], "tier": v["tier"],
                    "name": v["name"], "line": v["effect_short"]} if v else
                   {"slot": f"artifact{i}", "label": f"Artifact {i}", "empty": GEAR_EMPTY["artifact"]})
    return out


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
    weapon, armor, artifacts = worn(conn, user_id)
    return dict(
        header(p, username),
        rank=db.server_rank(conn, user_id, rules.REALM_ORDER),
        attributes=attributes.attribute_values(p, equipped, weapon, armor),
        qi=attributes.qi_resource(p, equipped, now),
        hp=attributes.hp_resource(p, equipped, weapon, now, armor),
        slots=technique_slots(p, learned),
        learned_count=len(learned),
        weapon=weapon_view(weapon),
        gear=gear_sockets(weapon, armor, artifacts),
        coins=p["lotus_coins"] if private else None,
        pearls=p["moon_pearls"] if private else None,
        beasts=p["beasts_slain"], herbs=p.get("herbs_gathered", 0), breakthroughs=p["breakthroughs"], failed=p["failed_breakthroughs"],
        duels_won=p.get("duels_won", 0), duels_lost=p.get("duels_lost", 0),
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
    """Items in a bag tab. 'materials:<group>' shows one Materials group (items.MATERIAL_GROUPS)."""
    cat, _, group = category.partition(":")
    found = db.get_items(conn, user_id, cat)
    if cat == "materials":
        found = sorted((i for i in found if not group or items.material_group(i) == group), key=items.material_order)
    return found


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
    groups = None
    if category.startswith("materials"):
        mats = db.get_items(conn, user_id, "materials")
        groups = [(g, label, sum(1 for i in mats if items.material_group(i) == g)) for g, label in items.MATERIAL_GROUPS]
    data = dict(header(p), category=category.partition(":")[0], group=category.partition(":")[2] or None,
                groups=groups, categories=[(c.key, c.label, c.icon) for c in items.CATEGORIES.values()],
                counts=db.category_counts(conn, user_id), used=db.slots_used(conn, user_id),
                capacity=p["bag_capacity"], page=page, pages=pages, tiles=tiles,
                inspect=dict(items.details(selected, p, learned), actions=action_labels(selected)) if selected else None)
    return data, page_items, pages, selected


def action_labels(item):
    """The buttons under the Inventory card for this item, in the order the view adds them."""
    names = {"use": items.use_label(item), "unequip": "Unequip", "discard": "Discard"}
    return [names[a] for a in items.actions(item) if names[a]]


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
    """All four slots with full details, base -> final stats (weapon + armor + techniques) and the
    artifacts' effects in their own list."""
    p = db.get_player(conn, user_id)
    equipped = db.get_techniques(conn, user_id)
    weapon, armor, artifacts = worn(conn, user_id)
    spare = [w for w in db.get_items(conn, user_id, "weapons") if not w["equipped"]]
    w = weapon_view(weapon)
    if w:
        w["requires"] = equipments.TIER_REALM_REQUIREMENT[weapon["grade"]]
    spare_counts = {c: sum(1 for i in db.get_items(conn, user_id, c) if not i["equipped"])
                    for c in ("weapons", "armor", "artifacts")}
    effects = [{"seal": v["seal"], "icon": v["icon"], "tier": v["tier"], "name": v["name"], "effect": v["effect"], "group": v["group"],
                "duel": f"{equipments.DUEL_COMBAT_ARTIFACT_STRENGTH:.0%} in Fair Duels" if v["group"] == "combat"
                else None}
               for v in (artifact_view(a) for a in artifacts) if v]
    import forge
    for key in p.get("artifact_passives", {}):                      # forged artifact passives (docs/forge.md)
        spec = forge.PASSIVES["artifact"][key]
        effects.append({"icon": f"passive:{spec['rarity']}", "color": forge.RARITY_COLORS[spec["rarity"]],
                        "tier": None, "name": f"{spec['name']} ({spec['rarity']} passive)", "effect": spec["text"],
                        "group": "passive", "duel": None})
    return dict(header(p), weapon=w, armor=armor_view(armor), artifacts=[artifact_view(a) for a in artifacts],
                attributes=attributes.attribute_values(p, equipped, weapon, armor), effects=effects,
                spare=[weapon_view(x) for x in spare[:4]], spare_count=len(spare), spare_counts=spare_counts)
