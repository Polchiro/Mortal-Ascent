"""Manuals: a manual stays a bag item (it stacks and can be traded) until it is used. Learning one copy makes its
technique yours for good, equipped at once (Learn & equip) or not (Learn only); spare copies stay in the bag. One
already known can be reread for mastery EXP and Insight ink. The bag says what will happen first (loot.manual_plan),
the same on Discord and the website."""
import asyncio
from types import SimpleNamespace

import pytest

from bot import db, loot, trading
from bot import player as rules

UID = 1


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.create_player(c, UID, "P1", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return c


def give(conn, key, qty=1):
    db.add_item(conn, UID, **dict(loot.manual(key), qty=qty))
    return next(i for i in db.get_items(conn, UID, "manuals") if i["key"] == key)


def techs(conn):
    return {t["name"]: bool(t["equipped"]) for t in db.get_techniques(conn, UID, equipped_only=False)}


def test_the_plan_says_what_will_happen(conn):
    plan = loot.manual_plan(conn, UID, give(conn, "fierce_tiger_claw"))
    assert not plan["ok"] and "Martial" in plan["why"]                           # a Yellow manual needs a realm
    plan = loot.manual_plan(conn, UID, give(conn, "twin_palm_strike"))
    assert plan["ok"] and not plan["known"] and plan["replaces"] == "Iron Fist"  # both slots full: the oldest goes
    db.update_player(conn, UID, realm="Martial Warrior")                         # a flex slot opens
    assert loot.manual_plan(conn, UID, give(conn, "twin_palm_strike"))["replaces"] is None
    plan = loot.manual_plan(conn, UID, give(conn, "iron_fist"))
    assert plan["known"] and plan["exp"] > 0 and plan["ink"]
    lines = loot.manual_lines(plan, qty=3)
    assert "Or keep it to trade" in lines[0] and "×3" in lines[-1]


def test_learn_and_equip_or_learn_only(conn):
    item = give(conn, "twin_palm_strike", qty=3)
    msg = loot.learn_manual(conn, UID, item["id"], equip=True)
    assert "in place of **Iron Fist**" in msg
    assert techs(conn) == {"Iron Fist": False, "Horse Stance Guard": True, "Twin Palm Strike": True}
    left = db.get_item(conn, UID, item["id"])
    assert left["qty"] == 2 and trading.why_not_tradeable(left) is None        # the spares stay, and can be traded
    item = give(conn, "crescent_sweep")
    msg = loot.learn_manual(conn, UID, item["id"], equip=False)
    assert "equip it there when you want it" in msg
    assert techs(conn)["Crescent Sweep"] is False and techs(conn)["Twin Palm Strike"] is True   # nothing swapped
    assert db.get_item(conn, UID, item["id"]) is None                          # the one copy is used


def test_a_known_manual_is_read_only_when_asked(conn):
    item = give(conn, "iron_fist", qty=2)
    assert "already know" in loot.learn_manual(conn, UID, item["id"])          # Learn won't eat it
    assert db.get_item(conn, UID, item["id"])["qty"] == 2
    msg = loot.read_manual(conn, UID, item["id"])
    assert "mastery EXP" in msg and "ink" in msg
    assert db.get_item(conn, UID, item["id"])["qty"] == 1
    other = give(conn, "crescent_sweep")
    assert "Learn it first" in loot.read_manual(conn, UID, other["id"])        # Read won't learn
    assert db.get_item(conn, UID, other["id"]) is not None


def test_too_low_a_realm_keeps_the_manual(conn):
    item = give(conn, "fierce_tiger_claw")
    assert "must reach" in loot.learn_manual(conn, UID, item["id"])
    assert db.get_item(conn, UID, item["id"]) is not None and "Fierce Tiger Claw" not in techs(conn)


def test_use_item_still_learns_and_equips(conn):
    item = give(conn, "twin_palm_strike")
    assert "comprehend" in loot.use_item(conn, UID, item["id"])
    assert techs(conn)["Twin Palm Strike"] is True


# ── Discord's bag ─────────────────────────────────────────────────────

class FakeBot:
    def __init__(self, c):
        self.conn, self.db_lock, self.busy = c, asyncio.Lock(), set()


def fake_user():
    async def read():
        return None
    avatar = SimpleNamespace(with_format=lambda *_: SimpleNamespace(with_size=lambda *_: SimpleNamespace(read=read)))
    return SimpleNamespace(id=UID, name="tester", display_avatar=avatar)


SENT = []


class FakeInteraction:
    def __init__(self, value=None):
        self.data = {"values": [str(value)]} if value is not None else {}
        self.response = SimpleNamespace(defer=self._noop)

    async def _noop(self, **_):
        pass

    async def edit_original_response(self, **kw):
        SENT.append(kw.get("content") or "")


def test_discord_bag_offers_the_same_choices(conn):
    from bot.sheet.view import CharacterSheet
    new = give(conn, "twin_palm_strike")
    known = give(conn, "iron_fist")
    bot = FakeBot(conn)

    async def go():
        view = CharacterSheet(bot, fake_user(), "inventory", "manuals")
        await view.render()
        await view.on_pick(FakeInteraction(new["id"]))
        labels = [getattr(c, "label", None) for c in view.children]
        assert "Learn & equip" in labels and "Learn only" in labels
        assert "in place of **Iron Fist**" in SENT[-1]                      # it says what it would replace
        bot.busy.add((UID, "spar"))                                         # no swap in a fight
        await next(c for c in view.children if getattr(c, "label", None) == "Learn & equip").callback(FakeInteraction())
        assert "Twin Palm Strike" not in techs(conn) and "fight" in SENT[-1]
        await next(c for c in view.children if getattr(c, "label", None) == "Learn only").callback(FakeInteraction())
        assert techs(conn)["Twin Palm Strike"] is False                     # learned, slots untouched
        await view.on_pick(FakeInteraction(known["id"]))
        labels = [getattr(c, "label", None) for c in view.children]
        assert "Read it" in labels and "Learn & equip" not in labels
    asyncio.run(go())
