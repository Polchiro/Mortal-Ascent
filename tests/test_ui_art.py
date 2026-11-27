"""The painted UI pieces (scripts/make_ui_art.py): every one there with clear edges, the currencies used by the
website purse and the Discord cards."""
import os

import numpy as np
from PIL import Image

from cards import art_icons
from scripts import make_ui_art as mua

ART = mua.ART


def alpha(rel):
    return np.asarray(Image.open(os.path.join(ART, rel + ".webp")).convert("RGBA"))[..., 3]


def test_every_piece_is_there_with_clear_edges():
    rels = [rel for jobs in mua.JOBS.values() for _, _, rel in jobs]
    assert len(rels) == len(set(rels)) == 42
    for rel in rels:
        a = alpha(rel)
        assert a[:3, :3].max() <= 8 and a[-3:, -3:].max() <= 8, rel           # nothing left in the corners
        assert (a > 128).mean() > 0.03, rel


def test_frames_are_clear_in_the_middle():
    for rel in ("ui/hero_plate", "ui/name_plaque", "ui/ring", "ui/seal_ring"):
        a = alpha(rel)
        h, w = a.shape
        x = w * 2 // 3 if rel in ("ui/hero_plate", "ui/name_plaque") else w // 2
        assert a[h // 2, x] <= 20, rel                                         # the page's own content shows through


def test_eight_blessings_and_eleven_realms():
    assert len([j for j in mua.JOBS["blessings1"] + mua.JOBS["blessings2"]]) == 8
    import economy
    from bot import player
    for tier in economy.BLESSING_TIERS:
        assert os.path.exists(os.path.join(ART, "icons", "blessings", art_icons.slug(tier) + ".webp")), tier
    for realm in player.REALM_ORDER:
        assert os.path.exists(os.path.join(ART, "icons", "realms", art_icons.slug(realm) + ".webp")), realm


def test_the_currencies_are_painted_on_the_web_and_the_cards():
    page = open("web/templates/_purse.html").read()
    assert "/art/icons/currency/moon_pearl.webp" in page and "/art/icons/currency/lotus_coin.webp" in page
    assert art_icons.resolve("deed:lotus_coin")[0].endswith("currency/lotus_coin.webp")
    from cards import purse
    img = Image.new("RGBA", (400, 400), (0, 0, 0, 255))
    assert purse.painted(img, (100, 100), 40, "moon_pearl", (200, 220, 255, 120))
    assert not purse.painted(img, (100, 100), 40, "no_such_thing", (0, 0, 0, 0))
