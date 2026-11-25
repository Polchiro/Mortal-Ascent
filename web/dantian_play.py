"""
The Dantian screen (docs/web.md "The Dantian"): your Internal Qi laid open. Everything here is the bot's own rules
read out, nothing new:

  - the Qi ledger: the Final Qi Rate the way bot/player.py qi_rate works it out (realm base × (1 + talent +
    technique + Qi artifact + Heavenly Blessing) × Qi pill × Blessed Land), line by line, with what is missing and
    where it comes from; per hour, minute and second; the time until the bar is full; the Qi waiting behind a gate;
  - the layers of the realm and its gates;
  - pill toxicity (bot/player.py current_toxicity, pill_effect_mult, toxicity_decay_hours): how much, what it does to
    your pills, when the next point fades;
  - your pills, each with what it would do to you now (the same sums as bot/crafting.use_pill), and eating one with
    the bot's own loot.use_item, as Discord's /inventory does;
  - the Qi-full ping: the same setting as Discord's /settings qi_pings.
"""
import threading
import time

import alchemy
import economy
import technique
import training
from bot import crafting, db, gear, loot, passive
from bot import player as rules

from .breakthrough_play import look_of, now_player
from .forge_play import rich
from .inventory import item_picture

LAND_NAMES = {k: k.replace("_", " ").title() for k in training.BLESSED_LANDS}
KIND_NAMES = {"qi": "Qi Pill", "burst": "Qi Burst Pill", "mending": "Mending Pill", "cleansing": "Cleansing Pill",
              "breakthrough": "Breakthrough Pill", "heaven": "Heaven-Defying Pill"}
KIND_COLOR = {"qi": "#6FC8FF", "burst": "#F5C35C", "mending": "#6FD9B0", "cleansing": "#D9C8FF",
              "breakthrough": "#B57BFF", "heaven": "#FF6B5A"}
ZONES = [(6, "quarter", "Pills work at a quarter of their strength"), (4, "half", "Pills work at half strength"),
         (1, "mild", "Pills at full strength"), (0, "clean", "Clean")]


def num(x, digits=1):
    s = f"{x:,.{digits}f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def pct(x):
    return f"{x:.1%}".replace(".0%", "%")


def dur(seconds):
    """3d 4h, 5h 12m, 40m."""
    seconds = int(max(0, seconds))
    days, rest = divmod(seconds, 86400)
    if days:
        h = rest // 3600
        return f"{days}d {h}h" if h else f"{days}d"
    return rules.fmt_duration(rest)


def best_technique(techs):
    if not techs:
        return None
    return max(techs, key=lambda t: technique.TRAINING_EXP_BONUS[t["grade"]] * rules.mastery_mult(t))


def ledger(p, techs, now):
    """The Qi Rate's sources, in the order qi_rate adds them: [{label, detail, value, on, how}], and the sum."""
    rows = []
    base = training.BASE_QI_RATE[p["realm"]]
    rows.append({"key": "base", "label": "Realm base", "detail": p["realm"], "value": f"{num(base, 2)} Qi/h", "on": True})
    tb = training.TALENT_QI_BONUS[p["talent"]]
    rows.append({"key": "talent", "label": "Talent", "detail": p["talent"], "value": f"+{pct(tb)}", "on": tb > 0,
                 "how": None if tb > 0 else "A higher talent (the Heaven-Defying Pill raises it)"})
    t, tq = best_technique(techs), rules.technique_qi_bonus(techs)
    stage = technique.MASTERY_STAGES[rules.stage_of(t)]["name"] if t else None
    rows.append({"key": "technique", "label": "Technique", "detail": f"{t['name']} · {stage}" if t else "None equipped",
                 "value": f"+{pct(tq)}", "on": tq > 0, "how": None if t else "Equip a technique (Profile)"})
    art = gear.artifact_bonus(p, "qi_rate")
    rows.append({"key": "artifact", "label": "Artifacts", "detail": "From what you wear" if art else "None that gather Qi",
                 "value": f"+{pct(art)}", "on": art > 0, "how": None if art else "Wear an artifact of Gathering (聚)"})
    b = rules.active_blessing(p, now)
    bq = economy.BLESSING_TIERS[b[0]]["qi_rate"] if b else 0
    rows.append({"key": "blessing", "label": "Heavenly Blessing", "detail": f"{b[0]} · {b[1]}d left" if b else "None",
                 "value": f"+{pct(bq)}", "on": bool(b), "how": None if b else "A Heavenly Blessing (Discord: /blessing)"})
    pill = rules.active_pill(p, now)
    rows.append({"key": "pill", "label": "Qi Pill", "mult": True,
                 "detail": f"{alchemy.QI_PILLS[pill[0]]['name']} · {dur(pill[2])} left" if pill else "None",
                 "value": f"×{pill[1]:.2f}" if pill else "×1", "on": bool(pill), "ends": p["pill_expires"] if pill else None,
                 "how": None if pill else "Eat a Qi Pill (below)"})
    land = rules.active_blessed_land(p, now)
    lm = training.BLESSED_LANDS[land[0]]["qi_multiplier"] if land else 1
    rows.append({"key": "land", "label": "Blessed Land", "mult": True,
                 "detail": f"{LAND_NAMES[land[0]]} · {dur(land[1])} left" if land else "None",
                 "value": f"×{lm:g}", "on": bool(land), "ends": p["blessed_land_expires"] if land else None,
                 "how": None if land else "Found while exploring: it multiplies everything above"})
    rate, mult = rules.qi_rate(p, now, techs)
    adds = [x for x in (tb, tq, art, bq) if x]
    sum_ = f"{num(base, 2)} × (1" + "".join(f" + {num(a, 3)}" for a in adds) + ")"
    if pill:
        sum_ += f" × {pill[1]:.2f}"
    if land:
        sum_ += f" × {lm:g}"
    return rows, sum_ + f" = {num(rate, 2)} Qi/h", rate


def toxicity(p, now):
    tox = rules.current_toxicity(p, now)
    zone, text = next((z, t) for lo, z, t in ZONES if tox >= lo)
    hours = rules.toxicity_decay_hours(p)
    nxt = None
    if tox and p.get("toxicity_at") is not None:
        period = hours * 3600
        nxt = period - ((now - p["toxicity_at"]) % period)
    cap = rules.toxicity_cap(p)
    faster = gear.artifact_bonus(p, "toxicity_decay_faster")
    return {"n": tox, "zone": zone, "text": text, "mult": rules.pill_effect_mult(tox), "every": num(hours, 1),
            "next": dur(nxt) if nxt else None, "next_s": round(nxt) if nxt else None,
            "clean": dur(nxt + (tox - 1) * hours * 3600) if nxt else None,
            "cap": None if cap == float("inf") else int(cap), "faster": pct(faster) if faster else None,
            "steps": [{"from": lo, "mult": m} for lo, m in training.PILL_TOXICITY_PENALTY]}


def pill_kind(item):
    if item["key"] == "heaven_defying":
        return "heaven", "Heaven", None
    return crafting.pill_info(item)


def preview(p, techs, item, now):
    """What eating this pill would do to you now (bot/crafting.use_pill's sums), or why it can't be eaten."""
    kind, grade, patterns = pill_kind(item)
    out = {"id": item["id"], "name": item["name"], "qty": item["qty"], "kind": kind, "kind_name": KIND_NAMES[kind],
           "grade": grade, "patterns": patterns, "picture": item_picture(item), "color": KIND_COLOR[kind],
           "can": True, "why": None, "lines": [], "warn": [], "tox": None}
    tox_now = rules.current_toxicity(p, now)
    if kind == "heaven":
        new = rules.talent_up(p["talent"])
        if new == p["talent"]:
            out.update(can=False, why=f"Your talent is already {p['talent']}: the pill would be wasted.")
        else:
            out["lines"].append(f"Talent {p['talent']} → {new}")
            q0 = rules.qi_rate(p, now, techs)[0]
            q1 = rules.qi_rate(dict(p, talent=new), now, techs)[0]
            out["lines"].append(f"Qi Rate {num(q0, 2)} → {num(q1, 2)} Qi/h")
        return out
    if kind == "breakthrough":
        out.update(can=False, why="Used at a realm gate: the best one is taken when you break through.")
        return out
    effect = (alchemy.pattern_effect(patterns) if patterns else 1.0) * (1 + gear.artifact_bonus(p, "pill_effect"))
    added = crafting.toxicity_for(patterns) if patterns else 1
    if kind == "cleansing":
        removed = max(1, int(crafting.pill_spec(kind, grade)["toxicity_removed"] * effect))
        left = max(0, tox_now - removed)
        out["tox"] = [tox_now, left]
        out["lines"].append(f"Toxicity {tox_now} → {left}")
        if not tox_now:
            out["warn"].append("You have no toxicity to wash out.")
        elif rules.pill_effect_mult(left) > rules.pill_effect_mult(tox_now):
            out["lines"].append("Pills back to " + ("full strength" if rules.pill_effect_mult(left) >= 1 else "half strength"))
        return out
    tox = rules.add_toxicity(p, tox_now, added)
    out["tox"] = [tox_now, tox]
    strength = rules.pill_effect_mult(tox) * effect
    half = kind in ("qi", "burst") and crafting.below_realm(p, grade)
    if half:
        strength *= alchemy.BELOW_REALM_EFFECT
        out["warn"].append("Below your realm's grade: half effect.")
    if rules.pill_effect_mult(tox) < 1:
        out["warn"].append(f"At {tox} toxicity pills work at {rules.pill_effect_mult(tox):.0%} strength.")
    if kind == "qi":
        current = rules.active_pill(p, now)
        if current:
            out.update(can=False, why=f"Your {alchemy.QI_PILLS[current[0]]['name']} is still working "
                                      f"({rules.fmt_duration(current[2])} left). Pills do not stack.")
            return out
        mult = 1 + (training.QI_PILLS[grade] - 1) * strength
        q0 = rules.qi_rate(p, now, techs)[0]
        q1 = rules.qi_rate(dict(p, pill_grade=grade, pill_mult=mult,
                                pill_expires=now + training.QI_PILL_DURATION_HOURS * 3600), now, techs)[0]
        out["lines"].append(f"Qi Rate ×{mult:.2f} for {training.QI_PILL_DURATION_HOURS} hours")
        out["lines"].append(f"{num(q0, 2)} → {num(q1, 2)} Qi/h")
    elif kind == "burst":
        rate = rules.qi_rate(p, now, techs)[0]
        qi = rate * crafting.pill_spec(kind, grade)["hours"] * strength
        out["lines"].append(f"+{num(qi, 1)} Qi at once")
    else:                                                                       # mending
        spec = crafting.pill_spec(kind, grade)
        hurt = rules.injured_for(p, now)
        if not hurt:
            out.update(can=False, why="You are not injured. Keep it for after a hard fight.")
            return out
        left = 0 if spec["injury_minutes"] is None else max(0, hurt - spec["injury_minutes"] * 60 * strength)
        out["lines"].append(f"Injured {rules.fmt_duration(hurt)} → " + (rules.fmt_duration(left) if left else "healed"))
    out["lines"].append(f"Toxicity {tox_now} → {tox}" + ("" if tox > tox_now else " (a clean pill)"))
    return out


def layers(p):
    """The realm's layers, with where its gates are (a phase bottleneck between phases, the realm gate at the end)."""
    top = rules.max_layer(p["realm"])
    out = []
    for n in range(1, top + 1):
        gate = None
        if n == top:
            gate = "realm"
        elif rules.phase_for(n) != rules.phase_for(n + 1):
            gate = "phase"
        out.append({"n": n, "done": n < p["layer"], "now": n == p["layer"], "gate": gate})
    return out


def view(conn, uid, now=None):
    now = time.time() if now is None else now
    p, techs = now_player(conn, uid, now)
    if p is None:
        return None
    need = rules.qi_needed(p["realm"], p["layer"])
    rows, sum_, rate = ledger(p, techs, now)
    kind, target = rules.next_gate(p)
    full = rules.at_full_gate(p)
    left = max(0.0, need - p["qi"])
    eta = None if full or kind == "peak" else dur(left / rate * 3600) if rate > 0 else None
    pills = [preview(p, techs, it, now) for it in db.get_items(conn, uid, "pills")]
    order = ["qi", "burst", "mending", "cleansing", "heaven", "breakthrough"]
    pills.sort(key=lambda x: (order.index(x["kind"]), x["name"]))
    from .breakthrough_play import plate
    hurt = rules.injured_for(p, now)
    return {
        "name": p["name"], "realm": p["realm"], "layer": rules.ordinal(p["layer"]), "phase": rules.phase_for(p["layer"]),
        "next_layer": rules.ordinal(p["layer"] + 1),
        "talent": p["talent"],
        "qi": round(p["qi"], 3), "need": need, "waiting": round(rules.overflow(p), 1), "full": bool(full),
        "rate": rate, "per_min": num(rate / 60, 3), "per_sec": num(rate / 3600, 4), "rate_text": num(rate, 2),
        "eta": eta, "gate": {"kind": kind, "target": target, "look": look_of(kind, target)},
        "plate": plate(p, techs, now), "ledger": rows, "formula": sum_, "layers": layers(p),
        "toxicity": toxicity(p, now), "pills": pills, "injured": rules.fmt_duration(hurt) if hurt else None,
        "pings": bool(p.get("qi_pings", 1)), "now": now,
    }


class Pills:
    """Eating pills, one at a time per player; the same nonce answers the same result."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self._guard = threading.Lock()
        self._locks = {}
        self._done = {}

    def _lock(self, uid):
        with self._guard:
            return self._locks.setdefault(uid, threading.Lock())

    def eat(self, conn, uid, item_id, nonce=None):
        """(result, why). The pill is eaten by the bot's own loot.use_item."""
        with self._lock(uid):
            d = self._done.get(uid)
            if d and nonce and d[0] == nonce:
                return d[1]
            now = self.clock()
            item = db.get_item(conn, uid, item_id)
            if not item or item["category"] != "pills":
                return None, "That pill is no longer in your bag."
            passive.bank(conn, uid, now)                       # as the bot does before every command
            p0 = dict(db.get_player(conn, uid))
            techs = db.get_techniques(conn, uid)
            pre = preview(p0, techs, item, now)
            if not pre["can"]:
                return None, pre["why"]
            before = view(conn, uid, now)
            msg = loot.use_item(conn, uid, item_id, now=now)
            after_item = db.get_item(conn, uid, item_id)
            eaten = (after_item["qty"] if after_item else 0) < item["qty"]
            if not eaten:
                return None, msg.replace("**", "")
            after = view(conn, uid, now)
            p1 = db.get_player(conn, uid)
            result = {"kind": pre["kind"], "name": item["name"], "color": pre["color"],
                      "lines": [str(rich(x)) for x in msg.split("\n") if x.strip()],
                      "before": {"qi": before["qi"], "rate": before["rate_text"], "tox": before["toxicity"]["n"],
                                 "talent": p0["talent"], "layer": before["layer"], "realm": before["realm"]},
                      "after": {"qi": after["qi"], "rate": after["rate_text"], "tox": after["toxicity"]["n"],
                                "talent": p1["talent"], "layer": after["layer"], "realm": after["realm"]},
                      "view": after}
            answer = (result, None)
            if nonce:
                with self._guard:
                    self._done[uid] = (nonce, answer)
            return answer


def set_pings(conn, uid, on):
    """The same switch as Discord's /settings qi_pings."""
    db.update_player(conn, uid, qi_pings=int(bool(on)))
    return bool(on)

