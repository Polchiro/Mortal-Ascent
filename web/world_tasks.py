"""
Today's tasks in the open world (docs/world.md "Today's tasks").

Every player gets PER_DAY tasks a day from TASKS, picked with a seed of their id and the UTC day (like the Discord
/daily quests, bot/quests.py), so the list stays the same all day and is new at midnight UTC. Progress is counted in
the existing daily_counts table as "world:<key>": record() is called where each thing happens out in the world
(a herb picked, a beast beaten, a glint looked into, a place reached, a trip banked). A task pays its Lotus Coins
the moment it is done, scaled by realm exactly like the quests (bot/quests.coin_scale); finishing all of the day's
tasks adds ALL_DONE_COINS. Every payment goes through db.add_coins, so it is in the ledger.

These are separate from the Discord /daily quests: those are unchanged, and the same herb or beast counts for both.
SHOAIB: the numbers below are the only place to change what a task asks or pays.
"""
import random
import time

from bot import db
from bot import quests as quest_rules

# key → what it asks (n times) and what it pays (Lotus Coins at Mortal; × the realm's coin scale)
TASKS = {
    "herbs":  {"text": "Pick {n} herbs out in the world",      "n": 5, "coins": 120},
    "beasts": {"text": "Defeat {n} beasts in the Moon Forest", "n": 2, "coins": 150},
    "finds":  {"text": "Look into {n} glints in the grass",     "n": 2, "coins": 120},
    "shrine": {"text": "Walk all the way to the Shrine Grove",  "n": 1, "coins": 100},
    "bank":   {"text": "Bring a trip's finds home to town",     "n": 1, "coins": 120},
    "seams":  {"text": "Dig {n} seams in the Ironvein Quarry",  "n": 5, "coins": 120},
}
PER_DAY = 3
ALL_DONE_COINS = 150           # grows with the realm like the tasks' coins
PREFIX = "world:"


def day(now):
    return time.strftime("%Y-%m-%d", time.gmtime(now))


def today(uid, now):
    """Today's task keys for this player, the same all day (seeded by id and UTC day)."""
    rng = random.Random(f"world-tasks:{uid}:{day(now)}")
    return sorted(rng.sample(sorted(TASKS), PER_DAY), key=list(TASKS).index)


def _pay(player, base):
    return round(base * quest_rules.coin_scale(player))


def board(conn, uid, now=None):
    """Today's tasks with progress, for the map screen: [{key, text, have, n, coins, done}], and the all-done bonus."""
    now = time.time() if now is None else now
    p = db.get_player(conn, uid)
    if p is None:
        return None
    rows = []
    for k in today(uid, now):
        t = TASKS[k]
        have = min(t["n"], db.daily_count(conn, uid, PREFIX + k, now))
        rows.append({"key": k, "text": t["text"].format(n=t["n"]), "have": have, "n": t["n"],
                     "coins": f"{_pay(p, t['coins']):,}", "done": have >= t["n"]})
    return {"tasks": rows, "bonus": f"{_pay(p, ALL_DONE_COINS):,}", "all": all(r["done"] for r in rows)}


def record(conn, uid, key, now=None):
    """Something counted towards a task happened. If it is one of today's tasks and this finishes it, it pays (and
    the all-done bonus with the last one). Returns the lines to tell the player (empty when nothing was finished)."""
    now = time.time() if now is None else now
    if key not in today(uid, now):
        return []
    t = TASKS[key]
    if db.daily_count(conn, uid, PREFIX + key, now) >= t["n"]:
        return []                                       # done already today
    db.bump_daily(conn, uid, PREFIX + key, now)
    if db.daily_count(conn, uid, PREFIX + key, now) != t["n"]:
        return []
    p = db.get_player(conn, uid)
    text = t["text"].format(n=t["n"])
    coins = _pay(p, t["coins"])
    db.add_coins(conn, uid, coins, f"World task: {text}")
    out = [f"Task done: {text} · +{coins:,} Lotus Coins"]
    if all(db.daily_count(conn, uid, PREFIX + k, now) >= TASKS[k]["n"] for k in today(uid, now)):
        bonus = _pay(p, ALL_DONE_COINS)
        db.add_coins(conn, uid, bonus, "World tasks: all done today")
        out.append(f"All of today's tasks done · +{bonus:,} Lotus Coins")
    return out
