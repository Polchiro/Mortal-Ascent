"""Mining in the Ironvein Quarry (docs/world.md "The Ironvein Quarry"): the land and its road, the seams, and the
referee (web/mine_play.py): what a seam holds is fixed when you start on it, the blows are checked, a seam pays once,
and a day gives forge.SEAMS_PER_DAY seams."""
import collections
import random

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import forge  # noqa: E402
from bot import db, materials  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402
from web import env, land, mine_play, overworld, quarry  # noqa: E402

UID = 781
NOW = 1_800_000_000.0


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "ma.db"))
    db.create_player(c, UID, "Miner", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    yield c
    c.close()


def mines(now):
    return mine_play.Mines(clock=lambda: now[0], rng_factory=lambda uid: random.Random(7))


def dig(m, conn, now, seam, blows=None):
    d, why = m.start(conn, UID, seam["id"], seam["x"], seam["y"])
    assert why is None, why
    now[0] += 3
    blows = [i * 600 for i in range(d["strikes"])] if blows is None else blows
    return d, m.finish(conn, UID, seam["id"], blows, seam["x"], seam["y"])


def pouch(conn):
    return {i["key"]: i["qty"] for i in db.get_items(conn, UID, "materials")}


# ── the land ──────────────────────────────────────────────────────────

def test_the_quarry_is_a_land_you_walk_to_from_the_crossroads():
    assert overworld.PLACES[quarry.KEY]["safe"] and "herbs" not in overworld.PLACES[quarry.KEY]
    out, back = overworld.ENTRANCES[("crossroads", "road_quarry")], overworld.ENTRANCES[(quarry.KEY, "north")]
    assert out["to"] == quarry.KEY and back["to"] == "crossroads"
    assert land.OPPOSITE[out["side"]] == back["side"]
    assert overworld.walkable("crossroads", *overworld.arrival("crossroads", "road_quarry"))
    assert overworld.walkable(quarry.KEY, *overworld.arrival(quarry.KEY, "north"))


def test_every_seam_spot_can_be_reached_and_no_piece_walls_you_in():
    G = 2
    st = land.LANDS[quarry.KEY]["start"]
    seen = {(round(st[0] * G), round(st[1] * G))}
    q = collections.deque(seen)
    while q:
        x, y = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and quarry.walkable(n[0] / G, n[1] / G):
                seen.add(n)
                q.append(n)
    for sx, sy in quarry.SPOTS:                       # somewhere to stand within reach of each seam
        assert any((x / G - sx) ** 2 + (y / G - sy) ** 2 <= (mine_play.REACH * 0.9) ** 2 for x, y in seen), (sx, sy)
    assert len(quarry.SPOTS) > mine_play.SEAM_COUNT and len(set(quarry.SPOTS)) == len(quarry.SPOTS)
    assert all(name in env.ASSETS and name in env.catalog() for name, *_ in quarry.PLACED)
    assert len(quarry.pieces()) == len(quarry.PLACED)


# ── the numbers ───────────────────────────────────────────────────────

def test_what_each_kind_of_seam_gives():
    rng = random.Random(1)
    got = collections.Counter()
    for _ in range(4000):
        items = materials.roll_seam("iron", "Mortal", rng)
        assert items[0]["key"] == "base:weapon:1" and 1 <= items[0]["qty"] <= 2
        for i in items[1:]:
            got[i["key"]] += 1
    assert set(got) <= {"fuel:1", "essence:metal:shard"}
    assert 0.07 < got["fuel:1"] / 4000 < 0.13 and 0.01 < got["essence:metal:shard"] / 4000 < 0.035
    coal = [materials.roll_seam("coal", "Martial King", rng) for _ in range(2000)]
    assert all(len(c) == 1 and c[0]["key"] == "fuel:5" and c[0]["qty"] in (1, 2) for c in coal)
    assert 0.03 < sum(c[0]["qty"] == 2 for c in coal) / 2000 < 0.08
    jade = materials.roll_seam("jade", "Martial Expert", rng)
    assert [(i["key"], i["qty"]) for i in jade] == [("base:artifact:3", 1)]
    assert abs(sum(forge.SEAM_KINDS.values()) - 1) < 1e-9 and forge.SEAMS_PER_DAY == 24
    assert materials.seam_gives("iron", "Mortal") == "Iron Ore" and materials.seam_gives("jade", "Mortal") == "Green Jade"


# ── the referee ───────────────────────────────────────────────────────

def test_a_seam_pays_what_was_planned_when_you_started(conn):
    now = [NOW]
    m = mines(now)
    seam = m.view(conn, UID)["seams"][0]
    assert len(m.view(conn, UID)["seams"]) == mine_play.SEAM_COUNT
    d, why = m.start(conn, UID, seam["id"], seam["x"], seam["y"])
    planned = [(i["key"], i["qty"]) for i in m._m[UID].dig.holds]
    assert d["strikes"] == forge.SEAMS[seam["kind"]]["strikes"] and "holds" not in d
    now[0] += 3
    got, why = m.finish(conn, UID, seam["id"], [i * 500 for i in range(d["strikes"])], seam["x"], seam["y"])
    assert why is None and pouch(conn) == dict(planned)
    assert [(g["name"], g["qty"]) for g in got["got"]] and got["left"] == forge.SEAMS_PER_DAY - 1
    assert seam["id"] not in [s["id"] for s in m.view(conn, UID)["seams"]]            # dug out; another opens later
    assert len(m.view(conn, UID)["seams"]) == mine_play.SEAM_COUNT - 1
    now[0] += mine_play.REGROW[1] + 1
    assert len(m.view(conn, UID)["seams"]) == mine_play.SEAM_COUNT


def test_the_blows_are_checked(conn):
    now = [NOW]
    m = mines(now)
    seam = m.view(conn, UID)["seams"][0]
    d, _ = m.start(conn, UID, seam["id"], seam["x"], seam["y"])
    n = d["strikes"]
    assert m.finish(conn, UID, seam["id"], [0], seam["x"], seam["y"])[0] is None                 # too few
    now[0] += 3
    assert m.finish(conn, UID, seam["id"], [i * 100 for i in range(n)], seam["x"], seam["y"])[0] is None   # too fast
    assert m.finish(conn, UID, seam["id"], ["x"] * n, seam["x"], seam["y"])[0] is None
    assert m.finish(conn, UID, seam["id"], [i * 500 for i in range(n)], seam["x"] + 5, seam["y"])[0] is None  # far
    assert pouch(conn) == {}
    assert m.finish(conn, UID, seam["id"], [i * 500 for i in range(n)], seam["x"], seam["y"])[0]
    assert m.finish(conn, UID, seam["id"], [i * 500 for i in range(n)], seam["x"], seam["y"])[0] is None   # once


def test_blows_sent_at_once_are_refused_until_the_dig_has_taken_its_time(conn):
    now = [NOW]
    m = mines(now)
    seam = m.view(conn, UID)["seams"][0]
    d, _ = m.start(conn, UID, seam["id"], seam["x"], seam["y"])
    blows = [i * 500 for i in range(d["strikes"])]
    assert m.finish(conn, UID, seam["id"], blows, seam["x"], seam["y"])[0] is None     # no time has passed here
    now[0] += 2.5
    assert m.finish(conn, UID, seam["id"], blows, seam["x"], seam["y"])[0]


def test_a_day_gives_only_so_many_seams(conn):
    now = [NOW]
    m = mines(now)
    for _ in range(forge.SEAMS_PER_DAY):
        now[0] += mine_play.REGROW[1] + 1
        seam = m.view(conn, UID)["seams"][0]
        _, (got, why) = dig(m, conn, now, seam)
        assert got, why
    v = m.view(conn, UID)
    assert v["left"] == 0 and all(s["spent"] for s in v["seams"])
    seam = v["seams"][0]
    assert m.start(conn, UID, seam["id"], seam["x"], seam["y"])[0] is None
    now[0] += 86400                                                         # the next day (UTC)
    assert m.view(conn, UID)["left"] == forge.SEAMS_PER_DAY


def test_a_dig_left_half_done_waits_then_closes(conn):
    now = [NOW]
    m = mines(now)
    seam = m.view(conn, UID)["seams"][0]
    m.start(conn, UID, seam["id"], seam["x"], seam["y"])
    holds = m._m[UID].dig.holds
    now[0] += 60
    assert any(s["cracked"] for s in m.view(conn, UID)["seams"])
    m.start(conn, UID, seam["id"], seam["x"], seam["y"])
    assert m._m[UID].dig.holds is holds                 # picked back up: the same plan, nothing rolled again
    now[0] += mine_play.KEEP + 1
    assert not any(s["cracked"] for s in m.view(conn, UID)["seams"])


def test_the_seams_kinds_follow_their_shares():
    m = mine_play.Mines(rng_factory=lambda uid: random.Random(3))
    mm, rng = m._miner(1)
    kinds = collections.Counter(m._open(mine_play.Miner(), rng, 0)["kind"] for _ in range(6000))
    for k, share in forge.SEAM_KINDS.items():
        assert abs(kinds[k] / 6000 - share) < 0.03


# ── the website ───────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Miner", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, appearance='{"gender": "female"}')
    c.close()
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "miner", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=path, session_secret="s"))
    cl = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    import urllib.parse
    r = cl.get("/login")
    state = urllib.parse.parse_qs(urllib.parse.urlparse(r.headers["location"]).query)["state"][0]
    cl.get("/callback", params={"code": "c", "state": state})
    cl.app_ = app
    cl.path = path
    return cl


def test_mining_through_the_website(client):
    world = client.app_.state.world
    c = db.connect(client.path)
    world.enter(c, UID, quarry.KEY)
    st = world.state(c, UID, quarry.KEY)
    assert st["herbs"] == [] and st["beasts"] == [] and len(st["mine"]["seams"]) == mine_play.SEAM_COUNT
    seam = st["mine"]["seams"][0]
    w = world.walker(UID)
    w.x, w.y = seam["x"] + 1.0, seam["y"]
    c.close()
    assert client.get(f"/wild/{quarry.KEY}").status_code == 200
    far = client.post("/world/mine", data={"id": seam["id"], "x": seam["x"] + 9, "y": seam["y"]}).json()
    assert far["error"] and not far.get("dig")
    r = client.post("/world/mine", data={"id": seam["id"], "x": w.x, "y": w.y}).json()
    assert r["dig"]["strikes"] in (3, 5) and r["dig"]["gives"]
    world.mines._m[UID].dig.began -= 5
    blows = ",".join(str(i * 600) for i in range(r["dig"]["strikes"]))
    out = client.post("/world/mine/done", data={"id": seam["id"], "blows": blows, "x": w.x, "y": w.y}).json()
    assert out["got"]["got"] and out["world"]["mine"]["left"] == forge.SEAMS_PER_DAY - 1
    c = db.connect(client.path)
    assert db.get_items(c, UID, "materials") and db.daily_count(c, UID, mine_play.COUNT) == 1
    c.close()
