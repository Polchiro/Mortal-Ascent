# Mortal Ascent in a box (docs/docker.md).
# One image runs either the website (the default) or the Discord bot:
#   docker build -t mortal-ascent .
#   docker run --env-file .env -p 8000:8000 -v ./data:/data mortal-ascent            # website
#   docker run --env-file .env -v ./data:/data mortal-ascent python -m bot            # Discord bot
# Easier: docker compose up -d   (runs both, see docker-compose.yml)
#
# Secrets are NOT inside the image: .env is left out (.dockerignore) and passed in when the box starts.
# The database lives outside the box in /data, so rebuilding or replacing the box never loses players.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MORTAL_DB_PATH=/data/mortal_ascent.db \
    WEB_HOST=0.0.0.0 \
    WEB_PORT=8000

WORKDIR /app

# Install the packages first, so changing game code doesn't re-download them on every build.
COPY requirements.txt requirements-web.txt ./
RUN pip install -r requirements-web.txt

COPY . .

# Run as an ordinary user, not the all-powerful root, so a bug in the game can't take over the box.
RUN useradd --create-home --uid 10001 game \
    && mkdir -p /data && chown game:game /data
USER game

VOLUME ["/data"]
EXPOSE 8000

# Docker marks the box "unhealthy" if the website stops answering.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('WEB_PORT', '8000') + '/healthz', timeout=4)" || exit 1

CMD ["python", "-m", "web"]
