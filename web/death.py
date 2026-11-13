"""
A beaten beast going down on the website fight screen (docs/web.md, "The victory sequence").

beasts.DEATH_ANIMATIONS has one shared set of frames per body category (cut from SHOAIB's video by
scripts/make_death_sheet.py). Nothing is painted per beast: here the shared frames are recoloured from the beast's
own picture (its dark, middle and light tones) and served at /art/death/<category>/<slug>.webp, made once and kept
in memory. view() also says where the body is inside the beast's picture, so fight.js can lay the frames over it at
the beast's own size. A beast with no category tips over where it stands; bandits scatter.
"""
import io
import os
import re
from functools import lru_cache

import numpy as np
from PIL import Image, ImageOps

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
def _look(path):
    """(body box as shares of the picture: left, top, right, bottom; its dark, middle and light colours)."""
    im = Image.open(path).convert("RGBA")
    im.thumbnail((200, 200))
    a = np.asarray(im).astype(np.float32)
    solid = a[:, :, 3] > 128
    ys, xs = np.nonzero(solid)
    h, w = solid.shape
    box = (xs.min() / w, ys.min() / h, (xs.max() + 1) / w, (ys.max() + 1) / h)
    rgb = a[:, :, :3][a[:, :, 3] > 220]
    lum = rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    def tone(lo, hi):
        a_, b_ = np.quantile(lum, [lo, hi])
        part = rgb[(lum >= a_) & (lum <= b_)]
        part = part if len(part) else rgb
        vivid = 0.1 + (part.max(axis=1) - part.min(axis=1)) / np.maximum(part.max(axis=1), 1)   # its colour, not its greys
        return tuple(int(v) for v in (part * vivid[:, None]).sum(axis=0) / vivid.sum())
    return tuple(round(float(v), 4) for v in box), (tone(0.04, 0.22), tone(0.4, 0.6), tone(0.85, 0.97))


@lru_cache(maxsize=64)
def sheet(category, slug):
    """The category's frames in this beast's colours, as WebP bytes. None when there is no such sheet or beast."""
    anim = beasts.DEATH_ANIMATIONS.get(category)
    path = picture(slug)
    if not anim or not path:
        return None
    try:
        src = Image.open(os.path.join(ROOT, "art", "fx", "death", anim["sheet"])).convert("RGBA")
    except OSError:
        return None
    _, (dark, mid, light) = _look(path)
    grey = src.convert("L")
    alpha = src.getchannel("A")
    lum = np.asarray(grey)[np.asarray(alpha) > 128]
    lo, md, hi = (int(v) for v in np.quantile(lum, [0.03, 0.5, 0.985]))
    md = min(max(md, lo + 1), hi - 1)
    out = ImageOps.colorize(grey, dark, light, mid, blackpoint=lo, whitepoint=hi, midpoint=md).convert("RGBA")
    out.putalpha(alpha)
    buf = io.BytesIO()
    out.save(buf, "WEBP", quality=88, method=4)
    return buf.getvalue()


def view(enemy):
    """How this enemy goes down, for the fight page (read by web/static/fight.js)."""
    if enemy.get("kind") != "beast":
        return {"kind": "rout", "linger": LINGER_MS}
    slug = enemy.get("slug")
    cat = beasts.death_category(enemy["name"])
    path = picture(slug)
    if not cat or not path:
        return {"kind": "fall", "linger": LINGER_MS}
    anim = beasts.DEATH_ANIMATIONS[cat]
    box, _ = _look(path)
    return {"kind": "sheet", "category": cat, "src": f"/art/death/{cat}/{slug}.webp", "frames": anim["frames"],
            "cols": anim["cols"], "rows": anim["rows"], "ms": anim["ms"], "impact": anim["impact"],
            "cell": list(anim["cell"]), "body": list(anim["body"]), "flip": anim["faces"] == "right",
            "box": list(box), "linger": LINGER_MS}
