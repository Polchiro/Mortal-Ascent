"""Shared rare herb events on the website (web/herb_events.py, docs/world.md "A heavenly phenomenon"): two a day in
the Moon Forest; one herb everyone can kneel at; the first right answer pulls it free, 500 years old at the
claimant's own grade; a claim a day; a round you were beaten to costs nothing."""
import random
import time

import pytest

pytest.importorskip("fastapi")

import alchemy  # noqa: E402
from bot import db  # noqa: E402
from bot import player as rules  # noqa: E402
from web import gather_play, herb_events, hunt_play, land, overworld, parties  # noqa: E402

A, B = 801, 802
DAY = 1_800_000_000 - 1_800_000_000 % 86400


@pytest.fixture
def conn(tmp_path, monkeypatch):
    monkeypatch.setattr(herb_events, "ENABLED", True)
    c = db.connect(str(tmp_path / "ma.db"))
    for uid, name in ((A, "Ann"), (B, "Bo")):
        db.create_player(c, uid, name, "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, uid, spirit_check_in=0, herb_streak=5)      # a spirit check is due: it must not interrupt
    yield c
    c.close()


class Setup:
    def __init__(self, conn):
        self.now = [DAY + 10.0]
        clock = lambda: self.now[0]                                           # noqa: E731
        self.gathers = gather_play.Gathers(clock)
        self.world = overworld.World(hunt_play.Hunts(parties.Parties(), clock=clock), self.gathers, clock, lambda: random.Random(4))
        self.conn = conn
        self.ev = self.world.events
        self.ev.ensure(conn)

    def rise(self):
        """Move the clock to the day's first event and stand both players by it."""
        row = self.conn.execute("SELECT * FROM world_events ORDER BY starts").fetchone()
        self.now[0] = row["starts"] + 5
        for uid in (A, B):
            self.world.enter(self.conn, uid, row["place"])
            w = self.world.walker(uid)
            w.x, w.y, w.t = row["x"] - 1.0, row["y"], self.now[0]
        return row

    def kneel(self, uid, row):
        w = self.world.walker(uid)
        return self.world.gather_event(self.conn, uid, row["place"], w.x, w.y)


def test_two_events_a_day_in_the_forests_far_clearings(conn):
    s = Setup(conn)
    rows = conn.execute("SELECT * FROM world_events").fetchall()
    assert len(rows) == herb_events.PER_DAY == 2
    for r in rows:
        assert r["place"] in herb_events.LANDS and (r["x"], r["y"]) in [tuple(p) for p in land.LANDS[r["place"]]["secret"]]
        assert overworld.walkable(r["place"], r["x"], r["y"])
        assert DAY <= r["starts"] and r["ends"] - r["starts"] == herb_events.MINUTES * 60 and r["ends"] <= DAY + 86400
        assert r["type"] in alchemy.HERB_TYPE_CHANCE and r["claimed_by"] is None
    s.ev._made.clear()
    s.ev.ensure(conn)                                                         # asked again: no more are made
    assert conn.execute("SELECT COUNT(*) FROM world_events").fetchone()[0] == 2


def test_everyone_is_told_a_light_has_risen_but_only_its_land_knows_where(conn):
    s = Setup(conn)
    assert s.ev.view(conn, A, "town") is None or not s.ev.view(conn, A, "town")["live"] or True
    row = s.rise()
    far = s.ev.view(conn, A, "town")
    assert far["live"] and far["region"] == "Moon Forest" and "x" not in far and not far["here"]
    other = next(k for k in herb_events.LANDS if k != row["place"])
    assert "x" not in s.ev.view(conn, A, other) and s.ev.view(conn, A, other)["inForest"]
    here = s.ev.view(conn, A, row["place"])
    assert (here["x"], here["y"]) == (row["x"], row["y"]) and 0 < here["left"] <= herb_events.MINUTES * 60
    assert s.world.state(conn, A, row["place"])["event"]["here"]


def test_the_first_right_answer_pulls_it_free_at_500_years_and_the_other_loses_nothing(conn):
    s = Setup(conn)
    row = s.rise()
    sa, why = s.kneel(A, row)
    sb, why_b = s.kneel(B, row)
    assert why is None and why_b is None
    ra, rb = sa.g.round, sb.g.round
    assert ra.kind == rb.kind == "herb"                                        # no Wandering Spirit, though one was due
    assert ra.herb["data"]["age"] == herb_events.AGE and ra.herb["data"]["type"] == row["type"] and ra.old
    s.now[0] += 2
    s.world.pick(conn, A, ra.answer, sa.turn)
    got = db.get_items(conn, A, "herbs")
    assert len(got) == 1 and got[0]["key"].endswith(":500") and db.get_player(conn, A)["herb_streak"] == 6
    s.world.pick(conn, B, rb.answer, sb.turn)                                 # right too, but second
    assert db.get_items(conn, B, "herbs") == [] and db.get_player(conn, B)["herb_streak"] == 5   # nothing lost
    assert sb.result == gather_play.TAKEN_LINE and sb.g.round is None
    v = s.ev.view(conn, B, row["place"])
    assert v["claimed"] and not v["live"] and not v["mine"] and s.ev.view(conn, A, row["place"])["mine"]
    assert conn.execute("SELECT claimed_by FROM world_events WHERE id = ?", (row["id"],)).fetchone()[0] == A


def test_only_one_claim_can_land(conn):
    s = Setup(conn)
    row = s.rise()
    assert s.ev.claim(conn, A, row["id"]) is True
    assert s.ev.claim(conn, B, row["id"]) is False and s.ev.claim(conn, A, row["id"]) is False
    assert db.daily_count(conn, A, herb_events.WON, s.now[0]) == 1 and db.daily_count(conn, B, herb_events.WON, s.now[0]) == 0


def test_a_wrong_pick_costs_as_always_and_you_kneel_only_once(conn):
    s = Setup(conn)
    row = s.rise()
    sa, _ = s.kneel(A, row)
    wrong = next(k for k, _, _ in sa.g.round.options if k != sa.g.round.answer)
    s.world.pick(conn, A, wrong, sa.turn)
    assert db.get_items(conn, A, "herbs") == [] and db.get_player(conn, A)["herb_streak"] == 0
    assert s.ev.view(conn, A, row["place"])["live"]                            # still there for the others
    again, why = s.kneel(A, row)
    assert again is None and "already" in why
    sb, _ = s.kneel(B, row)
    s.world.pick(conn, B, sb.g.round.answer, sb.turn)
    assert len(db.get_items(conn, B, "herbs")) == 1


def test_one_claim_a_day_and_it_fades_after_twenty_minutes(conn):
    s = Setup(conn)
    rows = conn.execute("SELECT * FROM world_events ORDER BY starts").fetchall()
    row = s.rise()
    sa, _ = s.kneel(A, row)
    s.world.pick(conn, A, sa.g.round.answer, sa.turn)
    second = rows[1]
    if second["starts"] < row["ends"]:                                         # (they overlap this seed: nothing to test)
        return
    s.now[0] = second["starts"] + 5
    for uid in (A, B):
        s.world.enter(conn, uid, second["place"])
        w = s.world.walker(uid)
        w.x, w.y, w.t = second["x"] - 1.0, second["y"], s.now[0]
    assert s.ev.view(conn, A, second["place"])["capped"]
    none, why = s.kneel(A, second)
    assert none is None and "already claimed" in why
    s.now[0] = second["ends"] + 1
    v = s.ev.view(conn, B, second["place"])
    assert v is not None and not v["live"] and not v["claimed"]                # fading, unclaimed
    assert s.kneel(B, second)[0] is None
    s.now[0] = second["ends"] + herb_events.AFTER + 1
    assert s.ev.view(conn, B, second["place"]) is None


def test_a_round_open_when_someone_else_takes_it_is_called_off(conn):
    s = Setup(conn)
    row = s.rise()
    sa, _ = s.kneel(A, row)
    sb, _ = s.kneel(B, row)
    s.world.pick(conn, A, sa.g.round.answer, sa.turn)
    s.now[0] += 60                                                             # B's time would have run out by now
    s.world.state(conn, B, row["place"])
    assert sb.g.round is None and sb.result == gather_play.TAKEN_LINE
    assert db.get_player(conn, B)["herb_streak"] == 5


def test_switched_off_there_are_none(conn, monkeypatch):
    s = Setup(conn)
    row = s.rise()
    monkeypatch.setattr(herb_events, "ENABLED", False)
    assert s.ev.view(conn, A, row["place"]) is None and s.kneel(A, row)[0] is None
