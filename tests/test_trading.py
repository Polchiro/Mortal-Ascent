"""Trading between players (bot/trading.py, docs/trading.md): offers, confirmations, the swap, and its safety checks."""
import random

import pytest

from bot import db, loot, trading
from bot import player as rules
from bot.trading import Trade, TradeError


@pytest.fixture
def conn():
    return db.connect(":memory:")


def player(conn, uid, coins=1000, pearls=50):
    db.create_player(conn, uid, f"P{uid}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(conn, uid, lotus_coins=coins, moon_pearls=pearls)


def herb(conn, uid, qty, tier="Mystic", age=100):
    h = loot.herb(tier, "qi", age)
    db.add_item(conn, uid, h["category"], h["key"], h["name"], h["grade"], qty, h["data"])
    return next(i for i in db.get_items(conn, uid, "herbs") if i["key"] == h["key"])


def weapon(conn, uid, equip=False):
    it = loot.roll_weapon("spirit", random.Random(1))
    loot.store(conn, uid, [it])
    w = max(db.get_items(conn, uid, "weapons"), key=lambda i: i["id"])
    if equip:
        db.equip_weapon(conn, uid, w["id"])
    return db.get_item(conn, uid, w["id"])


def test_a_full_trade_moves_items_and_currency_with_no_tax(conn):
    player(conn, 1, coins=1000, pearls=50)
    player(conn, 2, coins=200, pearls=0)
    h = herb(conn, 1, 45)
    w = weapon(conn, 2)
    t = Trade(1, 2)
    t.set_item(conn, 1, h["id"], 10)
    t.set_currency(conn, 1, "moon_pearls", 20)
    t.set_item(conn, 2, w["id"], 1)
    t.set_currency(conn, 2, "lotus_coins", 150)
    assert not t.confirm(1)
    assert t.confirm(2)
    assert t.execute(conn) is None and t.status == "complete"
    p1, p2 = db.get_player(conn, 1), db.get_player(conn, 2)
    assert (p1["lotus_coins"], p1["moon_pearls"]) == (1150, 30)       # no tax: exactly what was offered
    assert (p2["lotus_coins"], p2["moon_pearls"]) == (50, 20)
    assert db.get_item(conn, 1, h["id"])["qty"] == 35
    got = [i for i in db.get_items(conn, 2, "herbs") if i["key"] == h["key"]]
    assert got and got[0]["qty"] == 10 and got[0]["data"]["age"] == 100
    moved = db.get_item(conn, 1, w["id"])                              # the same weapon, passives and buffs intact
    assert moved and moved["data"] == w["data"] and db.get_item(conn, 2, w["id"]) is None


def test_any_change_clears_both_confirmations(conn):
    player(conn, 1)
    player(conn, 2)
    h = herb(conn, 1, 5)
    t = Trade(1, 2)
    t.set_item(conn, 1, h["id"], 2)
    t.confirm(1)
    t.confirm(2)
    t.set_item(conn, 1, h["id"], 3)
    assert not any(o.confirmed for o in t.offers.values())
    assert t.execute(conn) == "Both players must confirm."


def test_cannot_offer_more_than_owned_equipped_or_bound(conn):
    player(conn, 1, coins=100)
    player(conn, 2)
    h = herb(conn, 1, 5)
    w = weapon(conn, 1, equip=True)
    db.add_item(conn, 1, "pills", "heaven_defying", "Heaven-Defying Pill", "Heaven")
    pill = next(i for i in db.get_items(conn, 1, "pills") if i["key"] == "heaven_defying")
    t = Trade(1, 2)
    with pytest.raises(TradeError):
        t.set_item(conn, 1, h["id"], 6)
    with pytest.raises(TradeError):
        t.set_item(conn, 1, w["id"], 1)
    with pytest.raises(TradeError):
        t.set_item(conn, 1, pill["id"], 1)
    with pytest.raises(TradeError):
        t.set_currency(conn, 1, "lotus_coins", 101)
    with pytest.raises(TradeError):
        t.set_item(conn, 1, 999_999, 1)                     # not theirs
    assert all(i["id"] != w["id"] for i in trading.tradeable_items(conn, 1))


def test_the_swap_rechecks_everything_and_moves_nothing_on_failure(conn):
    player(conn, 1, coins=500)
    player(conn, 2, coins=500)
    h = herb(conn, 1, 10)
    t = Trade(1, 2)
    t.set_item(conn, 1, h["id"], 10)
    t.set_currency(conn, 2, "lotus_coins", 400)
    t.confirm(1)
    t.confirm(2)
    db.discard_item(conn, 1, h["id"], 3)                    # spent elsewhere after confirming
    why = t.execute(conn)
    assert why and t.status == "open"
    assert db.get_player(conn, 2)["lotus_coins"] == 500 and db.get_item(conn, 1, h["id"])["qty"] == 7
    assert not any(o.confirmed for o in t.offers.values())


def test_bag_space_is_checked_for_the_receiver(conn):
    player(conn, 1)
    player(conn, 2)
    db.update_player(conn, 2, bag_capacity=db.slots_used(conn, 2))     # receiver's bag is exactly full
    w = weapon(conn, 1)
    t = Trade(1, 2)
    t.set_item(conn, 1, w["id"], 1)
    t.confirm(1)
    t.confirm(2)
    assert "bag" in t.execute(conn)
    assert db.get_item(conn, 1, w["id"]) is not None


def test_both_empty_cannot_confirm_and_cancel_ends_it(conn):
    player(conn, 1)
    player(conn, 2)
    t = Trade(1, 2)
    with pytest.raises(TradeError):
        t.confirm(1)
    t.cancel(2)
    assert t.status == "cancelled" and t.ended_by == 2
    with pytest.raises(TradeError):
        t.set_currency(conn, 1, "lotus_coins", 1)


def test_picker_groups_by_category_and_real_grades(conn):
    player(conn, 1)
    herb(conn, 1, 3, tier="Heaven")
    herb(conn, 1, 3, tier="Mortal", age=10)
    core = loot.beast_core("elite", "Martial Master")
    db.add_item(conn, 1, core["category"], core["key"], core["name"], core["grade"], 2, core["data"])
    weapon(conn, 1)
    counts = trading.category_counts(conn, 1)
    assert counts["herbs"] == 2 and counts["cores"] == 1 and counts["weapons"] >= 1
    assert [g for g, _ in trading.grades_in(conn, 1, "herbs")] == ["Mortal", "Heaven"]
    assert trading.grades_in(conn, 1, "weapons")[0][0] in ("Ordinary", "Refined", "Spirit", "Treasure", "Divine")


def test_card_renders_every_state(conn):
    from cards.trade import W, render_preview, render_trade
    player(conn, 1)
    player(conn, 2)
    h = herb(conn, 1, 45)
    w = weapon(conn, 2)
    t = Trade(1, 2)
    names = {1: "Shoaib", 2: "Lin"}
    for step in range(4):
        if step == 1:
            t.set_item(conn, 1, h["id"], 10)
            t.set_currency(conn, 2, "moon_pearls", 20)
            t.set_item(conn, 2, w["id"], 1)
        if step == 2:
            t.confirm(1)
        if step == 3:
            t.confirm(2)
            assert t.execute(conn) is None
        data = trading.card_data(conn, t, names)
        assert render_trade(data).size[0] == W and render_preview(dict(data, viewer=1)).size[0] == W
    t2 = Trade(1, 2)
    t2.cancel(1)
    assert render_trade(trading.card_data(conn, t2, names)).size[0] == W


def test_trade_panels_build(conn):
    """The private Discord panels build for every step without a live Discord connection."""
    import asyncio
    from types import SimpleNamespace
    from bot import trade_view

    player(conn, 1)
    player(conn, 2)
    h = herb(conn, 1, 45, tier="Heaven")

    async def go():
        bot = SimpleNamespace(conn=conn, busy=set(), db_lock=asyncio.Lock())
        users = {1: SimpleNamespace(id=1, display_name="A"), 2: SimpleNamespace(id=2, display_name="B")}
        window = SimpleNamespace(bot=bot, trade=Trade(1, 2), users=users)
        p = trade_view.ItemPicker(window, 1)
        assert p.embed().title
        p.category = "herbs"
        p.build()
        p.grade = "Heaven"
        p.build()
        p.item, p.qty = db.get_item(conn, 1, h["id"]), 10
        p.build()
        assert "Owned: **45**" in p.embed().description
        assert trade_view.CurrencyPanel(window, 1).embed().fields
        window.trade.set_item(conn, 1, h["id"], 3)
        assert trade_view.RemovePanel(window, 1).has_lines
    asyncio.run(go())


def test_picker_screens_render(conn):
    from cards.trade import W, render_picker
    player(conn, 1)
    h = herb(conn, 1, 45, tier="Heaven")
    player(conn, 2)
    t = Trade(1, 2)
    t.set_item(conn, 1, h["id"], 10)
    assert render_picker({"mode": "categories", "categories": trading.picker_categories(conn, 1)}).size[0] == W
    d = trading.picker_items(conn, 1, "herbs", "Heaven", t.offers[1])
    assert d["items"][0]["offering"] == 10
    assert render_picker(dict(d, mode="items", category="Herbs", grade="Heaven")).size[0] == W
    item = db.get_item(conn, 1, h["id"])
    assert render_picker({"mode": "quantity", "item": trading.picker_row(item, 10), "qty": 10,
                          "category": "Herbs"}).size[0] == W
    assert render_picker({"mode": "currency", "currencies": [
        {"key": "lotus_coins", "label": "Lotus Coins", "balance": 10, "offering": 0}]}).size[0] == W
