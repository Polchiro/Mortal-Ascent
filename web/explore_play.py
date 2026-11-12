"""
Exploring and fighting on the website. docs/web.md, "Explore".

The game is the bot's: bot/expedition.py (the five steps, the encounters, the loot, finish), bot/fight.py (every
turn of a fight) and bot/hunt.py (a lair hunted alone, as in a DM with the bot). This module only keeps each
player's expedition in memory, keeps the clocks on the server, and turns the state into page data.

The server referees: the beast's next move is only shown as the bot shows it (its warning bar); each fight turn,
hazard and idle limit has a deadline measured here. A page that comes back late (or never) gets what the bot
does when its timer runs out: Guard in a fight (three in a row: flee), a failed leap from a hazard, and after two
idle minutes the walk home.
"""
import threading
import time
from dataclasses import dataclass, field

import battle as battle_rules
import explore as explore_rules

from bot import combat, crafting, db, hunt
from bot import player as rules
from bot.expedition import TIMER_GRACE_SECONDS as HAZARD_GRACE, Expedition
from bot.fight_view import GRACE_SECONDS as TURN_GRACE, TIER_LABEL, describe
from cards.scenes import REGION
from bot.explore_card import REGION_BY_TIER

from .forge_play import rich
from .profile import number

IDLE_SECONDS = 120                      # like the bot's expedition panel (views.PANEL_IDLE_SECONDS)
MAX_TIMEOUTS = 200
ACTIONS = ("strike", "attack_tech", "defense_tech", "pill", "guard", "break", "flee")   # keys 1-7
ACTION_LABEL = {"strike": "Strike", "attack_tech": "Attack technique", "defense_tech": "Defense technique",
                "pill": "Mending Pill", "guard": "Guard", "break": "Break", "flee": "Flee"}
PATH_LABEL = {"left": "Left", "middle": "Ahead", "right": "Right"}
FIGHTER = "/art/portraits/fighter_stance.webp"
FACE = "/art/portraits/cultivator_default.webp"
ARENA = "/art/scenes/arena_ruins.jpg"


@dataclass
class Run:
    exp: Expedition
    choosing: bool = True               # the three paths are showing
    merchant_step: int = None
    turn: int = 0                       # bumps on every change: a stale page can't act twice
    touched: float = 0.0                # the last thing the player did (idle limit)
    turn_started: float = 0.0           # when the current fight turn began (its timer)
    prev: dict = None                   # HP before the last fight turn, for the damage numbers
    notice: str = None
    lair_battle: object = None          # a lair hunted alone (bot/hunt.py), after the expedition
    lair_result: list = None
    lair_won: str = None
    started: float = field(default_factory=time.time)

    @property
    def battle(self):
        return self.lair_battle if self.lair_battle is not None and self.lair_result is None else self.exp.battle


class Explores:
    """Each player's expedition (one at a time). Lost if the website restarts, like a bot restart."""

    def __init__(self, clock=time.time, rng_factory=None):
        self.clock = clock
        self.rng_factory = rng_factory
        self._s = {}
        self._lock = threading.Lock()

    def get(self, uid):
        return self._s.get(uid)

    def clear(self, uid):
        self._s.pop(uid, None)

    # ── starting ────────────────────────────────────────────────────

    def blocked(self, conn, uid, now=None):
        """Why this player can't set out now, or None (the same checks as /explore)."""
        now = self.clock() if now is None else now
        p = db.get_player(conn, uid)
        if p is None:
            return "No character yet."
        hurt = rules.injured_for(p, now)
        if hurt:
            return f"🩹 You are still injured. Rest for **{rules.fmt_duration(hurt)}** before exploring again."
        wait = db.cooldown_left(conn, uid, "explore", now)
        if wait:
            return f"🦶 Your legs still ache from the last expedition. Explore again in **{rules.fmt_duration(wait)}**."
        return None

    def start(self, conn, uid):
        """Set out. The cooldown starts now and is saved, so Discord can't start a second one meanwhile."""
        with self._lock:
            s = self._s.get(uid)
            if s and not self._finished(s):
                return s, None
            why = self.blocked(conn, uid)
            if why:
                return None, why
            now = self.clock()
            db.set_cooldown(conn, uid, "explore", explore_rules.EXPLORE_COOLDOWN_MINUTES * 60, now)
            exp = Expedition(conn, uid, self.rng_factory() if self.rng_factory else None)
            exp.next_step()
            s = Run(exp, touched=now)
            self._s[uid] = s
            return s, None

    @staticmethod
    def _finished(s):
        return s.exp.over and (s.lair_battle is None or s.lair_result is not None)

    # ── clocks ──────────────────────────────────────────────────────

    def catch_up(self, conn, uid):
        """Everything whose time ran out: fight turns, a hazard, an idle expedition."""
        s = self._s.get(uid)
        if not s:
            return None
        with self._lock:
            s.exp.conn = conn
            now = self.clock()
            b = s.battle
            n = 0
            while b is not None and not b.over and now > s.turn_started + battle_rules.TURN_SECONDS + TURN_GRACE \
                    and n < MAX_TIMEOUTS:
                missed = s.turn_started + battle_rules.TURN_SECONDS
                self._resolve(conn, s, b)                    # nobody picked: the engine plays Guard
                s.turn_started = missed + TURN_GRACE
                n += 1
                b = s.battle
            e = s.exp
            if e.pending == "hazard" and e.hazard["shown_at"] is not None and \
                    now > e.hazard["shown_at"] + e.hazard["seconds"] + HAZARD_GRACE:
                e.dodge(None, now=now)                       # too slow
                s.turn += 1
                s.touched = now
            if not e.over and s.battle is None and now > s.touched + IDLE_SECONDS:
                e.story = ["You lingered too long; night falls and you head home."]
                e.finish(now=now)
                s.turn += 1
        return s

    def seen(self, uid):
        """The page with a hazard is on screen: its 3-second clock starts now (like the bot after it shows it)."""
        s = self._s.get(uid)
        if s and s.exp.pending == "hazard" and s.exp.hazard["shown_at"] is None:
            s.exp.hazard["shown_at"] = self.clock()

    # ── the player's choices ────────────────────────────────────────

    def act(self, conn, uid, what, arg, turn):
        """One button press. Ignored when it is for an old page or not possible now."""
        s = self.catch_up(conn, uid)
        if not s or turn != s.turn:
            return s
        with self._lock:
            e, now = s.exp, self.clock()
            s.notice = None
            b = s.battle
            if what == "move":
                if b is None or b.over or arg not in ACTIONS:
                    return s
                why = b.choose(uid, arg)
                if why:
                    s.notice = why
                    s.turn += 1
                    return s
                self._resolve(conn, s, b)
                s.touched = now
                return s
            if b is not None:
                return s                                     # only fight buttons while fighting
            if what == "path" and not e.over and s.choosing and arg in e.paths:
                enc = e.paths[arg][0]
                e.choose(arg)
                s.choosing = False
                if enc == "wandering_merchant":
                    s.merchant_step = e.step
                self._fight_began(s)
            elif what == "deeper" and e.can_go_deeper and not s.choosing:
                e.next_step()
                s.choosing = True
            elif what == "return" and not e.over and e.pending is None:
                e.story = ["You head back the way you came, loot in hand."]
                e.finish(now=now)
            elif what == "dodge" and e.pending == "hazard" and arg in explore_rules.PATHS:
                e.dodge(arg, now=now)
            elif what == "help" and e.pending == "stranger" and arg in ("coins", "hp", "leave"):
                e.help_stranger(arg)
                self._fight_began(s)
            elif what == "buy" and e.merchant and s.merchant_step == e.step and arg in ("pill", "herb") \
                    and not e.over and not s.choosing:
                s.notice = e.buy(arg)
            elif what == "hunt" and e.over and e.lair and s.lair_battle is None:
                why = self.lair_problem(conn, uid, e.lair, now)
                if why:
                    s.notice = why
                else:
                    s.lair_battle = hunt.start_battle(conn, e.lair, [uid])
                    s.turn_started, s.prev = now, None
            else:
                return s
            s.turn += 1
            s.touched = now
        return s

    def lair_problem(self, conn, uid, lair, now):
        if now > lair["closes"]:
            return f"The {lair['beast'][0]} has moved on. The lair is empty."
        return hunt.can_join(db.get_player(conn, uid), now)

    def _fight_began(self, s):
        if s.exp.pending == "fight":
            s.turn_started, s.prev = self.clock(), None

    def _resolve(self, conn, s, b):
        s.prev = {"enemy": round(b.enemy["hp"]), "me": round(b.fighters[0].hp)}
        b.resolve()
        for f in b.fighters:
            crafting.bank_fight_pills(conn, f)
        s.turn += 1
        s.turn_started = self.clock()
        if b.over:
            if b is s.lair_battle:
                lines, _news = hunt.pay(conn, s.exp.lair, b)     # the website has no channel to announce in
                s.lair_result, s.lair_won = lines, b.result
            else:
                s.exp.end_fight()
                s.choosing = False


# ── page data ────────────────────────────────────────────────────────

def lines(items):
    return [rich(x) for x in items if x]


def region(exp):
    name = REGION_BY_TIER.get(exp.tier, "The Wilds")
    return name, f"/art/scenes/{REGION.get(name, 'region_bamboo_forest')}.jpg"


def home_view(conn, uid, explores):
    p = db.get_player(conn, uid)
    if p is None:
        return None
    import challenges
    name = REGION_BY_TIER.get(challenges.REALM_TIER[p["realm"]], "The Wilds")
    return {"coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"]), "region": name,
            "scene": f"/art/scenes/{REGION.get(name, 'region_bamboo_forest')}.jpg",
            "blocked": rich(explores.blocked(conn, uid) or "") or None, "steps": explore_rules.MAX_STEPS,
            "cooldown": explore_rules.EXPLORE_COOLDOWN_MINUTES, "realm": p["realm"]}


def found_list(exp):
    from bot import loot
    out = [f"🪷 {exp.coins:,}"] if exp.coins else []
    return out + [loot.describe(i) for i in exp.items]


def play_view(conn, s, now):
    e = s.exp
    p = db.get_player(conn, e.user_id)
    name, scene = region(e)
    out = {"turn": s.turn, "region": name, "scene": scene, "step": e.step, "steps": explore_rules.MAX_STEPS,
           "hp": round(e.hp), "max_hp": round(e.max_hp), "hp_pct": round(e.hp / max(1, e.max_hp) * 100),
           "found": found_list(e), "notice": rich(s.notice) if s.notice else None,
           "coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"])}
    b = s.battle
    if b is not None:
        out["mode"] = "fight"
        out["fight"] = fight_view(conn, s, b, p, now)
        return out
    if s.lair_result is not None:
        out["mode"] = "lair_over"
        lair = e.lair
        out["lair"] = {"name": lair["beast"][0], "won": s.lair_won, "lines": lines(s.lair_result),
                       "title": {"won": "Victory!", "fled": "You slipped away", "escaped": "It escaped"}.get(
                           s.lair_won, "The hunt failed")}
        return out
    if e.over:
        out["mode"] = "over"
        out["title"] = "Expedition failed" if e.defeated else "You return safely"
        out["story"] = lines(e.story)
        out["summary"] = lines(e.summary)
        if e.lair and now < e.lair["closes"]:
            out["lair"] = {"name": e.lair["beast"][0], "tier": TIER_LABEL[e.lair["tier"]],
                           "closes": max(0, round((e.lair["closes"] - now) / 60)),
                           "problem": rich(hunt.can_join(p, now) or "") or None,
                           "art": f"/art/beasts/{_slug(e.lair['beast'][0])}.png"}
        return out
    if s.choosing:
        out["mode"] = "choose"
        out["story"] = lines(e.story)
        out["paths"] = [{"key": k, "label": PATH_LABEL[k], "clue": clue} for k, (_, clue) in e.paths.items()]
        out["deeper_note"] = (f"Step {e.step}: rarer finds, but beasts are +{(e.step - 1) * 10}% stronger."
                              if e.step > 1 else None)
        return out
    out["story"] = lines(e.story)
    if e.pending == "hazard":
        out["mode"] = "hazard"
        h = e.hazard
        left = h["seconds"] if h["shown_at"] is None else max(0.0, h["shown_at"] + h["seconds"] - now)
        out["hazard"] = {"seconds": h["seconds"], "left": round(left, 1),
                         "paths": [{"key": k, "label": PATH_LABEL[k]} for k in explore_rules.PATHS]}
        return out
    if e.pending == "stranger":
        out["mode"] = "stranger"
        out["stranger"] = {"cost": e.stranger_cost}
        return out
    out["mode"] = "story"
    m = e.merchant
    if m and s.merchant_step == e.step:
        import alchemy
        out["merchant"] = [
            {"key": "pill", "label": alchemy.QI_PILLS[m["pill"]]["name"], "price": m["pill_price"],
             "bought": "pill" in m["bought"]},
            {"key": "herb", "label": m["herb"], "price": m["herb_price"], "bought": "herb" in m["bought"]}]
    out["deeper"] = e.can_go_deeper
    if e.lair:
        out["lair_note"] = (f"The {e.lair['beast'][0]}'s lair stays open {hunt.open_minutes(e.lair['tier'])} minutes. "
                            "You can hunt it alone when you head home.")
    return out


def _slug(name):
    import beasts
    return beasts.slug(name)


def statuses(d):
    return [battle_rules.STATUSES[k]["name"] for k in d if k in battle_rules.STATUSES and k != "charged"]


def action_info(b, f, key):
    tier = b.enemy["tier"]
    if key == "strike":
        return "Beats Break. Into a Guard it is blocked and you are Stunned. Same move: both hit at half."
    if key == "guard":
        return ("Beats Strike: blocks it and counters for half a Strike. "
                f"Blocks {battle_rules.CHARGE_GUARD_BLOCK:.0%} of a charged attack.")
    if key == "break":
        return "Beats Guard: shatters it and staggers the beast. Interrupts a charged attack. Loses to Strike."
    if key == "flee":
        return f"{battle_rules.FLEE_CHANCE[tier]:.0%} chance to get away. No reward."
    if key == "pill":
        if not f.pills:
            return "No Mending pills in your bag. Refine them in Alchemy."
        return (f"{f.pills[0]['name']}: heals {f.pills[0]['heal']:.0%} HP and uses your turn. "
                f"At most {battle_rules.PILLS_PER_FIGHT} per fight.")
    t = f.tech(key)
    if not t:
        return "No technique in this slot yet."
    rest = combat.cooldown_turns(t)
    as_ = "a Strike" if key == "attack_tech" else "a Guard"
    return f"{t['name']}: {describe(t)}. Counts as {as_}. Rests {rest} turn{'s' if rest != 1 else ''} after use."


def actions(b, f):
    out = []
    for i, key in enumerate(ACTIONS):
        t = f.tech(key) if key.endswith("_tech") else None
        label = t["name"] if t else ACTION_LABEL[key]
        state = ""
        if key.endswith("_tech"):
            left = f.cooldowns.get(key, 0)
            state = "Empty" if not t else (f"{left} turn{'s' if left != 1 else ''}" if left else "Ready")
        elif key == "pill":
            n = f.pill_count()
            state = f"×{n}" if n else "None"
        out.append({"key": key, "no": i + 1, "label": label, "icon": f"/art/icons/actions/{key}.webp",
                    "ready": f.ready(key) and not b.over, "state": state, "info": action_info(b, f, key)})
    return out


def fight_view(conn, s, b, p, now):
    f = b.fighters[0]
    e = b.enemy
    beast = e["kind"] == "beast"
    head, hint = b.warning if getattr(b, "warning", None) else ("", "")
    intent = getattr(b, "intent", None) or {}
    danger = intent.get("kind") if intent.get("kind") in ("charged", "signature") else None
    log = [(icon, rich(text)) for icon, text in (b.log or [])]
    fx = effects(b.log or [], f.name)
    prev = s.prev or {}
    left = max(0.0, s.turn_started + battle_rules.TURN_SECONDS - now)
    return {
        "lair": b is s.lair_battle,
        "title": ("Beast King's den" if e["tier"] == "beast_king" else "Elite lair") if b is s.lair_battle else
                 ("Bandits" if not beast else "Wild beast") + f" · Step {s.exp.step} of {explore_rules.MAX_STEPS}",
        "me": {"name": f.name, "realm": f.realm, "layer": f.layer, "hp": round(f.hp), "max_hp": round(f.max_hp),
               "hp_pct": round(f.hp / max(1, f.max_hp) * 100), "attack": number(round(f.attack)),
               "defense": number(round(f.defense)), "statuses": statuses(f.statuses), "stunned": f.stunned,
               "face": FACE, "art": FIGHTER, "qi": number(round(p["qi"])),
               "delta": round(f.hp) - prev["me"] if "me" in prev else 0},
        "enemy": {"name": e["name"], "tier": TIER_LABEL[e["tier"]], "role": e.get("role", "").title(),
                  "element": e.get("element") if beast else None, "realm": e.get("realm", ""),
                  "hp": round(e["hp"]), "max_hp": round(e["max_hp"]), "hp_pct": round(e["hp"] / max(1, e["max_hp"]) * 100),
                  "statuses": statuses(e["statuses"]),
                  "art": f"/art/beasts/{e['slug']}.png" if beast and e.get("slug") else "/art/scenes/subject_bandits.png",
                  "delta": round(e["hp"]) - prev["enemy"] if "enemy" in prev else 0},
        "warning": {"head": rich(head), "hint": rich(hint), "danger": danger},
        "log": log, "fx": fx, "turn_no": b.turn, "seconds": battle_rules.TURN_SECONDS, "left": round(left, 1),
        "actions": actions(b, f), "arena": ARENA,
    }


def effects(log, me):
    """Which animations the last turn earns, read from the engine's own log."""
    fx = set()
    for icon, text in log:
        mine = text.startswith(me)
        if icon == "sword" and "dmg" in text:
            fx.add("slash")
        elif icon == "fist" and "dmg" in text:
            fx.add("crack")
        if icon == "shield" and mine and ("blocked" in text or "counters" in text):
            fx.add("shield")
        if "counters for" in text:
            fx.add("counter")
        if "Stunned" in text and mine:
            fx.add("stun")
        if "staggers" in text or "shatters" in text:
            fx.add("stagger")
        if icon == "skull" and "−" in text:
            fx.add("claw")
        if icon == "pill":
            fx.add("heal")
    return sorted(fx)
