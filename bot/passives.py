"""
Gear passives (docs/forge.md): where they are stored and how the rules read them. Every number comes from forge.py.

A weapon, armor or artifact keeps its passives in item data["passives"]: one entry per slot
(forge.PASSIVE_SLOTS), a passive key or None for an empty slot.

Worn artifact passives reach the rules through the player dict, like artifact effects: db.get_player() puts
{passive key: fx dict} under "artifact_passives", and artifact_passive(player, key, fx) reads one number.
Artifact passives whose number has the same name as an artifact effect (qi_rate, lotus_coins, mastery_exp...)
add to it in gear.artifact_bonus, so every rule that reads the effect gets the passive too.

Worn weapon and armor passives go under "gear_passives" (a list of keys). Their stat numbers (attack, hp, defense)
add in with the other % buffs (player.stat_buffs); the rest ride on each fighter as a Kit (below), which the fight
engines (bot/fight.py, bot/duel.py) call at fixed moments of a turn.
"""
import random as _random

import forge

GEAR_KIND = {"weapons": "weapon", "armor": "armor", "artifacts": "artifact"}


def gear_kind(item):
    return GEAR_KIND.get(item.get("category"))


def slots(item):
    """The item's passive slots: a list as long as its tier allows, None for empty."""
    n = forge.PASSIVE_SLOTS[item["grade"]]["slots"]
    have = list((item.get("data") or {}).get("passives") or [])
    return (have + [None] * n)[:n]


def spec(item, key):
    return forge.PASSIVES[gear_kind(item)][key]


def worn_passives(items):
    """Every passive on these worn items, each counted once (no duplicates on one character)."""
    out = []
    for it in items:
        if not gear_kind(it):
            continue
        for k in slots(it):
            if k and k not in out:
                out.append(k)
    return out


def artifact_passives(artifacts):
    """{passive key: fx} for worn artifacts, each passive once."""
    out = {}
    for a in artifacts:
        for k in slots(a):
            if k and k not in out:
                out[k] = forge.PASSIVES["artifact"][k]["fx"]
    return out


def artifact_passive(player, key, fx=None):
    """The number a worn artifact passive gives (0 when not worn). fx: which number of the passive (default: its
    first one)."""
    got = (player or {}).get("artifact_passives", {}).get(key)
    if not got:
        return 0
    return got[fx] if fx else next(iter(got.values()))


def has_artifact_passive(player, key):
    return key in (player or {}).get("artifact_passives", {})


def slot_views(item, gear=None):
    """The item's passive slots for cards: [{"name", "rarity", "text"} or None for an empty slot]."""
    gear = gear or gear_kind(item)
    out = []
    for k in slots(item):
        spec = forge.PASSIVES[gear].get(k) if k else None
        out.append({"name": spec["name"], "rarity": spec["rarity"], "text": spec["text"]} if spec else None)
    return out


def label(key, gear):
    p = forge.PASSIVES[gear][key]
    return f"{forge.RARITY_EMOJI[p['rarity']]} {p['name']}"


def combat_spec(key):
    """A weapon or armor passive's spec (the two sets never share a key)."""
    return forge.PASSIVES["weapon"].get(key) or forge.PASSIVES["armor"][key]


STAT_KEYS = ("attack", "hp", "defense")


def stat_passives(items):
    """[(passive name, stat, pct)] for the stat passives on these worn weapons / armor (Keen Edge, Sturdy...)."""
    out, seen = [], set()
    for it in items:
        for k in (it.get("data") or {}).get("passives") or []:
            if not k or k in seen or k in forge.PASSIVES["artifact"]:
                continue
            seen.add(k)
            spec = combat_spec(k)
            for stat in STAT_KEYS:
                if spec["fx"].get(stat):
                    out.append((spec["name"], stat, spec["fx"][stat]))
    return out


# ══ Combat: weapon and armor passives in a fight ═══════════════════════

# Numbers that are counts, not strengths: never halved in Fair Duels.
COUNTS = {"uses_per_fight", "max_stacks", "turns", "every_turns", "after_turns", "every_hits", "extra_hits",
          "survive_hp", "immune", "low_hp_below", "missing_hp_step", "below_hp"}


class Kit:
    """The weapon and armor passives one fighter wears, with their state for one fight.

    scale: forge.DUEL_PASSIVE_STRENGTH in Fair Duels (every strength and chance halved, counts kept), else 1.
    Each method returns log lines as (icon, text) for the battle log, e.g. ("herb", "Lifesteal: +38 HP")."""

    def __init__(self, keys=(), scale=1.0, rng=None, name=""):
        self.keys = [k for k in keys if not forge.PASSIVES["artifact"].get(k)]
        self.scale = scale
        self.rng = rng or _random.Random()
        self.name = name
        self.used = set()            # once-per-fight passives already spent
        self.rhythm = 0              # Strikes in a row (Rhythm)
        self.crack = 0               # Armor Crack stacks on the target
        self.riposte = False         # a Guard just blocked a hit (Riposte)
        self.hits_taken = 0          # Black Tortoise's Shell
        self.first_hit = True        # Golden Body
        self.stone = 0.0             # Stone Skin defense bonus so far
        self.base_defense = None
        self.bleed = 0               # Bleeding Cut turns left on the target
        self.stole = False           # Devouring Edge took its Attack already

    def has(self, key):
        return key in self.keys

    def fx(self, key, field):
        """A passive's number at this fight's strength (0 when not worn)."""
        if key not in self.keys:
            return 0
        v = combat_spec(key)["fx"].get(field, 0)
        if field in COUNTS or self.scale == 1.0:
            return v
        if field == "mult":
            return 1 + (v - 1) * self.scale
        if field == "max_hit":
            return min(1.0, v / self.scale)
        return v * self.scale

    def label(self, key):
        return combat_spec(key)["name"]

    def _line(self, icon, key, text):
        return (icon, f"{self.name} — {self.label(key)}: {text}" if text else f"{self.name} — {self.label(key)}!")

    def chance(self, key, field="chance"):
        p = self.fx(key, field)
        return bool(p) and self.rng.random() < p

    def once(self, key):
        """Spend a once-per-fight passive. True if it was still there."""
        if key not in self.keys or key in self.used:
            return False
        self.used.add(key)
        return True

    # ── attacking ────────────────────────────────────────────────────

    def attack_mods(self, base, turn, vs_beast=False, duel=False, target_staggered=False, target_hp_frac=1.0,
                    own_hp_frac=1.0, combo=False):
        """(damage multiplier, extra pierce, extra hits, log lines) for this fighter's Strike or Break."""
        lines = []
        add = 0.0
        add += self.fx("hunters_edge", "damage_vs_beasts") if vs_beast else 0
        add += self.fx("duelists_edge", "damage_in_duels") if duel else 0
        add += self.fx("opening_strike", "damage_turn_1") if turn == 1 else 0
        add += self.fx("breaker", "break_damage") if base == "break" else 0
        add += self.fx("pursuit", "damage_vs_staggered") if target_staggered else 0
        if self.has("executioner") and target_hp_frac < self.fx("executioner", "low_hp_below"):
            add += self.fx("executioner", "damage_vs_low_hp")
        if base == "strike" and self.rhythm:
            add += self.fx("rhythm", "strike_streak_damage") * min(self.rhythm, self.fx("rhythm", "max_stacks"))
        if base == "strike" and self.riposte and self.has("riposte"):
            add += self.fx("riposte", "strike_after_guard")
            lines.append(self._line("sword", "riposte", f"+{self.fx('riposte', 'strike_after_guard'):.0%}"))
        if self.has("blood_frenzy"):
            steps = int((1 - own_hp_frac) / self.fx("blood_frenzy", "missing_hp_step") + 1e-9)
            add += steps * self.fx("blood_frenzy", "attack_per_step")
        mult = 1 + add
        if self.chance("dragons_wrath"):
            mult *= self.fx("dragons_wrath", "mult")
            lines.append(self._line("flame", "dragons_wrath", f"×{self.fx('dragons_wrath', 'mult'):g} damage"))
        if self.has("ten_thousand_swords") and turn > self.fx("ten_thousand_swords", "after_turns") \
                and self.once("ten_thousand_swords"):
            mult *= self.fx("ten_thousand_swords", "mult")
            lines.append(self._line("sword", "ten_thousand_swords", f"×{self.fx('ten_thousand_swords', 'mult'):g}!"))
        if self.chance("flash_step"):
            mult *= 1 + self.fx("flash_step", "second_hit")
            lines.append(self._line("sword", "flash_step", "a second strike"))
        pierce = self.fx("sunder", "ignore_defense") + self.crack * self.fx("armor_crack", "defense_down_per_hit")
        hits = 0
        if combo and self.chance("combo_master"):
            hits = self.fx("combo_master", "extra_hits")
            lines.append(self._line("sword", "combo_master", f"+{hits} hit"))
        return mult, min(0.9, pierce), hits, lines

    def moved(self, base):
        """After this fighter's move each turn: Rhythm counts Strikes in a row, Riposte is spent by a Strike."""
        self.rhythm = self.rhythm + 1 if base == "strike" else 0
        if base == "strike":
            self.riposte = False

    def can_pierce_guard(self):
        """Heaven-Splitting: once per fight, a Strike can't be Guarded."""
        return self.once("heaven_splitting")

    def dealt(self, owner, dmg, base, target=None):
        """After this fighter's hit landed for dmg: Lifesteal, Devouring Edge, Armor Crack, Bleeding Cut, Thunder
        Edge. target: a dict with "attack" (an enemy) or an object with .attack (a duelist). Returns (stun, lines)."""
        lines = []
        if dmg <= 0:
            return False, lines
        pct = self.fx("lifesteal", "heal_of_damage") + self.fx("devouring_edge", "heal_of_damage")
        if pct:
            got = self.heal(owner, dmg * pct)
            if got:
                key = "devouring_edge" if self.has("devouring_edge") else "lifesteal"
                lines.append(self._line("herb", key, f"+{got:,} HP"))
        if self.has("devouring_edge") and not self.stole and target is not None:
            self.stole = True
            steal = self.fx("devouring_edge", "steal_attack")
            if isinstance(target, dict):
                taken = target["attack"] * steal
                target["attack"] -= taken
            else:
                taken = target.attack * steal
                target.attack -= taken
            owner.attack += taken
            lines.append(self._line("skull", "devouring_edge", f"steals {steal:.0%} Attack"))
        if self.has("armor_crack") and self.crack < self.fx("armor_crack", "max_stacks"):
            self.crack += 1
        if base == "strike" and self.has("bleeding_cut"):
            self.bleed = self.fx("bleeding_cut", "turns")
        stun = self.chance("thunder_edge")
        if stun:
            lines.append(self._line("star", "thunder_edge", "stunned, it can't Guard next turn"))
        return stun, lines

    def bleed_tick(self, target_max_hp):
        """Bleeding Cut at the end of the turn: damage to the target (0 when not bleeding)."""
        if self.bleed <= 0:
            return 0
        self.bleed -= 1
        return max(1, round(target_max_hp * self.fx("bleeding_cut", "bleed_max_hp")))

    # ── defending ────────────────────────────────────────────────────

    def guard_block(self):
        """Bulwark: extra share a Guard blocks."""
        return self.fx("bulwark", "guard_block")

    def guarded(self):
        """A Guard of this fighter blocked a hit: Riposte is ready."""
        if self.has("riposte"):
            self.riposte = True

    def taken(self, owner, dmg, turn, from_break=False, charged=False, vs_beast=False, duel=False, aura=0.0,
              mirror_artifact=0.0):
        """A hit for dmg is about to land on this fighter. Returns (dmg, reflected back, lines)."""
        lines = []
        if dmg <= 0:
            return 0, 0, lines
        if self.chance("evasive", "dodge"):
            return 0, 0, [self._line("shield", "evasive", "dodged")]
        if charged and self.once("mirror_shell"):
            return 0, dmg, [self._line("shield", "mirror_shell", f"the charge goes back for {dmg:,.0f}")]
        self.hits_taken += 1
        every = self.fx("black_tortoise_shell", "every_hits")
        if every and self.hits_taken % every == 0:
            return 0, 0, [self._line("shield", "black_tortoise_shell", "the hit is fully blocked")]
        cut = aura
        cut += self.fx("beastward", "damage_taken_from_beasts") if vs_beast else 0
        cut += self.fx("duel_guard", "damage_taken_in_duels") if duel else 0
        cut += self.fx("steadfast", "damage_taken_turn_1") if turn == 1 else 0
        cut += self.fx("iron_will", "damage_taken_from_break") if from_break else 0
        cut += self.fx("fortified", "charged_damage_taken") if charged else 0
        dmg *= 1 - min(0.9, cut)
        if self.first_hit:
            self.first_hit = False
            if self.has("golden_body"):
                dmg *= 1 - self.fx("golden_body", "first_hit_taken")
                lines.append(self._line("shield", "golden_body", f"−{self.fx('golden_body', 'first_hit_taken'):.0%}"))
        cap = self.fx("mountain_stance", "max_hit")
        if cap and dmg > owner.max_hp * cap:
            dmg = owner.max_hp * cap
            lines.append(self._line("shield", "mountain_stance", f"held to {cap:.0%} of max HP"))
        reflect = min(self.fx("thorns", "reflect") + self.fx("spiked_plates", "reflect"),
                      max(0.0, forge.REFLECT_CAP - mirror_artifact))
        back = dmg * reflect
        if back >= 1:
            key = "spiked_plates" if self.has("spiked_plates") else "thorns"
            lines.append(self._line("skull", key, f"reflects {back:,.0f}"))
        return dmg, back, lines

    def after_taken(self, owner):
        """After HP went down: Second Wind, then Undying Blade or Phoenix Rebirth on a lethal hit."""
        lines = []
        if owner.hp <= 0:
            if self.once("undying_blade"):
                owner.hp = self.fx("undying_blade", "survive_hp")
                lines.append(self._line("star", "undying_blade", f"survives at {owner.hp} HP!"))
            elif self.once("phoenix_rebirth"):
                owner.hp = max(1, round(owner.max_hp * self.fx("phoenix_rebirth", "revive_hp")))
                lines.append(("star", f"{self.name} — Phoenix Rebirth! Back at {owner.hp:,} HP"))
            return lines
        if self.has("second_wind") and owner.hp < owner.max_hp * self.fx("second_wind", "below_hp") \
                and self.once("second_wind"):
            got = self.heal(owner, owner.max_hp * self.fx("second_wind", "heal"))
            lines.append(self._line("herb", "second_wind", f"+{got:,} HP"))
        return lines

    def resists_stun(self):
        """Unshaken / Unbreakable Will: shrug off a stun or stagger."""
        p = max(self.fx("unshaken", "stagger_resist"), self.fx("unbreakable_will", "stagger_resist"))
        return bool(p) and self.rng.random() < p

    def immune(self, status):
        """Immortal Body: immune to bleeding and poison (battle.STATUSES 'bleeding', 'poisoned')."""
        names = {"bleed": "bleeding", "poison": "poisoned"}
        return any(names.get(x, x) == status for x in (self.fx("immortal_body", "immune") or []))

    def heal(self, owner, amount):
        """Heal the owner (Vital Flow makes it stronger). Returns HP healed."""
        amount *= 1 + self.fx("vital_flow", "healing")
        got = max(0, min(owner.max_hp - owner.hp, round(amount)))
        owner.hp += got
        return got

    def end_turn(self, owner, turn, cooldowns=None):
        """Recovery / Immortal Body heal, Stone Skin, Sword Heart, at the end of each turn."""
        lines = []
        if owner.hp <= 0:
            return lines
        pct = self.fx("recovery", "heal_per_turn") + self.fx("immortal_body", "heal_per_turn")
        if pct and owner.hp < owner.max_hp:
            got = self.heal(owner, max(1, owner.max_hp * pct))
            if got:
                key = "immortal_body" if self.has("immortal_body") else "recovery"
                lines.append(self._line("herb", key, f"+{got:,} HP"))
        if self.has("stone_skin") and self.stone < self.fx("stone_skin", "max"):
            if self.base_defense is None:
                self.base_defense = owner.defense
            self.stone = min(self.fx("stone_skin", "max"), self.stone + self.fx("stone_skin", "defense_per_turn"))
            owner.defense = self.base_defense * (1 + self.stone)
        every = self.fx("sword_heart", "every_turns")
        if every and (turn + 1) % every == 0:
            if cooldowns is None and hasattr(owner, "free_cast"):       # beast fights: Battle Qi
                if not owner.free_cast:
                    owner.free_cast = True
                    lines.append(self._line("star", "sword_heart", "your next technique costs no Battle Qi"))
            elif cooldowns is not None and any(cooldowns.values()):     # duels and spars: cooldowns
                for k in cooldowns:
                    cooldowns[k] = 0
                lines.append(self._line("star", "sword_heart", "your technique is ready"))
        return lines


def gear_passive_keys(player):
    """The weapon and armor passives the player wears (db.get_player puts them under 'gear_passives')."""
    return list((player or {}).get("gear_passives", []))


def kit_for(player, scale=1.0, rng=None):
    return Kit(gear_passive_keys(player), scale, rng, (player or {}).get("name", ""))
