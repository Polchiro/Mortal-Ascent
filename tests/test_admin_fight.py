"""/admin fight_beast: any beast in the game can be spawned and fought on the normal fight screen."""
import asyncio
from types import SimpleNamespace

import beasts

from bot import admin, db
from bot import player as rules
from tests.test_prefix import FakeUser, run


def _conn():
    c = db.connect(":memory:")
    db.create_player(c, 1, "P1", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return c


def test_every_beast_is_listed_and_found_by_its_pick_value():
    rows = admin.all_beasts()
    assert len(rows) == sum(len(r) for r in beasts.BEASTS.values())
    for row in rows:
        assert admin.find_beasts(admin.beast_key(row)) == [row]
        assert len(admin.beast_label(row)) <= 100


def test_search_by_name_part_and_tier():
    assert [r[1] for r in admin.find_beasts("grey wolf")] == ["Grey Wolf"]
    kings = admin.find_beasts("beast king")
    assert kings and all(r[2] == "beast_king" for r in kings)
    assert admin.find_beasts("no such beast") == []


def test_battle_uses_the_beast_and_tier_override():
    conn = _conn()
    row = next(r for r in admin.all_beasts() if r[1] == "Wild Boar")
    b = admin.beast_battle(conn, 1, row)
    assert b.enemy["name"] == "Wild Boar" and b.enemy["tier"] == "normal" and not b.over
    elite = admin.beast_battle(conn, 1, row, tier="elite")
    assert elite.enemy["tier"] == "elite" and elite.enemy["max_hp"] > b.enemy["max_hp"]
    assert elite.scene == "encounter_elite_lair"
    high = next(r for r in admin.all_beasts() if r[0] != "Mortal")
    assert admin.beast_battle(conn, 1, high, home_realm=True).enemy["max_hp"] > \
        admin.beast_battle(conn, 1, high).enemy["max_hp"]


def test_fight_beast_as_a_text_command(monkeypatch):
    from bot.client import MortalAscent
    bot = asyncio.run(_make(MortalAscent))
    user = FakeUser()

    async def app_info():
        return SimpleNamespace(team=None, owner=user)
    monkeypatch.setattr(bot, "application_info", app_info)
    run(bot, "m start", author=user)
    _, sent = run(bot, "m admin fight_beast Grey Wolf", author=user)
    assert (user.id, "hunt") in bot.busy
    assert any("Pick your move" in (m.content or "") for m in sent)
    _, sent = run(bot, "m admin fight_beast Grey Wolf", author=user)
    assert "already in a fight" in sent[-1].content


async def _make(cls):
    return cls(":memory:")


def test_web_fight_queues_a_fight_for_the_website(monkeypatch):
    from bot.client import MortalAscent
    bot = asyncio.run(_make(MortalAscent))
    user = FakeUser()

    async def app_info():
        return SimpleNamespace(team=None, owner=user)
    monkeypatch.setattr(bot, "application_info", app_info)
    run(bot, "m start", author=user)
    _, sent = run(bot, "m admin web_fight Mountain Tiger", author=user)
    assert "waiting for you on the website" in sent[-1].content
    row, tier, home = admin.take_web_fight(bot.conn, user.id)
    assert row[1] == "Mountain Tiger" and tier is None and home is False
    assert admin.take_web_fight(bot.conn, user.id) is None
