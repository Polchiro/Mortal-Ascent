"""
Sparring with the Martial Master on the website (docs/technique.md "On the website", /training and /spar).

Nothing here is a new rule. A spar is bot/sparring.Spar, the same object Discord's /spar plays: the master's
rhythm and tells, the counters, the techniques' rests, the artifacts, the 15 exchanges. What a finished spar
gives is what bot/views.SparView.finish gives, line for line: mastery EXP only for well-timed techniques
(technique.SPAR_EXP_PER_TIMED_USE, SPAR_WIN_EXP), the daily rates, a trial's breakthrough or its 24-hour wait,
the quest counts and the two-hour rest. The rest starts when the spar starts, as on Discord, and it is the same
saved cooldown, so a spar on Discord and one here can't overlap.

The server referees: the page only sends which button was pressed. It is never told the master's move for the
exchange being played, only his tell (when he gives one) and what he did in the exchanges already over.

Only the web's own: TURN_SECONDS (the bot's 15 plus the web's round trip, as in the Arena), no shuffled buttons
(the keys 1-4 stay put; the timer and the three-timeouts forfeit still end an idle spar), and a Yield button that
does what three timeouts do. Spars live in this process's memory, like duels: a restart ends one unsaved (its
rest stays, as when the bot restarts).
"""
import random
import re
import threading
import time
from dataclasses import dataclass, field

import battle
import challenges
import looks
import technique

from bot import db, mastery, quests, sparring
from bot import player as players

from . import spar_master, technique_fx

TURN_SECONDS = 20                          # the bot's 15, plus a little for the web round trip (as web/duel_play.py)
MASTER = {"name": "Martial Master"}
YARD = "/art/spar/yard.jpg"                             # an ordinary spar: the training yard, seen from the side
HALL = "/art/scenes/spar_hall.jpg"                      # a mastery trial: the hall at night
TECH_KEYS = ("attack_tech", "defense_tech", "flex_tech")
HINT = {"strike": "Beats Break. Into his Guard nothing lands. Same move: you trade blows at half.",
        "guard": "Beats Strike, and opens him: your attack technique right after is perfect timing. A Break gets through.",
        "break": "Beats Guard. Into his Strike you are hit first. Same move: you trade blows at half."}
WORD = {("win", "guard"): "Opening!", ("win", "strike"): "Struck first!", ("win", "break"): "Guard broken!",
        ("lose", "guard"): "Blocked!", ("lose", "strike"): "Too slow!", ("lose", "break"): "He breaks your guard!",
        ("tie", "guard"): "Standoff", ("tie", "strike"): "Clash!", ("tie", "break"): "Clash!"}


def plain(text):
    """A bot line without Discord's marks: no **bold**, no *italics*, no leading emoji."""
    text = re.sub(r"\*+", "", text or "")
    return re.sub(r"^[^\w\"'(]+", "", text).strip()


def _icon(t):
    from bot.sheet.data import tech_kind
    from .profile import art_url
    return art_url(tech_kind(t["name"], players.TECH_BY_NAME.get(t["name"], {}).get("school", "Body"))) or \
        f"/art/icons/actions/{t['type']}_tech.webp"


def _bar(t):
    """A technique's mastery bar for the pages."""
    cap = players.mastery_cap(t)
    stage = players.stage_of(t)
    return {"id": t["id"], "name": t["name"], "grade": t["grade"], "type": t["type"], "icon": _icon(t),
            "stage": technique.MASTERY_STAGES[stage]["name"], "exp": t["mastery_exp"], "cap": cap,
            "pct": 100 if cap is None else max(0, min(100, round(100 * t["mastery_exp"] / cap))),
            "next": technique.MASTERY_STAGES[stage + 1]["name"] if cap is not None else None,
            "full": players.bar_full(t)}


@dataclass
class Session:
    spar: object
    player: dict
    techniques: list
    focus: dict | None
    trial: bool
    look: dict | None
    deadline: float
    timeouts: int = 0
    turns: list = field(default_factory=list)       # per exchange played: what each did, for the page to act out
    result: dict | None = None
    v: int = 1

    @property
    def over(self):
        return self.result is not None


class Hall:
    def __init__(self, clock=time.time, rng=None):
        self.clock = clock
        self.rng = rng or random.Random()
        self.lock = threading.RLock()
        self.spars = {}             # uid → Session

    # ── who may spar (the checks of Discord's /spar, in its order) ────────────────

    def busy(self, uid):
        s = self.spars.get(uid)
        return s is not None and not s.over

    def _why_not(self, conn, uid, tech_id):
        """(why not, the trial's technique). why not is None when the spar may start."""
        now = self.clock()
        p = db.get_player(conn, uid)
        if p is None:
            return "You have no character yet.", None
        hurt = players.injured_for(p, now)
        if hurt:
            return f"You are injured. Rest for {players.fmt_duration(hurt)} before sparring.", None
        if self.busy(uid):
            return "You are already sparring.", None
        focus = None
        if tech_id is not None:
            focus = db.get_technique(conn, uid, tech_id)
            if not focus:
                return "You don't know that technique.", None
            if not players.bar_full(focus):
                return f"{focus['name']} isn't ready for a trial: its mastery bar isn't full.", None
            if not focus["equipped"]:
                return f"Equip {focus['name']} to take its trial.", None
            wait = db.cooldown_left(conn, uid, f"trial:{focus['id']}", now)
            if wait:
                return f"You failed this trial recently. Retry in {players.fmt_duration(wait)}.", None
        wait = db.cooldown_left(conn, uid, "spar", now)
        if wait:
            return f"The master is resting. Spar again in {players.fmt_duration(wait)}.", None
        return None, focus

    def start(self, conn, uid, tech_id=None):
        """Begin a spar, or `tech_id`'s mastery trial. Returns None, or why not."""
        with self.lock:
            self.tick(conn)
            why, focus = self._why_not(conn, uid, tech_id)
            if why:
                return why
            now = self.clock()
            p = db.get_player(conn, uid)
            techs = db.get_techniques(conn, uid)
            strength = technique.TRIAL_MASTER_STRENGTH[players.stage_of(focus) + 1] if focus else 1.0
            spar = sparring.Spar(p, techs, db.equipped_weapon(conn, uid), strength, self.rng,
                                 armor=db.equipped_armor(conn, uid))
            # the rest starts now, not when the spar ends (bot/client.claim_session): it is saved, so it holds
            # through a restart and against a second spar on Discord
            db.set_cooldown(conn, uid, "spar", technique.SPAR_COOLDOWN_MINUTES * 60, now)
            self.spars[uid] = Session(spar, p, techs, focus, focus is not None, looks.of_player(p),
                                      now + TURN_SECONDS)
            return None

    # ── time passing ─────────────────────────────────────────────────────────────

    def tick(self, conn):
        """Play the exchanges whose time ran out: no pick is a Guard, three in a row and you walk away."""
        now = self.clock()
        for s in list(self.spars.values()):
            while not s.over and now >= s.deadline:
                s.timeouts += 1
                if s.timeouts >= battle.TIMEOUTS_TO_FLEE:
                    self._finish(conn, s, forfeit=True, why="You stood still too long and walked away from the spar.")
                else:
                    self._play(conn, s, battle.TIMEOUT_MOVE, timed_out=True, at=s.deadline)

    # ── an exchange ──────────────────────────────────────────────────────────────

    def pick(self, conn, uid, choice, turn=None):
        """Play this exchange's move. Returns None, or why not."""
        with self.lock:
            self.tick(conn)
            s = self.spars.get(uid)
            if s is None or s.over:
                return "The spar is over."
            if turn is not None and turn != s.spar.turn:
                return None                                  # a late press for an exchange already played
            if choice not in [c[0] for c in s.spar.choices()]:
                return "That isn't one of your moves."
            if not s.spar.ready(choice):
                left = s.spar.cooldowns[choice]
                return f"That technique is still recovering ({left} more exchange{'s' if left != 1 else ''})."
            s.timeouts = 0
            self._play(conn, s, choice)
            return None

    def give_up(self, conn, uid):
        """Yield: the same as walking away on three timeouts (nothing earned)."""
        with self.lock:
            s = self.spars.get(uid)
            if s is not None and not s.over:
                self._finish(conn, s, forfeit=True, why="You bow out of the spar.")

    def _play(self, conn, s, choice, timed_out=False, at=None):
        sp = s.spar
        turn, his = sp.turn, sp.master
        hp0, mhp0, timed0 = sp.hp, sp.m_hp, sum(sp.timed.values())
        t = sp.tech(choice)
        base = ("strike" if t["type"] == "attack" else "guard") if t else choice
        text = plain(sp.play(choice))
        outcome = "tie" if base == his else "win" if challenges.COUNTERS[his] == base else "lose"
        timed = sum(sp.timed.values()) > timed0
        fx = None
        if t:
            fx = technique_fx.of(t["name"], t["grade"], looks.gender_of(s.look))
            if fx and fx["motion"] in ("deflect", "sidestep") and outcome != "win":
                fx = None       # only when his blow really was stopped: the picture never shows more than happened
        s.turns.append({
            "turn": turn, "outcome": outcome, "word": WORD[(outcome, base if outcome != "lose" else his)],
            "timed": timed, "timed_out": timed_out, "line": ("You hesitated and raised your guard. " if timed_out else "") + text,
            "me": {"move": choice, "base": base, "label": t["name"] if t else choice.title(), "tech": bool(t),
                   "type": t["type"] if t else None, "grade": t["grade"] if t else None, "fx": fx,
                   "lost": round(hp0) - round(sp.hp)},
            "master": {"move": his, "label": his.title(), "lost": round(mhp0) - round(sp.m_hp)}})
        s.v += 1
        if sp.over:
            self._finish(conn, s)
        else:
            s.deadline = (at if at is not None else self.clock()) + TURN_SECONDS

    # ── the end (bot/views.SparView.finish, line for line) ───────────────────────

    def _finish(self, conn, s, forfeit=False, why=None):
        now = self.clock()
        sp, uid = s.spar, s.player["user_id"]
        won = sp.won and not forfeit
        if forfeit:
            sp.timed = {}
        daily = players.daily_rate(technique.SPAR_DAILY_RATES, db.daily_count(conn, uid, "spar", now))
        by_id = {t["id"]: t for t in s.techniques}
        gains, notes = [], [why] if why else []
        for tid, exp in sp.mastery_awards(daily).items():
            tech = by_id[tid]
            gained, _ = mastery.gain(conn, s.player, tech, exp)
            if gained:
                gains.append({"gained": gained, **_bar(tech)})
            if players.bar_full(tech) and not s.trial:
                notes.append(f"{tech['name']} is ready for its trial to reach {_bar(tech)['next']}.")
        if not sp.timed and not forfeit:
            notes.append("No technique was used at the right moment, so no mastery EXP this time.")
        if daily < 1:
            notes.append(f"You have sparred a lot today: EXP ×{daily:g}.")
        trial = None
        if s.trial:
            trial = {"name": s.focus["name"], "passed": won, "stage": None}
            if won:
                trial["stage"] = mastery.pass_trial(conn, s.focus)
                notes.append(f"Breakthrough! {s.focus['name']} reaches {trial['stage']}.")
            else:
                db.set_cooldown(conn, uid, f"trial:{s.focus['id']}", technique.TRIAL_FAIL_COOLDOWN_HOURS * 3600, now)
                notes.append(f"The trial failed. No EXP is lost; you may retry in {technique.TRIAL_FAIL_COOLDOWN_HOURS} hours.")
        db.bump_daily(conn, uid, "spar", now)
        quests.record(conn, uid, "spar", now=now)
        if won:
            quests.record(conn, uid, "spar_win", now=now)
        db.set_cooldown(conn, uid, "spar", technique.SPAR_COOLDOWN_MINUTES * 60, now)
        s.result = {"outcome": "victory" if won else "forfeit" if forfeit else "defeat", "gains": gains,
                    "notes": notes, "trial": trial, "exchanges": len(s.turns),
                    "again": players.fmt_duration(technique.SPAR_COOLDOWN_MINUTES * 60)}
        s.v += 1

    def done(self, uid):
        """Leave a finished spar's result."""
        with self.lock:
            s = self.spars.get(uid)
            if s is not None and s.over:
                del self.spars[uid]

    # ── what the pages show ──────────────────────────────────────────────────────

    def hall(self, conn, uid):
        """The training yard's page: your equipped techniques and their mastery, and whether the master will spar."""
        with self.lock:
            self.tick(conn)
            now = self.clock()
            p = db.get_player(conn, uid)
            if p is None:
                return None
            if uid in self.spars and self.spars[uid].over:
                del self.spars[uid]                                    # walked in from a finished spar's result
            techs = []
            for t in db.get_techniques(conn, uid):
                b = _bar(t)
                wait = db.cooldown_left(conn, uid, f"trial:{t['id']}", now) if b["full"] else 0
                b["trial_wait"] = players.fmt_duration(wait) if wait else None
                b["strength"] = technique.TRIAL_MASTER_STRENGTH[players.stage_of(t) + 1] if b["full"] else None
                techs.append(b)
            hurt = players.injured_for(p, now)
            wait = db.cooldown_left(conn, uid, "spar", now)
            done_today = db.daily_count(conn, uid, "spar", now)
            full = technique.SPAR_DAILY_RATES[0][0]
            return {"name": p["name"], "realm": p["realm"], "layer": p["layer"], "techniques": techs,
                    "in_spar": self.busy(uid),
                    "hurt": players.fmt_duration(hurt) if hurt else None,
                    "wait": players.fmt_duration(wait) if wait else None,
                    "today": done_today, "full_left": max(0, full - done_today),
                    "rate": players.daily_rate(technique.SPAR_DAILY_RATES, done_today),
                    "per_use": technique.SPAR_EXP_PER_TIMED_USE, "win": technique.SPAR_WIN_EXP,
                    "rest": players.fmt_duration(technique.SPAR_COOLDOWN_MINUTES * 60),
                    "exchanges": sparring.MAX_TURNS, "seconds": TURN_SECONDS}

    def _move(self, sp, key):
        t = sp.tech(key) if key in TECH_KEYS else None
        if not t:
            return {"key": key, "label": key.title(), "icon": f"/art/icons/actions/{key}.webp", "ready": True,
                    "tech": False, "kind": "", "state": "", "info": HINT[key]}
        left = sp.cooldowns[key]
        attack = t["type"] == "attack"
        when = ("right after you Guard his Strike" if attack else "against his Strike")
        return {"key": key, "label": t["name"], "icon": _icon(t), "ready": not left, "tech": True,
                "type": t["type"], "kind": "Attack technique" if attack else "Defense technique",
                "state": f"Ready in {left} exchange{'s' if left != 1 else ''}" if left else "Ready",
                "info": f"{t['name']}: counts as {'a Strike' if attack else 'a Guard'}, with its effects, then rests a "
                        f"few exchanges. Perfect timing (mastery EXP): {when}."}

    def state(self, conn, uid):
        """The spar as the page shows it, or None. Never the master's move for the exchange being played."""
        with self.lock:
            self.tick(conn)
            s = self.spars.get(uid)
            if s is None:
                return None
            sp, look = s.spar, s.look
            gender = looks.gender_of(look)
            sheets = {}
            for act, sh in (looks.attack_sheets(look) or {}).items():
                sheets[act] = sh
            if looks.guard_sheet(look):
                sheets["guard"] = looks.guard_sheet(look)
            art = []
            for key in TECH_KEYS:
                t = sp.tech(key)
                if not t:
                    continue
                motions, pics = technique_fx.assets(t["name"], gender)
                art += pics
                for m in motions:
                    if looks.motion_sheet(look, m):
                        sheets[m] = looks.motion_sheet(look, m)
            turn = min(sp.turn, sparring.MAX_TURNS)
            timed = sum(sp.timed.values())
            nxt = technique.MASTERY_STAGES[players.stage_of(s.focus) + 1]["name"] if s.trial and not s.over else None
            out = {
                "v": s.v, "turn": sp.turn, "shown_turn": turn, "max_turns": sparring.MAX_TURNS,
                "seconds": TURN_SECONDS, "left": 0 if s.over else max(0, round(s.deadline - self.clock())),
                "trial": s.trial, "arena": HALL if s.trial else YARD,
                "title": (f"Mastery trial: {s.focus['name']}" + (f" → {nxt}" if nxt else "")) if s.trial
                         else "Sparring with the Master",
                "me": {"name": s.player["name"], "realm": f"{s.player['realm']} · Layer {s.player['layer']}",
                       "hp": round(sp.hp), "max_hp": round(sp.max_hp), "face": looks.face(look), "gender": gender,
                       "poses": {p: looks.fighter(look, p) for p in looks.POSES}, "isheet": looks.idle_sheet(look),
                       "sheets": sheets, "art": art,
                       "moves": [self._move(sp, k) for k, _ in sp.choices()]},
                "master": {**MASTER, "img": spar_master.still(), "sheets": spar_master.sheets(), "hp": round(sp.m_hp), "max_hp": round(sp.m_max),
                           "tag": f"Trial · ×{sp.strength:g} strength" if s.trial else "Sparring · your realm and layer",
                           "staggered": sp.m_staggered},
                "tell": None if s.over else plain(sp.hint()), "has_tell": bool(sp.tell) and not s.over,
                # the tell as a pose: the same thing his words say (each tell names one move), never more
                "tell_pose": sp.master if sp.tell and not s.over else None,
                "opening": sp.blocked_strike and not s.over,
                "timed": timed, "per_use": technique.SPAR_EXP_PER_TIMED_USE, "win": technique.SPAR_WIN_EXP,
                "beads": [{"turn": t["turn"], "his": t["master"]["move"], "outcome": t["outcome"], "timed": t["timed"]}
                          for t in s.turns],
                "last": s.turns[-1] if s.turns else None,
                "history": [{"turn": t["turn"], "lines": [t["line"]]} for t in s.turns],
                "over": s.over, "result": s.result}
            return out
