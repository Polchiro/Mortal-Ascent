"""
The profile page's data. docs/web.md, "The profile page".

All numbers come from bot/sheet/data.profile_data, the same function the bot's /profile card uses,
so the website and Discord always agree. This module only turns them into text and picture links.
"""
import os

from bot import db
from bot.sheet import data as sheet
from cards import art_icons

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
    }
