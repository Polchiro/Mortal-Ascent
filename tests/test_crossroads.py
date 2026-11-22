"""The Crossroads outside the town gate (web/crossroads.py, docs/world.md): its layout, its roads, and setting out
down one."""
import json
import math
import random
import re
import urllib.parse

import pytest

import hunting
from bot import db
from bot import player as rules
from web import crossroads as cr
from web import town


def _player(realm):
    return {"name": "Shoaib", "realm": realm}


def reachable(start, step=0.25):
    def key(x, y):
        return round(x / step), round(y / step)
    seen, todo = {key(*start)}, [start]
    while todo:
        x, y = todo.pop()
        for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step)):
            nx, ny = x + dx, y + dy
            if key(nx, ny) not in seen and cr.walkable(nx, ny):
                seen.add(key(nx, ny))
                todo.append((nx, ny))
    return seen, key


def test_every_hunting_ground_has_a_road_and_the_gate_a_door():
    assert set(cr.ROADS) == {loc["key"] for loc in hunting.LOCATIONS}
    keys = [e["key"] for e in cr.exits(_player("Mortal"))]
    assert keys[0] == "town_gate" and len(keys) == len(set(keys)) == 1 + len(hunting.LOCATIONS)


def test_you_can_walk_from_the_gate_to_every_road_end():
    assert cr.walkable(*cr.START)
    seen, key = reachable(cr.START)
    for e in cr.exits(_player("Mortal")):
        assert cr.walkable(e["x"], e["y"]), e["key"]
        assert key(e["x"], e["y"]) in seen, e["key"]


def test_the_ways_out_stand_apart():
    ex = cr.exits(_player("Mortal"))
    for i, a in enumerate(ex):
        for b in ex[i + 1:]:
            assert math.dist((a["x"], a["y"]), (b["x"], b["y"])) > 2 * cr.REACH, (a["key"], b["key"])
    assert math.dist(cr.START, (cr.GATE["x"], cr.GATE["y"])) > cr.REACH     # coming out doesn't ask you to go back in


def test_roads_are_clear_and_pieces_stay_off_them():
    for a, b in cr.roads():
        for i in range(41):
            t = i / 40
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            if town.inside(*p, cr.AREA):
                assert cr.walkable(*p), p                                  # nothing stands on a road
    for b in cr.BUILDINGS:
        assert b["img"] in town.kit() or (b["img"] + "_m") in town.kit()


def test_every_piece_has_its_picture_placed():
    placed = town.placed(cr.BUILDINGS, cr.PROPS, cr.SIZE)
    assert len(placed) == len(cr.BUILDINGS) + len(cr.PROPS)
    assert sum(1 for b in cr.BUILDINGS if b["img"] in ("pine", "bush", "blossom", "boulders")) > 60   # a real forest
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for q in placed:
        assert os.path.exists(os.path.join(root, q["src"].lstrip("/"))), q["src"]
    from PIL import Image
    im = Image.open(os.path.join(root, cr.ART.lstrip("/")))
    assert im.size == (cr.SIZE * 128 * 1.5, cr.SIZE * 64 * 1.5)


def test_roads_open_wait_or_are_sealed():
    by = {e["key"]: e for e in cr.exits(_player("Martial Warrior"))}
    assert by["road_moon_forest"]["state"] == "open"
    assert by["road_crimson_gorge"]["go"] == [["Enter Crimson Gorge", "/crossroads/go/crimson_gorge", "post"]]
    assert by["road_frostpeak_mountains"]["state"] == "locked" and not by["road_frostpeak_mountains"]["go"]
    assert "Martial Master" in by["road_frostpeak_mountains"]["title"]
    rest = {e["key"]: e for e in cr.exits(_player("Martial Warrior"), "resting from the last expedition for 9m")}
    assert rest["road_moon_forest"]["state"] == "waiting" and not rest["road_moon_forest"]["go"]
    assert "9m" in rest["road_moon_forest"]["line"] and rest["road_moon_forest"]["title"] == "Resting"
    assert rest["road_frostpeak_mountains"]["state"] == "locked"


def test_the_page_data_is_the_town_pages_shape():
    d = cr.page_data({"src": "x"}, _player("Mortal"), near="road_moon_forest")
    assert d["near"] == "road_moon_forest" and d["npcs"] == [] and d["ground"] == cr.ART
    assert all(e["exit"] and len(e["glow"]) == 2 for e in d["exits"])
    assert cr.page_data({"src": "x"}, _player("Mortal"), near="nowhere")["near"] is None


# ── the pages ──────────────────────────────────────────────────────────────────────────────────────────────────
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

WARRIOR, RESTING = 911, 912


@pytest.fixture
def site(tmp_path, monkeypatch):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    for uid, name, realm in ((WARRIOR, "Shoaib", "Martial Warrior"), (RESTING, "Nicolas", "Martial Apprentice")):
        db.create_player(c, uid, name, "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, uid, realm=realm, layer=4)
    db.set_cooldown(c, RESTING, "explore", 1200)
    c.close()
    monkeypatch.delenv("ADMIN_IDS", raising=False)
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


def _data(text):
    return json.loads(re.search(r'id="mapdata">(.*?)</script>', text, re.S).group(1))


def test_the_crossroads_needs_a_login(site):
    app, _, _ = site
    anon = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    assert anon.get("/crossroads").headers["location"] == "/"
    assert anon.post("/crossroads/go/moon_forest").headers["location"] == "/"


def test_the_crossroads_is_walked(site):
    _, login, _ = site
    a = login(WARRIOR)
    r = a.get("/crossroads?near=town_gate")
    assert r.status_code == 200 and "/static/town.js" in r.text
    d = _data(r.text)
    assert d["near"] == "town_gate" and d["sheet"]["src"]
    states = {e["key"]: e["state"] for e in d["exits"]}
    assert states["road_crimson_gorge"] == "open" and states["road_celestial_forbidden_lands"] == "locked"
    assert a.get(cr.ART).status_code == 200


def test_down_a_road_is_a_walked_solo_hunt(site):
    app, login, path = site
    a = login(WARRIOR)
    assert a.post("/crossroads/go/crimson_gorge").headers["location"] == "/hunt"
    party = app.state.parties.of(WARRIOR)
    assert party.solo and party.hunting and party.location == "crimson_gorge"
    assert app.state.hunts.get(party.id).map                                 # everyone walks now, not just admins
    assert 'id="homeDlg"' in a.get("/hunt").text
    c = db.connect(path)
    assert db.cooldown_left(c, WARRIOR, "explore") > 0                       # the shared explore rest started
    c.close()
    assert a.get("/crossroads").headers["location"] == "/hunt"               # out hunting: that comes first
    assert a.post("/crossroads/go/moon_forest").headers["location"] == "/hunt"


def test_the_server_refuses_a_sealed_road(site):
    app, login, path = site
    a = login(WARRIOR)
    assert a.post("/crossroads/go/frostpeak_mountains").headers["location"] == \
        "/crossroads?near=road_frostpeak_mountains"
    assert "needs Martial Master" in a.get("/crossroads").text
    assert app.state.parties.of(WARRIOR) is None                             # nothing left behind
    c = db.connect(path)
    assert not db.cooldown_left(c, WARRIOR, "explore")                       # and no rest started
    c.close()


def test_resting_can_not_set_out(site):
    app, login, _ = site
    b = login(RESTING)
    d = _data(b.get("/crossroads").text)
    assert {e["key"]: e["state"] for e in d["exits"]}["road_moon_forest"] == "waiting"
    assert b.post("/crossroads/go/moon_forest").headers["location"] == "/crossroads?near=road_moon_forest"
    assert "resting from the last expedition" in b.get("/crossroads").text
    assert app.state.parties.of(RESTING) is None


def test_an_unknown_road_is_refused(site):
    _, login, _ = site
    a = login(WARRIOR)
    assert a.post("/crossroads/go/the_moon").headers["location"] == "/crossroads"
    assert "no such road" in a.get("/crossroads").text


def test_heading_home_comes_back_up_the_same_road(site):
    app, login, _ = site
    a = login(WARRIOR)
    a.post("/crossroads/go/moon_forest")
    turn = re.search(r'name="turn" value="([^"]*)"', a.get("/hunt").text).group(1)
    a.post("/hunt/act", data={"what": "return", "arg": "", "turn": turn})
    assert "Back to the Crossroads" in a.get("/hunt").text
    assert a.post("/hunt/done").headers["location"] == "/crossroads?near=road_moon_forest"
    assert app.state.parties.of(WARRIOR) is None
    d = _data(a.get("/crossroads?near=road_moon_forest").text)
    assert d["near"] == "road_moon_forest"
    assert {e["key"]: e["state"] for e in d["exits"]}["road_moon_forest"] == "waiting"   # now resting


def test_a_solo_hunt_still_choosing_is_dropped_and_a_team_goes_to_its_lobby(site):
    app, login, _ = site
    a = login(WARRIOR)
    a.post("/explore/solo")
    assert a.get("/crossroads").status_code == 200 and app.state.parties.of(WARRIOR) is None
    a.post("/party/create", data={"name": "Gorge Runners", "visibility": "public"})
    assert a.get("/crossroads").headers["location"] == "/hunt"


def test_a_look_without_a_walking_sheet_chooses_from_a_list(site, monkeypatch):
    import looks
    monkeypatch.setattr(looks, "WALK_SHEETS", {})
    _, login, _ = site
    r = login(WARRIOR).get("/crossroads")
    assert r.status_code == 200 and 'id="map"' not in r.text and "THE ROADS" in r.text
    assert 'action="/crossroads/go/crimson_gorge"' in r.text and 'href="/town"' in r.text
