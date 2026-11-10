"""
Alchemy on the website. docs/web.md, "Alchemy".

The game itself is the bot's: bot/crafting.py (plan, take_ingredients, craft_for, Craft, finish_craft) and every
number in alchemy.py. This module only keeps each player's running craft in memory and turns it into page data,
the same way web/forge_play.py does for the forge.

The server is the referee: the safe heat zone, the herb order and the true pulse never leave it, and every
decision has a deadline. A page that comes back late (or never) gets the timed-out move, like the bot's timer.
"""
import random
import re
import threading
import time
from dataclasses import dataclass, field

import alchemy

from bot import craft_card, crafting, db, loot

from .forge_play import rich
from .inventory import item_picture
from .profile import number

GRADE_COLOR = {"Mortal": "#C9D2E6", "Yellow": "#F5D04A", "Mystic": "#6FA8FF", "Earth": "#B57BFF",
               "Heaven": "#F5C35C"}
EXPLODED_COLOR = "#E05A4F"
STAGE_TITLE = {s: name.split(" ", 1)[1] for s, name in crafting.STAGE_NAMES.items()}   # without the emoji
PREFER = ("young", "old")
MAX_TIMEOUTS = 500                       # walking away: every decision left times out (the bot allows 200)
BAR = re.compile(r"\s*[▱◆┃]{5,}")       # the text heat / Yin-Yang bars; the page draws real gauges instead


@dataclass
class Session:
    kind: str
    grade: str
    craft: crafting.Craft
    used: list                           # [(item, qty)] taken from the bag: given back by Second Chance
    herbs: list                          # the ingredients as rows (bot/craft_card.herb_rows)
    deadline: float
    turn: int = 0                        # bumps on every decision, so a stale page can't act twice
    outcome: dict = None
    started: float = field(default_factory=time.time)


class Crafts:
    """Each player's craft in progress (one at a time). Lost if the website restarts, like a bot restart."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self._s = {}
        self._lock = threading.Lock()

    def get(self, uid):
        return self._s.get(uid)

    def clear(self, uid):
        self._s.pop(uid, None)

    def start(self, conn, uid, kind, grade, prefer="young", batch=1, rng=None):
        """Plan from the database, take the herbs (and core) and start. Returns (session, None) or (None, reason)."""
        with self._lock:
            if uid in self._s and self._s[uid].outcome is None:
                return None, "You are already refining a pill. Finish that one first."
            p = db.get_player(conn, uid)
            if p is None:
                return None, "No character yet."
            if (kind, grade) not in craftable(p):
                return None, "Your alchemist rank can't refine that pill yet."
            batch = max(1, min(int(batch), alchemy.batch_cap(crafting.rank_of(p["alchemy_exp"]))))
            pl = crafting.plan(conn, uid, kind, grade, prefer if prefer in PREFER else "young", batch)
            if pl["missing"]:
                return None, "Still missing: " + ", ".join(pl["missing"])
            if not crafting.take_ingredients(conn, uid, pl):
                return None, "Your herbs changed in the meantime. Check the recipe again."
            craft = crafting.craft_for(p, kind, grade, pl["age"], rng, batch)
            used = list(pl["uses"]) + ([(pl["core"], pl["core_qty"])] if pl["core"] else [])
            s = Session(kind, grade, craft, used, craft_card.herb_rows(pl["uses"], pl["core"], pl["core_qty"]),
                        self._deadline(craft))
            self._s[uid] = s
            self._finish_if_done(conn, uid, s)
            return s, None

    def _deadline(self, craft):
        return self.clock() + craft.seconds + crafting.TIMER_GRACE_SECONDS

    def catch_up(self, conn, uid):
        """Apply every decision whose time ran out (the page was closed or too slow)."""
        s = self._s.get(uid)
        if not s or s.outcome is not None:
            return s
        with self._lock:
            n = 0
            while not s.craft.done and self.clock() > s.deadline and n < MAX_TIMEOUTS:
                missed = s.deadline
                s.craft.act(None)
                s.turn += 1
                n += 1
                s.deadline = missed + s.craft.seconds + crafting.TIMER_GRACE_SECONDS
            self._finish_if_done(conn, uid, s)
        return s

    def act(self, conn, uid, key, turn):
        """The player's choice. Ignored if it is for an old turn or not one of the buttons."""
        s = self.catch_up(conn, uid)
        if not s or s.outcome is not None or s.craft.done or turn != s.turn:
            return s
        with self._lock:
            pr = s.craft.prompt()
            if key not in {k for k, _, _ in pr.options}:
                return s
            s.craft.act(key)
            s.turn += 1
            s.deadline = self._deadline(s.craft)
            self._finish_if_done(conn, uid, s)
        return s

    def _finish_if_done(self, conn, uid, s):
        if s.craft.done and s.outcome is None:
            old = crafting.rank_of(db.get_player(conn, uid)["alchemy_exp"])
            lines, news = crafting.finish_craft(conn, uid, s.craft, ingredients=s.used)
            new = crafting.rank_of(db.get_player(conn, uid)["alchemy_exp"])
            s.outcome = {"lines": lines, "news": news, "exp": s.craft.exp(),
                         "rank_up": crafting.rank_label(new) if new > old else None}


# ── shared bits ──────────────────────────────────────────────────────

def craftable(player):
    """(kind, grade) pairs this alchemist's rank allows, in the bot's /craft order."""
    r = crafting.rank_of(player["alchemy_exp"])
    return [(k, g) for k in crafting.KINDS for g in alchemy.GRADES if crafting.pill_spec(k, g)["rank"] <= r]


def pill_picture(kind, grade, patterns=1):
    return item_picture(crafting.crafted_pill(kind, grade, patterns))


def herb_picture(grade, type_):
    return item_picture(loot.herb(grade, type_))


def core_picture(core, grade):
    return item_picture({"category": "materials", "key": f"core:{core}:{grade}", "name": loot.CORE_NAMES[core],
                         "grade": grade, "data": {"core": core, "grade": grade}})


def rank_view(player):
    exp = player["alchemy_exp"]
    r = crafting.rank_of(exp)
    nxt = alchemy.ALCHEMIST_RANK_EXP.get(r + 1)
    return {"rank": crafting.rank_label(r), "exp": number(exp),
            "next": f"{number(nxt)} for {crafting.rank_label(r + 1)}" if nxt else "max rank"}


def herb_counts(conn, uid, grade):
    """{herb type: how many of this grade the player holds}."""
    out = {}
    for h in db.get_items(conn, uid, "herbs"):
        if h["grade"] == grade:
            t = (h.get("data") or {}).get("type")
            out[t] = out.get(t, 0) + h["qty"]
    return out


# ── the choose-your-pill page ────────────────────────────────────────

def parse_pill(text):
    kind, _, grade = (text or "").partition(":")
    return (kind, grade) if kind in crafting.KINDS and grade in alchemy.GRADES else None


def setup_view(conn, uid, pill=None, batch=None, prefer=None):
    p = db.get_player(conn, uid)
    if p is None:
        return None
    rank = crafting.rank_of(p["alchemy_exp"])
    cap = alchemy.batch_cap(rank)
    out = {**rank_view(p), "coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"]), "cap": cap,
           "pills": [], "chosen": None}
    options = craftable(p)
    for k, g in options:
        ready = not crafting.plan(conn, uid, k, g)["missing"]
        out["pills"].append({"key": f"{k}:{g}", "name": crafting.pill_name(k, g), "label": crafting.KINDS[k][0],
                             "emoji": crafting.KINDS[k][1], "grade": g, "color": GRADE_COLOR[g], "ready": ready,
                             "picture": pill_picture(k, g)})
    if not options:
        return out
    want = parse_pill(pill)
    if want not in options:                                  # default: the first pill the herbs are ready for
        want = next(((k, g) for (k, g), v in zip(options, out["pills"]) if v["ready"]), options[0])
    for v in out["pills"]:
        v["selected"] = v["key"] == f"{want[0]}:{want[1]}"
    kind, grade = want
    spec = crafting.pill_spec(kind, grade)
    prefer = prefer if prefer in PREFER else "young"
    try:
        batch = max(1, min(int(batch or 1), cap))
    except (TypeError, ValueError):
        batch = 1
    pl = crafting.plan(conn, uid, kind, grade, prefer, batch)
    c = crafting.craft_for(p, kind, grade, pl["age"], random.Random(0), batch)
    solo = crafting.craft_for(p, kind, grade, pl["age"], random.Random(0), 1) if batch > 1 else None
    have = herb_counts(conn, uid, grade)
    recipe = [{"name": alchemy.HERBS[grade][t][0], "qty": n * batch, "have": have.get(t, 0),
               "short": have.get(t, 0) < n * batch, "picture": herb_picture(grade, t)}
              for t, n in crafting.KINDS[kind][3]]
    if kind == "breakthrough":
        key = f"core:{spec['core']}:{grade}"
        got = sum(i["qty"] for i in db.get_items(conn, uid, "materials") if i["key"] == key)
        recipe.append({"name": f"{grade} {loot.CORE_NAMES[spec['core']]}", "qty": batch, "have": got,
                       "short": got < batch, "picture": core_picture(spec["core"], grade)})
    uses = [] if pl["missing"] else (
        [{"name": loot.herb_label(i), "qty": q, "picture": item_picture(i)} for i, q in pl["uses"]]
        + ([{"name": loot.describe(pl["core"]), "qty": pl["core_qty"], "picture": item_picture(pl["core"])}]
           if pl["core"] else []))
    age = alchemy.HERB_AGES[pl["age"]]
    relief = []
    if c.ranks_above:
        relief.append(f"{min(c.ranks_above, 3)} rank(s) above the recipe: wider heat zone, more time"
                      + (", herb hints" if 2 in c.stages else ""))
    if c.forgive:
        relief.append(f"{c.forgive} mistake(s) forgiven")
    if c.zone_bonus:
        relief.append(f"Furnace artifact: +{c.zone_bonus}° heat zone")
    batches = [{"n": n, "on": n == batch, "ready": not crafting.plan(conn, uid, kind, grade, prefer, n)["missing"]}
               for n in range(1, cap + 1)]
    out["chosen"] = {
        "key": f"{kind}:{grade}", "name": crafting.pill_name(kind, grade), "label": crafting.KINDS[kind][0],
        "emoji": crafting.KINDS[kind][1], "grade": grade, "color": GRADE_COLOR[grade],
        "picture": pill_picture(kind, grade), "effect": craft_card.effect_line(kind, grade),
        "min_age": crafting.age_word(spec["min_age"]), "needs_rank": crafting.rank_label(spec["rank"]),
        "difficulty": c.diff["name"], "seconds": f"{c.seconds:g}", "zone": c.zone_width,
        "stages": [crafting.STAGE_NAMES[s] for s in c.stages],
        "recipe": recipe, "uses": uses, "missing": pl["missing"], "ready": not pl["missing"],
        "age": pl["age"], "max_patterns": age["max_patterns"],
        "score_bonus": f"+{age['score_bonus']:.0%}" if age["score_bonus"] else None,
        "relief": relief, "batch": batch, "batches": batches, "prefer": prefer,
        "solo": {"seconds": f"{solo.seconds:g}", "zone": solo.zone_width} if solo else None,
    }
    return out


# ── the playing page ─────────────────────────────────────────────────

def stage_art(stage, grade):
    if stage == 6:
        return "/art/scenes/alchemy_tribulation.jpg"
    if stage == 4:
        return f"/art/scenes/pill_{grade.lower()}.png"
    return "/art/scenes/cauldron.png"


def play_view(s, now):
    c = s.craft
    trib = c.tribulation is not None
    points = [{"name": STAGE_TITLE[st], "emoji": crafting.STAGE_NAMES[st].split(" ", 1)[0],
               "pct": f"{c.scores[st]:.0%}" if st in c.scores else None,
               "active": not c.done and not trib and c.stage == st} for st in c.stages]
    if trib:
        points.append({"name": STAGE_TITLE[6], "emoji": "⚡",
                       "pct": {"won": "won", "lost": "lost"}.get(c.tribulation),
                       "active": c.tribulation == "pending" and not c.done})
    out = {"name": crafting.pill_name(s.kind, s.grade), "batch": c.batch, "grade": s.grade,
           "color": GRADE_COLOR[s.grade], "picture": pill_picture(s.kind, s.grade),
           "effect": craft_card.effect_line(s.kind, s.grade), "points": points, "turn": s.turn,
           "herbs": [dict(h, label=f"{h['age']}-year {h['name']}" if h["age"] else h["name"]) for h in s.herbs],
           "done": s.outcome is not None, "total": len(c.stages)}
    if s.outcome is None:
        pr = c.prompt()
        left = max(0.0, s.deadline - crafting.TIMER_GRACE_SECONDS - now)
        out.update({
            "stage": pr.stage, "stage_no": c.stages.index(pr.stage) + 1 if pr.stage in c.stages else None,
            "title": STAGE_TITLE[pr.stage], "art": stage_art(pr.stage, s.grade),
            "lines": [rich(BAR.sub("", x)) for x in pr.lines],
            "options": [{"key": k, "label": lbl, "emoji": em, "good": pr.style.get(k) == "success"}
                        for k, lbl, em in pr.options],
            "seconds": pr.seconds, "left": round(left, 1), "log": [rich(x) for x in c.log], "gauge": gauge(c, pr),
        })
    else:
        o, n = s.outcome, c.result
        out.update({
            "patterns": n, "exploded": not n, "score": f"{c.score():.0%}",
            "title": (f"{crafting.pill_name(s.kind, s.grade)} · {crafting.CN[n]}纹" if n
                      else "The craft fails" if c.core_lost else "The cauldron explodes"),
            "result_color": GRADE_COLOR[s.grade] if n else EXPLODED_COLOR,
            "art": pill_picture(s.kind, s.grade, n) if n else "/art/scenes/cauldron_burst.png",
            "log": [rich(x) for x in c.log], "lines": [rich(x) for x in o["lines"]],
            "tribulation": c.tribulation,
        })
    return out


def gauge(c, pr):
    """What the stage's bar shows. Only what the player's text already shows: never the safe zone or order."""
    if pr.stage == 1:
        return {"kind": "heat", "pct": c.heat, "label": f"{c.heat}°", "left": "0°", "right": "100°"}
    if pr.stage in (3, 5):
        return {"kind": "balance", "yin": c.yin, "yang": c.yang}
    if pr.stage == 4:
        return {"kind": "pulse", "level": pr.view.get("pulse", 0), "steps": len(crafting.PULSES) - 1}
    return None
