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
    assert rules.qi_needed("Martial King", 8) == round(29000 * 1.5)


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

    from bot.client import MortalAscent
    from bot.sheet import view as sheet_view

    async def go():
        bot = MortalAscent(":memory:")
        sheet_view.AVATAR_TIMEOUT_SECONDS = 0.2
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


def test_admin_reset_and_give(conn, monkeypatch):
    from bot import admin
    new_player(conn)
    now = time.time()
    db.set_cooldown(conn, 1, "explore", 3600, now)
    db.set_cooldown(conn, 1, "train", 3600, now)
    db.bump_daily(conn, 1, "practice", now)
    db.update_player(conn, 1, injured_until=now + 600, seclusion_start=now - 3600, seclusion_end=now + 3600)
    done = admin.reset_player(conn, 1, now)
    assert len(done) == 4
    assert db.cooldown_left(conn, 1, "explore", now) == 0 and db.cooldown_left(conn, 1, "train", now) == 0
    assert db.daily_count(conn, 1, "practice", now) == 0
    p = db.get_player(conn, 1)
    assert not rules.injured_for(p, now) and rules.seclusion_qi(p, (), now)[2]
    assert admin.reset_player(conn, 1, now + 1) == []

    admin.give(conn, 1, lotus_coins=100, moon_pearls=5, qi=rules.qi_needed("Mortal", 1) + 1)
    p = db.get_player(conn, 1)
    assert p["lotus_coins"] == 150 and p["moon_pearls"] == 5 and p["layer"] == 2

    monkeypatch.setenv("ADMIN_IDS", "123, 456,junk")
    assert admin.admin_ids_from_env() == {123, 456}


def test_every_command_works_in_dms():
    """All commands (including groups like /internal and /admin) are allowed in the bot's DMs,
    and member options accept plain users, which is what Discord sends in a DM."""
    from bot.client import MortalAscent

    bot = MortalAscent(":memory:")
    commands = bot.tree.get_commands()
    assert commands
    for cmd in commands:
        payload = cmd.to_dict(bot.tree)
        assert set(payload["contexts"]) >= {0, 1}, cmd.name      # 0 = server, 1 = DM with the bot
    for name in ("profile",):
        param = bot.tree.get_command(name).get_parameter("member")
        assert param.type.name == "user"


def test_setup_hook_syncs_globally_and_clears_old_guild_copy():
    import asyncio
    from unittest.mock import AsyncMock

    from bot.client import MortalAscent

    bot = MortalAscent(":memory:", guild_id=42)
    bot.tree.sync = AsyncMock()
    asyncio.run(bot.setup_hook())
    calls = bot.tree.sync.await_args_list
    assert calls[0].kwargs == {}                         # global sync first
    assert calls[1].kwargs["guild"].id == 42             # then the emptied per-server copy
    assert bot.tree.get_commands(guild=calls[1].kwargs["guild"]) == []


def test_hunt_in_dm_is_solo():
    import asyncio

    from bot import hunt
    from bot.client import MortalAscent
    from bot.views import HuntView

    async def go():
        bot = MortalAscent(":memory:")
        p = new_player(bot.conn)
        lair = hunt.roll_lair(p, "elite", random.Random(1))
        solo = HuntView(bot, lair, p, solo=True)
        team = HuntView(bot, lair, p)
        assert [b.label for b in solo.children] == ["Start the hunt"]
        assert "alone" in solo.embed().description
        assert len(team.children) == 3
    asyncio.run(go())
