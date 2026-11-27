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
    assert len(rels) == len(set(rels)) == 63
    for rel in rels:
        a = alpha(rel)
        if rel in mua.SHAPES:                                                  # a plate cut to its own square-cornered outline
            continue
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


def test_the_move_pictures_are_one_size_discs_with_room_to_spill():
    """The five move pictures (docs/web.md "Painted UI"): the disc the same size in every square, solid inside, so
    each sits in its button's socket the same; the square clear at its corners for the sword, flames and sparks."""
    for move in ("strike", "techniques", "guard", "break", "flee"):
        a = alpha(f"icons/actions/{move}")
        h, w = a.shape
        assert abs(h - w) <= 1 and a[h // 2, w // 2] == 255, move
        r = w / 2 / mua.DISC_REACH
        assert a[h // 2, round(w / 2 - r * 0.9)] > 240 and a[h // 2, round(w / 2 + r * 0.9)] > 240, move
        assert a[:4, :4].max() <= 8, move


def test_the_break_button_has_no_teal_left_and_the_panel_no_tab():
    import cv2
    rgba = np.asarray(Image.open(os.path.join(ART, "ui/move_break.webp")).convert("RGBA"))
    hsv = cv2.cvtColor(np.ascontiguousarray(rgba[..., :3]), cv2.COLOR_RGB2HSV)
    right = (np.arange(rgba.shape[1]) >= rgba.shape[1] * 0.72)[None, :]
    teal = right & (hsv[..., 0] >= 70) & (hsv[..., 0] <= 110) & (hsv[..., 1] > 30) & (hsv[..., 2] > 60) & (rgba[..., 3] > 128)
    assert teal.sum() < 50
    panel = np.asarray(Image.open(os.path.join(ART, "ui/fight_info.webp")).convert("RGB")).astype(int)
    tab = panel[5:40, 40:140]                                               # where the gold tab was: the dark frame now
    assert (tab[..., 0] - tab[..., 2]).mean() < 40


def test_the_fight_screens_use_the_painted_moves():
    css = open("web/static/style.css").read()
    for piece in ("move_strike", "move_techniques", "move_guard", "move_break", "fight_side_pill", "fight_side_flee",
                  "fight_info", "fight_info_tab"):
        assert f"/art/ui/{piece}.webp" in css, piece
    for src in ("web/explore_play.py", "web/static/duel.js", "web/static/spar.js"):           # Techniques: the book
        assert "/art/icons/actions/techniques.webp" in open(src).read(), src


def test_break_through_is_a_slim_pill_beside_the_plate():
    """The map screen's Break Through button (docs/web.md "The map screen"): the slim gold pill, not the big tab."""
    css = open("web/static/style.css").read()
    last = css[css.index("Break through, compact"):]
    assert "/art/ui/fight_pill.webp" in last and "left:calc(var(--pw) + 6px)" in last
    assert "@media (max-width:700px)" in last                                 # under the bars on a phone


def test_the_turns_call_outs_sit_between_the_banners():
    css = open("web/static/style.css").read()
    tail = css[css.index("this turn's call-outs: up in the gap between the two banners"):]
    assert ".bfeed{top:4px;" in tail and "min(30vw,450px)" in tail


def test_phones_give_the_arena_the_room():
    css = open("web/static/style.css").read()
    tail = css[css.index("More room for the fight"):]
    assert 'grid-template-areas:"me enemy" "scene scene" "bar bar" "side hist"' in tail       # plates in one row
    assert ".battle>.binfo .ititle,.battle>.binfo .itext,.battle>.binfo .sub{display:none}" in tail
    assert ".battle>.bhist{grid-row:2;grid-column:1/3;justify-self:start" in tail             # computer: bottom-left


def test_the_map_medallions_can_fold_away():
    page = open("web/templates/_walkui.html").read()
    assert 'id="dockFold"' in page and "ma.dockFolded" in page and "classList.toggle('folded'" in page
    assert ".mdock.folded .dbtn{display:none}" in open("web/static/style.css").read()


def test_the_fight_banners_are_smaller():
    css = open("web/static/style.css").read()
    assert "--bw:min(30vw,450px)" in css and ".battle>.binfo .sub{display:none}" in css
