"""
Plain data for the Alchemy Chamber card (cards/alchemy.render_alchemy), built from a running Craft.

Only reads the craft: it never changes a rule or a number. What the card shows of the hidden parts
follows the text the player sees: the fire follows the (maybe misleading) heat text, the pill glows at
the shown pulse, and the safe heat zone and the herb order are never drawn.
"""
from collections import Counter

import alchemy
import training

POSITION_SHORT = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}
MODE = {1: "ignite", 2: "herbs", 3: "fuse", 4: "condense", 5: "seal", 6: "tribulation"}
STRIKE_DIR = {"left": "left", "above": "above", "right": "right"}


def plain(s):
    """Card text without Markdown and emoji (the card fonts have no emoji)."""
    s = s.replace("**", "").replace("*", "")
    out = []
    for ch in s:
        o = ord(ch)
        if 0x2190 <= o <= 0x21FF or 0x2300 <= o <= 0x23FF or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF \
                or o >= 0x1F000 or o == 0xFE0F:
            continue
        out.append(ch)
    return " ".join("".join(out).split())


def effect_line(kind, grade):
    """'Mystic · ×1.8 Qi rate · 2 hours': the pill's base effect, before patterns."""
    if kind == "qi":
        return f"{grade} · ×{training.QI_PILLS[grade]:g} Qi rate · {training.QI_PILL_DURATION_HOURS} hours"
    if kind == "burst":
        return f"{grade} · {alchemy.QI_BURST_PILLS[grade]['hours']} hours of Qi at once"
    if kind == "mending":
        spec = alchemy.MENDING_PILLS[grade]
        injury = "cures injury" if spec["injury_minutes"] is None else f"−{spec['injury_minutes']} min injury"
        return f"{grade} · heals {spec['heal']:.0%} HP · {injury}"
    if kind == "cleansing":
        return f"{grade} · −{alchemy.CLEANSING_PILLS[grade]['toxicity_removed']} toxicity"
    return f"{grade} · +{training.BREAKTHROUGH_PILLS[grade]:.0%} breakthrough chance"


def herb_rows(herbs, core=None, core_qty=1):
    """The planned ingredients as card rows: [{name, type, age, qty}] (+ the Beast Core)."""
    rows = []
    for item, qty in herbs:
        d = item.get("data") or {}
        rows.append({"name": item["name"], "type": d.get("type", "qi"), "age": d.get("age", 10), "qty": qty})
    if core:
        rows.append({"name": core["name"], "type": "core", "age": None, "qty": core_qty})
    return rows


def _herb_states(c, rows):
    """'in' once a herb is in the cauldron, 'waiting' before; the core goes in at Seal the Core."""
    stage_i = len(c.stages) if c.done or c.tribulation else c.stage_i
    if 2 not in c.stages:
        placed = None                                   # no herb stage: everything goes in together
    elif stage_i < c.stages.index(2):
        placed = Counter()
    elif stage_i == c.stages.index(2):
        batch = getattr(c, "batch", 1)              # a batch puts in one herb of each set per decision
        placed = Counter({t: n * batch for t, n in Counter(c.order[:c.placed]).items()})
    else:
        placed = None
    out = []
    for r in rows:
        r = dict(r)
        if r["type"] == "core":
            if c.core_lost:
                r["state"] = "lost"
            else:
                sealed = 5 in c.stages and (stage_i > c.stages.index(5))
                r["state"] = "in" if sealed else "waiting"
        elif placed is None:
            r["state"] = "in"
        else:
            n = min(r["qty"], placed[r["type"]])
            placed[r["type"]] -= n
            if n == r["qty"]:
                r["state"] = "in"
            elif n:                                      # part of a stack is in: split the row
                out.append(dict(r, qty=n, state="in"))
                r.update(qty=r["qty"] - n, state="waiting")
            else:
                r["state"] = "waiting"
        out.append(r)
    return out[:4]


def _stages(c):
    out = []
    stage_i = len(c.stages) if c.tribulation else c.stage_i
    for i, s in enumerate(c.stages):
        if c.core_lost and s == 5:
            state = "failed"
        elif c.done or i < stage_i:
            state = "done"
        elif i == stage_i:
            state = "current"
        else:
            state = "todo"
        out.append({"key": s, "state": state})
    if c.tribulation:
        state = {"pending": "current", "won": "done", "lost": "failed"}[c.tribulation]
        out.append({"key": 6, "state": state})
    return out


def _patterns(c, score):
    if c.done:
        earned = c.result
    elif c.tribulation == "pending":
        earned = alchemy.TRIBULATION_FAIL_PATTERNS
    elif c.scores:
        from .crafting import patterns_for
        earned = patterns_for(score, c.max_patterns) if score >= c.explode_below else 0
    else:
        earned = 0
    return {"earned": earned, "cap": c.max_patterns, "effect": alchemy.pattern_effect(earned) if earned else 0}


def card_data(c, herbs=(), outcome=None, pill_name=None, seed=None):
    """Plain data for render_alchemy. herbs: herb_rows(); outcome (after the craft): {exp, rank_up, stored}."""
    from . import crafting
    name = pill_name or crafting.pill_name(c.kind, c.grade)
    batch = getattr(c, "batch", 1)
    score = c.score() if c.scores else None
    data = {
        "accent": "tribulation" if c.tribulation == "pending" else "alchemy",
        "seed": seed if seed is not None else c.decisions + 1,
        "pill": {"name": f"{name} ×{batch}" if batch > 1 else name, "grade": c.grade, "kind": c.kind, "sub": effect_line(c.kind, c.grade)},
        "stages": _stages(c),
        "herbs": _herb_states(c, list(herbs)),
        "refining": {"score": score, "bonus": c.score_bonus, "forgive": c.forgive, "explode": c.explode_below},
        "patterns": _patterns(c, score or 0),
        "done": c.done,
        "corner": {"seconds": f"{c.seconds:g}s to choose",
                   "difficulty": c.diff["name"] + (f" · Batch ×{batch}" if batch > 1 else "")},
        "warning_icon": "flame",
    }
    if c.done:
        return _result(c, data, name, outcome or {})
    pr = c.prompt()
    st = pr.stage
    data["mode"] = MODE[st]
    lines = [plain(x) for x in pr.lines]
    if st == 1:
        data.update(heat=c.heat, heat_state=pr.view.get("heat_state", c.heat_state(c.heat)), zone_width=c.zone_width)
        data["corner"]["label"] = f"ROUND {c.round + 1} / {c.diff['rounds']}"
        data["warning"] = (lines[2], lines[3])
    elif st == 2:
        left = Counter(c.order[c.placed:])
        data["herbs_left"] = [{"name": alchemy.HERBS[c.grade][t][0], "type": t, "count": n}
                              for t, n in sorted(left.items())]          # sorted by type: never the hidden order
        data.update(next_pos=POSITION_SHORT[c.placed + 1], placed=c.placed, total=len(c.order))
        data["corner"]["label"] = f"HERB {c.placed + 1} / {len(c.order)}"
        data["warning"] = (f"Which herb goes in {POSITION_SHORT[c.placed + 1]}?",
                           " ".join(plain(x) for x in c.clues + c.insights))
        data["warning_icon"] = "herb"
    elif st in (3, 5):
        moves = c.diff["rounds"] if st == 3 else alchemy.SEAL_CORE_MOVES
        data.update(yin=c.yin, yang=c.yang, move=c.round + 1, moves=moves, wild=c.diff["wild_herbs"])
        data["corner"]["label"] = f"MOVE {c.round + 1} / {moves}"
        hint = next((x for x in lines if x.startswith("Circulate")), "")
        data["warning"] = (lines[0], hint)
        data["warning_icon"] = "lotus"
    elif st == 4:
        shown = pr.view.get("pulse", c.pulse)
        data.update(pulse=shown, pulse_text=lines[1].rstrip(".").rstrip("…") if len(lines) > 1 else "")
        data["corner"]["label"] = f"STAGE {c.stages.index(4) + 1} / {len(c.stages)}"
        data["warning"] = (lines[1], "Condense at the perfect pulse: too early is weak, too late and it cracks.")
        data["warning_icon"] = "pill"
    else:
        data.update(strike=c.strike + 1, strikes=crafting.TRIBULATION_STRIKES, blocked=c.blocked,
                    strike_dir=STRIKE_DIR.get(c.strike_dir[0], "above"))
        last = c.strike + 1 == crafting.TRIBULATION_STRIKES
        data["corner"]["label"] = "FINAL STRIKE" if last else f"STRIKE {c.strike + 1} / {crafting.TRIBULATION_STRIKES}"
        data["corner"]["difficulty"] = c.diff["name"]
        data["warning"] = ("Dark clouds gather: the pill calls down a tribulation!", lines[1])
        data["warning_icon"] = "star"
        data["tribulation"] = _trib_panel(c)
    return data


def _trib_panel(c):
    marks = ["blocked"] * c.blocked + ["hit"] * (c.strike - c.blocked)
    marks += ["todo"] * (3 - len(marks))
    return {"effect9": alchemy.pattern_effect(9), "fail": alchemy.TRIBULATION_FAIL_PATTERNS, "marks": marks}


def _result(c, data, name, outcome):
    from . import crafting
    n = c.result
    data["corner"]["seconds"] = None
    exp = outcome.get("exp", c.exp())
    tail = f"+{exp:,} alchemy EXP"
    if outcome.get("rank_up"):
        tail += f" · You are now a {outcome['rank_up']} Alchemist!"
    if n:
        data["mode"] = "success"
        data.update(result=n, effect=alchemy.pattern_effect(n), toxicity=crafting.toxicity_text(c.kind, c.grade, n))
        data["corner"]["label"] = "REFINED"
        batch = getattr(c, "batch", 1)
        made = f"{batch} {name}{'s' if name.endswith('Pill') else ''}" if batch > 1 else f"a {name}"
        head = (f"Nine patterns! The heavens bow to your {name}{f' ×{batch}' if batch > 1 else ''}!" if n == 9
                else f"You craft {made} with {n} pattern{'s' if n > 1 else ''}!")
        if outcome.get("stored") is False:
            tail = "Your bag is full, so the pill rolls away and is lost. " + tail
        data["warning"] = (head, f"Final score {c.score():.0%} · {tail}")
        data["warning_icon"] = "star"
    else:
        data["mode"] = "exploded"
        data.update(score=c.score(), core_lost=c.core_lost)
        data["why"] = ("The Beast Core fought free of the pill and shattered." if c.core_lost else
                       f"Below {c.explode_below:.0%} the cauldron bursts.")
        data["corner"]["label"] = "FAILED"
        data["warning"] = ("The craft fails. The herbs and the Beast Core are lost." if c.core_lost
                           else "The cauldron explodes! The herbs are lost.", f"Final score {c.score():.0%} · {tail}")
    return data
