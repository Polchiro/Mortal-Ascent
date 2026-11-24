"""
Train on the website: Meridian Circulation (docs/training.md "Train on the website").

WEBSITE ONLY (SHOAIB, Nov 25): Discord's /train keeps its challenges. Here a session is a ~2-minute meditation of
three circulation cycles. Pulses of Qi flow along your meridians: gold Qi must reach the Dantian, dark turbid Qi must
leave through an exit (a palm or a sole). You steer with junctions (turn them), gates (close them to hold Qi back)
and your breath (hold it to slow all Qi to 40%).

What it pays is the bot's own: the score goes to bot/trainer.finish (4 hours of your Qi rate × score, +15% per
condition, the event, 10% under 50%, breakthroughs, Spirit Dew, the quest count, the 60-minute rest). The rest starts
when the session is set up, as on Discord's claim_session. Tier, conditions and event are rolled from the bot's
tables (challenges.py).

The server referees, as for Practice (web/practice_play.py): it makes the map and every pulse from a seed (make_plan),
keeps the time the session began, and when the page sends what you did ([t ms, what, which]) it replays the whole
session through web/train_sim.py (the page runs the same rules in web/static/train_sim.js) and scores it itself.

PROTOTYPE (PR 1): tiers 1 and 2 only; a higher tier plays tier 2's network for now (its reward is the same formula).
The map is drawn in code over the Practice hall. Train has no teacher (SHOAIB, Nov 25): your own character is the
whole scene, and a good session ends in a celebration of its own.
"""
import json
import os
import random
import threading
import time
from dataclasses import dataclass

import challenges
import looks
import training

from bot import db, trainer
from bot import player as players

from . import train_sim as sim
from .practice_play import plain

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = "/art/train"                           # cut from SHOAIB's pictures and videos by scripts/make_train_art.py
FX = ["dantian", "dantian_upper", "seal", "lotus", "knot", "bloom", "crack", "scatter"]
# where the cushion is in each background picture: its middle (fractions of the picture) and its width. The page
# seats your character there
SEATS = {"chamber": (0.549, 0.634, 0.156), "hermit": (0.502, 0.722, 0.14)}
BUILT_TIERS = 2                              # PROTOTYPE: tiers 3-5 come in PR 2

TICK = sim.TICK
SPEED = 60                                   # units a tick (a line's length is its distance × 100): 12 body-widths/s
RAIN_SPEED = 75                              # Heavy Rain: Qi flows 25% faster
# Breath (Space): 4 s of slowing when full; refills in 5 s once let go. Old Injury: drains twice as fast
BREATH = {"max": 400, "drain": 5, "refill": 4}
# Gates (approved): a closed gate bursts after 4 s of holding Qi, or with 3 pulses waiting at it
GATE = {"hold": 4000 // TICK, "most": 3, "gap": 480}
PAUSE = 2500 // TICK                         # between cycles: the Dantian compresses, the map shifts
SETTLE = 3000                                # ms before the first pulse: the map glows in, nothing moves yet
CYCLES = 3
# Per tier: pulses a cycle (approved), the gap between pulses (ticks; the first cycle is calmer), dark Qi's share
TIERS = {1: {"pulses": 10, "gap": (60, 54), "dark": 0.3},
         2: {"pulses": 12, "gap": (52, 46), "dark": 0.3}}
CLOSE_SHARE, CLOSE_GAP = 0.25, 16                     # after the first cycle, 1 pulse in 4 follows close behind
RIVAL_PULSES, RIVAL_WINS, RIVAL_GAP = 6, 4, 34       # the Rival Disciple's round (approved: expel 4 of 6)
NIGHT_SHOW = 0.4                                     # Night Training: colours show for the last 40% of a trip
DRUNK_LIE = 0.25                                     # Drunken Master: the preview is wrong 1 time in 4
HARMONY = 10                                         # every 10 clean pulses in a row: a Qi Resonance (Breath full)
CHOOSE = 10000 // TICK                               # a blessing must be taken within 10 s (else the first is)
BOON_TEXT = {"breath": ("Deep Breath", "Your Breath lasts 50% longer, and fills now."),
             "steady": ("Steady Flow", "All Qi flows 15% slower."),
             "mend": ("Mending", "Regain 25 Stability now."),
             "seal": ("Strong Seals", "Gates burst only with 5 waiting, or after 6 seconds.")}
MAX_SECONDS = 260
CONDITIONS = ["heavy_rain", "night_training", "drunken_master", "old_injury"]
CONDITION_TEXT = {"heavy_rain": "Qi flows 25% faster",
                  "night_training": "a pulse shows its colour only near the end of its trip; the preview is dark",
                  "drunken_master": "the preview is wrong 1 time in 4 (the pulse itself never lies)",
                  "old_injury": "one limb's meridian is injured (Qi crawls through it) and your breath runs out twice as fast"}
EVENT_TEXT = {"wandering_hermit": "A Wandering Hermit watches: the hardest network, two conditions, Qi ×5.",
              "epiphany": "Epiphany! Everything flows today: Qi +50%.",
              "rival_disciple": "A rival disciple waits. After the third cycle they push 6 dark pulses into you: "
                                f"expel {RIVAL_WINS} for Qi ×2."}
# The guide (train.html "How to play"): every number in it comes from here, the bot's tables or the rules, so it
# can't drift from the game. What each tier adds (tiers 3-5 are described as they are designed; they play tier 2's
# network until they are built, BUILT_TIERS).
TIER_GUIDE = {1: ("Mortal, Apprentice, Warrior", "One flow from the crown, 2 junctions, 1 gate, 10 pulses a cycle. "
                  "Learn to steer. The first cycle is all gold; dark Qi joins from the second."),
              2: ("Expert, Master", "A second flow starts from a palm: 3-4 junctions, 2 gates, 12 pulses a cycle. From "
                  "the second cycle a knot blocks one line into the Dantian, so send the gold round it."),
              3: ("Grandmaster, Lord", "Both palms flow: 5 junctions, 14 pulses. Cracked lines leak, and one stretch "
                  "reverses its flow every 8 seconds."),
              4: ("King, Emperor", "Crown, palms and a sole: 6 junctions, 3 gates with limited uses, 15 pulses. Two "
                  "pulses that meet merge into a surge that needs a clear path."),
              5: ("Ancestor, Saint", "All five points, 7-8 junctions, 16 pulses. Blue spirit Qi must rise to the brow "
                  "(the upper Dantian) while gold sinks to the belly.")}
CONDITION_GUIDE = {"heavy_rain": "Qi flows 25% faster. Set junctions earlier than you think.",
                   "night_training": "Pulses are grey until the last 40% of their trip, and the Next strip is dark. "
                                     "Watch each pulse, not the strip.",
                   "drunken_master": "The Next strip is wrong 1 time in 4. The pulse itself always shows its true "
                                     "colour: trust the pulse.",
                   "old_injury": "One limb's channel is injured (red dashes): Qi crawls through it at 60% speed, and "
                                 "your Breath runs out twice as fast."}
EVENT_GUIDE = {"wandering_hermit": "The session moves to a mountain peak: the hardest network with two conditions. "
                                   "Qi ×5.",
               "epiphany": "Everything you gather today sticks: +50% Qi. Nothing changes in how you play.",
               "rival_disciple": f"After the third cycle a rival pushes {RIVAL_PULSES} dark pulses into you. Expel "
                                 f"{RIVAL_WINS} or more for Qi ×2. It doesn't change your score."}


def guide(tier):
    """Everything the "How to play" guide shows, from the game's own numbers."""
    ev = challenges.EVENTS
    lo_hi = {t: challenges.CONDITIONS_PER_TIER[t] for t in TIER_GUIDE}
    stab = sim.STABILITY
    return {
        "tier": tier, "built": BUILT_TIERS,
        "tiers": [{"n": t, "realms": r, "text": x, "built": t <= BUILT_TIERS,
                   "conds": "none" if lo_hi[t] == (0, 0) else f"{lo_hi[t][0]}-{lo_hi[t][1]}" if lo_hi[t][0] != lo_hi[t][1]
                   else str(lo_hi[t][0])} for t, (r, x) in TIER_GUIDE.items()],
        "conditions": [{"name": plain(trainer.CONDITION_NAMES[c]), "text": CONDITION_GUIDE[c]} for c in CONDITIONS],
        "condition_bonus": round(challenges.CONDITION_EXP_BONUS * 100),
        "events": [{"name": k.replace("_", " ").title(), "chance": round(ev[k]["chance"] * 100), "text": EVENT_GUIDE[k]}
                   for k in ("wandering_hermit", "epiphany", "rival_disciple")],
        "boons": [{"name": n, "text": t} for n, t in BOON_TEXT.values()],
        "harmony": HARMONY, "choose": CHOOSE * TICK // 1000,
        "stability": {"gold_lost": -stab["gold_lost"], "dark_in": -stab["dark_in"], "burst": -stab["burst"],
                      "clean": stab["clean"]},
        "gate": {"most": GATE["most"], "hold": GATE["hold"] * TICK // 1000},
        "breath": {"secs": BREATH["max"] // BREATH["drain"] * TICK / 1000,
                   "refill": BREATH["max"] // BREATH["refill"] * TICK / 1000},
        "hours": training.TRAIN_REWARD_HOURS, "rest": training.TRAIN_COOLDOWN_MINUTES,
        "low": round(challenges.LOW_SCORE_THRESHOLD * 100), "low_rate": round(challenges.LOW_SCORE_EXP_RATE * 100),
    }


HINTS = ["Turn the junction so the gold goes down to the Dantian.",
         "Dark Qi out through a palm!",
         "Hold Space (or Breathe) to slow everything down."]
# what the scroll says (no teacher: the verdict is the meditation's own)
LINES = {"begin": "Close your eyes. Follow the light inward. Gold to the centre, darkness out.",
         "great": "Your meridians are clear as spring water. Well done.",
         "good": "The Qi listened to you, mostly. Again, more calmly.",
         "poor": "The Qi drifts. You chased it instead of guiding it.",
         "bad": "The Qi scatters. Breathe first, then steer.",
         "deviation": "Qi deviation! Stop. Breathe. We start again another day."}

# ── the body's map: an acupuncture chart over the seated figure (a 100 × 100 box round it, facing you) ──────────
# id: (x, y, type). Left and right are YOUR left and right as you look at the figure; a session may mirror them.
# The points sit where the figure's own acupoints are: the crown (Baihui), the throat, the heart (Tanzhong), the
# Dantian below the navel, the palms resting on the knees (Laogong) and the soles tucked under the shins (Yongquan).
BODY = {
    "crown": (50, 4, "source"), "throat": (50, 25, "junction"), "heart": (50, 41, "junction"),
    "dantian": (50, 61, "dantian"),
    "l_shoulder": (35, 30, "path"), "l_elbow": (27, 49, "path"), "l_palm": (22, 72, "exit"),
    "r_shoulder": (65, 30, "path"), "r_elbow": (73, 49, "path"), "r_palm": (78, 72, "exit"),
    "l_hip": (39, 69, "path"), "r_hip": (61, 69, "path"), "l_sole": (35, 86, "exit"), "r_sole": (65, 86, "exit"),
}
# The channels curve with the body: the points between two acupoints, in order (a line not listed runs straight).
# A line the other way round (the palm up to the elbow) follows the same points backwards.
ROUTES = {
    ("crown", "throat"): [(50, 11), (50, 18)],
    ("throat", "heart"): [(50, 33)],
    ("heart", "dantian"): [(50, 48), (50, 55)],
    ("throat", "l_shoulder"): [(45, 26.5), (40, 27.5)],
    ("throat", "r_shoulder"): [(55, 26.5), (60, 27.5)],
    ("heart", "r_shoulder"): [(56, 39), (61, 35)],
    ("l_shoulder", "l_elbow"): [(31, 35), (28.5, 42)],
    ("l_elbow", "l_palm"): [(25.5, 56), (23.5, 64)],
    ("r_shoulder", "r_elbow"): [(69, 35), (71.5, 42)],
    ("r_elbow", "r_palm"): [(74.5, 56), (76.5, 64)],
    ("heart", "r_hip"): [(55, 47), (59, 54), (61, 62)],
    ("r_hip", "r_sole"): [(63, 75), (64.5, 81)],
    ("r_hip", "dantian"): [(57, 66), (54, 63)],
    ("l_elbow", "l_hip"): [(30.5, 57), (34.5, 64)],
    ("l_elbow", "l_sole"): [(28, 58), (30, 67), (32.5, 77)],
    ("l_hip", "dantian"): [(43, 66), (46.5, 63)],
}
LIMBS = {"left arm": ["l_shoulder", "l_elbow", "l_palm"], "right arm": ["r_shoulder", "r_elbow", "r_palm"],
         "left leg": ["l_hip", "l_sole"], "right leg": ["r_hip", "r_sole"]}


def route(a, b):
    """The whole channel from acupoint a to b: [(x, y), ...] from a's point to b's."""
    if (a, b) in ROUTES:
        mid = ROUTES[(a, b)]
    else:
        mid = list(reversed(ROUTES.get((b, a), [])))
    return [BODY[a][:2]] + list(mid) + [BODY[b][:2]]


def _middle(a, b, at=0.5):
    """Where a gate or knot `at` of the way along channel a→b sits: (segment index, its point)."""
    pts = route(a, b)
    k = min(len(pts) - 2, int((len(pts) - 1) * at))
    (x1, y1), (x2, y2) = pts[k], pts[k + 1]
    return k, ((x1 + x2) / 2, (y1 + y2) / 2)


def _network(tier, cycle):
    """The network for one cycle: {id: [type, [outs]]} (positions come from BODY, mirrored or not).

    Tier 1: the crown alone. The throat sends Qi down to the heart or out along the left arm; the heart sends it on
    to the Dantian or out along the right arm. One gate.
    Tier 2: the crown and the left palm (a second flow). The palm's Qi climbs to the elbow, which sends it in by the
    hip or down to the sole; from the second cycle the right hip is a fourth junction (Dantian or sole), and a knot
    blocks one of the two lines into the Dantian, so its Qi must go round. Two gates."""
    net = {"crown": ["source", ["throat"]], "throat": ["junction", ["heart", "l_shoulder"]],
           "heart": ["junction", ["dantian", "r_shoulder"]], "dantian": ["dantian", []],
           "l_shoulder": ["path", ["l_elbow"]], "l_elbow": ["path", ["l_palm"]], "l_palm": ["exit", []],
           "r_shoulder": ["path", ["r_elbow"]], "r_elbow": ["path", ["r_palm"]], "r_palm": ["exit", []]}
    if tier >= 2:
        net["throat"] = ["junction", ["heart", "r_shoulder"]]
        net["heart"] = ["junction", ["dantian", "r_hip"]]
        net["r_hip"] = ["junction", ["r_sole", "dantian"]] if cycle >= 1 else ["path", ["r_sole"]]
        net["r_sole"] = ["exit", []]
        net["l_palm"] = ["source", ["l_elbow"]]
        net["l_elbow"] = ["junction", ["l_hip", "l_sole"]]
        net["l_hip"] = ["path", ["dantian"]]
        net["l_sole"] = ["exit", []]
        for n in ("l_shoulder",):
            net.pop(n)
    return net


def _channels(net, pos, mirror):
    """Turn each line a→b of the network into its curved channel: plain path points ("a~b~0", ...) between the two
    acupoints. Returns {(a, b): [a, the points..., b]}. Qi passes the path points without stopping."""
    chains = {}
    for a in list(net):
        kind, outs = net[a]
        new = []
        for b in outs:
            pts = route(a, b)[1:-1]
            ids = [f"{a}~{b}~{i}" for i in range(len(pts))]
            for i, (x, y) in enumerate(pts):
                net[ids[i]] = ["path", [ids[i + 1] if i + 1 < len(ids) else b]]
                pos[ids[i]] = (round(100 - x if mirror else x, 2), y)
            new.append(ids[0] if ids else b)
            chains[(a, b)] = [a] + ids + [b]
        net[a] = [kind, new]
    return chains


def _split(net, pos, a, b, nid, kind, at):
    """Put a gate or a knot on the line a→b, `at` of the way along."""
    net[a][1] = [nid if o == b else o for o in net[a][1]]
    net[nid] = [kind, [b]]
    (xa, ya), (xb, yb) = pos[a], pos[b]
    pos[nid] = (round(xa + (xb - xa) * at, 2), round(ya + (yb - ya) * at, 2))


GATE_APART = 14                              # body units between two gates' middles, at least


def _apart(lines):
    mids = [_middle(a, b)[1] for a, b in lines]
    return all(((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5 >= GATE_APART
               for i, (x1, y1) in enumerate(mids) for (x2, y2) in mids[i + 1:])


def reaches(nodes, start, goal_types):
    """Can Qi from `start` reach a node of one of `goal_types` along some way (junctions set either way)?"""
    seen, todo = set(), [start]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        if nodes[n]["type"] in goal_types:
            return True
        if nodes[n]["type"] != "knot":
            todo += nodes[n]["out"]
    return False


def make_plan(tier, conditions, event, rng):
    """The whole session from a random generator: every cycle's network and every pulse, and the rules' numbers."""
    play = min(tier, BUILT_TIERS)
    T = TIERS[play]
    mirror = rng.random() < 0.5
    # gates sit only on channels long enough to tap them clear of the junctions and the Dantian, even on a phone
    gate_lines = {1: [("crown", "throat"), ("l_shoulder", "l_elbow"), ("r_shoulder", "r_elbow")],
                  2: [("crown", "throat"), ("l_palm", "l_elbow"), ("l_elbow", "l_hip"), ("r_shoulder", "r_elbow")]}[play]
    knot_lines = [("heart", "dantian"), ("r_hip", "dantian")]
    first_knot = rng.randrange(2)
    gates_now = rng.sample(gate_lines, play)
    while not _apart(gates_now):                     # two gates never sit on top of each other
        gates_now = rng.sample(gate_lines, play)
    if play == 1:                                    # tier 1's first cycle has only gold: its gate is on the crown
        gates_now = [("crown", "throat")]
    injured = []
    hurt_limb = None
    if "old_injury" in conditions:
        hurt_limb = rng.choice(["left arm", "right arm"] if play == 1 else ["left leg", "right arm", "right leg"])
    cycles = []
    ways = {}
    pid = 0
    rounds = CYCLES + (1 if event == "rival_disciple" else 0)
    for c in range(rounds):
        rival = c == CYCLES
        net = _network(play, min(c, CYCLES - 1))
        pos = {n: (100 - BODY[n][0] if mirror else BODY[n][0], BODY[n][1]) for n in net}
        if c == 1 and not rival:                    # the map shifts: a gate moves to another line
            others = [ln for ln in gate_lines if ln not in gates_now and _apart(gates_now[1:] + [ln])]
            gates_now = gates_now[1:] + [rng.choice(others)] if others else gates_now
        chains = _channels(net, pos, mirror)           # every line becomes its curved channel
        for i, (a, b) in enumerate(gates_now):
            if (a, b) in chains:
                k = _middle(a, b)[0]
                _split(net, pos, chains[(a, b)][k], chains[(a, b)][k + 1], f"gate{i + 1}", "gate", 0.5)
        if play >= 2 and c >= 1:                    # tier 2: a knot from the second cycle, moving in the third
            a, b = knot_lines[(first_knot + (1 if c >= 2 else 0)) % 2]
            if (a, b) in chains:
                k = _middle(a, b, 0.6)[0]
                _split(net, pos, chains[(a, b)][k], chains[(a, b)][k + 1], "knot", "knot", 0.5)
        nodes = {}
        for n, (kind, out) in net.items():
            x, y = pos[n]
            nodes[n] = {"x": x, "y": y, "type": kind, "out": list(out)}
            if kind == "junction":
                ways.setdefault(n, rng.randrange(2))     # which way it starts (a junction met again keeps its own)
                nodes[n]["way"] = ways[n]
        lens = {}
        for n, node in nodes.items():
            for o in node["out"]:
                (x1, y1), (x2, y2) = pos[n], pos[o]
                lens[sim.edge(n, o)] = max(100, round(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 * 100))
        if hurt_limb:
            limb = LIMBS[hurt_limb]
            injured = sorted({k for k in lens if any(part.split("~")[0] in limb or (len(part.split("~")) == 3 and (
                part.split("~")[0] in limb or part.split("~")[1] in limb)) for part in k.split(">"))})
        sources = sorted(n for n in nodes if nodes[n]["type"] == "source")
        pulses = []
        if rival:
            count, gap, dark_share, at = RIVAL_PULSES, RIVAL_GAP, 1.0, 20
        else:
            count, gap, dark_share, at = T["pulses"], T["gap"][0 if c == 0 else 1], T["dark"], 0
            if play == 1 and c == 0:
                dark_share = 0.0                     # tier 1: no dark Qi in the first cycle
        darks = set(rng.sample(range(count), round(count * dark_share))) if dark_share < 1 else set(range(count))
        for i in range(count):
            src = sources[0] if len(sources) == 1 else rng.choice(sources)
            pulses.append({"id": pid, "at": at, "src": src, "dark": i in darks})
            pid += 1
            close = c > 0 and not rival and rng.random() < CLOSE_SHARE
            at += CLOSE_GAP if close else gap + rng.randrange(-6, 7)
        cycles.append({"kind": "rival" if rival else "cycle", "nodes": nodes, "lens": lens, "pulses": pulses})
    boons = [rng.sample(sim.BOONS, 2) for _ in range(CYCLES - 1)]          # the two to choose from, after cycles 1, 2
    plan = {"tick": TICK, "speed": RAIN_SPEED if "heavy_rain" in conditions else SPEED,
            "harmony": HARMONY, "choose": CHOOSE, "boons": boons,
            "breath": dict(BREATH, drain=BREATH["drain"] * (2 if "old_injury" in conditions else 1)),
            "gate": dict(GATE), "pause": PAUSE, "max_ticks": (MAX_SECONDS * 1000 - SETTLE) // TICK,
            "injured": injured, "tier": play, "cycles": cycles}
    # what the page shows ahead of each pulse (Drunken Master: wrong 1 time in 4)
    lies = set()
    if "drunken_master" in conditions:
        for c in cycles:
            for q in c["pulses"]:
                if rng.random() < DRUNK_LIE:
                    lies.add(q["id"])
    plan["shown"] = {str(q["id"]): (not q["dark"]) if q["id"] in lies else q["dark"]
                     for c in cycles for q in c["pulses"]}
    return plan


def _there(url):
    return url if os.path.exists(os.path.join(ROOT, url.lstrip("/"))) else None


_heroes = {}


def hero_art(gender):
    """Your character meditating (art/train/hero/<gender>/sheets.json): the loop's sprite sheet, the three endings'
    videos with their sounds, and `fit`, where the body's acupoints are. None until the art is cut: then the page
    draws a plain seated figure."""
    if gender not in _heroes:
        try:
            with open(os.path.join(ROOT, "art", "train", "hero", gender, "sheets.json")) as fh:
                data = json.load(fh)
            _heroes[gender] = data if data.get("loop") and data.get("fit") else None
        except (OSError, ValueError):
            _heroes[gender] = None
    return _heroes[gender]


def scene_art(event=None):
    """The place: the meditation chamber (a looping video, its sound the room's own), or the Hermit's peak when a
    Wandering Hermit watches; the Practice hall stands in if neither is there."""
    place = "hermit" if event == "wandering_hermit" and _there(ART + "/hermit.jpg") else "chamber"
    picture = _there(f"{ART}/{place}.jpg")
    if not picture:
        return {"picture": "/art/practice/hall.jpg", "video": None, "sound": None, "seat": None}
    x, y, w = SEATS[place]
    return {"picture": picture, "video": _there(ART + "/chamber.mp4") if place == "chamber" else None,
            "sound": _there(ART + "/chamber.wav"), "seat": {"x": x, "y": y, "w": w}}


def fx_art():
    return {name: _there(f"{ART}/fx/{name}.webp") for name in FX}


def roll(player, rng):
    """The session's tier (by realm), conditions and event, from the bot's tables (bot/trainer.roll_session's rolls)."""
    tier = challenges.REALM_TIER[player["realm"]]
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
    return tier, rng.sample(CONDITIONS, min(n, len(CONDITIONS))), event


def length_ms(plan):
    """How long the session runs with no actions at all: the shortest it can be (breath and gates only add time)."""
    st = sim.run(plan, [])
    return SETTLE + (st["end_tick"] + 1) * TICK


@dataclass
class Session:
    player: dict
    tier: int
    conditions: list
    event: str | None
    plan: dict
    made: float
    go_at: float | None = None
    result: dict | None = None
    look: dict | None = None


class Chamber:
    """The meditations under way, one per player."""

    READY_SECONDS = 15 * 60          # set up but never begun
    LATE_SECONDS = 180               # begun, and the result not sent this long after the longest it can run

    def __init__(self, clock=time.time, rng=None):
        self.clock = clock
        self.rng = rng or random.Random()
        self.lock = threading.RLock()
        self.sessions = {}

    def tick(self):
        now = self.clock()
        for uid, s in list(self.sessions.items()):
            if s.result is not None:
                continue
            if (s.go_at is None and now - s.made > self.READY_SECONDS) or \
                    (s.go_at is not None and now - s.go_at > MAX_SECONDS + self.LATE_SECONDS):
                del self.sessions[uid]               # walked away: nothing earned, the rest stays

    def busy(self, uid):
        s = self.sessions.get(uid)
        return s is not None and s.result is None

    def start(self, conn, uid):
        """Set up a meditation. Returns None, or why not."""
        with self.lock:
            self.tick()
            now = self.clock()
            p = db.get_player(conn, uid)
            if p is None:
                return "You have no character yet."
            if self.busy(uid):
                return "You are already meditating."
            wait = db.cooldown_left(conn, uid, "train", now)
            if wait:
                return f"Your meridians need rest. Train again in {players.fmt_duration(wait)}."
            tier, conds, event = roll(p, self.rng)
            plan = make_plan(tier, conds, event, random.Random(self.rng.getrandbits(64)))
            # the rest starts now, as on Discord (bot/client.claim_session): set up and walked away from, it holds
            db.set_cooldown(conn, uid, "train", trainer.cooldown_seconds(p, now), now)
            self.sessions[uid] = Session(p, tier, conds, event, plan, now, look=looks.of_player(p))
            return None

    def go(self, uid):
        with self.lock:
            self.tick()
            s = self.sessions.get(uid)
            if s is None or s.result is not None:
                return "There is no meditation to begin."
            if s.go_at is None:
                s.go_at = self.clock()
            return None

    def submit(self, conn, uid, actions):
        """Replay the session from the actions, pay it, keep the result. Returns (result or None, why not)."""
        with self.lock:
            self.tick()
            s = self.sessions.get(uid)
            if s is None:
                return None, "The meditation is over."
            if s.result is not None:
                return s.result, None
            if s.go_at is None:
                return None, "The meditation hasn't begun."
            clean = clean_actions(actions, s.plan)
            if clean is None:
                return None, "Those actions can't be right."
            st = sim.run(s.plan, clean)
            now = self.clock()
            if now - s.go_at < (SETTLE + (st["end_tick"] + 1) * TICK) / 1000 - 2.0:
                return None, "The meditation isn't over yet."
            score, parts = sim.score(s.plan, st)
            mult, notes = 1.0, []
            ev = challenges.EVENTS
            if s.event == "wandering_hermit":
                mult *= ev["wandering_hermit"]["exp_multiplier"]
            elif s.event == "epiphany":
                mult *= 1 + ev["epiphany"]["exp_bonus"]
            rival = None
            if s.event == "rival_disciple" and not st["deviation"]:
                rival = st["rival_out"] >= RIVAL_WINS
                if rival:
                    mult *= ev["rival_disciple"]["win_exp_multiplier"]
                    notes.append(f"You expelled {st['rival_out']} of the rival's {RIVAL_PULSES} dark pulses: Qi ×2!")
                else:
                    notes.append(f"You expelled {st['rival_out']} of the rival's {RIVAL_PULSES}. "
                                 "The rival smirks and leaves. No bonus this time.")
            p = db.get_player(conn, uid)
            before = {"realm": p["realm"], "layer": p["layer"], "qi": p["qi"]}
            session = {"conditions": s.conditions, "challenge": p.get("last_challenge")}  # the bot's memory stays
            qi, events, p = trainer.finish(conn, uid, session, score, mult, self.rng, now)
            notes += [plain(line) for line in events if line and line.strip()]
            if score < challenges.LOW_SCORE_THRESHOLD:
                notes.append(f"Under {challenges.LOW_SCORE_THRESHOLD:.0%}, a session earns only "
                             f"{challenges.LOW_SCORE_EXP_RATE:.0%} of its Qi.")
            verdict = "deviation" if st["deviation"] else \
                "great" if score >= 0.85 else "good" if score >= 0.7 else "poor" if score >= 0.5 else "bad"
            need = players.qi_needed(p["realm"], p["layer"])
            if st["resonances"]:
                notes.append(f"Harmony: {st['best_harmony']} clean pulses in a row at best, "
                             f"{st['resonances']} Qi Resonance{'' if st['resonances'] == 1 else 's'}.")
            s.result = {"score": score, **parts, "boon_names": [BOON_TEXT[b][0] for b in st["boons"]], "gained": round(qi, 1), "notes": notes, "rival": rival,
                        "rival_out": st["rival_out"], "verdict": verdict, "line": LINES[verdict],
                        "approve": score >= 0.7 and not st["deviation"],
                        "bar": {"qi": round(p["qi"], 1), "need": need,
                                "before": round(before["qi"], 1) if (before["realm"], before["layer"]) ==
                                (p["realm"], p["layer"]) else 0,
                                "where": f"{p['realm']}, {players.ordinal(p['layer'])} Layer"},
                        "again": players.fmt_duration(trainer.cooldown_seconds(p, now))}
            return s.result, None

    def give_up(self, uid):
        with self.lock:
            s = self.sessions.get(uid)
            if s is not None and s.result is None:
                del self.sessions[uid]               # nothing earned; the rest stays, as on Discord

    def done(self, uid):
        with self.lock:
            s = self.sessions.get(uid)
            if s is not None and s.result is not None:
                del self.sessions[uid]

    # ── what the pages show ──────────────────────────────────────────────────

    def state(self, uid):
        with self.lock:
            self.tick()
            s = self.sessions.get(uid)
            if s is None:
                return None
            look = s.look
            gold, dark = sim.totals(s.plan)
            return {
                "tier": s.tier, "plays": s.plan["tier"], "plan": s.plan, "settle": SETTLE,
                "night": NIGHT_SHOW if "night_training" in s.conditions else None,
                "drunk": "drunken_master" in s.conditions, "totals": {"gold": gold, "dark": dark},
                "boon_text": {k: {"name": n, "text": t} for k, (n, t) in BOON_TEXT.items()},
                "conditions": [{"key": c, "name": plain(trainer.CONDITION_NAMES[c]), "text": CONDITION_TEXT[c]}
                               for c in s.conditions],
                "event": {"key": s.event, "name": s.event.replace("_", " ").title(), "text": EVENT_TEXT[s.event]}
                if s.event else None,
                "hints": HINTS if s.plan["tier"] == 1 else [],
                "guide": guide(s.tier),
                "me": {"name": s.player["name"], "gender": looks.gender_of(look), "face": looks.face(look)},
                "begin": LINES["begin"],
                "chamber": scene_art(s.event), "hero": hero_art(looks.gender_of(look)), "fx": fx_art(),
                "rival": _there(ART + "/rival.webp"),
                "body": {n: [x, y] for n, (x, y, _) in BODY.items()},
                "begun": s.go_at is not None, "result": s.result,
            }

    def hall(self, conn, uid):
        """Train's card in the training yard: the rest, the tier."""
        with self.lock:
            self.tick()
            now = self.clock()
            p = db.get_player(conn, uid)
            if p is None:
                return None
            wait = db.cooldown_left(conn, uid, "train", now)
            tier = challenges.REALM_TIER[p["realm"]]
            return {"wait": players.fmt_duration(wait) if wait else None, "busy": self.busy(uid), "tier": tier,
                    "rest": players.fmt_duration(trainer.cooldown_seconds(p, now)), "badge": _there(ART + "/badge.webp"),
                    "prototype": tier > BUILT_TIERS}


def clean_actions(actions, plan):
    """The page's actions, checked: [t ms, what, which], in time order, within the session. None when they can't
    be right."""
    if not isinstance(actions, list) or len(actions) > 1500:
        return None
    ids = set()
    for c in plan["cycles"]:
        ids |= {n for n, node in c["nodes"].items() if node["type"] in ("junction", "gate")}
    out, last = [], -1
    for row in actions:
        try:
            t, what, which = int(row[0]), str(row[1]), str(row[2])
        except (TypeError, ValueError, IndexError):
            return None
        if what not in ("j", "g", "b", "B", "o") or t < last or not 0 <= t <= MAX_SECONDS * 1000:
            return None
        if (what in ("j", "g") and which not in ids) or (what == "o" and which not in sim.BOONS):
            return None
        last = t
        out.append([t, what, which if what in ("j", "g", "o") else ""])
    return out
