# Combat

Fights in /explore (wild beasts, bandits) and team hunts (Elite Lairs, Beast King Dens)
are played **turn by turn** on one fight screen. /spar uses the same screen against the
master (see technique.md), and /train shows its challenges in the same framed style.

All numbers are in `battle.py`. The engine is `bot/fight.py`, the card `cards/battle.py`,
the buttons `bot/fight_view.py`.

## The fight screen

One image card plus buttons, in a **single message that is edited every turn**.

| Part | What it shows |
|---|---|
| Scene window | The beast under a moon, mist and mountains, in its element's colours. Beast art from `art/beasts/<beast_slug>.png` if the file exists, otherwise a silhouette for its body type |
| Over the scene | Beast seal, name, tier · role · element · realm, HP bar, element seal, status chips (Staggered, Hidden, Charged…) |
| Top right | Turn number and seconds to choose |
| Bottom left | **Hunting Party**: each member's seal, name, realm, HP bar and last move. The arrow marks the fighter the beast is going for; names turn red below 25% HP. Solo fights show **You** plus your equipped techniques and Mending pills, and whether each is ready |
| Bottom right | **Last turn**: what happened, with small icons |
| Warning bar | The beast's next move: a tell, or its telegraphed element move |

Buttons, each with a round medallion icon (uploaded as the bot's application emojis at start-up;
normal emojis if that fails):

1. **Strike · Guard · Break**
2. Your equipped **techniques**, greyed out with the turns left while they rest
3. **Mending pill** (from your bag) · **Flee**

Beast art: name the file after the beast, lower case, spaces and punctuation as `_`
(`White-Browed Tiger King` → `art/beasts/white_browed_tiger_king.png`). A transparent PNG works best.

## Turns

- **15 seconds** to pick. No pick = you **Guard**. **Three timeouts in a row** = you flee.
- **Team hunts:** every member picks secretly; the turn resolves when everyone has picked or time runs out.
- The card is redrawn once per turn; the message text shows who is still choosing.

## Counters

**Strike beats Break · Guard beats Strike · Break beats Guard**

| You \ Beast | Strike | Guard | Break |
|---|---|---|---|
| **Strike** | Both hit at 50% | Blocked | You hit, it misses |
| **Guard** | Blocked fully | Nothing happens | It hits you |
| **Break** | It hits you, you miss | You hit and **stagger** it | Both hit at 50% |

- **Stagger:** the beast loses its next turn and takes +25% damage meanwhile.
- Damage uses stats.md, with the **30% per-turn cap** on every hit except charged attacks.
- Each turn the beast attacks **one** fighter (the arrow). Others are only hurt by charged attacks.
- Beasts pick moves by role (Armored guards more, Hunters strike more). In 60% of turns the warning
  bar shows a **tell** for the move it is about to make.

## Techniques

Techniques keep their effects and the per-grade cooldowns from technique.md.

- **Attack technique** = a stronger Strike. Combo hits several times, Pierce ignores defense,
  Heavy hits harder, Stagger weakens the beast's next Guard (Nine Dragons: it cannot Guard at all).
- **Defense technique** = a Guard with extras: Counter reflects blocked damage, Recover heals on a
  block, Unbreakable halves a Break, Evade may dodge a Break. Against a charged attack it adds its
  block % to the Guard.
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

## Rewards (unchanged)

- Wild beasts: Lotus Coins, chest chance, beast cores, beasts slain.
- Bandits: win = their purse; lose = they rob 10% of your Lotus Coins.
- Losing a fight in /explore ends the expedition as a defeat (explore.md).
- Hunts: every winner rolls their own chest and core, Beast King kills count for the realm
  gate, and a fallen Beast King is announced. Losing injures the team for 1 hour.
