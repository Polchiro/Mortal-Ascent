# Website (web game, step 1: login and profile)

The website is the same game as the Discord bot, in a browser. It shares the bot's **database** and
**game rules**, so a character is one character everywhere: progress made in Discord shows up on the
website, and later the other way round.

**Built:** Discord login, the player's real profile page, the inventory, logout, and `/api/me` (the profile
as JSON for the next pages). The website only **reads** the game for now; every action still happens in Discord.

**Next:** the playable screens from the web mockup (forge, alchemy, gather, fight), then using items
(Open, Equip, Take) from the inventory.
Every action's result is decided **on the server** with the bot's own rules; the browser only shows it,
so players can't cheat by editing the page.

## Running it on your computer

1. `pip install -r requirements-web.txt`
2. Discord Developer Portal > your app > **OAuth2**:
   - copy the **Client ID** and **Client Secret** into `.env` (see `.env.example`)
   - under **Redirects**, add `http://localhost:8000/callback` and press **Save Changes**
3. Optional: put any long random text in `WEB_SESSION_SECRET` so logins survive a restart.
4. From the repo root: `python -m web`, then open <http://localhost:8000>.

The bot and the website can run at the same time; they use the same `mortal_ascent.db`.
By default the website only listens on your own computer (`127.0.0.1`).

## Logging in

| Step | What happens |
|---|---|
| 1 | The player presses **Continue with Discord** (`/login`) |
| 2 | We send them to Discord's own permission page, asking only for the `identify` scope |
| 3 | They press **Authorize**; Discord sends them back to `/callback` with a one-time code |
| 4 | The server swaps the code for a token, asks Discord who they are, and logs them in |

- We get their **Discord ID, display name and avatar**. Never their email, messages or password.
- The token is used once and **not stored**. The login lives in a signed cookie (`ma_session`, 14 days,
  HttpOnly, SameSite=Lax, Secure when the site uses https).
- A random `state` value is checked on the way back, so a forged or reused login link is refused.
- **Cancel** on Discord returns to the front page: "You cancelled. Nothing was shared with the game."
- A Discord account with no character sees "No character yet" and is told to use `/start` in Discord.

## The profile page

All numbers come from `bot/sheet/data.profile_data`, the same function the `/profile` card uses:
realm, layer and phase, talent, realm rank, Internal Qi (with rate and time to full), HP / Attack / Defense,
Lotus Coins and Moon Pearls, the technique slots with their painted icons, beasts slain, herbs gathered,
breakthroughs, duels won and the weapon.

## The inventory page

`/inventory` is the same bag as the bot's `/inventory`: the tabs (Chests, Manuals, Weapons, Armor,
Artifacts, Pills, Herbs, Materials) with how many items each holds, the items as painted tiles in
their rarity colour, and an Inspect panel for the chosen item. The tabs, items and Inspect text all come
from `bot/sheet` (`items.CATEGORIES`, `data.bag_items`, `items.details`), so they always match Discord.

- `?tab=<key>` picks a tab (an unknown one shows Weapons); `?item=<id>` picks an item. Only the
  logged-in player's own items can be picked.
- Pictures: each item's painting (`cards/art_icons.py`); chests use `art/chests/<rarity>.png` and
  manuals their technique's icon.
- Viewing only for now: using, equipping and opening items stays in Discord.

Only `art/icons`, `art/scenes` and `art/chests` are served (as `/art/...`), plus `web/static`. Nothing else in the repo
(code, `.env`, the database) can be opened from the browser.

## Going online later

- Add the real address as a second redirect, e.g. `https://<your-domain>/callback`, and set
  `WEB_REDIRECT_URI` to it. With an `https://` address the login cookie is only sent over https.
- When the bot and the website both write often, move from SQLite to PostgreSQL (CLAUDE.md, Tech stack).
