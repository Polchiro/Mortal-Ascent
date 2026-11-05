# Mortal Ascent bot

Discord bot for Mortal Ascent, built on discord.py with SQLite player storage.
It reuses the game constants (`realms.py`, `stats.py`, `training.py`, `economy.py`, …)
the Character Sheet cards and the `/internal qi` dantian card in `cards/` (crimson and gold).
The older ink-wash cards (`profile_card.py`, `balance_card.py`, `inventory_card.py`, `qi_card.py`) stay in the repo as a
future profile theme. See `docs/character-sheet.md` for how the sheet is built.

## Commands

| Command | What it does |
|---|---|
| `/start` | Creates your character: rolls a talent, Mortal 1st Layer, Iron Fist + Horse Stance Guard, 50 Lotus Coins |
| `/profile [member]` | Opens your **Character Sheet** on the Profile tab: realm, phase and layer, HP / Attack / Defense, Internal Qi, equipped techniques and weapon, your avatar as the portrait. Buttons under it switch to the Techniques, Equipment, Inventory and Purse tabs. With a member it shows only their Profile card, with their purse hidden |
| `/balance` | Opens the sheet on the Purse tab: Lotus Coins, Moon Pearls, active Heavenly Blessing and your last 8 transactions |
| `/inventory [category]` | Opens the sheet on the Inventory tab (Chests, Manuals, Weapons, Pills, Herbs, Materials): a grid of items by category, pages, and an Inspect panel. Pick an item to Open, Learn, Take, Equip, Unequip or Discard it (Discard asks first, and never works on an equipped item) |
| `/explore` | A 5-step expedition: pick a path from its clue, face what is there, then go deeper or return with the loot. 30 min cooldown |
| `/train` | A timed training challenge with the master. The score becomes Internal Qi; layers inside a phase open automatically. 60 min cooldown |
| `/meditate` | Shows how fast your Qi gathers on its own and when your bar fills. Passive Qi is added automatically before every command (up to 12 hours is kept while you are away) |
| `/seclusion [hours]` | Enter closed-door seclusion for 8–24 hours at ×2 Qi Rate (no exploring or sparring). Run it again to check on it or leave early (early = no ×2) |
| `/internal qi` | Sends the dantian card (same crimson-and-gold style as the Character Sheet, with the dantian orb filling as your bar fills): Qi bar (plus Qi waiting to be collected), Qi Rate, time to a full bar, the next gate, your cultivation status, and every Qi source (talent, technique, blessing, pill, Blessed Land, seclusion, pill toxicity) with the full formula |
| `/breakthrough` | When your Qi bar is full at a phase bottleneck (90%) or realm gate (70%), attempt it. Shows the chance and risk first |
| `/practice <technique>` | A training challenge for one technique's mastery EXP (40 × score). 30 min cooldown; 5 full sessions a day, then 50%, then 10% |
| `/spar [technique]` | A turn-by-turn fight with a master. EXP only for techniques used at the right moment. With a technique whose bar is full, it is that technique's **mastery trial**. 2 h cooldown |
| `/techniques` | Opens the sheet on the Techniques tab: the Attack, Defense and Flex sockets, then every learned technique with effect, power, cooldown and mastery. Equip or unequip (not during a fight) |
| `/equipment` | Opens the sheet on the Equipment tab: your weapon slot, base → final stats with every buff's source, and menus to swap or remove your weapon (not during a fight) |
| `/shop` | Moon Pearl shop: Heavenly Fate Reroll (never lower), Qi pills, +20 bag slots, name change |
| `/blessing` | The eight Heavenly Blessing tiers; buy one with Moon Pearls (same tier adds 30 days) |
| `/recharge` | Shows the Moon Pearl packages. Buying is not switched on (see below) |
| `/reroll` | Fate Reroll with Lotus Coins: 10,000, then ×1.5 each time; normal odds, can go lower |
| `/physician` | Pay Lotus Coins to heal an injury right away |
| `/cooldown` | Every timer in one place: explore, train, practice and spar cooldowns, mastery trials, daily practice/spar counts, seclusion, injury, pill toxicity, blessing, Qi pill and blessed land. Times show in your own time zone |
| `/admin reset [member]` | **Owner/admins only.** Clears all cooldowns and daily limits, heals injuries, finishes a seclusion timer, frees a stuck session |
| `/admin give [member] [lotus_coins] [moon_pearls] [qi]` | **Owner/admins only.** Adds coins, pearls or Qi for testing |
| `/gather` | Gather herbs for alchemy, no limit. One message updates in place: the bot names a herb and describes it, you pick the plant that matches before time runs out (10s at Mortal down to 6s at Heaven). Poisonous look-alikes cost 5% HP. Herbs have an age (10 to 1000 years); 100-year+ herbs fight back (6 choices, 3s less). Right picks in a row build the Herbal Insight streak (more old herbs). A Wandering Spirit asks a simple question every 15–25 gathers; 3 misses pause gathering for 1 hour |
| `/tutorial` | The Old Master's eleven lessons (one is on herbs and pills) on how to play, paged with Back / Next buttons and a jump menu |
| `/index [section] [realm]` | The Jianghu Compendium: every beast (by realm), technique manual, weapon, chest, pill (with recipes) and herb (with look-alikes and how to /gather), read from the game data. A menu switches section; Back / Next turn pages |
| `/bestiary [realm]` | A realm's six beasts with tier, role and stats against you, and the Beast Kings you've slain |

### Text commands with "m"

Every command above also works as a normal message starting with **`m`** and a space, for when
Discord's `/` menu is acting up: `m start`, `m gather`, `m index herbs`, `m internal qi`, `m index`, `m cooldown`,
`m profile @someone`, `m seclusion 12`, `m practice Iron Fist`, `m bestiary Martial Warrior`,
`m admin give @someone lotus_coins:500`. Capital letters don't matter. Options go in order, or by
name like the slash menu (`m spar technique:Iron Fist`). `m help` lists them all. Shortcuts:
`m qi`, `m cd`, `m bal`, `m inv`, `m p`, `m g` (= `m gather`), `m herbs` and `m pills`
(= `m index herbs` / `m index pills`).

Replies that are private with a slash command are normal messages with `m`, since only slash
commands can reply privately. To read `m` messages in servers, the bot needs **Message Content
Intent** (see Run it). In DMs with the bot they work either way.

Finding an **Elite Lair** or **Beast King Den** in /explore posts a hunt call with Join / Leave /
Start buttons. It stays open 30 / 60 minutes; the finder starts the fight and every winner rolls
their own chest. Beating a Beast King counts toward the Martial King and Martial Saint requirements.

Rare finds are announced in the channel: Divine weapons, Heaven manuals, the Heaven-Defying Pill
(0.05% in Jade Chests, raises talent one rank), Saint and Divine talents, and Beast King kills.

## Gameplay defaults

The design docs leave some things open. Until they are decided, the bot uses these
(each is a named constant, marked DEFAULT, in `bot/`):

- **Fights are automatic.** The Strike / Guard / Break fight screen is not designed yet, so
  beast and bandit fights play out by themselves with the stats.md damage formula and give a
  short report. Your attack technique is used every turn; your defense technique catches about
  a third of the hits. Each use gives +20 mastery EXP.
- **Coins:** chests hold 10–25 (Wooden), 30–60 (Bronze), 80–150 (Silver), 200–400 (Jade) Lotus
  Coins at Mortal; Normal beasts give 3–8, beaten bandits 10–20. All amounts double each realm.
- **Team hunts** fight on their own like solo fights. The beast telegraphs a charged attack every 3rd
  turn (1.5× a normal hit, ignores the 30% cap); fighters with a defense technique guard it 75% of the
  time. Up to 8 fighters. Winners get 20–40 (Elite) or 60–120 (King) Lotus Coins × realm scale;
  losing injures everyone for 1 hour. A full team usually wins; a short-handed one rarely does.
- **/recharge** shows the packages only. Real-money purchases must go through Discord's app
  monetization (economy.md), which needs setting up in the Discord Developer Portal first.
- **Physician** costs 1 Lotus Coin per minute of injury left (× realm scale).
- **Discard** removes items for good, with no refund. It asks first and refuses equipped items.
- **Transactions:** every Lotus Coin and Moon Pearl change is written to a ledger (last 100 kept per player); the Purse tab shows the newest 8.
- **Not built because the docs leave them undesigned:** player trading / market, armor and artifacts, character titles, a numeric level,
  Divine pity, profile card themes, Contribution Points and Spirit Stones, regions and weather.
- **Defeat** keeps chests as well as manuals and weapons; half the coins and herbs found are lost.
- **Merchant** sells one Qi pill (Mortal grade at tier 1, Yellow at tier 2, Mystic above) for
  40 / 120 / 400 coins and one herb for 10 (× realm scale).
- **Herbs** are the alchemy herbs in `alchemy.py` (docs/alchemy.md): 4 types × 5 tiers, each with an age.
  They come from /gather, Herb Patches in /explore (1–3 of your tier) and merchants (a 10-year herb of your tier).
  They stack by kind and age in the Herbs bag tab. The old herbs (Dew Lotus Petal, Tiger Bone Moss, ...) are gone:
  any left in a bag turn into the closest 10-year Mortal herb when the bot starts.
- **/gather** isn't blocked by injuries, only by seclusion. HP isn't stored outside fights, so a look-alike's 5% HP
  only shows on the gathering message. Gathering is flagged for review (logged and saved in `gather_flag`, never a
  ban) at an average pick under 0.3s over 50 gathers or 12+ hours non-stop. Chests don't drop herbs yet (no odds in the docs).
- **/craft** (the alchemy minigame), Beast Cores and alchemist ranks are designed in docs/alchemy.md but not built yet.
  Crafted-only pills (Qi Burst, Mending, Cleansing, Breakthrough) show in /index with their recipes.
- **Learning a manual** is instant and equips it in that type's slot (the old technique stays learned).
  A duplicate of a learned manual gives 100 mastery EXP (× grade EXP multiplier).
- **Breakthroughs**: Qi stops at a full bar at a bottleneck until you use `/breakthrough`.
  Mortal → Martial Apprentice always succeeds. A failed phase bottleneck costs 20% of current Qi
  but no injury.
- **Challenges** built: Read the Master, Endless Waves, Ambush and Find the Weakness (tiers 1–2).
  Tiers 3–5 use these four until Rhythm of the Blade and Sword Formation are built.
  Endless Waves starts at 3.0s per wave and gets 8% faster each wave. Timed buttons allow 1 extra
  second for Discord lag.
- **Ambush** (SHOAIB's rule): 3 HP, and your one counter stops every attacker whose move it beats.
  Ambush uses Read the Master's time per step.
- **Find the Weakness** score: solved in 1–2 tries = 100%, falling to 50% on the last try; unsolved = 0.
  60 seconds per move press.
- **Mastery stages** only rise by passing a trial (/spar with the technique). EXP stops at a full bar.
- **/spar**: the master repeats a 3–4 move rhythm (15% surprises) and shows a tell half the time.
  Winning an exchange lands a hit; ties hurt both a little. +30 EXP per well-timed use, +100 to each
  well-timed technique on a win. 15 exchanges; if time runs out, whoever is in better shape wins.
  60 seconds per move, then you forfeit. Not while injured or secluded.
- **Seclusion and passive Qi** use the Qi Rate at the moment you collect. Passive Qi does not gather
  during seclusion; entering seclusion banks your passive Qi first.
- **Qi Rate** now includes the best equipped technique, an active Qi pill and a Blessed Land.

## Run it

1. Create an application and bot at https://discord.com/developers/applications,
   copy the bot token, and invite it with the `bot` and `applications.commands` scopes.
   On the **Bot** tab, turn on **Message Content Intent** and save (needed for `m` text
   commands in servers). If it is off, the bot still starts, logs a warning, and `m` commands
   only work in DMs.
2. From the repo root:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env      # then paste your token into .env
   python -m bot
   ```

Commands always sync globally, so they work in every server the bot is in **and in a
direct message with the bot**. Discord can take up to an hour to show new or changed
commands (usually it's a few minutes). If you see an old command list, restart Discord (Ctrl+R).

`DISCORD_GUILD_ID` is optional. Older versions synced a separate copy of the commands to that
server; if it is set, the bot now removes that copy so commands are not listed twice.

Run **one** copy of the bot. Two copies would both answer every `m` command, so:

- A second `python -m bot` on the same computer stops at once with a message, even from another
  folder (it locks a file next to the database and one in the temp folder named after a hash of the token).
- Copies that share a database answer each `m` message only once (the message is claimed in the database first).
- `m ping` answers with the computer name, process number, start time and code version. Two answers
  mean two copies are running, and the computer name tells you where the other one is.
- A copy on another computer or a hosting service can't be stopped from here. Stop it there, or
  reset the token in the Developer Portal (Bot tab > Reset Token), which logs out every copy, and put
  the new token in `.env`.

### Lag and double clicks

- `/explore`, `/train`, `/practice` and `/spar` start their cooldown the moment the session starts,
  and mark the session as running in the same step, before the bot waits on anything. A second
  send of the same command (slash or `m`) is turned away, and a restart can't skip the cooldown.
  The cooldown is set again when the session ends, so the footer's "again in N minutes" still holds.
- Every button and menu on a player's view handles one click at a time. A double click during lag
  gets "still being handled", and a button from an earlier step (or a finished view) does nothing.
  This covers confirmations (breakthrough, reroll, physician, shop, blessings), so nothing is
  bought or claimed twice. Starting a team hunt also only happens once.
- `/seclusion` checks again under the database lock that you are not already in seclusion,
  exploring or sparring.

### Playing in DMs

Open a DM with the bot (click its name, then **Message**) and type `/`. Every command works there.
You must share at least one server with the bot. In a DM, lairs found in `/explore` are hunted alone,
since nobody else can see the call; explore in a server to gather a team.

The token is read only from the `DISCORD_TOKEN` environment variable (or the
git-ignored `.env`). Never commit it.

## Fonts

Run `python scripts/render_sheet.py` to save every Character Sheet card for a made-up player in `previews/`,
and `python scripts/render_results.py` for the /spar (blue), /train (green) and /explore (amber) result cards.

The cards look best with `Cinzel.ttf`, `Inter.ttf` and `NotoSerifSC-Bold.otf`
(all free on Google Fonts) in the `fonts/` folder at the repo root (see `fonts/README.md`). Without them the
renderers fall back to DejaVu Sans and the Chinese characters show as boxes.

## Tests

```bash
pip install pytest
python -m pytest tests
```
