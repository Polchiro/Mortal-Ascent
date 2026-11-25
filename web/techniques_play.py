"""
Techniques on the website (docs/web.md "Techniques"): every technique you have learned, its mastery and what it
does, and the three sockets (Attack, Defense, and Flex from Martial Warrior). Equipping and taking off use the bot's
own rules (bot/db.equip_technique, bot/db.unequip_technique), the same as Discord's /techniques:
  - equipping fills a free socket, or replaces the oldest equipped technique of the same type;
  - one attack and one defense technique always stay equipped (only the Flex one can simply come off);
  - nothing can be swapped during a fight (a duel, a spar, a drill or a beast fight).
"""
from bot import db
from bot import player as rules
from bot.sheet import data as sheet

from .alchemy_play import GRADE_COLOR
from .profile import art_url

FIGHTING = "Techniques can only be swapped outside of fights. Finish your fight first."


def would_replace(learned, tech, slots):
    """What db.equip_technique would take off to make room for `tech` (its own rule, without writing), or None."""
    equipped = [t for t in learned if t["equipped"]]
    same = [t for t in equipped if t["type"] == tech["type"]]
    other = [t for t in equipped if t["type"] != tech["type"]]
    if len(same) >= slots - 1 or len(equipped) >= slots:
        return same[0] if same else (other[0] if len(other) > 1 else None)
    return None


def card(t, learned, slots):
    v = sheet.technique_view(t)
    equipped = [x for x in learned if x["equipped"]]
    out = {"id": t["id"], "name": v["name"], "type": v["type"], "kind": "Attack" if v["type"] == "attack" else "Defense",
           "grade": v["grade"], "color": GRADE_COLOR.get(v["grade"], "#C9D2E6"), "school": v["school"],
           "icon": art_url(v["icon"]), "stage": v["stage_name"], "exp": v["exp"], "cap": v["cap"],
           "pct": 100 if not v["cap"] else min(100, round(v["exp"] / v["cap"] * 100)),
           "trial": v["trial_ready"], "effect": v["effect"], "power": v["power"], "passive": v["passive"],
           "cooldown": v["cooldown"], "equipped": v["equipped"], "action": None, "note": None}
    if t["equipped"]:
        if sum(x["type"] == t["type"] for x in equipped) > 1:
            out["action"] = "unequip"
        else:
            out["note"] = f"Your only {out['kind'].lower()} technique: equip another to swap it"
    else:
        out["action"] = "equip"
        gone = would_replace(learned, t, slots)
        out["note"] = f"Replaces {gone['name']}" if gone else "Goes into a free slot"
    return out


def view(conn, uid):
    """Everything techniques.html shows, or None without a character."""
    p = db.get_player(conn, uid)
    if p is None:
        return None
    learned = db.get_techniques(conn, uid, equipped_only=False)
    slots = rules.technique_slots(p["realm"])
    sockets = []
    for s in sheet.technique_slots(p, learned):
        t = s["tech"]
        sockets.append({"slot": s["slot"], "locked": s["locked"], "note": s.get("note"),
                        "name": t["name"] if t else None, "grade": t["grade"] if t else None,
                        "color": GRADE_COLOR.get(t["grade"], "#C9D2E6") if t else None,
                        "stage": t["stage_name"] if t else None, "power": t["power"] if t else None,
                        "icon": art_url(t["icon"]) if t else None})
    order = sorted(learned, key=lambda t: (not t["equipped"], t["type"], t["id"]))
    equipped = [t for t in learned if t["equipped"]]
    return {"sockets": sockets, "slot_count": slots, "cards": [card(t, learned, slots) for t in order],
            "qi_bonus": f"+{rules.technique_qi_bonus(equipped):.0%}".replace("+0%", "") or None,
            "learned": len(learned), "coins": p["lotus_coins"], "pearls": p["moon_pearls"]}


def equip(conn, uid, tech_id, fighting=False):
    """(ok, message). The bot's own rule (db.equip_technique)."""
    if fighting:
        return False, FIGHTING
    p = db.get_player(conn, uid)
    tech = db.get_technique(conn, uid, tech_id) if (p and tech_id is not None) else None
    if not tech:
        return False, "You don't know that technique."
    if tech["equipped"]:
        return False, "That technique is already equipped."
    replaced = db.equip_technique(conn, uid, tech_id, rules.technique_slots(p["realm"]))
    return True, f"Equipped {tech['name']}" + (f" in place of {replaced}." if replaced else ".")


def unequip(conn, uid, tech_id, fighting=False):
    if fighting:
        return False, FIGHTING
    tech = db.get_technique(conn, uid, tech_id) if tech_id is not None else None
    if not tech or not tech["equipped"]:
        return False, "That technique isn't equipped."
    if db.unequip_technique(conn, uid, tech_id):
        return True, f"Took off {tech['name']}."
    return False, "You must keep one technique of each type equipped."


def fighting(state, uid):
    """Is this player in a fight on the website right now (a duel, a spar, a drill or a beast fight)?"""
    for name in ("arena", "hall", "practice"):
        s = getattr(state, name, None)
        if s is not None and s.busy(uid):
            return True
    hunts = getattr(state, "hunts", None)
    if hunts is not None:
        party = hunts.parties.of(uid)
        h = hunts._h.get(party.id) if party else None
        if h is not None and h.battle is not None and uid in h.exps:
            return True
    return False
