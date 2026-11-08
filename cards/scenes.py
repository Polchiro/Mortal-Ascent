"""
Painted scenes and objects (art/scenes/): region backgrounds for /explore and its fights, places (Blessed Land,
lairs, hazards), the sparring hall, and encounter subjects (chest, herbs, ore, tablet, bandits, merchant).

photo(name, w, h) -> a scene file cover-fitted to w×h (pixels), or None when the file is missing, so every card
keeps its drawn fallback. subject(name) -> a transparent subject, or None.
"""
import os
from functools import lru_cache

from PIL import Image

DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "scenes")

REGION = {"Bamboo Forest": "region_bamboo_forest", "Misty Pine Valley": "region_misty_pine_valley",
          "Red Cliff Gorge": "region_red_cliff_gorge", "Thunder Peaks": "region_thunder_peaks",
          "Northern Sea Wilds": "region_northern_sea_wilds"}
PLACE = {"peaceful_clearing": "encounter_peaceful_clearing", "blessed_land": "encounter_blessed_land",
         "elite_lair": "encounter_elite_lair", "beast_king_den": "encounter_beast_king_den",
         "poison mist": "encounter_poison_mist", "landslide": "encounter_landslide"}
SUBJECT = {"treasure_chest": "subject_treasure_chest", "herb_patch": "subject_herb_patch",
           "ore_vein": "subject_ore_vein", "stone_tablet": "subject_stone_tablet", "bandits": "subject_bandits",
           "wandering_merchant": "subject_wandering_merchant", "injured_stranger": "subject_injured_stranger",
           "wandering_hermit": "subject_wandering_hermit"}


def exists(name):
    return bool(name) and os.path.exists(os.path.join(DIR, name + ".jpg"))


@lru_cache(maxsize=24)
def photo(name, w, h):
    """The scene `name` (no extension) scaled to cover w×h and centre-cropped, as RGBA; None if missing."""
    path = os.path.join(DIR, f"{name}.jpg") if name else None
    if not path or not os.path.exists(path):
        return None
    try:
        im = Image.open(path).convert("RGB")
    except Exception:
        return None
    sc = max(w / im.size[0], h / im.size[1])
    im = im.resize((max(w, round(im.size[0] * sc)), max(h, round(im.size[1] * sc))), Image.LANCZOS)
    x, y = (im.size[0] - w) // 2, (im.size[1] - h) // 2
    return im.crop((x, y, x + w, y + h)).convert("RGBA")


@lru_cache(maxsize=16)
def subject(name):
    path = os.path.join(DIR, f"{name}.png") if name else None
    if not path or not os.path.exists(path):
        return None
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None
