# Mortal Ascent bot

Discord bot for Mortal Ascent, built on discord.py with SQLite player storage.
It reuses the game constants (`realms.py`, `stats.py`, `training.py`, `economy.py`, …)
and the card renderers (`profile_card.py`, `balance_card.py`, `inventory_card.py`) from the repo root.

## Commands

| Command | What it does |
|---|---|
| `/start` | Creates your character: rolls a talent, Mortal 1st Layer, Iron Fist + Horse Stance Guard, 50 Lotus Coins |
| `/profile [member]` | Sends the ink-wash profile card (your Discord avatar sits in the Qi ring) |
| `/balance` | Sends the purse card: Lotus Coins, Moon Pearls, active Heavenly Blessing |
| `/inventory [category]` | Sends the bag card. Menus under it switch tab and page, and use an item: open a chest, equip a weapon, learn a manual, take a Qi pill |
| `/explore` | A 5-step expedition: pick a path from its clue, face what is there, then go deeper or return with the loot. 45 min cooldown |
| `/train` | A timed training challenge with the master (Read the Master or Endless Waves). The score becomes Internal Qi; layers and breakthroughs happen automatically. 60 min cooldown |

## Gameplay defaults

The design docs leave some things open. Until they are decided, the bot uses these
(each is a named constant, marked DEFAULT, in `bot/`):

- **Fights are automatic.** The Strike / Guard / Break fight screen is not designed yet, so
  beast and bandit fights play out by themselves with the stats.md damage formula and give a
  short report. Your attack technique is used every turn; your defense technique catches about
  a third of the hits. Each use gives +20 mastery EXP.
- **Coins:** chests hold 10–25 (Wooden), 30–60 (Bronze), 80–150 (Silver), 200–400 (Jade) Lotus
  Coins at Mortal; Normal beasts give 3–8, beaten bandits 10–20. All amounts double each realm.
- **Elite Lairs and Beast King Dens** are found but cannot be fought yet (team hunts come later).
- **Defeat** keeps chests as well as manuals and weapons; half the coins and herbs found are lost.
- **Merchant** sells one Qi pill (Mortal grade at tier 1, Yellow at tier 2, Mystic above) for
  40 / 120 / 400 coins and one herb for 10 (× realm scale).
- **Herbs** are Spirit Grass, Dew Lotus Petal, Red Ginseng Root, Moonlight Fern and Tiger Bone Moss.
  They have no use until alchemy exists.
- **Learning a manual** is instant and equips it in that type's slot (the old technique stays learned).
  A duplicate of a learned manual gives 100 mastery EXP (× grade EXP multiplier).
- **Breakthroughs** happen as soon as the Qi bar fills; there is no `/breakthrough` command yet.
  Mortal → Martial Apprentice always succeeds. A failed phase bottleneck costs 20% of current Qi
  but no injury.
- **/train** has Read the Master and Endless Waves (everything tier 1 uses). Higher realms get the
  same two at their tier's numbers until Ambush, Find the Weakness, Rhythm of the Blade and Sword
  Formation are built. Endless Waves starts at 3.0s per wave and gets 8% faster each wave.
  Timed buttons allow 1 extra second for Discord lag.
- **Qi Rate** now includes the best equipped technique, an active Qi pill and a Blessed Land.

## Run it

1. Create an application and bot at https://discord.com/developers/applications,
   copy the bot token, and invite it with the `bot` and `applications.commands` scopes.
2. From the repo root:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env      # then paste your token into .env
   python -m bot
   ```

Set `DISCORD_GUILD_ID` to your test server's ID so commands show up instantly;
without it they sync globally, which can take up to an hour.

The token is read only from the `DISCORD_TOKEN` environment variable (or the
git-ignored `.env`). Never commit it.

## Fonts

The cards look best with `Cinzel.ttf`, `Inter.ttf` and `NotoSerifSC-Bold.otf`
(all free on Google Fonts) in the `fonts/` folder at the repo root (see `fonts/README.md`). Without them the
renderers fall back to DejaVu Sans and the Chinese characters show as boxes.

## Tests

```bash
pip install pytest
python -m pytest tests
```
