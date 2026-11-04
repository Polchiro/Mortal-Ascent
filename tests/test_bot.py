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
    p = new_player(conn)
    assert profile_card.render_profile(rules.profile_data(p, db.get_techniques(conn, 1), 1)).size == (1200, 720)
    assert render_balance(rules.balance_data(p)).size == (1200, 500)


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
