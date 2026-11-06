"""
Friendly PvP duels (/duel). Rules: docs/pvp.md. Numbers: pvp.py (repo root).

A Duel holds all state and has no Discord code, so it can be tested directly.
bot/duel_view.py shows it as one card + buttons and edits that message every turn.

Each turn:
  1. Both players pick SECRETLY at the same time: Strike, Guard, Break or an equipped technique.
     No pick in time = Guard; three timeouts in a row = that player forfeits.
  2. resolve() reveals both moves and plays them against each other with the beast-fight counters:
     Strike beats Break, Guard beats Strike, Break beats Guard; the same move on both sides clashes.
Fair duel: both use the base stats of the lower player's realm and layer, and weapon / armor / technique
% buffs count at half strength (pvp.BUFF_SHARE). Combat artifacts work at half strength
(equipments.DUEL_COMBAT_ARTIFACT_STRENGTH). Technique effects and mastery count fully.
"""
import random

import equipments
import pvp
import stats
import technique

from . import combat, gear
from . import player as rules

MOVES = ("strike", "guard", "break")
CHOICES = MOVES + ("attack_tech", "defense_tech")
BASE_MOVE = {"strike": "strike", "guard": "guard", "break": "break", "attack_tech": "strike", "defense_tech": "guard"}
MOVE_LABEL = {"strike": "Strike", "guard": "Guard", "break": "Break"}


def tech_effect(tech):
    return rules.TECH_BY_NAME.get(tech["name"], {}).get("effect") if tech else None


def lower_of(p1, p2):
    """(realm, layer) of the lower of two players: the lower realm, or the lower layer in the same realm."""
    key = lambda p: (rules.realm_index(p["realm"]), p["layer"])     # noqa: E731
    low = min((p1, p2), key=key)
    return low["realm"], low["layer"]


def fair_stats(player, techniques, weapon, realm, layer, armor=None):
    """(hp, attack, defense) for a fair duel: the base stats of (realm, layer), plus this player's
    weapon, armor and technique % buffs at pvp.BUFF_SHARE strength."""
    hp, attack, defense = rules.base_stats(realm, layer)
    pct = {k: sum(v for _, v in src) * pvp.BUFF_SHARE
           for k, src in rules.stat_buffs(techniques, weapon, armor).items()}
    return (round(hp * (1 + pct["hp"])), round(attack * (1 + pct["attack"])), round(defense * (1 + pct["defense"])))


class Duelist:
    """One side of the duel."""

    def __init__(self, player, techniques, hp, attack, defense, weapon=None, fx=None):
        self.player = player
        self.uid = player["user_id"]
        self.name = player["name"]
        self.realm, self.layer = player["realm"], player["layer"]
        self.talent = player.get("talent", "Ordinary")
        self.hp = self.max_hp = hp
        self.attack, self.defense = attack, defense
        self.techs = techniques
        self.weapon = weapon
        self.fx = fx if fx is not None else gear.combat_fx(player)   # combat artifact effects (bot/gear.py)
        self.atk_t = next((t for t in techniques if t["type"] == "attack"), None)
        self.def_t = next((t for t in techniques if t["type"] == "defense"), None)
        self.cooldowns = {"attack_tech": 0, "defense_tech": 0}
        self.pick = None                 # this turn's choice (secret until both have picked)
        self.last_move = None            # label of the move played last turn
        self.last_dealt = 0              # damage dealt last turn
        self.timeouts = 0                # timeouts in a row
        self.staggered = False           # broken last turn: takes more damage this turn
        self.guard_weak = 0.0            # share of a Strike that slips through this player's next Guard
        self.healed = 0.0                # HP healed by Recover so far (capped per duel)
        self.evaded_turn = -99           # last turn Evade triggered
        self.dealt = 0.0

    def tech(self, key):
        return self.atk_t if key == "attack_tech" else self.def_t

    def ready(self, choice):
        if choice in ("attack_tech", "defense_tech"):
            return self.tech(choice) is not None and self.cooldowns[choice] == 0
        return choice in MOVES

    def move_label(self, choice):
        if choice in ("attack_tech", "defense_tech"):
            return self.tech(choice)["name"]
        return MOVE_LABEL[choice]

    @property
    def hp_frac(self):
        return self.hp / self.max_hp if self.max_hp else 0


def make_duelist(player, techniques, weapon, realm, layer, armor=None):
    """Fair Duel side: armor counts at half like the weapon, combat artifacts at half strength."""
    hp, atk, dfn = fair_stats(player, techniques, weapon, realm, layer, armor)
    return Duelist(player, techniques, hp, atk, dfn, weapon,
                   fx=gear.combat_fx(player, equipments.DUEL_COMBAT_ARTIFACT_STRENGTH))


def start(p1, techs1, weapon1, p2, techs2, weapon2, rng=None, armor1=None, armor2=None):
    """A fair duel between two players (p1 is the challenger)."""
    realm, layer = lower_of(p1, p2)
    return Duel(make_duelist(p1, techs1, weapon1, realm, layer, armor1),
                make_duelist(p2, techs2, weapon2, realm, layer, armor2), rng, fair=(realm, layer))


class Duel:
    def __init__(self, a, b, rng=None, fair=None):
        self.rng = rng or random.Random()
        self.fair = fair                 # (realm, layer) both fight at
        self.sides = [a, b]
        self.turn = 1
        self.result = None               # "won" or "draw"
        self.winner = None               # the winning Duelist (None on a draw)
        self.reason = None               # "ko", "forfeit", "timeouts", "time" (turn limit)
        self.log = [("star", f"{a.name} and {b.name} bow to each other. Begin!")]
        self.history = []                # one entry per turn, for the duel log table

    # ── state ─────────────────────────────────────────────────────────

    @property
    def over(self):
        return self.result is not None

    def duelist(self, uid):
        return next((d for d in self.sides if d.uid == uid), None)

    def other(self, d):
        return self.sides[1] if d is self.sides[0] else self.sides[0]

    def locked(self, d):
        """Has this player picked this turn? (Never WHAT they picked.)"""
        return d.pick is not None

    def both_picked(self):
        return all(d.pick is not None for d in self.sides)

    def intensity(self, turn=None):
        """Extra damage share from rising intensity on this turn: 0 before pvp.INTENSITY_START_TURN."""
        turn = self.turn if turn is None else turn
        if turn < pvp.INTENSITY_START_TURN:
            return 0.0
        return round((turn - pvp.INTENSITY_START_TURN + 1) * pvp.INTENSITY_PER_TURN, 4)

    # ── picking ───────────────────────────────────────────────────────

    def choose(self, uid, choice):
        """Record a secret pick. Returns None, or why it was refused. Resolves nothing."""
        d = self.duelist(uid)
        if self.over or d is None:
            return "You are not in this duel."
        if choice not in CHOICES:
            return "That move isn't allowed in a duel."
        if d.pick is not None:
            return f"You already locked in **{d.move_label(d.pick)}** this turn."
        if not d.ready(choice):
            if d.tech(choice) is None:
                return "You have no technique of that kind equipped."
            left = d.cooldowns[choice]
            return f"That technique is still recovering ({left} more turn{'s' if left != 1 else ''})."
        d.pick = choice
        d.timeouts = 0
        return None

    def forfeit(self, uid):
        """A player flees (or walks away): the other one wins."""
        d = self.duelist(uid)
        if self.over or d is None:
            return
        for x in self.sides:
            x.last_dealt = 0
        self._finish(self.other(d), "forfeit")
        self.log = [("flee", f"{d.name} fled the duel. {self.other(d).name} wins by forfeit.")]

    # ── resolving a turn ──────────────────────────────────────────────

    def _skill(self, d, choice):
        """(skill, pierce, hits, stagger) for this player's attacking move."""
        if choice == "break":
            return pvp.BREAK_SKILL, 0.0, 1, 0.0
        if choice != "attack_tech":
            return stats.BASIC_ATTACK_MULTIPLIER, 0.0, 1, 0.0
        t = d.atk_t
        skill = technique.ATTACK_TECHNIQUE[t["grade"]][0] * rules.mastery_mult(t)
        eff = tech_effect(t)
        pierce, hits, stagger = 0.0, 1, 0.0
        if eff and eff[0] == "combo":
            hits, skill = eff[1][0], skill * eff[1][1]
        elif eff and eff[0] == "pierce":
            pierce = eff[1]
        elif eff and eff[0] == "heavy":
            skill *= eff[1]
        elif eff and eff[0] == "stagger":
            stagger = eff[1]
        return skill, pierce, hits, stagger

    def _hit(self, att, dfn, skill, pierce=0.0, hits=1, share=1.0):
        """Damage from att to dfn: stats.md formula, stagger bonus and rising intensity, then the 30% cap."""
        total = 0.0
        for _ in range(hits):
            total += combat.damage(att.attack, dfn.defense, float("inf"), skill * share, pierce, self.rng)
        if dfn.staggered:
            total *= pvp.STAGGER_DAMAGE_BONUS
        total *= 1 + self.intensity()
        return min(total, dfn.max_hp * stats.MAX_HIT_PERCENT)

    def _attack(self, att, a_choice, dfn, d_choice, notes):
        """What att's move does to dfn. Returns (damage to dfn, damage back to att, a log line or None)."""
        mine, theirs = BASE_MOVE[a_choice], BASE_MOVE[d_choice]
        label = att.move_label(a_choice)
        if mine == "guard":
            return 0, 0, None
        skill, pierce, hits, stagger = self._skill(att, a_choice)
        def_tech = d_choice == "defense_tech"
        eff = tech_effect(dfn.def_t) if def_tech else None
        share, note = 1.0, ""
        if mine == "strike":
            if theirs == "strike":
                share, note = pvp.CLASH_DAMAGE, "blows clash"
            elif theirs == "break":
                note = "beats the Break"
                if att.fx.get("strike_vs_break_damage"):                       # Fang artifact
                    share = 1 + att.fx["strike_vs_break_damage"]
                    note += f" (Fang +{att.fx['strike_vs_break_damage']:.0%})"
            else:                                       # Guard beats Strike
                if dfn.guard_weak > 0:
                    share, note = dfn.guard_weak, "slips through the weakened guard"
                else:
                    blocked = self._hit(att, dfn, skill, pierce, hits)
                    line = f"{att.name} — {label}: blocked by {dfn.name}"
                    back = 0
                    if eff and eff[0] == "counter":
                        back = min(blocked * eff[1], att.max_hp * stats.MAX_HIT_PERCENT)
                        line += f", countered for {back:,.0f}"
                    mirror = dfn.fx.get("guard_reflect")
                    if mirror:                                                  # Mirror artifact
                        reflected = blocked * mirror
                        back = min(back + reflected, att.max_hp * stats.MAX_HIT_PERCENT)
                        line += f", Mirror reflects {reflected:,.0f}"
                    elif eff and eff[0] == "recover":
                        room = dfn.max_hp * pvp.RECOVER_MAX_PER_DUEL - dfn.healed
                        heal = round(max(0.0, min(dfn.max_hp * eff[1], room)))
                        if heal > 0:
                            notes.append(("heal", dfn, heal))
                            line += f", {dfn.name} recovers {heal:,}"
                        else:
                            line += f" (Recover used up: max {pvp.RECOVER_MAX_PER_DUEL:.0%} per duel)"
                    return 0, back, ("shield", line)
        else:                                           # Break
            if theirs == "strike":
                return 0, 0, ("fist", f"{att.name} — {label}: too slow, {dfn.name}'s Strike lands first")
            if theirs == "break":
                share, note = pvp.CLASH_DAMAGE, "the two charges collide"
            else:                                       # Break beats Guard
                note = "the guard shatters!"
                if eff and eff[0] == "evade":
                    if self.turn - dfn.evaded_turn > pvp.EVADE_COOLDOWN_TURNS and self.rng.random() < eff[1]:
                        dfn.evaded_turn = self.turn
                        return 0, 0, ("shield", f"{att.name} — {label}: {dfn.name} slips away (Evade)")
                if eff and eff[0] == "unbreakable":
                    share, note = 0.5, "the guard holds half (Unbreakable)"
                notes.append(("stagger", dfn, 0))
        dodge = dfn.fx.get("dodge_chance")
        if dodge and self.rng.random() < dodge:                                 # Feather artifact
            return 0, 0, ("shield", f"{att.name} — {label}: {dfn.name} sidesteps it (Feather)")
        dmg = self._hit(att, dfn, skill, pierce, hits, share)
        if stagger and dmg > 0:
            notes.append(("weaken", dfn, stagger))
        jolt = att.fx.get("break_stagger_chance")
        if mine == "break" and theirs != "guard" and dmg > 0 and jolt and self.rng.random() < jolt:
            notes.append(("stagger", dfn, 0))                                   # Thunder artifact
            note = (note + ", " if note else "") + "Thunder: staggered!"
        icon = "sword" if mine == "strike" else "fist"
        return dmg, 0, (icon, f"{att.name} — {label}: {dmg:,.0f} dmg" + (f", {note}" if note else ""))

    def resolve(self):
        """Reveal both picks and play the turn. A player who has not picked Guards (a timeout)."""
        if self.over:
            return []
        a, b = self.sides
        log, picks, timed = [], {}, {}
        for d in self.sides:
            timed[d] = d.pick is None
            if d.pick is None:
                d.timeouts += 1
                d.pick = pvp.TIMEOUT_MOVE
                log.append(("hourglass", f"{d.name} hesitated: Guard."))
            picks[d] = d.pick
        gone = [d for d in self.sides if d.timeouts >= pvp.TIMEOUTS_TO_FORFEIT]
        if gone:
            for d in self.sides:
                d.last_dealt = 0
            self._record(picks, timed, {a: 0, b: 0})
            for d in self.sides:
                d.pick = None
            if len(gone) == 2:
                self._finish(None, "timeouts")
                self.log = log + [("flee", "Both stood frozen too long. The duel is a draw.")]
            else:
                self._finish(self.other(gone[0]), "timeouts")
                self.log = log + [("flee", f"{gone[0].name} stood frozen too long and forfeits. "
                                           f"{self.other(gone[0]).name} wins.")]
            return self.log

        # reveal
        log.insert(0, ("star", f"{a.name}: {a.move_label(picks[a])}  ·  {b.name}: {b.move_label(picks[b])}"))
        for d in self.sides:
            for k in d.cooldowns:
                d.cooldowns[k] = max(0, d.cooldowns[k] - 1)
            if picks[d].endswith("_tech"):
                d.cooldowns[picks[d]] = combat.cooldown_turns(d.tech(picks[d]))
                reset = d.fx.get("cooldown_reset_chance")
                if reset and self.rng.random() < reset:                         # Focus artifact
                    d.cooldowns[picks[d]] = 0
                    log.append(("star", f"{d.name} — Focus: {d.tech(picks[d])['name']} is ready again at once!"))
        notes = []
        dmg_ab, back_a, line_a = self._attack(a, picks[a], b, picks[b], notes)
        dmg_ba, back_b, line_b = self._attack(b, picks[b], a, picks[a], notes)
        log += [line for line in (line_a, line_b) if line]
        if BASE_MOVE[picks[a]] == BASE_MOVE[picks[b]] == "guard":
            log.append(("shield", "Both hold their guard. Nothing happens."))
        to_a = round(dmg_ba + back_a)                   # counters (and Mirror) land on the attacker
        to_b = round(dmg_ab + back_b)
        a.hp, b.hp = max(0, a.hp - to_a), max(0, b.hp - to_b)
        a.last_dealt, b.last_dealt = to_b, to_a
        a.dealt += to_b
        b.dealt += to_a
        for d in self.sides:
            d.last_move = d.move_label(picks[d])
            d.staggered = False
            d.guard_weak = 0.0
        for kind, d, val in notes:
            if kind == "heal" and d.hp > 0:
                d.hp = min(d.max_hp, d.hp + val)
                d.healed += val
            elif kind == "stagger":
                d.staggered = True
            elif kind == "weaken":
                d.guard_weak = max(d.guard_weak, min(1.0, val))
        for d in self.sides:
            lotus = d.fx.get("heal_per_turn")
            if lotus and 0 < d.hp < d.max_hp and a.hp > 0 and b.hp > 0:        # Lotus artifact
                heal = min(d.max_hp - d.hp, max(1, round(d.max_hp * lotus)))
                d.hp += heal
                log.append(("herb", f"{d.name} — Lotus: +{heal:,}"))
        self._record(picks, timed, {a: to_b, b: to_a})
        for d in self.sides:
            d.pick = None

        if a.hp <= 0 and b.hp <= 0:
            self._finish(None, "ko")
            log.append(("skull", "Both fall at the same moment. A draw!"))
        elif a.hp <= 0 or b.hp <= 0:
            win = a if b.hp <= 0 else b
            self._finish(win, "ko")
            log.append(("skull", f"{self.other(win).name} is down. {win.name} wins!"))
        elif self.turn >= pvp.MAX_TURNS:
            self.decide_on_time(log)
        self.log = log
        if not self.over:
            self.turn += 1
        return self.log

    def decide_on_time(self, log=None):
        """The turn limit: the higher % of HP left wins, a draw if equal."""
        a, b = self.sides
        fa, fb = round(a.hp_frac, 4), round(b.hp_frac, 4)
        if fa == fb:
            self._finish(None, "time")
            line = f"Turn {pvp.MAX_TURNS}: time! Both have {fa:.0%} HP left. A draw."
        else:
            win = a if fa > fb else b
            self._finish(win, "time")
            line = (f"Turn {pvp.MAX_TURNS}: time! {win.name} wins with {win.hp_frac:.0%} HP left "
                    f"against {self.other(win).hp_frac:.0%}.")
        if log is not None:
            log.append(("star", line))

    def _finish(self, winner, reason):
        self.winner = winner
        self.result = "won" if winner else "draw"
        self.reason = reason

    def _record(self, picks, timed, dealt):
        self.history.append({"turn": self.turn, "moves": [
            {"user_id": d.uid, "move": picks[d], "technique": d.tech(picks[d])["name"] if picks[d].endswith("_tech") else None,
             "timed_out": timed[d], "damage": dealt[d], "hp_after": max(0, d.hp)} for d in self.sides]})

    # ── after the duel ────────────────────────────────────────────────

    def loser(self):
        return self.other(self.winner) if self.winner else None
