"""/admin item: every item in the game can be given, and the list comes from the data modules."""
import asyncio
from types import SimpleNamespace

import pytest

import alchemy
import equipments
import forge
import technique

from bot import admin, crafting, db, item_catalog, loot, materials
from bot import player as rules
from tests.test_prefix import FakeUser, run


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.create_player(c, 1, "P1", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, 1, bag_capacity=10_000)
    return c


def test_catalog_reads_every_data_module():
    kinds = {}
    for e in item_catalog.CATALOG.values():
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    tiers = len(equipments.TIERS)
    assert kinds["weapon"] == tiers * len(equipments.WEAPON_TYPES)
    assert kinds["armor"] == tiers * len(equipments.ARMOR_TYPES)
    assert kinds["artifact"] == tiers * len(equipments.ARTIFACT_FAMILIES)
    assert kinds["material"] == len(forge.all_materials())
    assert kinds["herb"] == sum(len(t) for t in alchemy.HERBS.values())
    assert kinds["pill"] == sum(len(k[2]) for k in crafting.KINDS.values()) + 1    # + Heaven-Defying
    assert kinds["manual"] == len(technique.TECHNIQUES)
    assert kinds["chest"] == len(loot.CHEST_ORDER)
    labels = [e["label"].lower() for e in item_catalog.CATALOG.values()]
    assert len(set(labels)) == len(labels) and max(map(len, labels)) <= 100      # Discord's choice limit


@pytest.mark.parametrize("entry_id", list(item_catalog.CATALOG))
def test_every_item_can_be_given(conn, entry_id):
    stored, lost = admin.give_item(conn, 1, entry_id, 2)
    assert stored and not lost
    kind = item_catalog.CATALOG[entry_id]["kind"]
    items = db.get_items(conn, 1)
    if kind in ("weapon", "armor", "artifact"):
        assert len(items) == 2                                       # gear does not stack
    else:
        assert len(items) == 1 and items[0]["qty"] == 2
    assert "🎁" in admin.item_reply(entry_id, stored, lost)


def test_gifts_match_what_the_game_makes(conn):
    flawless = item_catalog.make("weapon:spirit:sword", quality="flawless")[0]
    assert flawless["name"].startswith("Flawless")
    assert flawless["data"]["buffs"] == {k: hi for k, (lo, hi) in equipments.WEAPON_BUFFS["sword"]["spirit"].items()}
    assert item_catalog.make("armor:divine:robe", quality="cracked")[0]["name"].startswith("Cracked")
    assert item_catalog.make("artifact:treasure:fang")[0] == loot.artifact("fang", "treasure")

    herb = item_catalog.make("herb:Earth:qi", 3, age=500)[0]
    assert herb["key"] == "Earth:qi:500" and herb["qty"] == 3

    shop = item_catalog.make("pill:qi:Mortal")[0]
    assert crafting.pill_info(shop) == ("qi", "Mortal", None)
    mend = item_catalog.make("pill:mending:Yellow", patterns=9)[0]
    assert crafting.pill_info(mend) == ("mending", "Yellow", 9)
    assert crafting.pill_info(item_catalog.make("pill:burst:Mortal")[0])[2] == item_catalog.DEFAULT_PATTERNS

    mat = item_catalog.make("material:seal", 7)[0]
    assert materials.is_forge_material(mat) and mat["qty"] == 7
    core = item_catalog.make("core:elite:Mystic")[0]
    assert core["key"] == "core:elite:Mystic"


def test_search_and_resolve():
    hits = item_catalog.search("fang")
    assert hits and all("fang" in label.lower() for _, label in hits)
    assert len(item_catalog.search("")) == 25
    assert item_catalog.resolve("Iron Sword") == ("weapon:ordinary:sword", None)
    assert item_catalog.resolve("weapon:divine:spear")[0] == "weapon:divine:spear"
    entry, problem = item_catalog.resolve("sword")
    assert entry is None and "matches" in problem
    assert item_catalog.resolve("no such thing")[0] is None


def test_full_bag(conn):
    db.update_player(conn, 1, bag_capacity=1)
    stored, lost = admin.give_item(conn, 1, "weapon:ordinary:saber", 3)
    assert len(stored) == 1 and len(lost) == 2
    assert "could not fit" in admin.item_reply("weapon:ordinary:saber", stored, lost)
    stored, lost = admin.give_item(conn, 1, "material:fuel:1", 50)     # forging materials use no slot
    assert stored and not lost


def test_admin_item_as_a_text_command(monkeypatch):
    from bot.client import MortalAscent
    bot = asyncio.run(_make(MortalAscent))
    user = FakeUser()

    async def app_info():
        return SimpleNamespace(team=None, owner=user)
    monkeypatch.setattr(bot, "application_info", app_info)
    run(bot, "m start", author=user)
    _, sent = run(bot, "m admin item Iron Sword amount:2 quality:flawless", author=user)
    assert "Flawless Iron Sword" in sent[-1].content and "×2" in sent[-1].content
    _, sent = run(bot, "m admin item Iron Ore amount:40", author=user)
    assert "Iron Ore ×40" in sent[-1].content
    names = [i["name"] for i in db.get_items(bot.conn, user.id)]
    assert names.count("Flawless Iron Sword") == 2 and "Iron Ore" in names


async def _make(cls):
    return cls(":memory:")
