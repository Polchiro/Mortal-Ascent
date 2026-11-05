"""
The fight screen on Discord: one card + buttons in a single message that is edited every turn
(docs/combat.md). FightMixin is shared by the /explore view and the team hunt view.

Buttons:  row 1  Strike · Guard · Break
          row 2  your equipped techniques (greyed out with the turns left while they rest)
          row 3  Mending pill · Flee
Each turn has a 15-second timer: no pick = Guard, three timeouts in a row = flee.
In team hunts every member picks secretly; the turn resolves when all have picked or time is up.
"""
import asyncio
import io
import logging
import time

import discord

import battle as rules_data
import technique

from . import mastery
from . import render as card_render
from .fight import Battle
from cards import battle_icons
from cards.battle import render_battle, seal_char
from cards.theme import SCHOOL_CHAR

log = logging.getLogger("mortal-ascent")
GRACE_SECONDS = 1.5          # Discord round-trip allowance before the timer resolves the turn
TIER_LABEL = {"normal": "Normal", "elite": "Elite", "beast_king": "Beast King", "bandit": "Bandits"}
SCHOOL_COLOR = {"Fist": (226, 84, 72), "Palm": (110, 150, 232), "Finger": (196, 110, 228), "Leg": (232, 160, 62),
                "Body": (96, 196, 160)}


def jpg(image, filename):
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=88)
    buf.seek(0)
    return discord.File(buf, filename=filename)


def emoji(bot, key):
    em = getattr(bot, "emojis_ma", None)
    return em.get(key) if em else battle_icons.FALLBACK.get(key)


def _school(tech):
    from . import player as rules
    return rules.TECH_BY_NAME.get(tech["name"], {}).get("school", "Body")


def card_data(b, header):
    """Plain data for cards.battle.render_battle."""
    e = b.enemy
    tags = [TIER_LABEL[e["tier"]]]
    if e["kind"] == "beast":
        tags += [e["role"].title(), e["element"]]
    tags.append(e.get("realm", ""))
    palette = "Master" if e["kind"] == "master" else e["element"]
    party = []
    target = b.target()
    for f in b.fighters:
        if f.fled:
            move = "Fled"
        elif f.hp <= 0:
            move = "Knocked out"
        else:
            move = f.last_move or "Waiting..."
        party.append({"name": f.name, "realm": f.realm, "layer": f.layer, "hp": round(f.hp), "max_hp": round(f.max_hp),
                      "move": move, "arrow": f is target and not b.over, "ko": f.hp <= 0})
    loadout = []
    if not b.team:
        f = b.fighters[0]
        for key in ("attack_tech", "defense_tech"):
            t = f.tech(key)
            if not t:
                continue
            left = f.cooldowns[key]
            school = _school(t)
            loadout.append({"name": t["name"], "seal": SCHOOL_CHAR.get(school, "武"), "color": SCHOOL_COLOR.get(school),
                            "ready": not left, "state": "Ready" if not left else f"{left} turn{'s' if left > 1 else ''}"})
        n = f.pill_count()
        loadout.append({"name": f.pills[0]["name"] if f.pills else "Mending Pill", "seal": "丹", "color": (82, 186, 120),
                        "ready": f.can_pill(),
                        "state": (f"×{n} in bag" if f.pills_used < rules_data.PILLS_PER_FIGHT else "used up") if n else "none"})
    return {"palette": palette, "header": header, "turn": b.turn, "seconds": rules_data.TURN_SECONDS,
            "result": b.result,
            "enemy": {"name": e["name"], "seal": seal_char(e["name"], e["body"]), "tags": [t for t in tags if t],
                      "hp": round(e["hp"]), "max_hp": round(e["max_hp"]),
                      "element_seal": "师" if e["kind"] == "master" else rules_data.ELEMENTS[e["element"]]["seal"],
                      "statuses": b.status_chips(), "body": e["body"], "slug": e.get("slug")},
            "party_title": "Hunting party" if b.team else "You", "party": party, "loadout": loadout,
            "log": list(b.log), "warning": b.warning or ("", "")}


def fight_text(b):
    """Text fallback when the card cannot be rendered."""
    e = b.enemy
    lines = [f"**{e['name']}** · {round(e['hp']):,}/{round(e['max_hp']):,} HP"]
    lines += [f"• {f.name}: {round(f.hp):,}/{round(f.max_hp):,} HP" for f in b.fighters]
    lines += [""] + [t for _, t in b.log]
    if b.warning and not b.over:
        lines += ["", f"⚠️ **{b.warning[0]}** {b.warning[1]}"]
    return "\n".join(lines)


def give_mastery(conn, f):
    """+COMBAT_EXP_PER_USE mastery EXP per technique use. Returns trial notes."""
    notes = []
    by_id = {t["id"]: t for t in f.techs}
    for tid, uses in Battle.mastery_uses(f).items():
        _, note = mastery.gain(conn, f.player, by_id[tid], uses * technique.COMBAT_EXP_PER_USE)
        if note:
            notes.append(note)
    return notes


class FightMixin:
    """Mixed into an OwnedView. The host sets self.bot and implements on_fight_end(interaction)."""

    fight = None
    fight_header = ""
    _turn_task = None
    _deadline = 0.0
    _turn_lock = None

    # ── buttons ───────────────────────────────────────────────────────

    def fight_buttons(self):
        b = self.fight
        team = b.team
        solo = b.fighters[0] if not team else None
        stunned = bool(solo and solo.stunned)
        for key in ("strike", "guard", "break"):
            self._fight_button(key.title(), key, discord.ButtonStyle.primary, 0,
                               disabled=stunned and key != "guard")
        for key in ("attack_tech", "defense_tech"):
            if solo:
                t = solo.tech(key)
                if not t:
                    continue
                left = solo.cooldowns[key]
                label = t["name"][:60] + (f" (⏳ {left})" if left else "")
                self._fight_button(label, key, discord.ButtonStyle.secondary if left else discord.ButtonStyle.success,
                                   1, disabled=bool(left) or stunned, icon=_school(t).lower())
            else:
                self._fight_button("Attack technique" if key == "attack_tech" else "Defense technique", key,
                                   discord.ButtonStyle.success, 1)
        if solo:
            n = solo.pill_count()
            self._fight_button(f"Mending pill ×{n}" if n else "No Mending pills", "pill", discord.ButtonStyle.secondary, 2,
                               disabled=not solo.can_pill() or stunned)
        else:
            self._fight_button("Mending pill", "pill", discord.ButtonStyle.secondary, 2)
        self._fight_button("Flee", "flee", discord.ButtonStyle.danger, 2, disabled=stunned)

    def _fight_button(self, label, key, style, row, disabled=False, icon=None):
        async def cb(interaction):
            await self.fight_click(interaction, key)
        b = discord.ui.Button(label=label, emoji=emoji(self.bot, icon or key), style=style, row=row, disabled=disabled)
        b.callback = cb
        b.fight_key = key
        self.add_item(b)

    # ── turns ─────────────────────────────────────────────────────────

    async def start_fight(self, interaction, battle, header):
        """Show the fight in this view's message. `interaction` may already be deferred, or None."""
        self.fight, self.fight_header = battle, header
        self._turn_lock = asyncio.Lock()
        if interaction and not interaction.response.is_done():
            await interaction.response.defer()
        await self._show_turn(interaction)

    def waiting_text(self):
        b = self.fight
        stamp = f"<t:{int(self._deadline)}:R>"
        if not b.team:
            return f"⏳ Pick your move · time runs out {stamp}"
        ready = [f.name for f in b.active() if f.pick]
        waiting = [f.name for f in b.waiting_for()]
        return (f"⏳ Everyone picks secretly · time runs out {stamp}\n"
                + (f"✅ Ready: {', '.join(ready)}\n" if ready else "")
                + (f"🤔 Waiting for: {', '.join(waiting)}" if waiting else ""))

    async def fight_click(self, interaction, choice):
        b = self.fight
        if b is None or b.over:
            await interaction.response.send_message("This fight is over.", ephemeral=True)
            return
        turn = b.turn
        why = b.choose(interaction.user.id, choice)
        if why:
            await interaction.response.send_message(why, ephemeral=True)
            return
        if b.all_picked():
            await interaction.response.defer()
            await self.resolve_turn(turn, interaction)
            return
        # team hunt: keep the pick secret, show who is still choosing
        f = b.fighter(interaction.user.id)
        await interaction.response.edit_message(content=self.waiting_text())
        await interaction.followup.send(f"You chose **{f.move_label(choice)}**. Waiting for the others...", ephemeral=True)

    async def resolve_turn(self, turn, interaction=None):
        async with self._turn_lock:
            b = self.fight
            if b is None or b.over or b.turn != turn:
                return
            from . import crafting     # here: crafting imports the views, which import this module
            async with self.bot.db_lock:
                b.resolve()
                for f in b.fighters:
                    crafting.bank_fight_pills(self.bot.conn, f)
            if b.over:
                self._cancel_timer()
                await self.on_fight_end(interaction)
            else:
                await self._show_turn(interaction)

    async def fight_card_file(self, filename="fight.jpg"):
        """The current card as a JPEG: about a third of the PNG size, so the turn-by-turn edits upload faster."""
        try:
            img = await card_render.render(render_battle, card_data(self.fight, self.fight_header))
        except Exception:
            log.exception("Could not render the fight card")
            return None
        return jpg(img, filename)

    async def _show_turn(self, interaction):
        self._deadline = time.time() + rules_data.TURN_SECONDS
        self.clear_items()
        self.fight_buttons()
        file = await self.fight_card_file()
        self._deadline = time.time() + rules_data.TURN_SECONDS     # the timer starts when the card is shown
        kw = {"content": self.waiting_text(), "view": self}
        if file:
            kw.update(attachments=[file], embed=None)
        else:
            kw.update(attachments=[], embed=discord.Embed(title=self.fight_header, description=fight_text(self.fight)))
        await self.edit_fight_message(interaction, **kw)
        self._arm_timer()

    async def edit_fight_message(self, interaction, **kw):
        try:
            if interaction is not None:
                await interaction.edit_original_response(**kw)
                return
        except discord.HTTPException:
            log.warning("Editing through the interaction failed; editing the message instead", exc_info=True)
        if self.message is not None:
            try:
                await self.message.edit(**kw)
            except discord.HTTPException:   # interaction token expired (15 min): edit through the channel
                ch = getattr(self.message, "channel", None)
                if ch is None:
                    raise
                await ch.get_partial_message(self.message.id).edit(**kw)

    def _arm_timer(self):
        self._cancel_timer()
        turn = self.fight.turn
        self._turn_task = asyncio.create_task(self._timer(turn))

    def _cancel_timer(self):
        task = self._turn_task
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
        self._turn_task = None

    async def _timer(self, turn):
        try:
            await asyncio.sleep(max(0.0, self._deadline - time.time()) + GRACE_SECONDS)
            await self.resolve_turn(turn, None)
        except asyncio.CancelledError:
            pass
        except Exception:
            log.exception("Fight timer failed")

    def stop_fight(self):
        self._cancel_timer()

    async def on_fight_end(self, interaction):     # pragma: no cover - the host overrides it
        raise NotImplementedError
