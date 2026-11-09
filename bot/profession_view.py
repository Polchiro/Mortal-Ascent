"""/profession: your Alchemist and Blacksmith ranks on one card."""
import io

import discord
from discord import app_commands

from . import db, profession
from . import render as card_render

NOT_STARTED = "You have not begun your journey yet. Use **/start** to step through the gates of the Jianghu."


def register(bot):
    @bot.tree.command(name="profession", description="Your Alchemist and Blacksmith ranks: EXP, what you can make, what's next")
    @app_commands.describe(player="Someone else's professions (defaults to yours)")
    async def profession_cmd(interaction: discord.Interaction, player: discord.User | None = None):
        target = player or interaction.user
        p = db.get_player(bot.conn, target.id)
        if not p:
            msg = NOT_STARTED if target == interaction.user else f"{target.display_name} has not begun their journey yet."
            await interaction.response.send_message(msg, ephemeral=True)
            return
        from cards.profession import render_profession
        await interaction.response.defer()
        img = await card_render.render(render_profession, profession.card_data(p))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        await interaction.followup.send(file=discord.File(buf, filename="profession.png"))
