# Daily Quests

Numbers live in `quests.py`. Code: `bot/quests.py` (rules), `bot/quest_view.py` (/daily), `cards/quests.py` (card).

## How it works
- **When:** every day at midnight UTC, each player gets `QUESTS_PER_DAY` (4) quests.
- **How they're picked:** a weighted pick from `QUESTS`, seeded by the player and the day. The list stays the same all day and differs between players.
- **What counts:** only what you do that day.
  - `/train` sessions;
  - `/practice` runs;
  - `/spar` bouts;
  - `/explore` trips you finish;
  - beasts defeated on them;
  - herbs gathered;
  - pills crafted. A batch counts every pill.
- **Rewards:** each quest pays Lotus Coins and Moon Pearls.
  - The coins grow with the realm: × (1 + `COIN_STEP_PER_REALM` × realm index), so Mortal ×1 and Martial Saint ×3.5.
  - The pearls are flat.
- **Claiming:** **/daily** shows the card. Its **Claim** button gives every finished reward. Each quest is claimed once a day.

## Complete all quests
- **Reward:** finishing every quest of the day adds `ALL_DONE_COINS` (scaled like the quest coins) and `ALL_DONE_PEARLS`.
- **Chest:** there's an `ALL_DONE_CHEST_CHANCE` (60%) chance of a chest, weighted by `ALL_DONE_CHEST_TIERS`:

  | Chest | Weight |
  |---|---|
  | Common | 40 |
  | Uncommon | 30 |
  | Rare | 18 |
  | Epic | 9 |
  | Legendary | 3 |

  That works out to 24%, 18%, 10.8%, 5.4% and 1.8%.
- **The roll is fixed for the day** (seeded by player and day), so claiming again can't reroll it.
- **Full bag:** if the chest doesn't fit, nothing of the bonus is given yet. It waits until a slot is free.

## Daily totals (Mortal realm)
- **Quests:** about 300–360 🪷 and 13–15 🌙.
- **Bonus:** +150 🪷 and +8 🌙.
- **Total:** about 21–23 🌙 a day, roughly 650 a month.
