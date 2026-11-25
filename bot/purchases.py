"""
Moon Pearls bought with real money: orders, giving pearls once, taking them back (docs/payments.md).

This file never sees a card or talks to the payment company. The website (a later step) calls:

    create_order(...)   when a player presses Buy        -> an order "pending", price from the server's table
    grant(...)          ONLY when the payment company's signed message says the payment went through
    revoke(...)         when the payment company says the payment was refunded or charged back

Safety rules kept here:
  * Prices and pack sizes come only from economy.PEARL_PACKS. An order stores the price it was made at.
  * Each payment gives pearls once. The order moves pending -> paid in one database step that only one message can
    win, and the payment company's transaction number is UNIQUE in the table, so a repeated message changes nothing.
  * The pearls, the ledger line and the purchase record are written in the same transaction: all or nothing.
  * Test-mode payments can't fill a real-money order, and the other way round.
  * A refund or chargeback takes the pearls back. Pearls already spent become players.pearl_debt, which new pearls
    pay off first (db.change_currency), and the player can't buy more until it is cleared.
  * Every purchase stays in pearl_purchases for good (the ledger only keeps the last 100 lines).
"""
import secrets
import sqlite3
import time

import economy

from . import db

PENDING, PAID, REFUNDED, CHARGEBACK = "pending", "paid", "refunded", "chargeback"
TAKEN_BACK = (REFUNDED, CHARGEBACK)
MAX_OPEN_ORDERS = 10            # unpaid orders a player may start in an hour (stops someone spamming the button)


class PurchaseError(Exception):
    """A request that must not give or take pearls. The message is safe to log (no secrets in it)."""


def pack(key):
    """The pack from the server's own table, or PurchaseError. Never trust a price or size sent by a page."""
    p = economy.PEARL_PACKS.get(key)
    if p is None:
        raise PurchaseError(f"unknown pack {key!r}")
    return {"key": key, **p}


def is_first_purchase(conn, user_id):
    """True until the player has a paid pack (a refunded one still counts, so the bonus can't be farmed)."""
    return conn.execute("SELECT 1 FROM pearl_purchases WHERE user_id = ? AND status != ? LIMIT 1",
                        (user_id, PENDING)).fetchone() is None


def create_order(conn, user_id, pack_key, live, now=None):
    """Start an order for one pack. Returns the order dict. No pearls change here."""
    now = time.time() if now is None else now
    p = pack(pack_key)
    player = conn.execute("SELECT pearl_debt FROM players WHERE user_id = ?", (user_id,)).fetchone()
    if player is None:
        raise PurchaseError("no such player")
    if player["pearl_debt"] > 0:
        raise PurchaseError(f"pearl debt of {player['pearl_debt']:,} from a refunded purchase must be cleared first")
    recent = conn.execute("SELECT COUNT(*) FROM pearl_purchases WHERE user_id = ? AND status = ? AND created_at > ?",
                          (user_id, PENDING, now - 3600)).fetchone()[0]
    if recent >= MAX_OPEN_ORDERS:
        raise PurchaseError("too many unpaid orders; try again later")
    order_id = "MP-" + secrets.token_hex(8).upper()       # random, so order numbers can't be guessed
    with conn:
        conn.execute("INSERT INTO pearl_purchases (order_id, user_id, pack, price_cents, status, live, created_at) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?)", (order_id, user_id, p["key"], p["price_cents"], PENDING,
                                                      int(bool(live)), now))
    return find(conn, order_id)


def grant(conn, order_id, *, user_id, pack_key, provider, payment_id, live, now=None):
    """Give the pearls for a confirmed payment. Call it ONLY after the payment company's signature was checked.

    Every detail the company reports must match the order: the player, the pack and test/real mode.
    Returns ("granted", order) the first time and ("duplicate", order) for a repeat of the same payment.
    Raises PurchaseError for anything that doesn't match (nothing changes then)."""
    now = time.time() if now is None else now
    if not provider or not payment_id:
        raise PurchaseError("missing provider or payment id")
    order = find(conn, order_id)
    if order is None:
        raise PurchaseError(f"unknown order {order_id!r}")
    if order["provider"] == provider and order["payment_id"] == str(payment_id):
        return "duplicate", order                         # the same confirmation arrived again
    if order["user_id"] != int(user_id):
        raise PurchaseError(f"order {order_id} belongs to another player")
    if order["pack"] != pack_key:
        raise PurchaseError(f"order {order_id} is for {order['pack']}, payment was for {pack_key!r}")
    if order["live"] != int(bool(live)):
        raise PurchaseError(f"order {order_id} is {'real' if order['live'] else 'test'}-mode; payment was not")
    if order["status"] != PENDING:
        raise PurchaseError(f"order {order_id} is already {order['status']}")
    p = pack(order["pack"])
    try:
        with conn:
            won = conn.execute("UPDATE pearl_purchases SET status = ?, provider = ?, payment_id = ?, paid_at = ? "
                               "WHERE order_id = ? AND status = ?",
                               (PAID, provider, str(payment_id), now, order_id, PENDING)).rowcount
            if not won:                                   # another copy of the message got here first
                raise _Lost()
            first = conn.execute("SELECT 1 FROM pearl_purchases WHERE user_id = ? AND status != ? AND order_id != ? "
                                 "LIMIT 1", (order["user_id"], PENDING, order_id)).fetchone() is None
            bonus = p["pearls"] * (economy.FIRST_PURCHASE_MULTIPLIER - 1) if first else 0
            gained = p["pearls"] + bonus
            conn.execute("UPDATE pearl_purchases SET pearls = ?, bonus = ? WHERE order_id = ?",
                         (gained, bonus, order_id))
            _add_pearls(conn, order["user_id"], gained, f"Bought {p['name']}" + (" (first purchase ×2)" if bonus else ""),
                        now)
    except _Lost:
        again = find(conn, order_id)
        if again["provider"] == provider and again["payment_id"] == str(payment_id):
            return "duplicate", again
        raise PurchaseError(f"order {order_id} is already {again['status']}")
    except sqlite3.IntegrityError:
        raise PurchaseError(f"payment {payment_id} was already used for another order")
    return "granted", find(conn, order_id)


def revoke(conn, order_id, kind, now=None):
    """Take a refunded or charged-back purchase's pearls back. Safe to call more than once.

    Takes what the player still has; pearls already spent are added to their pearl_debt.
    A refund for an order that was never paid just closes it, so a late "paid" message can't give pearls.
    Returns ("revoked" | "duplicate", order)."""
    if kind not in TAKEN_BACK:
        raise PurchaseError(f"unknown kind {kind!r}")
    now = time.time() if now is None else now
    order = find(conn, order_id)
    if order is None:
        raise PurchaseError(f"unknown order {order_id!r}")
    if order["status"] in TAKEN_BACK:
        return "duplicate", order
    with conn:
        won = conn.execute("UPDATE pearl_purchases SET status = ?, refunded_at = ? WHERE order_id = ? AND status = ?",
                           (kind, now, order_id, order["status"])).rowcount
        if not won:
            return "duplicate", find(conn, order_id)
        if order["status"] == PAID and order["pearls"]:
            uid = order["user_id"]
            have = conn.execute("SELECT moon_pearls, pearl_debt FROM players WHERE user_id = ?", (uid,)).fetchone()
            take = min(have["moon_pearls"], order["pearls"])
            short = order["pearls"] - take
            conn.execute("UPDATE players SET moon_pearls = moon_pearls - ?, pearl_debt = pearl_debt + ? "
                         "WHERE user_id = ?", (take, short, uid))
            conn.execute("UPDATE pearl_purchases SET taken_back = ?, debt_added = ? WHERE order_id = ?",
                         (take, short, order_id))
            name = pack(order["pack"])["name"]
            why = f"{'Refund' if kind == REFUNDED else 'Chargeback'}: {name}" + (f" ({short:,} owed)" if short else "")
            db.write_ledger(conn, uid, "moon_pearls", -take, have["moon_pearls"] - take, why, now)
    return "revoked", find(conn, order_id)


def _add_pearls(conn, user_id, amount, reason, now):
    """Inside the grant transaction: add pearls, paying any pearl_debt first, with a ledger line."""
    have = conn.execute("SELECT moon_pearls, pearl_debt FROM players WHERE user_id = ?", (user_id,)).fetchone()
    if have is None:
        raise PurchaseError("no such player")
    paid = min(amount, have["pearl_debt"])
    conn.execute("UPDATE players SET moon_pearls = moon_pearls + ?, pearl_debt = pearl_debt - ? WHERE user_id = ?",
                 (amount - paid, paid, user_id))
    if paid:
        reason += f" ({paid:,} paid toward refund debt)"
    db.write_ledger(conn, user_id, "moon_pearls", amount - paid, have["moon_pearls"] + amount - paid, reason, now)


class _Lost(Exception):
    pass


# ── looking purchases up (for the owner when a player asks, and the player's own history) ─────────────

def find(conn, order_id=None, payment_id=None):
    """One purchase by our order number or by the payment company's transaction number."""
    if order_id:
        row = conn.execute("SELECT * FROM pearl_purchases WHERE order_id = ?", (order_id,)).fetchone()
    else:
        row = conn.execute("SELECT * FROM pearl_purchases WHERE payment_id = ?", (str(payment_id),)).fetchone()
    return dict(row) if row else None


def history(conn, user_id, limit=50):
    """A player's purchases, newest first (unpaid ones included)."""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM pearl_purchases WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, limit))]
