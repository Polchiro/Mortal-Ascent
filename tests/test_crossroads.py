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


def test_roads_are_clear_and_only_the_town_wall_stands_here():
    from web import land
    for a, b, _w in land.segments(cr.KEY):
        for i in range(5):
            t = i / 4
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            if town.inside(*p, cr.AREA):
                assert cr.walkable(*p), p                                  # nothing stands on a road
    assert {b["img"] for b in cr.BUILDINGS} <= {"wall_s", "wall_l", "gate"}  # an empty land: the town's wall and gate
    for key, end in cr.ROADS.items():
        assert cr.road_dist(end) < 0.2, key                                  # each road really ends where its exit is
    assert cr.road_dist((cr.GATE["x"], cr.GATE["y"])) < 0.2


def test_every_piece_has_its_picture_placed():
    placed = town.placed(cr.BUILDINGS, cr.PROPS, cr.SIZE)
    assert len(placed) == len(cr.BUILDINGS) + len(cr.PROPS)
    import os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for q in placed:
        assert os.path.exists(os.path.join(root, q["src"].lstrip("/"))), q["src"]
    assert os.path.exists(os.path.join(root, cr.ART.lstrip("/")))


def test_roads_are_open_closed_or_sealed():
    by = {e["key"]: e for e in cr.exits(_player("Martial Warrior"))}
    assert by["road_moon_forest"]["state"] == "open"
    # a road whose land isn't built starts nothing: the old menu hunt is gone from the roads
    assert by["road_crimson_gorge"]["state"] == "closed" and by["road_crimson_gorge"]["go"] == []
    assert by["road_crimson_gorge"]["title"] == "Not open yet" and "not open yet" in by["road_crimson_gorge"]["line"]
    assert by["road_frostpeak_mountains"]["state"] == "locked" and not by["road_frostpeak_mountains"]["go"]
    assert "Martial Master" in by["road_frostpeak_mountains"]["title"]
    assert all(not e["go"] for e in by.values() if e["key"] != "town_gate")


def test_the_page_data_is_the_town_pages_shape():
    d = cr.page_data({"src": "x"}, _player("Mortal"), near="road_moon_forest")
    assert d["near"] == "road_moon_forest" and d["npcs"] == [] and d["ground"]["have"] and d["size"] == 60
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


def test_the_crossroads_is_walked(site):
    _, login, _ = site
    a = login(WARRIOR)
    r = a.get("/crossroads?near=town_gate")
    assert r.status_code == 200 and "/static/town.js" in r.text
    d = _data(r.text)
    assert d["place"] == "crossroads" and d["sheet"]["src"]
    from web import overworld
    assert (d["hero"]["x"], d["hero"]["y"]) == overworld.arrival("crossroads", "town_gate")   # in from the gate
    by = {e["key"]: e for e in d["exits"]}
    assert by["road_crimson_gorge"]["state"] == "closed" and by["road_celestial_forbidden_lands"]["state"] == "locked"
    assert by["road_moon_forest"]["walk"] and by["town_gate"]["walk"] and not by["road_crimson_gorge"].get("walk")
    assert a.get(cr.ART).status_code == 200
    g = d["ground"]
    assert a.get(f"{g['base']}c_{g['have'][0]}.webp").status_code == 200       # the ground comes in chunks


def test_no_road_starts_the_old_hunt(site):
    app, login, path = site
    a = login(WARRIOR)
    assert a.post("/crossroads/go/crimson_gorge").status_code in (404, 405)
    assert a.post("/crossroads/go/moon_forest").status_code in (404, 405)
    assert app.state.parties.of(WARRIOR) is None
    c = db.connect(path)
    assert not db.cooldown_left(c, WARRIOR, "explore")
    c.close()


def test_resting_still_walks_the_forest_road(site):
    _, login, _ = site
    b = login(RESTING)
    d = _data(b.get("/crossroads").text)
    road = {e["key"]: e for e in d["exits"]}["road_moon_forest"]
    assert road["state"] == "open" and road["walk"]                         # resting: nothing to meet, but you can walk
    assert d["world"]["wary"] is True


def test_a_solo_hunt_still_choosing_is_dropped_and_a_team_goes_to_its_lobby(site):
    app, login, _ = site
    a = login(WARRIOR)
    a.post("/explore/solo")
    assert a.get("/crossroads").status_code == 200 and app.state.parties.of(WARRIOR) is None
    a.post("/party/create", data={"name": "Gorge Runners", "visibility": "public"})
    assert a.get("/crossroads").headers["location"] == "/hunt"


def test_a_look_without_a_walking_sheet_reads_the_roads_from_a_list(site, monkeypatch):
    import looks
    monkeypatch.setattr(looks, "WALK_SHEETS", {})
    _, login, _ = site
    r = login(WARRIOR).get("/crossroads")
    assert r.status_code == 200 and 'id="map"' not in r.text and "THE ROADS" in r.text
    assert "/crossroads/go/" not in r.text and 'href="/town"' in r.text and "Not open yet" in r.text
