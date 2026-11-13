"""
Interactive turn-based fights: /explore beasts and bandits, Elite Lair and Beast King team hunts.
Rules: docs/combat.md. Numbers: battle.py (repo root).

A Battle holds all state and has no Discord code, so it can be tested directly.
bot/fight_view.py shows it as one card + buttons and edits that message every turn.

Each turn:
  1. The enemy has already planned its move (shown in the warning bar when it is telegraphed).
  2. Every fighter picks a move (secretly in team hunts): Strike, Guard, Break, a technique,
     a Mending pill or Flee. No pick in time = Guard; three timeouts in a row = flee.
  3. resolve() plays the turn: Strike beats Break, Guard beats Strike, Break beats Guard.

Combat artifacts (bot/gear.py, docs/equipment.md) ride on each Fighter as `fx`: Fang (Strike beats
Break), Bell (charged attacks), Mirror (Guard reflects), Thunder (Break staggers), Lotus (heal per
turn), Feather (dodge) and Focus (a free technique).

Techniques spend Battle Qi (battle.BATTLE_QI_START, TECHNIQUE_QI_COST); there are no technique cooldowns here.

Forged weapon and armor passives (docs/forge.md) ride on each Fighter as `kit` (bot/passives.Kit): the turn
asks it for damage bonuses, what a landed hit does (Lifesteal...), how a hit taken is softened (Golden Body...),
lethal saves (Phoenix Rebirth) and the end-of-turn effects, and writes its lines in the battle log.
The 30% per-hit cap still applies after every passive.
"""
import random

import battle
import beasts
import challenges
import stats
import technique

from . import combat, gear, passives
from . import player as rules

MOVES = ("strike", "guard", "break")
BASE_MOVE = {"strike": "strike", "guard": "guard", "break": "break", "attack_tech": "strike", "defense_tech": "guard"}
MOVE_LABEL = {"strike": "Strike", "guard": "Guard", "break": "Break", "pill": "Pill", "flee": "Flee"}

TELLS = {
    "strike": ["The {name} bares its fangs, ready to pounce...", "The {name} coils to leap at you..."],
    "guard": ["The {name} hunkers low, hide bristling...", "The {name} backs off, wary of your blows..."],
    "break": ["The {name} paws the ground, ready to crash through any guard...",
              "The {name} lowers its head to charge straight through..."],
}
BANDIT_TELLS = {
    "strike": ["The {name} raise their blades for a quick slash..."],
    "guard": ["The {name} close ranks behind their shields..."],
    "break": ["The {name} wind up a heavy overhead chop..."],
}
NO_TELL = "The {name} circles you, watching for an opening..."


def short_name(name):
    """'White-Browed Tiger King' -> 'Tiger King', 'Flame-Maned Lion' -> 'Lion' (for the warning bar)."""
    base = name.split(",")[0].split("(")[0].strip()
    words = base.split()
    if len(words) >= 2 and words[-1] == "King":
        return " ".join(words[-2:])
    return words[-1]


def tech_effect(tech):
    return rules.TECH_BY_NAME.get(tech["name"], {}).get("effect") if tech else None


def break_held(def_t, eff):
    """Share of a Break a defense technique still holds (technique.md): its block %, then Unbreakable halves the
    rest. 0 for a plain Guard."""
    rest = 1.0
    if battle.DEFENSE_TECH_BLOCKS_BREAK:
        block = technique.DEFENSE_TECHNIQUE[def_t["grade"]][0] * rules.mastery_mult(def_t)
        rest -= min(technique.MAX_DAMAGE_BLOCKED, block)
    if eff and eff[0] == "unbreakable":
        rest *= 0.5
    return 1 - rest


class Fighter:
    """One player in the fight."""

    def __init__(self, player, techniques, hp, max_hp, attack, defense, pills=None):
        self.player = player
        self.uid = player["user_id"]
        self.name = player["name"]
        self.realm, self.layer = player["realm"], player["layer"]
        self.hp, self.max_hp, self.attack, self.defense = hp, max_hp, attack, defense
        self.techs = techniques
        self.atk_t = next((t for t in techniques if t["type"] == "attack"), None)
        self.def_t = next((t for t in techniques if t["type"] == "defense"), None)
        self.cooldowns = {"attack_tech": 0, "defense_tech": 0}   # always 0 here: Battle Qi limits techniques
        self.max_bqi = battle.BATTLE_QI_START + (player.get("spirit") or 0) * stats.SPIRIT_BATTLE_QI
        self.bqi = self.max_bqi           # Battle Qi: full at the start of every fight
        self.free_cast = False            # Sword Heart: the next technique costs nothing
        self.statuses = {}                # key -> turns left
        self.pills = pills or []          # [{"id", "name", "heal", "qty"}] Mending pills in the bag
        self.pills_used = 0
        self.pick = None                  # this turn's choice
        self.last_move = None             # label of the move played last turn
        self.timeouts = 0
        self.fled = False
        self.atk_uses = self.guard_uses = 0
        self.dealt = 0.0
        self.fx = gear.combat_fx(player)  # combat artifact effects {effect: value}
        self.kit = passives.kit_for(player)   # forged weapon / armor passives (bot/passives.py)

    @property
    def active(self):
        return self.hp > 0 and not self.fled

    @property
    def stunned(self):
        return "stunned" in self.statuses

    def tech(self, key):
        return self.atk_t if key == "attack_tech" else self.def_t

    def qi_cost(self, key):
        """Battle Qi this technique costs now: by grade, more while Chilled, nothing after Sword Heart."""
        t = self.tech(key)
        if not t:
            return 0
        if self.free_cast:
            return 0
        return battle.TECHNIQUE_QI_COST.get(t["grade"], 30) + (battle.CHILLED_QI_COST if "chilled" in self.statuses else 0)

    def gain_qi(self, amount):
        self.bqi = min(self.max_bqi, self.bqi + amount)

    def pill_count(self):
        return sum(p["qty"] for p in self.pills)

    def can_pill(self):
        return self.pill_count() > 0 and self.pills_used < battle.PILLS_PER_FIGHT and self.hp < self.max_hp

    def ready(self, choice):
        """Can this move be played now? Techniques rest after use; a stunned fighter can only Guard."""
        if self.stunned and choice != "guard":
            return False
        if choice in ("attack_tech", "defense_tech"):
            return self.tech(choice) is not None and self.bqi >= self.qi_cost(choice)
        if choice == "pill":
            return self.can_pill()
        return choice in MOVES or choice == "flee"

    def move_label(self, choice):
        if choice in ("attack_tech", "defense_tech"):
            return self.tech(choice)["name"]
        return MOVE_LABEL[choice]


def enemy_from_beast(stats_, beast_name):
    element, body = beasts.TRAITS[beast_name]
    return dict(stats_, kind="beast", element=element, body=body, statuses={}, guard_weak=0.0)


def enemy_from_bandits(stats_):
    return dict(stats_, kind="bandit", tier="bandit", role="bandit", element=battle.BANDIT_ELEMENT, body="human",
                statuses={}, guard_weak=0.0)


class Battle:
    """mode: 'beast' (explore wild beast), 'bandit', or 'hunt' (Elite / Beast King team hunt)."""

    def __init__(self, fighters, enemy, rng=None, title="", subtitle=""):
        self.rng = rng or random.Random()
        self.fighters = fighters
        self.enemy = enemy
        self.title, self.subtitle = title, subtitle
        self.turn = 1
        self.enemy_turns = 0
        self.charges = 0                  # charged attacks planned so far (unique skills take some of them)
        self.log = [("star", self._intro())]
        self.intent = None
        self.warning = None
        self.result = None                # "won", "lost", "fled", "escaped" (enemy got away at the turn limit)
        self.history = []                 # every turn's log, oldest first
        for f in fighters:
            f.kit.rng = self.rng
        self._plan()

    # ── state ─────────────────────────────────────────────────────────

    @property
    def over(self):
        return self.result is not None

    @property
    def tier(self):
        return self.enemy["tier"]

    @property
    def team(self):
        return len(self.fighters) > 1

    def active(self):
        return [f for f in self.fighters if f.active]

    def waiting_for(self):
        return [f for f in self.active() if f.pick is None]

    def fighter(self, uid):
        return next((f for f in self.fighters if f.uid == uid), None)

    def _intro(self):
        e = self.enemy
        if e["kind"] == "bandit":
            return f"{e['name']} block the path!"
        if self.team:
            return f"The hunt begins! The {e['name']} rises to meet you."
        return f"A {e['name']} leaps from the brush!"

    # ── the enemy's plan ──────────────────────────────────────────────

    def _plan(self):
        """Pick the enemy's move for this turn and write the warning bar."""
        e = self.enemy
        nm = short_name(e["name"]) if e["kind"] == "beast" else e["name"]
        e["statuses"].pop("charged", None)
        if "staggered" in e["statuses"]:
            self.intent = None
            self.warning = (f"The {nm} reels, off balance!", "It loses this turn. Strike or Break freely.")
            return
        self.enemy_turns += 1
        alive = self.active()
        target = self.rng.choice(alive) if alive else None
        kind = "normal"
        if e["kind"] == "beast":
            if e["tier"] in beasts.CHARGED_ATTACK_TIERS:
                if self.enemy_turns % battle.CHARGE_EVERY == 0:
                    kind = "charged"
            elif self.enemy_turns % battle.SIGNATURE_EVERY == 0:
                kind = "signature"
        el = battle.ELEMENTS[e["element"]]
        skill = None
        if kind == "charged":
            self.charges += 1
            skill = self.unique_skill()
            if skill and (self.charges - 1) % skill["every"]:
                skill = None
        if skill:
            move = "strike"
            head, hint = skill["warn"]
            self.warning = (head.format(name=nm), hint.format(who="Everyone " if self.team else ""))
            e["statuses"]["charged"] = 1
        elif kind != "normal":
            move = "strike"
            head, effect = el["warn"]
            head = head.format(name=nm)
            if kind == "charged":
                hint = (f"Charged attack — {'everyone ' if self.team else ''}Guard, or Break it first. {effect}")
                e["statuses"]["charged"] = 1
            else:
                hint = f"Its {el['move']} comes now — Guard it. {effect}"
            status = el["status"]
            if battle.STATUSES[status]["on"] == "enemy":
                e["statuses"][status] = battle.STATUSES[status]["turns"]
            self.warning = (head, hint)
        else:
            weights = dict(battle.MOVE_WEIGHTS[e["role"]])
            if e["guard_weak"] >= 1.0 or e.pop("no_guard", False):      # no_guard: Thunder Edge passive
                weights["guard"] = 0
            move = self.rng.choices(list(weights), weights=list(weights.values()))[0]
            if self.rng.random() < battle.TELL_CHANCE:
                tells = BANDIT_TELLS if e["kind"] == "bandit" else TELLS
                self.warning = (self.rng.choice(tells[move]).format(name=nm), "Read its move and counter it.")
            else:
                self.warning = (NO_TELL.format(name=nm), "No tell this turn. Trust your instincts.")
        self.intent = {"move": move, "kind": kind, "target": target, "skill": skill["name"] if skill else None,
                       "name": skill["name"] if skill else el["move"] if kind != "normal" else MOVE_LABEL[move]}

    def unique_skill(self):
        """The beast's own skill (battle.UNIQUE_SKILLS), or None."""
        return battle.UNIQUE_SKILLS.get(self.enemy["name"]) if self.enemy["kind"] == "beast" else None

    def planned_skill(self):
        """The unique skill the beast is winding up this turn, or None."""
        return self.unique_skill() if self.intent and self.intent.get("skill") else None

    # ── picking ───────────────────────────────────────────────────────

    def choose(self, uid, choice):
        """Record a fighter's pick. Returns None, or why it was refused. Resolves nothing."""
        f = self.fighter(uid)
        if self.over or not f or not f.active:
            return "You are not in this fight any more."
        if not f.ready(choice):
            if f.stunned:
                return "You are stunned: you can only Guard this turn."
            if choice == "pill":
                return "You have no Mending pill you can use now."
            if f.tech(choice) is None:
                return "You have no technique in that slot."
            return f"Not enough Battle Qi: it costs {f.qi_cost(choice)} and you have {f.bqi:.0f}."
        f.pick = choice
        f.timeouts = 0
        return None

    def all_picked(self):
        return not self.waiting_for()

    # ── resolving a turn ──────────────────────────────────────────────

    def _hit_enemy(self, f, skill=1.0, pierce=0.0, hits=1, share=1.0):
        e = self.enemy
        total = 0.0
        for _ in range(hits):
            if e["dodge"] and self.rng.random() < e["dodge"]:
                continue
            total += combat.damage(f.attack, e["defense"], e["max_hp"], skill * share, pierce, self.rng,
                                   cap=combat.hit_cap(e))
        total = min(total, e["max_hp"] * combat.hit_cap(e))            # the 30% cap is per turn (40% low-realm Normals)
        if "staggered" in e["statuses"]:
            total *= battle.STAGGER_DAMAGE_BONUS
        if "stoneskin" in e["statuses"]:
            total *= battle.STATUSES["stoneskin"]["damage_taken"]
        e["hp"] = max(0, e["hp"] - total)
        f.dealt += total
        return total

    def _attack_skill(self, f, use_tech):
        """(skill, pierce, hits, stagger) for a Strike (with the attack technique if use_tech)."""
        if not use_tech:
            return stats.BASIC_ATTACK_MULTIPLIER, 0.0, 1, 0.0
        t = f.atk_t
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

    def _enemy_hit(self, f, kind):
        e = self.enemy
        atk = e["attack"] * (battle.STATUSES["roused"]["attack_mult"] if "roused" in e["statuses"] else 1.0)
        if kind == "charged":
            skill = self.planned_skill()
            mult = skill["mult"] if skill else battle.CHARGE_MULT
            dmg = combat.damage(atk, f.defense, float("inf"), mult, rng=self.rng)
            return dmg * (1 - min(1.0, f.fx.get("charged_damage_reduction", 0)))     # Bell artifact
        mult = battle.SIGNATURE_MULT if kind == "signature" else 1.0
        return combat.damage(atk, f.defense, f.max_hp, mult, rng=self.rng)

    def _apply_status(self, f, key):
        spec = battle.STATUSES[key]
        if spec["on"] == "player":
            # +1: statuses tick down at the end of this turn, and a stun must still hold on the next one
            f.statuses[key] = spec["turns"] + (1 if spec.get("stun") else 0)

    def resolve(self):
        """Play the turn. Fighters who have not picked Guard (a timeout). Returns the turn's log."""
        if self.over:
            return []
        e = self.enemy
        it = self.intent
        uskill = self.planned_skill()       # the beast's unique skill, if this is it
        m = it["move"] if it else None
        kind = it["kind"] if it else None
        en = e["name"] if e["kind"] == "bandit" else short_name(e["name"])
        log = []
        played = {}                       # fighter -> base move this turn (None: open, e.g. pill or failed flee)
        interrupted = False
        weak, e["guard_weak"] = e["guard_weak"], 0.0

        for f in self.active():
            choice = f.pick
            if choice is None:
                f.timeouts += 1
                if f.timeouts >= battle.TIMEOUTS_TO_FLEE:
                    f.fled = True
                    f.last_move = "Fled"
                    log.append(("flee", f"{f.name} stood frozen too long and fled the fight."))
                    continue
                choice = battle.TIMEOUT_MOVE
                log.append(("hourglass", f"{f.name} hesitated: Guard."))
            if f.stunned:
                choice = "guard"
            f.pick = None
            f.last_move = f.move_label(choice) if choice not in ("pill", "flee") else MOVE_LABEL[choice]

            if choice == "flee":
                if self.rng.random() < battle.FLEE_CHANCE[self.tier]:
                    f.fled = True
                    log.append(("flee", f"{f.name} escaped!"))
                    continue
                log.append(("flee", f"{f.name} tried to flee, but the {en} cut them off!"))
                played[f] = None
                continue
            if choice == "pill":
                pill = next(p for p in f.pills if p["qty"] > 0)
                pill["qty"] -= 1
                f.pills_used += 1
                heal = round(f.max_hp * pill["heal"])
                f.hp = min(f.max_hp, f.hp + heal)
                pill.setdefault("used", 0)
                pill["used"] += 1
                log.append(("pill", f"{f.name} swallowed a {pill['name']}: +{heal:,} HP"))
                played[f] = None
                continue

            base = BASE_MOVE[choice]
            played[f] = base
            used = choice if choice.endswith("_tech") else None
            if used == "attack_tech":
                f.atk_uses += 1
            elif used == "defense_tech":
                f.guard_uses += 1
            if used:
                cost = f.qi_cost(used)
                f.free_cast = False
                reset = f.fx.get("cooldown_reset_chance")
                if cost and reset and self.rng.random() < reset:            # Focus artifact
                    log.append(("star", f"{f.name} — Focus: {f.tech(used)['name']} costs no Battle Qi!"))
                else:
                    f.bqi = max(0, f.bqi - cost)

            if base == "guard":
                f.kit.moved(base)
                continue                  # resolved with the enemy's attack below
            skill, pierce, hits, stagger = self._attack_skill(f, used == "attack_tech")
            combo = used == "attack_tech" and (tech_effect(f.atk_t) or ("",))[0] == "combo"
            label = f.move_label(choice)
            if base == "break":
                skill = battle.BREAK_SKILL
            hidden = "hidden" in e["statuses"]
            f.kit.moved(base)
            if base == "strike" and hidden:
                log.append(("strike", f"{f.name} — {label}: the {en} is hidden, it misses!"))
                continue
            share, note = 1.0, ""
            if m is None:
                pass                                  # staggered: free hit
            elif kind == "charged":
                if base == "break":
                    interrupted = True
                    note = "interrupts the charge!"
            elif m == "guard":
                if base == "strike":
                    if weak <= 0 and f.kit.can_pierce_guard():
                        note = "Heaven-Splitting: no guard can stop it!"
                    elif weak <= 0:
                        log.append(("shield", f"{f.name} — {label}: blocked by the {en}'s guard"))
                        if battle.BLOCKED_STRIKE_STUN and not f.kit.resists_stun():
                            self._apply_status(f, "stunned")
                            log.append(("shield", f"{f.name} is thrown off balance: Stunned"))
                        continue
                    else:
                        share, note = weak, "slips through its weakened guard"
                else:
                    e["statuses"]["staggered"] = battle.STAGGER_TURNS + 1   # this turn's tick + its next turn
                    note = "the guard shatters!"
            elif m == "strike":
                if base == "strike":
                    share, note = battle.CLASH_DAMAGE, "blows clash"
                else:
                    log.append(("fist", f"{f.name} — {label}: missed, the {en} was Striking"))
                    continue
            elif m == "break":
                if base == "break":
                    share, note = battle.CLASH_DAMAGE, "the two charges collide"
                elif f.fx.get("strike_vs_break_damage"):                      # Fang artifact
                    bonus = f.fx["strike_vs_break_damage"]
                    share, note = 1 + bonus, f"beats its Break (Fang +{bonus:.0%})"
            if base == "break" and hidden:
                e["statuses"].pop("hidden", None)
                note = (note + " " if note else "") + "drags it out of the shadows!"
            mult, more_pierce, more_hits, kit_lines = f.kit.attack_mods(
                base, self.turn, vs_beast=e["kind"] == "beast", target_staggered="staggered" in e["statuses"],
                target_hp_frac=e["hp"] / e["max_hp"], own_hp_frac=f.hp / f.max_hp, combo=combo)
            dmg = self._hit_enemy(f, skill, min(0.95, pierce + more_pierce), hits + more_hits, share * mult)
            stun, dealt_lines = f.kit.dealt(f, dmg, base, e)
            if stun and e["hp"] > 0:
                e["no_guard"] = True
            kit_lines += dealt_lines
            if stagger and dmg > 0:
                e["guard_weak"] = max(e["guard_weak"], stagger)
            jolt = f.fx.get("break_stagger_chance")
            if (base == "break" and dmg > 0 and jolt and e["hp"] > 0 and "staggered" not in e["statuses"]
                    and self.rng.random() < jolt):                           # Thunder artifact
                e["statuses"]["staggered"] = battle.STAGGER_TURNS + 1
                note = (note + ", " if note else "") + "Thunder: it staggers!"
            icon = "sword" if base == "strike" else "fist"
            text = f"{f.name} — {label}: " + (f"{dmg:,.0f} dmg" if dmg else "dodged!")
            if note:
                text += f", {note}"
            log.append((icon, text))
            log += kit_lines
            if e["hp"] <= 0:
                break

        # the enemy's attack
        if e["hp"] > 0 and m in ("strike", "break"):
            if kind == "charged" and interrupted:
                log.append(("skull", f"{en} — {it['name']} broken off before it lands!"))
            else:
                targets = list(played) if kind == "charged" else ([it["target"]] if it["target"] in played else [])
                hit_names = []
                for t in targets:
                    if not t.active:
                        continue
                    mine = played[t]
                    dmg = self._enemy_hit(t, kind)
                    blocked_note = ""
                    if mine == "guard" and m == "strike":
                        if kind == "charged":
                            block = battle.CHARGE_GUARD_BLOCK
                            if t.def_t and t.last_move == t.def_t["name"]:
                                block += technique.DEFENSE_TECHNIQUE[t.def_t["grade"]][0] * rules.mastery_mult(t.def_t)
                            block = min(technique.MAX_DAMAGE_BLOCKED, block + t.kit.guard_block())   # Bulwark
                        else:
                            block = 1.0
                        blocked = dmg * block
                        dmg -= blocked
                        blocked_note = f"blocked {block:.0%}"
                        t.kit.guarded()                                         # Riposte
                        mirror = t.fx.get("guard_reflect")
                        if mirror and blocked > 0 and e["hp"] > 0:              # Mirror artifact
                            back = min(e["hp"], blocked * mirror)
                            e["hp"] = max(0, e["hp"] - back)
                            blocked_note += f", Mirror reflects {back:,.0f}"
                        if t.def_t and t.last_move == t.def_t["name"]:
                            eff = tech_effect(t.def_t)
                            if eff and eff[0] == "counter":
                                back = min(e["hp"], blocked * eff[1])
                                e["hp"] = max(0, e["hp"] - back)
                                blocked_note += f", countered for {back:,.0f}"
                            elif eff and eff[0] == "recover":
                                heal = round(t.max_hp * eff[1])
                                t.hp = min(t.max_hp, t.hp + heal)
                                blocked_note += f", recovered {heal:,}"
                        if battle.GUARD_COUNTER and kind == "normal" and e["hp"] > 0:
                            back = self._hit_enemy(t, battle.GUARD_COUNTER)
                            blocked_note += f", counters for {back:,.0f}"
                        if kind == "normal" and battle.BATTLE_QI_GOOD_GUARD:
                            t.gain_qi(battle.BATTLE_QI_GOOD_GUARD)
                            blocked_note += f", +{battle.BATTLE_QI_GOOD_GUARD} Battle Qi"
                        log.append(("shield", f"{t.name} — {t.last_move}: {blocked_note}"))
                    elif mine == "strike" and m == "break":
                        log.append(("shield", f"{t.name} beat the {en}'s Break to the punch"))
                        dmg = 0
                    elif mine == m and kind != "charged":
                        dmg *= battle.CLASH_DAMAGE
                    elif mine == "guard" and m == "break" and t.def_t and t.last_move == t.def_t["name"]:
                        eff = tech_effect(t.def_t)
                        if eff and eff[0] == "evade" and self.rng.random() < eff[1]:
                            dmg = 0
                            log.append(("shield", f"{t.name} slipped away from the {en}'s Break"))
                        else:
                            held = break_held(t.def_t, eff)
                            if held:
                                dmg *= 1 - held
                                log.append(("shield", f"{t.name} — {t.last_move}: holds {held:.0%} of the Break"))
                    dmg = round(dmg)
                    if dmg <= 0:
                        continue
                    dodge = t.fx.get("dodge_chance")
                    if dodge and self.rng.random() < dodge:                     # Feather artifact
                        log.append(("shield", f"{t.name} sidesteps the blow (Feather)"))
                        continue
                    dmg, back, kit_lines = t.kit.taken(
                        t, dmg, self.turn, from_break=m == "break", charged=kind == "charged",
                        vs_beast=e["kind"] == "beast", aura=self._aura(t),
                        mirror_artifact=t.fx.get("guard_reflect", 0) if mine == "guard" else 0)
                    log += kit_lines
                    if back and e["hp"] > 0:                                    # Thorns, Mirror Shell
                        e["hp"] = max(0, e["hp"] - min(back, e["max_hp"] * stats.MAX_HIT_PERCENT))
                    dmg = round(dmg)
                    if dmg <= 0:
                        continue
                    t.hp = max(0, t.hp - dmg)
                    hit_names.append(f"{t.name} −{dmg:,}")
                    saves = t.kit.after_taken(t)
                    status = uskill["status"] if uskill else battle.ELEMENTS[e["element"]]["status"]
                    if uskill and mine == "guard":
                        status = None                                           # a Guard rides out the shockwave
                    if status and battle.STATUSES[status]["on"] == "player" and t.hp > 0 and (
                            kind != "normal" or self.rng.random() < battle.STATUS_ON_HIT_CHANCE):
                        if t.kit.immune(status):
                            hit_names[-1] += f" (Immortal Body: no {battle.STATUSES[status]['name']})"
                        elif status == "stunned" and t.kit.resists_stun():
                            hit_names[-1] += " (resists the stun)"
                        else:
                            self._apply_status(t, status)
                            hit_names[-1] += f" ({battle.STATUSES[status]['name']})"
                    if t.hp <= 0:
                        hit_names[-1] += ", knocked out!"
                    log += saves
                if hit_names:
                    what = it["name"] if kind != "normal" else MOVE_LABEL[m]
                    log.append(("skull", f"{en} — {what} on " + ", ".join(hit_names)))
                if uskill and e["hp"] > 0:
                    after = uskill["after"]
                    e["statuses"][after] = battle.STATUSES[after]["turns"] + 1       # +1: this turn's tick
                    log.append(("roar", f"{en} — {uskill['name']}: " + uskill["roused"]))
        elif e["hp"] > 0 and m == "guard" and not any(b in ("strike", "break") for b in played.values()):
            log.append(("shield", f"{en} — Guard: it waits behind its guard"))

        self._end_of_turn(log)
        self.history.append(log)
        self.log = log or [("star", "Both sides circle each other.")]
        if not self.over:
            self.turn += 1
            if self.turn > battle.MAX_TURNS[self.tier]:
                self.result = "escaped"
                self.log.append(("star", f"The {en} slips away into the wilds."))
            else:
                self._plan()
        return self.log

    def _aura(self, t):
        """Heavenly Aegis: the damage cut an ally's armor gives this fighter in a team hunt."""
        return max([o.kit.fx("heavenly_aegis", "team_damage_taken") for o in self.fighters
                    if o is not t and o.active] or [0])

    def _end_of_turn(self, log):
        e = self.enemy
        for f in self.fighters:
            if not f.active:
                f.statuses.clear()
                continue
            for key in list(f.statuses):
                spec = battle.STATUSES[key]
                if spec.get("dot"):
                    dmg = max(1, round(f.max_hp * spec["dot"]))
                    f.hp = max(0, f.hp - dmg)
                    log.append(("flame", f"{f.name} — {spec['name']}: −{dmg:,}"))
                    log += f.kit.after_taken(f)
                f.statuses[key] -= 1
                if f.statuses[key] <= 0:
                    del f.statuses[key]
            if f.active:
                f.gain_qi(battle.BATTLE_QI_PER_TURN)
                log += f.kit.end_turn(f, self.turn)
            bleed = f.kit.bleed_tick(e["max_hp"]) if e["hp"] > 0 else 0
            if bleed:
                e["hp"] = max(0, e["hp"] - bleed)
                f.dealt += bleed
                log.append(("flame", f"{f.name} — Bleeding Cut: the {short_name(e['name'])} bleeds −{bleed:,}"))
            lotus = f.fx.get("heal_per_turn")
            if lotus and 0 < f.hp < f.max_hp:                                # Lotus artifact
                heal = min(f.max_hp - f.hp, max(1, round(f.max_hp * lotus)))
                f.hp += heal
                log.append(("herb", f"{f.name} — Lotus: +{heal:,}"))
        if e["hp"] > 0:
            for key in list(e["statuses"]):
                spec = battle.STATUSES[key]
                if spec.get("regen"):
                    heal = round(e["max_hp"] * spec["regen"])
                    e["hp"] = min(e["max_hp"], e["hp"] + heal)
                    log.append(("herb", f"{short_name(e['name'])} — {spec['name']}: +{heal:,}"))
                if key == "charged":
                    continue
                e["statuses"][key] -= 1
                if e["statuses"][key] <= 0:
                    del e["statuses"][key]
        if e["hp"] <= 0:
            self.result = "won"
        elif not self.active():
            self.result = "fled" if all(f.fled for f in self.fighters) else "lost"

    # ── for the card ─────────────────────────────────────────────────

    def status_chips(self):
        return [battle.STATUSES[k]["name"] for k in self.enemy["statuses"]]

    def target(self):
        return self.intent["target"] if self.intent else None

    @staticmethod
    def mastery_uses(f):
        """{technique id: uses} for COMBAT_EXP_PER_USE."""
        out = {}
        if f.atk_t and f.atk_uses:
            out[f.atk_t["id"]] = f.atk_uses
        if f.def_t and f.guard_uses:
            out[f.def_t["id"]] = f.guard_uses
        return out


def counters():
    return challenges.COUNTERS
