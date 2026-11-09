# Leaderboard

Numbers live in `leaderboard.py`. Code: `bot/leaderboard.py` (ranking), `bot/leaderboard_view.py` (/leaderboard), `cards/leaderboard.py` (card).

## Boards
| Board | Ranked by | Ties |
|---|---|---|
| Realm | realm, then layer, then Qi (the same order as the profile's server rank) | older account first |
| Lotus Coins | Lotus Coins held now | older account first |
| Moon Pearls | Moon Pearls held now | older account first |

## How it works
- **Command:** **/leaderboard** (or `m lb`) opens the Realm board. A button for each board switches between them, and the `board` option opens one directly.
- **What the card shows:**
  - the top `TOP_N` (10);
  - the top three on a podium in gold, silver and bronze rings, with their Discord avatars (cached `AVATAR_CACHE_SECONDS`);
  - your own rank, even when you're outside the top ten.
- **Adding a board:** add an entry to `BOARDS`, and an ordering in `bot/leaderboard._key` if it isn't a player column.
