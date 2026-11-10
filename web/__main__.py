"""
Entry point: python -m web  (run from the repo root, like the bot).

Environment variables (put them in .env, which is git-ignored):
  DISCORD_CLIENT_ID      required — Discord Developer Portal > your app > OAuth2 > Client ID
  DISCORD_CLIENT_SECRET  required — same page, Client Secret. Never commit it or share it.
  WEB_REDIRECT_URI       optional — defaults to http://localhost:8000/callback (add it under OAuth2 > Redirects)
  WEB_SESSION_SECRET     optional — any long random text; keeps players logged in across restarts
  MORTAL_DB_PATH         optional — the same SQLite file the bot uses
  WEB_HOST, WEB_PORT     optional — default 127.0.0.1 and 8000 (only your own computer can open it)
"""
import logging
import os
import sys

import uvicorn

from bot.__main__ import load_dotenv
from .app import ROOT, Settings, create_app


def settings_from_env():
    load_dotenv(os.path.join(ROOT, ".env"))
    client_id = os.environ.get("DISCORD_CLIENT_ID", "").strip()
    secret = os.environ.get("DISCORD_CLIENT_SECRET", "").strip()
    if not client_id or not secret:
        sys.exit("DISCORD_CLIENT_ID and DISCORD_CLIENT_SECRET are not set. Add them to .env "
                 "(Discord Developer Portal > your app > OAuth2). See docs/web.md.")
    session_secret = os.environ.get("WEB_SESSION_SECRET", "").strip()
    if not session_secret:
        logging.getLogger("mortal-ascent-web").warning(
            "WEB_SESSION_SECRET is not set: everyone is logged out when the website restarts. "
            "Add any long random text to .env to keep logins.")
    db_path = os.environ.get("MORTAL_DB_PATH", "mortal_ascent.db")
    if not os.path.isabs(db_path):
        db_path = os.path.join(ROOT, db_path)
    return Settings(client_id=client_id, client_secret=secret,
                    redirect_uri=os.environ.get("WEB_REDIRECT_URI", "http://localhost:8000/callback").strip(),
                    db_path=db_path, session_secret=session_secret)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = settings_from_env()
    host = os.environ.get("WEB_HOST", "127.0.0.1")
    port = int(os.environ.get("WEB_PORT", "8000"))
    print(f"\n  Mortal Ascent website: open http://localhost:{port} in your browser\n")
    uvicorn.run(create_app(settings), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
