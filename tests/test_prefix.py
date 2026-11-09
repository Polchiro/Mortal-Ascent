"""The "m" text commands: parsing, and running real commands through the message stand-in."""
import asyncio

import pytest

from bot import prefix


class FakeMessage:
    def __init__(self, channel, content=None, **kw):
        self.channel, self.content, self.kw = channel, content, kw
        self.edits = []

    async def edit(self, **kw):
        self.edits.append(kw)
        return self


class FakeChannel:
    def __init__(self):
        self.sent = []

    async def send(self, content=None, **kw):
        msg = FakeMessage(self, content, **kw)
        self.sent.append(msg)
        return msg

    def typing(self):
        async def nothing():
            return None
        return nothing()


class FakeUser:
    bot = False

    def __init__(self, uid=111111111111111111, name="Lin"):
        self.id, self.display_name, self.name = uid, name, name
        self.mention = f"<@{uid}>"


class FakeInput:
    next_id = 1000

    def __init__(self, content, author=None, guild=None):
        FakeInput.next_id += 1
        self.id = FakeInput.next_id
        self.content, self.author, self.guild = content, author or FakeUser(), guild
        self.channel, self.mentions = FakeChannel(), []


@pytest.fixture
def bot():
    from bot.client import MortalAscent

    async def make():
        return MortalAscent(":memory:")
    return asyncio.run(make())


def run(bot, content, **kw):
    msg = FakeInput(content, **kw)
    handled = asyncio.run(prefix.handle_message(bot, msg))
    return handled, msg.channel.sent


def test_strip_prefix():
    assert prefix.strip_prefix("m internal qi") == "internal qi"
    assert prefix.strip_prefix("M   Index ") == "Index"
    assert prefix.strip_prefix("mindex") is None
    assert prefix.strip_prefix("hello m start") is None


def test_every_slash_command_is_reachable(bot):
    table = prefix.command_table(bot.tree)
    for name in ("start", "profile", "internal qi", "index", "cooldown", "admin reset", "admin give", "tutorial"):
        cmd, found, _ = prefix.find_command(table, name.upper())
        assert found == name and cmd is table[name]
    assert prefix.find_command(table, "qi")[1] == "internal qi"
    assert prefix.find_command(table, "hello there")[0] is None


def test_parse_choices_numbers_and_text(bot):
    table = prefix.command_table(bot.tree)

    def parse(text):
        cmd, _, rest = prefix.find_command(table, text)
        return asyncio.run(prefix.parse_args(bot, None, cmd, rest))

    kw = parse("index techniques")
    assert kw["section"].value == "techniques" and "realm" not in kw
    kw = parse("index beasts martial warrior")
    assert kw["section"].value == "beasts" and kw["realm"].value == "Martial Warrior"
    assert parse("bestiary mortal")["realm"].value == "Mortal"
    assert parse("practice Iron Fist") == {"technique": "Iron Fist"}
    assert parse("spar technique:Iron Fist") == {"technique": "Iron Fist"}
    assert parse("admin give qi:500 lotus_coins:20") == {"qi": 500, "lotus_coins": 20}
    assert parse("index dragons") == {"search": "dragons"}             # free text searches the Compendium
    with pytest.raises(prefix.UsageError):
        parse("practice")


def test_commands_run_from_a_message(bot):
    handled, sent = run(bot, "m cooldown")
    assert handled and "/start" in sent[0].content            # not started yet
    handled, sent = run(bot, "M START")
    assert handled and sent[0].kw["embed"].title.startswith("🏮")
    handled, sent = run(bot, "m cd")
    assert "Incense Clock" in sent[0].kw["embed"].title
    handled, sent = run(bot, "m internal qi")
    assert sent[0].kw["file"].filename == "qi.png"
    handled, sent = run(bot, "m index pills")
    assert sent[0].kw["view"] is not None
    handled, sent = run(bot, "m gather")
    assert sent[0].kw["files"][0].filename == "gather.jpg" and sent[0].kw["view"] is not None
    handled, sent = run(bot, "m craft")
    assert "Alchemy Cauldron" in sent[0].kw["embed"].title and sent[0].kw["view"] is not None
    handled, sent = run(bot, "m herbs")
    assert "How to /gather" in sent[0].kw["embed"].description and sent[0].kw["file"].filename == "compendium.png"
    handled, sent = run(bot, "m pills")
    assert "Pills · Overview" in sent[0].kw["embed"].description
    handled, sent = run(bot, "m help")
    assert "m gather" in sent[0].kw["embed"].description and "m craft" in sent[0].kw["embed"].description
    handled, sent = run(bot, "m seclusion 12")                 # removed command: stays quiet
    assert not handled and not sent
    handled, sent = run(bot, "m internal")
    assert "m internal qi" in sent[0].content
    handled, sent = run(bot, "m help")
    assert "m internal qi" in sent[0].kw["embed"].description


def test_chat_is_ignored(bot):
    assert run(bot, "m hello everyone") == (False, [])
    assert run(bot, "just chatting") == (False, [])
    bot_author = FakeUser()
    bot_author.bot = True
    assert run(bot, "m start", author=bot_author) == (False, [])


def test_each_message_is_answered_once(bot):
    msg = FakeInput("m cooldown")
    assert asyncio.run(prefix.handle_message(bot, msg))
    assert asyncio.run(prefix.handle_message(bot, msg))     # a second copy of the bot sees it too
    assert len(msg.channel.sent) == 1


def test_ping_names_this_copy(bot):
    handled, sent = run(bot, "m ping")
    assert handled and "Pong" in sent[0].content and "process" in sent[0].content
