"""
/trade @player: swap items and currencies (docs/trading.md). Rules: bot/trading.py. Numbers: trade.py.

1. InviteView: the other player gets Accept / Decline for trade.INVITE_SECONDS.
2. TradeView: the public trade window (one card + buttons), edited after every change, in the channel so
   others can watch. Only the two traders can press.
     Add Item     → a private picker: Category → Grade → Item → Quantity → Add to Offer
     Add Currency → a private panel: Lotus Coins / Moon Pearls → type the amount
     Remove       → a private menu of your lines
     Review Trade → the private Trade Preview card → Confirm
     Cancel
   Any change clears both confirmations. When both have confirmed the swap runs at once.
"""
import asyncio
import logging
import time

import discord
from discord import app_commands

import trade as TR

from . import db, trading
from . import render as card_render
from .duel_view import in_fight
from .fight_view import jpg
from .trading import Trade, TradeError
from cards.trade import render_picker, render_preview, render_trade

log = logging.getLogger("mortal-ascent")
COLOR = discord.Color.from_rgb(240, 200, 110)
NOT_STARTED = "You have not begun your journey yet. Use **/start** to step through the gates of the Jianghu."
CAT_LABEL = {k: (label, em) for k, label, em in TR.CATEGORIES}


def why_cannot_trade(bot, me_user, them_user):
    if them_user.bot:
        return "Bots don't trade."
    if them_user.id == me_user.id:
        return "You can't trade with yourself."
    me, them = db.get_player(bot.conn, me_user.id), db.get_player(bot.conn, them_user.id)
    if not me:
        return NOT_STARTED
    if not them:
        return f"**{them_user.display_name}** has not begun their journey yet (/start)."
    for p, who in ((me, "You are"), (them, f"**{them['name']}** is")):
        if (p["user_id"], "trade") in bot.busy:
            return f"{who} already in a trade."
        if in_fight(bot, p["user_id"]):
            return f"{who} in a fight right now."
        why = trading.why_cannot_trade(p)
        if why:
            return (f"{who} not ready to trade: " if p is them else "") + why
    return None


async def ephemeral(interaction, text=None, embed=None, view=None, file=None):
    kw = {"ephemeral": True}
    if text:
        kw["content"] = text
    if embed:
        kw["embed"] = embed
    if view:
        kw["view"] = view
    if file:
        kw["file"] = file
    if interaction.response.is_done():
        return await interaction.followup.send(**kw)
    await interaction.response.send_message(**kw)


# ── the invite ────────────────────────────────────────────────────────

class InviteView(discord.ui.View):
    def __init__(self, bot, me, them):
        super().__init__(timeout=TR.INVITE_SECONDS)
        self.bot, self.me, self.them = bot, me, them
        self.message = None
        self.done = False
        self.deadline = time.time() + TR.INVITE_SECONDS

    def embed(self, text=None):
        return discord.Embed(
            title="🤝 A trade request", color=COLOR,
            description=text or (f"{self.me.mention} wants to trade with {self.them.mention}.\n\n"
                                 f"{self.them.mention}, accept <t:{int(self.deadline)}:R>?"))

    def _release(self):
        self.bot.busy.discard((self.me.id, "trade"))

    async def _close(self, interaction, text):
        self.done = True
        self.stop()
        self._release()
        if interaction is not None:
            await interaction.response.edit_message(content=None, embed=self.embed(text), view=None)
        elif self.message is not None:
            try:
                await self.message.edit(content=None, embed=self.embed(text), view=None)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        if not self.done:
            await self._close(None, f"⌛ **{self.them.display_name}** didn't answer. The request expired.")

    @discord.ui.button(label="Accept", emoji="🤝", style=discord.ButtonStyle.success)
    async def accept(self, interaction, button):
        if interaction.user.id != self.them.id:
            await ephemeral(interaction, "Only the invited player can accept." if interaction.user.id != self.me.id
                            else "Wait for them to accept.")
            return
        if self.done:
            await ephemeral(interaction, "This request is over.")
            return
        self.bot.busy.discard((self.me.id, "trade"))
        why = why_cannot_trade(self.bot, self.me, self.them)
        if why:
            await self._close(interaction, f"The trade can't start: {why}")
            return
        self.done = True
        self.stop()
        self.bot.busy.add((self.me.id, "trade"))
        self.bot.busy.add((self.them.id, "trade"))
        await interaction.response.defer()
        try:
            from .sheet.view import fetch_avatar
            avatars = await asyncio.gather(fetch_avatar(self.me), fetch_avatar(self.them))
            view = TradeView(self.bot, self.me, self.them, dict(zip((self.me.id, self.them.id), avatars)))
            view.message = self.message
            await view.refresh(first=True)
        except Exception:
            self.bot.busy.discard((self.me.id, "trade"))
            self.bot.busy.discard((self.them.id, "trade"))
            raise

    @discord.ui.button(label="Decline", emoji="🙇", style=discord.ButtonStyle.secondary)
    async def decline(self, interaction, button):
        uid = interaction.user.id
        if self.done:
            await ephemeral(interaction, "This request is over.")
        elif uid == self.them.id:
            await self._close(interaction, f"🙇 **{self.them.display_name}** declined the trade.")
        elif uid == self.me.id:
            await self._close(interaction, f"**{self.me.display_name}** withdrew the request.")
        else:
            await ephemeral(interaction, "This request isn't for you.")


# ── the trade window ──────────────────────────────────────────────────

class TradeView(discord.ui.View):
    def __init__(self, bot, me, them, avatars):
        super().__init__(timeout=TR.SESSION_SECONDS)
        self.bot, self.users = bot, {me.id: me, them.id: them}
        self.trade = Trade(me.id, them.id)
        self.avatars = avatars
        self.message = None
        self.note = None
        self.lock = asyncio.Lock()

    def names(self):
        return {uid: u.display_name for uid, u in self.users.items()}

    def data(self, viewer=None):
        d = trading.card_data(self.bot.conn, self.trade, self.names(), note=self.note)
        d["avatars"] = self.avatars
        if viewer is not None:
            d["viewer"] = viewer
        return d

    async def refresh(self, first=False):
        """Redraw the public card (and drop the buttons once the trade is over)."""
        img = await card_render.render(render_trade, self.data())
        over = self.trade.status != "open"
        if over:
            self.stop()
            for uid in self.users:
                self.bot.busy.discard((uid, "trade"))
        kw = dict(content=None, embed=None, attachments=[jpg(img, "trade.jpg")], view=None if over else self)
        try:
            await self.message.edit(**kw)
        except discord.HTTPException:
            log.exception("Could not update the trade window")

    async def changed(self, note=None):
        self.note = note
        await self.refresh()

    async def on_timeout(self):
        if self.trade.status == "open":
            self.trade.cancel()
            self.note = "The trade window closed after a long wait. Nothing changed hands."
            await self.refresh()

    async def interaction_check(self, interaction):
        if interaction.user.id not in self.users:
            await ephemeral(interaction, "This trade isn't yours. Start your own with **/trade @player**.")
            return False
        if self.trade.status != "open":
            await ephemeral(interaction, "This trade is over.")
            return False
        return True

    async def on_error(self, interaction, error, item):
        log.exception("Trade window failed", exc_info=error)
        try:
            await ephemeral(interaction, "⚠️ Something went wrong on our side. Please try again.")
        except discord.HTTPException:
            pass

    @discord.ui.button(label="Add Item", emoji="🎒", style=discord.ButtonStyle.primary, row=0)
    async def add_item(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        picker = ItemPicker(self, interaction.user.id)
        await interaction.followup.send(file=await picker.picture(), view=picker, ephemeral=True)

    @discord.ui.button(label="Add Currency", emoji="🪷", style=discord.ButtonStyle.primary, row=0)
    async def add_currency(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        panel = CurrencyPanel(self, interaction.user.id)
        await interaction.followup.send(file=await panel.picture(), view=panel, ephemeral=True)

    @discord.ui.button(label="Remove", emoji="➖", style=discord.ButtonStyle.secondary, row=0)
    async def remove(self, interaction, button):
        panel = RemovePanel(self, interaction.user.id)
        if not panel.has_lines:
            await ephemeral(interaction, "Your offer is empty.")
            return
        await ephemeral(interaction, "Choose what to take back out of your offer.", view=panel)

    @discord.ui.button(label="Review Trade", emoji="🔍", style=discord.ButtonStyle.success, row=0)
    async def review(self, interaction, button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        img = await card_render.render(render_preview, self.data(viewer=interaction.user.id))
        await interaction.followup.send(content="**Trade Preview**: check every line, then confirm.",
                                        file=jpg(img, "preview.jpg"), view=ConfirmPanel(self, interaction.user.id),
                                        ephemeral=True)

    @discord.ui.button(label="Cancel", emoji="✖️", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction, button):
        await interaction.response.defer()
        async with self.lock:
            self.trade.cancel(interaction.user.id)
            await self.changed()

    # changes from the private panels ──────────────────────────────────

    async def apply(self, interaction, fn, *args):
        """Run one change on the trade. Returns None when done, else the reason shown to the player."""
        async with self.lock:
            if self.trade.status != "open":
                return "This trade is over."
            try:
                async with self.bot.db_lock:
                    fn(self.bot.conn, interaction.user.id, *args)
            except TradeError as e:
                return str(e)
            await self.changed()
        return None

    async def confirm(self, interaction):
        async with self.lock:
            if self.trade.status != "open":
                return "This trade is over."
            try:
                both = self.trade.confirm(interaction.user.id)
            except TradeError as e:
                return str(e)
            note = None
            if both:
                async with self.bot.db_lock:
                    why = self.trade.execute(self.bot.conn)
                if why:
                    note = f"The trade didn't go through: {why} Both confirmations were cleared."
            await self.changed(note)
            return note


# ── Add Item: Category → Grade → Item → Quantity ─────────────────────

class _Panel(discord.ui.View):
    """A private panel for one trader."""

    def __init__(self, window, uid):
        super().__init__(timeout=TR.SESSION_SECONDS)
        self.window, self.uid = window, uid

    @property
    def conn(self):
        return self.window.bot.conn

    async def interaction_check(self, interaction):
        if self.window.trade.status != "open":
            await interaction.response.edit_message(content="This trade is over.", embed=None, view=None)
            return False
        return True


class ItemPicker(_Panel):
    def __init__(self, window, uid):
        super().__init__(window, uid)
        self.category = self.grade = None
        self.item = None
        self.qty = 0
        self.message_note = None
        self.build()

    def offered(self, item_id):
        return self.window.trade.offers[self.uid].qty_of(item_id)

    def embed(self):
        e = discord.Embed(color=COLOR)
        if self.item:
            it = self.item
            e.title = f"{trading.item_label(it)}"
            e.description = (f"**{trading.grade_label(it)}** · {CAT_LABEL[trading.trade_category(it)][0]}\n\n"
                             f"Owned: **{it['qty']:,}**\nOffering: **{self.qty:,}**")
        elif self.category:
            label, em = CAT_LABEL[self.category]
            e.title = f"{em} {label}" + (f" · {self.grade}" if self.grade else "")
            e.description = "Choose a grade." if not self.grade else "Choose an item."
        else:
            e.title = "🎒 Add an item"
            e.description = "Choose a category."
        if self.message_note:
            e.set_footer(text=self.message_note)
        return e

    def build(self):
        self.clear_items()
        conn, uid = self.conn, self.uid
        if self.item:
            it = self.item
            for label, step in (("−10", -10), ("−1", -1), ("+1", 1), ("+10", 10)):
                b = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, row=0,
                                      disabled=(step < 0 and self.qty <= 0) or (step > 0 and self.qty >= it["qty"]))
                b.callback = self._step(step)
                self.add_item(b)
            b = discord.ui.Button(label="Max", style=discord.ButtonStyle.secondary, row=0, disabled=self.qty >= it["qty"])
            b.callback = self._step(None)
            self.add_item(b)
            b = discord.ui.Button(label="Type amount", emoji="⌨️", style=discord.ButtonStyle.secondary, row=1)
            b.callback = self._type
            self.add_item(b)
            b = discord.ui.Button(label="Add to Offer" if not self.offered(it["id"]) else "Update Offer", emoji="✅",
                                  style=discord.ButtonStyle.success, row=1)
            b.callback = self._add
            self.add_item(b)
            self._back(row=1)
            return
        if not self.category:
            counts = trading.category_counts(conn, uid)
            opts = [discord.SelectOption(label=label, value=k, emoji=em, description=f"{counts[k]} tradeable")
                    for k, label, em in TR.CATEGORIES if counts[k]]
            if not opts:
                opts = [discord.SelectOption(label="Nothing tradeable in your bag", value="none")]
            s = discord.ui.Select(placeholder="Category", options=opts, row=0)
            s.callback = self._pick_category
            self.add_item(s)
            return
        if not self.grade:
            grades = trading.grades_in(conn, uid, self.category)
            s = discord.ui.Select(placeholder="Grade", row=0, options=[
                discord.SelectOption(label=g, value=g, description=f"{n} item{'s' if n != 1 else ''}") for g, n in grades[:25]]
                or [discord.SelectOption(label="Nothing here", value="none")])
            s.callback = self._pick_grade
            self.add_item(s)
            self._back(row=1)
            return
        items = trading.tradeable_items(conn, uid, self.category, self.grade)
        opts = []
        for it in items[:25]:
            off = self.offered(it["id"])
            desc = f"Owned: {it['qty']:,}" + (f" · Offering: {off:,}" if off else "")
            opts.append(discord.SelectOption(label=trading.item_label(it)[:100], value=str(it["id"]), description=desc))
        s = discord.ui.Select(placeholder="Item" + (f" (first 25 of {len(items)})" if len(items) > 25 else ""), row=0,
                              options=opts or [discord.SelectOption(label="Nothing here", value="none")])
        s.callback = self._pick_item
        self.add_item(s)
        self._back(row=1)

    def _back(self, row):
        b = discord.ui.Button(label="Back", emoji="↩️", style=discord.ButtonStyle.secondary, row=row)
        b.callback = self._go_back
        self.add_item(b)

    def picture_data(self):
        conn, offer = self.conn, self.window.trade.offers[self.uid]
        if self.item:
            row = trading.picker_row(self.item, self.offered(self.item["id"]))
            return {"mode": "quantity", "item": row, "qty": self.qty, "note": self.message_note,
                    "category": CAT_LABEL[trading.trade_category(self.item)][0]}
        if self.category:
            d = trading.picker_items(conn, self.uid, self.category, self.grade, offer)
            return dict(d, mode="items", category=CAT_LABEL[self.category][0], grade=self.grade,
                        note=self.message_note)
        return {"mode": "categories", "categories": trading.picker_categories(conn, self.uid), "note": self.message_note}

    async def picture(self):
        img = await card_render.render(render_picker, self.picture_data())
        return jpg(img, "pick.jpg")

    async def _show(self, interaction):
        self.build()
        await interaction.response.defer()
        await interaction.edit_original_response(content=None, embed=None, attachments=[await self.picture()],
                                                 view=self)

    async def _go_back(self, interaction):
        self.message_note = None
        if self.item:
            self.item = None
        elif self.grade:
            self.grade = None
        else:
            self.category = None
        await self._show(interaction)

    async def _pick_category(self, interaction):
        v = interaction.data["values"][0]
        if v != "none":
            self.category = v
            grades = trading.grades_in(self.conn, self.uid, v)
            if len(grades) == 1:
                self.grade = grades[0][0]
        await self._show(interaction)

    async def _pick_grade(self, interaction):
        v = interaction.data["values"][0]
        if v != "none":
            self.grade = v
        await self._show(interaction)

    async def _pick_item(self, interaction):
        v = interaction.data["values"][0]
        if v != "none":
            self.item = db.get_item(self.conn, self.uid, int(v))
            self.qty = self.offered(int(v)) or (1 if self.item and self.item["qty"] else 0)
        await self._show(interaction)

    def _step(self, step):
        async def cb(interaction):
            have = self.item["qty"]
            self.qty = have if step is None else max(0, min(have, self.qty + step))
            await self._show(interaction)
        return cb

    async def _type(self, interaction):
        await interaction.response.send_modal(AmountModal(self.item["qty"], self.qty, self._typed,
                                                          title=trading.item_label(self.item)[:45]))

    async def _typed(self, interaction, value):
        self.qty = max(0, min(self.item["qty"], value))
        await self._show(interaction)

    async def _add(self, interaction):
        it = self.item
        why = await self.window.apply(interaction, self.window.trade.set_item, it["id"], self.qty)
        if why:
            self.message_note = f"⚠ {why}"
        else:
            self.message_note = (f"Added: {self.qty:,} × {trading.item_label(it)}" if self.qty
                                 else f"Removed {trading.item_label(it)}")
            self.item = None
        await self._show(interaction)


class AmountModal(discord.ui.Modal):
    def __init__(self, maximum, current, done, title="Amount", label=None):
        super().__init__(title=title)
        self.maximum, self.done = maximum, done
        self.amount = discord.ui.TextInput(label=label or f"Amount (0 – {maximum:,})", default=str(current),
                                           max_length=12)
        self.add_item(self.amount)

    async def on_submit(self, interaction):
        raw = self.amount.value.replace(",", "").replace(" ", "").lower()
        mult = 1
        if raw.endswith("k"):
            raw, mult = raw[:-1], 1000
        try:
            value = int(float(raw) * mult)
        except ValueError:
            await ephemeral(interaction, f"`{self.amount.value}` isn't a number.")
            return
        await self.done(interaction, value)


# ── Add Currency ──────────────────────────────────────────────────────

class CurrencyPanel(_Panel):
    def __init__(self, window, uid):
        super().__init__(window, uid)
        self.note = None
        for cur, label, em in TR.CURRENCIES:
            b = discord.ui.Button(label=label, emoji=em, style=discord.ButtonStyle.primary)
            b.callback = self._open(cur, label)
            self.add_item(b)

    def embed(self):
        p = db.get_player(self.conn, self.uid)
        o = self.window.trade.offers[self.uid]
        e = discord.Embed(title="Add currency", color=COLOR)
        for cur, label, em in TR.CURRENCIES:
            e.add_field(name=f"{em} {label}", value=f"Balance: **{p[cur]:,}**\nOffering: **{getattr(o, cur):,}**")
        if self.note:
            e.set_footer(text=self.note)
        return e

    async def picture(self):
        p = db.get_player(self.conn, self.uid)
        o = self.window.trade.offers[self.uid]
        data = {"mode": "currency", "note": self.note,
                "currencies": [{"key": cur, "label": label, "balance": p[cur], "offering": getattr(o, cur)}
                               for cur, label, _ in TR.CURRENCIES]}
        return jpg(await card_render.render(render_picker, data), "currency.jpg")

    def _open(self, cur, label):
        async def cb(interaction):
            have = db.get_player(self.conn, self.uid)[cur]
            current = getattr(self.window.trade.offers[self.uid], cur)

            async def done(inter, value):
                why = await self.window.apply(inter, self.window.trade.set_currency, cur, value)
                self.note = f"⚠ {why}" if why else f"Offering {max(0, value):,} {label}"
                await inter.response.defer()
                await inter.edit_original_response(content=None, embed=None, attachments=[await self.picture()],
                                                   view=self)

            await interaction.response.send_modal(AmountModal(have, current, done, title=label,
                                                              label=f"{label} to offer (you have {have:,})"))
        return cb


# ── Remove ────────────────────────────────────────────────────────────

class RemovePanel(_Panel):
    def __init__(self, window, uid):
        super().__init__(window, uid)
        o = window.trade.offers[uid]
        opts = []
        for ln in o.lines:
            it = db.get_item(window.bot.conn, uid, ln["item_id"])
            if it:
                opts.append(discord.SelectOption(label=f"{trading.item_label(it)}"[:90], value=f"item:{it['id']}",
                                                 description=f"Offering {ln['qty']:,}"))
        for cur, label, em in TR.CURRENCIES:
            if getattr(o, cur):
                opts.append(discord.SelectOption(label=label, value=f"cur:{cur}", emoji=em,
                                                 description=f"Offering {getattr(o, cur):,}"))
        self.has_lines = bool(opts)
        if opts:
            s = discord.ui.Select(placeholder="Take back…", options=opts[:25], min_values=1,
                                  max_values=min(len(opts), 25))
            s.callback = self._remove
            self.add_item(s)

    async def _remove(self, interaction):
        await interaction.response.defer()
        for v in interaction.data["values"]:
            kind, key = v.split(":", 1)
            if kind == "item":
                await self.window.apply(interaction, self.window.trade.set_item, int(key), 0)
            else:
                await self.window.apply(interaction, self.window.trade.set_currency, key, 0)
        await interaction.edit_original_response(content="✅ Removed from your offer.", view=None)


# ── Review → Confirm ──────────────────────────────────────────────────

class ConfirmPanel(_Panel):
    @discord.ui.button(label="Confirm Trade", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        await interaction.response.defer()
        why = await self.window.confirm(interaction)
        if self.window.trade.status == "complete":
            text = "🤝 **Trade complete!** Everything is in your bag."
        elif why:
            text = f"⚠️ {why}"
        else:
            text = "✅ You confirmed. Waiting for the other player."
        await interaction.edit_original_response(content=text, attachments=[], view=None)

    @discord.ui.button(label="Back", emoji="↩️", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        await interaction.response.edit_message(content="Keep adding to your offer in the trade window.",
                                                attachments=[], view=None)


# ── the command ───────────────────────────────────────────────────────

def register(bot):
    @bot.tree.command(name="trade", description="Trade items, Lotus Coins and Moon Pearls with another player")
    @app_commands.describe(player="The player you want to trade with")
    async def trade_cmd(interaction: discord.Interaction, player: discord.User):
        if interaction.guild is None:
            await interaction.response.send_message("Trades happen in a server channel. Use **/trade** there.",
                                                    ephemeral=True)
            return
        why = why_cannot_trade(bot, interaction.user, player)
        if why:
            await interaction.response.send_message(why, ephemeral=True)
            return
        bot.busy.add((interaction.user.id, "trade"))
        try:
            view = InviteView(bot, interaction.user, player)
            await interaction.response.send_message(content=player.mention, embed=view.embed(), view=view,
                                                    allowed_mentions=discord.AllowedMentions(users=[player]))
            view.message = await interaction.original_response()
        except Exception:
            bot.busy.discard((interaction.user.id, "trade"))
            raise
