# Strength and Vitality

Points the player places on top of the realm's own growth (stats.md). The realm still gives every
cultivator the same base HP, Attack and Defense; the points let two cultivators of the same layer differ.

## Earning points

- **One point for every layer climbed** since Mortal layer 1 (`stats.ATTRIBUTE_POINTS_PER_LAYER`).
  Mortal has 3 layers, every other realm 10: Martial Apprentice layer 1 = 3 points, Martial Warrior layer 6 = 18,
  Martial Saint Peak = 102.
- The count comes from the realm and layer (`player.attribute_points`), so players who were already high
  when this was added have all their points waiting. Only the placed points are saved (`strength`, `vitality`).

## What they do

| Point | Effect | Where it adds |
|---|---|---|
| **Strength** | +0.5% Attack (`stats.STRENGTH_ATTACK`) | Added to the weapon, armor and technique % bonuses |
| **Vitality** | +0.5% max HP (`stats.VITALITY_HP`) | Same |

Defense is not changed by points. Every fight, hunt, spar and duel uses them through `player.final_stats`.
**Fair Duels** count only as many points as the lower player's level earns, shared in the same proportion.

## Placing and resetting

- `/attributes strength:<n> vitality:<n>` in Discord, or the Strength & Vitality panel on the website's profile,
  which previews the new Attack and HP before you confirm. Points can't be placed during a fight in Discord.
- **Reset** gives every placed point back. The first reset is free (`stats.FREE_ATTRIBUTE_RESETS`), then each
  costs **200 Moon Pearls** (`stats.ATTRIBUTE_RESET_PEARLS`, the price of a name change). It is in the ledger as
  "Attribute reset".

## Balance

Simulated against a realm's normal beasts (600 fights per build, about 40 points): a Martial Master who spams
Strike ends a fight with roughly 10 points more of their HP left with everything in Strength, 7 with everything in
Vitality; for players who read the beast the gain is small. With the Stunned / counter rule (combat.md) a Strength
player still has to read the beast to land the bigger hits.
