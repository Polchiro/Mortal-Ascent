"""
Text commands with the "m" prefix, for when Discord's slash menu is acting up.

Every slash command also works as a normal message:

    m start              m internal qi          m profile @someone
    m train              m practice Iron Fist   m bestiary Martial Warrior
    m index beasts       m admin give @someone lotus_coins:500

The prefix is "m" followed by a space, in any case ("M index" works too).
Options can be given in order, or by name like the slash menu: "m spar technique:Iron Fist".

How it works: the message is turned into a small stand-in for a Discord Interaction, and the
slash command's own code runs with it. So both ways of calling a command always behave the same.
Replies go to the channel as a reply to your message. Buttons and menus under them work as normal.
Messages that would be private ("ephemeral") with a slash command are normal messages here,
because only slash commands can send private replies.
"""
import logging
import re

from . import db, instance

import discord
from discord import app_commands
from discord.enums import AppCommandOptionType as Opt

log = logging.getLogger("mortal-ascent")

PREFIX = "m"
ERROR_MSG = "⚠️ Something went wrong on our side. The error was logged; please try again in a moment."

# Short names for commands people type a lot. Each maps to the full command words.
ALIASES = {
    "qi": "internal qi",
    "cd": "cooldown",
    "lb": "leaderboard",
    "prof": "profession",
    "bal": "balance",
    "inv": "inventory",
    "p": "profile",
    "g": "gather",
    "herbs": "index herbs",
    "pills": "index pills",
}

USER_ID = re.compile(r"^<@!?(\d+)>$|^(\d{15,21})$")


class UsageError(Exception):
    """The text didn't fit the command's options. The message is shown to the player."""


# ── the stand-in Interaction ──────────────────────────────────────────

class _Response:
    def __init__(self, it):
        self._it = it
        self._done = False

    def is_done(self):
        return self._done

    async def send_message(self, content=None, **kwargs):
        self._done = True
        return await self._it._send(content, **kwargs)

    async def defer(self, **kwargs):
        self._done = True
        try:
            await self._it.channel.typing()     # shows "Bot is typing..." while a card renders
        except discord.HTTPException:
            pass

    async def edit_message(self, **kwargs):
        self._done = True
        return await self._it.edit_original_response(**kwargs)

    async def send_modal(self, modal):
        raise UsageError("That window only opens from a slash command or a button.")


class _Followup:
    def __init__(self, it):
        self._it = it

    async def send(self, content=None, **kwargs):
        return await self._it._send(content, **kwargs)


class MessageInteraction:
    """Just enough of discord.Interaction for the command callbacks, backed by a message."""

    def __init__(self, bot, message, command):
        self.client = bot
        self.message = message
        self.user = message.author
        self.channel = message.channel
        self.guild = message.guild
        self.command = command
        self.data = {}
        self.response = _Response(self)
        self.followup = _Followup(self)
        self._original = None

    async def _send(self, content=None, *, ephemeral=False, wait=False, thinking=False, **kwargs):
        kwargs = {k: v for k, v in kwargs.items() if v is not None}
        msg = await self.channel.send(content, reference=self.message, mention_author=False, **kwargs)
        if self._original is None:
            self._original = msg        # like Discord: the first reply is the "original response"
        return msg

    async def original_response(self):
        return self._original

    async def edit_original_response(self, **kwargs):
        if self._original is None:          # after defer(): the first reply carries the new files
            files = kwargs.pop("attachments", None)
            return await self._send(**kwargs, files=files or None)
        return await self._original.edit(**kwargs)

    async def delete_original_response(self):
        if self._original is not None:
            await self._original.delete()


# ── reading the command and its options ───────────────────────────────

def command_table(tree):
    """{"start": cmd, "internal qi": cmd, ...} plus {"internal": group} for every slash command."""
    table = {}
    for cmd in tree.get_commands():
        table[cmd.name] = cmd
        if isinstance(cmd, app_commands.Group):
            for sub in cmd.commands:
                table[f"{cmd.name} {sub.name}"] = sub
    return table


def strip_prefix(content):
    """'m internal qi' -> 'internal qi'. None if the message isn't a prefix command."""
    m = re.match(rf"^\s*{PREFIX}\s+(\S.*)$", content or "", re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def find_command(table, text):
    """Split 'internal qi 5' into (command, 'internal qi', '5'). Returns (None, word, '') if unknown."""
    words = text.split()
    first = words[0].lower()
    if first in ALIASES:
        words = ALIASES[first].split() + words[1:]
        first = words[0]
    cmd = table.get(first)
    if isinstance(cmd, app_commands.Group):
        if len(words) > 1 and f"{first} {words[1].lower()}" in table:
            return table[f"{first} {words[1].lower()}"], f"{first} {words[1].lower()}", " ".join(words[2:])
        return cmd, first, " ".join(words[1:])
    if cmd is None:
        return None, first, ""
    return cmd, first, " ".join(words[1:])


def usage(name, cmd):
    if isinstance(cmd, app_commands.Group):
        return " · ".join(f"`{PREFIX} {name} {sub.name}`" for sub in cmd.commands)
    parts = [f"<{p.name}>" if p.required else f"[{p.name}]" for p in cmd.parameters]
    return f"`{' '.join([PREFIX, name] + parts)}`"


def _match_choice(param, tokens):
    """Longest run of tokens that names one of the param's choices. Returns (Choice, used) or (None, 0)."""
    for n in range(len(tokens), 0, -1):
        said = " ".join(tokens[:n]).lower()
        exact = [c for c in param.choices if said in (c.name.lower(), str(c.value).lower())]
        if exact:
            return exact[0], n
        starts = [c for c in param.choices if c.name.lower().startswith(said)]
        if len(starts) == 1:
            return starts[0], n
    return None, 0


async def _to_user(bot, message, text):
    m = USER_ID.match(text.strip())
    if not m:
        raise UsageError(f"`{text}` isn't a member. Mention them, like @name, or paste their user ID.")
    uid = int(m.group(1) or m.group(2))
    for u in message.mentions:
        if u.id == uid:
            return u
    user = bot.get_user(uid)
    if user is None:
        try:
            user = await bot.fetch_user(uid)
        except discord.HTTPException:
            raise UsageError("I couldn't find that member.") from None
    return user


def _to_number(param, text):
    try:
        value = int(text) if param.type is Opt.integer else float(text)
    except ValueError:
        raise UsageError(f"**{param.name}** must be a number, not `{text}`.") from None
    lo, hi = param.min_value, param.max_value
    if (lo is not None and value < lo) or (hi is not None and value > hi):
        raise UsageError(f"**{param.name}** must be between {lo:g} and {hi:g}.")
    return value


async def convert(bot, message, param, text):
    """Turn the typed text for one option into the value the slash command would get."""
    if param.choices:
        choice, used = _match_choice(param, text.split())
        if not choice or used != len(text.split()):
            names = ", ".join(c.name for c in param.choices)
            raise UsageError(f"**{param.name}** must be one of: {names}.")
        return choice
    if param.type is Opt.user:
        return await _to_user(bot, message, text)
    if param.type in (Opt.integer, Opt.number):
        return _to_number(param, text)
    return text


async def parse_args(bot, message, cmd, text):
    """Read 'name:value' options and positional words into keyword arguments for the callback."""
    params = list(cmd.parameters)
    kwargs = {}
    names = "|".join(re.escape(p.name) for p in params)
    named = re.split(rf"(?:^|\s)({names}):", text, flags=re.IGNORECASE) if names else [text]
    positional = named[0].split()
    for key, value in zip(named[1::2], named[2::2]):
        param = next(p for p in params if p.name.lower() == key.lower())
        kwargs[param.name] = await convert(bot, message, param, value.strip())

    for i, param in enumerate(params):
        if param.name in kwargs:
            continue
        if not positional:
            if param.required:
                raise UsageError(f"Missing **{param.name}**.")
            continue
        token = positional[0]
        if param.choices:
            choice, used = _match_choice(param, positional)
            if choice:
                kwargs[param.name] = choice
                del positional[:used]
            elif param.required:
                await convert(bot, message, param, token)   # raises with the list of choices
        elif param.type is Opt.user:
            if USER_ID.match(token):
                kwargs[param.name] = await _to_user(bot, message, token)
                positional.pop(0)
            elif param.required:
                await _to_user(bot, message, token)
        elif param.type in (Opt.integer, Opt.number):
            if re.fullmatch(r"-?\d+(\.\d+)?", token):
                kwargs[param.name] = _to_number(param, token)
                positional.pop(0)
            elif param.required:
                _to_number(param, token)
        else:
            # Text (a technique name): the last text option takes the rest of the line.
            later_text = any(p.type is Opt.string and not p.choices and p.name not in kwargs
                             for p in params[i + 1:])
            take = 1 if later_text else len(positional)
            kwargs[param.name] = " ".join(positional[:take])
            del positional[:take]
    if positional:
        raise UsageError(f"I didn't understand `{' '.join(positional)}`.")
    return kwargs


# ── help and the message handler ──────────────────────────────────────

def help_embed(table):
    lines = [usage(name, cmd) for name, cmd in table.items()
             if not isinstance(cmd, app_commands.Group) and not name.startswith("admin")]
    e = discord.Embed(title="📜 Commands", color=0x8B5A2B, description=(
        f"Every slash command also works with **`{PREFIX}`** in front, like `{PREFIX} internal qi` or "
        f"`{PREFIX} index`. `<option>` is needed, `[option]` is optional. You can also name an option, "
        f"like `{PREFIX} spar technique:Iron Fist`.\n\n" + "\n".join(lines)))
    e.set_footer(text=f"Shortcuts: " + ", ".join(f"{PREFIX} {k} = {PREFIX} {v}" for k, v in ALIASES.items())
                 + f" · {PREFIX} ping shows which computer the bot runs on")
    return e


async def handle_message(bot, message):
    """Run a prefix command if the message is one. Returns True if it was handled."""
    if message.author.bot:
        return False
    text = strip_prefix(message.content)
    if not text:
        return False
    table = command_table(bot.tree)
    first = text.split()[0].lower()
    if first not in ("help", "ping") and find_command(table, text)[0] is None:
        return False            # "m hello" in a chat: not for us, stay quiet
    # If two copies of the bot share this database, only the first to claim the message answers it.
    if not db.claim_message(bot.conn, message.id):
        log.warning("Another copy of the bot already answered message %s. Only one copy should run! "
                    "Use \"%s ping\" in Discord to see where each copy runs.", message.id, PREFIX)
        return True
    if first == "ping":
        await message.channel.send(f"🏓 Pong from {instance.describe()}\n*Two answers mean two copies of "
                                   "the bot are running; the computer name shows where each one is.*",
                                   reference=message, mention_author=False)
        return True
    if first == "help":
        await message.channel.send(embed=help_embed(table), reference=message, mention_author=False)
        return True
    cmd, name, rest = find_command(table, text)
    if cmd is None:
        return False            # "m hello" in a chat: not for us, stay quiet
    if isinstance(cmd, app_commands.Group):
        await message.channel.send(f"Try {usage(name, cmd)}", reference=message, mention_author=False)
        return True

    interaction = MessageInteraction(bot, message, cmd)
    try:
        kwargs = await parse_args(bot, message, cmd, rest)
        await bot.before_command(interaction)
        await cmd.callback(interaction, **kwargs)
    except UsageError as e:
        await message.channel.send(f"{e}\nUsage: {usage(name, cmd)}", reference=message, mention_author=False)
    except Exception:
        log.exception("%s %s failed", PREFIX, name)
        try:
            await interaction._send(ERROR_MSG)
        except discord.HTTPException:
            log.exception("Could not send the error message")
    return True
