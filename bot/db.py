"""
SQLite player storage.

One row per Discord account in `players`, plus learned techniques in
`techniques`. All functions take an open sqlite3.Connection so tests can
use an in-memory database.
"""
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
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
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
