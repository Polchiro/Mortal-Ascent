"""Alchemy on the website (docs/web.md, "Alchemy"): the bot's own /craft engine, refereed on the server."""
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from bot import crafting, db, loot  # noqa: E402
from bot import player as rules  # noqa: E402
from web import alchemy_play  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

UID = 778
QI = "qi:Mortal"


def herb_count(path):
    c = db.connect(path)
    n = sum(h["qty"] for h in db.get_items(c, UID, "herbs"))
    c.close()
    return n


def pills(path):
    c = db.connect(path)
    out = db.get_items(c, UID, "pills")
    c.close()
    return out


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Alchemist", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    loot.store(c, UID, [dict(loot.herb("Mortal", "qi", 10), qty=6), dict(loot.herb("Mortal", "purity", 10), qty=3)])
    c.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "alch", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=db_path, session_secret="s"))
    c = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c.get("/login").headers["location"]).query)
    c.get("/callback", params={"code": "x", "state": q["state"][0]})
    c.now = [1000.0]
    app.state.crafts.clock = lambda: c.now[0]
    c.crafts = app.state.crafts
    return c


def begin(client, pill=QI):
    return client.post("/alchemy/begin", data={"pill": pill, "batch": "1", "prefer": "young"})


def test_alchemy_page_shows_pills_and_recipe(client):
    page = client.get("/alchemy")
    assert page.status_code == 200 and "Choose a pill" in page.text
    assert "Ember Dantian Pill" in page.text and "Ready to craft" in page.text
    assert "2 × Spirit Grass" in page.text and "Begin refining" in page.text
    assert "disabled" not in page.text.split("Begin refining")[0][-80:]
    assert 'href="/alchemy"' in page.text                                # the nav tab


def test_begin_takes_the_herbs(client, db_path):
    before = herb_count(db_path)
    r = begin(client)
    assert r.status_code == 303 and r.headers["location"] == "/alchemy/play"
    assert herb_count(db_path) == before - 3
    play = client.get("/alchemy/play")
    assert "STAGE 1 OF" in play.text and "Stoke" in play.text
    assert client.get("/alchemy").headers["location"] == "/alchemy/play"   # one craft at a time
    assert begin(client).headers["location"].startswith("/alchemy?")
    assert herb_count(db_path) == before - 3


def test_missing_herbs_refuse_to_begin(client, db_path):
    page = client.get("/alchemy?pill=mending:Mortal")
    assert "Missing:" in page.text
    r = begin(client, "mending:Mortal")
    assert r.headers["location"].startswith("/alchemy?") and "Still missing" in client.get(r.headers["location"]).text
    assert client.crafts.get(UID) is None


def test_a_pill_above_the_rank_is_refused(client, db_path):
    r = begin(client, "qi:Heaven")
    assert "rank" in client.get(r.headers["location"]).text
    assert client.crafts.get(UID) is None
    assert "Heaven-Devouring" not in client.get("/alchemy").text


def play_to_the_end(client):
    for _ in range(80):
        s = client.crafts.get(UID)
        if s.outcome is not None:
            return s
        pr = s.craft.prompt()
        client.post("/alchemy/act", data={"key": pr.options[0][0], "turn": s.turn})
    raise AssertionError("the craft never finished")


def test_playing_every_stage_finishes_with_a_result(client, db_path):
    begin(client)
    s = play_to_the_end(client)
    page = client.get("/alchemy/play")
    assert "FINAL SCORE" in page.text and "Craft again" in page.text and "alchemy EXP" in page.text
    c = db.connect(db_path)
    assert db.get_player(c, UID)["alchemy_exp"] > 0
    c.close()
    if s.craft.result:
        assert [p["data"]["patterns"] for p in pills(db_path)] == [s.craft.result]
    else:
        assert pills(db_path) == []
    r = client.post("/alchemy/done")
    assert r.headers["location"].startswith("/alchemy?pill=qi") and client.crafts.get(UID) is None


def test_a_careful_craft_makes_a_pill(client, db_path):
    begin(client)
    s = client.crafts.get(UID)
    c = s.craft
    for _ in range(80):
        if s.outcome is not None:
            break
        pr = c.prompt()
        if pr.stage == 1:      # steer toward the middle of the hidden zone, as a player reading the hints would
            mid = c.zone_lo + c.zone_width / 2
            key = "stoke" if c.heat + c.drift < mid - 6 else "fan" if c.heat + c.drift > mid + 6 else "hold"
        elif pr.stage == 4:
            key = "condense" if c.pulse >= 3 else "wait"     # ≥70% here alone keeps the score above 40%
        else:
            key = pr.options[0][0]
        client.post("/alchemy/act", data={"key": key, "turn": s.turn})
    assert s.outcome is not None and c.result > 0
    assert len(pills(db_path)) == 1 and "纹" in client.get("/alchemy/play").text


def test_old_turns_and_unknown_buttons_are_ignored(client):
    begin(client)
    s = client.crafts.get(UID)
    client.post("/alchemy/act", data={"key": "explode", "turn": s.turn})
    assert s.turn == 0
    client.post("/alchemy/act", data={"key": "hold", "turn": 5})
    assert s.turn == 0
    client.post("/alchemy/act", data={"key": "hold", "turn": 0})
    assert s.turn == 1
    client.post("/alchemy/act", data={"key": "hold", "turn": 0})         # the same page sent twice
    assert s.turn == 1


def test_running_out_of_time_plays_the_timed_out_move(client, db_path):
    begin(client)
    s = client.crafts.get(UID)
    client.now[0] += s.craft.seconds + crafting.TIMER_GRACE_SECONDS + 0.5
    client.get("/alchemy/play")
    assert s.turn == 1 and s.craft.stage == 1
    client.now[0] += 10_000                                             # walked away: everything times out
    client.get("/alchemy/play")
    assert s.outcome is not None and s.craft.done


def test_the_page_never_shows_the_hidden_answers(client):
    begin(client)
    s = client.crafts.get(UID)
    page = client.get("/alchemy/play").text
    for shown in (f"{s.craft.heat}°", f"({s.craft.zone_width}° wide)", "<span>0°</span>", "<span>100°</span>"):
        page = page.replace(shown, "")
    assert f"{s.craft.zone_lo}°" not in page and "zone_lo" not in page


def test_batch_needs_the_rank_and_herbs_per_pill(client, db_path):
    c = db.connect(db_path)
    db.update_player(c, UID, alchemy_exp=100)                           # 2nd Grade: batches of 2
    c.close()
    page = client.get(f"/alchemy?pill={QI}&batch=2")
    assert "Pills at once" in page.text and "4 × Spirit Grass" in page.text
    before = herb_count(db_path)
    client.post("/alchemy/begin", data={"pill": QI, "batch": "9", "prefer": "young"})   # capped at 2
    s = client.crafts.get(UID)
    assert s.craft.batch == 2 and herb_count(db_path) == before - 6


def test_setup_view_matches_the_bot_plan(db_path):
    c = db.connect(db_path)
    v = alchemy_play.setup_view(c, UID, QI)
    pl = crafting.plan(c, UID, "qi", "Mortal")
    game = crafting.craft_for(db.get_player(c, UID), "qi", "Mortal", pl["age"])
    c.close()
    assert v["chosen"]["ready"] and not pl["missing"]
    assert v["chosen"]["difficulty"] == game.diff["name"] and v["chosen"]["zone"] == game.zone_width
    assert v["chosen"]["seconds"] == f"{game.seconds:g}"
