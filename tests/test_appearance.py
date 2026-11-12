"""Character appearance (docs/appearance.md): choosing a look, paying for changes, pictures, website and cards."""
import io
import urllib.parse

import pytest
from PIL import Image

import looks
from bot import appearance, db
from bot import player as rules

UID = 791


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(looks, "CACHE", str(tmp_path / "looks_cache"))


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.create_player(c, UID, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return c


def me(conn):
    return db.get_player(conn, UID)


def test_new_and_existing_players_have_no_look_yet(conn):
    p = me(conn)
    assert p["appearance"] is None and p["appearance_changes"] == 0 and looks.of_player(p) is None


def test_every_option_has_its_picture_and_hair_mask():
    for g, hairs in looks.HAIRSTYLES.items():
        for h, _ in hairs:
            img = looks.render({"gender": g, "hair": h, "color": "silver"})
            assert img.size == (260, 540)


def test_first_look_is_free_then_moon_pearls(conn):
    stats_before = {k: me(conn)[k] for k in ("strength", "vitality", "spirit", "realm", "layer", "lotus_coins")}
    ok, msg = appearance.choose(conn, UID, "female", "braid", "azure")
    assert ok and "Single Braid" in msg and "Moon Pearls" not in msg
    p = me(conn)
    assert looks.of_player(p) == {"gender": "female", "hair": "braid", "color": "azure"}
    assert p["appearance_changes"] == 1 and p["moon_pearls"] == 0
    assert {k: p[k] for k in stats_before} == stats_before                 # a picture only

    ok, msg = appearance.choose(conn, UID, "male", "topknot", "black")     # no pearls: refused, nothing changes
    assert not ok and "200 Moon Pearls" in msg and looks.of_player(me(conn))["gender"] == "female"

    db.update_player(conn, UID, moon_pearls=250)
    ok, msg = appearance.choose(conn, UID, "male", "topknot", "black")
    assert ok and "200 Moon Pearls" in msg
    p = me(conn)
    assert p["moon_pearls"] == 50 and p["appearance_changes"] == 2 and looks.of_player(p)["hair"] == "topknot"
    assert any(e["reason"] == "Appearance change" for e in db.ledger(conn, UID))


def test_bad_or_unchanged_choices_are_refused(conn):
    assert not appearance.choose(conn, UID, "female", "topknot", "silver")[0]     # a male hairstyle
    assert not appearance.choose(conn, UID, "male", "topknot", "green")[0]
    assert not appearance.choose(conn, UID, "robot", "topknot", "silver")[0]
    assert appearance.choose(conn, UID, "male", "long", "silver")[0]
    ok, msg = appearance.choose(conn, UID, "male", "long", "silver")
    assert not ok and "already" in msg and me(conn)["appearance_changes"] == 1


def test_a_broken_stored_look_counts_as_none():
    assert looks.parse("{not json") is None and looks.parse('{"gender": "male", "hair": "x", "color": "silver"}') is None


def test_colour_changes_only_the_hair():
    import numpy as np
    plain = np.asarray(looks.render({"gender": "female", "hair": "ponytail", "color": "silver"}))
    red = np.asarray(looks.render({"gender": "female", "hair": "ponytail", "color": "crimson"}))
    outside = np.asarray(Image.open(f"{looks.ART}/female_ponytail_hair.png").convert("L")) == 0
    moved = (plain != red).any(-1)[outside]
    assert moved.mean() < 0.02                                # outside the hair (bar its soft edge) nothing moves


def test_face_for_cards_is_cached_png():
    look = {"gender": "male", "hair": "topknot", "color": "brown"}
    data = looks.face_png(look)
    assert Image.open(io.BytesIO(data)).size == (looks.FACE_SIZE, looks.FACE_SIZE)
    assert looks.face_png(look) == data


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


def test_look_pictures_are_served(client):
    r = client.get("/look/female_crown_bun_azure.webp")
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    r = client.get("/look/male_long_crimson_face.png")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert client.get("/look/female_topknot_silver.webp").status_code == 404
    assert client.get("/look/../../etc/passwd").status_code == 404


def test_profile_invites_a_free_look_then_shows_it(client):
    page = client.get("/profile").text
    assert "Choose your look" in page and "/art/portraits/cultivator_default.webp" in page
    page = client.get("/appearance").text
    assert "Your first look is <b>free</b>" in page and "Decide later" in page and "Single Braid" in page
    r = client.post("/appearance", data={"gender": "female", "hair": "braid", "color": "azure"})
    assert r.headers["location"] == "/profile"
    page = client.get("/profile").text
    assert "/look/female_braid_azure.webp" in page and "Change look" in page and "new look is set" in page
    page = client.get("/appearance").text
    assert "200 Moon Pearls" in page and "disabled" in page              # no pearls yet
    client.post("/appearance", data={"gender": "male", "hair": "topknot", "color": "silver"})
    assert "200 Moon Pearls" in client.get("/appearance").text
    assert looks.of_player(player_at(client.path))["hair"] == "braid"


def test_profile_page_scripts_stay_out_of_the_title(client):
    page = client.get("/profile").text
    title = page.split("<title>")[1].split("</title>")[0]
    assert "<script" not in title and 'class="hallbg"' in page


def test_logged_out_cannot_choose(client):
    from fastapi.testclient import TestClient
    fresh = TestClient(client.app, base_url="http://localhost:8000", follow_redirects=False)
    assert fresh.post("/appearance", data={"gender": "male", "hair": "long", "color": "silver"}).status_code == 303
    assert player_at(client.path)["appearance"] is None
