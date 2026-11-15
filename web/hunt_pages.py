"""
Page data for Explore's hunting screens (docs/hunting.md): the entry, the team browser, the lobby and the
location cards. Only reads: every change goes through web/parties.py and web/hunt_play.py.
"""
import os
from functools import lru_cache

import beasts
import forge
import hunting

from bot import db, loot, materials

from .forge_play import rich
from .profile import number

TIER_LABEL = {"normal": "Normal", "elite": "Elite", "beast_king": "Beast King"}
SHORT_TIER = {"normal": "", "elite": "Elite", "beast_king": "King"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@lru_cache(maxsize=None)
def beast_icon(name):
    """The beast's round icon (art/icons/beasts), or its painting when it has no icon yet."""
    slug = beasts.slug(name)
    if os.path.exists(os.path.join(ROOT, "art", "icons", "beasts", f"{slug}.webp")):
        return f"/art/icons/beasts/{slug}.webp"
    return f"/art/beasts/{slug}.png"


def purse(p):
    return {"coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"])}


def entry_view(conn, uid, parties, hunts):
    p = db.get_player(conn, uid)
    if p is None:
        return None
    loc = hunting.location_for(p["realm"])
    return {**purse(p), "realm": p["realm"], "home": loc["name"] if loc else None,
            "scene": f"/art/scenes/{loc['card'] if loc else 'region_bamboo_forest'}.jpg",
            "blocked": hunts.blocked(conn, uid), "open": len(parties.public()), "max": hunting.MAX_PARTY,
            "steps": hunting.MAX_ENCOUNTERS}


def _leader_row(conn, party):
    lead = db.get_player(conn, party.leader)
    return lead["name"] if lead else "?", lead["realm"] if lead else ""


def teams_view(conn, uid, parties):
    p = db.get_player(conn, uid)
    rows = []
    for party in parties.public():
        name, realm = _leader_row(conn, party)
        loc = hunting.location(party.location) if party.location else None
        why = None
        if party.full:
            why = "Full"
        elif loc and hunting.eligible(p, loc):
            why = f"Needs {hunting.requirement(loc)}+"
        rows.append({"id": party.id, "name": party.name, "leader": name, "realm": realm,
                     "members": len(party.members), "max": hunting.MAX_PARTY,
                     "location": loc["name"] if loc else None, "full": party.full, "blocked": why})
    return {**purse(p), "teams": rows, "realm": p["realm"]}


def lobby_view(conn, uid, party, hunts):
    p = db.get_player(conn, uid)
    loc = hunting.location(party.location) if party.location else None
    lead = party.leader == uid
    members = []
    for m in party.members:
        pl = db.get_player(conn, m.uid)
        bad = None
        if pl and loc:
            bad = "Realm too low" if hunting.eligible(pl, loc) else None
        rest = hunts.blocked(conn, m.uid)
        members.append({"uid": m.uid, "name": pl["name"] if pl else "?", "realm": pl["realm"] if pl else "",
                        "layer": pl["layer"] if pl else 0, "leader": m.uid == party.leader, "me": m.uid == uid,
                        "ready": m.ready or m.uid == party.leader, "bad": bad,
                        "rest": rest[0].upper() + rest[1:] if rest else None})
    problems = hunts.parties.start_problems(conn, party, hunts.blocked)
    return {**purse(p), "id": party.id, "name": party.name, "public": party.public, "code": party.code,
            "lead": lead, "solo": party.solo, "version": party.version, "members": members,
            "open": hunting.MAX_PARTY - len(party.members), "max": hunting.MAX_PARTY,
            "location": location_card(loc, p) if loc else None, "me_ready": party.member(uid).ready,
            "problems": problems, "can_start": lead and not problems,
            "scene": f"/art/scenes/{loc['card'] if loc else 'region_bamboo_forest'}.jpg"}


def location_card(loc, player):
    pool = hunting.pool(loc)
    tiers = sorted({forge.tier_for_realm(r) for r in loc["realms"]})
    mats = []
    for t in tiers:
        for part, kw in (("binding", {}), ("base", {"gear": "armor"})):
            name = loot.describe(materials.material(forge.material_key(part, t, **kw), 1))
            if name not in mats:
                mats.append(name)
    elements = sorted({beasts.element_of(n) for n, *_ in pool if beasts.element_of(n)})
    why = hunting.eligible(player, loc)
    here = player["realm"] in loc["realms"]
    return {"key": loc["key"], "name": loc["name"], "text": loc["text"], "art": f"/art/scenes/{loc['card']}.jpg",
            "requirement": hunting.requirement(loc), "ok": why is None,
            "state": "Your realm" if here else "Open" if why is None else "Realm too low",
            "home": hunting.home_realms(loc),
            "beasts": [{"name": n, "tier": TIER_LABEL[t], "tkey": t, "role": r.title(), "realm": home,
                        "short": SHORT_TIER[t], "icon": beast_icon(n)} for n, t, r, home in pool],
            "rewards": ["Lotus Coins", "Beast Cores", "Chests (from beasts)"] + mats
                       + ([f"{', '.join(elements)} essences"] if elements else [])}


def locations_view(conn, uid, party):
    p = db.get_player(conn, uid)
    return {**purse(p), "lead": party.leader == uid, "solo": party.solo, "chosen": party.location,
            "realm": p["realm"], "cards": [location_card(loc, p) for loc in hunting.LOCATIONS]}


def lines(items):
    return [rich(x) for x in items if x]
