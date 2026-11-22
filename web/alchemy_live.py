"""
Live alchemy on the website: every stage of the craft played with the hands instead of buttons. docs/web.md,
"Live alchemy".

    🔥 Ignite      hold to pump the bellows, let go to cool; keep the heat inside the (moving) golden band
    🌿 Add Herbs   tap the right herb as the cauldron breathes in
    ☯️ Fuse        tap when the Yin and Yang orbs meet
    💊 Condense    tap when the pill glints, ready to set
    🔒 Seal Core   as Fuse, with the Beast Core: miss too many meetings and it shatters
    ⚡ Tribulation  raise your shield toward the lightning before it lands

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

from .inventory import item_picture

GRACE = 0.09            # seconds of network jitter forgiven on each side of a timing window
BEGIN_WAIT = 20.0       # a page that never says "begin": the stage starts this long after it was handed out
LINGER = 0.25           # a stage whose time is up is settled on the next request this long after its end
TICK = 0.02             # the heat simulation step (static/alchemy_live.js uses the same)

# 🔥 Ignite
IGNITE_WARMUP = 1.5     # the first seconds (getting the heat into the band) don't count
IGNITE_MIN_BAND = 10    # the heat band is never narrower than this (a big batch could squeeze it to 6°)
IGNITE_MAX_TEMPO = 1.35 # nor faster than this
BATCH_SWAY = 0.25       # each pill beyond the first calms the band's sway by this share
IGNITE_PERFECT = 0.85   # this share of the time in the band is a full score
HEAT_UP, HEAT_DOWN, HEAT_EASE = 24.0, 17.0, 0.25   # °/s while pumping / resting; seconds to reach that speed
GUST_PUSH, GUST_LENGTH, GUST_OMEN = 30.0, 0.7, 0.9
GUSTS = {"Mortal": 1, "Yellow": 2, "Mystic": 2, "Earth": 3, "Heaven": 3}
BAND_SWAY = {"Mortal": 3, "Yellow": 5, "Mystic": 7, "Earth": 9, "Heaven": 11}   # ° the band drifts each way

# 🌿 Herbs
BREATH = 1.3            # seconds per breath (at tempo 1)
BREATH_WINDOW = 0.18    # share of a breath, each side of its peak, that is "on the breath"
BREATHS_PER_HERB = 4    # no herb by then: the cauldron goes cold on that one
OFF_BREATH = 0.7

# ☯️ Fuse / 🔒 Seal
MEET = 1.5              # seconds between the orbs' meetings (at tempo 1)
MISS_COST = 0.15        # each tap when the orbs are apart
SEAL_SHATTER = 3        # this many taps out of time shatter the core

# 💊 Condense
PULSE = 0.82            # seconds per pulse (at tempo 1)
GLINT = 0.28            # share of the "ready" pulse, each side of its middle, that glints
READY_NOT_GLINT = 0.7   # pressed on the ready pulse, but not in its glint

# ⚡ Tribulation
CALM = (1.1, 1.9)
OMEN = 1.0              # seconds the clouds show where the bolt comes from (at tempo 1), never under 0.6
SHIELD_EARLY = 0.3


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
    g = dgrade(c)
    f = min(f, IGNITE_MAX_TEMPO)
    length = 4 + c.diff["rounds"] * 0.8
    w = max(c.zone_width, IGNITE_MIN_BAND)
    lo = max(5, min(c.zone_lo, 95 - w))
    sway = BAND_SWAY[g] * max(0.0, 1 - BATCH_SWAY * (c.batch - 1))
    sway = round(max(0, min(sway, lo - 5, 95 - lo - w)), 2)
    gusts, t = [], IGNITE_WARMUP + 0.4
    for _ in range(GUSTS[g]):
        room = length - 1.0 - t - (GUSTS[g] - len(gusts) - 1) * 1.6
        if room < 0:
            break
        start = t + rng.uniform(0, room)
        gusts.append([round(start, 2), rng.choice([1, -1])])
        t = start + 1.6
    pub = {"tempo": round(f, 3), "heat": c.heat, "lo": lo, "width": w, "sway": sway, "period": round(6.0 / f, 2),
           "phase": round(rng.uniform(0, 2 * math.pi), 3), "up": round(HEAT_UP * f ** 0.5, 2), "down": round(HEAT_DOWN * f ** 0.5, 2),
           "ease": HEAT_EASE, "gusts": gusts, "push": round(GUST_PUSH * f ** 0.5, 2), "gust": GUST_LENGTH, "omen": GUST_OMEN,
           "warmup": IGNITE_WARMUP, "perfect": IGNITE_PERFECT, "tick": TICK}
    return pub, {"holds": []}, length


def dgrade(c):
    """The grade whose difficulty this craft uses (breakthrough pills: one grade harder)."""
    for g, d in alchemy.DIFFICULTY.items():
        if d is c.diff:
            return g
    return c.grade


def make_herbs(c, rng, f):
    breath = BREATH / f
    kinds = sorted(set(c.order))
    pub = {"breath": round(breath, 3), "window": BREATH_WINDOW, "per": BREATHS_PER_HERB, "count": len(c.order),
           "clues": c.clues, "insights": c.insights,
           "herbs": [{"key": t, "name": alchemy.HERBS[c.grade][t][0], "emoji": loot.TYPE_EMOJI.get(t, "🌿"),
                      "picture": item_picture(loot.herb(c.grade, t))} for t in kinds]}
    return pub, {"placed": 0, "since": 0.0, "points": 0.0, "marks": []}, breath * BREATHS_PER_HERB * len(c.order)


def meetings(rng, f, count, wild):
    gap, out, t = MEET / f, [], MEET / f * 1.2
    for _ in range(count):
        out.append(round(t, 3))
        t += gap * (rng.uniform(0.7, 1.3) if wild else 1)
    return out


def make_fuse(c, rng, f, seal=False):
    need = alchemy.SEAL_CORE_MOVES if seal else max(3, c.diff["rounds"] - 2)
    spare = 1 if seal else 2
    meet = meetings(rng, f * (1.1 if seal else 1), need + spare, c.diff["wild_herbs"])
    window = 0.09 + 0.025 * c.balance_tolerance
    pub = {"meet": meet, "need": need, "window": round(window, 3), "seal": seal,
           "allowed": (1 if c.seal_pass >= 10 else 0) if seal else None, "shatter": SEAL_SHATTER if seal else None}
    return pub, {"fused": 0, "used": [], "unsteady": 0}, meet[-1] + 0.6


def make_condense(c, rng, f):
    pulse, start = PULSE / f, min(c.pulse, 1)
    decoy = None
    if rng.random() < c.diff["misleading"] * 2:
        decoy = rng.choice([2, 3])
    pub = {"pulse": round(pulse, 3), "start": start, "glint": GLINT, "decoy": decoy, "steps": len(crafting.PULSES) - 1}
    return pub, {}, (5 - start) * pulse


def make_tribulation(c, rng, f):
    omen = max(0.6, OMEN / f)
    strikes, t = [], 0.6
    for _ in range(crafting.TRIBULATION_STRIKES - c.strike):
        t += rng.uniform(*CALM)
        strikes.append([round(t, 3), round(t + omen, 3)])
        t += omen
    pub = {"strikes": strikes, "early": SHIELD_EARLY}
    return pub, {"i": 0, "pressed": None}, strikes[-1][1] + 0.6


MAKERS = {1: make_ignite, 2: make_herbs, 3: make_fuse, 4: make_condense,
          5: lambda c, rng, f: make_fuse(c, rng, f, seal=True), 6: make_tribulation}


# ── 🔥 the heat, worked out the same way the page draws it ───────────

def band_lo(p, t):
    return p["lo"] + p["sway"] * math.sin(2 * math.pi * t / p["period"] + p["phase"])


def gust_at(p, t):
    for start, way in p["gusts"]:
        if start <= t < start + p["gust"]:
            return way * p["push"]
    return 0.0


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
        want = p["up"] if pumping else -p["down"]
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
    if how == "on":
        d["points"] += 1
    elif how == "off":
        d["points"] += OFF_BREATH
    elif not c._mistake():                       # wrong herb or too slow, unless experience saves it
        d["points"] += OFF_BREATH
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
    phase = (t % p["breath"]) / p["breath"]
    on = abs(phase - 0.5) <= p["window"] + GRACE / p["breath"]
    right = ev["herb"] == c.order[d["placed"]]
    herb_mark(live, c, ("on" if on else "off") if right else "wrong")
    d["since"] = t
    return herb_reply(live)


def herb_reply(live):
    d = live.data
    return {"placed": d["placed"], "marks": d["marks"], "over": live.over}


def press_fuse(live, c, t, ev):
    d, p = live.data, live.pub
    hit = next((i for i, m in enumerate(p["meet"]) if abs(t - m) <= p["window"] + GRACE and i not in d["used"]), None)
    if hit is not None:
        d["used"].append(hit)
        d["fused"] += 1
        if d["fused"] >= p["need"]:
            live.over = True
        return {"fused": d["fused"], "hit": True, "over": live.over}
    if any(abs(t - m) <= p["window"] + GRACE for m in p["meet"]):
        return {"fused": d["fused"], "hit": None}          # a second tap on a meeting already used: nothing
    if c._mistake():
        d["unsteady"] += 1
    if p["seal"] and d["unsteady"] >= p["shatter"]:
        live.over = True
    return {"fused": d["fused"], "hit": False, "unsteady": d["unsteady"], "over": live.over}


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
    omen, bolt = p["strikes"][d["i"]]
    if ev.get("omen") and t >= omen - SHIELD_EARLY:          # the clouds show where it comes from
        return {"i": d["i"], "from": c.strike_dir[0]}
    way = ev.get("shield")
    if way in {k for k, _, _ in crafting.DIRECTIONS} and d["pressed"] is None and t >= omen - SHIELD_EARLY:
        d["pressed"] = way
        return {"i": d["i"], "shield": way}
    return {"i": d["i"]}


def strike_resolve(live, c, t):
    """Every bolt that has landed by t strikes (or breaks on the shield), in order, through the bot's own rules."""
    d, p = live.data, live.pub
    while not live.over and d["i"] < len(p["strikes"]) and t > p["strikes"][d["i"]][1] + GRACE:
        blocked = d["pressed"] == c.strike_dir[0]
        d.setdefault("marks", []).append(bool(blocked))
        c.act(c.strike_dir[0] if blocked else None)
        d["i"], d["pressed"] = d["i"] + 1, None
        if c.done:
            live.over = True
            marks = d["marks"]
            c.log = [f"⛈️ The Tribulation: {' '.join('🛡️' if m else '⚡' for m in marks)} · {sum(marks)} of "
                     f"{len(marks)} strikes blocked" + (". You survived it!" if all(marks) else
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
    score = min(1.0, share / p["perfect"])
    c.heat = round(heat)
    c.settle(score, [f"🔥 The heat held in the golden band {share:.0%} of the time. Heat control: **{score:.0%}**"])
    live.result = {"score": score, "share": share}


def settle_herbs(live, c, t):
    herb_timeouts(live, c, t)
    d = live.data
    while d["placed"] < live.pub["count"]:                    # the stage was cut short: the rest go cold
        herb_mark(live, c, "slow")
    score = d["points"] / live.pub["count"]
    on = sum(m["how"] == "on" for m in d["marks"])
    wrong = sum(m["how"].startswith(("wrong", "slow")) for m in d["marks"])
    c.settle(score, [f"🌿 {on} of {live.pub['count']} herbs on the breath"
                     + (f", {wrong} backlash{'es' if wrong > 1 else ''}" if wrong else "")
                     + f". Herb order: **{score:.0%}**"])
    live.result = {"score": score, "marks": d["marks"]}


def fuse_score(d, p):
    return max(0.0, min(1.0, d["fused"] / p["need"] - MISS_COST * d["unsteady"]))


def settle_fuse(live, c, t):
    d, p = live.data, live.pub
    score = fuse_score(d, p)
    c.settle(score, [f"☯️ {d['fused']} of {p['need']} fusions" + (f", {d['unsteady']} unsteady" if d["unsteady"] else "")
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
    if at is None:
        level = 5
    else:
        level = min(5, p["start"] + int(at // p["pulse"]))
    if level >= 5:
        score, how = crafting.CRACKED_SCORE, f"💔 Too late: *{crafting.PULSES[-1]}*."
    elif level == 4:
        mid = (4 - p["start"] + 0.5) * p["pulse"]
        glint = abs(at - mid) <= p["glint"] * p["pulse"] + GRACE
        score = 1.0 if glint else READY_NOT_GLINT
        how = "✨ You condense in the glint: a perfect pulse!" if glint else "💊 You condense on the ready pulse."
    else:
        score, how = crafting.PULSE_SCORE[level], f"💊 You condense at *{crafting.PULSES[level]}*."
    c.settle(score, [f"{how} **{score:.0%}**"])
    live.result = {"score": score, "level": level}


def settle_tribulation(live, c, t):
    strike_resolve(live, c, max(t, live.length + 1))
    live.result = {"marks": live.data.get("marks", [])}


SETTLE = {1: settle_ignite, 2: settle_herbs, 3: settle_fuse, 4: settle_condense, 5: settle_seal,
          6: settle_tribulation}


# ── the pill's quality ───────────────────────────────────────────────

TIERS = [(9, "Perfect", "#F5C35C"), (7, "Superior", "#B57BFF"), (4, "High quality", "#6FA8FF"), (1, "Normal", "#C9D2E6"),
         (0, "Failed", "#E05A4F")]


def tier(patterns):
    """Failed (0) · Normal (1-3) · High quality (4-6) · Superior (7-8) · Perfect (9, after the Tribulation)."""
    for least, name, color in TIERS:
        if patterns >= least:
            return {"name": name, "color": color}
