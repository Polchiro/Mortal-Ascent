# Combat

Fights in /explore (wild beasts, bandits) and team hunts (Elite Lairs, Beast King Dens)
are played **turn by turn** on one fight screen. /spar uses the same screen against the
master (see technique.md), /train shows its challenges in the same framed style, and /duel plays
player against player on it (see pvp.md).

All numbers are in `battle.py`. The engine is `bot/fight.py`, the card `cards/battle.py`,
the buttons `bot/fight_view.py`.

## The fight screen

One image card and buttons in a **single message that is edited every turn** (cards/beast_fight.py). Beast
fights, /spar and /train-/practice all use it.

**Look:** a cinematic encounter. The beast's painting (art/beasts/<slug>.png, one per beast and the_master.png)
stands in a misty landscape of its element, lit from behind by a rim of the element's colour, with drifting
particles (embers, snow, wisps, sparks, spores, dust...). No boxes: text sits on soft shade. Two typefaces: Cinzel
for the name and the result, Inter for the rest. The sky, the beast and the lighting are drawn once per fight
(about 1s) and reused, so each turn renders in about 0.1s.

| Part | What it shows |
|---|---|
| Top left | Tier · realm (Elite underlined in silver, Beast King in gold), the name (gold leaf for a Beast King), role · element, ATK / DEF, the Profile's HP bar with the HP lost last turn and the HP % |
| Top right | Turn, seconds to act, status (Charged, Staggered, Hidden…) |
| Lower left | **Next move**: the beast's tell; red with **POWERFUL ATTACK** or **SIGNATURE MOVE** when it is charging |
| Bottom | You: name, realm, HP bar with %, the last turn in two lines; your techniques and pills as medallions (dark with the turns left while resting). Team hunts list every hunter's HP |
| Staging | Predators close and low, dragons and serpents rising, giants filling the lower half, winged beasts high, Shadow beasts veiled in fog, Beast Kings with a column of light |
| Result | The scene dims: Victory / Defeat / Escaped, the tier (Elite, Beast King), and turns, damage dealt, damage taken and HP left |

Beast art: a transparent PNG named after the beast (`White-Browed Tiger King` → `white_browed_tiger_king.png`);
prompts for every beast are in art/beasts/PROMPTS.md. Without a file, a drawn creature is used.

Buttons, each with a round medallion icon (uploaded as the bot's application emojis at start-up;
normal emojis if that fails):

1. **Strike · Guard · Break**
2. Your equipped **techniques**, greyed out with the turns left while they rest
3. **Mending pill** (from your bag) · **Flee**


## Turns

- **15 seconds** to pick. No pick = you **Guard**. **Three timeouts in a row** = you flee.
- **Team hunts:** every member picks secretly; the turn resolves when everyone has picked or time runs out.
- The card is redrawn once per turn; the message text shows who is still choosing.

## Counters

**Strike beats Break · Guard beats Strike · Break beats Guard**

| You \ Beast | Strike | Guard | Break |
|---|---|---|---|
| **Strike** | Both hit at 50% | Blocked, and you are **Stunned** | You hit, it misses |
| **Guard** | Blocked fully, and you **counter** for 50% | Nothing happens | It hits you |
| **Break** | It hits you, you miss | You hit and **stagger** it | Both hit at 50% |

- **Stagger:** the beast loses its next turn and takes +25% damage meanwhile.
- **Stunned (you):** a Strike into the beast's Guard throws you off balance: you can only Guard next turn
  (`battle.BLOCKED_STRIKE_STUN`). Thunder's stun works the same way.
- **Counter:** a Guard that fully blocks a normal Strike hits back with half a Strike (`battle.GUARD_COUNTER`).
  Not against signature or charged attacks.
- Why: spamming Strike and the attack technique used to win as often as reading the beast, and faster.
  Simulations (600 fights per build) now show reading the beast leaves more HP and ends fights ~20% sooner.
- Damage uses stats.md, with the **30% per-turn cap** on every hit except charged attacks.
- Each turn the beast attacks **one** fighter (the arrow). Others are only hurt by charged attacks.
- Beasts pick moves by role (Armored guards more, Hunters strike more). In 70% of turns the warning
  bar shows a **tell** for the move it is about to make.

## Techniques

Techniques keep their effects from technique.md. Against beasts they have **no cooldown**: they spend **Battle Qi**.

### Battle Qi

A fight energy, separate from cultivation's Internal Qi (it never touches your cultivation bar).

| | |
|---|---|
| Start of every fight | 100 (`battle.BATTLE_QI_START`) + 2 per **Spirit** point (attributes.md) |
| Back every turn | +10 (`BATTLE_QI_PER_TURN`), never above the start |
| A good Guard (fully blocks a normal Strike) | +25 more (`BATTLE_QI_GOOD_GUARD`) |
| Technique cost | Mortal 30 · Yellow 35 · Mystic 40 · Earth 45 · Heaven 50 (`TECHNIQUE_QI_COST`) |
| Chilled | techniques cost +10 |

Gear that touched cooldowns works on Battle Qi here: **Focus** (artifact) gives a chance that a technique costs
nothing, **Sword Heart** (forged passive) makes the next technique free every 3rd turn. Duels and spars keep their
per-grade cooldowns. Simulated against normal beasts (1,200 fights per row): win rates and HP left are unchanged;
players use their techniques more often (about 75% of turns when reading the beast, was 61%).

- **Attack technique** = a stronger Strike. Combo hits several times, Pierce ignores defense,
  Heavy hits harder, Stagger weakens the beast's next Guard (Nine Dragons: it cannot Guard at all).
- **Defense technique** = a Guard with extras: it **holds its block % of a Break** (20% Mortal to 50% Heaven;
  a plain Guard holds nothing), so it's the safe pick when you can't read the beast. Counter reflects blocked
  damage, Recover heals on a block, Unbreakable halves what's left of a Break, Evade may dodge a Break.
  Against a charged attack it adds its block % to the Guard.
- +20 mastery EXP per use, as before.

## Telegraphed moves

Every beast announces its element move **one turn ahead** in the warning bar.

| Beast | Move | Rule |
|---|---|---|
| Elite, Beast King | **Charged attack** every 3rd turn | 1.5× damage, **ignores the 30% cap**, hits the **whole party**. Guard blocks 50% (+ your defense technique's block, max 80%); **Break interrupts it** for everyone |
| Normal | **Signature strike** every 4th turn | 1.2× damage (capped). Guard blocks it. If it lands, its element status always applies |

## Elements

Every beast has one of eight elements. The element sets the scene's colours (sky, moon, mist,
rim light, eyes, HP bar, panels, warning bar; see `ELEMENT_ACCENTS` in cards/theme.py) and adds
one status. Player statuses land with 30% of normal hits and always with the telegraphed move;
beast statuses start when it telegraphs.

| Element | Seal | Status | Effect |
|---|---|---|---|
| Blood | 血 | Bleeding (you) | −4% max HP per turn, 3 turns |
| Frost | 霜 | Chilled (you) | Techniques rest 1 turn longer, 2 turns |
| Flame | 炎 | Burning (you) | −5% max HP per turn, 3 turns |
| Shadow | 影 | Hidden (beast) | Strikes miss it for 2 turns; a Break drags it out |
| Thunder | 雷 | Stunned (you) | You can only Guard next turn |
| Venom | 毒 | Poisoned (you) | −3% max HP per turn, 4 turns |
| Earth | 岩 | Stoneskin (beast) | Takes 30% less damage, 2 turns |
| Jade | 玉 | Regrowth (beast) | Heals 4% max HP per turn, 3 turns |

Bandits use the Blood palette and cause Bleeding, but have no telegraphed move.

## Body types

When there is no art file, the scene draws a silhouette with rim light, glowing eyes and fangs:
**big cat, wolf, bird, serpent, ape, turtle, insect, dragon** (`beasts.TRAITS`). Hoofed beasts
(boars, oxen, rhinos, stags, steeds) use the wolf body; bears use the ape body.

## Pills and fleeing

- **Mending pill:** heals its % of max HP (alchemy.md) and uses your turn. At most **2 per fight**.
  It leaves your bag and adds pill toxicity as usual.
- **Flee:** 80% chance against Normal beasts and bandits, 50% Elite, 35% Beast King. A failed
  attempt leaves you open for that turn.
- Fleeing a wild beast ends the encounter with no reward and no injury; the expedition goes on.
  In a hunt, a fighter who flees gets no reward and no injury.
- After 30 turns (60 in hunts) the beast escapes.

## /spar and mastery trials

/spar uses the same screen against **the Master**: a robed silhouette in the Master palette
(steel blue night). The rules stay those of technique.md: the master follows a rhythm with
tells, mastery EXP comes only from well-timed techniques, and trials are the same fight
against a stronger master. New here:

- **15 seconds per exchange**; no pick = Guard; three timeouts in a row = you walk away (forfeit).
- The Strike / Guard / Break buttons still shuffle every exchange (technique.md anti-AFK rule);
  the technique buttons stay on the second row.
- The **You** panel counts your well-timed technique uses; the warning bar shows his tell.

## /train and /practice

The challenges keep their rules from challenges.md and `challenges.py`. Only the look changes:
every step is shown in the same framed card, in the **training courtyard** (temple halls, red
pillars, lanterns) with the green Courtyard accent, and the buttons use the same medallion icons.

| Part | What it shows |
|---|---|
| Top right | Move / Wave / Round / Try number and the seconds to answer |
| Bars | Challenge progress (moves, points, rounds survived, tries) and yours (correct answers, stamina, HP) |
| Chips | The session's conditions (Heavy Rain, Night Training…) |
| Last move | The result of your last answer (Find the Weakness: your earlier guesses), in the log panel |
| Warning bar | The master's tell, or what the disciples are doing |

Each card is drawn **before** its timer starts, so drawing never eats into your answer time.
Night Training shows a dark card first and the real one when the moonlight reveals the move.

## Rewards (unchanged)

- Wild beasts: Lotus Coins, chest chance, beast cores, beasts slain.
- Bandits: win = their purse; lose = they rob 10% of your Lotus Coins.
- Losing a fight in /explore ends the expedition as a defeat (explore.md).
- Hunts: every winner rolls their own chest and core, Beast King kills count for the realm
  gate, and a fallen Beast King is announced. Losing injures the team for 1 hour.

## Gear

- Weapon and armor % buffs are part of your HP, Attack and Defense (stats.md).
- Combat artifacts (Fang, Bell, Mirror, Thunder, Lotus, Feather, Focus) work in every fight here and in
  team hunts; see equipment.md "How artifact effects work in the game".
