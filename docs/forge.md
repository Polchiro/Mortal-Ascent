# Forging — /forge, Passives and Materials

The forging loop: **collect materials → forge at the anvil in a minigame → put passives on your weapons, armor and
artifacts → raise your blacksmith rank → forge better gear.**

All numbers are in `forge.py`. Numbers marked DEFAULT there were not in the design and were picked by the bot.

> **Built:** this page and the data (Part 1); materials in the game (Part 2): every drop source, the Materials tab
> in /inventory (groups Base · Bindings · Essences · Fuel & Liquids · Beast Cores), drawn material icons
> (cards/material_icons.py), and the Index sections Materials and Passives (weapon, armor, artifact).
> Part 3: the **/forge** command (and `m forge`) with the Forge Hall card (cards/forge.py), round button icons
> (cards/forge_icons.py), blacksmith ranks, and the Swift Hands, Steady Hand and Second Chance artifact passives.
> **Not built yet:** passives in fights and on cards (Part 4). Until then forged passives are saved on the gear and
> shown in /forge, but don't change fights yet.

Forging materials sit in a materials pouch: they stack by type and **don't use bag slots** (DEFAULT,
`forge.MATERIALS_USE_BAG_SLOTS`). Beast Cores still do.

---

## 1. Passive slots

Every weapon, armor and artifact has passive slots by tier. A forge puts one passive in a slot.

| Gear tier | Slots | Highest rarity |
|---|---|---|
| ⚪ Ordinary | 1 | Rare |
| 🟢 Refined | 1 | Epic |
| 🔵 Spirit | 1 | Epic |
| 🟣 Treasure | 2 | Legendary |
| 🟠 Divine | 2 | Mythical |

Rarities, lowest to highest: ⚪ Common · 🟢 Uncommon · 🔵 Rare · 🟣 Epic · 🟠 Legendary · 🔴 Mythical.
**Mythical** names glow on cards and are announced to the server.

---

## 2. Passives

Each passive belongs to a **family**. An essence of that family makes the forge pick from that family only.

### ⚔️ Weapon passives

| Rarity | Passive | Effect | Family |
|---|---|---|---|
| Common | Keen Edge | +3% Attack | 金 Metal |
| Common | Weighted | +2% Attack, +1% HP | 金 Metal |
| Common | Balanced | +2% Attack, +1% Defense | 金 Metal |
| Common | Hunter's Edge | +4% damage against beasts | 影 Shadow |
| Common | Duelist's Edge | +3% damage in duels | 影 Shadow |
| Uncommon | Opening Strike | +10% damage on turn 1 | 炎 Flame |
| Uncommon | Breaker | +8% Break damage | 炎 Flame |
| Uncommon | Pursuit | +6% damage against a staggered target | 影 Shadow |
| Uncommon | Executioner | +8% damage against targets under 30% HP | 炎 Flame |
| Uncommon | Rhythm | Each Strike in a row +4% damage (max 3 stacks) | 雷 Thunder |
| Rare | Lifesteal | Heal 4% of the damage you deal | 血 Blood |
| Rare | Armor Crack | Each hit −3% target Defense (max 5 stacks) | 金 Metal |
| Rare | Bleeding Cut | Strikes bleed 2% max HP for 2 turns | 血 Blood |
| Rare | Riposte | After a successful Guard, next Strike +15% | 影 Shadow |
| Rare | Flash Step | 5% chance to strike twice (second hit 50%) | 雷 Thunder |
| Epic | Thunder Edge | 10% stun: the target can't Guard next turn | 雷 Thunder |
| Epic | Blood Frenzy | +1% Attack per 5% HP missing | 血 Blood |
| Epic | Sunder | Ignore 10% Defense | 金 Metal |
| Epic | Combo Master | Combo techniques: 30% chance of +1 hit | 雷 Thunder |
| Legendary | Heaven-Splitting | Once per fight, a Strike can't be Guarded | 金 Metal |
| Legendary | Undying Blade | Once per fight, survive a lethal hit at 1 HP | 血 Blood |
| Legendary | Dragon's Wrath | 12% chance of ×1.5 damage | 炎 Flame |
| Mythical | Sword Heart | Every 3rd turn your technique has no cooldown | 影 Shadow |
| Mythical | Ten Thousand Swords Return | After 5 turns, the next hit deals ×2 | 雷 Thunder |
| Mythical | Devouring Edge | Heal 10% of damage dealt, steal 5% target Attack for the fight | 血 Blood |

### 🛡️ Armor passives

| Rarity | Passive | Effect | Family |
|---|---|---|---|
| Common | Sturdy | +3% Defense | 土 Earth |
| Common | Thick Hide | +3% HP | 木 Jade |
| Common | Padded | +2% HP, +1% Defense | 土 Earth |
| Common | Beastward | −4% damage from beasts | 毒 Venom |
| Common | Duel Guard | −3% damage in duels | 影 Shadow |
| Uncommon | Steadfast | −10% damage on turn 1 | 霜 Frost |
| Uncommon | Second Wind | Once per fight, heal 5% when below 50% HP | 木 Jade |
| Uncommon | Iron Will | −5% damage from Break | 霜 Frost |
| Uncommon | Thorns | Reflect 3% | 毒 Venom |
| Uncommon | Recovery | Heal 1% HP every turn | 木 Jade |
| Rare | Bulwark | Guard blocks 10% more | 土 Earth |
| Rare | Spiked Plates | Reflect 6% | 毒 Venom |
| Rare | Evasive | 5% dodge | 影 Shadow |
| Rare | Unshaken | 50% chance to resist Stagger | 霜 Frost |
| Rare | Fortified | −10% damage from charged attacks | 土 Earth |
| Epic | Golden Body | The first hit each fight −50% | 霜 Frost |
| Epic | Stone Skin | +1% Defense per turn (max +10%) | 土 Earth |
| Epic | Vital Flow | Healing +25% | 木 Jade |
| Epic | Unbreakable Will | Immune to Stagger | 霜 Frost |
| Legendary | Phoenix Rebirth | Once per fight, revive at 20% HP | 木 Jade |
| Legendary | Mountain Stance | No single hit takes more than 20% max HP | 土 Earth |
| Legendary | Mirror Shell | Once per fight, a charged attack deals 0 and goes back to the attacker | 毒 Venom |
| Mythical | Immortal Body | Heal 3% max HP per turn, immune to bleed and poison | 木 Jade |
| Mythical | Black Tortoise's Shell | Every 4th hit against you is fully blocked | 土 Earth |
| Mythical | Heavenly Aegis | In team hunts, allies take −10% damage | 影 Shadow |

### 🔮 Artifact passives (on top of the artifact's own effect)

| Rarity | Passive | Effect | Family |
|---|---|---|---|
| Common | Qi Flow | +2% Qi Rate | 气 Spirit Dew |
| Common | Lucky Coin | +2% Lotus Coins | 福 Fortune Coin |
| Common | Herbalist | +3% old-herb chance | 丹 Cauldron Ash |
| Common | Swift Hands | +0.5s per decision in /gather, /craft, /forge | 悟 Insight Ink |
| Uncommon | Scholar | +4% mastery EXP | 悟 Insight Ink |
| Uncommon | Pill Affinity | Pills +5% stronger | 丹 Cauldron Ash |
| Uncommon | Prospector | +5% forging material drops | 福 Fortune Coin |
| Uncommon | Clear Head | Toxicity fades 10% faster | 气 Spirit Dew |
| Rare | Deep Pockets | 5% chance of an extra chest roll | 福 Fortune Coin |
| Rare | Steady Hand | /craft and /forge safe zones +2° | 丹 Cauldron Ash |
| Rare | Keen Eye | /explore clues 10% less likely to lie | 悟 Insight Ink |
| Rare | Spirit Bond | +10% Beast Core chance | 悟 Insight Ink |
| Epic | Second Chance | Once a day, a failed craft or forge keeps its materials | 丹 Cauldron Ash |
| Epic | Insightful | +10% mastery EXP from /practice | 悟 Insight Ink |
| Epic | Fortune's Favor | +8% rare /explore encounters | 福 Fortune Coin |
| Legendary | Heaven's Favor | +5% realm breakthrough chance | 气 Spirit Dew |
| Legendary | Alchemy Sage | Pills can reach 1 pattern beyond the herb-age limit | 丹 Cauldron Ash |
| Legendary | Treasure Sense | Jade Chests 20% more likely | 福 Fortune Coin |
| Mythical | Dao Heart | +10% Qi Rate, toxicity never above 5 | 气 Spirit Dew |
| Mythical | Fate Weaver | Once a week, reroll one chest's contents | 福 Fortune Coin |

### Balance rules
- The **30% per-hit cap** still applies. No passive lifts it.
- **No duplicates:** the same passive can't be on two items one character wears. The forge never offers a passive
  the character already has; if two worn items share one anyway (swapped gear), only one counts.
- Passives work at **half strength in Fair Duels** (like combat artifacts).
- All **reflect** together is capped at **20%**.
- Each **once-per-fight** effect fires once per fight.

---

## 3. Materials (70 types)

Material tiers 1–5 line up with gear tiers: tier 1 forges Ordinary gear, tier 5 forges Divine gear.

### Base materials (needed)
| Tier | ⚔️ Weapon metal | 🛡️ Armor | 🔮 Artifact jade |
|---|---|---|---|
| 1 | Iron Ore | Rough Hide | Green Jade |
| 2 | Black Iron | Iron Shell | White Jade |
| 3 | Spirit Silver | Spirit Silk | Spirit Jade |
| 4 | Star Iron | Dragon Scale | Star Jade |
| 5 | Heavenly Gold | Qilin Hide | Primordial Jade |

### Bindings (needed), Fuel and Quench liquids (optional)
| Tier | Binding | 🔥 Fuel (widens Ignite zone) | 💧 Quench liquid (widens Quench window) |
|---|---|---|---|
| 1 | Beast Bone | Charcoal (+2°) | Spring Water (+4°) |
| 2 | Tough Sinew | Black Coal (+3°) | Beast Oil (+6°) |
| 3 | Spirit Fang | Spirit Coal (+4°) | Spirit Spring Water (+8°) |
| 4 | Dragon Tendon | Fire Beast Core (+5°) | Dragon Blood (+10°) |
| 5 | Chaos Crystal | Sunflame Stone (+6°) | Heavenly Dew (+12°) |

### Essences (optional): 13 families × 3 grades
| Grade | Highest rarity it can give |
|---|---|
| Shard | Uncommon |
| Crystal | Epic |
| Heart | Mythical |

| Gear | Families |
|---|---|
| ⚔️ Weapon | 金 Metal, 血 Blood, 雷 Thunder, 炎 Flame, 影 Shadow |
| 🛡️ Armor | 土 Earth, 木 Jade, 霜 Frost, 毒 Venom, 影 Shadow (the same Shadow essence as weapons) |
| 🔮 Artifact | 气 Spirit Dew, 福 Fortune Coin, 丹 Cauldron Ash, 悟 Insight Ink |

### 🔏 Seal Stone
Needed to **Replace** (locks one slot). From chests and the Moon Pearl shop (30 🌙, DEFAULT).

### Recipe per forge
| Gear tier | Base material | Binding |
|---|---|---|
| Ordinary | 3 × tier 1 | 2 × tier 1 |
| Refined | 4 × tier 2 | 2 × tier 2 |
| Spirit | 5 × tier 3 | 3 × tier 3 |
| Treasure | 6 × tier 4 | 3 × tier 4 |
| Divine | 8 × tier 5 | 4 × tier 5 |

Plus, if you want: 1 essence, 1 fuel, 1 quench liquid.

- **With an essence:** the passive comes only from that family, and never above the essence grade's rarity.
  If the family has no passive left at that rarity, it falls to the best one it has **below** (never above).
  The menu greys out an essence that can't give anything on that gear (today: a Blood Shard on weapons).
- **Without an essence:** a random passive of that rarity from every family of that gear type.

---

## 4. Where materials drop

The material tier follows your realm, the same way Beast Cores and herbs do (Mortal → tier 1, Martial
Apprentice/Warrior → 2, Expert/Master → 3, Grand Master/Grandmaster → 4, Martial King and above → 5).
In chests, the tier is rolled like a weapon's tier in that chest.

| Source | Drops |
|---|---|
| ⛏️ Ore Vein (new /explore encounter, 6%) | 2–4 weapon metal · 30% a fuel · 10% a Metal Shard |
| 🐾 Normal beast | 30% a binding · 30% an armor material · 8% Shard of the beast's element |
| ⚔️ Elite beast | 60% 1–2 bindings · 60% 1–2 armor materials · 5% Crystal of the beast's element |
| 👑 Beast King | 2–3 bindings · 2–3 armor materials · 20% Crystal, 2% Heart of the beast's element |
| 🌿 /gather | 8% per herb: a spring's quench liquid · 3% per herb: a Jade Shard |
| 📦 Chests | Artifact jades (15/25/35/50% for Wooden/Bronze/Silver/Jade) · Fortune Coins · Seal Stones (0/1/3/8%) |
| ⚗️ /craft | Cauldron Ash: 1 Shard (1–3 patterns), 2 Shards (4–6), 1 Crystal (7–8), 1 Heart (9) |
| 📜 /practice | 15% an Insight Ink Shard · a duplicate manual gives Insight Ink (Shard → Heart by grade) |
| 🏋️ /train | 15% a Spirit Dew Shard · a breakthrough gives Spirit Dew (phase: Shard, realm: Crystal) |
| 🌙 Shop | Seal Stone, 30 Moon Pearls |

Percentages for bindings, armor materials, springs, chests, ash, ink and dew are DEFAULTs.

---

## 5. /forge — the minigame

Choose gear → **Enchant** (fill an empty slot), **Reroll** or **Replace** → pick an essence, fuel and liquid
(optional) → see the cost and what you need → play. One image card, edited each turn, with a timer per decision.

| # | Stage | What you do |
|---|---|---|
| 1 | 🔥 Ignite the Forge | Pump the bellows to keep the heat in the hidden safe zone. Fuel widens the zone |
| 2 | 🌡️ Heat the Metal | The metal glows dull red → cherry red → orange → yellow → white. Pull it out at the colour the gear needs |
| 3 | 🔨 Hammer | Several strikes. Each shows a hint (*rings true / dull thud / cooling*). Strike Hard, Strike Light or Reheat |
| 4 | 💧 Quench | Water (fast, risky, up to 20 points) or Oil (slow, safe, up to 15), then the moment to plunge. Liquid widens the window |
| 5 | ✨ Inscribe | Carve the rune by picking the right strokes in order |

Each stage gives **0–20 points** (100 total). **Below 50 = FAILED.**

### Score → rarity
| Score | Rarity | Inscribe needed |
|---|---|---|
| 50–64 | Common | — |
| 65–74 | Uncommon | — |
| 75–84 | Rare | — |
| 85–92 | Epic | 12 / 20 |
| 93–97 | Legendary | 16 / 20 |
| 98–100 | Mythical | 19 / 20 |

Then it is capped by the gear tier and the essence grade. *Inscribe counts most:* a weak inscription holds a high
score back one rarity at a time until the inscription is good enough (DEFAULT numbers).

### Difficulty by gear tier
| Gear tier | Difficulty | Time per decision | Ignite zone | Hints that lie | Hammer strikes | Rune strokes | Metal colour needed |
|---|---|---|---|---|---|---|---|
| Ordinary | Normal | 6s | 30° | 0% | 3 | 3 | cherry red |
| Refined | Hard | 5s | 25° | 0% | 4 | 3 | orange |
| Spirit | Very Hard | 4s | 20° | 15% | 5 | 4 | orange |
| Treasure | Extreme | 3.5s | 15° | 25% | 6 | 4 | yellow |
| Divine | Super Hard | 3s | 12° | 35% | 7 | 5 | white |

The Quench window starts at 40° (Ordinary) and narrows by 6° per tier to 16° (Divine).

### How each stage plays (DEFAULT numbers in `forge.py`, "Stage rules")
- **🔥 Ignite** (3–7 rounds by tier): Pump (+12°), Hold, or Vent (−12°). After each move the fire drifts ±5°, or
  a gust/draught moves it 12–18° (30% of rounds); the omen line warns which way. The hidden safe zone sits
  between 20° and 85°. Points = rounds ending in the zone ÷ rounds.
- **🌡️ Heat:** the metal starts dull red and gets one colour hotter each time you keep heating. 20 points at the
  right colour, 10 at one colour off, 0 further; heating past white burns it (0).
- **🔨 Hammer:** each strike the metal *rings true* (Strike Hard), gives a *dull thud* (Strike Light) or is
  *cooling* (Reheat). Points = right strikes ÷ strikes.
- **💧 Quench:** choose Water (window ×0.7, up to 20) or Oil (window ×1.3, up to 15). The blade starts at
  820–900° and the target is 420–620°. **Wait** cools it 30–60°, **Wait a breath** 6–12°. Plunging in the middle
  half of the window gives full points, elsewhere in the window half, outside it 2. Too cold misses (2).
- **✨ Inscribe:** the rune's strokes are shown in order; each pick offers 4 strokes. Points = right strokes ÷ strokes.
- A lying hint (by tier) shows the wrong heat text, colour, hammer hint, temperature or one wrong stroke in the
  sequence. A decision not made in time counts as a wrong one (Ignite: Hold; Heat: keep heating; Quench: oil,
  then wait). Every forge is random: the zone, target colour order, metal states, temperatures and rune change.
- The materials and coins are taken when you press **Begin**. Walking away lets every decision time out.

---

## 6. Blacksmith rank

1st–9th Grade, on the **same EXP curve as alchemist ranks** (100 / 400 / 1,200 / 3,200 / 8,200 / 20,200 / 50,200 /
120,200 total EXP).

| Gear tier | Rank needed | Base EXP |
|---|---|---|
| Ordinary | 1st | 10 |
| Refined | 2nd | 25 |
| Spirit | 4th | 60 |
| Treasure | 6th | 150 |
| Divine | 8th | 400 |

- **Every attempt gives EXP:** a failed forge gives 20% of the base, a success gives the base × (1 + 0.1 per rarity
  step above Common). Ranks far above the gear tier give less, as in /craft.
- **Rank relief:** each rank above the requirement (max 3 counted) gives **+0.5s per decision** and **+2°** on the
  Ignite zone and Quench window.

---

## 7. Enchant, Reroll, Replace, Fail

| Action | What it does | Cost |
|---|---|---|
| Enchant | Fills an empty slot | Materials only (DEFAULT) |
| Reroll | Forge again: every slot gets a new random passive | Materials + Lotus Coins |
| Replace | Treasure/Divine only: lock one slot with 1 Seal Stone, reroll the other | Materials + 1 Seal Stone + Lotus Coins ×2 |

| Gear tier | Reroll coins | Replace coins |
|---|---|---|
| Ordinary | 500 | — |
| Refined | 2,000 | — |
| Spirit | 8,000 | — |
| Treasure | 30,000 | 60,000 |
| Divine | 100,000 | 200,000 |

- **Failed forge:** ALL materials used are lost, essence, fuel and liquid included. The gear and its current
  passives stay safe. (The Second Chance artifact passive saves the materials once a day.)
- **Reroll on 2-slot gear:** both slots are reforged; the score's rarity applies to each (DEFAULT).
