# Training Challenges

One shared challenge system, used by two commands:
- **/train** — gives realm training EXP (difficulty set by realm)
- **/practice <technique>** — gives mastery EXP (difficulty set by mastery stage)

Every session rolls a random challenge, may roll random conditions,
and has a small chance of a surprise event. Nothing is the same twice.

## Difficulty tiers

| Tier | /practice (mastery stage) | /train (realm) |
|---|---|---|
| 1 | Glimpsing the Gate | Mortal, Martial Apprentice, Martial Warrior |
| 2 | Entering the Hall | Martial Expert, Martial Master |
| 3 | Pure Flame | Grand Martial Master, Martial Grandmaster |
| 4 | Divine Transformation | Martial King, Martial Emperor |
| 5 | Return to Simplicity | Martial Ancestor, Martial Saint |

| Tier | Challenges available | Conditions per session |
|---|---|---|
| 1 | Read the Master, Endless Waves | None |
| 2 | + Ambush, Find the Weakness | 0–1 |
| 3 | All 6 | 1 |
| 4 | All 6, harder versions | 1–2 |
| 5 | All 6, hardest versions | 2 |

- The same challenge never appears twice in a row for a player

## The 6 challenges

Basic counters used throughout: **Guard beats Strike, Break beats Guard, Strike beats Break**.

### 🥋 Read the Master
The master shows **descriptive tells** instead of icons
(e.g. *"He shifts his weight onto his back foot..."* = Guard).
Player presses the counter before time runs out.

| Tier | Steps | Time per step | Deceptive tells |
|---|---|---|---|
| 1 | 4 | 8.0s | 0% |
| 2 | 5 | 7.0s | 0% |
| 3 | 6 | 6.0s | 10% |
| 4 | 7 | 5.0s | 20% |
| 5 | 8 | 4.0s | 30% |

(Raised from 3.0s → 1.5s: players could not react in time. Ambush uses the same timer.)

- Large pool of tells per stance, picked at random
- Deceptive tell: describes one move but contains a subtle sign revealing the real one

### 🎵 Rhythm of the Blade
The master repeats a **hidden pattern** of stances, random each session.

| Tier | Pattern length | Total steps |
|---|---|---|
| 3 | 3 | 10 |
| 4 | 4 | 11 |
| 5 | 5 | 12 |

- **Foresight:** press the counter *before* the stance appears = ×2 points
- Wrong foresight guess = step fails

### 🌊 Endless Waves
Disciples attack in waves, each wave faster.
- First wave: 7.0s / 6.5s / 6.0s / 5.0s / 4.5s by tier, then 8% faster each wave (never under 2.5s)
- Stamina: 100. Each counter costs 10. A fast counter refunds 5.
- **Technique strike:** costs 30 stamina, gives ×2 points for that step
- Ends when stamina runs out or a counter is missed
- Score = waves survived (target waves: 5 / 6 / 7 / 8 / 10 by tier)

### 👥 Ambush
Two opponents show stances at the same time. Player counters **one**;
the other one hits.
- Player has 3 HP in the drill
- One opponent is marked as stronger (hits for 2 HP)
- Score = rounds survived (target rounds: — / 5 / 6 / 7 / 8 by tier)

### 🔍 Find the Weakness
The master has a hidden sequence of moves (his weakness).
Player guesses; after each guess:
✅ = right move, right place · 🔶 = right move, wrong place

| Tier | Sequence length | Tries allowed |
|---|---|---|
| 2 | 3 | 8 |
| 3 | 4 | 8 |
| 4 | 4 | 7 |
| 5 | 5 | 6 |

- Score = based on tries used (fewer tries, higher score)

### 🧩 Sword Formation
Build a sequence of moves that satisfies all of the master's rules.
Example rules: *"Never two Guards in a row"*, *"Break must come right after Strike"*,
*"Exactly 2 Strikes"*, *"Start with Guard"*.

| Tier | Sequence length | Rules | Time limit |
|---|---|---|---|
| 3 | 5 | 3 | 60s |
| 4 | 6 | 4 | 50s |
| 5 | 7 | 5 | 40s |

- Rules are generated randomly; the bot checks a solution exists before showing it
- Score = solved or not, with a bonus for speed

## Conditions

Rolled only when they affect the chosen challenge. Each gives **+15% EXP**.

| Condition | Effect |
|---|---|
| 🌧️ Heavy Rain | All timers 25% shorter |
| 🩹 Old Injury | Strike costs double stamina / gives half points |
| 🍶 Drunken Master | Half of the tells are unreliable — rely on patterns |
| 🌙 Night Training | Stance is hidden until the last 40% of the timer |

## Surprise events

| Event | Chance | What happens |
|---|---|---|
| 🧙 Wandering Hermit | 1% | Hardest version of a challenge + 2 conditions, ×5 EXP |
| 💡 Epiphany | 2% | After the challenge: +50% EXP for this session |
| ⚔️ Rival Disciple | 2% | A rival interrupts for a short fight; win = ×2 EXP |

## EXP

```
Session EXP = Base EXP × Score × (1 + condition bonuses) × event multiplier × daily rate
```

- Score: 0–100% from the challenge result
- Score below 50% = only 10% of EXP
- Base EXP: /practice = 40 mastery EXP; /train = set in training.md

## Anti-AFK

- Button positions shuffle every round
- Challenges, tells and patterns are random every session, so recordings don't help
- Daily diminishing returns (see technique.md and training.md)
