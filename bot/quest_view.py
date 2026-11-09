"""
/daily: today's quests on a card, with a Claim button (bot/quests.py, docs/quests.md).
"""
import io

import discord

from . import db, loot, quests
from . import render as card_render
from .views import OwnedView

NOT_STARTED = "You have not begun your journey yet. Use **/start** to step through the gates of the Jianghu."


async def card(bot, uid):
    from cards.quests import render_quests
    async with bot.db_lock:
        data = quests.board(bot.conn, db.get_player(bot.conn, uid))
    img = await card_render.render(render_quests, data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename="daily.png"), data


def claim_text(out):
    if not out["coins"] and not out["pearls"] and not out["bag_full"]:
        return "Nothing to claim yet."
    lines = []
    if out["coins"] or out["pearls"]:
        lines.append(f"🎁 You claim **{out['coins']:,}** 🪷 Lotus Coins and **{out['pearls']:,}** 🌙 Moon Pearls.")
    if out["bonus"]:
        lines.append(f"🏆 Every quest done! A **{loot.CHEST_NAMES[out['chest']]}** {loot.CHEST_EMOJI[out['chest']]} "
                     "is in your bag." if out["chest"] else "🏆 Every quest done! No chest this time.")
    if out["bag_full"]:
        lines.append("⚠️ Your bag is full, so the all-quests reward waits. Free a slot and press Claim again.")
    return "\n".join(lines)


class DailyView(OwnedView):
    def __init__(self, bot, uid, data):
        super().__init__(uid, timeout=300)
        self.bot = bot
        self.build(data)

    def build(self, data):
        self.clear_items()
        n = data["claimable"]
        claim = discord.ui.Button(label=f"Claim rewards ({n})" if n else "Nothing to claim",
                                  style=discord.ButtonStyle.success if n else discord.ButtonStyle.secondary,
                                  emoji="🎁", disabled=not n)
        claim.callback = self.on_claim
        refresh = discord.ui.Button(label="Refresh", style=discord.ButtonStyle.secondary, emoji="🔄")
        refresh.callback = self.on_refresh
        self.add_item(claim)
        self.add_item(refresh)

    async def on_claim(self, interaction):
        await interaction.response.defer()
        async with self.bot.db_lock:
            out = quests.claim(self.bot.conn, self.owner_id)
        file, data = await card(self.bot, self.owner_id)
        self.build(data)
        await interaction.edit_original_response(content=claim_text(out), attachments=[file], view=self)

    async def on_refresh(self, interaction):
        await interaction.response.defer()
        file, data = await card(self.bot, self.owner_id)
        self.build(data)
        await interaction.edit_original_response(attachments=[file], view=self)


def register(bot):
    @bot.tree.command(name="daily", description="Today's daily quests: Lotus Coins, Moon Pearls and a chance of a chest")
    async def daily(interaction: discord.Interaction):
        uid = interaction.user.id
        if not db.get_player(bot.conn, uid):
            await interaction.response.send_message(NOT_STARTED, ephemeral=True)
            return
        await interaction.response.defer()
        file, data = await card(bot, uid)
        view = DailyView(bot, uid, data)
        view.message = await interaction.followup.send(file=file, view=view, wait=True)
