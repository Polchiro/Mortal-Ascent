"""
Discord client and slash commands: /start, /profile, /balance, /inventory, /explore, /train,
/meditate, /seclusion, /breakthrough, /internal qi, /practice, /spar, /techniques, /equipment,
/shop, /blessing, /recharge, /reroll, /physician, /bestiary, /cooldown. /tutorial and /index are in guide.py,
/gather in gathering.py, /craft in crafting.py, /duel in duel_view.py. Admin testing commands are in admin.py.
Every command also works as a text message with the "m" prefix ("m internal qi"); see prefix.py.
"""
import asyncio
import io
import logging
import time

import discord
from discord import app_commands

import beasts as beast_rules
import economy
import explore as explore_rules
import technique as technique_rules
import talent as talent_rules
import training
from cards.dantian import render_dantian

from . import (admin, combat, cooldowns, crafting, db, duel_view, gathering, guide, hunt, instance, loot, prefix, qi,
               trainer)
from . import render as card_render
from .emojis import Emojis
from . import player as rules
from .sheet import items as sheet_items
from .sheet.view import open_sheet, send_public_profile
from .views import (BlessingView, ConfirmView, ExploreView, ShopView, SparView, TrainView, blessing_embed,
                    shop_embed)

log = logging.getLogger("mortal-ascent")

NOT_STARTED = "You have not begun your journey yet. Use **/start** to step through the gates of the Jianghu."


def png(image, filename):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename=filename)


class MortalAscent(discord.Client):
    def __init__(self, db_path, guild_id=None, message_content=True):
        intents = discord.Intents.default()
        # Needed to read "m ..." text commands in servers. Turn on "Message Content Intent" in the
        # Developer Portal (Bot tab). DMs with the bot work even without it.
        intents.message_content = message_content
        super().__init__(intents=intents, activity=discord.Game(f"{prefix.PREFIX} help | /start"))
        # Every command works both in servers and in a direct message with the bot.
        self.tree = app_commands.CommandTree(
            self, allowed_contexts=app_commands.AppCommandContext(guild=True, dm_channel=True))
        self.tree.interaction_check = self.before_command
        self.conn = db.connect(db_path)
        self.guild_id = guild_id
        self.db_lock = asyncio.Lock()
        self.busy = set()          # (user_id, "explore" | "train" | "spar" | "hunt" | "duel" ...) while a session runs
        self.emojis_ma = Emojis()  # fight button icons (uploaded as application emojis in setup_hook)
        self.tree.on_error = self.on_app_command_error
        register_commands(self)
        admin.register(self)
        guide.register(self)
        gathering.register(self)
        crafting.register(self)
        duel_view.register(self)

    async def before_command(self, interaction):
        """Runs before every slash command: bank the passive Qi gathered since last time."""
        try:
            async with self.db_lock:
                sync_passive_qi(self.conn, interaction.user.id)
        except Exception:
            log.exception("Passive Qi sync failed")
        return True

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
        # Upload the fight button icons in the background; until then (or if it fails) buttons use normal emojis.
        asyncio.create_task(self.emojis_ma.setup(self))
        # Commands are always synced globally: per-server commands never show up in DMs.
        synced = await self.tree.sync()
        for line in sync_report([c.name for c in self.tree.get_commands()], [c.name for c in synced],
                                instance.code_version()):
            log.info(line)
        if self.guild_id:
            # Older versions synced a copy of every command to DISCORD_GUILD_ID. Remove that copy,
            # otherwise each command would be listed twice in that server.
            guild = discord.Object(id=self.guild_id)
            self.tree.clear_commands(guild=guild)
            try:
                await self.tree.sync(guild=guild)
                log.info("Removed the old per-server copy of the commands from guild %s", self.guild_id)
            except discord.HTTPException:
                log.warning("Could not clear per-server commands in guild %s", self.guild_id, exc_info=True)

    async def on_ready(self):
        log.info("Logged in as %s (%s)", self.user, self.user.id)

    async def on_message(self, message):
        """Text commands: "m start", "m internal qi", "m index"... (prefix.py)."""
        await prefix.handle_message(self, message)




def sync_passive_qi(conn, user_id, now=None):
    """Add the passive Qi gathered since the last collection (training.md: it gathers at your
    Qi Rate and stores up to 12 hours). Called before every command, so Qi rises on its own.
    Returns (qi_added, events)."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    if not p or rules.in_seclusion(p):
        return 0.0, []
    techs = db.get_techniques(conn, user_id)
    qi, _ = rules.passive_qi(p, techs, now)
    p, events = rules.add_qi(p, qi, techs, now=now)
    db.update_player(conn, user_id, qi=p["qi"], layer=p["layer"], qi_collected_at=now)
    return qi, events


def sync_report(local_names, synced_names, version="unknown"):
    """Startup lines that show which slash commands Discord now has, so a missing one is easy to spot."""
    lines = [f"Bot code version: {version}",
             f"Discord now has {len(synced_names)} slash commands: " + ", ".join(sorted(synced_names))]
    missing = sorted(set(local_names) - set(synced_names))
    if missing:
        lines.append("WARNING: these commands did not reach Discord: " + ", ".join(missing))
    else:
        lines.append("All commands reached Discord (a new one can take a few minutes to show; press Ctrl+R in "
                     "Discord to refresh). Text commands like \"m duel @player\" work right away.")
    return lines


def next_gate_is_realm(player):
    return rules.next_gate(player)[0] == "realm"


def claim_session(bot, uid, kind, cooldown=None, seconds=0):
    """Mark a session as running and start its cooldown in one step. This has no await in it, so it
    can't be interrupted: if the same command arrives twice (a double send during lag, or a slash
    command and an "m" command at once), the second one sees the session and is turned away.
    The cooldown starts now, not when the session ends, and it is saved in the database, so it
    also holds if the bot restarts mid-session. Returns False if the session was already running."""
    if (uid, kind) in bot.busy:
        return False
    bot.busy.add((uid, kind))
    if cooldown:
        db.set_cooldown(bot.conn, uid, cooldown, seconds)
    return True


def release_session(bot, uid, kind, cooldown=None):
    """Undo claim_session when the session could not start (the message failed to send)."""
    bot.busy.discard((uid, kind))
    if cooldown:
        db.clear_cooldown(bot.conn, uid, cooldown)


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
        news = loot.talent_announcement(user.display_name, talent)
        if news:
            await interaction.followup.send(news)

    @tree.command(name="profile", description="Open your Character Sheet: realm, attributes, Internal Qi, techniques")
    @app_commands.describe(member="Whose profile to view (defaults to you)")
    async def profile(interaction: discord.Interaction, member: discord.User | None = None):
        target = member or interaction.user
        if not db.get_player(bot.conn, target.id):
            msg = NOT_STARTED if target == interaction.user else f"{target.display_name} has not begun their journey yet."
            await interaction.response.send_message(msg, ephemeral=True)
            return
        if target != interaction.user:
            async with bot.db_lock:
                sync_passive_qi(bot.conn, target.id)
            await send_public_profile(bot, interaction, target)
            return
        await open_sheet(bot, interaction, "profile")

    @tree.command(name="balance", description="Open your purse: Lotus Coins, Moon Pearls, blessing and recent transactions")
    async def balance(interaction: discord.Interaction):
        if not db.get_player(bot.conn, interaction.user.id):
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        await open_sheet(bot, interaction, "purse")

    @tree.command(name="inventory", description="Open your bag: chests, manuals, weapons, pills, herbs and materials")
    @app_commands.describe(category="Which tab to open first")
    @app_commands.choices(category=[app_commands.Choice(name=c.label, value=c.key)
                                    for c in sheet_items.CATEGORIES.values()])
    async def inventory(interaction: discord.Interaction, category: app_commands.Choice[str] | None = None):
        if not db.get_player(bot.conn, interaction.user.id):
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        await open_sheet(bot, interaction, "inventory", category.value if category else None)

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
        if not claim_session(bot, uid, "explore", "explore", explore_rules.EXPLORE_COOLDOWN_MINUTES * 60):
            await interaction.response.send_message("You are already on an expedition. Finish it first!", ephemeral=True)
            return
        sent = False
        try:
            view = ExploreView(bot, uid)
            await interaction.response.send_message(embed=view.embed(), view=view)
            sent = True
            view.message = await interaction.original_response()
        except Exception:
            if not sent:      # never shown: give the cooldown back (once shown, the view's timeout ends it)
                release_session(bot, uid, "explore", "explore")
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
        mode = "practice" if tech else "train"
        if not claim_session(bot, uid, "train", mode, trainer.cooldown_seconds(p, mode=mode)):
            await interaction.response.send_message("You are already training. Finish that session first!", ephemeral=True)
            return
        sent = False
        try:
            view = TrainView(bot, uid, trainer.roll_session(p, tech=tech))
            view.interaction = interaction
            await view.send_intro(interaction)
            sent = True
        except Exception:
            if not sent:      # never shown: give the cooldown back (once shown, the view's timeout ends it)
                release_session(bot, uid, "train", mode)
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

    @tree.command(name="meditate", description="See your passive Qi: how fast it gathers and when your next layer comes")
    async def meditate(interaction: discord.Interaction):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)     # passive Qi was already banked by before_command
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        if rules.in_seclusion(p):
            await interaction.response.send_message(
                "🧘 You are in seclusion; your Qi gathers there at ×2. Check it with **/seclusion**.", ephemeral=True)
            return
        rate, mult = rules.qi_rate(p, techniques=db.get_techniques(bot.conn, uid))
        need = rules.qi_needed(p["realm"], p["layer"])
        left = max(0.0, need - p["qi"])
        eta = (f"Your bar fills in about **{rules.fmt_duration(left / rate * 3600)}**." if left and rate
               else "Your bar is full!" + (" Use **/breakthrough**." if rules.next_gate(p)[0] in ("phase", "realm") else ""))
        text = ["*You sit cross-legged and feel Qi flowing in...*",
                f"Your Qi gathers **on its own** at **{rate:,.2f} Qi/hour** (×{mult:.2f}). It is added every time you "
                f"use a command, and up to {training.PASSIVE_MAX_STORED_HOURS} hours of it is kept while you are away.",
                qi_line(p), eta]
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
        if (uid, "explore") in bot.busy or (uid, "spar") in bot.busy:
            await interaction.response.send_message("Finish your expedition or spar first.", ephemeral=True)
            return
        async with bot.db_lock:
            p = db.get_player(bot.conn, uid)
            # Checked again now that we hold the lock: another command may have run while we waited.
            if rules.in_seclusion(p) or (uid, "explore") in bot.busy or (uid, "spar") in bot.busy:
                taken = True
            else:
                taken = False
                techs = db.get_techniques(bot.conn, uid)
                qi, _ = rules.passive_qi(p, techs, now)          # bank passive Qi before the doors close
                p, events = rules.add_qi(p, qi, techs, now=now)
                end = now + hours * 3600
                save_progress(uid, p, qi_collected_at=now, seclusion_start=now, seclusion_end=end)
        if taken:
            await interaction.response.send_message(
                "You are already in seclusion, or busy with an expedition or spar.", ephemeral=True)
            return
        rate = rules.qi_rate(p, now, techs)[0] * training.SECLUSION_QI_MULTIPLIER
        lines = [f"*You seal the doors and sink into meditation for {hours} hours...*",
                 f"Qi Rate ×{training.SECLUSION_QI_MULTIPLIER:g}: **{rate:,.1f} Qi/hour**. You emerge <t:{int(end)}:R>.",
                 "No exploring or sparring until then. Use **/seclusion** to check or leave early."]
        if qi >= 0.1:
            lines.append(f"(Collected {qi:,.1f} passive Qi first.)")
        await interaction.response.send_message(embed=embed("🧘 Closed-Door Seclusion", "\n".join(lines + events)))

    internal = app_commands.Group(name="internal", description="Your inner cultivation")
    tree.add_command(internal)

    @internal.command(name="qi", description="See your Internal Qi, Qi Rate, time to the next gate and every active boost")
    async def qi_status(interaction: discord.Interaction):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        await interaction.response.defer()
        data = qi.qi_data(p, db.get_techniques(bot.conn, uid))
        image = await card_render.render(render_dantian, data)
        await interaction.followup.send(file=png(image, "qi.png"))

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
        pill = crafting.best_breakthrough_pill(bot.conn, uid, p) if kind == "realm" and chance < 1 else None
        if pill:
            chance = min(1.0, chance + pill[1])
            risk += f"\n🏔️ Your **{pill[0]['name']}** adds **+{pill[1]:.1%}** (used up either way)."
        if chance >= 1 and kind == "realm" and p["realm"] == "Mortal":
            risk = "The Old Master guides you; this first gate cannot fail."

        async def attempt():
            async with bot.db_lock:
                fresh = db.get_player(bot.conn, uid)
                use = None
                if next_gate_is_realm(fresh):
                    use = crafting.best_breakthrough_pill(bot.conn, uid, fresh)
                    if use and rules.breakthrough_chance(fresh) >= 1:
                        use = None
                ok, msg = rules.attempt_breakthrough(fresh, db.get_techniques(bot.conn, uid),
                                                     bonus=use[1] if use else 0)
                if ok is not None:
                    save_progress(uid, fresh)
                    if use:
                        db.remove_item(bot.conn, use[0]["id"])
                        msg += f"\n🏔️ The **{use[0]['name']}** dissolves into your meridians."
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
        if not claim_session(bot, uid, "spar", "spar", technique_rules.SPAR_COOLDOWN_MINUTES * 60):
            await interaction.response.send_message("You are already sparring!", ephemeral=True)
            return
        sent = False
        try:
            view = SparView(bot, uid, focus, trial)
            sent = True        # start() answers at once (defer), so the session is shown from here on
            await view.start(interaction)
        except Exception:
            if not sent:      # never shown: give the cooldown back (once shown, the view's timeout ends it)
                release_session(bot, uid, "spar", "spar")
            raise

    @tree.command(name="techniques", description="See your techniques and mastery, and choose which are equipped")
    async def techniques(interaction: discord.Interaction):
        if not db.get_player(bot.conn, interaction.user.id):
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        await open_sheet(bot, interaction, "techniques")

    @tree.command(name="equipment", description="See your weapon and final stats, and change your weapon")
    async def equipment(interaction: discord.Interaction):
        if not db.get_player(bot.conn, interaction.user.id):
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        await open_sheet(bot, interaction, "equipment")

    @tree.command(name="shop", description="The Moon Pearl shop: rerolls, pills, bag space, name change")
    async def shop(interaction: discord.Interaction):
        p = db.get_player(bot.conn, interaction.user.id)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        view = ShopView(bot, interaction.user.id)
        await interaction.response.send_message(embed=shop_embed(p), view=view)
        view.message = await interaction.original_response()

    @tree.command(name="blessing", description="View and buy Heavenly Blessings with Moon Pearls")
    async def blessing(interaction: discord.Interaction):
        p = db.get_player(bot.conn, interaction.user.id)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        view = BlessingView(bot, interaction.user.id)
        await interaction.response.send_message(embed=blessing_embed(p), view=view)
        view.message = await interaction.original_response()

    @tree.command(name="recharge", description="Moon Pearl Pavilion: see the Moon Pearl packages")
    async def recharge(interaction: discord.Interaction):
        e = embed("🌙 Moon Pearl Pavilion", "\n".join(
            [f"**{name}** · ${price} · 🌙 {pearls:,}" for name, price, pearls in economy.RECHARGE_PACKAGES]
            + ["", f"✨ Your first purchase gives ×{economy.FIRST_PURCHASE_MULTIPLIER} pearls.", "",
               "*Purchases are not open yet. They must go through Discord's own app monetization, which the "
               "bot owner switches on in the Discord Developer Portal.*"]))
        await interaction.response.send_message(embed=e, ephemeral=True)

    @tree.command(name="reroll", description="Fate Reroll: spend Lotus Coins to reroll your talent (it can go lower!)")
    async def reroll(interaction: discord.Interaction):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        cost = rules.fate_reroll_cost(p)
        if p["lotus_coins"] < cost:
            await interaction.response.send_message(
                f"A Fate Reroll costs 🪷 **{cost:,}** Lotus Coins; you have 🪷 {p['lotus_coins']:,}. "
                "(Each reroll costs ×1.5 more. The Moon Pearl shop sells one that never goes lower.)", ephemeral=True)
            return

        async def go():
            async with bot.db_lock:
                fresh = db.get_player(bot.conn, uid)
                price = rules.fate_reroll_cost(fresh)
                if fresh["lotus_coins"] < price:
                    return embed("🎲 Fate Reroll", "You can no longer afford it.")
                if db.spend(bot.conn, uid, "lotus_coins", price, "Fate Reroll") is None:
                    return embed("🎲 Fate Reroll", "You can no longer afford it.")
                new = rules.reroll_talent(fresh["talent"], talent_rules.FATE_REROLL["can_go_lower"])
                db.update_player(bot.conn, uid, talent=new, fate_rerolls=fresh["fate_rerolls"] + 1)
            news = loot.talent_announcement(fresh["name"], new) if new != fresh["talent"] else None
            if news:
                await interaction.channel.send(news)
            return embed("🎲 Fate Reroll", f"The Aptitude Stone glows... **{fresh['talent']} → {new}**\n🪷 −{price:,}")

        view = ConfirmView(uid, f"Reroll for {cost:,} coins", go, emoji="🎲")
        await interaction.response.send_message(embed=embed("🎲 Fate Reroll", (
            f"Your talent: **{p['talent']}**. A reroll costs 🪷 **{cost:,}** and uses the normal odds, "
            "so it **can go lower**.")), view=view, ephemeral=True)

    @tree.command(name="physician", description="Pay a physician in Lotus Coins to heal your injury now")
    async def physician(interaction: discord.Interaction):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        left = rules.injured_for(p)
        if not left:
            await interaction.response.send_message("🩺 *\"You look perfectly healthy to me.\"*", ephemeral=True)
            return
        cost = rules.physician_cost(p)

        async def heal():
            async with bot.db_lock:
                fresh = db.get_player(bot.conn, uid)
                price = rules.physician_cost(fresh)
                if fresh["lotus_coins"] < price:
                    return embed("🩺 Physician", f"You need 🪷 {price:,} but have 🪷 {fresh['lotus_coins']:,}.")
                if db.spend(bot.conn, uid, "lotus_coins", price, "Physician") is None:
                    return embed("🩺 Physician", f"You need 🪷 {price:,} but have 🪷 {fresh['lotus_coins']:,}.")
                db.update_player(bot.conn, uid, injured_until=None)
            return embed("🩺 Physician", f"Needles, herbs and a bitter tea. You are healed! 🪷 −{price:,}")

        view = ConfirmView(uid, f"Heal for {cost:,} coins", heal, style=discord.ButtonStyle.success, emoji="🩺")
        await interaction.response.send_message(embed=embed("🩺 Physician", (
            f"You are injured for another **{rules.fmt_duration(left)}**. Healing now costs 🪷 **{cost:,}**.")),
            view=view, ephemeral=True)

    @tree.command(name="cooldown", description="See every timer at once: cooldowns, daily limits, seclusion, injury and boons")
    async def cooldown(interaction: discord.Interaction):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        e = discord.Embed(title=f"⏳ {p['name']}'s Incense Clock",
                          description="*The incense burns down; the Dao waits for no one.*",
                          color=economy.BALANCE_EMBED_COLOR)
        for title, lines in cooldowns.timer_sections(bot.conn, p):
            e.add_field(name=title, value="\n".join(lines), inline=False)
        e.set_footer(text="Times are shown in your own time zone. Daily counts renew at midnight UTC.")
        await interaction.response.send_message(embed=e)

    @tree.command(name="bestiary", description="The beasts of a realm, with their strength against you")
    @app_commands.describe(realm="Which realm's beasts (defaults to yours)")
    @app_commands.choices(realm=[app_commands.Choice(name=r, value=r) for r in rules.REALM_ORDER])
    async def bestiary(interaction: discord.Interaction, realm: app_commands.Choice[str] | None = None):
        p = db.get_player(bot.conn, interaction.user.id)
        if not p:
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        r = realm.value if realm else p["realm"]
        ref = dict(p, realm=r, layer=p["layer"] if r == p["realm"] else 1)
        icons = {"normal": "🐾 Normal", "elite": "⚔️ Elite", "beast_king": "👑 Beast King"}
        e = embed(f"📖 Bestiary · {r}", "Stats at " + (f"your layer ({rules.ordinal(ref['layer'])})" if r == p["realm"]
                                                     else "1st Layer") + ". Elites and Kings are for teams; "
                  "find their lairs in /explore.")
        for b in beast_rules.BEASTS[r]:
            st = (combat.beast_stats(ref, b) if b[1] == "normal"
                  else hunt.team_beast({"beast": b}, [ref]))
            dodge = " · 15% dodge" if st["dodge"] else ""
            e.add_field(name=f"{b[0]}", value=(f"{icons[b[1]]} · {b[2].title()}\n❤️ {st['max_hp']:,} · "
                                                f"⚔️ {st['attack']:,.0f} · 🛡️ {st['defense']:,.0f}{dodge}"))
        kills = rules.king_kills(p)
        if kills:
            e.set_footer(text="Beast Kings slain in: " + ", ".join(kills))
        await interaction.response.send_message(embed=e)
