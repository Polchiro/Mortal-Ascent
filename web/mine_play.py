"""
Mining in the Ironvein Quarry (docs/world.md "The Ironvein Quarry"; SHOAIB approved the rules Nov 25 2026).
WEBSITE ONLY: Discord's /explore keeps its Ore Vein encounter, unchanged.

Seams open at the foot of the quarry's walls (web/quarry.SPOTS), each player's own, SEAM_COUNT at a time; one that is
dug out opens again somewhere else a few minutes later. Walk up, press E and strike it with the pick: 3 blows for
iron and coal, 5 for jade. What a seam gives is the bot's own material tables (forge.SEAMS, bot/materials.roll_seam),
at your realm's tier. A player may open forge.SEAMS_PER_DAY seams a day (UTC).

The server referees, as for Train and Practice: when you start on a seam it makes the plan from a seed (the blows it
takes and exactly what it holds, decided then), keeps the time, and when the page sends the blows it struck
([ms since the start, ...], the page's own clock so a slow connection costs nothing) it checks there were enough,
far enough apart, that the dig took as long as it must, that you stand by the seam and that it wasn't dug before,
then pays what the plan held. The blows change nothing about what you get: they are the digging.
A dig you walk away from waits KEEP seconds with its cracks; after that the seam is whole again.
"""
import random
import threading
import time
from dataclasses import dataclass, field

import forge

from bot import db, loot, materials

from . import quarry
from .inventory import item_picture

PLACE = quarry.KEY
SEAM_COUNT = 8
REGROW = (120, 240)                   # seconds before a dug seam opens again at another spot
REACH = 1.9                           # how close (tiles) you stand to dig (a seam is a rock: you can't stand on it)
MIN_GAP_MS = 420                      # two blows can't be closer than this (a swing takes about a second)
KEEP = 600                            # a dig left half done waits this long
COUNT = "world:seams"                 # today's seams, in daily_counts
ART = {"iron": "/art/env/quarry/seams/seam_iron_01.webp", "coal": "/art/env/quarry/seams/seam_coal_01.webp",
       "jade": "/art/env/quarry/seams/seam_jade_01.webp"}
TALL = {"iron": 118, "coal": 96, "jade": 108}          # how tall each stands on the map (px at the walkers' size)
COLOR = {"iron": "#C9D2E6", "coal": "#B7A58C", "jade": "#8FE3B0"}


@dataclass
class Dig:
    seam: int                         # the seam's id
    kind: str
    strikes: int
    holds: list                       # the material items it gives, rolled when the dig began
    began: float
    seed: int


@dataclass
class Miner:
    seams: list = field(default_factory=list)      # {id, x, y, kind, ready}
    dig: Dig = None
    ids: int = 0


class Mines:
    """Each player's seams and the dig under way. Kept in the website's memory, as herbs are: a restart opens new
    seams. Today's count is in the database, so a restart doesn't give the day's seams again."""

    def __init__(self, clock=time.time, rng_factory=None):
        self.clock = clock
        self.rng_factory = rng_factory or (lambda uid: random.Random())
        self._m = {}
        self._rng = {}
        self.lock = threading.RLock()

    def _miner(self, uid):
        if uid not in self._m:
            self._m[uid] = Miner()
            self._rng[uid] = self.rng_factory(uid)
        return self._m[uid], self._rng[uid]

    def _open(self, m, rng, ready):
        taken = {(s["x"], s["y"]) for s in m.seams}
        free = [p for p in quarry.SPOTS if p not in taken]
        if not free:
            return None
        x, y = rng.choice(free)
        m.ids += 1
        return {"id": m.ids, "x": x, "y": y, "kind": loot.pick(forge.SEAM_KINDS, rng), "ready": ready}

    def left_today(self, conn, uid):
        return max(0, forge.SEAMS_PER_DAY - db.daily_count(conn, uid, COUNT, self.clock()))

    def view(self, conn, uid):
        """What this player sees in the quarry: the open seams and how many they may still open today."""
        with self.lock:
            m, rng = self._miner(uid)
            now = self.clock()
            if m.dig and now - m.dig.began > KEEP:
                m.dig = None
            while len(m.seams) < SEAM_COUNT:
                s = self._open(m, rng, now)
                if s is None:
                    break
                m.seams.append(s)
            left = self.left_today(conn, uid)
            return {"left": left, "day": forge.SEAMS_PER_DAY, "reach": REACH,
                    "seams": [{"id": s["id"], "x": s["x"], "y": s["y"], "kind": s["kind"],
                               "name": forge.SEAMS[s["kind"]]["name"], "src": ART[s["kind"]], "tall": TALL[s["kind"]],
                               "color": COLOR[s["kind"]], "spent": left <= 0,
                               "cracked": bool(m.dig and m.dig.seam == s["id"])}
                              for s in m.seams if s["ready"] <= now]}

    def start(self, conn, uid, sid, x, y):
        """Start on a seam (or pick a half-done dig back up): ({kind, name, strikes, gives, ...}, None) or (None, why)."""
        with self.lock:
            m, rng = self._miner(uid)
            now = self.clock()
            s = next((s for s in m.seams if s["id"] == sid and s["ready"] <= now), None)
            if s is None:
                return None, "That seam is worked out."
            if (x - s["x"]) ** 2 + (y - s["y"]) ** 2 > REACH ** 2:
                return None, "Walk closer to the seam."
            if self.left_today(conn, uid) <= 0:
                return None, "The rock needs rest. You have opened today's seams: new ones at midnight UTC."
            p = db.get_player(conn, uid)
            if p is None:
                return None, "No character yet."
            if not (m.dig and m.dig.seam == sid and now - m.dig.began <= KEEP):
                seed = rng.getrandbits(48)
                plan = random.Random(seed)
                m.dig = Dig(sid, s["kind"], forge.SEAMS[s["kind"]]["strikes"],
                            materials.roll_seam(s["kind"], p["realm"], plan, materials.prospector(p)), now, seed)
            d = m.dig
            return {"id": sid, "kind": d.kind, "name": forge.SEAMS[d.kind]["name"], "strikes": d.strikes,
                    "gives": materials.seam_gives(d.kind, p["realm"]), "gap": MIN_GAP_MS,
                    "left": self.left_today(conn, uid), "day": forge.SEAMS_PER_DAY}, None

    def finish(self, conn, uid, sid, blows, x, y):
        """The page's blows ([ms since the start]). Checked, then the plan's materials are paid.
        (result, None) or (None, why): a refusal leaves the dig as it was."""
        with self.lock:
            m, rng = self._miner(uid)
            now = self.clock()
            d = m.dig
            s = next((s for s in m.seams if s["id"] == sid), None)
            if d is None or s is None or d.seam != sid or now - d.began > KEEP:
                return None, "That seam is worked out."
            if (x - s["x"]) ** 2 + (y - s["y"]) ** 2 > REACH ** 2:
                return None, "Walk closer to the seam."
            try:
                ts = sorted(float(b) for b in blows)[:64]
            except (TypeError, ValueError):
                return None, "The blows could not be read."
            good = []
            for t in ts:                                       # blows closer than a swing apart count once
                if t >= 0 and (not good or t - good[-1] >= MIN_GAP_MS):
                    good.append(t)
            need = (d.strikes - 1) * MIN_GAP_MS / 1000
            if len(good) < d.strikes or now - d.began < need - 0.05:
                return None, "The seam isn't broken open yet."
            if self.left_today(conn, uid) <= 0:
                return None, "The rock needs rest. You have opened today's seams: new ones at midnight UTC."
            stored, _ = loot.store(conn, uid, d.holds)
            db.bump_daily(conn, uid, COUNT, now)
            m.dig = None
            m.seams = [q for q in m.seams if q["id"] != sid]
            nxt = self._open(m, rng, now + rng.uniform(*REGROW))
            if nxt:
                m.seams.append(nxt)
            got = [{"name": i["name"], "qty": i["qty"], "picture": item_picture(i)} for i in stored]
            have = {i["key"]: i["qty"] for i in db.get_items(conn, uid, "materials")}
            pouch = [f"{have.get(i['key'], 0)} {i['name']}" for i in stored]
            return {"got": got, "kind": d.kind, "lines": materials.lines(stored), "pouch": pouch,
                    "left": self.left_today(conn, uid), "day": forge.SEAMS_PER_DAY}, None
