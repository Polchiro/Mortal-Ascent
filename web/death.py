"""
A beaten beast going down on the website fight screen (docs/web.md, "The victory sequence").

beasts.DEATH_ANIMATIONS has one shared movement per body category (measured from SHOAIB's video by
scripts/make_death_motion.py): numbers only, no artwork. The beast always goes down as its own picture: fight.js
bends and lowers that picture through the movement. view() hands it the movement and where the body is inside the
beast's picture, so the same movement fits every beast's size and place. A beast with no category tips over where
it stands; bandits scatter.
"""
import os
import re
from functools import lru_cache

from PIL import Image

import beasts

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = re.compile(r"^[a-z0-9_]{1,60}$")
LINGER_MS = 800                         # the body lies there this long before the Victory panel comes up


def picture(slug):
    """The beast's picture as the fight shows it: its cut-out idle pose if it has one, else its painting."""
    if not slug or not SLUG.match(slug):
        return None
    for path in (os.path.join(ROOT, "art", "beasts", "poses", slug, "idle.webp"),
                 os.path.join(ROOT, "art", "beasts", f"{slug}.png")):
        if os.path.exists(path):
            return path
    return None


@lru_cache(maxsize=128)
def body_box(path):
    """Where the beast is inside its picture, as shares of it: (left, top, right, bottom)."""
    alpha = Image.open(path).convert("RGBA").getchannel("A").point(lambda v: 255 if v > 128 else 0)
    left, top, right, bottom = alpha.getbbox() or (0, 0) + alpha.size
    w, h = alpha.size
    return (round(left / w, 4), round(top / h, 4), round(right / w, 4), round(bottom / h, 4))


def view(enemy):
    """How this enemy goes down, for the fight page (read by web/static/fight.js)."""
    if enemy.get("kind") != "beast":
        return {"kind": "rout", "linger": LINGER_MS}
    cat = beasts.death_category(enemy["name"])
    path = picture(enemy.get("slug"))
    if not cat or not path:
        return {"kind": "fall", "linger": LINGER_MS}
    anim = beasts.DEATH_ANIMATIONS[cat]
    return {"kind": "warp", "category": cat, "ms": anim["ms"], "impact": anim["impact"],
            "motion": [{"w": w, "h": list(h)} for w, h in anim["motion"]],
            "box": list(body_box(path)), "linger": LINGER_MS}
