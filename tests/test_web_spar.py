"""Sparring with the Martial Master on the website (web/spar_play.py, docs/technique.md "On the website")."""
import json
import random
import urllib.parse

import pytest

import challenges
import technique
from bot import db, sparring
from bot import player as rules
from web import spar_play, town

A = 111


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def setup(tmp_path):
    conn = db.connect(str(tmp_path / "ma.db"))
    db.create_player(conn, A, "Lin Feng", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    clock = Clock()
    return conn, clock, spar_play.Hall(clock=clock, rng=random.Random(7))


def counter(move):
    return challenges.COUNTERS[move]


def techs(conn):
    return {t["name"]: t for t in db.get_techniques(conn, A)}


def fill_bar(conn, name="Iron Fist"):
    t = techs(conn)[name]
    db.add_mastery(conn, t["id"], rules.mastery_cap(t) - t["mastery_exp"])
    return t["id"]


def play_out(conn, hall, choose):
    """Play a spar to its end; `choose(session)` picks each move. Returns the final state."""
    while True:
        s = hall.spars[A]
        if s.over:
            return hall.state(conn, A)
        assert hall.pick(conn, A, choose(s), s.spar.turn) is None


def test_the_yard_shows_your_techniques_and_the_spar(setup):
    conn, clock, hall = setup
    v = hall.hall(conn, A)
    assert [t["name"] for t in v["techniques"]] == ["Iron Fist", "Horse Stance Guard"]
    assert v["techniques"][0]["pct"] == 0 and not v["techniques"][0]["full"]
    assert v["wait"] is None and v["hurt"] is None and not v["in_spar"]
    assert v["full_left"] == technique.SPAR_DAILY_RATES[0][0] and v["rate"] == 1.0
    assert v["per_use"] == technique.SPAR_EXP_PER_TIMED_USE and v["win"] == technique.SPAR_WIN_EXP


def test_starting_a_spar_starts_the_rest_as_on_discord(setup):
    conn, clock, hall = setup
    assert hall.start(conn, A) is None
    assert hall.busy(A) and hall.hall(conn, A)["in_spar"]
    assert db.cooldown_left(conn, A, "spar", clock()) == technique.SPAR_COOLDOWN_MINUTES * 60
    assert hall.start(conn, A) == "You are already sparring."
    s = hall.state(conn, A)
    assert s["turn"] == 1 and s["max_turns"] == sparring.MAX_TURNS and not s["over"]
    assert s["master"]["hp"] == s["master"]["max_hp"] and s["me"]["hp"] == s["me"]["max_hp"]
    assert [m["key"] for m in s["me"]["moves"]] == ["strike", "guard", "break", "attack_tech", "defense_tech"]


def test_the_master_is_your_own_realm_and_layer(setup):
    conn, clock, hall = setup
    hall.start(conn, A)
    p = db.get_player(conn, A)
    assert hall.state(conn, A)["master"]["max_hp"] == round(rules.base_stats(p["realm"], p["layer"])[0])


def test_the_page_is_never_told_his_move_for_this_exchange(setup):
    conn, clock, hall = setup
    hall.start(conn, A)
    sp = hall.spars[A].spar
    for _ in range(4):
        s = hall.state(conn, A)
        shown = json.dumps({k: v for k, v in s.items() if k not in ("last", "beads", "history")})
        assert '"pattern"' not in shown and "master_move" not in shown
        assert set(s["master"]) == {"name", "img", "hp", "max_hp", "tag", "staggered"}       # nothing about his choice
        assert len(s["beads"]) == sp.turn - 1                                               # only exchanges already over
        assert s["has_tell"] == bool(sp.tell)
        hall.pick(conn, A, "guard", sp.turn)


def test_an_exchange_is_the_bots_own(setup):
    """The same seed and the same moves give the same fight as bot/sparring.Spar played directly."""
    conn, clock, hall = setup
    hall.start(conn, A)
    p = db.get_player(conn, A)
    twin = sparring.Spar(p, db.get_techniques(conn, A), db.equipped_weapon(conn, A), 1.0, random.Random(7),
                         armor=db.equipped_armor(conn, A))
    for move in ("guard", "attack_tech", "strike", "break", "defense_tech"):
        his = twin.master
        twin.play(move)
        assert hall.pick(conn, A, move, hall.spars[A].spar.turn) is None
        s = hall.state(conn, A)
        assert s["last"]["master"]["move"] == his
        assert (s["me"]["hp"], s["master"]["hp"]) == (round(twin.hp), round(twin.m_hp))
        assert s["timed"] == sum(twin.timed.values())


def test_outcome_word_and_opening(setup):
    conn, clock, hall = setup
    hall.start(conn, A)
    sp = hall.spars[A].spar
    sp.master = "strike"
    hall.pick(conn, A, "guard", sp.turn)
    s = hall.state(conn, A)
    assert s["last"]["outcome"] == "win" and s["last"]["word"] == "Opening!" and s["opening"]
    assert s["beads"][0] == {"turn": 1, "his": "strike", "outcome": "win", "timed": False}
    sp.master = "guard"
    hall.pick(conn, A, "attack_tech", sp.turn)                  # right after the blocked Strike: perfect timing
    s = hall.state(conn, A)
    assert s["last"]["timed"] and s["timed"] == 1 and not s["opening"]
    assert s["last"]["outcome"] == "lose" and s["last"]["word"] == "Blocked!"
    assert s["last"]["me"]["fx"]["motion"] == "fist"            # Iron Fist plays the punch
    tech = [m for m in s["me"]["moves"] if m["key"] == "attack_tech"][0]
    assert not tech["ready"] and "Ready in" in tech["state"]
    assert hall.pick(conn, A, "attack_tech", sp.turn).startswith("That technique is still recovering")
    assert hall.pick(conn, A, "meteor", sp.turn) == "That isn't one of your moves."


def test_a_late_press_for_an_old_exchange_does_nothing(setup):
    conn, clock, hall = setup
    hall.start(conn, A)
    hall.pick(conn, A, "guard", 1)
    assert hall.pick(conn, A, "strike", 1) is None and hall.spars[A].spar.turn == 2


def test_no_pick_is_a_guard_and_three_in_a_row_forfeit(setup):
    conn, clock, hall = setup
    hall.start(conn, A)
    clock.t += spar_play.TURN_SECONDS + 1
    s = hall.state(conn, A)
    assert s["last"]["me"]["move"] == "guard" and s["last"]["timed_out"] and s["turn"] == 2
    hall.pick(conn, A, "strike", 2)                              # a real pick clears the count
    clock.t += spar_play.TURN_SECONDS * 2 + 1
    assert not hall.state(conn, A)["over"] and hall.spars[A].timeouts == 2
    clock.t += spar_play.TURN_SECONDS
    s = hall.state(conn, A)
    assert s["over"] and s["result"]["outcome"] == "forfeit" and s["result"]["gains"] == []
    assert techs(conn)["Iron Fist"]["mastery_exp"] == 0


def test_yield_earns_nothing_and_counts_as_a_spar(setup):
    conn, clock, hall = setup
    hall.start(conn, A)
    sp = hall.spars[A].spar
    sp.master = "strike"
    hall.pick(conn, A, "defense_tech", 1)                        # well timed, but then you walk away
    hall.give_up(conn, A)
    s = hall.state(conn, A)
    assert s["over"] and s["result"]["outcome"] == "forfeit" and s["result"]["gains"] == []
    assert techs(conn)["Horse Stance Guard"]["mastery_exp"] == 0
    assert db.daily_count(conn, A, "spar", clock()) == 1


def test_a_win_pays_the_bots_mastery_exp(setup):
    conn, clock, hall = setup
    hall.start(conn, A)

    def choose(s):                      # read him perfectly, and use Iron Fist on every opening
        sp = s.spar
        if sp.blocked_strike and sp.ready("attack_tech"):
            return "attack_tech"
        return counter(sp.master)
    s = play_out(conn, hall, choose)
    r = s["result"]
    assert r["outcome"] == "victory"
    uses = hall.spars[A].spar.timed
    fist = techs(conn)["Iron Fist"]
    assert uses.get(fist["id"]), "the script should have landed at least one well-timed Iron Fist"
    want = uses[fist["id"]] * technique.SPAR_EXP_PER_TIMED_USE + technique.SPAR_WIN_EXP
    want = min(round(want * rules.mastery_bonus(db.get_player(conn, A), clock())), rules.mastery_cap({**fist, "mastery_exp": 0}))
    assert fist["mastery_exp"] == want
    gain = [g for g in r["gains"] if g["name"] == "Iron Fist"][0]
    assert gain["gained"] == want and gain["exp"] == want
    assert db.daily_count(conn, A, "spar", clock()) == 1
    assert db.cooldown_left(conn, A, "spar", clock()) == technique.SPAR_COOLDOWN_MINUTES * 60
    hall.done(A)
    assert hall.state(conn, A) is None
    assert hall.start(conn, A).startswith("The master is resting.")


def test_no_timed_technique_no_exp_even_on_a_win(setup):
    conn, clock, hall = setup
    hall.start(conn, A)
    s = play_out(conn, hall, lambda s: counter(s.spar.master) if s.spar.master != "strike" else "break")
    assert s["result"]["gains"] == []
    assert any("no mastery EXP" in n for n in s["result"]["notes"])
    assert all(t["mastery_exp"] == 0 for t in techs(conn).values())


def test_the_daily_rate_halves_after_three(setup):
    conn, clock, hall = setup
    for _ in range(technique.SPAR_DAILY_RATES[0][0]):
        db.bump_daily(conn, A, "spar", clock())
    v = hall.hall(conn, A)
    assert v["full_left"] == 0 and v["rate"] == 0.5
    hall.start(conn, A)
    sp = hall.spars[A].spar
    sp.master = "strike"
    hall.pick(conn, A, "defense_tech", 1)
    sp.m_hp = 1                                                   # end it: the next winning exchange finishes him
    sp.master = "guard"
    hall.pick(conn, A, "break", 2)
    s = hall.state(conn, A)
    assert s["result"]["outcome"] == "victory"
    p = db.get_player(conn, A)
    want = round((technique.SPAR_EXP_PER_TIMED_USE + technique.SPAR_WIN_EXP) * 0.5 * rules.mastery_bonus(p, clock()))
    assert techs(conn)["Horse Stance Guard"]["mastery_exp"] == want
    assert any("EXP ×0.5" in n for n in s["result"]["notes"])


def test_injured_or_resting_you_cannot_spar(setup):
    conn, clock, hall = setup
    db.update_player(conn, A, injured_until=clock() + 600)
    assert hall.start(conn, A).startswith("You are injured.")
    db.update_player(conn, A, injured_until=0)
    db.set_cooldown(conn, A, "spar", 600, clock())               # as if a spar had just been played on Discord
    assert hall.start(conn, A) == "The master is resting. Spar again in 10m."
    assert hall.hall(conn, A)["wait"] == "10m"


def test_a_trial_needs_a_full_bar_and_an_equipped_technique(setup):
    conn, clock, hall = setup
    fist = techs(conn)["Iron Fist"]["id"]
    assert "isn't ready for a trial" in hall.start(conn, A, fist)
    assert hall.start(conn, A, 9999) == "You don't know that technique."
    fill_bar(conn)
    v = hall.hall(conn, A)["techniques"][0]
    assert v["full"] and v["strength"] == technique.TRIAL_MASTER_STRENGTH[1] and v["next"] == technique.MASTERY_STAGES[1]["name"]
    with conn:
        conn.execute("UPDATE techniques SET equipped = 0 WHERE id = ?", (fist,))
    assert hall.start(conn, A, fist) == "Equip Iron Fist to take its trial."


def test_passing_a_trial_raises_the_stage(setup):
    conn, clock, hall = setup
    fist = fill_bar(conn)
    assert hall.start(conn, A, fist) is None
    s = hall.state(conn, A)
    p = db.get_player(conn, A)
    assert s["trial"] and s["arena"] == spar_play.HALL and "Iron Fist" in s["title"]
    assert s["master"]["max_hp"] == round(rules.base_stats(p["realm"], p["layer"])[0] * technique.TRIAL_MASTER_STRENGTH[1])
    sp = hall.spars[A].spar
    sp.m_hp, sp.master = 1, "guard"
    hall.pick(conn, A, "break", 1)
    s = hall.state(conn, A)
    assert s["result"]["outcome"] == "victory" and s["result"]["trial"] == {
        "name": "Iron Fist", "passed": True, "stage": technique.MASTERY_STAGES[1]["name"]}
    assert techs(conn)["Iron Fist"]["stage"] == 1
    assert not db.cooldown_left(conn, A, f"trial:{fist}", clock())


def test_failing_a_trial_costs_a_day_and_nothing_else(setup):
    conn, clock, hall = setup
    fist = fill_bar(conn)
    before = techs(conn)["Iron Fist"]["mastery_exp"]
    hall.start(conn, A, fist)
    sp = hall.spars[A].spar
    sp.hp, sp.master = 1, "strike"
    hall.pick(conn, A, "break", 1)
    s = hall.state(conn, A)
    assert s["result"]["outcome"] == "defeat" and not s["result"]["trial"]["passed"]
    t = techs(conn)["Iron Fist"]
    assert t["stage"] == 0 and t["mastery_exp"] == before
    assert db.cooldown_left(conn, A, f"trial:{fist}", clock()) == technique.TRIAL_FAIL_COOLDOWN_HOURS * 3600
    hall.done(A)
    clock.t += technique.SPAR_COOLDOWN_MINUTES * 60 + 1
    assert hall.start(conn, A, fist).startswith("You failed this trial recently.")
    assert hall.hall(conn, A)["techniques"][0]["trial_wait"]


def test_a_spar_counts_for_the_quests(setup):
    conn, clock, hall = setup
    seen = []
    from bot import quests
    real = quests.record

    def spy(c, uid, event, *a, **k):
        seen.append(event)
        return real(c, uid, event, *a, **k)
    spar_play.quests.record = spy
    try:
        hall.start(conn, A)
        sp = hall.spars[A].spar
        sp.m_hp, sp.master = 1, "guard"
        hall.pick(conn, A, "break", 1)
    finally:
        spar_play.quests.record = real
    assert seen == ["spar", "spar_win"]


def test_the_martial_master_opens_the_yard():
    master = next(n for n in town.NPCS if n["key"] == "master")
    assert ["Enter the training yard", "/training"] in master["go"]


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


def test_the_training_page_and_a_spar_through_the_routes(client):
    r = client.get("/training")
    assert r.status_code == 200 and "The Martial Master" in r.text and "Iron Fist" in r.text
    assert client.get("/spar").headers["location"] == "/training"            # no spar yet
    assert client.post("/training/spar").headers["location"] == "/spar"
    assert client.get("/training").headers["location"] == "/spar"            # a spar under way: straight back into it
    page = client.get("/spar")
    assert page.status_code == 200 and "spar.js" in page.text and "Martial Master" in page.text
    assert "hero_male_strike_sheet" in page.text                             # your own frame-by-frame movements
    s = client.get("/spar/state").json()
    assert s["turn"] == 1
    out = client.post("/spar/pick", data={"move": "guard", "turn": 1}).json()
    assert out["error"] is None and out["state"]["turn"] == 2 and out["state"]["last"]["me"]["move"] == "guard"
    assert client.post("/spar/pick", data={"move": "nonsense", "turn": 2}).json()["error"]
    done = client.post("/spar/yield").json()
    assert done["over"] and done["result"]["outcome"] == "forfeit"
    assert client.post("/spar/done").headers["location"] == "/training"
    r = client.get("/training")
    assert r.status_code == 200 and "The master is resting" in r.text


def test_the_pages_need_a_login(tmp_path):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=str(tmp_path / "x.db"), session_secret="t")
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert cl.get("/training").headers["location"] == "/"
    assert cl.get("/spar/state").json() == {"gone": True}
    assert cl.post("/spar/pick", data={"move": "guard"}).json() == {"gone": True}
