"""
Practice on the website: drilling one technique with Senior Sister Xue (docs/technique.md "Practice on the website").

WEBSITE ONLY (SHOAIB, Nov 24): Discord's /practice keeps its four challenges. Here a session is a ~40-second real-time
drill chosen by the technique itself:

  Striking (every attack technique): targets light up on a training dummy (a kicking post for kicks); hit each as
      its ring closes. Palms strike targets in pairs, fingers and piercing techniques small targets, combo techniques
      quick chains, heavy techniques a charge (hold, release on the mark).
  Defending (every defence technique): blows come high (a sandbag), middle (a staff) or low (a log); meet each in
      its lane as it lands. Stances brace (press and hold through the blow), deflections and steps time a tap,
      countering techniques strike back after some deflections, recovering techniques breathe between blows.

What it pays is the bot's own: the score becomes mastery EXP through bot/trainer.finish_practice (40 EXP × score,
+15% per condition, the event, the daily rates, a score under 50% earns 10%, Insightful gear, the Insight Ink
chance, the quest count, the 30-minute rest). The rest starts when the drill is set up, as on Discord. The tier is
the technique's mastery stage + 1; conditions and events are rolled from the bot's tables, and each means here what
it means there in spirit: Heavy Rain makes every window 25% narrower, Night Training hides a target until late,
Drunken Master adds feints (targets you must not touch), Old Injury makes charges and braces count half. A Rival
Disciple steps in after the drill with three quick targets: meet two and the EXP doubles.

The server referees: it makes the pattern, it keeps the time the drill began, and when the page sends what was
pressed and when, it grades every target itself, checks the drill took as long as it must, and works out the score.
The page's own clock times the presses (so a slow connection costs nothing), which means a perfect bot could play
it, as an auto-clicker could on Discord; the daily rates cap what that is worth. Drills live in this process's
memory, like spars: a restart ends one unpaid (its rest stays).
"""
import json
import os
import random
import re
import threading
import time
from dataclasses import dataclass, field

import challenges
import looks
import technique

from bot import db, trainer
from bot import player as players

from . import technique_fx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = "/art/practice"
HALL_PICTURE, HALL_SOUND = ART + "/hall.jpg", ART + "/hall.wav"      # the hall's sound: her "watching" video's air
NAME = "Senior Sister Xue"
TITLE = "Drill Instructor"

# The tiers (the technique's mastery stage + 1). ms. gap: between beats; approach: how long a target shows before
# it is due; perfect / good: the grading windows either side of that moment; count: the beats in a drill (the
# finishing blow and a rival's round come on top); doubles: the chance a beat is two targets at once; feints: the
# chance a beat is one you must leave alone. The last stage, Return to Simplicity, is calmer: fewer, slower beats,
# each wanting near-perfect timing.
TIERS = {
    1: {"gap": 1150, "approach": 1500, "perfect": 120, "good": 280, "count": 18, "doubles": 0.0, "feints": 0.0},
    2: {"gap": 1000, "approach": 1350, "perfect": 110, "good": 260, "count": 20, "doubles": 0.0, "feints": 0.0},
    3: {"gap": 880, "approach": 1200, "perfect": 100, "good": 240, "count": 22, "doubles": 0.2, "feints": 0.0},
    4: {"gap": 800, "approach": 1100, "perfect": 90, "good": 220, "count": 22, "doubles": 0.25, "feints": 0.1},
    5: {"gap": 1050, "approach": 1050, "perfect": 75, "good": 190, "count": 16, "doubles": 0.15, "feints": 0.1},
}
FORM_SHARE, FORM_SLOWER = 0.25, 1.4     # the first quarter of the beats ("Form") comes 40% slower
LEAD_IN = 900                           # ms of quiet before the first target shows
CHAIN_GAP = 320                         # between the targets of a combo chain
CHARGE_LEAD = 650                       # a charge's target shows this much earlier, to hold it
BRACE_HOLD, BRACE_HOLD_HEAVY = 400, 650 # how long a brace is held through the blow (Unbreakable: the heavier)
HOLD_SLACK = 90                         # a brace let go this close to its end still counts as held
COUNTER_AFTER = 450                     # a counter after a deflection
RIVAL_TARGETS, RIVAL_GAP = 3, 700
DRUNK_FEINTS = 0.15                     # Drunken Master: at least this many feints
RAIN = challenges.CONDITIONS["heavy_rain"]["timer_multiplier"]          # 0.75: windows 25% narrower
NIGHT_SHOW = 0.4                        # Night Training: a target shows only in the last 40% of its approach
POINTS = {"perfect": 1.0, "good": 0.6, "avoided": 1.0}
STRAY_COST = 0.2                        # a press at nothing costs a fifth of a target (mashing never pays)
STREAK_SHARE = 0.15                     # the score: 85% accuracy, 15% the longest unbroken run
CONDITIONS = {"strike": ["heavy_rain", "night_training", "drunken_master", "old_injury"],
              "defend": ["heavy_rain", "night_training", "drunken_master", "old_injury"]}
CONDITION_TEXT = {"heavy_rain": "every timing window is 25% narrower",
                  "night_training": "targets show only at the last moment",
                  "drunken_master": "more feints: leave the dark targets alone",
                  "old_injury": "charges and braces count half"}
EVENT_TEXT = {"wandering_hermit": "A Wandering Hermit watches: the hardest drill, two conditions, EXP ×5.",
              "epiphany": "Epiphany! Everything you learn today sticks: EXP +50%.",
              "rival_disciple": "A rival disciple waits by the door. Beat their three targets after the drill for EXP ×2."}

STRIKE_LANES = {"dummy": 4, "post": 3}       # targets on the dummy (1-4) / the kicking post (1-3)
DEFEND_LANES = 4                             # 0 high (sandbag), 1 middle (staff), 2 low (log), 3 Space (breath / counter)
TARGETS = ["straw", "dummy", "iron", "stone", "jade"]     # the dummy by mastery stage (1-5)
DRILL_NAMES = {"strike": "Striking drill", "defend": "Defending drill"}
MOTION_TEXT = {
    "fist": "Hit each target as its ring closes on it.",
    "palm": "Palm strikes land in pairs: hit both targets as their rings close.",
    "kick": "Kick each target on the post as its ring closes.",
    "finger": "Finger strikes are precise: the targets are small, the timing tight.",
    "brace": "Brace in the blow's lane as it lands, and hold until it has passed.",
    "deflect": "Turn each blow aside in its lane the moment it lands.",
    "sidestep": "Step clear of each blow in its lane the moment it arrives.",
}
EFFECT_TEXT = {
    "combo": "Your technique chains: some targets come in quick runs.",
    "heavy": "Your technique is heavy: hold on a charge target and release as its ring closes.",
    "pierce": "Your technique pierces: its targets are small.",
    "counter": "Your technique counters: after some deflections, strike back with your Counter key (Space).",
    "recover": "Your technique restores: breathe with your Breathe key (Space) when the ring of breath fills.",
    "unbreakable": "Your technique is unbreakable: the blows are heavier, the braces longer.",
}
LINES = {"begin": {"strike": "Strike only when the ring closes. Not before, not after. Begin!",
                   "defend": "Read where the blow comes from and meet it. Begin!"},
         "great": "That's how it's done. Your hands remember now.",
         "good": "Not bad. Again tomorrow, a little sharper.",
         "poor": "Sloppy. Watch the rings, not your own fists.",
         "bad": "Did you sleep through it? Again, properly this time."}


def plain(text):
    """A bot line without Discord's marks and leading emoji."""
    text = re.sub(r"\*+", "", text or "")
    return "\n".join(re.sub(r"^[^\w\"'(]+", "", line).strip() for line in text.splitlines()).strip()


def drill_of(tech):
    """How a technique drills: {mode, motion, effect, arg}."""
    spec = players.TECH_BY_NAME.get(tech["name"], {})
    effect, arg = spec.get("effect") or (None, None)
    fx = technique_fx.of(tech["name"], tech.get("grade", "Mortal"), "female") or {}
    attack = tech["type"] == "attack"
    motion = fx.get("motion") or next(iter(technique_fx.assets(tech["name"], "female")[0]), None) or \
        ("fist" if attack else "brace")
    if attack and motion not in ("fist", "palm", "kick", "finger"):
        motion = "fist"
    if not attack and motion not in ("brace", "deflect", "sidestep"):
        motion = "brace"
    return {"mode": "strike" if attack else "defend", "motion": motion, "effect": effect, "arg": arg}


def roll(tech, rng):
    """The session's tier, conditions and event, from the bot's tables (bot/trainer.roll_session's rolls)."""
    tier = players.stage_of(tech) + 1
    event = None
    for name, spec in challenges.EVENTS.items():
        if rng.random() < spec["chance"]:
            event = name
            break
    if event == "wandering_hermit":
        tier = 5
    lo, hi = challenges.CONDITIONS_PER_TIER[tier]
    n = rng.randint(lo, hi)
    if event == "wandering_hermit":
        n = challenges.EVENTS["wandering_hermit"]["extra_conditions"]
    pool = CONDITIONS[drill_of(tech)["mode"]]
    return tier, rng.sample(pool, min(n, len(pool))), event


_sheets = []


def instructor_sheets():
    """Her movements (art/practice/instructor/: watch, begin, approve, disapprove + sheets.json, cut from SHOAIB's
    videos by scripts/make_master_sheets.py --instructor), or None: then her portrait stands in."""
    if not _sheets:
        try:
            with open(os.path.join(ROOT, "art", "practice", "instructor", "sheets.json")) as fh:
                data = json.load(fh)
            _sheets.append(data if {"watch", "begin", "approve", "disapprove"} <= set(data["sheets"]) else None)
        except (OSError, ValueError, KeyError):
            _sheets.append(None)
    return _sheets[0]


def windows(tier, conditions, drill):
    t = dict(TIERS[tier])
    scale = RAIN if "heavy_rain" in conditions else 1.0
    if drill["motion"] == "finger" or drill["effect"] == "pierce":
        scale *= 0.85
    if drill["motion"] == "deflect":
        scale *= 0.9
    t["perfect"], t["good"] = round(t["perfect"] * scale), round(t["good"] * scale)
    if "drunken_master" in conditions:
        t["feints"] = max(t["feints"], DRUNK_FEINTS)
    return t


def pattern(drill, tier, conditions, event, rng):
    """The drill's targets, in order of when they are due: dicts with i, at (ms from the start), lane, kind (tap,
    charge, brace, feint), small, hold (a brace's ms), phase (form, flow, finish, rival)."""
    w = windows(tier, conditions, drill)
    strike = drill["mode"] == "strike"
    lanes = STRIKE_LANES["post" if drill["motion"] == "kick" else "dummy"] if strike else 3
    small = strike and (drill["motion"] == "finger" or drill["effect"] == "pierce")
    hold = BRACE_HOLD_HEAVY if drill["effect"] == "unbreakable" else BRACE_HOLD
    out = []

    def add(at, lane, kind, phase, **more):
        out.append({"at": round(at), "lane": lane, "kind": kind, "small": small and lane < lanes, "phase": phase,
                    **more})

    at = LEAD_IN + w["approach"] + CHARGE_LEAD
    for beat in range(w["count"]):
        form = beat < w["count"] * FORM_SHARE
        phase = "form" if form else "flow"
        gap = w["gap"] * (FORM_SLOWER if form else 1)
        lane = rng.randrange(lanes)
        if not form and w["feints"] and rng.random() < w["feints"]:
            add(at, lane, "feint", phase)
        elif strike:
            if drill["effect"] == "combo" and not form and rng.random() < 0.45:
                run = drill["arg"][0] if isinstance(drill["arg"], tuple) else 2
                for k in range(run):
                    add(at + k * CHAIN_GAP, rng.randrange(lanes), "tap", phase, chain=k + 1)
                gap += (run - 1) * CHAIN_GAP
            elif drill["effect"] == "heavy" and rng.random() < 0.35:
                add(at, lane, "charge", phase)
                gap += 250
            elif drill["motion"] == "palm" or (not form and rng.random() < w["doubles"]):
                other = rng.choice([x for x in range(lanes) if x != lane])
                add(at, lane, "tap", phase, pair=True)
                add(at, other, "tap", phase, pair=True)
            else:
                add(at, lane, "tap", phase)
        else:
            if drill["motion"] == "brace":
                add(at, lane, "brace", phase, hold=hold)
                gap += hold * 0.5
            else:
                add(at, lane, "tap", phase)
            if drill["effect"] == "counter" and not form and rng.random() < 0.5:
                add(at + COUNTER_AFTER, 3, "tap", phase, counter=True)
                gap += 200
            if drill["effect"] == "recover" and rng.random() < 0.4:
                add(at + gap * 0.55, 3, "tap", phase, breath=True)
                gap *= 1.15
        at += gap
    # the finishing blow: a charge into the heart of the dummy, or one heavy blow to brace / meet
    if strike:
        add(at + 200, min(1, lanes - 1), "charge", "finish", finish=True)
    else:
        add(at + 200, 1, "brace" if drill["motion"] == "brace" else "tap", "finish", finish=True, hold=hold)
    at += 200 + w["gap"]
    if event == "rival_disciple":
        at += 900
        for k in range(RIVAL_TARGETS):
            add(at + k * RIVAL_GAP, rng.randrange(lanes), "tap", "rival", rival=True)
    out.sort(key=lambda p: (p["at"], p["lane"]))
    for i, p in enumerate(out):
        p["i"] = i
        p.setdefault("hold", 0)
    return out, w


def duration(prompts, w):
    last = max(p["at"] + p.get("hold", 0) for p in prompts)
    return last + w["good"] + 600


def mark(p, t, w):
    off = abs(t - p["at"])
    return "perfect" if off <= w["perfect"] else "good" if off <= w["good"] else None


def visible(p, t, w):
    lead = w["approach"] + (CHARGE_LEAD if p["kind"] == "charge" else 0)
    return p["at"] - lead <= t <= p["at"] + w["good"]


def grade(prompts, inputs, w):
    """Grade every target from the presses: inputs are (t ms, lane, 'd' | 'u'). Returns (results, strays): results
    a list in the targets' order of perfect / good / miss (a target) or avoided / struck (a feint)."""
    res = [None] * len(prompts)
    held = {}
    strays = 0
    for t, lane, kind in sorted(inputs, key=lambda x: (x[0], x[2] == "d")):
        if kind == "d":
            if lane in held:
                continue
            cands = [p for p in prompts if p["lane"] == lane and res[p["i"]] is None and p["kind"] != "feint" and
                     (visible(p, t, w) if p["kind"] == "charge" else abs(t - p["at"]) <= w["good"])]
            if cands:
                p = min(cands, key=lambda q: abs(t - q["at"]))
                if p["kind"] == "tap":
                    res[p["i"]] = mark(p, t, w)
                elif p["kind"] == "brace":
                    res[p["i"]] = mark(p, t, w)
                    held[lane] = (p, t)
                else:                                             # a charge: graded when let go
                    res[p["i"]] = "holding"
                    held[lane] = (p, t)
                continue
            feint = [p for p in prompts if p["lane"] == lane and p["kind"] == "feint" and res[p["i"]] is None and
                     visible(p, t, w)]
            if feint:
                res[feint[0]["i"]] = "struck"
            else:
                strays += 1
        else:
            if lane not in held:
                continue
            p, _ = held.pop(lane)
            if p["kind"] == "charge":
                res[p["i"]] = mark(p, t, w) or "miss"
            elif t < p["at"] + p["hold"] - HOLD_SLACK:                # let go of a brace too soon
                res[p["i"]] = "good" if res[p["i"]] == "perfect" else "miss"
    for lane, (p, _) in held.items():                               # still held when the drill ended
        if p["kind"] == "charge":
            res[p["i"]] = "miss"
    out = []
    for p, r in zip(prompts, res):
        if p["kind"] == "feint":
            out.append("struck" if r == "struck" else "avoided")
        else:
            out.append(r if r in ("perfect", "good") else "miss")
    return out, strays


def score_of(prompts, results, strays, conditions):
    """(score 0-1, details). Accuracy is most of it: a perfect is worth 1, a good 0.6, a feint left alone 1, and
    each press at nothing costs 0.2; the rest is the longest unbroken run. The rival's targets don't count."""
    rows = [(p, r) for p, r in zip(prompts, results) if not p.get("rival")]
    hurt = "old_injury" in conditions
    weight = [0.5 if hurt and p["kind"] in ("charge", "brace") else 1.0 for p, _ in rows]
    total = sum(weight) or 1
    got = sum(w * POINTS.get(r, 0) for w, (_, r) in zip(weight, rows))
    accuracy = max(0.0, (got - STRAY_COST * strays) / total)
    run = best = 0
    for _, r in rows:
        run = run + 1 if r in POINTS else 0
        best = max(best, run)
    streak = best / max(1, len(rows))
    score = max(0.0, min(1.0, (1 - STREAK_SHARE) * accuracy + STREAK_SHARE * streak))
    count = {k: sum(1 for _, r in rows if r == k) for k in ("perfect", "good", "miss", "avoided", "struck")}
    return round(score, 4), {**count, "strays": strays, "best_run": best, "targets": len(rows),
                             "accuracy": round(min(1.0, accuracy), 4)}


@dataclass
class Drill:
    player: dict
    tech: dict
    drill: dict
    tier: int
    conditions: list
    event: str | None
    prompts: list
    w: dict
    made: float
    go_at: float | None = None
    result: dict | None = None
    look: dict | None = None
    gone: bool = False

    @property
    def length(self):
        return duration(self.prompts, self.w)


class Hall:
    """The drills under way, one per player."""

    READY_SECONDS = 15 * 60          # set up but never begun
    LATE_SECONDS = 180               # begun, and the result not sent this long after it ended

    def __init__(self, clock=time.time, rng=None):
        self.clock = clock
        self.rng = rng or random.Random()
        self.lock = threading.RLock()
        self.drills = {}

    def tick(self):
        now = self.clock()
        for uid, d in list(self.drills.items()):
            if d.result is not None:
                continue
            if (d.go_at is None and now - d.made > self.READY_SECONDS) or \
                    (d.go_at is not None and now - d.go_at > d.length / 1000 + self.LATE_SECONDS):
                del self.drills[uid]                 # walked away: nothing earned, the rest stays

    def busy(self, uid):
        d = self.drills.get(uid)
        return d is not None and d.result is None

    def start(self, conn, uid, tech_id):
        """Set up a drill of technique `tech_id`. Returns None, or why not."""
        with self.lock:
            self.tick()
            now = self.clock()
            p = db.get_player(conn, uid)
            if p is None:
                return "You have no character yet."
            tech = db.get_technique(conn, uid, tech_id) if tech_id is not None else None
            if not tech:
                return "You don't know that technique."
            if players.bar_full(tech):
                nxt = technique.MASTERY_STAGES[players.stage_of(tech) + 1]["name"]
                return f"{tech['name']}'s mastery bar is full. Pass its trial with the Martial Master to reach {nxt}."
            if self.busy(uid):
                return "You are already practising."
            wait = db.cooldown_left(conn, uid, "practice", now)
            if wait:
                return f"Your hands need rest. Practise again in {players.fmt_duration(wait)}."
            tier, conds, event = roll(tech, self.rng)
            drill = drill_of(tech)
            prompts, w = pattern(drill, tier, conds, event, self.rng)
            # the rest starts now, as on Discord (bot/client.claim_session): set up and walked away from, it still holds
            db.set_cooldown(conn, uid, "practice", trainer.cooldown_seconds(p, now, "practice"), now)
            self.drills[uid] = Drill(p, tech, drill, tier, conds, event, prompts, w, now, look=looks.of_player(p))
            return None

    def go(self, uid):
        """The drill begins now (the page has counted down). Returns None, or why not."""
        with self.lock:
            self.tick()
            d = self.drills.get(uid)
            if d is None or d.result is not None:
                return "There is no drill to begin."
            if d.go_at is None:
                d.go_at = self.clock()
            return None

    def submit(self, conn, uid, inputs):
        """Grade the drill from the presses, pay it, and keep the result. Returns (result or None, why not)."""
        with self.lock:
            self.tick()
            d = self.drills.get(uid)
            if d is None:
                return None, "The drill is over."
            if d.result is not None:
                return d.result, None
            if d.go_at is None:
                return None, "The drill hasn't begun."
            now = self.clock()
            if now - d.go_at < d.length / 1000 - 2.0:
                return None, "The drill isn't over yet."
            clean = clean_inputs(inputs, d)
            if clean is None:
                return None, "Those presses can't be right."
            results, strays = grade(d.prompts, clean, d.w)
            score, detail = score_of(d.prompts, results, strays, d.conditions)
            mult, notes = 1.0, []
            ev = challenges.EVENTS
            if d.event == "wandering_hermit":
                mult *= ev["wandering_hermit"]["exp_multiplier"]
            elif d.event == "epiphany":
                mult *= 1 + ev["epiphany"]["exp_bonus"]
            rival = None
            if d.event == "rival_disciple":
                rivals = [r for p, r in zip(d.prompts, results) if p.get("rival")]
                rival = sum(1 for r in rivals if r in ("perfect", "good")) >= trainer.RIVAL_WINS_NEEDED
                if rival:
                    mult *= ev["rival_disciple"]["win_exp_multiplier"]
                    notes.append("You beat the rival disciple: EXP ×2!")
                else:
                    notes.append("The rival disciple laughs and walks off. No bonus this time.")
            p = db.get_player(conn, uid)
            session = {"technique_id": d.tech["id"], "conditions": d.conditions,
                       "challenge": p.get("last_challenge")}          # the bot's challenge memory is left as it was
            gained, daily, note, tech = trainer.finish_practice(conn, uid, session, score, mult, now, self.rng)
            if note:
                notes += [plain(line) for line in note.splitlines() if line.strip()]
            if score < challenges.LOW_SCORE_THRESHOLD:
                notes.append(f"Under {challenges.LOW_SCORE_THRESHOLD:.0%}, a drill earns only "
                             f"{challenges.LOW_SCORE_EXP_RATE:.0%} of its EXP.")
            if daily < 1:
                notes.append(f"You have practised a lot today: EXP ×{daily:g}.")
            cap = players.mastery_cap(tech)
            verdict = "great" if score >= 0.85 else "good" if score >= 0.7 else "poor" if score >= 0.5 else "bad"
            d.result = {"score": score, **detail, "results": results, "gained": gained, "daily": daily,
                        "notes": notes, "rival": rival, "verdict": verdict, "line": LINES[verdict],
                        "approve": score >= 0.7,
                        "bar": {"exp": tech["mastery_exp"], "cap": cap, "before": tech["mastery_exp"] - gained,
                                "stage": technique.MASTERY_STAGES[players.stage_of(tech)]["name"],
                                "full": players.bar_full(tech)},
                        "again": players.fmt_duration(trainer.cooldown_seconds(p, now, "practice"))}
            return d.result, None

    def give_up(self, uid):
        with self.lock:
            d = self.drills.get(uid)
            if d is not None and d.result is None:
                del self.drills[uid]                 # nothing earned; the rest stays, as on Discord

    def done(self, uid):
        with self.lock:
            d = self.drills.get(uid)
            if d is not None and d.result is not None:
                del self.drills[uid]

    # ── what the pages show ──────────────────────────────────────────────────

    def state(self, uid):
        """The drill as the page plays it, or None."""
        with self.lock:
            self.tick()
            d = self.drills.get(uid)
            if d is None:
                return None
            t = d.tech
            look = d.look
            gender = looks.gender_of(look)
            dr = d.drill
            sheets = {}
            motion_sheet = looks.motion_sheet(look, dr["motion"])
            if motion_sheet:
                sheets[dr["motion"]] = motion_sheet
            if looks.guard_sheet(look):
                sheets["guard"] = looks.guard_sheet(look)
            fx = technique_fx.of(t["name"], t["grade"], gender) or {}
            cap = players.mastery_cap(t)
            target = TARGETS[min(4, players.stage_of(t))] if dr["motion"] != "kick" else "post"
            tips = [MOTION_TEXT[dr["motion"]]] + ([EFFECT_TEXT[dr["effect"]]] if dr["effect"] in EFFECT_TEXT else [])
            return {
                "technique": {"id": t["id"], "name": t["name"], "grade": t["grade"], "type": t["type"],
                              "icon": _icon(t), "stage": technique.MASTERY_STAGES[players.stage_of(t)]["name"],
                              "tier": d.tier, "exp": t["mastery_exp"], "cap": cap},
                "drill": {**dr, "name": DRILL_NAMES[dr["mode"]], "tips": tips, "target": target,
                          "lanes": (STRIKE_LANES["post" if dr["motion"] == "kick" else "dummy"] if dr["mode"] == "strike"
                                    else DEFEND_LANES),
                          "art": (fx.get("art") or [None])[0], "picture": f"{ART}/{target}.webp"},
                "w": {k: d.w[k] for k in ("approach", "perfect", "good")}, "charge_lead": CHARGE_LEAD,
                "night": NIGHT_SHOW if "night_training" in d.conditions else None,
                "prompts": d.prompts, "length": d.length,
                "conditions": [{"key": c, "name": plain(trainer.CONDITION_NAMES[c]), "text": CONDITION_TEXT[c]}
                               for c in d.conditions],
                "event": {"key": d.event, "name": d.event.replace("_", " ").title(), "text": EVENT_TEXT[d.event]}
                if d.event else None,
                "me": {"name": d.player["name"], "gender": gender, "face": looks.face(look),
                       "poses": {p: looks.fighter(look, p) for p in looks.POSES}, "isheet": looks.idle_sheet(look),
                       "sheets": sheets},
                "instructor": {"name": NAME, "title": TITLE, "line": LINES["begin"][dr["mode"]],
                               "portrait": ART + "/portrait.jpg", "sheets": instructor_sheets()},
                "hall": {"picture": HALL_PICTURE, "sound": HALL_SOUND},
                "begun": d.go_at is not None, "result": d.result,
            }

    def hall(self, conn, uid):
        """Practice's part of the training yard: the rest, today's sessions, each technique's drill."""
        with self.lock:
            self.tick()
            now = self.clock()
            p = db.get_player(conn, uid)
            if p is None:
                return None
            wait = db.cooldown_left(conn, uid, "practice", now)
            today = db.daily_count(conn, uid, "practice", now)
            full = technique.PRACTICE_DAILY_RATES[0][0]
            drills = {}
            for t in db.get_techniques(conn, uid):
                dr = drill_of(t)
                drills[t["id"]] = {"mode": dr["mode"], "name": DRILL_NAMES[dr["mode"]],
                                   "icon": "/art/practice/icon_strike.webp" if dr["mode"] == "strike" else
                                   ("/art/practice/icon_breath.webp" if dr["motion"] == "brace" else
                                    "/art/practice/icon_defend.webp")}
            return {"wait": players.fmt_duration(wait) if wait else None, "today": today,
                    "full_left": max(0, full - today),
                    "rate": players.daily_rate(technique.PRACTICE_DAILY_RATES, today),
                    "rest": players.fmt_duration(trainer.cooldown_seconds(p, now, "practice")),
                    "base": technique.PRACTICE_BASE_EXP, "drills": drills, "busy": self.busy(uid),
                    "name": NAME, "title": TITLE}


def clean_inputs(inputs, d):
    """The page's presses, checked: a list of [t, lane, 'd' | 'u'] within the drill. None when they can't be right."""
    if not isinstance(inputs, list) or len(inputs) > 6 * len(d.prompts) + 60:
        return None
    lanes = d.drill["mode"] == "strike" and STRIKE_LANES["post" if d.drill["motion"] == "kick" else "dummy"] \
        or DEFEND_LANES
    out = []
    for row in inputs:
        try:
            t, lane, kind = float(row[0]), int(row[1]), str(row[2])
        except (TypeError, ValueError, IndexError):
            return None
        if kind not in ("d", "u") or not 0 <= lane < lanes or not -500 <= t <= d.length + 3000:
            return None
        out.append((t, lane, kind))
    return out


def _icon(t):
    from bot.sheet.data import tech_kind
    from .profile import art_url
    return art_url(tech_kind(t["name"], players.TECH_BY_NAME.get(t["name"], {}).get("school", "Body"))) or \
        f"/art/icons/actions/{t['type']}_tech.webp"
