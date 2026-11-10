"""The website's forge (docs/web.md, "The forge"): the bot's own engine, refereed on the server."""
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import forge  # noqa: E402
from bot import db, forging, item_catalog, loot, materials  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

UID = 777


def gear_id(path):
    c = db.connect(path)
    i = db.get_items(c, UID, "weapons")[0]["id"]
    c.close()
    return i


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Smith", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, lotus_coins=50_000)
    loot.store(c, UID, item_catalog.make("weapon:ordinary:sword", 1, quality="normal"))
    recipe = forge.RECIPE["ordinary"]
    loot.store(c, UID, [materials.material(forge.material_key("base", 1, gear="weapon"), recipe["base"] * 3),
                        materials.material(forge.material_key("binding", 1), recipe["binding"] * 3)])
    c.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "smith", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=db_path, session_secret="s"))
    c = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c.get("/login").headers["location"]).query)
    c.get("/callback", params={"code": "x", "state": q["state"][0]})
    c.now = [1000.0]
    app.state.forges.clock = lambda: c.now[0]
    c.forges = app.state.forges
    return c


def coins(path):
    c = db.connect(path)
    v = db.get_player(c, UID)["lotus_coins"]
    c.close()
    return v


def begin(client, db_path):
    return client.post("/forge/begin", data={"item": gear_id(db_path), "action": "enchant"})


def test_forge_page_shows_gear_and_cost(client, db_path):
    page = client.get("/forge")
    assert page.status_code == 200 and "Choose your gear" in page.text
    assert "Enchant" in page.text and "Begin forging" in page.text and "disabled" not in page.text.split("Begin forging")[0][-80:]
    assert f'name="item" value="{gear_id(db_path)}"' in page.text


def test_begin_takes_the_materials_and_coins(client, db_path):
    before = coins(db_path)
    r = begin(client, db_path)
    assert r.status_code == 303 and r.headers["location"] == "/forge/play"
    assert coins(db_path) == before - forge.forge_coins("enchant", "ordinary")
    play = client.get("/forge/play")
    assert "STAGE 1 OF 5" in play.text and "Pump" in play.text
    assert client.get("/forge").headers["location"] == "/forge/play"     # one forge at a time
    assert begin(client, db_path).headers["location"].startswith("/forge?")


def test_missing_materials_refuse_to_begin(client, db_path):
    c = db.connect(db_path)
    for it in db.get_items(c, UID, "materials"):
        db.remove_item(c, it["id"], it["qty"])
    c.close()
    page = client.get("/forge")
    assert "Missing:" in page.text
    r = begin(client, db_path)
    assert r.headers["location"].startswith("/forge?") and "Still missing" in client.get(r.headers["location"]).text
    assert client.forges.get(UID) is None


def play_to_the_end(client):
    for _ in range(80):
        s = client.forges.get(UID)
        if s.outcome is not None:
            return s
        pr = s.game.prompt()
        client.post("/forge/act", data={"key": pr.options[0][0], "turn": s.turn})
    raise AssertionError("the forge never finished")


def test_playing_every_stage_finishes_with_a_result(client, db_path):
    begin(client, db_path)
    s = play_to_the_end(client)
    page = client.get("/forge/play")
    assert "POINTS" in page.text and "Forge again" in page.text and "blacksmith EXP" in page.text
    c = db.connect(db_path)
    assert db.get_player(c, UID)["blacksmith_exp"] > 0
    item = db.get_items(c, UID, "weapons")[0]
    c.close()
    if s.outcome["rarity"]:
        assert (item["data"] or {}).get("passives")
    r = client.post("/forge/done")
    assert r.headers["location"] == "/forge" and client.forges.get(UID) is None


def test_old_turns_and_unknown_buttons_are_ignored(client, db_path):
    begin(client, db_path)
    s = client.forges.get(UID)
    client.post("/forge/act", data={"key": "explode", "turn": s.turn})
    assert s.turn == 0
    client.post("/forge/act", data={"key": "hold", "turn": 5})
    assert s.turn == 0
    client.post("/forge/act", data={"key": "hold", "turn": 0})
    assert s.turn == 1
    client.post("/forge/act", data={"key": "hold", "turn": 0})          # the same page sent twice
    assert s.turn == 1


def test_running_out_of_time_plays_the_timed_out_move(client, db_path):
    begin(client, db_path)
    s = client.forges.get(UID)
    client.now[0] += s.game.seconds + forge.TIMER_GRACE_SECONDS + 0.5
    client.get("/forge/play")
    assert s.turn == 1 and s.game.stage == "ignite"
    client.now[0] += 10_000                                             # walked away: everything times out
    client.get("/forge/play")
    assert s.outcome is not None and s.outcome["score"] < forge.FAIL_BELOW


def test_the_page_never_shows_the_hidden_answers(client, db_path):
    begin(client, db_path)
    s = client.forges.get(UID)
    page = client.get("/forge/play").text
    for shown in (f"{s.game.heat}°", f"({s.game.zone_width}° wide)", "0° cold", "100° wild"):
        page = page.replace(shown, "")
    assert f"{s.game.zone_lo}°" not in page and "zone_lo" not in page
