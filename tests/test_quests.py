"""Daily quests (bot/quests.py, docs/quests.md)."""
import quests as config
from bot import db, quests
from bot.quests import record

DAY = 1_800_000_000          # a fixed moment, so the day's quests are fixed


def new(conn, uid=1):
    from test_explore_card import new_player
    new_player(conn) if uid == 1 else None
    return db.get_player(conn, uid)


def finish_all(conn, uid, now=DAY):
    for k in quests.todays_keys(uid, now):
        q = config.QUESTS[k]
        record(conn, uid, q["event"], q["n"], now=now)


def test_four_different_quests_fixed_for_the_day_and_new_tomorrow():
    a = quests.todays_keys(1, DAY)
    assert len(a) == config.QUESTS_PER_DAY == len(set(a)) and set(a) <= set(config.QUESTS)
    assert quests.todays_keys(1, DAY + 3600) == a
    days = {tuple(quests.todays_keys(1, DAY + 86400 * i)) for i in range(10)}
    assert len(days) > 1


def test_progress_claim_once_and_all_done_bonus():
    conn = db.connect(":memory:")
    p = new(conn)
    keys = quests.todays_keys(1, DAY)
    first = config.QUESTS[keys[0]]
    record(conn, 1, first["event"], first["n"] - 1, now=DAY)
    b = quests.board(conn, p, DAY)
    assert b["claimable"] == 0 and b["quests"][0]["have"] == first["n"] - 1
    assert quests.claim(conn, 1, DAY)["coins"] == 0
    record(conn, 1, first["event"], 5, now=DAY)
    before = db.get_player(conn, 1)
    out = quests.claim(conn, 1, DAY)
    after = db.get_player(conn, 1)
    assert out["quests"] == [first["name"]] and not out["bonus"]
    assert after["lotus_coins"] - before["lotus_coins"] == round(first["coins"] * quests.coin_scale(p))
    assert after["moon_pearls"] - before["moon_pearls"] == first["pearls"]
    assert quests.claim(conn, 1, DAY)["coins"] == 0                          # claimed once
    finish_all(conn, 1)
    out = quests.claim(conn, 1, DAY)
    assert out["bonus"] and out["chest"] == quests.bonus_chest(1, DAY)
    assert out["pearls"] == sum(config.QUESTS[k]["pearls"] for k in keys[1:]) + config.ALL_DONE_PEARLS
    if out["chest"]:
        assert any(i["key"] == out["chest"] for i in db.get_items(conn, 1, "chests"))
    b = quests.board(conn, p, DAY)
    assert b["claimable"] == 0 and b["bonus"]["claimed"]
    assert quests.board(conn, p, DAY + 86400)["quests"][0]["have"] == 0     # a new day starts empty


def test_bonus_waits_for_bag_space_and_keeps_its_chest():
    conn = db.connect(":memory:")
    new(conn)
    now = next(DAY + 86400 * i for i in range(200) if quests.bonus_chest(1, DAY + 86400 * i))
    db.update_player(conn, 1, bag_capacity=db.slots_used(conn, 1))
    finish_all(conn, 1, now)
    out = quests.claim(conn, 1, now)
    assert out["bag_full"] and not out["bonus"] and quests.board(conn, db.get_player(conn, 1), now)["bonus"]["ready"]
    db.update_player(conn, 1, bag_capacity=999)
    out = quests.claim(conn, 1, now)
    assert out["bonus"] and out["chest"] == quests.bonus_chest(1, now)


def test_chest_odds_and_only_common_to_legendary():
    odds = quests.chest_odds()
    assert set(odds) == {"common", "uncommon", "rare", "epic", "legendary"}
    assert abs(sum(odds.values()) - config.ALL_DONE_CHEST_CHANCE) < 1e-9
    got = {quests.bonus_chest(7, DAY + 86400 * i) for i in range(400)}
    assert None in got and got - {None} <= set(odds)


def test_activities_count_toward_quests():
    conn = db.connect(":memory:")
    new(conn)
    for e in quests.EVENTS:
        record(conn, 1, e, now=DAY)
        assert db.daily_count(conn, 1, "quest:" + e, DAY) == 1
    record(conn, 1, "not_a_quest", now=DAY)
    assert db.daily_count(conn, 1, "quest:not_a_quest", DAY) == 0


def test_card_renders_every_state():
    from cards.quests import render_quests
    conn = db.connect(":memory:")
    p = new(conn)
    assert render_quests(quests.board(conn, p, DAY)).size[0] == 1200
    finish_all(conn, 1)
    assert render_quests(quests.board(conn, p, DAY)).size[0] == 1200
    quests.claim(conn, 1, DAY)
    assert render_quests(quests.board(conn, p, DAY)).size[0] == 1200
