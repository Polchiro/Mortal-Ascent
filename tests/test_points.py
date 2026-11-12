"""Strength and Vitality points (docs/attributes.md): earning, placing, resetting, fights and the website."""
import urllib.parse

import pytest

import stats
from bot import db, duel, points
from bot import player as rules

UID = 790


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.create_player(c, UID, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, realm="Martial Warrior", layer=6)            # 3 + 10 + 5 = 18 points
    return c


def me(conn):
    return db.get_player(conn, UID)


def test_one_point_per_layer_climbed():
    assert rules.attribute_points("Mortal", 1) == 0
    assert rules.attribute_points("Mortal", 3) == 2
    assert rules.attribute_points("Martial Apprentice", 1) == 3            # Mortal has three layers
    assert rules.attribute_points("Martial Warrior", 6) == 18
    assert rules.attribute_points("Martial Saint", 10) == 102


def test_existing_players_start_with_their_points_and_nothing_placed(conn):
    p = me(conn)
    assert p["strength"] == p["vitality"] == 0 and rules.unspent_points(p) == 18


def test_points_raise_attack_and_hp_on_top_of_the_realm(conn):
    before = rules.final_stats(me(conn))
    ok, msg = points.place(conn, UID, strength=10, vitality=8)
    assert ok and "+10 Strength" in msg and "+8 Vitality" in msg
    hp, atk, dfn = rules.base_stats("Martial Warrior", 6)
    after = rules.final_stats(me(conn))
    assert after == (round(hp * (1 + 8 * stats.VITALITY_HP)), round(atk * (1 + 10 * stats.STRENGTH_ATTACK)), dfn)
    assert after[2] == before[2]                                             # Defense untouched
    assert rules.unspent_points(me(conn)) == 0


def test_cannot_place_more_than_you_have_or_nothing(conn):
    assert points.place(conn, UID, strength=19)[0] is False
    assert points.place(conn, UID)[0] is False
    assert points.place(conn, UID, strength=-3, vitality=5)[0] is False
    assert points.place(conn, UID, strength="x")[0] is False
    assert me(conn)["strength"] == 0


def test_first_reset_is_free_then_moon_pearls(conn):
    points.place(conn, UID, strength=18)
    ok, msg = points.reset(conn, UID)
    assert ok and "free" in msg and me(conn)["strength"] == 0 and rules.unspent_points(me(conn)) == 18
    points.place(conn, UID, vitality=5)
    ok, msg = points.reset(conn, UID)                                        # no pearls
    assert not ok and "200 Moon Pearls" in msg and me(conn)["vitality"] == 5
    db.change_currency(conn, UID, "moon_pearls", 250, "test")
    ok, msg = points.reset(conn, UID)
    assert ok and me(conn)["vitality"] == 0 and me(conn)["moon_pearls"] == 50
    assert db.ledger(conn, UID, 1)[0]["reason"] == "Attribute reset"
    assert points.reset(conn, UID)[0] is False                              # nothing placed


def test_profile_sheet_lists_strength_and_vitality_as_sources(conn):
    from bot.sheet import attributes
    points.place(conn, UID, strength=4, vitality=2)
    vals = {a["key"]: a for a in attributes.attribute_values(me(conn))}
    assert ("Strength", 4 * stats.STRENGTH_ATTACK) in vals["attack"]["sources"]
    assert ("Vitality", 2 * stats.VITALITY_HP) in vals["hp"]["sources"]


def test_fair_duels_count_only_the_points_the_lower_level_earns(conn):
    points.place(conn, UID, strength=12, vitality=6)
    p = me(conn)
    hp, atk, _ = duel.fair_stats(p, [], None, "Martial Apprentice", 1)      # earns 3 points: 2 Str, 1 Vit
    bhp, batk, _ = rules.base_stats("Martial Apprentice", 1)
    assert atk == round(batk * (1 + 2 * stats.STRENGTH_ATTACK)) and hp == round(bhp * (1 + 1 * stats.VITALITY_HP))
    hp, atk, _ = duel.fair_stats(p, [], None, "Martial Warrior", 6)         # same level: all of them
    assert atk == round(rules.base_stats("Martial Warrior", 6)[1] * (1 + 12 * stats.STRENGTH_ATTACK))


def test_discord_reply_text(conn):
    from bot.client import attributes_text
    text = attributes_text(me(conn))
    assert "Points to place: 18" in text and "free the first time" in text


# ── website ──────────────────────────────────────────────────────────

@pytest.fixture
def client(tmp_path, monkeypatch):
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from web import app as web_app
    from web import discord_oauth as oauth
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, realm="Martial Warrior", layer=6)
    c.close()
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "s", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=path, session_secret="s"))
    tc = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(tc.get("/login").headers["location"]).query)
    tc.get("/callback", params={"code": "x", "state": q["state"][0]})
    tc.path = path
    return tc


def player_at(path):
    c = db.connect(path)
    p = db.get_player(c, UID)
    c.close()
    return p


def test_profile_panel_places_and_resets(client):
    page = client.get("/profile").text
    assert "Strength, Vitality &amp; Spirit" in page and "18 points to place" in page and "Place points" in page
    r = client.post("/profile/attributes", data={"strength": "5", "vitality": "3"})
    assert r.headers["location"] == "/profile#develop"
    p = player_at(client.path)
    assert (p["strength"], p["vitality"]) == (5, 3)
    page = client.get("/profile").text
    assert "You place" in page and "10 points to place" in page and "Strength" in page and "Reset for free" in page
    client.post("/profile/attributes", data={"strength": "99"})
    assert "only have" in client.get("/profile").text and player_at(client.path)["strength"] == 5
    client.post("/profile/attributes/reset")
    p = player_at(client.path)
    assert (p["strength"], p["vitality"], p["attribute_resets"]) == (0, 0, 1)
    client.post("/profile/attributes", data={"vitality": "1"})
    assert "Reset for 200" in client.get("/profile").text


def test_logged_out_cannot_place(client):
    from fastapi.testclient import TestClient
    fresh = TestClient(client.app, base_url="http://localhost:8000", follow_redirects=False)
    assert fresh.post("/profile/attributes", data={"strength": "5"}).headers["location"] == "/"
    assert player_at(client.path)["strength"] == 0


def test_spirit_points_count_against_the_same_pool_and_reset(conn):
    ok, msg = points.place(conn, UID, strength=8, vitality=4, spirit=6)
    assert ok and "+6 Spirit" in msg and rules.unspent_points(me(conn)) == 0
    assert points.place(conn, UID, spirit=1)[0] is False
    assert rules.final_stats(me(conn))[1] == round(rules.base_stats("Martial Warrior", 6)[1] * (1 + 8 * stats.STRENGTH_ATTACK))
    points.reset(conn, UID)
    assert me(conn)["spirit"] == 0 and rules.unspent_points(me(conn)) == 18


def test_fights_start_with_spirit_battle_qi(conn):
    import battle
    points.place(conn, UID, spirit=5)
    from bot.expedition import Expedition
    e = Expedition(conn, UID)
    e.next_step()
    e.paths = {p: ("wild_beast", "x") for p in e.paths}
    e.choose("left")
    assert e.battle.fighters[0].max_bqi == battle.BATTLE_QI_START + 5 * stats.SPIRIT_BATTLE_QI


def test_profile_panel_places_spirit(client):
    client.post("/profile/attributes", data={"spirit": "4"})
    assert player_at(client.path)["spirit"] == 4
    assert "fights start with" in client.get("/profile").text
