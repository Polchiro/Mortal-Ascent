"""The walkable hunting-ground map (web/hunt_map.py, Hunt.map in web/hunt_play.py, docs/hunting.md "The map")."""
import random

import pytest

import hunting
import looks
from bot import db
from bot import player as rules
from scripts import make_hero_walk
from web import hunt_map
from web.hunt_play import MAP_IDLE_SECONDS, Hunts, walks
from web.parties import Parties


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "m.db"))
    db.create_player(c, 1, "Walker", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, 1, realm="Martial Apprentice", layer=5)
    yield c
    c.close()


class Clock:
    t = 1_000_000.0

    def __call__(self):
        return self.t


def _hunt(conn, walk, seed=9):
    clock = Clock()
    parties = Parties(clock=clock)
    hunts = Hunts(parties, clock=clock, rng_factory=lambda: random.Random(seed))
    p, _ = parties.create(conn, 1, "", True, solo=True)
    parties.set_location(conn, 1, "moon_forest")
    assert hunts.start(conn, 1, walk=walk) is None
    return hunts, hunts.get(p.id), clock


def _walk_to(hunts, conn, h, clock, x, y):
    """Report positions along a straight line at walking pace (as the page would)."""
    px, py, _ = h.pos[1]
    n = max(1, int(((x - px) ** 2 + (y - py) ** 2) ** .5 / 0.8) + 1)
    for i in range(1, n + 1):
        clock.t += 0.3
        assert hunts.report(conn, 1, px + (x - px) * i / n, py + (y - py) * i / n) is not None


def _engage(hunts, conn, h, clock):
    b = h.beast
    tx = b["x"] + 0.5 if b["x"] + 0.5 < hunt_map.SIZE - hunt_map.EDGE else b["x"] - 0.5
    _walk_to(hunts, conn, h, clock, tx, b["y"])
    hunts.act(conn, 1, "engage", f"{tx},{b['y']}", hunts.version(h, 1))


def test_the_map_rolls_the_same_first_beast_as_the_menus(conn):
    _, menu, _ = _hunt(conn, walk=False, seed=21)
    first = (menu.battle.enemy["name"], menu.battle.enemy["tier"])
    conn.execute("DELETE FROM cooldowns")
    _, walked, _ = _hunt(conn, walk=True, seed=21)
    assert walked.battle is None and walked.step == 1
    assert (walked.beast["name"], walked.beast["tier"]) == first
    assert hunt_map.walkable(walked.beast["x"], walked.beast["y"])


def test_walking_up_to_the_beast_starts_the_usual_fight(conn):
    hunts, h, clock = _hunt(conn, walk=True)
    name = h.beast["name"]
    hunts.act(conn, 1, "engage", f"{h.pos[1][0]},{h.pos[1][1]}", hunts.version(h, 1))    # from the start: too far
    assert h.battle is None
    _engage(hunts, conn, h, clock)
    assert h.battle is not None and h.battle.enemy["name"] == name and h.beast is None
    assert h.loc["arena"] == "battle_bamboo_forest"


def test_no_teleporting(conn):
    hunts, h, clock = _hunt(conn, walk=True)
    b = h.beast
    clock.t += 0.3
    assert hunts.report(conn, 1, b["x"], b["y"]) == pytest.approx(hunt_map.START)          # put back where you were
    hunts.act(conn, 1, "engage", f"{b['x']},{b['y']}", hunts.version(h, 1))
    assert h.battle is None
    clock.t += 0.3
    assert hunts.report(conn, 1, 0.5, 0.5) == pytest.approx(hunt_map.START)                # off the map
    assert hunts.report(conn, 1, "nan", "1") == pytest.approx(hunt_map.START)


def test_after_a_win_the_next_beast_is_out_on_the_map_and_rewards_are_unchanged(conn, monkeypatch):
    monkeypatch.setattr(hunting, "tier_odds", lambda step, luck=0: {"normal": 1.0})
    hunts, h, clock = _hunt(conn, walk=True)
    _engage(hunts, conn, h, clock)
    f = h.battle.fighter(1)
    f.attack *= 50
    while h.battle is not None:
        hunts.act(conn, 1, "move", "guard" if f.stunned else "strike", hunts.version(h, 1))
    assert h.ended is not None and any("falls in" in x for x in h.lines[1])           # the ordinary /explore payout
    assert h.exps[1].beasts_slain == 1 and h.exps[1].coins > 0
    assert h.step == 2 and h.beast is not None                                          # the next one waits out there
    hunts.act(conn, 1, "continue", "", hunts.version(h, 1))
    hunts.act(conn, 1, "deeper", "", hunts.version(h, 1))                               # no menu button on the map
    assert h.battle is None and h.step == 2
    coins = db.get_player(conn, 1)["lotus_coins"]
    hunts.act(conn, 1, "return", "", hunts.version(h, 1))
    assert h.over and db.get_player(conn, 1)["lotus_coins"] > coins


def test_walking_keeps_you_out_and_standing_still_sends_you_home(conn):
    hunts, h, clock = _hunt(conn, walk=True)
    for _ in range(5):
        clock.t += MAP_IDLE_SECONDS - 60
        x, y, _t = h.pos[1]
        _walk_to(hunts, conn, h, clock, x + 0.5 if x < 12 else x - 0.5, y)
        hunts.catch_up(conn, 1)
        assert not h.over
    clock.t += MAP_IDLE_SECONDS + 1
    hunts.catch_up(conn, 1)
    assert h.over


def test_only_admins_with_a_walking_look_walk(conn, monkeypatch):
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    assert not walks(conn, 1)
    monkeypatch.setenv("ADMIN_IDS", "1")
    assert walks(conn, 1)                                                               # no look chosen yet: male
    db.update_player(conn, 1, appearance=looks.dump({"gender": "female"}))
    assert not walks(conn, 1)                                                           # no walking sheet for her yet


def test_the_walk_sheet_meets_the_spec():
    from PIL import Image
    im = Image.open(make_hero_walk.OUT)
    assert make_hero_walk.check(im) == []
    s = looks.WALK_SHEETS["male"]
    assert (s["cell"], s["rows"], s["cols"], s["feet"]) == (256, 8, 8, [128, 232]) and len(s["stand"]) == 8
