# Website (web game, step 1: login and profile)

The website is the same game as the Discord bot, in a browser. It shares the bot's **database** and
**game rules**, so a character is one character everywhere: progress made in Discord shows up on the
website, and later the other way round.

**Built:** Discord login, the player's real profile page, the inventory, the **forge**, **alchemy**, **gathering**
and **exploring with turn-based fights** (all fully playable, saved to the same character), logout, and `/api/me` (the profile as JSON for the next pages).

**Next:** using items (Open, Take) from the inventory, training, and team hunts.
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

Layout (a dark xianxia hall, `body.hallbg`, background `art/scenes/profile_hall.jpg`):

- **Identity:** the player's chosen look (docs/appearance.md), or `art/portraits/cultivator_default.webp` until they
  choose one, with a **Choose your look** (free) or **Change look** button. The portrait sits over the
  realm's seal character (`cards/theme.REALM_CHAR`), name, realm and layer, and title chips: talent, alchemist and
  blacksmith rank (once they have EXP) and the realm rank.
- **Cultivation:** realm n of 11, the layer pips, phase, the Internal Qi bar, rate, status and the next gate.
- **Attributes:** HP, Internal Qi, Attack, Defense (icons in `art/icons/attr/`), each with its realm base and
  every bonus on top (weapon, armor, technique passives), from `bot/sheet/attributes.attribute_values`.
- **Strength, Vitality & Spirit:** the points to place (docs/attributes.md), + and − buttons with a live preview of the new
  Attack, HP and Battle Qi (same formula as `player.final_stats`); type any amount or press **Max** to put every
  free point into one stat; Place points, and Reset (first free, then 200 Moon Pearls).
  Everything is checked again on the server (`bot/points.py`).
- **Equipment:** weapon, armor and the two artifact slots, plus the three technique slots. Unequip from here.
- **Journey:** beasts slain, herbs gathered, breakthroughs, duels won.

Apart from placing and resetting points and unequipping gear, the page only shows.

## The appearance page

`/appearance` (from the profile's look button): gender, hairstyle (round face thumbnails) and hair colour, with a
live full-body preview. The first look is free, then each change costs 200 Moon Pearls; **Decide later** goes back
to the profile. Saving goes through `bot/appearance.py`. Pictures come from `/look/<gender>_<hair>_<color>.webp`
(full body) and `/look/..._face.png` (round faces), drawn by `looks.py` and cached in `art/.looks/`.

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
- **Equip / Unequip** for weapons, armor and artifacts, in the Inspect panel. The rules are the bot's own
  (`loot.use_item`, `gear.equip_problem`): the realm a tier needs, one weapon and one armor, two artifacts of
  different families. Only the logged-in player's own gear can be changed, and the bot's message is shown.
- The profile page has an **Equipment** card: the four slots (weapon, armor, two artifacts) with what is worn,
  its effects, Unequip, and a link to the bag for an empty slot. HP / Attack / Defense follow at once.
- The website can't see a fight running in Discord. A fight reads the gear when it starts, so changing gear here
  during one counts from the next fight.
- Using and opening items (pills, chests, manuals) stays in Discord for now.

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

## Gathering

`/gather` is the bot's `/gather` (docs/alchemy.md, section 2) in the browser, with the same engine:
`bot/gathering.py` (`Gathering`) rolls the herb, its age and the choices, checks the pick, stores the herb and keeps
the Herbal Insight streak, the Wandering Spirit check, the poison HP and the review flags.

1. **Start:** the streak, the odds per grade at the player's realm, and the Wandering Spirit's pause if there is one.
2. **Round:** the place (its painting is the background), the herb to find with its description, the numbered
   choice cards (each plant's drawing and LOOK text) and a timer bar. Keys **1–6** pick a card. The Wandering
   Spirit round shows four signs instead.
3. **Result:** the real herb ringed in green, a wrong pick in red, every plant named, then **Gather again** or **Stop**.
4. **The trip ends** (Stop, two idle minutes, or the spirit's pause): what was gathered this trip.

**Why this is fast with many players.** In Discord every round is a 1200×940 card drawn on the server, one at a
time for all players. Here the browser shows the page; the server only sends text and small pictures that are
drawn once and kept.

**The server referees.** Which choice is real stays on the server until the pick: the page has no plant names,
and each choice's picture is asked for by its position (`/gather/plant/<turn>/o2.png`), only for the page now
showing. The time for a pick is measured on the server, so a late right answer is still "too slow", and a closed
page times out. Old or repeated pages and unknown choices are ignored. One trip at a time per player, kept in
the website's memory. Rare finds (Earth, Heaven) are announced only when gathered in Discord.

## Explore

`/explore` is the bot's `/explore` (docs/explore.md) in the browser, with the same engines: `bot/expedition.py` runs
the steps, encounters, loot and the walk home; every fight turn is `bot/fight.py` (the rules in docs/combat.md);
a lair is fought with `bot/hunt.py`.

1. **Set out:** the same checks as Discord (injury, the 30-minute rest). The rest starts when you set out and is
   saved, so Discord can't start a second expedition at the same time, and the other way round.
2. **Steps:** three paths with their clues, then the encounter: merchant, wounded stranger, hazard (a 3-second
   leap, timed from when the page shows it), herbs, ore, chests and so on. Go deeper or return safely.
3. **Fights** (`explore_play.html`, the arena `art/scenes/arena_ruins.jpg`): your card (portrait, realm, HP,
   Attack, Defense, statuses), the beast's plate (tier, role, element, realm, HP, statuses), your fighter
   (`art/portraits/fighter_stance.webp`) facing the beast's painting (`art/beasts/`), the beast's warning in the
   plate, the battle log, and **four big moves** with keys 1–4 (`art/icons/actions/`): Strike, **Techniques** (a
   small menu with your attack and defense technique, their effect and Battle Qi cost), Guard, Break. **Mending Pill** (P)
   and **Flee** (F) are small buttons on the side. Hovering a move shows what it beats and its cooldown. After a
   turn a big word over your fighter says what happened (Countered!, Blocked!, Stunned!, Clash!, Guard broken!).
   A move is sent without leaving the page (`web/static/fight.js`), so the screen doesn't jump back to the top.
   Light animations are read from the engine's own log: a slash on a hit, a screen shake on Break, red claws when
   the beast hits, a blue ring on a block, green on a pill, damage numbers.
4. **Lairs:** an Elite lair or Beast King den found on the website can't be posted to a Discord channel, so it is
   hunted **alone**, exactly like a lair found in a DM with the bot (`hunt.start_battle` with one fighter,
   `hunt.pay`), from the end screen while it is open.

The server keeps every clock. **Fight turns have no reaction time on the website for now**: a turn waits for the
player, and only a page left alone for 10 minutes (`explore_play.TURN_LIMIT`) gets the bot's timed-out move
(Guard; three in a row: flee), so a forgotten fight still ends. A hazard answered too late fails, and two idle
minutes outside a fight end the expedition (as the bot's panel does). Old pages and moves that aren't
possible are ignored. Rare finds are announced only in Discord.

Only `art/icons`, `art/scenes`, `art/chests`, `art/portraits` and `art/beasts` are served (as `/art/...`), plus `web/static`. Nothing else in the repo
(code, `.env`, the database) can be opened from the browser.

## Going online later

- Add the real address as a second redirect, e.g. `https://<your-domain>/callback`, and set
  `WEB_REDIRECT_URI` to it. With an `https://` address the login cookie is only sent over https.
- When the bot and the website both write often, move from SQLite to PostgreSQL (CLAUDE.md, Tech stack).
