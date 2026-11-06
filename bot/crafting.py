"""
/craft — the alchemy minigame (docs/alchemy.md, sections 4–6).

Pick a pill, then refine it stage by stage. Discord adds a delay to every button press, so every
stage is turn-based with a timer per decision, never a moving bar:

    🔥 1 Ignite the Cauldron   keep the heat inside a hidden safe zone (Stoke / Fan / Hold)
    🌿 2 Add the Herbs         put the herbs in the hidden order the clues describe
    ☯️ 3 Fuse the Essences     balance Yin and Yang (Circulate / Compress / Cool / Ignite)
    💊 4 Condense the Pill     press Condense at the perfect pulse
    🔒 5 Seal the Core         Breakthrough pills only: balance with the Beast Core in 3 moves
    ⚡ Pill Tribulation        a 95%+ craft that may reach 9 patterns must survive the lightning

Score → 1–9 pill patterns (丹纹), capped by herb age. Every number comes from alchemy.py.
Craft holds the game and has no Discord code, so it can be tested directly. CraftView drives it:
while a craft runs, the message shows the Alchemy Chamber card (cards/alchemy.py, data from
bot/craft_card.py) with the readable details in the text under it, edited after every decision.
"""
import asyncio
import logging
import random
import time
from dataclasses import dataclass, field

import discord

import alchemy
import training

from . import craft_card, db, gear, loot
from . import player as rules
from . import render as card_render
from .fight_view import jpg
from .views import COLOR, OwnedView
from cards.alchemy import render_alchemy

log = logging.getLogger("mortal-ascent")

TIMER_GRACE_SECONDS = 1.0           # Discord round-trip allowance, as in /train and /gather
IDLE_TIMEOUT = 300
CN = ["", "一", "二", "三", "四", "五", "六", "七", "八", "九"]
AGES = sorted(alchemy.HERB_AGES)

# kind → (label, emoji, table, recipe)
KINDS = {
    "qi":           ("Qi Pill", "🌀", alchemy.QI_PILLS, alchemy.QI_PILL_RECIPE),
    "burst":        ("Qi Burst Pill", "⚡", alchemy.QI_BURST_PILLS, alchemy.QI_BURST_RECIPE),
    "mending":      ("Mending Pill", "❤️", alchemy.MENDING_PILLS, alchemy.MENDING_RECIPE),
    "cleansing":    ("Cleansing Pill", "💧", alchemy.CLEANSING_PILLS, alchemy.CLEANSING_RECIPE),
    "breakthrough": ("Breakthrough Pill", "🏔️", alchemy.BREAKTHROUGH_PILLS, alchemy.BREAKTHROUGH_RECIPE),
}

# DEFAULT numbers the design leaves open
HEAT_STEP = 12                      # Stoke / Fan move the heat this much
HEAT_CALM_DRIFT = 5                 # normal drift each round: −5…+5
HEAT_SPIKE = (12, 18)               # a spike (hinted) moves it this much
HEAT_SPIKE_CHANCE = 0.30
BALANCE_TOLERANCE = 5               # Yin and Yang within 50 ± 5 = perfect
BALANCE_MOVES = {"circulate": None, "compress": (-10, -10), "cool": (12, 0), "ignite": (0, 12)}
WILD_HERB_PUSH = 6
SEAL_PASS = 12                      # Seal the Core passes when |Yin−50| + |Yang−50| ≤ this
PULSE_SCORE = {4: 1.0, 3: 0.7, 2: 0.45, 1: 0.25, 0: 0.15}
CRACKED_SCORE = 0.2
CONDENSE_WEIGHT = 2                 # "this stage decides most of the pill patterns"
TRIBULATION_STRIKES = 3


def pill_name(kind, grade):
    if kind == "qi":
        return alchemy.QI_PILLS[grade]["name"]
    return f"{grade} {KINDS[kind][0]}"


def pill_spec(kind, grade):
    return KINDS[kind][2][grade]


def rank_of(exp):
    return max(r for r, need in alchemy.ALCHEMIST_RANK_EXP.items() if exp >= need)


def rank_label(rank):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(rank, f"{rank}th") + " Grade"


def age_tier(ages):
    """The average age of a recipe's herbs, rounded down to an age tier."""
    avg = sum(ages) / len(ages)
    return max(a for a in AGES if a <= avg)


def patterns_for(score, max_patterns):
    for min_score, n in alchemy.SCORE_TO_PATTERNS:
        if score >= min_score:
            return min(n, max_patterns)
    return 0


def toxicity_for(patterns):
    for min_patterns, tox in alchemy.PATTERN_TOXICITY:
        if patterns >= min_patterns:
            return tox
    return alchemy.PATTERN_TOXICITY[-1][1]


def crafted_pill(kind, grade, patterns):
    return {"category": "pills", "key": f"{kind}:{grade}:{patterns}",
            "name": f"{pill_name(kind, grade)} · {CN[patterns]}纹", "grade": grade,
            "data": {"kind": kind, "grade": grade, "patterns": patterns}}


# ── choosing herbs ────────────────────────────────────────────────────

def plan(conn, user_id, kind, grade, prefer="young"):
    """Which herbs (and core) a craft would use. Returns a dict:
    {uses: [(item, qty)], ages: [...], age: tier, core: item or None, missing: [text]}.
    prefer="young" uses the youngest herbs that still meet the minimum age; "old" the oldest."""
    spec, recipe = pill_spec(kind, grade), KINDS[kind][3]
    herbs = [h for h in db.get_items(conn, user_id, "herbs") if h["grade"] == grade]
    missing, chosen = [], []          # chosen: [(item, age)] one entry per herb unit
    for type_, n in recipe:
        units = sorted(((h, h["data"]["age"]) for h in herbs if h["data"]["type"] == type_
                        for _ in range(h["qty"])), key=lambda u: u[1], reverse=prefer == "old")
        if len(units) < n:
            missing.append(f"{n - len(units)} more {alchemy.HERBS[grade][type_][0]}")
        chosen += [(u, type_) for u in units[:n]]
        if prefer == "young":
            spare = units[n:]
            # swap the youngest picked herb for the oldest spare one until the average is old enough
            while spare and chosen and age_tier([a for (_, a), _ in chosen]) < spec["min_age"]:
                mine = [c for c in chosen if c[1] == type_]
                if not mine:
                    break
                worst = min(mine, key=lambda c: c[0][1])
                best = max(spare, key=lambda u: u[1])
                if best[1] <= worst[0][1]:
                    break
                chosen.remove(worst)
                spare.remove(best)
                chosen.append((best, type_))
    ages = [a for (_, a), _ in chosen]
    tier = age_tier(ages) if ages else 10
    if not missing and tier < spec["min_age"]:
        missing.append(f"herbs averaging {spec['min_age']}-year or older")
    core = None
    if kind == "breakthrough":
        key = f"core:{spec['core']}:{grade}"
        core = next((i for i in db.get_items(conn, user_id, "materials") if i["key"] == key), None)
        if not core:
            missing.append(f"1 {grade} {loot.CORE_NAMES[spec['core']]}")
    uses = {}
    for (item, _), _ in chosen:
        uses.setdefault(item["id"], [item, 0])[1] += 1
    return {"uses": [tuple(v) for v in uses.values()], "ages": ages, "age": tier, "core": core, "missing": missing}


def take_ingredients(conn, user_id, plan_):
    """Use up the planned herbs and core. False (nothing taken) if any is gone in the meantime."""
    wanted = list(plan_["uses"]) + ([(plan_["core"], 1)] if plan_["core"] else [])
    for item, qty in wanted:
        fresh = db.get_item(conn, user_id, item["id"])
        if not fresh or fresh["qty"] < qty:
            return False
    for item, qty in wanted:
        db.remove_item(conn, item["id"], qty)
    return True


# ── the minigame ──────────────────────────────────────────────────────

@dataclass
class Prompt:
    stage: int
    title: str
    lines: list
    options: list            # [(key, label, emoji)]
    seconds: float
    style: dict = field(default_factory=dict)    # key → "primary" / "danger" / "success"
    view: dict = field(default_factory=dict)     # what the card draws: the shown heat state / pulse (bot/craft_card)


STAGE_NAMES = {1: "🔥 Ignite the Cauldron", 2: "🌿 Add the Herbs", 3: "☯️ Fuse the Essences",
               4: "💊 Condense the Pill", 5: "🔒 Seal the Core", 6: "⚡ Pill Tribulation"}

PULSES = ["a faint glow", "a steady light", "the light brightens", "the light swells, warm and full",
          "✨ the light trembles, ready to set", "cracks of light race across the pill"]
POSITION = {1: "first", 2: "second", 3: "third", 4: "fourth"}
DIRECTIONS = [("left", "⬅️", "the LEFT"), ("above", "⬆️", "ABOVE"), ("right", "➡️", "the RIGHT")]


class Craft:
    def __init__(self, kind, grade, rank, age, rng=None, zone_bonus=0):
        self.rng = rng or random.Random()
        self.kind, self.grade, self.age = kind, grade, age
        spec = pill_spec(kind, grade)
        self.required_rank = spec["rank"]
        self.ranks_above = max(0, rank - spec["rank"])
        relief = min(self.ranks_above, alchemy.RANK_RELIEF["max_ranks_counted"])
        dgrade = grade
        if kind == "breakthrough":
            i = alchemy.GRADES.index(grade) + alchemy.BREAKTHROUGH_DIFFICULTY_STEP
            dgrade = alchemy.GRADES[min(i, len(alchemy.GRADES) - 1)]
        self.diff = alchemy.DIFFICULTY[dgrade]
        self.zone_width = round(self.diff["zone"] * (1 + alchemy.RANK_RELIEF["zone_bonus"] * relief)) + round(zone_bonus)
        self.zone_bonus = round(zone_bonus)       # degrees from the Furnace artifact (炉)
        self.seconds = self.diff["seconds"] + alchemy.RANK_RELIEF["seconds_bonus"] * relief
        self.hints = alchemy.RANK_RELIEF["hints_per_rank"] * relief
        a = alchemy.HERB_AGES[age]
        self.forgive = (1 if relief >= alchemy.RANK_RELIEF["forgive_from_ranks"] else 0) + a.get("mistakes_forgiven", 0)
        self.explode_below = a.get("explode_below", alchemy.EXPLODE_BELOW)
        self.score_bonus, self.max_patterns = a["score_bonus"], a["max_patterns"]
        self.stages = list(self.diff["stages"]) + ([alchemy.SEAL_CORE_STAGE] if kind == "breakthrough" else [])
        self.scores = {}
        self.log = []                # feedback for the last decision
        self.stage_i = -1
        self.done = False
        self.result = None
        self.core_lost = False
        self.tribulation = None      # None / "pending" / "won" / "lost"
        self._prompt = None
        self.decisions = 0
        self._next_stage()

    # ── flow ─────────────────────────────────────────────────────────

    @property
    def stage(self):
        return self.stages[self.stage_i] if 0 <= self.stage_i < len(self.stages) else None

    def _next_stage(self):
        self.stage_i += 1
        if self.stage_i >= len(self.stages):
            self._finish()
            return
        getattr(self, f"_start_{self.stage}")()

    def misleading(self):
        return self.rng.random() < self.diff["misleading"]

    def _mistake(self):
        """True if the mistake counts, False if a forgiveness was spent on it."""
        if self.forgive > 0:
            self.forgive -= 1
            self.log.append("🍀 Your experience saves the mistake (forgiven).")
            return False
        return True

    def prompt(self):
        """The current decision. Built once per decision, so a misleading hint stays the same on screen."""
        if self.done:
            return None
        if self._prompt is None:
            self._prompt = getattr(self, f"_prompt_{6 if self.tribulation == 'pending' else self.stage}")()
        return self._prompt

    def act(self, key):
        """key=None means the timer ran out."""
        self.log = []
        self._prompt = None
        self.decisions += 1
        if self.tribulation == "pending":
            self._act_tribulation(key)
        else:
            getattr(self, f"_act_{self.stage}")(key)

    # ── 🔥 Stage 1: heat ─────────────────────────────────────────────

    def _start_1(self):
        self.zone_lo = self.rng.randint(20, 85 - self.zone_width)
        self.heat = self.rng.choice([self.rng.randint(5, max(5, self.zone_lo - 5)),
                                     self.rng.randint(min(95, self.zone_lo + self.zone_width + 5), 95)])
        self.round, self.points = 0, 0
        self._roll_drift()

    def _roll_drift(self):
        if self.rng.random() < HEAT_SPIKE_CHANCE:
            self.drift = self.rng.choice([1, -1]) * self.rng.randint(*HEAT_SPIKE)
        else:
            self.drift = self.rng.randint(-HEAT_CALM_DRIFT, HEAT_CALM_DRIFT)
        if self.diff["wild_herbs"]:
            self.drift += self.rng.randint(-3, 3)

    def heat_state(self, heat):
        if heat < self.zone_lo:
            return "cold"
        if heat > self.zone_lo + self.zone_width:
            return "hot"
        return "zone"

    def _prompt_1(self):
        texts = {"cold": "The herbs lie dull and cold in the cauldron.", "hot": "The cauldron hisses and smokes!",
                 "zone": "A soft golden glow fills the cauldron."}
        state = self.heat_state(self.heat)
        if self.misleading():
            state = self.rng.choice([s for s in texts if s != state])
        if self.drift >= HEAT_SPIKE[0]:
            omen = "*The flames lick hungrily at the walls...*"
        elif self.drift <= -HEAT_SPIKE[0]:
            omen = "*A cold draught creeps under the cauldron...*"
        else:
            omen = "*The fire burns evenly.*"
        lines = [f"Round {self.round + 1} of {self.diff['rounds']} · keep the heat in the hidden safe zone "
                 f"({self.zone_width}° wide).",
                 f"🌡️ **{self.heat}°** {heat_bar(self.heat)}", texts[state], omen]
        return Prompt(1, STAGE_NAMES[1], lines, [("stoke", f"Stoke +{HEAT_STEP}°", "🔥"),
                                                 ("hold", "Hold", "✋"), ("fan", f"Fan −{HEAT_STEP}°", "🌬️")],
                      self.seconds, view={"heat_state": state})

    def _act_1(self, key):
        move = {"stoke": HEAT_STEP, "fan": -HEAT_STEP}.get(key, 0)
        if key is None:
            self.log.append("⏳ Too slow, the fire does as it likes.")
        self.heat = max(0, min(100, self.heat + move + self.drift))
        if self.heat_state(self.heat) == "zone":
            self.points += 1
            self.log.append(f"🔥 {self.heat}°: the cauldron glows steadily. In the zone!")
        else:
            self.log.append(f"🔥 {self.heat}°: " + ("too cold." if self.heat_state(self.heat) == "cold" else "too hot!"))
            if not self._mistake():
                self.points += 1
        self.round += 1
        if self.round >= self.diff["rounds"]:
            self.scores[1] = self.points / self.diff["rounds"]
            self.log.append(f"Heat control: **{self.scores[1]:.0%}**")
            self._next_stage()
        else:
            self._roll_drift()

    # ── 🌿 Stage 2: herb order ───────────────────────────────────────

    def _start_2(self):
        units = [t for t, n in KINDS[self.kind][3] for _ in range(n)]
        self.rng.shuffle(units)
        self.order, self.placed, self.points = units, 0, 0
        kinds = sorted(set(units))
        self.clues = []
        for t in kinds:
            spots = [i + 1 for i, u in enumerate(units) if u == t]
            if self.misleading() and len(kinds) > 1:
                spots = sorted(self.rng.sample(range(1, len(units) + 1), len(spots)))
            name = alchemy.HERBS[self.grade][t][0]
            where = " and ".join(POSITION[s] for s in spots)
            self.clues.append(self.rng.choice([f"*The {name} wants to go in {where}.*",
                                               f"*The cauldron hums: {name}, {where}.*",
                                               f"*{name} shies from the heat unless it goes in {where}.*"]))
        self.insights = []
        for pos in self.rng.sample(range(len(units)), min(self.hints, len(units))):
            self.insights.append(f"💡 Insight: the {POSITION[pos + 1]} herb is "
                                 f"**{alchemy.HERBS[self.grade][units[pos]][0]}**.")
        if len(kinds) == 1:
            self.scores[2] = 1.0
            self.log.append(f"🌿 Only {alchemy.HERBS[self.grade][kinds[0]][0]} in this recipe: it all goes in together.")
            self._next_stage()

    def _prompt_2(self):
        names = [alchemy.HERBS[self.grade][t][0] for t in self.order[:self.placed]]
        lines = ["Add the herbs in the order the cauldron asks for. A wrong herb causes a **backlash**.",
                 *self.clues, *self.insights,
                 f"In the cauldron: {', '.join(names) if names else 'nothing yet'}",
                 f"Which herb goes in **{POSITION[self.placed + 1]}**?"]
        kinds = sorted(set(self.order))
        return Prompt(2, STAGE_NAMES[2], lines,
                      [(t, alchemy.HERBS[self.grade][t][0], loot.TYPE_EMOJI[t]) for t in kinds], self.seconds)

    def _act_2(self, key):
        want = self.order[self.placed]
        name = alchemy.HERBS[self.grade][want][0]
        if key == want:
            self.points += 1
            self.log.append(f"🌿 The {name} sinks in smoothly.")
        else:
            self.log.append(("⏳ Too slow! " if key is None else "") + f"💥 **Backlash!** The cauldron spits fire. "
                            f"It wanted the {name}.")
            if not self._mistake():
                self.points += 1
        self.placed += 1
        if self.placed >= len(self.order):
            self.scores[2] = self.points / len(self.order)
            self.log.append(f"Herb order: **{self.scores[2]:.0%}**")
            self._next_stage()

    # ── ☯️ Stage 3: Yin and Yang ─────────────────────────────────────

    def _start_balance(self, far):
        while True:
            self.yin, self.yang = self.rng.randint(15, 85), self.rng.randint(15, 85)
            if self.imbalance() >= far:
                break
        self.round = 0

    def _start_3(self):
        self._start_balance(30)

    def imbalance(self):
        return abs(self.yin - 50) + abs(self.yang - 50)

    def balance_score(self):
        if abs(self.yin - 50) <= BALANCE_TOLERANCE and abs(self.yang - 50) <= BALANCE_TOLERANCE:
            return 1.0
        return max(0.0, 1 - self.imbalance() / 60)

    def _balance_prompt(self, stage, moves, extra):
        lines = [*extra, f"Move {self.round + 1} of {moves} · bring both to 50.",
                 f"🌑 Yin  **{self.yin}** {heat_bar(self.yin, mark=50)}",
                 f"🌕 Yang **{self.yang}** {heat_bar(self.yang, mark=50)}",
                 "Circulate: both flow toward each other · Compress: both −10 · Cool: Yin +12 · Ignite: Yang +12"]
        if self.diff["wild_herbs"]:
            lines.append("*Wild herbs push the bars each turn.*")
        return Prompt(stage, STAGE_NAMES[stage], lines, [("circulate", "Circulate", "🌀"), ("compress", "Compress", "🗜️"),
                                                         ("cool", "Cool", "❄️"), ("ignite", "Ignite", "🔥")],
                      self.seconds)

    def _balance_move(self, key):
        if key == "circulate":
            mid = (self.yin + self.yang) / 2
            step = lambda v: v + max(-10, min(10, mid - v))
            self.yin, self.yang = round(step(self.yin)), round(step(self.yang))
        elif key in BALANCE_MOVES:
            dy, dg = BALANCE_MOVES[key]
            self.yin, self.yang = self.yin + dy, self.yang + dg
        else:
            self.log.append("⏳ Too slow, the essences drift.")
        if self.diff["wild_herbs"]:
            if self.rng.random() < 0.5:
                self.yin += self.rng.randint(-WILD_HERB_PUSH, WILD_HERB_PUSH)
            else:
                self.yang += self.rng.randint(-WILD_HERB_PUSH, WILD_HERB_PUSH)
        self.yin, self.yang = max(0, min(100, self.yin)), max(0, min(100, self.yang))
        self.round += 1
        self.log.append(f"☯️ Yin {self.yin} · Yang {self.yang}")

    def _prompt_3(self):
        return self._balance_prompt(3, self.diff["rounds"], ["Balance the two essences before the moves run out."])

    def _act_3(self, key):
        self._balance_move(key)
        if self.round >= self.diff["rounds"] or self.balance_score() == 1.0:
            self.scores[3] = self.balance_score()
            self.log.append(f"Fusion: **{self.scores[3]:.0%}**" + (" (perfect balance!)" if self.scores[3] == 1 else ""))
            self._next_stage()

    # ── 💊 Stage 4: condense ─────────────────────────────────────────

    def _start_4(self):
        self.pulse = self.rng.randint(0, 1)

    def _prompt_4(self):
        shown = self.pulse
        if self.misleading():
            shown = max(0, min(len(PULSES) - 2, shown + self.rng.choice([-1, 1])))
        lines = ["The pill pulses in the cauldron. Press **Condense** at the perfect pulse: too early is weak, "
                 "too late and it cracks.", f"💊 *{PULSES[shown].capitalize()}...*"]
        return Prompt(4, STAGE_NAMES[4], lines, [("condense", "Condense", "💊"), ("wait", "Wait", "⏳")],
                      self.seconds, {"condense": "success"}, view={"pulse": shown})

    def _act_4(self, key):
        if key == "condense":
            self.scores[4] = PULSE_SCORE[min(4, self.pulse)]
            self.log.append(f"💊 You condense at *{PULSES[self.pulse]}*: **{self.scores[4]:.0%}**")
            self._next_stage()
            return
        self.pulse += self.rng.choice([1, 1, 1, 2])
        if self.pulse >= len(PULSES) - 1:
            self.scores[4] = CRACKED_SCORE
            self.log.append(("⏳ " if key is None else "") + f"💔 Too late: *{PULSES[-1]}*. **{CRACKED_SCORE:.0%}**")
            self._next_stage()

    # ── 🔒 Stage 5: seal the core ────────────────────────────────────

    def _start_5(self):
        self._start_balance(20)

    def _prompt_5(self):
        return self._balance_prompt(5, alchemy.SEAL_CORE_MOVES, [
            "The Beast Core fights the pill. Balance it in **3 moves** or the core shatters!"])

    def _act_5(self, key):
        self._balance_move(key)
        if self.round >= alchemy.SEAL_CORE_MOVES:
            if self.imbalance() <= SEAL_PASS:
                self.scores[5] = self.balance_score()
                self.log.append(f"🔒 The core is sealed into the pill! **{self.scores[5]:.0%}**")
                self._next_stage()
            else:
                self.core_lost = True
                self.log.append("💥 The Beast Core shatters! The craft fails.")
                self._finish(failed=True)

    # ── finishing and the Pill Tribulation ──────────────────────────

    def score(self):
        total = weight = 0
        for stage, s in self.scores.items():
            w = CONDENSE_WEIGHT if stage == 4 else 1
            total += s * w
            weight += w
        return min(1.0, (total / weight if weight else 0) + self.score_bonus)

    def _finish(self, failed=False):
        if failed:
            self.done, self.result = True, 0
            return
        s = self.score()
        n = patterns_for(s, self.max_patterns)
        if s < self.explode_below:
            n = 0
        if n == 9 and alchemy.NINE_PATTERN_NEEDS_TRIBULATION and self.tribulation is None:
            self.tribulation, self.strike = "pending", 0
            self.blocked = 0
            self._roll_strike()
            return
        self.done, self.result = True, n

    def _roll_strike(self):
        self.strike_dir = self.rng.choice(DIRECTIONS)

    def _prompt_6(self):
        lines = ["⛈️ *Dark clouds gather over the cauldron. The heavens will not let a nine-pattern pill be born "
                 "without a trial!*", f"Strike {self.strike + 1} of {TRIBULATION_STRIKES}: lightning gathers "
                 f"from **{self.strike_dir[2]}**. Raise your shield!"]
        return Prompt(6, STAGE_NAMES[6], lines, [(k, f"Shield {w.title()}", e) for k, e, w in DIRECTIONS],
                      self.seconds)

    def _act_tribulation(self, key):
        if key == self.strike_dir[0]:
            self.blocked += 1
            self.log.append("🛡️ The lightning breaks on your shield!")
        else:
            self.log.append("⚡ The lightning strikes the cauldron!")
        self.strike += 1
        if self.strike < TRIBULATION_STRIKES:
            self._roll_strike()
            return
        won = self.blocked == TRIBULATION_STRIKES
        self.tribulation = "won" if won else "lost"
        self.done, self.result = True, 9 if won else alchemy.TRIBULATION_FAIL_PATTERNS

    def exp(self):
        return round(alchemy.craft_exp(self.grade, self.result, self.kind == "breakthrough", self.ranks_above))


def heat_bar(value, width=20, mark=None):
    pos = round(value / 100 * (width - 1))
    cells = ["▱"] * width
    if mark is not None:
        cells[round(mark / 100 * (width - 1))] = "┃"
    cells[pos] = "◆"
    return "".join(cells)


def finish_craft(conn, user_id, craft, now=None):
    """Store the pill, add alchemy EXP. Returns (lines, announcement or None)."""
    p = db.get_player(conn, user_id)
    exp = craft.exp()
    old_rank = rank_of(p["alchemy_exp"])
    new_exp = p["alchemy_exp"] + exp
    db.update_player(conn, user_id, alchemy_exp=new_exp)
    lines, news = [], None
    if craft.result == 0:
        lines.append("💥 **The cauldron explodes!** The herbs are lost." if not craft.core_lost
                     else "💥 **The craft fails.** The herbs and the Beast Core are lost.")
    else:
        pill = crafted_pill(craft.kind, craft.grade, craft.result)
        stored, _ = loot.store(conn, user_id, [pill])
        e = alchemy.pattern_effect(craft.result)
        lines.append(f"✨ You craft a **{pill['name']}**! Effect ×{e:.2f} · toxicity +{toxicity_for(craft.result)}")
        if not stored:
            lines.append("⚠️ Your bag is full, so the pill rolls away and is lost.")
        if craft.result == 9:
            news = f"📢 Thunder fades over the Jianghu: **{p['name']}** has crafted a nine-pattern **{pill['name']}**!"
    lines.append(f"Final score **{craft.score():.0%}**" + (f" (+{craft.score_bonus:.0%} from {craft.age}-year herbs)"
                                                           if craft.score_bonus else ""))
    lines.append(f"📈 +{exp:,} alchemy EXP")
    new_rank = rank_of(new_exp)
    if new_rank > old_rank:
        lines.append(f"🎉 You are now a **{rank_label(new_rank)} Alchemist**!")
    return lines, news


# ── using crafted pills (called from loot.use_item) ───────────────────

def pill_info(item):
    """(kind, grade, patterns or None). Shop and merchant Qi pills have no patterns."""
    d = item.get("data") or {}
    if d.get("kind"):
        return d["kind"], d["grade"], d["patterns"]
    return "qi", item["grade"], None


def below_realm(player, grade):
    return alchemy.GRADES.index(grade) < alchemy.GRADES.index(alchemy.HERB_TIER_BY_REALM[player["realm"]])


def use_pill(conn, user_id, item, now=None):
    """Swallow a Qi, Qi Burst, Mending or Cleansing pill. Returns the message."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    kind, grade, patterns = pill_info(item)
    effect = alchemy.pattern_effect(patterns) if patterns else 1.0
    added = toxicity_for(patterns) if patterns else 1
    if kind == "breakthrough":
        return ("🏔️ Breakthrough pills are used by **/breakthrough** at a realm gate: the best one in your bag "
                "is taken automatically.")
    tox_now = rules.current_toxicity(p, now)
    if kind == "cleansing":
        removed = max(1, int(pill_spec(kind, grade)["toxicity_removed"] * effect))
        db.remove_item(conn, item["id"])
        db.update_player(conn, user_id, toxicity=max(0, tox_now - removed), toxicity_at=now)
        return f"💧 The **{item['name']}** washes through your meridians. Toxicity {tox_now} → {max(0, tox_now - removed)}."
    tox = tox_now + added
    strength = rules.pill_effect_mult(tox) * effect
    half = kind in ("qi", "burst") and below_realm(p, grade)
    if half:
        strength *= alchemy.BELOW_REALM_EFFECT
    note = ""
    if rules.pill_effect_mult(tox) < 1:
        note += " ☠️ Your body is clogged with pill toxins, so the pill works less well."
    if half:
        note += " The pill is below your realm's grade, so it gives only half."
    if kind == "qi":
        current = rules.active_pill(p, now)
        if current:
            return (f"Your **{alchemy.QI_PILLS[current[0]]['name']}** is still working "
                    f"({rules.fmt_duration(current[2])} left). Pills do not stack.")
        mult = 1 + (training.QI_PILLS[grade] - 1) * strength
        db.remove_item(conn, item["id"])
        db.update_player(conn, user_id, pill_grade=grade, pill_mult=mult,
                         pill_expires=now + training.QI_PILL_DURATION_HOURS * 3600, toxicity=tox, toxicity_at=now)
        return (f"💊 You swallow the **{item['name']}**. Qi Rate ×{mult:.2f} for "
                f"{training.QI_PILL_DURATION_HOURS} hours. Toxicity: {tox}." + note)
    if kind == "burst":
        techs = db.get_techniques(conn, user_id)
        rate, _ = rules.qi_rate(p, now, techs)
        qi = rate * pill_spec(kind, grade)["hours"] * strength
        db.remove_item(conn, item["id"])
        p, events = rules.add_qi(p, qi, techs, now=now)
        db.update_player(conn, user_id, qi=p["qi"], qi_overflow=p["qi_overflow"], layer=p["layer"], toxicity=tox,
                         toxicity_at=now)
        return "\n".join([f"⚡ The **{item['name']}** bursts in your dantian: **+{qi:,.1f} Qi**. Toxicity: {tox}." + note]
                         + events)
    # mending
    spec = pill_spec(kind, grade)
    hurt = rules.injured_for(p, now)
    if not hurt:
        return "You are not injured. Keep the Mending Pill for after a hard fight."
    db.remove_item(conn, item["id"])
    if spec["injury_minutes"] is None:
        left = 0
    else:
        left = max(0, hurt - spec["injury_minutes"] * 60 * strength)
    db.update_player(conn, user_id, injured_until=now + left if left else None, toxicity=tox, toxicity_at=now)
    return (f"❤️ The **{item['name']}** knits your wounds. "
            + (f"Injury left: {rules.fmt_duration(left)}." if left else "Your injury is healed!")
            + f" Toxicity: {tox}." + note)


def best_breakthrough_pill(conn, user_id, player):
    """The breakthrough pill /breakthrough would use at a realm gate (your realm's grade or higher), or None."""
    need = alchemy.GRADES.index(alchemy.HERB_TIER_BY_REALM[player["realm"]])
    best = None
    for it in db.get_items(conn, user_id, "pills"):
        kind, grade, patterns = pill_info(it)
        if kind != "breakthrough" or alchemy.GRADES.index(grade) < need:
            continue
        bonus = training.BREAKTHROUGH_PILLS[grade] * alchemy.pattern_effect(patterns)
        if best is None or bonus > best[1]:
            best = (it, bonus)
    return best


# ── Discord ───────────────────────────────────────────────────────────

# button colours per action (the look only: the actions themselves come from Craft.prompt)
BUTTON_STYLE = {"stoke": discord.ButtonStyle.danger, "ignite": discord.ButtonStyle.danger,
                "hold": discord.ButtonStyle.secondary, "wait": discord.ButtonStyle.secondary,
                "compress": discord.ButtonStyle.secondary, "condense": discord.ButtonStyle.success}


def button_emoji(bot, key, default):
    """The medallion icon uploaded as an application emoji (cards/alchemy_icons.py), else the plain emoji."""
    em = getattr(bot, "emojis_ma", None)
    custom = getattr(em, "custom", {}).get("craft_" + key) if em else None
    return custom or default


class CraftView(OwnedView):
    """Picker → recipe → stages → result, all in one message."""

    def __init__(self, bot, owner_id, rng=None):
        super().__init__(owner_id, timeout=IDLE_TIMEOUT)
        self.bot, self.rng = bot, rng or random.Random()
        self.choice = None          # (kind, grade)
        self.prefer = "young"
        self.craft = None
        self.result_lines = None
        self.notice = None
        self.timer = None
        self.shown_at = None
        self.herbs = []             # the planned ingredients, as card rows (bot/craft_card.herb_rows)
        self.outcome = None         # {exp, rank_up, stored} once the craft is over
        self.build()

    @property
    def player(self):
        return db.get_player(self.bot.conn, self.owner_id)

    def rank(self):
        return rank_of(self.player["alchemy_exp"])

    def furnace(self):
        """Extra safe-zone degrees from a worn Furnace artifact (炉)."""
        return gear.artifact_bonus(self.player, "craft_zone_degrees")

    # ── screens ──────────────────────────────────────────────────────

    def embed(self):
        if self.craft and not self.craft.done:
            return self.stage_embed()
        if self.result_lines:
            e = discord.Embed(title="🏺 The Cauldron Cools", description="\n".join(self.result_lines), color=COLOR)
            e.set_footer(text=self.rank_line())
            return e
        if self.choice:
            return self.recipe_embed()
        return self.picker_embed()

    def rank_line(self):
        exp = self.player["alchemy_exp"]
        r = self.rank()
        nxt = alchemy.ALCHEMIST_RANK_EXP.get(r + 1)
        return f"{rank_label(r)} Alchemist · {exp:,} EXP" + (f" / {nxt:,} for {rank_label(r + 1)}" if nxt else " · max rank")

    def craftable(self):
        r = self.rank()
        return [(k, g) for k in KINDS for g in alchemy.GRADES if pill_spec(k, g)["rank"] <= r]

    def picker_embed(self):
        e = discord.Embed(title="🏺 Alchemy Cauldron", color=COLOR, description=(
            "Choose a pill to refine. Every craft is random: the safe heat, herb order, balance and timing change "
            "each time. No cooldown: your herbs are the limit.\n\n"
            "Score → **1–9 pill patterns** (丹纹). More patterns, stronger pill and less toxicity. "
            "Below 40% the cauldron explodes."))
        ready = []
        for k, g in self.craftable():
            pl = plan(self.bot.conn, self.owner_id, k, g)
            if not pl["missing"]:
                ready.append(f"{KINDS[k][1]} {pill_name(k, g)}")
        e.add_field(name="Ready to craft", value="\n".join(ready[:15]) or "Nothing yet. **/gather** herbs first.",
                    inline=False)
        if self.notice:
            e.add_field(name="​", value=self.notice, inline=False)
        e.set_footer(text=self.rank_line())
        return e

    def recipe_embed(self):
        kind, grade = self.choice
        spec = pill_spec(kind, grade)
        pl = plan(self.bot.conn, self.owner_id, kind, grade, self.prefer)
        recipe = " + ".join(f"{n} {alchemy.HERBS[grade][t][0]}" for t, n in KINDS[kind][3])
        if kind == "breakthrough":
            recipe += f" + 1 {loot.CORE_NAMES[spec['core']]}"
        c = Craft(kind, grade, self.rank(), pl["age"], random.Random(0), self.furnace())
        lines = [f"**Recipe:** {recipe}",
                 f"**Herbs:** {age_word(spec['min_age'])} · **Difficulty:** {c.diff['name']} "
                 f"({len(c.stages)} stages, {c.seconds:g}s per decision)"]
        if pl["missing"]:
            lines.append(f"❌ **Missing:** {', '.join(pl['missing'])}")
        else:
            used = ", ".join(f"{loot.herb_label(i)} ×{q}" for i, q in pl["uses"])
            lines.append(f"✅ **Will use:** {used}" + (f", {loot.describe(pl['core'])}" if pl["core"] else ""))
            a = alchemy.HERB_AGES[pl["age"]]
            lines.append(f"Average age **{pl['age']}-year**: up to **{a['max_patterns']}** patterns"
                         + (f", +{a['score_bonus']:.0%} score" if a["score_bonus"] else ""))
        relief = []
        if c.ranks_above:
            relief.append(f"{min(c.ranks_above, 3)} rank(s) above the recipe: wider heat zone, more time"
                          + (", herb hints" if 2 in c.stages else ""))
        if c.forgive:
            relief.append(f"{c.forgive} mistake(s) forgiven")
        if c.zone_bonus:
            relief.append(f"🔮 Furnace artifact: +{c.zone_bonus}° heat zone")
        if relief:
            lines.append("🍀 " + " · ".join(relief))
        lines.append("\n**Stages:** " + " → ".join(STAGE_NAMES[s] for s in c.stages))
        e = discord.Embed(title=f"{KINDS[kind][1]} {pill_name(kind, grade)}", description="\n".join(lines), color=COLOR)
        if self.notice:
            e.add_field(name="​", value=self.notice, inline=False)
        e.set_footer(text=self.rank_line())
        return e

    def stage_embed(self):
        pr = self.craft.prompt()
        lines = []
        if self.craft.log:
            lines += self.craft.log + [""]
        lines += pr.lines
        stage_no = (self.craft.stages.index(pr.stage) + 1) if pr.stage in self.craft.stages else None
        title = f"{pill_name(self.craft.kind, self.craft.grade)} · {pr.title}"
        e = discord.Embed(title=title, description="\n".join(lines), color=COLOR)
        e.set_footer(text=(f"Stage {stage_no} of {len(self.craft.stages)} · " if stage_no else "")
                     + f"⏳ {pr.seconds:g}s per decision")
        return e

    # ── buttons ──────────────────────────────────────────────────────

    def build(self):
        self.clear_items()
        if self.craft and not self.craft.done:
            pr = self.craft.prompt()
            for key, label, emoji in pr.options:
                style = BUTTON_STYLE.get(key) or {"success": discord.ButtonStyle.success}.get(
                    pr.style.get(key), discord.ButtonStyle.primary)
                self.button(label, self.make_act(key), emoji=button_emoji(self.bot, key, emoji), style=style)
            return
        if self.result_lines:
            self.button("Craft Again", self.on_again, emoji=button_emoji(self.bot, "again", "🏺"),
                        style=discord.ButtonStyle.success)
            self.button("Close", self.on_close, emoji="🏮")
            return
        if self.choice:
            pl = plan(self.bot.conn, self.owner_id, *self.choice, self.prefer)
            self.button("Begin", self.on_begin, emoji="🔥", style=discord.ButtonStyle.success,
                        disabled=bool(pl["missing"]))
            self.button("Use oldest herbs" if self.prefer == "young" else "Use youngest herbs", self.on_prefer,
                        emoji="🏵️" if self.prefer == "young" else "🌱")
            self.button("Back", self.on_back, emoji="◀️")
            return
        options = []
        for k, g in self.craftable()[:25]:
            pl = plan(self.bot.conn, self.owner_id, k, g)
            desc = "Ready" if not pl["missing"] else "Missing " + ", ".join(pl["missing"])
            options.append(discord.SelectOption(label=pill_name(k, g)[:100], value=f"{k}:{g}", emoji=KINDS[k][1],
                                                description=desc[:100]))
        sel = discord.ui.Select(placeholder="Choose a pill to craft", options=options)
        sel.callback = self.on_pick
        self.picker = sel
        self.add_item(sel)

    async def redraw(self, interaction):
        """The picker and recipe screens: text only, so any card from the last craft is taken off."""
        self.build()
        await interaction.response.edit_message(embed=self.embed(), view=self, attachments=[])
        self.notice = None

    async def on_pick(self, interaction):
        kind, grade = self.picker.values[0].split(":")
        self.choice = (kind, grade)
        await self.redraw(interaction)

    async def on_prefer(self, interaction):
        self.prefer = "old" if self.prefer == "young" else "young"
        await self.redraw(interaction)

    async def on_back(self, interaction):
        self.choice = None
        await self.redraw(interaction)

    async def on_begin(self, interaction):
        kind, grade = self.choice
        async with self.bot.db_lock:
            pl = plan(self.bot.conn, self.owner_id, kind, grade, self.prefer)
            ok = not pl["missing"] and take_ingredients(self.bot.conn, self.owner_id, pl)
        if not ok:
            self.notice = "Your herbs changed in the meantime. Check the recipe again."
            await self.redraw(interaction)
            return
        self.craft = Craft(kind, grade, self.rank(), pl["age"], self.rng, self.furnace())
        self.herbs = craft_card.herb_rows(pl["uses"], pl["core"])
        self.result_lines, self.outcome = None, None
        await self.show_step(interaction)

    def make_act(self, key):
        async def cb(interaction):
            await self.resolve(key, time.monotonic() - (self.shown_at or time.monotonic()), interaction)
        return cb

    async def resolve(self, key, elapsed, interaction=None):
        c = self.craft
        if not c or c.done:
            return
        if self.timer and interaction is not None:
            self.timer.cancel()
        if elapsed > c.seconds + TIMER_GRACE_SECONDS:
            key = None
        c.act(key)
        if c.done:
            await self.finish_and_store(c)
        if interaction is not None or self.message:
            await self.show_step(interaction)
        if c.done and getattr(self, "news", None) and self.message:
            try:
                await self.message.channel.send(self.news)
            except Exception:
                log.warning("Could not announce a nine-pattern pill", exc_info=True)
            self.news = None

    async def finish_and_store(self, c):
        async with self.bot.db_lock:
            old_rank = self.rank()
            self.result_lines, news = finish_craft(self.bot.conn, self.owner_id, c)
            new_rank = self.rank()
        self.outcome = {"exp": c.exp(), "rank_up": rank_label(new_rank) if new_rank > old_rank else None,
                        "stored": not any("bag is full" in line.lower() for line in self.result_lines)}
        self.result_lines = c.log + [""] + self.result_lines if c.log else self.result_lines
        self.news = news

    async def card_file(self):
        """The Alchemy Chamber card as a JPEG (rendered on the card thread), or None if it can't be drawn."""
        try:
            data = craft_card.card_data(self.craft, self.herbs, self.outcome)
            img = await card_render.render(render_alchemy, data)
        except Exception:
            log.exception("Could not render the alchemy card")
            return None
        return jpg(img, "craft.jpg")

    async def show_step(self, interaction, view=True):
        """Render the card for the current decision (or the result) and edit the one craft message."""
        self.build()
        if interaction is not None and not interaction.response.is_done():
            await interaction.response.defer()          # rendering can take a moment: answer Discord first
        file = await self.card_file()
        kw = {"embed": self.embed(), "view": self if view else None, "attachments": [file] if file else []}
        await self.edit(interaction, **kw)
        if view:
            self.after_show()                            # the decision timer starts once the card is shown

    async def edit(self, interaction, **kw):
        try:
            if interaction is not None:
                await interaction.edit_original_response(**kw)
                return
        except discord.HTTPException:
            log.warning("Editing the craft through the interaction failed; editing the message instead", exc_info=True)
        if self.message is not None:
            try:
                await self.message.edit(**kw)
            except discord.HTTPException:   # interaction token expired (15 min): edit through the channel
                ch = getattr(self.message, "channel", None)
                if ch is None:
                    raise
                await ch.get_partial_message(self.message.id).edit(**kw)

    def after_show(self):
        if self.craft and not self.craft.done:
            self.start_timer()

    def start_timer(self):
        self.shown_at = time.monotonic()
        c = self.craft
        marker = c.decisions

        async def expire():
            await asyncio.sleep(c.seconds + TIMER_GRACE_SECONDS)
            if c is self.craft and not c.done and c.decisions == marker and not self._handling:
                self._handling = True
                try:
                    await self.resolve(None, c.seconds + TIMER_GRACE_SECONDS)
                except Exception:
                    log.exception("Craft timeout failed")
                finally:
                    self._handling = False
        self.timer = asyncio.create_task(expire())

    async def on_again(self, interaction):
        self.craft, self.result_lines, self.outcome = None, None, None
        await self.redraw(interaction)

    async def on_close(self, interaction):
        self.clear_items()
        await interaction.response.edit_message(embed=self.embed(), view=None)
        self.finish()

    def finish(self):
        self.stop()
        self.bot.busy.discard((self.owner_id, "craft"))

    async def on_timeout(self):
        try:
            c = self.craft
            if c and not c.done:
                # walking away: every remaining decision times out
                for _ in range(200):
                    if c.done:
                        break
                    c.act(None)
                await self.finish_and_store(c)
                self.news = None
            if self.message:
                if c:
                    self.clear_items()
                    await self.show_step(None, view=False)
                else:
                    await self.message.edit(embed=self.embed(), view=None)
        except Exception:
            log.exception("Craft timeout handling failed")
        finally:
            self.bot.busy.discard((self.owner_id, "craft"))


def age_word(min_age):
    return "any age" if min_age <= 10 else f"average {min_age}-year or older"


def register(bot):
    @bot.tree.command(name="craft", description="Alchemy: refine herbs into pills in a cauldron minigame")
    async def craft(interaction: discord.Interaction):
        uid = interaction.user.id
        if not db.get_player(bot.conn, uid):
            await interaction.response.send_message(
                "You have not begun your journey yet. Use **/start** to step through the gates of the Jianghu.",
                ephemeral=True)
            return
        if (uid, "craft") in bot.busy:
            await interaction.response.send_message("Your cauldron is already lit. Finish that craft first.",
                                                    ephemeral=True)
            return
        bot.busy.add((uid, "craft"))
        try:
            view = CraftView(bot, uid)
            await interaction.response.send_message(embed=view.embed(), view=view)
            view.message = await interaction.original_response()
        except Exception:
            bot.busy.discard((uid, "craft"))
            raise


# ── Mending pills in fights (docs/combat.md) ──────────────────────────

def fight_pills(conn, user_id):
    """Mending pills in the bag, best first, as the fight engine wants them:
    [{"id", "name", "heal", "qty"}]. heal = share of max HP (alchemy.MENDING_PILLS × patterns × toxicity)."""
    p = db.get_player(conn, user_id)
    mult = rules.pill_effect_mult(rules.current_toxicity(p))
    out = []
    for it in db.get_items(conn, user_id, "pills"):
        kind, grade, patterns = pill_info(it)
        if kind != "mending":
            continue
        effect = alchemy.pattern_effect(patterns) if patterns else 1.0
        out.append({"id": it["id"], "name": pill_name(kind, grade), "qty": it.get("qty", 1), "grade": grade,
                    "heal": alchemy.MENDING_PILLS[grade]["heal"] * effect * mult, "patterns": patterns})
    return sorted(out, key=lambda x: -x["heal"])


def swallow_in_fight(conn, user_id, pill, now=None):
    """Take one pill swallowed in a fight out of the bag and add its toxicity."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    added = toxicity_for(pill["patterns"]) if pill.get("patterns") else 1
    db.remove_item(conn, pill["id"])
    db.update_player(conn, user_id, toxicity=rules.current_toxicity(p, now) + added, toxicity_at=now)


def bank_fight_pills(conn, fighter):
    """Remove the pills a fighter swallowed since the last call (the engine counts them in pill['used'])."""
    for pill in fighter.pills:
        while pill.get("used", 0) > pill.get("banked", 0):
            swallow_in_fight(conn, fighter.uid, pill)
            pill["banked"] = pill.get("banked", 0) + 1
