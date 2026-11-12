"""Fixed icons must reach players: the website's picture links change when a file changes, and the bot
replaces an uploaded button emoji whose picture changed (Discord keeps an emoji's first picture forever)."""
import asyncio
import os

import pytest

from bot import db
from bot import emojis as em


class FakeEmoji:
    def __init__(self, name):
        self.name, self.deleted = name, False

    async def delete(self):
        self.deleted = True


class FakeClient:
    def __init__(self, conn, existing=()):
        self.conn = conn
        self.existing = [FakeEmoji(n) for n in existing]
        self.uploaded = []

    async def fetch_application_emojis(self):
        return list(self.existing)

    async def create_application_emoji(self, name, image):
        self.uploaded.append(name)
        return FakeEmoji(name)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "t.db"))
    yield c
    c.close()


def test_an_emoji_with_an_old_picture_is_replaced_and_then_kept(conn):
    first = FakeClient(conn, existing=["ma_t_iron_fist"])        # uploaded before fingerprints were kept
    asyncio.run(em.Emojis().setup(first))
    assert first.existing[0].deleted and "ma_t_iron_fist" in first.uploaded
    names = set(first.uploaded)
    again = FakeClient(conn, existing=sorted(names))              # next start: same pictures
    e = em.Emojis()
    asyncio.run(e.setup(again))
    assert again.uploaded == [] and not any(x.deleted for x in again.existing)
    assert e.custom["t_iron_fist"].name == "ma_t_iron_fist"


def test_a_changed_picture_is_uploaded_again(conn):
    asyncio.run(em.Emojis().setup(FakeClient(conn)))
    db.set_setting(conn, "emoji:ma_pill", "an-older-picture")
    names = [n for (n,) in conn.execute("SELECT substr(key, 7) FROM settings WHERE key LIKE 'emoji:%'")]
    c = FakeClient(conn, existing=names)
    asyncio.run(em.Emojis().setup(c))
    assert c.uploaded == ["ma_pill"]


pytest.importorskip("fastapi")


def test_web_picture_links_carry_the_file_version():
    from web.inventory import tab_picture
    from web.profile import ART_ROOT, art_url
    url = art_url("tech:iron_fist")
    path, _, version = url.partition("?v=")
    assert path == "/art/icons/tech/iron_fist.webp"
    assert int(version) == int(os.path.getmtime(os.path.join(ART_ROOT, "icons/tech/iron_fist.webp")))
    for key in ("manuals", "pills", "armor", "chests"):
        assert "?v=" in tab_picture(key)


def test_art_is_rechecked_by_the_browser(tmp_path):
    from fastapi.testclient import TestClient
    from web import app as web_app
    settings = web_app.Settings(client_id="cid", client_secret="s", db_path=str(tmp_path / "w.db"), session_secret="t")
    client = TestClient(web_app.create_app(settings))
    r = client.get("/art/icons/index/pills_qi.webp?v=1")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"
