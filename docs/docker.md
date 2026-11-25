# Docker — Mortal Ascent in a box

Docker packs the game, Python and every package it needs into one **image**. Any computer or server with
Docker can run it the same way, without installing Python by hand. Playing locally with `python -m web`
still works exactly as before; Docker is optional and mostly for hosting the game online.

## Files

| File | What it does |
|---|---|
| `Dockerfile` | The recipe for the image: Python 3.13, the packages, the game's code |
| `.dockerignore` | What is never put in the image: `.env` (secrets), the database, `.git`, tests |
| `docker-compose.yml` | Runs two boxes from the one image: the website and the Discord bot |

## Safety

- **No secrets in the image.** `.env` is left out and handed to the box only when it starts (`env_file`).
  The image can be shared or uploaded to a host without leaking your Discord token or keys.
- **The database is outside the box**, in the `data/` folder (`/data` inside). Rebuilding or replacing the
  box never loses players. `data/` is git-ignored.
- **Runs as an ordinary user** (`game`), not the all-powerful root user.
- **Only your own computer can open the website** (`127.0.0.1`, on the port in `WEB_PORT`, default 8000). When the game is hosted online, the
  host's HTTPS goes in front of it.
- **Health check:** Docker opens `/healthz` every 30 seconds and marks the box unhealthy if the site
  stops answering or the database won't open. `/healthz` shows nothing about players.

## First time

1. Install Docker Desktop (Windows/Mac) and start it.
2. Make a `data` folder in the repo and **copy your `mortal_ascent.db` into it** if you want your current
   players. Otherwise a new empty database is made there.
3. Make sure `.env` has `DISCORD_TOKEN`, `DISCORD_CLIENT_ID` and `DISCORD_CLIENT_SECRET`.
4. Stop `python -m web` and the bot if they're running (two copies of the bot would answer twice).
5. In the repo folder:

```
docker compose up -d --build
```

Open http://localhost:8000 (or the port in `WEB_PORT` in your `.env`, e.g. 8765). The first build downloads Python and the packages and takes a few minutes;
later builds reuse them.

## Everyday

| Want to | Command |
|---|---|
| See what they print | `docker compose logs -f` (Ctrl+C stops watching, not the game) |
| Update after `git pull` | `docker compose up -d --build` |
| Stop | `docker compose down` |
| Restart | `docker compose restart` |
| Check health | `docker compose ps` |

## Notes

- While running in Docker, the database in use is `data/mortal_ascent.db`, not the one in the repo root.
- The website and the bot share the same database file, just as they do without Docker.
- To run only one of them: `docker compose up -d web` or `docker compose up -d bot`.
