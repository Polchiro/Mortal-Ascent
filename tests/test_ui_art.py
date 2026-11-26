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
    assert len(rels) == len(set(rels)) == 50
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


def test_the_profile_uses_the_painted_seal_slots_plaque_and_journey():
    from bot import player as rules
    from web.profile import realm_track
    for realm in rules.REALM_ORDER:                              # every realm's seal is a real file
        url = realm_track(realm, 1, 9)["seal"].split("?")[0]
        assert os.path.exists(url.lstrip("/")), realm
    page = open("web/templates/profile.html").read()
    assert 'src="{{ t.seal }}"' in page and "macro emblem" not in page
    assert "s-{{ w.tab }}" in page                              # the empty slot frames by kind
    css = open("web/static/style.css").read()
    for piece in ("slot_weapon", "slot_armor", "slot_artifact", "slot_empty", "name_plaque"):
        assert f"/art/ui/{piece}.webp" in css, piece
    src = open("web/profile.py").read()
    assert "/art/icons/journey/" in src


def test_discord_cards_use_the_journey_and_realm_paintings():
    for deed in ("beasts", "herbs", "breakthroughs", "duels"):
        assert art_icons.resolve("deed:" + deed)[0].endswith(f"journey/{deed}.webp")
    assert art_icons.resolve("emblem:realm:Martial King")[0].endswith("realms/martial_king.webp")
    assert art_icons.resolve("deed:rank") is None               # no painting: still drawn


def test_the_fight_banners_are_dark_inside_and_clear_outside():
    """The fight screens' panels (docs/web.md "Painted UI"): the grooves and the ring filled with dark lacquer so text
    reads on any scene, the corners outside the frame clear."""
    for rel in ("ui/fight_me", "ui/fight_foe", "ui/fight_omen", "ui/fight_toast", "ui/fight_pill"):
        im = np.asarray(Image.open(os.path.join(ART, rel + ".webp")).convert("RGBA"))
        h, w = im.shape[:2]
        assert im[0, 0, 3] < 20 and im[-1, -1, 3] < 60, rel
        assert im[h // 2, w // 2, 3] > 180 and im[h // 2, w // 2, :3].max() < 60, rel     # dark lacquer in the middle
    for rel in ("ui/foe_ring_normal", "ui/foe_ring_elite", "ui/foe_ring_boss"):
        a = alpha(rel)
        assert a[a.shape[0] // 2, a.shape[1] // 2] < 20, rel                              # the face shows through


def test_the_beast_fight_spar_and_duel_use_the_painted_banners():
    css = open("web/static/style.css").read()
    for piece in ("fight_me", "fight_foe", "fight_omen", "fight_toast", "fight_pill", "foe_ring_elite", "foe_ring_boss"):
        assert f"/art/ui/{piece}.webp" in css, piece
    assert "rank-{{ F.enemy.tier" in open("web/templates/explore_play.html").read()       # Elite / Beast King ring
    assert 'class="dface sface" src="{{ s.master.img }}"' in open("web/templates/spar.html").read()
    for page in ("explore_play", "spar", "duel"):                                        # all share the .bme / .benemy plates
        t = open(f"web/templates/{page}.html").read()
        assert 'class="bme' in t and 'class="benemy' in t, page
