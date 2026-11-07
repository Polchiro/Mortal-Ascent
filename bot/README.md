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
| `/profile [member]` | Opens your **Character Sheet** on the Profile tab: realm, phase and layer, HP / Attack / Defense, Internal Qi, equipped techniques, the Gear row (weapon, armor, two artifacts), your avatar as the portrait. Buttons under it switch to the Techniques, Equipment, Inventory and Purse tabs. With a member it shows only their Profile card, with their purse hidden |
| `/balance` | Opens the sheet on the Purse tab: Lotus Coins, Moon Pearls, active Heavenly Blessing and your last 8 transactions |
| `/inventory [category]` | Opens the sheet on the Inventory tab (Chests, Manuals, Weapons, Armor, Artifacts, Pills, Herbs, Materials): a grid of items by category, pages, and an Inspect panel. Pick an item to Open, Learn, Take, Equip, Unequip or Discard it (Discard asks first, and never works on an equipped item) |
| `/explore` | A 5-step expedition: pick a path from its clue, face what is there, then go deeper or return with the loot. 30 min cooldown |
| `/train` | A timed training challenge with the master. The score becomes Internal Qi; layers inside a phase open automatically. 60 min cooldown |
| `/seclusion [hours]` | Enter closed-door seclusion for 8–24 hours at ×2 Qi Rate (no exploring or sparring). Run it again to check on it or leave early (early = no ×2) |
| `/internal qi` | Sends the dantian card (same crimson-and-gold style as the Character Sheet, with the dantian orb filling as your bar fills): Qi bar (plus Qi waiting behind a bottleneck), Qi Rate, time to a full bar, the next gate, your cultivation status, and every Qi source (talent, technique, blessing, pill, Blessed Land, seclusion, pill toxicity) with the full formula |
| `/breakthrough` | When your Qi bar is full at a phase bottleneck (90%) or realm gate (70%), attempt it. Shows the chance and risk first |
| `/practice <technique>` | A training challenge for one technique's mastery EXP (40 × score). 30 min cooldown; 5 full sessions a day, then 50%, then 10% |
| `/spar [technique]` | A turn-by-turn fight with a master. EXP only for techniques used at the right moment. With a technique whose bar is full, it is that technique's **mastery trial**. 2 h cooldown |
| `/duel @player` | A friendly PvP duel on the fight screen: Accept/Decline for 60 s, both fight at the lower player's realm and layer, picks are secret. No rewards, no risk; wins/losses show on the Profile. Rules: docs/pvp.md |
| `/techniques` | Opens the sheet on the Techniques tab: the Attack, Defense and Flex sockets, then every learned technique with effect, power, cooldown and mastery. Equip or unequip (not during a fight) |
| `/equipment` | Opens the sheet on the Equipment tab: your four gear slots (weapon, armor, two artifacts), base → final stats with every buff's source, your artifacts' effects, and menus to swap or remove gear (not during a fight) |
| `/shop` | Moon Pearl shop: Heavenly Fate Reroll (never lower), Qi pills, +20 bag slots, name change |
| `/blessing` | The eight Heavenly Blessing tiers; buy one with Moon Pearls (same tier adds 30 days) |
| `/recharge` | Shows the Moon Pearl packages. Buying is not switched on (see below) |
| `/reroll` | Fate Reroll with Lotus Coins: 10,000, then ×1.5 each time; normal odds, can go lower |
| `/physician` | Pay Lotus Coins to heal an injury right away |
| `/settings [qi_pings]` | Your settings. `qi_pings:off` stops the "your Qi is full: use /breakthrough!" mention (on by default) |
| `/cooldown` | Every timer in one place: explore, train, practice and spar cooldowns, mastery trials, daily practice/spar counts, seclusion, injury, pill toxicity, blessing, Qi pill and blessed land. Times show in your own time zone |
| `/admin reset [member]` | **Owner/admins only.** Clears all cooldowns and daily limits, heals injuries, finishes a seclusion timer, frees a stuck session |
| `/admin give [member] [item] [amount] [lotus_coins] [moon_pearls] [qi] [quality] [age] [patterns]` | **Owner/admins only.** Gives any item (start typing its name in **item**: weapons, armor, artifacts, materials, herbs, pills, manuals, chests) and/or coins, pearls or Qi. `/admin item` does the same for items only |
| `/admin give_weapon`, `give_armor`, `give_artifact`, `give_herb`, `give_pill`, `give_material` | **Owner/admins only.** One command per kind of item, with pick lists for the type and tier/grade (no typing needed). Each has `amount` and `member`; herbs have `age`, pills `patterns`, weapons and armor `quality` |
| `/admin item <item> [amount] [member] [quality] [age] [patterns]` | **Owner/admins only.** Gives any item in the game: weapons, armor, artifacts, forging materials, Beast Cores, herbs, pills, manuals, chests. Start typing a name and pick it from the list. Text version: `m admin item Iron Sword amount:2` |
| `/admin duelstats` | **Owner/admins only.** Duel balance: each technique's and basic move's pick count and win rate (docs/pvp.md) |
| `/gather` | Gather herbs for alchemy, no limit. One message updates in place: the bot names a herb and describes it, you pick the plant that matches before time runs out (10s at Mortal down to 6s at Heaven). Poisonous look-alikes cost 5% HP. Herbs have an age (10 to 1000 years); 100-year+ herbs fight back (6 choices, 3s less). Right picks in a row build the Herbal Insight streak (more old herbs). A Wandering Spirit asks a simple question every 15–25 gathers; 3 misses pause gathering for 1 hour |
| `/craft` | The alchemy cauldron (docs/alchemy.md). Pick a pill whose herbs you have (it shows what is ready, what is missing, and which herbs it will use; a button switches between youngest and oldest herbs), then refine it stage by stage, every decision on a timer: 🔥 keep the heat in a hidden safe zone, 🌿 add the herbs in the order the clues give, ☯️ balance Yin and Yang, 💊 condense at the perfect pulse, 🔒 seal the Beast Core (Breakthrough pills). The score becomes **1–9 pill patterns** (capped by herb age; 9 needs the ⚡ Pill Tribulation and is announced). Gives alchemy EXP toward ranks 1st–9th Grade. No cooldown. While a craft runs, the message shows the Alchemy Chamber card (cards/alchemy.py) with round icon buttons, edited after every decision |
| `/tutorial` | The Old Master's eighteen lessons (four on herbs and /craft, four on /forge, written step by step) on how to play, paged with Back / Next buttons and a jump menu |
| `/index [section] [realm] [search]` | The Jianghu Compendium: every beast (by realm), technique manual, weapon, armor, artifact, chest, pill (with recipes) and herb (with look-alikes and how to /gather), read from the game data. Each page is an image card (bot/compendium.py, cards/compendium.py) with a text copy under it. Menus: section, then tier (Overview first); Back / Next only when a tier needs two cards. `search:` jumps to an item (`m index Qilin` works too) |
| Forging materials | Used by `/forge`: ~70 material types drop from the new ⛏️ Ore Vein encounter in /explore, beasts, /gather, chests, /craft, /practice, /train, breakthroughs and the Moon Pearl shop (Seal Stone). They show in /inventory → Materials (Base, Bindings, Essences, Fuel & Liquids) and use no bag slots. `/index materials` lists them; `/index` Passives sections list every gear passive. Rules: docs/forge.md |
| `/forge` | The blacksmith's forge (docs/forge.md). Pick a weapon, armor or artifact, then **Enchant** (fill an empty slot), **Reroll** (forge every slot again) or **Replace** (Treasure/Divine: lock a slot with a Seal Stone). Add an essence (picks the passive family), fuel (wider Ignite zone) and quench liquid (wider Quench window) if you have them, see the cost, then play five timed stages: 🔥 Ignite, 🌡️ Heat, 🔨 Hammer, 💧 Quench, ✨ Inscribe. The score (0–100) gives the passive's rarity, capped by the gear tier and essence. Below 50 the forge fails: materials lost, gear safe. Gives blacksmith EXP (ranks 1st–9th Grade). A Mythical passive is announced. The message shows the Forge Hall card (cards/forge.py) with round icon buttons, edited after every decision. Forged passives work in fights, duels (half strength) and everyday actions (bot/passives.py) and show on the Equipment card in rarity colours |
| `/bestiary [realm]` | A realm's six beasts with tier, role and stats against you, and the Beast Kings you've slain |

### Text commands with "m"

Every command above also works as a normal message starting with **`m`** and a space, for when
Discord's `/` menu is acting up: `m start`, `m gather`, `m craft`, `m forge`, `m index herbs`, `m internal qi`, `m index`, `m cooldown`,
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

Rare finds are announced in the channel: Divine weapons, armor and artifacts, Heaven manuals, the Heaven-Defying Pill
(0.05% in Jade Chests, raises talent one rank), Saint and Divine talents, and Beast King kills.

## Gameplay defaults

The design docs leave some things open. Until they are decided, the bot uses these
(each is a named constant, marked DEFAULT, in `bot/`):

- **Fights are turn-based** (docs/combat.md): explore beasts, bandits and team hunts use the
  interactive fight screen. All fight numbers are in `battle.py`.
- **Coins:** chests hold 10–25 (Wooden), 30–60 (Bronze), 80–150 (Silver), 200–400 (Jade) Lotus
  Coins at Mortal; Normal beasts give 3–8, beaten bandits 10–20. All amounts double each realm.
- **Team hunts** are played on the same fight screen; every member picks secretly each turn. Up to 8
  fighters. Winners get 20–40 (Elite) or 60–120 (King) Lotus Coins × realm scale; losing injures
  everyone for 1 hour; fighters who flee get nothing and are not injured.
- **/recharge** shows the packages only. Real-money purchases must go through Discord's app
  monetization (economy.md), which needs setting up in the Discord Developer Portal first.
- **Physician** costs 1 Lotus Coin per minute of injury left (× realm scale).
- **Discard** removes items for good, with no refund. It asks first and refuses equipped items.
- **Transactions:** every Lotus Coin and Moon Pearl change is written to a ledger (last 100 kept per player); the Purse tab shows the newest 8.
- **Not built because the docs leave them undesigned:** player trading / market, character titles, a numeric level,
  Divine pity, profile card themes, Contribution Points and Spirit Stones, regions and weather.
- **Defeat** keeps chests as well as manuals and gear; half the coins and herbs found are lost.
- **Merchant** sells one Qi pill (Mortal grade at tier 1, Yellow at tier 2, Mystic above) for
  40 / 120 / 400 coins and one herb for 10 (× realm scale).
- **Herbs** are the alchemy herbs in `alchemy.py` (docs/alchemy.md): 4 types × 5 tiers, each with an age.
  They come from /gather, Herb Patches in /explore (1–3 of your tier) and merchants (a 10-year herb of your tier).
  They stack by kind and age in the Herbs bag tab. The old herbs (Dew Lotus Petal, Tiger Bone Moss, ...) are gone:
  any left in a bag turn into the closest 10-year Mortal herb when the bot starts.
- **/gather** isn't blocked by injuries, only by seclusion. HP isn't stored outside fights, so a look-alike's 5% HP
  only shows on the gathering message. Gathering is flagged for review (logged and saved in `gather_flag`, never a
  ban) at an average pick under 0.3s over 50 gathers or 12+ hours non-stop. Chests don't drop herbs yet (no odds in the docs).
- **/craft** follows docs/alchemy.md. Choices the doc leaves open: Stoke/Fan move the heat 12°, normal drift is ±5°
  and a hinted spike is 12–18°; Stage 2's clues name each herb's place (a misleading clue names a wrong one); Yin
  and Yang count as perfect within 50 ± 5; Condense scores 100% at "the light trembles", 70% one pulse early, down
  to 15%, and 20% if it cracks; Condense counts double in the final score ("decides most of the patterns"); Seal
  the Core is 3 balance moves and passes within 12 points of 50/50; the Pill Tribulation is 3 lightning strikes to
  block. Herbs and the core are used up when the craft begins. Walking away lets every decision time out.
- **Crafted pills**: Qi and Qi Burst pills below your realm's grade give half (shop pills too). Mending pills shorten
  an injury (HP isn't stored outside fights). Cleansing pills always remove at least 1 toxicity. Breakthrough pills
  are used by /breakthrough at a **realm** gate: the best one of your realm's grade or higher, used up either way.
- **Beast Cores** drop from Normal beasts in /explore (5%) and from Elite (15%) and Beast King (50%) team hunts,
  graded by the beast's realm. They sit in the Materials tab.
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
- **Passive Qi** has no storage limit and is banked every minute by a background task (bot/passive.py)
  and before every command. It does not gather during seclusion; entering seclusion banks it first.
- **Qi at a gate is never lost**: above a full bar it goes to `qi_overflow` and flows into the next
  layers after a successful breakthrough. A failed breakthrough keeps it.
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
