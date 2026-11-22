"""
Live alchemy on the website: every stage of the craft played with the hands instead of buttons. docs/web.md,
"Live alchemy".

    🔥 Ignite      hold to pump the bellows, let go to cool; keep the heat inside the (moving) golden band
    🌿 Add Herbs   tap the right herb as the cauldron breathes in
    ☯️ Fuse        tap when the Yin and Yang orbs meet
    💊 Condense    tap when the pill glints, ready to set
    🔒 Seal Core   as Fuse, with the Beast Core: miss too many meetings and it shatters
    ⚡ Tribulation  Protect from blue bolts as the ring closes, Dodge red ones to the safe side

The craft itself is still the bot's (bot/crafting.py Craft): its herb order, clues, heat zone, Tribulation
directions, forgiveness and every number in alchemy.py. A stage here only decides that stage's score (0…1) and
hands it to Craft.settle; patterns, explosions, the Tribulation, EXP, toxicity and rewards are unchanged.

The server is the referee. Each stage starts when the page says it began ("begin"); after that every press is timed
by the server's own clock from that moment (so the network delay cancels out, and every window has a little grace for
its jitter). Nothing the page sends can say *when* it happened. The herb order and the lightning's direction never
leave the server before the player could see them anyway (the clues, the omen in the clouds).

The difficulty knobs map onto the hands (tempo below): the grade's decision time, rank relief, Swift Hands and the
batch penalty set how fast everything moves; the safe-zone width (rank, Furnace, Steady Hand, batch) sets the heat
band; the Yin-Yang tolerance and Seal pass (batch) set the Fuse and Seal windows; misleading hints become false
glints and a moving heat band; wild herbs make the Qi orbs irregular. Skill matters: steady hands reach a full score
in every stage, which the old buttons rarely allowed.
"""
import math
from dataclasses import dataclass, field

import alchemy

from bot import crafting, loot
from bot.crafting import BALANCE_TOLERANCE

from .inventory import item_picture

GRACE = 0.09            # seconds of network jitter forgiven on each side of a timing window
GRACE_PRECISE = 0.03    # ...but only this much on Fuse / Seal's precise window (the whole grace made it ±0.15 s)
BEGIN_WAIT = 120.0      # a page that never says "begin" (closed, or its player reading the help): the stage starts this long after it was handed out
LINGER = 0.25           # a stage whose time is up is settled on the next request this long after its end
TICK = 0.02             # the heat simulation step (static/alchemy_live.js uses the same)

# Every timed press is precise, good or rough (shown on the page), so the patterns follow the hands: rough play
# everywhere lands about 1-3 patterns, good play 4-6, precise play (and the higher grades' extra challenges
# handled) 7-9, within what the herbs' age allows.
TIMING = {"precise": 1.0, "good": 0.8, "rough": 0.5}
WINDOW = {"Mortal": 0.20, "Yellow": 0.18, "Mystic": 0.16, "Earth": 0.14, "Heaven": 0.12}
                        # seconds each side of the moment that are "good" (half of it "precise"), by difficulty grade:
                        # the same feel at any speed, so a slow basic recipe isn't loose and a fast one isn't brutal
ROUGH_REACH = 1.8       # a press this many windows away from the moment still counts, roughly (Fuse / Seal)
RANK_MARGIN = 0.06      # each alchemist rank above the recipe (3 at most) widens every window and calms the
                        # gusts and sway by this share. It never removes a challenge.

# 🔥 Ignite
IGNITE_WARMUP = 1.5     # the first seconds (getting the heat into the band) don't count
IGNITE_MIN_BAND = 10    # the heat band is never narrower than this (a big batch could squeeze it to 6°)
IGNITE_MAX_TEMPO = 1.35 # nor faster than this
BATCH_SWAY = 0.25       # each pill beyond the first calms the band's sway by this share
IGNITE_PERFECT = 0.95   # this share of the time in the band is a full score...
IGNITE_ZERO = 0.45      # ...and this share or less scores nothing (in between, a straight line)
HEAT_UP, HEAT_DOWN, HEAT_EASE = 24.0, 17.0, 0.25   # °/s while pumping / resting; seconds to reach that speed
GUST_PUSH, GUST_LENGTH, GUST_OMEN = 30.0, 0.7, 0.9
GUSTS = {"Mortal": 1, "Yellow": 2, "Mystic": 2, "Earth": 3, "Heaven": 3}
BAND_SWAY = {"Mortal": 3, "Yellow": 5, "Mystic": 7, "Earth": 9, "Heaven": 11}   # ° the band drifts each way
JUMPS = {"Earth": 1, "Heaven": 1}   # Earth+: the fire's heart jumps the band to a new place mid-stage...
JUMP_WARN = 1.2                      # ...shown (a ghost band) this long before
FLARES = {"Heaven": 2}               # Heaven: flare-ups. The heat surges by itself, and pumping into one overheats
FLARE_LENGTH, FLARE_PUSH, FLARE_PUMP, FLARE_OMEN = 1.2, 14.0, 2.2, 1.0

# 🌿 Herbs
BREATH = 1.3            # seconds per breath (at tempo 1)
BREATHS_PER_HERB = 4    # no herb by then: the cauldron goes cold on that one
VOLATILE_FROM = "Earth"  # Earth+: one herb is volatile and goes in on the OUT-breath (the ring at its smallest)
BREATH_SHIFT = {"Heaven": 0.75}   # Heaven: after the second breath the rhythm quickens to this share

# ☯️ Fuse / 🔒 Seal
MEET = 1.5              # seconds between the orbs' meetings (at tempo 1)
MISS_COST = 0.15        # each tap when the orbs are apart
SEAL_SHATTER = 3        # this many taps out of time shatter the core
REVERSE_FROM = "Earth"  # Earth+: the orbs change direction now and then
CHAOS = {"Earth": 1, "Heaven": 3}   # Earth+: a chaos orb crosses this many times just before a meeting; a tap on
                                    # it is unsteady
FUSE_TIGHTER = {"Earth": 0.9, "Heaven": 0.8}   # Fuse / Seal windows on the top grades, on top of WINDOW
RUSH_FROM = "Heaven"    # Heaven: the orbs drift slowly, then rush together at the end (harder to time by eye)
CHAOS_LEAD, CHAOS_HALF = 0.42, 0.15

# 💊 Condense
PULSE = 0.82            # seconds per pulse (at tempo 1)
GLINT = 0.18            # the glint is WINDOW each side of the ready pulse's middle, never over twice this share of it
READY_NOT_GLINT = 0.7   # pressed on the ready pulse, but not in its glint (rough)
QUICKEN_FROM = "Earth"  # Earth+: each beat comes quicker than the last...
QUICKEN = 0.88          # ...by this share
EARLY_READY = {"Heaven": [0, 1, 2]}   # Heaven: the gold ring may come after fewer warm-up beats (can't just count)

# ⚡ Tribulation: each round is one bolt or a quick pair. 🔵 blue: Protect (raise the shield as the ring closes);
# 🔴 red, too strong to block: Dodge toward the SAFE side. A fake-out flips the safe side once during the warning.
TRIB_ROUNDS = {          # the bolts of each round, by the craft's difficulty grade
    "Mortal": [["blue"], ["red"], ["blue"]],
    "Yellow": [["blue"], ["red"], ["blue"]],
    "Mystic": [["blue"], ["red"], ["red", "blue"]],
    "Earth":  [["red"], ["blue"], ["red", "blue"]],
    "Heaven": [["red"], ["blue", "red"], ["red", "blue"]],
}
TRIB_WARN = {"Mortal": 2.2, "Yellow": 2.2, "Mystic": 1.6, "Earth": 1.3, "Heaven": 1.1}   # seconds of warning
TRIB_FAKE = {"Mortal": 0, "Yellow": 0, "Mystic": 0, "Earth": 0.5, "Heaven": 0.75}      # chance a red bolt fakes out
TRIB_CALM = (1.2, 1.8)   # seconds between rounds
TRIB_PAIR = 0.15         # the second bolt of a pair starts warning this soon after the first lands
PROTECT_WINDOW = 0.5     # the shield holds this long: raised earlier than this before the bolt, it fades
SEE_EARLY = 0.3          # the warning may be asked for this much before it shows (network)


def harder(c, from_grade):
    """True when this craft's difficulty grade is from_grade or above."""
    return alchemy.GRADES.index(dgrade(c)) >= alchemy.GRADES.index(from_grade)


def margin(c):
    """The alchemist's rank margin: 1.0 at the recipe's rank, up to 1.18 three ranks above."""
    return 1 + RANK_MARGIN * min(c.ranks_above, 3)


def judge(off, window):
    """How a press `off` seconds (or breath shares) from the moment rates against its window."""
    if off <= window / 2:
        return "precise"
    if off <= window:
        return "good"
    return "rough"


def tempo(c):
    """How fast this craft's hands must be: the grade's decision time with every relief and penalty
    (Mortal 6s → 0.75, Heaven 3s → 1.5; rank and Swift Hands slow it down, a batch speeds it up)."""
    return max(0.7, min(1.6, 4.5 / c.seconds))


@dataclass
class Live:
    id: int
    stage: int                  # 1-5, or 6 for the Tribulation
    issued: float
    length: float               # seconds after the begin it lasts at most
    pub: dict                   # what the page gets
    t0: float = None
    over: bool = False
    result: dict = None         # how it went, for the page
    data: dict = field(default_factory=dict)

    def elapsed(self, now):
        return now - (self.t0 if self.t0 is not None else self.issued + BEGIN_WAIT)

    def expired(self, now):
        return self.over or self.elapsed(now) > self.length + LINGER


# ── making each stage ────────────────────────────────────────────────

def make(c, rng, n, now):
    """The live stage for the craft's current decision."""
    stage = 6 if c.tribulation == "pending" else c.stage
    f = tempo(c)
    pub, data, length = MAKERS[stage](c, rng, f)
    pub.setdefault("tempo", round(f, 3))
    pub.update(stage=stage, length=round(length, 3))
    return Live(n, stage, now, length, pub, data=data)


def make_ignite(c, rng, f):
    g, m = dgrade(c), margin(c)
    f = min(f, IGNITE_MAX_TEMPO)
    length = 4 + c.diff["rounds"] * 0.8
    w = max(c.zone_width, IGNITE_MIN_BAND)
    lo = max(5, min(c.zone_lo, 95 - w))
    sway = BAND_SWAY[g] * max(0.0, 1 - BATCH_SWAY * (c.batch - 1)) / m
    jumps = []
    for _ in range(JUMPS.get(g, 0)):
        at = round(length * rng.uniform(0.4, 0.6), 2)
        room_up, room_down = 95 - (lo + w) - sway, lo - 5 - sway
        size = w + 6
        way = 1 if room_up >= size and (room_down < size or rng.random() < 0.5) else -1
        size = min(size, room_up if way > 0 else room_down)
        if size > 4:
            jumps.append([at, round(way * size, 1)])
    shift = sum(d for _, d in jumps)
    sway = round(max(0, min(sway, lo - 5, 95 - lo - w, lo + shift - 5, 95 - lo - shift - w)), 2)
    gusts, t = [], IGNITE_WARMUP + 0.4
    for _ in range(GUSTS[g]):
        room = length - 1.0 - t - (GUSTS[g] - len(gusts) - 1) * 1.6
        if room < 0:
            break
        start = t + rng.uniform(0, room)
        gusts.append([round(start, 2), rng.choice([1, -1])])
        t = start + 1.6
    flares = []
    busy = [x for x, _ in gusts] + [x for x, _ in jumps]
    for k in range(FLARES.get(g, 0)):
        lo_t = IGNITE_WARMUP + 1.0 + (length - IGNITE_WARMUP - 2.5) * k / FLARES[g]
        hi_t = IGNITE_WARMUP + 1.0 + (length - IGNITE_WARMUP - 2.5) * (k + 1) / FLARES[g]
        tries = [round(rng.uniform(lo_t, hi_t), 2) for _ in range(12)]
        at = max(tries, key=lambda x: min([abs(x - b) for b in busy] or [9]))   # as clear of gusts and jumps as it can
        flares.append([at, FLARE_LENGTH])
        busy.append(at)
    pub = {"tempo": round(f, 3), "heat": c.heat, "lo": lo, "width": w, "sway": sway, "period": round(6.0 / f, 2),
           "phase": round(rng.uniform(0, 2 * math.pi), 3), "up": round(HEAT_UP * f ** 0.5, 2),
           "down": round(HEAT_DOWN * f ** 0.5, 2), "ease": HEAT_EASE, "gusts": gusts,
           "push": round(GUST_PUSH * f ** 0.5 / m, 2), "gust": GUST_LENGTH, "omen": GUST_OMEN,
           "jumps": jumps, "jumpwarn": JUMP_WARN, "flares": flares, "flarepush": round(FLARE_PUSH * f ** 0.5, 2),
           "flarepump": FLARE_PUMP, "flareomen": FLARE_OMEN,
           "warmup": IGNITE_WARMUP, "perfect": IGNITE_PERFECT, "zero": IGNITE_ZERO, "tick": TICK}
    return pub, {"holds": []}, length


def dgrade(c):
    """The grade whose difficulty this craft uses (breakthrough pills: one grade harder)."""
    for g, d in alchemy.DIFFICULTY.items():
        if d is c.diff:
            return g
    return c.grade


def make_herbs(c, rng, f):
    g = dgrade(c)
    breath = BREATH / f
    kinds = sorted(set(c.order))
    n = len(c.order)
    clues, insights = c.clues, c.insights
    if len(kinds) == 1:                                   # one herb: no order to find, only the timing
        clues = [f"*Only {alchemy.HERBS[c.grade][kinds[0]][0]} in this recipe: add each one on the breath.*"]
        insights = []
    pub = {"breath": round(breath, 3), "window": round(WINDOW[g] / breath * margin(c), 3), "per": BREATHS_PER_HERB,
           "count": n, "clues": clues, "insights": insights,
           "volatile": rng.randrange(1, n) if harder(c, VOLATILE_FROM) and n > 1 else None,
           "shift": [round(2 * breath, 3), round(breath * BREATH_SHIFT[g], 3)] if g in BREATH_SHIFT else None,
           "herbs": [{"key": t, "name": alchemy.HERBS[c.grade][t][0], "emoji": loot.TYPE_EMOJI.get(t, "🌿"),
                      "picture": item_picture(loot.herb(c.grade, t))} for t in kinds]}
    return pub, {"placed": 0, "since": 0.0, "points": 0.0, "marks": []}, breath * BREATHS_PER_HERB * n


def breath_at(p, t):
    """(phase 0..1 of the breath at t, its length): 0.5 the fullest, 0 and 1 the emptiest."""
    if p.get("shift") and t >= p["shift"][0]:
        b = p["shift"][1]
        return ((t - p["shift"][0]) % b) / b, b
    return (t % p["breath"]) / p["breath"], p["breath"]


def meetings(rng, f, count, wild):
    gap, out, t = MEET / f, [], MEET / f * 1.2
    for _ in range(count):
        out.append(round(t, 3))
        t += gap * (rng.uniform(0.7, 1.3) if wild else 1)
    return out


def make_fuse(c, rng, f, seal=False):
    g = dgrade(c)
    need = alchemy.SEAL_CORE_MOVES if seal else max(3, c.diff["rounds"] - 2)
    spare = 1 if seal else 0             # Fuse: every meeting counts, a missed one scores nothing
    meet = meetings(rng, f * (1.1 if seal else 1), need + spare, c.diff["wild_herbs"])
    window = (WINDOW[g] * FUSE_TIGHTER.get(g, 1) * (c.balance_tolerance / BALANCE_TOLERANCE) ** 0.5
              * margin(c))                                    # a batch tightens it, rank widens it
    reverse = sorted(rng.sample(range(len(meet)), min(2, len(meet)))) if harder(c, REVERSE_FROM) else []
    chaos = [round(meet[i] - CHAOS_LEAD, 3) for i in sorted(rng.sample(range(len(meet)), min(CHAOS.get(g, 0), len(meet))))]
    pub = {"meet": meet, "need": need, "window": round(window, 3), "seal": seal, "reverse": reverse, "chaos": chaos,
           "rush": harder(c, RUSH_FROM), "gp": GRACE_PRECISE,
           "chaoshalf": CHAOS_HALF, "reach": ROUGH_REACH,
           "allowed": (1 if c.seal_pass >= 10 else 0) if seal else None, "shatter": SEAL_SHATTER if seal else None}
    return pub, {"fused": 0, "credit": 0.0, "used": [], "unsteady": 0}, meet[-1] + 0.6


def make_condense(c, rng, f):
    g = dgrade(c)
    pulse = PULSE / f
    start = rng.choice(EARLY_READY[g]) if g in EARLY_READY else min(c.pulse, 1)
    decoy = None
    if rng.random() < c.diff["misleading"] * 2:
        decoy = rng.choice([lv for lv in (2, 3) if lv >= start] or [3])
        decoy = decoy if decoy >= start and decoy < 4 else None
    quick = QUICKEN if harder(c, QUICKEN_FROM) else 1.0
    beats, t, d = [], 0.0, pulse                       # when each pulse level begins, from `start` to 5 (cracked)
    for _ in range(start, 6):
        beats.append(round(t, 3))
        t += d
        d *= quick
    ready = beats[4 - start + 1] - beats[4 - start]
    glint = min(GLINT * 2, WINDOW[g] * margin(c) / ready)       # as a share of the ready beat
    pub = {"pulse": round(pulse, 3), "start": start, "beats": beats, "glint": round(glint, 3),
           "decoy": decoy, "steps": len(crafting.PULSES) - 1}
    return pub, {}, beats[-1]


def pulse_at(p, t):
    """(pulse level at t, where in that beat 0..1, the beat's length)."""
    b = p["beats"]
    i = max(0, min(len(b) - 1, sum(1 for x in b if x <= t) - 1))
    if i >= len(b) - 1:
        return 5, 0.0, p["pulse"]
    length = b[i + 1] - b[i]
    return p["start"] + i, (t - b[i]) / length, length


def make_tribulation(c, rng, f):
    g = dgrade(c)
    warn = TRIB_WARN[g] * margin(c)
    bolts, rounds, t = [], [], 1.0
    for kinds in TRIB_ROUNDS[g][c.strike:]:
        idx = []
        for j, kind in enumerate(kinds):
            if j:
                t += TRIB_PAIR
            b = {"kind": kind, "warn": round(t, 3), "hit": round(t + warn, 3)}
            secret = {"safe": rng.choice(["left", "right"]), "flip": None}
            if kind == "red" and rng.random() < TRIB_FAKE[g]:
                secret["flip"] = round(t + warn * rng.uniform(0.35, 0.6), 3)
            idx.append(len(bolts))
            bolts.append((b, secret))
            t += warn
        rounds.append(idx)
        t += rng.uniform(*TRIB_CALM)
    pub = {"bolts": [b for b, _ in bolts], "rounds": rounds, "protect": round(PROTECT_WINDOW * margin(c), 3),
           "grace": GRACE}
    return pub, {"secret": [s_ for _, s_ in bolts], "acts": {}, "round": 0, "marks": []}, bolts[-1][0]["hit"] + 0.8


def final_safe(secret):
    """Where a red bolt is safe from when it lands: the side shown last."""
    if secret["flip"] is None:
        return secret["safe"]
    return "left" if secret["safe"] == "right" else "right"


def bolt_ok(live, i):
    b, sec, a = live.pub["bolts"][i], live.data["secret"][i], live.data["acts"].get(i)
    if a is None:
        return False
    what, t = a
    if b["kind"] == "blue":
        return what == "protect" and b["hit"] - live.pub["protect"] - GRACE <= t <= b["hit"] + GRACE
    return what == final_safe(sec) and t <= b["hit"] + GRACE


MAKERS = {1: make_ignite, 2: make_herbs, 3: make_fuse, 4: make_condense,
          5: lambda c, rng, f: make_fuse(c, rng, f, seal=True), 6: make_tribulation}


# ── 🔥 the heat, worked out the same way the page draws it ───────────

def band_lo(p, t):
    jump = sum(d for at, d in p.get("jumps", ()) if t >= at)
    return p["lo"] + jump + p["sway"] * math.sin(2 * math.pi * t / p["period"] + p["phase"])


def flaring(p, t):
    return any(at <= t < at + n for at, n in p.get("flares", ()))


def gust_at(p, t):
    push = p.get("flarepush", 0) if flaring(p, t) else 0.0
    for start, way in p["gusts"]:
        if start <= t < start + p["gust"]:
            return push + way * p["push"]
    return push


def heat_run(p, holds, until):
    """(share of the counted time in the band, final heat). holds: [(t, pumping)] as the server heard them."""
    heat, speed, pumping, i = float(p["heat"]), 0.0, False, 0
    counted = inside = 0
    steps = int(round(until / p["tick"]))
    for k in range(steps):
        t = k * p["tick"]
        while i < len(holds) and holds[i][0] <= t:
            pumping = holds[i][1]
            i += 1
        want = (p["up"] * (p.get("flarepump", 1) if flaring(p, t) else 1)) if pumping else -p["down"]
        speed += (want - speed) * min(1.0, p["tick"] / p["ease"])
        heat = max(0.0, min(100.0, heat + (speed + gust_at(p, t)) * p["tick"]))
        if t >= p["warmup"]:
            counted += 1
            lo = band_lo(p, t)
            inside += lo <= heat <= lo + p["width"]
    return (inside / counted if counted else 0.0), heat


# ── the page's presses, as the server times them ─────────────────────

def press(live, c, t, ev):
    """One press, t seconds after the stage began by the server's clock. Returns what the page should show."""
    if live.over:
        return {"over": True}
    return PRESS[live.stage](live, c, t, ev or {})


def press_ignite(live, c, t, ev):
    if "pump" in ev and t <= live.length + GRACE:
        live.data["holds"].append((max(0.0, t), bool(ev["pump"])))
    return {}


def herb_timeouts(live, c, t):
    d, p = live.data, live.pub
    while d["placed"] < p["count"] and t > d["since"] + p["breath"] * p["per"]:
        d["since"] += p["breath"] * p["per"]
        herb_mark(live, c, "slow")


def herb_mark(live, c, how):
    d = live.data
    want = c.order[d["placed"]]
    name = alchemy.HERBS[c.grade][want][0]
    if how in TIMING:
        d["points"] += TIMING[how]
    elif not c._mistake():                       # wrong herb or too slow, unless experience saves it
        d["points"] += TIMING["rough"]
        how += "-forgiven"
    d["marks"].append({"how": how, "want": name})
    d["placed"] += 1
    if d["placed"] >= live.pub["count"]:
        live.over = True


def press_herbs(live, c, t, ev):
    herb_timeouts(live, c, t)
    d, p = live.data, live.pub
    if live.over or ev.get("herb") not in {h["key"] for h in p["herbs"]}:
        return herb_reply(live)
    phase, b = breath_at(p, t)
    out = p.get("volatile") == d["placed"]                 # the volatile herb goes in on the out-breath
    off = min(phase, 1 - phase) if out else abs(phase - 0.5)
    how = judge(max(0.0, off - GRACE / b), p["window"])
    right = ev["herb"] == c.order[d["placed"]]
    herb_mark(live, c, how if right else "wrong")
    d["since"] = t
    return herb_reply(live)


def herb_reply(live):
    d = live.data
    return {"placed": d["placed"], "marks": d["marks"], "over": live.over}


def press_fuse(live, c, t, ev):
    d, p = live.data, live.pub
    on_chaos = any(abs(t - x) <= p["chaoshalf"] + GRACE for x in p["chaos"])
    near = [(abs(t - m), i) for i, m in enumerate(p["meet"]) if i not in d["used"]]
    off, hit = min(near) if near else (99, None)
    if not on_chaos and hit is not None and off <= p["window"] * p["reach"] + GRACE:
        how = judge(max(0.0, off - GRACE_PRECISE), p["window"])
        if how == "rough" and off - GRACE <= p["window"]:
            how = "good"                                    # the full grace still applies to good
        d["used"].append(hit)
        d["fused"] += 1
        d["credit"] += TIMING[how]
        if d["fused"] >= p["need"]:
            live.over = True
        return {"fused": d["fused"], "hit": True, "how": how, "over": live.over}
    if not on_chaos and any(abs(t - m) <= p["window"] + GRACE for m in p["meet"]):
        return {"fused": d["fused"], "hit": None}          # a second tap on a meeting already used: nothing
    if c._mistake():
        d["unsteady"] += 1
    if p["seal"] and d["unsteady"] >= p["shatter"]:
        live.over = True
    return {"fused": d["fused"], "hit": False, "chaos": on_chaos, "unsteady": d["unsteady"], "over": live.over}


def press_condense(live, c, t, ev):
    if "pressed" not in live.data:
        live.data["pressed"] = max(0.0, t)
        live.over = True
    return {"over": True}


def press_tribulation(live, c, t, ev):
    d, p = live.data, live.pub
    strike_resolve(live, c, t)
    if live.over:
        return {"over": True}
    try:
        i = int(ev.get("bolt", -1))
    except (TypeError, ValueError):
        return {}
    if not 0 <= i < len(p["bolts"]) or t < p["bolts"][i]["warn"] - SEE_EARLY:
        return {}
    b, sec = p["bolts"][i], d["secret"][i]
    if ev.get("omen"):                                     # the warning: what kind of bolt, and where is safe
        return {"bolt": i, "kind": b["kind"], "safe": sec["safe"] if b["kind"] == "red" else None,
                "flip": sec["flip"]}
    what = ev.get("act")
    if what in ("protect", "left", "right") and i not in d["acts"] and t <= b["hit"] + GRACE:
        d["acts"][i] = (what, t)
        return {"bolt": i, "ok": bolt_ok(live, i)}
    return {"bolt": i}


def strike_resolve(live, c, t):
    """Every round whose bolts have all landed by t strikes (or is weathered), in order, through the bot's own
    rules: a round weathered is a strike blocked."""
    d, p = live.data, live.pub
    while not live.over and d["round"] < len(p["rounds"]) and t > p["bolts"][p["rounds"][d["round"]][-1]]["hit"] + GRACE:
        ok = all(bolt_ok(live, i) for i in p["rounds"][d["round"]])
        d["marks"].append(ok)
        c.act(c.strike_dir[0] if ok else None)
        d["round"] += 1
        if c.done:
            live.over = True
            marks = d["marks"]
            c.log = [f"⛈️ The Tribulation: {' '.join('🛡️' if m else '⚡' for m in marks)} · {sum(marks)} of "
                     f"{len(marks)} strikes weathered" + (". You survived it!" if all(marks) else
                                                          ". The pill survives, scarred: 8 patterns.")]


PRESS = {1: press_ignite, 2: press_herbs, 3: press_fuse, 4: press_condense, 5: press_fuse, 6: press_tribulation}


# ── settling a stage into the craft ──────────────────────────────────

def settle(live, c, t):
    """The stage is over (or ran out): score it into the craft. Returns what the page shows about how it went."""
    SETTLE[live.stage](live, c, t)
    live.over = True
    return live.result


def settle_ignite(live, c, t):
    p = live.pub
    share, heat = heat_run(p, live.data["holds"], live.length)
    score = max(0.0, min(1.0, (share - p["zero"]) / (p["perfect"] - p["zero"])))
    c.heat = round(heat)
    c.settle(score, [f"🔥 The heat held in the golden band {share:.0%} of the time. Heat control: **{score:.0%}**"])
    live.result = {"score": score, "share": share}


def settle_herbs(live, c, t):
    herb_timeouts(live, c, t)
    d = live.data
    while d["placed"] < live.pub["count"]:                    # the stage was cut short: the rest go cold
        herb_mark(live, c, "slow")
    score = d["points"] / live.pub["count"]
    on = sum(m["how"] == "precise" for m in d["marks"])
    wrong = sum(m["how"].startswith(("wrong", "slow")) for m in d["marks"])
    c.settle(score, [f"🌿 {on} of {live.pub['count']} herbs precisely on the breath"
                     + (f", {wrong} backlash{'es' if wrong > 1 else ''}" if wrong else "")
                     + f". Herb order: **{score:.0%}**"])
    live.result = {"score": score, "marks": d["marks"]}


def fuse_score(d, p):
    return max(0.0, min(1.0, d.get("credit", d["fused"]) / p["need"] - MISS_COST * d["unsteady"]))


def settle_fuse(live, c, t):
    d, p = live.data, live.pub
    score = fuse_score(d, p)
    missed = p["need"] - d["fused"]
    c.settle(score, [f"☯️ {d['fused']} of {p['need']} fusions" + (f", {missed} missed" if missed else "")
                     + (f", {d['unsteady']} unsteady" if d["unsteady"] else "")
                     + f". Fusion: **{score:.0%}**"])
    live.result = {"score": score}


def settle_seal(live, c, t):
    d, p = live.data, live.pub
    if d["fused"] < p["need"] - p["allowed"] or d["unsteady"] >= p["shatter"]:
        c.shatter_core([f"🔒 Only {d['fused']} of {p['need']} seals held."])
        live.result = {"score": 0, "shattered": True}
        return
    score = max(0.3, fuse_score(d, p))
    c.settle(score, [f"🔒 The core is sealed into the pill! **{score:.0%}**"])
    live.result = {"score": score}


def settle_condense(live, c, t):
    p = live.pub
    at = live.data.get("pressed")
    level, ph, length = (5, 0, 1) if at is None else pulse_at(p, at)
    if level >= 5:
        score, how = crafting.CRACKED_SCORE, f"💔 Too late: *{crafting.PULSES[-1]}*."
    elif level == 4:
        rate = judge(max(0.0, abs(ph - 0.5) - GRACE / length), p["glint"]) if abs(ph - 0.5) <= p["glint"] + GRACE / length else None
        score = TIMING[rate] if rate in ("precise", "good") else READY_NOT_GLINT
        how = {"precise": "✨ You condense in the heart of the glint: a perfect pulse!",
               "good": "✨ You condense in the glint."}.get(rate, "💊 You condense on the ready pulse, off its glint.")
    else:
        score, how = crafting.PULSE_SCORE[level], f"💊 You condense at *{crafting.PULSES[level]}*."
    c.settle(score, [f"{how} **{score:.0%}**"])
    live.result = {"score": score, "level": level}


def settle_tribulation(live, c, t):
    strike_resolve(live, c, max(t, live.length + 1))
    live.result = {"marks": live.data.get("marks", [])}


SETTLE = {1: settle_ignite, 2: settle_herbs, 3: settle_fuse, 4: settle_condense, 5: settle_seal,
          6: settle_tribulation}
