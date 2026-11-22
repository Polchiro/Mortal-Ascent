"""
The live forge on the website: the blacksmith's stages played with the hands instead of buttons. docs/web.md,
"Live forge".

    🔥 Ignite   hold to pump the bellows, tap V to open the vent; keep the forge heat in the band while the coals
                burn down
    🌡️ Heat     watch the metal's colour in the furnace mouth and pull it out when it matches the target
    🔨 Hammer   a glowing spot slides along the blank: strike when it passes under the hammer, Hard or Light as the
                metal asks (bright ring: hard; soft spreading glow: light), or Reheat when the glow fades

    💦 Quench   choose water or oil, then the glowing blade cools in real time: plunge it at the target temperature
    ✍️ Inscribe draw the rune stroke by stroke (drag; a tap is a dot), in the order the clue shows

The forge itself is still the bot's (bot/forging.py Forge): its safe zone, colours, metal states, the 20 points per
stage, the total, the rarity rules, materials and rewards. A live stage only decides that stage's share of its 20
points and hands it to Forge.settle.

The server is the referee, as in web/alchemy_live.py: a stage starts when the page says it began, and every press is
timed by the server's own clock from that moment, with a little grace for network jitter.

Harder gear adds challenges, not just speed (TIER_* below); the gear tier's decision time with rank relief and Swift
Hands sets the tempo; the Ignite band is the forge's safe zone (rank, fuel, Steady Hand).
"""
import math

import forge

from bot import forging

from .alchemy_live import Live, BEGIN_WAIT, GRACE, LINGER, TICK  # noqa: F401  (the same stage record and timing)

LIVE_STAGES = ("ignite", "heat", "hammer", "quench", "inscribe")
TIERS = forge.TIERS


def at_least(tier, from_tier):
    return TIERS.index(tier) >= TIERS.index(from_tier)


def tempo(g):
    """How fast this forge's hands must be: Ordinary 6 s → 0.75 … Divine 3 s → 1.5 (rank and Swift Hands slow it)."""
    return max(0.7, min(1.6, 4.5 / g.seconds))


def margin(g):
    """Each blacksmith rank above the gear's (3 at most) widens the timing windows a little."""
    return 1 + 0.06 * g.bonuses.get("rank", 0)


# 🔥 Ignite: pump (hold) heats, the vent (tap) dumps heat, the coals burn down so resting cools faster and faster
IGNITE_WARMUP, IGNITE_ZERO, IGNITE_PERFECT = 1.5, 0.45, 0.95       # the first seconds don't count; share → points
PUMP, REST, EASE = 22.0, 9.0, 0.3                                   # °/s pumping / resting at the start
BURN = {"ordinary": 0.5, "refined": 0.6, "spirit": 1.0, "treasure": 1.1, "divine": 1.2}   # rest cooling grows by this
VENT_DROP, VENT_COOLDOWN = 14.0, 1.2                                # ° a vent dumps; seconds before it works again
GUSTS = {"ordinary": 0, "refined": 1, "spirit": 2, "treasure": 2, "divine": 3}
GUST_PUSH, GUST_LENGTH, GUST_OMEN = 26.0, 0.7, 0.9
JAM_FROM, JAM_LENGTH, JAM_OMEN = "treasure", 2.0, 0.8               # the vent sticks for a while
FLARE_FROM, FLARE_LENGTH, FLARE_PUSH, FLARE_OMEN = "divine", 1.2, 16.0, 0.9


def make_ignite(g, rng, f):
    t = g.tier
    length = 4 + g.diff["heat_rounds"] * 0.8
    gusts, at = [], IGNITE_WARMUP + 0.4
    for _ in range(GUSTS[t]):
        room = length - 1.0 - at - (GUSTS[t] - len(gusts) - 1) * 1.6
        if room < 0:
            break
        start = at + rng.uniform(0, room)
        gusts.append([round(start, 2), rng.choice([1, -1])])
        at = start + 1.6
    busy = [x for x, _ in gusts]

    def free(lo, hi):
        tries = [round(rng.uniform(lo, hi), 2) for _ in range(12)]
        return max(tries, key=lambda x: min([abs(x - b) for b in busy] or [9]))

    jam = free(length * 0.35, length * 0.7) if at_least(t, JAM_FROM) else None
    if jam is not None:
        busy.append(jam)
    flare = free(length * 0.3, length * 0.75) if at_least(t, FLARE_FROM) else None
    pub = {"heat": g.heat, "lo": g.zone_lo, "width": g.zone_width, "up": round(PUMP * f ** 0.5, 2),
           "down": round(REST * f ** 0.5, 2), "burn": BURN[t], "ease": EASE, "vent": VENT_DROP,
           "cooldown": VENT_COOLDOWN, "gusts": gusts, "push": round(GUST_PUSH * f ** 0.5 / margin(g), 2),
           "gust": GUST_LENGTH, "omen": GUST_OMEN, "jam": [jam, JAM_LENGTH] if jam is not None else None,
           "jamomen": JAM_OMEN, "flare": [flare, FLARE_LENGTH] if flare is not None else None,
           "flarepush": round(FLARE_PUSH * f ** 0.5, 2), "flareomen": FLARE_OMEN, "warmup": IGNITE_WARMUP,
           "zero": IGNITE_ZERO, "perfect": IGNITE_PERFECT, "tick": TICK, "length": round(length, 3)}
    return pub, {"events": []}, length


def jammed(p, t):
    return bool(p.get("jam")) and p["jam"][0] <= t < p["jam"][0] + p["jam"][1]


def push_at(p, t):
    push = 0.0
    if p.get("flare") and p["flare"][0] <= t < p["flare"][0] + p["flare"][1]:
        push += p["flarepush"]
    for start, way in p["gusts"]:
        if start <= t < start + p["gust"]:
            push += way * p["push"]
    return push


def ignite_run(p, events, until):
    """(share of the counted time in the band, final heat). events: [(t, "pump"/"rest"/"vent")] as the server heard
    them; a vent inside its cooldown or while jammed does nothing (static/forge_live.js runs the same)."""
    heat, speed, pumping, i, last_vent = float(p["heat"]), 0.0, False, 0, -99.0
    counted = inside = 0
    lo, hi = p["lo"], p["lo"] + p["width"]
    for k in range(int(round(until / p["tick"]))):
        t = k * p["tick"]
        while i < len(events) and events[i][0] <= t:
            what = events[i][1]
            if what == "vent":
                if t - last_vent >= p["cooldown"] and not jammed(p, t):
                    heat -= p["vent"]
                    last_vent = t
            else:
                pumping = what == "pump"
            i += 1
        rest = p["down"] * (1 + p["burn"] * t / p["length"])
        want = p["up"] if pumping else -rest
        speed += (want - speed) * min(1.0, p["tick"] / p["ease"])
        heat = max(0.0, min(100.0, heat + (speed + push_at(p, t)) * p["tick"]))
        if t >= p["warmup"]:
            counted += 1
            inside += lo <= heat <= hi
    return (inside / counted if counted else 0.0), heat


def press_ignite(live, g, t, ev):
    what = ev.get("do")
    if what in ("pump", "rest", "vent") and t <= live.length + GRACE:
        live.data["events"].append((max(0.0, t), what))
    return {}


def settle_ignite(live, g, t):
    p = live.pub
    share, heat = ignite_run(p, live.data["events"], live.length)
    frac = max(0.0, min(1.0, (share - p["zero"]) / (p["perfect"] - p["zero"])))
    g.heat = round(heat)
    g.settle(frac, [f"🔥 The forge held in the band {share:.0%} of the time."])
    live.result = {"share": share}


# 🌡️ Heat: the colour climbs through forge.HEAT_COLORS; pull it out at the target. Past white it burns.
COLOR_SECONDS = 1.6          # seconds per colour at tempo 1, each varied ±15%
UNEVEN_FROM = "spirit"       # the tip heats ahead of the base: judge the middle
SHIMMER_FROM = "treasure"    # the colour flickers
RUSH_FROM = "divine"         # the last colours come faster


def make_heat(g, rng, f):
    n = len(forge.HEAT_COLORS)
    bounds, t = [0.0], 0.0
    for i in range(n):
        d = COLOR_SECONDS / f * rng.uniform(0.85, 1.15)
        if at_least(g.tier, RUSH_FROM) and i >= n - 2:
            d *= 0.7
        t += d
        bounds.append(round(t, 3))
    pub = {"bounds": bounds, "colors": forge.HEAT_COLORS, "target": g.target, "uneven": at_least(g.tier, UNEVEN_FROM),
           "shimmer": at_least(g.tier, SHIMMER_FROM), "length": round(bounds[-1] + 0.3, 3)}
    return pub, {}, bounds[-1] + 0.3


def color_at(p, t):
    """The colour (index) of the metal's middle at t; len(colors) = burnt."""
    return sum(1 for b in p["bounds"][1:] if t >= b)


def press_heat(live, g, t, ev):
    if ev.get("do") == "pull" and "pulled" not in live.data:
        live.data["pulled"] = max(0.0, t)
        live.over = True
    return {"over": True}


def settle_heat(live, g, t):
    p = live.pub
    at = live.data.get("pulled")
    c = color_at(p, at) if at is not None else len(p["colors"])
    if c >= len(p["colors"]):
        g.settle(0, ["💔 The metal burns past white and spits sparks!"])
        live.result = {"color": None}
        return
    pts = forge.HEAT_POINTS_BY_MISS.get(abs(c - p["target"]), 0)
    g.settle(pts / forge.STAGE_MAX_POINTS, [f"🌡️ You pull it out **{p['colors'][c]}**."])
    live.result = {"color": c}


# 🔨 Hammer: each strike a spot slides along the blank and passes under the hammer once
SWEEP = 1.5                  # seconds the spot takes to cross (at tempo 1)
HIT_WINDOW = 0.16            # seconds each side of "under the hammer" (× the rank margin)
STRIKE_GAP = 0.45            # seconds between strikes
MOVING_FROM = "spirit"       # the spot speeds up and slows down as it slides
DECOY_FROM = "treasure"      # a fainter, false spot crosses first: striking it is a bad blow
DOUBLE_FROM = "divine"       # some strikes want two blows, one on each of two spots


def make_hammer(g, rng, f):
    strikes, t = [], 0.6
    for i in range(g.diff["strikes"]):
        state = rng.choice(list(forge.HAMMER_STATES))
        sweep = SWEEP / f * rng.uniform(0.9, 1.1)
        under = round(t + sweep * rng.uniform(0.45, 0.65), 3)
        s = {"state": state, "start": round(t, 3), "end": round(t + sweep, 3), "under": [under]}
        if state != "cooling" and at_least(g.tier, DOUBLE_FROM) and rng.random() < 0.5:
            s["under"].append(round(min(t + sweep - 0.15, under + 0.42 / f), 3))
        if state != "cooling" and at_least(g.tier, DECOY_FROM) and rng.random() < 0.6:
            s["decoy"] = round(t + sweep * 0.2, 3)
        if at_least(g.tier, MOVING_FROM):
            s["wobble"] = round(rng.uniform(0.15, 0.3), 2)
        strikes.append(s)
        t += sweep + STRIKE_GAP
    pub = {"strikes": strikes, "window": round(HIT_WINDOW * margin(g), 3), "states": forge.HAMMER_STATES,
           "length": round(t, 3)}
    return pub, {"acts": {}}, t


def strike_at(p, t):
    """Which strike t falls in (its whole stretch, from its start to the next one's)."""
    s = p["strikes"]
    for i in range(len(s)):
        nxt = s[i + 1]["start"] if i + 1 < len(s) else p["length"]
        if s[i]["start"] - 0.1 <= t < nxt:
            return i
    return None


def press_hammer(live, g, t, ev):
    p, acts = live.pub, live.data["acts"]
    what = ev.get("do")
    i = strike_at(p, t)
    if what not in ("hard", "light", "reheat") or i is None:
        return {}
    acts.setdefault(i, []).append((max(0.0, t), what))
    return {"strike": i, "good": strike_good(p, i, acts.get(i, [])) if len(acts[i]) >= need(p, i) else None}


def need(p, i):
    s = p["strikes"][i]
    return 1 if s["state"] == "cooling" else len(s["under"])


def strike_good(p, i, presses):
    """A good strike: the right blow (forge.HAMMER_STATES answer); a hard or light blow also lands with the spot under
    the hammer, every spot once, and never on the decoy."""
    s = p["strikes"][i]
    want = forge.HAMMER_STATES[s["state"]]["answer"]
    if not presses:
        return False
    if want == "reheat":
        return presses[0][1] == "reheat"
    hits = [x for x in presses if x[1] in ("hard", "light")]
    if any(x[1] != want for x in presses) or len(hits) < len(s["under"]):
        return False
    w = p["window"] + GRACE
    if s.get("decoy") is not None and any(abs(x[0] - s["decoy"]) <= w and all(abs(x[0] - u) > w for u in s["under"])
                                          for x in hits):
        return False
    return all(any(abs(x[0] - u) <= w for x in hits) for u in s["under"])


def settle_hammer(live, g, t):
    p, acts = live.pub, live.data["acts"]
    good = [strike_good(p, i, acts.get(i, [])) for i in range(len(p["strikes"]))]
    g.settle(sum(good) / len(good), [f"🔨 {sum(good)} of {len(good)} strikes landed true."])
    live.result = {"good": good}


# 💦 Quench: water (fast, risky) or oil (slow, safe), the bot's QUENCH; then the blade cools from its start
# temperature, and the plunge is judged by the bot's own rule (forge_live.quench_points = Forge._quench_points)
COOL = 95.0                  # °/s it cools at tempo 1 (water cools it faster still: COOL_MEDIUM)
COOL_MEDIUM = {"water": 1.15, "oil": 0.85}
DRAUGHTS_FROM = "spirit"     # the cooling speeds up and slows down
STEAM_FROM = "treasure"      # steam hides the thermometer now and then (the blade's own colour still shows)
RUSH_COOL_FROM = "divine"    # it cools faster the nearer it gets to the target
CHOOSE_SECONDS = 8.0         # time to pick a quench before it picks oil


def make_quench(g, rng, f):
    t = forge.QUENCH_TEMPS
    start, target = rng.randint(*t["start"]), rng.randint(*t["target"])
    wave = [round(rng.uniform(0, 6.28), 2), round(rng.uniform(0.6, 1.1), 2)] if at_least(g.tier, DRAUGHTS_FROM) else None
    steam = []
    if at_least(g.tier, STEAM_FROM):
        steam = [[round(x, 2), 0.7] for x in (rng.uniform(0.8, 1.6), rng.uniform(2.0, 2.8))]
    pub = {"start": start, "target": target, "window": {m: round(g.window * forge.QUENCH[m]["window_mult"], 1) for m in forge.QUENCH},
           "max": {m: forge.QUENCH[m]["max_points"] for m in forge.QUENCH}, "cool": round(COOL * f, 2), "medium": COOL_MEDIUM,
           "wave": wave, "steam": steam, "rush": at_least(g.tier, RUSH_COOL_FROM), "choose": CHOOSE_SECONDS, "tick": TICK}
    span = (start - target) / (COOL * f * COOL_MEDIUM["oil"] * 0.6) + 2.0         # time enough to go cold, slowly
    pub["length"] = round(CHOOSE_SECONDS + span, 3)
    return pub, {}, CHOOSE_SECONDS + span


def quench_temp(p, medium, since):
    """The blade's temperature `since` seconds after the quench was chosen (static/forge_live.js runs the same)."""
    temp, k = float(p["start"]), 0
    rate0 = p["cool"] * p["medium"][medium]
    steps = int(max(0.0, since) / p["tick"])
    for k in range(steps):
        tt = k * p["tick"]
        rate = rate0
        if p["wave"]:
            rate *= 1 + 0.3 * math.sin(p["wave"][1] * 2 * math.pi * tt + p["wave"][0])
        if p["rush"]:
            rate *= 1 + 0.6 * max(0.0, 1 - (temp - p["target"]) / 250)
        temp -= rate * p["tick"]
    return temp


def quench_points(p, medium, temp):
    """The bot's Forge._quench_points, for this medium's window and top points."""
    off, half, top = abs(temp - p["target"]), p["window"][medium] / 2, p["max"][medium]
    if off <= half / 2:
        return top
    if off <= half:
        return round(top * forge.QUENCH_HALF_POINTS)
    return forge.QUENCH_MISS_POINTS


def press_quench(live, g, t, ev):
    d, what = live.data, ev.get("do")
    if what in forge.QUENCH and "medium" not in d:
        d["medium"], d["chose"] = what, max(0.0, t)
        return {"medium": what}
    if what == "plunge" and "medium" in d and "plunged" not in d:
        d["plunged"] = max(0.0, t)
        live.over = True
        return {"over": True}
    return {}


def settle_quench(live, g, t):
    p, d = live.pub, live.data
    medium = d.get("medium") or "oil"
    chose = d.get("chose", min(t, p["choose"]))
    g.medium = medium
    if "plunged" in d:
        temp = quench_temp(p, medium, d["plunged"] - chose)
        pts = quench_points(p, medium, temp)
        g.temp, g.quench_target = round(temp), p["target"]
        word = "perfect!" if pts == p["max"][medium] else "close." if pts > forge.QUENCH_MISS_POINTS else "the steel shudders."
        g.settle(pts / forge.STAGE_MAX_POINTS, [f"💦 You plunge it into the {medium} at **{round(temp)}°**: {word}"])
        live.result = {"medium": medium, "temp": round(temp), "pts": pts}
    else:
        g.settle(forge.QUENCH_MISS_POINTS / forge.STAGE_MAX_POINTS, ["🥶 The blade went cold before the quench."])
        live.result = {"medium": medium, "temp": None}


# ✍️ Inscribe: the bot's rune, strokes and clue (Forge._start_inscribe); each stroke drawn by hand, in order
STROKE_SECONDS = 2.6         # seconds per stroke at tempo 1 (the whole carving's time)
FADE_FROM = "treasure"       # the clue fades after a look: carve it from memory
FADE_AFTER = 2.5


def make_inscribe(g, rng, f):
    n = len(g.order)
    length = 1.0 + n * STROKE_SECONDS / f * margin(g)
    pub = {"rune": g.rune, "clue": g.clue, "count": n, "strokes": forge.STROKES,
           "fade": FADE_AFTER if at_least(g.tier, FADE_FROM) else None, "length": round(length, 3)}
    return pub, {"carved": []}, length


def press_inscribe(live, g, t, ev):
    d, what = live.data, ev.get("do")
    if what not in forge.STROKES or len(d["carved"]) >= len(g.order):
        return {}
    i = len(d["carved"])
    ok = what == g.order[i]
    d["carved"].append(ok)
    if len(d["carved"]) >= len(g.order):
        live.over = True
    return {"i": i, "ok": ok, "want": None if ok else g.order[i], "over": live.over}


def settle_inscribe(live, g, t):
    d, n = live.data, len(g.order)
    right = sum(d["carved"])
    g.carved_ok = list(d["carved"]) + [False] * (n - len(d["carved"]))
    g.carved, g.right = n, right
    g.settle(right / n, [f"✨ The Rune of {g.rune}: {right} of {n} strokes carved clean."
                         + ("" if len(d["carved"]) == n else " The chisel ran out of time.")])
    live.result = {"right": right, "n": n}


MAKERS = {"ignite": make_ignite, "heat": make_heat, "hammer": make_hammer, "quench": make_quench,
          "inscribe": make_inscribe}
PRESS = {"ignite": press_ignite, "heat": press_heat, "hammer": press_hammer, "quench": press_quench,
         "inscribe": press_inscribe}
SETTLE = {"ignite": settle_ignite, "heat": settle_heat, "hammer": settle_hammer, "quench": settle_quench,
          "inscribe": settle_inscribe}


def make(g, rng, n, now):
    f = tempo(g)
    pub, data, length = MAKERS[g.stage](g, rng, f)
    pub.update(stage=g.stage, tempo=round(f, 3), length=round(length, 3))
    return Live(n, g.stage, now, length, pub, data=data)


def press(live, g, t, ev):
    if live.over:
        return {"over": True}
    return PRESS[live.stage](live, g, t, ev or {})


def settle(live, g, t):
    SETTLE[live.stage](live, g, t)
    live.over = True
    return live.result
