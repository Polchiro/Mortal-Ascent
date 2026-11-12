"""Character appearance (docs/appearance.md): choosing male or female, paying for changes, pictures, website."""
import os
import urllib.parse

import pytest
from PIL import Image

import looks
from bot import appearance, db
from bot import player as rules

UID = 791
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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
    assert looks.portrait(None) == "/art/portraits/hero_male.webp"           # the default painting


def test_every_gender_has_its_paintings():
    for g in looks.GENDERS:
        look = {"gender": g}
        full = Image.open(os.path.join(ROOT, looks.portrait(look).lstrip("/")))
        fight = Image.open(os.path.join(ROOT, looks.fighter(look).lstrip("/")))
        face = Image.open(os.path.join(ROOT, looks.face(look).lstrip("/")))
        assert full.mode == "RGBA" and fight.size == (1024, 559)            # the fight canvas the poses use
        assert face.size[0] == face.size[1]


def test_first_look_is_free_then_moon_pearls(conn):
    stats_before = {k: me(conn)[k] for k in ("strength", "vitality", "spirit", "realm", "layer", "lotus_coins")}
    ok, msg = appearance.choose(conn, UID, "female")
    assert ok and "Female" in msg and "Moon Pearls" not in msg
    p = me(conn)
    assert looks.of_player(p) == {"gender": "female"}
    assert p["appearance_changes"] == 1 and p["moon_pearls"] == 0
    assert {k: p[k] for k in stats_before} == stats_before                 # a picture only

    ok, msg = appearance.choose(conn, UID, "male")                # no pearls: refused, nothing changes
    assert not ok and "200 Moon Pearls" in msg and looks.of_player(me(conn))["gender"] == "female"

    db.update_player(conn, UID, moon_pearls=250)
    ok, msg = appearance.choose(conn, UID, "male")
    assert ok and "200 Moon Pearls" in msg
    p = me(conn)
    assert p["moon_pearls"] == 50 and p["appearance_changes"] == 2 and looks.of_player(p) == {"gender": "male"}
    assert any(e["reason"] == "Appearance change" for e in db.ledger(conn, UID))


def test_bad_or_unchanged_choices_are_refused(conn):
    assert not appearance.choose(conn, UID, "robot")[0]
    assert appearance.choose(conn, UID, "male")[0]
    ok, msg = appearance.choose(conn, UID, "male")
    assert not ok and "already" in msg and me(conn)["appearance_changes"] == 1


def test_a_broken_stored_look_counts_as_none():
    assert looks.parse("{not json") is None and looks.parse('{"gender": "x"}') is None


def test_a_look_saved_with_a_hairstyle_keeps_its_gender(conn):
    db.update_player(conn, UID, appearance='{"color": "azure", "gender": "female", "hair": "braid"}', appearance_changes=1)
    assert looks.of_player(me(conn)) == {"gender": "female"}
    assert looks.portrait(looks.of_player(me(conn))) == "/art/portraits/hero_female.webp"
    assert not appearance.choose(conn, UID, "female")[0]                   # same look: nothing charged


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


def test_paintings_are_served(client):
    for g in looks.GENDERS:
        for url in (looks.portrait({"gender": g}), looks.fighter({"gender": g}), looks.face({"gender": g})):
            r = client.get(url)
            assert r.status_code == 200 and r.headers["content-type"] == "image/webp"


def test_profile_invites_a_free_look_then_shows_it(client):
    page = client.get("/profile").text
    assert "Choose your look" in page and "/art/portraits/hero_male.webp" in page
    page = client.get("/appearance").text
    assert "Your first look is <b>free</b>" in page and "Decide later" in page and "Female" in page
    assert "Hairstyle" not in page
    r = client.post("/appearance", data={"gender": "female"})
    assert r.headers["location"] == "/profile"
    page = client.get("/profile").text
    assert "/art/portraits/hero_female.webp" in page and "Change look" in page and "new look is set" in page
    page = client.get("/appearance").text
    assert "200 Moon Pearls" in page and "disabled" in page              # no pearls yet
    client.post("/appearance", data={"gender": "male"})
    assert "200 Moon Pearls" in client.get("/appearance").text
    assert looks.of_player(player_at(client.path)) == {"gender": "female"}


def test_profile_page_scripts_stay_out_of_the_title(client):
    page = client.get("/profile").text
    title = page.split("<title>")[1].split("</title>")[0]
    assert "<script" not in title and 'class="hallbg"' in page


def test_logged_out_cannot_choose(client):
    from fastapi.testclient import TestClient
    fresh = TestClient(client.app, base_url="http://localhost:8000", follow_redirects=False)
    assert fresh.post("/appearance", data={"gender": "male"}).status_code == 303
    assert player_at(client.path)["appearance"] is None


def test_the_stylesheet_has_no_unclosed_blocks():
    css = open(os.path.join(ROOT, "web", "static", "style.css"), encoding="utf-8").read()
    depth = 0
    for ch in css:
        depth += (ch == "{") - (ch == "}")
        assert depth >= 0
    assert depth == 0                                                     # one open "{" hides every rule after it
