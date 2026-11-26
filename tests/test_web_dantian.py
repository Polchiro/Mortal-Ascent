"""The Dantian screen (web/dantian_play.py, web/dantian_routes.py, docs/web.md "The Dantian"): the Qi ledger is the
bot's own sum, a pill's preview is what eating it then does (through the bot's own loot.use_item), toxicity reads as
the bot reads it, and the plate and the profile show it."""
import random
import time
import urllib.parse

import pytest

import training
from bot import crafting, db, loot
from bot import player as rules
from web import dantian_play as dp
from web import overworld
from web import profile as prof

A = 444


def pill(conn, uid, kind, grade="Yellow", patterns=6, qty=1):
    p = crafting.crafted_pill(kind, grade, patterns)
    db.add_item(conn, uid, p["category"], p["key"], p["name"], p["grade"], qty, p["data"])
    return [it for it in db.get_items(conn, uid, "pills") if it["key"] == p["key"]][0]


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "ma.db"))
    db.create_player(c, A, "Lin Yue", "Gifted", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, A, realm="Martial Warrior", layer=5, qi=10.0, qi_collected_at=time.time())
    return c


def test_the_ledger_is_the_bots_sum(conn):
    v = dp.view(conn, A)
    p = db.get_player(conn, A)
    rate = rules.qi_rate(p, time.time(), db.get_techniques(conn, A))[0]
    assert v["rate"] == pytest.approx(rate) and v["formula"].endswith(f"= {dp.num(rate, 2)} Qi/h")
    keys = [r["key"] for r in v["ledger"]]
    assert keys == ["base", "talent", "technique", "artifact", "blessing", "pill", "land"]
    assert v["ledger"][1]["on"] and v["ledger"][1]["value"] == f"+{dp.pct(training.TALENT_QI_BONUS['Gifted'])}"
    off = {r["key"]: r for r in v["ledger"] if not r["on"]}
    assert off["land"]["how"] and off["pill"]["how"] and off["blessing"]["how"]
    assert v["per_sec"] == dp.num(rate / 3600, 4)


def test_layers_and_gates(conn):
    v = dp.view(conn, A)
    gates = {l["n"]: l["gate"] for l in v["layers"] if l["gate"]}
    assert gates == {3: "phase", 6: "phase", 9: "phase", 10: "realm"}
    assert [l["n"] for l in v["layers"] if l["now"]] == [5] and v["next_layer"] == "6th"


def test_toxicity_reads_as_the_bot_reads_it(conn):
    now = time.time()
    db.update_player(conn, A, toxicity=5, toxicity_at=now - 3 * 3600)
    t = dp.toxicity(db.get_player(conn, A), now)
    assert t["n"] == 5 and t["zone"] == "half" and t["mult"] == 0.5
    assert t["next_s"] == pytest.approx((training.TOXICITY_DECAY_HOURS - 3) * 3600, abs=2)
    db.update_player(conn, A, toxicity=0)
    assert dp.toxicity(db.get_player(conn, A), now)["zone"] == "clean"


def test_the_plate_badge_says_what_toxicity_does(conn):
    from web import overworld
    now = time.time()
    for n, zone, hint in ((3, "mild", "full power · one more halves them"), (4, "half", "only work at 50%"),
                          (7, "quarter", "only work at 25%")):
        db.update_player(conn, A, toxicity=n, toxicity_at=now)
        t = overworld.tox_of(db.get_player(conn, A), now)
        assert t["n"] == n and t["zone"] == zone and hint in t["hint"] and t["fade"].startswith("−1 every")
    db.update_player(conn, A, toxicity=1, toxicity_at=now)
    assert "halves" not in overworld.tox_of(db.get_player(conn, A), now)["hint"]
    db.update_player(conn, A, toxicity=0)
    assert overworld.tox_of(db.get_player(conn, A), now) is None


def test_a_qi_pill_does_what_it_said(conn):
    it = pill(conn, A, "qi", "Yellow", 6)
    p = db.get_player(conn, A)
    pre = dp.preview(p, db.get_techniques(conn, A), it, time.time())
    assert pre["can"] and pre["tox"] == [0, 1]
    r, why = dp.Pills().eat(conn, A, it["id"])
    assert why is None and r["after"]["tox"] == 1
    mult = db.get_player(conn, A)["pill_mult"]
    assert f"×{mult:.2f}" in pre["lines"][0]
    again = dp.preview(db.get_player(conn, A), [], pill(conn, A, "qi", "Yellow", 6), time.time())
    assert not again["can"] and "do not stack" in again["why"]


def test_a_burst_pill_gives_what_it_said(conn):
    it = pill(conn, A, "burst", "Yellow", 9)
    pre = dp.preview(db.get_player(conn, A), db.get_techniques(conn, A), it, time.time())
    before = db.get_player(conn, A)["qi"]
    dp.Pills().eat(conn, A, it["id"])
    gained = db.get_player(conn, A)["qi"] - before
    shown = float(pre["lines"][0].split("+")[1].split(" ")[0].replace(",", ""))
    assert gained == pytest.approx(shown, abs=0.2)


def test_cleansing_and_mending(conn):
    now = time.time()
    db.update_player(conn, A, toxicity=4, toxicity_at=now)
    c = pill(conn, A, "cleansing", "Yellow", 5)
    pre = dp.preview(db.get_player(conn, A), [], c, now)
    dp.Pills().eat(conn, A, c["id"])
    assert rules.current_toxicity(db.get_player(conn, A)) == pre["tox"][1] < 4
    m = pill(conn, A, "mending", "Mystic", 9)
    assert not dp.preview(db.get_player(conn, A), [], m, now)["can"]                 # not injured
    assert dp.Pills().eat(conn, A, m["id"])[0] is None
    db.update_player(conn, A, injured_until=now + 3600)
    assert dp.preview(db.get_player(conn, A), [], m, now)["can"]


def test_breakthrough_pills_wait_for_the_gate(conn):
    it = pill(conn, A, "breakthrough", "Mystic", 6)
    pre = dp.preview(db.get_player(conn, A), [], it, time.time())
    assert not pre["can"] and "realm gate" in pre["why"]
    assert dp.Pills().eat(conn, A, it["id"])[0] is None and db.get_item(conn, A, it["id"])["qty"] == 1


def test_the_heaven_defying_pill(conn):
    h = loot.HEAVEN_DEFYING
    db.add_item(conn, A, h["category"], h["key"], h["name"], h["grade"], 1)
    it = [x for x in db.get_items(conn, A, "pills") if x["key"] == "heaven_defying"][0]
    pre = dp.preview(db.get_player(conn, A), [], it, time.time())
    assert pre["kind"] == "heaven" and pre["lines"][0] == "Talent Gifted → Genius"
    r, _ = dp.Pills().eat(conn, A, it["id"])
    assert r["before"]["talent"] == "Gifted" and r["after"]["talent"] == "Genius"


def test_one_pill_per_press(conn):
    it = pill(conn, A, "burst", "Yellow", 9, qty=3)
    pills = dp.Pills()
    first = pills.eat(conn, A, it["id"], nonce="x")
    assert pills.eat(conn, A, it["id"], nonce="x") == first
    assert db.get_item(conn, A, it["id"])["qty"] == 2
    assert dp.Pills().eat(conn, A, 999999) == (None, "That pill is no longer in your bag.")


def test_the_ping_switch_is_the_bots(conn):
    assert dp.set_pings(conn, A, False) is False and db.get_player(conn, A)["qi_pings"] == 0
    assert dp.view(conn, A)["pings"] is False
    dp.set_pings(conn, A, True)
    assert db.get_player(conn, A)["qi_pings"] == 1


def test_the_plate_shows_the_gourd(conn):
    p = db.get_player(conn, A)
    assert overworld.hero_view(conn, A, p)["tox"] is None
    db.update_player(conn, A, toxicity=6, toxicity_at=time.time())
    t = overworld.hero_view(conn, A, db.get_player(conn, A))["tox"]
    assert t["n"] == 6 and t["zone"] == "quarter" and t["mult"] == "25%"


def test_the_passives_by_what_they_help(conn):
    rng = random.Random(1)
    w = loot.roll_weapon("treasure", rng)
    w["data"] = dict(w.get("data") or {}, passives=["keen_edge", "lifesteal"])
    db.add_item(conn, A, w["category"], w["key"], w["name"], w["grade"], 1, w["data"])
    a = loot.roll_artifact("treasure", rng)
    a["data"] = dict(a.get("data") or {}, passives=["qi_flow", "deep_pockets"])
    db.add_item(conn, A, a["category"], a["key"], a["name"], a["grade"], 1, a["data"])
    conn.execute("UPDATE items SET equipped = 1 WHERE user_id = ? AND category IN ('weapons', 'artifacts')", (A,))
    conn.commit()
    v = prof.passives_view(conn, A)
    groups = {g["group"]: [r["name"] for r in g["rows"]] for g in v["groups"]}
    assert groups == {"Combat": ["Keen Edge", "Lifesteal"], "Cultivation": ["Qi Flow"], "Fortune": ["Deep Pockets"]}
    assert v["totals"] == ["Attack +3% from 1 passive"] and v["count"] == 4
    row = [r for r in dp.view(conn, A)["ledger"] if r["key"] == "artifact"][0]
    assert row["on"] and row["value"] == "+2%"                                     # Qi Flow reaches the Qi Rate


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
    db.update_player(c, UID, toxicity=2, toxicity_at=time.time())
    pill(c, UID, "burst", "Mortal", 9, qty=2)
    c.close()
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=path, session_secret="test")
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "token")
    monkeypatch.setattr(oauth, "fetch_user", lambda token: {"id": UID, "username": "shoaib", "avatar": None})
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
    cl.get("/callback", params={"code": "good", "state": q["state"][0]})
    return cl


def test_the_ways_in(client):
    town = client.get("/town").text
    assert 'id="heroQi"' in town and "/dantian?from=" in town and 'id="heroTox"' in town and "toxicity.webp" in town
    profile = client.get("/profile").text
    assert "/dantian?from=/profile" in profile and "Your passives" in profile


def test_eating_through_the_routes(client):
    page = client.get("/dantian")
    assert page.status_code == 200 and "dantian.js" in page.text and "WHERE YOUR QI COMES FROM" in page.text
    v = client.get("/dantian/view").json()
    burst = [p for p in v["pills"] if p["kind"] == "burst"][0]
    out = client.post("/dantian/eat", json={"item": burst["id"], "nonce": "n"}).json()
    assert out["error"] is None and out["result"]["after"]["tox"] == 2                # 9 patterns: a clean pill
    assert client.post("/dantian/eat", json={"item": "x"}).json()["error"]
    assert client.post("/dantian/pings", json={"on": False}).json() == {"pings": False}


def test_the_pages_need_a_login(tmp_path):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=str(tmp_path / "x.db"), session_secret="t")
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert cl.get("/dantian").headers["location"] == "/"
    assert cl.get("/dantian/view").json() == {"gone": True}
    assert cl.post("/dantian/eat", json={"item": 1}).json() == {"gone": True}
    assert cl.post("/dantian/pings", json={"on": True}).json() == {"gone": True}
