import random
import time

import pytest

from bot import db
from bot import player as rules


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, talent="Genius"):
    return db.create_player(conn, uid, f"P{uid}", talent, rules.STARTING_LOTUS_COINS, rules.starting_techniques())


def test_create_and_load(conn):
    p = new_player(conn)
    assert p["realm"] == "Mortal" and p["layer"] == 1 and p["lotus_coins"] == 50
    names = [t["name"] for t in db.get_techniques(conn, 1)]
    assert names == ["Iron Fist", "Horse Stance Guard"]


def test_roll_talent_is_valid():
    rng = random.Random(0)
    assert all(rules.roll_talent(rng) in rules.talent.TALENTS for _ in range(200))


def test_stats_follow_stats_md():
    assert rules.base_stats("Mortal", 1) == (50, 12, 3)
    hp, atk, dfn = rules.base_stats("Martial King", 9)
    assert hp == round(3000 * 1.32) and atk == round(3000 * 1.32 * 0.25)
    assert rules.base_stats("Martial King", 10)[0] == round(3000 * 1.40)


def test_phase_and_qi_needed():
    assert rules.phase_for(1) == "Early Phase"
    assert rules.phase_for(8) == "Late Phase"
    assert rules.phase_for(10) == "Peak Phase"
    assert rules.qi_needed("Martial King", 8) == round(35840 * 1.5)


def test_qi_rate_with_blessing(conn):
    p = new_player(conn, talent="Genius")
    assert rules.qi_rate(p) == pytest.approx((2.5 * 1.2, 1.2))
    p["blessing_tier"], p["blessing_expires"] = "Bright Moon", time.time() + 12 * 86400
    assert rules.qi_rate(p)[1] == pytest.approx(1.5)
    assert rules.active_blessing(p)[1] == 12


def test_server_rank(conn):
    new_player(conn, 1)
    new_player(conn, 2)
    conn.execute("UPDATE players SET layer = 3 WHERE user_id = 2")
    assert db.server_rank(conn, 2, rules.REALM_ORDER) == 1
    assert db.server_rank(conn, 1, rules.REALM_ORDER) == 2


def test_cards_render(conn):
    from balance_card import render_balance
    from profile_card import render_profile

    p = new_player(conn)
    img = render_profile(rules.profile_data(p, db.get_techniques(conn, 1), 1))
    assert img.size == (1200, 720)
    p["blessing_tier"], p["blessing_expires"] = "Starfall", time.time() + 86400
    assert render_balance(rules.balance_data(p)).size == (1200, 500)


def test_cards_render_without_any_system_fonts(conn, monkeypatch):
    """Windows has no DejaVu: rendering must fall back instead of raising (the /profile hang)."""
    import profile_card
    from balance_card import render_balance

    monkeypatch.setattr(profile_card, "FALLBACK_FONTS", ["no-such-font.ttf"])
    monkeypatch.setattr(profile_card, "CJK_CANDIDATES", ["no-such-cjk.otf"])
    profile_card.clear_font_cache()
    p = new_player(conn)
    assert profile_card.render_profile(rules.profile_data(p, db.get_techniques(conn, 1), 1)).size == (1200, 720)
    assert render_balance(rules.balance_data(p)).size == (1200, 500)
    profile_card.clear_font_cache()


def test_command_error_always_answers():
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from bot.client import MortalAscent

    bot = MortalAscent(":memory:")
    for deferred in (True, False):
        inter = MagicMock()
        inter.response.is_done.return_value = deferred
        inter.response.send_message = AsyncMock()
        inter.followup.send = AsyncMock()
        asyncio.run(bot.on_app_command_error(inter, RuntimeError("boom")))
        sent = inter.followup.send if deferred else inter.response.send_message
        sent.assert_awaited_once()


def test_fonts_are_looked_up_once(conn, monkeypatch):
    """A missing font made Pillow search the whole system font folder on every call (slow /profile on Windows)."""
    import PIL.ImageFont
    import profile_card
    from balance_card import render_balance

    p = new_player(conn)
    data = rules.profile_data(p, db.get_techniques(conn, 1), 1)
    profile_card.render_profile(data)
    render_balance(rules.balance_data(p))
    calls = []
    real = PIL.ImageFont.truetype
    monkeypatch.setattr(PIL.ImageFont, "truetype", lambda *a, **k: calls.append(a) or real(*a, **k))
    profile_card.render_profile(data)
    render_balance(rules.balance_data(p))
    assert calls == []


def test_profile_renders_from_avatar_bytes(conn):
    import io
    from PIL import Image
    from profile_card import render_profile

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, format="PNG")
    p = new_player(conn)
    data = rules.profile_data(p, db.get_techniques(conn, 1), 1)
    data["avatar_bytes"] = buf.getvalue()
    assert render_profile(data).size == (1200, 720)


def test_profile_command_twice_with_slow_avatar():
    """Run /profile twice in a row with an avatar download that never finishes: both must reply."""
    import asyncio
    from unittest.mock import AsyncMock, MagicMock

    from bot import client
    from bot.client import MortalAscent

    async def go():
        bot = MortalAscent(":memory:")
        client.AVATAR_TIMEOUT_SECONDS = 0.2
        start = bot.tree.get_command("start").callback
        profile = bot.tree.get_command("profile").callback
        balance = bot.tree.get_command("balance").callback

        def inter():
            i = MagicMock()
            i.user.id, i.user.display_name = 1, "Tester"
            i.response.send_message, i.response.defer, i.followup.send = AsyncMock(), AsyncMock(), AsyncMock()

            async def never():
                await asyncio.sleep(3600)
            i.user.display_avatar.with_format.return_value.with_size.return_value.read = never
            return i

        await start(inter())
        for cmd in (profile, profile, balance, balance):
            i = inter()
            await asyncio.wait_for(cmd(i), 30)
            i.response.defer.assert_awaited_once()
            assert i.followup.send.call_args.kwargs["file"].filename.endswith(".png")
    asyncio.run(go())
