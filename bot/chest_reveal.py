"""
Chest Opening Reward Reveal (opened from the Inventory's Open button, bot/sheet/view.py).

Rolling and showing are separate:

1. loot.begin_chest rolls the chest once (the same tables and odds as always) and, in one database step,
   takes the chest out of the bag and stores the roll as a pending chest. Nothing is granted yet.
2. ChestReveal shows that stored roll in stages: the sealed chest -> Break the Seal -> the lid opens with a
   light whose colour hints at the best reward -> every reward, best first, styled by rarity.
3. Collect Rewards calls loot.claim_chest, which marks the pending chest collected and grants its coins and
   items exactly once. A second click, a stale button or a restart can't grant it again.

If the player never presses Collect, the rewards are not lost: the view collects them when it times out, and
any pending chest left behind (a restart) is collected the next time the Character Sheet opens.
"""
import asyncio
import logging
import time
import zlib

import discord

import forge

from . import db, loot, materials
from . import render as card_render
from .sheet import items as bag
from .views import OwnedView, png

log = logging.getLogger("mortal-ascent")

REVEAL_TIMEOUT_SECONDS = 600          # the reveal's buttons work this long; then the rewards are collected for you
OPENING_PAUSE_SECONDS = 1.6           # how long the opening light shows before the rewards
STALE_AFTER_SECONDS = REVEAL_TIMEOUT_SECONDS + 60   # older pending chests are collected when the sheet opens

RARITIES = forge.RARITIES             # Common .. Mythical, with forge.RARITY_COLORS
GEAR_RARITY = {"ordinary": "Common", "refined": "Uncommon", "spirit": "Rare", "treasure": "Epic", "divine": "Legendary"}
GRADE_RARITY = {"Mortal": "Common", "Yellow": "Uncommon", "Mystic": "Rare", "Earth": "Epic", "Heaven": "Legendary"}
ESSENCE_RARITY = {"shard": "Uncommon", "crystal": "Epic", "heart": "Legendary"}
FLAVOR = {
    "Epic": ["A treasure sect elders would quarrel over.", "Its aura is thick enough to taste.",
             "Few cultivators ever hold such a thing."],
    "Legendary": ["Its radiance stills the air of the secret realm.", "Ancient powers once fought over this.",
                  "The kind of find told about in teahouses for years."],
    "Mythical": ["The heavens themselves tremble. Such a find comes once in a lifetime.",
                 "Fate bends around it. Even immortals would envy you."],
}
EXCEPTIONAL = {
    "Epic": "🟣 Violet light floods the chamber: **{item}**!",
    "Legendary": "🌟 **Golden radiance!** You hold **{item}**, a legendary treasure!",
    "Mythical": "🔴✨ **THE HEAVENS TREMBLE!** A mythical treasure, **{item}**, answers your call!",
}


def reward_rarity(item):
    """One of Common .. Mythical for an item a chest gives (display only; the roll decides the item)."""
    cat, grade, key = item["category"], item.get("grade"), item.get("key", "")
    if key == "heaven_defying":
        return "Mythical"
    if cat in ("weapons", "armor", "artifacts"):
        return GEAR_RARITY.get(grade, "Common")
    if cat in ("manuals", "pills", "herbs"):
        return GRADE_RARITY.get(grade, "Common")
    if cat == "materials" and key in materials.MATERIALS:
        m = materials.MATERIALS[key]
        if m["kind"] == "essence":
            return ESSENCE_RARITY.get(m["grade"], "Uncommon")
        if m["kind"] == "seal":
            return "Epic"
        return RARITIES[max(0, min(4, m["tier"] - 1))]
    return GRADE_RARITY.get(grade, "Common")


def reward_view(item, player):
    """How one reward shows on the card: name, quantity, icon, rarity, kind and its main effect."""
    rarity = reward_rarity(item)
    full = dict(item, id=0, equipped=0, qty=item.get("qty", 1))
    try:
        info = bag.details(full, player)
        kind, line = info["kind"], (info["effects"][0] if info["effects"] else "")
    except Exception:                       # a reward the Inspect panel doesn't describe: show it plainly
        log.warning("No details for chest reward %s", item.get("key"), exc_info=True)
        kind, line = item["category"].title(), ""
    flavor = None
    if rarity in FLAVOR:
        options = FLAVOR[rarity]
        flavor = options[zlib.crc32(item["name"].encode()) % len(options)]
    return {"name": loot.describe(dict(item, qty=1)), "qty": full["qty"], "icon": bag.item_icon(full),
            "rarity": rarity, "color": forge.RARITY_COLORS[rarity], "kind": kind, "line": line, "flavor": flavor}


def card_data(pending, player, stage, result=None):
    """What cards/chest.py draws for one stage. `result` (from loot.claim_chest) marks what was left behind."""
    lost_ids = {id(x) for x in (result or {}).get("lost", [])}
    items = (result["stored"] + result["lost"]) if result else pending["items"]
    rewards = []
    for it in items:
        rw = reward_view(it, player)
        rw["lost"] = id(it) in lost_ids
        rewards.append(rw)
    rewards.sort(key=lambda r: -RARITIES.index(r["rarity"]))
    best = rewards[0]["rarity"] if rewards else "Common"
    return {"stage": stage, "chest_key": pending["chest_key"], "chest_name": pending["chest_name"],
            "coins": pending["coins"], "rewards": rewards, "best": best, "notes": pending["notes"],
            "collected": stage == "collected", "rarity_colors": forge.RARITY_COLORS}


def exceptional_lines(data):
    """Highlight lines under the reveal for Epic and better rewards."""
    out = []
    for rw in data["rewards"]:
        if rw["rarity"] in EXCEPTIONAL and not rw.get("lost"):
            out.append(EXCEPTIONAL[rw["rarity"]].format(item=rw["name"]))
    return out[:3]


def sheet_emoji(bot, key):
    from .sheet.view import sheet_emoji as emoji
    return emoji(bot, key)


class ChestReveal(OwnedView):
    """One opened chest: Break the Seal -> opening light -> rewards -> Collect Rewards (granted once)."""

    def __init__(self, bot, user, pending, sheet=None):
        super().__init__(user.id, timeout=REVEAL_TIMEOUT_SECONDS)
        self.bot, self.user, self.pending, self.sheet = bot, user, pending, sheet
        self.stage = "sealed"
        self.result = None
        self.build()

    def player(self):
        return db.get_player(self.bot.conn, self.owner_id)

    def data(self):
        return card_data(self.pending, self.player(), self.stage, self.result)

    async def file(self):
        from cards.chest import render_chest
        image = await card_render.render(render_chest, self.data())
        return png(image, "chest.png")

    def build(self):
        self.clear_items()
        if self.stage == "sealed":
            self.button("Break the Seal", self.on_break, emoji=sheet_emoji(self.bot, "sheet_break_seal"),
                        style=discord.ButtonStyle.primary)
        elif self.stage == "reveal":
            self.button("Collect Rewards", self.on_collect, emoji=sheet_emoji(self.bot, "sheet_collect"),
                        style=discord.ButtonStyle.success)

    def text(self):
        if self.stage == "sealed":
            return f"🔒 You carry the **{self.pending['chest_name']}** to a quiet corner of the secret realm..."
        if self.stage == "reveal":
            lines = exceptional_lines(self.data())
            return "\n".join(lines + ["Press **Collect Rewards** to put them in your bag."])
        return None

    async def on_break(self, interaction):
        self.stage = "opening"
        self.clear_items()
        await interaction.response.edit_message(content=None, attachments=[await self.file()], view=self)
        best = self.data()["best"]
        await asyncio.sleep(OPENING_PAUSE_SECONDS + (0.8 if RARITIES.index(best) >= 4 else 0))
        self.stage = "reveal"
        self.build()
        try:
            await interaction.edit_original_response(content=self.text(), attachments=[await self.file()], view=self)
        except discord.HTTPException:       # the interaction expired: the rewards stay pending (collected later)
            log.warning("Could not show chest rewards", exc_info=True)

    async def collect(self):
        """Grant the pending chest once. Returns announcement lines for rare finds."""
        news = []
        async with self.bot.db_lock:
            self.result = loot.claim_chest(self.bot.conn, self.owner_id, self.pending["id"], announce=news)
        self.stage = "collected"
        self.clear_items()
        return news

    def collected_text(self, auto=False):
        if self.result is None:
            return "These rewards were already added to your bag."
        lost = self.result["lost"]
        msg = ("⌛ The reveal timed out, so your rewards were collected for you." if auto
               else "🎒 **Rewards collected.** Everything is in your bag.")
        if lost:
            msg += f"\n⚠️ Your bag was full, so {len(lost)} item{'s' if len(lost) > 1 else ''} stayed behind."
        return msg

    async def on_collect(self, interaction):
        await interaction.response.defer()
        news = await self.collect()
        try:
            await interaction.edit_original_response(content=self.collected_text(), attachments=[await self.file()],
                                                     view=None)
        except discord.HTTPException:
            log.warning("Could not show collected chest", exc_info=True)
        for line in news:
            await interaction.followup.send(line)
        await self.refresh_sheet()
        self.stop()

    async def refresh_sheet(self):
        """Redraw the Character Sheet the chest came from, so its bag shows the new items."""
        sheet = self.sheet
        if not sheet or not sheet.message or sheet.is_finished():
            return
        try:
            file = await sheet.render()
            await sheet.message.edit(attachments=[file], view=sheet)
        except discord.HTTPException:
            log.warning("Could not refresh the sheet after a chest", exc_info=True)

    async def on_timeout(self):
        if self.stage == "collected":
            return
        news = await self.collect()
        if self.message:
            try:
                await self.message.edit(content=self.collected_text(auto=True), attachments=[await self.file()],
                                        view=None)
                for line in news:
                    await self.message.channel.send(line)
            except discord.HTTPException:
                log.warning("Could not update a timed-out chest", exc_info=True)


async def post(bot, interaction, sheet, pending):
    """Post the sealed chest under the sheet (after the Inventory's Open button stored the roll)."""
    view = ChestReveal(bot, interaction.user, pending, sheet)
    try:
        view.message = await interaction.followup.send(content=view.text(), file=await view.file(), view=view,
                                                       wait=True)
    except discord.HTTPException:
        # the reveal couldn't be posted: grant now so nothing is lost, and say what was inside
        log.warning("Could not post a chest reveal; granting it directly", exc_info=True)
        view.stop()
        async with bot.db_lock:
            result = loot.claim_chest(bot.conn, interaction.user.id, pending["id"])
        if result:
            try:
                await interaction.followup.send(loot.chest_text(result))
            except discord.HTTPException:
                pass


def collect_stale(conn, user_id, now=None, announce=None):
    """Collect pending chests nobody collected (the bot restarted mid-reveal). Returns a notice or None."""
    now = time.time() if now is None else now
    found = db.unclaimed_chests(conn, user_id, before=now - STALE_AFTER_SECONDS)
    lines = []
    for p in found:
        result = loot.claim_chest(conn, user_id, p["id"], announce=announce, now=now)
        if result:
            got = ", ".join(loot.describe(i) for i in result["stored"]) or "no items"
            lines.append(f"🎁 Unopened rewards from your **{result['chest_name']}** were added: "
                         f"{result['coins']:,} Lotus Coins, {got}.")
    return "\n".join(lines) or None
