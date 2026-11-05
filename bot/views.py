"""
Discord buttons and menus for /explore, /train, /spar, hunts, the shop and blessings.
The Character Sheet tabs (/profile, /inventory, /techniques, ...) are in bot/sheet/view.py.

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

import economy
import explore
import talent as talent_rules
import technique

from . import db, hunt, loot, mastery, trainer
from . import player as rules
from . import result_cards
from cards.activity import render_explore, render_spar, render_train
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


STILL_WORKING_MSG = "⏳ Your last click is still being handled. Wait a moment."
OLD_BUTTON_MSG = "That button is from an earlier step and no longer works. Use the newest buttons."


class OwnedView(discord.ui.View):
    """A view only its owner can press.

    Every button and menu is guarded against lag exploits: while one click is being handled, other
    clicks on the view are turned away, and buttons from an earlier step (before the view was
    rebuilt) or from a finished view do nothing. So a double click can't run an action twice."""

    def __init__(self, owner_id, timeout=180):
        self._generation = 0       # goes up every time the buttons are rebuilt
        self._handling = False     # a click is being handled right now
        super().__init__(timeout=timeout)
        self.owner_id = owner_id
        self.message = None

    def clear_items(self):
        self._generation += 1
        return super().clear_items()

    def add_item(self, item):
        inner, generation = item.callback, self._generation

        async def guarded(interaction):
            if self._handling:
                await safe_reply(interaction, STILL_WORKING_MSG)
                return
            if generation != self._generation or self.is_finished():
                await safe_reply(interaction, OLD_BUTTON_MSG)
                return
            self._handling = True       # set before any await, so a second click can't slip in
            try:
                await inner(interaction)
            finally:
                self._handling = False

        item.callback = guarded
        return super().add_item(item)

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

    lair_posted = False
    news_sent = False

    async def update(self, interaction):
        self.build()
        if self.exp.over:
            await interaction.response.defer()
            file = await result_cards.card_file(render_explore, result_cards.explore_data(self.exp), "explore.png")
            if file:
                await interaction.edit_original_response(embed=None, attachments=[file], view=None)
            else:
                await interaction.edit_original_response(embed=self.embed(), view=None)
        else:
            await interaction.response.edit_message(embed=self.embed(), view=self)
        self.notice = None
        if self.exp.lair and not self.lair_posted:
            self.lair_posted = True
            await post_hunt(self.bot, interaction, self.exp.lair, self.exp.player)
        if self.exp.over and not self.news_sent:
            self.news_sent = True
            for line in self.exp.announce:
                await interaction.followup.send(line)
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
                file = await result_cards.card_file(render_explore, result_cards.explore_data(self.exp), "explore.png")
                if file:
                    await self.message.edit(embed=None, attachments=[file], view=None)
                else:
                    await self.message.edit(embed=self.embed(), view=None)
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

    @property
    def title(self):
        s = self.session
        what = f"Practice: {s['technique_name']}" if s["mode"] == "practice" else "Training"
        return f"{what} · {trainer.CHALLENGE_NAMES[s['challenge']]}"

    def intro(self):
        s = self.session
        e = discord.Embed(title=self.title, color=COLOR)
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
        elif s["challenge"] == "ambush":
            a = trainer.challenges.AMBUSH
            lines.append(f"Two disciples attack at once, one marked 💪 stronger (hits for {a['strong_opponent_damage']}). "
                         f"Pick **one** counter: it stops every attacker whose move it beats, the rest hit you. "
                         f"You have **{a['player_hp']} HP**. Survive "
                         f"**{trainer.Ambush(s['tier']).target}** rounds.")
        elif s["challenge"] == "find_the_weakness":
            w = trainer.Weakness(s["tier"])
            lines.append(f"The master hides a sequence of **{w.length} moves**: his weakness. Press moves to build a guess. "
                         f"After each guess: ✅ = right move, right place · 🔶 = right move, wrong place. "
                         f"You have **{w.tries} tries**; fewer tries, higher score.")
        else:
            w = trainer.challenges.ENDLESS_WAVES
            lines.append(f"Disciples attack in waves, each faster. Stamina **{w['start_stamina']}**: each counter costs "
                         f"{w['counter_cost']}, a fast counter refunds {w['fast_counter_refund']}. "
                         f"✨ **Technique** works on anything for {w['technique_strike_cost']} stamina and gives ×2 points. "
                         f"Survive **{w['target_waves'][s['tier']]}** waves.")
        if s["conditions"]:
            lines.append(f"\n**Conditions** (+15% {'mastery EXP' if s['mode'] == 'practice' else 'Qi'} each):")
            lines += [f"{trainer.CONDITION_NAMES[c]}: {trainer.CONDITION_TEXT[c]}" for c in s["conditions"]]
        e.description = "\n".join(lines)
        e.set_footer(text="Press Begin when you are ready. Buttons shuffle every round.")
        return e

    async def on_begin(self, interaction):
        self.clear_items()
        await interaction.response.edit_message(embed=self.step_embed("*Get ready...*"), view=self)
        self.task = asyncio.create_task(self.run())

    def step_embed(self, body, title=None, footer=None):
        e = discord.Embed(title=title or self.title,
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

    async def ambush(self, tier, conditions):
        a = trainer.Ambush(tier, self.rng)
        secs = trainer.timer(trainer.challenges.READ_THE_MASTER["seconds_per_step"][tier], conditions)
        night = "night_training" in conditions
        last = ""
        while not a.done:
            head = f"{last}\n\n**Round {a.round}** · ⏱️ {secs:g}s · ❤️ {a.hp} HP · Survived {a.survived}/{a.target}\n"
            sides = []
            for i, mv in enumerate(a.moves):
                tag = " 💪" if i == a.strong else ""
                sides.append(f"{'Left' if i == 0 else 'Right'} disciple{tag}: **{trainer.STANCE_EMOJI[mv]} "
                             f"{trainer.STANCE_LABEL[mv]}**")
            embed = self.step_embed(head + "\n".join(sides))
            hidden = self.step_embed(head + "🌙 *Two shapes move in the dark...*") if night else None
            key, elapsed = await self.ask(embed, hidden, self.counter_choices(), secs)
            last = a.answer(key, elapsed, secs)
        return a.score, f"{last}\n\nYou survived **{a.survived}** of {a.target} rounds."

    async def weakness(self, tier):
        w = trainer.Weakness(tier, self.rng)
        while not w.done:
            guess = []
            while len(guess) < w.length:
                hist = "\n".join(f"{' '.join(trainer.STANCE_EMOJI[m] for m in g)}  →  {'✅' * ex}{'🔶' * near}"
                                  f"{'▫️' * (w.length - ex - near)}" for g, (ex, near) in w.history)
                cur = " ".join(trainer.STANCE_EMOJI[m] for m in guess) + " ▫️" * (w.length - len(guess))
                body = (f"**Try {len(w.history) + 1}/{w.tries}** · build a guess of {w.length} moves\n"
                        + (hist + "\n\n" if hist else "") + f"Your guess: {cur}")
                key, _ = await self.ask(self.step_embed(body), None, self.counter_choices(), 60)
                if key is None:
                    w.history.append((guess, (0, 0)))
                    break
                guess.append(key)
            else:
                w.guess(guess)
        secret = " ".join(trainer.STANCE_EMOJI[m] for m in w.secret)
        if w.solved:
            return w.score, f"🎯 You found his weakness in **{len(w.history)}** tries: {secret}"
        return w.score, f"The master's weakness was {secret}. Better luck next time."

    async def run(self):
        uid = self.owner_id
        try:
            s = self.session
            if s["challenge"] == "read_the_master":
                score, last, _ = await self.read_master(s["tier"], s["conditions"])
            elif s["challenge"] == "ambush":
                score, last = await self.ambush(s["tier"], s["conditions"])
            elif s["challenge"] == "find_the_weakness":
                score, last = await self.weakness(s["tier"])
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

            score_line = f"**Score:** {score:.0%}" + ("  *(below 50%: only 10% reward)*" if score < 0.5 else "")
            if s["mode"] == "practice":
                async with self.bot.db_lock:
                    exp, daily, note, tech = trainer.finish_practice(self.bot.conn, uid, s, score, mult)
                    p = db.get_player(self.bot.conn, uid)
                cap = rules.mastery_cap(tech)
                bar = f"{tech['mastery_exp']:,} / {cap:,}" if cap else f"{tech['mastery_exp']:,} (final stage)"
                lines = [last, ""] + notes + [score_line, f"**{tech['name']}:** +{exp:,} mastery EXP · {bar}"]
                card_notes = [last] + notes
                if daily < 1:
                    lines.append(f"*Tired from practising today: EXP ×{daily:g}.*")
                    card_notes.append(lines[-1])
                if note:
                    lines.append(note)
                    card_notes.append(note)
                reward = {"technique": tech["name"], "exp": round(exp), "total": tech["mastery_exp"], "cap": cap}
                done_title, verb = "🥋 Practice complete", "practise"
            else:
                async with self.bot.db_lock:
                    qi, events, p = trainer.finish(self.bot.conn, uid, s, score, mult, self.rng)
                need = rules.qi_needed(p["realm"], p["layer"])
                lines = [last, ""] + notes + [
                    score_line, f"**Internal Qi:** +{qi:,.1f}",
                    f"**{p['realm']}, {rules.ordinal(p['layer'])} Layer** · Qi {p['qi']:,.1f} / {need:,}",
                ] + events
                card_notes = [last] + notes + events
                reward = {"qi": qi, "total": p["qi"], "need": need, "realm": p["realm"], "layer": p["layer"]}
                done_title, verb = "🥋 Training complete", "train"
            mins = trainer.cooldown_seconds(p, mode=s["mode"]) / 60
            self.clear_items()
            card = result_cards.train_data(p, s, score, reward, card_notes, mins, verb)
            file = await result_cards.card_file(render_train, card, "train.png")
            if file:
                await self.interaction.edit_original_response(embed=None, attachments=[file], view=None)
            else:
                await self.edit(self.step_embed("\n".join(lines).strip(), title=done_title,
                                                footer=f"You can {verb} again in {mins:g} minutes."), view=False)
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


# ── /spar ─────────────────────────────────────────────────────────────

class SparView(OwnedView):
    TURN_SECONDS = 60

    def __init__(self, bot, owner_id, focus=None, trial=False, rng=None):
        super().__init__(owner_id, timeout=self.TURN_SECONDS)
        from .sparring import Spar
        self.bot, self.rng = bot, rng or random.Random()
        conn = bot.conn
        self.player = db.get_player(conn, owner_id)
        self.techniques = db.get_techniques(conn, owner_id)
        self.focus, self.trial = focus, trial
        strength = 1.0
        if trial:
            strength = technique.TRIAL_MASTER_STRENGTH[rules.stage_of(focus) + 1]
        self.spar = Spar(self.player, self.techniques, db.equipped_weapon(conn, owner_id), strength, self.rng)
        self.last = ""
        self.result = None
        self.build()

    @property
    def title(self):
        return ("🏯 " if self.trial else "🥋 ") + self.title_plain

    @property
    def title_plain(self):
        if self.trial:
            nxt = technique.MASTERY_STAGES[rules.stage_of(self.focus) + 1]["name"]
            return f"Mastery Trial: {self.focus['name']} → {nxt}"
        return "Sparring with the Master"

    def embed(self):
        sp = self.spar
        e = discord.Embed(title=self.title, color=COLOR)
        if self.result:
            e.description = self.result
        else:
            lines = []
            if sp.turn == 1:
                lines.append("**Counters:** 🛡️ Guard beats ⚔️ Strike · 💥 Break beats 🛡️ Guard · ⚔️ Strike beats 💥 Break\n"
                             "Mastery EXP comes only from techniques used **at the right moment**: your attack technique "
                             "right after you Guard his Strike, your defense technique against his Strike.\n"
                             "Techniques need to **recover** for a few exchanges after use; plain Strike, Guard and "
                             "Break are always ready.\n")
                if self.trial:
                    lines.append(f"*This master fights at ×{sp.strength:g} strength. Win to break through.*\n")
            if self.last:
                lines.append(self.last + "\n")
            lines.append(f"**Exchange {sp.turn}/{MAX_TURNS_SPAR()}**")
            lines.append(sp.hint())
            e.description = "\n".join(lines)
        e.add_field(name="You", value=hp_bar(round(sp.hp), sp.max_hp, 10), inline=False)
        e.add_field(name="Master", value=hp_bar(round(sp.m_hp), sp.m_max, 10), inline=False)
        return e

    def build(self):
        self.clear_items()
        if self.result:
            return
        choices = self.spar.choices()
        self.rng.shuffle(choices)
        emoji = {"strike": "⚔️", "guard": "🛡️", "break": "💥", "attack_tech": "✨", "defense_tech": "🔰"}
        for key, label in choices:
            async def cb(interaction, key=key):
                await self.play(interaction, key)
            style = discord.ButtonStyle.success if key.endswith("_tech") else discord.ButtonStyle.primary
            left = self.spar.cooldowns.get(key, 0)
            if left:   # technique is cooling down: greyed out with turns remaining
                label = f"{label[:60]} (⏳ {left} turn{'s' if left > 1 else ''})"
                style = discord.ButtonStyle.secondary
            b = self.button(label[:80], cb, emoji=emoji[key], style=style,
                            row=0 if not key.endswith("_tech") else 1, disabled=bool(left))
            b.spar_key = key

    async def play(self, interaction, key):
        self.last = self.spar.play(key)
        if self.spar.over:
            async with self.bot.db_lock:
                self.result = self.finish()
        self.build()
        if not self.result:
            await interaction.response.edit_message(embed=self.embed(), view=self)
            return
        self.stop()
        self.bot.busy.discard((self.owner_id, "spar"))
        await interaction.response.defer()
        file = await result_cards.card_file(render_spar, self.card, "spar.png")
        if file:
            await interaction.edit_original_response(embed=None, attachments=[file], view=None)
        else:
            await interaction.edit_original_response(embed=self.embed(), view=None)

    def finish(self, forfeit=False):
        conn, uid, sp = self.bot.conn, self.owner_id, self.spar
        won = sp.won and not forfeit
        if forfeit:
            sp.timed = {}
        daily = rules.daily_rate(technique.SPAR_DAILY_RATES, db.daily_count(conn, uid, "spar"))
        lines = [self.last, ""] if self.last else []
        lines.append("🏆 **You win the spar!**" if won else ("🏳️ You walked away from the spar." if forfeit
                                                            else "😤 **The master wins this time.**"))
        notes = [self.last] if self.last else []        # for the result card
        gains = []
        by_id = {t["id"]: t for t in self.techniques}
        for tid, exp in sp.mastery_awards(daily).items():
            if forfeit:
                break
            gained, note = mastery.gain(conn, self.player, by_id[tid], exp)
            if gained:
                lines.append(f"📈 **{by_id[tid]['name']}** +{gained} mastery EXP")
                gains.append((by_id[tid], gained))
            if note and not self.trial:
                lines.append(note)
                notes.append(note)
        if not sp.timed and not forfeit:
            lines.append("*No technique was used at the right moment, so no mastery EXP this time.*")
        if daily < 1:
            lines.append(f"*You have sparred a lot today: EXP ×{daily:g}.*")
            notes.append(lines[-1])
        if self.trial:
            if won:
                stage = mastery.pass_trial(conn, self.focus)
                lines.append(f"🌸 **Breakthrough!** {self.focus['name']} reaches **{stage}**!")
            else:
                db.set_cooldown(conn, uid, f"trial:{self.focus['id']}", technique.TRIAL_FAIL_COOLDOWN_HOURS * 3600)
                lines.append(f"The trial failed. No EXP is lost; you may retry in {technique.TRIAL_FAIL_COOLDOWN_HOURS} hours.")
            notes.append(lines[-1])
        db.bump_daily(conn, uid, "spar")
        db.set_cooldown(conn, uid, "spar", technique.SPAR_COOLDOWN_MINUTES * 60)
        lines.append(f"\n*You can spar again in {technique.SPAR_COOLDOWN_MINUTES // 60} hours.*")
        outcome = "victory" if won else ("forfeit" if forfeit else "defeat")
        self.card = result_cards.spar_data(self, outcome, gains, notes)
        return "\n".join(lines).strip()

    async def on_timeout(self):
        try:
            if not self.result:
                self.last = "⏳ You stood still too long."
                async with self.bot.db_lock:
                    self.result = self.finish(forfeit=True)
                self.build()
                if self.message:
                    file = await result_cards.card_file(render_spar, self.card, "spar.png")
                    if file:
                        await self.message.edit(embed=None, attachments=[file], view=None)
                    else:
                        await self.message.edit(embed=self.embed(), view=None)
        except Exception:
            log.exception("Spar timeout handling failed")
        finally:
            self.bot.busy.discard((self.owner_id, "spar"))


def MAX_TURNS_SPAR():
    from .sparring import MAX_TURNS
    return MAX_TURNS


# ── /breakthrough and /seclusion confirmations ────────────────────────

class ConfirmView(OwnedView):
    """One action button plus Cancel. `action(interaction)` returns the text to show."""

    def __init__(self, owner_id, label, action, style=discord.ButtonStyle.danger, emoji=None):
        super().__init__(owner_id, timeout=120)
        self.action = action
        self.button(label, self.on_go, emoji=emoji, style=style)
        self.button("Cancel", self.on_cancel)

    async def on_go(self, interaction):
        embed = await self.action()
        self.clear_items()
        self.stop()
        await interaction.response.edit_message(embed=embed, view=None)

    async def on_cancel(self, interaction):
        self.stop()
        await interaction.response.edit_message(view=None)

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.HTTPException:
                pass


# ── Team hunts ────────────────────────────────────────────────────────

async def post_hunt(bot, interaction, lair, finder):
    # In a DM with the bot nobody else can see the call, so the finder hunts alone.
    solo = interaction.guild is None
    view = HuntView(bot, lair, finder, solo=solo)
    content = ("📢 **Server-wide alert!** A Beast King has been sighted!"
               if lair["tier"] == "beast_king" and not solo else None)
    view.message = await interaction.followup.send(content=content, embed=view.embed(), view=view, wait=True)


class HuntView(discord.ui.View):
    def __init__(self, bot, lair, finder, solo=False):
        super().__init__(timeout=max(30, lair["closes"] - time.time()))
        self.bot, self.lair = bot, lair
        self.solo = solo
        self.leader = finder["user_id"]
        self.members = {finder["user_id"]: finder["name"]}
        self.result = None
        self.message = None
        self.started = False
        if not solo:
            self.join_btn = OwnedView.button(self, "Join hunt", self.on_join, emoji="⚔️",
                                             style=discord.ButtonStyle.success)
            OwnedView.button(self, "Leave", self.on_leave, emoji="🚶")
        OwnedView.button(self, "Start the hunt", self.on_start, emoji="🔥", style=discord.ButtonStyle.danger)

    def embed(self):
        name, tier, role = self.lair["beast"]
        size = beasts_team_size(tier)
        label = "👑 Beast King Den" if tier == "beast_king" else "⚔️ Elite Lair"
        e = discord.Embed(title=f"{label}: {name}", color=COLOR)
        if self.result:
            e.description = self.result
            return e
        e.description = (f"A **{name}** ({role.title()}, {self.lair['realm']}) waits. Meant for a team of **{size}**; "
                         f"each extra fighter adds +20% to its HP. Its stats follow the team's strongest member.\n"
                         f"Watch for its **charged attacks**.\n\nThe lair closes <t:{int(self.lair['closes'])}:R>. "
                         + ("You are in a DM, so you hunt **alone**. Explore in a server to call a team."
                            if self.solo else "The finder starts the hunt."))
        e.add_field(name=f"Team ({len(self.members)}/{hunt.MAX_TEAM})", value="\n".join(self.members.values()))
        return e

    async def on_error(self, interaction, error, item):
        log.exception("Hunt view failed", exc_info=error)
        await safe_reply(interaction, ERROR_MSG)

    async def on_join(self, interaction):
        uid = interaction.user.id
        if uid in self.members:
            await interaction.response.send_message("You are already in this hunt.", ephemeral=True)
            return
        if len(self.members) >= hunt.MAX_TEAM:
            await interaction.response.send_message("The hunting party is full.", ephemeral=True)
            return
        p = db.get_player(self.bot.conn, uid)
        why = hunt.can_join(p)
        if why:
            await interaction.response.send_message(why, ephemeral=True)
            return
        self.members[uid] = p["name"]
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def on_leave(self, interaction):
        uid = interaction.user.id
        if uid == self.leader or uid not in self.members:
            await interaction.response.send_message(
                "The finder can't leave; just let the lair close." if uid == self.leader else "You are not in this hunt.",
                ephemeral=True)
            return
        del self.members[uid]
        await interaction.response.edit_message(embed=self.embed(), view=self)

    async def on_start(self, interaction):
        if interaction.user.id != self.leader:
            await interaction.response.send_message("Only the one who found the lair can start the hunt.", ephemeral=True)
            return
        if self.started:     # a double click during lag must not fight (and pay out) twice
            await interaction.response.send_message("The hunt has already begun!", ephemeral=True)
            return
        self.started = True
        await interaction.response.defer()
        async with self.bot.db_lock:
            fit = [u for u in self.members if not hunt.can_join(db.get_player(self.bot.conn, u))]
            won, lines, news = hunt.resolve(self.bot.conn, self.lair, fit or [self.leader])
        head = "🏆 **Victory!**" if won else "☠️ **The hunt failed.** Everyone limps home injured."
        self.result = "\n".join([head] + lines)
        self.clear_items()
        self.stop()
        await interaction.edit_original_response(content=None, embed=self.embed(), view=None)
        for line in news:
            await interaction.followup.send(line)

    async def on_timeout(self):
        if self.result or not self.message:
            return
        self.result = f"The {self.lair['beast'][0]} has moved on. The lair is empty."
        self.clear_items()
        try:
            await self.message.edit(content=None, embed=self.embed(), view=None)
        except discord.HTTPException:
            pass


def beasts_team_size(tier):
    import beasts
    return beasts.BEAST_TIERS[tier]["team_size"]


# ── Moon Pearl shop and Heavenly Blessings ────────────────────────────

SHOP_ITEMS = {
    # key in economy.PEARL_SHOP: (label, description)
    "heavenly_fate_reroll":   ("🌟 Heavenly Fate Reroll", "Reroll your talent; it never goes lower"),
    "mortal_qi_pill_x3":      ("💊 Mortal Qi Pill ×3", "×1.2 Qi Rate for 4h each"),
    "yellow_qi_pill_x3":      ("💊 Yellow Qi Pill ×3", "×1.4 Qi Rate for 4h each"),
    "mystic_qi_pill_x1":      ("💊 Mystic Qi Pill ×1", "×1.7 Qi Rate for 4h"),
    "inventory_expansion_20": ("🎒 Inventory expansion", "+20 bag slots"),
    "name_change":            ("✏️ Name change", "Change the name on your cards"),
}
SHOP_PILLS = {"mortal_qi_pill_x3": ("Mortal", 3), "yellow_qi_pill_x3": ("Yellow", 3), "mystic_qi_pill_x1": ("Mystic", 1)}


def buy_shop_item(conn, user_id, key, new_name=None, rng=random):
    """Spend Moon Pearls on a shop item. Returns (message, announcement or None)."""
    p = db.get_player(conn, user_id)
    price = economy.PEARL_SHOP[key]
    if p["moon_pearls"] < price:
        return f"You need 🌙 {price:,} Moon Pearls but have 🌙 {p['moon_pearls']:,}.", None
    if key == "name_change" and not (new_name or "").strip():
        return "Please give a name.", None
    # Pay first: the spend fails (and nothing is given) if the pearls are gone by now.
    if db.spend(conn, user_id, "moon_pearls", price, f"Shop: {SHOP_ITEMS[key][0].split(' ', 1)[1]}") is None:
        return f"You need 🌙 {price:,} Moon Pearls but have 🌙 {p['moon_pearls']:,}.", None
    news = None
    if key in SHOP_PILLS:
        grade, qty = SHOP_PILLS[key]
        if not db.add_item(conn, user_id, **dict(loot.pill(grade), qty=qty)):
            db.change_currency(conn, user_id, "moon_pearls", price, "Refund: bag full")
            return "Your bag is full.", None
        msg = f"💊 {qty}× **{grade} Qi Pill** added to your bag."
    elif key == "inventory_expansion_20":
        db.update_player(conn, user_id, bag_capacity=p["bag_capacity"] + 20)
        msg = f"🎒 Your bag now holds **{p['bag_capacity'] + 20}** slots."
    elif key == "name_change":
        new_name = new_name.strip()[:32]
        db.update_player(conn, user_id, name=new_name)
        msg = f"✏️ You are now known as **{new_name}**."
    else:   # heavenly_fate_reroll
        new = rules.reroll_talent(p["talent"], talent_rules.HEAVENLY_FATE_REROLL["can_go_lower"], rng)
        db.update_player(conn, user_id, talent=new)
        msg = (f"🌟 The Aptitude Stone glows... **{new} Talent!**" if new != p["talent"]
               else f"🌟 The stone flickers and settles. You remain **{new}** (it never goes lower).")
        if new != p["talent"]:
            news = loot.talent_announcement(p["name"], new)
    return msg + f"\n🌙 −{price:,} Moon Pearls", news


class NameModal(discord.ui.Modal, title="Change your name"):
    name = discord.ui.TextInput(label="New name", max_length=32, min_length=1)

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction):
        async with self.bot.db_lock:
            msg, _ = buy_shop_item(self.bot.conn, interaction.user.id, "name_change", str(self.name))
        await interaction.response.send_message(msg, ephemeral=True)


def shop_embed(p):
    e = discord.Embed(title="🌙 Moon Pearl Shop", color=COLOR,
                      description=f"Speed and style, never power. You have **🌙 {p['moon_pearls']:,}** Moon Pearls.")
    for key, (label, desc) in SHOP_ITEMS.items():
        e.add_field(name=f"{label} · 🌙 {economy.PEARL_SHOP[key]:,}", value=desc, inline=False)
    lo, hi = economy.PEARL_SHOP["profile_theme"]
    e.add_field(name=f"🖼️ Profile card themes · 🌙 {lo}–{hi}", value="*Coming in a later update.*", inline=False)
    e.set_footer(text="Get Moon Pearls with /recharge or by trading (coming later).")
    return e


class ShopView(OwnedView):
    def __init__(self, bot, owner_id):
        super().__init__(owner_id, timeout=180)
        self.bot = bot
        sel = discord.ui.Select(placeholder="Buy something...", options=[
            discord.SelectOption(label=f"{label} · {economy.PEARL_SHOP[k]:,} pearls"[:100], value=k)
            for k, (label, _) in SHOP_ITEMS.items()])
        sel.callback = self.on_pick
        self.add_item(sel)

    async def on_pick(self, interaction):
        key = interaction.data["values"][0]
        if key == "name_change":
            await interaction.response.send_modal(NameModal(self.bot))
            return
        label = SHOP_ITEMS[key][0]

        async def buy():
            async with self.bot.db_lock:
                msg, news = buy_shop_item(self.bot.conn, self.owner_id, key)
            if news:
                await interaction.channel.send(news)
            return discord.Embed(title=label, description=msg, color=COLOR)

        confirm = ConfirmView(self.owner_id, f"Buy for {economy.PEARL_SHOP[key]:,} pearls", buy,
                              style=discord.ButtonStyle.success, emoji="🌙")
        await interaction.response.send_message(f"Buy **{label}**?", view=confirm, ephemeral=True)


BLESSING_EMOJI = {"Gentle Breeze": "🍃", "Spring Rain": "🌧️", "Bright Moon": "🌕", "Blazing Sun": "☀️",
                  "Rolling Thunder": "⚡", "Starfall": "🌠", "Heavenly Dragon": "🐉", "Eternal Dao": "☯️"}


def buy_blessing(conn, user_id, tier, now=None):
    """Same tier adds 30 days; a different tier replaces the current one with a fresh 30 days."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    price = economy.BLESSING_TIERS[tier]["price"]
    if p["moon_pearls"] < price:
        return f"You need 🌙 {price:,} Moon Pearls but have 🌙 {p['moon_pearls']:,}."
    days = economy.BLESSING_DURATION_DAYS * 86400
    current = rules.active_blessing(p, now)
    if current and current[0] == tier:
        expires = p["blessing_expires"] + days
        msg = f"{BLESSING_EMOJI[tier]} Your **{tier}** blessing is extended by {economy.BLESSING_DURATION_DAYS} days."
    else:
        expires = now + days
        msg = f"{BLESSING_EMOJI[tier]} Heaven smiles on you: **{tier}** for {economy.BLESSING_DURATION_DAYS} days!"
        if current:
            msg += f" (It replaces {current[0]}.)"
    if db.spend(conn, user_id, "moon_pearls", price, f"Blessing: {tier}") is None:
        return f"You need 🌙 {price:,} Moon Pearls but have 🌙 {p['moon_pearls']:,}."
    db.update_player(conn, user_id, blessing_tier=tier, blessing_expires=expires)
    return msg + f"\n🌙 −{price:,} Moon Pearls"


def blessing_embed(p):
    b = rules.active_blessing(p)
    e = discord.Embed(title="☯️ Heavenly Blessings", color=COLOR, description=(
        f"You have **🌙 {p['moon_pearls']:,}** Moon Pearls. "
        + (f"Active: **{b[0]}**, {b[1]} day(s) left." if b else "No active blessing.")
        + "\nBuying the same tier adds 30 days; a different tier replaces yours with a fresh 30 days (no refund)."))
    for tier, t in economy.BLESSING_TIERS.items():
        e.add_field(name=f"{BLESSING_EMOJI[tier]} {tier} · 🌙 {t['price']:,}", value=rules.blessing_perks(tier), inline=False)
    return e


class BlessingView(OwnedView):
    def __init__(self, bot, owner_id):
        super().__init__(owner_id, timeout=180)
        self.bot = bot
        sel = discord.ui.Select(placeholder="Choose a blessing...", options=[
            discord.SelectOption(label=f"{tier} · {t['price']:,} pearls", value=tier, emoji=BLESSING_EMOJI[tier])
            for tier, t in economy.BLESSING_TIERS.items()])
        sel.callback = self.on_pick
        self.add_item(sel)

    async def on_pick(self, interaction):
        tier = interaction.data["values"][0]

        async def buy():
            async with self.bot.db_lock:
                msg = buy_blessing(self.bot.conn, self.owner_id, tier)
            return discord.Embed(title="☯️ Heavenly Blessing", description=msg, color=COLOR)

        confirm = ConfirmView(self.owner_id, f"Buy {tier}", buy, style=discord.ButtonStyle.success, emoji="☯️")
        await interaction.response.send_message(
            f"Buy **{tier}** for 🌙 {economy.BLESSING_TIERS[tier]['price']:,}?", view=confirm, ephemeral=True)
