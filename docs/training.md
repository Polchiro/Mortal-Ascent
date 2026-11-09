# Training — Internal Qi

Realm progress is measured in **Internal Qi** (内力).
Fill the Qi bar of your current layer to advance.

## Internal Qi Rate

Every player has one **Internal Qi Rate** (Qi per hour), shown on their profile:

> Internal Qi Rate: 1,280 Qi/hour (×1.85)

```
Final Qi Rate = Base Rate × (1 + Talent + Technique + Blessing) × Pill multiplier
```

- All % bonuses add together, then the pill multiplier applies on top
- Blessed Lands multiply the final rate (below)

### Base rate by realm

| Realm | Base rate (Qi/hour) |
|---|---|
| Mortal | 2.5 |
| Martial Apprentice | 5 |
| Martial Warrior | 10 |
| Martial Expert | 20 |
| Martial Master | 40 |
| Grand Martial Master | 80 |
| Martial Grandmaster | 160 |
| Martial King | 320 |
| Martial Emperor | 640 |
| Martial Ancestor | 1,280 |
| Martial Saint | 2,560 |

### Rate bonuses

**Talent**

| Talent | Bonus |
|---|---|
| Ordinary | +0% |
| Gifted | +10% |
| Genius | +20% |
| Prodigy | +35% |
| Heavenly | +50% |
| Saint | +75% |
| Divine | +100% |

**Technique:** best equipped technique's training bonus, +5% to +60% (see technique.md)

**Heavenly Blessing:** +10% to +150% (see economy.md)

## Ways to gain Internal Qi

### 1. /train — active training
- Plays a challenge from the pool (see challenges.md)
- Reward = **4 hours of your Final Qi Rate × challenge score**
- Challenge conditions add +15% each to that session
- Cooldown: 60 minutes

### 2. Passive Qi
- Qi gathers on its own at your Final Qi Rate, for as long as you are away, with **no limit**
- Nothing to collect: the bot adds it to your bar every minute (and before every command),
  so your profile and rank are always current
- **/internal qi** shows how fast it flows and when your bar fills

### 3. Blessed Lands (from /explore)

| Blessed Land | Qi Rate | Duration |
|---|---|---|
| 💧 Spirit Spring | ×2 | 20–30 min |
| 🌸 Lotus Grove | ×2 (also mastery EXP ×2) | 20–30 min |
| 🐉 Dragon Vein (ultra rare) | ×3 (also mastery EXP ×3) | 20–30 min |

- /train and /practice cooldowns are halved while the boost is active

## Pills

Pills will be crafted with /craft (alchemy, not built yet) — full rules in **alchemy.md**.
For now they come from chests, merchants and the Moon Pearl shop. Summary:

| Qi pill | Grade | Qi Rate | Duration |
|---|---|---|---|
| Ember Dantian Pill | Mortal | ×1.3 | 2 hours |
| Clear Meridian Pill | Yellow | ×1.5 | 2 hours |
| Jade Marrow Pill | Mystic | ×1.8 | 2 hours |
| Thousand Rivers Pill | Earth | ×2.2 | 2 hours |
| Heaven-Devouring Pill | Heaven | ×2.8 | 2 hours |

- Only one Qi pill active at a time; pill patterns (丹纹) change the effect ×0.85–×1.25
- A Qi pill below your realm's grade gives half its bonus
- Toxicity 4–5: pill effects ×0.5 · 6+: ×0.25 · drops by 1 every 8 hours

## Layers and Qi needed

Qi needed for one layer in the **Early phase**:

| Realm | Qi per layer |
|---|---|
| Mortal (3 layers, tutorial) | 8 |
| Martial Apprentice | 16 |
| Martial Warrior | 64 |
| Martial Expert | 260 |
| Martial Master | 900 |
| Grand Martial Master | 2,850 |
| Martial Grandmaster | 9,300 |
| Martial King | 29,000 |
| Martial Emperor | 89,000 |
| Martial Ancestor | 265,000 |
| Martial Saint | 790,000 |

Phase multipliers on Qi needed: Early ×1, Middle ×1.2, Late ×1.5, Peak ×2.

## Breakthroughs

| Step | How |
|---|---|
| Layer → layer (same phase) | Automatic when the bar fills |
| Phase → phase (3rd→4th, 6th→7th, 9th→10th) | Chance by realm, see below |
| Realm → realm (Peak → next realm) | Chance by the realm you enter, see below |

Gates get much harder the higher you climb (numbers live in `training.py`):

| Realm | Phase gates inside it | Realm gate into it |
|---|---|---|
| Martial Apprentice | 80% | 100% (from Mortal) |
| Martial Warrior | 70% | 50% |
| Martial Expert | 60% | 35% |
| Martial Master | 50% | 25% |
| Grand Martial Master | 42% | 18% |
| Martial Grandmaster | 35% | 12% |
| Martial King | 28% | 8% |
| Martial Emperor | 22% | 5% |
| Martial Ancestor | 17% | 3% |
| Martial Saint | 12% | 1.5% |

Breakthrough pills and artifacts (e.g. Heaven's Favor) add to realm gates only, up to 95% at most.

- **No Qi is ever lost at a gate.** When the bar is full at a bottleneck or realm gate it stays
  exactly full, and every extra point of Qi (passive, /train, pills, anything) waits behind the
  gate. Profile and /internal qi show it: "Qi bar full · +180 Qi waiting behind the bottleneck"
- After a **successful** breakthrough all the waiting Qi flows into the new layer. It can fill
  several layers and stops again at the next gate, where any new extra waits again
- When your bar becomes full at a gate, the bot mentions you once in the channel you last used it in
  ("your Qi is full: use /breakthrough!"). Turn this off with **/settings qi_pings:off**
- Failed phase breakthrough: lose 20% of the bar; the Qi waiting behind the gate is kept
- Failed realm breakthrough: lose 20% of the bar + 6-hour injury (no exploring or fighting); the Qi
  waiting behind the gate is kept
- Breakthrough Pills: +5% / +7% / +10% / +12% / +15% success (Mortal → Heaven, see alchemy.md)

### Realm requirements (besides Qi)

| To reach | Also needs |
|---|---|
| Martial Master | One technique at Entering the Hall |
| Martial King | A Mystic technique at Pure Flame + defeat a Beast King of your realm |
| Martial Saint | An Earth technique at Divine Transformation + defeat a Martial Ancestor Beast King |

## Pacing (Martial Saint target)

Assumes Genius talent, a decent technique, 8 /train sessions a day for active players.

| Player | Time to Martial Saint |
|---|---|
| Active + passive Qi + 3 pills a day | ~3 months |
| Active + passive Qi, no pills | ~5.5–6 months |
| Casual (2 sessions a day + passive) | ~10–11 months |

Time per realm grows as you climb (active + pills): the first five realms take about a
week in total, Martial King about 9 days, Martial Saint about a month.
