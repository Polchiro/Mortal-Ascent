"""Techniques on the website (web/techniques_play.py, web/techniques_routes.py, docs/web.md "Techniques"): the same
equip and unequip as Discord's /techniques, through bot/db's own functions."""
import urllib.parse

import pytest

from bot import db
from bot import player as rules
from web import techniques_play as tp

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

A = 333333333333333333


@pytest.fixture
def path(tmp_path):
    p = str(tmp_path / "ma.db")
    c = db.connect(p)
    db.create_player(c, A, "Lin Yue", "Gifted", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    c.close()
    return p


def conn_of(path):
    return db.connect(path)


def by_name(c, name):
    return next(t for t in db.get_techniques(c, A, equipped_only=False) if t["name"] == name)


def learn(c, name, type_, grade):
    return db.learn_technique(c, A, name, type_, grade, equip=False)


def equipped(c):
    return {t["name"] for t in db.get_techniques(c, A)}


def test_the_page_lists_what_you_know(path):
    c = conn_of(path)
    learn(c, "Fierce Tiger Claw", "attack", "Yellow")
    v = tp.view(c, A)
    assert [s["slot"] for s in v["sockets"]] == ["Attack", "Defense", "Flex"] and v["sockets"][2]["locked"]
    cards = {x["name"]: x for x in v["cards"]}
    assert cards["Iron Fist"]["equipped"] and cards["Iron Fist"]["action"] is None      # the only attack: stays
    assert cards["Fierce Tiger Claw"]["action"] == "equip" and cards["Fierce Tiger Claw"]["note"] == "Replaces Iron Fist"
    assert cards["Fierce Tiger Claw"]["power"].startswith("×") and cards["Fierce Tiger Claw"]["grade"] == "Yellow"


def test_equipping_swaps_as_the_bot_does(path):
    c = conn_of(path)
    tid = learn(c, "Fierce Tiger Claw", "attack", "Yellow")
    ok, msg = tp.equip(c, A, tid)
    assert ok and "in place of Iron Fist" in msg
    assert equipped(c) == {"Fierce Tiger Claw", "Horse Stance Guard"}
    assert tp.equip(c, A, tid) == (False, "That technique is already equipped.")
    assert tp.equip(c, A, 999999)[0] is False


def test_the_flex_slot_and_taking_off(path):
    c = conn_of(path)
    db.update_player(c, A, realm="Martial Warrior", layer=1)
    tid = learn(c, "Fierce Tiger Claw", "attack", "Yellow")
    v = {x["name"]: x for x in tp.view(c, A)["cards"]}
    assert v["Fierce Tiger Claw"]["note"] == "Goes into a free slot"
    ok, msg = tp.equip(c, A, tid)
    assert ok and "in place" not in msg and len(equipped(c)) == 3
    v = {x["name"]: x for x in tp.view(c, A)["cards"]}
    assert v["Fierce Tiger Claw"]["action"] == "unequip" and v["Iron Fist"]["action"] == "unequip"
    assert v["Horse Stance Guard"]["action"] is None                       # the only defense
    ok, _ = tp.unequip(c, A, tid)
    assert ok and equipped(c) == {"Iron Fist", "Horse Stance Guard"}
    ok, why = tp.unequip(c, A, by_name(c, "Iron Fist")["id"])
    assert not ok and "one technique of each type" in why


def test_no_swapping_in_a_fight(path):
    c = conn_of(path)
    tid = learn(c, "Fierce Tiger Claw", "attack", "Yellow")
    ok, why = tp.equip(c, A, tid, fighting=True)
    assert not ok and "outside of fights" in why and "Iron Fist" in equipped(c)


def test_the_routes(path, monkeypatch):
    c = conn_of(path)
    tid = learn(c, "Fierce Tiger Claw", "attack", "Yellow")
    c.close()
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=path, session_secret="test")
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "token")
    monkeypatch.setattr(oauth, "fetch_user", lambda token: {"id": A, "username": "x", "avatar": None})
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert cl.get("/techniques").status_code == 303                       # signed out
    q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
    cl.get("/callback", params={"code": "good", "state": q["state"][0]})
    page = cl.get("/techniques").text
    assert "Fierce Tiger Claw" in page and "Replaces Iron Fist" in page and 'href="/techniques"' in page
    r = cl.post("/techniques/equip", data={"tech": str(tid)})
    assert r.status_code == 303 and r.headers["location"] == "/techniques"
    page = cl.get("/techniques").text
    assert "Equipped Fierce Tiger Claw in place of Iron Fist." in page
    assert "/techniques" in cl.get("/profile").text


def test_the_cards_come_in_grade_sections_heaven_first(path):
    c = conn_of(path)
    learn(c, "Fierce Tiger Claw", "attack", "Yellow")
    learn(c, "Heaven-Rending Palm", "attack", "Heaven")
    v = tp.view(c, A)
    assert [s["grade"] for s in v["sections"]] == ["Heaven", "Yellow", "Mortal"]           # only grades you know
    mortal = v["sections"][-1]["cards"]
    assert mortal[0]["equipped"] and sum(len(s["cards"]) for s in v["sections"]) == len(v["cards"]) == v["learned"]
    assert v["attacks"] + v["defenses"] == v["learned"]


def test_the_page_has_the_filter_and_sections(path, monkeypatch):
    c = conn_of(path)
    learn(c, "Heaven-Rending Palm", "attack", "Heaven")
    c.close()
    html = open("web/templates/techniques.html").read()
    assert 'data-show="attack"' in html and 'data-show="defense"' in html and 'class="techgrade" open' in html
    assert 'data-type="{{ t.type }}"' in html
