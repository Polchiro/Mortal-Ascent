"""
The open world (docs/world.md): the town, the Crossroads and the lands of the Moon Forest, walked as one world.

A place is the town (web/town.py), the Crossroads (web/crossroads.py) or a wild land (web/land.py LANDS: big, empty
ground for now). They are joined by ENTRANCES: walk into one (the town gate, the mouth of a road or path at a land's
edge) and you come out of its partner on the next place, as far to its side as you went in and still walking. The page
(web/static/town.js) walks every place the same way; the server knows which place you are in and where you stand (it
checks each report could be walked), so nobody skips a road by typing an address or picks a herb from across a field.

What grows and roams there is each player's own, rolled by the server:
  herbs    a few at a time in each place, at random spots off the paths; picked, one regrows somewhere else a little
           later. Its grade is the gatherer's own (alchemy.herb_grade_odds: rare herbs stay as rare), its type is the
           region's (alchemy.REGION_HERB_TYPES). Picking it is one round of the gathering game (bot/gathering.py,
           web/gather_play.py).
  beasts   in the wild lands: walk near one and it may notice you and charge; walk up to one and you attack. Which
           beast is the location's own roster and odds (hunting.pool, hunting.tier_odds for the trip's next step:
           one roll a step, whichever land you are in).
  finds    in the wild lands: a glint in the grass, now and then; one of /explore's finds (explore.ENCOUNTERS, at
           their odds among those found this way). A secret spot leans to the rare ones.
A beast or a find is an encounter: the first starts a trip (the 30-minute explore rest), a trip holds
hunting.MAX_ENCOUNTERS of them across all the forest's lands, and what you carry is banked when you walk back into
town (web/hunt_play.py). With none left, or while resting or injured, the beasts keep their distance and nothing
glints; herbs still grow.

Nothing here is kept in the database: like a hunt, it is lost if the website restarts (you start in town; a trip
under way ends as a hunt does when the website restarts).
"""
import math
import random
import threading
import time
from dataclasses import dataclass, field

import alchemy
import beasts as beast_rules
import explore as explore_rules
import hunting

from bot import db, gear, loot

from . import crossroads, hunt_map, land, town

# ── the places ──────────────────────────────────────────────────────────────────────────────────────────────────

# The wild places: the open lands of a hunting ground (web/land.py), with its beasts and finds. Moon Forest is three
# lands deep; a trip (and its 5 encounters) runs across all of them.
WILD = {"forest_edge": "moon_forest", "deep_woods": "moon_forest", "shrine_grove": "moon_forest"}
WILD_NAMES = {"forest_edge": ("Moon Forest: Forest Edge", "the forest's edge"),
              "deep_woods": ("Moon Forest: Deep Woods", "the deep woods"),
              "shrine_grove": ("Moon Forest: Shrine Grove", "the shrine's grove")}

PLACES = {
    "town": {"title": town.NAME, "kicker": "MORTAL ASCENT · TOWN", "url": "/town", "safe": True},
    "crossroads": {"title": crossroads.NAME, "kicker": "MORTAL ASCENT · OUTSIDE THE GATE", "url": "/crossroads",
                   "herbs": {"count": 10, "region": "crossroads", "where": "the meadow outside the town walls"}},
}
for _key, _loc in WILD.items():
    PLACES[_key] = {"title": WILD_NAMES[_key][0], "kicker": "MORTAL ASCENT · THE WILDS", "url": f"/wild/{_key}",
                    "loc": _loc, "land": True,
                    "herbs": {"count": 14, "region": _loc, "where": WILD_NAMES[_key][1]},
                    "beasts": {"count": 5},
                    "finds": {"count": 1, "secret": land.LANDS[_key].get("secret", [])}}

# The entrances: walk into one and you come out of its partner. Each stands on an edge of its place (`side`: which
# way is out), `half` wide to either side, and takes you once you are within `depth` of it. You come out as far to
# the side of the partner as you went in, still walking the same way.
def _gate(place, key):
    g = land.LANDS[place]["gates"][key]
    return {"at": g["at"], "side": g["side"], "half": land.ROAD_W / 2 + 0.5, "depth": 0.3}


def _join(a, b):
    """Two land gates, each other's way through."""
    return {a: _gate(*a) | {"to": b[0], "arrive": b[1]}, b: _gate(*b) | {"to": a[0], "arrive": a[1]}}


ENTRANCES = {
    ("town", "gate_out"): {"at": (28.6, 16.0), "side": "x1", "half": 0.8, "depth": 0.75,
                           "to": "crossroads", "arrive": "town_gate"},
    ("crossroads", "town_gate"): {"at": (crossroads.GATE["x"], crossroads.GATE["y"]), "side": "x0", "half": 0.9,
                                  "depth": 0.75, "to": "town", "arrive": "gate_out"},
    **_join(("crossroads", "road_moon_forest"), ("forest_edge", "north")),
    **_join(("forest_edge", "south"), ("deep_woods", "north")),
    **_join(("deep_woods", "east"), ("shrine_grove", "west")),
}
TRIGGER = 0.75                        # walk this close to an entrance and you go through
ARRIVE_GAP = TRIGGER + 1.2            # you come out this far in, so you aren't sent straight back
FRESH = 1800                          # a place you left less than this long ago keeps where you stood (a reload)

HERB_REACH = 1.6                      # how close (tiles) to kneel at a herb or look at a find
HERB_REGROW = (45, 90)                # seconds before a picked herb grows again somewhere else: walking from herb
                                      # to herb is what paces gathering (about 4 a minute at most; the old Gather
                                      # page gave more), not waiting for them
FIND_REGROW = (240, 480)
HERB_ROOM = 2.0                       # herbs don't grow closer together than this
BEAST_GAP = 6.0                       # a beast appears this far from you at least ...
BEAST_APART = 4.0                     # ... and from the other beasts
QUIET = 3.0                           # nothing grows or appears this close to an entrance

# /explore's finds that need no choice of their own (the others: bandits, hazards, merchants, strangers, lairs come
# later), at their /explore odds among themselves; a secret spot only the rare ones
FINDS = ["treasure_chest", "herb_patch", "peaceful_clearing", "ore_vein", "stone_tablet", "blessed_land",
         "wandering_hermit"]
SECRET_FINDS = ["stone_tablet", "blessed_land", "wandering_hermit"]
SECRET_CHANCE = 0.3                   # a new find appears at one of the map's secret spots this often


def find_odds(kinds):
    w = {k: explore_rules.ENCOUNTERS[k]["chance"] for k in kinds}
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def url(place):
    return PLACES[place]["url"]


def place_of_url(path):
    return next((k for k, p in PLACES.items() if p["url"] == path), None)


def walkable(place, x, y):
    if place == "town":
        return town.walkable(x, y)
    if place == "crossroads":
        return crossroads.walkable(x, y)
    return land.walkable(place, x, y)


def size(place):
    return town.SIZE if place == "town" else land.size(place)


def start(place):
    return town.START if place == "town" else tuple(land.LANDS[place]["start"])


def mouth(e, x, y):
    """Where (x, y) stands against an entrance: (how far past it, outward; how far to its side)."""
    (nx, ny), (tx, ty) = land.SIDES[e["side"]]
    dx, dy = x - e["at"][0], y - e["at"][1]
    return dx * nx + dy * ny, dx * tx + dy * ty


def arrival(place, key, side=0.0):
    """Where you come in through this entrance: a few steps in from it, `side` tiles to its side (as far as you
    were to the side of the one you went into), or nearer its middle if nothing can stand there."""
    if key is None or (place, key) not in ENTRANCES:
        return start(place)
    e = ENTRANCES[(place, key)]
    (nx, ny), (tx, ty) = land.SIDES[e["side"]]
    lim = max(0.0, e["half"] - 0.4)
    for s in (max(-lim, min(lim, side)), 0.0):
        x, y = e["at"][0] - nx * ARRIVE_GAP + tx * s, e["at"][1] - ny * ARRIVE_GAP + ty * s
        if all(walkable(place, x + dx, y + dy) for dx, dy in ((0, 0), (.3, 0), (-.3, 0), (0, .3), (0, -.3))):
            return round(x, 3), round(y, 3)
    ex, ey = e["at"]
    sx, sy = start(place)
    if math.dist((ex, ey), (sx, sy)) < ARRIVE_GAP:
        sx, sy = size(place) / 2, size(place) / 2
    for i in range(1, 101):
        t = i / 100
        x, y = ex + (sx - ex) * t, ey + (sy - ey) * t
        if math.dist((x, y), (ex, ey)) > ARRIVE_GAP and walkable(place, x, y):
            return round(x, 3), round(y, 3)
    return start(place)


def moved(place, prev, x, y, now):
    """The position a player reports, if it could be true (walkable here, no faster than walking); else None."""
    try:
        x, y = float(x), float(y)
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)) or not walkable(place, x, y):
        return None
    px, py, pt = prev
    if math.dist((x, y), (px, py)) > hunt_map.SPEED * hunt_map.SLACK * max(0.0, now - pt) + hunt_map.JUMP:
        return None
    return (round(x, 3), round(y, 3), now)


# ── each player's world ─────────────────────────────────────────────────────────────────────────────────────────

@dataclass
class Walker:
    place: str
    x: float
    y: float
    t: float
    rng: random.Random
    loose: bool = False                       # the town placed you by someone you came back from: trust one report
    left: dict = field(default_factory=dict)  # place → (x, y, time) where you last stood there
    herbs: dict = field(default_factory=dict)     # place → [herb]
    beasts: dict = field(default_factory=dict)    # place → [beast], or missing: roll them afresh
    finds: dict = field(default_factory=dict)     # place → [find]
    gathering: tuple = None                   # (place, herb id) whose round is on screen
    ids: int = 0
    roll: tuple = None                        # ((trip, step), tier): the kind of beast this step of the trip offers


class World:
    def __init__(self, hunts, gathers, clock=time.time, rng_factory=None):
        self.hunts, self.gathers = hunts, gathers
        self.clock = clock
        self.rng_factory = rng_factory
        self.lock = threading.RLock()
        self._w = {}

    def walker(self, uid):
        return self._w.get(uid)

    def _id(self, w):
        w.ids += 1
        return w.ids

    # ── where you are ───────────────────────────────────────────────

    def enter(self, conn, uid, place, near=None, side=0.0):
        """You open this place's page: you are here now. Where you stand: where you stood (a reload), or in from
        `near` (an entrance), or its start. Coming into town ends a trip under way and banks it: its lines."""
        now = self.clock()
        with self.lock:
            w = self._w.get(uid)
            if w is None:
                rng = self.rng_factory() if self.rng_factory else random.Random()
                w = self._w[uid] = Walker(place, *start(place), now, rng)
            if w.place != place:
                w.left[w.place] = (w.x, w.y, now)
            keep = w.left.get(place) if near is None else None
            if w.place == place and near is None and now - w.t < FRESH:
                pass                                          # a reload: where you stood
            elif keep and now - keep[2] < FRESH and walkable(place, keep[0], keep[1]):
                w.x, w.y = keep[0], keep[1]
            else:
                w.x, w.y = (arrival(place, near, side) if near in {k for p, k in ENTRANCES if p == place}
                            else start(place))
            w.place, w.t = place, now
            w.loose = place == "town"                         # the page may stand you by someone: nothing to gain
            w.gathering = None
        if place == "town":
            return self.hunts.world_home(conn, uid)
        return None

    def report(self, conn, uid, place, x, y):
        """Where the page says you are. Answers where the server has you ({x, y}), or that you are elsewhere."""
        now = self.clock()
        with self.lock:
            w = self._w.get(uid)
            if w is None or w.place != place:
                return {"place": w.place if w else "town", "url": url(w.place if w else "town")}
            pos = moved(place, (w.x, w.y, w.t), x, y, now)
            if pos is None and w.loose:
                try:
                    fx, fy = float(x), float(y)
                    if math.isfinite(fx) and math.isfinite(fy) and walkable(place, fx, fy):
                        pos = (fx, fy, now)
                except (TypeError, ValueError):
                    pass
            if pos is not None:
                w.x, w.y, w.t = pos
                w.loose = False
            else:
                w.t = now
        self.hunts.touch(uid)
        return {"x": w.x, "y": w.y}

    def _at(self, w, place, x, y):
        """Report and check in one: you are in `place`, at a spot you could have walked to. (x, y) or None."""
        if w is None or w.place != place:
            return None
        pos = moved(place, (w.x, w.y, w.t), x, y, self.clock())
        if pos is None:
            return None
        w.x, w.y, w.t = pos
        return pos[:2]

    def move(self, conn, uid, place, key, x, y):
        """Through an entrance: the place you come out in, or None (not there, or the way is sealed)."""
        e = ENTRANCES.get((place, key))
        with self.lock:
            w = self._w.get(uid)
            at = self._at(w, place, x, y)
            if e is None or at is None:
                return None
            out, side = mouth(e, *at)
            if out < -(e["depth"] + 0.9) or abs(side) > e["half"] + 0.6:
                return None
            to = e["to"]
            loc = PLACES[to].get("loc")
            if loc:
                p = db.get_player(conn, uid)
                if p is None or hunting.eligible(p, hunting.location(loc)):
                    return None
            if self.hunts.trip(uid) is not None and self.hunts.trip(uid).battle is not None:
                return None
        lines = self.enter(conn, uid, to, e["arrive"], side)
        return to, lines

    # ── what grows and roams there ──────────────────────────────────

    def _spot(self, w, place, near_ok, apart, gap_you=0.0):
        """A random walkable spot: `near_ok(x, y)` (inside a herb area ...), with room round it, away from the
        entrances, `apart` from the given spots, `gap_you` from you."""
        n = size(place)
        for _ in range(120):
            x, y = 1 + w.rng.random() * (n - 2), 1 + w.rng.random() * (n - 2)
            if not near_ok(x, y):
                continue
            if not all(walkable(place, x + dx, y + dy) for dx, dy in ((0, 0), (.5, 0), (-.5, 0), (0, .5), (0, -.5))):
                continue
            if any(math.dist((x, y), e["at"]) < QUIET for (p, _), e in ENTRANCES.items() if p == place):
                continue
            if any(math.dist((x, y), s) < d for s, d in apart):
                continue
            if gap_you and math.dist((x, y), (w.x, w.y)) < gap_you:
                continue
            return round(x, 2), round(y, 2)
        return None

    def _herb(self, w, conn, uid, place, ready):
        cfg = PLACES[place]["herbs"]

        def ok(x, y):                             # anywhere off the paths (and not under the town wall)
            return land.off_path(place, x, y) and (place != "crossroads" or x > crossroads.WALL_X + 2.5)
        apart = [((h["x"], h["y"]), HERB_ROOM) for h in w.herbs.get(place, [])]
        at = self._spot(w, place, ok, apart)
        if at is None:
            return None
        p = db.get_player(conn, uid)
        grade = loot.herb_tier(p["realm"], w.rng)
        type_ = loot.pick(alchemy.REGION_HERB_TYPES[cfg["region"]], w.rng)
        return {"id": self._id(w), "x": at[0], "y": at[1], "grade": grade, "type": type_, "ready": ready}

    def _beast(self, w, place, tier):
        loc = hunting.location(PLACES[place]["loc"])
        name, _, role, _home = w.rng.choice([b for b in hunting.pool(loc) if b[1] == tier])
        apart = [((b["x"], b["y"]), BEAST_APART) for b in w.beasts.get(place) or []]
        at = self._spot(w, place, lambda x, y: True, apart, gap_you=BEAST_GAP)
        if at is None:
            return None
        return {"id": self._id(w), "name": name, "tier": tier, "role": role, "x": at[0], "y": at[1]}

    def _find(self, w, place, ready):
        cfg = PLACES[place]["finds"]
        apart = [((f["x"], f["y"]), 4.0) for f in w.finds.get(place, [])]
        if cfg.get("secret") and w.rng.random() < SECRET_CHANCE:
            free = [s for s in cfg["secret"] if walkable(place, *s) and all(math.dist(s, a) >= d for a, d in apart)]
            if free:
                x, y = w.rng.choice(free)
                return {"id": self._id(w), "x": x, "y": y, "secret": True, "ready": ready}
        at = self._spot(w, place, lambda x, y: True, apart, gap_you=4.0)
        if at is None:
            return None
        return {"id": self._id(w), "x": at[0], "y": at[1], "secret": False, "ready": ready}

    def _grow(self, w, conn, uid, place):
        """Fill the place up: its herbs, its beasts (rolled afresh after an encounter), its finds."""
        now = self.clock()
        cfg = PLACES[place]
        self._settle(w, conn, uid)
        if cfg.get("herbs"):
            hs = w.herbs.setdefault(place, [])
            while len(hs) < cfg["herbs"]["count"]:
                h = self._herb(w, conn, uid, place, now)
                if h is None:
                    break
                hs.append(h)
        trip = self.hunts.trip(uid)
        if cfg.get("beasts") and w.beasts.get(place) is None and not (trip and trip.battle is not None):
            # One roll for the trip's next step, exactly as a hunt rolls its next beast (hunt_play.Hunts._roll):
            # one beast out there is of that kind, the rest are Normal. So an Elite or a Beast King is on offer no
            # more often than a hunt would meet one (and you may still choose a Normal beast instead).
            # The roll is the step's, not the place's: every land of the forest offers the same kind until the trip
            # moves on, so walking from land to land doesn't roll again.
            step = min((trip.step if trip else 0) + 1, hunting.MAX_ENCOUNTERS)
            if w.roll is None or w.roll[0] != (id(trip) if trip else None, step):
                p = db.get_player(conn, uid)
                luck = gear.artifact_bonus(p, "explore_luck") + gear.artifact_bonus(p, "rare_encounters")
                w.roll = ((id(trip) if trip else None, step), loot.pick(hunting.tier_odds(step, luck), w.rng))
            tiers = [w.roll[1]] + ["normal"] * (cfg["beasts"]["count"] - 1)
            w.rng.shuffle(tiers)
            w.beasts[place] = []
            for tier in tiers:
                b = self._beast(w, place, tier)
                if b:
                    w.beasts[place].append(b)
        if cfg.get("finds"):
            fs = w.finds.setdefault(place, [])
            while len(fs) < cfg["finds"]["count"]:
                f = self._find(w, place, now)
                if f is None:
                    break
                fs.append(f)

    def _settle(self, w, conn, uid):
        """A herb whose round was answered (or ran out) while the page was away is gone: it regrows elsewhere."""
        if w.gathering is None:
            return
        s = self.gathers.catch_up(conn, uid)
        if s is None or s.g.round is None:
            place, hid = w.gathering
            w.gathering = None
            last = s.last[0] if s and s.last else None
            if last is not None and last.kind == "herb":
                self._picked(w, conn, uid, place, hid)

    def _picked(self, w, conn, uid, place, hid):
        hs = w.herbs.get(place, [])
        w.herbs[place] = [h for h in hs if h["id"] != hid]
        h = self._herb(w, conn, uid, place, self.clock() + w.rng.uniform(*HERB_REGROW))
        if h:
            w.herbs[place].append(h)

    def blocked(self, conn, uid):
        """Why you meet nothing right now (beasts keep away, nothing glints), or None: a trip with encounters left,
        or none under way and free to start one."""
        trip = self.hunts.trip(uid)
        if trip is not None:
            return "spent" if trip.step >= hunting.MAX_ENCOUNTERS else None
        party = self.hunts.parties.of(uid)
        if party is not None and not party.solo:
            return "team"
        return self.hunts.blocked(conn, uid)

    def state(self, conn, uid, place):
        """What this player sees here now: herbs, beasts, finds, the trip and why nothing would meet them."""
        with self.lock:
            w = self._w.get(uid)
            if w is None or w.place != place:
                return None
            self._grow(w, conn, uid, place)
            now = self.clock()
            quiet = None if PLACES[place].get("safe") else self.blocked(conn, uid)   # in town: nothing to meet anyway
            trip = self.hunts.trip_view(conn, uid)
            herbs = [{"id": h["id"], "x": h["x"], "y": h["y"], "grade": h["grade"], "type": h["type"],
                      "name": alchemy.HERBS[h["grade"]][h["type"]][0], "color": _grade_color(h["grade"]),
                      "picture": _herb_picture(h["grade"], h["type"]), "rank": alchemy.GRADES.index(h["grade"])}
                     for h in w.herbs.get(place, []) if h["ready"] <= now]
            beasts = [{"id": b["id"], "name": b["name"], "tier": b["tier"],
                       "tierName": {"normal": "Normal", "elite": "Elite", "beast_king": "Beast King"}[b["tier"]],
                       "role": b["role"].title(), "x": b["x"], "y": b["y"],
                       "src": f"/art/beasts/{beast_rules.slug(b['name'])}.png"}
                      for b in (w.beasts.get(place) or [])]
            finds = [] if quiet else [{"id": f["id"], "x": f["x"], "y": f["y"], "secret": f["secret"]}
                                      for f in w.finds.get(place, []) if f["ready"] <= now]
            p = db.get_player(conn, uid)
            purse = {"coins": f"{int(p['lotus_coins']):,}", "pearls": f"{int(p['moon_pearls']):,}"} if p else None
            return {"place": place, "herbs": herbs, "beasts": beasts, "finds": finds, "trip": trip, "purse": purse,
                    "wary": bool(quiet), "quiet": _quiet_line(quiet),
                    "wander": hunt_map.WANDER, "notice": hunt_map.NOTICE, "reach": HERB_REACH,
                    "beastReach": hunt_map.REACH}

    # ── doing things there ──────────────────────────────────────────

    def gather(self, conn, uid, place, hid, x, y):
        """Kneel at a herb: a round of the gathering game for it. (session, None) or (None, why)."""
        with self.lock:
            w = self._w.get(uid)
            at = self._at(w, place, x, y)
            if at is None:
                return None, "You are not there."
            self._settle(w, conn, uid)
            h = next((h for h in w.herbs.get(place, []) if h["id"] == hid and h["ready"] <= self.clock()), None)
            if h is None:
                return None, "The herb is gone."
            if math.dist(at, (h["x"], h["y"])) > HERB_REACH:
                return None, "Walk closer to the herb."
            s, why = self.gathers.start(conn, uid, herb=(h["grade"], h["type"], PLACES[place]["herbs"]["where"]))
            if s is None:
                return None, why
            w.gathering = (place, hid) if s.g.round is not None and s.g.round.kind == "herb" else None
            return s, None

    def pick(self, conn, uid, key, turn):
        """Your choice in the gathering round. A herb round answered: that herb is gone and regrows elsewhere."""
        with self.lock:
            w = self._w.get(uid)
            s = self.gathers.pick(conn, uid, key, turn)
            if w is not None:
                self._settle(w, conn, uid)
            return s

    def walk_away(self, conn, uid, turn):
        """Close the gathering panel mid-round: that herb counts as missed (and is gone)."""
        with self.lock:
            w = self._w.get(uid)
            s = self.gathers.stop(conn, uid, turn)
            if w is not None:
                self._settle(w, conn, uid)
            return s

    def engage(self, conn, uid, place, bid, x, y):
        """A beast and you meet (it charged you, or you walked up to it): the fight. None, or why not."""
        loc = PLACES.get(place, {}).get("loc")
        with self.lock:
            w = self._w.get(uid)
            at = self._at(w, place, x, y)
            if at is None or not loc:
                return "You are not there."
            if w.gathering is not None:
                return "You are gathering."
            b = next((b for b in w.beasts.get(place) or [] if b["id"] == bid), None)
            if b is None:
                return "It is gone."
            if not hunt_map.close_enough(at, b):
                return "It is too far away."
            quiet = self.blocked(conn, uid)
            if quiet:
                return _quiet_line(quiet)
            why = self.hunts.world_fight(conn, uid, loc, b)
            if why:
                return _quiet_line(why) or why
            w.beasts.clear()                                  # the rest scatter: new ones come out after the fight
            return None

    def discover(self, conn, uid, place, fid, x, y):
        """Look at what glints: one of /explore's finds. (lines, None) or (None, why)."""
        loc = PLACES.get(place, {}).get("loc")
        with self.lock:
            w = self._w.get(uid)
            at = self._at(w, place, x, y)
            if at is None or not loc:
                return None, "You are not there."
            f = next((f for f in w.finds.get(place, []) if f["id"] == fid and f["ready"] <= self.clock()), None)
            if f is None:
                return None, "It is gone."
            if math.dist(at, (f["x"], f["y"])) > HERB_REACH:
                return None, "Walk closer."
            quiet = self.blocked(conn, uid)
            if quiet:
                return None, _quiet_line(quiet)
            kinds = SECRET_FINDS if f["secret"] else FINDS
            kind = loot.pick(find_odds(kinds), w.rng)
            lines, why = self.hunts.world_find(conn, uid, loc, kind)
            if why:
                return None, _quiet_line(why) or why
            w.finds[place] = [x for x in w.finds[place] if x["id"] != fid]
            nf = self._find(w, place, self.clock() + w.rng.uniform(*FIND_REGROW))
            if nf:
                w.finds[place].append(nf)
            w.beasts.clear()                                  # a step deeper: the beasts out there change
            return lines, None

    def defeated(self, uid):
        """Carried home from a lost fight: you wake up in town."""
        with self.lock:
            w = self._w.get(uid)
            if w is not None:
                w.left[w.place] = (w.x, w.y, 0)
                w.place, w.x, w.y, w.t = "town", *town.START, self.clock()
                w.beasts.clear()


def _quiet_line(why):
    if not why:
        return None
    if why == "spent":
        return "This trip's encounters are spent: the beasts keep their distance. Walk back to town to bank your finds."
    if why == "team":
        return "You are in a team: the wilds' beasts wait for your party's hunt."
    if why.startswith("injured") or why.startswith("resting"):
        return f"You are {why}: the beasts keep their distance and nothing glints, but herbs still grow."
    return why


def _grade_color(grade):
    from .alchemy_play import GRADE_COLOR
    return GRADE_COLOR[grade]


def _herb_picture(grade, type_):
    from .alchemy_play import herb_picture
    return herb_picture(grade, type_)


# ── the page ────────────────────────────────────────────────────────────────────────────────────────────────────

def walk_exits(place, data):
    """Mark this place's exits that you walk through (ENTRANCES), and add any it has no exit for yet."""
    have = {e["key"] for e in data.get("exits", [])}

    def how(e):
        return {"walk": True, "go": [], "out": list(land.SIDES[e["side"]][0]), "half": e["half"], "depth": e["depth"]}
    for x in data.get("exits", []):
        if (place, x["key"]) in ENTRANCES and x.get("state", "open") != "locked":
            x.update(how(ENTRANCES[(place, x["key"])]))
    for (p, key), e in ENTRANCES.items():
        if p == place and key not in have:
            x, y = e["at"]
            to = PLACES[e["to"]]["title"]
            data.setdefault("exits", []).append({"key": key, "name": to, "title": "The way to " + to, "x": x, "y": y,
                                                 "line": "", "exit": True, "kind": "path", "state": "open",
                                                 "glow": [x, y], **how(e)})
    return data


ZOOM = land.ZOOM


def wild_data(sheet, place, hero):
    """A wild land's page data, in the town page's shape (web/static/town.js walks every place)."""
    return {"sheet": sheet, "size": land.size(place), "ground": land.ground(place), "zoom": ZOOM,
            "area": [list(p) for p in land.area(place)], "inset": 0, "blocked": [], "pieces": [],
            "tone": None, "lights": [], "reach": 1.5, "scale": land.SCALE, "hero": {"x": hero[0], "y": hero[1]},
            "near": None, "npcs": [], "exits": [], "atmos": True}


def page_data(conn, world, uid, place, sheet, p, blocked, near=None):
    """Everything the page needs for this place: the map (in the town page's shape) and what is out there."""
    w = world.walker(uid)
    hero = (w.x, w.y) if w else start(place)
    if place == "town":
        data = town.page_data(sheet, near)
        data["hero"] = {"x": hero[0], "y": hero[1]} if near is None and w else data["hero"]
    elif place == "crossroads":
        data = crossroads.page_data(sheet, p, blocked, None)
        data["hero"] = {"x": hero[0], "y": hero[1]}
    else:
        data = wild_data(sheet, place, hero)
    walk_exits(place, data)
    info = PLACES[place]
    data.update({"place": place, "title": info["title"], "kicker": info["kicker"], "url": info["url"],
                 "trigger": TRIGGER, "world": world.state(conn, uid, place)})
    return data
