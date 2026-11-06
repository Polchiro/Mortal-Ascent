"""
/forge (and "m forge"): the Discord side of the blacksmith minigame (docs/forge.md, section 5).

One message, edited at every step: choose gear → choose Enchant / Reroll / Replace and the extras → see the cost
→ Begin → five stages on the Forge Hall card (cards/forge.py) → the result. The rules and numbers live in
bot/forging.py and forge.py; this file only shows them and passes the clicks on.
"""
import asyncio
import logging
import random
import time

import discord

import forge

from . import db, forge_card, forging, materials, passives
from . import render as card_render
from .fight_view import jpg
from .views import OwnedView
from cards.forge import render_forge

log = logging.getLogger("mortal-ascent")
COLOR = 0xE07A2A                     # molten orange, the "forge" accent
GEAR_EMOJI = {"weapon": "⚔️", "armor": "🛡️", "artifact": "🔮"}
ACTION_EMOJI = {"enchant": "✨", "reroll": "🎲", "replace": "🔒"}
ACTION_HELP = {
    "enchant": "Fill an empty slot with a new passive.",
    "reroll": "Forge every slot again. The old passives are replaced.",
    "replace": "Lock one slot with a Seal Stone and forge the other.",
}
BUTTON_STYLE = {"pump": discord.ButtonStyle.danger, "keep": discord.ButtonStyle.danger,
                "reheat": discord.ButtonStyle.danger, "vent": discord.ButtonStyle.primary,
                "water": discord.ButtonStyle.primary, "oil": discord.ButtonStyle.secondary,
                "plunge": discord.ButtonStyle.success, "pull": discord.ButtonStyle.success,
                "hard": discord.ButtonStyle.secondary, "light": discord.ButtonStyle.secondary}
NONE = "none"


def button_emoji(bot, key, default):
    """The drawn medallion uploaded as an application emoji (cards/forge_icons.py), else the plain emoji."""
    em = getattr(bot, "emojis_ma", None)
    custom = getattr(em, "custom", {}).get("forge_" + key) if em else None
    return custom or default


def slot_lines(item):
    gear = passives.gear_kind(item)
    out = []
    for i, key in enumerate(passives.slots(item)):
        if key:
            ps = forge.PASSIVES[gear][key]
            out.append(f"Slot {i + 1}: {forge.RARITY_EMOJI[ps['rarity']]} **{ps['name']}**: {ps['text']}")
        else:
            out.append(f"Slot {i + 1}: ▫️ *Empty slot*")
    return out


class ForgeView(OwnedView):
    """Picker → plan (action, extras, cost) → stages → result, all in one message."""

    def __init__(self, bot, owner_id, rng=None):
        super().__init__(owner_id, timeout=forge.IDLE_TIMEOUT_SECONDS)
        self.bot, self.rng = bot, rng or random.Random()
        self.item_id = None
        self.action = None
        self.essence = self.fuel = self.liquid = None
        self.lock = None
        self.plan = None             # the Plan being played
        self.game = None
        self.outcome = None
        self.result_lines = None
        self.notice = None
        self.news = None
        self.timer = None
        self.shown_at = None
        self.build()

    @property
    def conn(self):
        return self.bot.conn

    @property
    def player(self):
        return db.get_player(self.conn, self.owner_id)

    def item(self):
        return db.get_item(self.conn, self.owner_id, self.item_id) if self.item_id else None

    def current_plan(self):
        it = self.item()
        if not it or not self.action:
            return None
        return forging.make_plan(self.conn, self.owner_id, it, self.action, self.essence, self.fuel, self.liquid,
                                 self.lock)

    def rank_line(self):
        exp = self.player["blacksmith_exp"]
        r = forging.rank_of(exp)
        nxt = forge.BLACKSMITH_RANK_EXP.get(r + 1)
        return (f"{forging.rank_label(r)} Blacksmith · {exp:,} EXP"
                + (f" / {nxt:,} for {forging.rank_label(r + 1)}" if nxt else " · max rank"))

    # ── screens ──────────────────────────────────────────────────────

    def embed(self):
        if self.game and not self.game.done:
            return self.stage_embed()
        if self.result_lines:
            e = discord.Embed(title="⚒️ The Forge Cools", description="\n".join(self.result_lines), color=COLOR)
            e.set_footer(text=self.rank_line())
            return e
        if self.item_id:
            return self.plan_embed()
        return self.picker_embed()

    def picker_embed(self):
        e = discord.Embed(title="⚒️ The Forge Hall", color=COLOR, description=(
            "Choose a weapon, armor or artifact to forge. A forge puts a **passive** in one of its slots: "
            "five stages (Ignite, Heat, Hammer, Quench, Inscribe), each worth up to 20 points.\n\n"
            f"Below **{forge.FAIL_BELOW}** the forge fails: the materials are lost, the gear and its passives stay. "
            "A higher score gives a rarer passive, up to the gear's tier cap."))
        if not forging.forgeable(self.conn, self.owner_id):
            e.add_field(name="Nothing to forge yet", value="Find weapons, armor or artifacts in **/explore** and "
                        "chests first.", inline=False)
        if self.notice:
            e.add_field(name="​", value=self.notice, inline=False)
        e.set_footer(text=self.rank_line())
        return e

    def plan_embed(self):
        it = self.item()
        gear = passives.gear_kind(it)
        tier = it["grade"]
        lines = [f"**{tier.title()} {gear}** · up to {forge.PASSIVE_SLOTS[tier]['max_rarity']} passives", ""]
        lines += slot_lines(it)
        pl = self.current_plan()
        if pl:
            g = forging.Forge(tier, forging.rank_of(self.player["blacksmith_exp"]), random.Random(0), pl.fuel,
                              pl.liquid, forging.swift_seconds(self.player), forging.steady_degrees(self.player))
            lines += ["", f"{ACTION_EMOJI[pl.action]} **{forging.ACTION_LABEL[pl.action]}:** {ACTION_HELP[pl.action]}",
                      f"**Difficulty:** {g.diff['name']} · {g.seconds:g}s per decision · needs "
                      f"{forging.rank_label(forge.RANK_NEEDED[tier])} Blacksmith"]
            uses = ", ".join(f"{materials.MATERIALS[k]['name']} ×{q}" for k, q in pl.uses)
            cost = uses + (f", 🪷 {pl.coins:,} Lotus Coins" if pl.coins else "")
            if pl.missing:
                lines.append(f"❌ **Missing:** {', '.join(pl.missing)}")
                lines.append(f"**Cost:** {cost}")
            else:
                lines.append(f"✅ **Will use:** {cost}")
            cap = forge.rarity_cap(tier, materials.MATERIALS[pl.essence]["grade"] if pl.essence else None)
            lines.append(f"**Best possible:** {forge.RARITY_EMOJI[cap]} {cap}"
                         + (f" ({materials.MATERIALS[pl.essence]['name']} picks the family)" if pl.essence else ""))
            helps = []
            if g.bonuses["rank"]:
                helps.append(f"{g.bonuses['rank']} rank(s) above: wider zones, more time")
            if g.bonuses["fuel"]:
                helps.append(f"fuel +{g.bonuses['fuel']}° Ignite zone")
            if g.bonuses["liquid"]:
                helps.append(f"liquid +{g.bonuses['liquid']}° quench window")
            if g.bonuses["swift"]:
                helps.append(f"Swift Hands +{g.bonuses['swift']:g}s")
            if g.bonuses["steady"]:
                helps.append(f"Steady Hand +{g.bonuses['steady']}°")
            if helps:
                lines.append("🍀 " + " · ".join(helps))
            lines.append("\n**Stages:** " + " → ".join(forge.STAGE_NAMES[s] for s in forge.STAGES))
        else:
            lines += ["", "Choose what to do below."]
        e = discord.Embed(title=f"{GEAR_EMOJI[gear]} {it['name']}", description="\n".join(lines)[:4000], color=COLOR)
        if self.notice:
            e.add_field(name="​", value=self.notice, inline=False)
        e.set_footer(text=self.rank_line())
        return e

    def stage_embed(self):
        g = self.game
        pr = g.prompt()
        lines = (g.log + [""] if g.log else []) + pr.lines
        e = discord.Embed(title=f"{self.plan.item['name']} · {pr.title}", description="\n".join(lines), color=COLOR)
        e.set_footer(text=f"Stage {g.stage_i + 1} of {len(forge.STAGES)} · ⏳ {pr.seconds:g}s per decision")
        return e

    # ── buttons and menus ────────────────────────────────────────────

    def build(self):
        self.clear_items()
        if self.game and not self.game.done:
            for key, label, emoji in self.game.prompt().options:
                self.button(label, self.make_act(key), emoji=button_emoji(self.bot, key, emoji),
                            style=BUTTON_STYLE.get(key, discord.ButtonStyle.primary))
            return
        if self.result_lines:
            self.button("Forge Again", self.on_again, emoji=button_emoji(self.bot, "again", "⚒️"),
                        style=discord.ButtonStyle.success)
            self.button("Close", self.on_close, emoji="🏮")
            return
        if self.item_id:
            self.build_plan()
            return
        items = forging.forgeable(self.conn, self.owner_id)
        if not items:
            self.button("Close", self.on_close, emoji="🏮")
            return
        options = []
        for it in items[:25]:
            gear = passives.gear_kind(it)
            filled = [k for k in passives.slots(it) if k]
            desc = (("Worn · " if it["equipped"] else "") + f"{it['grade'].title()} {gear} · "
                    + (", ".join(forge.PASSIVES[gear][k]["name"] for k in filled) if filled else "empty slot"))
            options.append(discord.SelectOption(label=it["name"][:100], value=str(it["id"]), emoji=GEAR_EMOJI[gear],
                                                description=desc[:100]))
        sel = discord.ui.Select(placeholder="Choose gear to forge", options=options)
        sel.callback = self.on_pick
        self.picker = sel
        self.add_item(sel)

    def _select(self, placeholder, choices, current, callback, row):
        """A menu of (value, label, description, emoji) with a 'none' choice first."""
        options = [discord.SelectOption(label="None", value=NONE, default=current is None)]
        for value, label, desc, emoji in choices[:24]:
            options.append(discord.SelectOption(label=label[:100], value=value, description=(desc or None) and desc[:100],
                                                emoji=emoji, default=value == current))
        sel = discord.ui.Select(placeholder=placeholder, options=options, row=row)
        sel.callback = lambda interaction, s=sel: callback(interaction, s.values[0])
        self.add_item(sel)

    def build_plan(self):
        it = self.item()
        acts = forging.actions_for(it)
        if self.action not in acts:
            self.action = acts[0] if acts else None
        conn, uid = self.conn, self.owner_id
        ess = [(k, materials.MATERIALS[k]["name"], "" if ok else why, materials.KIND_EMOJI["essence"])
               for k, ok, why in forging.essence_options(conn, uid, it)]
        if ess:
            self._select("Essence: choose the passive family (optional)", ess, self.essence, self.on_essence, 0)
        fuels = [(k, materials.MATERIALS[k]["name"], f"+{forge.FUEL_ZONE_BONUS[materials.MATERIALS[k]['tier'] - 1]}° "
                  "Ignite zone", materials.KIND_EMOJI["fuel"]) for k in forging.extra_options(conn, uid, "fuel")]
        if fuels:
            self._select("Fuel: a wider Ignite zone (optional)", fuels, self.fuel, self.on_fuel, 1)
        liquids = [(k, materials.MATERIALS[k]["name"],
                    f"+{forge.LIQUID_WINDOW_BONUS[materials.MATERIALS[k]['tier'] - 1]}° quench window",
                    materials.KIND_EMOJI["liquid"]) for k in forging.extra_options(conn, uid, "liquid")]
        if liquids:
            self._select("Quench liquid: a wider quench window (optional)", liquids, self.liquid, self.on_liquid, 2)
        if self.action == "replace":
            gear = passives.gear_kind(it)
            opts = [discord.SelectOption(label=f"Keep slot {i + 1}: {forge.PASSIVES[gear][k]['name']}"[:100],
                                         value=str(i), default=self.lock == i)
                    for i, k in enumerate(passives.slots(it))]
            sel = discord.ui.Select(placeholder="Choose the slot to lock with the Seal Stone", options=opts, row=3)
            sel.callback = lambda interaction, s=sel: self.on_lock(interaction, int(s.values[0]))
            self.add_item(sel)
        for a in acts:
            self.button(forging.ACTION_LABEL[a], self.make_action(a), emoji=ACTION_EMOJI[a], row=4,
                        style=discord.ButtonStyle.primary if a == self.action else discord.ButtonStyle.secondary)
        pl = self.current_plan()
        self.button("Begin", self.on_begin, emoji=button_emoji(self.bot, "again", "🔥"), row=4,
                    style=discord.ButtonStyle.success, disabled=not pl or bool(pl.missing))
        self.button("Back", self.on_back, emoji="◀️", row=4)

    async def redraw(self, interaction):
        """The picker and plan screens: text only, so the last card is taken off."""
        self.build()
        await interaction.response.edit_message(embed=self.embed(), view=self, attachments=[])
        self.notice = None

    async def on_pick(self, interaction):
        self.item_id = int(self.picker.values[0])
        self.action = self.essence = self.fuel = self.liquid = self.lock = None
        await self.redraw(interaction)

    def make_action(self, action):
        async def cb(interaction):
            self.action = action
            self.lock = (self.lock or 0) if action == "replace" else None
            await self.redraw(interaction)
        return cb

    async def on_essence(self, interaction, value):
        self.essence = None if value == NONE else value
        await self.redraw(interaction)

    async def on_fuel(self, interaction, value):
        self.fuel = None if value == NONE else value
        await self.redraw(interaction)

    async def on_liquid(self, interaction, value):
        self.liquid = None if value == NONE else value
        await self.redraw(interaction)

    async def on_lock(self, interaction, slot):
        self.lock = slot
        await self.redraw(interaction)

    async def on_back(self, interaction):
        self.item_id = None
        await self.redraw(interaction)

    async def on_begin(self, interaction):
        async with self.bot.db_lock:
            pl = self.current_plan()
            ok = pl is not None and not pl.missing and forging.take_materials(self.conn, self.owner_id, pl)
        if not ok:
            self.notice = "Your materials or coins changed in the meantime. Check the cost again."
            await self.redraw(interaction)
            return
        self.plan = pl
        self.game = forging.new_game(self.conn, self.owner_id, pl, self.rng)
        self.outcome, self.result_lines = None, None
        await self.show_step(interaction)

    # ── playing ──────────────────────────────────────────────────────

    def make_act(self, key):
        async def cb(interaction):
            await self.resolve(key, time.monotonic() - (self.shown_at or time.monotonic()), interaction)
        return cb

    async def resolve(self, key, elapsed, interaction=None):
        g = self.game
        if not g or g.done:
            return
        if self.timer and interaction is not None:
            self.timer.cancel()
        if elapsed > g.seconds + forge.TIMER_GRACE_SECONDS:
            key = None
        g.act(key)
        if g.done:
            await self.finish_and_store()
        if interaction is not None or self.message:
            await self.show_step(interaction)
        if g.done and self.news and self.message:
            try:
                await self.message.channel.send(self.news)
            except Exception:
                log.warning("Could not announce a Mythical forge", exc_info=True)
            self.news = None

    async def finish_and_store(self):
        async with self.bot.db_lock:
            self.outcome = forging.finish_forge(self.conn, self.owner_id, self.plan, self.game, self.rng)
        self.result_lines = (self.game.log + [""] if self.game.log else []) + self.outcome["lines"]
        self.news = self.outcome["news"]

    async def card_file(self):
        """The Forge Hall card as a JPEG (rendered on the card thread), or None if it can't be drawn."""
        try:
            data = forge_card.card_data(self.plan, self.game, self.outcome)
            img = await card_render.render(render_forge, data)
        except Exception:
            log.exception("Could not render the forge card")
            return None
        return jpg(img, "forge.jpg")

    async def show_step(self, interaction, view=True):
        self.build()
        if interaction is not None and not interaction.response.is_done():
            await interaction.response.defer()
        file = await self.card_file()
        kw = {"embed": self.embed(), "view": self if view else None, "attachments": [file] if file else []}
        await self.edit(interaction, **kw)
        if view and self.game and not self.game.done:
            self.start_timer()

    async def edit(self, interaction, **kw):
        try:
            if interaction is not None:
                await interaction.edit_original_response(**kw)
                return
        except discord.HTTPException:
            log.warning("Editing the forge through the interaction failed; editing the message instead", exc_info=True)
        if self.message is not None:
            try:
                await self.message.edit(**kw)
            except discord.HTTPException:
                ch = getattr(self.message, "channel", None)
                if ch is None:
                    raise
                await ch.get_partial_message(self.message.id).edit(**kw)

    def start_timer(self):
        self.shown_at = time.monotonic()
        g = self.game
        marker = g.decisions

        async def expire():
            await asyncio.sleep(g.seconds + forge.TIMER_GRACE_SECONDS)
            if g is self.game and not g.done and g.decisions == marker and not self._handling:
                self._handling = True
                try:
                    await self.resolve(None, g.seconds + forge.TIMER_GRACE_SECONDS)
                except Exception:
                    log.exception("Forge timeout failed")
                finally:
                    self._handling = False
        self.timer = asyncio.create_task(expire())

    async def on_again(self, interaction):
        self.game, self.plan, self.outcome, self.result_lines = None, None, None, None
        if self.item_id and not self.item():
            self.item_id = None
        await self.redraw(interaction)

    async def on_close(self, interaction):
        self.clear_items()
        await interaction.response.edit_message(embed=self.embed(), view=None)
        self.finish()

    def finish(self):
        self.stop()
        self.bot.busy.discard((self.owner_id, "forge"))

    async def on_timeout(self):
        try:
            g = self.game
            if g and not g.done:
                for _ in range(300):                 # walking away: every remaining decision times out
                    if g.done:
                        break
                    g.act(None)
                await self.finish_and_store()
                self.news = None
            if self.message:
                if g:
                    self.clear_items()
                    await self.show_step(None, view=False)
                else:
                    await self.message.edit(embed=self.embed(), view=None)
        except Exception:
            log.exception("Forge timeout handling failed")
        finally:
            self.bot.busy.discard((self.owner_id, "forge"))


def register(bot):
    @bot.tree.command(name="forge", description="Blacksmith: forge passives onto your weapons, armor and artifacts")
    async def forge_cmd(interaction: discord.Interaction):
        uid = interaction.user.id
        if not db.get_player(bot.conn, uid):
            await interaction.response.send_message(
                "You have not begun your journey yet. Use **/start** to step through the gates of the Jianghu.",
                ephemeral=True)
            return
        if (uid, "forge") in bot.busy:
            await interaction.response.send_message("Your forge is already lit. Finish that forge first.",
                                                    ephemeral=True)
            return
        bot.busy.add((uid, "forge"))
        try:
            view = ForgeView(bot, uid)
            await interaction.response.send_message(embed=view.embed(), view=view)
            view.message = await interaction.original_response()
        except Exception:
            bot.busy.discard((uid, "forge"))
            raise
