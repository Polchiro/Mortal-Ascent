"""Chest Opening Reward Reveal: roll once and store, reveal exactly that, grant exactly once."""
import asyncio
import random
import time
from types import SimpleNamespace

import pytest

from bot import chest_reveal as cr
from bot import db, loot, materials
from bot import player as rules
from cards.chest import render_chest


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.create_player(c, 1, "Shoaib", "Genius", 50, rules.starting_techniques())
    db.update_player(c, 1, realm="Martial King", layer=4)
    return c


def chest_id(conn, tier="silver", qty=1):
    db.add_item(conn, 1, **dict(loot.chest(tier), qty=qty))
    return next(i["id"] for i in db.get_items(conn, 1, "chests") if i["key"] == tier)


def bag(conn):
    return sorted((i["category"], i["key"], i["qty"]) for i in db.get_items(conn, 1))


def test_begin_takes_the_chest_and_grants_nothing(conn):
    cid = chest_id(conn)
    before_coins = db.get_player(conn, 1)["lotus_coins"]
    pending = loot.begin_chest(conn, 1, cid, random.Random(3))
    assert pending and pending["claimed_at"] is None
    assert db.get_items(conn, 1, "chests") == []                       # the chest is gone at once
    assert db.get_player(conn, 1)["lotus_coins"] == before_coins       # but nothing is granted yet
    assert bag(conn) == []
    assert loot.begin_chest(conn, 1, cid, random.Random(3)) is None    # a second Open on the same chest


def test_the_roll_is_the_same_as_before(conn):
    """The reveal changes nothing about the odds: same RNG, same contents as open_chest."""
    p = db.get_player(conn, 1)
    for seed in range(40):
        cid = chest_id(conn, "jade")
        pending = loot.begin_chest(conn, 1, cid, random.Random(seed))
        coins, items = loot.open_chest(p, "jade", random.Random(seed))
        assert pending["coins"] == coins
        assert [(i["category"], i["key"], i.get("qty", 1)) for i in pending["items"]] == \
            [(i["category"], i["key"], i.get("qty", 1)) for i in items]


def test_claim_grants_exactly_once(conn):
    cid = chest_id(conn)
    pending = loot.begin_chest(conn, 1, cid, random.Random(7))
    coins0 = db.get_player(conn, 1)["lotus_coins"]
    result = loot.claim_chest(conn, 1, pending["id"])
    assert result and db.get_player(conn, 1)["lotus_coins"] == coins0 + pending["coins"]
    after = bag(conn)
    assert len(result["stored"]) == len(pending["items"])
    assert loot.claim_chest(conn, 1, pending["id"]) is None            # double click / second view
    assert loot.claim_chest(conn, 2, pending["id"]) is None            # someone else's id
    assert bag(conn) == after and db.get_player(conn, 1)["lotus_coins"] == coins0 + pending["coins"]


def test_rewards_stack_into_existing_stacks(conn):
    db.add_item(conn, 1, **materials.material("seal", 2))
    cid = chest_id(conn, "jade", qty=3)
    pending = loot.begin_chest(conn, 1, cid, random.Random(1))
    pending["items"] = [materials.material("seal", 3)]                 # a known reward
    pid = db.start_pending_chest(conn, 1, cid, "jade", "Jade Chest", 10, pending["items"], [])
    loot.claim_chest(conn, 1, pid)
    seals = [i for i in db.get_items(conn, 1, "materials") if i["key"] == "seal"]
    assert len(seals) == 1 and seals[0]["qty"] == 5
    assert db.get_items(conn, 1, "chests")[0]["qty"] == 1             # 3 chests, 2 opened


def test_full_bag_leaves_items_behind_but_pays_the_coins(conn):
    cid = chest_id(conn)
    db.update_player(conn, 1, bag_capacity=0)
    pid = db.start_pending_chest(conn, 1, cid, "silver", "Silver Chest", 99,
                                 [loot.roll_weapon("refined", random.Random(1))], [])
    coins0 = db.get_player(conn, 1)["lotus_coins"]
    result = loot.claim_chest(conn, 1, pid)
    assert result["lost"] and not result["stored"]
    assert db.get_player(conn, 1)["lotus_coins"] == coins0 + 99
    data = cr.card_data(result, db.get_player(conn, 1), "collected", result)
    assert data["rewards"][0]["lost"]
    assert render_chest(data).size[0] == 1200


def test_stale_pending_chests_are_collected_when_the_sheet_opens(conn):
    now = time.time()
    old = loot.begin_chest(conn, 1, chest_id(conn), random.Random(2), now=now - cr.STALE_AFTER_SECONDS - 5)
    fresh = loot.begin_chest(conn, 1, chest_id(conn, "wooden"), random.Random(2), now=now)
    note = cr.collect_stale(conn, 1, now)
    assert note and "Silver Chest" in note
    assert db.get_pending_chest(conn, old["id"])["claimed_at"] is not None
    assert db.get_pending_chest(conn, fresh["id"])["claimed_at"] is None   # a reveal still open is left alone
    assert cr.collect_stale(conn, 1, now) is None


def test_reward_rarities():
    assert cr.reward_rarity(dict(loot.HEAVEN_DEFYING)) == "Mythical"
    assert cr.reward_rarity(loot.roll_weapon("divine", random.Random(1))) == "Legendary"
    assert cr.reward_rarity(loot.roll_armor("treasure", random.Random(1))) == "Epic"
    assert cr.reward_rarity(loot.roll_artifact("spirit", random.Random(1))) == "Rare"
    assert cr.reward_rarity(loot.roll_weapon("refined", random.Random(1))) == "Uncommon"
    assert cr.reward_rarity(loot.roll_weapon("ordinary", random.Random(1))) == "Common"
    assert cr.reward_rarity(materials.material("seal")) == "Epic"


def test_every_stage_renders_and_rewards_sort_best_first(conn):
    p = db.get_player(conn, 1)
    fake = {"id": 0, "chest_key": "jade", "chest_name": "Jade Chest", "coins": 300, "notes": ["👝 **Deep Pockets:** x"],
            "items": [loot.roll_weapon("ordinary", random.Random(1)), dict(loot.HEAVEN_DEFYING),
                      loot.roll_armor("treasure", random.Random(2))]}
    for stage in ("sealed", "opening", "reveal", "collected"):
        data = cr.card_data(fake, p, stage)
        assert render_chest(data).size[0] == 1200
    data = cr.card_data(fake, p, "reveal")
    assert [r["rarity"] for r in data["rewards"]] == ["Mythical", "Epic", "Common"] and data["best"] == "Mythical"
    assert "THE HEAVENS TREMBLE" in cr.exceptional_lines(data)[0]
    empty = dict(fake, items=[])
    assert render_chest(cr.card_data(empty, p, "reveal")).size[0] == 1200


class FakeBot:
    def __init__(self, c):
        self.conn, self.db_lock, self.busy = c, asyncio.Lock(), set()


def test_view_collects_once_even_if_asked_twice(conn):
    pending = loot.begin_chest(conn, 1, chest_id(conn), random.Random(5))

    async def go():
        view = cr.ChestReveal(FakeBot(conn), SimpleNamespace(id=1, name="tester"), pending)
        assert [c.label for c in view.children] == ["Break the Seal"]
        view.stage = "reveal"
        view.build()
        assert [c.label for c in view.children] == ["Collect Rewards"]
        await view.collect()
        first = bag(conn), db.get_player(conn, 1)["lotus_coins"]
        assert view.result is not None and view.children == []
        await view.collect()                                           # a second try grants nothing
        assert view.result is None and (bag(conn), db.get_player(conn, 1)["lotus_coins"]) == first
        assert "already" in view.collected_text()
        await view.on_timeout()                                        # timing out after collecting is harmless
        assert (bag(conn), db.get_player(conn, 1)["lotus_coins"]) == first
    asyncio.run(go())


def test_timeout_collects_for_the_player(conn):
    pending = loot.begin_chest(conn, 1, chest_id(conn), random.Random(6))
    coins0 = db.get_player(conn, 1)["lotus_coins"]

    async def go():
        view = cr.ChestReveal(FakeBot(conn), SimpleNamespace(id=1, name="tester"), pending)
        await view.on_timeout()                                        # no message to edit: still collected
        assert db.get_player(conn, 1)["lotus_coins"] == coins0 + pending["coins"]
    asyncio.run(go())


def test_use_item_still_opens_a_chest_in_one_step(conn):
    cid = chest_id(conn, "jade")
    msg = loot.use_item(conn, 1, cid, random.Random(0))
    assert "Jade Chest" in msg and db.get_items(conn, 1, "chests") == []
    assert db.unclaimed_chests(conn, 1) == []


def test_inventory_open_button_starts_a_reveal(conn):
    """The sheet's Open on a chest stores the roll, updates the sheet and posts the sealed chest."""
    from bot.sheet.view import CharacterSheet
    cid = chest_id(conn, "bronze")
    sent, edits = [], []

    async def defer(*a, **k):
        pass

    async def edit(**k):
        edits.append(k)

    async def send(**k):
        sent.append(k)
        return SimpleNamespace(id=99)

    async def no_avatar():
        return None
    user = SimpleNamespace(id=1, name="tester", display_avatar=None)
    inter = SimpleNamespace(user=user, response=SimpleNamespace(defer=defer, is_done=lambda: True),
                            edit_original_response=edit, followup=SimpleNamespace(send=send))

    async def go():
        sheet = CharacterSheet(FakeBot(conn), user, "inventory", "chests")
        await sheet.render()
        assert sheet.selected == cid
        await sheet.on_use(inter)
        assert db.get_items(conn, 1, "chests") == []
        pending = db.unclaimed_chests(conn, 1)
        assert len(pending) == 1
        assert isinstance(sent[-1]["view"], cr.ChestReveal) and sent[-1]["view"].pending["id"] == pending[0]["id"]
        assert edits                                                   # the sheet was redrawn without the chest
    asyncio.run(go())
