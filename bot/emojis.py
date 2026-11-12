"""
Fight, craft, forge, explore, gather and Character Sheet button icons as the bot's application emojis (docs/combat.md, docs/alchemy.md).

At startup the medallion icons from cards/battle_icons.py, cards/alchemy_icons.py, cards/wild_icons.py and
cards/forge_icons.py and cards/sheet_icons.py are
uploaded as application emojis named ma_<key>. If that fails (no permission, rate limit, offline tests),
buttons use normal emojis.

Discord keeps an uploaded emoji's picture forever, so a fingerprint of each uploaded picture is saved in the
settings table ("emoji:<name>"). When an icon's picture changes (a re-cut technique painting, say), the old emoji
is deleted and the new picture uploaded at the next start; unchanged ones are reused as before.
"""
import hashlib
import logging

import discord

from cards import alchemy_icons, battle_icons, forge_icons, sheet_icons, wild_icons

from . import db
from . import render as card_render

log = logging.getLogger("mortal-ascent")
PREFIX = "ma_"
ICON_SETS = (battle_icons, alchemy_icons, wild_icons, forge_icons, sheet_icons)


class Emojis:
    def __init__(self):
        self.custom = {}            # key -> discord.Emoji

    def get(self, key):
        """The custom emoji for a button, or the plain fallback emoji."""
        if key not in self.custom and key in battle_icons.TECH_SCHOOL:     # a technique icon that didn't upload
            key2 = battle_icons.TECH_SCHOOL[key]
            return self.custom.get(key2) or battle_icons.FALLBACK.get(key2)
        return self.custom.get(key) or next((m.FALLBACK[key] for m in ICON_SETS if key in m.FALLBACK), None)

    async def setup(self, client):
        try:
            existing = {e.name: e for e in await client.fetch_application_emojis()}
        except Exception:
            log.warning("Could not list application emojis; fight buttons use normal emojis", exc_info=True)
            return
        conn = getattr(client, "conn", None)
        for icons, key in ((m, k) for m in ICON_SETS for k in m.ICONS):
            name = PREFIX + getattr(icons, "EMOJI_NAME", {}).get(key, key)
            old = existing.get(name)
            try:
                image = await card_render.render(icons.icon_png, key)   # the card thread (FreeType)
            except Exception:
                log.warning("Could not draw button icon %s", name, exc_info=True)
                if old is not None:
                    self.custom[key] = old
                continue
            print_ = fingerprint(image)
            if old is not None and saved_fingerprint(conn, name) == print_:
                self.custom[key] = old                      # same picture as the one Discord has
                continue
            try:
                if old is not None:                         # an older picture: replace it
                    await old.delete()
                    old = None
                self.custom[key] = await client.create_application_emoji(name=name, image=image)
                save_fingerprint(conn, name, print_)
                log.info("Uploaded button icon %s", name)
            except (discord.DiscordException, ValueError):
                log.warning("Could not upload button icon %s; using a normal emoji", name, exc_info=True)
                if old is not None:                         # couldn't delete it: the old picture beats none
                    self.custom[key] = old


def fingerprint(png):
    return hashlib.sha1(png).hexdigest()[:16]


def saved_fingerprint(conn, name):
    """The fingerprint of the picture last uploaded as this emoji, or None (unknown: uploaded before
    fingerprints were kept, so it may be an old picture)."""
    if conn is None:
        return None
    try:
        return db.get_setting(conn, "emoji:" + name)
    except Exception:
        return None


def save_fingerprint(conn, name, value):
    if conn is None:
        return
    try:
        db.set_setting(conn, "emoji:" + name, value)
    except Exception:
        log.warning("Could not save the fingerprint of %s", name, exc_info=True)
