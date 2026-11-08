"""Excess Internal Qi survives /breakthrough: an admin gift above a full bar can be spent on attempt
after attempt, and both a failure and a success keep every point that the attempt did not cost."""
import pytest

from bot import admin, db
from bot import player as rules

REALM, GATE = "Martial Warrior", 9           # 9th layer: the Late Phase bottleneck
NEED = rules.qi_needed(REALM, GATE)          # 96 Qi
LOSS = 0.20                                  # training.BREAKTHROUGH_FAIL_QI_LOSS (20% of the bar)


class Roll:
    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


FAIL, WIN = Roll(0.99), Roll(0.0)


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.create_player(c, 1, "P1", "Ordinary", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, 1, realm=REALM, layer=GATE, qi=20.0, qi_overflow=0.0)
    return c


def total(p):
    return p["qi"] + (p["qi_overflow"] or 0)


def attempt(conn, roll):
    """What /breakthrough does: read the player, attempt, save with progress_fields, read back."""
    p = db.get_player(conn, 1)
    ok, msg = rules.attempt_breakthrough(p, db.get_techniques(conn, 1), rng=roll)
    if ok is not None:
        db.update_player(conn, 1, **rules.progress_fields(p))
    return ok, msg, p, db.get_player(conn, 1)


def test_admin_gift_lands_in_the_same_qi_the_breakthrough_reads(conn):
    admin.give(conn, 1, qi=1000)
    p = db.get_player(conn, 1)
    assert p["qi"] == NEED and total(p) == pytest.approx(1020)


def test_bar_not_full_cannot_attempt(conn):
    ok, msg, _, saved = attempt(conn, WIN)
    assert ok is None and "not full" in msg
    assert saved["qi"] == 20 and saved["layer"] == GATE


def test_exactly_full_bar_fails_with_the_usual_cost(conn):
    db.update_player(conn, 1, qi=float(NEED))
    ok, _, _, saved = attempt(conn, FAIL)
    assert ok is False
    assert saved["qi"] == pytest.approx(NEED * (1 - LOSS)) and saved["qi_overflow"] == 0


def test_big_gift_then_failure_keeps_the_excess_and_can_retry(conn):
    admin.give(conn, 1, qi=1000)
    ok, msg, p, saved = attempt(conn, FAIL)
    assert ok is False and saved["layer"] == GATE
    assert total(saved) == pytest.approx(1020 - NEED * LOSS)     # only the failure cost is gone
    assert saved["qi"] == NEED                                     # the bar is full again
    assert (saved["qi"], saved["qi_overflow"]) == pytest.approx((p["qi"], p["qi_overflow"]))  # stored = shown
    assert rules.ready_to_break(saved)


def test_big_gift_then_success_keeps_the_excess(conn):
    admin.give(conn, 1, qi=1000)
    ok, _, _, saved = attempt(conn, WIN)
    assert ok and saved["layer"] == GATE + 1
    # The full 96 bar opened the 10th layer; the other 924 flow into it (128 bar) and wait at the realm gate.
    assert total(saved) == pytest.approx(1020 - NEED)
    assert saved["qi"] == rules.qi_needed(REALM, 10)


def test_repeated_failures_each_cost_once_and_never_reset(conn):
    admin.give(conn, 1, qi=1000)
    expected = 1020.0
    for _ in range(5):
        ok, _, _, saved = attempt(conn, FAIL)
        expected -= NEED * LOSS
        assert ok is False and saved["qi"] == NEED
        assert total(saved) == pytest.approx(expected)
    ok, _, _, saved = attempt(conn, WIN)
    assert ok and total(saved) == pytest.approx(expected - NEED)


def test_a_bar_left_short_by_an_old_failure_refills_on_the_next_attempt(conn):
    # Saved before this fix: the bar dropped to 80% and 924 Qi sat unused behind the gate.
    db.update_player(conn, 1, qi=NEED * 0.8, qi_overflow=924.0)
    ok, _, _, saved = attempt(conn, FAIL)
    assert ok is False                                   # the attempt was allowed
    assert saved["qi"] == NEED
    assert total(saved) == pytest.approx(NEED * 0.8 + 924 - NEED * LOSS)


def test_a_bar_left_short_refills_when_any_qi_arrives():
    p = {"realm": REALM, "layer": GATE, "qi": NEED * 0.8, "qi_overflow": 924.0}
    p, _ = rules.add_qi(p, 1)
    assert p["qi"] == NEED and total(p) == pytest.approx(NEED * 0.8 + 925)
