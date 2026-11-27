"""
A party's hunt on the website (docs/hunting.md): up to five beasts from the chosen location, fought together.

Nothing here is a new rule. Each member carries their own bot/expedition.Expedition (their HP, what they found,
the defeat penalty, the walk home that banks it, the shared 30-minute explore rest, quests); every fight turn is
bot/fight.Battle with all members in it; rewards are the bot's own:
  • a Normal beast pays each member who stood to the end exactly like a /explore beast
    (Expedition._beast_result: coins, chest chance, beast core, materials), banked on the walk home;
  • an Elite or a Beast King pays like a Discord lair hunt (bot/hunt._pay), straight into each winner's bag.
Every member rolls their own rewards: nobody competes for a drop.

The server referees: each member may send one move per turn; a team turn has TEAM_TURN_SECONDS, then whoever
has not picked Guards (three in a row: flees), which is the bot's own timeout rule. Nobody joins halfway.

A trip in the open world (web/overworld.py, docs/world.md) is a Solo Hunt too (`world`): it starts with your first
encounter out there (and with it the 30-minute explore rest), each beast you meet or find you uncover is one of its
MAX_ENCOUNTERS steps, and what you carry is banked when you walk back into town. Beasts and finds come from the
world (where they stand, which one): the fight and the find themselves are the ones here and in bot/expedition.py.
"""
import random
import time
from types import SimpleNamespace
from dataclasses import dataclass, field

import beasts
import explore as explore_rules
import hunting

from bot import combat, crafting, db, fight, gear, hunt, loot
from bot.expedition import Expedition

from . import explore_play as ep
from . import hunt_map
from .forge_play import rich
from .profile import number

TEAM_TURN_SECONDS = 30            # a team turn: everyone picks, or the stragglers Guard
SOLO_TURN_SECONDS = ep.TURN_LIMIT  # alone, the turn waits for you, as in Explore
IDLE_SECONDS = ep.IDLE_SECONDS    # between beasts, the leader decides within this or the party heads home
MAP_IDLE_SECONDS = 600            # on the map, walking about: ten minutes without a step and you head home
TIER_WORD = {"normal": "", "elite": "Elite ", "beast_king": "Beast King "}


@dataclass
class Hunt:
    party_id: str
    loc: dict
    rng: random.Random
    exps: dict                     # uid → Expedition, for members still out in the wilds
    order: list                    # uids in party order (for the allies panel)
    step: int = 0
    battle: object = None
    lair: dict = None              # an Elite / Beast King being fought (paid by bot/hunt._pay)
    v: int = 0                     # bumps on every change everyone should see
    turn_started: float = 0.0
    touched: float = 0.0
    prev: dict = None              # HP before the last turn, for the damage numbers
    story: list = field(default_factory=list)     # what happened at this step, for everyone
    lines: dict = field(default_factory=dict)     # uid → what the last fight paid them
    ended: object = None           # the fight just won, kept on screen until each member presses Continue
    acked: set = field(default_factory=set)
    results: dict = field(default_factory=dict)   # uid → their final summary (title, lines) once they are home
    notice: dict = field(default_factory=dict)    # uid → a refused move's reason
    over: bool = False
    map: bool = False              # walk the hunting ground (web/hunt_map.py): the next beast waits on the map
    beast: dict = None             # map: the next beast, rolled already, and where it stands
    pos: dict = field(default_factory=dict)       # map: uid → (x, y, time) last known
    world: bool = False            # a trip in the open world: beasts and finds come from web/overworld.py

    def active(self):
        return [u for u in self.order if u in self.exps]


class Hunts:
    def __init__(self, parties, clock=time.time, rng_factory=None):
        self.parties = parties
        self.lock = parties.lock          # one lock for parties and hunts: membership and fights never disagree
        self.clock = clock
        self.rng_factory = rng_factory
        self._h = {}                      # party id → Hunt (the latest, kept while its results are shown)

    def get(self, pid):
        return self._h.get(pid)

    # ── who may set out ─────────────────────────────────────────────

    def blocked(self, conn, uid):
        """The same checks as /explore: injured, or still resting from the last expedition (shared with Discord)."""
        from bot import player as rules
        now = self.clock()
        p = db.get_player(conn, uid)
        hurt = rules.injured_for(p, now)
        if hurt:
            return f"injured for {rules.fmt_duration(hurt)}"
        wait = db.cooldown_left(conn, uid, "explore", now)
        if wait:
            return f"resting from the last expedition for {rules.fmt_duration(wait)}"
        return None

    def start(self, conn, uid, walk=False, world=False):
        """The leader sets out. None, or why not. `walk`: on the walkable map (web/hunt_map.py); `world`: a trip in
        the open world (encounters come from web/overworld.py, nothing is spawned here)."""
        with self.lock:
            party = self.parties.of(uid)
            if party is None:
                return "You are not in a party."
            if party.leader != uid:
                return "Only the leader can start the expedition."
            if party.hunting:
                return None
            problems = self.parties.start_problems(conn, party, self.blocked)
            if problems:
                return problems[0]
            now = self.clock()
            rng = self.rng_factory() if self.rng_factory else random.Random()
            exps = {}
            for m in party.members:
                db.set_cooldown(conn, m.uid, "explore", explore_rules.EXPLORE_COOLDOWN_MINUTES * 60, now)
                exps[m.uid] = Expedition(conn, m.uid, rng)
                m.ready = False
            h = Hunt(party.id, hunting.location(party.location), rng, exps, party.uids(), touched=now,
                     map=walk or world, world=world)
            self._h[party.id] = h
            party.hunting = True
            self.parties._bump(party)
            if world:
                pass
            elif walk:
                h.pos = {u: (*hunt_map.start(hunt_map.plan(h.loc["key"])), now) for u in exps}
                self._spawn(h)
            else:
                self._next(conn, h)
            return None

    # ── the beasts ──────────────────────────────────────────────────

    def _next(self, conn, h):
        """Walk on: the next beast of this location comes out."""
        name, tier, role = self._roll(h)
        self._battle(conn, h, name, tier, role)

    def _roll(self, h):
        """The next beast: a step deeper, its kind and which one, from the location's pool."""
        h.step += 1
        h.story, h.lines, h.ended, h.acked, h.notice = [], {}, None, set(), {}
        lead = h.exps[h.active()[0]].player
        luck = gear.artifact_bonus(lead, "explore_luck") + gear.artifact_bonus(lead, "rare_encounters")
        tier = loot.pick(hunting.tier_odds(h.step, luck), h.rng)
        name, _, role, _home = h.rng.choice([b for b in hunting.pool(h.loc) if b[1] == tier])
        return name, tier, role

    def _spawn(self, h):
        """Map: the next beast is rolled now (exactly as _next would) and stands somewhere on the map."""
        name, tier, role = self._roll(h)
        m = hunt_map.plan(h.loc["key"])
        you = h.pos.get(h.active()[0], (*hunt_map.start(m), 0))
        x, y = hunt_map.spot(h.rng, you[:2], m)
        h.beast = {"name": name, "tier": tier, "role": role, "x": x, "y": y}
        h.story = [f"🐾 Somewhere in {h.loc['name']}, a {TIER_WORD[tier]}**{name}** ({role.title()}) is hunting too."]
        h.touched = self.clock()
        h.v += 1

    def _battle(self, conn, h, name, tier, role):
        """The fight with this beast, for everyone still out hunting."""
        party = [h.exps[u] for u in h.active()]
        players = [e.player for e in party]
        fighters = []
        for e in party:
            e.conn = conn
            fighters.append(fight.Fighter(e.player, e.techniques, e.hp, e.max_hp, e.attack, e.defense,
                                          pills=crafting.fight_pills(conn, e.user_id)))
        top = max(players, key=lambda p: (_realm_rank(p["realm"]), p["layer"]))
        if tier == "normal":
            # as /explore: the beast of this step (+10% a step deeper), measured on the strongest member,
            # plus the bot's +20% HP for each fighter beyond the beast's intended team size
            stats_ = combat.beast_stats(top, (name, tier, role), h.step)
            extra = max(0, len(players) - beasts.BEAST_TIERS[tier]["team_size"])
            stats_["hp"] = stats_["max_hp"] = round(stats_["hp"] * (1 + beasts.EXTRA_PLAYER_HP_BONUS * extra))
            h.lair = None
        else:
            # as a Discord lair hunt (bot/hunt.team_beast): no step bonus, team-size HP
            h.lair = {"beast": (name, tier, role), "tier": tier, "realm": top["realm"], "finder": top["user_id"]}
            stats_ = hunt.team_beast(h.lair, players)
        enemy = fight.enemy_from_beast(stats_, name)
        enemy["realm"], enemy["slug"] = top["realm"], beasts.slug(name)
        h.battle = fight.Battle(fighters, enemy, h.rng)
        bonus = f" (+{(h.step - 1) * 10}% stronger this deep)" if tier == "normal" and h.step > 1 else ""
        h.story = [f"🐾 A {TIER_WORD[tier]}**{name}** ({role.title()}) bars the way{bonus}!"]
        h.turn_started, h.prev = self.clock(), None
        h.v += 1

    def _resolve(self, conn, h):
        b = h.battle
        h.prev = {"enemy": round(b.enemy["hp"]), **{f.uid: round(f.hp) for f in b.fighters}}
        b.resolve()
        for f in b.fighters:
            crafting.bank_fight_pills(conn, f)
        h.turn_started = self.clock()
        h.v += 1
        h.notice = {}
        if b.over:
            self._fight_over(conn, h, b)

    def _fight_over(self, conn, h, b):
        name = b.enemy["name"]
        won = b.result == "won"
        h.lines = {}
        if h.lair and won:                                     # Elite / Beast King: the lair-hunt payout
            rows = [{"p": f.player, "techs": f.techs, "atk_uses": f.atk_uses, "guard_uses": f.guard_uses,
                     "dealt": f.dealt, "fled": f.fled or f.hp <= 0} for f in b.fighters]
            head = f"**{name}** · {b.enemy['max_hp']:,} HP · {len(rows)} fighter(s) · {b.turn} turns"
            paid, _news = hunt._pay(conn, h.lair, rows, True, name, head, rng=h.rng)
        for f in b.fighters:
            e = h.exps.get(f.uid)
            if e is None:
                continue
            e.conn = conn
            e.hp = max(0, round(f.hp))
            mine = []
            if not (h.lair and won):                           # the lair payout already gave the mastery EXP
                e._mastery_from_fight({"attack_uses": f.atk_uses, "guard_uses": f.guard_uses})
            if f.hp <= 0:
                mine.append(f"☠️ You fell to the **{name}**.")
            elif f.fled:
                mine.append(f"🏃 You escaped from the **{name}**.")
            elif won and h.lair:
                mine += paid
            elif won:
                e.story = []
                e._beast_result(b, name)                       # coins, chest, core, materials: kept until home
                mine += e.story
                if h.world:                                    # out in the open world: today's tasks count it
                    from . import world_tasks
                    mine += world_tasks.record(conn, f.uid, "beasts", self.clock())
            elif b.result == "escaped":
                mine.append(f"🌫️ The **{name}** slinks away into the wilds.")
            h.lines[f.uid] = mine
            if f.hp <= 0:
                self._home(conn, h, f.uid, defeated=True)
        h.battle = None
        h.touched = self.clock()
        if won:
            h.ended = b
        else:
            h.story = h.story + [f"The fight with the **{name}** is over."]
        h.v += 1
        if not h.exps:
            self._finish(h)
        elif h.world:                                          # back out in the world, where you stood
            h.beast = None
        elif h.map:                                            # back on the map: the next beast is already out there
            ended, lines = h.ended, h.lines
            if h.step < hunting.MAX_ENCOUNTERS:
                self._spawn(h)
            else:
                h.beast = None
                h.story = ["That is as deep as a hunt goes. Walk back to the trail head, or head home."]
            h.ended, h.lines = ended, lines                   # the victory stays on screen until you press Continue

    def _home(self, conn, h, uid, defeated=False, why=None):
        """This member's expedition ends: what they carry is banked (halved on defeat), the rest timer is set."""
        e = h.exps.pop(uid, None)
        if e is None:
            return
        e.conn = conn
        e.battle = None
        if defeated:
            e.story = []
            e._defeat()
        else:
            e.story = [why or "You head back the way you came, loot in hand."]
            e.finish(now=self.clock())
        title = "Expedition failed" if defeated else "You return safely"
        h.results[uid] = {"title": title, "lines": [rich(x) for x in (e.story + e.summary) if x],
                          "defeated": defeated, "slain": e.beasts_slain}
        h.v += 1

    def _finish(self, h):
        h.over = True
        party = self.parties.get(h.party_id)
        if party is not None:
            party.hunting = False
            self.parties._bump(party)

    # ── clocks ──────────────────────────────────────────────────────

    def catch_up(self, conn, uid):
        """Fight turns whose time ran out, and a party left standing too long between beasts."""
        with self.lock:
            party = self.parties.of(uid)
            h = self._h.get(party.id) if party else None
            if h is None or h.over:
                return h
            now = self.clock()
            limit = TEAM_TURN_SECONDS if len(h.battle.fighters if h.battle else h.exps) > 1 else SOLO_TURN_SECONDS
            n = 0
            while h.battle is not None and not h.battle.over and now > h.turn_started + limit + ep.TURN_GRACE \
                    and n < ep.MAX_TIMEOUTS:
                missed = h.turn_started + limit
                self._resolve(conn, h)                         # stragglers Guard (the engine's own timeout)
                if h.battle is not None:
                    h.turn_started = missed + ep.TURN_GRACE
                n += 1
            idle = MAP_IDLE_SECONDS if h.map else IDLE_SECONDS
            if h.battle is None and not h.over and now > h.touched + idle:
                for u in list(h.exps):
                    self._home(conn, h, u, why="You lingered too long; night falls and the party heads home.")
                self._finish(h)
            return h

    # ── what members do ─────────────────────────────────────────────

    def version(self, h, uid):
        """This member's page version: changes when anything they should see changes (an ally's pick doesn't,
        so it never makes their own move stale), and once they have picked."""
        b = h.battle
        picked = 1 if b is not None and (f := b.fighter(uid)) is not None and f.pick is not None else 0
        return h.v * 2 + picked

    def act(self, conn, uid, what, arg, turn):
        h = self.catch_up(conn, uid)
        if h is None:
            return None
        with self.lock:
            party = self.parties.of(uid)
            if party is None or party.id != h.party_id:
                return h
            now = self.clock()
            if what == "move":
                b = h.battle
                if b is None or b.over or turn != self.version(h, uid) or arg not in ep.ACTIONS:
                    return h                                   # old page, already picked, or not in a fight
                f = b.fighter(uid)
                if f is None or not f.active or f.pick is not None:
                    return h                                   # one move a turn: a pick is final
                why = b.choose(uid, arg)
                if why:
                    h.notice[uid] = why
                    h.v += 1
                    return h
                h.notice.pop(uid, None)
                if b.all_picked():
                    self._resolve(conn, h)
                return h
            if turn != self.version(h, uid):
                return h
            if what == "continue":
                if h.ended is not None:
                    h.acked.add(uid)
                    h.v += 1
                return h
            if h.battle is not None or h.over:
                return h
            lead = party.leader == uid
            if what == "engage":                               # map: you walked up to the beast
                if not (h.map and h.beast and uid in h.exps):
                    return h
                x, _, y = (arg or "").partition(",")
                pos = hunt_map.moved(h.pos[uid], x, y, now, hunt_map.plan(h.loc["key"]))
                if pos is None or not hunt_map.close_enough(pos, h.beast):
                    return h                                   # too far, or not a place you could have walked to
                h.pos[uid] = pos
                b, h.beast = h.beast, None
                self._battle(conn, h, b["name"], b["tier"], b["role"])
                return h
            if what == "deeper" and lead and uid in h.exps and h.step < hunting.MAX_ENCOUNTERS and not h.map:
                self._next(conn, h)
            elif what == "return" and lead and uid in h.exps:
                for u in list(h.exps):
                    self._home(conn, h, u)
                self._finish(h)
            elif what == "leave" and uid in h.exps:
                self._home(conn, h, uid, why="You leave the hunt and head home with what you carry.")
                if not h.exps:
                    self._finish(h)
            else:
                return h
            h.touched = now
            h.v += 1
            return h

    def report(self, conn, uid, x, y):
        """Map: where this player says they are now. Kept if they could have walked there; the page gets back
        where the server has them (so a bad report puts them back where they were)."""
        h = self.catch_up(conn, uid)
        with self.lock:
            if h is None or not h.map or h.over or uid not in h.exps:
                return None
            now = self.clock()
            pos = hunt_map.moved(h.pos[uid], x, y, now, hunt_map.plan(h.loc["key"]))
            if pos is not None:
                if pos[:2] != h.pos[uid][:2]:
                    h.touched = now                            # walking about is not idling
                h.pos[uid] = pos
            else:
                h.pos[uid] = (*h.pos[uid][:2], now)
            return h.pos[uid][:2]

    def leave_party(self, conn, uid):
        """Leaving the party during a hunt: your own walk home first (never in the middle of a fight)."""
        with self.lock:
            party = self.parties.of(uid)
            h = self._h.get(party.id) if party else None
            if h is not None and not h.over and uid in h.exps:
                if h.battle is not None:
                    return "Finish the fight first (or Flee)."
                self._home(conn, h, uid, why="You leave the party and head home with what you carry.")
                if not h.exps:
                    self._finish(h)
            if h is not None:
                h.results.pop(uid, None)
            self.parties.leave(uid)
            return None

    # ── the open world (web/overworld.py) ───────────────────────────

    def trip(self, uid):
        """This player's open-world trip still under way, or None."""
        with self.lock:
            party = self.parties.of(uid)
            h = self._h.get(party.id) if party else None
            return h if h is not None and h.world and not h.over and uid in h.exps else None

    def _trip(self, conn, uid, loc_key):
        """The trip this encounter belongs to: the one under way, or a new one (which starts the explore rest).
        (hunt, None) or (None, why not)."""
        h = self.trip(uid)
        if h is not None:
            if h.step >= hunting.MAX_ENCOUNTERS:
                return None, "spent"
            return h, None
        party = self.parties.of(uid)
        if party is not None:
            if not party.solo:
                return None, "You are in a team: hunt with them from the lobby (ask the Gate Warden)."
            if party.hunting:
                return None, "Finish the hunt you are on first."
            self.parties.leave(uid)                           # a Solo Hunt still choosing its ground
        _, why = self.parties.create(conn, uid, "", False, True)
        if why:
            return None, why
        why = self.parties.set_location(conn, uid, loc_key) or self.start(conn, uid, walk=True, world=True)
        if why:
            self.parties.leave(uid)
            return None, why
        return self.trip(uid), None

    def world_fight(self, conn, uid, loc_key, beast):
        """A beast met out in the world (`beast`: name, tier, role, as web/overworld.py rolled it): the fight of
        this trip's next step. None, or why not."""
        with self.lock:
            h, why = self._trip(conn, uid, loc_key)
            if h is None:
                return why
            if h.battle is not None:
                return "You are already fighting."
            h.step += 1
            h.story, h.lines, h.ended, h.acked, h.notice = [], {}, None, set(), {}
            self._battle(conn, h, beast["name"], beast["tier"], beast["role"])
            h.touched = self.clock()
            return None

    def world_find(self, conn, uid, loc_key, kind):
        """Something found out in the world: one of /explore's own finds (bot/expedition.Expedition._<kind>), this
        trip's next step. (lines, None) or (None, why not)."""
        with self.lock:
            h, why = self._trip(conn, uid, loc_key)
            if h is None:
                return None, why
            if h.battle is not None:
                return None, "You are fighting."
            e = h.exps[uid]
            e.conn = conn
            h.step += 1
            h.story, h.lines, h.ended, h.acked, h.notice = [], {}, None, set(), {}
            e.story = []
            getattr(e, f"_{kind}")()
            lines = [rich(x) for x in e.story if x]
            h.touched = self.clock()
            h.v += 1
            return lines, None

    def world_home(self, conn, uid):
        """Back in town: the trip ends and what you carry is banked (bot/expedition.Expedition.finish). The lines
        to show, or None (no trip)."""
        h = self.catch_up(conn, uid)
        with self.lock:
            if h is None or not h.world or h.battle is not None:
                return None
            if h.over or uid not in h.exps:                    # it ended out there (night fell): what it banked
                if uid not in h.results or h.results[uid].get("defeated"):
                    return None
            else:
                self._home(conn, h, uid, why="You walk back through the town gate with what you carry.")
                self._finish(h)
            res = h.results.pop(uid, None)
            self._h.pop(h.party_id, None)
            self.parties.leave(uid)
            return res["lines"] if res else []

    def touch(self, uid):
        """Walking about the world is not idling (MAP_IDLE_SECONDS)."""
        with self.lock:
            h = self.trip(uid)
            if h is not None:
                h.touched = self.clock()

    def trip_view(self, conn, uid):
        """The trip, for the world's HUD: how many of its encounters are used, HP, what is carried."""
        h = self.catch_up(conn, uid)
        with self.lock:
            if h is None or not h.world or h.over or uid not in h.exps:
                return None
            e = h.exps[uid]
            return {"step": h.step, "steps": hunting.MAX_ENCOUNTERS, "spent": h.step >= hunting.MAX_ENCOUNTERS,
                    "hp": round(e.hp), "max_hp": round(e.max_hp), "found": ep.found_list(e),
                    "fighting": h.battle is not None or (h.ended is not None and uid not in h.acked)}

    def walked(self, uid):
        """If this player's hunt is (or was) walked on the map (web/hunt_map.py): its ground's key; else None."""
        with self.lock:
            party = self.parties.of(uid)
            h = self._h.get(party.id) if party else None
            return h.loc["key"] if h and h.map else None

    def dismiss(self, uid):
        """Seen the hunt's result: back to the lobby (a Solo Hunt party simply ends)."""
        with self.lock:
            party = self.parties.of(uid)
            h = self._h.get(party.id) if party else None
            if h is None:
                return party
            if h.over or uid not in h.exps:
                h.results.pop(uid, None)
                if h.over and not h.results:
                    self._h.pop(h.party_id, None)
            if party.solo and h.over:
                self.parties.leave(uid)
                return None
            return party


def _realm_rank(realm):
    from bot import player as rules
    return rules.realm_index(realm)


# ── page data ────────────────────────────────────────────────────────

class _Seen:
    """What explore_play.fight_view reads from a running expedition, for one member of a hunt."""

    def __init__(self, h, uid, title, arena):
        self.prev = {"enemy": h.prev["enemy"], "me": h.prev[uid]} if h.prev and uid in h.prev else None
        self.lair_battle, self.test, self.lair_result = None, False, None
        self.battle = h.battle
        self.title, self.arena = title, arena
        self.ended = ({"battle": h.ended, "lines": h.lines.get(uid, []), "next": "continue"}
                      if h.ended is not None and uid not in h.acked else None)
        self.exp = h.exps.get(uid) or SimpleNamespace(over=True, step=h.step, tier=None)


def arena(loc):
    return f"/art/scenes/{loc['arena']}.jpg"


def view(conn, hunts, h, uid):
    """The hunt page for this member: the fight (on the shared fight screen) or what happened at this step."""
    p = db.get_player(conn, uid)
    loc = h.loc
    out = {"turn": hunts.version(h, uid), "location": loc["name"], "scene": f"/art/scenes/{loc['card']}.jpg",
           "step": h.step, "steps": hunting.MAX_ENCOUNTERS, "coins": number(p["lotus_coins"]),
           "pearls": number(p["moon_pearls"]), "act_url": "/hunt/act", "play_url": "/hunt", "done_url": "/hunt/done",
           "notice": rich(h.notice[uid]) if h.notice.get(uid) else None,
           "world": h.world, "loc_key": loc["key"]}
    party = hunts.parties.of(uid)
    lead = party is not None and party.leader == uid
    if uid in h.results and (h.over or uid not in h.exps):
        out["mode"] = "home"
        out["result"] = h.results[uid]
        out["solo"] = party.solo if party else True
        out["walked"] = h.map                               # back to the Crossroads (web/crossroads.py), not Explore
        out["world"] = h.world                              # an open-world trip: back to town (defeated) or out there
        return out
    b = h.battle if h.battle is not None else (h.ended if h.ended is not None and uid not in h.acked else None)
    if b is not None and b.fighter(uid) is not None:
        s = _Seen(h, uid, f"{loc['name']} · Beast {h.step} of {hunting.MAX_ENCOUNTERS}", arena(loc))
        F = ep.fight_view(conn, s, b, p, hunts.clock(), me=uid)
        f = b.fighter(uid)
        F["team"] = team_view(conn, hunts, h, b, uid) if len(b.fighters) > 1 else None
        if f.pick is not None or not f.active:              # you have moved (or fallen): wait for the others
            for a in F["main"] + F["side"]:
                a["ready"] = False
                for t in a.get("techs", []):
                    t["ready"] = False
        out["mode"] = "fight"
        out["fight"] = F
        return out
    if h.map:
        return {**out, **map_view(conn, h, uid, p, lead)}
    e = h.exps.get(uid)
    out["mode"] = "between"
    out["story"] = [rich(x) for x in h.story]
    out["mine"] = [rich(x) for x in h.lines.get(uid, [])]
    out["hp"], out["max_hp"] = (round(e.hp), round(e.max_hp)) if e else (0, 1)
    out["hp_pct"] = round(out["hp"] / max(1, out["max_hp"]) * 100)
    out["found"] = ep.found_list(e) if e else []
    out["lead"] = lead
    out["deeper"] = lead and h.step < hunting.MAX_ENCOUNTERS
    out["next_note"] = (f"Beast {h.step + 1}: rarer beasts, and Normal beasts are +{h.step * 10}% stronger."
                        if h.step < hunting.MAX_ENCOUNTERS else "This is as deep as a hunt goes. Head home.")
    out["members"] = [_member_row(conn, h, u, party) for u in h.order]
    out["idle"] = max(0, round(h.touched + IDLE_SECONDS - hunts.clock()))
    return out


def walks(conn, uid):
    """Whether this player walks the hunting-ground map (web/hunt_map.py) on a Solo Hunt: everyone whose look has a
    walking sheet (looks.WALK_SHEETS). A look without one keeps the menus."""
    import looks
    p = db.get_player(conn, uid)
    return p is not None and looks.walk_sheet(looks.of_player(p)) is not None


def map_view(conn, h, uid, p, lead):
    """The map page's data: the walking sheet, where you are, and the beast waiting out there."""
    import json
    import looks
    e = h.exps.get(uid)
    beast = None
    if h.beast:
        b = h.beast
        beast = {"name": b["name"], "tier": b["tier"], "tierName": TIER_WORD[b["tier"]].strip() or "Normal",
                 "role": b["role"].title(), "x": b["x"], "y": b["y"], "src": f"/art/beasts/{beasts.slug(b['name'])}.png"}
    m = hunt_map.plan(h.loc["key"])
    x, y = h.pos.get(uid, (*hunt_map.start(m), 0))[:2]
    data = {"sheet": looks.walk_sheet(looks.of_player(p)), "hero": {"x": x, "y": y}, "beast": beast,
            "size": hunt_map.SIZE, "reach": hunt_map.REACH, "start": list(hunt_map.start(m)),
            **hunt_map.page_data(h.loc["key"]),
            "turn": None, "step": h.step, "steps": hunting.MAX_ENCOUNTERS}
    return {"mode": "map", "story": [rich(x) for x in h.story], "mine": [rich(x) for x in h.lines.get(uid, [])],
            "hp": round(e.hp) if e else 0, "max_hp": round(e.max_hp) if e else 1,
            "hp_pct": round((e.hp if e else 0) / max(1, e.max_hp if e else 1) * 100),
            "found": ep.found_list(e) if e else [], "lead": lead, "map": data, "map_json": json.dumps(data).replace("</", "<\\/")}


def _member_row(conn, h, u, party):
    pl = db.get_player(conn, u)
    e = h.exps.get(u)
    state = "Hunting" if e else (h.results.get(u, {}) or {}).get("title", "Left")
    return {"name": pl["name"] if pl else "?", "realm": pl["realm"] if pl else "", "leader": party and party.leader == u,
            "hp": round(e.hp) if e else 0, "max_hp": round(e.max_hp) if e else 1,
            "hp_pct": round(e.hp / max(1, e.max_hp) * 100) if e else 0, "state": state, "out": e is None}


# Each player's colour in a team fight (SHOAIB Nov 27: the round portraits look alike): you are always gold,
# teammates blue, purple and teal in the party's order, the same all fight; their portrait rings and their names in
# the fight's messages use it (fight.js `partyNames`). Presentation only.
YOU_COLOR, PARTY_COLORS = "#E8C27A", ("#5FA8FF", "#B48CFF", "#3FD2B4", "#FF8A6A")


def team_view(conn, hunts, h, b, uid):
    left = max(0, h.turn_started + TEAM_TURN_SECONDS - hunts.clock())
    allies = []
    others = 0
    for f in b.fighters:
        pl = db.get_player(conn, f.uid)
        allies.append({"name": f.name, "me": f.uid == uid, "hp": round(max(0, f.hp)), "max_hp": round(f.max_hp),
                       "hp_pct": max(0, round(f.hp / max(1, f.max_hp) * 100)),
                       "state": "Fallen" if f.hp <= 0 else "Fled" if f.fled else "Standing" if b.over else
                                "Ready" if f.pick is not None else "Choosing",
                       "face": ep.look_face(pl) if pl else None,
                       # their own strike picture, for when they dash in and hit the beast (fight.js `cameo`)
                       "strike": ep.look_poses(pl).get("strike") if pl and f.uid != uid else None})
        if f.uid == uid:
            allies[-1]["color"] = YOU_COLOR
        else:
            allies[-1]["color"] = PARTY_COLORS[others % len(PARTY_COLORS)]
            others += 1
    allies.sort(key=lambda a: not a["me"])                    # you first, then the party in its order
    me = b.fighter(uid)
    return {"allies": allies, "left": round(left), "total": TEAM_TURN_SECONDS,
            "waiting": me is not None and (me.pick is not None or not me.active) and not b.over,
            "fallen": me is not None and me.hp <= 0}
