"""
Fight button icons as the bot's application emojis (docs/combat.md).

At startup the medallion icons from cards/battle_icons.py are uploaded once as application emojis
named ma_<key>. If that fails (no permission, rate limit, offline tests), buttons use normal emojis.
"""
import logging

import discord

from cards import battle_icons

from . import render as card_render

log = logging.getLogger("mortal-ascent")
PREFIX = "ma_"


class Emojis:
    def __init__(self):
        self.custom = {}            # key -> discord.Emoji

    def get(self, key):
        """The custom emoji for a button, or the plain fallback emoji."""
        return self.custom.get(key) or battle_icons.FALLBACK.get(key)

    async def setup(self, client):
        try:
            existing = {e.name: e for e in await client.fetch_application_emojis()}
        except Exception:
            log.warning("Could not list application emojis; fight buttons use normal emojis", exc_info=True)
            return
        for key in battle_icons.ICONS:
            name = PREFIX + key
            if name in existing:
                self.custom[key] = existing[name]
                continue
            try:
                image = await card_render.render(battle_icons.icon_png, key)   # the card thread (FreeType)
                self.custom[key] = await client.create_application_emoji(name=name, image=image)
                log.info("Uploaded fight icon %s", name)
            except (discord.HTTPException, ValueError):
                log.warning("Could not upload fight icon %s; using a normal emoji", name, exc_info=True)
