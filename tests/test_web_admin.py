"""The admin panel on the website (web/admin_panel.py, web/admin_routes.py, docs/web.md "Admin panel"): Discord's
/admin tools for ADMIN_IDS only, doing the same through the same helpers in bot/admin.py."""
import re
import urllib.parse

import pytest

from bot import db
from bot import player as rules

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

ADMIN, OTHER = 111111111111111111, 222222222222222222


def client_for(path, uid, monkeypatch):
    settings = web_app.Settings(client_id="cid", client_secret="secret", db_path=path, session_secret="test")
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "token")
    monkeypatch.setattr(oauth, "fetch_user", lambda token: {"id": uid, "username": "x", "avatar": None})
    cl = TestClient(web_app.create_app(settings), base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(cl.get("/login").headers["location"]).query)
    cl.get("/callback", params={"code": "good", "state": q["state"][0]})
    return cl


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_IDS", str(ADMIN))
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    for uid, name in ((ADMIN, "Shoaib"), (OTHER, "Lin Yue")):
        db.create_player(c, uid, name, "Gifted", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    c.close()
    return path, monkeypatch


def do(cl, **form):
    page = cl.get(f"/admin?who={form.get('who', '')}").text
    token = re.search(r'name="token" value="([^"]+)"', page).group(1)
    r = cl.post("/admin/do", data=dict(form, token=token))
    assert r.status_code == 303
    return cl.get(r.headers["location"].split("#")[0]).text


def test_only_admins_see_it(setup):
    path, mp = setup
    other = client_for(path, OTHER, mp)
    assert other.get("/admin").status_code == 404
    assert other.post("/admin/do", data={"action": "reset"}).status_code == 404
    assert other.get("/admin/search?kind=item&q=jade").status_code == 404
    assert ">Admin<" not in other.get("/profile").text
    admin = client_for(path, ADMIN, mp)
    assert admin.get("/admin").status_code == 200 and ">Admin<" in admin.get("/profile").text


def test_giving_chests_and_items(setup):
    path, mp = setup
    cl = client_for(path, ADMIN, mp)
    page = do(cl, action="chest", tier="legendary", amount="5", who=str(OTHER))
    assert "Legendary Chest" in page and "×5" in page
    c = db.connect(path)
    assert [(i["key"], i["qty"]) for i in db.get_items(c, OTHER, "chests")] == [("legendary", 5)]
    do(cl, action="item", item="chest:mythic", amount="2", who=str(ADMIN))
    assert [(i["key"], i["qty"]) for i in db.get_items(c, ADMIN, "chests")] == [("mythic", 2)]
    rows = cl.get("/admin/search?kind=item&q=rare chest").json()
    assert rows[0]["id"] == "chest:rare"


def test_coins_realm_and_reset(setup):
    path, mp = setup
    cl = client_for(path, ADMIN, mp)
    do(cl, action="give", coins="5000", qi="10", who=str(OTHER))
    do(cl, action="realm", realm="Martial Expert", layer="4", who=str(OTHER))
    c = db.connect(path)
    p = db.get_player(c, OTHER)
    assert p["lotus_coins"] == rules.STARTING_LOTUS_COINS + 5000 and (p["realm"], p["layer"]) == ("Martial Expert", 4)
    db.update_player(c, OTHER, injured_until=10 ** 11)
    assert "Healed the injury" in do(cl, action="reset", who=str(OTHER))


def test_cooldowns_and_a_bad_token(setup):
    path, mp = setup
    cl = client_for(path, ADMIN, mp)
    page = do(cl, action="cooldowns", how="off", hours="2")
    assert "All cooldowns are off" in page and "Off for everyone" in page
    r = cl.post("/admin/do", data={"action": "reset", "token": "wrong"})
    assert "out of date" in cl.get(r.headers["location"]).text
