"""The town hub (docs/town.md): its layout on the painting, and the /town page."""
import json
import math
import os
import re

import pytest

from web import town

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def reachable_from_start(step=0.25):
    """Every walkable point (on a fine grid) you can get to from the gate."""
    def key(x, y):
        return round(x / step), round(y / step)
    seen, todo = {key(*town.START)}, [town.START]
    while todo:
        x, y = todo.pop()
        for dx, dy in ((step, 0), (-step, 0), (0, step), (0, -step)):
            nx, ny = x + dx, y + dy
            if key(nx, ny) not in seen and town.walkable(nx, ny):
                seen.add(key(nx, ny))
                todo.append((nx, ny))
    return seen


def test_the_painting_fills_the_grid():
    from PIL import Image
    im = Image.open(os.path.join(ROOT, town.ART.lstrip("/")))
    assert im.width == 2 * im.height and im.width >= town.SIZE * 128      # 2:1, at least the world's size


def test_you_can_walk_up_to_everyone_from_the_gate():
    assert town.walkable(*town.START)
    spots = reachable_from_start()
    for n in town.NPCS:
        close = [s for s in spots if math.dist((s[0] * 0.25, s[1] * 0.25), (n["x"], n["y"])) < town.REACH * 0.8]
        assert close, f"nobody can reach {n['name']}"


def test_buildings_props_and_the_pond_block_the_way():
    for cx, cy, r in town.BLOCKED:
        assert not town.walkable(cx, cy)
    for b in town.BUILDINGS:
        assert not town.walkable(b["x0"] + b["a"] / 2, b["y0"] + b["b"] / 2), b["key"]
    for p in town.PROPS:
        assert not town.walkable(p["x"], p["y"])
    assert not town.walkable(1, 30) and not town.walkable(town.SIZE - 1, town.SIZE / 2)    # outside the walls


def test_every_piece_has_its_picture_and_sits_on_the_ground():
    from PIL import Image
    pieces = town.placed()
    assert len(pieces) == len(town.BUILDINGS) + len(town.PROPS)
    for q in pieces:
        im = Image.open(os.path.join(ROOT, q["src"].lstrip("/")))
        assert im.mode == "RGBA"
        left, top, w, h = q["rect"]
        assert 0 <= left and left + w <= town.SIZE * 128 and top + h <= town.SIZE * 64 and w > 0 and h > 0
    edge = {"wall_s", "wall_l", "tower", "tower_low", "gatehouse"}   # wall slices tuck under the towers and the gate
    gap = 0.2                                                 # stone bases never touch: a little ground between
    for a in town.BUILDINGS:
        for b in town.BUILDINGS:
            if a is not b and not (a["img"] in edge or b["img"] in edge):
                assert (a["x0"] + a["a"] + gap <= b["x0"] or b["x0"] + b["a"] + gap <= a["x0"] or
                        a["y0"] + a["b"] + gap <= b["y0"] or b["y0"] + b["b"] + gap <= a["y0"]), (a["key"], b["key"])


def test_townsfolk_are_complete_and_unique():
    keys = [n["key"] for n in town.NPCS]
    assert len(keys) == len(set(keys))
    for n in town.NPCS:
        assert n["name"] and n["title"] and n["line"]
        for label, href in n.get("go", []):
            assert label and href.startswith("/")
        if n.get("src"):                                   # a see-through picture, taller than wide, that exists
            from PIL import Image
            im = Image.open(os.path.join(ROOT, n["src"].lstrip("/")))
            assert im.mode == "RGBA" and im.height > im.width and 100 <= n["h"] <= 160


# ── the page ───────────────────────────────────────────────────────────────────────────────────────────────────
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from bot import appearance, db  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

UID = 123456789012345678


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, lotus_coins=12480, moon_pearls=96)
    c.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=db_path, session_secret="test")
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "token")
    monkeypatch.setattr(oauth, "fetch_user", lambda token: {"id": UID, "username": "shoaib", "avatar": None})
    c = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    q = c.get("/login").headers["location"]
    state = re.search(r"state=([^&]+)", q).group(1)
    c.get("/callback", params={"code": "x", "state": state})
    return c


def test_the_town_needs_a_login(db_path):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=db_path, session_secret="test")
    c = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert c.get("/town").headers["location"] == "/"


def test_everyone_with_a_walking_sheet_walks_the_town(client):
    r = client.get("/town")
    assert r.status_code == 200 and 'id="map"' in r.text and "/static/town.js" in r.text
    data = json.loads(re.search(r'id="mapdata">(.*?)</script>', r.text, re.S).group(1))
    assert data["sheet"]["src"].endswith("hero_male_walk.webp") and data["ground"] == town.ART
    assert len(data["npcs"]) == len(town.NPCS) and data["hero"] == {"x": town.START[0], "y": town.START[1]}
    assert 'href="/town"' in client.get("/profile").text                                # the Town tab
    assert client.get(town.ART).status_code == 200 and client.get("/static/town.js").status_code == 200


def test_every_place_the_townsfolk_send_you_exists(client):
    for n in town.NPCS:
        for _, href in n.get("go", []):
            assert client.get(href).status_code == 200, href


def test_a_look_without_a_walking_sheet_talks_from_a_list(client, db_path, monkeypatch):
    import looks
    c = db.connect(db_path)
    ok, _ = appearance.choose(c, UID, "female")
    c.close()
    assert ok
    monkeypatch.setattr(looks, "WALK_SHEETS", {k: v for k, v in looks.WALK_SHEETS.items() if k != "female"})
    r = client.get("/town")
    assert r.status_code == 200 and 'id="map"' not in r.text and "THE TOWNSFOLK" in r.text
    assert 'href="/forge"' in r.text and "Martial Master" in r.text
