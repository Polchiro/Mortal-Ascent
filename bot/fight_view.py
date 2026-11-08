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
from cards.beast_fight import render_beast_fight as render_battle   # the encounter screen (cards/beast_fight.py)
from cards.technique_icons import tech_kind

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


def enemy_seal(e, realm):
    """The beast nameplate: its realm's emblem with its element badge in the corner (cards/emblems.py).
    Bandits and unknown beasts use the realm of the fight."""
    import beasts
    if e["kind"] == "master":
        return "school:Body"
    beast_realm = next((r for r, rows in beasts.BEASTS.items() if any(row[0] == e["name"] for row in rows)), realm)
    return f"emblem:beast:{beast_realm}:{e['element']}"


def _school(tech):
    from . import player as rules
    return rules.TECH_BY_NAME.get(tech["name"], {}).get("school", "Body")


def describe(tech):
    """Short plain-words effect of a technique for the card: damage multiplier and its special effect."""
    from . import player as rules
    eff = rules.TECH_BY_NAME.get(tech["name"], {}).get("effect")
    if tech["type"] == "attack":
        base = f"Strike ×{technique.ATTACK_TECHNIQUE[tech['grade']][0] * rules.mastery_mult(tech):.2f} damage"
    else:
        block = technique.DEFENSE_TECHNIQUE[tech["grade"]][0] * rules.mastery_mult(tech)
        base = f"Guard, +{block:.0%} block vs charged"
    kind, val = eff or (None, None)
    extra = {"combo": lambda: f"{val[0]} hits of {val[1]:.0%}" if val else "",
             "pierce": lambda: f"ignores {val:.0%} defense",
             "heavy": lambda: f"×{val:g} heavier, rests longer",
             "stagger": lambda: "it can't Guard next turn" if val >= 1 else f"its next Guard lets {val:.0%} through",
             "counter": lambda: f"reflects {val:.0%} of blocked dmg",
             "recover": lambda: f"heals {val:.0%} HP on a block",
             "unbreakable": lambda: "Break hits you for half",
             "evade": lambda: f"{val:.0%} chance to dodge a Break"}.get(kind)
    return base + (f" · {extra()}" if extra else "")


def snapshot(b):
    """HP now, to show next turn how much each side lost or gained (the card's damage numbers)."""
    return {"enemy": round(b.enemy["hp"]), "party": {f.uid: round(f.hp) for f in b.fighters}}


def short_effect(tech):
    """A technique's power in a few characters, under its name on the card."""
    from . import player as rules
    if tech["type"] == "attack":
        return f"×{technique.ATTACK_TECHNIQUE[tech['grade']][0] * rules.mastery_mult(tech):.2f} damage"
    block = technique.DEFENSE_TECHNIQUE[tech["grade"]][0] * rules.mastery_mult(tech)
    return f"+{block:.0%} block"


def card_data(b, header, prev=None):
    """Plain data for cards.battle.render_battle. `prev` (snapshot() of the turn before) adds damage numbers."""
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
                      "move": move, "arrow": f is target and not b.over, "ko": f.hp <= 0,
                      "delta": round(f.hp) - prev["party"][f.uid] if prev and f.uid in prev["party"] else 0})
    loadout = []
    if not b.team:
        f = b.fighters[0]
        for key in ("attack_tech", "defense_tech"):
            t = f.tech(key)
            if not t:
                continue
            left = f.cooldowns[key]
            school = _school(t)
            loadout.append({"name": t["name"], "seal": tech_kind(t["name"], school), "color": SCHOOL_COLOR.get(school),
                            "ready": not left, "state": "Ready" if not left else f"{left} turn{'s' if left > 1 else ''}",
                            "desc": describe(t), "short": short_effect(t)})
        n = f.pill_count()
        loadout.append({"name": f.pills[0]["name"] if f.pills else "Mending Pill",
                        "seal": f"emblem:pill:mending:{f.pills[0].get('grade', 'Mortal')}" if f.pills
                        else "emblem:pill:mending:Mortal", "color": (82, 186, 120),
                        "ready": f.can_pill(),
                        "state": (f"×{n} in bag" if f.pills_used < rules_data.PILLS_PER_FIGHT else "used up") if n else "none",
                        "desc": (f"Heals {f.pills[0]['heal']:.0%} HP · uses your turn · max "
                                 f"{rules_data.PILLS_PER_FIGHT} per fight") if f.pills else "Craft them with /craft",
                        "short": f"Heals {f.pills[0]['heal']:.0%} HP" if f.pills else "Craft with /craft"})
    intent = getattr(b, "intent", None) or {}
    danger = intent.get("kind") if intent.get("kind") in ("charged", "signature") and not b.over else None
    return {"palette": palette, "header": header, "turn": b.turn, "seconds": rules_data.TURN_SECONDS,
            "result": b.result,
            "enemy": {"name": e["name"], "seal": enemy_seal(e, b.fighters[0].realm), "tags": [t for t in tags if t],
                      "hp": round(e["hp"]), "max_hp": round(e["max_hp"]),
                      "element_seal": "school:Palm" if e["kind"] == "master" else "emblem:element:" + e["element"],
                      "statuses": b.status_chips(), "body": e["body"], "slug": e.get("slug"),
                      "delta": round(e["hp"]) - prev["enemy"] if prev else 0,
                      "atk": round(e.get("attack", 0)), "def": round(e.get("defense", 0))},
            "danger": danger, "scene": getattr(b, "scene", None),
            "party_title": "Hunting party" if b.team else "You", "party": party, "loadout": loadout,
            "log": list(b.log), "warning": b.warning or ("", "")}


LOG_EMOJI = {"sword": "⚔️", "shield": "🛡️", "fist": "💥", "skull": "💀", "star": "✨", "pill": "💊", "flee": "🏃",
             "hourglass": "⏳", "flame": "🔥", "herb": "🌿"}


def _hp(x):
    return x.get("bar_label") or f"{x['hp']:,} / {x['max_hp']:,} HP"


def card_embed(data):
    """No text box under the fight card any more: the card carries HP, damage, the log, the techniques and the
    warning in large type. Kept so callers can pass embed=card_embed(data) (None removes the old embed);
    details_embed() still builds the long text for the text-only fallback."""
    return None


def details_embed(data):
    """The long text version of a turn (HP, the last turn, the warning, each technique). Takes render_battle's data."""
    from cards.theme import ELEMENT_ACCENTS
    e, party = data["enemy"], data["party"]
    team = len(party) > 1
    lines = [f"**{e['name']}** · {_hp(e)}" + (f" · *{', '.join(e['statuses'])}*" if e.get("statuses") else "")]
    for m in party:
        mark = "▶ " if team and m.get("arrow") else ""
        move = m.get("move") if team and m.get("move") else ""
        lines.append(f"{mark}**{m['name']}** · {_hp(m)}" + (f" · {move}" if move else ""))
    log_ = data.get("log") or []
    if log_:
        lines += ["", f"**{data.get('log_title', 'Last turn')}**"]
        lines += [f"{LOG_EMOJI.get(kind, '•')} {text}" for kind, text in log_[-8:]]
    head, hint = data.get("warning") or ("", "")
    if head and not data.get("result"):
        lines += ["", f"⚠️ **{head}**" + (f"\n{hint}" if hint else "")]
    moves = [i for i in data.get("loadout", []) if i.get("desc")]
    if moves and not data.get("result"):
        lines += ["", "**Your moves**"]
        for i in moves:
            mark = "✅" if i["ready"] else "⏳"
            lines.append(f"{mark} **{i['name']}** ({i['state']}): {i['desc']}")
    acc = ELEMENT_ACCENTS.get(data["palette"])
    return discord.Embed(description="\n".join(lines)[:4000],
                         color=discord.Color.from_rgb(*acc.rim) if acc else None)


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
                                   1, disabled=bool(left) or stunned, icon=battle_icons.tech_emoji_key(t["name"]))
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

    _prev_hp = None

    def turn_data(self):
        """The card's data for the current turn, with the damage since the last card; then remember this turn."""
        data = card_data(self.fight, self.fight_header, self._prev_hp)
        self._prev_hp = snapshot(self.fight)
        return data

    async def start_fight(self, interaction, battle, header):
        """Show the fight in this view's message. `interaction` may already be deferred, or None."""
        self.fight, self.fight_header = battle, header
        self._prev_hp = snapshot(battle)
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

    async def fight_card_file(self, filename="fight.jpg", data=None):
        """The current card as a JPEG: about a third of the PNG size, so the turn-by-turn edits upload faster."""
        try:
            img = await card_render.render(render_battle, data or self.turn_data())
        except Exception:
            log.exception("Could not render the fight card")
            return None
        return jpg(img, filename)

    async def _show_turn(self, interaction):
        self._deadline = time.time() + rules_data.TURN_SECONDS
        self.clear_items()
        self.fight_buttons()
        data = self.turn_data()
        file = await self.fight_card_file(data=data)
        self._deadline = time.time() + rules_data.TURN_SECONDS     # the timer starts when the card is shown
        kw = {"content": self.waiting_text(), "view": self}
        if file:
            kw.update(attachments=[file], embed=card_embed(data))     # the card, then the readable details
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
