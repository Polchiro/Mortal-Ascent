"""Drawn icons and emblems: every technique, grade, rarity, realm, beast tier, element and pill type has one,
and the cards use them instead of seal characters."""
import random

import pytest
from PIL import Image, ImageChops

import beasts
import equipments
import talent as talent_rules
import technique
from bot import compendium, crafting, loot
from bot import player as rules
from bot.sheet import items
from cards import battle_icons
from cards import emblems as E
from cards import theme as T
from cards.technique_icons import SCHOOL_ICON, TECH_ICON, tech_kind


def drawn(fn, size):
    """Draw at `size` on a transparent canvas; return the image (at S×)."""
    img = Image.new("RGBA", T.P(size * 2, size * 2), (0, 0, 0, 0))
    fn(img, (size, size), size)
    return img


def ink(img):
    """How many pixels were painted."""
    return img.getchannel("A").point(lambda v: 255 if v > 40 else 0).histogram()[255]


def assert_distinct(images):
    for i, a in enumerate(images):
        for b in images[i + 1:]:
            assert ImageChops.difference(a, b).getbbox(alpha_only=False) is not None


# ── techniques ────────────────────────────────────────────────────────

def test_every_technique_has_its_own_icon():
    assert set(TECH_ICON) == set(technique.TECHNIQUES)
    for key, t in technique.TECHNIQUES.items():
        assert tech_kind(t["name"], t["school"]) == "tech:" + key
    imgs = [drawn(lambda img, c, s, k=k: T.icon(img, "tech:" + k, c, s, T.GOLD), 48) for k in TECH_ICON]
    assert all(ink(i) > 200 for i in imgs)
    assert_distinct(imgs)


def test_every_school_has_a_base_shape_and_unknown_techniques_fall_back_to_it():
    assert set(SCHOOL_ICON) == {t["school"] for t in technique.TECHNIQUES.values()}
    assert tech_kind("Some Future Palm", "Palm") == "school:Palm"
    for s in SCHOOL_ICON:
        assert ink(drawn(lambda img, c, size: T.icon(img, "school:" + s, c, size, T.GOLD), 24)) > 30


@pytest.mark.parametrize("size", [24, 100])
def test_technique_icons_draw_small_and_large(size):
    for k in TECH_ICON:
        assert ink(drawn(lambda img, c, s: T.icon(img, "tech:" + k, c, s, T.GOLD), size)) > 0


# ── emblems ───────────────────────────────────────────────────────────

SETS = {
    "grade": list(technique.GRADES),
    "rarity": list(equipments.TIERS),
    "realm": list(rules.REALM_ORDER),
    "beast_tier": list(beasts.BEAST_TIERS),
    "element": list(beasts.ELEMENTS),
    "pill": list(crafting.KINDS),
    "talent": list(talent_rules.TALENTS),
}


@pytest.mark.parametrize("kind", list(SETS))
def test_every_step_of_every_set_has_an_emblem(kind):
    keys = SETS[kind]
    assert all(E.has_emblem(kind, k) for k in keys)
    for size in (24, 100):
        imgs = [drawn(lambda img, c, s, k=k: E.emblem(img, kind, k, c, s), size) for k in keys]
        assert all(ink(i) > 100 for i in imgs)
        assert_distinct(imgs)


def test_pills_are_tinted_by_grade_with_pattern_rings():
    imgs = [drawn(lambda img, c, s, g=g: E.emblem(img, "pill", "qi", c, s, grade=g), 100) for g in technique.GRADES]
    assert_distinct(imgs)
    plain = drawn(lambda img, c, s: E.emblem(img, "pill", "qi", c, s, grade="Earth"), 100)
    ringed = drawn(lambda img, c, s: E.emblem(img, "pill", "qi", c, s, grade="Earth", patterns=9), 100)
    assert ImageChops.difference(plain, ringed).getbbox(alpha_only=False) is not None


def test_icon_kinds_cover_beast_tiles_manuals_and_the_book():
    for kind in ("emblem:beast:Martial King:Flame", "emblem:manual:iron_fist:Mortal", "emblem:pill:breakthrough:Heaven:9",
                 "emblem:book", "emblem:element:Frost"):
        assert ink(drawn(lambda img, c, s: T.icon(img, kind, c, s, T.GOLD), 60)) > 100
    assert E.icon_png("emblem:rarity:divine")[:8] == b"\x89PNG\r\n\x1a\n"


def test_empty_slots_are_faint_outlines():
    for kind in ["armor", "artifact"] + ["school:" + s for s in SCHOOL_ICON]:
        img = drawn(lambda img, c, s: E.empty_slot(img, kind, c, s), 60)
        assert 0 < ink(img) < (120 * T.S) ** 2 * 0.3       # an outline, not a filled shape


# ── where they are used ───────────────────────────────────────────────

def is_cjk(s):
    return any("㐀" <= ch <= "鿿" for ch in s)


def test_bag_tabs_and_gear_use_drawn_icons():
    assert items.CATEGORIES["armor"].icon == "gear:robe" and items.CATEGORIES["artifacts"].icon == "pearl"
    assert not any(is_cjk(c.icon) for c in items.CATEGORIES.values())
    armor = loot.roll_armor("spirit", random.Random(1))
    assert items.item_icon(armor) == "gear:" + armor["key"]
    assert items.item_icon(loot.artifact("bell", "divine")) == "gear:bell"
    assert items.item_icon(loot.manual("iron_fist")) == "emblem:manual:iron_fist:Mortal"
    assert items.item_icon(loot.pill("Yellow")) == "emblem:pill:qi:Yellow:0"
    assert items.item_icon(crafting.crafted_pill("mending", "Earth", 5)) == "emblem:pill:mending:Earth:5"


def test_compendium_uses_emblems_not_seal_characters():
    for section in compendium.SECTIONS:
        for key, seal, label, color in compendium.tiers(section):
            assert not is_cjk(seal), (section, key)
        pages = [compendium.tier_page(section)] + [compendium.tier_page(section, t[0]) for t in compendium.tiers(section)]
        for p in pages:
            assert not is_cjk(p["seal"])
            for t in p["tiles"]:
                assert not is_cjk(t["glyph"]), (section, t["name"])
    assert compendium.tier_page("beasts")["seal"] == "emblem:book"
    beast = compendium.tier_page("beasts", "Martial King")["tiles"][0]
    assert beast["glyph"].startswith("emblem:beast:Martial King:")


def test_rare_drop_announcements_carry_their_emblem():
    a = loot.announcement("Ana", {"category": "weapons", "name": "X", "grade": "divine"})
    assert a.icon == "emblem:rarity:divine"
    m = loot.manual("heaven_rending_palm")
    assert loot.announcement("Ana", m).icon == "emblem:manual:heaven_rending_palm:Heaven"
    assert loot.announcement("Ana", loot.HEAVEN_DEFYING).icon.startswith("emblem:pill:")


def test_fight_buttons_have_a_drawn_icon_per_technique_with_short_emoji_names():
    for key in technique.TECHNIQUES:
        k = "t_" + key
        assert k in battle_icons.ICONS and k in battle_icons.FALLBACK
        assert len("ma_" + battle_icons.EMOJI_NAME.get(k, k)) <= 32
    assert not any(v[2] for v in battle_icons.ICONS.values())        # no seal characters left
    names = ["ma_" + battle_icons.EMOJI_NAME.get(k, k) for k in battle_icons.ICONS]
    assert len(set(names)) == len(names)
    assert battle_icons.tech_emoji_key("Nine Dragons Ascending Fist") == "t_nine_dragons_ascending_fist"
    assert battle_icons.icon_png("t_iron_fist")[:4] == b"\x89PNG"


# ── /internal qi, talents, herbs and /craft ───────────────────────────

def test_every_talent_has_an_emblem():
    assert set(E.TALENTS) == set(T.TALENT)


def test_qi_sources_use_drawn_icons():
    import time

    from bot import db, qi
    conn = db.connect(":memory:")
    db.create_player(conn, 1, "Ana", "Genius", 0, rules.starting_techniques())
    p = db.get_player(conn, 1)
    rows = qi.sources(p, db.get_techniques(conn, 1), time.time())
    assert rows and not any(is_cjk(r["seal"]) for r in rows)
    assert rows[0]["seal"] == "emblem:realm:Mortal" and rows[1]["seal"] == "emblem:talent:Genius"
    for r in rows:
        assert ink(drawn(lambda img, c, s: T.seal(img, c, s / 2, r["seal"], T.EMBER), 40)) > 100


def test_herbs_craft_stages_and_craft_buttons_are_drawn():
    import alchemy
    from cards import alchemy_icons
    from cards.misc_icons import HERB_ICON, MISC_ICON, STAGE_ICON
    assert set(alchemy.HERB_TYPE_CHANCE) <= set(HERB_ICON)
    assert set(STAGE_ICON) == {1, 2, 3, 4, 5, 6}
    for kind in list(HERB_ICON.values()) + list(STAGE_ICON.values()):
        assert ink(drawn(lambda img, c, s: T.icon(img, kind, c, s, T.GOLD), 40)) > 100
    assert_distinct([drawn(lambda img, c, s, k=k: T.icon(img, "misc:" + k, c, s, T.GOLD), 40) for k in MISC_ICON])
    assert not any(v[2] for v in alchemy_icons.ICONS.values())
    names = ["ma_" + alchemy_icons.EMOJI_NAME.get(k, k) for k in alchemy_icons.ICONS]
    assert len(set(names)) == len(names) and all(len(n) <= 32 for n in names)
