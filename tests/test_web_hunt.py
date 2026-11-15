"""Explore's hunting pages on the website (docs/hunting.md): two players, one site."""
import random
import re
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import hunting  # noqa: E402
from bot import db  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

A, B, C = 801, 802, 803


@pytest.fixture
def site(tmp_path, monkeypatch):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    for uid, name, realm in ((A, "Shoaib", "Martial Apprentice"), (B, "Nicolas", "Mortal"), (C, "Elder", "Martial Saint")):
        db.create_player(c, uid, name, "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, uid, realm=realm, layer=4)
    c.close()
    who = {"id": None}
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": who["id"], "username": "u", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=path, session_secret="s"))
    app.state.hunts.rng_factory = lambda: random.Random(5)

    def login(uid):
        cl = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
        who["id"] = uid
        cl.get("/callback", params={"code": "x", "state": q["state"][0]})
        return cl
    return app, login, path


def test_entry_shows_three_ways_in(site):
    _, login, _ = site
    a = login(A)
    r = a.get("/explore")
    assert r.status_code == 200
    for text in ("Solo Hunt", "Create a Team", "Find a Team", "Moon Forest"):
        assert text in r.text


def test_public_team_from_creation_to_shared_fight(site):
    app, login, path = site
    a, b = login(A), login(B)
    r = a.post("/party/create", data={"name": "Moon Wolves", "visibility": "public"})
    assert r.headers["location"] == "/hunt"
    lobby = a.get("/hunt").text
    assert "Moon Wolves" in lobby and "Start expedition" in lobby and "Choose where to hunt." in lobby
    teams = b.get("/explore/teams").text
    assert "Moon Wolves" in teams and "Recruiting" in teams
    pid = re.search(r'name="id" value="([^"]+)"', teams).group(1)
    assert b.post("/party/join", data={"id": pid}).headers["location"] == "/hunt"
    assert "Nicolas" in a.get("/hunt").text
    # the member can't pick the place or start
    b.post("/party/location", data={"key": "moon_forest"})
    assert app.state.parties.of(A).location is None
    b.post("/party/start")
    assert not app.state.parties.of(A).hunting
    cards = a.get("/hunt/locations").text
    assert cards.count('class="hpanel loc') == len(hunting.LOCATIONS)
    assert "Mountain Tiger" in cards and "Wild Boar" in cards                           # this ground's own roster
    a.post("/party/location", data={"key": "moon_forest"})
    b.post("/party/ready", data={"ready": "1"})
    a.post("/party/start")
    assert app.state.parties.of(A).hunting
    fa, fb = a.get("/hunt").text, b.get("/hunt").text
    for page in (fa, fb):
        assert 'class="battle' in page and 'data-team="1"' in page and 'data-play="/hunt"' in page
        assert 'action="/hunt/act"' in page and "Shoaib" in page and "Nicolas" in page
        assert "/art/scenes/battle_bamboo_forest.jpg" in page
    # one move each; the turn plays when both have picked
    turn = re.search(r'name="turn" value="(\d+)"', fa).group(1)
    a.post("/hunt/act", data={"what": "move", "arg": "guard", "turn": turn})
    after = a.get("/hunt").text
    assert 'data-waiting="1"' in after and "Waiting for your party" in after
    h = app.state.hunts.get(app.state.parties.of(A).id)
    assert h.battle.turn == 1
    turn_b = re.search(r'name="turn" value="(\d+)"', fb).group(1)
    b.post("/hunt/act", data={"what": "move", "arg": "guard", "turn": turn_b})
    assert h.battle.turn == 2
    assert a.get("/hunt/v").json()["h"] is not None


def test_private_team_joins_by_invitation_id_only(site):
    app, login, _ = site
    a, b = login(A), login(B)
    a.post("/party/create", data={"name": "Hidden Lotus", "visibility": "private"})
    code = app.state.parties.of(A).code
    assert code in a.get("/hunt").text
    assert "Hidden Lotus" not in b.get("/explore/teams").text
    r = b.post("/party/join", data={"code": "WRONG1"}, follow_redirects=True)
    assert "No party has that invitation ID" in r.text
    a.post("/party/code")
    assert b.post("/party/join", data={"code": code}, follow_redirects=True).url.path == "/explore/teams"
    b.post("/party/join", data={"code": app.state.parties.of(A).code})
    assert app.state.parties.of(B) is app.state.parties.of(A)


def test_wrong_realm_cannot_join_and_leader_can_remove(site):
    app, login, _ = site
    a, b, c = login(A), login(B), login(C)
    a.post("/party/create", data={"name": "Moon Wolves", "visibility": "public"})
    a.post("/party/location", data={"key": "moon_forest"})
    pid = app.state.parties.of(A).id
    teams = c.get("/explore/teams").text
    assert "For Mortal – Martial Apprentice" in teams
    c.post("/party/join", data={"id": pid})
    assert app.state.parties.of(C) is None
    b.post("/party/join", data={"id": pid})
    a.post("/party/kick", data={"uid": str(B)})
    assert app.state.parties.of(B) is None
    a.post("/party/disband")
    assert app.state.parties.of(A) is None and a.get("/hunt").headers["location"] == "/explore"


def test_solo_hunt_goes_straight_to_a_fight(site):
    app, login, path = site
    a = login(A)
    assert a.post("/explore/solo").headers["location"] == "/hunt/locations"
    assert "Enter Moon Forest" in a.get("/hunt/locations").text
    a.post("/party/location", data={"key": "moon_forest"})
    page = a.get("/hunt").text
    assert 'class="battle' in page and 'data-team' not in page                          # alone: no team panel
    c = db.connect(path)
    assert db.cooldown_left(c, A, "explore") > 0                                         # the shared explore rest
    c.close()


def test_poll_endpoint_and_logged_out(site):
    app, login, _ = site
    a = login(A)
    assert a.get("/hunt/v").json() == {"gone": True}
    a.post("/party/create", data={"name": "Moon Wolves", "visibility": "public"})
    v = a.get("/hunt/v").json()
    assert v["p"] == app.state.parties.of(A).version and v["h"] is None
    anon = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    assert anon.get("/hunt").headers["location"] == "/"
    assert anon.post("/party/start").headers["location"] == "/"
