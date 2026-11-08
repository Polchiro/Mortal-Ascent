"""
Trading between two players (docs/trading.md). Numbers: trade.py. No Discord code here: bot/trade_view.py
drives it and cards/trade.py draws it.

A Trade holds two Offers. An offer is a list of item lines {item_id, qty} plus Lotus Coins and Moon Pearls.
Any change to either offer clears both confirmations. When both have confirmed, execute() checks
everything again and moves it all in one database transaction, or moves nothing and says why.
"""
import time
from dataclasses import dataclass, field

import alchemy
import equipments
import trade as T

from . import db
from . import player as rules
from .sheet import items as bag

GEAR = ("weapons", "armor", "artifacts")


# ── what can be traded, and how the picker groups it ──────────────────

def trade_category(item):
    """The picker category of a bag item: cores, herbs, materials, weapons, armor, artifacts, pills, other."""
    cat = item["category"]
    if cat == "materials":
        return "cores" if item["key"].startswith("core:") else "materials"
    if cat in ("chests", "manuals"):
        return "other"
    return cat


def why_not_tradeable(item):
    """None if this item may be offered, else the reason."""
    if item["equipped"]:
        return "It's equipped. Unequip it first."
    if item["key"] in T.UNTRADEABLE.get(item["category"], ()):
        return "It's bound to you and can't be traded."
    return None


def grade_label(item):
    """The grade filter an item sits under, in the game's own words."""
    cat = item["category"]
    if cat in GEAR:
        return item["grade"].title()
    if cat in ("herbs", "pills", "manuals") or item["key"].startswith("core:"):
        return item.get("grade") or "Mortal"
    return bag.rarity(item)[0]


_GRADE_ORDER = (list(alchemy.GRADES) + [t.title() for t in equipments.TIERS]
                + [f"Tier {n}" for n in range(1, 11)] + ["Wooden", "Bronze", "Silver", "Jade"])


def grade_sort(label):
    return (_GRADE_ORDER.index(label), label) if label in _GRADE_ORDER else (len(_GRADE_ORDER), label)


def tradeable_items(conn, user_id, category=None, grade=None):
    """The player's items that may be offered, optionally only one picker category and grade."""
    out = []
    for it in db.get_items(conn, user_id):
        if why_not_tradeable(it):
            continue
        if category and trade_category(it) != category:
            continue
        if grade and grade_label(it) != grade:
            continue
        out.append(it)
    return out


def category_counts(conn, user_id):
    counts = {k: 0 for k, _, _ in T.CATEGORIES}
    for it in tradeable_items(conn, user_id):
        counts[trade_category(it)] += 1
    return counts


def grades_in(conn, user_id, category):
    """[(grade label, how many items)] the player has in this picker category, in game order."""
    seen = {}
    for it in tradeable_items(conn, user_id, category):
        g = grade_label(it)
        seen[g] = seen.get(g, 0) + 1
    return sorted(seen.items(), key=lambda kv: grade_sort(kv[0]))


def item_label(item):
    """A short name with its grade or age, for menus and the card."""
    cat = item["category"]
    if cat == "herbs":
        return f"{(item.get('data') or {}).get('age', 10)}-year {item['name']}"
    if cat == "pills":
        p = (item.get("data") or {}).get("patterns")
        return item["name"] + (f" ({p} patterns)" if p else "")
    return item["name"]


def why_cannot_trade(player, other=None):
    """None if this player may trade now, else the reason."""
    if T.MIN_REALM and rules.realm_index(player["realm"]) < rules.realm_index(T.MIN_REALM):
        return f"Trading opens at **{T.MIN_REALM}**."
    return None


# ── the trade ─────────────────────────────────────────────────────────

@dataclass
class Offer:
    user_id: int
    lines: list = field(default_factory=list)      # [{"item_id", "qty"}]
    lotus_coins: int = 0
    moon_pearls: int = 0
    confirmed: bool = False

    def qty_of(self, item_id):
        return next((ln["qty"] for ln in self.lines if ln["item_id"] == item_id), 0)

    def empty(self):
        return not self.lines and not self.lotus_coins and not self.moon_pearls


class TradeError(Exception):
    """A change that isn't allowed; the message is shown to the player."""


class Trade:
    def __init__(self, uid1, uid2, now=None):
        self.offers = {uid1: Offer(uid1), uid2: Offer(uid2)}
        self.order = (uid1, uid2)
        self.status = "open"           # open · complete · cancelled
        self.snapshot = None
        self.ended_by = None
        self.touched = time.time() if now is None else now

    def other(self, uid):
        return self.order[1] if uid == self.order[0] else self.order[0]

    def _changed(self, now=None):
        for o in self.offers.values():
            o.confirmed = False
        self.touched = time.time() if now is None else now

    def _open(self):
        if self.status != "open":
            raise TradeError("This trade is over.")

    # changes ──────────────────────────────────────────────────────────

    def set_item(self, conn, uid, item_id, qty):
        """Offer `qty` of one item (0 removes it). The quantity is checked against what the player owns."""
        self._open()
        offer = self.offers[uid]
        item = db.get_item(conn, uid, item_id)
        if item is None:
            raise TradeError("That item is no longer in your bag.")
        why = why_not_tradeable(item)
        if why:
            raise TradeError(why)
        qty = int(qty)
        if qty < 0:
            raise TradeError("The amount can't be negative.")
        if qty > item["qty"]:
            raise TradeError(f"You only have {item['qty']:,}.")
        line = next((ln for ln in offer.lines if ln["item_id"] == item_id), None)
        if qty == 0:
            if line:
                offer.lines.remove(line)
                self._changed()
            return
        if line:
            if line["qty"] == qty:
                return
            line["qty"] = qty
        else:
            if len(offer.lines) >= T.MAX_LINES:
                raise TradeError(f"An offer can hold {T.MAX_LINES} different items at most.")
            offer.lines.append({"item_id": item_id, "qty": qty})
        self._changed()

    def set_currency(self, conn, uid, currency, amount):
        self._open()
        if currency not in db.CURRENCY_COLUMNS:
            raise TradeError("Unknown currency.")
        amount = int(amount)
        if amount < 0:
            raise TradeError("The amount can't be negative.")
        have = db.get_player(conn, uid)[currency]
        if amount > have:
            raise TradeError(f"You only have {have:,}.")
        offer = self.offers[uid]
        if getattr(offer, currency) != amount:
            setattr(offer, currency, amount)
            self._changed()

    def confirm(self, uid):
        self._open()
        if all(o.empty() for o in self.offers.values()):
            raise TradeError("Both offers are empty. Add something first.")
        self.offers[uid].confirmed = True
        self.touched = time.time()
        return all(o.confirmed for o in self.offers.values())

    def unconfirm(self, uid):
        self.offers[uid].confirmed = False

    def cancel(self, uid=None):
        if self.status == "open":
            self.status = "cancelled"
            self.ended_by = uid

    # the swap ─────────────────────────────────────────────────────────

    def check(self, conn):
        """Everything still holds? Returns None, or the reason the trade can't go through."""
        for uid, offer in self.offers.items():
            p = db.get_player(conn, uid)
            if p is None:
                return "A trader no longer has a character."
            for cur in db.CURRENCY_COLUMNS:
                if getattr(offer, cur) > p[cur]:
                    return f"**{p['name']}** no longer has enough {cur.replace('_', ' ').title()}."
            for ln in offer.lines:
                it = db.get_item(conn, uid, ln["item_id"])
                if it is None or it["qty"] < ln["qty"]:
                    return f"**{p['name']}** no longer has everything they offered."
                why = why_not_tradeable(it)
                if why:
                    return f"**{p['name']}**: {it['name']}: {why}"
        for uid in self.offers:
            need = self._slots_after(conn, uid)
            cap = db.get_player(conn, uid)["bag_capacity"]
            if need > cap:
                p = db.get_player(conn, uid)
                return f"**{p['name']}**'s bag would be over full ({need} / {cap} slots)."
        return None

    def _slots_after(self, conn, uid):
        """How many bag slots `uid` would use after the trade."""
        used = db.slots_used(conn, uid)
        for ln in self.offers[uid].lines:               # stacks given away completely free a slot
            it = db.get_item(conn, uid, ln["item_id"])
            if it and ln["qty"] >= it["qty"] and db.uses_slot(it["category"], it["key"]):
                used -= 1
        mine = {(i["category"], i["key"]) for i in db.get_items(conn, uid) if i["category"] in db.BAG_STACKABLE}
        incoming = set()
        for ln in self.offers[self.other(uid)].lines:
            it = db.get_item(conn, self.other(uid), ln["item_id"])
            if it is None or not db.uses_slot(it["category"], it["key"]):
                continue
            if it["category"] in db.BAG_STACKABLE:
                k = (it["category"], it["key"])
                if k in mine or k in incoming:
                    continue
                incoming.add(k)
            used += 1
        return used

    def execute(self, conn, now=None):
        """Swap both offers in one transaction. Returns None when done, else the reason (nothing moved)."""
        self._open()
        if not all(o.confirmed for o in self.offers.values()):
            return "Both players must confirm."
        why = self.check(conn)
        if why:
            self._changed()
            return why
        now = time.time() if now is None else now
        a, b = self.order
        self.snapshot = {uid: offer_rows(conn, o) for uid, o in self.offers.items()}   # the card after the swap
        try:
            with conn:
                for giver, taker in ((a, b), (b, a)):
                    offer = self.offers[giver]
                    for ln in offer.lines:
                        _move_item(conn, giver, taker, ln["item_id"], ln["qty"])
                    for cur in db.CURRENCY_COLUMNS:
                        amt = getattr(offer, cur)
                        if amt:
                            _move_currency(conn, giver, taker, cur, amt, now)
        except _Abort as e:
            self._changed()
            self.snapshot = None
            return str(e)
        self.status = "complete"
        return None


class _Abort(Exception):
    pass


def _move_item(conn, giver, taker, item_id, qty):
    row = conn.execute("SELECT * FROM items WHERE id = ? AND user_id = ? AND equipped = 0", (item_id, giver)).fetchone()
    if row is None or row["qty"] < qty:
        raise _Abort("An offered item changed. Nothing was traded.")
    cat, key = row["category"], row["key"]
    if cat in db.BAG_STACKABLE:
        conn.execute("UPDATE items SET qty = qty - ? WHERE id = ?", (qty, item_id))
        conn.execute("DELETE FROM items WHERE id = ? AND qty <= 0", (item_id,))
        mine = conn.execute("SELECT id FROM items WHERE user_id = ? AND category = ? AND key = ?",
                            (taker, cat, key)).fetchone()
        if mine:
            conn.execute("UPDATE items SET qty = qty + ? WHERE id = ?", (qty, mine[0]))
        else:
            conn.execute("INSERT INTO items (user_id, category, key, name, grade, qty, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
                         (taker, cat, key, row["name"], row["grade"], qty, row["data"]))
    else:                                   # gear is unique: the item itself changes hands, buffs and passives intact
        conn.execute("UPDATE items SET user_id = ?, equipped = 0 WHERE id = ?", (taker, item_id))


def _move_currency(conn, giver, taker, cur, amt, now):
    for uid, delta in ((giver, -amt), (taker, amt)):
        bal = conn.execute(f"SELECT {cur} FROM players WHERE user_id = ?", (uid,)).fetchone()[0]
        new = bal + delta
        if new < 0:
            raise _Abort("Someone's balance changed. Nothing was traded.")
        conn.execute(f"UPDATE players SET {cur} = ? WHERE user_id = ?", (new, uid))
        conn.execute("INSERT INTO ledger (user_id, currency, delta, balance, reason, at) VALUES (?, ?, ?, ?, ?, ?)",
                     (uid, cur, delta, new, "Trade", now))
        conn.execute("DELETE FROM ledger WHERE user_id = ? AND id NOT IN "
                     "(SELECT id FROM ledger WHERE user_id = ? ORDER BY id DESC LIMIT ?)", (uid, uid, db.LEDGER_KEEP))


# ── plain data for the card ───────────────────────────────────────────

def offer_rows(conn, offer):
    """The offer's lines as card rows: icon, name, grade, qty, rarity colour key."""
    rows = []
    for ln in offer.lines:
        it = db.get_item(conn, offer.user_id, ln["item_id"])
        if it is None:
            continue
        label, key = bag.rarity(it)
        rows.append({"icon": bag.item_icon(it), "name": item_label(it), "grade": grade_label(it) if it["category"] != "herbs"
                     else it.get("grade") or label, "qty": ln["qty"], "color_key": key,
                     "unique": it["category"] not in db.BAG_STACKABLE})
    return rows


def card_data(conn, trade, names, view=None, note=None):
    """names: {uid: display name}; view: whose eyes (None = the public card)."""
    sides = []
    for uid in trade.order:
        o = trade.offers[uid]
        p = db.get_player(conn, uid)
        rows = trade.snapshot[uid] if trade.status == "complete" and trade.snapshot else offer_rows(conn, o)
        sides.append({"uid": uid, "name": names.get(uid) or p["name"], "realm": f"{p['realm']} {p['layer']}",
                      "rows": rows, "lotus_coins": o.lotus_coins, "moon_pearls": o.moon_pearls,
                      "confirmed": o.confirmed})
    n_conf = sum(s["confirmed"] for s in sides)
    if trade.status == "complete":
        status = ("complete", "Everything is in both bags")
    elif trade.status == "cancelled":
        who = names.get(trade.ended_by) if trade.ended_by else None
        status = ("cancelled", f"Cancelled by {who} · nothing changed hands" if who else "Nothing changed hands")
    elif n_conf == 1:
        waiting = next(s["name"] for s in sides if not s["confirmed"])
        status = ("one", f"Waiting for {waiting} to confirm")
    else:
        status = ("open", "Add items, then Review Trade to confirm")
    return {"sides": sides, "status": status, "note": note}



# ── plain data for the picker screens ─────────────────────────────────

def picker_categories(conn, user_id):
    counts = category_counts(conn, user_id)
    return [{"key": k, "label": label, "count": counts[k]} for k, label, _ in T.CATEGORIES]


def picker_row(item, offering=0):
    label, key = bag.rarity(item)
    return {"icon": bag.item_icon(item), "name": item_label(item), "grade": grade_label(item), "color_key": key,
            "owned": item["qty"], "offering": offering}


def picker_items(conn, user_id, category, grade, offer):
    items = tradeable_items(conn, user_id, category, grade) if grade else []
    return {"grades": [g for g, _ in grades_in(conn, user_id, category)],
            "items": [picker_row(it, offer.qty_of(it["id"])) for it in items]}
