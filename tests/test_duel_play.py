"""Duels at the Arena on the website (web/duel_play.py, docs/pvp.md "On the website")."""
import random

import pytest

import pvp
from bot import db
from bot import player as rules
from web import duel_play

A, B, C = 111, 222, 333


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def setup(tmp_path):
    conn = db.connect(str(tmp_path / "ma.db"))
    for uid, name in ((A, "Lin Feng"), (B, "Mei Xue"), (C, "Bai Long")):
        db.create_player(conn, uid, name, "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    clock = Clock()
    return conn, clock, duel_play.Arena(clock=clock, rng=random.Random(4))


def test_a_challenge_by_name_accepted_starts_a_duel(setup):
    conn, clock, arena = setup
    assert arena.challenge(conn, A, "nobody") == "No cultivator is called nobody."
    assert arena.challenge(conn, A, "Lin Feng") == "You can't challenge yourself."
    assert arena.challenge(conn, A, "mei xue") is None                     # names match whatever the case
    assert arena.lobby(conn, B)["incoming"][0]["name"] == "Lin Feng"
    assert arena.lobby(conn, A)["outgoing"]["name"] == "Mei Xue"
    assert arena.answer(conn, B, A, accept=True) is None
    sa, sb = arena.state(conn, A), arena.state(conn, B)
    assert sa["me"]["name"] == "Lin Feng" and sa["them"]["name"] == "Mei Xue" and sb["me"]["name"] == "Mei Xue"
    assert sa["turn"] == 1 and not sa["over"] and arena.lobby(conn, A)["in_duel"]
    assert "pick" not in sa["them"] and "moves" not in sa["them"]          # never what the other one may pick


def test_a_declined_or_expired_challenge_is_gone(setup):
    conn, clock, arena = setup
    arena.challenge(conn, A, "Mei Xue")
    assert arena.answer(conn, B, A, accept=False) is None and arena.state(conn, A) is None
    arena.challenge(conn, A, "Mei Xue")
    clock.t += duel_play.CHALLENGE_SECONDS + 1
    assert arena.lobby(conn, B)["incoming"] == []
    assert arena.answer(conn, B, A, accept=True) == "That challenge has expired."


def test_the_queue_pairs_the_first_two(setup):
    conn, clock, arena = setup
    assert arena.join_queue(conn, A) is None and arena.lobby(conn, A)["queued"]
    assert arena.lobby(conn, C)["waiting"] == 1
    assert arena.join_queue(conn, C) is None
    assert arena.state(conn, A)["them"]["name"] == "Bai Long" and not arena.lobby(conn, A)["queued"]


def test_a_turn_resolves_when_both_pick_and_hides_the_pick_till_then(setup):
    conn, clock, arena = setup
    arena.challenge(conn, A, "Mei Xue")
    arena.answer(conn, B, A, True)
    assert arena.pick(conn, A, "strike", 1) is None
    assert arena.state(conn, B)["them"]["locked"] and arena.state(conn, A)["me"]["pick"] == "Strike"
    assert arena.pick(conn, A, "guard", 1) == "You already locked in Strike this turn."
    assert arena.pick(conn, B, "guard", 1) is None
    s = arena.state(conn, A)
    assert s["turn"] == 2 and s["last"]["moves"][A]["label"] == "Strike" and s["last"]["moves"][B]["label"] == "Guard"
    assert s["them"]["locked"] is False


def test_time_running_out_guards_for_you(setup):
    conn, clock, arena = setup
    arena.challenge(conn, A, "Mei Xue")
    arena.answer(conn, B, A, True)
    arena.pick(conn, A, "break", 1)
    clock.t += duel_play.TURN_SECONDS + 1
    s = arena.state(conn, A)
    assert s["turn"] == 2 and s["last"]["moves"][B]["timed_out"]


def test_fleeing_loses_and_is_saved_with_the_pair_cooldown(setup):
    conn, clock, arena = setup
    arena.challenge(conn, A, "Mei Xue")
    arena.answer(conn, B, A, True)
    arena.flee(conn, A)
    s = arena.state(conn, B)
    assert s["over"] and s["result"]["won"] and s["result"]["reason"] == "forfeit"
    assert db.get_player(conn, B)["duels_won"] == 1 and db.get_player(conn, A)["duels_lost"] == 1
    assert conn.execute("SELECT COUNT(*) FROM duels").fetchone()[0] == 1
    assert not arena.lobby(conn, A)["in_duel"]                             # the Arena page doesn't send you back to it
    arena.done(A)
    arena.done(B)
    assert arena.state(conn, A) is None
    assert "wait" in arena.challenge(conn, A, "Mei Xue")                    # the bot's cooldown for the pair
    clock.t += pvp.PAIR_COOLDOWN_SECONDS + 1
    assert arena.challenge(conn, A, "Mei Xue") is None


def test_a_full_duel_ends_and_counts(setup):
    conn, clock, arena = setup
    arena.join_queue(conn, A)
    arena.join_queue(conn, B)
    for _ in range(pvp.MAX_TURNS + 1):
        s = arena.state(conn, A)
        if s["over"]:
            break
        arena.pick(conn, A, "strike", s["turn"])
        arena.pick(conn, B, "break", s["turn"])
    s = arena.state(conn, A)
    assert s["over"] and s["result"]["won"]                                  # Strike beats Break every turn
    assert db.get_player(conn, A)["duels_won"] == 1


def test_you_cannot_duel_while_in_one(setup):
    conn, clock, arena = setup
    arena.challenge(conn, A, "Mei Xue")
    arena.answer(conn, B, A, True)
    assert arena.challenge(conn, C, "Lin Feng") == "Lin Feng is in a duel right now."
    assert arena.join_queue(conn, A) == "You are already in a duel."
