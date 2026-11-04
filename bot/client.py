"""
Discord client and slash commands: /start, /profile, /balance, /inventory, /explore, /train,
/meditate, /seclusion, /breakthrough, /practice, /spar, /techniques, /equipment.
"""
import asyncio
import io
import logging
import os
import tempfile
import time

import discord
from discord import app_commands

import economy
import training
from balance_card import render_balance
from profile_card import render_profile

from . import db, trainer
from . import player as rules
from .views import (ConfirmView, EquipmentView, ExploreView, InventoryView, SparView, TechniquesView,
                    TrainView)

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
        if rules.in_seclusion(p):
            await interaction.response.send_message(
                "🧘 You are in closed-door seclusion. Leave it with **/seclusion** before exploring.", ephemeral=True)
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
        await start_challenge(interaction, p, None)

    async def start_challenge(interaction, p, tech):
        uid = interaction.user.id
        bot.busy.add((uid, "train"))
        try:
            view = TrainView(bot, uid, trainer.roll_session(p, tech=tech))
            view.interaction = interaction
            await interaction.response.send_message(embed=view.intro(), view=view)
        except Exception:
            bot.busy.discard((uid, "train"))
            raise

    def embed(title, text):
        return discord.Embed(title=title, description=text, color=economy.BALANCE_EMBED_COLOR)

    def qi_line(p):
        return (f"**{p['realm']}, {rules.ordinal(p['layer'])} Layer** · Qi {p['qi']:,.1f} / "
                f"{rules.qi_needed(p['realm'], p['layer']):,}")

    def save_progress(uid, p, **extra):
        db.update_player(bot.conn, uid, qi=p["qi"], realm=p["realm"], layer=p["layer"],
                         breakthroughs=p["breakthroughs"], failed_breakthroughs=p["failed_breakthroughs"],
                         injured_until=p.get("injured_until"), **extra)

    @tree.command(name="meditate", description="Collect the Internal Qi you gathered passively (stores up to 12 hours)")
    async def meditate(interaction: discord.Interaction):
        uid = interaction.user.id
        async with bot.db_lock:
            p = db.get_player(bot.conn, uid)
            if not p:
                await interaction.response.send_message(NOT_STARTED, ephemeral=True)
                return
            if rules.in_seclusion(p):
                await interaction.response.send_message(
                    "🧘 You are in seclusion; your Qi gathers there instead. Check it with **/seclusion**.", ephemeral=True)
                return
            techs = db.get_techniques(bot.conn, uid)
            now = time.time()
            qi, hours = rules.passive_qi(p, techs, now)
            p, events = rules.add_qi(p, qi, techs, now=now)
            save_progress(uid, p, qi_collected_at=now)
        full = hours >= training.PASSIVE_MAX_STORED_HOURS
        text = [f"*You sit cross-legged and draw in the Qi gathered over {hours:.1f} hours...*",
                f"**Internal Qi:** +{qi:,.1f}" + ("  *(storage was full: 12h max)*" if full else ""),
                qi_line(p)] + events
        await interaction.response.send_message(embed=embed("🧘 Meditation", "\n".join(text)))

    async def end_seclusion(uid):
        async with bot.db_lock:
            p = db.get_player(bot.conn, uid)
            if not rules.in_seclusion(p):
                return embed("🧘 Seclusion", "You are not in seclusion.")
            techs = db.get_techniques(bot.conn, uid)
            now = time.time()
            qi, hours, done = rules.seclusion_qi(p, techs, now)
            p, events = rules.add_qi(p, qi, techs, now=now)
            save_progress(uid, p, seclusion_start=None, seclusion_end=None, qi_collected_at=now)
        head = ("*You open the doors after {:.1f} hours of seclusion. Your Qi surges!*" if done else
                "*You leave seclusion early after {:.1f} hours. The ×2 bonus is lost.*").format(hours)
        return embed("🧘 Seclusion ends", "\n".join([head, f"**Internal Qi:** +{qi:,.1f}", qi_line(p)] + events))

    @tree.command(name="seclusion", description="Enter closed-door seclusion for 8-24 hours at ×2 Qi Rate, or check/leave it")
    @app_commands.describe(hours="How long to stay in seclusion (8-24). Leave it out to check on a seclusion")
    async def seclusion(interaction: discord.Interaction,
                        hours: app_commands.Range[int, training.SECLUSION_MIN_HOURS, training.SECLUSION_MAX_HOURS] | None = None):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        now = time.time()
        if rules.in_seclusion(p):
            if now >= p["seclusion_end"]:
                await interaction.response.send_message(embed=await end_seclusion(uid))
                return
            techs = db.get_techniques(bot.conn, uid)
            so_far = rules.seclusion_qi(dict(p), techs, p["seclusion_end"])[0]
            view = ConfirmView(uid, "Leave early", lambda: end_seclusion(uid), emoji="🚪")
            await interaction.response.send_message(embed=embed("🧘 In seclusion", (
                f"You emerge <t:{int(p['seclusion_end'])}:R> with about **{so_far:,.0f} Qi**.\n"
                "Leaving early gives Qi for the time spent, **without** the ×2 bonus.")), view=view, ephemeral=True)
            view.message = await interaction.original_response()
            return
        if hours is None:
            await interaction.response.send_message(
                f"Choose how long: **/seclusion hours:{training.SECLUSION_MIN_HOURS}** up to "
                f"{training.SECLUSION_MAX_HOURS}. Your Qi Rate is doubled, but you cannot explore or spar.", ephemeral=True)
            return
        if (uid, "explore") in bot.busy:
            await interaction.response.send_message("Finish your expedition first.", ephemeral=True)
            return
        async with bot.db_lock:
            p = db.get_player(bot.conn, uid)
            techs = db.get_techniques(bot.conn, uid)
            qi, _ = rules.passive_qi(p, techs, now)          # bank passive Qi before the doors close
            p, events = rules.add_qi(p, qi, techs, now=now)
            end = now + hours * 3600
            save_progress(uid, p, qi_collected_at=now, seclusion_start=now, seclusion_end=end)
        rate = rules.qi_rate(p, now, techs)[0] * training.SECLUSION_QI_MULTIPLIER
        lines = [f"*You seal the doors and sink into meditation for {hours} hours...*",
                 f"Qi Rate ×{training.SECLUSION_QI_MULTIPLIER:g}: **{rate:,.1f} Qi/hour**. You emerge <t:{int(end)}:R>.",
                 "No exploring or sparring until then. Use **/seclusion** to check or leave early."]
        if qi >= 0.1:
            lines.append(f"(Collected {qi:,.1f} passive Qi first.)")
        await interaction.response.send_message(embed=embed("🧘 Closed-Door Seclusion", "\n".join(lines + events)))

    @tree.command(name="breakthrough", description="Attempt to break through a phase bottleneck or into the next realm")
    async def breakthrough(interaction: discord.Interaction):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        techs = db.get_techniques(bot.conn, uid)
        kind, target = rules.next_gate(p)
        need = rules.qi_needed(p["realm"], p["layer"])
        blocked = None
        if kind in ("layer", "peak"):
            blocked = "There is no bottleneck ahead of you. Layers within a phase open on their own as Qi fills."
        elif p["qi"] < need:
            blocked = f"Your Qi bar is not full yet: **{p['qi']:,.1f} / {need:,}**. Keep training."
        elif kind == "realm" and rules.realm_requirement_missing(p, techs, target):
            blocked = f"🔒 To reach **{target}** you also need {rules.realm_requirement_missing(p, techs, target)}."
        if blocked:
            await interaction.response.send_message(embed=embed("⛰️ Breakthrough", blocked), ephemeral=True)
            return
        chance = rules.breakthrough_chance(p)
        risk = (f"Failure costs {training.BREAKTHROUGH_FAIL_QI_LOSS:.0%} of your Qi"
                + (f" and a {training.INJURY_HOURS}-hour injury." if kind == "realm" else "."))
        if chance >= 1:
            risk = "The Old Master guides you; this first gate cannot fail."

        async def attempt():
            async with bot.db_lock:
                fresh = db.get_player(bot.conn, uid)
                ok, msg = rules.attempt_breakthrough(fresh, db.get_techniques(bot.conn, uid))
                if ok is not None:
                    save_progress(uid, fresh)
            return embed("⛰️ Breakthrough", f"{msg}\n{qi_line(fresh)}")

        view = ConfirmView(uid, "Attempt breakthrough", attempt, style=discord.ButtonStyle.success, emoji="⛰️")
        await interaction.response.send_message(embed=embed("⛰️ Breakthrough", (
            f"Your Qi presses against the gate to **{target}**.\n**Success chance:** {chance:.0%}\n{risk}")), view=view)
        view.message = await interaction.original_response()

    async def technique_autocomplete(interaction: discord.Interaction, current: str):
        techs = db.get_techniques(bot.conn, interaction.user.id, equipped_only=False)
        return [app_commands.Choice(name=f"{t['name']} ({t['grade']} {t['type']})", value=str(t["id"]))
                for t in techs if current.lower() in t["name"].lower()][:25]

    def find_technique(uid, value):
        techs = db.get_techniques(bot.conn, uid, equipped_only=False)
        return next((t for t in techs if str(t["id"]) == value or t["name"].lower() == value.lower()), None)

    @tree.command(name="practice", description="Practise one technique in a training challenge for mastery EXP")
    @app_commands.describe(technique="The technique to practise")
    @app_commands.autocomplete(technique=technique_autocomplete)
    async def practice(interaction: discord.Interaction, technique: str):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        tech = find_technique(uid, technique)
        if not tech:
            await interaction.response.send_message("You don't know that technique. See **/techniques**.", ephemeral=True)
            return
        if rules.bar_full(tech):
            await interaction.response.send_message(
                f"**{tech['name']}**'s mastery bar is full. Pass its trial with **/spar technique:{tech['name']}** first.",
                ephemeral=True)
            return
        if (uid, "train") in bot.busy:
            await interaction.response.send_message("You are already training. Finish that session first!", ephemeral=True)
            return
        wait = db.cooldown_left(bot.conn, uid, "practice")
        if wait:
            await interaction.response.send_message(
                f"🥢 Your hands need rest. Practise again in **{rules.fmt_duration(wait)}**.", ephemeral=True)
            return
        await start_challenge(interaction, p, tech)

    @tree.command(name="spar", description="Spar with a master for mastery EXP, or take a technique's mastery trial")
    @app_commands.describe(technique="A technique whose mastery bar is full: take its trial instead of a normal spar")
    @app_commands.autocomplete(technique=technique_autocomplete)
    async def spar(interaction: discord.Interaction, technique: str | None = None):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        if rules.in_seclusion(p):
            await interaction.response.send_message("🧘 You are in seclusion. No sparring until you leave.", ephemeral=True)
            return
        hurt = rules.injured_for(p)
        if hurt:
            await interaction.response.send_message(
                f"🩹 You are injured. Rest for **{rules.fmt_duration(hurt)}** before sparring.", ephemeral=True)
            return
        if (uid, "spar") in bot.busy:
            await interaction.response.send_message("You are already sparring!", ephemeral=True)
            return
        focus, trial = None, False
        if technique:
            focus = find_technique(uid, technique)
            if not focus:
                await interaction.response.send_message("You don't know that technique. See **/techniques**.", ephemeral=True)
                return
            if not rules.bar_full(focus):
                cap = rules.mastery_cap(focus)
                why = (f"{focus['mastery_exp']:,} / {cap:,} EXP" if cap else "it is already at the final stage")
                await interaction.response.send_message(
                    f"**{focus['name']}** isn't ready for a trial ({why}). Leave the technique out for a normal spar.",
                    ephemeral=True)
                return
            if not focus["equipped"]:
                await interaction.response.send_message(f"Equip **{focus['name']}** in **/techniques** to take its trial.",
                                                        ephemeral=True)
                return
            twait = db.cooldown_left(bot.conn, uid, f"trial:{focus['id']}")
            if twait:
                await interaction.response.send_message(
                    f"You failed this trial recently. Retry in **{rules.fmt_duration(twait)}**.", ephemeral=True)
                return
            trial = True
        wait = db.cooldown_left(bot.conn, uid, "spar")
        if wait:
            await interaction.response.send_message(
                f"The master is resting. Spar again in **{rules.fmt_duration(wait)}**.", ephemeral=True)
            return
        bot.busy.add((uid, "spar"))
        try:
            view = SparView(bot, uid, focus, trial)
            await interaction.response.send_message(embed=view.embed(), view=view)
            view.message = await interaction.original_response()
        except Exception:
            bot.busy.discard((uid, "spar"))
            raise

    @tree.command(name="techniques", description="See your techniques and mastery, and choose which are equipped")
    async def techniques(interaction: discord.Interaction):
        if not db.get_player(bot.conn, interaction.user.id):
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        view = TechniquesView(bot, interaction.user.id)
        await interaction.response.send_message(embed=view.embed(), view=view)
        view.message = await interaction.original_response()

    @tree.command(name="equipment", description="See your weapon and final stats, and change your weapon")
    async def equipment(interaction: discord.Interaction):
        if not db.get_player(bot.conn, interaction.user.id):
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        view = EquipmentView(bot, interaction.user.id)
        await interaction.response.send_message(embed=view.embed(), view=view)
        view.message = await interaction.original_response()
