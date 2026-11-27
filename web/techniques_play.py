"""
Techniques on the website (docs/web.md "Techniques"): every technique you have learned, its mastery and what it
does, and the three sockets (Attack, Defense, and Flex from Martial Warrior). Equipping and taking off use the bot's
own rules (bot/db.equip_technique, bot/db.unequip_technique), the same as Discord's /techniques:
  - equipping fills a free socket, or replaces the oldest equipped technique of the same type;
  - one attack and one defense technique always stay equipped (only the Flex one can simply come off);
  - nothing can be swapped during a fight (a duel, a spar, a drill or a beast fight).
"""
import technique
from bot import db
from bot import player as rules
from bot.sheet import data as sheet

from .alchemy_play import GRADE_COLOR
from .profile import art_url

FIGHTING = "Techniques can only be swapped outside of fights. Finish your fight first."


def would_replace(learned, tech, slots):
    """What db.equip_technique would take off to make room for `tech` (its own rule, without writing), or None."""
    return db.bumped([t for t in learned if t["equipped"]], tech["type"], slots)


def card(t, learned, slots):
    v = sheet.technique_view(t)
    equipped = [x for x in learned if x["equipped"]]
    out = {"id": t["id"], "name": v["name"], "type": v["type"], "kind": "Attack" if v["type"] == "attack" else "Defense",
           "grade": v["grade"], "color": GRADE_COLOR.get(v["grade"], "#C9D2E6"), "school": v["school"],
           "icon": art_url(v["icon"]), "stage": v["stage_name"], "exp": v["exp"], "cap": v["cap"],
           "pct": 100 if not v["cap"] else min(100, round(v["exp"] / v["cap"] * 100)),
           "trial": v["trial_ready"], "effect": v["effect"], "power": v["power"], "passive": v["passive"],
           "cooldown": v["cooldown"], "equipped": v["equipped"], "action": None, "note": None}
    held = db.slotted(equipped)
    if t["equipped"]:
        out["action"] = "unequip"                    # no minimum: any slot can be emptied (technique.md "Slots")
        out["slot"] = next((n for n, x in held.items() if x["id"] == t["id"]), None)
    else:
        out["action"] = "equip"                      # into the slot you pick: what is there comes off
        out["slots"] = [{"no": n, "open": n <= slots, "holds": held[n]["name"] if n in held and n <= slots else None}
                        for n in (1, 2, 3)]
    return out


def sections(cards):
    """The cards by grade, Heaven first down to Mortal (the best you have on top), each grade only if you know one:
    [{"grade", "color", "cards"}]. Within a grade: equipped first, then attack before defense, then by name."""
    order = list(technique.GRADES)[::-1]
    out = []
    for g in order + sorted({c["grade"] for c in cards} - set(order)):
        mine = sorted((c for c in cards if c["grade"] == g), key=lambda c: (not c["equipped"], c["type"], c["name"]))
        if mine:
            out.append({"grade": g, "color": GRADE_COLOR.get(g, "#C9D2E6"), "cards": mine})
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
    cards = [card(t, learned, slots) for t in order]
    return {"sockets": sockets, "slot_count": slots, "cards": cards, "sections": sections(cards),
            "attacks": sum(c["type"] == "attack" for c in cards), "defenses": sum(c["type"] == "defense" for c in cards),
            "qi_bonus": f"+{rules.technique_qi_bonus(equipped):.0%}".replace("+0%", "") or None,
            "learned": len(learned), "coins": p["lotus_coins"], "pearls": p["moon_pearls"]}


def equip(conn, uid, tech_id, fighting=False, slot=None):
    """(ok, message). Into `slot` (1-3), taking off what is there; the bot's own rule (db.equip_technique)."""
    if fighting:
        return False, FIGHTING
    p = db.get_player(conn, uid)
    tech = db.get_technique(conn, uid, tech_id) if (p and tech_id is not None) else None
    if not tech:
        return False, "You don't know that technique."
    if tech["equipped"]:
        return False, "That technique is already equipped."
    open_slots = rules.technique_slots(p["realm"])
    if slot is not None and not 1 <= slot <= open_slots:
        return False, "That slot opens at Martial Warrior." if slot == 3 else "There is no such slot."
    replaced = db.equip_technique(conn, uid, tech_id, open_slots, slot)
    where = f" in slot {slot}" if slot else ""
    return True, f"Equipped {tech['name']}{where}" + (f", in place of {replaced}." if replaced else ".")


def unequip(conn, uid, tech_id, fighting=False):
    if fighting:
        return False, FIGHTING
    tech = db.get_technique(conn, uid, tech_id) if tech_id is not None else None
    if not tech or not tech["equipped"]:
        return False, "That technique isn't equipped."
    if db.unequip_technique(conn, uid, tech_id):
        return True, f"Took off {tech['name']}: its slot is empty."
    return False, "That technique isn't equipped."


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
