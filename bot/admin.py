"""
Admin-only testing commands: /admin reset, /admin give, /admin item, /admin duelstats, and the /admin set_*
commands that set a player's realm, technique mastery, alchemist rank, blacksmith rank and Herbal Insight.

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
import equipments
import forge
import technique as tech_data

from . import crafting, db, forging, item_catalog, loot
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


# ── /admin set_* (pure helpers, so the tests can call them) ──

def set_realm(conn, user_id, realm, layer):
    """Put the player at `realm`, `layer` (clamped to the realm's layers) with an empty Qi bar.
    Returns the layer actually set."""
    layer = max(1, min(layer, rules.max_layer(realm)))
    db.update_player(conn, user_id, realm=realm, layer=layer, qi=0.0, qi_overflow=0.0, qi_ping_gate=None)
    return layer


def find_techniques(techs, text):
    """The techniques `text` names: "all" (or nothing), a technique id, or (part of) a name.
    Returns a list (empty if nothing matches)."""
    text = (text or "").strip().lower()
    if text in ("", "all", "all techniques"):
        return list(techs)
    if text.isdigit():
        hit = [t for t in techs if t["id"] == int(text)]
        if hit:
            return hit
    exact = [t for t in techs if t["name"].lower() == text]
    return exact or [t for t in techs if text in t["name"].lower()]


def stage_exp(tech, stage):
    """Mastery EXP at the start of `stage` for this technique's grade."""
    return round(tech_data.MASTERY_STAGES[stage]["exp_to_reach"] * tech_data.GRADE_EXP_MULTIPLIER[tech["grade"]])


def set_mastery(conn, techs, stage, full_bar=False):
    """Set each technique's mastery stage. EXP goes to the start of that stage, or to a full bar (ready for
    the trial to the next stage) when `full_bar`. Returns one line per technique."""
    lines = []
    last = len(tech_data.MASTERY_STAGES) - 1
    for t in techs:
        exp = stage_exp(t, stage)
        ready = full_bar and stage < last
        if ready:
            exp = stage_exp(t, stage + 1)
        db.set_mastery(conn, t["id"], exp=exp, stage=stage)
        line = f"📜 **{t['name']}** → **{tech_data.MASTERY_STAGES[stage]['name']}** ({exp:,} EXP)"
        if ready:
            line += f" · bar full, ready for the trial to **{tech_data.MASTERY_STAGES[stage + 1]['name']}**"
        lines.append(line)
    return lines


def set_alchemy_rank(conn, user_id, rank):
    db.update_player(conn, user_id, alchemy_exp=alchemy.ALCHEMIST_RANK_EXP[rank])
    return f"⚗️ Alchemist rank set to **{crafting.rank_label(rank)}** ({alchemy.ALCHEMIST_RANK_EXP[rank]:,} EXP)"


def set_blacksmith_rank(conn, user_id, rank):
    db.update_player(conn, user_id, blacksmith_exp=forge.BLACKSMITH_RANK_EXP[rank])
    return f"🔨 Blacksmith rank set to **{forging.rank_label(rank)}** ({forge.BLACKSMITH_RANK_EXP[rank]:,} EXP)"


def set_foraging(conn, user_id, insight=None, herbs_gathered=None):
    """/gather progress: the Herbal Insight streak (raises old-herb chances) and the herbs-gathered count."""
    fields, lines = {}, []
    if insight is not None:
        fields["herb_streak"] = insight
        mult = next(m for min_streak, m in alchemy.STREAK_BONUS if insight >= min_streak)
        lines.append(f"🔥 Herbal Insight set to **{insight}** (old herbs ×{mult:g})")
    if herbs_gathered is not None:
        fields["herbs_gathered"] = herbs_gathered
        lines.append(f"🌿 Herbs gathered set to **{herbs_gathered:,}**")
    db.update_player(conn, user_id, **fields)
    return lines


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

    quality_choices = [app_commands.Choice(name=q.title(), value=q) for q in item_catalog.QUALITY_POS]
    age_choices = [app_commands.Choice(name=f"{a}-year", value=a) for a in sorted(alchemy.HERB_AGES)]

    async def give_item_lines(uid, item, amount, quality, age, patterns, member):
        """Give a catalog item. Returns (reply line, None) or (None, why not)."""
        entry_id, problem = item_catalog.resolve(item)
        if problem:
            return None, problem
        if item_catalog.CATALOG[entry_id]["kind"] in item_catalog.GEAR_KINDS + ("artifact",):
            amount = min(amount, item_catalog.MAX_GEAR)
        async with bot.db_lock:
            stored, lost = give_item(bot.conn, uid, entry_id, amount, quality and quality.value,
                                     age and age.value, patterns)
        who, whose = (member.mention, f"{member.mention}'s") if member else ("you", "Your")
        return item_reply(entry_id, stored, lost, who, whose), None

    @group.command(name="give", description="Give any item (weapon, armor, artifact, material, herb, pill...), "
                                            "coins, pearls or Qi")
    @app_commands.describe(
        item="An item: start typing a name (weapon, armor, artifact, material, herb, pill, manual, chest)",
        amount="How many of the item (weapons, armor and artifacts: up to 25)",
        member="Who gets it (defaults to you)", lotus_coins="Lotus Coins to add",
        moon_pearls="Moon Pearls to add", qi="Internal Qi to add (levels up like normal Qi)",
        quality="Weapons and armor: how good the stats are (default: random, like a drop)",
        age="Herbs: how old (default 10-year)",
        patterns="Pills: pill patterns 1-9 (default: shop Qi pill, other pills 5)")
    @app_commands.choices(quality=quality_choices, age=age_choices)
    async def give_cmd(interaction: discord.Interaction, member: discord.User | None = None,
                       item: str | None = None,
                       amount: app_commands.Range[int, 1, 100_000] = 1,
                       lotus_coins: app_commands.Range[int, 0, 10_000_000] = 0,
                       moon_pearls: app_commands.Range[int, 0, 1_000_000] = 0,
                       qi: app_commands.Range[int, 0, 100_000_000] = 0,
                       quality: app_commands.Choice[str] | None = None,
                       age: app_commands.Choice[int] | None = None,
                       patterns: app_commands.Range[int, 1, 9] | None = None):
        uid = await check(interaction, member)
        if uid is None:
            return
        if not (item or lotus_coins or moon_pearls or qi):
            await interaction.response.send_message(
                "Pick something to give: an **item** (start typing its name), lotus_coins, moon_pearls or qi.",
                ephemeral=True)
            return
        lines = []
        if item:
            line, problem = await give_item_lines(uid, item, amount, quality, age, patterns, member)
            if problem:
                await interaction.response.send_message(problem, ephemeral=True)
                return
            lines.append(line)
        if lotus_coins or moon_pearls or qi:
            async with bot.db_lock:
                events = give(bot.conn, uid, lotus_coins, moon_pearls, qi)
                p = db.get_player(bot.conn, uid)
            got = [s for n, s in ((lotus_coins, f"🪷 {lotus_coins:,} Lotus Coins"),
                                  (moon_pearls, f"🌙 {moon_pearls:,} Moon Pearls"), (qi, f"✨ {qi:,} Qi")) if n]
            lines += [f"🎁 Gave {', '.join(got)} to {member.mention if member else 'you'}.",
                      f"Now: **{p['realm']}, {rules.ordinal(p['layer'])} Layer** · Qi {p['qi']:,.1f} / "
                      f"{rules.qi_needed(p['realm'], p['layer']):,} · 🪷 {p['lotus_coins']:,} · "
                      f"🌙 {p['moon_pearls']:,}"] + events
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @give_cmd.autocomplete("item")
    async def give_autocomplete(interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=label, value=i) for i, label in item_catalog.search(current)]

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
        line, problem = await give_item_lines(uid, item, amount, quality, age, patterns, member)
        await interaction.response.send_message(problem or line, ephemeral=True)

    @item_cmd.autocomplete("item")
    async def item_autocomplete(interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=label, value=i) for i, label in item_catalog.search(current)]

    # ── one command per kind of item, with pick lists (nothing to type) ──
    def picks(pairs):
        return [app_commands.Choice(name=label[:100], value=value) for value, label in pairs]

    tier_choices = picks([(t, equipments.TIER_DISPLAY[t]) for t in equipments.TIERS])
    grade_choices = picks([(g, g) for g in alchemy.GRADES])
    amount_help = "How many (default 1)"
    member_help = "Who gets it (defaults to you)"

    async def give_picked(interaction, member, entry_id, amount, quality=None, age=None, patterns=None):
        uid = await check(interaction, member)
        if uid is None:
            return
        line, problem = await give_item_lines(uid, entry_id, amount, quality, age, patterns, member)
        await interaction.response.send_message(problem or line, ephemeral=True)

    @group.command(name="give_weapon", description="Give a weapon: pick the type and tier")
    @app_commands.describe(weapon="Weapon type", tier="Tier", amount=amount_help, member=member_help,
                           quality="How good the stats are (default: random, like a drop)")
    @app_commands.choices(weapon=picks([(w, w.title()) for w in equipments.WEAPON_TYPES]), tier=tier_choices,
                          quality=quality_choices)
    async def give_weapon(interaction: discord.Interaction, weapon: app_commands.Choice[str],
                          tier: app_commands.Choice[str], amount: app_commands.Range[int, 1, 25] = 1,
                          quality: app_commands.Choice[str] | None = None, member: discord.User | None = None):
        await give_picked(interaction, member, f"weapon:{tier.value}:{weapon.value}", amount, quality)

    @group.command(name="give_armor", description="Give armor: pick the type and tier")
    @app_commands.describe(armor="Armor type", tier="Tier", amount=amount_help, member=member_help,
                           quality="How good the stats are (default: random, like a drop)")
    @app_commands.choices(armor=picks([(a, equipments.ARMOR_TYPE_DISPLAY[a][1]) for a in equipments.ARMOR_TYPES]),
                          tier=tier_choices, quality=quality_choices)
    async def give_armor(interaction: discord.Interaction, armor: app_commands.Choice[str],
                         tier: app_commands.Choice[str], amount: app_commands.Range[int, 1, 25] = 1,
                         quality: app_commands.Choice[str] | None = None, member: discord.User | None = None):
        await give_picked(interaction, member, f"armor:{tier.value}:{armor.value}", amount, quality)

    @group.command(name="give_artifact", description="Give an artifact: pick what it does and its tier")
    @app_commands.describe(artifact="Which artifact (what it does)", tier="Tier", amount=amount_help,
                           member=member_help)
    @app_commands.choices(artifact=picks(item_catalog.artifact_families()), tier=tier_choices)
    async def give_artifact(interaction: discord.Interaction, artifact: app_commands.Choice[str],
                            tier: app_commands.Choice[str], amount: app_commands.Range[int, 1, 25] = 1,
                            member: discord.User | None = None):
        await give_picked(interaction, member, f"artifact:{tier.value}:{artifact.value}", amount)

    @group.command(name="give_herb", description="Give herbs: pick the kind, grade and age")
    @app_commands.describe(herb="Kind of herb", grade="Grade (Mortal is the lowest)", amount=amount_help,
                           age="How old (default 10-year)", member=member_help)
    @app_commands.choices(herb=picks(item_catalog.herb_types()), grade=grade_choices, age=age_choices)
    async def give_herb(interaction: discord.Interaction, herb: app_commands.Choice[str],
                        grade: app_commands.Choice[str], amount: app_commands.Range[int, 1, 100_000] = 1,
                        age: app_commands.Choice[int] | None = None, member: discord.User | None = None):
        await give_picked(interaction, member, f"herb:{grade.value}:{herb.value}", amount, age=age)

    @group.command(name="give_pill", description="Give pills: pick the kind and grade")
    @app_commands.describe(pill="Kind of pill", grade="Grade (Mortal is the lowest)", amount=amount_help,
                           patterns="Pill patterns 1-9 (default: shop Qi pill, other pills 5)", member=member_help)
    @app_commands.choices(pill=picks(item_catalog.pill_kinds()), grade=grade_choices)
    async def give_pill(interaction: discord.Interaction, pill: app_commands.Choice[str],
                        grade: app_commands.Choice[str] | None = None,
                        amount: app_commands.Range[int, 1, 100_000] = 1,
                        patterns: app_commands.Range[int, 1, 9] | None = None, member: discord.User | None = None):
        entry_id = "pill:heaven_defying" if pill.value == "heaven_defying" else \
            f"pill:{pill.value}:{grade.value if grade else alchemy.GRADES[0]}"
        await give_picked(interaction, member, entry_id, amount, patterns=patterns)

    @group.command(name="give_material", description="Give forging materials: pick the type, then the material")
    @app_commands.describe(material_type="Type of material", material="Which one (pick from the list)",
                           amount=amount_help, member=member_help)
    @app_commands.choices(material_type=picks(item_catalog.material_groups()))
    async def give_material(interaction: discord.Interaction, material_type: app_commands.Choice[str],
                            material: str | None = None, amount: app_commands.Range[int, 1, 100_000] = 1,
                            member: discord.User | None = None):
        options = item_catalog.search("", limit=100, prefix="material:" + material_type.value)
        if material:
            entry_id = material if material in item_catalog.CATALOG else None
            if entry_id is None:
                found = item_catalog.search(material, limit=100, prefix="material:" + material_type.value)
                entry_id = found[0][0] if len(found) == 1 else None
        else:
            entry_id = options[0][0] if len(options) == 1 else None
        if entry_id is None:
            names = ", ".join(f"**{item_catalog.CATALOG[i]['name']}**" for i, _ in options)
            await interaction.response.send_message(f"Pick a **material** from the list: {names}", ephemeral=True)
            return
        await give_picked(interaction, member, entry_id, amount)

    @give_material.autocomplete("material")
    async def material_autocomplete(interaction: discord.Interaction, current: str):
        group_value = getattr(interaction.namespace, "material_type", None)
        prefix = "material:" + group_value if group_value else None
        return [app_commands.Choice(name=label, value=i)
                for i, label in item_catalog.search(current, prefix=prefix, kind="material")]

    # ── /admin set_*: realm, technique mastery, alchemy, forging, foraging ──
    def whose_text(member):
        return f"{member.mention}'s" if member else "Your"

    realm_choices = picks([(r, r) for r in rules.REALM_ORDER])

    @group.command(name="set_realm", description="Set a martial art realm and layer (the Qi bar starts empty)")
    @app_commands.describe(realm="Realm (pick from the list)",
                           layer="Layer 1-10 (Mortal has 3; default 1)", member=member_help)
    @app_commands.choices(realm=realm_choices)
    async def set_realm_cmd(interaction: discord.Interaction, realm: app_commands.Choice[str],
                            layer: app_commands.Range[int, 1, 10] = 1, member: discord.User | None = None):
        uid = await check(interaction, member)
        if uid is None:
            return
        async with bot.db_lock:
            got = set_realm(bot.conn, uid, realm.value, layer)
        text = f"🏔️ {whose_text(member)} realm is now **{realm.value}, {rules.ordinal(got)} Layer** " \
               f"(Qi 0 / {rules.qi_needed(realm.value, got):,})."
        if got != layer:
            text += f"\n{realm.value} has only {rules.max_layer(realm.value)} layers."
        await interaction.response.send_message(text, ephemeral=True)

    stage_choices = picks([(i, s["name"]) for i, s in enumerate(tech_data.MASTERY_STAGES)])

    @group.command(name="set_mastery", description="Set a technique's mastery stage (or all of them)")
    @app_commands.describe(stage="Mastery stage (Glimpsing the Gate is the lowest)", technique="Which technique (pick from the list; "
                                                                 "default: all of them)",
                           full_bar="Fill the EXP bar so the trial to the next stage is ready (default: no)",
                           member=member_help)
    @app_commands.choices(stage=stage_choices)
    async def set_mastery_cmd(interaction: discord.Interaction, stage: app_commands.Choice[int],
                              technique: str | None = None, full_bar: bool = False,
                              member: discord.User | None = None):
        uid = await check(interaction, member)
        if uid is None:
            return
        async with bot.db_lock:
            techs = db.get_techniques(bot.conn, uid, equipped_only=False)
            hit = find_techniques(techs, technique)
            if hit:
                lines = set_mastery(bot.conn, hit, stage.value, full_bar)
        if not hit:
            names = ", ".join(f"**{t['name']}**" for t in techs) or "none"
            await interaction.response.send_message(
                f"No technique matches that. {whose_text(member)} techniques: {names}", ephemeral=True)
            return
        await interaction.response.send_message("\n".join(lines)[:2000], ephemeral=True)

    @set_mastery_cmd.autocomplete("technique")
    async def technique_autocomplete(interaction: discord.Interaction, current: str):
        target = getattr(interaction.namespace, "member", None) or interaction.user
        techs = db.get_techniques(bot.conn, target.id, equipped_only=False)
        shown = find_techniques(techs, current) if current else techs
        out = [app_commands.Choice(name="All techniques", value="all")] if not current else []
        for t in shown:
            label = f"{t['name']} · {t['grade']} {t['type']} · {tech_data.MASTERY_STAGES[rules.stage_of(t)]['name']}"
            out.append(app_commands.Choice(name=label[:100], value=str(t["id"])))
        return out[:25]

    rank_choices = picks([(r, crafting.rank_label(r)) for r in sorted(alchemy.ALCHEMIST_RANK_EXP)])

    @group.command(name="set_alchemy", description="Set the alchemist rank (for /craft)")
    @app_commands.describe(rank="Alchemist rank (1st Grade is the lowest)", member=member_help)
    @app_commands.choices(rank=rank_choices)
    async def set_alchemy_cmd(interaction: discord.Interaction, rank: app_commands.Choice[int],
                              member: discord.User | None = None):
        uid = await check(interaction, member)
        if uid is None:
            return
        async with bot.db_lock:
            line = set_alchemy_rank(bot.conn, uid, rank.value)
        await interaction.response.send_message(line, ephemeral=True)

    @group.command(name="set_blacksmith", description="Set the blacksmith rank (for /forge)")
    @app_commands.describe(rank="Blacksmith rank (1st Grade is the lowest)", member=member_help)
    @app_commands.choices(rank=rank_choices)
    async def set_blacksmith_cmd(interaction: discord.Interaction, rank: app_commands.Choice[int],
                                 member: discord.User | None = None):
        uid = await check(interaction, member)
        if uid is None:
            return
        async with bot.db_lock:
            line = set_blacksmith_rank(bot.conn, uid, rank.value)
        await interaction.response.send_message(line, ephemeral=True)

    @group.command(name="set_foraging", description="Set /gather progress: Herbal Insight streak and herbs gathered")
    @app_commands.describe(insight="Herbal Insight streak (10 = old herbs ×1.5, 25 = ×2, 50 = ×3)",
                           herbs_gathered="Herbs gathered (shown on the profile)", member=member_help)
    async def set_foraging_cmd(interaction: discord.Interaction,
                               insight: app_commands.Range[int, 0, 100_000] | None = None,
                               herbs_gathered: app_commands.Range[int, 0, 10_000_000] | None = None,
                               member: discord.User | None = None):
        uid = await check(interaction, member)
        if uid is None:
            return
        if insight is None and herbs_gathered is None:
            await interaction.response.send_message("Pick **insight** and/or **herbs_gathered** to set.",
                                                    ephemeral=True)
            return
        async with bot.db_lock:
            lines = set_foraging(bot.conn, uid, insight, herbs_gathered)
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

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
