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
| `/train` | A timed training challenge with the master. The score becomes Internal Qi; layers inside a phase open automatically. 60 min cooldown |
| `/meditate` | Collects the Qi you gathered passively at your Qi Rate (stores up to 12 hours) |
| `/seclusion [hours]` | Enter closed-door seclusion for 8–24 hours at ×2 Qi Rate (no exploring or sparring). Run it again to check on it or leave early (early = no ×2) |
| `/breakthrough` | When your Qi bar is full at a phase bottleneck (90%) or realm gate (70%), attempt it. Shows the chance and risk first |
| `/practice <technique>` | A training challenge for one technique's mastery EXP (40 × score). 30 min cooldown; 5 full sessions a day, then 50%, then 10% |
| `/spar [technique]` | A turn-by-turn fight with a master. EXP only for techniques used at the right moment. With a technique whose bar is full, it is that technique's **mastery trial**. 2 h cooldown |
| `/techniques` | All learned techniques with effects, power and mastery bars; equip or unequip (flex slot from Martial Warrior) |
| `/equipment` | Your weapon, base → final stats, and menus to swap or remove your weapon |

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
