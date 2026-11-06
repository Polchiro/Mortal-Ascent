"""
/forge: the blacksmith minigame (docs/forge.md, section 5). Every number comes from forge.py.

Pick a gear item, then Enchant (fill an empty slot), Reroll (every slot) or Replace (lock one slot with a Seal
Stone, reroll the other). Add an essence, fuel and quench liquid if you like, see the cost, then play five
turn-based stages, each worth 0–20 points:

    🔥 1 Ignite the Forge   keep the heat in a hidden safe zone (Pump / Hold / Vent); fuel widens it
    🌡️ 2 Heat the Metal     pull the metal out at the colour the gear needs
    🔨 3 Hammer             Strike Hard / Strike Light / Reheat, reading the hint each strike
    💧 4 Quench             Water (fast, risky) or Oil (slow, safe), then plunge at the right temperature
    ✨ 5 Inscribe           carve the rune's strokes in order

Score below 50 = failed: every material used is lost, the gear and its passives stay. Otherwise the score gives a
rarity (capped by the gear tier and the essence grade) and the slot gets a passive.

Forge holds the game and has no Discord code, so it can be tested directly. ForgeView (bot/forge_view.py) drives it.
"""
import random
from dataclasses import dataclass, field

import forge

from . import db, loot, materials, passives

STAGE_KEYS = forge.STAGES
STROKE_LABEL = {"horizontal": ("Horizontal", "➖"), "vertical": ("Vertical", "⏐"), "sweep": ("Sweep", "↙️"),
                "press": ("Press", "↘️"), "dot": ("Dot", "⏺️"), "hook": ("Hook", "↩️")}
ACTION_LABEL = {"enchant": "Enchant", "reroll": "Reroll", "replace": "Replace"}


def rank_of(exp):
    return max(r for r, need in forge.BLACKSMITH_RANK_EXP.items() if exp >= need)


def rank_label(rank):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(rank, f"{rank}th") + " Grade"


def tier_no(tier):
    return forge.TIERS.index(tier) + 1


# ── choosing what to forge ────────────────────────────────────────────

def forgeable(conn, user_id):
    """Every weapon, armor and artifact the player owns, worn first."""
    out = []
    for cat in ("weapons", "armor", "artifacts"):
        out += db.get_items(conn, user_id, cat)
    return sorted(out, key=lambda i: (not i["equipped"], forge.GEAR_KINDS.index(passives.gear_kind(i)), i["id"]))


def actions_for(item):
    """Which actions this item allows now: enchant (an empty slot), reroll (a filled slot), replace (2 slots)."""
    s = passives.slots(item)
    out = []
    if None in s:
        out.append("enchant")
    if any(s):
        out.append("reroll")
    if item["grade"] in forge.REPLACE_TIERS and all(s):
        out.append("replace")
    return out


def owned_materials(conn, user_id):
    return {i["key"]: i for i in db.get_items(conn, user_id, "materials") if i["key"] in materials.MATERIALS}


def essence_options(conn, user_id, item):
    """[(key, usable, why)] for the essences the player holds that fit this gear."""
    gear, out = passives.gear_kind(item), []
    for key, it in owned_materials(conn, user_id).items():
        m = materials.MATERIALS[key]
        if m["kind"] != "essence" or not forge.essence_fits(gear, m["family"]):
            continue
        ok = forge.usable_essence(gear, item["grade"], m["family"], m["grade"])
        out.append((key, ok, "" if ok else f"no {forge.FAMILIES[m['family']]['name']} {gear} passive fits"))
    return out


def extra_options(conn, user_id, kind):
    """Fuel or liquid keys the player holds, best tier first."""
    keys = [k for k in owned_materials(conn, user_id) if materials.MATERIALS[k]["kind"] == kind]
    return sorted(keys, key=lambda k: -materials.MATERIALS[k]["tier"])


@dataclass
class Plan:
    item: dict
    action: str
    lock: int = None                 # Replace: the slot index kept
    essence: str = None              # material keys, or None
    fuel: str = None
    liquid: str = None
    uses: list = field(default_factory=list)       # [(material key, qty)]
    coins: int = 0
    missing: list = field(default_factory=list)    # reasons the forge can't start

    @property
    def gear(self):
        return passives.gear_kind(self.item)

    @property
    def tier(self):
        return self.item["grade"]


def make_plan(conn, user_id, item, action, essence=None, fuel=None, liquid=None, lock=None):
    """What a forge would cost and whether it can start."""
    p = db.get_player(conn, user_id)
    pl = Plan(item, action, lock, essence, fuel, liquid)
    n, tier = tier_no(item["grade"]), item["grade"]
    recipe = forge.RECIPE[tier]
    pl.uses = [(forge.material_key("base", n, gear=pl.gear), recipe["base"]), (forge.material_key("binding", n),
                                                                               recipe["binding"])]
    for key in (essence, fuel, liquid):
        if key:
            pl.uses.append((key, 1))
    if action == "replace":
        pl.uses.append(("seal", forge.REPLACE_SEAL_STONES))
    pl.coins = forge.forge_coins(action, tier)
    have = owned_materials(conn, user_id)
    for key, qty in pl.uses:
        got = have[key]["qty"] if key in have else 0
        if got < qty:
            pl.missing.append(f"{qty - got} more {materials.MATERIALS[key]['name']}")
    if p["lotus_coins"] < pl.coins:
        pl.missing.append(f"🪷 {pl.coins - p['lotus_coins']:,} more Lotus Coins")
    need = forge.RANK_NEEDED[tier]
    if rank_of(p["blacksmith_exp"]) < need:
        pl.missing.append(f"blacksmith rank {rank_label(need)}")
    if action not in actions_for(item):
        pl.missing.append(f"{ACTION_LABEL[action]} is not possible on this item now")
    if action == "replace" and lock not in (0, 1):
        pl.missing.append("a slot to lock")
    if essence:
        m = materials.MATERIALS[essence]
        if not forge.usable_essence(pl.gear, tier, m["family"], m["grade"]):
            pl.missing.append(f"an essence that fits ({m['name']} gives no {pl.gear} passive)")
    return pl


def take_materials(conn, user_id, plan):
    """Spend the materials and coins. False (nothing taken) if anything is gone in the meantime."""
    have = owned_materials(conn, user_id)
    for key, qty in plan.uses:
        if key not in have or have[key]["qty"] < qty:
            return False
    if plan.coins and db.spend(conn, user_id, "lotus_coins", plan.coins, f"Forge: {ACTION_LABEL[plan.action]}") is None:
        return False
    for key, qty in plan.uses:
        db.remove_item(conn, have[key]["id"], qty)
    return True


def refund_materials(conn, user_id, plan):
    """Put a plan's materials back (Second Chance)."""
    loot.store(conn, user_id, [materials.material(k, q) for k, q in plan.uses])


# ── the minigame ──────────────────────────────────────────────────────

@dataclass
class Prompt:
    stage: str
    title: str
    lines: list
    options: list            # [(key, label, emoji)]
    seconds: float
    view: dict = field(default_factory=dict)     # what the card draws (bot/forge_card.py)


class Forge:
    def __init__(self, tier, rank, rng=None, fuel=None, liquid=None, extra_seconds=0.0, extra_degrees=0):
        """fuel / liquid: material keys or None. extra_seconds: Swift Hands. extra_degrees: Steady Hand."""
        self.rng = rng or random.Random()
        self.tier = tier
        self.diff = forge.DIFFICULTY[tier]
        self.ranks_above = max(0, rank - forge.RANK_NEEDED[tier])
        relief = min(self.ranks_above, forge.RANK_RELIEF["max_ranks_counted"])
        fuel_bonus = forge.FUEL_ZONE_BONUS[materials.MATERIALS[fuel]["tier"] - 1] if fuel else 0
        liquid_bonus = forge.LIQUID_WINDOW_BONUS[materials.MATERIALS[liquid]["tier"] - 1] if liquid else 0
        rank_deg = forge.RANK_RELIEF["zone_degrees"] * relief
        self.seconds = self.diff["seconds"] + forge.RANK_RELIEF["seconds_bonus"] * relief + extra_seconds
        self.zone_width = self.diff["zone"] + rank_deg + fuel_bonus + extra_degrees
        self.window = self.diff["quench_window"] + rank_deg + liquid_bonus + extra_degrees
        self.bonuses = {"rank": relief, "fuel": fuel_bonus, "liquid": liquid_bonus, "steady": extra_degrees,
                        "swift": extra_seconds}
        self.points = {}             # stage → 0–20
        self.log = []
        self.stage_i = -1
        self.done = False
        self.decisions = 0
        self._prompt = None
        self._next_stage()

    # ── flow ─────────────────────────────────────────────────────────

    @property
    def stage(self):
        return STAGE_KEYS[self.stage_i] if 0 <= self.stage_i < len(STAGE_KEYS) else None

    def _next_stage(self):
        self.stage_i += 1
        if self.stage_i >= len(STAGE_KEYS):
            self.done = True
            return
        getattr(self, f"_start_{self.stage}")()

    def _score_stage(self, frac):
        pts = round(max(0.0, min(1.0, frac)) * forge.STAGE_MAX_POINTS)
        self.points[self.stage] = pts
        self.log.append(f"{forge.STAGE_NAMES[self.stage]}: **{pts} / {forge.STAGE_MAX_POINTS}**")
        self._next_stage()

    def misleading(self):
        return self.rng.random() < self.diff["misleading"]

    def prompt(self):
        """The current decision, built once so a misleading hint stays the same on screen."""
        if self.done:
            return None
        if self._prompt is None:
            self._prompt = getattr(self, f"_prompt_{self.stage}")()
        return self._prompt

    def act(self, key):
        """key=None: the timer ran out."""
        self.log = []
        self._prompt = None
        self.decisions += 1
        getattr(self, f"_act_{self.stage}")(key)

    def score(self):
        return sum(self.points.values())

    def rarity(self):
        """The rarity the score earned (before the gear and essence caps), or None = failed."""
        if not self.done or self.score() < forge.FAIL_BELOW:
            return None
        return forge.rarity_for_score(self.score(), self.points.get("inscribe", 0))

    # ── 🔥 Ignite ────────────────────────────────────────────────────

    def _start_ignite(self):
        lo, hi = forge.IGNITE["zone_from"], forge.IGNITE["zone_to"]
        self.zone_lo = self.rng.randint(lo, max(lo, hi - self.zone_width))
        top = min(100, self.zone_lo + self.zone_width)
        self.heat = self.rng.choice([self.rng.randint(0, max(0, self.zone_lo - 5)), self.rng.randint(min(100, top + 5), 100)])
        self.round, self.hits = 0, 0
        self._roll_drift()

    def _roll_drift(self):
        g = forge.IGNITE
        if self.rng.random() < g["spike_chance"]:
            self.drift = self.rng.choice([1, -1]) * self.rng.randint(*g["spike"])
        else:
            self.drift = self.rng.randint(-g["calm_drift"], g["calm_drift"])

    def heat_state(self, heat):
        if heat < self.zone_lo:
            return "cold"
        if heat > self.zone_lo + self.zone_width:
            return "hot"
        return "zone"

    def _prompt_ignite(self):
        texts = {"cold": "The coals glow dull and sleepy.", "hot": "Sparks roar out of the forge mouth!",
                 "zone": "A clean orange fire hums in the forge."}
        state = self.heat_state(self.heat)
        if self.misleading():
            state = self.rng.choice([s for s in texts if s != state])
        spike = forge.IGNITE["spike"][0]
        omen = ("*The wind gusts into the bellows...*" if self.drift >= spike
                else "*A cold draught creeps under the forge...*" if self.drift <= -spike else "*The fire burns evenly.*")
        lines = [f"Round {self.round + 1} of {self.diff['heat_rounds']} · keep the heat in the hidden safe zone "
                 f"({self.zone_width}° wide).", f"🌡️ **{self.heat}°**", texts[state], omen]
        g = forge.IGNITE
        return Prompt("ignite", forge.STAGE_NAMES["ignite"], lines,
                      [("pump", f"Pump +{g['pump']}°", "💨"), ("hold", "Hold", "✋"), ("vent", f"Vent {g['vent']}°", "🌬️")],
                      self.seconds, view={"heat": self.heat, "state": state, "round": self.round,
                                          "rounds": self.diff["heat_rounds"]})

    def _act_ignite(self, key):
        g = forge.IGNITE
        if key is None:
            self.log.append("⏳ Too slow, the fire does as it likes.")
        self.heat = max(0, min(100, self.heat + {"pump": g["pump"], "vent": g["vent"]}.get(key, 0) + self.drift))
        state = self.heat_state(self.heat)
        self.hits += state == "zone"
        self.log.append(f"🔥 {self.heat}°: " + {"zone": "steady and hot. In the zone!", "cold": "too cold.",
                                                "hot": "too hot!"}[state])
        self.round += 1
        if self.round >= self.diff["heat_rounds"]:
            self._score_stage(self.hits / self.diff["heat_rounds"])
        else:
            self._roll_drift()

    # ── 🌡️ Heat the metal ────────────────────────────────────────────

    def _start_heat(self):
        self.color = 0
        self.target = forge.HEAT_COLORS.index(forge.HEAT_TARGET[self.tier])

    def _prompt_heat(self):
        shown = self.color
        if self.misleading():
            shown = max(0, min(len(forge.HEAT_COLORS) - 1, shown + self.rng.choice([-1, 1])))
        lines = [f"This {self.tier.title()} gear needs the metal **{forge.HEAT_TARGET[self.tier]}**.",
                 f"The metal glows **{forge.HEAT_COLORS[shown]}**.",
                 "Pull it out at the right colour: too early or too late loses points, past white it burns."]
        return Prompt("heat", forge.STAGE_NAMES["heat"], lines, [("pull", "Pull it out", "🪝"), ("keep", "Keep heating", "🔥")],
                      self.seconds, view={"color": shown, "target": self.target})

    def _act_heat(self, key):
        if key == "pull":
            miss = abs(self.color - self.target)
            pts = forge.HEAT_POINTS_BY_MISS.get(miss, 0)
            self.log.append(f"🌡️ You pull it out **{forge.HEAT_COLORS[self.color]}**.")
            self._score_stage(pts / forge.STAGE_MAX_POINTS)
            return
        self.color += 1
        if self.color >= len(forge.HEAT_COLORS):
            self.log.append(("⏳ " if key is None else "") + "💔 The metal burns past white and spits sparks!")
            self._score_stage(0)

    # ── 🔨 Hammer ────────────────────────────────────────────────────

    def _start_hammer(self):
        self.strike, self.good = 0, 0
        self._roll_metal()

    def _roll_metal(self):
        self.metal = self.rng.choice(list(forge.HAMMER_STATES))

    def _prompt_hammer(self):
        shown = self.metal
        if self.misleading():
            shown = self.rng.choice([s for s in forge.HAMMER_STATES if s != self.metal])
        lines = [f"Strike {self.strike + 1} of {self.diff['strikes']}.", f"*{forge.HAMMER_STATES[shown]['hint']}*"]
        return Prompt("hammer", forge.STAGE_NAMES["hammer"], lines,
                      [("hard", "Strike Hard", "🔨"), ("light", "Strike Light", "🪶"), ("reheat", "Reheat", "🔥")],
                      self.seconds, view={"metal": shown, "strike": self.strike, "strikes": self.diff["strikes"]})

    def _act_hammer(self, key):
        right = forge.HAMMER_STATES[self.metal]["answer"]
        if key == right:
            self.good += 1
            self.log.append({"hard": "🔨 A clean, ringing blow!", "light": "🪶 A gentle tap shapes it just right.",
                             "reheat": "🔥 You reheat it in time."}[key])
        else:
            self.log.append(("⏳ Too slow! " if key is None else "") + "💢 A bad blow: the metal "
                            + {"hard": "wanted a hard strike.", "light": "wanted a light touch.",
                               "reheat": "was cooling and needed reheating."}[right])
        self.strike += 1
        if self.strike >= self.diff["strikes"]:
            self._score_stage(self.good / self.diff["strikes"])
        else:
            self._roll_metal()

    # ── 💧 Quench ────────────────────────────────────────────────────

    def _start_quench(self):
        t = forge.QUENCH_TEMPS
        self.medium = None
        self.temp = self.rng.randint(*t["start"])
        self.quench_target = self.rng.randint(*t["target"])

    def quench_window(self):
        return self.window * forge.QUENCH[self.medium]["window_mult"] if self.medium else self.window

    def _prompt_quench(self):
        if self.medium is None:
            w, o = forge.QUENCH["water"], forge.QUENCH["oil"]
            lines = ["Choose the quench.", f"💧 **Water**: fast and risky, narrow window, up to {w['max_points']} points.",
                     f"🛢️ **Oil**: slow and safe, wide window, up to {o['max_points']} points."]
            return Prompt("quench", forge.STAGE_NAMES["quench"], lines,
                          [("water", "Water", "💧"), ("oil", "Oil", "🛢️")], self.seconds, view={"temp": self.temp})
        shown = self.temp
        if self.misleading():
            shown += self.rng.choice([-1, 1]) * self.rng.randint(15, 35)
        lines = [f"Plunge the blade into the {self.medium} at about **{self.quench_target}°** "
                 f"(± {self.quench_window() / 2:.0f}°).", f"The blade is at **{shown}°** and cooling."]
        return Prompt("quench", forge.STAGE_NAMES["quench"], lines, [("plunge", "Plunge", "💦"), ("breath", "Wait a breath", "🫧"),
                                                                      ("wait", "Wait", "⏳")],
                      self.seconds, view={"temp": shown, "target": self.quench_target, "window": self.quench_window(),
                                          "medium": self.medium})

    def _quench_points(self):
        off, half = abs(self.temp - self.quench_target), self.quench_window() / 2
        top = forge.QUENCH[self.medium]["max_points"]
        if off <= half / 2:
            return top
        if off <= half:
            return round(top * forge.QUENCH_HALF_POINTS)
        return forge.QUENCH_MISS_POINTS

    def _act_quench(self, key):
        if self.medium is None:
            self.medium = key if key in forge.QUENCH else "oil"
            self.log.append(("⏳ Too slow: you grab the oil. " if key is None else "")
                            + ("💧 You ready the water trough." if self.medium == "water" else "🛢️ You ready the oil bath."))
            return
        if key == "plunge":
            pts = self._quench_points()
            self.log.append(f"💦 You plunge it at **{self.temp}°**: " + ("perfect!" if pts == forge.QUENCH[self.medium]["max_points"]
                                                                       else "close." if pts > forge.QUENCH_MISS_POINTS
                                                                       else "the steel shudders."))
            self._score_stage(pts / forge.STAGE_MAX_POINTS)
            return
        self.temp -= self.rng.randint(*forge.QUENCH_TEMPS["small_step" if key == "breath" else "step"])
        if self.temp < self.quench_target - self.quench_window() / 2:
            self.log.append(("⏳ " if key is None else "") + "🥶 The blade went cold before the quench.")
            self._score_stage(forge.QUENCH_MISS_POINTS / forge.STAGE_MAX_POINTS)

    # ── ✨ Inscribe ──────────────────────────────────────────────────

    def _start_inscribe(self):
        n = self.diff["strokes"]
        self.rune = self.rng.choice(forge.RUNES)
        self.order = [self.rng.choice(forge.STROKES) for _ in range(n)]
        self.carved, self.right = 0, 0
        self.carved_ok = []
        clue = list(self.order)
        if self.misleading():
            i = self.rng.randrange(n)
            clue[i] = self.rng.choice([s for s in forge.STROKES if s != clue[i]])
        self.clue = clue

    def _prompt_inscribe(self):
        want = self.order[self.carved]
        pool = [want] + self.rng.sample([s for s in forge.STROKES if s != want], forge.STROKE_CHOICES - 1)
        self.rng.shuffle(pool)
        seq = " → ".join(STROKE_LABEL[s][0] for s in self.clue)
        lines = [f"Carve the **Rune of {self.rune}**: {seq}.", f"Stroke {self.carved + 1} of {len(self.order)}."]
        return Prompt("inscribe", forge.STAGE_NAMES["inscribe"], lines,
                      [(s, STROKE_LABEL[s][0], STROKE_LABEL[s][1]) for s in pool], self.seconds,
                      view={"rune": self.rune, "clue": self.clue, "carved": self.order[:self.carved]})

    def _act_inscribe(self, key):
        want = self.order[self.carved]
        self.carved_ok.append(key == want)
        if key == want:
            self.right += 1
            self.log.append(f"✨ A clean {STROKE_LABEL[want][0].lower()} stroke.")
        else:
            self.log.append(("⏳ Too slow! " if key is None else "") + f"🩸 The chisel slips. It wanted a "
                            f"{STROKE_LABEL[want][0].lower()}.")
        self.carved += 1
        if self.carved >= len(self.order):
            self._score_stage(self.right / len(self.order))

    def exp(self, rarity):
        return round(forge.forge_exp(self.tier, rarity, self.ranks_above))


# ── finishing ─────────────────────────────────────────────────────────

def other_worn_passives(conn, user_id, item):
    """Passives on the player's other worn gear (no duplicates on one character)."""
    worn = [w for w in (db.get_items(conn, user_id, "weapons") + db.get_items(conn, user_id, "armor")
                        + db.get_items(conn, user_id, "artifacts")) if w["equipped"] and w["id"] != item["id"]]
    return set(passives.worn_passives(worn))


def apply_result(conn, user_id, plan, rarity, rng=random):
    """Write the new passives on the gear. Returns [(slot, key)] for the changed slots ([] if nothing fit)."""
    item = db.get_item(conn, user_id, plan.item["id"])
    s = passives.slots(item)
    if plan.action == "enchant":
        targets = [s.index(None)]
    elif plan.action == "replace":
        targets = [i for i in range(len(s)) if i != plan.lock]
    else:
        targets = list(range(len(s)))
    essence = None
    if plan.essence:
        m = materials.MATERIALS[plan.essence]
        essence = (m["family"], m["grade"])
    exclude = other_worn_passives(conn, user_id, item) | {k for i, k in enumerate(s) if k and i not in targets}
    changed = []
    for i in targets:
        key = forge.pick_passive(plan.gear, item["grade"], rarity, essence, exclude, rng)
        if key is None:
            continue
        s[i] = key
        exclude.add(key)
        changed.append((i, key))
    if changed:
        data = dict(item.get("data") or {}, passives=s)
        db.set_item_data(conn, item["id"], data)
    return changed


def finish_forge(conn, user_id, plan, game, rng=random, now=None):
    """Apply the outcome: passives on success, materials lost on failure (Second Chance once a day), blacksmith EXP.
    Returns a dict {rarity, changed, exp, rank_up, refunded, news, lines}."""
    p = db.get_player(conn, user_id)
    rarity = game.rarity()
    capped = forge.capped_rarity(rarity, plan.tier, materials.MATERIALS[plan.essence]["grade"] if plan.essence else None)
    out = {"rarity": None, "changed": [], "refunded": False, "news": None, "lines": [], "score": game.score()}
    if capped is None:
        out["title"] = failure_line(plan, rng)
        out["lines"].append(f"💥 **{out['title']}** Score {game.score()} / 100 (below {forge.FAIL_BELOW}).")
        if passives.has_artifact_passive(p, "second_chance") and db.daily_count(conn, user_id, "second_chance", now) < \
                passives.artifact_passive(p, "second_chance", "uses_per_day"):
            db.bump_daily(conn, user_id, "second_chance", now)
            refund_materials(conn, user_id, plan)
            out["refunded"] = True
            out["lines"].append("🍀 **Second Chance:** your artifact catches the pieces. The materials are saved.")
        else:
            out["lines"].append("The materials are lost. Your gear and its passives are safe.")
    else:
        changed = apply_result(conn, user_id, plan, capped, rng)
        out["rarity"], out["changed"] = capped, changed
        if not changed:
            out["lines"].append("The forge sang, but no new passive could take hold (all fitting passives are "
                                "already on your gear). The materials are used.")
        for _, key in changed:
            ps = forge.PASSIVES[plan.gear][key]
            out["lines"].append(f"✨ **{ps['name']}** ({forge.RARITY_EMOJI[ps['rarity']]} {ps['rarity']}): {ps['text']}")
            if ps["rarity"] in forge.ANNOUNCE_RARITIES:
                out["news"] = (f"📢 The anvil thunders across the Jianghu: **{p['name']}** has forged the Mythical "
                               f"passive **{ps['name']}** onto **{plan.item['name']}**!")
        if capped != rarity:
            out["lines"].append(f"(Your score earned {rarity}; the {plan.tier.title()} gear"
                                + (" and the essence" if plan.essence else "") + f" cap it at {capped}.)")
    old_rank = rank_of(p["blacksmith_exp"])
    out["exp"] = game.exp(out["rarity"])
    new_exp = p["blacksmith_exp"] + out["exp"]
    db.update_player(conn, user_id, blacksmith_exp=new_exp)
    new_rank = rank_of(new_exp)
    out["rank_up"] = rank_label(new_rank) if new_rank > old_rank else None
    out["lines"].append(f"📈 +{out['exp']:,} blacksmith EXP")
    if out["rank_up"]:
        out["lines"].append(f"🎉 You are now a **{out['rank_up']} Blacksmith**!")
    return out


FAILURES = {
    "weapon": ["The blade cracked in the quench...", "The edge shattered under the last blow..."],
    "armor": ["The plates split as they cooled...", "The rivets burst and the armor tore..."],
    "artifact": ["The jade cracked in the quench...", "The rune flared and burned out..."],
}


def failure_line(plan, rng=random):
    return rng.choice(FAILURES[plan.gear])


def swift_seconds(player):
    """Swift Hands: extra seconds per decision."""
    return passives.artifact_passive(player, "swift_hands", "decision_seconds")


def steady_degrees(player):
    """Steady Hand: extra degrees on the safe zones."""
    return passives.artifact_passive(player, "steady_hand", "safe_zone_degrees")


def new_game(conn, user_id, plan, rng=None):
    p = db.get_player(conn, user_id)
    return Forge(plan.tier, rank_of(p["blacksmith_exp"]), rng, plan.fuel, plan.liquid, swift_seconds(p),
                 steady_degrees(p))
