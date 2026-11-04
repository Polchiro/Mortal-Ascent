"""
Discord buttons and menus for /inventory, /explore and /train.

Each view belongs to the player who ran the command; anyone else pressing
its buttons gets a polite "not yours". Every view answers on error, so a
button never leaves Discord stuck on "This interaction failed".
"""
import asyncio
import io
import logging
import random
import time

import discord

import explore
import training
from inventory_card import (CHEST_CHARS, MATERIAL_CHAR, PER_PAGE, manual_item, render_inventory,
                            weapon_item)
from profile_card import GRADES, JADE
import technique

from . import db, loot, trainer
from . import player as rules
from .expedition import PATH_EMOJI, Expedition

log = logging.getLogger("mortal-ascent")
COLOR = 0xB02C22
ERROR_MSG = "⚠️ Something went wrong on our side. The error was logged; please try again in a moment."


def png(image, filename):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename=filename)


async def safe_reply(interaction, msg):
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        log.exception("Could not send a reply")


class OwnedView(discord.ui.View):
    def __init__(self, owner_id, timeout=180):
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.message = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("These buttons belong to someone else.", ephemeral=True)
            return False
        return True

    async def on_error(self, interaction, error, item):
        log.exception("View %s failed", type(self).__name__, exc_info=error)
        await safe_reply(interaction, ERROR_MSG)

    def button(self, label, callback, emoji=None, style=discord.ButtonStyle.secondary, row=None, disabled=False):
        b = discord.ui.Button(label=label, emoji=emoji, style=style, row=row, disabled=disabled)
        b.callback = callback
        self.add_item(b)
        return b

    def disable_all(self):
        for item in self.children:
            item.disabled = True


def hp_bar(hp, max_hp, width=12):
    filled = round(width * hp / max_hp) if max_hp else 0
    return "▰" * filled + "▱" * (width - filled) + f"  {hp:,}/{max_hp:,}"


# ── /inventory ────────────────────────────────────────────────────────

USE_VERB = {"chests": "Open", "weapons": "Equip", "manuals": "Learn", "pills": "Take"}


def tile_for(item, learned_names):
    cat, qty = item["category"], item["qty"]
    if cat == "manuals":
        t = technique.TECHNIQUES[item["key"]]
        return manual_item(t, qty=qty, learned=t["name"] in learned_names)
    if cat == "weapons":
        return weapon_item(item["name"], item["grade"], rules.buff_text(rules.weapon_buffs(item)).replace("  ·  ", " · "),
                           equipped=bool(item["equipped"]))
    if cat == "pills":
        char, color = GRADES[item["grade"]]
        return {"char": char, "color": color, "name": item["name"], "qty": qty,
                "sub": f"×{training.QI_PILLS[item['grade']]} Qi · {training.QI_PILL_DURATION_HOURS}h"}
    if cat == "chests":
        char, color = CHEST_CHARS[item["key"]]
        return {"char": char, "color": color, "name": item["name"], "qty": qty, "sub": "Open for loot"}
    return {"char": MATERIAL_CHAR, "color": JADE, "name": item["name"], "qty": qty, "sub": "Pill ingredient"}


def inventory_data(conn, user_id, category, page):
    p = db.get_player(conn, user_id)
    items = db.get_items(conn, user_id, category)
    learned = {t["name"] for t in db.get_techniques(conn, user_id, equipped_only=False)}
    pages = max(1, -(-len(items) // PER_PAGE))
    page = min(max(1, page), pages)
    data = {"name": p["name"], "category": category, "page": page,
            "items": [tile_for(i, learned) for i in items],
            "counts": db.category_counts(conn, user_id), "capacity": p["bag_capacity"]}
    return data, items[(page - 1) * PER_PAGE: page * PER_PAGE], pages


class InventoryView(OwnedView):
    def __init__(self, bot, owner_id, category="manuals"):
        super().__init__(owner_id, timeout=300)
        self.bot, self.category, self.page, self.pages = bot, category, 1, 1

    async def render(self):
        """Build components for the current page and return the card as a discord.File."""
        data, page_items, self.pages = inventory_data(self.bot.conn, self.owner_id, self.category, self.page)
        self.page = data["page"]
        self.clear_items()

        cat_select = discord.ui.Select(placeholder="Category", row=0, options=[
            discord.SelectOption(label=label, value=key, default=key == self.category)
            for key, label in (("manuals", "Manuals"), ("weapons", "Weapons"), ("pills", "Pills"),
                               ("materials", "Materials"), ("chests", "Chests"))])
        cat_select.callback = self.on_category
        self.add_item(cat_select)

        usable = [i for i in page_items if i["category"] in USE_VERB]
        if usable:
            use = discord.ui.Select(placeholder="Use an item...", row=1, options=[
                discord.SelectOption(label=f"{USE_VERB[i['category']]}: {i['name']}"[:100], value=str(i["id"]),
                                     description=(f"×{i['qty']}" if i["qty"] > 1 else None))
                for i in usable])
            use.callback = self.on_use
            self.add_item(use)

        self.button("Prev", self.on_prev, emoji="◀️", row=2, disabled=self.page <= 1)
        self.button("Next", self.on_next, emoji="▶️", row=2, disabled=self.page >= self.pages)
        image = await asyncio.to_thread(render_inventory, data)
        return png(image, "inventory.png")

    async def refresh(self, interaction):
        await interaction.response.defer()
        file = await self.render()
        await interaction.edit_original_response(attachments=[file], view=self)

    async def on_category(self, interaction):
        self.category, self.page = interaction.data["values"][0], 1
        await self.refresh(interaction)

    async def on_prev(self, interaction):
        self.page -= 1
        await self.refresh(interaction)

    async def on_next(self, interaction):
        self.page += 1
        await self.refresh(interaction)

    async def on_use(self, interaction):
        item_id = int(interaction.data["values"][0])
        await interaction.response.defer()
        async with self.bot.db_lock:
            msg = loot.use_item(self.bot.conn, self.owner_id, item_id)
        file = await self.render()
        await interaction.edit_original_response(attachments=[file], view=self)
        await interaction.followup.send(msg, ephemeral=True)

    async def on_timeout(self):
        self.disable_all()
        if self.message:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                pass


# ── /explore ──────────────────────────────────────────────────────────

class ExploreView(OwnedView):
    def __init__(self, bot, owner_id, rng=None):
        super().__init__(owner_id, timeout=300)
        self.bot = bot
        self.exp = Expedition(bot.conn, owner_id, rng)
        self.exp.next_step()
        self.choosing = True
        self.notice = None
        self.build()

    def embed(self):
        e = self.exp
        title = (f"🌲 Expedition · Step {e.step}/{explore.MAX_STEPS}" if not e.over
                 else ("☠️ Expedition failed" if e.defeated else "🏮 You return safely"))
        e_ = discord.Embed(title=title, color=COLOR)
        if e.over:
            e_.description = "\n".join(e.story + [""] + e.summary).strip()
            mins = explore.EXPLORE_COOLDOWN_MINUTES
            e_.set_footer(text=f"You can explore again in {mins} minutes.")
        elif self.choosing:
            lines = list(e.story) + ([""] if e.story else [])
            lines.append("Three paths lie ahead:")
            lines += [f"{PATH_EMOJI[p]} *{clue}*" for p, (_, clue) in e.paths.items()]
            if e.step > 1:
                lines.append(f"\n*Step {e.step}: rarer finds, but beasts are +{(e.step - 1) * 10}% stronger.*")
            e_.description = "\n".join(lines)
        else:
            e_.description = "\n".join(e.story)
        if self.notice:
            e_.description += f"\n\n*{self.notice}*"
        e_.add_field(name="❤️ HP", value=hp_bar(e.hp, e.max_hp), inline=False)
        found = []
        if e.coins:
            found.append(f"🪷 {e.coins:,}")
        found += [loot.describe(i) for i in e.items]
        if not e.over:
            e_.add_field(name="🎒 Found so far", value=", ".join(found) or "Nothing yet", inline=False)
        return e_

    def build(self):
        self.clear_items()
        e = self.exp
        if e.over:
            return
        if self.choosing:
            for path in explore.PATHS:
                self.button(path.title(), self.make_path(path), emoji=PATH_EMOJI[path], style=discord.ButtonStyle.primary)
            return
        if e.pending == "hazard":
            for path in explore.PATHS:
                self.button(path.title(), self.make_dodge(path), emoji=PATH_EMOJI[path], style=discord.ButtonStyle.danger)
            return
        if e.pending == "stranger":
            self.button(f"Give 🪷 {e.stranger_cost}", self.make_help("coins"), emoji="🪷")
            self.button("Tend wounds (−15% HP)", self.make_help("hp"), emoji="🩹")
            self.button("Walk past", self.make_help("leave"), emoji="🚶")
            return
        m = e.merchant
        if m and self.merchant_step == e.step:
            self.button(f"{m['pill']} Qi Pill · 🪷 {m['pill_price']}", self.make_buy("pill"), emoji="💊", row=0,
                        disabled="pill" in m["bought"])
            self.button(f"{m['herb']} · 🪷 {m['herb_price']}", self.make_buy("herb"), emoji="🌿", row=0,
                        disabled="herb" in m["bought"])
        if e.step < explore.MAX_STEPS:
            self.button("Go deeper", self.on_deeper, emoji="🔦", style=discord.ButtonStyle.primary, row=1)
        self.button("Return safely", self.on_return, emoji="🏮", style=discord.ButtonStyle.success, row=1)

    merchant_step = None

    async def update(self, interaction):
        self.build()
        await interaction.response.edit_message(embed=self.embed(), view=self)
        self.notice = None
        if self.exp.over:
            self.stop()
            self.bot.busy.discard((self.owner_id, "explore"))

    def make_path(self, path):
        async def cb(interaction):
            enc = self.exp.paths[path][0]
            async with self.bot.db_lock:
                self.exp.choose(path)
            self.choosing = False
            if enc == "wandering_merchant":
                self.merchant_step = self.exp.step
            await self.update(interaction)
            if self.exp.pending == "hazard":
                self.exp.hazard["shown_at"] = time.time()
        return cb

    def make_dodge(self, path):
        async def cb(interaction):
            async with self.bot.db_lock:
                self.exp.dodge(path)
            await self.update(interaction)
        return cb

    def make_help(self, how):
        async def cb(interaction):
            async with self.bot.db_lock:
                self.exp.help_stranger(how)
            await self.update(interaction)
        return cb

    def make_buy(self, what):
        async def cb(interaction):
            async with self.bot.db_lock:
                self.notice = self.exp.buy(what)
            await self.update(interaction)
        return cb

    async def on_deeper(self, interaction):
        self.exp.next_step()
        self.choosing = True
        await self.update(interaction)

    async def on_return(self, interaction):
        async with self.bot.db_lock:
            self.exp.story = ["You head back the way you came, loot in hand."]
            self.exp.finish()
        await self.update(interaction)

    async def on_timeout(self):
        """Idle for 5 minutes: walk home with what was found."""
        try:
            if not self.exp.over:
                async with self.bot.db_lock:
                    self.exp.story = ["You lingered too long; night falls and you head home."]
                    self.exp.finish()
            self.build()
            if self.message:
                await self.message.edit(embed=self.embed(), view=self)
        except Exception:
            log.exception("Explore timeout handling failed")
        finally:
            self.bot.busy.discard((self.owner_id, "explore"))


# ── /train ────────────────────────────────────────────────────────────

class TrainView(OwnedView):
    def __init__(self, bot, owner_id, session, rng=None):
        super().__init__(owner_id, timeout=900)
        self.bot, self.session = bot, session
        self.rng = rng or random.Random()
        self.future = None
        self.interaction = None    # the /train command interaction; we edit its message
        self.task = None
        self.button("Begin", self.on_begin, emoji="🥋", style=discord.ButtonStyle.success)

    def intro(self):
        s = self.session
        e = discord.Embed(title=f"Training · {trainer.CHALLENGE_NAMES[s['challenge']]}", color=COLOR)
        lines = []
        if s["event"] == "wandering_hermit":
            lines.append("🧙 **A Wandering Hermit appears!** *\"Let me see what you are made of.\"* "
                         "Hardest version, two conditions, **×5 Qi**.\n")
        lines.append("**Counters:** 🛡️ Guard beats ⚔️ Strike · 💥 Break beats 🛡️ Guard · ⚔️ Strike beats 💥 Break\n")
        if s["challenge"] == "read_the_master":
            lines.append("The master shows a **tell** for his next move. Press the counter before time runs out.")
            if trainer.challenges.READ_THE_MASTER["deceptive_chance"][s["tier"]] or "drunken_master" in s["conditions"]:
                lines.append("Some tells lie! Watch for the hidden sign: *clenched rear fist* = Strike, "
                             "*tucked elbows* = Guard, *lifted heel* = Break.")
        else:
            w = trainer.challenges.ENDLESS_WAVES
            lines.append(f"Disciples attack in waves, each faster. Stamina **{w['start_stamina']}**: each counter costs "
                         f"{w['counter_cost']}, a fast counter refunds {w['fast_counter_refund']}. "
                         f"✨ **Technique** works on anything for {w['technique_strike_cost']} stamina and gives ×2 points. "
                         f"Survive **{w['target_waves'][s['tier']]}** waves.")
        if s["conditions"]:
            lines.append("\n**Conditions** (+15% Qi each):")
            lines += [f"{trainer.CONDITION_NAMES[c]}: {trainer.CONDITION_TEXT[c]}" for c in s["conditions"]]
        e.description = "\n".join(lines)
        e.set_footer(text="Press Begin when you are ready. Buttons shuffle every round.")
        return e

    async def on_begin(self, interaction):
        self.clear_items()
        await interaction.response.edit_message(embed=self.step_embed("*Get ready...*"), view=self)
        self.task = asyncio.create_task(self.run())

    def step_embed(self, body, title=None, footer=None):
        e = discord.Embed(title=title or f"Training · {trainer.CHALLENGE_NAMES[self.session['challenge']]}",
                          description=body.strip(), color=COLOR)
        if footer:
            e.set_footer(text=footer)
        return e

    def set_choices(self, choices):
        self.clear_items()
        choices = list(choices)
        self.rng.shuffle(choices)   # anti-AFK: positions shuffle every round
        for key, label, emoji in choices:
            async def cb(interaction, key=key):
                await interaction.response.defer()
                if self.future and not self.future.done():
                    self.future.set_result((key, time.monotonic()))
            self.button(label, cb, emoji=emoji, style=discord.ButtonStyle.primary)

    async def edit(self, embed, view=True):
        await self.interaction.edit_original_response(embed=embed, view=self if view else None)

    async def ask(self, embed, hidden_embed, choices, seconds):
        """Show a prompt with buttons. Returns (choice or None, elapsed seconds)."""
        self.set_choices(choices)
        self.future = asyncio.get_running_loop().create_future()
        await self.edit(hidden_embed or embed)
        t0 = time.monotonic()
        wait = seconds + trainer.TIMER_GRACE_SECONDS
        if hidden_embed:
            reveal = seconds * (1 - training_reveal())
            try:
                key, at = await asyncio.wait_for(asyncio.shield(self.future), reveal)
                return key, at - t0
            except asyncio.TimeoutError:
                await self.edit(embed)
                wait -= reveal
        try:
            key, at = await asyncio.wait_for(self.future, max(0.1, wait))
            return key, at - t0
        except asyncio.TimeoutError:
            return None, seconds + trainer.TIMER_GRACE_SECONDS

    def counter_choices(self):
        return [(st, trainer.STANCE_LABEL[st], trainer.STANCE_EMOJI[st]) for st in trainer.STANCES]

    async def read_master(self, tier, conditions, steps=None, title=None):
        plan = trainer.master_steps(tier, conditions, self.rng, steps)
        night = "night_training" in conditions
        right, last = 0, ""
        for i, (stance, tell, secs) in enumerate(plan, 1):
            head = f"{last}\n\n**Move {i}/{len(plan)}** · ⏱️ {secs:g}s\n"
            embed = self.step_embed(head + f"🥋 *{tell}*", title)
            hidden = self.step_embed(head + "🌙 *Darkness... you cannot see his move yet.*", title) if night else None
            key, elapsed = await self.ask(embed, hidden, self.counter_choices(), secs)
            want = trainer.counter_of(stance)
            if key == want and elapsed <= secs + trainer.TIMER_GRACE_SECONDS:
                right += 1
                last = f"✅ Correct! He was going to **{trainer.STANCE_LABEL[stance]}**."
            elif key is None or elapsed > secs + trainer.TIMER_GRACE_SECONDS:
                last = f"⏳ Too slow! It was a **{trainer.STANCE_LABEL[stance]}** (counter: {trainer.STANCE_LABEL[want]})."
            else:
                last = f"❌ He was going to **{trainer.STANCE_LABEL[stance]}**, so {trainer.STANCE_LABEL[want]} was the counter."
        return right / len(plan), last, right

    async def endless_waves(self, tier, conditions):
        w = trainer.Waves(tier, conditions)
        night = "night_training" in conditions
        last = ""
        choices = self.counter_choices() + [("technique", "Technique", "✨")]
        while not w.done:
            stance = self.rng.choice(trainer.STANCES)
            secs = trainer.wave_seconds(tier, w.wave + 1, conditions)
            head = (f"{last}\n\n**Wave {w.wave + 1}** · ⏱️ {secs:.2g}s · 💪 Stamina {w.stamina:g} · "
                    f"Points {w.points:g}/{w.target}\n")
            embed = self.step_embed(head + f"A disciple attacks with a **{trainer.STANCE_EMOJI[stance]} "
                                           f"{trainer.STANCE_LABEL[stance]}**!")
            hidden = self.step_embed(head + "🌙 *A shape moves in the dark...*") if night else None
            key, elapsed = await self.ask(embed, hidden, choices, secs)
            last = w.answer(stance, key, elapsed, secs)
        return w.score, f"{last}\n\nYou scored **{w.points:g}** of {w.target} points."

    async def run(self):
        uid = self.owner_id
        try:
            s = self.session
            if s["challenge"] == "read_the_master":
                score, last, _ = await self.read_master(s["tier"], s["conditions"])
            else:
                score, last = await self.endless_waves(s["tier"], s["conditions"])

            mult, notes = 1.0, []
            if s["event"] == "wandering_hermit":
                mult *= trainer.challenges.EVENTS["wandering_hermit"]["exp_multiplier"]
                notes.append("🧙 The hermit nods. **×5 Qi!**")
            elif s["event"] == "epiphany":
                mult *= 1 + trainer.challenges.EVENTS["epiphany"]["exp_bonus"]
                notes.append("💡 **Epiphany!** Something clicks: +50% Qi.")
            elif s["event"] == "rival_disciple":
                await self.edit(self.step_embed(f"{last}\n\n⚔️ **A rival disciple interrupts!** "
                                                f"*\"You call that training?\"* Win {trainer.RIVAL_WINS_NEEDED} of "
                                                f"{trainer.RIVAL_STEPS} exchanges for ×2 Qi!"), view=False)
                await asyncio.sleep(3)
                _, last2, wins = await self.read_master(s["tier"], s["conditions"], trainer.RIVAL_STEPS,
                                                        title="⚔️ Rival Disciple")
                if wins >= trainer.RIVAL_WINS_NEEDED:
                    mult *= trainer.challenges.EVENTS["rival_disciple"]["win_exp_multiplier"]
                    notes.append(f"{last2}\n⚔️ You beat the rival! **×2 Qi!**")
                else:
                    notes.append(f"{last2}\n⚔️ The rival laughs and walks off. No bonus this time.")

            async with self.bot.db_lock:
                qi, events, p = trainer.finish(self.bot.conn, uid, s, score, mult, self.rng)
            need = rules.qi_needed(p["realm"], p["layer"])
            lines = [last, ""] + notes + [
                f"**Score:** {score:.0%}" + ("  *(below 50%: only 10% Qi)*" if score < 0.5 else ""),
                f"**Internal Qi:** +{qi:,.1f}",
                f"**{p['realm']}, {rules.ordinal(p['layer'])} Layer** · Qi {p['qi']:,.1f} / {need:,}",
            ] + events
            mins = trainer.cooldown_seconds(p) / 60
            self.clear_items()
            await self.edit(self.step_embed("\n".join(lines).strip(), title="🥋 Training complete",
                                            footer=f"You can train again in {mins:g} minutes."), view=False)
        except Exception:
            log.exception("/train session failed")
            try:
                await self.edit(self.step_embed(ERROR_MSG, title="Training interrupted"), view=False)
            except Exception:
                try:
                    await self.interaction.followup.send(ERROR_MSG, ephemeral=True)
                except Exception:
                    log.exception("Could not report the /train failure")
        finally:
            self.stop()
            self.bot.busy.discard((uid, "train"))

    async def on_timeout(self):
        # Begin was never pressed
        self.bot.busy.discard((self.owner_id, "train"))
        if self.task is None and self.interaction:
            try:
                await self.edit(self.step_embed("*You never stepped onto the training ground.*"), view=False)
            except discord.HTTPException:
                pass


def training_reveal():
    return trainer.challenges.CONDITIONS["night_training"]["reveal_at_timer_fraction"]
