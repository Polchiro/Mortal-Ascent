"""
Hunting parties on the website (docs/hunting.md): create, find, join, the lobby, and who may do what.

Every rule is checked here, on the server, under one lock: the size cap, one party per player, the invitation ID,
the leader's rights. The page only shows what this module allows. Parties live in the website's memory, like a
forge or an expedition in progress, so a website restart ends them (nothing is lost: loot is only ever banked
in the database).

A player who stops answering is handled without breaking the party: in the lobby a member unseen for
PRESENCE_SECONDS is removed (the leader too, and the next member leads); a party left empty is gone.
"""
import re
import secrets
import threading
import time
from dataclasses import dataclass, field

import hunting

from bot import db

PRESENCE_SECONDS = 180            # a lobby page polls every few seconds; three silent minutes and you are out
NAME_MIN, NAME_MAX = 3, 24
CODE_LEN = 6
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"     # no 0/O, 1/I: easy to read out to a friend
CODE_TRIES = 10                   # wrong invitation IDs per player ...
CODE_WINDOW = 600                 # ... in this many seconds, then a pause (nobody can guess IDs by brute force)
NAME_OK = re.compile(r"^[\w .,'!?&\-]+$", re.UNICODE)


@dataclass
class Member:
    uid: int
    joined: float
    seen: float
    ready: bool = False


@dataclass
class Party:
    id: str                       # internal handle (in URLs), never the invitation ID
    name: str
    public: bool
    leader: int
    members: list                 # [Member], in the order they joined (the next leader is the oldest)
    code: str = None              # invitation ID (private parties only)
    location: str = None          # hunting.LOCATIONS key, chosen by the leader
    solo: bool = False            # Solo Hunt: a party of one that nobody else can see or join
    hunting: bool = False         # an expedition is under way (web/hunt_play.py)
    version: int = 0              # bumps on every change: lobby pages reload when it moves
    created: float = field(default_factory=time.time)

    def uids(self):
        return [m.uid for m in self.members]

    def member(self, uid):
        return next((m for m in self.members if m.uid == uid), None)

    @property
    def full(self):
        return len(self.members) >= hunting.MAX_PARTY


class Parties:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.RLock()
        self._p = {}              # id → Party
        self._of = {}             # uid → party id (one party per player)
        self._codes = {}          # invitation ID → party id
        self._fails = {}          # uid → [times of wrong invitation IDs]

    # ── reading ─────────────────────────────────────────────────────

    def of(self, uid):
        with self.lock:
            pid = self._of.get(uid)
            return self._p.get(pid) if pid else None

    def get(self, pid):
        return self._p.get(pid)

    def public(self):
        """Parties shown in the browser: public, still in the lobby, newest first (full ones too, marked full)."""
        with self.lock:
            self.sweep()
            return sorted((p for p in self._p.values() if p.public and not p.solo and not p.hunting),
                          key=lambda p: -p.created)

    # ── making and joining ──────────────────────────────────────────

    def create(self, conn, uid, name, public, solo=False):
        """(party, None) or (None, why not)."""
        with self.lock:
            self.sweep()
            if db.get_player(conn, uid) is None:
                return None, "No character yet."
            if uid in self._of:
                return None, "You are already in a hunting party. Leave it first."
            if solo:
                name = "Solo Hunt"
            else:
                name = " ".join((name or "").split())
                if not NAME_MIN <= len(name) <= NAME_MAX:
                    return None, f"A party name is {NAME_MIN} to {NAME_MAX} characters."
                if not NAME_OK.match(name):
                    return None, "Use letters, numbers, spaces and simple punctuation in the name."
            now = self.clock()
            pid = secrets.token_urlsafe(9)
            p = Party(pid, name, bool(public) and not solo, uid, [Member(uid, now, now)], solo=solo, created=now)
            if not p.public and not solo:
                self._new_code(p)
            self._p[pid] = p
            self._of[uid] = pid
            return p, None

    def join_public(self, conn, uid, pid):
        with self.lock:
            self.sweep()
            p = self._p.get(pid)
            if p is None or not p.public or p.solo:
                return None, "That party is gone."
            return self._join(conn, uid, p)

    def join_code(self, conn, uid, code):
        with self.lock:
            self.sweep()
            now = self.clock()
            fails = [t for t in self._fails.get(uid, []) if now - t < CODE_WINDOW]
            self._fails[uid] = fails
            if len(fails) >= CODE_TRIES:
                return None, "Too many wrong invitation IDs. Wait a few minutes and try again."
            code = re.sub(r"[^A-Z0-9]", "", (code or "").upper())
            pid = self._codes.get(code)
            p = self._p.get(pid) if pid else None
            if p is None:
                fails.append(now)
                return None, "No party has that invitation ID. Check it with your friend; the leader may have made a new one."
            return self._join(conn, uid, p)

    def _join(self, conn, uid, p):
        player = db.get_player(conn, uid)
        if player is None:
            return None, "No character yet."
        if uid in p.uids():
            return p, None                                    # already in: nothing to do
        if uid in self._of:
            return None, "You are already in a hunting party. Leave it first."
        if p.hunting:
            return None, "That party is already out hunting. Nobody can join halfway."
        if p.full:
            return None, f"That party is full ({hunting.MAX_PARTY} / {hunting.MAX_PARTY})."
        loc = hunting.location(p.location) if p.location else None
        if loc:
            why = hunting.eligible(player, loc)
            if why:
                return None, f"You can't join: {loc['name']} is for {hunting.requirement(loc)}."
        now = self.clock()
        p.members.append(Member(uid, now, now))
        self._of[uid] = p.id
        self._bump(p)
        return p, None

    # ── leaving ─────────────────────────────────────────────────────

    def leave(self, uid):
        """Leave your party (the hunt itself is left through web/hunt_play.py first)."""
        with self.lock:
            p = self.of(uid)
            if p is None:
                return
            self._remove(p, uid)

    def kick(self, uid, target):
        with self.lock:
            p = self.of(uid)
            if p is None or p.leader != uid:
                return "Only the leader can remove members."
            if p.hunting:
                return "Not during a hunt."
            if target == uid or target not in p.uids():
                return "That player is not in your party."
            self._remove(p, target)
            return None

    def disband(self, uid):
        with self.lock:
            p = self.of(uid)
            if p is None or p.leader != uid:
                return "Only the leader can disband the party."
            if p.hunting:
                return "Not during a hunt. Return home first."
            self._drop(p)
            return None

    def _remove(self, p, uid):
        p.members = [m for m in p.members if m.uid != uid]
        self._of.pop(uid, None)
        if not p.members:
            self._drop(p)
            return
        if p.leader == uid:
            p.leader = p.members[0].uid                       # the longest-standing member leads now
            p.members[0].ready = False
        self._bump(p)

    def _drop(self, p):
        for m in p.members:
            self._of.pop(m.uid, None)
        if p.code:
            self._codes.pop(p.code, None)
        self._p.pop(p.id, None)
        p.members = []
        p.version += 1

    # ── the lobby ───────────────────────────────────────────────────

    def seen(self, uid):
        """A page of this player's party was just shown or polled: they are still here."""
        with self.lock:
            p = self.of(uid)
            m = p.member(uid) if p else None
            if m:
                m.seen = self.clock()
            return p

    def set_ready(self, uid, ready):
        with self.lock:
            p = self.of(uid)
            if p is None or p.hunting:
                return
            m = p.member(uid)
            if m and m.ready != bool(ready):
                m.ready = bool(ready)
                self._bump(p)

    def set_location(self, conn, uid, key):
        with self.lock:
            p = self.of(uid)
            if p is None or p.leader != uid:
                return "Only the leader chooses where to hunt."
            if p.hunting:
                return "Not during a hunt."
            loc = hunting.location(key)
            if loc is None:
                return "No such place."
            why = hunting.eligible(db.get_player(conn, uid), loc)
            if why:
                return f"You can't lead a hunt there: {loc['name']} is for {hunting.requirement(loc)}."
            if p.location != key:
                p.location = key
                for m in p.members:
                    m.ready = False                           # a new destination: everyone confirms again
                self._bump(p)
            return None

    def set_public(self, uid, public):
        with self.lock:
            p = self.of(uid)
            if p is None or p.leader != uid or p.solo:
                return "Only the leader can change who may join."
            public = bool(public)
            if p.public != public:
                p.public = public
                if public and p.code:
                    self._codes.pop(p.code, None)
                    p.code = None
                elif not public:
                    self._new_code(p)
                self._bump(p)
            return None

    def new_code(self, uid):
        """A fresh invitation ID; the old one stops working at once."""
        with self.lock:
            p = self.of(uid)
            if p is None or p.leader != uid or p.public or p.solo:
                return "Only the leader of a private party can make a new invitation ID."
            self._new_code(p)
            self._bump(p)
            return None

    def _new_code(self, p):
        if p.code:
            self._codes.pop(p.code, None)
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LEN))
            if code not in self._codes:
                break
        p.code = code
        self._codes[code] = p.id

    def start_problems(self, conn, p, blocked):
        """Everything that stops this party setting out, as a list of short lines (empty: ready to go).
        `blocked(conn, uid)` gives an injury or rest reason, or None (web/hunt_play.py)."""
        out = []
        loc = hunting.location(p.location) if p.location else None
        if loc is None:
            out.append("Choose where to hunt.")
        for m in p.members:
            player = db.get_player(conn, m.uid)
            if player is None:
                out.append("A member has no character.")
                continue
            if loc:
                why = hunting.eligible(player, loc)
                if why:
                    out.append(why)
            why = blocked(conn, m.uid)
            if why:
                out.append(f"{player['name']}: {why}")
            if m.uid != p.leader and not m.ready:
                out.append(f"{player['name']} is not ready.")
        return out

    # ── housekeeping ────────────────────────────────────────────────

    def sweep(self):
        """Members who left the lobby without a word (closed the tab, lost the connection) are taken out."""
        with self.lock:
            now = self.clock()
            for p in list(self._p.values()):
                if p.hunting:
                    continue                                  # in a hunt the turn timers deal with silence
                for m in list(p.members):
                    if now - m.seen > PRESENCE_SECONDS:
                        self._remove(p, m.uid)

    def _bump(self, p):
        p.version += 1
