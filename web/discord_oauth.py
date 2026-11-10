"""
Discord login (OAuth2, "identify" scope only) for the website. docs/web.md, "Logging in".

The player clicks "Continue with Discord", Discord shows its own permission page, then sends the
player back to our /callback with a one-time code. We swap that code for a token and ask Discord
who the player is. We only ever get their Discord ID, username and avatar: no email, no messages,
no password. The token is used once and not stored.

Plain urllib, so the website needs no extra HTTP library.
"""
import json
import secrets
import urllib.parse
import urllib.request

AUTHORIZE_URL = "https://discord.com/oauth2/authorize"
TOKEN_URL = "https://discord.com/api/oauth2/token"
ME_URL = "https://discord.com/api/users/@me"
SCOPE = "identify"
TIMEOUT = 10                       # seconds to wait for Discord
USER_AGENT = "MortalAscentWeb (https://github.com/Polchiro/Mortal-Ascent, 1.0)"


class LoginError(Exception):
    """Discord refused the code or could not be reached. The message is safe to show."""


def new_state():
    """A random value we remember in the session and check on the way back (stops forged logins)."""
    return secrets.token_urlsafe(24)


def authorize_url(client_id, redirect_uri, state):
    query = urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code",
        "scope": SCOPE, "state": state, "prompt": "none",
    })
    return f"{AUTHORIZE_URL}?{query}"


def _request(req):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:                # HTTPError, URLError, timeout, bad JSON
        raise LoginError("Discord did not accept the login. Please try again.") from e


def exchange_code(client_id, client_secret, redirect_uri, code):
    """The one-time code -> an access token (string)."""
    body = urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret, "grant_type": "authorization_code",
        "code": code, "redirect_uri": redirect_uri,
    }).encode()
    req = urllib.request.Request(TOKEN_URL, data=body, method="POST", headers={
        "Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT})
    token = _request(req).get("access_token")
    if not token:
        raise LoginError("Discord did not accept the login. Please try again.")
    return token


def fetch_user(access_token):
    """{'id': int, 'username': str, 'avatar': str | None} for the logged-in player."""
    req = urllib.request.Request(ME_URL, headers={"Authorization": f"Bearer {access_token}", "User-Agent": USER_AGENT})
    me = _request(req)
    try:
        return {"id": int(me["id"]), "username": me.get("global_name") or me["username"], "avatar": me.get("avatar")}
    except (KeyError, TypeError, ValueError) as e:
        raise LoginError("Discord did not accept the login. Please try again.") from e


def avatar_url(user_id, avatar_hash, size=256):
    """The player's Discord picture, or None when they have none (the page shows our emblem)."""
    if not avatar_hash:
        return None
    return f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png?size={size}"
