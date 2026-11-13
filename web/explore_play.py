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
import json
import os
import threading
import re
import time
from dataclasses import dataclass, field

import battle as battle_rules
import explore as explore_rules
import looks

from bot import crafting, db, hunt
from bot import player as rules
from bot.expedition import TIMER_GRACE_SECONDS as HAZARD_GRACE, Expedition
from bot.fight_view import GRACE_SECONDS as TURN_GRACE, TIER_LABEL, describe
from cards.scenes import REGION
from bot.explore_card import REGION_BY_TIER

from .forge_play import rich
from .profile import number

IDLE_SECONDS = 120                      # like the bot's expedition panel (views.PANEL_IDLE_SECONDS)
# No reaction time on the website for now: a turn waits for the player. Only a page left alone this long
# gets the bot's timed-out move (Guard; three in a row: flee), so a forgotten fight still ends.
TURN_LIMIT = 600
MAX_TIMEOUTS = 200
ACTIONS = ("strike", "attack_tech", "defense_tech", "pill", "guard", "break", "flee")
MAIN = ("strike", "techniques", "guard", "break")             # the four big buttons, keys 1-4
SIDE = ("pill", "flee")                                       # small buttons on the side: P and F
ACTION_LABEL = {"strike": "Strike", "attack_tech": "Attack technique", "defense_tech": "Defense technique",
                "pill": "Mending Pill", "guard": "Guard", "break": "Break", "flee": "Flee"}
PATH_LABEL = {"left": "Left", "middle": "Ahead", "right": "Right"}
POSES = looks.POSES                  # the fight script swaps these (docs/web.md)
ARENA = "/art/scenes/arena_ruins.jpg"   # a fight with no region (should not happen; kept as the fallback)


POSES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "beasts", "poses")
_poses_cache = {}


def beast_poses(slug):
    """A beast's cut-out fight poses (art/beasts/poses/<slug>/: idle, crouch, leap, slam, roar + poses.json), or None.
    Each pose: its picture and where it sits, in % of the idle pose (fight.js swaps them as the beast moves)."""
    if not slug:
        return None
    if slug not in _poses_cache:
        try:
            with open(os.path.join(POSES_DIR, slug, "poses.json")) as fh:
                data = json.load(fh)
            _poses_cache[slug] = {"aspect": data["aspect"], "poses": {
                k: dict(v, src=f"/art/beasts/poses/{slug}/{k}.webp") for k, v in data["poses"].items()}}
        except (OSError, ValueError, KeyError):
            _poses_cache[slug] = None
    return _poses_cache[slug]


def arena(exp):
    """The fight background: the battleground of the region being explored (art/scenes/battle_<region>.jpg)."""
    name = REGION_BY_TIER.get(getattr(exp, "tier", None))
    if not name:
        return ARENA
    return f"/art/scenes/battle_{name.lower().replace(' ', '_')}.jpg"


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
    test: bool = False                  # an /admin web_fight test fight (rides in lair_battle): no rewards
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

    def start_test(self, conn, uid):
        """A test fight queued in Discord with /admin web_fight: it starts now, on its own (no expedition, no
        cooldown), and pays nothing. None when nothing is queued or an expedition is still going."""
        from bot import admin
        with self._lock:
            s = self._s.get(uid)
            if s and not self._finished(s):
                return None
            queued = admin.take_web_fight(conn, uid)
            if not queued:
                return None
            row, tier, home = queued
            now = self.clock()
            exp = Expedition(conn, uid, self.rng_factory() if self.rng_factory else None)
            exp.over = True
            s = Run(exp, choosing=False, touched=now, test=True)
            s.lair_battle = admin.beast_battle(conn, uid, row, tier, home, rng=self.rng_factory() if self.rng_factory else None)
            s.turn_started = now
            self._s[uid] = s
            return s

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
            while b is not None and not b.over and now > s.turn_started + TURN_LIMIT + TURN_GRACE \
                    and n < MAX_TIMEOUTS:
                missed = s.turn_started + TURN_LIMIT
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
            if b is s.lair_battle and s.test:
                f = b.fighters[0]
                s.lair_result = [f"{b.enemy['name']} · {b.turn} turns · you ended on {round(f.hp):,} / {round(f.max_hp):,} HP",
                                 "Test fight: no rewards, no injury, no cooldown."]
                s.lair_won = b.result
            elif b is s.lair_battle:
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
        out["lair"] = {"name": s.lair_battle.enemy["name"], "won": s.lair_won, "lines": lines(s.lair_result),
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
        return (f"Beats Strike: blocks it, counters for half a Strike and gives +{battle_rules.BATTLE_QI_GOOD_GUARD} "
                f"Battle Qi. Blocks {battle_rules.CHARGE_GUARD_BLOCK:.0%} of a charged attack.")
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
    as_ = "a Strike" if key == "attack_tech" else "a Guard"
    return f"{t['name']}: {describe(t)}. Counts as {as_}. Costs {f.qi_cost(key)} Battle Qi."


def action(b, f, key):
    t = f.tech(key) if key.endswith("_tech") else None
    state = ""
    if key.endswith("_tech"):
        state = "Empty slot" if not t else f"{f.qi_cost(key)} Battle Qi" + ("" if f.ready(key) else " · not enough")
    elif key == "pill":
        n = f.pill_count()
        state = f"×{n}" if n else "None"
    icon = f"/art/icons/actions/{key}.webp"
    if t:
        from bot.sheet.data import tech_kind
        from .profile import art_url
        icon = art_url(tech_kind(t["name"], rules.TECH_BY_NAME.get(t["name"], {}).get("school", "Body"))) or icon
    return {"key": key, "label": t["name"] if t else ACTION_LABEL[key], "icon": icon,
            "ready": f.ready(key) and not b.over, "state": state, "info": action_info(b, f, key),
            "kind": "Attack technique" if key == "attack_tech" else "Defense technique" if key == "defense_tech" else ""}


def actions(b, f):
    """The four big buttons (Strike, Techniques, Guard, Break) and the two small ones (Pill, Flee)."""
    techs = [action(b, f, k) for k in ("attack_tech", "defense_tech")]
    main = []
    for i, key in enumerate(MAIN):
        if key == "techniques":
            ready = [t for t in techs if t["ready"]]
            main.append({"key": key, "no": i + 1, "label": "Techniques", "icon": "/art/icons/actions/attack_tech.webp",
                         "ready": bool(ready), "state": f"{len(ready)} ready" if ready else "Need Battle Qi",
                         "info": "Your attack technique counts as a Strike, your defense technique as a Guard. "
                                 f"They spend Battle Qi: +{battle_rules.BATTLE_QI_PER_TURN} comes back every turn, "
                                 f"+{battle_rules.BATTLE_QI_GOOD_GUARD} more on a good Guard.", "techs": techs})
        else:
            main.append(dict(action(b, f, key), no=i + 1))
    side = [dict(action(b, f, k), hotkey="P" if k == "pill" else "F") for k in SIDE]
    return main, side


def result_banner(log, me):
    """The big word over your fighter after a turn, read from the engine's log (like the mockup's "Dodge!")."""
    mine = [t for _, t in log if t.startswith(me)]
    theirs = [t for _, t in log if not t.startswith(me)]
    text = " ".join(mine)
    if "counters for" in text:
        return "Countered!", "You blocked the blow and struck back."
    if "Stunned" in text:
        return "Stunned!", "Your Strike hit its Guard. Only Guard next turn."
    if "blocked by" in text:
        return "Blocked!", "It guarded against your Strike."
    if any("shatters" in t or "staggers" in t for t in mine + theirs):
        return "Guard broken!", "It is staggered and loses its next turn."
    if "clash" in text:
        return "Clash!", "Same move: both hit at half."
    if "heals" in text or "swallow" in text.lower():
        return "Restored!", "The pill's warmth spreads through you."
    if mine and "dmg" in text:
        return "Hit!", None
    if any("misses" in t or "blocked" in t for t in theirs):
        return "Evaded!", "The attack missed."
    return None, None


GRADE_COLOR = {"Mortal": "#D8D4CC", "Yellow": "#F0C566", "Mystic": "#7FB4FF", "Earth": "#6FD99A", "Heaven": "#E2A8FF"}
DEFENSE_SHOWS = {"counter": "countered", "recover": "recovered", "evade": "slipped away", "unbreakable": "of the Break"}


def cast(b, f):
    """The technique you used this turn, for its own animation (docs/web.md): which school and effect it has,
    its grade colour, and whether it landed. None when the turn used no technique."""
    t = next((x for x in (f.atk_t, f.def_t) if x and b.log and f.last_move == x["name"]), None)
    if t is None:
        return None
    info = rules.TECH_BY_NAME.get(t["name"], {})
    mine = " ".join(text for _, text in b.log if text.startswith(f.name + " — " + t["name"]))
    effect = (info.get("effect") or ("",))[0]
    if t["type"] == "attack":
        landed = "dmg" in mine
        shown = effect if landed else ""
        school = info.get("school", "Fist").lower()
    else:
        landed = "blocked" in mine or "holds" in mine or "slipped away" in mine
        shown = effect if effect in DEFENSE_SHOWS and DEFENSE_SHOWS[effect] in mine else ""
        if "holds" in mine and not shown:
            shown = "hold"
        school = "body" if info.get("school") == "Body" else "palmdef"
    from bot.sheet.data import tech_kind
    from .profile import art_url
    return {"name": t["name"], "kind": t["type"], "school": school, "effect": shown, "landed": landed,
            "grade": t["grade"], "color": GRADE_COLOR.get(t["grade"], "#E8C27A"),
            "icon": art_url(tech_kind(t["name"], info.get("school", "Body"))) or f"/art/icons/actions/{t['type']}_tech.webp"}


def look_face(player):
    """The round face on the fight card: the player's painting (looks.py)."""
    return looks.face(looks.of_player(player))


def look_poses(player):
    """The fighter's pose pictures: the player's painting, facing the beast."""
    look = looks.of_player(player)
    return {pose: looks.fighter(look, pose) for pose in POSES}


def fight_view(conn, s, b, p, now):
    f = b.fighters[0]
    e = b.enemy
    beast = e["kind"] == "beast"
    head, hint = b.warning if getattr(b, "warning", None) else ("", "")
    intent = getattr(b, "intent", None) or {}
    danger = intent.get("kind") if intent.get("kind") in ("charged", "signature") else None
    skill = battle_rules.UNIQUE_SKILLS.get(e["name"]) if beast else None
    poses = beast_poses(e.get("slug")) if beast else None
    winding = bool(skill and intent.get("skill") and not b.over)
    log = [(icon, rich(text)) for icon, text in (b.log or [])]
    fx = effects(b.log or [], f.name)
    prev = s.prev or {}
    main, side = actions(b, f)
    word, sub = result_banner(b.log or [], f.name)
    return {
        "lair": b is s.lair_battle,
        "title": "Admin test fight" if s.test else
                 ("Beast King's den" if e["tier"] == "beast_king" else "Elite lair") if b is s.lair_battle else
                 ("Bandits" if not beast else "Wild beast") + f" · Step {s.exp.step} of {explore_rules.MAX_STEPS}",
        "me": {"name": f.name, "realm": f.realm, "layer": f.layer, "hp": round(f.hp), "max_hp": round(f.max_hp),
               "hp_pct": round(f.hp / max(1, f.max_hp) * 100), "attack": number(round(f.attack)),
               "defense": number(round(f.defense)), "statuses": statuses(f.statuses), "stunned": f.stunned,
               "face": look_face(p), "poses": look_poses(p), "tip": looks.sword_tip(looks.of_player(p)),
               "sheet": looks.attack_sheet(looks.of_player(p)), "gsheet": looks.guard_sheet(looks.of_player(p)),
               "bqi": round(f.bqi), "max_bqi": f.max_bqi,
               "bqi_pct": max(0, min(100, round(f.bqi / max(1, f.max_bqi) * 100))),
               "delta": round(f.hp) - prev["me"] if "me" in prev else 0},
        "enemy": {"name": e["name"], "tier": TIER_LABEL[e["tier"]], "role": e.get("role", "").title(),
                  "element": e.get("element") if beast else None, "realm": e.get("realm", ""),
                  "hp": round(e["hp"]), "max_hp": round(e["max_hp"]), "hp_pct": round(e["hp"] / max(1, e["max_hp"]) * 100),
                  "statuses": statuses(e["statuses"]),
                  "art": poses["poses"]["idle"]["src"] if poses else
                         f"/art/beasts/{e['slug']}.png" if beast and e.get("slug") else "/art/scenes/subject_bandits.png",
                  "poses": poses, "pose": "crouch" if poses and winding and "crouch" in poses["poses"] else "idle",
                  "delta": round(e["hp"]) - prev["enemy"] if "enemy" in prev else 0},
        "warning": {"head": rich(head), "hint": rich(hint), "danger": danger,
                    "skill": skill["fx"] if winding else None},
        "roused": "roused" in e["statuses"],
        "log": log, "history": history(b), "fx": fx, "cast": cast(b, f), "events": events(b.log or [], f), "turn_no": b.turn, "main": main, "side": side, "arena": arena(getattr(s, "exp", None)),
        "result": {"word": word, "sub": sub} if word else None,
    }


def history(b):
    """Every turn's log so far, newest first, for the Battle History panel (the engine keeps them in b.history).
    Before the first move it is the fight's opening line."""
    turns = getattr(b, "history", None) or []
    out = [{"turn": i + 1, "lines": [(icon, rich(text)) for icon, text in log]} for i, log in enumerate(turns) if log]
    if not out:
        return [{"turn": 0, "lines": [(icon, rich(text)) for icon, text in (b.log or [])]}]
    return out[::-1]


def _number(text, pattern):
    m = re.search(pattern, text)
    return int(m.group(1).replace(",", "")) if m else 0


def events(log, f):
    """What happened this turn, in order, for the fight screen to act out (web/static/fight.js, docs/web.md).
    Read from the engine's own log; nothing here decides anything.

    {"who": "me", "act": "strike" | "break", "hit": bool, "dmg": n, "blocked": bool}   your weapon attack
    {"who": "me", "act": "guard", "counter": n}       the beast struck and your Guard stopped it (n = counter damage)
    {"who": "me", "act": "tech"}                      a technique: it plays its own animation
    {"who": "enemy", "act": "attack", "dmg": n}       the beast hit you
    {"who": "enemy", "act": "pounce", "dmg": n, "guard": bool, "stun": bool}
                                                      a unique skill (battle.UNIQUE_SKILLS, its "fx") landed;
                                                      it replaces your Guard's own event this turn
    """
    out = []
    skills = {v["name"]: v["fx"] for v in battle_rules.UNIQUE_SKILLS.values()}
    techs = {t["name"] for t in (f.atk_t, f.def_t) if t}
    for icon, text in log:
        mine = text.startswith(f.name + " — ")
        move = text[len(f.name) + 3:].split(":")[0] if mine else ""
        if move in ("Strike", "Break"):
            dmg = _number(text, r"([\d,]+) dmg")
            out.append({"who": "me", "act": move.lower(), "hit": dmg > 0, "dmg": dmg, "blocked": "blocked" in text})
        elif move == "Guard" and "blocked" in text:
            out.append({"who": "me", "act": "guard", "counter": _number(text, r"counters for ([\d,]+)")})
        elif move in techs:
            out.append({"who": "me", "act": "tech"})
        elif icon == "skull" and not mine and any(f" — {n} on " in text for n in skills):
            name = next(n for n in skills if f" — {n} on " in text)
            dmg = _number(text, r" on " + re.escape(f.name) + r" −([\d,]+)")
            guard = [x for x in out if x["act"] == "guard"]
            out = [x for x in out if x["act"] != "guard"]
            out.append({"who": "enemy", "act": skills[name], "dmg": dmg, "guard": bool(guard),
                        "stun": f"{f.name} −{dmg:,} (Stunned)" in text})
        elif icon == "roar" and not any(x["act"] in skills.values() for x in out):
            name = next((n for n in skills if f" — {n}:" in text), None)    # it landed but did you no harm
            if name:
                guard = [x for x in out if x["act"] == "guard"]
                out = [x for x in out if x["act"] != "guard"]
                out.append({"who": "enemy", "act": skills[name], "dmg": 0, "guard": bool(guard), "stun": False})
        elif icon == "skull" and not mine:
            dmg = _number(text, r" on " + re.escape(f.name) + r" −([\d,]+)")
            if dmg:
                out.append({"who": "enemy", "act": "attack", "dmg": dmg})
    return out


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
