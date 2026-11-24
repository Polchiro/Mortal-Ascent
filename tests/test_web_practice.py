"""Practice with Senior Sister Xue on the website (web/practice_play.py, docs/technique.md "Practice on the website")."""
import os
import random
import urllib.parse
from collections import Counter

import pytest

import challenges
import technique
from bot import db, trainer
from bot import player as rules
from web import practice_play as pp

A = 111
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


class Quiet(random.Random):
    """No event, no condition: the plain drill (every roll misses)."""
    def random(self):
        return 0.99

    def randint(self, a, b):
        return a


@pytest.fixture
def setup(tmp_path):
    conn = db.connect(str(tmp_path / "ma.db"))
    db.create_player(conn, A, "Lin Feng", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    clock = Clock()
    return conn, clock, pp.Hall(clock=clock, rng=random.Random(7))


def techs(conn):
    return {t["name"]: t for t in db.get_techniques(conn, A)}


def every_technique():
    return [{"name": n, "type": s["type"], "grade": s["grade"]} for n, s in rules.TECH_BY_NAME.items()]


def perfect(prompts):
    """The presses of someone who never misses (and leaves every feint alone)."""
    out = []
    for p in prompts:
        if p["kind"] == "tap":
            out += [[p["at"], p["lane"], "d"], [p["at"] + 50, p["lane"], "u"]]
        elif p["kind"] == "brace":
            out += [[p["at"], p["lane"], "d"], [p["at"] + p["hold"] + 20, p["lane"], "u"]]
        elif p["kind"] == "charge":
            out += [[p["at"] - 300, p["lane"], "d"], [p["at"], p["lane"], "u"]]
    return out


def run(hall, clock, conn, inputs):
    """Begin the drill, let it run its length, send the presses."""
    assert hall.go(A) is None
    clock.t += hall.drills[A].length / 1000 + 0.5
    return hall.submit(conn, A, inputs)


# ── what each technique drills ───────────────────────────────────────────────

def test_every_technique_has_a_drill_of_its_own_kind():
    seen = Counter()
    for t in every_technique():
        d = pp.drill_of(t)
        assert d["mode"] == ("strike" if t["type"] == "attack" else "defend")
        assert d["motion"] in (("fist", "palm", "kick", "finger") if t["type"] == "attack" else ("brace", "deflect", "sidestep"))
        seen[d["mode"]] += 1
    assert seen == {"strike": 15, "defend": 15}
    assert pp.drill_of({"name": "Drifting Mist Steps", "type": "defense"})["motion"] == "sidestep"


def test_the_patterns_follow_the_technique():
    for t in every_technique():
        d = pp.drill_of(t)
        for tier in range(1, 6):
            prompts, w = pp.pattern(d, tier, [], None, random.Random(tier))
            ats = [p["at"] for p in prompts]
            assert ats == sorted(ats) and [p["i"] for p in prompts] == list(range(len(prompts)))
            lanes = (pp.STRIKE_LANES["post" if d["motion"] == "kick" else "dummy"] if d["mode"] == "strike"
                     else pp.DEFEND_LANES)
            assert all(0 <= p["lane"] < lanes for p in prompts)
            assert sum(1 for p in prompts if p["phase"] == "finish") == 1
            kinds = {p["kind"] for p in prompts}
            if d["mode"] == "strike":
                assert "brace" not in kinds and "charge" in kinds          # the finishing blow is always a charge
                if d["motion"] == "palm":
                    assert all(p.get("pair") for p in prompts if p["phase"] == "form")
                if d["motion"] == "finger" or d["effect"] == "pierce":
                    assert all(p["small"] for p in prompts)
            else:
                assert "charge" not in kinds
                if d["motion"] == "brace":
                    assert all(p["hold"] > 0 for p in prompts if p["kind"] == "brace")
                if d["effect"] not in ("counter", "recover"):
                    assert all(p["lane"] < 3 for p in prompts)


def test_the_effects_shape_the_drill():
    def drill(name):
        return pp.drill_of({"name": name, "type": rules.TECH_BY_NAME[name]["type"]})
    by_effect = {}
    for t in every_technique():
        by_effect.setdefault(rules.TECH_BY_NAME[t["name"]]["effect"] and rules.TECH_BY_NAME[t["name"]]["effect"][0],
                             t["name"])
    rng = random.Random(3)
    if "combo" in by_effect:
        ps, _ = pp.pattern(drill(by_effect["combo"]), 3, [], None, rng)
        assert any(p.get("chain") for p in ps)
    if "heavy" in by_effect:
        ps, _ = pp.pattern(drill(by_effect["heavy"]), 3, [], None, rng)
        assert sum(1 for p in ps if p["kind"] == "charge") > 1
    if "counter" in by_effect:
        ps, _ = pp.pattern(drill(by_effect["counter"]), 3, [], None, rng)
        assert any(p.get("counter") and p["lane"] == 3 for p in ps)
    if "recover" in by_effect:
        ps, _ = pp.pattern(drill(by_effect["recover"]), 3, [], None, rng)
        assert any(p.get("breath") and p["lane"] == 3 for p in ps)


def test_the_stages_grow_faster_and_the_last_is_strict():
    d = pp.drill_of({"name": "Iron Fist", "type": "attack"})
    gaps = [pp.TIERS[t]["gap"] for t in range(1, 5)]
    assert gaps == sorted(gaps, reverse=True)
    assert pp.TIERS[5]["perfect"] < pp.TIERS[4]["perfect"] and pp.TIERS[5]["count"] < pp.TIERS[4]["count"]
    assert not any(p["kind"] == "feint" for p in pp.pattern(d, 1, [], None, random.Random(1))[0])
    assert any(p["kind"] == "feint" for s in range(20) for p in pp.pattern(d, 4, [], None, random.Random(s))[0])


def test_the_conditions_mean_what_they_say():
    d = pp.drill_of({"name": "Iron Fist", "type": "attack"})
    plain, rain = pp.windows(2, [], d), pp.windows(2, ["heavy_rain"], d)
    assert rain["perfect"] == round(plain["perfect"] * challenges.CONDITIONS["heavy_rain"]["timer_multiplier"])
    assert pp.windows(1, ["drunken_master"], d)["feints"] >= pp.DRUNK_FEINTS
    ps, _ = pp.pattern(d, 2, [], None, random.Random(5))
    res = ["perfect" if p["kind"] != "charge" else "miss" for p in ps]
    whole, _ = pp.score_of(ps, res, 0, [])
    hurt, _ = pp.score_of(ps, res, 0, ["old_injury"])
    assert hurt > whole                                          # a missed charge counts half with Old Injury


# ── grading ──────────────────────────────────────────────────────────────────

def test_perfect_play_scores_full_and_nothing_scores_nothing():
    for name in ("Iron Fist", "Horse Stance Guard"):
        d = pp.drill_of({"name": name, "type": rules.TECH_BY_NAME[name]["type"]})
        ps, w = pp.pattern(d, 3, [], None, random.Random(2))
        res, strays = pp.grade(ps, perfect(ps), w)
        assert strays == 0 and set(res) <= {"perfect", "avoided"}
        assert pp.score_of(ps, res, strays, [])[0] == 1.0
        res, strays = pp.grade(ps, [], w)
        assert pp.score_of(ps, res, strays, [])[0] == 0.0


def test_timing_windows_and_holds():
    w = {"perfect": 100, "good": 250, "approach": 1000}
    tap = [{"i": 0, "at": 1000, "lane": 1, "kind": "tap", "hold": 0}]
    assert pp.grade(tap, [(1080, 1, "d")], w)[0] == ["perfect"]
    assert pp.grade(tap, [(1200, 1, "d")], w)[0] == ["good"]
    assert pp.grade(tap, [(1300, 1, "d")], w) == (["miss"], 1)           # too late: a press at nothing
    assert pp.grade(tap, [(1000, 2, "d")], w) == (["miss"], 1)           # the wrong lane
    brace = [{"i": 0, "at": 1000, "lane": 0, "kind": "brace", "hold": 400}]
    assert pp.grade(brace, [(1000, 0, "d"), (1420, 0, "u")], w)[0] == ["perfect"]
    assert pp.grade(brace, [(1000, 0, "d"), (1100, 0, "u")], w)[0] == ["good"]     # let go too soon
    assert pp.grade(brace, [(1200, 0, "d"), (1250, 0, "u")], w)[0] == ["miss"]
    charge = [{"i": 0, "at": 2000, "lane": 1, "kind": "charge", "hold": 0}]
    assert pp.grade(charge, [(1500, 1, "d"), (2050, 1, "u")], w)[0] == ["perfect"]
    assert pp.grade(charge, [(1500, 1, "d"), (1600, 1, "u")], w)[0] == ["miss"]    # let go too early
    assert pp.grade(charge, [(1500, 1, "d")], w)[0] == ["miss"]                   # never let go
    feint = [{"i": 0, "at": 1000, "lane": 0, "kind": "feint", "hold": 0}]
    assert pp.grade(feint, [], w)[0] == ["avoided"]
    assert pp.grade(feint, [(990, 0, "d")], w)[0] == ["struck"]


def test_mashing_never_pays():
    d = pp.drill_of({"name": "Iron Fist", "type": "attack"})
    ps, w = pp.pattern(d, 2, [], None, random.Random(4))
    end = pp.duration(ps, w)
    mash = [(t, lane, k) for t in range(0, end, 60) for lane in range(4) for k in ("d", "u")]
    res, strays = pp.grade(ps, mash, w)
    assert pp.score_of(ps, res, strays, [])[0] < challenges.LOW_SCORE_THRESHOLD


# ── the hall: start, the rest, the pay ───────────────────────────────────────

def test_a_drill_starts_the_rest_and_pays_what_the_bot_pays(setup):
    conn, clock, hall = setup
    hall.rng = Quiet()
    fist = techs(conn)["Iron Fist"]
    assert hall.start(conn, A, fist["id"]) is None
    assert db.cooldown_left(conn, A, "practice", clock()) == trainer.cooldown_seconds(db.get_player(conn, A), clock(), "practice")
    assert hall.start(conn, A, fist["id"]) == "You are already practising."
    s = hall.state(A)
    assert s["drill"]["mode"] == "strike" and s["technique"]["tier"] == 1 and not s["conditions"] and not s["event"]
    assert s["instructor"]["name"] == pp.NAME and s["hall"]["sound"] == pp.HALL_SOUND
    d = hall.drills[A]
    result, why = run(hall, clock, conn, perfect(d.prompts))
    assert why is None and result["score"] == 1.0 and result["verdict"] == "great" and result["approve"]
    want = round(trainer.practice_exp(1.0, [], 1.0, 1.0))
    assert result["gained"] == want and techs(conn)["Iron Fist"]["mastery_exp"] == want
    assert db.daily_count(conn, A, "practice", clock()) == 1
    assert hall.submit(conn, A, [])[0] is result                     # sent twice: paid once
    hall.done(A)
    assert A not in hall.drills
    why = hall.start(conn, A, fist["id"])
    assert why.startswith("Your hands need rest.")


def test_a_low_score_pays_a_tenth(setup):
    conn, clock, hall = setup
    hall.rng = Quiet()
    assert hall.start(conn, A, techs(conn)["Horse Stance Guard"]["id"]) is None
    result, _ = run(hall, clock, conn, [])
    assert result["score"] == 0 and result["gained"] == 0 and not result["approve"]
    assert any("10%" in n for n in result["notes"])


def test_the_server_keeps_the_time(setup):
    conn, clock, hall = setup
    tid = techs(conn)["Iron Fist"]["id"]
    assert hall.start(conn, A, tid) is None
    assert hall.submit(conn, A, []) == (None, "The drill hasn't begun.")
    hall.go(A)
    clock.t += 3
    assert hall.submit(conn, A, []) == (None, "The drill isn't over yet.")
    clock.t += hall.drills[A].length / 1000
    assert hall.submit(conn, A, [["x", 0, "d"]]) == (None, "Those presses can't be right.")
    assert hall.submit(conn, A, [[100, 9, "d"]]) == (None, "Those presses can't be right.")
    assert hall.submit(conn, A, [[1e9, 0, "d"]]) == (None, "Those presses can't be right.")
    assert hall.submit(conn, A, "nonsense") == (None, "Those presses can't be right.")
    assert hall.submit(conn, A, [])[1] is None


def test_a_full_bar_goes_to_the_trial_and_walking_away_pays_nothing(setup):
    conn, clock, hall = setup
    t = techs(conn)["Iron Fist"]
    db.add_mastery(conn, t["id"], rules.mastery_cap(t))
    assert "Pass its trial with the Martial Master" in hall.start(conn, A, t["id"])
    assert hall.start(conn, A, 999) == "You don't know that technique."
    g = techs(conn)["Horse Stance Guard"]
    assert hall.start(conn, A, g["id"]) is None
    hall.give_up(A)
    assert A not in hall.drills and techs(conn)["Horse Stance Guard"]["mastery_exp"] == 0
    assert db.cooldown_left(conn, A, "practice", clock())                # the rest stays, as on Discord


def test_a_drill_left_unbegun_or_unsent_is_dropped(setup):
    conn, clock, hall = setup
    assert hall.start(conn, A, techs(conn)["Iron Fist"]["id"]) is None
    clock.t += hall.READY_SECONDS + 1
    assert hall.state(A) is None


def test_the_rival_disciple_doubles_it(setup):
    conn, clock, hall = setup

    hall.rng = Quiet()
    assert hall.start(conn, A, techs(conn)["Iron Fist"]["id"]) is None
    d = hall.drills[A]
    d.event = "rival_disciple"                                       # as if it had been rolled
    d.prompts, d.w = pp.pattern(d.drill, d.tier, d.conditions, d.event, random.Random(1))
    assert sum(1 for p in d.prompts if p.get("rival")) == pp.RIVAL_TARGETS
    result, _ = run(hall, clock, conn, perfect(d.prompts))
    assert result["rival"] is True
    mult = challenges.EVENTS["rival_disciple"]["win_exp_multiplier"]
    assert result["gained"] == round(trainer.practice_exp(1.0, d.conditions, mult, 1.0))


def test_the_yard_lists_a_drill_for_each_technique(setup):
    conn, clock, hall = setup
    v = hall.hall(conn, A)
    ids = {t["name"]: t["id"] for t in db.get_techniques(conn, A)}
    assert v["drills"][ids["Iron Fist"]]["mode"] == "strike" and v["drills"][ids["Horse Stance Guard"]]["mode"] == "defend"
    assert v["wait"] is None and v["full_left"] == technique.PRACTICE_DAILY_RATES[0][0] and v["base"] == technique.PRACTICE_BASE_EXP


def test_her_movements_and_the_hall_are_there():
    sheets = pp.instructor_sheets()
    assert sheets and {"watch", "begin", "approve", "disapprove"} <= set(sheets["sheets"])
    for name, sp in sheets["sheets"].items():
        assert os.path.exists(os.path.join(ROOT, sp["src"].lstrip("/")))
        assert len(sp["at"]) == sp["frames"]
        if name != "watch":
            assert os.path.exists(os.path.join(ROOT, sp["sound"]["src"].lstrip("/")))
    for pic in ("hall.jpg", "hall.wav", "portrait.jpg", "plaque.webp", "scroll.webp", "sandbag.webp", "staff.webp",
                "log.webp", "post.webp", "broken.webp") + tuple(t + ".webp" for t in pp.TARGETS):
        assert os.path.exists(os.path.join(ROOT, "art", "practice", pic)), pic


def test_her_unarmed_movements_are_there_and_his_fall_back():
    her = pp.hero_sheets("female")
    assert her and set(her["sheets"]) == {"stance", "strike", "block", "struck"}
    for name, sp in her["sheets"].items():
        assert os.path.exists(os.path.join(ROOT, sp["src"].lstrip("/"))) and sp["frames"] <= sp["cols"] * sp["rows"]
        if name != "stance":
            assert os.path.exists(os.path.join(ROOT, sp["sound"]["src"].lstrip("/")))
        assert all(0 <= k < sp["frames"] for k in sp.get("keys", {}).values())
    assert her["sheets"]["stance"]["loop"] and her["sheets"]["strike"]["hand"]
    if not os.path.exists(os.path.join(ROOT, "art", "practice", "hero", "male", "sheets.json")):
        assert pp.hero_sheets("male") is None                    # no unarmed art yet: the sword fighter stands in


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
    c.close()
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=path, session_secret="test")
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "token")
    monkeypatch.setattr(oauth, "fetch_user", lambda token: {"id": UID, "username": "shoaib", "avatar": None})
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
    cl.get("/callback", params={"code": "good", "state": q["state"][0]})
    cl.db_path = path
    return cl


def test_a_drill_through_the_routes(client):
    r = client.get("/training")
    assert r.status_code == 200 and "Practice with Senior Sister Xue" in r.text and 'action="/practice/start"' in r.text
    assert client.get("/practice").headers["location"] == "/training#practice"          # no drill yet
    c = db.connect(client.db_path)
    tid = {t["name"]: t["id"] for t in db.get_techniques(c, UID)}["Iron Fist"]
    assert client.post("/practice/start", data={"technique": tid}).headers["location"] == "/practice"
    assert client.get("/training").headers["location"] == "/practice"                    # a drill under way
    page = client.get("/practice")
    assert page.status_code == 200 and "practice.js" in page.text and "Senior Sister Xue" in page.text
    assert 'id="pleave"' in page.text and 'href="/profile"' not in page.text         # no tabs: only Leave
    assert 'id="pkeyrow"' in page.text and 'id="pguides"' in page.text              # Settings: your keys, guides
    s = client.get("/practice/state").json()
    assert s["drill"]["mode"] == "strike" and s["prompts"] and not s["begun"]
    assert client.post("/practice/submit", json={"inputs": []}).json()["error"] == "The drill hasn't begun."
    assert client.post("/practice/go").json() == {"ok": True}
    assert client.post("/practice/submit", json={"inputs": []}).json()["error"] == "The drill isn't over yet."
    hall = client.app.state.practice
    hall.drills[UID].go_at -= hall.drills[UID].length / 1000 + 1                      # as if it had run its length
    out = client.post("/practice/submit", json={"inputs": perfect(s["prompts"])}).json()
    assert out["error"] is None and out["result"]["score"] == 1.0 and out["result"]["gained"] > 0
    assert client.get("/practice/state").json()["result"]["score"] == 1.0                # a reload shows the result
    assert client.post("/practice/done").headers["location"] == "/training#practice"
    r = client.get("/training")
    assert "She is resting your hands" in r.text
    c.close()


def test_a_spar_and_a_drill_never_run_together(client):
    c = db.connect(client.db_path)
    tid = {t["name"]: t["id"] for t in db.get_techniques(c, UID)}["Iron Fist"]
    c.close()
    assert client.post("/practice/start", data={"technique": tid}).headers["location"] == "/practice"
    assert client.post("/training/spar").headers["location"] == "/training"
    assert not client.app.state.hall.busy(UID)
    assert client.post("/practice/yield").headers["location"] == "/training#practice"
    assert client.get("/practice").headers["location"] == "/training#practice"


def test_the_practice_pages_need_a_login(tmp_path):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=str(tmp_path / "x.db"), session_secret="t")
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert cl.get("/practice").headers["location"] == "/"
    assert cl.get("/practice/state").json() == {"gone": True}
    assert cl.post("/practice/submit", json={"inputs": []}).json() == {"gone": True}
    assert cl.post("/practice/start", data={"technique": 1}).headers["location"] == "/"
