"""The open world (web/overworld.py, docs/world.md): walking between places, herbs, beasts, finds and trips."""
import collections
import math
import random
import urllib.parse

import pytest

import alchemy
import explore as explore_rules
import hunting
from bot import db
from bot import player as rules
from web import overworld as ow
from web.gather_play import Gathers
from web.hunt_play import Hunts
from web.parties import Parties

UID, OTHER = 701, 702


class Clock:
    def __init__(self):
        self.t = 10_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "w.db"))
    for uid in (UID, OTHER):
        db.create_player(c, uid, f"P{uid}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, uid, realm="Martial Warrior", layer=3, spirit_check_in=999)
    return c


@pytest.fixture
def world():
    clock = Clock()
    hunts = Hunts(Parties(), clock=clock, rng_factory=lambda: random.Random(5))
    seeds = iter(range(100, 10_000))
    w = ow.World(hunts, Gathers(clock=clock), clock=clock, rng_factory=lambda: random.Random(next(seeds)))
    w.now = clock
    return w


def into_forest(world, conn, uid=UID):
    world.enter(conn, uid, "crossroads")
    world.enter(conn, uid, "forest_edge", "north")
    return world.state(conn, uid, "forest_edge")


def stand(world, uid, x, y):
    w = world.walker(uid)
    w.x, w.y = x, y


# ── the places and the ways between them ──────────────────────────────────────────────────────────────────────

def test_every_entrance_leads_somewhere_and_back():
    for (place, key), e in ow.ENTRANCES.items():
        assert place in ow.PLACES and e["to"] in ow.PLACES
        assert ow.walkable(place, *e["at"]), (place, key)                    # you can walk into it
        back = [k for (p, k), x in ow.ENTRANCES.items() if p == e["to"] and x["to"] == place]
        assert back, (place, key)                                             # and there is a way back
        if e["arrive"] is not None:
            assert (e["to"], e["arrive"]) in ow.ENTRANCES
        x, y = ow.arrival(e["to"], e["arrive"])
        assert ow.walkable(e["to"], x, y)
        if e["arrive"]:                                                       # out far enough not to go straight back
            assert math.dist((x, y), ow.ENTRANCES[(e["to"], e["arrive"])]["at"]) > ow.ARRIVE_GAP - 1e-6


def test_you_walk_from_town_to_the_forest_and_back(world, conn):
    world.enter(conn, UID, "town")
    gate = ow.ENTRANCES[("town", "gate_out")]["at"]
    assert world.move(conn, UID, "town", "gate_out", *gate) is None          # too far: you are at the town's start
    stand(world, UID, gate[0] - 0.4, gate[1])
    to, _ = world.move(conn, UID, "town", "gate_out", *gate)
    w = world.walker(UID)
    assert to == "crossroads" and w.place == "crossroads"
    assert (w.x, w.y) == ow.arrival("crossroads", "town_gate")
    road = ow.ENTRANCES[("crossroads", "road_moon_forest")]["at"]
    assert world.move(conn, UID, "crossroads", "road_moon_forest", *road) is None   # the road is far from the gate
    stand(world, UID, road[0], road[1] - 0.5)
    assert world.move(conn, UID, "crossroads", "road_moon_forest", *road)[0] == "forest_edge"
    for place, key, to in (("forest_edge", "south", "deep_woods"), ("deep_woods", "east", "shrine_grove"),
                           ("shrine_grove", "west", "deep_woods"), ("deep_woods", "north", "forest_edge")):
        at = ow.ENTRANCES[(place, key)]["at"]
        stand(world, UID, *at)
        assert world.move(conn, UID, place, key, *at)[0] == to               # three lands deep, and back
    out = ow.ENTRANCES[("forest_edge", "north")]["at"]
    stand(world, UID, out[0] - 0.5, out[1] + 0.5)
    assert world.move(conn, UID, "forest_edge", "north", out[0] - 0.5, out[1] + 0.5)[0] == "crossroads"
    w = world.walker(UID)
    assert math.dist((w.x, w.y), road) < 3                                   # back at the end of the forest road


def test_you_come_out_as_far_to_the_side_as_you_went_in(world, conn):
    world.enter(conn, UID, "crossroads")
    road = ow.ENTRANCES[("crossroads", "road_moon_forest")]
    for side in (-1.0, 0.0, 0.9):
        stand(world, UID, road["at"][0] + side, road["at"][1])
        assert world.move(conn, UID, "crossroads", "road_moon_forest", road["at"][0] + side, road["at"][1])
        w = world.walker(UID)
        into = ow.ENTRANCES[("forest_edge", "north")]["at"]
        assert w.x == pytest.approx(into[0] + side) and w.y == pytest.approx(into[1] + ow.ARRIVE_GAP)
        back = (w.x, into[1])
        stand(world, UID, *back)
        assert world.move(conn, UID, "forest_edge", "north", *back)[0] == "crossroads"
        w = world.walker(UID)
        assert w.x == pytest.approx(road["at"][0] + side)                    # and the same on the way back
    stand(world, UID, road["at"][0] + 4, road["at"][1])                      # beside the road, not in its mouth
    assert world.move(conn, UID, "crossroads", "road_moon_forest", road["at"][0] + 4, road["at"][1]) is None


def test_the_lands_are_big_and_their_paths_meet_at_the_gates():
    from web import land
    assert land.size("crossroads") >= 60 and all(land.size(k) >= 70 for k in ow.WILD)
    for (place, key), e in ow.ENTRANCES.items():
        if place == "town":
            continue
        assert not land.off_path(place, *e["at"], room=0), (place, key)       # a path runs out through every gate
        (nx, ny), _ = land.SIDES[e["side"]]
        beyond = (e["at"][0] + nx * 4, e["at"][1] + ny * 4)
        assert not land.off_path(place, *beyond, room=0), (place, key)        # and on past the rim
        if e["to"] != "town":
            assert land.SIDES[ow.ENTRANCES[(e["to"], e["arrive"])]["side"]][0] == (-nx, -ny)   # out one side, in the other
    for k in land.LANDS:
        g = land.ground(k)
        assert g["have"] and g["chunk"] == 1024


def test_reports_are_checked_like_the_hunting_map(world, conn):
    world.enter(conn, UID, "crossroads")
    w = world.walker(UID)
    x0, y0 = w.x, w.y
    assert world.report(conn, UID, "crossroads", x0 + 0.2, y0) == {"x": pytest.approx(x0 + 0.2), "y": y0}
    world.now.t += 0.1
    assert world.report(conn, UID, "crossroads", x0 + 8, y0)["x"] == pytest.approx(x0 + 0.2)   # too fast: put back
    assert world.report(conn, UID, "forest_edge", 19, 19)["url"] == "/crossroads"      # you are not there


def test_a_reload_keeps_where_you_stood(world, conn):
    world.enter(conn, UID, "crossroads")
    stand(world, UID, 10.0, 21.0)
    world.enter(conn, UID, "crossroads")
    assert (world.walker(UID).x, world.walker(UID).y) == (10.0, 21.0)


# ── herbs ─────────────────────────────────────────────────────────────────────────────────────────────────────

def test_herbs_grow_in_their_areas_off_the_road(world, conn):
    world.enter(conn, UID, "crossroads")
    hs = world.state(conn, UID, "crossroads")["herbs"]
    cfg = ow.PLACES["crossroads"]["herbs"]
    assert len(hs) == cfg["count"]
    for h in hs:
        assert ow.walkable("crossroads", h["x"], h["y"])
        from web import land
        assert land.off_path("crossroads", h["x"], h["y"])
        assert all(math.dist((h["x"], h["y"]), e["at"]) >= ow.QUIET for (p, _), e in ow.ENTRANCES.items()
                   if p == "crossroads")
    assert world.state(conn, UID, "town") is None                            # you are not there
    world.enter(conn, UID, "town")
    assert world.state(conn, UID, "town")["herbs"] == []                     # nothing grows in town


def test_each_player_has_their_own_herbs(world, conn):
    world.enter(conn, UID, "crossroads")
    world.enter(conn, OTHER, "crossroads")
    mine = {(h["x"], h["y"]) for h in world.state(conn, UID, "crossroads")["herbs"]}
    theirs = {(h["x"], h["y"]) for h in world.state(conn, OTHER, "crossroads")["herbs"]}
    assert mine != theirs


def test_regions_favour_their_herb_types_and_grades_keep_their_odds(world, conn):
    world.enter(conn, UID, "crossroads")
    w = world.walker(UID)
    p = db.get_player(conn, UID)
    for place in ("crossroads", "forest_edge"):
        types, grades = collections.Counter(), collections.Counter()
        for _ in range(3000):
            h = world._herb(w, conn, UID, place, 0)
            types[h["type"]] += 1
            grades[h["grade"]] += 1
        want = alchemy.REGION_HERB_TYPES[ow.PLACES[place]["herbs"]["region"]]
        for t, share in want.items():
            assert abs(types[t] / 3000 - share) < 0.04, (place, t)
        for g, share in alchemy.herb_grade_odds(p["realm"]).items():          # rare herbs stay rare
            assert abs(grades[g] / 3000 - share) < 0.03, (place, g)
    for row in alchemy.REGION_HERB_TYPES.values():
        assert abs(sum(row.values()) - 1) < 1e-9 and set(row) == set(alchemy.HERB_TYPE_CHANCE)


# ── beasts, finds and trips ───────────────────────────────────────────────────────────────────────────────────

def test_beasts_roam_the_wilds_only(world, conn):
    st = into_forest(world, conn)
    loc = hunting.location("moon_forest")
    names = {b[0] for b in hunting.pool(loc)}
    assert len(st["beasts"]) == ow.PLACES["forest_edge"]["beasts"]["count"]
    w = world.walker(UID)
    for b in st["beasts"]:
        assert b["name"] in names and ow.walkable("forest_edge", b["x"], b["y"])
        assert math.dist((b["x"], b["y"]), (w.x, w.y)) >= ow.BEAST_GAP
    assert sum(1 for b in st["beasts"] if b["tier"] != "normal") <= 1        # one roll a step, as a hunt
    world.enter(conn, UID, "crossroads")
    assert world.state(conn, UID, "crossroads")["beasts"] == []


def test_special_beasts_are_on_offer_no_more_often_than_a_hunt_meets_them(world, conn):
    into_forest(world, conn)
    w = world.walker(UID)
    n, special = 4000, 0
    for _ in range(n):
        w.beasts.clear()
        w.roll = None                                                         # as if a new step each time
        st = world.state(conn, UID, "forest_edge")
        kinds = [b["tier"] for b in st["beasts"]]
        assert sum(1 for k in kinds if k != "normal") <= 1
        special += any(k != "normal" for k in kinds)
    odds = hunting.tier_odds(1, 0)
    assert abs(special / n - (1 - odds["normal"])) < 0.02


def test_walking_from_land_to_land_does_not_roll_the_step_again(world, conn):
    into_forest(world, conn)
    w = world.walker(UID)
    seen = set()
    for _ in range(60):                                                       # in and out of all three lands
        for place, key in (("forest_edge", "north"), ("deep_woods", "north"), ("shrine_grove", "west")):
            world.enter(conn, UID, place, key)
            w.beasts.pop(place, None)                                         # even if its beasts are rolled afresh
            seen.add(tuple(sorted(b["tier"] for b in world.state(conn, UID, place)["beasts"])))
    assert len(seen) == 1                                                     # one roll for the step, whatever you walk


def test_meeting_a_beast_starts_a_trip_and_the_rest(world, conn):
    st = into_forest(world, conn)
    b = st["beasts"][0]
    assert world.engage(conn, UID, "forest_edge", b["id"], b["x"], b["y"])   # too far from where you stand
    stand(world, UID, b["x"] + 0.8, b["y"])
    assert world.engage(conn, UID, "forest_edge", b["id"], b["x"] + 0.8, b["y"]) is None
    trip = world.hunts.trip(UID)
    assert trip is not None and trip.step == 1 and trip.battle is not None and trip.world
    assert trip.battle.enemy["name"] == b["name"]                            # the beast you met
    assert db.cooldown_left(conn, UID, "explore", world.now.t) > 0            # the 30-minute explore rest
    assert world.walker(UID).beasts.get("forest_edge") is None                # the others scatter


def test_a_find_is_an_explore_find_and_a_step(world, conn):
    st = into_forest(world, conn)
    f = st["finds"][0]
    stand(world, UID, f["x"], f["y"])
    lines, why = world.discover(conn, UID, "forest_edge", f["id"], f["x"], f["y"])
    assert why is None and lines
    assert world.hunts.trip(UID).step == 1
    assert f["id"] not in [x["id"] for x in world.state(conn, UID, "forest_edge")["finds"]]


def test_finds_keep_explores_odds_and_secret_spots_the_rare_ones():
    odds = ow.find_odds(ow.FINDS)
    base = {k: explore_rules.ENCOUNTERS[k]["chance"] for k in ow.FINDS}
    for a in ow.FINDS:
        for b in ow.FINDS:
            assert odds[a] / odds[b] == pytest.approx(base[a] / base[b])     # the same odds among themselves
    assert set(ow.find_odds(ow.SECRET_FINDS)) == set(ow.SECRET_FINDS)
    assert all(explore_rules.ENCOUNTERS[k]["rare"] for k in ow.SECRET_FINDS)


def _spend(world, conn, n):
    """n encounters through finds (the quickest way to use up a trip in a test)."""
    for _ in range(n):
        w = world.walker(UID)
        f = next(iter(w.finds["forest_edge"]), None)
        f["ready"] = 0
        stand(world, UID, f["x"], f["y"])
        lines, why = world.discover(conn, UID, "forest_edge", f["id"], f["x"], f["y"])
        assert why is None, why


def test_a_trip_holds_five_encounters_then_the_wilds_go_quiet(world, conn):
    into_forest(world, conn)
    world.state(conn, UID, "forest_edge")
    _spend(world, conn, hunting.MAX_ENCOUNTERS)
    st = world.state(conn, UID, "forest_edge")
    assert st["trip"]["spent"] and st["wary"] and st["finds"] == [] and "spent" in st["quiet"]
    b = st["beasts"][0]
    stand(world, UID, b["x"] + 0.5, b["y"])
    assert "spent" in world.engage(conn, UID, "forest_edge", b["id"], b["x"] + 0.5, b["y"])
    assert world.hunts.trip(UID).step == hunting.MAX_ENCOUNTERS               # no sixth
    assert st["herbs"]                                                        # herbs still grow


def test_walking_into_town_banks_the_trip(world, conn):
    into_forest(world, conn)
    world.state(conn, UID, "forest_edge")
    trip = None
    for _ in range(3):
        _spend(world, conn, 1)
        trip = world.hunts.trip(UID)
    e = trip.exps[UID]
    carried = len(e.items) + (1 if e.coins else 0)
    world.enter(conn, UID, "crossroads", "road_moon_forest")
    assert world.hunts.trip(UID) is not None                                  # the Crossroads isn't town
    lines = world.enter(conn, UID, "town")
    assert lines and "town gate" in lines[0]
    assert world.hunts.trip(UID) is None and world.hunts.parties.of(UID) is None
    assert carried == 0 or len(lines) > 1


def test_resting_or_injured_means_nothing_to_meet(world, conn):
    db.set_cooldown(conn, UID, "explore", 600, world.now.t)
    st = into_forest(world, conn)
    assert st["wary"] and st["finds"] == [] and st["herbs"] and "resting" in st["quiet"]
    b = st["beasts"][0]
    stand(world, UID, b["x"] + 0.5, b["y"])
    assert "resting" in world.engage(conn, UID, "forest_edge", b["id"], b["x"] + 0.5, b["y"])
    assert world.hunts.trip(UID) is None


def test_a_team_member_meets_nothing(world, conn):
    world.hunts.parties.create(conn, UID, "Gorge Runners", True)
    st = into_forest(world, conn)
    assert st["wary"] and "team" in st["quiet"]


def test_beasts_wait_while_you_gather(world, conn):
    st = into_forest(world, conn)
    h = st["herbs"][0]
    stand(world, UID, h["x"], h["y"])
    s, why = world.gather(conn, UID, "forest_edge", h["id"], h["x"], h["y"])
    assert why is None
    b = world.walker(UID).beasts["forest_edge"][0]
    stand(world, UID, b["x"] + 0.5, b["y"])
    assert world.engage(conn, UID, "forest_edge", b["id"], b["x"] + 0.5, b["y"]) == "You are gathering."


def test_carried_home_after_a_defeat(world, conn):
    into_forest(world, conn)
    world.defeated(UID)
    w = world.walker(UID)
    assert w.place == "town" and (w.x, w.y) == tuple(ow.start("town"))


# ── the pages ──────────────────────────────────────────────────────────────────────────────────────────────────
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402


@pytest.fixture
def site(tmp_path, monkeypatch):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, realm="Martial Warrior", layer=3)
    c.close()
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "u", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=path, session_secret="s"))
    app.state.hunts.rng_factory = lambda: random.Random(5)
    cl = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
    cl.get("/callback", params={"code": "x", "state": q["state"][0]})
    cl.world = app.state.world
    return cl


def test_you_cant_type_your_way_into_the_forest(site):
    site.get("/town")
    assert site.get("/wild/forest_edge").headers["location"] == "/town"
    site.get("/crossroads")
    assert site.get("/wild/forest_edge").headers["location"] == "/crossroads"
    assert site.get("/wild/nowhere").headers["location"] == "/crossroads"


def test_the_purse_is_at_the_top_right_and_kept_fresh(site):
    r = site.get("/town")
    assert 'class="pursepill pearls"' in r.text and 'class="pursepill coins"' in r.text and 'id="setBtn"' in r.text
    assert 'data-size="1.5"' in r.text                                        # the character size setting
    st = site.post("/world/state", data={"place": "town"}).json()
    assert set(st["purse"]) == {"coins", "pearls"} and "," in st["purse"]["coins"] or st["purse"]["coins"].isdigit()
    assert 'class="pursepill coins"' in site.get("/profile").text             # and on the other pages' top bar


def test_moving_answers_the_next_place(site):
    site.get("/crossroads")
    road = ow.ENTRANCES[("crossroads", "road_moon_forest")]["at"]
    stand(site.world, UID, road[0], road[1] - 0.4)
    v = site.post("/world/move", data={"place": "crossroads", "key": "road_moon_forest", "x": road[0],
                                       "y": road[1]}).json()
    assert v["to"] == "forest_edge" and v["url"] == "/wild/forest_edge"
    d = v["data"]
    assert d["place"] == "forest_edge" and d["ground"]["base"] == "/art/maps/land/forest_edge/" and d["atmos"]
    assert d["size"] == 70 and d["zoom"] < 1 and d["pieces"] == []            # a big, empty land
    assert d["world"]["beasts"] and d["world"]["herbs"]
    north = next(e for e in d["exits"] if e["key"] == "north")
    assert north["walk"] and north["out"] == [0, -1] and north["half"] > 1 and any(e["key"] == "south" for e in d["exits"])
    assert site.get("/wild/forest_edge").status_code == 200                  # now you are there: a reload works
    assert site.get("/wild/moon_forest").headers["location"] == "/wild/forest_edge"   # an old address: where you are
    bad = site.post("/world/move", data={"place": "forest_edge", "key": "north", "x": 30, "y": 30}).json()
    assert bad["stay"]


def test_the_pages_carry_the_world(site):
    import json
    import re
    r = site.get("/crossroads")
    d = json.loads(re.search(r'id="mapdata">(.*?)</script>', r.text, re.S).group(1))
    assert d["place"] == "crossroads" and len(d["world"]["herbs"]) == ow.PLACES["crossroads"]["herbs"]["count"]
    gate = next(e for e in d["exits"] if e["key"] == "town_gate")
    road = next(e for e in d["exits"] if e["key"] == "road_moon_forest")
    assert gate["walk"] and road["walk"] and not road["go"]                   # walked through, no menu
    sealed = next(e for e in d["exits"] if e["key"] == "road_frostpeak_mountains")
    assert not sealed.get("walk") and sealed["state"] == "locked"
    assert 'id="gpanel"' in r.text and 'id="fpanel"' in r.text
    t = site.get("/town")
    td = json.loads(re.search(r'id="mapdata">(.*?)</script>', t.text, re.S).group(1))
    assert next(e for e in td["exits"] if e["key"] == "gate_out")["walk"]


def _meet_a_beast(site):
    site.get("/crossroads")
    road = ow.ENTRANCES[("crossroads", "road_moon_forest")]["at"]
    stand(site.world, UID, road[0], road[1] - 0.4)
    v = site.post("/world/move", data={"place": "crossroads", "key": "road_moon_forest", "x": road[0],
                                       "y": road[1]}).json()
    b = v["data"]["world"]["beasts"][0]
    stand(site.world, UID, b["x"] + 0.6, b["y"])
    out = site.post("/world/engage", data={"place": "forest_edge", "id": b["id"], "x": b["x"] + 0.6,
                                           "y": b["y"]}).json()
    assert out["fight"] == "/hunt"
    return b


def _turn(site):
    import re
    return re.search(r'name="turn" value="([^"]*)"', site.get("/hunt").text).group(1)


def test_after_a_fight_you_are_back_where_you_stood(site):
    b = _meet_a_beast(site)
    assert site.get("/wild/forest_edge").headers["location"] == "/hunt"       # mid-fight: the fight comes first
    trip = site.world.hunts.trip(UID)
    for _ in range(40):
        if trip.battle is None:
            break
        fb = trip.battle
        fb.enemy["hp"] = 1
        fb.enemy["statuses"].clear()
        fb.intent = {"move": "break", "kind": "normal", "target": fb.fighters[0], "name": "Break"}
        site.post("/hunt/act", data={"what": "move", "arg": "strike", "turn": _turn(site)})
    assert trip.battle is None and "Victory!" in site.get("/hunt").text
    site.post("/hunt/act", data={"what": "continue", "arg": "", "turn": _turn(site)})
    assert site.get("/hunt").headers["location"] == "/world/back"             # back out in the world,
    assert site.get("/world/back").headers["location"] == "/wild/forest_edge"  # where you stand
    r = site.get("/wild/forest_edge")
    assert r.status_code == 200
    w = site.world.walker(UID)
    assert (w.x, w.y) == pytest.approx((b["x"] + 0.6, b["y"]))                # where you stood
    st = site.post("/world/state", data={"place": "forest_edge"}).json()
    assert st["trip"]["step"] == 1 and not st["wary"] and len(st["beasts"]) == 5   # new beasts are out
    assert b["id"] not in [x["id"] for x in st["beasts"]]


def test_falling_in_the_wilds_carries_you_home(site):
    _meet_a_beast(site)
    trip = site.world.hunts.trip(UID)
    for _ in range(40):
        if trip.battle is None:
            break
        fb = trip.battle
        fb.fighters[0].hp = 1
        fb.intent = {"move": "strike", "kind": "normal", "target": fb.fighters[0], "name": "Strike"}
        site.post("/hunt/act", data={"what": "move", "arg": "break", "turn": _turn(site)})
    page = site.get("/hunt").text
    assert "Expedition failed" in page and "Back to town" in page
    assert site.post("/hunt/done").headers["location"] == "/town"
    assert site.world.walker(UID).place == "town" and site.world.hunts.trip(UID) is None
    assert site.get("/town").status_code == 200
    assert site.get("/wild/forest_edge").headers["location"] == "/town"       # you walk back out from the gate
