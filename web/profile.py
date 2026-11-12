"""
The profile page's data. docs/web.md, "The profile page".

All numbers come from bot/sheet/data.profile_data, the same function the bot's /profile card uses,
so the website and Discord always agree. This module only turns them into text and picture links.
"""
import os

import stats

from bot import crafting, db, forging, points
from bot import player as rules
from bot.sheet import data as sheet
from cards import art_icons
from cards.theme import REALM_CHAR

PORTRAIT = "/art/portraits/cultivator_default.webp"
ATTR_ICON = "/art/icons/attr/{}.webp"
ART_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art")


def art_url(kind):
    """'/art/icons/tech/iron_fist.webp' for an icon kind like 'tech:iron_fist', or None."""
    found = art_icons.resolve(kind) if kind else None
    if not found:
        return None
    rel = os.path.relpath(found[0], ART_ROOT).replace(os.sep, "/")
    return "/art/" + rel


def number(x):
    """12480 -> '12,480'; 3.125 -> '3.1'."""
    if isinstance(x, float) and not x.is_integer():
        return f"{x:,.1f}"
    return f"{int(x):,}"


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def eta_text(eta):
    """'2h 33m' -> 'full in 2h 33m'; words like 'Ready now' stay as they are."""
    if not eta:
        return None
    return f"full in {eta}" if eta[0].isdigit() else eta


def pct(x):
    """0.025 -> '+2.5%'."""
    v = round(x * 100, 1)
    return f"{'+' if v >= 0 else ''}{v:g}%"


def attribute_rows(attrs, qi):
    """HP, Internal Qi, Attack, Defense: the number, its realm base and every bonus on top (name, %)."""
    rows = []
    for key in ("hp", "attack", "defense"):
        a = attrs[key]
        rows.append({"key": key, "label": "HP" if key == "hp" else a["label"], "icon": ATTR_ICON.format(key),
                     "value": number(a["final"]), "base": number(a["base"]),
                     "bonus": pct(a["bonus"]) if a["bonus"] else None,
                     "sources": [(name, pct(v)) for name, v in a["sources"]]})
    rows.insert(1, {"key": "qi", "label": "Internal Qi", "icon": ATTR_ICON.format("qi"),
                    "value": number(qi["qi"]), "base": None, "of": number(qi["capacity"]), "bonus": None,
                    "sources": [("Flows in", f"+{number(float(qi['rate']))} / hour")]})
    return rows


def titles(player):
    """The character's standing: talent and crafting ranks (the game has no other titles yet)."""
    out = [(f"{player['talent']} Talent", "talent")]
    a, b = crafting.rank_of(player["alchemy_exp"]), forging.rank_of(player["blacksmith_exp"])
    if player["alchemy_exp"]:
        out.append((f"{crafting.rank_label(a)} Alchemist", "craft"))
    if player["blacksmith_exp"]:
        out.append((f"{forging.rank_label(b)} Blacksmith", "craft"))
    return out


def realm_track(realm, layer, max_layer):
    """Realm n of N, the layer pips and the next realm's name."""
    order = rules.REALM_ORDER
    i = order.index(realm)
    return {"no": i + 1, "of": len(order), "seal": REALM_CHAR.get(realm, "武"),
            "next": order[i + 1] if i + 1 < len(order) else None,
            "pips": [{"n": n, "on": n <= layer, "now": n == layer} for n in range(1, max_layer + 1)]}


def development(conn, user_id):
    """The Strength / Vitality panel: points, what they give, and what the page needs to preview a choice."""
    from bot.sheet.data import worn
    p = db.get_player(conn, user_id)
    techs = db.get_techniques(conn, user_id)
    weapon, armor, _ = worn(conn, user_id)
    hp, attack, _ = rules.base_stats(p["realm"], p["layer"])
    other = {k: sum(v for _, v in src) for k, src in rules.stat_buffs(techs, weapon, armor).items()}
    cost = points.reset_cost(p)
    import battle
    return {"strength": p["strength"], "vitality": p["vitality"], "spirit": p["spirit"], "free": rules.unspent_points(p),
            "bqi": battle.BATTLE_QI_START + p["spirit"] * stats.SPIRIT_BATTLE_QI, "per_spi": stats.SPIRIT_BATTLE_QI,
            "earned": rules.attribute_points(p["realm"], p["layer"]),
            "str_pct": pct(p["strength"] * stats.STRENGTH_ATTACK), "vit_pct": pct(p["vitality"] * stats.VITALITY_HP),
            "per_str": pct(stats.STRENGTH_ATTACK), "per_vit": pct(stats.VITALITY_HP),
            "reset_cost": cost, "can_reset": bool(p["strength"] or p["vitality"] or p["spirit"]),
            "pearls": p["moon_pearls"],
            # the preview uses the same formula as player.final_stats: round(base × (1 + every % bonus))
            "calc": {"hp": hp, "attack": attack, "hp_pct": other["hp"], "atk_pct": other["attack"],
                     "s": p["strength"], "v": p["vitality"], "ps": stats.STRENGTH_ATTACK, "pv": stats.VITALITY_HP,
                     "q": p["spirit"], "pq": stats.SPIRIT_BATTLE_QI, "bq": battle.BATTLE_QI_START}}


def profile_view(conn, user_id, username=None):
    """Everything profile.html shows, or None when this Discord account has no character yet."""
    if db.get_player(conn, user_id) is None:
        return None
    d = sheet.profile_data(conn, user_id, username=username)
    qi = d["qi"]
    cap = qi["capacity"] or 1
    attrs = {a["key"]: a for a in d["attributes"]}
    slots = []
    for s in d["slots"]:
        t = s.get("tech")
        slots.append({
            "slot": s["slot"], "locked": s["locked"], "note": s.get("note"),
            "name": t["name"] if t else None, "grade": t["grade"] if t else None,
            "mastery": t["stage_name"] if t else None, "power": t["power"] if t else None,
            "icon": art_url(t["icon"]) if t else None,
        })
    return {
        "name": d["name"], "talent": d["talent"], "realm": d["realm"], "phase": d["phase"],
        "layer": ordinal(d["layer"]), "max_layer": d["max_layer"], "rank": d["rank"],
        "qi": number(qi["qi"]), "qi_cap": number(qi["capacity"]), "qi_pct": max(0, min(100, round(qi["qi"] / cap * 100))),
        "qi_rate": number(float(qi["rate"])), "qi_eta": eta_text(qi["eta"]), "qi_status": qi["status"],
        "qi_gate": qi["gate"], "qi_gate_note": qi["gate_note"],
        "hp": number(attrs["hp"]["final"]), "attack": number(attrs["attack"]["final"]),
        "defense": number(attrs["defense"]["final"]),
        "injured": d["hp"]["injured_for"] > 0,
        "coins": number(d["coins"]), "pearls": number(d["pearls"]),
        "slots": slots,
        "weapon": d["weapon"]["name"] if d.get("weapon") else None,
        "stats": [("Beasts slain", number(d["beasts"])), ("Herbs gathered", number(d["herbs"])),
                  ("Breakthroughs", number(d["breakthroughs"])),
                  ("Duels won", number(d["duels_won"]))],
        "status": d["status"],
        "portrait": PORTRAIT,
        "dev": development(conn, user_id),
        "layer_no": d["layer"],
        "titles": titles(db.get_player(conn, user_id)),
        "track": realm_track(d["realm"], d["layer"], d["max_layer"]),
        "attributes": attribute_rows(attrs, qi),
        "qi_tone": qi["status_tone"],
    }
