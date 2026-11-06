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

import forge

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
    category    TEXT    NOT NULL,   -- manuals, weapons, armor, artifacts, pills, herbs, materials, chests
    key         TEXT    NOT NULL,   -- technique key, pill grade, "tier:type:age" herb, chest tier, weapon/armor type,
                                    -- artifact family
    name        TEXT    NOT NULL,
    grade       TEXT,               -- technique/pill grade or weapon/armor/artifact/chest tier
    qty         INTEGER NOT NULL DEFAULT 1,
    data        TEXT,               -- JSON extras (weapon / armor buffs, artifact family)
    equipped    INTEGER NOT NULL DEFAULT 0      -- 1 = worn; artifacts store their slot (1 or 2)
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

CREATE TABLE IF NOT EXISTS duels (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at    REAL    NOT NULL,
    ended_at      REAL    NOT NULL,
    channel_id    INTEGER,
    p1_id         INTEGER NOT NULL,   -- the challenger
    p2_id         INTEGER NOT NULL,
    p1_realm      TEXT    NOT NULL,   -- "Martial Warrior 3" (realm and layer before the fair-duel levelling)
    p2_realm      TEXT    NOT NULL,
    fair_realm    TEXT    NOT NULL,   -- the lower realm and layer both fought at
    p1_techniques TEXT    NOT NULL,   -- JSON list of equipped technique names
    p2_techniques TEXT    NOT NULL,
    winner_id     INTEGER,            -- NULL for a draw
    reason        TEXT    NOT NULL,   -- ko, time (turn limit), forfeit (fled), timeouts
    turns         INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS duel_moves (
    duel_id     INTEGER NOT NULL REFERENCES duels(id) ON DELETE CASCADE,
    turn        INTEGER NOT NULL,
    user_id     INTEGER NOT NULL,
    move        TEXT    NOT NULL,     -- strike, guard, break, attack_tech, defense_tech
    technique   TEXT,                 -- the technique's name for attack_tech / defense_tech
    timed_out   INTEGER NOT NULL DEFAULT 0,
    damage      INTEGER NOT NULL DEFAULT 0,   -- damage this player dealt that turn
    hp_after    INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS duel_moves_duel ON duel_moves(duel_id);

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
    "qi_collected_at":      "REAL",      # passive Qi was last banked here (it gathers from this time on)
    "seclusion_start":      "REAL",
    "seclusion_end":        "REAL",
    "fate_rerolls":         "INTEGER NOT NULL DEFAULT 0",    # Lotus Coin rerolls used (cost ×1.5 each)
    "king_kills":           "TEXT NOT NULL DEFAULT ''",       # realms whose Beast King you helped slay
    # /gather (docs/alchemy.md)
    "herb_streak":          "INTEGER NOT NULL DEFAULT 0",    # Herbal Insight: correct picks in a row
    "herbs_gathered":       "INTEGER NOT NULL DEFAULT 0",
    "spirit_check_in":      "INTEGER",                       # gathers until the next Wandering Spirit check
    "spirit_check_fails":   "INTEGER NOT NULL DEFAULT 0",
    "gather_paused_until":  "REAL",
    "gather_flag":          "TEXT",                          # why gathering was flagged for review (no ban)
    "alchemy_exp":          "INTEGER NOT NULL DEFAULT 0",    # alchemist rank comes from this (alchemy.py)
    # /duel (docs/pvp.md)
    "duels_won":            "INTEGER NOT NULL DEFAULT 0",
    "duels_lost":           "INTEGER NOT NULL DEFAULT 0",
    # Qi kept while the bar is full at a gate (bot/player.py add_qi); flows on after a breakthrough
    "qi_overflow":          "REAL NOT NULL DEFAULT 0",
    # "Your Qi is full" ping (bot/passive.py, /settings)
    "qi_pings":             "INTEGER NOT NULL DEFAULT 1",    # 0 = the player turned the pings off
    "qi_ping_gate":         "TEXT",                          # the gate ("Mortal:3") already pinged about
    "last_channel_id":      "INTEGER",                       # where the player last used the bot
}
TECHNIQUE_COLUMNS = {
    "stage": "INTEGER NOT NULL DEFAULT 0",   # mastery stage index; raised only by passing a trial
}

BAG_STACKABLE = {"manuals", "pills", "herbs", "materials", "chests"}   # gear is unique (rolled buffs, slots)


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
    replace_old_herbs(conn)
    return conn


def replace_old_herbs(conn):
    """The herbs from before alchemy (Dew Lotus Petal, Tiger Bone Moss, ...) are no longer in the game.
    Any still in a bag become 10-year Mortal herbs of the closest kind, so nobody loses them."""
    from .loot import OLD_HERBS, herb
    rows = conn.execute("SELECT * FROM items WHERE category = 'materials' AND key IN (%s)"
                        % ",".join("?" * len(OLD_HERBS)), list(OLD_HERBS)).fetchall()
    for r in rows:
        new = herb("Mortal", OLD_HERBS[r["key"]], 10)
        with conn:
            conn.execute("DELETE FROM items WHERE id = ?", (r["id"],))
            row = conn.execute("SELECT id FROM items WHERE user_id = ? AND category = 'herbs' AND key = ?",
                               (r["user_id"], new["key"])).fetchone()
            if row:
                conn.execute("UPDATE items SET qty = qty + ? WHERE id = ?", (r["qty"], row[0]))
            else:
                conn.execute("INSERT INTO items (user_id, category, key, name, grade, qty, data) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?)", (r["user_id"], "herbs", new["key"], new["name"],
                                                              new["grade"], r["qty"], json.dumps(new["data"])))


def get_player(conn, user_id):
    """The player's row as a dict, plus "artifact_fx": {effect: value} of the artifacts they wear
    (bot/gear.py), so every rule that has the player can apply them."""
    row = conn.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return None
    from . import gear
    p = dict(row)
    p["artifact_fx"] = gear.artifact_effects(equipped_artifacts(conn, user_id))
    return p


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
    key = lambda p: (realm_order.index(p["realm"]), p["layer"], p["qi"] + (p["qi_overflow"] or 0))
    mine = key(me)
    ahead = sum(1 for r in conn.execute("SELECT realm, layer, qi, qi_overflow FROM players") if key(r) > mine)
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
    return [_item(r) for r in conn.execute(sql + " ORDER BY equipped > 0 DESC, equipped, id", args)]


def get_item(conn, user_id, item_id):
    row = conn.execute("SELECT * FROM items WHERE id = ? AND user_id = ?", (item_id, user_id)).fetchone()
    return _item(row) if row else None


# Forging materials (forge.py) live in the materials pouch and use no bag slot; Beast Cores still do.
FREE_SLOT_SQL = "category = 'materials' AND key NOT LIKE 'core:%'"


def uses_slot(category, key):
    return forge.MATERIALS_USE_BAG_SLOTS or not (category == "materials" and not key.startswith("core:"))


def slots_used(conn, user_id):
    free = "" if forge.MATERIALS_USE_BAG_SLOTS else f" AND NOT ({FREE_SLOT_SQL})"
    return conn.execute("SELECT COUNT(*) FROM items WHERE user_id = ?" + free, (user_id,)).fetchone()[0]


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
    if uses_slot(category, key) and slots_used(conn, user_id) >= cap:
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
    row = conn.execute("SELECT * FROM items WHERE user_id = ? AND category = 'weapons' AND equipped > 0",
                       (user_id,)).fetchone()
    return _item(row) if row else None


def unequip_weapon(conn, user_id):
    with conn:
        conn.execute("UPDATE items SET equipped = 0 WHERE user_id = ? AND category = 'weapons'", (user_id,))


def equip_weapon(conn, user_id, item_id):
    equip_single(conn, user_id, "weapons", item_id)


def equip_single(conn, user_id, category, item_id):
    """Wear this item in its category's only slot (weapon, armor), taking off whatever was there."""
    with conn:
        conn.execute("UPDATE items SET equipped = 0 WHERE user_id = ? AND category = ?", (user_id, category))
        conn.execute("UPDATE items SET equipped = 1 WHERE id = ? AND user_id = ? AND category = ?",
                     (item_id, user_id, category))


def equipped_armor(conn, user_id):
    row = conn.execute("SELECT * FROM items WHERE user_id = ? AND category = 'armor' AND equipped > 0",
                       (user_id,)).fetchone()
    return _item(row) if row else None


def equipped_artifacts(conn, user_id):
    """Worn artifacts, slot 1 first. `equipped` holds the slot number."""
    return [_item(r) for r in conn.execute(
        "SELECT * FROM items WHERE user_id = ? AND category = 'artifacts' AND equipped > 0 ORDER BY equipped",
        (user_id,))]


def equip_artifact(conn, user_id, item_id, slot):
    with conn:
        conn.execute("UPDATE items SET equipped = 0 WHERE user_id = ? AND category = 'artifacts' AND equipped = ?",
                     (user_id, slot))
        conn.execute("UPDATE items SET equipped = ? WHERE id = ? AND user_id = ? AND category = 'artifacts'",
                     (slot, item_id, user_id))


def unequip_category(conn, user_id, category):
    with conn:
        conn.execute("UPDATE items SET equipped = 0 WHERE user_id = ? AND category = ?", (user_id, category))


def unequip_item(conn, user_id, item_id):
    with conn:
        return conn.execute("UPDATE items SET equipped = 0 WHERE id = ? AND user_id = ? AND equipped > 0",
                            (item_id, user_id)).rowcount > 0


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


# ── Duels (docs/pvp.md) ───────────────────────────────────────────────

def save_duel(conn, duel, channel_id=None, started_at=None, now=None):
    """Log a finished duel and every move, and count the win / loss. Returns the duel's id."""
    now = time.time() if now is None else now
    a, b = duel.sides
    fair = f"{duel.fair[0]} {duel.fair[1]}" if duel.fair else ""
    with conn:
        cur = conn.execute(
            "INSERT INTO duels (started_at, ended_at, channel_id, p1_id, p2_id, p1_realm, p2_realm, fair_realm, "
            "p1_techniques, p2_techniques, winner_id, reason, turns) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (started_at or now, now, channel_id, a.uid, b.uid, f"{a.realm} {a.layer}", f"{b.realm} {b.layer}", fair,
             json.dumps([t["name"] for t in a.techs]), json.dumps([t["name"] for t in b.techs]),
             duel.winner.uid if duel.winner else None, duel.reason, len(duel.history)))
        duel_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO duel_moves (duel_id, turn, user_id, move, technique, timed_out, damage, hp_after) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(duel_id, t["turn"], m["user_id"], m["move"], m["technique"], int(m["timed_out"]), m["damage"], m["hp_after"])
             for t in duel.history for m in t["moves"]])
        if duel.winner:
            conn.execute("UPDATE players SET duels_won = duels_won + 1 WHERE user_id = ?", (duel.winner.uid,))
            conn.execute("UPDATE players SET duels_lost = duels_lost + 1 WHERE user_id = ?", (duel.loser().uid,))
    return duel_id


def duel_stats(conn):
    """For balancing: every move and technique picked in duels.
    Returns ({"duels", "draws", "avg_turns"}, [{"name", "kind", "picks", "duels", "wins"}, ...] most picked first).
    picks = turns it was played; duels = duels where a player played it at least once; wins = how many of those
    that player won."""
    row = conn.execute("SELECT COUNT(*) AS n, SUM(winner_id IS NULL) AS draws, AVG(turns) AS turns FROM duels").fetchone()
    summary = {"duels": row["n"], "draws": row["draws"] or 0, "avg_turns": row["turns"] or 0}
    rows = conn.execute("""
        SELECT COALESCE(m.technique, m.move) AS name, m.move AS kind, COUNT(*) AS picks,
               COUNT(DISTINCT m.duel_id || ':' || m.user_id) AS duels,
               COUNT(DISTINCT CASE WHEN d.winner_id = m.user_id THEN m.duel_id END) AS wins
        FROM duel_moves m JOIN duels d ON d.id = m.duel_id
        WHERE m.timed_out = 0
        GROUP BY name, kind ORDER BY picks DESC, name""").fetchall()
    return summary, [dict(r) for r in rows]
