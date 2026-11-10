# Website (web game, step 1: login and profile)

The website is the same game as the Discord bot, in a browser. It shares the bot's **database** and
**game rules**, so a character is one character everywhere: progress made in Discord shows up on the
website, and later the other way round.

**Built:** Discord login, the player's real profile page, the inventory, the **forge** and **alchemy** (both
fully playable, saved to the same character), logout, and `/api/me` (the profile as JSON for the next pages).

**Next:** the other playable screens from the web mockup (gather, fight), then using items
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
  manuals their technique's icon. Items with no painted file (the 39 essences) are drawn by the bot's own
  card code and served from `/art/drawn/<kind>.png` (`web/drawn.py`, drawn once and kept in memory), so they
  look exactly like the Discord cards.
- Viewing only for now: using, equipping and opening items stays in Discord.

## The forge

`/forge` is the bot's `/forge` (docs/forge.md, section 5) in the browser, with the same engine:
`bot/forging.py` makes the plan, takes the materials, runs the five stages and writes the passive.

1. **Choose:** the player's weapons, armor and artifacts (worn first) with their passive slots; the action
   (Enchant / Reroll / Replace, and the slot to lock for Replace); an optional essence, fuel and quench liquid.
2. **Cost:** the materials (with how many they have), the Lotus Coins, the difficulty and anything missing.
   **Begin** is only active when nothing is missing; the plan is rebuilt from the database on Begin,
   never trusted from the page.
3. **Play:** one page per decision with the stage's picture, the engine's lines and the buttons it offers,
   a timer bar, and the points per stage. The hidden zone, true metal and temperatures stay on the server.
4. **Result:** the rarity, the new passives, the lines from `finish_forge` (EXP, rank up, Second Chance).

**The server referees the clock.** Every decision has a deadline (`seconds + forge.TIMER_GRACE_SECONDS`).
When the page comes back late, or is closed, each missed decision is played as a timeout (`act(None)`),
exactly like the bot's timer, so walking away can't help. Each page carries a turn number: an old or
repeated page, or a button that isn't on offer, is ignored. One forge at a time per player; a forge in
progress lives in the website's memory and is lost if the website restarts (like a bot restart).

## Alchemy

`/alchemy` is the bot's `/craft` (docs/alchemy.md, section 5) in the browser, with the same engine:
`bot/crafting.py` picks the herbs (`plan`), takes them (`take_ingredients`), runs the stages (`Craft`, started by
`craft_for`, the same function `/craft` uses, so the Furnace artifact, Steady Hand, Swift Hands and Alchemy Sage
count on both) and stores the pill (`finish_craft`: EXP, rank up, quests, cauldron ash, Second Chance).

1. **Choose:** every pill the player's alchemist rank allows, each marked *Ready to craft* or *Missing herbs*.
2. **Recipe:** the herbs needed (with how many they have), the difficulty, seconds per decision, heat zone and
   stages; the batch size (from 2nd Grade, up to `alchemy.batch_cap`) and youngest / oldest herbs; then exactly
   which herbs go in, their average age and the most patterns it allows, and any rank relief.
   **Begin** is only active when nothing is missing; the plan is rebuilt from the database on Begin.
3. **Play:** one page per decision with the engine's lines and buttons, a timer bar, and the score per stage:
   a heat gauge (Ignite), the herb buttons (Add the Herbs), Yin and Yang bars (Fuse, Seal the Core), the glowing
   pill (Condense) and the Pill Tribulation. The safe heat zone, the herb order and the true pulse stay on the server.
4. **Result:** the pill and its patterns (e.g. *Jade Marrow Pill · 七纹*) or the explosion, with the lines from
   `finish_craft`. **Craft again** returns to the same recipe.

The server referees the clock exactly like the forge: every decision has a deadline (`seconds +
crafting.TIMER_GRACE_SECONDS`), late or missing pages play the timed-out move, old or repeated pages and buttons
that aren't on offer are ignored. One craft at a time per player, kept in the website's memory.
A nine-pattern pill is announced only when it is crafted in Discord (the website has no channel to post in).

Only `art/icons`, `art/scenes` and `art/chests` are served (as `/art/...`), plus `web/static`. Nothing else in the repo
(code, `.env`, the database) can be opened from the browser.

## Going online later

- Add the real address as a second redirect, e.g. `https://<your-domain>/callback`, and set
  `WEB_REDIRECT_URI` to it. With an `https://` address the login cookie is only sent over https.
- When the bot and the website both write often, move from SQLite to PostgreSQL (CLAUDE.md, Tech stack).
