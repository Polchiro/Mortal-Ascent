"""
Gathering herbs on the website. docs/web.md, "Gathering".

The game itself is the bot's: bot/gathering.py (Gathering: next_round, answer, the Wandering Spirit, the streak,
the review flags) and every number in alchemy.py. This module only keeps each player's gathering trip in memory
and turns it into page data, the same way web/forge_play.py does for the forge.

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

from .alchemy_play import GRADE_COLOR, herb_picture
from .forge_play import rich
from .inventory import item_picture
from .profile import number

IDLE_SECONDS = gathering.IDLE_TIMEOUT          # like the bot's panel: the trip ends after 2 idle minutes
SPIRIT_ART = "/art/scenes/gather_wandering_spirit.png"
HOME_LINE = "🏮 You shoulder your basket and head home."
DUSK_LINE = "🌙 Dusk falls and you head home."
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

    def start(self, conn, uid, rng=None):
        """Begin a trip (or return the one running). Returns (session, None) or (None, reason)."""
        self.catch_up(conn, uid)
        with self._lock:
            s = self.active(uid)
            if s:
                return s, None
            p = db.get_player(conn, uid)
            if p is None:
                return None, "No character yet."
            why = gathering.gather_blocked(p, self.clock(), conn)
            if why:
                return None, why
            s = Session(gathering.Gathering(conn, uid, rng, now=self.clock()))
            self._s[uid] = s
            self._new_round(s)
            return s, None

    def _new_round(self, s):
        r = s.g.next_round()
        if r.kind == "herb":
            s.place = r.place
        s.result, s.last = None, None
        s.shown_at = s.touched = self.clock()
        s.turn += 1

    def _answer(self, s, key, elapsed):
        r = s.g.round
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

    def pick(self, conn, uid, key, turn):
        """The player's choice. Ignored if it is for an old page or not one of the choices."""
        s = self.catch_up(conn, uid)
        if not s or s.g.over or s.g.round is None or turn != s.turn:
            return s
        with self._lock:
            if key not in {k for k, _, _ in s.g.round.options}:
                return s
            self._answer(s, key, self.clock() - s.shown_at)
        return s

    def again(self, conn, uid, turn):
        s = self.catch_up(conn, uid)
        if not s or s.g.over or s.g.round is not None or turn != s.turn:
            return s
        with self._lock:
            why = gathering.gather_blocked(s.g.player, self.clock(), conn)
            if why:
                s.g.over, s.result, s.last = True, why, None
                s.turn += 1
            else:
                self._new_round(s)
        return s

    def stop(self, conn, uid, turn):
        """Head home. Stopping in the middle of a round counts that round as missed, like a timeout."""
        s = self.catch_up(conn, uid)
        if not s or s.g.over or turn != s.turn:
            return s
        with self._lock:
            r = s.g.round
            if r is not None:
                self._answer(s, None, r.seconds + gathering.TIMER_GRACE_SECONDS)
                s.result = f"{s.result}\n{HOME_LINE}"
            else:
                s.result = (s.result + "\n" if s.result else "") + HOME_LINE
                s.turn += 1
            s.g.over = True
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


def home_view(conn, uid, now):
    """The page before a trip: where things stand and whether gathering is possible."""
    p = db.get_player(conn, uid)
    if p is None:
        return None
    mult, nxt = gather_card.streak_bonus(p["herb_streak"])
    why = gathering.gather_blocked(p, now, conn)
    return {"coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"]),
            "streak": p["herb_streak"], "mult": f"{mult:g}" if mult > 1 else None,
            "next": f"×{nxt[1]:g} old herbs at {nxt[0]}" if nxt else None,
            "total": number(p["herbs_gathered"]), "blocked": rich(why) if why else None,
            "odds": [{"grade": g, "color": GRADE_COLOR[g], "pct": f"{o:.1%}"}
                     for g, o in alchemy.herb_grade_odds(p["realm"]).items()]}


def play_view(conn, s, now):
    g = s.g
    g.conn = conn
    p = g.player
    r = g.round
    out = {"turn": s.turn, "over": g.over, "status": status_view(g, p), "place": s.place or "the misty slope",
           "scene": place_art(s.place), "coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"]),
           "mode": "over" if g.over else "round" if r else "result", "result": lines(s.result)}
    shown = r or (s.last[0] if s.last else None)
    if shown and shown.kind == "herb":
        herb = shown.herb
        d = herb["data"]
        out["target"] = {
            "name": herb["name"], "grade": herb["grade"], "color": GRADE_COLOR[herb["grade"]],
            "type": loot.TYPE_LABEL[d["type"]], "emoji": loot.TYPE_EMOJI[d["type"]],
            "rarity": alchemy.HERB_RARITY[herb["grade"]][0], "old": shown.old, "picture": item_picture(herb),
            "age": d["age"] if shown.old or not r else None,          # a normal herb's age is only known once picked
            "desc": alchemy.HERBS[herb["grade"]][d["type"]][1]}
        picked = s.last[1] if (s.last and not r) else None
        out["choices"] = [{
            "key": k, "no": i + 1, "look": label, "picture": f"/gather/plant/{s.turn}/{k}.png",
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
    if g.over:
        out["summary"] = out["status"]["session"]
    return out
