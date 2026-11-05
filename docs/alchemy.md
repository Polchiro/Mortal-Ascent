# Alchemy — Herbs, /gather, /craft and Pills

The alchemy loop: **gather herbs → craft pills in a minigame → raise your
alchemist rank → train faster.**

---

## 1. Herbs

### Herb tier by realm

Players find herbs of their own tier. 15% of gathers give a herb one tier lower.

| Herb tier | Found at realms |
|---|---|
| 凡 Mortal | Mortal |
| 黄 Yellow | Martial Apprentice, Martial Warrior |
| 玄 Mystic | Martial Expert, Martial Master |
| 地 Earth | Grand Martial Master, Martial Grandmaster |
| 天 Heaven | Martial King and above |

### Herb types

| Type | Used for | Gather chance |
|---|---|---|
| 🌀 Qi | Qi pills, Qi Burst pills | 30% |
| ❤️ Healing | Mending pills | 20% |
| 💧 Purity | Every recipe, Cleansing pills | 35% |
| 🏔️ Breakthrough | Breakthrough pills | 15% |

### All herbs

Each tier has 4 real herbs and 2 poisonous decoys. A decoy looks almost
like a real herb with **one detail wrong** — players must read carefully.

**凡 Mortal**
| Herb | Type | Description |
|---|---|---|
| Spirit Grass | 🌀 Qi | Thin green blades that sway with no wind |
| Red Berry | ❤️ Healing | Small red berries with a sweet smell |
| Dew Leaf | 💧 Purity | Broad leaf always holding a drop of dew |
| Iron Root | 🏔️ Breakthrough | Dark root, heavy as metal |
| ☠️ Ghost Grass | Decoy | Like Spirit Grass, but the blades are grey at the tips |
| ☠️ Bitter Nettle | Decoy | Red berries hidden under stinging leaves |

**黄 Yellow**
| Herb | Type | Description |
|---|---|---|
| Sun Ginseng | 🌀 Qi | Golden root, warm to the touch |
| Blood Flower | ❤️ Healing | Deep red petals with dark veins |
| Silver Moss | 💧 Purity | Moss that glows faintly on north-facing stones |
| Stone Root | 🏔️ Breakthrough | Grey root that grows through solid rock |
| ☠️ Fool's Ginseng | Decoy | Golden root, but cold to the touch |
| ☠️ Snake Moss | Decoy | Glowing moss on south-facing stones |

**玄 Mystic**
| Herb | Type | Description |
|---|---|---|
| Moon Mushroom | 🌀 Qi | Pale blue cap that opens only at night |
| Heart Lotus | ❤️ Healing | Pink lotus with a heart-shaped center |
| Jade Lily | 💧 Purity | Green-white lily, cool as jade |
| Thunder Root | 🏔️ Breakthrough | Black root found where lightning struck |
| ☠️ Shadow Mushroom | Decoy | Pale blue cap, but open in daylight |
| ☠️ Weeping Lily | Decoy | Green-white lily dripping dark sap |

**地 Earth**
| Herb | Type | Description |
|---|---|---|
| Golden Ginseng | 🌀 Qi | Root shaped like a sitting person, golden glow |
| Phoenix Flower | ❤️ Healing | Orange petals warm like embers |
| Snow Lily | 💧 Purity | White lily that blooms only in snow |
| Mountain Root | 🏔️ Breakthrough | Massive root deep beneath mountain cliffs |
| ☠️ Grave Ginseng | Decoy | Person-shaped root, but grows near bones |
| ☠️ Fire Thorn | Decoy | Orange petals hiding burning thorns |

**天 Heaven**
| Herb | Type | Description |
|---|---|---|
| Heaven Lotus | 🌀 Qi | Nine-leaf lotus floating above the water |
| Immortal Peach | ❤️ Healing | Glowing peach that smells of spring |
| Star Dew | 💧 Purity | Dewdrops that shine like stars, even by day |
| Chaos Root | 🏔️ Breakthrough | Root that seems to shift colours as you look |
| ☠️ Demon Lotus | Decoy | Nine-leaf lotus, but blood-red underneath |
| ☠️ Void Fruit | Decoy | Glowing fruit that casts no shadow |

### Herb age

Every herb has an age. Older herbs are rarer and make crafting easier.

| Age | Chance | About how often | Craft bonus | Max pill patterns |
|---|---|---|---|---|
| 🌱 10-year | 78% | Most herbs | — | 5 |
| 🌿 50-year | 18% | 1 in 5–6 | +5% score | 6 |
| 🍃 100-year | 3.6% | 1 in ~28 | +10% score | 7 |
| 🌳 500-year | 0.38% | 1 in ~260 | +15% score, 1 mistake forgiven | 8 |
| 🏵️ 1000-year | 0.02% | 1 in 5,000 | +25% score, explosion only below 30% | 9 |

- A recipe uses the **average age** of its herbs (rounded down to the age tier)
- Herbs of the same type and age stack in the bag

---

## 2. /gather — collecting herbs

**No limit.** Gathering is the main grind: players can gather as long as they like.

### How it works
1. `/gather` opens **one gathering message** that updates in place
2. The bot names the herb you are looking for and its description:
   > 🌿 *You search the misty slope for **Silver Moss**. It glows faintly and grows only on north-facing stones...*
3. **4 plant buttons** appear — one real herb, the rest decoys and other plants
4. Pick before time runs out:
   - ✅ **Correct:** you get the herb (age is rolled)
   - ☠️ **Decoy:** poisoned — lose 5% HP (never below 1), nothing gathered
   - ⏳ **Too slow:** nothing gathered
5. Press **🌿 Gather Again** to continue in the same message

| Herb tier | Time to pick |
|---|---|
| Mortal | 10s |
| Yellow | 9s |
| Mystic | 8s |
| Earth | 7s |
| Heaven | 6s |

At higher tiers, descriptions are subtler and decoys are closer to the real herb.

### Old herbs fight back
When the roll gives a **100-year or older** herb, the pick gets harder:
> ✨ *A **500-year Moon Mushroom!** It senses you and begins to sink into the earth...*

- **6 choices** instead of 4
- **3 seconds less** to choose (minimum 4s)
- Fail and the herb **escapes**

### Herbal Insight streak
Each correct pick in a row builds your streak. A wrong pick or timeout resets it.

| Streak | Chance of 50-year and older herbs |
|---|---|
| 0–9 | ×1 |
| 10–24 | ×1.5 |
| 25–49 | ×2 |
| 50+ | ×3 |

With a max streak, a 1000-year herb takes about 4–5 hours of focused gathering
instead of ~14.

### Anti-macro
- Button positions and texts **shuffle every gather**
- The right answer is in the **description**, which changes every time
- **Wandering Spirit check** every 15–25 gathers: a simple question
  (*"Press the button showing the moon"*). Fail 3 in a row → gathering paused for 1 hour
- **One gather at a time** — no parallel sessions
- **Flag for review** (no automatic ban): average reaction under 0.3s over 50
  gathers, or 12+ hours of gathering without a break
- The NPC merchant **does not buy herbs**, so unlimited gathering can't print Lotus Coins.
  Herbs are sold to other players on the market (5% tax).

### Other herb sources
- 🌿 Herb Patch in /explore: 1–3 herbs of your tier, ages rolled normally
- Chests: occasional herbs

---

## 3. Beast Cores

Needed for Breakthrough pills. They drop only from fights.

| Beast | Core | Drop chance |
|---|---|---|
| 🐾 Normal | Normal Beast Core | 5% |
| ⚔️ Elite | Elite Beast Core | 15% |
| 👑 Beast King | Beast King Core | 50% |

A core has the **tier of the beast's realm** (same tiers as herbs). A recipe needs
a core of the pill's grade.

---

## 4. Pills and recipes

All herbs in a recipe must be of the pill's grade.

### 🌀 Qi pills — Qi Rate boost for 2 hours

| Grade | Pill | Recipe | Min herb age | Rank | Use from | Qi Rate |
|---|---|---|---|---|---|---|
| 凡 Mortal | Ember Dantian Pill | 2 Spirit Grass + 1 Dew Leaf | Any | 1st | Mortal | ×1.3 |
| 黄 Yellow | Clear Meridian Pill | 2 Sun Ginseng + 1 Silver Moss | Any | 3rd | Martial Apprentice | ×1.5 |
| 玄 Mystic | Jade Marrow Pill | 2 Moon Mushroom + 1 Jade Lily | Any | 5th | Martial Expert | ×1.8 |
| 地 Earth | Thousand Rivers Pill | 2 Golden Ginseng + 1 Snow Lily | 50-year | 7th | Grand Martial Master | ×2.2 |
| 天 Heaven | Heaven-Devouring Pill | 2 Heaven Lotus + 1 Star Dew | 50-year | 9th | Martial King | ×2.8 |

- Only one Qi pill active at a time
- A Qi pill **below your realm's grade** gives only half its bonus
  (e.g. Ember Dantian ×1.3 → ×1.15 for a Martial Apprentice)

### ⚡ Qi Burst pills — instant Internal Qi

| Grade | Recipe | Min herb age | Rank | Gives |
|---|---|---|---|---|
| Mortal | 3 Spirit Grass + 1 Dew Leaf | 50-year | 2nd | 2 hours of your Qi Rate |
| Yellow | 3 Sun Ginseng + 1 Silver Moss | 50-year | 4th | 3 hours |
| Mystic | 3 Moon Mushroom + 1 Jade Lily | 50-year | 6th | 4 hours |
| Earth | 3 Golden Ginseng + 1 Snow Lily | 100-year | 8th | 5 hours |
| Heaven | 3 Heaven Lotus + 1 Star Dew | 100-year | 9th | 6 hours |

Below your realm's grade: half the Qi.

### ❤️ Mending pills — heal HP and shorten injuries

| Grade | Recipe | Rank | Heals | Injury |
|---|---|---|---|---|
| Mortal | 2 Red Berry + 1 Dew Leaf | 1st | 30% HP | −30 min |
| Yellow | 2 Blood Flower + 1 Silver Moss | 3rd | 40% HP | −1 h |
| Mystic | 2 Heart Lotus + 1 Jade Lily | 5th | 50% HP | −2 h |
| Earth | 2 Phoenix Flower + 1 Snow Lily | 7th | 65% HP | −3 h |
| Heaven | 2 Immortal Peach + 1 Star Dew | 9th | 80% HP | Cures injury |

### 💧 Cleansing pills — remove pill toxicity (add none themselves)

| Grade | Recipe | Min herb age | Rank | Removes |
|---|---|---|---|---|
| Mortal | 3 Dew Leaf | Any | 2nd | 1 toxicity |
| Yellow | 3 Silver Moss | Any | 4th | 1 toxicity |
| Mystic | 3 Jade Lily | Any | 6th | 2 toxicity |
| Earth | 3 Snow Lily | 50-year | 8th | 2 toxicity |
| Heaven | 3 Star Dew | 50-year | 9th | 3 toxicity |

### 🏔️ Breakthrough pills — hard on purpose

| Grade | Recipe | Beast Core | Min herb age | Rank | Breakthrough chance |
|---|---|---|---|---|---|
| Mortal | 2 Iron Root + 1 Dew Leaf | Normal | 50-year | 2nd | +5% |
| Yellow | 2 Stone Root + 1 Silver Moss | Elite | 100-year | 4th | +7% |
| Mystic | 2 Thunder Root + 1 Jade Lily | Elite | 100-year | 6th | +10% |
| Earth | 2 Mountain Root + 1 Snow Lily | Beast King | 500-year | 8th | +12% |
| Heaven | 2 Chaos Root + 1 Star Dew | Beast King | 500-year | 9th | +15% |

- Crafted **one difficulty level harder** than the pill's grade, plus Stage 5
- Failing Stage 5 **destroys the Beast Core**
- Only realm breakthroughs use them; **one pill per attempt**, used up even if it fails

### Pill toxicity
- Pills add toxicity based on their patterns (below)
- Toxicity 4–5: pill effects ×0.5 · Toxicity 6+: pill effects ×0.25
- Toxicity drops by **1 every 8 hours** — about 3 pills a day are safe

---

## 5. /craft — the alchemy minigame

Choose a pill, then refine it through the stages. Every craft is random:
ideal heat, herb order, balance values and timing change each time.
**No cooldown** — herbs are the limit. A craft takes about a minute.

Discord has a short delay on button presses, so every stage is **turn-based with
a timer per decision**, never a real-time moving bar.

### The stages

**🔥 Stage 1 — Ignite the Cauldron (heat control)**
- Heat shown 0–100°. The recipe has a hidden **safe zone**
- Each round: 🔥 **Stoke** (+heat) · 🌬️ **Fan** (−heat) · ✋ **Hold**
- Heat drifts randomly; hints warn of spikes (*"The flames lick hungrily at the walls..."*)
- Score = rounds kept inside the zone

**🌿 Stage 2 — Add the Herbs (order puzzle)**
- The herbs must go in a hidden order, random every craft
- The cauldron gives clues (*"The Moon Mushroom shies from the heat"*)
- A wrong herb causes a **backlash**: score lost and a heat spike

**☯️ Stage 3 — Fuse the Essences (balance puzzle)**
- Two bars, **Yin** and **Yang**. Balance them within a limited number of moves
- Actions: *Circulate · Compress · Cool · Ignite* — each moves both bars differently
- Wild herbs push the bars randomly each turn

**💊 Stage 4 — Condense the Pill (timing)**
- The pill pulses each round: *faint glow · steady light · the light trembles...*
- Press **Condense** at the perfect pulse. Too early = weak; too late = cracked
- This stage decides most of the pill patterns

**🔒 Stage 5 — Seal the Core (Breakthrough pills only)**
- Fuse the Beast Core into the pill: Stage 3's balance puzzle and Stage 4's timing
  combined, in one round of 3 moves
- Fail = Beast Core destroyed and the craft fails

### Difficulty levels

| Difficulty | Pill grade | Stages | Rounds per stage | Time per decision | Heat safe zone | Misleading hints | Extra |
|---|---|---|---|---|---|---|---|
| 🟢 Normal | Mortal | 1, 4 | 3 | 6s | 30° wide | 0% | — |
| 🟡 Hard | Yellow | 1, 2, 4 | 4 | 5s | 25° | 0% | — |
| 🟠 Very Hard | Mystic | 1, 2, 3, 4 | 5 | 4s | 20° | 15% | — |
| 🔴 Extreme | Earth | 1, 2, 3, 4 | 6 | 3.5s | 15° | 25% | Wild herbs |
| 💀 Super Hard | Heaven | 1, 2, 3, 4 | 7 | 3s | 12° | 35% | Wild herbs, Pill Tribulation |

Breakthrough pills use the next difficulty up (Heaven stays at Super Hard) and add Stage 5.

### Alchemist rank makes it easier

For each rank **above** the pill's required rank (counts up to 3):
- Heat safe zone **+10%** wider
- **+0.5s** per decision
- **1 free hint** in Stage 2 (one herb's position revealed)
- At **2+ ranks above**: 1 mistake forgiven per craft

### Score → pill patterns (丹纹)

Final score = average of stage scores + herb age bonus (max 100%).

| Score | Result | Patterns | Effect | Toxicity |
|---|---|---|---|---|
| Below 40% | 💥 Cauldron explodes — herbs lost | — | — | — |
| 40–47% | Pill | 1 (一纹) | ×0.85 | +2 |
| 47–55% | Pill | 2 | ×0.90 | +2 |
| 55–62% | Pill | 3 | ×0.95 | +2 |
| 62–70% | Pill | 4 | ×1.00 | +1 |
| 70–77% | Pill | 5 | ×1.05 | +1 |
| 77–85% | Pill | 6 | ×1.10 | +1 |
| 85–90% | Pill | 7 | ×1.15 | +1 |
| 90–95% | Pill | 8 | ×1.20 | 0 |
| 95%+ | Pill Tribulation | 9 (九纹) | ×1.25 | 0 |

- Patterns are **capped by herb age** (see Herb age table)
- **Pill Tribulation:** at 95%+ with 1000-year herbs, dark clouds gather — one final
  hard round. Survive = **9 patterns** (announced to the server). Fail = 8 patterns.
- The effect multiplier applies to Qi Rate, Qi Burst, healing, toxicity removed
  (rounded down) and breakthrough chance
- Shown as e.g. **Jade Marrow Pill · 七纹**

---

## 6. Alchemist rank (一品 → 九品)

Everyone starts as a **1st Grade Alchemist**.

| Rank | Can craft | EXP to reach |
|---|---|---|
| 1st Grade | Mortal Qi / Mending | — |
| 2nd Grade | + Mortal Burst / Cleansing / Breakthrough | 100 |
| 3rd Grade | Yellow Qi / Mending | 400 |
| 4th Grade | + Yellow Burst / Cleansing / Breakthrough | 1,200 |
| 5th Grade | Mystic Qi / Mending | 3,200 |
| 6th Grade | + Mystic Burst / Cleansing / Breakthrough | 8,200 |
| 7th Grade | Earth Qi / Mending | 20,200 |
| 8th Grade | + Earth Burst / Cleansing / Breakthrough | 50,200 |
| 9th Grade | All Heaven pills | 120,200 |

(EXP shown is the total needed.)

### Alchemy EXP per craft

```
EXP = Base EXP × (0.5 + 0.1 × patterns) × pill type multiplier × rank penalty
```

| Pill grade | Base EXP |
|---|---|
| Mortal | 10 |
| Yellow | 25 |
| Mystic | 60 |
| Earth | 150 |
| Heaven | 400 |

- Pill type multiplier: Breakthrough ×2, all others ×1
- Explosion: 20% of Base EXP
- Rank penalty: 1–2 ranks above the pill's required rank ×0.5; 3+ ranks above ×0.1
  (no farming easy pills)

Rough pace (average 5-pattern pills): 3rd Grade after ~45 crafts, 5th after ~170,
7th after ~480, 9th after ~1,200.
