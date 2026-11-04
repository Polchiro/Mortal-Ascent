# Training — Internal Qi

Realm progress is measured in **Internal Qi** (内力).
Fill the Qi bar of your current layer to advance.

## Internal Qi Rate

Every player has one **Internal Qi Rate** (Qi per hour), shown on their profile:

> Internal Qi Rate: 1,280 Qi/hour (×1.85)

```
Final Qi Rate = Base Rate × (1 + Talent + Technique + Patron) × Pill multiplier
```

- All % bonuses add together, then the pill multiplier applies on top
- Seclusion and Blessed Lands multiply the final rate (below)

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

**Patron (premium):** +15%

## Ways to gain Internal Qi

### 1. /train — active training
- Plays a challenge from the pool (see challenges.md)
- Reward = **4 hours of your Final Qi Rate × challenge score**
- Challenge conditions add +15% each to that session
- Cooldown: 60 minutes

### 2. Passive Qi — /meditate
- Qi gathers automatically at your Final Qi Rate
- Stores up to **12 hours**, then stops until collected
- **/meditate** collects the stored Qi (no cooldown)

### 3. Closed-Door Seclusion (闭关) — /seclusion
- Enter seclusion for 8–24 hours: **Qi Rate ×2** during that time
- Cannot explore, fight or trade while secluded
- Leaving early cancels the ×2 bonus for the time spent

### 4. Blessed Lands (from /explore)

| Blessed Land | Qi Rate | Duration |
|---|---|---|
| 💧 Spirit Spring | ×2 | 20–30 min |
| 🌸 Lotus Grove | ×2 (also mastery EXP ×2) | 20–30 min |
| 🐉 Dragon Vein (ultra rare) | ×3 (also mastery EXP ×3) | 20–30 min |

- /train and /practice cooldowns are halved while the boost is active

## Pills

Only one Qi pill can be active at a time (pills do not stack).

| Pill grade | Qi Rate multiplier | Duration |
|---|---|---|
| Mortal | ×1.2 | 4 hours |
| Yellow | ×1.4 | 4 hours |
| Mystic | ×1.7 | 4 hours |
| Earth | ×2.0 | 4 hours |
| Heaven | ×2.5 | 4 hours |

### Pill toxicity
- Each pill adds 1 toxicity
- Toxicity 4–5: pill effects ×0.5
- Toxicity 6+: pill effects ×0.25
- Toxicity drops by 1 every 24 hours

## Layers and Qi needed

Qi needed for one layer in the **Early phase**:

| Realm | Qi per layer |
|---|---|
| Mortal (3 layers, tutorial) | 10 |
| Martial Apprentice | 20 |
| Martial Warrior | 80 |
| Martial Expert | 320 |
| Martial Master | 1,120 |
| Grand Martial Master | 3,520 |
| Martial Grandmaster | 11,520 |
| Martial King | 35,840 |
| Martial Emperor | 110,080 |
| Martial Ancestor | 327,680 |
| Martial Saint | 972,800 |

Phase multipliers on Qi needed: Early ×1, Middle ×1.2, Late ×1.5, Peak ×2.

## Breakthroughs

| Step | How |
|---|---|
| Layer → layer (same phase) | Automatic when the bar fills |
| Phase → phase (3rd→4th, 6th→7th, 9th→10th) | 90% success |
| Realm → realm (Peak → next realm) | 70% base success |

- Failed realm breakthrough: lose 20% of current Qi + 6-hour injury (no exploring or fighting)
- Breakthrough Pills: +10% / +20% / +30% / +40% success (by pill grade)

### Realm requirements (besides Qi)

| To reach | Also needs |
|---|---|
| Martial Master | One technique at Entering the Hall |
| Martial King | A Mystic technique at Pure Flame + defeat a Beast King of your realm |
| Martial Saint | An Earth technique at Divine Transformation + defeat a Martial Ancestor Beast King |

## Pacing (Martial Saint target)

| Player | Time |
|---|---|
| Active, /train only | ~10.5 months |
| Active + passive Qi | ~7 months |
| Active + passive + pills | ~5.5 months |
| Casual (2 sessions/day + passive) | ~13 months |
