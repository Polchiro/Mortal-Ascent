"""A beast's animation frame sheets for the fight (art/beasts/sheets/<slug>/: idle, attack, hit, death + sheets.json,
cut from SHOAIB's videos by scripts/make_beast_sheets.py; docs/web.md "Animated beasts").

A beast with sheets is drawn from them instead of its still picture: the idle loops while it stands, the attack plays
when it attacks you (biting on the frame `bite`), the hit when it takes damage, the death when it falls (then holds
its last frame). The still picture stays underneath, unseen, so everything the fight already does to the beast
(moving it, flashing it, its roar) still has its picture to measure and to show. web/static/fight.js `BeastSheets`.
"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = re.compile(r"^[a-z0-9_]{1,60}$")
_cache = {}


def sheets(slug):
    """The beast's sheets as the page needs them (cell size, where its picture sits in the cell, each sheet), or None."""
    if not slug or not SLUG.match(slug):
        return None
    if slug not in _cache:
        try:
            with open(os.path.join(ROOT, "art", "beasts", "sheets", slug, "sheets.json")) as fh:
                data = json.load(fh)
            if set(data["sheets"]) != {"idle", "attack", "hit", "death"}:
                raise ValueError(slug)
            _cache[slug] = data
        except (OSError, ValueError, KeyError):
            _cache[slug] = None
    return _cache[slug]


def death_view(slug, linger):
    """How a beast with sheets goes down (web/death.view): its death sheet, then its last frame held."""
    d = (sheets(slug) or {}).get("sheets", {}).get("death")
    if not d:
        return None
    impact = round(d.get("impact", d["frames"] - 1) / d["frames"] * d["ms"])
    return {"kind": "sheet", "ms": d["ms"], "impact": impact, "linger": linger}
