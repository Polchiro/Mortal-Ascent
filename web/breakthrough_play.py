"""
Breakthrough on the website (docs/web.md "Breakthrough"): the bot's /breakthrough, with the same rules, chance, pill
and Heaven's dew (bot/player.py attempt_breakthrough, bot/crafting.best_breakthrough_pill, bot/materials). Nothing
here decides anything the bot doesn't: the server rolls with the bot's own function, then the page shows what
happened.

It adds only what a page needs around that:
  - the gate's assessment for the page and the player plate (assess, plate): Qi including what passive gathering
    has brought since it was last banked, the chance and what makes it up, what failing costs, what is missing;
  - one attempt per press (Gates.attempt): every assessment hands out a token, and an attempt needs the latest one;
    the same token twice (a double click, a reload) answers the first attempt's result again instead of trying
    again, and the gate is checked again inside the write (another tab, or the bot, may have moved it on);
  - the look of the ceremony: "inner" for a phase bottleneck, "dawn" (Heaven's Light) for the realms up to Martial
    Expert, "storm" (the Heavenly Tribulation) from Martial Master on. The look only: odds and rules are the bot's.

On Discord the best breakthrough pill is used by itself; here it is too, unless the player chooses to keep it.
"""
import secrets
import threading
import time

import training
from bot import crafting, db, loot, materials, passive
from bot import player as rules

from .forge_play import rich
from .inventory import item_picture

DAWN = ("Martial Apprentice", "Martial Warrior", "Martial Expert")     # Heaven's Light; above these, the storm
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]


def look_of(kind, target):
    if kind == "phase":
        return "inner"
    if kind == "realm":
        return "dawn" if target in DAWN else "storm"
    return None


def emblem(realm):
    """What the page draws a realm's lotus emblem from (like the profile's): its number and its petals."""
    i = rules.REALM_ORDER.index(realm)
    return {"roman": ROMAN[i] if i < len(ROMAN) else str(i + 1), "petals": 5 + i, "no": i + 1}


def num(x, digits=0):
    return f"{x:,.{digits}f}"


def now_player(conn, uid, now=None):
    """(player, techniques) with the passive Qi gathered since it was last banked added, as the bot would bank it.
    Only for showing: nothing is written."""
    now = time.time() if now is None else now
    p = db.get_player(conn, uid)
    if p is None:
        return None, []
    techs = db.get_techniques(conn, uid)
    p = dict(p)
    qi, _ = rules.passive_qi(p, techs, now)
    p, _ = rules.add_qi(p, qi, techs, now=now)
    rules.refill_bar(p)
    return p, techs


def plate(p, techs, now=None):
    """The Qi line and Break through button on the player plate (web/overworld.py hero_view)."""
    need = rules.qi_needed(p["realm"], p["layer"])
    kind, target = rules.next_gate(p)
    full = rules.at_full_gate(p)
    out = {"pct": max(0, min(100, round(p["qi"] / max(1, need) * 100))), "qi": num(p["qi"]), "need": num(need),
           "full": bool(full and kind in ("phase", "realm")), "look": look_of(kind, target), "ready": False,
           "label": None, "why": None}
    if not out["full"]:
        return out
    missing = rules.realm_requirement_missing(p, techs, target) if kind == "realm" else None
    if missing:
        out["why"] = "Needs " + missing.replace("**", "")
        return out
    out["ready"] = True
    chance = rules.breakthrough_chance(p) or 0
    out["chance"] = f"{chance:.0%}"
    out["label"] = ("Realm" if kind == "realm" else "Phase") + " · " + out["chance"]
    return out


def assess(conn, uid, now=None):
    """Everything the breakthrough page shows before the attempt, or None without a character."""
    now = time.time() if now is None else now
    p, techs = now_player(conn, uid, now)
    if p is None:
        return None
    need = rules.qi_needed(p["realm"], p["layer"])
    kind, target = rules.next_gate(p)
    full = rules.at_full_gate(p)
    hurt = rules.injured_for(p, now)
    a = {"name": p["name"], "kind": kind, "target": target, "look": look_of(kind, target),
         "realm": p["realm"], "layer": rules.ordinal(p["layer"]), "phase": rules.phase_for(p["layer"]),
         "from": emblem(p["realm"]), "qi": num(p["qi"]), "need": num(need), "pct": min(100, round(p["qi"] / max(1, need) * 100)),
         "waiting": num(rules.overflow(p)) if rules.overflow(p) >= 0.5 else None,
         "full": bool(full), "injured": rules.fmt_duration(hurt) if hurt else None,
         "missing": None, "ready": False, "first": False}
    if kind in ("layer", "peak"):
        a["why"] = ("You stand at the peak of the martial world." if kind == "peak" else
                    "There is no bottleneck ahead of you: layers inside a phase open on their own as Qi fills.")
        return a
    if kind == "realm":
        a["to"] = emblem(target)
        a["title"] = target
        a["sub"] = "1st Layer · Early Phase"
    else:
        a["to"] = emblem(p["realm"])
        a["title"] = f"{target}"
        a["sub"] = f"{p['realm']} · {rules.ordinal(p['layer'] + 1)} Layer"
    if not full:
        a["why"] = f"Your Qi bar is not full yet: {num(p['qi'], 1)} / {num(need)}. Keep gathering."
        return a
    if kind == "realm":
        missing = rules.realm_requirement_missing(p, techs, target)
        if missing:
            a["missing"] = str(rich(missing))
            a["why"] = "Something else is needed first."
            return a
        if hurt:                    # a failed realm breakthrough must heal before the next try (bot/player.py)
            a["why"] = (f"Your meridians are still injured from the last attempt. You can try again in "
                        f"{rules.fmt_duration(hurt)}. A Mending pill heals faster.")
            return a
    base = rules.breakthrough_chance(p) or 0
    a["base"] = f"{base:.0%}"
    pill = crafting.best_breakthrough_pill(conn, uid, p) if rules.pill_helps(p) else None
    art = 0.0
    if kind == "realm" and p["realm"] != "Mortal":
        from bot import gear
        art = gear.artifact_bonus(p, "breakthrough_chance")
        base_only = training.REALM_BREAKTHROUGH_SUCCESS[target]
        a["base"] = f"{base_only:.0%}"
    a["artifact"] = f"+{art:.0%}" if art else None
    a["pill"] = ({"name": pill[0]["name"], "bonus": f"+{pill[1]:.1%}".replace(".0%", "%"),
                  "picture": item_picture(pill[0])} if pill else None)
    a["chance"] = f"{(rules.breakthrough_chance(p, pill[1]) if pill else base):.0%}"
    a["chance_bare"] = f"{base:.0%}"
    a["cap"] = f"{training.BREAKTHROUGH_CHANCE_CAP:.0%}"
    a["capped"] = bool(kind == "realm" and pill and rules.breakthrough_chance(p, pill[1]) >= training.BREAKTHROUGH_CHANCE_CAP)
    a["lose"] = num(p["qi"] * training.BREAKTHROUGH_FAIL_QI_LOSS, 1)
    a["lose_pct"] = f"{training.BREAKTHROUGH_FAIL_QI_LOSS:.0%}"
    a["injury"] = f"{training.INJURY_HOURS} hours" if kind == "realm" else None
    a["first"] = kind == "realm" and p["realm"] == "Mortal"
    a["ready"] = True
    return a


class Gates:
    """One attempt per press, per player: tokens, a lock each, and the last result kept for a reload."""

    def __init__(self, clock=time.time, rng=None):
        self.clock = clock
        self.rng = rng
        self._guard = threading.Lock()
        self._locks = {}
        self._tokens = {}             # uid -> (token, gate_key)
        self._results = {}            # uid -> (token, result)

    def _lock(self, uid):
        with self._guard:
            return self._locks.setdefault(uid, threading.Lock())

    def view(self, conn, uid):
        """The assessment, with a fresh token when the attempt can be made."""
        a = assess(conn, uid, self.clock())
        if a and a.get("ready"):
            p = db.get_player(conn, uid)
            token = secrets.token_urlsafe(12)
            with self._guard:
                self._tokens[uid] = (token, rules.gate_key(p))
            a["token"] = token
        return a

    def last(self, uid):
        r = self._results.get(uid)
        return r[1] if r else None

    def attempt(self, conn, uid, token, keep_pill=False):
        """(result, None) or (None, why). The same token again answers the same result."""
        with self._lock(uid):
            done = self._results.get(uid)
            if done and token and done[0] == token:
                return done[1], None
            held = self._tokens.get(uid)
            if not held or not token or held[0] != token:
                return None, "This page was out of date. Here is how things stand now."
            now = self.clock()
            conn.execute("BEGIN IMMEDIATE")                     # the bot and other tabs wait for this one write
            try:
                passive.bank(conn, uid, now, commit=False)
                p = dict(db.get_player(conn, uid))
                techs = db.get_techniques(conn, uid)
                rules.refill_bar(p)
                if rules.gate_key(p) != held[1]:
                    conn.rollback()
                    return None, "Your cultivation moved on since this page opened. Here is how things stand now."
                before = dict(p)
                kind, target = rules.next_gate(p)
                use = None
                if kind == "realm" and not keep_pill:
                    use = crafting.best_breakthrough_pill(conn, uid, p)
                    if use and not rules.pill_helps(p):
                        use = None
                odds = rules.breakthrough_chance(p, use[1] if use else 0) or 0
                kw = {"bonus": use[1] if use else 0, "now": now}
                if self.rng is not None:
                    kw["rng"] = self.rng
                ok, msg = rules.attempt_breakthrough(p, techs, **kw)
                if ok is None:
                    conn.rollback()
                    return None, msg.replace("**", "")
                fields = rules.progress_fields(p)
                cols = ", ".join(f"{k} = ?" for k in fields)
                conn.execute(f"UPDATE players SET {cols} WHERE user_id = ?", (*fields.values(), uid))
                if use:                                            # used up either way, as on Discord
                    conn.execute("UPDATE items SET qty = qty - 1 WHERE id = ?", (use[0]["id"],))
                    conn.execute("DELETE FROM items WHERE id = ? AND qty <= 0", (use[0]["id"],))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            dew = None
            if ok:
                dew = materials.breakthrough_dew("realm" if p["realm"] != before["realm"] else "phase")
                loot.store(conn, uid, dew)
            result = self._result(before, p, kind, target, ok, odds, use, dew, msg, now)
            with self._guard:
                self._results[uid] = (token, result)
                self._tokens.pop(uid, None)
            return result, None

    def _result(self, before, p, kind, target, ok, odds, use, dew, msg, now):
        need = rules.qi_needed(p["realm"], p["layer"])
        lost = before["qi"] * training.BREAKTHROUGH_FAIL_QI_LOSS if not ok else 0
        hurt = rules.injured_for(p, now) if (not ok and kind == "realm") else 0
        layers = 0
        if ok:
            if kind == "realm":
                layers = p["layer"]
            else:
                layers = p["layer"] - before["layer"]
        lines = [str(rich(line)) for line in msg.split("\n") if line.strip()]
        return {
            "ok": bool(ok), "kind": kind, "look": look_of(kind, target), "target": target,
            "chance": f"{odds:.0%}",
            "before": {"realm": before["realm"], "layer": rules.ordinal(before["layer"]),
                       "qi": num(before["qi"], 1), "emblem": emblem(before["realm"])},
            "after": {"realm": p["realm"], "layer": rules.ordinal(p["layer"]), "phase": rules.phase_for(p["layer"]),
                      "qi": num(p["qi"], 1), "need": num(need), "pct": min(100, round(p["qi"] / max(1, need) * 100)),
                      "waiting": num(rules.overflow(p)) if rules.overflow(p) >= 0.5 else None,
                      "emblem": emblem(p["realm"])},
            "realm_up": p["realm"] != before["realm"],
            "layers": layers,
            "lost": num(lost, 1) if lost else None,
            "injury": rules.fmt_duration(hurt) if hurt else None,
            "pill": use[0]["name"] if use else None,
            "dew": [{"name": d["name"], "qty": d.get("qty", 1), "picture": item_picture(d)} for d in (dew or [])],
            "lines": lines,
        }
