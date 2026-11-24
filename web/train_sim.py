"""
Meridian Circulation's simulation (docs/training.md "Train on the website"): the one set of rules that both the page
(web/static/train_sim.js, a line-for-line copy) and the server (web/train_play.py, the referee) run.

It is step-based and uses whole numbers only, so the two copies always agree: time moves in ticks of TICK ms, each
pulse moves a whole number of units along its line each tick, and a junction's way is read the moment a pulse reaches
it. An action the player takes at t ms is applied at the start of tick t // TICK. tests/test_web_train.py runs both
copies on the same sessions to prove they agree.

The plan (made by web/train_play.make_plan from a seed) is plain JSON:
  {"tick": 50, "speed": 60, "breath": {...}, "gate": {...}, "injured": [edge keys], "rain": bool,
   "cycles": [{"kind": "cycle" | "rival", "nodes": {id: {x, y, type, out: [ids], ...}}, "lens": {"A>B": units},
               "pulses": [{"id", "at" (ticks after the cycle starts), "src", "dark"}]}, ...],
   "pause": ticks between cycles, "max_ticks": the hard end}
Node types: source, path, junction (two ways out, `out[0]` first), gate, knot (a blockage: Qi stops there and is
lost), exit (a palm or sole), dantian.

Actions: [t ms, what, which]: "j" turn junction `which`, "g" open / close gate `which`, "b" start breathing, "B" stop.
"""

TICK = 50

# Stability (approved, docs/training.md): -10 a gold pulse lost, -15 a dark pulse into the Dantian, -10 a gate burst,
# +2 a pulse delivered cleanly (gold in, dark out); Qi deviation at 0
STABILITY = {"start": 100, "gold_lost": -10, "dark_in": -15, "burst": -10, "clean": 2}


def edge(a, b):
    return a + ">" + b


def new_state(plan):
    return {"tick": 0, "cycle": 0, "cycle_start": 0, "pause_until": None, "next_id": 0,
            "pulses": [], "junctions": {}, "gates": {}, "breath": plan["breath"]["max"], "breathing": False,
            "stability": STABILITY["start"], "deviation": False, "over": False, "end_tick": None,
            "gold": 0, "gold_in": 0, "dark": 0, "dark_out": 0, "lost": 0, "dark_in": 0, "bursts": 0,
            "rival_dark": 0, "rival_out": 0, "spawned": 0, "events": []}


def cycle_of(plan, st):
    return plan["cycles"][st["cycle"]]


def _enter_cycle(plan, st, k):
    """A cycle begins at tick k: its gates open, its junctions keep the way they had if they were there before."""
    cyc = cycle_of(plan, st)
    st["cycle_start"], st["spawned"], st["pulses"] = k, 0, []
    junctions = {}
    for nid in sorted(cyc["nodes"]):
        n = cyc["nodes"][nid]
        if n["type"] == "junction":
            junctions[nid] = st["junctions"].get(nid, n.get("way", 0))
    st["junctions"] = junctions
    st["gates"] = {nid: {"open": True, "since": 0} for nid in sorted(cyc["nodes"]) if cyc["nodes"][nid]["type"] == "gate"}


def _bump(st, amount):
    st["stability"] = max(0, min(STABILITY["start"], st["stability"] + amount))
    if st["stability"] == 0:
        st["deviation"] = True


def _scored(plan, st):
    return cycle_of(plan, st)["kind"] == "cycle"


def _resolve(plan, st, p, how):
    """A pulse's trip ends: delivered, expelled, lost (knot, wrong exit, burst) or into the Dantian."""
    p["done"] = how
    scored = _scored(plan, st)
    if p["dark"]:
        if how == "out":
            if scored:
                st["dark_out"] += 1
                _bump(st, STABILITY["clean"])
            else:
                st["rival_out"] += 1
        elif how == "in" and scored:
            st["dark_in"] += 1
            _bump(st, STABILITY["dark_in"])
    else:
        if how == "in":
            if scored:
                st["gold_in"] += 1
                _bump(st, STABILITY["clean"])
        elif scored:
            st["lost"] += 1
            if how != "burst":                    # a burst costs its own -10 once, not -10 a pulse as well
                _bump(st, STABILITY["gold_lost"])
    st["events"].append([st["tick"], how, p["id"], 1 if p["dark"] else 0])


def apply(plan, st, action):
    """One of the player's actions, at the start of its tick."""
    _, what, which = action
    if what == "j" and which in st["junctions"]:
        st["junctions"][which] = 1 - st["junctions"][which]
    elif what == "g" and which in st["gates"]:
        g = st["gates"][which]
        if g["open"]:
            g["open"], g["since"] = False, st["tick"]
        else:
            _open_gate(plan, st, which)
    elif what == "b":
        if st["breath"] > 0:
            st["breathing"] = True
    elif what == "B":
        st["breathing"] = False


def _open_gate(plan, st, gid):
    """The gate opens: the pulses waiting at it go on through, one after another."""
    st["gates"][gid]["open"] = True
    waiting = [p for p in st["pulses"] if p["wait"] == gid and p["done"] is None]
    nxt = cycle_of(plan, st)["nodes"][gid]["out"][0]
    for i, p in enumerate(waiting):
        p["wait"], p["edge"], p["pos"] = None, edge(gid, nxt), -i * plan["gate"]["gap"]


def _speed(plan, st, p):
    s = plan["speed"]
    if p["edge"] in plan["injured"]:
        s = s * 3 // 5
    if st["breathing"]:
        s = s * 2 // 5
    return s


def _arrive(plan, st, p, nid):
    """A pulse reaches node `nid`. Returns True if it carries on along a new line."""
    cyc = cycle_of(plan, st)
    n = cyc["nodes"][nid]
    t = n["type"]
    if t == "dantian":
        _resolve(plan, st, p, "in")
        return False
    if t == "exit":
        _resolve(plan, st, p, "out" if p["dark"] else "wrong")
        return False
    if t == "knot":
        _resolve(plan, st, p, "knot")
        return False
    if t == "gate" and not st["gates"][nid]["open"]:
        p["wait"], p["pos"], p["waited"] = nid, 0, st["tick"]
        return False
    nxt = n["out"][st["junctions"][nid]] if t == "junction" else n["out"][0]
    p["edge"] = edge(nid, nxt)
    return True


def step(plan, st, actions=()):
    """Run tick st["tick"]: the actions that fall in it first, then the breath, new pulses, movement, gates."""
    if st["over"]:
        return st
    k = st["tick"]
    st["events"] = []
    if st["pause_until"] is not None and k >= st["pause_until"]:
        st["pause_until"] = None
        st["cycle"] += 1
        _enter_cycle(plan, st, k)
    for a in actions:
        apply(plan, st, a)
    b = plan["breath"]
    if st["breathing"]:
        st["breath"] = max(0, st["breath"] - b["drain"])
        if st["breath"] == 0:
            st["breathing"] = False
    else:
        st["breath"] = min(b["max"], st["breath"] + b["refill"])
    cyc = cycle_of(plan, st)
    if st["pause_until"] is None:
        while st["spawned"] < len(cyc["pulses"]) and cyc["pulses"][st["spawned"]]["at"] + st["cycle_start"] <= k:
            q = cyc["pulses"][st["spawned"]]
            src = cyc["nodes"][q["src"]]
            st["pulses"].append({"id": q["id"], "dark": q["dark"], "edge": edge(q["src"], src["out"][0]), "pos": 0,
                                 "wait": None, "waited": 0, "done": None})
            st["spawned"] += 1
            if cyc["kind"] == "cycle":
                st["dark" if q["dark"] else "gold"] += 1
            else:
                st["rival_dark"] += 1
    for p in st["pulses"]:
        if p["done"] is not None or p["wait"] is not None:
            continue
        p["pos"] += _speed(plan, st, p)
        while p["done"] is None and p["wait"] is None and p["pos"] >= cyc["lens"][p["edge"]]:
            p["pos"] -= cyc["lens"][p["edge"]]
            _arrive(plan, st, p, p["edge"].split(">")[1])
    g = plan["gate"]
    for gid in sorted(st["gates"]):
        gate = st["gates"][gid]
        if gate["open"]:
            continue
        waiting = [p for p in st["pulses"] if p["wait"] == gid and p["done"] is None]
        if waiting and (len(waiting) >= g["most"] or k - min(p["waited"] for p in waiting) >= g["hold"]):
            for p in waiting:
                _resolve(plan, st, p, "burst")
            st["bursts"] += 1 if _scored(plan, st) else 0
            if _scored(plan, st):
                _bump(st, STABILITY["burst"])
            st["events"].append([k, "gate_burst", gid, 0])
            gate["open"] = True
    if st["deviation"] and _scored(plan, st):
        st["over"], st["end_tick"] = True, k
        st["events"].append([k, "deviation", "", 0])
    elif st["pause_until"] is None and st["spawned"] == len(cyc["pulses"]) and \
            all(p["done"] is not None for p in st["pulses"]):
        st["events"].append([k, "cycle_done", cyc["kind"], st["cycle"]])
        if st["cycle"] + 1 < len(plan["cycles"]):
            st["pause_until"] = k + 1 + plan["pause"]
        else:
            st["over"], st["end_tick"] = True, k
    if not st["over"] and k + 1 >= plan["max_ticks"]:
        st["over"], st["end_tick"] = True, k
    st["tick"] = k + 1
    return st


def start(plan):
    st = new_state(plan)
    _enter_cycle(plan, st, 0)
    return st


def run(plan, actions):
    """Replay a whole session from the player's actions (sorted by time). Returns the final state."""
    st = start(plan)
    acts = sorted(actions, key=lambda a: a[0])
    i = 0
    while not st["over"]:
        mine = []
        while i < len(acts) and acts[i][0] // TICK <= st["tick"]:
            mine.append(acts[i])
            i += 1
        step(plan, st, mine)
    return st


def totals(plan):
    """Gold and dark pulses in the scored cycles (every one counts, sent or not: Qi deviation loses the rest)."""
    gold = dark = 0
    for c in plan["cycles"]:
        if c["kind"] == "cycle":
            for q in c["pulses"]:
                if q["dark"]:
                    dark += 1
                else:
                    gold += 1
    return gold, dark


def score(plan, st):
    """(score 0-1, parts). 60% gold delivered, 25% dark expelled, 15% Stability left; with no dark Qi at all the
    gold part takes its 25% (85% gold)."""
    gold, dark = totals(plan)
    g = st["gold_in"] / gold if gold else 1.0
    stab = 0 if st["deviation"] else st["stability"]
    if dark:
        d = st["dark_out"] / dark
        s = 0.60 * g + 0.25 * d + 0.15 * stab / 100
    else:
        d = None
        s = 0.85 * g + 0.15 * stab / 100
    return round(max(0.0, min(1.0, s)), 4), {"gold": gold, "gold_in": st["gold_in"], "dark": dark,
                                             "dark_out": st["dark_out"], "dark_in": st["dark_in"], "lost": st["lost"],
                                             "bursts": st["bursts"], "stability": stab, "deviation": st["deviation"],
                                             "gold_part": round(g, 4), "dark_part": None if d is None else round(d, 4)}
