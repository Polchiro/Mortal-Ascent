# Daily Quests

Numbers live in `quests.py`. Code: `bot/quests.py` (rules), `bot/quest_view.py` (/daily), `cards/quests.py` (card).

## How it works
- **When:** every day at midnight UTC, each player gets `QUESTS_PER_DAY` (6) quests.
- **How they're picked:** a weighted pick from `QUESTS`, seeded by the player and the day. The list stays the same all day and differs between players.
- **What counts:** only what you do that day.
  - `/train` sessions, `/practice` runs, `/spar` bouts and spar wins;
  - `/explore` trips you finish, and beasts defeated on them;
  - herbs gathered, and 100-year+ herbs gathered;
  - pills crafted (a batch counts every pill), and pills with 5+ patterns;
  - `/forge` attempts;
  - chests opened.
- **Rewards:** each quest pays Lotus Coins and Moon Pearls.
  - The coins grow with the realm: × (1 + `COIN_STEP_PER_REALM` × realm index), so Mortal ×1 and Martial Saint ×3.5.
  - The pearls are flat.
- **Claiming:** **/daily** shows the card. Its **Claim** button gives every finished reward. Each quest is claimed once a day.

## Complete all quests
- **Reward:** finishing every quest of the day adds `ALL_DONE_COINS` (600, scaled like the quest coins) and `ALL_DONE_PEARLS` (25).
- **Chest:** there's an `ALL_DONE_CHEST_CHANCE` (40%) chance of a chest, weighted by `ALL_DONE_CHEST_TIERS`:

  | Chest | Weight | Chance |
  |---|---|---|
  | Common | 55 | 22% |
  | Uncommon | 27 | 10.8% |
  | Rare | 12 | 4.8% |
  | Epic | 5 | 2% |
  | Legendary | 1 | 0.4% |

- **The roll is fixed for the day** (seeded by player and day), so claiming again can't reroll it.
- **Full bag:** if the chest doesn't fit, nothing of the bonus is given yet. It waits until a slot is free.

## Daily totals (Mortal realm)
- **Quests:** about 1,400–1,600 🪷 and 40–48 🌙 for six quests.
- **Bonus:** +600 🪷 and +25 🌙.
- **Total:** about 65–73 🌙 a day, roughly 2,000 a month, for a player who finishes everything every day.
