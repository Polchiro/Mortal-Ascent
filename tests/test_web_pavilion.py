"""The Moon Pavilion on the website (web/pavilion_play.py, web/pavilion_routes.py, docs/web.md "The Moon Pavilion"):
the Pearl shop and Heavenly Blessings through bot/shop.py, the same code as Discord's /shop and /blessing."""
import re
import urllib.parse

import pytest

import economy
from bot import db
from bot import player as rules
from bot import shop
from web import pavilion_play as pv
from web import town

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

A = 444444444444444444


@pytest.fixture
def path(tmp_path):
    p = str(tmp_path / "ma.db")
    c = db.connect(p)
    db.create_player(c, A, "Lin Yue", "Gifted", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, A, moon_pearls=2000)
    c.close()
    return p


def test_the_page_shows_what_discord_sells(path):
    c = db.connect(path)
    v = pv.view(c, A)
    assert [i["key"] for i in v["items"]] == [i["key"] for i in shop.shop_data(db.get_player(c, A))["items"]]
    assert [t["name"] for t in v["tiers"]] == list(economy.BLESSING_TIERS)
    theme = next(i for i in v["items"] if i["key"] == "profile_theme")
    assert theme["soon"] and pv.buy(c, A, "profile_theme")[0] is False


def test_buying_through_the_bots_shop(path):
    c = db.connect(path)
    cap = db.get_player(c, A)["bag_capacity"]
    ok, msg = pv.buy(c, A, "inventory_expansion_20")
    p = db.get_player(c, A)
    assert ok and p["bag_capacity"] == cap + 20 and p["moon_pearls"] == 2000 - economy.PEARL_SHOP["inventory_expansion_20"]
    assert pv.buy(c, A, "name_change", "  ") == (False, "Please give a name.")
    ok, _ = pv.buy(c, A, "name_change", "Iron Lotus")
    assert ok and db.get_player(c, A)["name"] == "Iron Lotus"
    db.update_player(c, A, moon_pearls=10)
    ok, msg = pv.buy(c, A, "mortal_qi_pill_x3")
    assert not ok and "You need" in msg and db.get_player(c, A)["moon_pearls"] == 10
    assert pv.buy(c, A, "nonsense")[0] is False


def test_a_blessing(path):
    c = db.connect(path)
    ok, msg = pv.bless(c, A, "Gentle Breeze", now=0)
    assert ok and rules.active_blessing(db.get_player(c, A), 0)[0] == "Gentle Breeze"
    v = pv.view(c, A, now=0)
    gb = next(t for t in v["tiers"] if t["name"] == "Gentle Breeze")
    sr = next(t for t in v["tiers"] if t["name"] == "Spring Rain")
    assert gb["active"] and "Adds 30 days" in gb["note"] and "Replaces your Gentle Breeze" in sr["note"]
    assert pv.bless(c, A, "Nope")[0] is False


def test_merchant_qian_runs_it_in_town():
    qian = next(n for n in town.page_data({})["npcs"] if n["key"] == "merchant")
    assert qian["name"] == "Merchant Qian" and ["Browse the Pearl shop", "/pavilion"] in qian["go"]
    assert not any(n["key"] == "pavilion" for n in town.NPCS)


def test_the_routes_need_the_pages_token(path, monkeypatch):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=path, session_secret="test")
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "token")
    monkeypatch.setattr(oauth, "fetch_user", lambda token: {"id": A, "username": "x", "avatar": None})
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert cl.get("/pavilion").status_code == 303
    q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
    cl.get("/callback", params={"code": "good", "state": q["state"][0]})
    page = cl.get("/pavilion").text
    assert "Pearl Shop" in page and "Heavenly Blessings" in page
    token = re.search(r'name="token" value="([^"]+)"', page).group(1)
    r = cl.post("/pavilion/bless", data={"token": token, "tier": "Gentle Breeze"})
    assert r.status_code == 303 and r.headers["location"] == "/pavilion?tab=blessing"
    page = cl.get(r.headers["location"]).text
    assert "Heaven smiles on you" in page and "Active" in page
    before = db.get_player(db.connect(path), A)["moon_pearls"]
    cl.post("/pavilion/bless", data={"token": token, "tier": "Gentle Breeze"})        # the used token again
    assert db.get_player(db.connect(path), A)["moon_pearls"] == before
