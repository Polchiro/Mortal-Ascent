"""The painted pills (scripts/make_pill_art.py, docs/alchemy.md "Pill pictures"): all 26 cut out on a clear square
with no ring, every pill the same size so the grades line up."""
import numpy as np
from PIL import Image

from cards import art_icons, theme
from scripts import make_pill_art as mpa


def test_every_pill_has_a_cut_out_painting_of_the_same_size():
    kinds = [f"emblem:pill:{k}:{g.capitalize()}" for k in mpa.KINDS for g in mpa.GRADES] + ["emblem:pill:heaven_defying"]
    assert len(kinds) == 26
    widths = []
    for kind in kinds:
        hit = art_icons.resolve(kind)
        assert hit, kind
        a = np.asarray(Image.open(hit[0]).convert("RGBA"))[..., 3]
        assert a.shape == (mpa.ICON, mpa.ICON), kind
        assert a[:6, :6].max() == 0 and a[-6:, -6:].max() == 0, kind              # clear corners: no ring, no backdrop
        assert a[mpa.ICON // 2, mpa.ICON // 2] == 255, kind                       # the pill sits in the middle, whole
        row = np.nonzero(a[mpa.ICON // 2] > 200)[0]
        widths.append(row.max() - row.min())
    assert max(widths) - min(widths) < mpa.ICON * 0.12                             # the pills line up (mist aside)


def test_the_cards_draw_the_painting_with_its_pattern_dots():
    img = Image.new("RGBA", (400, 400), (0, 0, 0, 255))
    assert theme.painted(img, "emblem:pill:mending:Earth:3", (100, 100), 60)
    assert art_icons.resolve("emblem:pill:mending:Earth:3")[1] == 3


def test_grids_name_every_pill_once():
    names = [n for g in mpa.GRIDS.values() for n in g]
    assert len(names) == len(set(names)) == 26 and "heaven_defying" in mpa.GRIDS["qi"]
