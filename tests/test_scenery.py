"""Still pools and mossy rocks on the lands (web/scenery.py), what other players see you doing, the mining task and
the blacksmith's word about the quarry."""
import collections
import math
import random

import pytest

pytest.importorskip("fastapi")

import alchemy  # noqa: E402
from bot import db  # noqa: E402
from bot import player as rules  # noqa: E402
from web import env, gather_play, hunt_play, land, overworld, parties, scenery, town, world_tasks  # noqa: E402

UID, OTHER = 811, 812
NOW = 1_800_000_000.0


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "ma.db"))
    for uid in (UID, OTHER):
        db.create_player(c, uid, f"P{uid}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    yield c
    c.close()


def make_world(now):
    clock = lambda: now[0]                                                     # noqa: E731
    return overworld.World(hunt_play.Hunts(parties.Parties(), clock=clock), gather_play.Gathers(clock), clock,
                           lambda: random.Random(9))


@pytest.mark.parametrize("place", sorted(scenery.PLACED))
def test_pools_and_rocks_stand_clear_of_the_ways_and_wall_nothing_in(place):
    spec = land.LANDS[place]
    keep = [tuple(g["at"]) for g in spec["gates"].values()] + [tuple(s) for s in spec.get("secret", [])] + [tuple(spec["start"])]
    for name, x, y, s, flip in scenery.PLACED[place]:
        assert name in env.ASSETS and name in env.catalog()
        assert land.path_dist(place, x, y) > 2.5 and all(math.dist((x, y), k) > 4 for k in keep), (name, x, y)
    assert len(scenery.pieces(place)) == len(scenery.PLACED[place])
    G = 2                                                 # everything walkable before is still reached, bar their feet
    st = spec["start"]
    seen = {(round(st[0] * G), round(st[1] * G))}
    q = collections.deque(seen)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and overworld.walkable(place, n[0] / G, n[1] / G):
                seen.add(n)
                q.append(n)
    for k in keep:
        assert (round(k[0] * G), round(k[1] * G)) in seen or any(abs(a / G - k[0]) + abs(b / G - k[1]) < 1.5 for a, b in seen)
    for px, py in scenery.pools(place):                   # a herb on a pool can be reached from its bank
        hx, hy = px + scenery.ON_POOL[0], py + scenery.ON_POOL[1]
        assert any(math.dist((a / G, b / G), (hx, hy)) < overworld.HERB_REACH * 0.85 for a, b in seen)


def test_water_herbs_take_the_pools_and_moss_the_rocks_without_changing_the_odds(conn):
    now = [NOW]
    world = make_world(now)
    world.enter(conn, UID, "forest_edge")
    w = world.walker(UID)
    db.update_player(conn, UID, realm="Martial Saint")                        # rare grades often, to see lotuses
    types, on_pool, by_rock, water_n, moss_n = collections.Counter(), 0, 0, 0, 0
    for _ in range(1500):
        w.herbs["forest_edge"] = []
        h = world._herb(w, conn, UID, "forest_edge", 0)
        types[h["type"]] += 1
        name = alchemy.HERBS[h["grade"]][h["type"]][0]
        if name in scenery.WATER_HERBS:
            water_n += 1
            on_pool += bool(h.get("water"))
            assert any(math.dist((h["x"], h["y"]), (px + .4, py + .4)) < 0.05 for px, py in scenery.pools("forest_edge"))
        if name in scenery.ROCK_HERBS:
            moss_n += 1
            by_rock += any(math.dist((h["x"], h["y"]), r) < 2.5 for r in scenery.rocks("forest_edge"))
    assert water_n > 50 and on_pool == water_n and moss_n > 20 and by_rock / moss_n > 0.9
    for t, share in alchemy.REGION_HERB_TYPES["moon_forest"].items():
        assert abs(types[t] / 1500 - share) < 0.05
    w.herbs["forest_edge"] = []                                               # two pools: the third lotus goes elsewhere
    got = []
    w.rng = random.Random(1)
    orig = overworld.loot.herb_tier
    try:
        overworld.loot.herb_tier = lambda realm, rng: "Heaven"
        for _ in range(60):
            h = world._herb(w, conn, UID, "forest_edge", 0)
            if h and alchemy.HERBS[h["grade"]][h["type"]][0] in scenery.WATER_HERBS:
                w.herbs["forest_edge"].append(h)
                got.append(bool(h.get("water")))
    finally:
        overworld.loot.herb_tier = orig
    assert sum(got) == len(scenery.pools("forest_edge")) and len(got) > sum(got)


def test_others_see_you_kneel_and_swing(conn):
    now = [NOW]
    world = make_world(now)
    for uid in (UID, OTHER):
        world.enter(conn, uid, "crossroads")
    a = world.walker(UID)
    world.report(conn, UID, "crossroads", a.x, a.y, "kneel")
    assert [o["act"] for o in world.others(conn, OTHER, "crossroads")] == ["kneel"]
    world.report(conn, UID, "crossroads", a.x, a.y, "dance")                 # only the two moves there are
    assert [o["act"] for o in world.others(conn, OTHER, "crossroads")] == [None]
    world.report(conn, UID, "crossroads", a.x, a.y, "swing")
    world.report(conn, UID, "crossroads", a.x, a.y)
    assert [o["act"] for o in world.others(conn, OTHER, "crossroads")] == [None]


def test_the_mining_task_and_the_blacksmiths_word():
    t = world_tasks.TASKS["seams"]
    assert t["n"] == 5 and t["coins"] == 120 and "Ironvein Quarry" in t["text"]
    tie = next(n for n in town.NPCS if n["key"] == "blacksmith")
    assert "Ironvein Quarry" in tie["line"]


def test_digging_seams_counts_for_the_task_when_it_is_todays(conn):
    day = next(d for d in range(400) if "seams" in world_tasks.today(UID, NOW + d * 86400))
    now = NOW + day * 86400
    coins = db.get_player(conn, UID)["lotus_coins"]
    lines = []
    for _ in range(5):
        lines += world_tasks.record(conn, UID, "seams", now)
    assert len(lines) == 1 and "Dig 5 seams" in lines[0]
    assert db.get_player(conn, UID)["lotus_coins"] == coins + 120
