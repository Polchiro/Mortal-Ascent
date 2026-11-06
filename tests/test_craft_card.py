"""The Alchemy Chamber card for /craft (cards/alchemy.py, bot/craft_card.py): every stage, the tribulation, both results."""
import asyncio
import random
import sys
from types import SimpleNamespace

import pytest

import alchemy
from bot import craft_card, crafting, db
from bot.crafting import Craft
from cards import alchemy_icons
from cards.alchemy import H, W, render_alchemy

from test_crafting import give, new_player, perfect


def herbs_for(kind, grade, age):
    rows = [{"name": alchemy.HERBS[grade][t][0], "type": t, "age": age, "qty": n} for t, n in crafting.KINDS[kind][3]]
    if kind == "breakthrough":
        rows.append({"name": "Elite Beast Core", "type": "core", "age": None, "qty": 1})
    return rows


def reach(mode, kind="qi", grade="Mystic", age=100, rank=5, chooser=perfect, seeds=400, after=0):
    """A craft stopped at a decision whose card shows `mode` (after `after` more decisions in that mode)."""
    for seed in range(seeds):
        c = Craft(kind, grade, rank, age, random.Random(seed))
        left = after
        for _ in range(300):
            if c.done:
                break
            if craft_card.card_data(c)["mode"] == mode:
                if not left:
                    return c
                left -= 1
            c.act(chooser(c))
    raise AssertionError(f"never reached {mode}")


def render(c, kind="qi", grade="Mystic", age=100, outcome=None):
    data = craft_card.card_data(c, herbs_for(kind, grade, age), outcome)
    img = render_alchemy(data)
    assert img.size == (W, H)
    return data


@pytest.mark.parametrize("mode", ["ignite", "herbs", "fuse", "condense"])
def test_card_renders_every_stage(mode):
    c = reach(mode, after=1)
    data = render(c)
    assert data["mode"] == mode
    current = [s for s in data["stages"] if s["state"] == "current"]
    assert len(current) == 1 and current[0]["key"] == {"ignite": 1, "herbs": 2, "fuse": 3, "condense": 4}[mode]
    assert data["warning"][0]


def test_card_renders_seal_the_core():
    c = reach("seal", kind="breakthrough", grade="Yellow", age=100)
    data = render(c, "breakthrough", "Yellow", 100)
    assert [s["key"] for s in data["stages"]][-1] == 5
    core = [h for h in data["herbs"] if h["type"] == "core"]
    assert core and core[0]["state"] == "waiting"


def test_card_renders_every_difficulty():
    for grade in alchemy.GRADES:
        c = Craft("qi", grade, 9, 1000, random.Random(2))
        data = render(c, grade=grade, age=1000)
        assert data["corner"]["difficulty"] == alchemy.DIFFICULTY[grade]["name"]


def test_card_renders_the_tribulation():
    c = reach("tribulation", grade="Heaven", age=1000, rank=9)
    data = render(c, grade="Heaven", age=1000)
    assert data["accent"] == "tribulation"
    assert data["stages"][-1] == {"key": 6, "state": "current"}
    assert data["patterns"]["earned"] == alchemy.TRIBULATION_FAIL_PATTERNS
    assert data["strike_dir"] in ("left", "above", "right")


def test_card_renders_a_nine_pattern_pill():
    c = reach("tribulation", grade="Heaven", age=1000, rank=9)
    while not c.done:
        c.act(perfect(c))
    assert c.result == 9
    data = render(c, grade="Heaven", age=1000, outcome={"exp": 800, "stored": True})
    assert data["mode"] == "success" and data["result"] == 9
    assert data["stages"][-1] == {"key": 6, "state": "done"}
    assert "Nine patterns" in data["warning"][0]


def test_card_renders_success_and_explosion():
    c = Craft("qi", "Mystic", 5, 100, random.Random(3))
    while not c.done:
        c.act(perfect(c))
    data = render(c, outcome={"exp": 60, "rank_up": "6th Grade", "stored": True})
    assert data["mode"] == "success" and data["corner"]["label"] == "REFINED"
    assert all(s["state"] == "done" for s in data["stages"])
    assert all(h["state"] == "in" for h in data["herbs"])
    assert "6th Grade" in data["warning"][1]

    c = Craft("qi", "Mystic", 5, 10, random.Random(3))
    while not c.done:
        c.act(None)                                     # walked away: every decision times out
    assert c.result == 0
    data = render(c, age=10, outcome={"exp": 12})
    assert data["mode"] == "exploded" and data["corner"]["label"] == "FAILED"


def test_card_renders_a_shattered_core():
    c = reach("seal", kind="breakthrough", grade="Yellow", age=100)
    while not c.done:
        c.act("compress")
    assert c.core_lost
    data = render(c, "breakthrough", "Yellow", 100)
    assert data["mode"] == "exploded" and data["core_lost"]
    assert {"key": 5, "state": "failed"} in data["stages"]
    assert [h for h in data["herbs"] if h["type"] == "core"][0]["state"] == "lost"


def test_fire_follows_the_shown_heat_text_not_the_hidden_zone():
    """A misleading hint changes the fire too, and the safe zone itself is never in the card data."""
    seen = set()
    for seed in range(300):
        c = Craft("qi", "Heaven", 9, 1000, random.Random(seed))
        pr = c.prompt()
        data = craft_card.card_data(c)
        assert data["heat_state"] == pr.view["heat_state"]
        texts = {"cold": "dull and cold", "hot": "hisses", "zone": "golden glow"}
        assert texts[data["heat_state"]] in data["warning"][0]
        if data["heat_state"] != c.heat_state(c.heat):
            seen.add("misleading")
        assert not {"zone_lo", "zone", "drift"} & set(data)       # only the zone's width, which the text says too
    assert "misleading" in seen


def test_herbs_float_in_type_order_never_the_hidden_order():
    c = reach("herbs")
    data = craft_card.card_data(c)
    assert [h["type"] for h in data["herbs_left"]] == sorted(h["type"] for h in data["herbs_left"])
    assert sum(h["count"] for h in data["herbs_left"]) == len(c.order) - c.placed


def test_pulse_on_the_card_is_the_shown_pulse():
    c = reach("condense", grade="Heaven", age=1000, rank=9)
    assert craft_card.card_data(c)["pulse"] == c.prompt().view["pulse"]


def test_card_text_has_no_markdown_or_emoji():
    assert craft_card.plain("✨ the light **trembles**, *ready*") == "the light trembles, ready"


def test_craft_icons_render():
    for key in alchemy_icons.ICONS:
        png = alchemy_icons.icon_png(key)
        assert png[:8] == b"\x89PNG\r\n\x1a\n"
    actions = {"stoke", "hold", "fan", *crafting.BALANCE_MOVES, "condense", "wait", *alchemy.HERB_TYPE_CHANCE,
               *(d[0] for d in crafting.DIRECTIONS), "again"}
    assert {"craft_" + a for a in actions} <= set(alchemy_icons.ICONS)


def test_alchemy_card_needs_only_pillow(monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", None)
    render(Craft("qi", "Mystic", 5, 100, random.Random(1)))


def test_craft_message_shows_a_card_every_decision():
    conn = db.connect(":memory:")
    new_player(conn)
    give(conn, "Yellow", "qi", 10, 2)
    give(conn, "Yellow", "purity", 10, 1)
    db.update_player(conn, 1, alchemy_exp=alchemy.ALCHEMIST_RANK_EXP[3])

    class FakeBot:
        def __init__(self, c):
            self.conn, self.db_lock, self.busy = c, asyncio.Lock(), {(1, "craft")}

    class FakeInteraction:
        def __init__(self):
            self.edits, self.deferred = [], False
            self.response = SimpleNamespace(edit_message=self.edit, defer=self.defer, is_done=lambda: self.deferred)

        async def defer(self):
            self.deferred = True

        async def edit(self, **kw):
            self.edits.append(kw)

        edit_original_response = edit

    async def go():
        view = crafting.CraftView(FakeBot(conn), 1, random.Random(4))
        view.choice = ("qi", "Yellow")
        await view.on_begin(it := FakeInteraction())
        assert it.deferred and it.edits[-1]["attachments"][0].filename == "craft.jpg"
        assert it.edits[-1]["embed"] is not None
        styles = {c.label.split()[0]: c.style for c in view.children}
        assert styles["Stoke"] != styles["Fan"]
        for _ in range(50):
            if view.craft.done:
                break
            view.timer.cancel()
            await view.resolve(perfect(view.craft), 0.5, it := FakeInteraction())
            assert it.edits[-1]["attachments"], "every decision edits the message with a new card"
        assert view.outcome and view.outcome["exp"] > 0 and view.outcome["stored"]
        await view.on_again(it := FakeInteraction())
        assert it.edits[-1]["attachments"] == []        # back to the text picker: the card comes off
        view.finish()

    asyncio.run(go())
