"""
Daily quests (quests.py, docs/quests.md).

Each player gets QUESTS_PER_DAY quests a day, picked from quests.QUESTS with a seed of their id and
the UTC day, so the list is the same all day and new at midnight UTC. Progress is counted in
daily_counts as "quest:<event>" (record() is called where each activity finishes). A finished quest
is claimed once ("quest_claimed:<key>"); finishing them all adds a bonus and maybe a chest
("quest_bonus"), rolled with the same seed so claiming again can't reroll it.
"""
import random
import time

import quests as config

from . import db, loot
from . import player as rules

EVENTS = {q["event"] for q in config.QUESTS.values()}


def day(now=None):
    return db._day(time.time() if now is None else now)


def seconds_to_reset(now=None):
    now = time.time() if now is None else now
    return 86400 - int(now) % 86400


def record(conn, user_id, event, n=1, now=None):
    """Count `n` of an activity toward today's quests."""
    if event not in EVENTS or n <= 0:
        return
    for _ in range(int(n)):
        db.bump_daily(conn, user_id, "quest:" + event, now)


def todays_keys(user_id, now=None):
    """The quests of the day for this player: a weighted pick, the same all day."""
    rng = random.Random(f"quests:{user_id}:{day(now)}")
    pool = dict(config.QUESTS)
    keys = []
    while pool and len(keys) < config.QUESTS_PER_DAY:
        k = rng.choices(list(pool), weights=[q["weight"] for q in pool.values()])[0]
        keys.append(k)
        del pool[k]
    return keys


def coin_scale(player):
    return 1 + config.COIN_STEP_PER_REALM * rules.realm_index(player["realm"])


def board(conn, player, now=None):
    """Today's quests with progress, plus the all-done bonus. The data for the /daily card."""
    uid = player["user_id"]
    scale = coin_scale(player)
    rows = []
    for k in todays_keys(uid, now):
        q = config.QUESTS[k]
        have = min(q["n"], db.daily_count(conn, uid, "quest:" + q["event"], now))
        rows.append({"key": k, "name": q["name"], "text": q["text"].format(n=q["n"]), "icon": q["icon"],
                     "have": have, "need": q["n"], "done": have >= q["n"],
                     "claimed": bool(db.daily_count(conn, uid, "quest_claimed:" + k, now)),
                     "coins": round(q["coins"] * scale), "pearls": q["pearls"]})
    all_done = all(r["done"] for r in rows)
    bonus_claimed = bool(db.daily_count(conn, uid, "quest_bonus", now))
    return {"name": player["name"], "quests": rows, "reset_in": seconds_to_reset(now),
            "bonus": {"coins": round(config.ALL_DONE_COINS * scale), "pearls": config.ALL_DONE_PEARLS,
                      "chance": config.ALL_DONE_CHEST_CHANCE, "tiers": chest_odds(),
                      "ready": all_done and not bonus_claimed, "claimed": bonus_claimed,
                      "chest": bonus_chest(uid, now) if bonus_claimed else None,
                      "done": sum(r["done"] for r in rows), "of": len(rows)},
            "claimable": sum(r["done"] and not r["claimed"] for r in rows) + (all_done and not bonus_claimed)}


def chest_odds():
    """{tier: chance of that chest when finishing everything}."""
    total = sum(config.ALL_DONE_CHEST_TIERS.values())
    return {t: config.ALL_DONE_CHEST_CHANCE * w / total for t, w in config.ALL_DONE_CHEST_TIERS.items()}


def bonus_chest(user_id, now=None):
    """The chest tier the all-done bonus gives today (None = no chest). Fixed for the day."""
    rng = random.Random(f"quest-bonus:{user_id}:{day(now)}")
    if rng.random() >= config.ALL_DONE_CHEST_CHANCE:
        return None
    tiers = config.ALL_DONE_CHEST_TIERS
    return rng.choices(list(tiers), weights=list(tiers.values()))[0]


def _claim_once(conn, user_id, name, now):
    """Mark a reward claimed; False if it already was (two clicks at once can't both claim)."""
    with conn:
        done = conn.execute("INSERT INTO daily_counts (user_id, name, day, count) VALUES (?, ?, ?, 1) "
                            "ON CONFLICT(user_id, name, day) DO NOTHING", (user_id, name, day(now))).rowcount
    return bool(done)


def claim(conn, user_id, now=None):
    """Give every finished, unclaimed reward. Returns {coins, pearls, quests: [names], chest, bonus, bag_full}."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    b = board(conn, p, now)
    out = {"coins": 0, "pearls": 0, "quests": [], "chest": None, "bonus": False, "bag_full": False}
    for r in b["quests"]:
        if r["done"] and not r["claimed"] and _claim_once(conn, user_id, "quest_claimed:" + r["key"], now):
            out["coins"] += r["coins"]
            out["pearls"] += r["pearls"]
            out["quests"].append(r["name"])
    if b["bonus"]["ready"] and _claim_once(conn, user_id, "quest_bonus", now):
        tier = bonus_chest(user_id, now)
        if tier and not loot.store(conn, user_id, [loot.chest(tier)])[0]:
            with conn:                          # bag full: undo, so it can be claimed once a slot is free
                conn.execute("DELETE FROM daily_counts WHERE user_id = ? AND name = 'quest_bonus' AND day = ?",
                             (user_id, day(now)))
            out["bag_full"] = True
        else:
            out["bonus"] = True
            out["coins"] += b["bonus"]["coins"]
            out["pearls"] += b["bonus"]["pearls"]
            out["chest"] = tier
    if out["coins"]:
        db.change_currency(conn, user_id, "lotus_coins", out["coins"], "Daily quests", now=now)
    if out["pearls"]:
        db.change_currency(conn, user_id, "moon_pearls", out["pearls"], "Daily quests", now=now)
    return out
