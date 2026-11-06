"""
/train — game logic for one training session (docs/training.md, docs/challenges.md).

A session rolls a challenge, conditions and maybe a surprise event, the
player plays it with buttons (bot/views.py), and the score becomes Internal Qi:

    Qi = Final Qi Rate × 4 hours × score × (1 + 15% per condition) × event
    (score below 50% gives only 10%)

Built so far: Read the Master and Endless Waves (tier 1) plus Ambush and
Find the Weakness (tier 2). Tiers 3-5 use these four, with their harder
numbers, until Rhythm of the Blade and Sword Formation are built.
"""
import random
import time

import challenges
import technique
import training

from . import db, loot, mastery, materials
from . import player as rules

STANCES = ["strike", "guard", "break"]
STANCE_LABEL = {"strike": "Strike", "guard": "Guard", "break": "Break"}
STANCE_EMOJI = {"strike": "⚔️", "guard": "🛡️", "break": "💥"}
BUILT_CHALLENGES = ["read_the_master", "endless_waves", "ambush", "find_the_weakness"]
CHALLENGE_NAMES = {"read_the_master": "🥋 Read the Master", "endless_waves": "🌊 Endless Waves",
                   "ambush": "👥 Ambush", "find_the_weakness": "🔍 Find the Weakness"}
CONDITION_NAMES = {"heavy_rain": "🌧️ Heavy Rain", "old_injury": "🩹 Old Injury",
                   "drunken_master": "🍶 Drunken Master", "night_training": "🌙 Night Training"}
CONDITION_TEXT = {"heavy_rain": "all timers 25% shorter",
                  "old_injury": "Strike costs double stamina and gives half points",
                  "drunken_master": "half of the tells are unreliable, so look for the hidden sign",
                  "night_training": "the move stays hidden until the last 40% of the timer"}
# conditions that change each challenge (challenges.md: rolled only when they affect it)
APPLIES_TO = {"read_the_master": ["heavy_rain", "drunken_master", "night_training"],
              "endless_waves": ["heavy_rain", "old_injury", "night_training"],
              "ambush": ["heavy_rain", "night_training"],
              "find_the_weakness": []}

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


def roll_session(player, rng=random, tech=None):
    """tech: a techniques row for /practice (tier = its mastery stage + 1), or None for /train (tier by realm)."""
    tier = rules.stage_of(tech) + 1 if tech else challenges.REALM_TIER[player["realm"]]
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
    return {"tier": tier, "challenge": challenge, "conditions": conds, "event": event,
            "mode": "practice" if tech else "train", "technique_id": tech["id"] if tech else None,
            "technique_name": tech["name"] if tech else None}


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


class Ambush:
    """Two opponents attack at once; one counter. Your counter stops every opponent whose move it
    beats (SHOAIB's rule, 2026-11-04), so when both use the same move one counter stops both."""

    def __init__(self, tier, rng=random):
        spec = challenges.AMBUSH
        self.spec, self.rng = spec, rng
        self.hp = spec["player_hp"]
        self.target = spec["target_rounds"].get(tier, spec["target_rounds"][min(spec["target_rounds"])])
        self.survived = 0
        self.round = 0
        self.new_round()

    def new_round(self):
        self.round += 1
        self.moves = [self.rng.choice(STANCES), self.rng.choice(STANCES)]
        self.strong = self.rng.randrange(2)

    def answer(self, pressed, elapsed, seconds):
        if pressed is None or elapsed > seconds + TIMER_GRACE_SECONDS:
            pressed = None
        hits, stopped = 0, 0
        for i, mv in enumerate(self.moves):
            if pressed is not None and counter_of(mv) == pressed:
                stopped += 1
            else:
                hits += self.spec["strong_opponent_damage"] if i == self.strong else self.spec["normal_opponent_damage"]
        self.hp = max(0, self.hp - hits)
        if self.hp > 0:
            self.survived += 1
        if pressed is None:
            text = f"⏳ Too slow! Both hit you (−{hits} HP)."
        elif stopped == 2:
            text = "✨ One counter stops them both!"
        elif stopped == 1:
            text = f"✅ You stop one; the other hits (−{hits} HP)."
        else:
            text = f"❌ Your counter stops neither (−{hits} HP)."
        if not self.done:
            self.new_round()
        return text

    @property
    def done(self):
        return self.hp <= 0 or self.survived >= self.target

    @property
    def score(self):
        return min(1.0, self.survived / self.target)


def weakness_feedback(secret, guess):
    """(right move right place, right move wrong place), Mastermind style."""
    exact = sum(a == b for a, b in zip(secret, guess))
    common = sum(min(secret.count(s), guess.count(s)) for s in STANCES)
    return exact, common - exact


class Weakness:
    """Find the Weakness: guess the master's hidden sequence of moves."""

    def __init__(self, tier, rng=random):
        spec = challenges.FIND_THE_WEAKNESS
        tier = tier if tier in spec["sequence_length"] else min(spec["sequence_length"])
        self.length = spec["sequence_length"][tier]
        self.tries = spec["tries_allowed"][tier]
        self.secret = [rng.choice(STANCES) for _ in range(self.length)]
        self.history = []
        self.solved = False

    def guess(self, moves):
        fb = weakness_feedback(self.secret, moves)
        self.history.append((list(moves), fb))
        self.solved = fb[0] == self.length
        return fb

    @property
    def done(self):
        return self.solved or len(self.history) >= self.tries

    @property
    def score(self):
        """DEFAULT: solved in 1-2 tries = 100%, falling to 50% on the last try; unsolved = 0."""
        if not self.solved:
            return 0.0
        k = len(self.history)
        if k <= 2:
            return 1.0
        return 1 - 0.5 * (k - 2) / max(1, self.tries - 2)


def qi_reward(player, techniques, score, conditions, event_mult=1.0, now=None):
    rate, _ = rules.qi_rate(player, now, techniques)
    qi = rate * training.TRAIN_REWARD_HOURS * score * (1 + challenges.CONDITION_EXP_BONUS * len(conditions)) * event_mult
    if score < challenges.LOW_SCORE_THRESHOLD:
        qi *= challenges.LOW_SCORE_EXP_RATE
    return qi


def cooldown_seconds(player, now=None, mode="train"):
    minutes = training.TRAIN_COOLDOWN_MINUTES if mode == "train" else technique.PRACTICE_COOLDOWN_MINUTES
    secs = minutes * 60
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
    db.update_player(conn, user_id, **rules.progress_fields(p), last_challenge=session["challenge"])
    dew = materials.roll_training_dew(rng)
    if dew:
        loot.store(conn, user_id, dew)
        events = list(events) + ["✨ Spirit dew gathers on your skin: " + ", ".join(materials.lines(dew))]
    db.set_cooldown(conn, user_id, "train", cooldown_seconds(p, now), now)
    return qi, events, p


def practice_exp(score, conditions, event_mult=1.0, daily=1.0):
    exp = technique.PRACTICE_BASE_EXP * score * (1 + challenges.CONDITION_EXP_BONUS * len(conditions)) * event_mult * daily
    if score < challenges.LOW_SCORE_THRESHOLD:
        exp *= challenges.LOW_SCORE_EXP_RATE
    return exp


def finish_practice(conn, user_id, session, score, event_mult=1.0, now=None, rng=random):
    """Grant mastery EXP for /practice. Returns (exp_gained, daily_rate, note, technique)."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    tech = db.get_technique(conn, user_id, session["technique_id"])
    daily = rules.daily_rate(technique.PRACTICE_DAILY_RATES, db.daily_count(conn, user_id, "practice", now))
    gained, note = mastery.gain(conn, p, tech, practice_exp(score, session["conditions"], event_mult, daily))
    db.bump_daily(conn, user_id, "practice", now)
    db.update_player(conn, user_id, last_challenge=session["challenge"])
    db.set_cooldown(conn, user_id, "practice", cooldown_seconds(p, now, "practice"), now)
    ink = materials.roll_practice_ink(rng)
    if ink:
        loot.store(conn, user_id, ink)
        found = "✨ Your notes leave a drop of insight: " + ", ".join(materials.lines(ink))
        note = f"{note}\n{found}" if note else found
    return gained, daily, note, tech
