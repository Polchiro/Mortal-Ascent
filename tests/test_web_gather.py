"""Gathering on the website (docs/web.md, "Gathering"): the bot's own /gather engine, refereed on the server."""
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import alchemy  # noqa: E402
from bot import db, gathering  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402
from web import gather_play  # noqa: E402

UID = 779


def player(path):
    c = db.connect(path)
    p = db.get_player(c, UID)
    c.close()
    return p


def herbs(path):
    c = db.connect(path)
    n = sum(h["qty"] for h in db.get_items(c, UID, "herbs"))
    c.close()
    return n


def set_player(path, **fields):
    c = db.connect(path)
    db.update_player(c, UID, **fields)
    c.close()


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Gatherer", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, spirit_check_in=999)
    c.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "gath", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=db_path, session_secret="s"))
    c = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c.get("/login").headers["location"]).query)
    c.get("/callback", params={"code": "x", "state": q["state"][0]})
    c.now = [1000.0]
    app.state.gathers.clock = lambda: c.now[0]
    c.gathers = app.state.gathers
    return c


def begin(client):
    r = client.post("/gather/begin")
    return client.gathers.get(UID), r


def test_gather_page_and_nav(client):
    page = client.get("/gather")
    assert page.status_code == 200 and "Start gathering" in page.text and "Herbal Insight" in page.text
    assert 'href="/gather"' in page.text and "Heaven" in page.text


def test_begin_shows_a_round_with_choices(client):
    s, r = begin(client)
    assert r.headers["location"] == "/gather/play"
    page = client.get("/gather/play").text
    rnd = s.g.round
    assert rnd.herb["name"] in page and "You are looking for" in page
    assert page.count('class="plantcard') == alchemy.GATHER_CHOICES or rnd.old
    for _, look, _ in rnd.options:
        assert look.split()[0] in page
    assert client.get("/gather").headers["location"] == "/gather/play"       # one trip at a time
    assert client.post("/gather/begin").headers["location"] == "/gather/play" and client.gathers.get(UID) is s


def test_the_round_page_never_tells_which_choice_is_real(client):
    s, _ = begin(client)
    rnd = s.g.round
    page = client.get("/gather/play").text
    for key, name in rnd.names.items():
        if key != rnd.answer:
            assert name not in page                    # the other plants' names stay on the server
    assert "right" not in page.split('class="plants')[1].split("</form>")[0]
    assert page.count(rnd.herb["name"]) >= 1
    # pictures are asked for by position, and only for the page now showing
    assert client.get(f"/gather/plant/{s.turn}/{rnd.answer}.png").headers["content-type"] == "image/png"
    assert client.get(f"/gather/plant/{s.turn + 1}/{rnd.answer}.png").status_code == 404
    assert client.get(f"/gather/plant/{s.turn}/o9.png").status_code == 404


def test_a_right_pick_stores_the_herb_and_builds_the_streak(client, db_path):
    s, _ = begin(client)
    rnd = s.g.round
    client.now[0] += 2
    client.post("/gather/pick", data={"key": rnd.answer, "turn": s.turn})
    assert herbs(db_path) == 1 and player(db_path)["herb_streak"] == 1 and player(db_path)["herbs_gathered"] == 1
    page = client.get("/gather/play").text
    assert "You gather" in page or "pull it free" in page
    assert "plantcard right" in page and "Gather again" in page
    for name in rnd.names.values():                    # after the pick every plant is named
        assert name in page


def test_a_decoy_poisons_and_resets_the_streak(client, db_path):
    set_player(db_path, herb_streak=7)
    s, _ = begin(client)
    rnd = s.g.round
    decoy = next(iter(rnd.decoys))
    client.post("/gather/pick", data={"key": decoy, "turn": s.turn})
    assert herbs(db_path) == 0 and player(db_path)["herb_streak"] == 0 and s.g.hp < s.g.max_hp
    page = client.get("/gather/play").text
    assert "look-alike" in page and "plantcard wrong" in page and "plantcard right" in page


def test_old_pages_and_unknown_choices_are_ignored(client, db_path):
    s, _ = begin(client)
    rnd, turn = s.g.round, s.turn
    client.post("/gather/pick", data={"key": "o9", "turn": turn})
    client.post("/gather/pick", data={"key": rnd.answer, "turn": turn + 3})
    assert s.g.round is rnd and herbs(db_path) == 0
    client.post("/gather/pick", data={"key": rnd.answer, "turn": turn})
    client.post("/gather/pick", data={"key": rnd.answer, "turn": turn})      # the same page sent twice
    assert herbs(db_path) == 1
    client.post("/gather/again", data={"turn": turn})                        # an old page's button
    assert s.g.round is None


def test_too_slow_misses_even_with_the_right_answer(client, db_path):
    set_player(db_path, herb_streak=4)
    s, _ = begin(client)
    rnd = s.g.round
    client.now[0] += rnd.seconds + gathering.TIMER_GRACE_SECONDS + 0.5
    client.post("/gather/pick", data={"key": rnd.answer, "turn": s.turn})
    assert herbs(db_path) == 0 and player(db_path)["herb_streak"] == 0
    assert "Too slow" in client.get("/gather/play").text


def test_gather_again_then_stop(client, db_path):
    s, _ = begin(client)
    client.post("/gather/pick", data={"key": s.g.round.answer, "turn": s.turn})
    client.post("/gather/again", data={"turn": s.turn})
    assert s.g.round is not None
    before = player(db_path)["herb_streak"]
    client.post("/gather/stop", data={"turn": s.turn})                        # mid-round: counts as missed
    assert s.g.over and player(db_path)["herb_streak"] == 0 and before == 1
    page = client.get("/gather/play").text
    assert "The trip ends" in page and "head home" in page and "1 ×" in page
    s2, _ = begin(client)                                                     # a fresh trip
    assert s2 is not s and not s2.g.over


def test_walking_away_ends_the_trip(client, db_path):
    s, _ = begin(client)
    client.now[0] += gather_play.IDLE_SECONDS + 60
    assert "Dusk falls" in client.get("/gather/play").text and s.g.over
    assert client.post("/gather/done").headers["location"] == "/gather" and client.gathers.get(UID) is None


def test_the_wandering_spirit_check(client, db_path):
    set_player(db_path, spirit_check_in=0)
    s, _ = begin(client)
    rnd = s.g.round
    assert rnd.kind == "spirit"
    page = client.get("/gather/play").text
    assert "Wandering Spirit" in page and page.count('class="btn btn-gold sign"') == 4
    wrong = next(k for k, _, _ in rnd.options if k != rnd.answer)
    client.post("/gather/pick", data={"key": wrong, "turn": s.turn})
    assert player(db_path)["spirit_check_fails"] == 1
    client.post("/gather/again", data={"turn": s.turn})
    assert s.g.round.kind == "spirit"                                         # it still blocks the way
    client.post("/gather/pick", data={"key": s.g.round.answer, "turn": s.turn})
    assert player(db_path)["spirit_check_fails"] == 0 and "not a puppet" in client.get("/gather/play").text


def test_a_spirit_pause_blocks_gathering(client, db_path):
    set_player(db_path, gather_paused_until=1000.0 + 600)
    page = client.get("/gather").text
    assert "Wandering Spirit" in page and "disabled" in page.split("Start gathering")[0][-60:]
    s, r = begin(client)
    assert s is None and r.headers["location"] == "/gather"


def test_many_rounds_in_a_row(client, db_path):
    s, _ = begin(client)
    got = 0
    for _ in range(25):
        rnd = s.g.round
        client.now[0] += 1.5
        client.post("/gather/pick", data={"key": rnd.answer, "turn": s.turn})
        assert client.get("/gather/play").status_code == 200
        got += 1
        client.post("/gather/again", data={"turn": s.turn})
        assert client.get("/gather/play").status_code == 200
    assert herbs(db_path) == got and player(db_path)["herb_streak"] == got
