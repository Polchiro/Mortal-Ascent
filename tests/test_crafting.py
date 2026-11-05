"""/craft (docs/alchemy.md): herb planning, the stages, patterns, EXP and ranks, using crafted pills, Beast Cores."""
import asyncio
import random
from types import SimpleNamespace

import pytest

import alchemy
import training
from bot import crafting, db, loot
from bot import player as rules
from bot.crafting import Craft
from bot.sheet import items


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, realm="Mortal"):
    db.create_player(conn, uid, f"P{uid}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(conn, uid, realm=realm)
    return db.get_player(conn, uid)


def give(conn, tier, type_, age, qty, uid=1):
    loot.store(conn, uid, [dict(loot.herb(tier, type_, age), qty=qty)])


def perfect(c):
    """A strong player: picks the best move each decision."""
    st = 6 if c.tribulation == "pending" else c.stage
    if st == 1:
        mid = c.zone_lo + c.zone_width / 2
        return min((("stoke", 12), ("hold", 0), ("fan", -12)), key=lambda a: abs(c.heat + a[1] + c.drift - mid))[0]
    if st == 2:
        return c.order[c.placed]
    if st in (3, 5):
        def after(k):
            y, g = c.yin, c.yang
            if k == "circulate":
                m = (y + g) / 2
                return abs(round(y + max(-10, min(10, m - y))) - 50) + abs(round(g + max(-10, min(10, m - g))) - 50)
            dy, dg = crafting.BALANCE_MOVES[k]
            return abs(y + dy - 50) + abs(g + dg - 50)
        return min(crafting.BALANCE_MOVES, key=after)
    if st == 4:
        return "condense" if c.pulse >= 4 else "wait"
    return c.strike_dir[0]


def play(c, chooser):
    for _ in range(200):
        if c.done:
            return c.result
        c.prompt()
        c.act(chooser(c))
    raise AssertionError("craft never ended")


# ── ranks, patterns ───────────────────────────────────────────────────

def test_rank_from_exp():
    assert crafting.rank_of(0) == 1 and crafting.rank_of(99) == 1 and crafting.rank_of(100) == 2
    assert crafting.rank_of(120200) == 9


def test_score_to_patterns_and_age_cap():
    assert crafting.patterns_for(0.39, 9) == 0
    assert crafting.patterns_for(0.40, 9) == 1
    assert crafting.patterns_for(0.80, 9) == 6
    assert crafting.patterns_for(0.99, 5) == 5                  # 10-year herbs: at most 5 patterns
    assert crafting.toxicity_for(1) == 2 and crafting.toxicity_for(5) == 1 and crafting.toxicity_for(8) == 0


def test_age_tier_rounds_down():
    assert crafting.age_tier([10, 10, 100]) == 10                # average 40 → 10-year
    assert crafting.age_tier([50, 50, 100]) == 50
    assert crafting.age_tier([1000, 1000, 1000]) == 1000


# ── herb planning ─────────────────────────────────────────────────────

def test_plan_uses_recipe_herbs_and_reports_missing(conn):
    new_player(conn)
    give(conn, "Mortal", "qi", 10, 1)
    pl = crafting.plan(conn, 1, "qi", "Mortal")
    assert "1 more Spirit Grass" in pl["missing"][0] and "1 more Dew Leaf" in pl["missing"][1]
    give(conn, "Mortal", "qi", 10, 2)
    give(conn, "Mortal", "purity", 10, 1)
    pl = crafting.plan(conn, 1, "qi", "Mortal")
    assert pl["missing"] == [] and sum(q for _, q in pl["uses"]) == 3


def test_plan_meets_the_minimum_age_with_young_herbs_first(conn):
    new_player(conn)
    give(conn, "Mortal", "qi", 10, 5)
    give(conn, "Mortal", "qi", 100, 2)
    give(conn, "Mortal", "purity", 50, 1)
    pl = crafting.plan(conn, 1, "burst", "Mortal")                # 3 Spirit Grass + 1 Dew Leaf, 50-year average
    assert not pl["missing"] and pl["age"] >= 50
    assert sorted(pl["ages"]) == [10, 50, 100, 100]               # only as many old herbs as needed
    old = crafting.plan(conn, 1, "burst", "Mortal", prefer="old")
    assert sorted(old["ages"]) == [10, 50, 100, 100]


def test_breakthrough_needs_a_core(conn):
    new_player(conn)
    give(conn, "Mortal", "breakthrough", 50, 2)
    give(conn, "Mortal", "purity", 50, 1)
    assert "Normal Beast Core" in crafting.plan(conn, 1, "breakthrough", "Mortal")["missing"][0]
    loot.store(conn, 1, [loot.beast_core("normal", "Mortal")])
    pl = crafting.plan(conn, 1, "breakthrough", "Mortal")
    assert pl["missing"] == [] and pl["core"]
    assert crafting.take_ingredients(conn, 1, pl)
    assert db.get_items(conn, 1, "herbs") == [] and db.get_items(conn, 1, "materials") == []
    assert not crafting.take_ingredients(conn, 1, pl)            # already used


# ── the stages ────────────────────────────────────────────────────────

def test_stages_follow_the_difficulty():
    assert Craft("qi", "Mortal", 1, 10, random.Random(1)).stages == [1, 4]
    assert Craft("qi", "Yellow", 3, 10, random.Random(1)).stages == [1, 2, 4]
    assert Craft("qi", "Heaven", 9, 10, random.Random(1)).stages == [1, 2, 3, 4]
    c = Craft("breakthrough", "Mortal", 2, 50, random.Random(1))
    assert c.stages == [1, 2, 4, 5] and c.diff["name"] == "Hard"     # one difficulty harder + Seal the Core


def test_rank_relief_widens_the_zone_and_adds_time():
    base = Craft("qi", "Mortal", 1, 10, random.Random(1))
    eased = Craft("qi", "Mortal", 3, 10, random.Random(1))
    assert eased.zone_width == round(30 * 1.2) and eased.seconds == base.seconds + 1.0
    assert eased.forgive == 1 and base.forgive == 0
    assert Craft("qi", "Mortal", 1, 500, random.Random(1)).forgive == 1     # 500-year herbs forgive one


def test_good_play_beats_random_play():
    good = [play(Craft("qi", g, 9, 10, random.Random(s)), perfect) for g in alchemy.GRADES for s in range(40)]
    bad = [play(Craft("qi", g, 9, 10, random.Random(s)), lambda c: None) for g in alchemy.GRADES for s in range(40)]
    assert sum(good) / len(good) > 4 and sum(bad) / len(bad) < 1
    assert max(good) <= 5                                        # 10-year herbs cap at 5 patterns


def test_nine_patterns_need_the_tribulation():
    seen = set()
    for s in range(60):
        c = Craft("qi", "Heaven", 9, 1000, random.Random(s))
        play(c, perfect)
        seen.add((c.result, c.tribulation))
    assert (9, "won") in seen
    c = Craft("qi", "Heaven", 9, 1000, random.Random(3))
    while not c.done and c.tribulation != "pending":
        c.prompt()
        c.act(perfect(c))
    if c.tribulation == "pending":
        play(c, lambda c: "nowhere")
        assert c.result == alchemy.TRIBULATION_FAIL_PATTERNS


def test_failed_seal_destroys_the_core():
    c = Craft("breakthrough", "Mortal", 2, 50, random.Random(2))
    while c.stage != 5:
        c.prompt()
        c.act(perfect(c))
    c.yin, c.yang = 95, 5
    play(c, lambda c: None)
    assert c.done and c.result == 0 and c.core_lost


def test_misleading_hint_stays_the_same_on_screen():
    c = Craft("qi", "Heaven", 9, 10, random.Random(4))
    assert c.prompt() is c.prompt()


# ── finishing and using pills ─────────────────────────────────────────

def test_finish_stores_pill_and_exp(conn):
    new_player(conn)
    c = Craft("qi", "Mortal", 1, 10, random.Random(0))
    c.done, c.result = True, 5
    lines, news = crafting.finish_craft(conn, 1, c)
    pill = db.get_items(conn, 1, "pills")[0]
    assert pill["name"] == "Ember Dantian Pill · 五纹" and news is None
    assert db.get_player(conn, 1)["alchemy_exp"] == round(10 * (0.5 + 0.5))


def test_crafted_qi_pill_uses_patterns_and_toxicity(conn):
    new_player(conn)
    loot.store(conn, 1, [crafting.crafted_pill("qi", "Mortal", 9)])
    item = db.get_items(conn, 1, "pills")[0]
    msg = loot.use_item(conn, 1, item["id"], now=1000)
    p = db.get_player(conn, 1)
    assert p["pill_mult"] == pytest.approx(1 + 0.3 * 1.25) and p["toxicity"] == 0
    assert "×1.38" in msg or "×1.37" in msg


def test_shop_qi_pill_below_realm_gives_half(conn):
    new_player(conn, realm="Martial Apprentice")
    loot.store(conn, 1, [loot.pill("Mortal")])
    loot.use_item(conn, 1, db.get_items(conn, 1, "pills")[0]["id"], now=1000)
    assert db.get_player(conn, 1)["pill_mult"] == pytest.approx(1.15)


def test_burst_mending_and_cleansing(conn):
    new_player(conn)
    loot.store(conn, 1, [crafting.crafted_pill("burst", "Mortal", 4)])
    before = db.get_player(conn, 1)
    rate, _ = rules.qi_rate(before, 1000, db.get_techniques(conn, 1))
    loot.use_item(conn, 1, db.get_items(conn, 1, "pills")[0]["id"], now=1000)
    p = db.get_player(conn, 1)
    assert p["toxicity"] == 1 and (p["qi"] + p["layer"]) > before["qi"] + before["layer"]

    db.update_player(conn, 1, injured_until=1000 + 3600, toxicity=0, toxicity_at=1000)
    loot.store(conn, 1, [crafting.crafted_pill("mending", "Mortal", 4)])
    loot.use_item(conn, 1, db.get_items(conn, 1, "pills")[0]["id"], now=1000)
    assert db.get_player(conn, 1)["injured_until"] == pytest.approx(1000 + 1800)

    loot.store(conn, 1, [crafting.crafted_pill("cleansing", "Mortal", 1)])
    loot.use_item(conn, 1, db.get_items(conn, 1, "pills")[0]["id"], now=1000)
    assert db.get_player(conn, 1)["toxicity"] == 0                # 1 after mending, −1 (never less than 1 removed)


def test_breakthrough_pill_raises_the_realm_gate(conn):
    p = new_player(conn, realm="Martial Apprentice")
    loot.store(conn, 1, [crafting.crafted_pill("breakthrough", "Yellow", 4),
                         crafting.crafted_pill("breakthrough", "Mortal", 9)])
    it, bonus = crafting.best_breakthrough_pill(conn, 1, p)
    assert it["grade"] == "Yellow" and bonus == pytest.approx(training.BREAKTHROUGH_PILLS["Yellow"])
    p.update(layer=10, qi=rules.qi_needed("Martial Apprentice", 10))
    ok, _ = rules.attempt_breakthrough(p, rng=SimpleNamespace(random=lambda: 0.71), bonus=bonus)
    assert ok                                                     # 70% + 7%
    assert "breakthrough" in loot.use_item(conn, 1, it["id"]).lower()


def test_pill_details_in_the_bag(conn):
    p = new_player(conn)
    loot.store(conn, 1, [crafting.crafted_pill("mending", "Mortal", 7), loot.beast_core("elite", "Mortal")])
    pill = db.get_items(conn, 1, "pills")[0]
    d = items.details(pill, p)
    assert d["kind"] == "Mending Pill · 7 patterns" and "Injury" in d["effects"][0]
    core = db.get_items(conn, 1, "materials")[0]
    assert items.details(core, p)["kind"] == "Beast Core" and core["name"] == "Elite Beast Core"


# ── Beast Cores ───────────────────────────────────────────────────────

def test_beasts_drop_cores(conn):
    new_player(conn)
    found = [loot.roll_beast_core("beast_king", "Martial King", random.Random(s)) for s in range(200)]
    hits = [c for c in found if c]
    assert 60 < len(hits) < 140 and hits[0]["grade"] == "Heaven"
    assert loot.describe(hits[0]) == "Heaven Beast King Core"


# ── the craft message ─────────────────────────────────────────────────

def test_craft_view_from_pick_to_pill(conn):
    new_player(conn)
    give(conn, "Mortal", "qi", 10, 2)
    give(conn, "Mortal", "purity", 10, 1)

    class FakeBot:
        def __init__(self, c):
            self.conn, self.db_lock, self.busy = c, asyncio.Lock(), {(1, "craft")}

    class FakeInteraction:
        def __init__(self, values=None):
            self.edits = []
            self.data = {"values": values or []}
            self.response = SimpleNamespace(edit_message=self.edit)

        async def edit(self, **kw):
            self.edits.append(kw)

    async def go():
        view = crafting.CraftView(FakeBot(conn), 1, random.Random(1))
        assert "Ember Dantian Pill" in view.embed().fields[0].value
        view.choice = ("qi", "Mortal")
        await view.redraw(FakeInteraction())
        assert "Will use" in view.embed().description
        await view.on_begin(FakeInteraction())
        assert db.get_items(conn, 1, "herbs") == []
        for _ in range(50):
            if view.craft.done:
                break
            view.timer.cancel()
            await view.resolve(perfect(view.craft), 0.5, FakeInteraction())
        assert view.result_lines and db.get_player(conn, 1)["alchemy_exp"] > 0
        assert "Craft Again" in [c.label for c in view.children]
        view.finish()

    asyncio.run(go())
