"""The live /gather cards: every plant picture, the herb field card for every tier, results and the spirit."""
import random

import pytest
from PIL import ImageChops

import alchemy
from bot import db, gather_card, gathering
from bot import player as rules
from cards import herbfield, plants


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, realm=None):
    db.create_player(conn, uid, "Tester", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(conn, uid, spirit_check_in=999, **({"realm": realm} if realm else {}))


ALL_PLANTS = [n for t in alchemy.HERBS.values() for n, _ in t.values()] + [n for d in alchemy.DECOYS.values() for n, _ in d]


@pytest.mark.parametrize("name", ALL_PLANTS)
def test_every_herb_and_decoy_has_a_picture(name):
    kind, _ = plants.PLANTS[name]
    assert kind in plants.KINDS
    img = plants.plant(name)
    assert img.getbbox() is not None                 # something was drawn


def test_every_plant_kind_can_be_drawn():
    from PIL import Image
    for kind in plants.KINDS:
        img = Image.new("RGBA", plants.P(plants.PW, plants.PH), (0, 0, 0, 0))
        plants.DRAW[kind](img, {"color": (200, 200, 200), "face": "N", "sky": "moon"})
        assert img.getbbox() is not None


def test_a_decoy_looks_different_from_its_herb():
    """Each decoy's picture differs from the herb it imitates (its one wrong detail is drawn)."""
    pairs = [("Spirit Grass", "Ghost Grass"), ("Red Berry", "Bitter Nettle"), ("Sun Ginseng", "Fool's Ginseng"),
             ("Silver Moss", "Snake Moss"), ("Moon Mushroom", "Shadow Mushroom"), ("Jade Lily", "Weeping Lily"),
             ("Golden Ginseng", "Grave Ginseng"), ("Phoenix Flower", "Fire Thorn"), ("Heaven Lotus", "Demon Lotus"),
             ("Immortal Peach", "Void Fruit")]
    decoys = {n for d in alchemy.DECOYS.values() for n, _ in d}
    assert {d for _, d in pairs} == decoys
    for herb, decoy in pairs:
        assert plants.PLANTS[herb][0] == plants.PLANTS[decoy][0]          # same kind of plant ...
        diff = ImageChops.difference(plants.plant(herb).convert("RGB"), plants.plant(decoy).convert("RGB")).getbbox()
        assert diff is not None                                           # ... drawn with its one difference


@pytest.mark.parametrize("tier", alchemy.GRADES)
def test_field_card_renders_for_every_herb_tier(conn, tier, monkeypatch):
    new_player(conn, realm="Mortal")
    monkeypatch.setattr(gathering.loot, "herb_tier", lambda realm, rng=None: tier)
    g = gathering.Gathering(conn, 1, random.Random(2))
    r = g.next_round()
    assert r.kind == "herb" and r.herb["grade"] == tier
    data = gather_card.field_data(g, g.player, r)
    assert data["rarity"] == alchemy.HERB_RARITY[tier][0]
    assert [c["look"] for c in data["choices"]] == [label for _, label, _ in r.options]
    assert herbfield.render_field(data).size == (herbfield.W, herbfield.H)


def test_old_herb_round_has_six_choices_on_the_card(conn):
    new_player(conn, realm="Martial King")
    g = gathering.Gathering(conn, 1, random.Random(0))
    for seed in range(400):
        g.rng = random.Random(seed)
        r = g._herb_round(g.player)
        if r.old:
            break
    assert r.old and len(r.options) == alchemy.OLD_HERB_CHOICES
    data = gather_card.field_data(g, g.player, r)
    assert herbfield.render_field(data).size == (herbfield.W, herbfield.H)


@pytest.mark.parametrize("pick", ["answer", "decoy", "other", None])
def test_result_card_after_each_kind_of_pick(conn, pick):
    new_player(conn)
    g = gathering.Gathering(conn, 1, random.Random(5))
    r = g.next_round()
    key = {"answer": r.answer, "decoy": next(iter(r.decoys)), None: None,
           "other": next((k for k, _, _ in r.options if k != r.answer and k not in r.decoys), next(iter(r.decoys)))}[pick]
    text = g.answer(key, 1.0)
    data = gather_card.field_data(g, g.player, r, text, key)
    expected = {"answer": "gathered", "decoy": "poison", None: "slow", "other": "wrong"}[pick]
    if pick == "other" and key in r.decoys:
        expected = "poison"
    assert data["result"]["outcome"] == expected
    assert herbfield.render_field(data).size == (herbfield.W, herbfield.H)


def test_session_panel_counts_herbs_by_age(conn):
    new_player(conn)
    from bot import loot
    g = gathering.Gathering(conn, 1, random.Random(5))
    g.gathered = [loot.herb("Mortal", "qi", 10), loot.herb("Mortal", "qi", 10), loot.herb("Mortal", "purity", 100)]
    data = gather_card.field_data(g, g.player, g.next_round())
    assert data["gathered"] == 3 and data["best"] == "100-year Dew Leaf"
    assert [(row["name"], row["qty"]) for row in data["session"]] == [("Dew Leaf", 1), ("Spirit Grass", 2)]


def test_streak_bonus_matches_the_rules():
    assert gather_card.streak_bonus(0) == (1.0, (10, 1.5))
    assert gather_card.streak_bonus(14) == (1.5, (25, 2.0))
    assert gather_card.streak_bonus(60) == (3.0, None)


@pytest.mark.parametrize("ok", [True, False, None])
def test_spirit_card_renders(conn, ok):
    new_player(conn)
    db.update_player(conn, 1, spirit_check_in=0)
    g = gathering.Gathering(conn, 1, random.Random(1))
    r = g.next_round()
    assert r.kind == "spirit"
    text = None
    if ok is not None:
        text = g.answer(r.answer if ok else next(k for k, _, _ in r.options if k != r.answer), 1.0)
    data = gather_card.spirit_data(g, g.player, r, text)
    assert data["sign"] == {k: word for k, _, word in gathering.SPIRIT_SIGNS}[r.answer]
    if ok is not None:
        assert data["result"]["outcome"] == ("passed" if ok else "failed")
    assert herbfield.render_spirit(data).size == (herbfield.W, herbfield.H_SPIRIT)


def test_place_scenes_are_cached():
    herbfield.place_scene.cache_clear()
    for place in gathering.PLACES:
        herbfield.place_scene(place)
        assert place in herbfield.PLACE_NAME
    herbfield.place_scene(gathering.PLACES[0])
    assert herbfield.place_scene.cache_info().hits == 1
