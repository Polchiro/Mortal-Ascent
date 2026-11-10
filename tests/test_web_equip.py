"""Equipping gear on the website (docs/web.md, "The inventory page"): the bot's own rules (loot.use_item)."""
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import equipments  # noqa: E402
from bot import db, item_catalog, loot  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

UID, OTHER = 780, 781


def bag(path, cat, uid=UID):
    c = db.connect(path)
    out = db.get_items(c, uid, cat)
    c.close()
    return out


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    for uid in (UID, OTHER):
        db.create_player(c, uid, f"P{uid}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        loot.store(c, uid, item_catalog.make("weapon:ordinary:sword", 1, quality="normal"))
    loot.store(c, UID, item_catalog.make("weapon:ordinary:saber", 1, quality="normal"))
    c.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "eq", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=db_path, session_secret="s"))
    c = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c.get("/login").headers["location"]).query)
    c.get("/callback", params={"code": "x", "state": q["state"][0]})
    return c


def test_equip_and_unequip_a_weapon(client, db_path):
    a, b = bag(db_path, "weapons")
    page = client.get(f"/inventory?tab=weapons&item={a['id']}").text
    assert 'action="/inventory/equip"' in page and ">Equip<" in page
    r = client.post("/inventory/equip", data={"item": a["id"]})
    assert r.headers["location"] == f"/inventory?tab=weapons&item={a['id']}"
    page = client.get(r.headers["location"]).text
    assert "You equip" in page and 'action="/inventory/unequip"' in page and "<b>" in page
    client.post("/inventory/equip", data={"item": b["id"]})                 # one weapon: the first comes off
    assert {i["id"] for i in bag(db_path, "weapons") if i["equipped"]} == {b["id"]}
    client.post("/inventory/unequip", data={"item": b["id"]})
    assert not any(i["equipped"] for i in bag(db_path, "weapons"))
    assert "equipped any more" in client.get(client.post("/inventory/unequip", data={"item": b["id"]}).headers["location"]).text


def test_the_realm_rule_is_the_bots(client, db_path):
    c = db.connect(db_path)
    tier = next(t for t in equipments.TIERS if equipments.TIER_REALM_REQUIREMENT[t] != "Mortal")
    loot.store(c, UID, item_catalog.make(f"weapon:{tier}:sword", 1, quality="normal"))
    high = next(i for i in db.get_items(c, UID, "weapons") if i["grade"] == tier)
    c.close()
    r = client.post("/inventory/equip", data={"item": high["id"]})
    assert "You must reach" in client.get(r.headers["location"]).text
    assert not any(i["equipped"] for i in bag(db_path, "weapons"))


def test_armor_and_two_different_artifacts(client, db_path):
    c = db.connect(db_path)
    loot.store(c, UID, item_catalog.make("armor:ordinary:robe", 1, quality="normal"))
    loot.store(c, UID, item_catalog.make("artifact:ordinary:fang", 2) + item_catalog.make("artifact:ordinary:bell", 1))
    c.close()
    client.post("/inventory/equip", data={"item": bag(db_path, "armor")[0]["id"]})
    assert bag(db_path, "armor")[0]["equipped"]
    fangs = [a for a in bag(db_path, "artifacts") if "fang" in a["key"]]
    bell = next(a for a in bag(db_path, "artifacts") if "bell" in a["key"])
    client.post("/inventory/equip", data={"item": fangs[0]["id"]})
    r = client.post("/inventory/equip", data={"item": fangs[1]["id"]})         # same family: refused by the bot's rule
    assert "same family" in client.get(r.headers["location"]).text
    client.post("/inventory/equip", data={"item": bell["id"]})
    assert sorted(a["equipped"] for a in bag(db_path, "artifacts")) == [0, 1, 2]
    page = client.get("/profile").text
    assert page.count('action="/inventory/unequip"') == 3 and "ARMOR" in page


def test_only_your_own_gear_and_only_gear(client, db_path):
    theirs = bag(db_path, "weapons", OTHER)[0]
    r = client.post("/inventory/equip", data={"item": theirs["id"]})
    assert "no longer in your bag" in client.get(r.headers["location"]).text
    assert not bag(db_path, "weapons", OTHER)[0]["equipped"]
    c = db.connect(db_path)
    loot.store(c, UID, [dict(loot.herb("Mortal", "qi", 10), qty=1)])
    herb = db.get_items(c, UID, "herbs")[0]
    c.close()
    client.post("/inventory/equip", data={"item": herb["id"]})               # not gear: nothing is used
    assert bag(db_path, "herbs")[0]["qty"] == 1
    assert "/inventory/equip" not in client.get(f"/inventory?tab=herbs&item={herb['id']}").text
    assert client.post("/inventory/equip", data={"item": "x"}).status_code == 303


def test_profile_shows_the_gear_slots(client, db_path):
    page = client.get("/profile").text
    assert "Equipment" in page and "WEAPON" in page and "ARTIFACT 2" in page and "Choose from 2 in your bag" in page
    a = bag(db_path, "weapons")[0]
    client.post("/inventory/equip", data={"item": a["id"]})
    page = client.get("/profile").text
    assert a["name"] in page and "Unequip" in page
    r = client.post("/inventory/unequip", data={"item": a["id"], "back": "profile"})
    assert r.headers["location"] == "/profile" and "You take off" in client.get("/profile").text


def test_logged_out_cannot_equip(db_path):
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=db_path, session_secret="s"))
    c = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    a = bag(db_path, "weapons")[0]
    assert c.post("/inventory/equip", data={"item": a["id"]}).headers["location"] == "/"
    assert not bag(db_path, "weapons")[0]["equipped"]
