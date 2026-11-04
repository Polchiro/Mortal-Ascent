"""
Discord client and slash commands: /start, /profile, /balance, /inventory, /explore, /train.
"""
import asyncio
import io
import logging
import os
import tempfile

import discord
from discord import app_commands

import economy
from balance_card import render_balance
from profile_card import render_profile

from . import db, trainer
from . import player as rules
from .views import ExploreView, InventoryView, TrainView

log = logging.getLogger("mortal-ascent")

NOT_STARTED = "You have not begun your journey yet. Use **/start** to step through the gates of the Jianghu."


def png(image, filename):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename=filename)


class MortalAscent(discord.Client):
    def __init__(self, db_path, guild_id=None):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.conn = db.connect(db_path)
        self.guild_id = guild_id
        self.db_lock = asyncio.Lock()
        self.busy = set()          # (user_id, "explore" | "train") while a session is running
        self.tree.on_error = self.on_app_command_error
        register_commands(self)

    async def on_app_command_error(self, interaction, error):
        """Log any command failure and always answer, so Discord never hangs on "thinking..."."""
        log.exception("/%s failed", interaction.command.name if interaction.command else "?", exc_info=error)
        msg = "⚠️ Something went wrong on our side. The error was logged; please try again in a moment."
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except discord.HTTPException:
            log.exception("Could not send the error message")

    async def setup_hook(self):
        if self.guild_id:
            guild = discord.Object(id=self.guild_id)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            log.info("Synced commands to guild %s", self.guild_id)
        else:
            await self.tree.sync()
            log.info("Synced commands globally (can take up to an hour to appear)")

    async def on_ready(self):
        log.info("Logged in as %s (%s)", self.user, self.user.id)


async def render_with_avatar(member, render, make_data):
    """Download the member's avatar to a temp file, build card data, render off the event loop."""
    with tempfile.TemporaryDirectory() as tmp:
        avatar_path = None
        try:
            avatar_path = os.path.join(tmp, "avatar.png")
            await member.display_avatar.with_format("png").with_size(256).save(avatar_path)
        except Exception:
            log.warning("Could not download avatar for %s; using initial instead", member, exc_info=True)
            avatar_path = None
        data = make_data(avatar_path)
        return await asyncio.to_thread(render, data)


def register_commands(bot):
    tree = bot.tree

    @tree.command(name="start", description="Begin your journey and roll your talent")
    async def start(interaction: discord.Interaction):
        user = interaction.user
        async with bot.db_lock:
            if db.get_player(bot.conn, user.id):
                await interaction.response.send_message(
                    "You already walk the martial path. Use **/profile** to see your progress.", ephemeral=True)
                return
            talent = rules.roll_talent()
            db.create_player(bot.conn, user.id, user.display_name, talent,
                             rules.STARTING_LOTUS_COINS, rules.starting_techniques())

        coin = economy.CURRENCIES["lotus_coins"]
        embed = discord.Embed(
            title="🏮 The Gates of the Jianghu",
            description=(
                "*You arrive at the gates of the Jianghu. An old master looks you over...*\n"
                "*\"Place your hand on the Aptitude Stone.\"*\n"
                "⏳ *The stone begins to glow...*\n\n"
                f"✨ **{talent} Talent!**"
            ),
            color=economy.BALANCE_EMBED_COLOR,
        )
        embed.add_field(name="Realm", value="Mortal, 1st Layer")
        embed.add_field(name="Techniques", value=" · ".join(t["name"] for t in rules.starting_techniques()))
        embed.add_field(name=coin["name"], value=f"{coin['emoji']} {rules.STARTING_LOTUS_COINS}")
        embed.set_footer(text="Use /profile to know yourself.")
        await interaction.response.send_message(embed=embed)

    @tree.command(name="profile", description="Show your cultivation profile card")
    @app_commands.describe(member="Whose profile to view (defaults to you)")
    async def profile(interaction: discord.Interaction, member: discord.Member | None = None):
        target = member or interaction.user
        p = db.get_player(bot.conn, target.id)
        if not p:
            msg = NOT_STARTED if target == interaction.user else f"{target.display_name} has not begun their journey yet."
            await interaction.response.send_message(msg, ephemeral=True)
            return
        await interaction.response.defer()
        techniques = db.get_techniques(bot.conn, target.id)
        rank = db.server_rank(bot.conn, target.id, rules.REALM_ORDER)
        weapon = db.equipped_weapon(bot.conn, target.id)
        image = await render_with_avatar(
            target, render_profile,
            lambda av: rules.profile_data(p, techniques, rank, avatar_path=av, weapon=weapon))
        await interaction.followup.send(file=png(image, "profile.png"))

    @tree.command(name="balance", description="Show your Lotus Coins, Moon Pearls and blessing")
    async def balance(interaction: discord.Interaction):
        p = db.get_player(bot.conn, interaction.user.id)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        await interaction.response.defer()
        image = await asyncio.to_thread(render_balance, rules.balance_data(p))
        await interaction.followup.send(file=png(image, "balance.png"))

    @tree.command(name="inventory", description="Open your bag: manuals, weapons, pills, materials and chests")
    @app_commands.describe(category="Which tab to open first")
    @app_commands.choices(category=[app_commands.Choice(name=n, value=v) for n, v in (
        ("Manuals", "manuals"), ("Weapons", "weapons"), ("Pills", "pills"),
        ("Materials", "materials"), ("Chests", "chests"))])
    async def inventory(interaction: discord.Interaction, category: app_commands.Choice[str] | None = None):
        if not db.get_player(bot.conn, interaction.user.id):
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        await interaction.response.defer()
        if category is None:
            counts = db.category_counts(bot.conn, interaction.user.id)
            first = next((k for k in ("chests", "manuals", "weapons", "pills", "materials") if counts.get(k)), "manuals")
        else:
            first = category.value
        view = InventoryView(bot, interaction.user.id, first)
        file = await view.render()
        view.message = await interaction.followup.send(file=file, view=view, wait=True)

    @tree.command(name="explore", description="Venture into the wild: pick paths, fight beasts, find chests")
    async def explore(interaction: discord.Interaction):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        if (uid, "explore") in bot.busy:
            await interaction.response.send_message("You are already on an expedition. Finish it first!", ephemeral=True)
            return
        hurt = rules.injured_for(p)
        if hurt:
            await interaction.response.send_message(
                f"🩹 You are still injured. Rest for **{rules.fmt_duration(hurt)}** before exploring again.", ephemeral=True)
            return
        wait = db.cooldown_left(bot.conn, uid, "explore")
        if wait:
            await interaction.response.send_message(
                f"🦶 Your legs still ache from the last expedition. Explore again in **{rules.fmt_duration(wait)}**.",
                ephemeral=True)
            return
        bot.busy.add((uid, "explore"))
        try:
            view = ExploreView(bot, uid)
            await interaction.response.send_message(embed=view.embed(), view=view)
            view.message = await interaction.original_response()
        except Exception:
            bot.busy.discard((uid, "explore"))
            raise

    @tree.command(name="train", description="Train with the master to gather Internal Qi")
    async def train(interaction: discord.Interaction):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        if (uid, "train") in bot.busy:
            await interaction.response.send_message("You are already training. Finish that session first!", ephemeral=True)
            return
        wait = db.cooldown_left(bot.conn, uid, "train")
        if wait:
            await interaction.response.send_message(
                f"😮‍💨 Your muscles need rest. Train again in **{rules.fmt_duration(wait)}**.", ephemeral=True)
            return
        bot.busy.add((uid, "train"))
        try:
            view = TrainView(bot, uid, trainer.roll_session(p))
            view.interaction = interaction
            await interaction.response.send_message(embed=view.intro(), view=view)
        except Exception:
            bot.busy.discard((uid, "train"))
            raise
