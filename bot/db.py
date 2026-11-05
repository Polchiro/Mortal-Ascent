"""
SQLite player storage.

One row per Discord account in `players`, plus learned techniques in
`techniques`, bag contents in `items`, currency changes in `ledger` and command cooldowns
in `cooldowns`.
All functions take an open sqlite3.Connection so tests can use an in-memory
database.
"""
import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS players (
    user_id           INTEGER PRIMARY KEY,
    name              TEXT    NOT NULL,
    talent            TEXT    NOT NULL,
    realm             TEXT    NOT NULL DEFAULT 'Mortal',
    layer             INTEGER NOT NULL DEFAULT 1,
    qi                REAL    NOT NULL DEFAULT 0,
    lotus_coins       INTEGER NOT NULL DEFAULT 0,
    moon_pearls       INTEGER NOT NULL DEFAULT 0,
    blessing_tier     TEXT,
    blessing_expires  REAL,
    beasts_slain      INTEGER NOT NULL DEFAULT 0,
    breakthroughs     INTEGER NOT NULL DEFAULT 0,
    failed_breakthroughs INTEGER NOT NULL DEFAULT 0,
    created_at        REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS techniques (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES players(user_id) ON DELETE CASCADE,
    name        TEXT    NOT NULL,
    type        TEXT    NOT NULL,
    grade       TEXT    NOT NULL,
    mastery_exp INTEGER NOT NULL DEFAULT 0,
    equipped    INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS techniques_user ON techniques(user_id);

CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES players(user_id) ON DELETE CASCADE,
    category    TEXT    NOT NULL,   -- manuals, weapons, pills, materials, chests
    key         TEXT    NOT NULL,   -- technique key, pill grade, material name, chest tier, weapon type
    name        TEXT    NOT NULL,
    grade       TEXT,               -- technique/pill grade or weapon/chest tier
    qty         INTEGER NOT NULL DEFAULT 1,
    data        TEXT,               -- JSON extras (weapon buffs)
    equipped    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS items_user ON items(user_id);

CREATE TABLE IF NOT EXISTS daily_counts (
    user_id     INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    day         TEXT    NOT NULL,   -- UTC date, YYYY-MM-DD
    count       INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, name, day)
);

CREATE TABLE IF NOT EXISTS handled_messages (
    message_id  INTEGER PRIMARY KEY,   -- an "m" command message that a copy of the bot answered
    at          REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS ledger (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    currency    TEXT    NOT NULL,   -- a key of economy.CURRENCIES (lotus_coins, moon_pearls)
    delta       INTEGER NOT NULL,   -- what actually changed (+ gained, - spent)
    balance     INTEGER NOT NULL,   -- balance right after
    reason      TEXT    NOT NULL,
    at          REAL    NOT NULL
);
CREATE INDEX IF NOT EXISTS ledger_user ON ledger(user_id, id);

CREATE TABLE IF NOT EXISTS cooldowns (
    user_id     INTEGER NOT NULL,
    name        TEXT    NOT NULL,
    until       REAL    NOT NULL,
    PRIMARY KEY (user_id, name)
);
"""

# Columns added to `players` after the first release. Existing databases get
# them through ALTER TABLE in connect(), so nobody has to delete their .db file.
PLAYER_COLUMNS = {
    "injured_until":        "REAL",
    "pill_grade":           "TEXT",
    "pill_mult":            "REAL",
    "pill_expires":         "REAL",
    "toxicity":             "INTEGER NOT NULL DEFAULT 0",
    "toxicity_at":          "REAL",
    "blessed_land":         "TEXT",
    "blessed_land_expires": "REAL",
    "last_challenge":       "TEXT",
    "bag_capacity":         "INTEGER NOT NULL DEFAULT 60",
    "qi_collected_at":      "REAL",      # last /meditate (passive Qi gathers from here)
    "seclusion_start":      "REAL",
    "seclusion_end":        "REAL",
    "fate_rerolls":         "INTEGER NOT NULL DEFAULT 0",    # Lotus Coin rerolls used (cost ×1.5 each)
    "king_kills":           "TEXT NOT NULL DEFAULT ''",       # realms whose Beast King you helped slay
}
TECHNIQUE_COLUMNS = {
    "stage": "INTEGER NOT NULL DEFAULT 0",   # mastery stage index; raised only by passing a trial
}

BAG_STACKABLE = {"manuals", "pills", "materials", "chests"}   # weapons are unique (rolled buffs)


def connect(path):
    conn = sqlite3.connect(path, timeout=10)   # wait for another copy's write instead of failing
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    with conn:
        for table, cols in (("players", PLAYER_COLUMNS), ("techniques", TECHNIQUE_COLUMNS)):
            have = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            for col, decl in cols.items():
                if col not in have:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")
    return conn


def get_player(conn, user_id):
    row = conn.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def create_player(conn, user_id, name, talent, lotus_coins, techniques):
    """Insert a new player with their starting techniques. Returns the player dict."""
    with conn:
        conn.execute(
            "INSERT INTO players (user_id, name, talent, lotus_coins, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, name, talent, lotus_coins, time.time()),
        )
        conn.executemany(
            "INSERT INTO techniques (user_id, name, type, grade) VALUES (?, ?, ?, ?)",
            [(user_id, t["name"], t["type"], t["grade"]) for t in techniques],
        )
        if lotus_coins:
            conn.execute("INSERT INTO ledger (user_id, currency, delta, balance, reason, at) VALUES (?, ?, ?, ?, ?, ?)",
                         (user_id, "lotus_coins", lotus_coins, lotus_coins, "Starting purse", time.time()))
    return get_player(conn, user_id)


def get_techniques(conn, user_id, equipped_only=True):
    sql = "SELECT * FROM techniques WHERE user_id = ?"
    if equipped_only:
        sql += " AND equipped = 1"
    return [dict(r) for r in conn.execute(sql + " ORDER BY id", (user_id,))]


def server_rank(conn, user_id, realm_order):
    """1-based rank by realm, then layer, then Qi. realm_order: list of realm names, lowest first."""
    me = get_player(conn, user_id)
    key = lambda p: (realm_order.index(p["realm"]), p["layer"], p["qi"])
    mine = key(me)
    ahead = sum(1 for r in conn.execute("SELECT realm, layer, qi FROM players") if key(r) > mine)
    return ahead + 1


def update_player(conn, user_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k} = ?" for k in fields)
    with conn:
        conn.execute(f"UPDATE players SET {cols} WHERE user_id = ?", (*fields.values(), user_id))


# ── Currencies (every change goes through change_currency, which keeps the ledger) ──

CURRENCY_COLUMNS = ("lotus_coins", "moon_pearls")   # economy.CURRENCIES that are live
LEDGER_KEEP = 100                                   # newest ledger rows kept per player


def change_currency(conn, user_id, currency, delta, reason, clamp=False, now=None):
    """Add `delta` (negative to spend) to one currency and write a ledger row in the same step.

    A balance can never go below 0: a spend larger than the balance changes nothing and returns
    None, unless clamp=True (then it takes what there is, e.g. bandits stealing). The update only
    applies if the balance is still the one just read, so two changes at once can't both spend the
    same coins. Returns the new balance, or None (no such player, or not enough)."""
    if currency not in CURRENCY_COLUMNS:
        raise ValueError(f"unknown currency {currency!r}")
    delta = int(delta)
    now = time.time() if now is None else now
    for _ in range(5):
        row = conn.execute(f"SELECT {currency} FROM players WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        balance = row[0]
        new = balance + delta
        if new < 0:
            if not clamp:
                return None
            new = 0
        if new == balance:
            return balance
        with conn:
            done = conn.execute(f"UPDATE players SET {currency} = ? WHERE user_id = ? AND {currency} = ?",
                                (new, user_id, balance)).rowcount
            if done:
                conn.execute("INSERT INTO ledger (user_id, currency, delta, balance, reason, at) "
                             "VALUES (?, ?, ?, ?, ?, ?)", (user_id, currency, new - balance, new, reason, now))
                conn.execute("DELETE FROM ledger WHERE user_id = ? AND id NOT IN "
                             "(SELECT id FROM ledger WHERE user_id = ? ORDER BY id DESC LIMIT ?)",
                             (user_id, user_id, LEDGER_KEEP))
                return new
    raise RuntimeError("balance kept changing; try again")


def spend(conn, user_id, currency, amount, reason):
    """Take `amount` (> 0) if the player has it. Returns the new balance, or None if not enough."""
    if int(amount) <= 0:
        raise ValueError("amount must be positive")
    return change_currency(conn, user_id, currency, -int(amount), reason)


def add_coins(conn, user_id, amount, reason="Lotus Coins"):
    """Give (or, with a negative amount, take up to everything) Lotus Coins."""
    change_currency(conn, user_id, "lotus_coins", amount, reason, clamp=True)


def ledger(conn, user_id, limit=10):
    return [dict(r) for r in conn.execute(
        "SELECT * FROM ledger WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit))]


# ── Techniques ────────────────────────────────────────────────────────

def learn_technique(conn, user_id, name, type_, grade, slots=2):
    """Learn a technique and equip it (see equip_technique). Returns its id."""
    with conn:
        cur = conn.execute("INSERT INTO techniques (user_id, name, type, grade, equipped) VALUES (?, ?, ?, ?, 0)",
                           (user_id, name, type_, grade))
    equip_technique(conn, user_id, cur.lastrowid, slots)
    return cur.lastrowid


def equip_technique(conn, user_id, technique_id, slots=2):
    """Equip a learned technique. Slots: 1 attack + 1 defense, plus a flex slot when slots == 3
    (technique.md). Fills a free slot if there is one, otherwise replaces the oldest equipped
    technique of the same type. Returns the replaced technique's name or None."""
    tech = get_technique(conn, user_id, technique_id)
    equipped = get_techniques(conn, user_id)
    if not tech or tech["equipped"]:
        return None
    same = [t for t in equipped if t["type"] == tech["type"]]
    other = [t for t in equipped if t["type"] != tech["type"]]
    replaced = None
    if len(same) >= slots - 1 or len(equipped) >= slots:
        replaced = same[0] if same else (other[0] if len(other) > 1 else None)
    with conn:
        if replaced:
            conn.execute("UPDATE techniques SET equipped = 0 WHERE id = ?", (replaced["id"],))
        conn.execute("UPDATE techniques SET equipped = 1 WHERE id = ?", (technique_id,))
    return replaced["name"] if replaced else None


def unequip_technique(conn, user_id, technique_id):
    """Unequip, as long as one technique of that type stays equipped. Returns True on success."""
    tech = get_technique(conn, user_id, technique_id)
    if not tech or not tech["equipped"]:
        return False
    same = [t for t in get_techniques(conn, user_id) if t["type"] == tech["type"]]
    if len(same) < 2:
        return False
    with conn:
        conn.execute("UPDATE techniques SET equipped = 0 WHERE id = ?", (technique_id,))
    return True


def add_mastery(conn, technique_id, exp):
    with conn:
        conn.execute("UPDATE techniques SET mastery_exp = mastery_exp + ? WHERE id = ?", (int(exp), technique_id))


def set_mastery(conn, technique_id, exp=None, stage=None):
    with conn:
        if exp is not None:
            conn.execute("UPDATE techniques SET mastery_exp = ? WHERE id = ?", (int(exp), technique_id))
        if stage is not None:
            conn.execute("UPDATE techniques SET stage = ? WHERE id = ?", (stage, technique_id))


def get_technique(conn, user_id, technique_id):
    row = conn.execute("SELECT * FROM techniques WHERE id = ? AND user_id = ?", (technique_id, user_id)).fetchone()
    return dict(row) if row else None


# ── Bag ───────────────────────────────────────────────────────────────

def _item(row):
    d = dict(row)
    d["data"] = json.loads(d["data"]) if d["data"] else {}
    return d


def get_items(conn, user_id, category=None):
    sql, args = "SELECT * FROM items WHERE user_id = ?", [user_id]
    if category:
        sql += " AND category = ?"
        args.append(category)
    return [_item(r) for r in conn.execute(sql + " ORDER BY equipped DESC, id", args)]


def get_item(conn, user_id, item_id):
    row = conn.execute("SELECT * FROM items WHERE id = ? AND user_id = ?", (item_id, user_id)).fetchone()
    return _item(row) if row else None


def slots_used(conn, user_id):
    return conn.execute("SELECT COUNT(*) FROM items WHERE user_id = ?", (user_id,)).fetchone()[0]


def category_counts(conn, user_id):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT category, COUNT(*) FROM items WHERE user_id = ? GROUP BY category", (user_id,))}


def add_item(conn, user_id, category, key, name, grade=None, qty=1, data=None):
    """Put an item in the bag. Stackable items merge into an existing stack.
    Returns False (and stores nothing) when a new slot is needed but the bag is full."""
    if category in BAG_STACKABLE:
        row = conn.execute("SELECT id FROM items WHERE user_id = ? AND category = ? AND key = ?",
                           (user_id, category, key)).fetchone()
        if row:
            with conn:
                conn.execute("UPDATE items SET qty = qty + ? WHERE id = ?", (qty, row[0]))
            return True
    cap = conn.execute("SELECT bag_capacity FROM players WHERE user_id = ?", (user_id,)).fetchone()[0]
    if slots_used(conn, user_id) >= cap:
        return False
    with conn:
        conn.execute(
            "INSERT INTO items (user_id, category, key, name, grade, qty, data) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, category, key, name, grade, qty, json.dumps(data) if data else None))
    return True


def discard_item(conn, user_id, item_id, qty=1):
    """Throw away `qty` of an item the player owns. Refuses (returns False) if the item is gone,
    belongs to someone else, is equipped, or the stack is smaller than `qty`."""
    if qty < 1:
        return False
    with conn:
        done = conn.execute("UPDATE items SET qty = qty - ? WHERE id = ? AND user_id = ? AND equipped = 0 "
                            "AND qty >= ?", (qty, item_id, user_id, qty)).rowcount
        conn.execute("DELETE FROM items WHERE id = ? AND qty <= 0", (item_id,))
    return bool(done)


def remove_item(conn, item_id, qty=1):
    with conn:
        conn.execute("UPDATE items SET qty = qty - ? WHERE id = ?", (qty, item_id))
        conn.execute("DELETE FROM items WHERE id = ? AND qty <= 0", (item_id,))


def equipped_weapon(conn, user_id):
    row = conn.execute("SELECT * FROM items WHERE user_id = ? AND category = 'weapons' AND equipped = 1",
                       (user_id,)).fetchone()
    return _item(row) if row else None


def unequip_weapon(conn, user_id):
    with conn:
        conn.execute("UPDATE items SET equipped = 0 WHERE user_id = ? AND category = 'weapons'", (user_id,))


def equip_weapon(conn, user_id, item_id):
    with conn:
        conn.execute("UPDATE items SET equipped = 0 WHERE user_id = ? AND category = 'weapons'", (user_id,))
        conn.execute("UPDATE items SET equipped = 1 WHERE id = ? AND user_id = ?", (item_id, user_id))


# ── Cooldowns ─────────────────────────────────────────────────────────

def cooldown_left(conn, user_id, name, now=None):
    """Seconds until the cooldown ends (0 when ready)."""
    now = time.time() if now is None else now
    row = conn.execute("SELECT until FROM cooldowns WHERE user_id = ? AND name = ?", (user_id, name)).fetchone()
    return max(0.0, row[0] - now) if row else 0.0


def set_cooldown(conn, user_id, name, seconds, now=None):
    now = time.time() if now is None else now
    with conn:
        conn.execute("INSERT OR REPLACE INTO cooldowns (user_id, name, until) VALUES (?, ?, ?)",
                     (user_id, name, now + seconds))


def claim_message(conn, message_id, now=None):
    """Claim an "m" command message so it is answered once. If two copies of the bot share this
    database, both see the message but only the first to claim it answers. True if we got it."""
    now = time.time() if now is None else now
    with conn:
        got = conn.execute("INSERT OR IGNORE INTO handled_messages (message_id, at) VALUES (?, ?)",
                           (message_id, now)).rowcount == 1
        if got and message_id % 100 == 0:       # now and then, forget claims older than a day
            conn.execute("DELETE FROM handled_messages WHERE at < ?", (now - 86400,))
    return got


def clear_cooldown(conn, user_id, name):
    with conn:
        conn.execute("DELETE FROM cooldowns WHERE user_id = ? AND name = ?", (user_id, name))


# ── Daily counters (diminishing returns) ──────────────────────────────

def _day(now):
    return time.strftime("%Y-%m-%d", time.gmtime(now))


def daily_count(conn, user_id, name, now=None):
    now = time.time() if now is None else now
    row = conn.execute("SELECT count FROM daily_counts WHERE user_id = ? AND name = ? AND day = ?",
                       (user_id, name, _day(now))).fetchone()
    return row[0] if row else 0


def bump_daily(conn, user_id, name, now=None):
    now = time.time() if now is None else now
    with conn:
        conn.execute("INSERT INTO daily_counts (user_id, name, day, count) VALUES (?, ?, ?, 1) "
                     "ON CONFLICT(user_id, name, day) DO UPDATE SET count = count + 1",
                     (user_id, name, _day(now)))
