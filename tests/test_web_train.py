"""Train on the website: Meridian Circulation (web/train_play.py, web/train_sim.py, docs/training.md "Train on the website")."""
import heapq
import json
import os
import random
import shutil
import subprocess
import urllib.parse

import pytest

import challenges
import training
from bot import db, trainer
from bot import player as rules
from web import train_play as tp
from web import train_sim as sim

A = 111
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JS = os.path.join(ROOT, "web", "static", "train_sim.js")


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


class Quiet(random.Random):
    """No event, no condition (every roll misses)."""
    def random(self):
        return 0.99

    def randint(self, a, b):
        return a


@pytest.fixture
def setup(tmp_path):
    conn = db.connect(str(tmp_path / "ma.db"))
    db.create_player(conn, A, "Lin Feng", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    clock = Clock()
    return conn, clock, tp.Chamber(clock=clock, rng=Quiet(7))


def plans(n=24):
    r = random.Random(1)
    out = []
    for seed in range(n):
        conds = r.sample(tp.CONDITIONS, r.randint(0, 2))
        out.append(tp.make_plan(1 + seed % 2, conds, r.choice([None, "rival_disciple", "epiphany"]),
                                random.Random(seed)))
    return out


# ── a careful player: turns each junction for the pulse about to reach it ─────────────────────────────────────────

def _way(nodes, lens, start, goal):
    best, q = {start: 0}, [(0, start)]
    while q:
        d, n = heapq.heappop(q)
        if nodes[n]["type"] == goal:
            return d
        if nodes[n]["type"] in ("knot", "exit", "dantian"):
            continue
        for o in nodes[n]["out"]:
            nd = d + lens[sim.edge(n, o)]
            if nd < best.get(o, 1e18):
                best[o] = nd
                heapq.heappush(q, (nd, o))
    return 1e18


def careful(plan, boon=0, wait=0):
    """`boon`: which of the two blessings to take (0 or 1), `wait` ticks after it is offered."""
    st, acts = sim.start(plan), []
    while not st["over"]:
        k = st["tick"]
        if st["choosing"] is not None and k < st["choose_until"] - plan["choose"] + wait:
            sim.step(plan, st)
            continue
        if st["choosing"] is not None:
            a = [k * sim.TICK, "o", plan["boons"][st["choosing"]][boon]]
            acts.append(a)
            sim.step(plan, st, [a])
            continue
        nxt = st["pause_until"] is not None and k >= st["pause_until"]
        c = plan["cycles"][st["cycle"] + (1 if nxt else 0)]
        want = {}
        for p in st["pulses"]:
            if p["done"] is not None or p["wait"] is not None or p["edge"] not in c["lens"]:
                continue
            b = p["edge"].split(">")[1]
            left = c["lens"][p["edge"]] - p["pos"]
            if c["nodes"][b]["type"] != "junction" or (b in want and want[b][0] <= left):
                continue
            goal = "exit" if p["dark"] else "dantian"
            d = [_way(c["nodes"], c["lens"], o, goal) for o in c["nodes"][b]["out"]]
            want[b] = (left, 0 if d[0] <= d[1] else 1)
        mine = [[k * sim.TICK, "j", j] for j, (_, way) in want.items() if st["junctions"].get(j, way) != way]
        acts += mine
        sim.step(plan, st, mine)
    return st, acts


# ── the map ──────────────────────────────────────────────────────────────────────────────────────────────────────

def test_every_network_can_be_played_well():
    """The paths are already drawn and correct: from every source, gold can reach the Dantian and dark an exit."""
    for plan in plans(40):
        assert len([c for c in plan["cycles"] if c["kind"] == "cycle"]) == tp.CYCLES
        for c in plan["cycles"]:
            nodes = c["nodes"]
            for n, node in nodes.items():
                assert all(o in nodes for o in node["out"]) and ">" not in n
                assert len(node["out"]) == (2 if node["type"] == "junction" else 0 if node["type"] in
                                            ("dantian", "exit") else 1)
            for src in (n for n in nodes if nodes[n]["type"] == "source"):
                assert tp.reaches(nodes, src, {"dantian"}) and tp.reaches(nodes, src, {"exit"})


def test_the_tiers_follow_the_design():
    for seed in range(20):
        one = tp.make_plan(1, [], None, random.Random(seed))
        two = tp.make_plan(2, [], None, random.Random(seed))
        for plan, sources, junctions, gates, pulses in ((one, 1, {2}, 1, 10), (two, 2, {3, 4}, 2, 12)):
            for c in plan["cycles"]:
                kinds = [n["type"] for n in c["nodes"].values()]
                assert kinds.count("source") == sources and kinds.count("gate") == gates
                assert kinds.count("junction") in junctions and len(c["pulses"]) == pulses
                g = [(n["x"], n["y"]) for n in c["nodes"].values() if n["type"] == "gate"]
                assert all(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5 >= tp.GATE_APART - 1
                           for i, a in enumerate(g) for b in g[i + 1:])             # never on top of each other
        assert not any(q["dark"] for q in one["cycles"][0]["pulses"])        # tier 1: no dark Qi in the first cycle
        assert any(q["dark"] for c in one["cycles"][1:] for q in c["pulses"])
        assert not any(n["type"] == "knot" for n in two["cycles"][0]["nodes"].values())   # the first cycle is calm
        assert all(any(n["type"] == "knot" for n in c["nodes"].values()) for c in two["cycles"][1:])
        assert tp.make_plan(4, [], None, random.Random(seed))["tier"] == 2      # PROTOTYPE: tiers 3-5 play tier 2


def test_a_session_lasts_about_two_minutes_and_rival_adds_a_round():
    for seed in range(10):
        for tier in (1, 2):
            plan = tp.make_plan(tier, [], None, random.Random(seed))
            st, _ = careful(plan)
            seconds = (tp.SETTLE + (st["end_tick"] + 1) * sim.TICK) / 1000
            assert 75 <= seconds <= 125, seconds
            rival = tp.make_plan(tier, [], "rival_disciple", random.Random(seed))
            assert [c["kind"] for c in rival["cycles"]] == ["cycle"] * 3 + ["rival"]
            assert all(q["dark"] for q in rival["cycles"][3]["pulses"]) and len(rival["cycles"][3]["pulses"]) == 6


# ── the rules ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_careful_play_scores_full_and_doing_nothing_does_not():
    for plan in plans():
        st, acts = careful(plan)
        assert sim.score(plan, st)[0] >= 0.95 and not st["deviation"]
        assert sim.run(plan, acts)["gold_in"] == st["gold_in"]                    # the replay gives the same
        idle = sim.score(plan, sim.run(plan, []))[0]
        assert idle < 0.7


def test_the_score_weights():
    plan = tp.make_plan(2, [], None, random.Random(3))
    gold, dark = sim.totals(plan)
    st = sim.new_state(plan)
    st.update(gold_in=gold, dark_out=dark, stability=100)
    assert sim.score(plan, st)[0] == 1.0
    st.update(gold_in=0, dark_out=dark, stability=100)
    assert sim.score(plan, st)[0] == pytest.approx(0.40)
    st.update(gold_in=gold, dark_out=0, stability=0)
    assert sim.score(plan, st)[0] == pytest.approx(0.60)
    st.update(gold_in=gold, dark_out=dark, stability=100, deviation=True)
    assert sim.score(plan, st)[0] == pytest.approx(0.85)
    # the doc's worked example: 25 of 30 gold, 8 of 10 dark, Stability 70 -> 80.5%
    ex = {"cycles": [{"kind": "cycle", "pulses": [{"dark": False}] * 30 + [{"dark": True}] * 10}]}
    st.update(gold_in=25, dark_out=8, stability=70, deviation=False)
    assert sim.score(ex, st)[0] == pytest.approx(0.805)
    no_dark = {"cycles": [{"kind": "cycle", "pulses": [{"dark": False}] * 10}]}   # no dark Qi: 85% gold
    st.update(gold_in=10, dark_out=0, stability=0)
    assert sim.score(no_dark, st)[0] == pytest.approx(0.85)


def test_stability_and_qi_deviation():
    plan = tp.make_plan(2, [], None, random.Random(5))
    st = sim.run(plan, [])
    gone = st["lost"] + st["dark_in"]
    assert st["deviation"] and st["stability"] == 0 and gone > 0
    assert st["gold"] + st["dark"] < sum(sim.totals(plan))                         # it ends early: pulses never sent


def _junction_before(plan, gate):
    c = plan["cycles"][0]
    return next(n for n in c["nodes"] if gate in c["nodes"][n]["out"])


def test_gates_hold_qi_and_burst():
    plan = tp.make_plan(1, [], None, random.Random(2))
    gate = next(n for n, v in plan["cycles"][0]["nodes"].items() if v["type"] == "gate")
    st = sim.run(plan, [[0, "g", gate]])                                     # closed from the start, never opened
    assert st["bursts"] >= 1
    # held a little, then opened: no burst, and the held Qi goes on
    st = sim.start(plan)
    sim.step(plan, st, [[0, "g", gate]])
    held = False
    while not held:
        sim.step(plan, st)
        held = any(p["wait"] == gate for p in st["pulses"])
    sim.step(plan, st, [[st["tick"] * sim.TICK, "g", gate]])
    assert st["bursts"] == 0 and not any(p["wait"] for p in st["pulses"])


def test_breath_slows_qi_and_runs_out():
    plan = tp.make_plan(1, [], None, random.Random(4))
    calm, held = sim.start(plan), sim.start(plan)
    for _ in range(10):
        sim.step(plan, calm)
    sim.step(plan, held, [[0, "b", ""]])
    for _ in range(9):
        sim.step(plan, held)
    assert held["pulses"][0]["pos"] * 5 // 2 <= calm["pulses"][0]["pos"]       # 40% speed
    assert held["breath"] < plan["breath"]["max"]
    for _ in range(200):
        sim.step(plan, held)
    assert not held["breathing"]                                             # it runs out on its own
    hurt = tp.make_plan(1, ["old_injury"], None, random.Random(4))
    assert hurt["breath"]["drain"] == 2 * plan["breath"]["drain"] and hurt["injured"]


def test_the_conditions():
    rain = tp.make_plan(1, ["heavy_rain"], None, random.Random(1))
    assert rain["speed"] == tp.SPEED * 5 // 4
    drunk = tp.make_plan(2, ["drunken_master"], None, random.Random(1))
    truth = {str(q["id"]): q["dark"] for c in drunk["cycles"] for q in c["pulses"]}
    lies = sum(drunk["shown"][k] != v for k, v in truth.items())
    assert 0 < lies < len(truth) / 2
    plain = tp.make_plan(2, [], None, random.Random(1))
    assert all(plain["shown"][str(q["id"])] == q["dark"] for c in plain["cycles"] for q in c["pulses"])


def test_the_rival_round_counts_apart():
    plan = tp.make_plan(1, [], "rival_disciple", random.Random(8))
    st, acts = careful(plan)
    assert st["rival_out"] == tp.RIVAL_PULSES and st["rival_dark"] == tp.RIVAL_PULSES
    gold, dark = sim.totals(plan)
    assert st["dark"] == dark and st["gold"] == gold                         # the rival's pulses aren't in the score


# ── Harmony and the blessings ────────────────────────────────────────────────────────────────────────────────────

def test_harmony_builds_and_resonance_fills_the_breath():
    plan = tp.make_plan(1, [], None, random.Random(6))
    st, acts = careful(plan)
    clean = st["gold_in"] + st["dark_out"]
    assert st["best_harmony"] == clean and st["resonances"] == clean // tp.HARMONY   # never broken
    # breathe the bar empty, then let ten clean pulses in a row fill it at once
    st = sim.start(plan)
    seen = []
    for a in sorted(acts):
        while st["tick"] < a[0] // sim.TICK:
            sim.step(plan, st)
            seen += [e for e in st["events"] if e[1] == "resonance"]
        sim.step(plan, st, [a])
    assert seen and seen[0][2] == tp.HARMONY
    idle = sim.run(plan, [])
    assert idle["best_harmony"] < tp.HARMONY and idle["resonances"] == 0          # junctions the wrong way: broken
    assert sim.score(plan, st)[0] == sim.score(plan, dict(st, best_harmony=0, resonances=0))[0]   # it never scores


def test_open_a_meridian_between_cycles():
    for seed in range(12):
        plan = tp.make_plan(1 + seed % 2, [], None, random.Random(seed))
        assert len(plan["boons"]) == 2 and all(len(set(b)) == 2 and set(b) <= set(sim.BOONS) for b in plan["boons"])
        st, acts = careful(plan, seed % 2)
        assert st["boons"] == [plan["boons"][0][seed % 2], plan["boons"][1][seed % 2]]
        assert sum(1 for a in acts if a[1] == "o") == 2
        # no choice made: exactly 10 s after the cycle ends, the first is taken
        rest = sorted(a for a in acts if a[1] != "o")             # the same play, the choice left to the clock
        st, done, took, i = sim.start(plan), None, None, 0
        while not st["over"] and took is None:
            mine = []
            while i < len(rest) and rest[i][0] // sim.TICK <= st["tick"]:
                mine.append(rest[i])
                i += 1
            sim.step(plan, st, mine)
            for e in st["events"]:
                if e[1] == "cycle_done" and done is None:
                    done = e[0]
                if e[1] == "boon":
                    took = (e[0], e[2])
        assert took == (done + 1 + tp.CHOOSE, plan["boons"][0][0])
        # a blessing that isn't offered, or sent when nothing is being chosen, does nothing
        wrong = [b for b in sim.BOONS if b not in plan["boons"][0]][0]
        assert sim.run(plan, [[0, "o", plan["boons"][0][0]]] + [a for a in acts if a[1] != "o"])["boons"][0] == \
            plan["boons"][0][0]
        st = sim.start(plan)
        sim.step(plan, st, [[0, "o", wrong]])
        assert st["boons"] == []


def test_what_each_blessing_does():
    plan = tp.make_plan(1, [], None, random.Random(2))
    def blessed(boon):
        st = sim.start(plan)
        st.update(stability=60, choosing=0, choose_until=999)
        plan["boons"][0] = [boon, [b for b in sim.BOONS if b != boon][0]]
        sim.step(plan, st, [[0, "o", boon]])
        return st
    st = blessed("breath")
    assert st["breath_max"] == plan["breath"]["max"] * 3 // 2 == st["breath"]
    assert blessed("mend")["stability"] == 85
    st = blessed("seal")
    assert (st["gate_most"], st["gate_hold"]) == (5, 6000 // sim.TICK)
    st = blessed("steady")
    assert st["slow"] and st["pause_until"] is not None
    st["pause_until"], st["cycle"] = None, 0
    sim._enter_cycle(plan, st, st["tick"])
    p = {"edge": "x>y"}
    assert sim._speed(plan, st, p) == plan["speed"] * 17 // 20


# ── the page's copy of the rules ─────────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not shutil.which("node"), reason="node is not installed")
def test_the_page_and_the_server_agree(tmp_path):
    r = random.Random(2)
    cases = []
    for plan in plans(30):
        ids = sorted({n for c in plan["cycles"] for n, v in c["nodes"].items() if v["type"] in ("junction", "gate")})
        acts, t = [], 0
        for _ in range(r.randint(0, 250)):
            t += r.randint(0, 900)
            w = r.choice("jjjgbBo")
            acts.append([t, w, r.choice(ids) if w in "jg" else r.choice(sim.BOONS) if w == "o" else ""])
        cases += [{"plan": plan, "actions": acts}, {"plan": plan, "actions": careful(plan)[1]},
                  {"plan": plan, "actions": careful(plan, 1)[1]}]
    keys = ["gold", "gold_in", "dark", "dark_out", "dark_in", "lost", "bursts", "stability", "deviation", "end_tick",
            "rival_out", "breath", "tick", "harmony", "best_harmony", "resonances", "boons", "breath_max", "slow",
            "gate_most", "gate_hold"]
    script = tmp_path / "run.js"
    script.write_text("const sim = require(%s); let d = ''; process.stdin.on('data', x => d += x).on('end', () => "
                      "process.stdout.write(JSON.stringify(JSON.parse(d).map(c => { const st = sim.run(c.plan, c.actions);"
                      " return %s.map(k => st[k]); }))));" % (json.dumps(JS), json.dumps(keys)))
    out = subprocess.run(["node", str(script)], input=json.dumps(cases), capture_output=True, text=True, check=True)
    for case, theirs in zip(cases, json.loads(out.stdout)):
        st = sim.run(case["plan"], case["actions"])
        assert [st[k] for k in keys] == theirs


# ── the chamber: the rest, the pay, the referee ──────────────────────────────────────────────────────────────────

def run_session(chamber, clock, conn, actions=None):
    assert chamber.go(A) is None
    s = chamber.sessions[A]
    acts = careful(s.plan)[1] if actions is None else actions
    st = sim.run(s.plan, acts)
    clock.t += (tp.SETTLE + (st["end_tick"] + 1) * sim.TICK) / 1000 + 0.5
    return chamber.submit(conn, A, acts)


def test_a_session_starts_the_rest_and_pays_what_the_bot_pays(setup):
    conn, clock, chamber = setup
    assert chamber.start(conn, A) is None
    assert db.cooldown_left(conn, A, "train", clock.t) == pytest.approx(training.TRAIN_COOLDOWN_MINUTES * 60)
    assert chamber.start(conn, A) == "You are already meditating."
    p0 = db.get_player(conn, A)
    techs = db.get_techniques(conn, A)
    result, why = run_session(chamber, clock, conn)
    assert why is None and result["score"] >= 0.95
    expect = trainer.qi_reward(p0, techs, result["score"], [], 1.0, clock.t)
    assert result["gained"] == pytest.approx(expect, abs=0.1)
    assert db.get_player(conn, A)["last_challenge"] == p0.get("last_challenge")     # the bot's memory is left alone
    assert db.cooldown_left(conn, A, "train", clock.t) > 0
    chamber.done(A)
    assert "rest" in chamber.start(conn, A)                                           # the 60-minute rest holds


def test_walking_away_pays_nothing_and_the_rest_stays(setup):
    conn, clock, chamber = setup
    qi = db.get_player(conn, A)["qi"]
    assert chamber.start(conn, A) is None
    chamber.give_up(A)
    assert db.get_player(conn, A)["qi"] == qi and db.cooldown_left(conn, A, "train", clock.t) > 0
    assert not chamber.busy(A)


def test_a_low_score_pays_a_tenth(setup):
    conn, clock, chamber = setup
    assert chamber.start(conn, A) is None
    p0, techs = db.get_player(conn, A), db.get_techniques(conn, A)
    result, _ = run_session(chamber, clock, conn, actions=[])
    assert result["score"] < challenges.LOW_SCORE_THRESHOLD
    assert result["gained"] == pytest.approx(trainer.qi_reward(p0, techs, result["score"], [], 1.0, clock.t), abs=0.1)
    assert any("10%" in n for n in result["notes"])


def test_the_server_keeps_the_time_and_checks_the_actions(setup):
    conn, clock, chamber = setup
    assert chamber.start(conn, A) is None
    assert chamber.submit(conn, A, [])[1] == "The meditation hasn't begun."
    assert chamber.go(A) is None
    acts = careful(chamber.sessions[A].plan)[1]
    clock.t += 20
    assert chamber.submit(conn, A, acts)[1] == "The meditation isn't over yet."
    assert chamber.submit(conn, A, [[5, "j", "nowhere"]])[1] == "Those actions can't be right."
    assert chamber.submit(conn, A, [[500, "b", ""], [100, "B", ""]])[1] == "Those actions can't be right."   # out of order
    assert chamber.submit(conn, A, [[0, "b", ""]] * 2000)[1] == "Those actions can't be right."
    assert chamber.submit(conn, A, "nonsense")[1] == "Those actions can't be right."
    clock.t += 200
    result, why = chamber.submit(conn, A, acts)
    assert why is None and result["score"] >= 0.95
    assert chamber.submit(conn, A, [])[0] is result                               # sent twice: the same result


def test_a_session_left_unbegun_or_unsent_is_dropped(setup):
    conn, clock, chamber = setup
    assert chamber.start(conn, A) is None
    clock.t += tp.Chamber.READY_SECONDS + 1
    assert chamber.state(A) is None and not chamber.busy(A)


def test_the_events_pay_like_the_bot(setup):
    conn, clock, chamber = setup
    for event, mult in (("epiphany", 1.5), ("wandering_hermit", 5.0), ("rival_disciple", 2.0)):
        db.clear_cooldown(conn, A, "train")
        assert chamber.start(conn, A) is None
        s = chamber.sessions[A]
        s.event = event
        s.conditions = ["heavy_rain", "night_training"] if event == "wandering_hermit" else []
        s.plan = tp.make_plan(5 if event == "wandering_hermit" else 1, s.conditions, event, random.Random(1))
        p0, techs = db.get_player(conn, A), db.get_techniques(conn, A)
        result, _ = run_session(chamber, clock, conn)
        expect = trainer.qi_reward(p0, techs, result["score"], s.conditions, mult, clock.t)
        assert result["gained"] == pytest.approx(expect, abs=0.1), event
        if event == "rival_disciple":
            assert result["rival"] is True
        chamber.done(A)


def test_the_yard_card(setup):
    conn, clock, chamber = setup
    card = chamber.hall(conn, A)
    assert card["wait"] is None and card["tier"] == 1 and not card["prototype"] and not card["busy"]
    chamber.start(conn, A)
    card = chamber.hall(conn, A)
    assert card["busy"] and card["wait"]


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


def test_a_session_through_the_routes(client):
    r = client.get("/training")                                                   # Train left the Master's yard
    assert r.status_code == 200 and 'action="/train/start"' not in r.text
    assert client.get("/train").headers["location"] == "/town?near=keeper"
    assert client.post("/train/start").headers["location"] == "/train"
    assert client.get("/training").headers["location"] == "/train"                 # a session under way
    page = client.get("/train")
    assert page.status_code == 200 and "train.js" in page.text and "train_sim.js" in page.text
    assert 'id="tleave"' in page.text and 'href="/profile"' not in page.text       # no tabs: only Leave
    s = client.get("/train/state").json()
    assert s["plan"]["cycles"] and not s["begun"]
    assert client.post("/train/go").json() == {"ok": True}
    chamber = client.app.state.train
    chamber.sessions[UID].go_at -= tp.MAX_SECONDS
    out = client.post("/train/submit", json={"actions": careful(s["plan"])[1]}).json()
    assert out["error"] is None and out["result"]["score"] >= 0.95 and out["result"]["gained"] > 0
    assert client.get("/train/state").json()["result"]["score"] == out["result"]["score"]
    assert client.post("/train/done").headers["location"] == "/town?near=keeper"
    assert client.post("/train/start").headers["location"] == "/town?near=keeper"     # resting: back to Sister Jing


def test_one_thing_at_a_time(client):
    assert client.post("/train/start").headers["location"] == "/train"
    assert client.post("/training/spar").headers["location"] == "/training"
    assert not client.app.state.hall.busy(UID)
    c = db.connect(client.db_path)
    tid = db.get_techniques(c, UID)[0]["id"]
    c.close()
    assert client.post("/practice/start", data={"technique": tid}).headers["location"] == "/practice"
    assert client.post("/train/yield").headers["location"] == "/town?near=keeper"
    assert client.get("/train").headers["location"] == "/town?near=keeper"


def test_sister_jing_seats_you(client):
    from web import town
    jing = next(n for n in town.NPCS if n["key"] == "keeper")
    assert town.walkable(jing["x"], jing["y"]) and jing["go"][0][1] == "/town/visit/keeper"
    assert os.path.exists(os.path.join(ROOT, jing["src"].lstrip("/")))
    assert client.get("/town/visit/keeper").headers["location"] == "/train"
    assert client.app.state.train.busy(UID) and "Back to Sister Jing" in client.get("/train").text
    assert client.get("/town/visit/keeper").headers["location"] == "/train"       # already seated
    assert client.post("/train/yield").headers["location"] == "/town?near=keeper"  # back to her, not the yard
    assert client.get("/town/visit/keeper").headers["location"] == "/town?near=keeper"   # resting now
    assert "rest" in client.get("/town?near=keeper").text


def test_the_art_is_there_and_fits():
    """What scripts/make_train_art.py cut: the chamber, the effects, and each character's loop, endings and fit."""
    scene = tp.scene_art()
    for key in ("picture", "video", "sound"):
        assert scene[key] and os.path.exists(os.path.join(ROOT, scene[key].lstrip("/")))
    assert tp.scene_art("wandering_hermit")["picture"].endswith("hermit.jpg")
    assert tp.scene_art("wandering_hermit")["video"] is None
    assert all(tp.fx_art().values())
    rival = tp.rival_art()                                                 # his picture, and his attack with its sound
    assert rival["picture"] and rival["attack"]["ms"] > 5000
    for key in ("src", "sound"):
        assert os.path.exists(os.path.join(ROOT, rival["attack"][key].lstrip("/")))
    bx, by, bw, bh = rival["attack"]["body"]
    assert 0 < bw < 1920 and 0 < bh <= 1080                                # his body, not the whole frame
    for gender in ("female", "male"):
        art = tp.hero_art(gender)
        loop = art["loop"]
        assert loop["frames"] <= loop["cols"] * loop["rows"] and os.path.exists(os.path.join(ROOT, loop["src"].lstrip("/")))
        assert set(art["ends"]) == {"surge", "deviation", "scatter"}
        for end in art["ends"].values():
            assert os.path.exists(os.path.join(ROOT, end["src"].lstrip("/")))
            assert os.path.exists(os.path.join(ROOT, end["sound"].lstrip("/")))
        pts = art["fit"]["points"]
        assert set(pts) == set(tp.BODY)                                   # every acupoint of the map is on the body
        assert pts["crown"][1] < pts["throat"][1] < pts["heart"][1] < pts["dantian"][1]
        assert pts["l_palm"][0] < 50 < pts["r_palm"][0] and abs(pts["dantian"][0] - 50) < 1
        for name, (x, y) in pts.items():                                  # the map is only nudged onto the body
            assert abs(x - tp.BODY[name][0]) < 12 and abs(y - tp.BODY[name][1]) < 13, name


def test_the_guide_explains_everything_with_the_games_own_numbers(client):
    g = tp.guide(2)
    assert [t["n"] for t in g["tiers"]] == [1, 2, 3, 4, 5] and [t["built"] for t in g["tiers"]] == [True, True, False, False, False]
    assert [t["conds"] for t in g["tiers"]] == ["none", "0-1", "1", "1-2", "2"]          # the bot's own table
    assert {e["name"] for e in g["events"]} == {"Wandering Hermit", "Epiphany", "Rival Disciple"}
    assert [e["chance"] for e in g["events"]] == [round(challenges.EVENTS[k]["chance"] * 100)
                                                  for k in ("wandering_hermit", "epiphany", "rival_disciple")]
    assert len(g["conditions"]) == 4 and len(g["boons"]) == 4 and g["harmony"] == tp.HARMONY
    assert g["gate"] == {"most": 3, "hold": 4} and g["breath"] == {"secs": 4.0, "refill": 5.0}
    assert g["hours"] == training.TRAIN_REWARD_HOURS and g["rest"] == training.TRAIN_COOLDOWN_MINUTES
    assert client.get("/town/visit/keeper").headers["location"] == "/train"
    page = client.get("/train").text
    assert 'id="tguide"' in page and 'id="tguidebtn"' in page and 'id="tqbtn"' in page
    for part in ("The goal", "Controls", "Reading the map", "Score and Stability", "Harmony and blessings",
                 "How it ends", "Tiers", "Conditions", "Events", "Reward and rest", "Tips",
                 "Wandering Hermit", "Epiphany", "Rival Disciple", "Heavy Rain", "Night Training", "Drunken Master",
                 "Old Injury", "Deep Breath", "Strong Seals", "Qi deviation", "Tier 1 (yours)"):
        assert part in page, part


def test_the_train_pages_need_a_login(tmp_path):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=str(tmp_path / "x.db"), session_secret="t")
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert cl.get("/train").headers["location"] == "/"
    assert cl.get("/train/state").json() == {"gone": True}
    assert cl.post("/train/submit", json={"actions": []}).json() == {"gone": True}
    assert cl.post("/train/start").headers["location"] == "/"
