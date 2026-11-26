"""The painted forging materials (scripts/make_material_art.py, docs/forge.md "Pictures"): every one of the 70 has
its picture, cut out on a clear square with no ring, and the essences are the three shapes in each family's colour."""
import os

import numpy as np
from PIL import Image

import forge
from cards import art_icons, theme
from scripts import make_material_art as mma

MATS = forge.all_materials()


def test_every_material_has_a_cut_out_painting():
    assert len(MATS) == 70
    for key in MATS:
        hit = art_icons.resolve("mat:" + key)
        assert hit, key
        im = Image.open(hit[0])
        assert im.mode == "RGBA" and im.size == (mma.ICON, mma.ICON), key
        a = np.asarray(im)[..., 3]
        assert a[:6, :6].max() == 0 and a[-6:, -6:].max() == 0, key          # clear corners: no ring, no backdrop
        assert 0.12 < (a > 128).mean() < 0.8, key                           # an object, not an empty square


def test_essences_are_the_three_shapes_tinted_per_family():
    fams = {k.split(":")[1] for k in MATS if k.startswith("essence:")}
    assert len(fams) == 13
    for shape in mma.SHAPES:
        base = np.asarray(Image.open(os.path.join(mma.OUT, f"essence_shape_{shape}.webp")))
        for fam in fams:
            got = np.asarray(Image.open(os.path.join(mma.OUT, f"essence_{fam}_{shape}.webp")))
            assert (got[..., 3] == base[..., 3]).all()                       # same outline, only the colour differs
    frost = np.asarray(Image.open(os.path.join(mma.OUT, "essence_frost_heart.webp"))).astype(int)
    flame = np.asarray(Image.open(os.path.join(mma.OUT, "essence_flame_heart.webp"))).astype(int)
    m = frost[..., 3] > 200
    assert frost[m][:, 2].mean() > frost[m][:, 0].mean() and flame[m][:, 0].mean() > flame[m][:, 2].mean()


def test_the_cards_draw_the_painting():
    img = Image.new("RGBA", (400, 400), (0, 0, 0, 255))
    assert theme.painted(img, "mat:base:weapon:2", (100, 100), 60)
    assert theme.painted(img, "mat:essence:venom:shard", (100, 100), 60)


def test_file_names_match_what_the_cards_look_up():
    assert mma.file_name("base:weapon:2") == "base_weapon_2" and mma.file_name("seal") == "seal"
    assert mma.file_name("shape:heart") == "essence_shape_heart"
    every = [k for keys in mma.GRIDS.values() for k in keys if not k.startswith("shape:")]
    assert sorted(every) == sorted(k for k in MATS if not k.startswith("essence:"))
