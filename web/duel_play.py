"""
Duels at the Arena on the website (docs/pvp.md "On the website", /arena and /duel).

Nothing here is a new rule: a duel is bot/duel.Duel (the fair duel, the counters, rising intensity, the turn limit,
three timeouts = forfeit), saved by db.save_duel (which counts the win and loss for the Stele's Duels board) and
followed by the bot's one-minute cooldown for the pair. Friendly: nothing is won or lost.

How two players meet:
  • a challenge by name: the challenged player sees it in the Arena for CHALLENGE_SECONDS and accepts or declines;
  • the queue: "Find a match" waits for anyone else waiting, and the first two are paired.

The server referees, as for team hunts: both pick in secret, the turn resolves when both have picked, or when
TURN_SECONDS run out (whoever hasn't picked Guards). Pages poll `version` and fetch the state when it changes.
Duels live in this process's memory, like hunts: a restart ends them (nothing is saved until a duel ends).
"""
import random
import threading
import time
from dataclasses import dataclass, field

import looks
import pvp

from bot import db
from bot import duel as rules
from bot import player as players

CHALLENGE_SECONDS = pvp.ACCEPT_SECONDS     # a challenge waits this long for an answer
TURN_SECONDS = 20                          # the bot's 15, plus a little for the web round trip
GONE_SECONDS = 120                         # a finished duel stays on screen this long, or until you leave it
ARENA = "/art/scenes/arena_ruins.jpg"
HINT = {"strike": "Beats Break. Into a Guard it is blocked. Same move: both hit at half.",
        "guard": "Beats Strike. A Break smashes through it and staggers you: +25% damage next turn.",
        "break": "Beats Guard and staggers them. Into a Strike it misses. Same move: both hit at half."}


def _move(s, key):
    """One of your buttons: Strike, Guard, Break, or a technique (shown in the Techniques menu)."""
    t = s.tech(key) if key in rules.TECH_KEYS else None
    icon = f"/art/icons/actions/{key}.webp"
    if t:
        from bot.sheet.data import tech_kind
        from .profile import art_url
        icon = art_url(tech_kind(t["name"], players.TECH_BY_NAME.get(t["name"], {}).get("school", "Body"))) or \
            f"/art/icons/actions/{t['type']}_tech.webp"
    cd = s.cooldowns.get(key, 0) if t else 0
    cost = s.qi_cost(key)
    state = (f"{cost} Battle Qi" + (f" · ready in {cd} turn{'s' if cd != 1 else ''}" if cd
                                   else " · not enough" if s.bqi < cost else "")) if t else ""
    as_ = "a Strike" if s.base(key) == "strike" else "a Guard"
    return {"key": key, "label": t["name"] if t else rules.MOVE_LABEL[key], "icon": icon, "ready": s.ready(key),
            "tech": bool(t), "kind": {"attack": "Attack technique", "defense": "Defense technique"}.get(t["type"], "")
            if t else "", "state": state,
            "info": f"{t['name']}: counts as {as_}, with its effects. Costs {cost} Battle Qi and recovers for a few "
                    "turns after." if t else HINT[key]}


@dataclass
class Match:
    duel: object
    started: float
    deadline: float
    looks: dict                     # uid → look (for the fighter pictures)
    v: int = 1
    turns: list = field(default_factory=list)      # per resolved turn: what each side did, for the page to act out
    ended: float = 0.0
    left: set = field(default_factory=set)          # who has left the result screen


class Arena:
    def __init__(self, clock=time.time, rng=None):
        self.clock = clock
        self.rng = rng or random.Random()
        self.lock = threading.RLock()
        self.challenges = {}        # challenger uid → (target uid, until)
        self.queue = {}             # uid → since
        self.matches = {}           # uid → Match (both players point at the same one)
        self.v = {}                 # uid → their arena page's version (bumps when what they see changes)

    # ── versions ─────────────────────────────────────────────────────

    def _bump(self, *uids):
        for u in uids:
            self.v[u] = self.v.get(u, 0) + 1

    def version(self, conn, uid):
        """What the pages poll: the arena's number, the duel's number and the seconds left this turn."""
        with self.lock:
            self.tick(conn)
            m = self.matches.get(uid)
            out = {"a": self.v.get(uid, 0), "d": m.v if m else None, "live": self.busy(uid)}
            if m and not m.duel.over:
                out["left"] = max(0, round(m.deadline - self.clock()))
            return out

    # ── time passing ─────────────────────────────────────────────────

    def tick(self, conn):
        """Expire challenges, resolve turns whose time is up, forget long-finished duels."""
        now = self.clock()
        for c, (t, until) in list(self.challenges.items()):
            if until <= now:
                del self.challenges[c]
                self._bump(c, t)
        for m in {id(m): m for m in self.matches.values()}.values():
            if not m.duel.over and now >= m.deadline:
                self._resolve(conn, m)
            elif m.duel.over and now >= m.ended + GONE_SECONDS:
                for d in m.duel.sides:
                    self._leave(d.uid, m)

    # ── who may duel ─────────────────────────────────────────────────

    def busy(self, uid):
        return uid in self.matches and not self.matches[uid].duel.over

    def why_not(self, conn, uid, other=None):
        """Why `uid` can't duel (`other`) now, or None."""
        p = db.get_player(conn, uid)
        if p is None:
            return "You have no character yet."
        hurt = players.injured_for(p, self.clock())
        if hurt:
            return f"You are injured for {players.fmt_duration(hurt)}."
        if self.busy(uid):
            return "You are already in a duel."
        if other is not None:
            wait = db.cooldown_left(conn, uid, f"duel:{other}", self.clock())
            if wait:
                return f"You fought them a moment ago: wait {players.fmt_duration(wait)}."
        return None

    # ── challenges ───────────────────────────────────────────────────

    def challenge(self, conn, uid, name):
        """Challenge the player called `name`. Returns None, or why not."""
        with self.lock:
            self.tick(conn)
            name = (name or "").strip()
            if not name:
                return "Write the name of the cultivator you want to challenge."
            row = conn.execute("SELECT user_id FROM players WHERE name = ? COLLATE NOCASE", (name,)).fetchone()
            if row is None:
                return f"No cultivator is called {name}."
            target = row["user_id"]
            if target == uid:
                return "You can't challenge yourself."
            why = self.why_not(conn, uid, target)
            if why:
                return why
            them = db.get_player(conn, target)
            if self.busy(target):
                return f"{them['name']} is in a duel right now."
            if players.injured_for(them, self.clock()):
                return f"{them['name']} is injured."
            self.queue.pop(uid, None)
            self.challenges[uid] = (target, self.clock() + CHALLENGE_SECONDS)
            self._bump(uid, target)
            return None

    def withdraw(self, uid):
        with self.lock:
            c = self.challenges.pop(uid, None)
            if c:
                self._bump(uid, c[0])

    def answer(self, conn, uid, challenger, accept):
        """Accept or decline `challenger`'s challenge. Returns None, or why not."""
        with self.lock:
            self.tick(conn)
            c = self.challenges.get(challenger)
            if not c or c[0] != uid:
                return "That challenge has expired."
            del self.challenges[challenger]
            self._bump(uid, challenger)
            if not accept:
                return None
            why = self.why_not(conn, uid, challenger) or (self.why_not(conn, challenger, uid) and
                                                         "They can't duel right now.")
            if why:
                return why
            self._start(conn, challenger, uid)
            return None

    # ── the queue ────────────────────────────────────────────────────

    def join_queue(self, conn, uid):
        with self.lock:
            self.tick(conn)
            why = self.why_not(conn, uid)
            if why:
                return why
            self.withdraw(uid)
            other = next((u for u in sorted(self.queue, key=self.queue.get) if u != uid and not self.busy(u)
                          and not db.cooldown_left(conn, uid, f"duel:{u}", self.clock())), None)
            if other is None:
                self.queue[uid] = self.clock()
                self._bump(uid)
                return None
            del self.queue[other]
            self.queue.pop(uid, None)
            self._start(conn, other, uid)
            return None

    def leave_queue(self, uid):
        with self.lock:
            if self.queue.pop(uid, None) is not None:
                self._bump(uid)

    # ── a duel ───────────────────────────────────────────────────────

    def _start(self, conn, a, b):
        def side(uid):
            return (db.get_player(conn, uid), db.get_techniques(conn, uid), db.equipped_weapon(conn, uid),
                    db.equipped_armor(conn, uid))
        p1, t1, w1, ar1 = side(a)
        p2, t2, w2, ar2 = side(b)
        duel = rules.start(p1, t1, w1, p2, t2, w2, rng=self.rng, armor1=ar1, armor2=ar2)
        now = self.clock()
        m = Match(duel, now, now + TURN_SECONDS, {a: looks.of_player(p1), b: looks.of_player(p2)})
        for u in (a, b):
            self.queue.pop(u, None)
            self.challenges.pop(u, None)
            old = self.matches.get(u)
            if old is not None:
                old.left.add(u)
            self.matches[u] = m
        for c, (t, _) in list(self.challenges.items()):     # challenges to either of them are off
            if t in (a, b):
                del self.challenges[c]
                self._bump(c)
        db.set_cooldown(conn, a, f"duel:{b}", pvp.PAIR_COOLDOWN_SECONDS, now)
        db.set_cooldown(conn, b, f"duel:{a}", pvp.PAIR_COOLDOWN_SECONDS, now)
        self._bump(a, b)

    def pick(self, conn, uid, choice, turn):
        """Lock in this turn's move. Returns None, or why not."""
        with self.lock:
            self.tick(conn)
            m = self.matches.get(uid)
            if m is None or m.duel.over:
                return "The duel is over."
            if turn is not None and turn != m.duel.turn:
                return None                                  # a late press for a turn already played
            why = m.duel.choose(uid, choice)
            if why:
                return why.replace("**", "")
            m.v += 1
            if m.duel.both_picked():
                self._resolve(conn, m)
            return None

    def flee(self, conn, uid):
        with self.lock:
            m = self.matches.get(uid)
            if m is None or m.duel.over:
                return
            m.duel.forfeit(uid)
            m.turns.append({"turn": m.duel.turn, "fled": uid, "lines": [t for _, t in m.duel.log]})
            self._end(conn, m)

    def _resolve(self, conn, m):
        d = m.duel
        before = {s.uid: s.hp for s in d.sides}
        turn = d.turn
        d.resolve()
        entry = {"turn": turn, "lines": [t for _, t in d.log], "moves": {}}
        if d.history and d.history[-1]["turn"] == turn:
            for mv in d.history[-1]["moves"]:
                s = d.duelist(mv["user_id"])
                entry["moves"][mv["user_id"]] = {"move": mv["move"], "label": s.last_move or mv["move"],
                                                 "base": rules.BASE_MOVE.get(mv["move"], "guard"),
                                                 "dealt": mv["damage"], "lost": round(before[s.uid] - s.hp),
                                                 "timed_out": mv["timed_out"]}
        m.turns.append(entry)
        if d.over:
            self._end(conn, m)
        else:
            m.deadline = self.clock() + TURN_SECONDS
            m.v += 1

    def _end(self, conn, m):
        m.ended = self.clock()
        db.save_duel(conn, m.duel, started_at=m.started, now=m.ended)
        a, b = (s.uid for s in m.duel.sides)
        db.set_cooldown(conn, a, f"duel:{b}", pvp.PAIR_COOLDOWN_SECONDS, m.ended)
        db.set_cooldown(conn, b, f"duel:{a}", pvp.PAIR_COOLDOWN_SECONDS, m.ended)
        m.v += 1
        self._bump(a, b)

    def done(self, uid):
        """Leave a finished duel's result screen."""
        with self.lock:
            m = self.matches.get(uid)
            if m is not None and m.duel.over:
                self._leave(uid, m)

    def _leave(self, uid, m):
        m.left.add(uid)
        if self.matches.get(uid) is m:
            del self.matches[uid]
            self._bump(uid)

    # ── what the pages show ──────────────────────────────────────────

    def lobby(self, conn, uid):
        """The Arena page: your challenges both ways, the queue, and whether a duel is on."""
        with self.lock:
            self.tick(conn)
            now = self.clock()

            def who(u):
                p = db.get_player(conn, u)
                return {"id": u, "name": p["name"], "realm": p["realm"], "layer": p["layer"],
                        "won": p["duels_won"], "lost": p["duels_lost"]}
            mine = self.challenges.get(uid)
            p = db.get_player(conn, uid)
            return {
                "me": who(uid), "in_duel": self.busy(uid),
                "outgoing": {**who(mine[0]), "left": max(0, round(mine[1] - now))} if mine else None,
                "incoming": [{**who(c), "left": max(0, round(until - now))}
                             for c, (t, until) in sorted(self.challenges.items(), key=lambda kv: kv[1][1]) if t == uid],
                "queued": uid in self.queue, "waiting": len([u for u in self.queue if u != uid]),
                "hurt": players.fmt_duration(players.injured_for(p, now)) if players.injured_for(p, now) else None,
                "names": [r["name"] for r in conn.execute(
                    "SELECT name FROM players WHERE user_id != ? ORDER BY name COLLATE NOCASE LIMIT 500", (uid,))],
            }

    def state(self, conn, uid):
        """The duel as `uid` sees it (never what the other player picked this turn), or None."""
        with self.lock:
            self.tick(conn)
            m = self.matches.get(uid)
            if m is None:
                return None
            d = m.duel
            me = d.duelist(uid)
            them = d.other(me)

            def side(s, mine):
                look = m.looks[s.uid]
                out = {"uid": s.uid, "name": s.name, "hp": round(s.hp), "max_hp": round(s.max_hp),
                       "bqi": round(s.bqi), "max_bqi": round(s.max_bqi),
                       "locked": d.locked(s), "staggered": s.staggered,
                       "poses": {p: looks.fighter(look, p) for p in ("idle", "windup", "strike", "guard")},
                       "isheet": looks.idle_sheet(look)}
                out["face"] = looks.face(look)
                out["realm"] = f"{s.realm} · Layer {s.layer}"
                if mine:
                    out["pick"] = s.move_label(s.pick) if s.pick else None
                    out["moves"] = [_move(s, k) for k in rules.CHOICES if k not in rules.TECH_KEYS or s.tech(k)]
                return out
            fair = f"{d.fair[0]}, {players.ordinal(d.fair[1])} layer" if d.fair else ""
            out = {"v": m.v, "turn": d.turn, "max_turns": pvp.MAX_TURNS, "fair": fair, "arena": ARENA,
                   "intensity": d.intensity(), "me": side(me, True), "them": side(them, False),
                   "left": max(0, round(m.deadline - self.clock())) if not d.over else 0,
                   "seconds": TURN_SECONDS, "last": m.turns[-1] if m.turns else None, "over": d.over,
                   "history": [{"turn": t["turn"], "lines": t["lines"]} for t in m.turns]}
            if d.over:
                out["result"] = {"won": d.winner is me, "draw": d.winner is None, "reason": d.reason,
                                 "winner": d.winner.name if d.winner else None, "turns": len(d.history)}
            return out
