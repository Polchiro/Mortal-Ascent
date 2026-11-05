# Techniques

Two types only:
- **Attack technique** — used to deal damage
- **Defense technique** — used to block incoming damage

## Grades

| Grade | Can learn from realm |
|---|---|
| Mortal | Mortal |
| Yellow | Martial Apprentice |
| Mystic | Martial Expert |
| Earth | Grand Martial Master |
| Heaven | Martial King |

## Mastery stages

| Stage | Name | Effect multiplier |
|---|---|---|
| 1 | Glimpsing the Gate | ×1.00 |
| 2 | Entering the Hall | ×1.10 |
| 3 | Pure Flame | ×1.20 |
| 4 | Divine Transformation | ×1.35 |
| 5 | Return to Simplicity | ×1.50 |

Mastery EXP comes from /practice, /spar and using the technique in fights.

Mastery EXP needed to reach each stage (Mortal grade):

| To stage | EXP |
|---|---|
| 2 | 500 |
| 3 | 2,000 |
| 4 | 6,000 |
| 5 | 15,000 |

Higher grades need more EXP: Yellow ×2, Mystic ×3, Earth ×5, Heaven ×8.

## Training speed bonus

Better techniques make realm training faster.
Bonus to training EXP (at stage 1, before mastery multiplier):

| Grade | Training EXP bonus |
|---|---|
| Mortal | +5% |
| Yellow | +10% |
| Mystic | +15% |
| Earth | +25% |
| Heaven | +40% |

- Only the **best** equipped technique counts (bonuses do not stack)
- Mastery multiplier applies (e.g. Heaven at Return to Simplicity = +40% × 1.5 = +60%)

## Effects on stats (at stage 1, before mastery multiplier)

### Attack techniques

| Grade | Skill damage multiplier (when used) | Passive Attack % (while equipped) |
|---|---|---|
| Mortal | ×1.20 | +2% |
| Yellow | ×1.35 | +4% |
| Mystic | ×1.50 | +6% |
| Earth | ×1.70 | +9% |
| Heaven | ×2.00 | +12% |

### Defense techniques

| Grade | Damage blocked (when used) | Passive Defense % (while equipped) |
|---|---|---|
| Mortal | 20% | +2% |
| Yellow | 25% | +4% |
| Mystic | 30% | +6% |
| Earth | 40% | +9% |
| Heaven | 50% | +12% |

- Mastery multiplier applies to all four values
  (e.g. Heaven attack at Return to Simplicity = ×2.00 × 1.50 = ×3.00 damage)
- Damage blocked can never go above 80%
- Passive % buffs add into the buff totals in stats.md
- The 30% one-hit cap in stats.md still applies to every technique

## Technique slots

| Realm | Slots |
|---|---|
| Mortal | 2: 1 attack + 1 defense |
| Martial Warrior | 3: adds 1 flex slot (attack or defense) |

- Flex slot lets players build aggressive (2 attack + 1 defense) or tank (1 attack + 2 defense)
- Techniques can only be swapped **outside** of fights

## Schools

All techniques are unarmed. Weapons only give stat buffs (see equipment.md later).

| School | Style |
|---|---|
| Fist | Direct power |
| Palm | Flowing, controlling |
| Finger | Precise, piercing |
| Leg | Fast kicks, sweeps |
| Body | Defense and endurance |

## Technique effects

Each technique has one special effect. Grade and mastery multipliers still apply
to damage and block; the 30% cap applies to **total damage in one turn**.

### Attack effects
| Effect | What it does |
|---|---|
| Combo | Hits several times at reduced damage per hit |
| Pierce | Ignores part of the defender's Defense |
| Stagger | If it lands, the defender's next block is weaker |
| Heavy | Extra damage, but rests 1 turn longer after use (see Cooldowns) |

### Defense effects
| Effect | What it does |
|---|---|
| Counter | Reflects part of the blocked damage back |
| Recover | Heals a % of max HP when it blocks |
| Unbreakable | Break moves deal only half damage against it |
| Evade | Chance to take no damage at all |

### Cooldowns in fights

Techniques can't be spammed. After a technique is used in any fight (spar,
trials, explore, hunts, PvP later) it must rest for a number of turns before it
can be used again. Basic Strike, Guard and Break are always available.

| Grade | Cooldown after use |
|---|---|
| Mortal | 1 turn |
| Yellow | 1 turn |
| Mystic | 2 turns |
| Earth | 2 turns |
| Heaven | 3 turns |

- Heavy techniques rest 1 extra turn
- In /spar the technique button is greyed out and shows the turns left
- In auto fights (explore, hunts) the fighter uses basic strikes in between;
  in hunts, fighters keep their guard ready for the beast's charged attack
- No Qi cost: Qi is cultivation progress, not a fight resource

## Technique list

Names grow grander with grade: Mortal = plain actions, Yellow = animals,
Mystic = forces of nature, Earth = landscapes and legends, Heaven = cosmic.

### Mortal grade
| Technique | Type | School | Effect |
|---|---|---|---|
| Iron Fist | Attack | Fist | — |
| Twin Palm Strike | Attack | Palm | Combo: 2 hits × 60% |
| Crescent Sweep | Attack | Leg | Stagger: next block −15% |
| Horse Stance Guard | Defense | Body | — |
| Parrying Arm | Defense | Body | Counter 10% |
| Calm Breath Stance | Defense | Body | Recover 3% |

### Yellow grade
| Technique | Type | School | Effect |
|---|---|---|---|
| Fierce Tiger Claw | Attack | Fist | Stagger: next block −25% |
| Swift Swallow Kick | Attack | Leg | Pierce 15% |
| Raging Bull Fist | Attack | Fist | Heavy ×1.2 |
| Iron Cloth Body | Defense | Body | Unbreakable |
| Flowing Stream Palm | Defense | Palm | Recover 5% |
| Crane Wing Deflection | Defense | Palm | Counter 15% |

### Mystic grade
| Technique | Type | School | Effect |
|---|---|---|---|
| Rolling Thunder Palm | Attack | Palm | Stagger: next block −50% |
| Viper Fang Finger | Attack | Finger | Pierce 25% |
| Autumn Wind Kick | Attack | Leg | Combo: 3 hits × 40% |
| Moon Mirror Palm | Defense | Palm | Counter 25% |
| Drifting Mist Steps | Defense | Body | Evade 25% |
| Rooted Mountain Stance | Defense | Body | Unbreakable |

### Earth grade
| Technique | Type | School | Effect |
|---|---|---|---|
| Mountain-Shattering Fist | Attack | Fist | Heavy ×1.3 |
| Thousand Shadow Palm | Attack | Palm | Combo: 3 hits × 45% |
| River-Splitting Finger | Attack | Finger | Pierce 30% |
| Golden Bell Cover | Defense | Body | Unbreakable |
| Ancient Turtle Shell Art | Defense | Body | Recover 8% |
| Thousand Hands Deflection | Defense | Palm | Counter 30% |

### Heaven grade
| Technique | Type | School | Effect |
|---|---|---|---|
| Heaven-Rending Palm | Attack | Palm | Pierce 40% |
| Nine Dragons Ascending Fist | Attack | Fist | Stagger: opponent can't Guard next turn |
| Meteor-Falling Kick | Attack | Leg | Heavy ×1.5 |
| Void Mirror Stance | Defense | Palm | Counter 40% |
| Immortal Lotus Body | Defense | Body | Recover 12% |
| Cloud-Walking Shadow | Defense | Body | Evade 40% |

## Training mastery

Mastery is trained separately from realm training (/train).
Three ways, all requiring the player's attention (no AFK).

### 1. /practice <technique> — Training challenges

- Each session rolls a random challenge from the shared pool in **challenges.md**
- Difficulty tier = the technique's mastery stage
- Base EXP: 40 mastery EXP × score
- Cooldown: 30 minutes

### 2. /spar — training fight against a master NPC

- Short fight using the combat moves (Strike / Guard / Break)
- Master has patterns that hint at their next move
- Mastery EXP only for using the technique **at the right moment**
  (e.g. attack technique right after the master's Strike is blocked)
- +30 EXP per well-timed technique use, +100 EXP for winning
- Master is the same realm and layer as the player
- Cooldown: 2 hours

### 3. Mastery trial — stage breakthrough

- When the EXP bar is full, the player must pass a trial to reach the next stage
- Trial = /spar against a stronger master

| To stage | Master strength |
|---|---|
| Entering the Hall | ×1.2 |
| Pure Flame | ×1.4 |
| Divine Transformation | ×1.7 |
| Return to Simplicity | ×2.0 |

- Fail: no EXP lost, 24-hour cooldown before retrying

### Real fights

- +20 mastery EXP each time the technique is used against beasts or in PvP

### Anti-AFK rules

- Button positions shuffle every round (stops auto-clickers)
- Daily diminishing returns:
  - /practice: first 5 sessions full EXP, next 5 at 50%, then 10%
  - /spar: first 3 sessions full EXP, then 50%

## How players get techniques

1. **Start:** Iron Fist (attack) and Horse Stance Guard (defense)
2. **Beasts:** drops when defeating beasts in the wild (stronger beasts, higher grades)
3. **Quests:** rewards from quests
4. **Later:** sects, shops (not yet)
