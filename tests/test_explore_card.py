"""The live /explore cards: the crossroads, every encounter scene, the button icons and the message they go in."""
import asyncio
import random

import pytest

import explore
from bot import db, explore_card
from bot import player as rules
from bot.expedition import CLUES, Expedition
from cards import expedition as card, wild_icons


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, realm=None):
    db.create_player(conn, uid, "Tester", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    if realm:
        db.update_player(conn, uid, realm=realm)


def expedition_on(conn, kind, seed=0):
    """An expedition whose left path leads to `kind`, already chosen."""
    exp = Expedition(conn, 1, random.Random(seed))
    exp.next_step()
    exp.paths["left"] = (kind, CLUES[kind][0])
    exp.choose("left")
    return exp


# ── data ──────────────────────────────────────────────────────────────

def test_every_clue_has_a_label_and_every_kind_a_mood():
    for kind, clues in CLUES.items():
        assert kind in card.MOOD and kind in card.MOOD_FN and kind in explore_card.TITLE
        for clue in clues:
            assert explore_card.CLUE_LABEL[clue] and explore_card.clue_kind(clue) == kind
    assert set(CLUES) == set(explore.ENCOUNTERS)


def test_a_misleading_clue_is_drawn_as_what_it_says(conn):
    new_player(conn)
    exp = Expedition(conn, 1, random.Random(0))
    exp.next_step()
    exp.paths["left"] = ("wild_beast", "A faint golden glow...")        # a beast behind a treasure clue
    data = explore_card.crossroads_data(exp)
    assert data["paths"]["left"]["kind"] == "treasure_chest"
    assert data["paths"]["left"]["label"] == "A GOLDEN GLOW"


def test_crossroads_data_shows_depth_bonus_and_lying_clues(conn):
    new_player(conn, realm="Martial Expert")           # tier 2+: clues can lie
    exp = Expedition(conn, 1, random.Random(0))
    exp.next_step()
    exp.next_step()
    data = explore_card.crossroads_data(exp)
    assert data["step"] == 2 and "+10%" in data["bonus"] and "1.25" in data["bonus"]
    import challenges
    lie = explore.MISLEADING_CLUE_CHANCE[challenges.REALM_TIER["Martial Expert"]]
    assert lie > 0 and f"{lie:.0%}" in data["lie_note"]
    new_player(conn, uid=2)
    exp2 = Expedition(conn, 2, random.Random(0))
    exp2.next_step()
    assert explore_card.crossroads_data(exp2)["lie_note"] == ""


def test_found_tiles_count_the_same_find_together(conn):
    new_player(conn)
    from bot import loot
    exp = Expedition(conn, 1, random.Random(0))
    exp.next_step()
    exp.items = [loot.herb("Mortal", "qi", 10), loot.herb("Mortal", "qi", 10), loot.chest("wooden")]
    tiles = explore_card.crossroads_data(exp)["items"]
    assert [t["qty"] for t in tiles] == [2, 1]


def test_choosing_a_path_does_not_change_what_happens(conn):
    """The card only reads the expedition: same seed, same story, with or without building the card."""
    new_player(conn)
    new_player(conn, uid=2)
    a, b = Expedition(conn, 1, random.Random(4)), Expedition(conn, 2, random.Random(4))
    for exp in (a, b):
        exp.next_step()
    explore_card.crossroads_data(a)
    a.choose("middle")
    b.choose("middle")
    explore_card.encounter_data(a)
    assert a.paths == b.paths and a.story == b.story and a.hp == b.hp and a.coins == b.coins


# ── rendering ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", list(explore.ENCOUNTERS))
def test_crossroads_renders_every_clue_kind(conn, kind):
    new_player(conn)
    exp = Expedition(conn, 1, random.Random(0))
    exp.next_step()
    exp.paths["middle"] = ("wild_beast", CLUES[kind][1])
    img = card.render_crossroads(explore_card.crossroads_data(exp))
    assert img.size == (card.W, card.H)


@pytest.mark.parametrize("kind", list(explore.ENCOUNTERS))
def test_every_encounter_renders(conn, kind):
    new_player(conn)
    exp = expedition_on(conn, kind)
    if exp.pending == "fight":                      # beasts and bandits: the fight screen plays, then the result
        exp.battle.result = "won"
        exp.end_fight()
        assert explore_card.encounter_data(exp)["fight"]
    data = explore_card.encounter_data(exp, notice="You already bought that.")
    assert data["kind"] == kind and data["story"]
    img = card.render_encounter(data)
    assert img.size == (card.W, card.H)


def test_hazard_card_shows_where_it_comes_from(conn):
    new_player(conn)
    exp = expedition_on(conn, "hazard")
    data = explore_card.encounter_data(exp)
    assert data["hazard"]["danger"] == exp.hazard["danger"] and data["title"].endswith("!")
    assert card.render_encounter(data).size == (card.W, card.H)


def test_scenes_are_cached():
    card.crossroads_scene.cache_clear()
    card.crossroads_scene("wild_beast", "treasure_chest", "peaceful_clearing")
    card.crossroads_scene("wild_beast", "treasure_chest", "peaceful_clearing")
    assert card.crossroads_scene.cache_info().hits == 1
    card.mood("hazard")
    before = card.mood.cache_info().hits
    card.mood("hazard")
    assert card.mood.cache_info().hits == before + 1


@pytest.mark.parametrize("key", list(wild_icons.ICONS))
def test_button_icons_render(key):
    assert wild_icons.icon_png(key)[:4] == b"\x89PNG"
    assert key in wild_icons.FALLBACK


# ── the message ───────────────────────────────────────────────────────

class FakeBot:
    def __init__(self, conn):
        self.conn, self.db_lock, self.busy = conn, asyncio.Lock(), set()


class Response:
    def __init__(self):
        self.done = False

    def is_done(self):
        return self.done

    async def defer(self, **kw):
        self.done = True


class Interaction:
    def __init__(self):
        self.user = type("U", (), {"id": 1})()
        self.response = Response()
        self.edits = []

    async def edit_original_response(self, **kw):
        self.edits.append(kw)

    async def original_response(self):
        return None


def test_explore_message_is_a_live_jpeg_card(conn):
    from bot.views import ExploreView
    new_player(conn)

    async def go():
        view = ExploreView(FakeBot(conn), 1, random.Random(0))
        assert [c.label for c in view.children] == ["Left", "Middle", "Right", "Return safely"]
        it = Interaction()
        await view.send(it)
        kw = it.edits[-1]
        assert kw["attachments"][0].filename == "explore.jpg" and "Step 1 of 5" in kw["content"]
        view.exp.paths["left"] = ("treasure_chest", CLUES["treasure_chest"][0])
        it = Interaction()
        await view.children[0].callback(it)
        kw = it.edits[-1]
        assert kw["attachments"][0].filename == "explore.jpg" and "Hidden under the roots" in kw["content"]
        assert "Go deeper" in [c.label for c in view.children]
        it = Interaction()
        await next(c for c in view.children if c.label == "Go deeper").callback(it)
        assert view.choosing and view.exp.step == 2
        it = Interaction()
        await next(c for c in view.children if c.label == "Return safely").callback(it)
        assert view.exp.over and it.edits[-1]["attachments"][0].filename == "explore.png"
    asyncio.run(go())


def test_explore_cards_use_the_painted_scenes(conn):
    from cards import scenes
    new_player(conn)
    exp = Expedition(conn, 1, random.Random(0))
    exp.next_step()
    data = explore_card.crossroads_data(exp)
    assert scenes.exists(scenes.REGION[data["region"]])
    assert card.render_crossroads(data).size == (card.W, card.H)
    for kind in ("treasure_chest", "wandering_merchant", "blessed_land", "injured_stranger"):   # last: no art yet
        exp.encounter = kind
        assert card.render_encounter(explore_card.encounter_data(exp)).size == (card.W, card.H)
