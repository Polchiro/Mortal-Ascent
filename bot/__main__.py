"""
Entry point: python -m bot  (run from the repo root so the game modules import).

Environment variables:
  DISCORD_TOKEN    required — the bot token. Never commit it.
  DISCORD_GUILD_ID optional — sync slash commands to one server instantly (good for testing)
  MORTAL_DB_PATH   optional — SQLite file, defaults to mortal_ascent.db in the repo root
"""
import logging
import os
import sys

import discord

from . import instance
from .client import MortalAscent

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_dotenv(path):
    """Minimal .env loader so no extra dependency is needed. Real env vars win."""
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv(os.path.join(ROOT, ".env"))
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        sys.exit("DISCORD_TOKEN is not set. Copy .env.example to .env and fill it in.")
    guild = os.environ.get("DISCORD_GUILD_ID")
    db_path = os.environ.get("MORTAL_DB_PATH", os.path.join(ROOT, "mortal_ascent.db"))
    guild_id = int(guild) if guild else None
    lock = instance.acquire(db_path, token)
    if lock is None:
        pid = instance.holder(db_path, token)
        how = (f"It is process {pid}. To close it, run:  taskkill /PID {pid} /F" if os.name == "nt" and pid else
               f"It is process {pid}. To close it, run:  kill {pid}" if pid else
               "Close it with Ctrl+C in its window, or end python.exe in Task Manager (Details tab).")
        sys.exit("Mortal Ascent is already running on this computer (another window, terminal or folder, "
                 "maybe hidden in the background). Running two copies makes every \"m\" command happen "
                 f"twice, so this one will not start.\n{how}\nThen run python -m bot again.")
    logging.getLogger("mortal-ascent").info("This copy: %s", instance.describe())
    try:
        MortalAscent(db_path, guild_id=guild_id).run(token, log_handler=None)
    except discord.PrivilegedIntentsRequired:
        logging.getLogger("mortal-ascent").warning(
            "Message Content Intent is off, so \"m\" text commands only work in DMs with the bot. "
            "To use them in servers: Discord Developer Portal > your app > Bot > turn on "
            "\"Message Content Intent\" > Save, then restart the bot. Starting without it for now.")
        MortalAscent(db_path, guild_id=guild_id, message_content=False).run(token, log_handler=None)


if __name__ == "__main__":
    main()
