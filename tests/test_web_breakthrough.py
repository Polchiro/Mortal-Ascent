"""Breakthrough on the website (web/breakthrough_play.py, web/breakthrough_routes.py, docs/web.md "Breakthrough").
The attempt is the bot's own: these check that the page's server gives exactly what /breakthrough gives, one attempt
per press, and that the player plate shows the gate."""
import os
import random
import time
import urllib.parse

import pytest

import training
from bot import crafting, db
from bot import player as rules
from web import breakthrough_play as bp

A = 222
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Fixed(random.Random):
    def __init__(self, value):
        super().__init__(1)
        self.value = value

    def random(self):
        return self.value


def at_gate(conn, uid, realm="Martial Warrior", layer=10, waiting=50.0):
    need = rules.qi_needed(realm, layer)
    db.update_player(conn, uid, realm=realm, layer=layer, qi=float(need), qi_overflow=waiting, qi_collected_at=time.time())
    return need


def give_pill(conn, uid, grade="Mystic", patterns=6, qty=1):
    pill = crafting.crafted_pill("breakthrough", grade, patterns)
    db.add_item(conn, uid, pill["category"], pill["key"], pill["name"], pill["grade"], qty, pill["data"])


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "ma.db"))
    db.create_player(c, A, "Lin Yue", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return c


def test_the_look_follows_the_gate():
    assert bp.look_of("phase", "Middle Phase") == "inner"
    for realm in ("Martial Apprentice", "Martial Warrior", "Martial Expert"):
        assert bp.look_of("realm", realm) == "dawn"
    for realm in ("Martial Master", "Grandmaster", "Martial Saint"):
        assert bp.look_of("realm", realm) == "storm"
    assert bp.look_of("layer", None) is None


def test_the_assessment_is_the_bots_numbers(conn):
    at_gate(conn, A)
    give_pill(conn, A)
    a = bp.assess(conn, A)
    p = db.get_player(conn, A)
    pill = crafting.best_breakthrough_pill(conn, A, p)
    assert a["ready"] and a["kind"] == "realm" and a["target"] == "Martial Expert" and a["look"] == "dawn"
    assert a["chance"] == f"{rules.breakthrough_chance(p, pill[1]):.0%}"
    assert a["base"] == f"{training.REALM_BREAKTHROUGH_SUCCESS['Martial Expert']:.0%}"
    assert a["pill"]["name"] == pill[0]["name"]
    assert a["lose"] == f"{p['qi'] * training.BREAKTHROUGH_FAIL_QI_LOSS:,.1f}"
    assert a["injury"] == f"{training.INJURY_HOURS} hours" and a["waiting"] == "50"


def test_a_phase_gate_has_no_pill_and_no_injury(conn):
    at_gate(conn, A, layer=3)
    give_pill(conn, A)
    a = bp.assess(conn, A)
    assert a["kind"] == "phase" and a["look"] == "inner" and a["pill"] is None and a["injury"] is None
    assert a["chance"] == f"{training.PHASE_BOTTLENECK_SUCCESS['Martial Warrior']:.0%}"


def test_what_is_missing_closes_the_gate(conn):
    at_gate(conn, A, realm="Martial Expert")              # Martial Master needs a technique at Entering the Hall
    a = bp.Gates().view(conn, A)
    assert not a["ready"] and "Entering the Hall" in a["missing"] and "token" not in a
    p, techs = bp.now_player(conn, A)
    q = bp.plate(p, techs)
    assert q["full"] and not q["ready"] and q["why"].startswith("Needs") and q["look"] == "storm"


def test_not_full_and_no_gate(conn):
    db.update_player(conn, A, realm="Martial Warrior", layer=5, qi=1.0, qi_collected_at=time.time())
    a = bp.assess(conn, A)
    assert not a["ready"] and a["kind"] == "layer"
    p, techs = bp.now_player(conn, A)
    assert not bp.plate(p, techs)["full"]


def test_passive_qi_counts_as_the_bot_would_bank_it(conn):
    need = rules.qi_needed("Martial Warrior", 3)
    db.update_player(conn, A, realm="Martial Warrior", layer=3, qi=need - 0.5, qi_collected_at=time.time() - 3600)
    assert bp.assess(conn, A)["ready"]                    # an hour of gathering has filled it
    g = bp.Gates(rng=Fixed(0.0))
    a = g.view(conn, A)
    r, why = g.attempt(conn, A, a["token"])
    assert why is None and r["ok"] and db.get_player(conn, A)["layer"] == 4


def test_a_success_is_the_bots_success(conn):
    at_gate(conn, A, waiting=400.0)
    give_pill(conn, A, qty=2)
    g = bp.Gates(rng=Fixed(0.0))
    a = g.view(conn, A)
    r, why = g.attempt(conn, A, a["token"])
    p = db.get_player(conn, A)
    assert why is None and r["ok"] and r["realm_up"] and p["realm"] == "Martial Expert"
    assert p["breakthroughs"] == 1 and r["after"]["realm"] == "Martial Expert"
    assert r["layers"] == p["layer"] and r["pill"]
    assert db.get_items(conn, A, "pills")[0]["qty"] == 1                          # one pill used, as on Discord
    assert r["dew"] and any(i["category"] == "materials" for i in db.get_items(conn, A))
    assert any("floods in" in line for line in r["lines"])


def test_a_failure_costs_what_the_card_said(conn):
    need = at_gate(conn, A, waiting=0.0)
    give_pill(conn, A)
    g = bp.Gates(rng=Fixed(0.999))
    a = g.view(conn, A)
    r, why = g.attempt(conn, A, a["token"])
    p = db.get_player(conn, A)
    assert why is None and not r["ok"] and p["realm"] == "Martial Warrior" and p["failed_breakthroughs"] == 1
    assert p["qi"] == pytest.approx(need * (1 - training.BREAKTHROUGH_FAIL_QI_LOSS))
    assert r["lost"] == a["lose"] and r["injury"] and rules.injured_for(p) > 0
    assert db.get_items(conn, A, "pills") == []                                     # used up either way


def test_keeping_the_pill(conn):
    at_gate(conn, A)
    give_pill(conn, A)
    g = bp.Gates(rng=Fixed(0.999))
    a = g.view(conn, A)
    r, _ = g.attempt(conn, A, a["token"], keep_pill=True)
    assert r["pill"] is None and r["chance"] == a["chance_bare"]
    assert db.get_items(conn, A, "pills")[0]["qty"] == 1


def test_one_attempt_per_press(conn):
    at_gate(conn, A)
    g = bp.Gates(rng=Fixed(0.999))
    a = g.view(conn, A)
    assert g.attempt(conn, A, "not-it") == (None, "This page was out of date. Here is how things stand now.")
    first, _ = g.attempt(conn, A, a["token"])
    again, why = g.attempt(conn, A, a["token"])                                    # a double click, a reload
    assert why is None and again == first
    assert db.get_player(conn, A)["failed_breakthroughs"] == 1
    old = a["token"]
    a2 = g.view(conn, A)
    assert a2["token"] != old


def test_the_gate_is_checked_again_inside_the_write(conn):
    at_gate(conn, A)
    g = bp.Gates(rng=Fixed(0.0))
    a = g.view(conn, A)
    db.update_player(conn, A, realm="Martial Expert", layer=1, qi=0.0)             # another tab got there first
    r, why = g.attempt(conn, A, a["token"])
    assert r is None and "moved on" in why
    assert db.get_player(conn, A)["breakthroughs"] == 0


def test_the_first_gate_cannot_fail(conn):
    at_gate(conn, A, realm="Mortal", layer=3)
    a = bp.assess(conn, A)
    assert a["first"] and a["chance"] == "100%" and a["look"] == "dawn"


def test_the_art_is_there():
    for f in ("storm.jpg", "storm.mp4", "storm.mp3", "dawn.jpg", "dawn_lit.jpg", "dawn.mp4", "dawn.mp3"):
        assert os.path.exists(os.path.join(ROOT, "art", "breakthrough", f)), f
    for g in ("female", "male"):
        from web.breakthrough_routes import ends_art
        ends = ends_art(g)
        for name in ("inner", "ascend"):
            for key in ("src", "sound"):
                assert os.path.exists(os.path.join(ROOT, ends[name][key].lstrip("/"))), (g, name, key)


# ── the pages ────────────────────────────────────────────────────────────────

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

UID = 123456789012345678


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    at_gate(c, UID)
    c.close()
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=path, session_secret="test")
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "token")
    monkeypatch.setattr(oauth, "fetch_user", lambda token: {"id": UID, "username": "shoaib", "avatar": None})
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
    cl.get("/callback", params={"code": "good", "state": q["state"][0]})
    cl.db_path = path
    return cl


def test_the_plate_shows_the_gate(client):
    page = client.get("/town").text
    assert 'id="heroQi"' in page and 'id="heroBreak"' in page and "Break through" in page
    assert "/breakthrough?from=/town" in page and "k-dawn" in page
    profile = client.get("/profile").text
    assert "pbreak" in profile and 'href="/breakthrough?from=/profile"' in profile


def test_an_attempt_through_the_routes(client):
    client.app.state.gates.rng = Fixed(0.0)
    page = client.get("/breakthrough?from=/profile")
    assert page.status_code == 200 and "breakthrough.js" in page.text and "Hold to begin" in page.text
    assert 'href="/profile"' in page.text                                          # Back goes where you came from
    a = client.get("/breakthrough/view").json()
    out = client.post("/breakthrough/attempt", json={"token": a["token"], "keep_pill": False}).json()
    assert out["error"] is None and out["result"]["ok"] and out["result"]["after"]["realm"] == "Martial Expert"
    again = client.post("/breakthrough/attempt", json={"token": a["token"]}).json()
    assert again["result"] == out["result"]
    stale = client.post("/breakthrough/attempt", json={"token": "old"}).json()
    assert stale["result"] is None and stale["error"] and stale["view"]["realm"] == "Martial Expert"


def test_back_only_goes_to_this_site(client):
    client.get("/breakthrough?from=https://evil.example")
    assert 'href="/town"' in client.get("/breakthrough").text
    client.get("/breakthrough?from=//evil.example")
    assert "evil" not in client.get("/breakthrough").text


def test_the_pages_need_a_login(tmp_path):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=str(tmp_path / "x.db"), session_secret="t")
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert cl.get("/breakthrough").headers["location"] == "/"
    assert cl.get("/breakthrough/view").json() == {"gone": True}
    assert cl.post("/breakthrough/attempt", json={}).json() == {"gone": True}
