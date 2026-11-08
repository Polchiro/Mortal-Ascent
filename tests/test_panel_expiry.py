"""Idle panels close by themselves after PANEL_IDLE_SECONDS, and a new command closes an idle old panel."""
import asyncio
import random

import pytest

from bot import crafting, db, trainer
from bot import player as rules
from bot.forge_view import ForgeView
from bot.gathering import GatherView
from bot.views import PANEL_IDLE_SECONDS, ExploreView, TrainView, free_old_panel


@pytest.fixture
def conn(tmp_path):
    return db.connect(str(tmp_path / "test.db"))


def new_player(conn, uid=1):
    db.create_player(conn, uid, "Tester", "Ordinary", rules.STARTING_LOTUS_COINS, rules.starting_techniques())


class FakeBot:
    def __init__(self, conn):
        self.conn, self.db_lock, self.busy = conn, asyncio.Lock(), set()


class FakeResponse:
    def __init__(self, it):
        self.it = it

    def is_done(self):
        return bool(self.it.sent)

    async def send_message(self, content=None, **kwargs):
        self.it.sent.append(content)


class FakeInteraction:
    def __init__(self, uid=1):
        self.user = type("U", (), {"id": uid})()
        self.sent = []
        self.response = FakeResponse(self)


def test_solo_panels_close_after_two_idle_minutes(conn):
    new_player(conn)

    async def go():
        bot = FakeBot(conn)
        p = db.get_player(conn, 1)
        views = [ExploreView(bot, 1, random.Random(0)), TrainView(bot, 1, trainer.roll_session(p)),
                 crafting.CraftView(bot, 1), ForgeView(bot, 1), GatherView(bot, 1, random.Random(0))]
        assert PANEL_IDLE_SECONDS == 120
        assert all(v.timeout == PANEL_IDLE_SECONDS for v in views)
        for v in views:
            v.stop()
    asyncio.run(go())


def test_new_craft_closes_the_idle_old_panel(conn):
    new_player(conn)

    async def go():
        bot = FakeBot(conn)
        bot.busy.add((1, "craft"))
        old = crafting.CraftView(bot, 1).track(bot, "craft")
        it = FakeInteraction()
        assert await free_old_panel(bot, it, "craft", "busy")
        assert old.is_finished() and (1, "craft") not in bot.busy and it.sent == []
    asyncio.run(go())


def test_an_expedition_under_way_is_not_closed_but_linked(conn):
    new_player(conn)

    async def go():
        bot = FakeBot(conn)
        bot.busy.add((1, "explore"))
        view = ExploreView(bot, 1, random.Random(0)).track(bot, "explore")
        it = FakeInteraction()
        assert not await free_old_panel(bot, it, "explore", "You are already on an expedition.")
        assert not view.is_finished() and (1, "explore") in bot.busy
        assert "closes by itself after 2 minutes" in it.sent[0]
        view.stop()
    asyncio.run(go())


def test_train_never_begun_gives_the_cooldown_back(conn):
    new_player(conn)

    async def go():
        bot = FakeBot(conn)
        p = db.get_player(conn, 1)
        bot.busy.add((1, "train"))
        db.set_cooldown(conn, 1, "train", 600)
        view = TrainView(bot, 1, trainer.roll_session(p)).track(bot, "train")
        assert await free_old_panel(bot, FakeInteraction(), "train", "busy")
        assert (1, "train") not in bot.busy and db.cooldown_left(conn, 1, "train") == 0
        assert view.is_finished()
    asyncio.run(go())


def test_train_already_running_is_left_alone(conn):
    new_player(conn)

    async def go():
        bot = FakeBot(conn)
        p = db.get_player(conn, 1)
        bot.busy.add((1, "train"))
        view = TrainView(bot, 1, trainer.roll_session(p)).track(bot, "train")
        view.task = asyncio.create_task(asyncio.sleep(0))      # Begin was pressed
        it = FakeInteraction()
        assert not await free_old_panel(bot, it, "train", "busy")
        await view.on_timeout()                                 # the safety-net timeout doesn't free it either
        assert (1, "train") in bot.busy
        await view.task
        view.stop()
    asyncio.run(go())
