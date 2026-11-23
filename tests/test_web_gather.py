"""Gathering on the website (docs/world.md "Herbs"): walk up to a herb out in the world and play its round. The
round is the bot's own /gather engine (bot/gathering.py), refereed on the server (web/gather_play.py,
web/overworld.py)."""
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import alchemy  # noqa: E402
from bot import db, gathering  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

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
    app.state.world.clock = lambda: c.now[0]
    c.gathers, c.world = app.state.gathers, app.state.world
    assert c.get("/crossroads").status_code == 200               # out of the gate, into the meadow
    return c


def kneel(client, herb=None):
    """Stand by a herb and kneel: (session, the panel's data, the herb)."""
    st = client.post("/world/state", data={"place": "crossroads"}).json()
    h = herb or st["herbs"][0]
    w = client.world.walker(UID)
    w.x, w.y = h["x"], h["y"]
    g = client.post("/world/gather", data={"place": "crossroads", "id": h["id"], "x": h["x"], "y": h["y"]}).json()
    return client.gathers.get(UID), g, h


def pick(client, key, turn):
    return client.post("/world/gather/pick", data={"key": key, "turn": turn}).json()


def test_the_gather_page_is_gone_and_herbs_grow_in_the_world(client):
    r = client.get("/gather")
    assert r.headers["location"] == "/town"
    assert "herbs grow out in the world" in client.get("/town").text.lower()
    assert 'href="/gather"' not in client.get("/profile").text                # no Gather tab any more
    for gone in ("/gather/begin", "/gather/pick", "/gather/again", "/gather/stop", "/gather/done"):
        assert client.post(gone).status_code in (404, 405)


def test_kneeling_shows_the_round_for_that_herb(client):
    s, g, h = kneel(client)
    rnd = s.g.round
    assert g["mode"] == "round" and rnd.kind == "herb"
    assert rnd.herb["name"] == h["name"] == g["target"]["name"]               # the herb that grew there
    assert rnd.herb["grade"] == h["grade"] and rnd.herb["data"]["type"] == h["type"]
    assert len(g["choices"]) in (alchemy.GATHER_CHOICES, alchemy.OLD_HERB_CHOICES)
    assert "the meadow outside the town walls" in " ".join(g["prompt"])


def test_the_panel_never_tells_which_choice_is_real(client):
    s, g, _ = kneel(client)
    rnd = s.g.round
    flat = str({k: v for k, v in g.items() if k != "world"})               # (the map names herbs growing nearby)
    for key, name in rnd.names.items():
        if key != rnd.answer:
            assert name not in flat                                           # the other plants stay on the server
    assert all(c["state"] is None and c["name"] is None for c in g["choices"])
    turn = s.turn
    assert client.get(f"/gather/plant/{turn}/{rnd.answer}.png").headers["content-type"] == "image/png"
    assert client.get(f"/gather/plant/{turn + 1}/{rnd.answer}.png").status_code == 404
    assert client.get(f"/gather/plant/{turn}/o9.png").status_code == 404


def test_a_right_pick_stores_the_herb_and_it_regrows_elsewhere(client, db_path):
    s, g, h = kneel(client)
    rnd = s.g.round
    client.now[0] += 2
    out = pick(client, rnd.answer, s.turn)
    assert herbs(db_path) == 1 and player(db_path)["herb_streak"] == 1 and player(db_path)["herbs_gathered"] == 1
    assert out["mode"] == "result" and any("You gather" in x or "pull it free" in x for x in out["result"])
    assert any(c["state"] == "right" for c in out["choices"]) and all(c["name"] for c in out["choices"])
    ids = [x["id"] for x in out["world"]["herbs"]]
    assert h["id"] not in ids and len(ids) == 9                               # picked: gone, one regrowing
    client.now[0] += 91
    st = client.post("/world/state", data={"place": "crossroads"}).json()
    assert len(st["herbs"]) == 10 and h["id"] not in [x["id"] for x in st["herbs"]]


def test_a_decoy_poisons_and_resets_the_streak(client, db_path):
    set_player(db_path, herb_streak=7)
    s, g, h = kneel(client)
    rnd = s.g.round
    out = pick(client, next(iter(rnd.decoys)), s.turn)
    assert herbs(db_path) == 0 and player(db_path)["herb_streak"] == 0 and s.g.hp < s.g.max_hp
    assert any("look-alike" in x for x in out["result"])
    assert h["id"] not in [x["id"] for x in out["world"]["herbs"]]            # the herb is gone either way


def test_old_panels_and_unknown_choices_are_ignored(client, db_path):
    s, g, _ = kneel(client)
    rnd, turn = s.g.round, s.turn
    pick(client, "o9", turn)
    pick(client, rnd.answer, turn + 3)
    assert s.g.round is rnd and herbs(db_path) == 0
    pick(client, rnd.answer, turn)
    pick(client, rnd.answer, turn)                                           # the same panel sent twice
    assert herbs(db_path) == 1


def test_too_slow_misses_even_with_the_right_answer(client, db_path):
    set_player(db_path, herb_streak=4)
    s, g, _ = kneel(client)
    rnd = s.g.round
    client.now[0] += rnd.seconds + gathering.TIMER_GRACE_SECONDS + 0.5
    out = pick(client, rnd.answer, s.turn)
    assert herbs(db_path) == 0 and player(db_path)["herb_streak"] == 0
    assert any("Too slow" in x for x in out["result"])


def test_walking_away_counts_as_missed(client, db_path):
    set_player(db_path, herb_streak=3)
    s, g, h = kneel(client)
    out = client.post("/world/gather/away", data={"turn": s.turn}).json()
    assert player(db_path)["herb_streak"] == 0 and herbs(db_path) == 0
    assert h["id"] not in [x["id"] for x in out["world"]["herbs"]]


def test_you_must_kneel_by_the_herb(client):
    st = client.post("/world/state", data={"place": "crossroads"}).json()
    h = st["herbs"][0]
    w = client.world.walker(UID)
    w.x, w.y = h["x"] + 3, h["y"]
    out = client.post("/world/gather", data={"place": "crossroads", "id": h["id"], "x": w.x, "y": w.y}).json()
    assert out["error"] and client.gathers.get(UID) is None
    w.x, w.y = h["x"] + 0.5, h["y"]                                           # a jump across the meadow: refused
    out = client.post("/world/gather", data={"place": "crossroads", "id": h["id"], "x": h["x"] + 9, "y": h["y"]}).json()
    assert out["error"]
    out = client.post("/world/gather", data={"place": "town", "id": h["id"], "x": h["x"], "y": h["y"]}).json()
    assert out["error"]                                                       # not where you are


def test_the_wandering_spirit_check(client, db_path):
    set_player(db_path, spirit_check_in=0)
    s, g, h = kneel(client)
    rnd = s.g.round
    assert rnd.kind == "spirit" and g["spirit"] and len(g["spirit"]["signs"]) == 4
    wrong = next(k for k, _, _ in rnd.options if k != rnd.answer)
    out = pick(client, wrong, s.turn)
    assert player(db_path)["spirit_check_fails"] == 1
    assert h["id"] in [x["id"] for x in out["world"]["herbs"]]                # the herb is still there
    s, g, _ = kneel(client, h)
    assert s.g.round.kind == "spirit"                                         # it still blocks the way
    out = pick(client, s.g.round.answer, s.turn)
    assert player(db_path)["spirit_check_fails"] == 0 and any("not a puppet" in x for x in out["result"])
    s, g, _ = kneel(client, h)
    assert s.g.round.kind == "herb"                                           # and now the herb


def test_a_spirit_pause_blocks_gathering(client, db_path):
    set_player(db_path, gather_paused_until=1000.0 + 600)
    s, g, _ = kneel(client)
    assert "Wandering Spirit" in g["error"] and (s is None or s.g.round is None)


def test_many_herbs_in_a_row(client, db_path):
    got = 0
    for _ in range(12):
        st = client.post("/world/state", data={"place": "crossroads"}).json()
        if not st["herbs"]:
            client.now[0] += 95
            continue
        s, g, _ = kneel(client, st["herbs"][0])
        client.now[0] += 1.5
        pick(client, s.g.round.answer, s.turn)
        got += 1
    assert herbs(db_path) == got and player(db_path)["herb_streak"] == got and got >= 8
