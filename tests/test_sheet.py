"""Character Sheet: currencies and ledger, bag actions, card data, cards and the tabbed view."""
import asyncio
import io
import random
from types import SimpleNamespace

import pytest
from PIL import Image

from bot import db, loot
from bot import player as rules
from bot.sheet import attributes, items
from bot.sheet import data as sheet
from cards import RENDERERS


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1):
    return db.create_player(conn, uid, f"P{uid}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())


# ── Currencies ────────────────────────────────────────────────────────

def test_spend_never_goes_negative(conn):
    new_player(conn)
    assert db.spend(conn, 1, "lotus_coins", 51, "Too much") is None
    assert db.get_player(conn, 1)["lotus_coins"] == 50
    assert db.spend(conn, 1, "lotus_coins", 50, "All of it") == 0
    assert db.spend(conn, 1, "lotus_coins", 1, "Nothing left") is None
    with pytest.raises(ValueError):
        db.spend(conn, 1, "lotus_coins", -5, "Negative spend is a gift")
    with pytest.raises(ValueError):
        db.change_currency(conn, 1, "lotus_coins; DROP TABLE players", 1, "Bad column")


def test_clamped_loss_takes_only_what_there_is(conn):
    new_player(conn)
    db.add_coins(conn, 1, -500, "Robbed by bandits")
    assert db.get_player(conn, 1)["lotus_coins"] == 0
    assert db.ledger(conn, 1)[0]["delta"] == -50          # the ledger records what really changed


def test_ledger_records_every_change_newest_first(conn):
    new_player(conn)
    db.add_coins(conn, 1, 100, "Opened Uncommon Chest")
    db.change_currency(conn, 1, "moon_pearls", 300, "Admin gift")
    db.spend(conn, 1, "moon_pearls", 200, "Shop: Name change")
    rows = db.ledger(conn, 1)
    assert [r["reason"] for r in rows] == ["Shop: Name change", "Admin gift", "Opened Uncommon Chest", "Starting purse"]
    assert rows[0]["balance"] == 100 and rows[2]["balance"] == 150


def test_ledger_keeps_only_the_newest_rows(conn):
    new_player(conn)
    for _ in range(db.LEDGER_KEEP + 20):
        db.add_coins(conn, 1, 1, "Drip")
    assert len(db.ledger(conn, 1, 1000)) == db.LEDGER_KEEP


def test_stale_balance_does_not_double_spend(conn):
    """Two spends that both read 50 coins: only the money that is really there can go."""
    new_player(conn)
    assert db.spend(conn, 1, "lotus_coins", 30, "First") == 20
    assert db.spend(conn, 1, "lotus_coins", 30, "Second") is None
    assert db.get_player(conn, 1)["lotus_coins"] == 20


def test_shop_and_blessing_pay_through_the_wallet(conn):
    from bot.views import buy_blessing, buy_shop_item
    new_player(conn)
    msg, _ = buy_shop_item(conn, 1, "name_change", "Lin")
    assert "need" in msg and db.get_player(conn, 1)["name"] == "P1"   # no pearls, nothing happens
    db.change_currency(conn, 1, "moon_pearls", 500, "Admin gift")
    buy_shop_item(conn, 1, "name_change", "Lin")
    assert db.get_player(conn, 1)["name"] == "Lin" and db.get_player(conn, 1)["moon_pearls"] == 300
    assert "need" in buy_blessing(conn, 1, "Spring Rain")
    buy_blessing(conn, 1, "Gentle Breeze")
    p = db.get_player(conn, 1)
    assert p["moon_pearls"] == 0 and p["blessing_tier"] == "Gentle Breeze"
    assert db.ledger(conn, 1)[0]["reason"] == "Blessing: Gentle Breeze"


def test_shop_refunds_when_the_bag_is_full(conn):
    from bot.views import buy_shop_item
    new_player(conn)
    db.update_player(conn, 1, bag_capacity=0)
    db.change_currency(conn, 1, "moon_pearls", 60, "Admin gift")
    msg, _ = buy_shop_item(conn, 1, "mortal_qi_pill_x3")
    assert msg == "Your bag is full." and db.get_player(conn, 1)["moon_pearls"] == 60


# ── Bag ───────────────────────────────────────────────────────────────

def test_discard_rules(conn):
    new_player(conn)
    new_player(conn, 2)
    db.add_item(conn, 1, **dict(loot.herb("Mortal", "qi", 10), qty=5))
    db.add_item(conn, 1, **loot.roll_weapon("ordinary", random.Random(0)))
    herb = db.get_items(conn, 1, "herbs")[0]
    weapon = db.get_items(conn, 1, "weapons")[0]
    db.equip_weapon(conn, 1, weapon["id"])

    assert items.discard(conn, 2, herb["id"])[0] is False                 # someone else's item
    ok, _ = items.discard(conn, 1, weapon["id"])
    assert not ok and db.get_item(conn, 1, weapon["id"])                  # equipped: refused
    assert items.discard(conn, 1, herb["id"], 2)[0]
    assert db.get_item(conn, 1, herb["id"])["qty"] == 3
    assert items.discard(conn, 1, herb["id"], 99)[0]                      # more than there is: takes the stack
    assert db.get_item(conn, 1, herb["id"]) is None
    assert items.discard(conn, 1, herb["id"])[0] is False                 # already gone
    assert db.discard_item(conn, 1, weapon["id"], 0) is False


def test_item_actions_match_the_game(conn):
    new_player(conn)
    for it in (loot.chest("uncommon"), loot.manual("iron_fist"), loot.pill("Mortal"), loot.herb("Mortal", "qi", 10),
               loot.roll_weapon("ordinary", random.Random(0))):
        db.add_item(conn, 1, **it)
    by_cat = {i["category"]: i for i in db.get_items(conn, 1)}
    assert items.actions(by_cat["chests"]) == ["use", "discard"] and items.use_label(by_cat["chests"]) == "Open"
    assert items.actions(by_cat["herbs"]) == ["discard"]             # herbs have no use yet
    db.equip_weapon(conn, 1, by_cat["weapons"]["id"])
    assert items.actions(db.get_item(conn, 1, by_cat["weapons"]["id"])) == ["unequip"]
    p = db.get_player(conn, 1)
    for it in db.get_items(conn, 1):
        d = items.details(it, p, {"Iron Fist"})
        assert d["name"] and d["rarity"] and d["kind"]
    manual = items.details(by_cat["manuals"], p, {"Iron Fist"})
    assert any("Already learned" in n for n, _ in manual["notes"])


def test_bag_pages_and_selection(conn):
    new_player(conn)
    for i in range(sheet.BAG_PER_PAGE + 3):
        db.add_item(conn, 1, **loot.roll_weapon("ordinary", random.Random(i)))
    data, page_items, pages, sel = sheet.bag_data(conn, 1, "weapons", 2)
    assert pages == 2 and len(page_items) == 3 and sel["id"] == page_items[0]["id"]
    data, _, _, sel = sheet.bag_data(conn, 1, "weapons", 9, selected_id=page_items[1]["id"])
    assert data["page"] == 2 and sel["id"] == page_items[1]["id"]
    assert data["used"] == sheet.BAG_PER_PAGE + 3


# ── Attributes and slots ──────────────────────────────────────────────

def test_attributes_are_hp_attack_defense_only(conn):
    p = new_player(conn)
    vals = attributes.attribute_values(p, db.get_techniques(conn, 1))
    assert [a["key"] for a in vals] == ["hp", "attack", "defense"]
    assert (vals[0]["final"], vals[1]["final"], vals[2]["final"]) == rules.final_stats(p, db.get_techniques(conn, 1))
    assert vals[1]["sources"][0][0] == "Iron Fist"


def test_flex_slot_locked_until_martial_warrior(conn):
    p = new_player(conn)
    slots = sheet.technique_slots(p, db.get_techniques(conn, 1, equipped_only=False))
    assert [s["slot"] for s in slots] == ["Attack", "Defense", "Flex"]
    assert slots[2]["locked"] and slots[0]["tech"]["name"] == "Iron Fist"
    db.update_player(conn, 1, realm="Martial Warrior")
    slots = sheet.technique_slots(db.get_player(conn, 1), db.get_techniques(conn, 1, equipped_only=False))
    assert not slots[2]["locked"] and slots[2]["tech"] is None


def test_profile_hides_purse_from_others(conn):
    new_player(conn)
    assert sheet.profile_data(conn, 1)["coins"] == 50
    public = sheet.profile_data(conn, 1, private=False)
    assert public["coins"] is None and public["pearls"] is None


# ── Cards ─────────────────────────────────────────────────────────────

def all_card_data(conn, avatar=None):
    d = sheet.profile_data(conn, 1, "tester")
    d["avatar_bytes"] = avatar
    return {"profile": d, "techniques": sheet.techniques_data(conn, 1), "equipment": sheet.equipment_data(conn, 1),
            "inventory": sheet.bag_data(conn, 1, "chests")[0], "purse": sheet.purse_data(conn, 1)}


def test_every_card_renders_for_a_new_player(conn):
    new_player(conn)
    for tab, data in all_card_data(conn).items():
        img = RENDERERS[tab](data)
        assert img.size[0] == 1200 and img.mode == "RGB", tab


def test_cards_render_with_a_full_bag_and_an_avatar(conn):
    import scripts.render_sheet as demo
    c = db.connect(":memory:")
    demo.demo_player(c)
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 30, 30)).save(buf, format="PNG")
    for tab, data in all_card_data(c, buf.getvalue()).items():
        assert RENDERERS[tab](data).size[0] == 1200, tab
    for cat in items.ORDER:
        assert RENDERERS["inventory"](sheet.bag_data(c, 1, cat)[0]).size[0] == 1200
    public = sheet.profile_data(c, 1, private=False)
    assert RENDERERS["profile"](public).size == (1200, 830)


# ── The tabbed view ───────────────────────────────────────────────────

class FakeBot:
    def __init__(self, c):
        self.conn, self.db_lock, self.busy = c, asyncio.Lock(), set()


def fake_user(uid=1):
    async def read():
        return None
    avatar = SimpleNamespace(with_format=lambda *_: SimpleNamespace(with_size=lambda *_: SimpleNamespace(read=read)))
    return SimpleNamespace(id=uid, name="tester", display_avatar=avatar)


def test_sheet_builds_every_tab(conn):
    from bot.sheet.view import CharacterSheet
    new_player(conn)
    db.add_item(conn, 1, **loot.chest("common"))

    async def go():
        view = CharacterSheet(FakeBot(conn), fake_user(), "profile")
        for tab in ("profile", "techniques", "equipment", "inventory", "purse"):
            view.tab = tab
            f = await view.render()
            assert f.filename == f"{tab}.png"
            buttons = [c for c in view.children if getattr(c, "row", None) == 0]
            assert len(buttons) == 5 and sum(b.disabled for b in buttons) == 1
            rows = {}
            for c in view.children:
                rows.setdefault(c.row, []).append(c)
            assert all(len(v) <= 5 for v in rows.values())
        labels = [getattr(c, "label", None) for c in view.children]
        assert "Purse" in labels
        view.tab = "inventory"
        await view.render()
        assert "Open" in [getattr(c, "label", None) for c in view.children]
    asyncio.run(go())


def test_sheet_discard_needs_a_confirm(conn):
    from bot.sheet.view import CharacterSheet
    new_player(conn)
    db.add_item(conn, 1, **dict(loot.herb("Mortal", "qi", 10), qty=4))

    class FakeInteraction:
        def __init__(self):
            self.response = SimpleNamespace(defer=self._noop)
            self.edits = []

        async def _noop(self, **_):
            pass

        async def edit_original_response(self, **kw):
            self.edits.append(kw)

    async def go():
        view = CharacterSheet(FakeBot(conn), fake_user(), "inventory", "herbs")
        await view.render()
        await view.on_ask_discard(FakeInteraction())
        labels = [getattr(c, "label", "") for c in view.children]
        assert "Discard all ×4" in labels and "Cancel" in labels
        assert db.get_items(conn, 1, "herbs")[0]["qty"] == 4            # nothing gone yet
        await view.discard_callback(1)(FakeInteraction())
        assert db.get_items(conn, 1, "herbs")[0]["qty"] == 3
    asyncio.run(go())


def test_no_technique_swaps_in_a_fight(conn):
    from bot.sheet.view import CharacterSheet
    new_player(conn)
    db.update_player(conn, 1, realm="Martial Warrior")
    t = loot.technique.TECHNIQUES["crescent_sweep"]
    db.learn_technique(conn, 1, t["name"], t["type"], t["grade"], slots=2)     # replaces Iron Fist
    tid = next(x["id"] for x in db.get_techniques(conn, 1, equipped_only=False) if x["name"] == "Iron Fist")
    assert not db.get_technique(conn, 1, tid)["equipped"]
    bot = FakeBot(conn)
    bot.busy.add((1, "spar"))

    class FakeInteraction:
        def __init__(self, value):
            self.data = {"values": [str(value)]}
            self.response = SimpleNamespace(defer=self._noop)

        async def _noop(self, **_):
            pass

        async def edit_original_response(self, **kw):
            pass

    async def go():
        view = CharacterSheet(bot, fake_user(), "techniques")
        await view.on_equip_technique(FakeInteraction(tid))
        assert not db.get_technique(conn, 1, tid)["equipped"]
        bot.busy.clear()
        await view.on_equip_technique(FakeInteraction(tid))
        assert db.get_technique(conn, 1, tid)["equipped"]
    asyncio.run(go())


def test_cards_need_only_pillow(conn, monkeypatch):
    """requirements.txt installs Pillow and discord.py only, so the cards must not need numpy."""
    import sys
    from cards import theme
    monkeypatch.setitem(sys.modules, "numpy", None)        # any "import numpy" now fails
    theme._background.cache_clear()
    new_player(conn)
    for tab, data in all_card_data(conn).items():
        assert RENDERERS[tab](data).size[0] == 1200, tab
    theme._background.cache_clear()


# ── Night Ink redesign: purse vault, inspect actions, button icons, Qi card ──

def test_purse_shows_only_the_currencies(conn):
    new_player(conn)
    d = sheet.purse_data(conn, 1)
    assert [c["key"] for c in d["currencies"]] == list(db.CURRENCY_COLUMNS)
    assert RENDERERS["purse"](d).size == (1200, 370)


def test_inspect_shows_the_buttons_the_item_offers(conn):
    new_player(conn)
    db.add_item(conn, 1, **loot.chest("uncommon"))
    d, page_items, _, sel = sheet.bag_data(conn, 1, "chests")
    assert d["inspect"]["actions"] == ["Open", "Discard"]
    w = loot.roll_weapon("ordinary", random.Random(1))
    db.add_item(conn, 1, **w)
    wid = db.get_items(conn, 1, "weapons")[0]["id"]
    db.equip_weapon(conn, 1, wid)
    d, *_ = sheet.bag_data(conn, 1, "weapons", selected_id=wid)
    assert d["inspect"]["actions"] == ["Unequip"]        # worn gear can't be discarded


def test_sheet_icons_render_and_have_fallbacks():
    from cards import sheet_icons
    for key in sheet_icons.ICONS:
        assert sheet_icons.render_icon(key).getbbox()
        assert sheet_icons.FALLBACK[key]
        assert len("ma_" + key) <= 32
    from bot.sheet.view import TABS
    assert all(f"sheet_tab_{k}" in sheet_icons.ICONS for k, _ in TABS)
    assert set(sheet_icons.USE_KEY) == {c.use_verb for c in items.CATEGORIES.values() if c.use_verb}


def test_sheet_buttons_use_plain_emojis_without_uploaded_icons(conn):
    from bot.sheet.view import CharacterSheet
    new_player(conn)
    db.add_item(conn, 1, **loot.chest("common"))

    async def go():
        view = CharacterSheet(FakeBot(conn), fake_user(), "inventory")
        await view.render()
        tabs = [c for c in view.children if getattr(c, "row", None) == 0]
        assert all(b.emoji is not None for b in tabs)
        active = [b for b in tabs if b.disabled]
        assert len(active) == 1 and active[0].label == "Inventory"
        assert active[0].style.name == "primary"
    asyncio.run(go())


def test_qi_card_renders_new_full_and_toxic_players(conn):
    import time
    from bot import qi
    from cards.dantian import render_dantian, W, H
    new_player(conn)
    assert render_dantian(qi.qi_data(db.get_player(conn, 1), db.get_techniques(conn, 1))).size == (W, H)
    db.update_player(conn, 1, realm="Martial Expert", layer=3, qi=10 ** 7, qi_overflow=5000, toxicity=7,
                     toxicity_at=time.time())
    data = qi.qi_data(db.get_player(conn, 1), db.get_techniques(conn, 1))
    assert data["overflow_text"]
    assert render_dantian(data).size == (W, H)
