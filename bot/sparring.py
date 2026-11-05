"""
/spar — a training fight against a master NPC (docs/technique.md).

Each turn the master picks Strike, Guard or Break from a repeating pattern
(with the odd surprise) and you answer. Guard beats Strike, Break beats Guard,
Strike beats Break; the winner of an exchange lands a hit, a tie hurts both
a little. Your attack technique is a stronger Strike and your defense
technique a stronger Guard.

Techniques have a cooldown (technique.TECHNIQUE_COOLDOWN_TURNS): after you
use one it rests for a few exchanges and its button is greyed out. Plain
Strike, Guard and Break are always available.

Mastery EXP comes only from techniques used at the right moment:
  • attack technique right after you blocked the master's Strike
  • defense technique against the master's Strike
+30 per well-timed use, +100 to each well-timed technique for winning.
A trial is the same fight against a stronger master; winning raises the stage.
"""
import random

import challenges
import technique

from . import combat
from . import player as rules
from .trainer import STANCES, TELLS

# DEFAULTS where technique.md is open
MAX_TURNS = 15
TELL_CHANCE = 0.5          # turns where the master shows a tell; otherwise read his rhythm
PATTERN_BREAK_CHANCE = 0.15
CLASH_DAMAGE = 0.5         # share of a normal hit both sides take on a tie


class Spar:
    def __init__(self, player, techniques, weapon=None, strength=1.0, rng=None):
        self.rng = rng or random.Random()
        hp, self.attack, self.defense = rules.final_stats(player, techniques, weapon)
        self.hp = self.max_hp = hp
        mhp, matk, mdef = rules.base_stats(player["realm"], player["layer"])
        self.m_hp = self.m_max = round(mhp * strength)
        self.m_attack, self.m_defense = matk * strength, mdef * strength
        self.strength = strength
        self.atk_t = next((t for t in techniques if t["type"] == "attack"), None)
        self.def_t = next((t for t in techniques if t["type"] == "defense"), None)
        self.pattern = [self.rng.choice(STANCES) for _ in range(self.rng.randint(3, 4))]
        self.turn = 0
        self.blocked_strike = False      # last turn you Guarded the master's Strike
        self.timed = {}                  # technique id → well-timed uses
        self.cooldowns = {"attack_tech": 0, "defense_tech": 0}   # exchanges until ready
        self.log = []
        self._next()

    def _next(self):
        self.turn += 1
        st = self.pattern[(self.turn - 1) % len(self.pattern)]
        if self.rng.random() < PATTERN_BREAK_CHANCE:
            st = self.rng.choice(STANCES)
        self.master = st
        self.tell = self.rng.choice(TELLS[st]) if self.rng.random() < TELL_CHANCE else None

    @property
    def over(self):
        return self.hp <= 0 or self.m_hp <= 0 or self.turn > MAX_TURNS

    @property
    def won(self):
        if self.m_hp <= 0:
            return True
        if self.hp <= 0:
            return False
        return self.m_hp / self.m_max < self.hp / self.max_hp   # time ran out: better shape wins

    def choices(self):
        out = [(s, s.title()) for s in STANCES]
        if self.atk_t:
            out.append(("attack_tech", self.atk_t["name"]))
        if self.def_t:
            out.append(("defense_tech", self.def_t["name"]))
        return out

    def ready(self, choice):
        """True if this choice can be played now (techniques may be cooling down)."""
        return self.cooldowns.get(choice, 0) == 0

    def _tick_cooldowns(self, used):
        for key in self.cooldowns:
            self.cooldowns[key] = max(0, self.cooldowns[key] - 1)
        if used in self.cooldowns:
            tech = self.atk_t if used == "attack_tech" else self.def_t
            self.cooldowns[used] = combat.cooldown_turns(tech)

    def _hit_master(self, skill=1.0, pierce=0.0):
        dmg = combat.damage(self.attack, self.m_defense, self.m_max, skill, pierce, self.rng)
        self.m_hp = max(0, self.m_hp - dmg)
        return dmg

    def _hit_me(self, scale=1.0):
        dmg = combat.damage(self.m_attack, self.defense, self.max_hp, rng=self.rng) * scale
        self.hp = max(0, self.hp - dmg)
        return dmg

    def _timed(self, tech):
        self.timed[tech["id"]] = self.timed.get(tech["id"], 0) + 1

    def play(self, choice):
        """Resolve one exchange. Returns a line describing it."""
        if not self.ready(choice):
            return f"⏳ That technique is still recovering ({self.cooldowns[choice]} more exchange(s))."
        m = self.master
        me = {"attack_tech": "strike", "defense_tech": "guard"}.get(choice, choice)
        use_atk = choice == "attack_tech"
        use_def = choice == "defense_tech"
        was_blocked = self.blocked_strike
        self.blocked_strike = False
        notes = []

        if use_atk and was_blocked:
            self._timed(self.atk_t)
            notes.append(f"🎯 Perfect timing with **{self.atk_t['name']}**!")
        if use_def and m == "strike":
            self._timed(self.def_t)
            notes.append(f"🎯 **{self.def_t['name']}** meets his Strike at the right moment!")

        skill, pierce, hits = 1.0, 0.0, 1
        if use_atk:
            skill = technique.ATTACK_TECHNIQUE[self.atk_t["grade"]][0] * rules.mastery_mult(self.atk_t)
            eff = rules.TECH_BY_NAME.get(self.atk_t["name"], {}).get("effect")
            if eff and eff[0] == "combo":
                hits, skill = eff[1][0], skill * eff[1][1]
            elif eff and eff[0] == "pierce":
                pierce = eff[1]
            elif eff and eff[0] == "heavy":
                skill *= eff[1]

        if me == m:
            mine = self._hit_master(skill * CLASH_DAMAGE, pierce) if me != "guard" else 0
            theirs = self._hit_me(CLASH_DAMAGE) if m != "guard" else 0
            line = (f"Both of you {m.title()}! "
                    + (f"You trade blows ({mine:.0f} / {theirs:.0f})." if mine or theirs else "Neither gives ground."))
        elif challenges.COUNTERS[m] == me:          # you win the exchange
            if me == "guard":
                self.blocked_strike = True
                line = "🛡️ You Guard his Strike. An opening!"
                if use_def:
                    eff = rules.TECH_BY_NAME.get(self.def_t["name"], {}).get("effect")
                    if eff and eff[0] == "counter":
                        self.m_hp = max(0, self.m_hp - self.m_attack * eff[1])
                        line += " Your counter stings him."
                    elif eff and eff[0] == "recover":
                        self.hp = min(self.max_hp, self.hp + self.max_hp * eff[1])
                        line += " You recover a little."
            else:
                total = sum(self._hit_master(skill, pierce) for _ in range(hits))
                verb = "Break through his Guard" if me == "break" else "Strike before his Break lands"
                line = f"⚔️ You {verb}! (−{total:.0f})"
        else:                                       # he wins
            scale = 1.0
            if m == "break" and use_def:
                eff = rules.TECH_BY_NAME.get(self.def_t["name"], {}).get("effect")
                if eff and eff[0] == "unbreakable":
                    scale = 0.5
            if m == "guard":
                line = f"🛡️ He Guards your {me.title()}. Nothing lands."
            else:
                dmg = self._hit_me(scale)
                line = f"💥 His {m.title()} beats your {me.title()}! (−{dmg:.0f})"
        self.log.append(line)
        self._tick_cooldowns(choice)
        self._next()
        return " ".join(notes + [line])

    def hint(self):
        if self.tell:
            return f"🥋 *{self.tell}*"
        if self.turn > len(self.pattern):
            return "🥋 *His face gives nothing away... but masters move in rhythms.*"
        return "🥋 *His face gives nothing away.*"

    def mastery_awards(self, daily=1.0):
        """{technique_id: exp} before Blessing bonuses."""
        out = {}
        for tid, uses in self.timed.items():
            exp = uses * technique.SPAR_EXP_PER_TIMED_USE
            if self.won:
                exp += technique.SPAR_WIN_EXP
            out[tid] = exp * daily
        return out

