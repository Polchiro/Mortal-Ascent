"""
/train — game logic for one training session (docs/training.md, docs/challenges.md).

A session rolls a challenge, conditions and maybe a surprise event, the
player plays it with buttons (bot/views.py), and the score becomes Internal Qi:

    Qi = Final Qi Rate × 4 hours × score × (1 + 15% per condition) × event
    (score below 50% gives only 10%)

Built so far: Read the Master and Endless Waves, the two challenges of
tier 1 (every realm up to Martial Warrior). Higher tiers use the same two,
with that tier's harder numbers, until the other four are built.
"""
import random
import time

import challenges
import training

from . import db
from . import player as rules

STANCES = ["strike", "guard", "break"]
STANCE_LABEL = {"strike": "Strike", "guard": "Guard", "break": "Break"}
STANCE_EMOJI = {"strike": "⚔️", "guard": "🛡️", "break": "💥"}
BUILT_CHALLENGES = ["read_the_master", "endless_waves"]
CHALLENGE_NAMES = {"read_the_master": "🥋 Read the Master", "endless_waves": "🌊 Endless Waves"}
CONDITION_NAMES = {"heavy_rain": "🌧️ Heavy Rain", "old_injury": "🩹 Old Injury",
                   "drunken_master": "🍶 Drunken Master", "night_training": "🌙 Night Training"}
CONDITION_TEXT = {"heavy_rain": "all timers 25% shorter",
                  "old_injury": "Strike costs double stamina and gives half points",
                  "drunken_master": "half of the tells are unreliable, so look for the hidden sign",
                  "night_training": "the move stays hidden until the last 40% of the timer"}
# conditions that change each challenge (challenges.md: rolled only when they affect it)
APPLIES_TO = {"read_the_master": ["heavy_rain", "drunken_master", "night_training"],
              "endless_waves": ["heavy_rain", "old_injury", "night_training"]}

TELLS = {
    "strike": ["He draws his fist back to his hip...", "His shoulders tense as his weight pitches forward...",
               "He steps in, eyes fixed on your chest...", "His knuckles whiten as he winds up..."],
    "guard":  ["He shifts his weight onto his back foot...", "His arms rise to cover his face...",
               "He sinks low and goes very still...", "He turns his body side-on, chin tucked..."],
    "break":  ["He plants his feet and twists his hips...", "His palm opens, fingers spread wide...",
               "He lowers his head like a charging bull...", "He reaches out as if to grab your arm..."],
}
# A deceptive tell describes one move but carries a small sign of the real one
HIDDEN_SIGNS = {"strike": "...yet his rear fist is clenched tight.",
                "guard": "...yet his elbows stay tucked in.",
                "break": "...yet his front heel lifts off the ground."}

# DEFAULTS for Endless Waves timing (challenges.md says only "each wave faster")
WAVE_FIRST_SECONDS = {1: 3.0, 2: 2.75, 3: 2.5, 4: 2.25, 5: 2.0}
WAVE_SPEEDUP = 0.92
WAVE_MIN_SECONDS = 1.25
TIMER_GRACE_SECONDS = 1.0          # Discord round-trip allowance
RIVAL_STEPS, RIVAL_WINS_NEEDED = 3, 2


def counter_of(stance):
    return challenges.COUNTERS[stance]


def roll_session(player, rng=random):
    tier = challenges.REALM_TIER[player["realm"]]
    event = None
    for name, spec in challenges.EVENTS.items():
        if rng.random() < spec["chance"]:
            event = name
            break
    if event == "wandering_hermit":
        tier = 5
    pool = [c for c in challenges.CHALLENGES_BY_TIER[tier] if c in BUILT_CHALLENGES]
    if len(pool) > 1 and player.get("last_challenge") in pool:
        pool.remove(player["last_challenge"])
    challenge = rng.choice(pool)
    lo, hi = challenges.CONDITIONS_PER_TIER[tier]
    n = rng.randint(lo, hi)
    if event == "wandering_hermit":
        n = challenges.EVENTS["wandering_hermit"]["extra_conditions"]
    conds = rng.sample(APPLIES_TO[challenge], min(n, len(APPLIES_TO[challenge])))
    return {"tier": tier, "challenge": challenge, "conditions": conds, "event": event}


def timer(seconds, conditions):
    if "heavy_rain" in conditions:
        seconds *= challenges.CONDITIONS["heavy_rain"]["timer_multiplier"]
    return seconds


def make_tell(stance, deceptive, rng=random):
    if not deceptive:
        return rng.choice(TELLS[stance])
    fake = rng.choice([s for s in STANCES if s != stance])
    return f"{rng.choice(TELLS[fake])} {HIDDEN_SIGNS[stance]}"


def master_steps(tier, conditions, rng=random, steps=None):
    """Read the Master: list of (stance, tell, seconds)."""
    spec = challenges.READ_THE_MASTER
    n = steps or spec["steps"][tier]
    deceive = spec["deceptive_chance"][tier]
    if "drunken_master" in conditions:
        deceive = max(deceive, challenges.CONDITIONS["drunken_master"]["unreliable_tell_chance"])
    secs = timer(spec["seconds_per_step"][tier], conditions)
    out = []
    for _ in range(n):
        st = rng.choice(STANCES)
        out.append((st, make_tell(st, rng.random() < deceive, rng), secs))
    return out


def wave_seconds(tier, wave, conditions):
    return timer(max(WAVE_MIN_SECONDS, WAVE_FIRST_SECONDS[tier] * WAVE_SPEEDUP ** (wave - 1)), conditions)


class Waves:
    """Endless Waves scoring state."""

    def __init__(self, tier, conditions):
        spec = challenges.ENDLESS_WAVES
        self.spec, self.tier, self.conditions = spec, tier, conditions
        self.stamina = spec["start_stamina"]
        self.points = 0.0
        self.wave = 0
        self.target = spec["target_waves"][tier]
        self.over = False

    def answer(self, stance, pressed, elapsed, seconds):
        """pressed: 'strike'/'guard'/'break', 'technique', or None (timed out). Returns text."""
        self.wave += 1
        if pressed is None or elapsed > seconds + TIMER_GRACE_SECONDS:
            self.over = True
            return "⏳ Too slow! The disciple's blow lands."
        if pressed == "technique":
            cost = self.spec["technique_strike_cost"]
            if self.stamina < cost:
                self.over = True
                return "😮‍💨 Not enough stamina for a technique strike! You are knocked down."
            self.stamina -= cost
            self.points += self.spec["technique_strike_multiplier"]
            return "✨ Technique strike! The disciple goes flying (×2 points)."
        if pressed != counter_of(stance):
            self.over = True
            return f"❌ Wrong counter! {STANCE_LABEL[counter_of(stance)]} would have stopped that {STANCE_LABEL[stance]}."
        cost, pts = self.spec["counter_cost"], 1.0
        if pressed == "strike" and "old_injury" in self.conditions:
            cost *= challenges.CONDITIONS["old_injury"]["strike_stamina_multiplier"]
            pts *= challenges.CONDITIONS["old_injury"]["strike_points_multiplier"]
        self.stamina -= cost
        fast = elapsed <= seconds / 2
        if fast:
            self.stamina += self.spec["fast_counter_refund"]
        self.points += pts
        if self.stamina <= 0:
            self.over = True
        return "⚡ Fast counter! (+5 stamina)" if fast else "✅ Countered."

    @property
    def done(self):
        return self.over or self.points >= self.target

    @property
    def score(self):
        return min(1.0, self.points / self.target)


def qi_reward(player, techniques, score, conditions, event_mult=1.0, now=None):
    rate, _ = rules.qi_rate(player, now, techniques)
    qi = rate * training.TRAIN_REWARD_HOURS * score * (1 + challenges.CONDITION_EXP_BONUS * len(conditions)) * event_mult
    if score < challenges.LOW_SCORE_THRESHOLD:
        qi *= challenges.LOW_SCORE_EXP_RATE
    return qi


def cooldown_seconds(player, now=None):
    secs = training.TRAIN_COOLDOWN_MINUTES * 60
    if rules.active_blessed_land(player, now):
        secs *= training.BLESSED_LAND_COOLDOWN_MULTIPLIER
    return secs


def finish(conn, user_id, session, score, event_mult=1.0, rng=random, now=None):
    """Grant Qi, run breakthroughs, save, set cooldown. Returns (qi_gained, events, player)."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    techs = db.get_techniques(conn, user_id)
    qi = qi_reward(p, techs, score, session["conditions"], event_mult, now)
    p, events = rules.add_qi(p, qi, techs, rng, now)
    db.update_player(conn, user_id, qi=p["qi"], realm=p["realm"], layer=p["layer"],
                     breakthroughs=p["breakthroughs"], failed_breakthroughs=p["failed_breakthroughs"],
                     injured_until=p.get("injured_until"), last_challenge=session["challenge"])
    db.set_cooldown(conn, user_id, "train", cooldown_seconds(p, now), now)
    return qi, events, p
