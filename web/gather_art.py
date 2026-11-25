"""
The gathering and mining art (scripts/make_gather_art.py cuts it from SHOAIB's pictures and videos, Nov 25 2026):

  art/herbs/<herb>.webp      each of the 20 herbs painted growing from its patch of soil; catalog.json has its size
                             and foot (where it meets the ground). Drawn on the map and as a round's choices.
  art/gather/hero_<gender>_<kneel|swing>.webp   the hero kneeling at a herb and swinging a pick; sheets.json says how
                             each is laid out (cell, feet, cols, frames, fps, marks).
  art/gather/sounds/*.mp3    the videos' own sounds: kneeling, the hands in the leaves, rising, the pick's blows.

A round's choices are sent as pictures inside the round itself (data: addresses), never by the herb's name: the
address can't tell which plant is which, and the page has every picture before the clock matters.
"""
import base64
import io
import json
import os
from functools import lru_cache

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERBS = os.path.join(ROOT, "art", "herbs")
GATHER = os.path.join(ROOT, "art", "gather")
CHOICE_PX = 256                       # a choice card's picture, on its long side
# how tall each grade's plant stands on the map (px at the walkers' size): rarer herbs are bigger
MAP_HEIGHT = {"Mortal": 66, "Yellow": 74, "Mystic": 84, "Earth": 98, "Heaven": 118}


def slug(name):
    return name.lower().replace("'", "_").replace(" ", "_")


@lru_cache(maxsize=1)
def catalog():
    try:
        with open(os.path.join(HERBS, "catalog.json")) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def herb(name):
    """A herb's painting for the map: {src, w, h, foot}, or None if it isn't painted."""
    c = catalog().get(slug(name))
    return {"src": f"/art/herbs/{slug(name)}.webp", "w": c["w"], "h": c["h"], "foot": c["foot"]} if c else None


@lru_cache(maxsize=64)
def choice(name):
    """A herb's painting as a small picture inside the round (a data: address), or None if it isn't painted."""
    path = os.path.join(HERBS, slug(name) + ".webp")
    if not os.path.exists(path):
        return None
    from PIL import Image
    im = Image.open(path).convert("RGBA")
    im.thumbnail((CHOICE_PX, CHOICE_PX), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "WEBP", quality=82, method=4)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


@lru_cache(maxsize=1)
def _sheets():
    try:
        with open(os.path.join(GATHER, "sheets.json")) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def acts(gender):
    """This hero's kneel and swing sheets for the page: {"kneel": {...}, "swing": {...}} (what is cut)."""
    return {move: s for move in ("kneel", "swing") if (s := _sheets().get(f"{gender}_{move}"))}


@lru_cache(maxsize=1)
def sounds():
    """The recorded sounds by kind: {"kneel": ["/art/gather/sounds/kneel_1.mp3", ...], "pick": [...], ...}."""
    out = {}
    try:
        names = sorted(os.listdir(os.path.join(GATHER, "sounds")))
    except FileNotFoundError:
        return out
    for n in names:
        if n.endswith(".mp3"):
            out.setdefault(n.rsplit("_", 1)[0] if "_" in n else n[:-4], []).append(f"/art/gather/sounds/{n}")
    return out
