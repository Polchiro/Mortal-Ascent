"""Opening chests on the website (web/chest_play.py, web/chest_routes.py, docs/web.md "Opening a chest").
Every chest is rolled and granted by the bot's own functions; these check the bag-space guard, Open all, one opening
per press, rewards still waiting, and the pages."""
import os
import random
import urllib.parse

import pytest

import forge
from bot import db, loot
from bot import player as rules
from web import chest_play as cp

A = 333
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def give(conn, uid, tier, n=1):
    ch = loot.chest(tier)
    db.add_item(conn, uid, ch["category"], ch["key"], ch["name"], ch["grade"], n)
    return [it for it in db.get_items(conn, uid, "chests") if it["key"] == tier][0]["id"]


def fill(conn, uid, leave):
    """Fill the bag with swords until `leave` slots are free."""
    cap = db.get_player(conn, uid)["bag_capacity"]
    for i in range(cap - db.slots_used(conn, uid) - leave):
        db.add_item(conn, uid, "weapons", "iron_sword", f"Iron Sword {i}", "ordinary", 1, None)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "ma.db"))
    db.create_player(c, A, "Lin Yue", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return c


def test_the_most_a_chest_can_need():
    p = {"realm": "Mortal", "artifacts": []}
    assert cp.max_new_slots(p, "common") == 4           # manual, weapon, armour, artifact (no Heaven-Defying Pill)
    assert cp.max_new_slots(p, "mythic") == 5           # ...and the pill
    assert not forge.MATERIALS_USE_BAG_SLOTS             # materials go to the pouch


def test_opening_is_the_bots_opening(conn):
    item = give(conn, A, "rare", 2)
    coins = db.get_player(conn, A)["lotus_coins"]
    r, why = cp.Chests(rng=random.Random(4)).open(conn, A, item)
    assert why is None and r["opened"] == 1 and r["left"] == 1
    c = r["chests"][0]
    assert db.get_player(conn, A)["lotus_coins"] == coins + c["coins"] == coins + r["coins"]
    ranks = [x["rank"] for x in c["rewards"]]
    assert ranks == sorted(ranks)                                                   # worst first, the best last
    assert db.unclaimed_chests(conn, A) == []                                       # granted, not left waiting
    assert r["color"] == "rgb({}, {}, {})".format(*forge.RARITY_COLORS["Rare"]) and r["seals"] == 1


def test_lucky_rolls_bring_the_rare_ones_out_last(conn):
    class Lucky(random.Random):
        def random(self):
            return 0.0
    item = give(conn, A, "mythic")
    r, _ = cp.Chests(rng=Lucky(1)).open(conn, A, item)
    rewards = r["chests"][0]["rewards"]
    assert rewards[-1]["rarity"] == "Mythical" and rewards[-1]["flavor"]
    assert r["best"] == forge.RARITIES.index("Mythical") and r["summary"][0]["rarity"] == "Mythical"


def test_the_bag_guard(conn):
    item = give(conn, A, "epic", 3)
    fill(conn, A, 2)
    r, why = cp.Chests().open(conn, A, item)
    assert r is None and "2 free slots" in why and "make room" in why
    assert [it["qty"] for it in db.get_items(conn, A, "chests")] == [3]             # nothing was opened


def test_open_all_opens_what_fits(conn):
    item = give(conn, A, "common", 30)
    fill(conn, A, 9)                                                              # room for 9 // 4 = 2
    r, _ = cp.Chests(rng=random.Random(2)).open(conn, A, item, count=30)
    assert r["opened"] == 2 and r["asked"] == 30 and r["left"] == 28


def test_open_all_stops_at_twenty(conn):
    db.update_player(conn, A, bag_capacity=200)                                   # room for far more than 20
    item = give(conn, A, "common", 30)
    r, _ = cp.Chests(rng=random.Random(2)).open(conn, A, item, count=30)
    assert r["opened"] == cp.OPEN_ALL_MAX == 20 and r["left"] == 10
    total = sum(x["qty"] for x in r["summary"])
    assert total == sum(x["qty"] for c in r["chests"] for x in c["rewards"])       # grouped, nothing dropped


def test_one_opening_per_press(conn):
    item = give(conn, A, "uncommon", 3)
    ch = cp.Chests(rng=random.Random(5))
    first = ch.open(conn, A, item, nonce="n1")
    again = ch.open(conn, A, item, nonce="n1")
    assert again == first and db.get_items(conn, A, "chests")[0]["qty"] == 2
    ch.open(conn, A, item, nonce="n2")
    assert db.get_items(conn, A, "chests")[0]["qty"] == 1


def test_not_a_chest(conn):
    db.add_item(conn, A, "weapons", "iron_sword", "Iron Sword", "ordinary", 1, None)
    sword = db.get_items(conn, A, "weapons")[-1]["id"]
    assert cp.Chests().open(conn, A, sword) == (None, "That chest is no longer in your bag.")
    assert cp.Chests().open(conn, A, 999999)[0] is None


def test_rewards_still_waiting_are_collected(conn):
    item = give(conn, A, "rare")
    pending = loot.begin_chest(conn, A, item, rng=random.Random(1))             # a reveal nobody finished
    s = cp.shelf(conn, A)
    assert [w["id"] for w in s["waiting"]] == [pending["id"]]
    r, why = cp.Chests().collect(conn, A)
    assert why is None and r["opened"] == 1 and db.unclaimed_chests(conn, A) == []
    assert cp.Chests().collect(conn, A) == (None, "Nothing is waiting.")


def test_the_shelf(conn):
    give(conn, A, "legendary", 2)
    give(conn, A, "common", 1)
    s = cp.shelf(conn, A)
    by = {t["key"]: t for t in s["tiers"]}
    assert [t["key"] for t in s["tiers"]] == loot.CHEST_ORDER
    assert by["legendary"]["qty"] == 2 and by["common"]["qty"] == 1 and by["epic"]["qty"] == 0
    assert by["legendary"]["seals"] == 3 and by["common"]["seals"] == 0 and s["total"] == 3


def test_the_art_is_there():
    for f in ("shelf.jpg", "vault.jpg", "vault.mp4", "vault.mp3", "burst.mp4", "burst.mp3", "glow_in.mp4", "glow.mp4",
              "glow.mp3", "slip.webp", "lid.webp"):
        assert os.path.exists(os.path.join(ROOT, "art", "chest", f)), f


def test_every_chest_has_a_closed_and_an_open_picture():
    from web import inventory
    for tier in loot.CHEST_ORDER:
        assert cp.open_picture(tier).startswith(f"/art/chest/{tier}_open.webp")
        ch = loot.chest(tier)
        assert inventory.item_picture({"category": ch["category"], "key": ch["key"]}).startswith(f"/art/chest/{tier}.webp")


def test_the_shelf_and_the_vault_know_the_open_picture(conn):
    give(conn, A, "epic", 1)
    by = {t["key"]: t for t in cp.shelf(conn, A)["tiers"]}
    assert by["epic"]["open"].startswith("/art/chest/epic_open.webp")


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
    give(c, UID, "rare", 3)
    c.close()
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=path, session_secret="test")
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "token")
    monkeypatch.setattr(oauth, "fetch_user", lambda token: {"id": UID, "username": "shoaib", "avatar": None})
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
    cl.get("/callback", params={"code": "good", "state": q["state"][0]})
    cl.db_path = path
    return cl


def test_the_bag_leads_to_the_shelf(client):
    page = client.get("/inventory?tab=chests").text
    assert "/chests?open=" in page and "Treasure Shelf" in page


def test_opening_through_the_routes(client):
    page = client.get("/chests?from=/inventory?tab=chests")
    assert page.status_code == 200 and "chests.js" in page.text and "THE TREASURE SHELF" in page.text
    s = client.get("/chests/shelf").json()
    rare = [t for t in s["tiers"] if t["key"] == "rare"][0]
    out = client.post("/chests/open", json={"item": rare["item"], "count": 2, "nonce": "a"}).json()
    assert out["error"] is None and out["result"]["opened"] == 2 and out["shelf"]["total"] == 1
    again = client.post("/chests/open", json={"item": rare["item"], "count": 2, "nonce": "a"}).json()
    assert again["result"] == out["result"] and again["shelf"]["total"] == 1
    bad = client.post("/chests/open", json={"item": "x"}).json()
    assert bad["result"] is None and bad["error"]


def test_back_only_goes_to_this_site(client):
    client.get("/chests?from=https://evil.example")
    assert 'href="/inventory?tab=chests"' in client.get("/chests").text


def test_the_pages_need_a_login(tmp_path):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=str(tmp_path / "x.db"), session_secret="t")
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    assert cl.get("/chests").headers["location"] == "/"
    assert cl.get("/chests/shelf").json() == {"gone": True}
    assert cl.post("/chests/open", json={"item": 1}).json() == {"gone": True}
    assert cl.post("/chests/collect", json={}).json() == {"gone": True}
