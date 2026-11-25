"""
Gathering herbs on the website: a herb you walk up to out in the world (web/overworld.py, docs/world.md).

The game itself is the bot's: bot/gathering.py (Gathering: next_round, answer, the Wandering Spirit, the streak,
the review flags) and every number in alchemy.py. This module only keeps each player's gathering in memory (one
Gathering per player, so the review clock lasts across the herbs of a walk) and turns a round into the
data the map's gathering panel shows. The herb itself is the one that grew where you knelt: its grade and type were
rolled when it sprouted (web/overworld.py, with the gatherer's own grade odds), and the round is played for it.

The server is the referee: which choice is the real herb never leaves it before the pick, and every round has a
deadline measured on the server. Nothing is drawn as a card here: the browser shows the page and the pictures,
so many players can gather at once.
"""
import io
import threading
import time
from dataclasses import dataclass
from functools import lru_cache

import alchemy
from cards import herbfield, plants

from bot import db, gather_card, gathering, loot

from . import gather_art
from .alchemy_play import GRADE_COLOR, herb_picture
from .forge_play import rich
from .inventory import item_picture
from .profile import number

IDLE_SECONDS = gathering.IDLE_TIMEOUT          # like the bot's panel: the trip ends after 2 idle minutes
SPIRIT_ART = "/art/scenes/gather_wandering_spirit.png"
DUSK_LINE = "🌙 Dusk falls and you head home."
TAKEN_LINE = "🌫️ Someone pulled it free just before you. The light fades from your hands; nothing is lost."
_draw_lock = threading.Lock()                  # the card fonts are not safe to use from several threads at once


def place_art(place):
    return f"/art/scenes/{herbfield.PLACE_ART.get(place, 'gather_misty_slope')}.jpg"


@lru_cache(maxsize=64)
def _plant_png(name):
    with _draw_lock:
        img = plants.plant(name)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


@dataclass
class Session:
    g: gathering.Gathering
    shown_at: float = 0.0           # when the current round went on screen (server clock)
    touched: float = 0.0            # the last thing the player did, for the idle limit
    turn: int = 0                   # bumps on every change, so a stale page can't act twice
    last: tuple = None              # (round, picked key) of the round just answered
    result: str = None
    place: str = ""


class Gathers:
    """Each player's gathering trip (one at a time). Lost if the website restarts, like a bot restart."""

    def __init__(self, clock=time.time):
        self.clock = clock
        self._s = {}
        self._lock = threading.Lock()

    def get(self, uid):
        return self._s.get(uid)

    def clear(self, uid):
        self._s.pop(uid, None)

    def active(self, uid):
        s = self._s.get(uid)
        return s if s and not s.g.over else None

    def start(self, conn, uid, herb=None, rng=None, spirit=True):
        """A round for this herb (grade, type, place), in the player's running gathering or a new one. A round
        already on screen is returned as it is. Returns (session, None) or (None, reason)."""
        self.catch_up(conn, uid)
        with self._lock:
            s = self.active(uid)
            if s and s.g.round is not None:
                return s, None
            p = db.get_player(conn, uid)
            if p is None:
                return None, "No character yet."
            why = gathering.gather_blocked(p, self.clock(), conn)
            if why:
                return None, why
            if s is None:
                s = Session(gathering.Gathering(conn, uid, rng, now=self.clock()))
                self._s[uid] = s
            s.g.conn = conn
            self._new_round(s, herb, spirit)
            return s, None

    def _new_round(self, s, herb=None, spirit=True):
        r = s.g.next_round(herb, spirit)
        if r.kind == "herb":
            s.place = r.place
        s.result, s.last = None, None
        s.shown_at = s.touched = self.clock()
        s.turn += 1

    def _answer(self, s, key, elapsed):
        r = s.g.round
        s.g.found = []
        s.result = s.g.answer(key, elapsed, now=self.clock())
        s.last = (r, key)
        s.g.announce = None                # the website has no channel to announce a rare find in
        s.touched = self.clock()
        s.turn += 1

    def catch_up(self, conn, uid):
        """Time ran out on the round (page closed or too slow), or the player walked away."""
        s = self._s.get(uid)
        if not s or s.g.over:
            return s
        with self._lock:
            s.g.conn = conn
            r, now = s.g.round, self.clock()
            if r and now > s.shown_at + r.seconds + gathering.TIMER_GRACE_SECONDS:
                self._answer(s, None, now - s.shown_at)
                s.touched = s.shown_at + r.seconds          # the idle limit counts from when the round ended
            if not s.g.over and s.g.round is None and now > s.touched + IDLE_SECONDS:
                s.g.over = True
                s.result = DUSK_LINE
                s.last = None
                s.turn += 1
        return s

    def pick(self, conn, uid, key, turn, claim=None):
        """The player's choice. Ignored if it is for an old page or not one of the choices.
        `claim` (a shared herb, web/herb_events.py): called when the pick is right and in time, before anything is
        given; False means someone else pulled it free first, and the round is called off at no cost."""
        s = self.catch_up(conn, uid)
        if not s or s.g.over or s.g.round is None or turn != s.turn:
            return s
        with self._lock:
            r = s.g.round
            if key not in {k for k, _, _ in r.options}:
                return s
            elapsed = self.clock() - s.shown_at
            if claim and r.kind == "herb" and key == r.answer and elapsed <= r.seconds + gathering.TIMER_GRACE_SECONDS \
                    and not claim():
                self.call_off(uid, TAKEN_LINE)
                return s
            self._answer(s, key, elapsed)
        return s

    def call_off(self, uid, line):
        """End the round on screen with nothing won or lost (no streak change, no miss counted)."""
        s = self._s.get(uid)
        if not s or s.g.round is None:
            return s
        r, s.g.round = s.g.round, None
        s.result, s.last = line, (r, None)
        s.touched = self.clock()
        s.turn += 1
        return s

    def stop(self, conn, uid, turn):
        """Walk away from the herb mid-round: it counts as missed, like a timeout."""
        s = self.catch_up(conn, uid)
        if not s or s.g.over or turn != s.turn or s.g.round is None:
            return s
        with self._lock:
            r = s.g.round
            self._answer(s, None, r.seconds + gathering.TIMER_GRACE_SECONDS)
        return s

    def plant_png(self, uid, turn, key):
        """The drawn plant of one choice on the page now showing. Asked for by choice (o0, o1 ...), never by name,
        so the address can't tell which plant it is."""
        s = self._s.get(uid)
        r = s and (s.g.round or (s.last[0] if s.last else None))
        if not r or turn != s.turn or key not in r.names:
            return None
        return _plant_png(r.names[key])


# ── page data ────────────────────────────────────────────────────────

def lines(text):
    return [rich(x.lstrip("> ")) for x in (text or "").split("\n") if x.strip()]


def status_view(g, p):
    mult, nxt = gather_card.streak_bonus(p["herb_streak"])
    return {"hp": number(g.hp), "max_hp": number(g.max_hp), "hp_pct": round(g.hp / max(1, g.max_hp) * 100),
            "streak": p["herb_streak"], "mult": f"{mult:g}" if mult > 1 else None,
            "next": f"×{nxt[1]:g} old herbs at {nxt[0]}" if nxt else None,
            "session": [dict(r, picture=herb_picture_by_name(r["name"])) for r in gather_card.session_rows(g.gathered)],
            "gathered": len(g.gathered), "decoy": gather_card._common(g, p)["decoy_note"]}


@lru_cache(maxsize=64)
def herb_picture_by_name(name):
    for grade, types in alchemy.HERBS.items():
        for t, (n, _) in types.items():
            if n == name:
                return herb_picture(grade, t)
    return None


def play_view(conn, s, now):
    g = s.g
    g.conn = conn
    p = g.player
    r = g.round
    out = {"turn": s.turn, "over": g.over, "status": status_view(g, p), "place": s.place or "the wilds",
           "scene": place_art(s.place), "coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"]),
           "mode": "over" if g.over else "round" if r else "result", "result": lines(s.result)}
    shown = r or (s.last[0] if s.last else None)
    if shown and shown.kind == "herb":
        herb = shown.herb
        d = herb["data"]
        out["target"] = {
            "name": herb["name"], "grade": herb["grade"], "color": GRADE_COLOR[herb["grade"]],
            "type": loot.TYPE_LABEL[d["type"]], "emoji": loot.TYPE_EMOJI[d["type"]],
            "rarity": alchemy.HERB_RARITY[herb["grade"]][0], "old": shown.old,
            "picture": gather_art.choice(herb["name"]) if not r else item_picture(herb),   # the painting: once picked
            "age": d["age"] if shown.old or not r else None,          # a normal herb's age is only known once picked
            "rings": sorted(alchemy.HERB_AGES).index(d["age"]) + 1 if shown.old or not r else None,   # 1-5: 10 ... 1000 years
            "desc": alchemy.HERBS[herb["grade"]][d["type"]][1]}
        picked = s.last[1] if (s.last and not r) else None
        out["choices"] = [{
            # the painting, sent inside the round (no address to read the plant from, nothing to wait for once the
            # clock runs); a plant not painted yet keeps its drawn picture
            "key": k, "no": i + 1, "look": label,
            "picture": gather_art.choice(shown.names[k]) or f"/gather/plant/{s.turn}/{k}.png",
            # only after the pick: which one was real, and the name of each plant
            "state": None if r else "right" if k == shown.answer else "wrong" if k == picked else "",
            "name": None if r else shown.names[k],
        } for i, (k, label, _) in enumerate(shown.options)]
        out["wide"] = len(shown.options) > 4
    elif shown:
        out["spirit"] = {"art": SPIRIT_ART, "sign": shown.shown,
                         "signs": [{"key": k, "emoji": e} for k, _, e in shown.options] if r else []}
    if r:
        out["prompt"] = lines(r.prompt)
        out["seconds"] = r.seconds
        out["left"] = round(max(0.0, s.shown_at + r.seconds - now), 1)
    if not r and s.last and getattr(g, "found", None):       # a spring or a shard of jade found beside the herb
        out["bonus"] = [{"name": i["name"], "picture": item_picture(i), "kind": i["data"]["kind"]} for i in g.found]
    if g.over:
        out["summary"] = out["status"]["session"]
    return out
