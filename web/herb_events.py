"""
Shared rare herb events on the website (docs/world.md "A heavenly phenomenon"; SHOAIB approved the trial Nov 25 2026).
WEBSITE ONLY. Ordinary gathering is untouched: every player keeps their own herbs.

PER_DAY times a day (UTC), at random moments, a strange light rises somewhere in the Moon Forest: one spirit herb that
everyone can see, at one of the forest lands' far clearings. Whoever is on the website is told that a light has
risen over the Moon Forest, not where. Kneel at it and you play the ordinary gathering round for it (your own four
plants, the old-herb rules); the first right answer the server handles pulls it free. It gives a herb AGE years old,
of the event's type, at the grade the claimant's own realm rolls (alchemy.herb_grade_odds), so it is worth having at
every realm. It fades MINUTES after it rose if nobody claimed it.

Fairness: a player may claim WINS_PER_DAY a day; a round another player beat you to is called off at no cost (no
streak lost); each player may kneel once at each event; the Wandering Spirit never interrupts an event's round.

The day's events are rows in the database (world_events), made the first time anyone looks that day: place, spot,
type, when. The claim is one UPDATE that only succeeds while nobody has claimed it and it hasn't ended, so two right
answers at the same moment cannot both win, across however many copies of the website share the database.
A restart keeps the events (they are in the database); who has tried which is kept in memory.
"""
import os
import random
import threading
import time

import alchemy

from bot import db, loot

from . import land

ENABLED = os.environ.get("MA_HERB_EVENTS", "on").lower() not in ("off", "0", "no")
PER_DAY = 2
MINUTES = 20
AGE = 500
WINS_PER_DAY = 1
REGION = "moon_forest"
REGION_NAME = "Moon Forest"
LANDS = ("forest_edge", "deep_woods", "shrine_grove")
REACH = 2.0                           # how close (tiles) to kneel at it
AFTER = 60                            # seconds its fading still shows after it is claimed or runs out
WON = "world:event_won"               # a player's claims today, in daily_counts
WHERE = "the light of a heavenly phenomenon"


def _day(now):
    return time.strftime("%Y-%m-%d", time.gmtime(now))


def _day_start(now):
    return now - now % 86400


class Events:
    def __init__(self, clock=time.time, rng=None):
        self.clock = clock
        self.rng = rng or random.Random()
        self.tried = {}                   # event id → {player ids who knelt at it}
        self.lock = threading.Lock()
        self._made = set()

    def ensure(self, conn):
        """Make today's events if nobody has yet (a unique (day, n) keeps two copies of the website from both doing it)."""
        now = self.clock()
        day = _day(now)
        if day in self._made:
            return
        with self.lock:
            have = conn.execute("SELECT COUNT(*) FROM world_events WHERE day = ?", (day,)).fetchone()[0]
            if have < PER_DAY:
                start = _day_start(now)
                with conn:
                    for n in range(PER_DAY):
                        place = self.rng.choice(LANDS)
                        x, y = self.rng.choice(land.LANDS[place]["secret"])
                        at = start + self.rng.uniform(0, 86400 - MINUTES * 60)
                        conn.execute("INSERT OR IGNORE INTO world_events (day, n, place, x, y, type, starts, ends) "
                                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                     (day, n, place, x, y, loot.pick(alchemy.REGION_HERB_TYPES[REGION], self.rng),
                                      at, at + MINUTES * 60))
            self._made.add(day)

    def current(self, conn):
        """The event showing now: live (risen, not ended, unclaimed) or fading (ended or claimed in the last AFTER
        seconds). The row, or None."""
        if not ENABLED:
            return None
        self.ensure(conn)
        now = self.clock()
        rows = conn.execute("SELECT * FROM world_events WHERE starts <= ? AND ends > ? ORDER BY starts DESC",
                            (now, now - AFTER)).fetchall()
        for r in rows:
            if r["claimed_by"] is None and r["ends"] > now:
                return r
        for r in rows:
            gone = r["claimed_at"] if r["claimed_by"] is not None else r["ends"]
            if now - gone <= AFTER:
                return r
        return None

    def live(self, row):
        return row is not None and row["claimed_by"] is None and row["ends"] > self.clock()

    def wins_today(self, conn, uid):
        return db.daily_count(conn, uid, WON, self.clock())

    def view(self, conn, uid, place):
        """What this player's page is told: that a light has risen over the Moon Forest (everywhere); where it
        stands only on the land it is on."""
        row = self.current(conn)
        if row is None:
            return None
        now = self.clock()
        live = self.live(row)
        out = {"id": row["id"], "region": REGION_NAME, "live": live, "left": max(0, round(row["ends"] - now)),
               "here": place == row["place"], "inForest": place in LANDS,
               "mine": row["claimed_by"] == uid, "claimed": row["claimed_by"] is not None,
               "tried": uid in self.tried.get(row["id"], ()), "capped": self.wins_today(conn, uid) >= WINS_PER_DAY}
        if out["here"]:
            out.update(x=row["x"], y=row["y"], reach=REACH)
        return out

    def kneel(self, conn, uid, place, x, y, realm, rng):
        """May this player kneel at the event now? ((event id, (grade, type, where, age)), None) or (None, why)."""
        row = self.current(conn)
        if not self.live(row) or row["place"] != place:
            return None, "The light has faded."
        if (x - row["x"]) ** 2 + (y - row["y"]) ** 2 > REACH ** 2:
            return None, "Walk closer to the light."
        if self.wins_today(conn, uid) >= WINS_PER_DAY:
            return None, "You have already claimed a phenomenon today. Leave this one to another seeker."
        with self.lock:
            if uid in self.tried.setdefault(row["id"], set()):
                return None, "You have knelt at this light already: it will not open to you twice."
            self.tried[row["id"]].add(uid)
        return (row["id"], (loot.herb_tier(realm, rng), row["type"], WHERE, AGE)), None

    def claim(self, conn, uid, eid):
        """Pull it free: True for the one player whose claim lands first (and only while it is still there)."""
        now = self.clock()
        if self.wins_today(conn, uid) >= WINS_PER_DAY:
            return False
        with conn:
            cur = conn.execute("UPDATE world_events SET claimed_by = ?, claimed_at = ? "
                               "WHERE id = ? AND claimed_by IS NULL AND ends > ?", (uid, now, eid, now))
        if cur.rowcount != 1:
            return False
        db.bump_daily(conn, uid, WON, now)
        return True

    def taken(self, conn, eid, uid):
        """Whether someone else has claimed this event (or it has ended): a round still open for it is called off."""
        r = conn.execute("SELECT claimed_by, ends FROM world_events WHERE id = ?", (eid,)).fetchone()
        return r is None or (r["claimed_by"] is not None and r["claimed_by"] != uid) or r["ends"] <= self.clock()
