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
| Grandmaster | 80 |
| Martial Lord | 160 |
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
- On the website Train is a different game with the same pay: "Train on the website" below

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
| Grandmaster | 2,850 |
| Martial Lord | 9,300 |
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
| Grandmaster | 42% | 18% |
| Martial Lord | 35% | 12% |
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

## Train on the website: Meridian Circulation

**WEBSITE ONLY (SHOAIB, Nov 25).** Discord's `/train` keeps its challenges (challenges.md). On the website Train is a
**two-minute meditation**: your character sits facing you, the body turns into a glowing map of meridians, and pulses
of Qi flow along them. **Gold Qi** must reach the **Dantian**; **dark turbid Qi** must leave through an **exit** (a palm
or a sole). You never strike: you steer. The full design: the Claude Doc "Train redesign: Meridian Circulation".

**No teacher in the meditation (SHOAIB, Nov 25).** You sit alone. Hints and the opening line show as a quiet line of
text under the top bar, and your own character answers at the end (below). **Sister Jing**, keeper of the Quiet
Pavilion, stands by the pond in Azure Cloud Town: "Sit and meditate" seats you (`/town/visit/keeper`);
leaving returns you to her. She is the only way in: Train is no longer in the Martial Master's training yard.

**How a session ends** (worked out on the page from its own count, which the server's matches):

| Score | It is called | What plays |
|---|---|---|
| 85% or more | Meridians clear! | your Qi surge video and its sound, the golden bloom over the Dantian |
| 70-84% | Well guided | the same surge, a smaller bloom |
| 50-69% | The Qi drifts | the map dims, a low note (no video) |
| under 50% | The Qi scatters | your Qi scatters video and its sound, grey mist rising |
| Stability 0 | Qi deviation | your Qi deviation video and its sound, the crack; the session ends early |

**Status.** Tiers 1 and 2 are built, with their art. A player whose realm gives tier 3-5 (or a Wandering Hermit) plays
tier 2's network for now; the reward formula is the same at every tier.

**The art** (`art/train/`, cut from SHOAIB's Flow pictures and videos by `scripts/make_train_art.py`):
- **The chamber**: `chamber.mp4` loops behind everything (its last second cross-fades into its first) and its sound,
  `chamber.wav`, is the room's ambience under the meditation music (a mood in `spar_music.js`). The page places the
  picture so its cushion is under you, at your size. A Wandering Hermit moves the session to `hermit.jpg`.
- **You** (`hero/<gender>/`): `loop.webp`, the calm part of the meditation video as a sprite sheet played forwards then
  backwards (so it never jumps; his robe opens for a moment early in his video, which is left out). While the Qi flows
  you fade to a dim figure so the map reads over your robes. The three endings are small videos with the picture on
  top and its see-through mask underneath (`surge.mp4`, `deviation.mp4`, `scatter.mp4`: their light and smoke reach far
  past the body), each with its own sound at full level (`.mp3`).
- **The map on your body**: `sheets.json` `fit` holds where each acupoint is on each character's picture
  (`POINTS` in the script); the page nudges the map's points onto them, so the channels run from her real crown to her
  real palms. Only the drawing moves: the rules go by each line's length.
- **Effects** (`fx/`): the golden Dantian orb (turning slowly), the jade gate seal (whole when shut, a ghost when
  open), the exit lotus, the blockage knot, the golden bloom, the Qi deviation crack, the scattered Qi; the upper
  Dantian's blue orb waits for tier 5. `rival.webp` steps in for the Rival Disciple's round; `badge.webp` is Train's
  picture in the training yard. Without any of these the page draws its plain code version.

### How it plays
- **Three cycles** of about 35 seconds, after a 3-second settle-in where the map glows in and nothing moves. A session
  with a Rival Disciple has a fourth, short round.
- **Junctions** (jade rings, numbered top to bottom): click one, or press its number, to switch which way it sends Qi.
  A pulse reads the junction the moment it arrives. Junctions start each session pointing a random way.
- **Gates** (red seals): click one, or press Shift + its number, to close it; pulses wait in front of it. A pulse waiting
  **4 s**, or **3** pulses waiting, bursts the gate: the waiting Qi is lost. Opening it lets the waiting pulses through
  one after another.
- **Breath**: hold Space (the Breathe button on a phone) to slow all Qi to **40%**. A full Breath bar lasts 4 s and
  refills in 5 s once you let go.
- The strip at the top shows the next 3 pulses' colours.
- **Harmony** (SHOAIB, Nov 25: "do your best recommendations"): every pulse handled cleanly in a row (gold into the
  Dantian, dark out an exit) adds 1, shown under the cycle count; any other end (gold lost, dark in, a burst) sets it
  back to 0. The channels glow brighter as it builds. Every **10** in a row is a **Qi Resonance**: your Breath bar is
  full again, with a chime and a small bloom. Harmony never changes the score or the pay; only the three cycles count.
- **Open a meridian** (same day): when cycles 1 and 2 end, the session waits while you take one of two blessings (press
  1 or 2, or click) for the rest of the session. After **10 s** the first is taken for you. The four blessings, two
  offered each time, drawn from the session's seed:

  | Blessing | What it does |
  |---|---|
  | Deep Breath | the Breath bar holds 50% more (6 s instead of 4), and fills now |
  | Steady Flow | all Qi flows 15% slower |
  | Mending | +25 Stability now (never above 100) |
  | Strong Seals | gates burst only with 5 waiting, or after 6 s (instead of 3 and 4 s) |

  The scroll lists the blessings you took and your best Harmony.

### The networks (tiers 1-2)
| Tier | Realms | Sources | Junctions | Gates | Pulses a cycle | New idea |
|---|---|---|---|---|---|---|
| 1 | Mortal, Apprentice, Warrior | Crown | 2 | 1 | 10 | Steering; no dark Qi in cycle 1 |
| 2 | Expert, Master | Crown + one palm | 3, then 4 | 2 | 12 | Two flows at once; a knot from cycle 2 |

**The look (SHOAIB, Nov 25: "A, the acupuncture chart").** The channels curve with the seated body like a
medical scroll: thin jade lines through small acupoint dots, a slow flowing dash showing which way Qi goes, and the
chart's names beside the main points (Baihui at the crown, Tiantu at the throat, Tanzhong at the heart, the Dantian,
Laogong at the palms, Yongquan at the soles). Junctions are jade rings with an arrow; gates are red paper talisman
seals (bright when shut). The points sit at the figure's own acupoints (`BODY` and `ROUTES` in web/train_play.py), so
when the painted meditation picture arrives they are fitted to it. Gates only go on channels long enough to tap clear
of the junctions and the Dantian on a phone: the crown, the arms, and at tier 2 the palm's channel.

Between cycles the map shifts: a gate moves to another line (tier 1's first gate is always on the crown, the only
line gold uses in cycle 1); at tier 2 a **knot** blocks one of the two lines into the
Dantian from cycle 2 (and moves in cycle 3), so gold must be sent round it. A session may be mirrored left to right.
After the first cycle, 1 pulse in 4 follows close behind the one before (flip fast, close a gate, or breathe).
Dark Qi is 30% of the pulses (tier 1: from cycle 2).

### Score and Stability
- **Score = 60% gold delivered + 25% dark expelled + 15% Stability left** (each a share of all the pulses of the
  three cycles). With no dark Qi at all, gold counts 85%.
- **Stability** starts at 100: −10 per gold pulse lost (out an exit or into a knot), −15 per dark pulse into the
  Dantian, −10 per gate burst (its lost pulses cost nothing more), +2 per pulse delivered cleanly. At 0: **Qi
  deviation**, the session ends and every pulse not delivered counts as lost. It never costs Qi you already have.

### Pay, rest, conditions, events
- Paid by the bot's own `trainer.finish`: **4 hours of your Qi rate × score**, +15% per condition, × the event, 10% under
  50%, breakthroughs, Spirit Dew, the quest count. The bot's challenge memory (`last_challenge`) is left alone.
- The **60-minute rest** (shared with Discord's /train) starts when you press Train, as Discord's claim_session does.
  Walking away earns nothing.
- Tier, conditions and event are rolled from the bot's tables. In Meridian Circulation: **Heavy Rain** Qi flows 25%
  faster; **Night Training** a pulse shows its colour only for the last 40% of its trip and the preview is dark;
  **Drunken Master** the preview is wrong 1 time in 4 (the pulse itself never lies); **Old Injury** one limb's meridian
  is slow (60% speed) and Breath drains twice as fast (its leak comes with PR 2).
- **Wandering Hermit** ×5 with two conditions; **Epiphany** +50%; **Rival Disciple**: after cycle 3 the rival pushes 6
  dark pulses in; expel 4 for ×2. The rival's round doesn't change the score or Stability.

### The referee
The server makes the whole session from a seed (`web/train_play.make_plan`), keeps the time it began, and when the page
sends what you did (`[ms, "j" | "g" | "b" | "B", which]`) replays it through `web/train_sim.py` and scores it itself.
The page runs the same rules (`web/static/train_sim.js`, a line-for-line copy, whole numbers only, 50 ms ticks) so what
you see is what the server will count; tests run both copies on the same sessions. The server also checks the session
ran its full length and that the actions are in order, known and not too many.

Code: `web/train_play.py` (the session, the pay), `web/train_sim.py` + `web/static/train_sim.js` (the rules),
`web/train_routes.py`, `web/templates/train.html`, `web/static/train.js`, `train.css`; art `art/train/`,
`scripts/make_train_art.py`. Tests: `tests/test_web_train.py`.

