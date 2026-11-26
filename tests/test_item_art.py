"""The painted gear, artifacts, manuals and technique medallions (scripts/make_item_art.py, docs/equipment.md
"Pictures"): every one there, cut out with clear corners, and a manual shown as its scroll or book."""
import numpy as np
from PIL import Image

import equipments as eq
import technique
from cards import art_icons
from scripts import make_item_art as mia


def _clear_corners(path):
    a = np.asarray(Image.open(path).convert("RGBA"))[..., 3]
    assert a.shape == (mia.ICON, mia.ICON), path
    assert a[:5, :5].max() <= 8 and a[-5:, -5:].max() <= 8 and a[:5, -5:].max() <= 8 and a[-5:, :5].max() <= 8, path
    assert (a > 128).mean() > 0.02, path                                        # something is there (a spear is thin)


def test_every_weapon_armor_and_artifact_has_its_painting():
    names = [eq.WEAPON_NAMES[t][k] for t in eq.TIERS for k in eq.WEAPON_TYPES] + \
            [eq.ARMOR_NAMES[t][k] for t in eq.TIERS for k in eq.ARMOR_TYPES] + \
            [eq.artifact_name(f, t) for f in eq.ARTIFACT_FAMILIES for t in eq.TIERS]
    assert len(names) == 120
    for n in names:
        kind = art_icons.gear(n, "missing")
        assert kind != "missing", n
        _clear_corners(art_icons.resolve(kind)[0])


def test_grids_name_every_item_once():
    every = [n for g in list(mia.GEAR) + list(mia.FAMILIES) for n, _ in mia.grid_items(g)]
    assert len(every) == len(set(every)) == 120
    assert set(mia.FAMILIES.values()) == set(eq.ARTIFACT_FAMILIES)
    assert mia.single("sea-calming pillar")[0] == "Sea-Calming Pillar" and mia.single("nothing") is None


def test_a_manual_shows_its_scroll_or_book_and_the_technique_keeps_its_icon():
    for key, t in technique.TECHNIQUES.items():
        for g in mia.GRADES:
            hit = art_icons.resolve(f"emblem:manual:{key}:{g}")
            assert hit and hit[0].endswith(f"manuals/{t['type']}_{g.lower()}.webp"), (key, g)
        assert art_icons.resolve("tech:" + key)[0].endswith(f"tech/{key}.webp")
    for typ in ("attack", "defense"):
        for g in mia.GRADES:
            _clear_corners(art_icons.resolve(f"emblem:manual:{'iron_fist' if typ == 'attack' else 'parrying_arm'}:{g}")[0])
    assert art_icons.resolve("emblem:manual:no_such_technique:Mortal") is None


def test_technique_medallions_are_round_with_a_gold_rim():
    for key in technique.TECHNIQUES:
        im = np.asarray(Image.open(art_icons.resolve("tech:" + key)[0]).convert("RGBA")).astype(int)
        n = im.shape[0]
        assert im[2, 2, 3] <= 8 and im[n // 2, n // 2, 3] == 255
        rim = im[round(n * 0.03), n // 2]                                    # the top of the circle: gold
        assert rim[3] > 200 and rim[0] > rim[2] + 40, key
