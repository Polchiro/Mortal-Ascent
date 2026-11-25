"""Moon Pearls bought with real money (docs/payments.md): orders, giving pearls once, refunds and chargebacks.

Each test is one way someone could try to get pearls without paying, or one promise the engine makes."""
import sqlite3
import threading

import pytest

import economy
from bot import db, purchases
from bot import player as rules
from bot.purchases import PurchaseError

UID, OTHER = 501, 502


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    for uid, name in ((UID, "Shoaib"), (OTHER, "Lin")):
        db.create_player(c, uid, name, "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return c


def pearls(conn, uid=UID):
    return db.get_player(conn, uid)["moon_pearls"]


def debt(conn, uid=UID):
    return db.get_player(conn, uid)["pearl_debt"]


def paid(conn, order, payment_id="pay_1", live=False, **over):
    args = dict(user_id=order["user_id"], pack_key=order["pack"], provider="test", payment_id=payment_id, live=live)
    args.update(over)
    return purchases.grant(conn, order["order_id"], **args)


# ── prices come from the server ───────────────────────────────────────────

def test_packs_and_prices_come_only_from_the_server_table(conn):
    order = purchases.create_order(conn, UID, "jade_box", live=False)
    assert order["price_cents"] == 1000 and order["status"] == "pending" and order["pearls"] == 0
    assert pearls(conn) == 0                                   # making an order gives nothing
    with pytest.raises(PurchaseError):
        purchases.create_order(conn, UID, "free_pearls", live=False)


def test_launch_packs_leave_out_the_100_dollar_vault():
    assert [p["price_cents"] for p in economy.PEARL_PACKS.values()] == [200, 500, 1000, 2000, 5000]
    assert economy.RECHARGE_PACKAGES[2] == ("Jade Box", 10, 1080)       # /recharge still lists them


def test_order_numbers_are_random_and_unguessable(conn):
    ids = {purchases.create_order(conn, UID, "pearl_pouch", live=False)["order_id"] for _ in range(5)}
    assert len(ids) == 5 and all(i.startswith("MP-") and len(i) == 19 for i in ids)


def test_too_many_unpaid_orders_are_refused(conn):
    for _ in range(purchases.MAX_OPEN_ORDERS):
        purchases.create_order(conn, UID, "pearl_pouch", live=False, now=1000)
    with pytest.raises(PurchaseError, match="too many"):
        purchases.create_order(conn, UID, "pearl_pouch", live=False, now=1000)
    purchases.create_order(conn, UID, "pearl_pouch", live=False, now=1000 + 3601)   # an hour later is fine


# ── pearls only once, only when everything matches ───────────────────────

def test_first_purchase_gives_double_once_then_normal(conn):
    first = purchases.create_order(conn, UID, "jade_box", live=False)
    result, order = paid(conn, first)
    assert result == "granted" and order["status"] == "paid" and order["pearls"] == 2160 and order["bonus"] == 1080
    assert pearls(conn) == 2160
    second = purchases.create_order(conn, UID, "pearl_pouch", live=False)
    assert paid(conn, second, "pay_2")[1]["pearls"] == 200
    assert pearls(conn) == 2360
    line = db.ledger(conn, UID, 1)[0]
    assert line["delta"] == 200 and line["balance"] == 2360 and line["reason"] == "Bought Pearl Pouch"


def test_the_same_confirmation_twice_gives_pearls_once(conn):
    order = purchases.create_order(conn, UID, "pearl_pouch", live=False)
    assert paid(conn, order)[0] == "granted"
    assert paid(conn, order)[0] == "duplicate"
    assert paid(conn, order)[0] == "duplicate"
    assert pearls(conn) == 400


def test_one_payment_cannot_fill_two_orders(conn):
    a = purchases.create_order(conn, UID, "pearl_pouch", live=False)
    b = purchases.create_order(conn, UID, "pearl_pouch", live=False)
    paid(conn, a, "pay_same")
    with pytest.raises(PurchaseError, match="already used"):
        paid(conn, b, "pay_same")
    assert pearls(conn) == 400 and purchases.find(conn, b["order_id"])["status"] == "pending"


def test_a_second_payment_for_a_paid_order_gives_nothing(conn):
    order = purchases.create_order(conn, UID, "pearl_pouch", live=False)
    paid(conn, order, "pay_1")
    with pytest.raises(PurchaseError, match="already paid"):
        paid(conn, order, "pay_2")
    assert pearls(conn) == 400


@pytest.mark.parametrize("change, match", [
    ({"pack_key": "moon_treasury"}, "is for jade_box"),            # paid for a small pack, claims a big one
    ({"user_id": OTHER}, "another player"),                         # someone else's order
    ({"live": True}, "test-mode"),                                  # a test payment on a real order
    ({"payment_id": ""}, "missing"),
])
def test_anything_that_does_not_match_the_order_gives_nothing(conn, change, match):
    order = purchases.create_order(conn, UID, "jade_box", live=False)
    with pytest.raises(PurchaseError, match=match):
        paid(conn, order, **change)
    assert pearls(conn) == 0 and pearls(conn, OTHER) == 0
    assert purchases.find(conn, order["order_id"])["status"] == "pending"


def test_a_real_money_order_needs_a_real_payment(conn):
    order = purchases.create_order(conn, UID, "jade_box", live=True)
    with pytest.raises(PurchaseError, match="real-mode"):
        paid(conn, order, live=False)
    assert paid(conn, order, live=True)[0] == "granted"


def test_unknown_order_gives_nothing(conn):
    with pytest.raises(PurchaseError, match="unknown order"):
        purchases.grant(conn, "MP-FAKE", user_id=UID, pack_key="jade_box", provider="test", payment_id="x",
                        live=False)
    assert pearls(conn) == 0


def test_two_copies_of_a_confirmation_at_the_same_moment_give_pearls_once(tmp_path):
    path = str(tmp_path / "game.db")
    c = db.connect(path)
    db.create_player(c, UID, "Shoaib", "Genius", 0, rules.starting_techniques())
    order = purchases.create_order(c, UID, "jade_box", live=False)
    results, start = [], threading.Barrier(8)

    def deliver():
        mine = db.connect(path)
        start.wait()
        try:
            results.append(paid(mine, order, "pay_race")[0])
        except (PurchaseError, sqlite3.OperationalError) as e:
            results.append(type(e).__name__)

    threads = [threading.Thread(target=deliver) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results.count("granted") == 1
    assert pearls(c) == 2160


# ── refunds and chargebacks take the pearls back ─────────────────────────

def test_refund_takes_the_pearls_back(conn):
    order = purchases.create_order(conn, UID, "jade_box", live=False)
    paid(conn, order)
    result, after = purchases.revoke(conn, order["order_id"], "refunded")
    assert result == "revoked" and after["taken_back"] == 2160 and after["debt_added"] == 0
    assert pearls(conn) == 0 and debt(conn) == 0
    assert db.ledger(conn, UID, 1)[0]["reason"] == "Refund: Jade Box"
    assert purchases.revoke(conn, order["order_id"], "refunded")[0] == "duplicate"     # twice changes nothing
    assert paid(conn, order)[0] == "duplicate"            # the old "paid" message again gives nothing back


def test_chargeback_after_spending_leaves_a_debt_that_new_pearls_pay_first(conn):
    order = purchases.create_order(conn, UID, "pearl_pouch", live=False)
    paid(conn, order)                                                  # 400 (first purchase)
    db.spend(conn, UID, "moon_pearls", 300, "Blessing: Gentle Breeze")  # 100 left
    _, after = purchases.revoke(conn, order["order_id"], "chargeback")
    assert after["status"] == "chargeback" and after["taken_back"] == 100 and after["debt_added"] == 300
    assert pearls(conn) == 0 and debt(conn) == 300
    assert db.ledger(conn, UID, 1)[0]["reason"] == "Chargeback: Pearl Pouch (300 owed)"
    db.change_currency(conn, UID, "moon_pearls", 50, "Daily quests")
    assert pearls(conn) == 0 and debt(conn) == 250
    db.change_currency(conn, UID, "moon_pearls", 260, "Daily quests")
    assert pearls(conn) == 10 and debt(conn) == 0
    assert db.ledger(conn, UID, 1)[0]["reason"] == "Daily quests (250 paid toward refund debt)"


def test_no_new_purchases_while_in_debt(conn):
    db.update_player(conn, UID, pearl_debt=40)
    with pytest.raises(PurchaseError, match="debt"):
        purchases.create_order(conn, UID, "pearl_pouch", live=False)


def test_refunded_first_purchase_still_uses_up_the_double_bonus(conn):
    a = purchases.create_order(conn, UID, "pearl_pouch", live=False)
    paid(conn, a)
    purchases.revoke(conn, a["order_id"], "refunded")
    assert not purchases.is_first_purchase(conn, UID)
    b = purchases.create_order(conn, UID, "pearl_pouch", live=False)
    assert paid(conn, b, "pay_2")[1]["bonus"] == 0


def test_refund_before_the_paid_message_closes_the_order(conn):
    order = purchases.create_order(conn, UID, "pearl_pouch", live=False)
    purchases.revoke(conn, order["order_id"], "refunded")
    with pytest.raises(PurchaseError, match="already refunded"):
        paid(conn, order)
    assert pearls(conn) == 0 and debt(conn) == 0


# ── the permanent record ─────────────────────────────────────────────────

def test_purchases_are_kept_after_the_ledger_trims(conn):
    order = purchases.create_order(conn, UID, "jade_box", live=False)
    paid(conn, order, "pay_lookup")
    for _ in range(db.LEDGER_KEEP + 5):
        db.add_coins(conn, UID, 1, "Chest")
    assert not any("Jade Box" in r["reason"] for r in db.ledger(conn, UID, 500))
    assert purchases.find(conn, payment_id="pay_lookup")["order_id"] == order["order_id"]
    assert [p["order_id"] for p in purchases.history(conn, UID)] == [order["order_id"]]


def test_old_databases_get_the_new_column_and_table(tmp_path):
    path = str(tmp_path / "old.db")
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE players (user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, talent TEXT NOT NULL, "
                "realm TEXT NOT NULL DEFAULT 'Mortal', layer INTEGER NOT NULL DEFAULT 1, qi REAL NOT NULL DEFAULT 0, "
                "lotus_coins INTEGER NOT NULL DEFAULT 0, moon_pearls INTEGER NOT NULL DEFAULT 0, blessing_tier TEXT, "
                "blessing_expires REAL, beasts_slain INTEGER NOT NULL DEFAULT 0, breakthroughs INTEGER NOT NULL "
                "DEFAULT 0, failed_breakthroughs INTEGER NOT NULL DEFAULT 0, created_at REAL NOT NULL)")
    old.execute("INSERT INTO players (user_id, name, talent, moon_pearls, created_at) VALUES (1, 'A', 'Gifted', 7, 0)")
    old.commit()
    old.close()
    c = db.connect(path, setup=True)
    assert db.get_player(c, 1)["pearl_debt"] == 0 and db.get_player(c, 1)["moon_pearls"] == 7
    assert purchases.history(c, 1) == []
