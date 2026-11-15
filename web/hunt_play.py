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
from .forge_play import rich
from .profile import number

TEAM_TURN_SECONDS = 30            # a team turn: everyone picks, or the stragglers Guard
SOLO_TURN_SECONDS = ep.TURN_LIMIT  # alone, the turn waits for you, as in Explore
IDLE_SECONDS = ep.IDLE_SECONDS    # between beasts, the leader decides within this or the party heads home
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

    def start(self, conn, uid):
        """The leader sets out. None, or why not."""
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
            h = Hunt(party.id, hunting.location(party.location), rng, exps, party.uids(), touched=now)
            self._h[party.id] = h
            party.hunting = True
            self.parties._bump(party)
            self._next(conn, h)
            return None

    # ── the beasts ──────────────────────────────────────────────────

    def _next(self, conn, h):
        """Walk on: the next beast of this location comes out."""
        h.step += 1
        h.story, h.lines, h.ended, h.acked, h.notice = [], {}, None, set(), {}
        uids = h.active()
        party = [h.exps[u] for u in uids]
        lead = party[0].player
        luck = gear.artifact_bonus(lead, "explore_luck") + gear.artifact_bonus(lead, "rare_encounters")
        tier = loot.pick(hunting.tier_odds(h.step, luck), h.rng)
        name, _, role, _home = h.rng.choice([b for b in hunting.pool(h.loc) if b[1] == tier])
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
            if h.battle is None and not h.over and now > h.touched + IDLE_SECONDS:
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
            if what == "deeper" and lead and uid in h.exps and h.step < hunting.MAX_ENCOUNTERS:
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
           "notice": rich(h.notice[uid]) if h.notice.get(uid) else None}
    party = hunts.parties.of(uid)
    lead = party is not None and party.leader == uid
    if uid in h.results and (h.over or uid not in h.exps):
        out["mode"] = "home"
        out["result"] = h.results[uid]
        out["solo"] = party.solo if party else True
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


def _member_row(conn, h, u, party):
    pl = db.get_player(conn, u)
    e = h.exps.get(u)
    state = "Hunting" if e else (h.results.get(u, {}) or {}).get("title", "Left")
    return {"name": pl["name"] if pl else "?", "realm": pl["realm"] if pl else "", "leader": party and party.leader == u,
            "hp": round(e.hp) if e else 0, "max_hp": round(e.max_hp) if e else 1,
            "hp_pct": round(e.hp / max(1, e.max_hp) * 100) if e else 0, "state": state, "out": e is None}


def team_view(conn, hunts, h, b, uid):
    left = max(0, h.turn_started + TEAM_TURN_SECONDS - hunts.clock())
    allies = []
    for f in b.fighters:
        pl = db.get_player(conn, f.uid)
        allies.append({"name": f.name, "me": f.uid == uid, "hp": round(max(0, f.hp)), "max_hp": round(f.max_hp),
                       "hp_pct": max(0, round(f.hp / max(1, f.max_hp) * 100)),
                       "state": "Fallen" if f.hp <= 0 else "Fled" if f.fled else "Standing" if b.over else
                                "Ready" if f.pick is not None else "Choosing",
                       "face": ep.look_face(pl) if pl else None})
    me = b.fighter(uid)
    return {"allies": allies, "left": round(left), "total": TEAM_TURN_SECONDS,
            "waiting": me is not None and (me.pick is not None or not me.active) and not b.over,
            "fallen": me is not None and me.hp <= 0}
