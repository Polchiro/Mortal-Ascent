"""
Admin-only testing commands: /admin reset, /admin give, /admin item, /admin duelstats.

/admin item gives any item in the game (weapons, armor, artifacts, forging materials, Beast Cores,
herbs, pills, manuals, chests). The item list comes from bot/item_catalog.py, which reads the data modules.

Only the bot's owner (the account that owns the app in the Discord Developer Portal) and the
user IDs listed in ADMIN_IDS (comma-separated, in .env) can use them. Everyone else gets a
refusal, even if a server admin makes the commands visible to them.
"""
import os
import time

import discord
from discord import app_commands

import alchemy

from . import db, item_catalog, loot
from . import player as rules


def admin_ids_from_env():
    """User IDs from ADMIN_IDS, e.g. ADMIN_IDS=123456789012345678,987654321098765432"""
    ids = set()
    for part in os.environ.get("ADMIN_IDS", "").replace(" ", "").split(","):
        if part.isdigit():
            ids.add(int(part))
    return ids


def reset_player(conn, user_id, now=None):
    """Clear every cooldown and daily limit, heal injuries, end a running seclusion timer.
    Returns a list of what changed (for the reply)."""
    now = time.time() if now is None else now
    done = []
    with conn:
        n = conn.execute("DELETE FROM cooldowns WHERE user_id = ?", (user_id,)).rowcount
        if n:
            done.append(f"Cleared {n} cooldown(s) (explore, train, practice, spar, mastery trials)")
        n = conn.execute("DELETE FROM daily_counts WHERE user_id = ?", (user_id,)).rowcount
        if n:
            done.append("Reset today's practice and spar counts (full EXP again)")
    p = db.get_player(conn, user_id)
    if rules.injured_for(p, now):
        db.update_player(conn, user_id, injured_until=None)
        done.append("Healed the injury")
    if rules.in_seclusion(p) and p["seclusion_end"] > now:
        db.update_player(conn, user_id, seclusion_end=now)
        done.append("Seclusion timer finished: run **/seclusion** to collect the Qi (with ×2)")
    return done


def give(conn, user_id, lotus_coins=0, moon_pearls=0, qi=0.0, now=None):
    """Add currency and Qi (Qi goes through the normal level-up rules). Returns event lines."""
    p = db.get_player(conn, user_id)
    events = []
    fields = {}
    for currency, amount in (("lotus_coins", lotus_coins), ("moon_pearls", moon_pearls)):
        if amount:
            db.change_currency(conn, user_id, currency, amount, "Admin gift", clamp=True)
    if qi:
        techs = db.get_techniques(conn, user_id)
        p, events = rules.add_qi(p, qi, techs, now=now)
        fields.update(qi=p["qi"], qi_overflow=p["qi_overflow"], layer=p["layer"])
    db.update_player(conn, user_id, **fields)
    return events


def give_item(conn, user_id, entry_id, qty=1, quality=None, age=None, patterns=None):
    """Put `qty` of a catalog item in the player's bag. Returns (stored, left_behind) like loot.store."""
    return loot.store(conn, user_id, item_catalog.make(entry_id, qty, quality, age, patterns))


def item_reply(entry_id, stored, lost, who="you", whose="Your"):
    """The text /admin item answers with."""
    if not stored:
        return f"🎒 {whose} bag is full, so nothing was given. Free a slot and try again."
    if item_catalog.CATALOG[entry_id]["kind"] in item_catalog.GEAR_KINDS + ("artifact",):
        names = {}
        for it in stored:
            names[it["name"]] = names.get(it["name"], 0) + 1
        got = ", ".join(f"**{n}**" + (f" ×{k}" if k > 1 else "") for n, k in names.items())
    else:
        got = f"**{loot.describe(stored[0])}**"
    text = f"🎁 Gave {got} to {who}."
    if lost:
        text += f"\n🎒 The bag filled up: {len(lost)} more could not fit."
    return text


def duelstats_text(conn):
    """Each technique's (and basic move's) pick count and win rate in duels (docs/pvp.md), for balancing."""
    summary, rows = db.duel_stats(conn)
    if not summary["duels"]:
        return "No duels have been fought yet."
    head = (f"**{summary['duels']:,}** duels · {summary['draws']:,} draws · {summary['avg_turns']:.1f} turns on average\n"
            "*Picks: turns it was played (timeouts left out). Win rate: share of the duels where a player played it "
            "that this player won.*")
    tech = [r for r in rows if r["kind"].endswith("_tech")]
    basic = [r for r in rows if not r["kind"].endswith("_tech")]

    def line(r):
        rate = r["wins"] / r["duels"] if r["duels"] else 0
        icon = "⚔️" if r["kind"] in ("attack_tech", "strike", "break") else "🛡️"
        return f"{icon} **{r['name'].title() if r['kind'] == r['name'] else r['name']}** · {r['picks']:,} picks · " \
               f"{r['duels']:,} duels · **{rate:.0%}** wins"
    parts = [head, "", "**Techniques**"] + ([line(r) for r in tech] or ["None picked yet"])
    parts += ["", "**Basic moves**"] + [line(r) for r in basic]
    return "\n".join(parts)[:4000]


def register(bot):
    group = app_commands.Group(
        name="admin", description="Testing tools for the bot owner",
        default_permissions=discord.Permissions(administrator=True))   # hidden from regular members
    owner_ids = set()

    async def is_admin(user_id):
        if not owner_ids:
            info = await bot.application_info()
            if info.team:
                owner_ids.update(m.id for m in info.team.members)
            elif info.owner:
                owner_ids.add(info.owner.id)
        return user_id in owner_ids or user_id in admin_ids_from_env()

    async def check(interaction, member):
        """Return the target user ID, or None after replying with why not."""
        if not await is_admin(interaction.user.id):
            await interaction.response.send_message("⛔ Only the bot owner can use admin commands.", ephemeral=True)
            return None
        target = member or interaction.user
        if not db.get_player(bot.conn, target.id):
            await interaction.response.send_message(f"{target.mention} has not used **/start** yet.", ephemeral=True)
            return None
        return target.id

    @group.command(name="reset", description="Reset all cooldowns, daily limits and injuries (yours or a player's)")
    @app_commands.describe(member="Whose cooldowns to reset (defaults to you)")
    async def reset(interaction: discord.Interaction, member: discord.User | None = None):
        uid = await check(interaction, member)
        if uid is None:
            return
        async with bot.db_lock:
            done = reset_player(bot.conn, uid)
        stuck = {k for k in bot.busy if k[0] == uid}
        bot.busy -= stuck
        if stuck:
            done.append("Cleared a stuck explore/train/spar session")
        who = member.mention if member else "You"
        text = "\n".join(f"• {d}" for d in done) if done else "Nothing was on cooldown."
        await interaction.response.send_message(f"🔄 **{who}: everything is ready again.**\n{text}", ephemeral=True)

    @group.command(name="give", description="Give Lotus Coins, Moon Pearls or Internal Qi (yours or a player's)")
    @app_commands.describe(member="Who gets it (defaults to you)", lotus_coins="Lotus Coins to add",
                           moon_pearls="Moon Pearls to add", qi="Internal Qi to add (levels up like normal Qi)")
    async def give_cmd(interaction: discord.Interaction, member: discord.User | None = None,
                       lotus_coins: app_commands.Range[int, 0, 10_000_000] = 0,
                       moon_pearls: app_commands.Range[int, 0, 1_000_000] = 0,
                       qi: app_commands.Range[int, 0, 100_000_000] = 0):
        uid = await check(interaction, member)
        if uid is None:
            return
        if not (lotus_coins or moon_pearls or qi):
            await interaction.response.send_message("Pick an amount: lotus_coins, moon_pearls or qi.", ephemeral=True)
            return
        async with bot.db_lock:
            events = give(bot.conn, uid, lotus_coins, moon_pearls, qi)
            p = db.get_player(bot.conn, uid)
        got = [s for n, s in ((lotus_coins, f"🪷 {lotus_coins:,} Lotus Coins"),
                              (moon_pearls, f"🌙 {moon_pearls:,} Moon Pearls"), (qi, f"✨ {qi:,} Qi")) if n]
        lines = [f"🎁 Gave {', '.join(got)} to {member.mention if member else 'you'}.",
                 f"Now: **{p['realm']}, {rules.ordinal(p['layer'])} Layer** · Qi {p['qi']:,.1f} / "
                 f"{rules.qi_needed(p['realm'], p['layer']):,} · 🪷 {p['lotus_coins']:,} · 🌙 {p['moon_pearls']:,}"]
        await interaction.response.send_message("\n".join(lines + events), ephemeral=True)

    quality_choices = [app_commands.Choice(name=q.title(), value=q) for q in item_catalog.QUALITY_POS]
    age_choices = [app_commands.Choice(name=f"{a}-year", value=a) for a in sorted(alchemy.HERB_AGES)]

    @group.command(name="item", description="Give any item: weapon, armor, artifact, material, herb, pill, manual, chest")
    @app_commands.describe(
        item="Start typing a name, then pick it from the list",
        amount="How many (weapons, armor and artifacts: up to 25, one bag slot each)",
        member="Who gets it (defaults to you)",
        quality="Weapons and armor: how good the stats are (default: random, like a drop)",
        age="Herbs: how old (default 10-year)",
        patterns="Pills: pill patterns 1-9 (default: shop Qi pill, other pills 5)")
    @app_commands.choices(quality=quality_choices, age=age_choices)
    async def item_cmd(interaction: discord.Interaction, item: str,
                       amount: app_commands.Range[int, 1, 100_000] = 1,
                       member: discord.User | None = None,
                       quality: app_commands.Choice[str] | None = None,
                       age: app_commands.Choice[int] | None = None,
                       patterns: app_commands.Range[int, 1, 9] | None = None):
        uid = await check(interaction, member)
        if uid is None:
            return
        entry_id, problem = item_catalog.resolve(item)
        if problem:
            await interaction.response.send_message(problem, ephemeral=True)
            return
        if item_catalog.CATALOG[entry_id]["kind"] in item_catalog.GEAR_KINDS + ("artifact",):
            amount = min(amount, item_catalog.MAX_GEAR)
        async with bot.db_lock:
            stored, lost = give_item(bot.conn, uid, entry_id, amount, quality and quality.value,
                                     age and age.value, patterns)
        who, whose = (member.mention, f"{member.mention}'s") if member else ("you", "Your")
        await interaction.response.send_message(item_reply(entry_id, stored, lost, who, whose), ephemeral=True)

    @item_cmd.autocomplete("item")
    async def item_autocomplete(interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=label, value=i) for i, label in item_catalog.search(current)]

    @group.command(name="duelstats", description="Duel balance: each technique's pick count and win rate")
    async def duelstats(interaction: discord.Interaction):
        if not await is_admin(interaction.user.id):
            await interaction.response.send_message("⛔ Only the bot owner can use admin commands.", ephemeral=True)
            return
        async with bot.db_lock:
            text = duelstats_text(bot.conn)
        await interaction.response.send_message(
            embed=discord.Embed(title="⚔️ Duel stats", description=text, color=0xB02C22), ephemeral=True)

    bot.tree.add_command(group)
