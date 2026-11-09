"""
Painted item icons (art/icons/<group>/<name>.webp), cut from the Gemini icon sheets.

Every card draws icons through cards.theme.icon / seal with a "kind" string. When a painting exists
for that kind, it is drawn instead of the vector icon; anything without a painting keeps its drawn
icon, so a missing file never breaks a card.

Kinds that map to paintings:
  art:<group>/<name>              any painting by its path (gear/iron_sword, herbs/spirit_grass, cores/elite_mystic …)
  tech:<key>                      techniques
  mat:<key>                       forging materials (essences have no painting yet)
  passive:<Rarity>                passive rarity coins
  emblem:pill:<kind>:<grade>[:n]  pills (n = patterns, drawn as small dots under the pill)
  emblem:pill:heaven_defying      the Heaven-Defying Pill
  emblem:book                     the /index overview book

Files are small (160 px WebP) and every resize is cached, so a card pays for each icon once.
"""
import os
import re
from functools import lru_cache

from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "icons")


def slug(name):
    """'Disciple's Cloud Robe' → 'disciple_s_cloud_robe' (the file name of an item's painting)."""
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


@lru_cache(maxsize=1024)
def exists(rel):
    return os.path.exists(os.path.join(ROOT, rel + ".webp"))


def kind(group, name, fallback):
    """'art:<group>/<slug(name)>' when that painting exists, else `fallback`."""
    rel = f"{group}/{slug(name)}"
    return "art:" + rel if exists(rel) else fallback


def gear(name, fallback):
    return kind("gear", name, fallback)


def herb(name, fallback="herb"):
    return kind("herbs", name, fallback)


def core(beast_tier, grade, fallback):
    return kind("cores", f"{beast_tier}_{grade}", fallback)


def index(name, fallback):
    """A section symbol of /index (index/<name>), e.g. index("weapons_spirit", ...)."""
    return kind("index", name, fallback)


@lru_cache(maxsize=1024)
def resolve(kind_):
    """(painting path, pattern count) for an icon kind, or None when it has no painting."""
    rel, dots = None, 0
    if kind_.startswith("art:"):
        rel = kind_[4:]
    elif kind_.startswith("tech:"):
        rel = "tech/" + kind_[5:]
    elif kind_.startswith("mat:"):
        rel = "mat/" + kind_[4:].replace(":", "_")
    elif kind_.startswith("passive:"):
        rel = "passives/" + kind_[8:].lower()
    elif kind_ == "emblem:book":
        rel = "index/overview"
    elif kind_.startswith("emblem:pill:"):
        parts = kind_.split(":")[2:]
        if parts[0] == "heaven_defying":
            rel = "pills/heaven_defying"
        elif len(parts) >= 2:
            rel = f"pills/{parts[0]}_{parts[1].lower()}"
            dots = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    if rel and exists(rel):
        return os.path.join(ROOT, rel + ".webp"), dots
    return None


@lru_cache(maxsize=512)
def image(path, px):
    """The painting resized to px × px (RGBA)."""
    art = Image.open(path).convert("RGBA")
    return art if art.size == (px, px) else art.resize((px, px), Image.LANCZOS)
