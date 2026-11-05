"""
The Character Sheet: one message with five tabs (Profile, Techniques, Equipment,
Inventory, Purse) that the owner switches with buttons instead of new commands.

/profile, /techniques, /equipment, /inventory and /balance each open it on
their own tab. Only the owner can press anything (OwnedView), and every
action re-reads the database under the bot's lock before it changes anything,
so a stale card or a double click can't use, equip or discard twice.
"""
import asyncio
import logging

import discord

from cards import RENDERERS

from .. import db, loot
from .. import player as rules
from .. import render as card_render
from ..views import OwnedView, png
from . import data as sheet
from . import items

log = logging.getLogger("mortal-ascent")

TABS = [("profile", "Profile", "👤"), ("techniques", "Techniques", "📜"), ("equipment", "Equipment", "⚔️"),
        ("inventory", "Inventory", "🎒"), ("purse", "Purse", "🪷")]
FIGHT_SESSIONS = ("explore", "spar")    # technique.md: techniques are swapped outside of fights
AVATAR_TIMEOUT_SECONDS = 5


async def fetch_avatar(user):
    try:
        return await asyncio.wait_for(user.display_avatar.with_format("png").with_size(512).read(),
                                      AVATAR_TIMEOUT_SECONDS)
    except Exception:
        log.warning("Could not download avatar for %s; using initial instead", user, exc_info=True)
        return None


def first_category(conn, user_id):
    counts = db.category_counts(conn, user_id)
    return next((k for k in items.ORDER if counts.get(k)), items.ORDER[0])


class CharacterSheet(OwnedView):
    def __init__(self, bot, user, tab="profile", category=None):
        super().__init__(user.id, timeout=600)
        self.bot, self.user, self.tab = bot, user, tab
        self.avatar = None
        self.notice = None
        self.category = category or first_category(bot.conn, user.id)
        self.page = 1
        self.selected = None
        self.confirm_discard = False
        self.tech_page = 1

    # ── drawing ──────────────────────────────────────────────────────

    def card_data(self):
        conn, uid = self.bot.conn, self.owner_id
        if self.tab == "profile":
            d = sheet.profile_data(conn, uid, username=self.user.name)
            d["avatar_bytes"] = self.avatar
            return d
        if self.tab == "techniques":
            d = sheet.techniques_data(conn, uid, self.tech_page)
            self.tech_page = d["page"]
            return d
        if self.tab == "equipment":
            return sheet.equipment_data(conn, uid)
        if self.tab == "inventory":
            d, self.page_items, self.pages, sel = sheet.bag_data(conn, uid, self.category, self.page, self.selected)
            self.page = d["page"]
            self.selected = sel["id"] if sel else None
            self.selected_item = sel
            return d
        return sheet.purse_data(conn, uid)

    async def render(self):
        """Rebuild the buttons for the current tab and draw its card. Returns a discord.File."""
        if self.tab == "profile" and self.avatar is None:
            self.avatar = await fetch_avatar(self.user) or b""
        data = self.card_data()
        self.build()
        image = await card_render.render(RENDERERS[self.tab], data)
        return png(image, f"{self.tab}.png")

    async def show(self, interaction):
        await interaction.response.defer()
        file = await self.render()
        await interaction.edit_original_response(content=self.notice, attachments=[file], view=self)
        self.notice = None

    # ── components ───────────────────────────────────────────────────

    def build(self):
        self.clear_items()
        for key, label, emoji in TABS:
            active = key == self.tab
            self.button(label, self.tab_callback(key), emoji=emoji, row=0, disabled=active,
                        style=discord.ButtonStyle.danger if active else discord.ButtonStyle.secondary)
        getattr(self, f"build_{self.tab}", lambda: None)()

    def tab_callback(self, key):
        async def cb(interaction):
            self.tab, self.confirm_discard = key, False
            await self.show(interaction)
        return cb

    def select(self, placeholder, options, callback, row):
        sel = discord.ui.Select(placeholder=placeholder, options=options[:25], row=row)
        sel.callback = callback
        self.add_item(sel)

    # Techniques
    def build_techniques(self):
        conn, uid = self.bot.conn, self.owner_id
        learned = db.get_techniques(conn, uid, equipped_only=False)
        spare = [t for t in learned if not t["equipped"]]
        if spare:
            self.select("Equip a technique...", [
                discord.SelectOption(label=t["name"], value=str(t["id"]),
                                     description=f"{t['grade']} {t['type']} · {rules.TECH_BY_NAME.get(t['name'], {}).get('school', '')}")
                for t in spare], self.on_equip_technique, 1)
        equipped = [t for t in learned if t["equipped"]]
        removable = [t for t in equipped if sum(x["type"] == t["type"] for x in equipped) > 1]
        if removable:
            self.select("Unequip from the flex slot...", [
                discord.SelectOption(label=t["name"], value=str(t["id"])) for t in removable],
                self.on_unequip_technique, 2)
        pages = max(1, -(-len(learned) // sheet.TECH_PER_PAGE))
        if pages > 1:
            self.button("Prev", self.on_tech_prev, emoji="◀️", row=3, disabled=self.tech_page <= 1)
            self.button("Next", self.on_tech_next, emoji="▶️", row=3, disabled=self.tech_page >= pages)

    def in_fight(self):
        return any((self.owner_id, k) in self.bot.busy for k in FIGHT_SESSIONS)

    async def on_equip_technique(self, interaction):
        tid = int(interaction.data["values"][0])
        if self.in_fight():
            self.notice = "⚔️ Techniques can only be swapped outside of fights. Finish your fight first."
            return await self.show(interaction)
        async with self.bot.db_lock:
            p = db.get_player(self.bot.conn, self.owner_id)
            tech = db.get_technique(self.bot.conn, self.owner_id, tid)
            if not tech or tech["equipped"]:
                self.notice = "That technique is already equipped."
            else:
                replaced = db.equip_technique(self.bot.conn, self.owner_id, tid, rules.technique_slots(p["realm"]))
                self.notice = f"📜 Equipped **{tech['name']}**" + (f" in place of {replaced}." if replaced else ".")
        await self.show(interaction)

    async def on_unequip_technique(self, interaction):
        tid = int(interaction.data["values"][0])
        if self.in_fight():
            self.notice = "⚔️ Techniques can only be swapped outside of fights. Finish your fight first."
            return await self.show(interaction)
        async with self.bot.db_lock:
            ok = db.unequip_technique(self.bot.conn, self.owner_id, tid)
        self.notice = "📜 Unequipped." if ok else "You must keep one technique of each type equipped."
        await self.show(interaction)

    async def on_tech_prev(self, interaction):
        self.tech_page -= 1
        await self.show(interaction)

    async def on_tech_next(self, interaction):
        self.tech_page += 1
        await self.show(interaction)

    # Equipment
    def build_equipment(self):
        weapons = db.get_items(self.bot.conn, self.owner_id, "weapons")
        spare = [w for w in weapons if not w["equipped"]]
        if spare:
            self.select("Equip a weapon...", [
                discord.SelectOption(label=w["name"][:100], value=str(w["id"]),
                                     description=f"{w['grade'].title()} · {rules.buff_text(rules.weapon_buffs(w))}"[:100])
                for w in spare], self.on_equip_weapon, 1)
        if any(w["equipped"] for w in weapons):
            self.button("Unequip weapon", self.on_unequip_weapon, emoji="🤜", row=2)

    async def on_equip_weapon(self, interaction):
        if self.in_fight():
            self.notice = "⚔️ You can't change weapons in the middle of a fight."
            return await self.show(interaction)
        async with self.bot.db_lock:
            self.notice = loot.use_item(self.bot.conn, self.owner_id, int(interaction.data["values"][0]))
        await self.show(interaction)

    async def on_unequip_weapon(self, interaction):
        if self.in_fight():
            self.notice = "⚔️ You can't change weapons in the middle of a fight."
            return await self.show(interaction)
        async with self.bot.db_lock:
            db.unequip_weapon(self.bot.conn, self.owner_id)
        self.notice = "🤜 You put your weapon away."
        await self.show(interaction)

    # Inventory
    def build_inventory(self):
        counts = db.category_counts(self.bot.conn, self.owner_id)
        self.select("Category", [
            discord.SelectOption(label=f"{c.label} ({counts.get(c.key, 0)})", value=c.key, default=c.key == self.category)
            for c in items.CATEGORIES.values()], self.on_category, 1)
        page_items = getattr(self, "page_items", [])
        if page_items:
            self.select("Inspect an item...", [
                discord.SelectOption(label=f"{i['name']}" + (f" ×{i['qty']}" if i["qty"] > 1 else ""), value=str(i["id"]),
                                     description=items.rarity(i)[0] + (" · equipped" if i["equipped"] else ""),
                                     default=i["id"] == self.selected)
                for i in page_items], self.on_pick, 2)
        sel = getattr(self, "selected_item", None)
        if self.confirm_discard and sel:
            self.button(f"Discard {sel['name'][:40]}" + (" ×1" if sel["qty"] > 1 else ""), self.discard_callback(1),
                        emoji="🗑️", style=discord.ButtonStyle.danger, row=3)
            if sel["qty"] > 1:
                self.button(f"Discard all ×{sel['qty']}", self.discard_callback(sel["qty"]), emoji="🗑️",
                            style=discord.ButtonStyle.danger, row=3)
            self.button("Cancel", self.on_cancel_discard, row=3)
            return
        if getattr(self, "pages", 1) > 1:
            self.button("Prev", self.on_prev, emoji="◀️", row=3, disabled=self.page <= 1)
            self.button("Next", self.on_next, emoji="▶️", row=3, disabled=self.page >= self.pages)
        if sel:
            acts = items.actions(sel)
            if "use" in acts:
                self.button(items.use_label(sel), self.on_use, emoji="✨", style=discord.ButtonStyle.success, row=3)
            if "unequip" in acts:
                self.button("Unequip", self.on_unequip_weapon, emoji="🤜", row=3)
            if "discard" in acts:
                self.button("Discard", self.on_ask_discard, emoji="🗑️", row=3)

    async def on_category(self, interaction):
        self.category, self.page, self.selected, self.confirm_discard = interaction.data["values"][0], 1, None, False
        await self.show(interaction)

    async def on_pick(self, interaction):
        self.selected, self.confirm_discard = int(interaction.data["values"][0]), False
        await self.show(interaction)

    async def on_prev(self, interaction):
        self.page, self.selected = self.page - 1, None
        await self.show(interaction)

    async def on_next(self, interaction):
        self.page, self.selected = self.page + 1, None
        await self.show(interaction)

    async def on_use(self, interaction):
        item_id = self.selected
        if item_id is None:
            return await self.show(interaction)
        sel = getattr(self, "selected_item", None)
        if sel and sel["category"] == "weapons" and self.in_fight():
            self.notice = "⚔️ You can't change weapons in the middle of a fight."
            return await self.show(interaction)
        news = []
        async with self.bot.db_lock:
            self.notice = loot.use_item(self.bot.conn, self.owner_id, item_id, announce=news)
        await self.show(interaction)
        for line in news:
            await interaction.followup.send(line)

    async def on_ask_discard(self, interaction):
        self.confirm_discard = True
        self.notice = "🗑️ Discarded items are gone for good. Are you sure?"
        await self.show(interaction)

    async def on_cancel_discard(self, interaction):
        self.confirm_discard = False
        await self.show(interaction)

    def discard_callback(self, qty):
        async def cb(interaction):
            item_id, self.confirm_discard = self.selected, False
            async with self.bot.db_lock:
                ok, self.notice = items.discard(self.bot.conn, self.owner_id, item_id, qty)
            if ok:
                self.selected = None
            await self.show(interaction)
        return cb

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass


async def open_sheet(bot, interaction, tab, category=None):
    """Send a new Character Sheet on `tab` (the command callbacks call this)."""
    await interaction.response.defer()
    view = CharacterSheet(bot, interaction.user, tab, category)
    file = await view.render()
    view.message = await interaction.followup.send(file=file, view=view, wait=True)


async def send_public_profile(bot, interaction, member):
    """Someone else's profile: the Profile card only, with their purse hidden and no buttons."""
    await interaction.response.defer()
    data = sheet.profile_data(bot.conn, member.id, username=member.name, private=False)
    data["avatar_bytes"] = await fetch_avatar(member)
    image = await card_render.render(RENDERERS["profile"], data)
    await interaction.followup.send(file=png(image, "profile.png"))
