"""The World Map (web/world.py, docs/world.md): the scroll, the town gate out to it, setting out from it, and the ways
back."""
import json
import math
import os
import random
import re
import urllib.parse

import pytest

import hunting
from bot import db
from bot import player as rules
from web import town, world

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _player(realm):
    return {"name": "Shoaib", "realm": realm}


# ── the scroll ─────────────────────────────────────────────────────────────────────────────────────────────────

def test_every_hunting_ground_and_the_town_are_on_the_scroll():
    keys = [m["key"] for m in world.markers(_player("Mortal"))]
    assert keys == ["town", "ironvein_quarry"] + [loc["key"] for loc in hunting.LOCATIONS]
    for key, (x, y) in world.AT.items():
        assert 0.05 < x < 0.95 and 0.05 < y < 0.95, key                     # inside the painted paper
    spots = list(world.AT.values())
    for i, a in enumerate(spots):                                          # markers don't sit on each other
        for b in spots[i + 1:]:
            assert math.dist(a, b) > 0.08


def test_the_scroll_picture_is_cut_out():
    from PIL import Image
    im = Image.open(os.path.join(ROOT, world.ART.lstrip("/")))
    assert im.mode == "RGBA" and 1.6 < im.width / im.height < 1.95
    a = im.getchannel("A")
    assert a.getpixel((im.width // 2, im.height // 2)) == 255               # the painting
    assert a.getpixel((im.width // 2, 2)) == 0                               # the backdrop above the paper: gone


def test_locks_follow_the_realm():
    by = {m["key"]: m for m in world.markers(_player("Martial Warrior"))}
    assert by["moon_forest"]["state"] == "open" and not by["moon_forest"]["here"]
    assert by["crimson_gorge"]["state"] == "open" and by["crimson_gorge"]["here"]
    assert by["frostpeak_mountains"]["state"] == "locked"
    assert by["frostpeak_mountains"]["requirement"] == "Martial Master"
    saint = {m["key"]: m["state"] for m in world.markers(_player("Martial Saint"))}
    assert all(s == "open" for k, s in saint.items() if k != "town")         # a Saint may go anywhere
    mortal = {m["key"]: m["state"] for m in world.markers(_player("Mortal"))}
    assert mortal["moon_forest"] == "open" and mortal["crimson_gorge"] == "locked"


def test_resting_or_injured_waits_but_a_lock_stays_a_lock():
    by = {m["key"]: m for m in world.markers(_player("Martial Warrior"), "resting from the last expedition for 20m")}
    assert by["moon_forest"]["state"] == "waiting" and by["moon_forest"]["short"] == "Resting"
    assert by["frostpeak_mountains"]["state"] == "locked"
    hurt = {m["key"]: m for m in world.markers(_player("Mortal"), "injured for 40m")}
    assert hurt["moon_forest"]["short"] == "Injured"


# ── the town gate ──────────────────────────────────────────────────────────────────────────────────────────────

def test_the_gate_is_a_way_out_you_can_walk_to():
    from tests.test_town import reachable_from_start
    seen = reachable_from_start()
    for e in town.EXITS:
        assert town.walkable(e["x"], e["y"])
        assert (round(e["x"] / 0.25), round(e["y"] / 0.25)) in seen
        assert math.dist((e["x"], e["y"]), town.START) > town.REACH          # coming back in doesn't ask you to leave
        for n in town.NPCS:
            assert math.dist((e["x"], e["y"]), (n["x"], n["y"])) > town.REACH, n["key"]
        assert e["go"] and all(href.startswith("/") for _, href in e["go"])
    assert any(href.startswith("/crossroads") for e in town.EXITS for _, href in e["go"])


def test_the_page_gets_the_ways_out():
    data = town.page_data({"src": "x"})
    assert [e["key"] for e in data["exits"]] == [e["key"] for e in town.EXITS]
    assert all(e["exit"] and len(e["glow"]) == 2 for e in data["exits"])
    assert town.page_data({"src": "x"}, near="gate_out")["near"] is None      # back from the world: at the gate


# ── the pages ──────────────────────────────────────────────────────────────────────────────────────────────────
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

WARRIOR, RESTING = 901, 902


@pytest.fixture
def site(tmp_path, monkeypatch):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    for uid, name, realm in ((WARRIOR, "Shoaib", "Martial Warrior"), (RESTING, "Nicolas", "Martial Apprentice")):
        db.create_player(c, uid, name, "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, uid, realm=realm, layer=4)
    db.set_cooldown(c, RESTING, "explore", 1200)
    c.close()
    monkeypatch.delenv("ADMIN_IDS", raising=False)                           # nobody here is an admin
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


def test_the_world_map_needs_a_login(site):
    app, _, _ = site
    anon = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    assert anon.get("/world").headers["location"] == "/"


def test_the_world_map_is_only_a_map(site):
    _, login, _ = site
    a = login(WARRIOR)
    r = a.get("/world")
    assert r.status_code == 200 and world.ART in r.text and "/static/world.js" in r.text
    for loc in hunting.LOCATIONS:
        assert loc["name"] in r.text
    assert "Needs Martial Master" in r.text and "Crossroads" in r.text
    assert 'method="post"' not in r.text                                    # no travelling from the scroll
    assert a.post("/world/go/moon_forest").status_code in (404, 405)


def test_the_world_map_opens_from_anywhere(site):
    app, login, _ = site
    a = login(WARRIOR)
    a.post("/explore/solo")
    a.post("/party/location", data={"key": "moon_forest"})
    a.post("/hunt/start")
    assert app.state.parties.of(WARRIOR).hunting
    assert a.get("/world").status_code == 200                               # even out hunting: it is only a map
    assert app.state.parties.of(WARRIOR).hunting


def test_town_gate_leads_to_the_crossroads(site):
    _, login, _ = site
    a = login(WARRIOR)
    r = a.get("/town")
    data = json.loads(re.search(r'id="mapdata">(.*?)</script>', r.text, re.S).group(1))
    assert data["exits"][0]["key"] == "gate_out" and data["exits"][0]["walk"]   # walked through (web/overworld.py)
    assert a.get("/crossroads?near=town_gate").status_code == 200
