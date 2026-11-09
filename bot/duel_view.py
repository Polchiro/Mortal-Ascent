"""
/duel @player: friendly PvP duels on the fight screen (docs/pvp.md). Numbers: pvp.py.

1. ChallengeView: the challenged player gets Accept / Decline for pvp.ACCEPT_SECONDS. Both see each
   other's realm, layer, equipped techniques and weapon first.
2. DuelView: one card + buttons in the same message, edited every turn, in the channel where /duel
   was used so others can watch. Both players press the same buttons; every press is answered with a
   private (ephemeral) "You chose Guard", and the card only shows "LOCKED IN" until both have picked.
   Then the turn is revealed and resolved (bot/duel.py). 15 seconds per turn, no pick = Guard.
No consequences: HP is back to full afterwards, no injury, no Qi loss, no rewards. Only the win / loss
count (Profile tab) and the duel log (for /admin duelstats) are saved.
"""
import asyncio
import logging
import re
import time

import discord
from discord import app_commands

import pvp

from . import db, gear
from . import duel as duel_rules
from . import player as rules
from . import render as card_render
from .fight_view import LOG_EMOJI, describe, emoji, jpg
from cards.battle import render_duel
from cards.technique_icons import tech_kind
from cards.theme import ELEMENT_ACCENTS

log = logging.getLogger("mortal-ascent")
GRACE_SECONDS = 1.5                    # Discord round-trip allowance before the timer resolves the turn
FIGHT_KINDS = ("explore", "spar", "train", "duel", "hunt")    # bot.busy kinds that count as "in a fight"
COLOR = discord.Color.from_rgb(*ELEMENT_ACCENTS["Duel"].rim)
NOT_STARTED = "You have not begun your journey yet. Use **/start** to step through the gates of the Jianghu."
LOG_EMOJI = dict(LOG_EMOJI, heal="🌿")


def in_fight(bot, uid):
    return any((uid, k) in bot.busy for k in FIGHT_KINDS)


def why_cannot_duel(bot, challenger, target, now=None):
    """None if these two may duel now, else the reason (shown to the challenger)."""
    if target.bot:
        return "Bots don't duel. Challenge another player."
    if target.id == challenger.id:
        return "You can't duel yourself. Find a sparring partner!"
    conn = bot.conn
    me, them = db.get_player(conn, challenger.id), db.get_player(conn, target.id)
    if not me:
        return NOT_STARTED
    if not them:
        return f"**{target.display_name}** has not begun their journey yet (/start)."
    for p, who in ((me, "You are"), (them, f"**{them['name']}** is")):
        if in_fight(bot, p["user_id"]):
            return f"{who} busy in a fight or another duel right now."
        if rules.in_seclusion(p):
            return f"{who} in seclusion."
        hurt = rules.injured_for(p, now)
        if hurt:
            return f"{who} injured for {rules.fmt_duration(hurt)}."
    wait = db.cooldown_left(conn, challenger.id, f"duel:{target.id}", now)
    if wait:
        return f"You two just duelled. Catch your breath: **{rules.fmt_duration(wait)}**."
    return None


def set_pair_cooldown(conn, uid1, uid2, now=None):
    db.set_cooldown(conn, uid1, f"duel:{uid2}", pvp.PAIR_COOLDOWN_SECONDS, now)
    db.set_cooldown(conn, uid2, f"duel:{uid1}", pvp.PAIR_COOLDOWN_SECONDS, now)


# ── the challenge ─────────────────────────────────────────────────────

def loadout_text(conn, player):
    techs = db.get_techniques(conn, player["user_id"])
    weapon = db.equipped_weapon(conn, player["user_id"])
    lines = [f"**{player['realm']}, {rules.ordinal(player['layer'])} layer** · {player['talent']} talent"]
    if techs:
        for t in techs:
            icon = "⚔️" if t["type"] == "attack" else "🛡️"
            lines.append(f"{icon} {t['name']} *({t['grade']})*")
    else:
        lines.append("No techniques equipped")
    if weapon:
        lines.append(f"🗡️ {weapon['name']} · {rules.buff_text(rules.weapon_buffs(weapon))}")
    else:
        lines.append("🗡️ Bare hands")
    armor = db.equipped_armor(conn, player["user_id"])
    if armor:
        lines.append(f"🥋 {armor['name']} · {rules.buff_text(rules.weapon_buffs(armor))}")
    for a in db.equipped_artifacts(conn, player["user_id"]):
        lines.append(f"🔮 {a['name']} · {gear.effect_text(a)}")
    return "\n".join(lines)


def challenge_embed(conn, p1, p2, deadline):
    realm, layer = duel_rules.lower_of(p1, p2)
    e = discord.Embed(
        title="⚔️ A duel challenge!", color=COLOR,
        description=(f"<@{p1['user_id']}> challenges <@{p2['user_id']}> to a **friendly duel**.\n\n"
                     f"**Fair duel:** both fight as **{realm}, {rules.ordinal(layer)} layer**. Weapon, armor and "
                     f"technique buffs count at half, so do combat artifacts; technique effects and mastery count fully. No pills, Flee = forfeit.\n"
                     f"Nothing to win or lose: HP is full again afterwards.\n\n"
                     f"<@{p2['user_id']}>, accept <t:{int(deadline)}:R>?"))
    e.add_field(name=p1["name"], value=loadout_text(conn, p1))
    e.add_field(name=p2["name"], value=loadout_text(conn, p2))
    return e


class ChallengeView(discord.ui.View):
    def __init__(self, bot, challenger, target):
        super().__init__(timeout=pvp.ACCEPT_SECONDS)
        self.bot, self.challenger, self.target = bot, challenger, target
        self.message = None
        self.done = False
        self.deadline = time.time() + pvp.ACCEPT_SECONDS
        for label, cb, style, em in (("Accept", self.on_accept, discord.ButtonStyle.success, "⚔️"),
                                     ("Decline", self.on_decline, discord.ButtonStyle.secondary, "🙇")):
            b = discord.ui.Button(label=label, style=style, emoji=em)
            b.callback = cb
            self.add_item(b)

    async def on_error(self, interaction, error, item):
        log.exception("Duel challenge failed", exc_info=error)
        self._release()
        try:
            if interaction.response.is_done():
                await interaction.followup.send("⚠️ Something went wrong on our side. Please try again.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ Something went wrong on our side. Please try again.",
                                                        ephemeral=True)
        except discord.HTTPException:
            pass

    def _release(self):
        self.bot.busy.discard((self.challenger.id, "duel"))

    async def _close(self, interaction, text):
        self.done = True
        self.stop()
        self._release()
        e = discord.Embed(title="⚔️ Duel challenge", description=text, color=COLOR)
        if interaction is not None:
            await interaction.response.edit_message(content=None, embed=e, view=None)
        elif self.message is not None:
            try:
                await self.message.edit(content=None, embed=e, view=None)
            except discord.HTTPException:
                pass

    async def on_decline(self, interaction):
        uid = interaction.user.id
        if self.done:
            await interaction.response.send_message("This challenge is over.", ephemeral=True)
        elif uid == self.target.id:
            await self._close(interaction, f"🙇 **{self.target.display_name}** declined the duel.")
        elif uid == self.challenger.id:
            await self._close(interaction, f"**{self.challenger.display_name}** withdrew the challenge.")
        else:
            await interaction.response.send_message("This challenge isn't for you.", ephemeral=True)

    async def on_accept(self, interaction):
        if interaction.user.id != self.target.id:
            await interaction.response.send_message(
                "Only the challenged player can accept." if interaction.user.id != self.challenger.id
                else "Wait for them to accept.", ephemeral=True)
            return
        if self.done:
            await interaction.response.send_message("This challenge is over.", ephemeral=True)
            return
        bot = self.bot
        # the challenger's own "duel" mark is this challenge; check everything else again
        bot.busy.discard((self.challenger.id, "duel"))
        why = why_cannot_duel(bot, self.challenger, self.target)
        if why:
            await self._close(interaction, f"The duel can't start: {why}")
            return
        self.done = True                     # no await between the checks and here: a double click can't start two
        self.stop()
        bot.busy.add((self.challenger.id, "duel"))
        bot.busy.add((self.target.id, "duel"))
        await interaction.response.defer()
        try:
            from .sheet.view import fetch_avatar
            async with bot.db_lock:
                conn = bot.conn
                p1, p2 = db.get_player(conn, self.challenger.id), db.get_player(conn, self.target.id)
                d = duel_rules.start(p1, db.get_techniques(conn, p1["user_id"]), db.equipped_weapon(conn, p1["user_id"]),
                                     p2, db.get_techniques(conn, p2["user_id"]), db.equipped_weapon(conn, p2["user_id"]),
                                     armor1=db.equipped_armor(conn, p1["user_id"]),
                                     armor2=db.equipped_armor(conn, p2["user_id"]))
                set_pair_cooldown(conn, p1["user_id"], p2["user_id"])
            avatars = await asyncio.gather(fetch_avatar(self.challenger), fetch_avatar(self.target))
            view = DuelView(bot, d, avatars, getattr(interaction.channel, "id", None))
            view.message = self.message
            await view.start(interaction)
        except Exception:
            bot.busy.discard((self.challenger.id, "duel"))
            bot.busy.discard((self.target.id, "duel"))
            raise

    async def on_timeout(self):
        if self.done:
            return
        await self._close(None, f"⌛ **{self.target.display_name}** didn't answer in time. The challenge has expired.")


# ── the duel ──────────────────────────────────────────────────────────

def tech_text(t):
    """What a technique does in a duel (fight_view.describe without the beast-only parts)."""
    s = describe(t)
    s = re.sub(r"Guard, \+\d+% block vs charged", "Guard", s)
    return (s.replace("its next Guard", "their next Guard")
             .replace("it can't Guard next turn", "their next Guard lets 100% through"))


def _last_text(d):
    if d.last_move is None:
        return None
    return f"{d.last_move} · {d.last_dealt:,} dmg" if d.last_dealt else d.last_move


def move_icon(move):
    """cards.theme.icon kind of a move: the technique's painting, or a plain icon for Strike / Guard / Break."""
    if not move:
        return None
    t = rules.TECH_BY_NAME.get(move)
    if t:
        return tech_kind(move, t.get("school", "Body"))
    return {"Strike": "sword", "Guard": "shield", "Break": "fist"}.get(move, "star")


def hp_change(duel, i):
    """HP side i gained or lost on the last turn (the card's damage number); 0 before the first turn."""
    if not duel.history:
        return 0
    now = duel.history[-1]["moves"][i]["hp_after"]
    before = duel.history[-2]["moves"][i]["hp_after"] if len(duel.history) > 1 else duel.sides[i].max_hp
    return round(now) - round(before)


def duel_card_data(duel, avatars=(None, None)):
    """Plain data for cards.battle.render_duel. Never contains what a player picked this turn."""
    sides = []
    for i, d in enumerate(duel.sides):
        sides.append({"name": d.name, "realm": duel.fair[0] if duel.fair else d.realm,
                      "layer_label": f"{rules.ordinal(duel.fair[1] if duel.fair else d.layer)} layer",
                      "talent": d.talent, "hp": round(d.hp), "max_hp": round(d.max_hp), "locked": duel.locked(d),
                      "last": _last_text(d), "last_icon": move_icon(d.last_move), "avatar_bytes": avatars[i] if i < len(avatars) else None,
                      "winner": duel.over and duel.winner is d, "loser": duel.over and duel.winner is not None
                      and duel.winner is not d, "delta": hp_change(duel, i)})
    data = {"palette": "Duel", "turn": duel.turn, "seconds": pvp.TURN_SECONDS, "intensity": duel.intensity(),
            "fair_label": f"{sides[0]['realm']} · {sides[0]['layer_label'].split()[0]}", "sides": sides}
    reveal = next((t for k, t in duel.log if k == "star"), "")
    rest = [t for k, t in duel.log if t != reveal]
    if duel.turn == 1 and not duel.history and not duel.over:
        data["bottom"] = (reveal, "Both pick in secret. Strike beats Break · Guard beats Strike · Break beats Guard")
    else:
        hits = [f"{d.name} deals {d.last_dealt:,}" for d in duel.sides if d.last_dealt]
        data["bottom"] = (f"Last turn: {reveal}" if reveal else "Last turn",
                          " · ".join(hits) if hits else (rest[0] if rest else ""))
    if duel.over:
        turns = len(duel.history)
        if duel.winner:
            sub = f"{turns} turn{'s' if turns != 1 else ''} · {duel.winner.hp_frac:.0%} HP left"
            if duel.reason in ("forfeit", "timeouts"):
                sub = f"by forfeit · {turns} turn{'s' if turns != 1 else ''}"
            data["result"] = {"title": duel.winner.name, "sub": sub}
        else:
            data["result"] = {"title": "Draw", "draw": True,
                              "sub": f"{turns} turns · {duel.sides[0].hp_frac:.0%} vs {duel.sides[1].hp_frac:.0%} HP"}
    return data


def duel_embed(duel):
    """A short line under the card: who has locked in (it changes before the card is redrawn), the last turn's
    events and the rising intensity. HP, damage, last moves and techniques are on the card and the buttons."""
    lines = []
    if not duel.over:
        lines.append("  ·  ".join(f"**{d.name}** " + ("✅ locked in" if duel.locked(d) else "🤔 choosing")
                                  for d in duel.sides))
    if duel.log and duel.history:
        lines += [""] + [f"{LOG_EMOJI.get(k, '•')} {t}" for k, t in duel.log[-4:]]
    if not duel.over:
        inten = duel.intensity()
        if inten:
            lines += ["", f"🔥 **Rising intensity:** all damage +{inten:.0%} this turn."]
    return discord.Embed(description="\n".join(lines)[:4000], color=COLOR)


def duel_text(duel):
    """Text fallback when the card cannot be rendered."""
    return "\n".join(f"**{d.name}** · {round(d.hp):,}/{round(d.max_hp):,} HP" for d in duel.sides)


class DuelView(discord.ui.View):
    """Both duellists press the buttons on the same message; everyone else can watch."""

    def __init__(self, bot, duel, avatars=(None, None), channel_id=None):
        super().__init__(timeout=900)
        self.bot, self.duel, self.avatars, self.channel_id = bot, duel, avatars, channel_id
        self.message = None
        self.started_at = time.time()
        self._lock = asyncio.Lock()
        self._deadline = 0.0
        self._task = None
        self._ended = False
        for key, label, style, row in (("strike", "Strike", discord.ButtonStyle.primary, 0),
                                       ("guard", "Guard", discord.ButtonStyle.primary, 0),
                                       ("break", "Break", discord.ButtonStyle.primary, 0),
                                       ("attack_tech", "Attack technique", discord.ButtonStyle.success, 1),
                                       ("defense_tech", "Defense technique", discord.ButtonStyle.success, 1),
                                       ("flee", "Flee (forfeit)", discord.ButtonStyle.danger, 2)):
            self._button(key, label, style, row)

    def _button(self, key, label, style, row):
        async def cb(interaction):
            if key == "flee":
                await self.on_flee(interaction)
            else:
                await self.on_pick(interaction, key)
        b = discord.ui.Button(label=label, emoji=emoji(self.bot, key), style=style, row=row)
        b.callback = cb
        self.add_item(b)

    async def interaction_check(self, interaction):
        if self.duel.duelist(interaction.user.id) is None:
            await interaction.response.send_message("You are watching this duel. Challenge someone with **/duel**!",
                                                    ephemeral=True)
            return False
        return True

    async def on_error(self, interaction, error, item):
        log.exception("Duel view failed", exc_info=error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send("⚠️ Something went wrong on our side.", ephemeral=True)
            else:
                await interaction.response.send_message("⚠️ Something went wrong on our side.", ephemeral=True)
        except discord.HTTPException:
            pass

    # ── turns ─────────────────────────────────────────────────────────

    async def start(self, interaction):
        await self.show_turn(interaction)

    def waiting_text(self):
        d = self.duel
        stamp = f"<t:{int(self._deadline)}:R>"
        locked = [x.name for x in d.sides if d.locked(x)]
        choosing = [x.name for x in d.sides if not d.locked(x)]
        return (f"⚔️ **Friendly duel** · both pick in secret · time runs out {stamp}\n"
                + (f"✅ Locked in: {', '.join(locked)}\n" if locked else "")
                + (f"🤔 Choosing: {', '.join(choosing)}" if choosing else ""))

    async def on_pick(self, interaction, key):
        d = self.duel
        if d.over:
            await interaction.response.send_message("This duel is over.", ephemeral=True)
            return
        turn = d.turn
        why = d.choose(interaction.user.id, key)      # no await before this: two quick presses can't both count
        if why:
            await interaction.response.send_message(why, ephemeral=True)
            return
        me = d.duelist(interaction.user.id)
        other = d.other(me)
        both = d.both_picked()
        await interaction.response.send_message(
            f"You chose **{me.move_label(key)}**." + ("" if both else f" Waiting for {other.name}..."), ephemeral=True)
        if both:
            await self.resolve_turn(turn)
        else:
            await self.refresh_locks(turn)

    async def on_flee(self, interaction):
        d = self.duel
        if d.over:
            await interaction.response.send_message("This duel is over.", ephemeral=True)
            return
        d.forfeit(interaction.user.id)
        await interaction.response.send_message("🏃 You fled the duel. It counts as a loss.", ephemeral=True)
        async with self._lock:
            await self.end()

    async def refresh_locks(self, turn):
        """Show "LOCKED IN" on the card for the player who picked (never what they picked)."""
        async with self._lock:
            if self.duel.over or self.duel.turn != turn or self.duel.both_picked():
                return
            file = await self.card_file()
            kw = {"content": self.waiting_text(), "embed": duel_embed(self.duel)}
            if file:
                kw["attachments"] = [file]
            await self.edit(**kw)

    async def resolve_turn(self, turn):
        async with self._lock:
            d = self.duel
            if d.over or d.turn != turn:
                return
            d.resolve()
            if d.over:
                await self.end()
            else:
                await self.show_turn(None)

    async def card_file(self):
        try:
            img = await card_render.render(render_duel, duel_card_data(self.duel, self.avatars))
        except Exception:
            log.exception("Could not render the duel card")
            return None
        return jpg(img, "duel.jpg")

    async def show_turn(self, interaction):
        file = await self.card_file()
        self._deadline = time.time() + pvp.TURN_SECONDS        # the timer starts when the card is shown
        kw = {"content": self.waiting_text(), "view": self, "embed": duel_embed(self.duel)}
        kw["attachments"] = [file] if file else []
        if not file:
            kw["embed"].description = duel_text(self.duel) + "\n\n" + kw["embed"].description
        await self.edit(interaction, **kw)
        self._arm_timer()

    async def edit(self, interaction=None, **kw):
        try:
            if interaction is not None:
                await interaction.edit_original_response(**kw)
                return
        except discord.HTTPException:
            log.warning("Editing the duel through the interaction failed", exc_info=True)
        if self.message is None:
            return
        try:
            await self.message.edit(**kw)
        except discord.HTTPException:        # the interaction token expired: edit through the channel
            ch = getattr(self.message, "channel", None)
            if ch is None:
                raise
            await ch.get_partial_message(self.message.id).edit(**kw)

    def _arm_timer(self):
        self._cancel_timer()
        self._task = asyncio.create_task(self._timer(self.duel.turn))

    def _cancel_timer(self):
        task = self._task
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
        self._task = None

    async def _timer(self, turn):
        try:
            await asyncio.sleep(max(0.0, self._deadline - time.time()) + GRACE_SECONDS)
            await self.resolve_turn(turn)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Duel timer failed")

    # ── the end ───────────────────────────────────────────────────────

    async def end(self):
        """Save the result, free both players and show the final card. Call with self._lock held."""
        if self._ended:
            return
        self._ended = True
        self._cancel_timer()
        self.stop()
        d = self.duel
        a, b = d.sides
        try:
            async with self.bot.db_lock:
                db.save_duel(self.bot.conn, d, self.channel_id, self.started_at)
                set_pair_cooldown(self.bot.conn, a.uid, b.uid)
        finally:
            for x in d.sides:
                self.bot.busy.discard((x.uid, "duel"))
        file = await self.card_file()
        if d.winner:
            head = f"🏆 **{d.winner.name}** wins the duel against **{d.loser().name}**!"
        else:
            head = "🤝 **The duel ends in a draw.**"
        e = duel_embed(d)
        e.description = head + "\n" + e.description + "\n\n*A friendly duel: HP is full again, nothing was won or lost.*"
        kw = {"content": None, "embed": e, "view": None, "attachments": [file] if file else []}
        await self.edit(None, **kw)

    async def on_timeout(self):
        """Safety net (the turn timer normally ends an idle duel first)."""
        if not self._ended and not self.duel.over:
            async with self._lock:
                self.duel.decide_on_time()
                await self.end()


# ── /duel ─────────────────────────────────────────────────────────────

def register(bot):
    @bot.tree.command(name="duel", description="Challenge a player to a friendly, fair PvP duel (no rewards, no risk)")
    @app_commands.describe(opponent="The player you challenge")
    async def duel_cmd(interaction: discord.Interaction, opponent: discord.User):
        if interaction.guild is None:
            await interaction.response.send_message(
                "Duels happen in a server channel, so others can watch. Use **/duel** there.", ephemeral=True)
            return
        uid = interaction.user.id
        why = why_cannot_duel(bot, interaction.user, opponent)
        if why:
            await interaction.response.send_message(why, ephemeral=True)
            return
        if (uid, "duel") in bot.busy:
            await interaction.response.send_message("You already have a duel or challenge going.", ephemeral=True)
            return
        bot.busy.add((uid, "duel"))           # this challenge (no await since the checks)
        try:
            p1, p2 = db.get_player(bot.conn, uid), db.get_player(bot.conn, opponent.id)
            view = ChallengeView(bot, interaction.user, opponent)
            await interaction.response.send_message(content=opponent.mention,
                                                    embed=challenge_embed(bot.conn, p1, p2, view.deadline), view=view,
                                                    allowed_mentions=discord.AllowedMentions(users=[opponent]))
            view.message = await interaction.original_response()
        except Exception:
            bot.busy.discard((uid, "duel"))
            raise
