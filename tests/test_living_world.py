"""A living world (docs/world.md): other players on the map, where you stood kept through a restart, the sound file,
and today's tasks (web/world_tasks.py)."""
import random
import urllib.parse

import pytest

from bot import db
from bot import player as rules
from bot import quests as quest_rules
from web import overworld as ow
from web import world_tasks as wt
from web.gather_play import Gathers
from web.hunt_play import Hunts
from web.parties import Parties

UID, OTHER = 801, 802
NOW = 1_800_000_000.0          # a fixed day (UTC)


class Clock:
    def __init__(self):
        self.t = NOW

    def __call__(self):
        return self.t


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "lw.db"))
    for uid, name in ((UID, "Shoaib"), (OTHER, "Nicolas")):
        db.create_player(c, uid, name, "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, uid, realm="Martial Warrior", layer=3, spirit_check_in=999)
    return c


def make_world(clock=None):
    clock = clock or Clock()
    hunts = Hunts(Parties(), clock=clock, rng_factory=lambda: random.Random(5))
    seeds = iter(range(100, 10_000))
    w = ow.World(hunts, Gathers(clock=clock), clock=clock, rng_factory=lambda: random.Random(next(seeds)))
    w.now = clock
    return w


@pytest.fixture
def world():
    return make_world()


# ── other players ─────────────────────────────────────────────────────────────────────────────────────────────

def test_you_see_the_others_in_your_place_only(world, conn):
    world.enter(conn, UID, "town")
    world.enter(conn, OTHER, "town")
    seen = world.others(conn, UID, "town")
    assert [o["name"] for o in seen] == ["Nicolas"]
    o = seen[0]
    assert o["realm"] == "Martial Warrior · 3rd" and o["look"] in ("male", "female") and o["tag"]
    assert str(OTHER) not in o["tag"]                                     # not their Discord id
    world.enter(conn, OTHER, "crossroads")
    assert world.others(conn, UID, "town") == []                          # walked out of the gate
    assert world.others(conn, UID, "crossroads") is None                  # you are not there


def test_a_closed_page_fades_from_the_others(world, conn):
    world.enter(conn, UID, "town")
    world.enter(conn, OTHER, "town")
    world.now.t += ow.OTHERS_FRESH + 1
    assert world.others(conn, UID, "town") == []                          # Nicolas's page went quiet
    o = world.walker(OTHER)
    world.report(conn, OTHER, "town", o.x, o.y)                           # Nicolas's page speaks again
    assert [o["name"] for o in world.others(conn, UID, "town")] == ["Nicolas"]


# ── kept through a restart ────────────────────────────────────────────────────────────────────────────────────

def test_where_you_stood_survives_a_restart(world, conn):
    world.enter(conn, UID, "crossroads")
    world.enter(conn, UID, "forest_edge", "north")
    w = world.walker(UID)
    spot = db.world_spot(conn, UID)
    assert spot["place"] == "forest_edge" and (spot["x"], spot["y"]) == (w.x, w.y)
    after = make_world()                                                  # the website restarts: memory is empty
    assert after.walker(UID) is None
    assert after.restore(conn, UID) == "forest_edge"
    w2 = after.walker(UID)
    assert (w2.place, w2.x, w2.y) == ("forest_edge", w.x, w.y)
    after.enter(conn, UID, "forest_edge")                                 # the page opens there: you stay put
    assert (after.walker(UID).x, after.walker(UID).y) == (w.x, w.y)
    assert after.restore(conn, OTHER) is None                             # never walked: town as before


def test_walking_saves_now_and_then(world, conn):
    world.enter(conn, UID, "crossroads")
    w = world.walker(UID)
    x0 = w.x
    world.now.t += ow.SAVE_EVERY + 1
    world.report(conn, UID, "crossroads", w.x + 0.5, w.y)
    assert db.world_spot(conn, UID)["x"] == pytest.approx(x0 + 0.5)


# ── today's tasks ─────────────────────────────────────────────────────────────────────────────────────────────

def test_three_tasks_a_day_the_same_all_day():
    a = wt.today(UID, NOW)
    assert len(a) == wt.PER_DAY == 3 and len(set(a)) == 3 and set(a) <= set(wt.TASKS)
    assert wt.today(UID, NOW + 3600) == a                                  # later the same day
    days = {tuple(wt.today(UID, NOW + d * 86400)) for d in range(10)}
    assert len(days) > 1                                                  # a new list on other days


def test_a_task_pays_once_by_realm_and_the_last_adds_the_bonus(conn):
    keys = wt.today(UID, NOW)
    p = db.get_player(conn, UID)
    scale = quest_rules.coin_scale(p)
    start = p["lotus_coins"]
    first = keys[0]
    lines = []
    for _ in range(wt.TASKS[first]["n"] + 2):                              # more than it asks: pays once
        lines += wt.record(conn, UID, first, NOW)
    pay = round(wt.TASKS[first]["coins"] * scale)
    assert lines == [f"Task done: {wt.TASKS[first]['text'].format(n=wt.TASKS[first]['n'])} · +{pay:,} Lotus Coins"]
    assert db.get_player(conn, UID)["lotus_coins"] == start + pay
    other = next(k for k in wt.TASKS if k not in keys)
    assert wt.record(conn, UID, other, NOW) == []                          # not one of today's: nothing
    for k in keys[1:]:
        for _ in range(wt.TASKS[k]["n"]):
            last = wt.record(conn, UID, k, NOW)
    bonus = round(wt.ALL_DONE_COINS * scale)
    assert last[-1] == f"All of today's tasks done · +{bonus:,} Lotus Coins"
    total = sum(round(wt.TASKS[k]["coins"] * scale) for k in keys) + bonus
    assert db.get_player(conn, UID)["lotus_coins"] == start + total
    b = wt.board(conn, UID, NOW)
    assert b["all"] and all(t["done"] for t in b["tasks"])
    assert any(r["reason"].startswith("World task") for r in db.ledger(conn, UID))   # in the ledger
    assert wt.board(conn, UID, NOW + 86400)["all"] is False                 # tomorrow: new tasks


def test_the_world_counts_its_tasks(world, conn, monkeypatch):
    monkeypatch.setattr(wt, "today", lambda uid, now: ["shrine", "bank", "finds"])
    world.enter(conn, UID, "shrine_grove")
    assert db.daily_count(conn, UID, "world:shrine", NOW) == 1
    st = world.state(conn, UID, "shrine_grove")
    assert [t["key"] for t in st["tasks"]["tasks"]] == ["shrine", "bank", "finds"] and st["tasks"]["tasks"][0]["done"]


# ── the pages ─────────────────────────────────────────────────────────────────────────────────────────────────
pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402


@pytest.fixture
def site(tmp_path, monkeypatch):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    for uid, name in ((UID, "Shoaib"), (OTHER, "Nicolas")):
        db.create_player(c, uid, name, "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, uid, realm="Martial Warrior", layer=3)
    c.close()
    who = {"id": None}
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": who["id"], "username": "u", "avatar": None})

    def make():
        app = web_app.create_app(web_app.Settings("cid", "sec", db_path=path, session_secret="s"))
        app.state.hunts.rng_factory = lambda: random.Random(5)
        return app

    def login(app, uid):
        cl = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
        q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
        who["id"] = uid
        cl.get("/callback", params={"code": "x", "state": q["state"][0]})
        return cl
    return make, login


def test_the_page_shows_others_tasks_and_sound(site):
    make, login = site
    app = make()
    a, b = login(app, UID), login(app, OTHER)
    r = a.get("/town").text
    b.get("/town")
    assert "/static/sound.js" in r and 'id="tasks"' in r and 'data-sound="off"' in r and 'id="soundVol"' in r
    seen = a.post("/world/others", data={"place": "town"}).json()["others"]
    assert [o["name"] for o in seen] == ["Nicolas"]
    st = a.post("/world/state", data={"place": "town"}).json()
    assert len(st["tasks"]["tasks"]) == 3
    assert a.post("/world/others", data={"place": "crossroads"}).json() == {"gone": True}


def test_after_a_restart_the_page_takes_you_back(site):
    make, login = site
    app = make()
    a = login(app, UID)
    a.get("/crossroads?near=town_gate")
    road = ow.ENTRANCES[("crossroads", "road_moon_forest")]["at"]
    w = app.state.world.walker(UID)
    w.x, w.y = road[0], road[1] - 0.4
    assert a.post("/world/move", data={"place": "crossroads", "key": "road_moon_forest", "x": road[0],
                                       "y": road[1]}).json()["to"] == "forest_edge"
    app2 = make()                                                          # the website restarts
    a2 = login(app2, UID)
    assert a2.get("/town").headers["location"] == "/wild/forest_edge"      # back where you stood
    assert a2.get("/wild/forest_edge").status_code == 200


def test_a_herb_picked_counts_a_wrong_plant_does_not(world, conn, monkeypatch):
    monkeypatch.setattr(wt, "today", lambda uid, now: ["herbs", "bank", "finds"])
    world.enter(conn, UID, "crossroads")
    got = 0
    for right in (True, False, True):
        st = world.state(conn, UID, "crossroads")
        h = st["herbs"][0]
        w = world.walker(UID)
        w.x, w.y = h["x"], h["y"]
        s, why = world.gather(conn, UID, "crossroads", h["id"], h["x"], h["y"])
        assert why is None
        r = s.g.round
        if r.kind != "herb":
            continue
        key = r.answer if right else next(k for k, _, _ in r.options if k != r.answer)
        world.pick(conn, UID, key, s.turn)
        world.state(conn, UID, "crossroads")
        got += 1 if right else 0
        world.gathers._s.pop(UID, None)                                   # a fresh gathering for the next herb
    assert got and db.daily_count(conn, UID, "world:herbs", NOW) == got


def test_music_and_a_voice_for_everyone_in_town(site):
    import os
    import re
    from web import town
    make, login = site
    a = login(make(), UID)
    r = a.get("/town").text
    assert 'data-music="on"' in r and 'data-music="off"' in r               # Settings: Music On / Off
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    js = open(os.path.join(root, "web", "static", "sound.js"), encoding="utf-8").read()
    voices = js[js.index("var VOICES = {"):js.index("/* the little sounds */")]
    for n in town.NPCS:                                                    # nobody in town is without a voice
        assert re.search(rf"^\s+{n['key']}:", voices, re.M), n["key"]
    for place in ("town", "meadow", "forest"):                             # each kind of place has its tune
        assert re.search(rf"^\s+{place}:\s+\{{root:", js, re.M), place
    walk = open(os.path.join(root, "web", "static", "town.js"), encoding="utf-8").read()
    assert "snd('talk'" in walk and "snd('click')" in walk and "snd('bye')" in walk


def test_the_fights_have_their_sounds():
    import os
    import re
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def read(*p):
        return open(os.path.join(root, *p), encoding="utf-8").read()
    snd = read("web", "static", "fight_sound.js")
    have = set(re.findall(r"^    (\w+): function \(t", snd, re.M))
    assert {"press", "swing", "hit", "hurt", "block", "miss", "cast", "roar", "boom", "victory", "defeat"} <= have
    for js in ("fight.js", "duel.js"):                                     # every sound a fight asks for exists
        asked = set(re.findall(r"fs\('(\w+)'", read("web", "static", js)))
        asked |= set(re.findall(r"\[[^\[\]]*?, '(\w+)'(?:, [^\[\]]*)?\]", "".join(
            l for l in read("web", "static", js).splitlines() if "cues" in l or "add(" in l)))
        assert asked and asked <= have, (js, asked - have)
    for page in ("explore_play.html", "duel.html"):                        # loaded before the fight's own script
        html = read("web", "templates", page)
        own = "asset('fight.js')" if page.startswith("explore") else "asset('duel.js')"
        assert html.index("asset('fight_sound.js')") < html.index(own)


def test_a_database_is_set_up_once_not_on_every_connection(tmp_path, monkeypatch):
    """The website connects for every request: the tables and the old-data renames are done once per file."""
    calls = []
    real = db._set_up
    monkeypatch.setattr(db, "_set_up", lambda c: (calls.append(1), real(c))[1])
    path = str(tmp_path / "once.db")
    for _ in range(5):
        db.connect(path).close()
    assert len(calls) == 1
    db.connect(path, setup=True).close()                                   # asked for: done again
    assert len(calls) == 2
    import os
    os.remove(path)                                                        # a new file at the same place: set up again
    c = db.connect(path)
    assert len(calls) == 3 and c.execute("SELECT COUNT(*) FROM players").fetchone()[0] == 0
    other = str(tmp_path / "other.db")                                     # and every other file its own first time
    db.connect(other).close()
    assert len(calls) == 4


def test_a_walking_page_is_told_who_else_is_here_with_its_step(world, conn):
    world.enter(conn, UID, "town")
    world.enter(conn, OTHER, "town")
    me = world.walker(UID)
    r = world.report(None, UID, "town", me.x, me.y)                        # no database needed for a step
    assert [o["name"] for o in r["others"]] == ["Nicolas"]
    assert "others" not in world.report(None, UID, "town", me.x, me.y)     # told a moment ago: not again yet
    world.now.t += ow.OTHERS_EVERY
    assert "others" in world.report(None, UID, "town", me.x, me.y)
    saved = []
    world.with_conn = lambda fn, *a: saved.append(a)                       # the spot is saved through its own connection
    world.now.t += ow.SAVE_EVERY + 1
    world.report(None, UID, "town", me.x, me.y)
    assert saved and saved[0][0] == UID and saved[0][1] == "town"
