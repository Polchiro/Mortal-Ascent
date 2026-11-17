"""The Stone Stele's rankings (web/rankings.py, /rankings)."""
import re

import pytest

from bot import db
from bot import player as rules
from web import rankings

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

UID = 123456789012345678


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    for i in range(14):
        db.create_player(c, 1000 + i, f"Rival {i}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, 1000 + i, lotus_coins=1000 * (i + 1), duels_won=i, layer=1 + i % 5)
    db.create_player(c, UID, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, lotus_coins=50, duels_won=20, duels_lost=3)
    c.close()
    return path


def test_duels_board_ranks_most_won_first(db_path):
    c = db.connect(db_path)
    v = rankings.view(c, "duels", UID)
    assert v["top"][0]["name"] == "Shoaib" and v["top"][0]["you"] and v["top"][0]["value"] == "20 won · 3 lost"
    assert [r["rank"] for r in v["top"]] == list(range(1, rankings.TOP_N + 1)) and v["me"] is None


def test_you_are_shown_below_the_top_when_outside_it(db_path):
    c = db.connect(db_path)
    v = rankings.view(c, "lotus_coins", UID)
    assert all(not r["you"] for r in v["top"]) and v["me"]["name"] == "Shoaib" and v["me"]["rank"] == 15
    assert v["players"] == 15


def test_an_unknown_board_shows_the_first(db_path):
    c = db.connect(db_path)
    assert rankings.view(c, "nope", UID)["board"] == "realm"


def test_the_page(db_path, monkeypatch):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=db_path, session_secret="test")
    c = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert c.get("/rankings").headers["location"] == "/"
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "token")
    monkeypatch.setattr(oauth, "fetch_user", lambda token: {"id": UID, "username": "shoaib", "avatar": None})
    state = re.search(r"state=([^&]+)", c.get("/login").headers["location"]).group(1)
    c.get("/callback", params={"code": "x", "state": state})
    for board, _ in rankings.BOARDS:
        r = c.get(f"/rankings?board={board}")
        assert r.status_code == 200 and "Shoaib" in r.text
    assert "20 won" in c.get("/rankings?board=duels").text
