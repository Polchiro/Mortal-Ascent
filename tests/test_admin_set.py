"""/admin set_realm, set_mastery, set_alchemy, set_blacksmith, set_foraging."""
import asyncio
from types import SimpleNamespace

import pytest

import alchemy
import forge
import technique

from bot import admin, crafting, db, forging
from bot import player as rules
from tests.test_prefix import FakeUser, run


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.create_player(c, 1, "P1", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return c


def test_set_realm_clamps_layer_and_empties_qi(conn):
    db.update_player(conn, 1, qi=50, qi_overflow=20)
    assert admin.set_realm(conn, 1, "Martial King", 7) == 7
    p = db.get_player(conn, 1)
    assert (p["realm"], p["layer"], p["qi"], p["qi_overflow"]) == ("Martial King", 7, 0, 0)
    assert admin.set_realm(conn, 1, "Mortal", 9) == 3


def test_set_mastery_stage_and_full_bar(conn):
    techs = db.get_techniques(conn, 1, equipped_only=False)
    assert len(admin.find_techniques(techs, "all")) == len(techs)
    fist = admin.find_techniques(techs, "iron fist")
    assert [t["name"] for t in fist] == ["Iron Fist"]
    admin.set_mastery(conn, fist, 2)
    t = db.get_technique(conn, 1, fist[0]["id"])
    assert t["stage"] == 2 and rules.stage_of(t) == 2 and not rules.bar_full(t)
    admin.set_mastery(conn, fist, 1, full_bar=True)
    t = db.get_technique(conn, 1, fist[0]["id"])
    assert t["stage"] == 1 and rules.bar_full(t)
    last = len(technique.MASTERY_STAGES) - 1
    admin.set_mastery(conn, fist, last, full_bar=True)            # nothing above the last stage
    t = db.get_technique(conn, 1, fist[0]["id"])
    assert t["stage"] == last and rules.mastery_cap(t) is None


def test_set_crafting_ranks_and_foraging(conn):
    admin.set_alchemy_rank(conn, 1, 5)
    admin.set_blacksmith_rank(conn, 1, 7)
    admin.set_foraging(conn, 1, insight=25, herbs_gathered=300)
    p = db.get_player(conn, 1)
    assert crafting.rank_of(p["alchemy_exp"]) == 5 and forging.rank_of(p["blacksmith_exp"]) == 7
    assert (p["herb_streak"], p["herbs_gathered"]) == (25, 300)


async def _make(cls):
    return cls(":memory:")


def test_set_commands_as_text(monkeypatch):
    from bot.client import MortalAscent
    bot = asyncio.run(_make(MortalAscent))
    user = FakeUser()

    async def app_info():
        return SimpleNamespace(team=None, owner=user)
    monkeypatch.setattr(bot, "application_info", app_info)
    run(bot, "m start", author=user)
    checks = [("m admin set_realm realm:Martial Warrior layer:4", "Martial Warrior, 4th Layer"),
              ("m admin set_mastery stage:Pure Flame technique:Iron Fist", "Iron Fist** → **Pure Flame"),
              ("m admin set_mastery stage:Entering the Hall full_bar:true", "ready for the trial"),
              ("m admin set_alchemy rank:4th Grade", "4th Grade"),
              ("m admin set_blacksmith rank:3rd Grade", "3rd Grade"),
              ("m admin set_foraging insight:50", "Herbal Insight set to **50**")]
    for text, expect in checks:
        _, sent = run(bot, text, author=user)
        assert expect in sent[-1].content, (text, sent[-1].content)
    p = db.get_player(bot.conn, user.id)
    assert p["realm"] == "Martial Warrior" and p["herb_streak"] == 50
    assert crafting.rank_of(p["alchemy_exp"]) == 4

    cmd = bot.tree.get_command("admin").get_command("set_mastery")
    ac = cmd._params["technique"].autocomplete
    got = asyncio.run(ac(SimpleNamespace(namespace=SimpleNamespace(), user=user), ""))
    assert got[0].value == "all" and len(got) <= 25
    for name in ("set_realm", "set_mastery", "set_alchemy", "set_foraging"):
        for p in bot.tree.get_command("admin").get_command(name).parameters:
            assert len(p.choices) <= 25
