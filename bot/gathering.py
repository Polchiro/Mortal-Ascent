"""
/gather — collecting herbs for alchemy (docs/alchemy.md, section 2).

One gathering message updates in place: the herb field card (cards/herbfield.py). Each round names the
herb you are looking for and describes it; the numbered choice cards show the plants in front of you,
each drawn and described by its LOOK (alchemy.LOOKS), worded differently from the description. Pick the
one that matches before time runs out. Decoys look almost the same with one detail wrong.

Gathering holds all state and has no Discord code, so it can be tested directly.
GatherView drives it with buttons.
"""
import asyncio
import logging
import random
import time
from dataclasses import dataclass, field

import discord

import alchemy

from . import db, gather_card, gear, loot, materials
from . import player as rules
from .views import COLOR, OwnedView

log = logging.getLogger("mortal-ascent")

TIMER_GRACE_SECONDS = 1.0       # Discord round-trip allowance on timed buttons (same as /train)
SPIRIT_CHECK_SECONDS = 10
IDLE_TIMEOUT = 300              # the gathering message stops after 5 idle minutes

PLACES = [
    "the misty slope", "the riverbank", "the shade of old pines", "a mossy ravine", "the foot of a waterfall",
    "a sunlit meadow", "the ruins of a mountain shrine", "the edge of a bamboo grove",
]
SEARCH_LINES = [
    "You search {place} for **{name}**.",
    "Somewhere in {place} grows **{name}**.",
    "An old herbalist's notes say **{name}** grows in {place}.",
    "You kneel in {place}, looking for **{name}**.",
]
# Wandering Spirit check: (key, emoji, word)
SPIRIT_SIGNS = [("moon", "🌙", "the moon"), ("sun", "☀️", "the sun"), ("star", "⭐", "the star"),
                ("flame", "🔥", "the flame"), ("leaf", "🍃", "the leaf"), ("wave", "🌊", "the wave")]


@dataclass
class Round:
    kind: str                   # "herb" or "spirit"
    prompt: str
    options: list               # [(key, label, emoji)]
    answer: str                 # key of the right option
    seconds: float
    herb: dict = None           # the herb gathered on a right pick
    old: bool = False           # a 100-year+ herb that fights back
    decoys: set = field(default_factory=set)
    names: dict = field(default_factory=dict)   # option key → the plant's name (for its drawing on the card)
    place: str = ""
    shown: str = ""             # the sign the Wandering Spirit asks for (spirit rounds)


class Gathering:
    def __init__(self, conn, user_id, rng=None, now=None):
        self.conn, self.user_id = conn, user_id
        self.rng = rng or random.Random()
        self.started = time.time() if now is None else now
        p = self.player
        self.max_hp = rules.final_stats(p, db.get_techniques(conn, user_id), db.equipped_weapon(conn, user_id),
                                       db.equipped_armor(conn, user_id))[0]
        self.hp = self.max_hp           # HP isn't stored outside fights, so poison only lasts this session
        self.round = None
        self.gathered = []              # herbs gathered this session
        self.reactions = []             # seconds per herb pick, for the review flag
        self.over = False
        if p["spirit_check_in"] is None:          # first gather ever (0 = a check is waiting, even after a restart)
            db.update_player(conn, user_id, spirit_check_in=self.rng.randint(*alchemy.SPIRIT_CHECK_EVERY))

    @property
    def player(self):
        return db.get_player(self.conn, self.user_id)

    # ── rounds ───────────────────────────────────────────────────────

    def next_round(self):
        p = self.player
        if p["spirit_check_in"] <= 0:
            self.round = self._spirit_round()
        else:
            self.round = self._herb_round(p)
        return self.round

    def _herb_round(self, p):
        tier = loot.herb_tier(p["realm"], self.rng)
        type_ = loot.roll_herb_type(self.rng)
        age = loot.roll_age(self.rng, p["herb_streak"], gear.artifact_bonus(p, "old_herb_chance"))   # Gourd
        name, desc = alchemy.HERBS[tier][type_]
        old = age >= alchemy.OLD_HERB_FROM_AGE
        n = alchemy.OLD_HERB_CHOICES if old else alchemy.GATHER_CHOICES
        # the choices show each plant's LOOK (alchemy.LOOKS), never the description you are given
        others = [("decoy", d) for d, _ in alchemy.DECOYS[tier]]
        others += [("plant", alchemy.HERBS[tier][t][0]) for t in alchemy.HERBS[tier] if t != type_]
        self.rng.shuffle(others)
        # always at least one decoy, so every round has a trap to read past
        picked = [o for o in others if o[0] == "decoy"][:1]
        picked += [o for o in others if o not in picked][:n - 1 - len(picked)]
        options = [("herb", name)] + picked
        self.rng.shuffle(options)
        keyed = [(f"o{i}", kind, plant) for i, (kind, plant) in enumerate(options)]
        answer = next(k for k, kind, _ in keyed if kind == "herb")
        seconds = alchemy.GATHER_SECONDS[tier]
        place = self.rng.choice(PLACES)
        prompt = self.rng.choice(SEARCH_LINES).format(place=place, name=name) + f"\n> *{desc}*"
        if old:
            seconds = max(alchemy.OLD_HERB_MIN_SECONDS, seconds - alchemy.OLD_HERB_SECONDS_LESS)
            prompt = (f"✨ *A **{age}-year {name}**! It senses you and begins to sink into the earth...*\n"
                      f"> *{desc}*")
        return Round("herb", prompt, [(k, alchemy.LOOKS[plant], "🌿") for k, _, plant in keyed], answer, seconds,
                     herb=loot.herb(tier, type_, age), old=old,
                     decoys={k for k, kind, _ in keyed if kind == "decoy"},
                     names={k: plant for k, _, plant in keyed}, place=place)

    def _spirit_round(self):
        signs = self.rng.sample(SPIRIT_SIGNS, 4)
        want = self.rng.choice(signs)
        prompt = (f"👻 A **Wandering Spirit** drifts out of the mist and blocks your path.\n"
                  f"*\"Press the button showing {want[2]},\"* it whispers.")
        return Round("spirit", prompt, [(k, "", e) for k, e, _ in signs], want[0], SPIRIT_CHECK_SECONDS,
                     shown=want[2])

    # ── answers ──────────────────────────────────────────────────────

    def answer(self, key, elapsed, now=None):
        """key=None means time ran out. Returns the result text."""
        now = time.time() if now is None else now
        r, self.round = self.round, None
        p = self.player
        slow = key is None or elapsed > r.seconds + TIMER_GRACE_SECONDS
        if r.kind == "spirit":
            return self._spirit_answer(p, not slow and key == r.answer, now)

        fields = {"spirit_check_in": p["spirit_check_in"] - 1}
        if not slow:
            self.reactions.append(elapsed)
        if not slow and key == r.answer:
            stored, _ = loot.store(self.conn, self.user_id, [r.herb])
            fields.update(herb_streak=p["herb_streak"] + 1)
            if stored:
                fields["herbs_gathered"] = p["herbs_gathered"] + 1
                self.gathered.append(r.herb)
                text = f"✅ You gather **{loot.describe(r.herb)}**."
                if r.old:
                    text = f"✨ You pull it free before it escapes: **{loot.describe(r.herb)}**!"
                extra = materials.roll_gather(p["realm"], self.rng)
                if extra:
                    loot.store(self.conn, self.user_id, extra)
                    text += " Nearby you also find " + ", ".join(materials.lines(extra)) + "."
            else:
                text = f"✅ You find **{loot.describe(r.herb)}**, but your bag is full. You leave it behind."
        elif not slow and key in r.decoys:
            lost = max(0, min(self.hp - 1, round(self.max_hp * alchemy.DECOY_HP_LOSS)))
            self.hp -= lost
            fields["herb_streak"] = 0
            text = f"☠️ A poisonous look-alike! Its sap burns your hands (−{lost:,} HP). Nothing gathered."
            if r.old:
                text += f" The **{r.herb['name']}** escapes into the earth."
        elif not slow:
            fields["herb_streak"] = 0
            text = "❌ Not the herb you were looking for. Nothing gathered."
            if r.old:
                text += f" The **{r.herb['name']}** escapes into the earth."
        else:
            fields["herb_streak"] = 0
            text = ("⏳ Too slow! The herb sinks into the earth and escapes." if r.old
                    else "⏳ Too slow! You lose sight of it. Nothing gathered.")
        flag = self._review_flag(p, now)
        if flag:
            fields["gather_flag"] = flag
            log.warning("Gathering flagged for review: user %s: %s", self.user_id, flag)
        db.update_player(self.conn, self.user_id, **fields)
        return text

    def _spirit_answer(self, p, ok, now):
        if ok:
            db.update_player(self.conn, self.user_id, spirit_check_fails=0,
                             spirit_check_in=self.rng.randint(*alchemy.SPIRIT_CHECK_EVERY))
            return "👻 *\"So you are not a puppet,\"* the spirit laughs, and fades away. Gather on."
        fails = p["spirit_check_fails"] + 1
        if fails >= alchemy.SPIRIT_CHECK_FAILS_TO_PAUSE:
            until = now + alchemy.SPIRIT_CHECK_PAUSE_MINUTES * 60
            db.update_player(self.conn, self.user_id, spirit_check_fails=0, gather_paused_until=until,
                             spirit_check_in=self.rng.randint(*alchemy.SPIRIT_CHECK_EVERY))
            self.over = True
            return (f"👻 The spirit shrieks and the mist swallows the path. Gathering is paused for "
                    f"**{alchemy.SPIRIT_CHECK_PAUSE_MINUTES} minutes**.")
        db.update_player(self.conn, self.user_id, spirit_check_fails=fails, spirit_check_in=0)
        left = alchemy.SPIRIT_CHECK_FAILS_TO_PAUSE - fails
        return f"👻 *\"Wrong...\"* The spirit still blocks the way. ({left} more miss{'es' if left > 1 else ''} pauses gathering.)"

    def _review_flag(self, p, now):
        """Flag for an admin to look at (never an automatic ban): inhumanly fast picks, or 12+ hours non-stop."""
        if p.get("gather_flag"):
            return None
        last = self.reactions[-alchemy.FLAG_AVG_OVER_GATHERS:]
        if len(last) >= alchemy.FLAG_AVG_OVER_GATHERS and sum(last) / len(last) < alchemy.FLAG_AVG_REACTION_SECONDS:
            return f"average pick {sum(last) / len(last):.2f}s over {len(last)} gathers"
        if now - self.started >= alchemy.FLAG_CONTINUOUS_HOURS * 3600:
            return f"{alchemy.FLAG_CONTINUOUS_HOURS}+ hours of gathering without a break"
        return None


def streak_text(streak):
    mult = next(m for min_streak, m in alchemy.STREAK_BONUS if streak >= min_streak)
    nxt = next((s for s, _ in reversed(alchemy.STREAK_BONUS) if s > streak), None)
    text = f"🔥 Herbal Insight **{streak}**"
    text += f" · old herbs ×{mult:g}" if mult > 1 else ""
    if nxt:
        text += f" · ×{dict(alchemy.STREAK_BONUS)[nxt]:g} at {nxt}"
    return text


def gather_blocked(p, now=None):
    """Why this player can't gather right now, or None."""
    now = time.time() if now is None else now
    if rules.in_seclusion(p):
        return "🧘 You are in closed-door seclusion. Leave it with **/seclusion** before gathering herbs."
    paused = (p.get("gather_paused_until") or 0) - now
    if paused > 0:
        return f"👻 The Wandering Spirit's mist still hides the herbs. Gather again in **{rules.fmt_duration(paused)}**."
    return None


# ── Discord ───────────────────────────────────────────────────────────

class GatherView(OwnedView):
    """One message, edited every round: the herb field card (cards/herbfield.py) with numbered buttons."""

    def __init__(self, bot, owner_id, rng=None):
        super().__init__(owner_id, timeout=IDLE_TIMEOUT)
        self.bot = bot
        self.g = Gathering(bot.conn, owner_id, rng)
        self.result = None
        self.shown_at = None
        self.timer = None
        self.last = None            # (round, picked key) of the round just answered, for the result card
        self.place = None
        self.g.next_round()
        self.build()

    def embed(self):
        """Text fallback when the card can't be drawn."""
        p = self.g.player
        r = self.g.round
        e = discord.Embed(title="🌿 Gathering Herbs", color=COLOR)
        lines = []
        if self.result:
            lines += [self.result, ""]
        if r:
            lines.append(r.prompt)
            if r.kind == "herb":
                lines.append("")
                lines += [f"**{i + 1}** · {label}" for i, (_, label, _) in enumerate(r.options)]
                lines.append("\nPick the plant that matches the description. Read carefully: "
                             "poisonous look-alikes differ in one detail.")
            e.set_footer(text=f"⏳ {r.seconds:g} seconds to choose")
        elif self.g.over:
            lines.append(self.summary())
        lines.append("")
        lines.append(f"{hp_line(self.g.hp, self.g.max_hp)}  ·  {streak_text(p['herb_streak'])}")
        e.description = "\n".join(lines).strip()
        if not r and not self.g.over:
            e.set_footer(text="Gather as long as you like. The NPC merchant does not buy herbs.")
        return e

    def content(self, deadline=None):
        """The readable text above the card (Discord shows the card small on a computer)."""
        r = self.g.round
        if r and r.kind == "herb":
            text = f"Find the **{r.herb['name']}** before it slips away."
            text += "\n" + "\n".join(f"**{i + 1}** · {label}" for i, (_, label, _) in enumerate(r.options))
        elif r:
            text = "👻 A Wandering Spirit blocks your path. Press the sign it asks for."
        else:
            text = self.result or ""
            if self.g.over:
                text += "\n" + self.summary()
            else:
                text += f"\n{streak_text(self.g.player['herb_streak'])}"
        if r and deadline:
            text += f"\n⏳ Time runs out <t:{int(deadline)}:R>"
        return text.strip()[:1900]

    def summary(self):
        if not self.g.gathered:
            return "You leave the wilds empty-handed."
        counts = {}
        for h in self.g.gathered:
            counts[loot.herb_label(h)] = counts.get(loot.herb_label(h), 0) + 1
        return "**Gathered this trip:**\n" + "\n".join(f"• {k}" + (f" ×{v}" if v > 1 else "") for k, v in counts.items())

    def build(self):
        self.clear_items()
        r = self.g.round
        if r and r.kind == "herb":
            n = len(r.options)
            for i, (key, _, _) in enumerate(r.options):
                self.button(str(i + 1), self.make_pick(key), emoji=_emoji(self.bot, f"gather_{i + 1}"),
                            row=0 if n <= 4 else i // 3)
            self.button("Stop", self.on_stop, emoji=_emoji(self.bot, "gather_stop"), row=0 if n <= 4 else 1)
        elif r:
            for key, _, emoji in r.options:
                self.button(None, self.make_pick(key), emoji=emoji, style=discord.ButtonStyle.secondary, row=0)
        elif not self.g.over:
            self.button("Gather Again", self.on_again, emoji=_emoji(self.bot, "gather_again"),
                        style=discord.ButtonStyle.success)
            self.button("Stop", self.on_stop, emoji=_emoji(self.bot, "gather_stop"))

    # ── the card ─────────────────────────────────────────────────────

    async def card_file(self):
        """The herb field (or the spirit) as a JPEG rendered on the card thread, or None if it can't be drawn."""
        from cards.herbfield import render_field, render_spirit
        from .fight_view import jpg
        from . import render as card_render
        r, result, picked = self.g.round, None, None
        if r is None and self.last:
            (r, picked), result = self.last, self.result
        if r is None:
            return None
        try:
            p = self.g.player
            if r.kind == "spirit":
                data = gather_card.spirit_data(self.g, p, r, result)
                data["place"] = self.place or data["place"]
                img = await card_render.render(render_spirit, data)
            else:
                img = await card_render.render(render_field, gather_card.field_data(self.g, p, r, result, picked))
        except Exception:
            log.exception("Could not render the gather card")
            return None
        return jpg(img, "gather.jpg")

    async def show(self, interaction=None, view=True):
        """Render the card and edit the one gathering message (through the interaction when there is one)."""
        r = self.g.round
        if r and r.kind == "herb":
            self.place = r.place
        if interaction is not None and not interaction.response.is_done():
            await interaction.response.defer()
        file = await self.card_file()
        deadline = time.time() + r.seconds if r else None
        if file:
            kw = dict(content=self.content(deadline), embed=None, attachments=[file], view=self if view else None)
        else:
            kw = dict(content=None, embed=self.embed(), attachments=[], view=self if view else None)
        try:
            if interaction is not None:
                await interaction.edit_original_response(**kw)
                return
        except discord.HTTPException:
            log.warning("Editing the gathering through the interaction failed", exc_info=True)
        if self.message is not None:
            await self.message.edit(**kw)

    async def send(self, interaction):
        """The first message: answer Discord at once, put the card in, then start the round's timer."""
        await interaction.response.defer()
        await self.show(interaction)
        self.message = await interaction.original_response()
        self.start_timer()

    # ── rounds ───────────────────────────────────────────────────────

    def make_pick(self, key):
        async def cb(interaction):
            await self.resolve(key, time.monotonic() - (self.shown_at or time.monotonic()), interaction)
        return cb

    async def resolve(self, key, elapsed, interaction=None):
        """Answer the current round (key None = time ran out) and show the result."""
        r = self.g.round
        if not r:
            return
        if self.timer and interaction is not None:
            self.timer.cancel()
        async with self.bot.db_lock:
            self.result = self.g.answer(key, elapsed)
        self.last = (r, key)
        self.build()
        if self.g.over:
            self.finish()
        await self.show(interaction, view=not self.g.over)

    async def show_round(self, interaction):
        await self.show(interaction)
        self.start_timer()

    def start_timer(self):
        """Call right after the round is on screen: time it, and end it as 'too slow' if nobody picks."""
        self.shown_at = time.monotonic()
        r = self.g.round
        if r is None:
            return

        async def expire():
            await asyncio.sleep(r.seconds + TIMER_GRACE_SECONDS)
            if self.g.round is r and not self._handling:
                self._handling = True
                try:
                    await self.resolve(None, r.seconds + TIMER_GRACE_SECONDS)
                except Exception:
                    log.exception("Gather timeout failed")
                finally:
                    self._handling = False
        self.timer = asyncio.create_task(expire())

    async def on_again(self, interaction):
        p = self.g.player
        why = gather_blocked(p)
        if why:
            self.g.over = True
            self.result = why
            self.last = None
            self.build()
            self.finish()
            await interaction.response.edit_message(content=why + "\n" + self.summary(), embed=None,
                                                    attachments=[], view=None)
            return
        self.result = None
        self.g.next_round()
        self.build()
        await self.show_round(interaction)

    async def on_stop(self, interaction):
        r = self.g.round
        if r is not None:                 # stopping mid-round counts that round as missed, like a timeout
            if self.timer:
                self.timer.cancel()
            async with self.bot.db_lock:
                missed = self.g.answer(None, r.seconds + TIMER_GRACE_SECONDS)
            self.last = (r, None)
            self.result = f"{missed}\n🏮 You shoulder your basket and head home."
        else:
            self.result = (self.result + "\n" if self.result else "") + "🏮 You shoulder your basket and head home."
        self.g.over = True
        self.build()
        self.finish()
        await self.show(interaction, view=False)

    def finish(self):
        self.stop()
        self.bot.busy.discard((self.owner_id, "gather"))

    async def on_timeout(self):
        try:
            r = self.g.round
            if r:
                async with self.bot.db_lock:
                    self.g.answer(None, IDLE_TIMEOUT)
                self.last = (r, None)
            self.g.over = True
            self.result = "🌙 Dusk falls and you head home."
            self.clear_items()
            if self.message:
                await self.show(None, view=False)
        except Exception:
            log.exception("Gather timeout handling failed")
        finally:
            self.bot.busy.discard((self.owner_id, "gather"))


def _emoji(bot, key):
    """A gather button icon: the uploaded application emoji, or a plain emoji."""
    from cards import wild_icons
    em = getattr(bot, "emojis_ma", None)
    return (em.get(key) if em else None) or wild_icons.FALLBACK.get(key)


def hp_line(hp, max_hp):
    return f"❤️ {hp:,}/{max_hp:,} HP"


def register(bot):
    @bot.tree.command(name="gather", description="Gather herbs for alchemy: find the right plant before time runs out")
    async def gather(interaction: discord.Interaction):
        uid = interaction.user.id
        p = db.get_player(bot.conn, uid)
        if not p:
            await interaction.response.send_message(
                "You have not begun your journey yet. Use **/start** to step through the gates of the Jianghu.",
                ephemeral=True)
            return
        why = gather_blocked(p)
        if why:
            await interaction.response.send_message(why, ephemeral=True)
            return
        if (uid, "gather") in bot.busy:
            await interaction.response.send_message("You are already gathering. Use that message, or press Stop.",
                                                    ephemeral=True)
            return
        bot.busy.add((uid, "gather"))
        try:
            view = GatherView(bot, uid)
            await view.send(interaction)
        except Exception:
            bot.busy.discard((uid, "gather"))
            raise
