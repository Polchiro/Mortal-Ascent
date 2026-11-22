"""
The forge on the website. docs/web.md, "The forge".

The game itself is the bot's: bot/forging.py (make_plan, take_materials, Forge, finish_forge) and every number
in forge.py. This module only keeps each player's running forge in memory and turns it into page data.

The server is the referee: the hidden zone, the true metal and the temperatures never leave it, and every
decision has a deadline. A page that comes back late (or never) gets the timed-out move, like the bot's timer.
"""
import html
import json
import os
import re
import threading
import time
from dataclasses import dataclass, field

import forge

from bot import db, forging, materials, passives

from . import drawn, forge_live
from .profile import art_url, number

STAGE_ART = {s: f"/art/scenes/forge_stage_{s}.png" for s in forge.STAGES}
STAGE_TITLE = {"ignite": "Ignite the Forge", "heat": "Heat the Metal", "hammer": "Hammer", "quench": "Quench",
               "inscribe": "Inscribe"}
RARITY_COLOR = {"Common": "#C9D2E6", "Uncommon": "#6FD9B0", "Rare": "#6FA8FF", "Epic": "#B57BFF",
                "Legendary": "#F5C35C", "Mythical": "#FF6B6B"}
HEAT_CSS = ["#7A2A22", "#C0392B", "#F7943C", "#F5D04A", "#FFF6E0"]
BLANKS = {"weapon": "blank_sword", "armor": "blank_chest", "artifact": "blank_disc"}   # art/forge/, by gear kind
SHEETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "forge", "sheets.json")
GEAR_LABEL = {"weapon": "Weapon", "armor": "Armor", "artifact": "Artifact"}


@dataclass
class Session:
    plan: forging.Plan
    game: forging.Forge
    deadline: float
    turn: int = 0                       # bumps on every decision, so a stale page can't act twice
    outcome: dict = None
    started: float = field(default_factory=time.time)
    controls: str = "classic"           # "live" (forge_live: hands, the default) or "classic" (the buttons)
    live: object = None                 # the live stage being played (forge_live, an alchemy_live.Live)
    last: dict = None                   # how the last live stage went, for the page

    def is_live(self):
        return self.controls == "live" and not self.game.done and self.game.stage in forge_live.LIVE_STAGES


class Forges:
    """Each player's forge in progress (one at a time). Lost if the website restarts, like a bot restart."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self._s = {}
        self._lock = threading.Lock()

    def get(self, uid):
        return self._s.get(uid)

    def clear(self, uid):
        self._s.pop(uid, None)

    def start(self, conn, uid, plan, rng=None, controls="classic"):
        """Take the materials and start. Returns (session, None) or (None, reason)."""
        with self._lock:
            if uid in self._s and self._s[uid].outcome is None:
                return None, "You are already forging. Finish that one first."
            if plan.missing:
                return None, "Still missing: " + ", ".join(plan.missing)
            if not forging.take_materials(conn, uid, plan):
                return None, "Your materials or coins changed. Check the cost again."
            game = forging.new_game(conn, uid, plan, rng)
            s = Session(plan, game, self._deadline(game), controls=controls if controls in ("live", "classic") else "classic")
            self._s[uid] = s
            return s, None

    def _deadline(self, game):
        return self.clock() + game.seconds + forge.TIMER_GRACE_SECONDS

    def catch_up(self, conn, uid):
        """Apply every decision whose time ran out (the page was closed or too slow)."""
        s = self._s.get(uid)
        if not s or s.outcome is not None:
            return s
        with self._lock:
            if s.controls == "live":
                self._live_catch_up(conn, uid, s)
                return s
            while not s.game.done and self.clock() > s.deadline:
                missed = s.deadline
                s.game.act(None)
                s.turn += 1
                s.deadline = missed + s.game.seconds + forge.TIMER_GRACE_SECONDS
            self._finish_if_done(conn, uid, s)
        return s

    def act(self, conn, uid, key, turn):
        """The player's choice. Ignored if it is for an old turn or not one of the buttons."""
        s = self.catch_up(conn, uid)
        if not s or s.outcome is not None or s.game.done or turn != s.turn or s.is_live():
            return s
        with self._lock:
            pr = s.game.prompt()
            if key not in {k for k, _, _ in pr.options}:
                return s
            s.game.act(key)
            s.turn += 1
            s.deadline = self._deadline(s.game)
            self._finish_if_done(conn, uid, s)
        return s

    # ── live controls (forge_live) ──

    def _live_catch_up(self, conn, uid, s):
        """The live stage for the forge's current stage, settled when its time is up; the button stages (Quench,
        Inscribe for now) keep the bot's timer. Walking away runs everything out, as with the buttons."""
        now = at = self.clock()                     # `at`: when the next stage starts (a walked-away one: back then)
        for _ in range(500):
            g = s.game
            if g.done:
                break
            if s.is_live():
                if s.live is None:
                    s.live = forge_live.make(g, g.rng, s.turn, at)
                if not s.live.expired(now):
                    break
                lv = s.live
                end = (lv.t0 if lv.t0 is not None else lv.issued + forge_live.BEGIN_WAIT) + lv.length
                self._live_settle(s, lv.elapsed(now))
                at = min(now, end + forge_live.LINGER)
                s.deadline = at + g.seconds + forge.TIMER_GRACE_SECONDS
                continue
            if now <= s.deadline:                                  # a button stage, still in time
                break
            missed = s.deadline
            g.act(None)
            s.turn += 1
            s.deadline = missed + g.seconds + forge.TIMER_GRACE_SECONDS
        self._finish_if_done(conn, uid, s)

    def _live_settle(self, s, t):
        stage = s.live.stage
        result = forge_live.settle(s.live, s.game, t)
        s.last = dict(result or {}, stage=stage, title=STAGE_TITLE[stage], pts=s.game.points.get(stage))
        s.live = None
        s.turn += 1

    def live_begin(self, conn, uid, n):
        s = self.catch_up(conn, uid)
        if s and s.live is not None and s.live.id == n and s.live.t0 is None:
            s.live.t0 = min(self.clock(), s.live.issued + forge_live.BEGIN_WAIT)
        return s

    def live_press(self, conn, uid, n, ev):
        s = self.catch_up(conn, uid)
        if not s or s.live is None or s.live.id != n or s.live.t0 is None:
            return s, {"stale": True}
        with self._lock:
            reply = forge_live.press(s.live, s.game, self.clock() - s.live.t0, ev)
            if s.live.over:
                self._live_settle(s, self.clock() - s.live.t0)
                s.deadline = self._deadline(s.game)
                self._live_catch_up(conn, uid, s)
        return s, reply

    def live_act(self, conn, uid, key, turn):
        """A button stage on the live page (Quench, Inscribe for now): the bot's own decision."""
        s = self.catch_up(conn, uid)
        if not s or s.outcome is not None or s.game.done or turn != s.turn or s.is_live():
            return s
        with self._lock:
            pr = s.game.prompt()
            if key in {k for k, _, _ in pr.options}:
                s.game.act(key)
                s.turn += 1
                s.deadline = self._deadline(s.game)
                self._live_catch_up(conn, uid, s)
        return s

    def _finish_if_done(self, conn, uid, s):
        if s.game.done and s.outcome is None:
            s.outcome = forging.finish_forge(conn, uid, s.plan, s.game)


# ── text ─────────────────────────────────────────────────────────────

def rich(text):
    """The engine's **bold** / *italic* lines as safe HTML."""
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    return re.sub(r"\*(.+?)\*", r"<i>\1</i>", t)


def passive_view(gear, key):
    if not key:
        return None
    p = forge.PASSIVES[gear][key]
    return {"name": p["name"], "rarity": p["rarity"], "text": p["text"], "color": RARITY_COLOR.get(p["rarity"], "#F5DCA6")}


def material_view(key, qty=None, have=None):
    m = materials.MATERIALS[key]
    kind = materials.icon_kind(key)
    return {"key": key, "name": m["name"], "qty": qty, "have": have, "picture": art_url(kind) or drawn.url(kind),
            "short": have is not None and qty is not None and have < qty}


def gear_view(item):
    from .inventory import item_picture
    gear = passives.gear_kind(item)
    return {"id": item["id"], "name": item["name"], "tier": item["grade"].title(), "gear": GEAR_LABEL[gear],
            "equipped": bool(item["equipped"]), "picture": item_picture(item),
            "slots": [passive_view(gear, k) for k in passives.slots(item)]}


# ── the choose-your-forge page ───────────────────────────────────────

def setup_view(conn, uid, item_id=None, action=None, essence=None, fuel=None, liquid=None, lock=None):
    p = db.get_player(conn, uid)
    if p is None:
        return None
    gear = forging.forgeable(conn, uid)
    rank = forging.rank_of(p["blacksmith_exp"])
    out = {"rank": forging.rank_label(rank), "exp": number(p["blacksmith_exp"]), "coins": number(p["lotus_coins"]),
           "pearls": number(p["moon_pearls"]), "gear": [gear_view(i) for i in gear], "chosen": None}
    item = next((i for i in gear if i["id"] == item_id), gear[0] if gear else None)
    if not item:
        return out
    for g in out["gear"]:
        g["selected"] = g["id"] == item["id"]
    allowed = forging.actions_for(item)
    action = action if action in allowed else (allowed[0] if allowed else "enchant")
    have = forging.owned_materials(conn, uid)
    ess_opts = forging.essence_options(conn, uid, item)
    essence = essence if any(k == essence and ok for k, ok, _ in ess_opts) else None
    fuels, liquids = forging.extra_options(conn, uid, "fuel"), forging.extra_options(conn, uid, "liquid")
    fuel = fuel if fuel in fuels else None
    liquid = liquid if liquid in liquids else None
    lock = lock if lock in (0, 1) else (0 if action == "replace" else None)
    plan = forging.make_plan(conn, uid, item, action, essence, fuel, liquid, lock)
    preview = forging.Forge(item["grade"], rank, None, fuel, liquid, forging.swift_seconds(p), forging.steady_degrees(p))
    out["chosen"] = {
        "item": gear_view(item), "action": action, "lock": lock, "essence": essence, "fuel": fuel, "liquid": liquid,
        "actions": [{"key": a, "label": forging.ACTION_LABEL[a], "on": a == action} for a in ("enchant", "reroll", "replace")
                    if a in allowed],
        "essences": [dict(material_view(k), ok=ok, why=why, on=k == essence) for k, ok, why in ess_opts],
        "fuels": [dict(material_view(k), on=k == fuel) for k in fuels],
        "liquids": [dict(material_view(k), on=k == liquid) for k in liquids],
        "uses": [material_view(k, q, have[k]["qty"] if k in have else 0) for k, q in plan.uses],
        "coins": number(plan.coins) if plan.coins else None, "missing": plan.missing, "ready": not plan.missing,
        "difficulty": preview.diff["name"], "seconds": f"{preview.seconds:g}", "zone": preview.zone_width,
        "needs_rank": forging.rank_label(forge.RANK_NEEDED[item["grade"]]),
    }
    return out


def plan_from(conn, uid, form):
    """The Plan for the Begin button, rebuilt from the database (never trusted from the page)."""
    gear = {i["id"]: i for i in forging.forgeable(conn, uid)}
    try:
        item = gear[int(form.get("item", 0))]
    except (KeyError, ValueError):
        return None
    lock = form.get("lock")
    lock = int(lock) if lock in ("0", "1") else None
    return forging.make_plan(conn, uid, item, form.get("action") or "", form.get("essence") or None,
                             form.get("fuel") or None, form.get("liquid") or None, lock)


# ── the playing page ─────────────────────────────────────────────────

def play_view(s, now):
    g = s.game
    points = [{"name": STAGE_TITLE[k], "art": STAGE_ART[k], "pts": g.points.get(k),
               "active": not g.done and g.stage == k} for k in forge.STAGES]
    total = g.score()
    out = {"item": gear_view_plain(s.plan), "points": points, "total": total, "turn": s.turn, "done": s.outcome is not None,
           "live": s.controls == "live" and s.outcome is None}
    if s.outcome is None and s.controls == "live":
        out.update(stage=g.stage, stage_no=g.stage_i + 1, title="Forging")
    elif s.outcome is None:
        pr = g.prompt()
        left = max(0.0, s.deadline - forge.TIMER_GRACE_SECONDS - now)
        out.update({
            "stage": pr.stage, "stage_no": g.stage_i + 1, "title": STAGE_TITLE[pr.stage], "art": STAGE_ART[pr.stage],
            "lines": [rich(x) for x in pr.lines], "big": -1 if {k for k, _, _ in pr.options} == {"water", "oil"} else 1,
            "options": [{"key": k, "label": lbl} for k, lbl, _ in pr.options],
            "seconds": pr.seconds, "left": round(left, 1), "log": [rich(x) for x in g.log], "gauge": gauge(pr),
        })
    else:
        o = s.outcome
        changed = [passive_view(s.plan.gear, k) for _, k in o["changed"]]
        out.update({
            "rarity": o["rarity"], "color": RARITY_COLOR.get(o["rarity"], "#E05A4F"),
            "title": f"{o['rarity']} forge" if o["rarity"] else o.get("title", "The forge failed"),
            "changed": changed, "lines": [rich(x) for x in o["lines"]], "score": o["score"],
            "art": "/art/scenes/forge_success.png" if o["rarity"] else "/art/scenes/forge_cracked.png",
            "log": [rich(x) for x in g.log], "picture": gear_view(s.plan.item)["picture"], "rid": int(s.started * 1000),
            "grand": o["rarity"] in ("Legendary", "Mythical"),
        })
    return out


def scene_view(s, player):
    """What the live forge's scene is made of (forge_play.html .fscene): this player's smith (frame sheets of
    SHOAIB's videos, scripts/make_forge_sheets.py; none for a look without them, then only the forge and the effects
    show), the hammer alone for when the smith is hidden (scripts/make_forge_fx.py), and the blank of this gear kind (a sword, a chest plate or a round plate)."""
    import looks
    try:
        sheets = json.load(open(SHEETS))
    except (OSError, ValueError):
        sheets = {}
    return {"sheets": sheets.get(looks.gender_of(looks.of_player(player)), {}), "tool": sheets.get("tool", {}),
            "gear": s.plan.gear,
            "blank": f"/art/forge/{BLANKS[s.plan.gear]}.webp"}


def live_view(s, now):
    """The live page's state (static/forge_live.js)."""
    g = s.game
    base = play_view(s, now) if s.outcome is not None else None
    points = [{"key": k, "name": STAGE_TITLE[k], "pts": g.points.get(k), "active": not g.done and g.stage == k}
              for k in forge.STAGES]
    out = {"done": s.outcome is not None, "turn": s.turn, "points": points, "total": g.score(), "last": s.last,
           "log": [rich(x) for x in g.log]}
    if base:
        return out
    if s.live is not None:
        lv = s.live
        out["live"] = {"id": lv.id, "stage": lv.stage, "title": STAGE_TITLE[lv.stage], "pub": lv.pub,
                       "began": lv.t0 is not None, "t": round(now - lv.t0, 3) if lv.t0 is not None else None,
                       "no": forge.STAGES.index(lv.stage) + 1}
    elif not g.done:
        pr = g.prompt()
        out["prompt"] = {"stage": pr.stage, "title": STAGE_TITLE[pr.stage], "no": g.stage_i + 1,
                         "lines": [rich(x) for x in pr.lines], "gauge": gauge(pr), "seconds": pr.seconds,
                         "left": round(max(0.0, s.deadline - forge.TIMER_GRACE_SECONDS - now), 1),
                         "options": [{"key": k, "label": lbl} for k, lbl, _ in pr.options]}
    return out


def gear_view_plain(plan):
    return {"name": plan.item["name"], "tier": plan.tier.title(), "action": forging.ACTION_LABEL[plan.action]}


def gauge(pr):
    """What the stage's bar shows. Only what the player is allowed to see (the hint, not the truth)."""
    v = pr.view
    if pr.stage == "ignite":
        return {"kind": "heat", "pct": v["heat"], "label": f"{v['heat']}°", "left": "0° cold", "right": "100° wild"}
    if pr.stage == "heat":
        return {"kind": "colors", "colors": HEAT_CSS, "pct": (v["color"] + 0.5) / len(HEAT_CSS) * 100,
                "target": (v["target"] + 0.5) / len(HEAT_CSS) * 100, "left": "Dull red", "right": "White"}
    if pr.stage == "quench" and "target" in v:
        lo, hi = 300, 950
        pct = lambda t: max(0, min(100, (t - lo) / (hi - lo) * 100))  # noqa: E731
        w = v["window"] / 2
        return {"kind": "quench", "pct": pct(v["temp"]), "band_l": pct(v["target"] - w),
                "band_w": max(1.0, pct(v["target"] + w) - pct(v["target"] - w)), "left": f"{lo}°", "right": f"{hi}°"}
    return None
