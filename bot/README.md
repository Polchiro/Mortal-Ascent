# Mortal Ascent bot

Discord bot for Mortal Ascent, built on discord.py with SQLite player storage.
It reuses the game constants (`realms.py`, `stats.py`, `training.py`, `economy.py`, …)
and the card renderers (`profile_card.py`, `balance_card.py`) from the repo root.

## Commands

| Command | What it does |
|---|---|
| `/start` | Creates your character: rolls a talent, Mortal 1st Layer, Iron Fist + Horse Stance Guard, 50 Lotus Coins |
| `/profile [member]` | Sends the ink-wash profile card (your Discord avatar sits in the Qi ring) |
| `/balance` | Sends the purse card: Lotus Coins, Moon Pearls, active Heavenly Blessing |

## Run it

1. Create an application and bot at https://discord.com/developers/applications,
   copy the bot token, and invite it with the `bot` and `applications.commands` scopes.
2. From the repo root:

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r bot/requirements.txt
   cp .env.example .env      # then paste your token into .env
   python -m bot
   ```

Set `DISCORD_GUILD_ID` to your test server's ID so commands show up instantly;
without it they sync globally, which can take up to an hour.

The token is read only from the `DISCORD_TOKEN` environment variable (or the
git-ignored `.env`). Never commit it.

## Fonts

The cards look best with `Cinzel.ttf`, `Inter.ttf` and `NotoSerifSC-Bold.otf`
(all free on Google Fonts) in a `fonts/` folder at the repo root. Without them the
renderers fall back to DejaVu Sans and the Chinese characters show as boxes.

## Tests

```bash
pip install pytest
python -m pytest tests
```
