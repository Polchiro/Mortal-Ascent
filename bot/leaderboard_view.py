"""
/leaderboard: the top ten by Realm, Lotus Coins or Moon Pearls, with a button per board.
"""
import asyncio
import io
import time

import discord
from discord import app_commands

import leaderboard as config

from . import db, leaderboard
from . import render as card_render
from .views import OwnedView

_AVATARS = {}      # user_id → (fetched at, png bytes or None)


async def avatar(bot, uid):
    """A top player's Discord avatar, cached for AVATAR_CACHE_SECONDS."""
    from .sheet.view import fetch_avatar
    hit = _AVATARS.get(uid)
    if hit and time.time() - hit[0] < config.AVATAR_CACHE_SECONDS:
        return hit[1]
    user = bot.get_user(uid)
    if user is None:
        try:
            user = await bot.fetch_user(uid)
        except Exception:
            user = None
    data = await fetch_avatar(user) if user else None
    _AVATARS[uid] = (time.time(), data)
    return data


async def card(bot, uid, board_key):
    from cards.leaderboard import render_leaderboard
    async with bot.db_lock:
        data = leaderboard.board(bot.conn, board_key, uid)
    top3 = [r["user_id"] for r in data["top"][:3]]
    data["avatars"] = dict(zip(top3, await asyncio.gather(*(avatar(bot, u) for u in top3))))
    img = await card_render.render(render_leaderboard, data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="leaderboard.png")


class LeaderboardView(OwnedView):
    def __init__(self, bot, uid, board_key):
        super().__init__(uid, timeout=300)
        self.bot = bot
        self.build(board_key)

    def build(self, board_key):
        self.board = board_key
        self.clear_items()
        emoji = {"realm": "🏯", "lotus_coins": "🪷", "moon_pearls": "🌙"}
        for key, spec in config.BOARDS.items():
            b = discord.ui.Button(label=spec["label"], emoji=emoji.get(key),
                                  style=discord.ButtonStyle.primary if key == board_key else discord.ButtonStyle.secondary,
                                  disabled=key == board_key)
            b.callback = self._switch(key)
            self.add_item(b)

    def _switch(self, key):
        async def go(interaction):
            await interaction.response.defer()
            self.build(key)
            await interaction.edit_original_response(attachments=[await card(self.bot, self.owner_id, key)], view=self)
        return go


def register(bot):
    @bot.tree.command(name="leaderboard", description="The top cultivators by realm, Lotus Coins or Moon Pearls")
    @app_commands.describe(board="Which ranking to open")
    @app_commands.choices(board=[app_commands.Choice(name=b["label"], value=k) for k, b in config.BOARDS.items()])
    async def leaderboard_cmd(interaction: discord.Interaction, board: app_commands.Choice[str] | None = None):
        key = board.value if board else next(iter(config.BOARDS))
        await interaction.response.defer()
        file = await card(bot, interaction.user.id, key)
        view = LeaderboardView(bot, interaction.user.id, key)
        view.message = await interaction.followup.send(file=file, view=view, wait=True)
