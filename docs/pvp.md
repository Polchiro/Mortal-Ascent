# PvP duels (v1: friendly duels, for testing)

Two players fight each other on the same fight screen as beast fights, with the same moves.
Friendly duels have **no consequences**: nothing to win, nothing to lose.

All numbers are in `pvp.py`. The engine is `bot/duel.py`, the buttons and the command `bot/duel_view.py`,
the card `render_duel` in `cards/battle.py`.

## Starting a duel

**/duel @player** (or `m duel @player`), in a server channel.

- The challenged player gets **Accept / Decline** buttons for **60 seconds**. The challenger can withdraw with Decline.
- Before accepting, both see each other's **realm, layer, talent, equipped techniques and weapon**, and the
  realm and layer both will fight at.
- Not allowed while either player is **in a fight** (an expedition, spar, training challenge, hunt or another
  duel), **in seclusion** or **injured**.
- You can't duel yourself or a bot. Duels need a server channel (not a DM), so others can watch.
- **1-minute cooldown per pair of players** (from the start and again from the end of a duel). Other pairs are free.

## Fair duel (the only mode for now)

- Both fight with the **base stats of the lower player's realm and layer** (stats.md). Lower = the lower realm,
  or the lower layer in the same realm.
- **Weapon and technique % buffs count at half strength** (`BUFF_SHARE = 0.5`).
- **Technique effects and mastery count fully** (damage multipliers, Combo, Pierce, Heavy, Stagger, Counter,
  Recover, Unbreakable, Evade).
- **No pills.** **Flee = forfeit** (it counts as a loss).

## Turns

- Both players **pick secretly at the same time**: Strike, Guard, Break, or an equipped technique
  (Attack technique = a stronger Strike, Defense technique = a Guard with extras). Techniques keep their
  normal per-grade cooldowns (technique.md).
- Every button press gets a **private reply** ("You chose Guard") that only the presser sees. The card only shows
  **LOCKED IN** for a player who has picked, never *what* they picked.
- When both have picked, both moves are **revealed** and the turn is resolved.
- **15 seconds** to pick, or that player **Guards**. **3 timeouts in a row = forfeit** (both at once = a draw).

## Counters

**Strike beats Break · Guard beats Strike · Break beats Guard** (the same as beast fights).

| Your move \ theirs | Strike | Guard | Break |
|---|---|---|---|
| **Strike** | Both hit at 50% | You are blocked | You hit, they miss |
| **Guard** | You block | Nothing happens | They hit and **stagger** you |
| **Break** | They hit, you miss | You hit and **stagger** them | Both hit at 50% |

- **Stagger:** the broken player takes **+25% damage** on the next turn. (Unlike a beast, a player does not lose
  the turn: both always pick.)
- Defense technique extras work as in beast fights: **Counter** reflects part of a blocked Strike back,
  **Recover** heals on a block, **Unbreakable** halves a Break, **Evade** may dodge a Break.
- An attack technique with **Stagger** weakens the other player's next Guard (that share of a Strike slips through).

## Fair-fight rules

| Rule | Value |
|---|---|
| Per-hit cap | No hit deals more than **30%** of max HP (stats.md), after every bonus |
| Rising intensity | From **turn 10**, all damage **+10% per turn** (turn 10 = +10%, turn 11 = +20%, …) |
| Turn limit | After **turn 20**, the player with the higher **% of HP left** wins; a **draw** if equal |
| Recover | Heals at most **50% of max HP** per duel |
| Evade | Can't trigger **two turns in a row** |
| Knock-out | 0 HP loses; both at 0 on the same turn is a draw |

## The card

Same frame as beast fights, in the **Duel palette** (a mountain ledge at dusk over a sea of clouds).
Big type only; the details are in the text under the card, which Discord shows at reading size.

| Part | What it shows |
|---|---|
| Scene window | Both fighters facing each other: their Discord avatars in round gold frames (a robed silhouette if there is no avatar), **VS** between them |
| Top | "Friendly duel", the fair realm and layer, the **turn number** and seconds to choose |
| Under each fighter | **LOCKED IN** once that player has picked, otherwise "Choosing..." |
| Middle | **Rising intensity +X%** chip from turn 10 |
| Panel | Each side: talent seal, name, realm and layer, a big **HP bar**, the last move and its damage |
| Bottom bar | **Last turn**: both moves and the damage |
| At the end | A result banner: the winner (or Draw), turns, HP left; the loser's portrait greys out |

The duel is posted in the channel where /duel was used, and the same message is edited every turn
so others can watch.

## No consequences

HP is full again afterwards: no injury, no Qi loss, no Lotus Coins, no mastery EXP, no rewards.

## Tracking

- **Duels won / lost** are saved on the player and shown on the **Profile** tab (a draw counts for neither).
- Every duel is logged in the `duels` table (both players, their realms, the fair realm, equipped techniques,
  winner, how it ended, turn count) and every move in `duel_moves` (turn, player, move, technique, timeout,
  damage, HP after).
- **/admin duelstats** (bot owner only) shows each technique's and basic move's **pick count** (turns played,
  timeouts left out) and **win rate** (the share of duels where a player played it that this player won), for balancing.

## Not yet

Ranked Arena, True Power mode (real stats), rewards, tournaments, 2v2.
