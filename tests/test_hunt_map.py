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


MAP = hunt_map.plan("moon_forest")


def _route(a, b):
    """A walkable path from a to b around the map's rocks and water (breadth-first on a half-tile grid)."""
    from collections import deque
    snap = lambda p: (round(p[0] * 2) / 2, round(p[1] * 2) / 2)
    start, goal = snap(a), snap(b)
    prev, todo = {start: None}, deque([start])
    while todo:
        c = todo.popleft()
        if c == goal:
            break
        for dx, dy in ((.5, 0), (-.5, 0), (0, .5), (0, -.5), (.5, .5), (-.5, -.5), (.5, -.5), (-.5, .5)):
            n = (c[0] + dx, c[1] + dy)
            if n not in prev and hunt_map.walkable(*n, MAP):
                prev[n] = c
                todo.append(n)
    path, c = [], goal
    while c is not None:
        path.append(c)
        c = prev[c]
    return path[::-1][1:] + [b]


def _walk_to(hunts, conn, h, clock, x, y):
    """Report positions along a walkable route at walking pace (as the page would)."""
    for px, py in _route(h.pos[1][:2], (x, y)):
        clock.t += 0.3
        assert hunts.report(conn, 1, px, py) == pytest.approx((px, py), abs=1e-3)


def _engage(hunts, conn, h, clock):
    b = h.beast
    tx = next(x for x in (b["x"] + 0.5, b["x"] - 0.5, b["x"]) if hunt_map.walkable(x, b["y"], MAP))
    _walk_to(hunts, conn, h, clock, tx, b["y"])
    hunts.act(conn, 1, "engage", f"{tx},{b['y']}", hunts.version(h, 1))


def test_the_map_rolls_the_same_first_beast_as_the_menus(conn):
    _, menu, _ = _hunt(conn, walk=False, seed=21)
    first = (menu.battle.enemy["name"], menu.battle.enemy["tier"])
    conn.execute("DELETE FROM cooldowns")
    _, walked, _ = _hunt(conn, walk=True, seed=21)
    assert walked.battle is None and walked.step == 1
    assert (walked.beast["name"], walked.beast["tier"]) == first
    assert hunt_map.walkable(walked.beast["x"], walked.beast["y"], MAP)


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
    assert hunts.report(conn, 1, b["x"], b["y"]) == pytest.approx(hunt_map.start(MAP))          # put back where you were
    hunts.act(conn, 1, "engage", f"{b['x']},{b['y']}", hunts.version(h, 1))
    assert h.battle is None
    clock.t += 0.3
    assert hunts.report(conn, 1, 0.5, 0.5) == pytest.approx(hunt_map.start(MAP))                # off the map
    assert hunts.report(conn, 1, "nan", "1") == pytest.approx(hunt_map.start(MAP))


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
        _walk_to(hunts, conn, h, clock, x - 0.5, y)
        hunts.catch_up(conn, 1)
        assert not h.over
    clock.t += MAP_IDLE_SECONDS + 1
    hunts.catch_up(conn, 1)
    assert h.over


def test_everyone_with_a_walking_look_walks(conn, monkeypatch):
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    assert walks(conn, 1)                                                               # not an admin, no look yet: male
    db.update_player(conn, 1, appearance=looks.dump({"gender": "female"}))
    assert walks(conn, 1)                                                               # she walks too
    monkeypatch.setitem(looks.WALK_SHEETS, "female", None)
    assert not walks(conn, 1)                                                           # a look with no sheet keeps the menus


def test_the_moon_forest_map_blocks_its_rocks_and_water():
    assert hunt_map.walkable(*hunt_map.start(MAP), MAP)
    assert not hunt_map.walkable(14.2, 14.8, MAP)                                       # the pond
    assert not hunt_map.walkable(2.3, 17.6, MAP)                                        # the shrine
    assert hunt_map.walkable(12, 20, MAP)                                               # the stepping stones
    clock = Clock()
    assert hunt_map.moved((*hunt_map.start(MAP), clock.t), 14.2, 14.8, clock.t + 60, MAP) is None   # can't stand in it
    import random as r
    rng = r.Random(3)
    for _ in range(50):                                                                 # beasts stand with room around them
        x, y = hunt_map.spot(rng, hunt_map.start(MAP), MAP)
        assert hunt_map.walkable(x, y, MAP)


def test_a_charge_can_start_the_fight_only_within_its_reach():
    for tier in ("normal", "elite", "beast_king"):
        beast = {"x": 12.0, "y": 12.0, "tier": tier}
        reach = hunt_map.WANDER[tier] + hunt_map.NOTICE[tier] + hunt_map.REACH
        assert hunt_map.close_enough((12.0 + reach - 0.05, 12.0), beast)
        assert not hunt_map.close_enough((12.0 + reach + 0.05, 12.0), beast)
        assert hunt_map.SPAWN_GAP > reach                                               # it never sees you as it appears
    assert hunt_map.NOTICE["beast_king"] > hunt_map.NOTICE["elite"] > hunt_map.NOTICE["normal"]


def test_the_walk_sheets_meet_the_spec():
    from PIL import Image
    from scripts import make_heroine_walk
    for gender, path in (("male", make_hero_walk.OUT), ("female", make_heroine_walk.OUT)):
        assert make_hero_walk.check(Image.open(path)) == [], gender
        s = looks.WALK_SHEETS[gender]
        assert s["src"] == "/art/portraits/map/" + path.rsplit("/", 1)[1]
        assert (s["cell"], s["rows"], s["cols"], s["feet"]) == (256, 8, 8, [128, 232]) and len(s["stand"]) == 8
    from scripts import make_heroine_idle
    idle = looks.WALK_SHEETS["female"]["idle"]
    assert make_hero_walk.check(Image.open(make_heroine_idle.OUT)) == []
    assert idle["src"] == "/art/portraits/map/hero_female_idle.webp" and idle["cols"] == 8 and idle["loop"] > 1
