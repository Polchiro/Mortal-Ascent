"""The website: Discord login and the profile page (docs/web.md). Discord itself is faked."""
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from bot import db  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402
from web.profile import eta_text, number, ordinal, profile_view  # noqa: E402

UID = 123456789012345678


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, lotus_coins=12480, moon_pearls=96)
    c.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=db_path, session_secret="test")
    seen = {}

    def fake_exchange(client_id, client_secret, redirect_uri, code):
        seen["exchange"] = (client_id, client_secret, redirect_uri, code)
        if code == "bad":
            raise oauth.LoginError("Discord did not accept the login. Please try again.")
        return "token-" + code

    def fake_user(token):
        uid = UID if token == "token-good" else 42
        return {"id": uid, "username": "shoaib", "avatar": None}

    monkeypatch.setattr(oauth, "exchange_code", fake_exchange)
    monkeypatch.setattr(oauth, "fetch_user", fake_user)
    c = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    c.seen = seen
    return c


def start_login(client):
    r = client.get("/login")
    assert r.status_code == 303
    return urllib.parse.parse_qs(urllib.parse.urlparse(r.headers["location"]).query)


def log_in(client, code="good"):
    q = start_login(client)
    return client.get("/callback", params={"code": code, "state": q["state"][0]})


def test_front_page_and_login_redirect(client):
    r = client.get("/")
    assert r.status_code == 200 and "Continue with Discord" in r.text and 'href="/login"' in r.text
    q = start_login(client)
    assert q["client_id"] == ["cid"] and q["scope"] == ["identify"] and q["response_type"] == ["code"]
    assert q["redirect_uri"] == ["http://localhost:8000/callback"] and q["state"][0]


def test_login_shows_the_real_character(client):
    r = log_in(client)
    assert r.status_code == 303 and r.headers["location"] == "/profile"
    assert client.seen["exchange"] == ("cid", "secret", "http://localhost:8000/callback", "good")
    page = client.get("/profile")
    assert page.status_code == 200
    assert "Shoaib" in page.text and "Mortal" in page.text and "12,480" in page.text and "96" in page.text
    assert "Iron Fist" in page.text and "/art/icons/tech/iron_fist.webp" in page.text
    assert client.get("/").headers["location"] == "/profile"          # already logged in


def test_profile_needs_a_login(client):
    r = client.get("/profile")
    assert r.status_code == 303 and r.headers["location"] == "/"
    assert client.get("/api/me").status_code == 401


def test_wrong_or_missing_state_is_refused(client):
    start_login(client)
    assert client.get("/callback", params={"code": "good", "state": "forged"}).status_code == 400
    assert client.get("/callback", params={"code": "good", "state": ""}).status_code == 400
    assert client.get("/profile").status_code == 303                   # not logged in
    # a state can only be used once
    q = start_login(client)
    assert client.get("/callback", params={"code": "good", "state": q["state"][0]}).status_code == 303
    client.post("/logout")
    assert client.get("/callback", params={"code": "good", "state": q["state"][0]}).status_code == 400


def test_cancel_on_discord_goes_back_with_a_message(client):
    q = start_login(client)
    r = client.get("/callback", params={"error": "access_denied", "state": q["state"][0]})
    assert r.headers["location"] == "/"
    assert "Nothing was shared" in client.get("/").text


def test_discord_refusing_the_code_shows_an_error(client):
    r = log_in(client, code="bad")
    assert r.status_code == 502 and "try again" in r.text
    assert client.get("/profile").status_code == 303


def test_account_without_a_character_is_told_to_start(client):
    log_in(client, code="nochar")
    page = client.get("/profile")
    assert page.status_code == 200 and "/start" in page.text and "No character yet" in page.text
    assert client.get("/api/me").json()["profile"] is None


def test_api_me_and_logout(client):
    log_in(client)
    me = client.get("/api/me").json()
    assert me["user"]["id"] == str(UID) and me["profile"]["realm"] == "Mortal" and me["profile"]["coins"] == "12,480"
    r = client.post("/logout")
    assert r.status_code == 303 and client.get("/profile").status_code == 303


def test_art_is_served_but_not_the_rest_of_the_repo(client):
    assert client.get("/art/icons/tech/iron_fist.webp").status_code == 200
    assert client.get("/art/scenes/duel_ring_left.png").status_code == 200
    assert client.get("/static/style.css").status_code == 200
    for path in ("/art/../bot/db.py", "/.env", "/mortal_ascent.db", "/docs"):
        assert client.get(path).status_code == 404


def test_profile_view_matches_the_bot(db_path):
    c = db.connect(db_path)
    v = profile_view(c, UID, username="shoaib")
    from bot.sheet import data as sheet
    d = sheet.profile_data(c, UID, username="shoaib")
    assert v["realm"] == d["realm"] and v["phase"] == d["phase"] and v["qi_cap"] == number(d["qi"]["capacity"])
    assert v["hp"] == number([a for a in d["attributes"] if a["key"] == "hp"][0]["final"])
    assert profile_view(c, 1) is None


def test_helpers():
    assert eta_text("2h 33m") == "full in 2h 33m" and eta_text("Ready now") == "Ready now" and eta_text("") is None
    assert number(12480) == "12,480" and number(3.125) == "3.1" and number(8.0) == "8"
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22)] == ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd"]
    url = oauth.authorize_url("cid", "http://localhost:8000/callback", "abc")
    assert url.startswith(oauth.AUTHORIZE_URL) and "scope=identify" in url and "state=abc" in url
    assert oauth.avatar_url(1, None) is None and oauth.avatar_url(1, "h").endswith("/avatars/1/h.png?size=256")


def test_wrong_address_moves_to_the_redirect_address(db_path):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=db_path, session_secret="t",
                                redirect_uri="http://localhost:8765/callback")
    c = TestClient(web_app.create_app(settings), base_url="http://127.0.0.1:8765", follow_redirects=False)
    for path in ("/", "/login"):
        r = c.get(path)
        assert r.status_code == 303 and r.headers["location"] == "http://localhost:8765" + path



def give(path, uid, *entries):
    from bot import item_catalog, loot
    c = db.connect(path)
    for e in entries:
        loot.store(c, uid, item_catalog.make(e, 3 if e.startswith("herb") else 1))
    c.close()


def test_inventory_needs_a_login(client):
    r = client.get("/inventory")
    assert r.status_code == 303 and r.headers["location"] == "/"


def test_inventory_shows_the_bag_with_pictures_and_details(client, db_path):
    give(db_path, UID, "weapon:spirit:sword", "herb:Mystic:qi", "chest:epic", "pill:qi:Yellow")
    log_in(client)
    page = client.get("/inventory")
    assert page.status_code == 200 and "Weapons" in page.text and "Herbs" in page.text
    assert "/art/icons/gear/azure_frost_sword.webp" in page.text and "Azure Frost Sword" in page.text
    assert "Weapons only give stat buffs" in page.text                 # the Inspect panel, first item
    herbs = client.get("/inventory?tab=herbs")
    assert "Moon Mushroom" in herbs.text and "×3" in herbs.text and "Refine it with /craft" in herbs.text
    chests = client.get("/inventory?tab=chests")
    assert "/art/chests/epic.png" in chests.text and "Epic Chest" in chests.text
    assert client.get("/art/chests/epic.png").status_code == 200


def test_inventory_picks_an_item_and_ignores_other_players_items(client, db_path):
    give(db_path, UID, "pill:qi:Yellow", "pill:mending:Mortal")
    c = db.connect(db_path)
    db.create_player(c, 42, "Other", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    c.close()
    give(db_path, 42, "pill:heaven_defying")
    c = db.connect(db_path)
    mine = [i["id"] for i in db.get_items(c, UID, "pills")]
    theirs = db.get_items(c, 42, "pills")[0]["id"]
    c.close()
    log_in(client)
    second = client.get(f"/inventory?tab=pills&item={mine[1]}")
    assert 'class="tile sel"' in second.text and f"item={mine[1]}" in second.text
    other = client.get(f"/inventory?tab=pills&item={theirs}")
    assert other.status_code == 200 and "Heaven-Defying" not in other.text


def test_inventory_unknown_tab_and_empty_tab(client):
    log_in(client)
    assert client.get("/inventory?tab=../../etc").status_code == 200
    assert "Nothing here yet" in client.get("/inventory?tab=chests").text
