"""/forge (docs/forge.md Part 3): the blacksmith minigame, costs, rarity caps and what a forge writes on the gear."""
import asyncio
import random
from types import SimpleNamespace

import pytest

import forge
from bot import db, forging, loot, materials, passives
from bot import player as rules


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, coins=1_000_000, exp=0):
    db.create_player(conn, uid, "Tester", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(conn, uid, lotus_coins=coins, blacksmith_exp=exp)


def give_materials(conn, tier="ordinary", gear="weapon", times=1, uid=1, extra=()):
    n = forging.tier_no(tier)
    r = forge.RECIPE[tier]
    loot.store(conn, uid, [materials.material(forge.material_key("base", n, gear=gear), r["base"] * times),
                           materials.material(forge.material_key("binding", n), r["binding"] * times)]
               + [materials.material(k, q) for k, q in extra])


def give_gear(conn, kind="weapon", tier="ordinary", passive_keys=None, uid=1, equip=False):
    rng = random.Random(3)
    it = {"weapon": loot.roll_weapon, "armor": loot.roll_armor, "artifact": loot.roll_artifact}[kind](tier, rng)
    if passive_keys is not None:
        it["data"] = dict(it["data"], passives=list(passive_keys))
    loot.store(conn, uid, [it])
    item = max(db.get_items(conn, uid, it["category"]), key=lambda i: i["id"])
    if equip:
        if kind == "artifact":
            db.equip_artifact(conn, uid, item["id"], 1)
        else:
            db.equip_single(conn, uid, it["category"], item["id"])
    return db.get_item(conn, uid, item["id"])


def mats(conn, uid=1):
    return {i["key"]: i["qty"] for i in db.get_items(conn, uid, "materials")}


def perfect(g):
    """A strong player who reads every hint (hints can still lie on hard tiers)."""
    st = g.stage
    if st == "ignite":
        mid = g.zone_lo + g.zone_width / 2
        moves = {"pump": forge.IGNITE["pump"], "hold": 0, "vent": forge.IGNITE["vent"]}
        return min(moves, key=lambda k: abs(g.heat + moves[k] + g.drift - mid))
    if st == "heat":
        return "pull" if g.color == g.target else "keep"
    if st == "hammer":
        return forge.HAMMER_STATES[g.metal]["answer"]
    if st == "quench":
        if g.medium is None:
            return "oil"
        off = g.temp - g.quench_target
        if off <= g.quench_window() / 4:
            return "plunge"
        return "wait" if off - forge.QUENCH_TEMPS["step"][1] > 0 else "breath"
    return g.order[g.carved]


def play(g, chooser):
    for _ in range(300):
        if g.done:
            return g
        g.prompt()
        g.act(chooser(g))
    raise AssertionError("forge never ended")


def zero(g):
    return play(g, lambda g: None)


# ── the minigame ──────────────────────────────────────────────────────

def test_stages_run_in_order_and_score_out_of_100():
    g = forging.Forge("ordinary", 1, random.Random(1))
    seen = []
    for _ in range(300):
        if g.done:
            break
        if g.stage not in seen:
            seen.append(g.stage)
        g.prompt()
        g.act(perfect(g))
    assert seen == forge.STAGES and set(g.points) == set(forge.STAGES)
    assert 0 <= g.score() <= 100 and all(0 <= v <= forge.STAGE_MAX_POINTS for v in g.points.values())


def test_good_play_beats_random_and_idle_play():
    good = [play(forging.Forge("ordinary", 1, random.Random(s)), perfect).score() for s in range(40)]
    rnd = random.Random(9)
    bad = [play(forging.Forge("ordinary", 1, random.Random(s)),
                lambda g: rnd.choice([o[0] for o in g.prompt().options])).score() for s in range(40)]
    idle = [zero(forging.Forge("ordinary", 1, random.Random(s))).score() for s in range(10)]
    assert sum(good) / 40 > 85 and sum(good) / 40 > sum(bad) / 40 + 25
    assert max(idle) < forge.FAIL_BELOW
    assert all(zero(forging.Forge("ordinary", 1, random.Random(s))).rarity() is None for s in range(5))


def test_difficulty_follows_the_tier_and_bonuses_help():
    easy, hard = forging.Forge("ordinary", 1, random.Random(1)), forging.Forge("divine", 8, random.Random(1))
    assert easy.seconds > hard.seconds and easy.zone_width > hard.zone_width and easy.window > hard.window
    plain = forging.Forge("spirit", 4, random.Random(1))
    helped = forging.Forge("spirit", 7, random.Random(1), fuel="fuel:3", liquid="liquid:3", extra_seconds=0.5,
                           extra_degrees=2)
    assert helped.zone_width == plain.zone_width + 3 * forge.RANK_RELIEF["zone_degrees"] + forge.FUEL_ZONE_BONUS[2] + 2
    assert helped.window == plain.window + 3 * forge.RANK_RELIEF["zone_degrees"] + forge.LIQUID_WINDOW_BONUS[2] + 2
    assert helped.seconds == plain.seconds + 3 * forge.RANK_RELIEF["seconds_bonus"] + 0.5


def test_a_misleading_hint_stays_the_same_on_screen():
    g = forging.Forge("divine", 8, random.Random(4))
    assert g.prompt() is g.prompt()


def test_rarity_needs_the_inscription():
    g = forging.Forge("divine", 8, random.Random(1))
    g.done, g.points = True, {"ignite": 20, "heat": 20, "hammer": 20, "quench": 20, "inscribe": 20}
    assert g.rarity() == "Mythical"
    g.points = {"ignite": 20, "heat": 20, "hammer": 20, "quench": 20, "inscribe": 18}
    assert g.rarity() == "Legendary"
    g.points = {"ignite": 10, "heat": 10, "hammer": 10, "quench": 10, "inscribe": 9}
    assert g.rarity() is None


# ── plans and costs ───────────────────────────────────────────────────

def test_plan_uses_the_recipe_and_reports_what_is_missing(conn):
    new_player(conn)
    item = give_gear(conn)
    pl = forging.make_plan(conn, 1, item, "enchant")
    assert pl.missing and any("Iron" in m or "more" in m for m in pl.missing)
    give_materials(conn)
    pl = forging.make_plan(conn, 1, item, "enchant", fuel="fuel:1")
    assert any("Fuel" in m or "more" in m for m in pl.missing)          # no fuel owned
    pl = forging.make_plan(conn, 1, item, "enchant")
    assert not pl.missing and pl.coins == forge.ENCHANT_COINS["ordinary"]
    r = forge.RECIPE["ordinary"]
    assert dict(pl.uses) == {"base:weapon:1": r["base"], "binding:1": r["binding"]}


def test_actions_follow_the_slots(conn):
    new_player(conn)
    assert forging.actions_for(give_gear(conn, tier="ordinary")) == ["enchant"]
    assert forging.actions_for(give_gear(conn, tier="ordinary", passive_keys=["keen_edge"])) == ["reroll"]
    two = give_gear(conn, tier="treasure", passive_keys=["keen_edge", "weighted"])
    assert forging.actions_for(two) == ["reroll", "replace"]
    half = give_gear(conn, tier="treasure", passive_keys=["keen_edge", None])
    assert forging.actions_for(half) == ["enchant", "reroll"]


def test_rank_and_coins_are_required(conn):
    new_player(conn, coins=0)
    item = give_gear(conn, tier="refined", passive_keys=["keen_edge"])
    give_materials(conn, "refined")
    pl = forging.make_plan(conn, 1, item, "reroll")
    assert any("rank" in m for m in pl.missing) and any("Lotus" in m for m in pl.missing)
    db.update_player(conn, 1, lotus_coins=forge.REROLL_COINS["refined"],
                     blacksmith_exp=forge.BLACKSMITH_RANK_EXP[forge.RANK_NEEDED["refined"]])
    assert not forging.make_plan(conn, 1, item, "reroll").missing


def test_essence_that_gives_nothing_is_refused(conn):
    new_player(conn)
    item = give_gear(conn, tier="ordinary")
    give_materials(conn, extra=[("essence:blood:shard", 1)])
    pl = forging.make_plan(conn, 1, item, "enchant", essence="essence:blood:shard")
    assert any("essence" in m for m in pl.missing)


def test_take_materials_spends_everything(conn):
    new_player(conn)
    item = give_gear(conn, passive_keys=["keen_edge"])
    give_materials(conn, extra=[("fuel:1", 1), ("liquid:1", 2)])
    pl = forging.make_plan(conn, 1, item, "reroll", fuel="fuel:1", liquid="liquid:1")
    before = db.get_player(conn, 1)["lotus_coins"]
    assert forging.take_materials(conn, 1, pl)
    assert mats(conn) == {"liquid:1": 1}
    assert db.get_player(conn, 1)["lotus_coins"] == before - forge.REROLL_COINS["ordinary"]
    assert not forging.take_materials(conn, 1, pl)                      # nothing left to take


# ── outcomes ──────────────────────────────────────────────────────────

def finished(score_points, tier="ordinary"):
    g = forging.Forge(tier, forge.RANK_NEEDED[tier], random.Random(1))
    g.done, g.points = True, dict(zip(forge.STAGES, score_points))
    return g


def test_failure_loses_materials_but_keeps_the_gear(conn):
    new_player(conn)
    item = give_gear(conn, passive_keys=["keen_edge"])
    give_materials(conn)
    pl = forging.make_plan(conn, 1, item, "reroll")
    forging.take_materials(conn, 1, pl)
    out = forging.finish_forge(conn, 1, pl, finished([5, 5, 5, 5, 5]), random.Random(1))
    assert out["rarity"] is None and not out["refunded"]
    assert mats(conn) == {}
    assert passives.slots(db.get_item(conn, 1, item["id"])) == ["keen_edge"]
    assert db.get_player(conn, 1)["blacksmith_exp"] == out["exp"] > 0


def test_second_chance_saves_the_materials_once_a_day(conn):
    new_player(conn)
    give_gear(conn, "artifact", "spirit", passive_keys=["second_chance"], equip=True)
    item = give_gear(conn)
    for n in range(2):
        give_materials(conn)
        pl = forging.make_plan(conn, 1, item, "enchant")
        forging.take_materials(conn, 1, pl)
        out = forging.finish_forge(conn, 1, pl, finished([5, 5, 5, 5, 5]), random.Random(1), now=1_000_000)
        assert out["refunded"] == (n == 0)
    r = forge.RECIPE["ordinary"]
    assert mats(conn) == {"base:weapon:1": r["base"], "binding:1": r["binding"]}


def test_success_writes_a_passive_capped_by_the_gear_tier(conn):
    new_player(conn)
    item = give_gear(conn, tier="ordinary")
    give_materials(conn)
    pl = forging.make_plan(conn, 1, item, "enchant")
    forging.take_materials(conn, 1, pl)
    out = forging.finish_forge(conn, 1, pl, finished([20] * 5), random.Random(1))
    assert out["rarity"] == forge.PASSIVE_SLOTS["ordinary"]["max_rarity"]
    key = passives.slots(db.get_item(conn, 1, item["id"]))[0]
    assert forge.PASSIVES["weapon"][key]["rarity"] == out["rarity"]


def test_essence_picks_the_family_and_caps_the_rarity(conn):
    new_player(conn, exp=forge.BLACKSMITH_RANK_EXP[8])
    item = give_gear(conn, tier="divine")
    give_materials(conn, "divine", extra=[("essence:metal:shard", 1)])
    pl = forging.make_plan(conn, 1, item, "enchant", essence="essence:metal:shard")
    assert not pl.missing
    forging.take_materials(conn, 1, pl)
    out = forging.finish_forge(conn, 1, pl, finished([20] * 5, "divine"), random.Random(1))
    key = out["changed"][0][1]
    spec = forge.PASSIVES["weapon"][key]
    assert spec["family"] == "metal"
    assert forge.RARITIES.index(spec["rarity"]) <= forge.RARITIES.index(forge.ESSENCE_GRADES["shard"]["max_rarity"])


def test_replace_keeps_the_locked_slot_and_never_duplicates(conn):
    new_player(conn, exp=forge.BLACKSMITH_RANK_EXP[8])
    item = give_gear(conn, tier="treasure", passive_keys=["keen_edge", "weighted"])
    for seed in range(15):
        give_materials(conn, "treasure", extra=[("seal", 1)])
        pl = forging.make_plan(conn, 1, item, "replace", lock=0)
        assert not pl.missing, pl.missing
        forging.take_materials(conn, 1, pl)
        forging.finish_forge(conn, 1, pl, finished([20, 20, 20, 20, 15], "treasure"), random.Random(seed))
        s = passives.slots(db.get_item(conn, 1, item["id"]))
        assert s[0] == "keen_edge" and s[1] and s[1] != "keen_edge"


def test_no_passive_twice_on_one_character(conn):
    new_player(conn, exp=forge.BLACKSMITH_RANK_EXP[8])
    worn = give_gear(conn, "armor", "ordinary", equip=True)
    for seed in range(12):                                   # enchant then reroll the worn armor many times
        give_materials(conn, "ordinary", "armor")
        action = forging.actions_for(db.get_item(conn, 1, worn["id"]))[0]
        pl = forging.make_plan(conn, 1, db.get_item(conn, 1, worn["id"]), action)
        forging.take_materials(conn, 1, pl)
        forging.finish_forge(conn, 1, pl, finished([20, 20, 20, 10, 5]), random.Random(seed))
    armor_key = passives.slots(db.get_item(conn, 1, worn["id"]))[0]
    item = give_gear(conn, "armor", "ordinary")
    for seed in range(20):
        give_materials(conn, "ordinary", "armor")
        action = forging.actions_for(db.get_item(conn, 1, item["id"]))[0]
        pl = forging.make_plan(conn, 1, db.get_item(conn, 1, item["id"]), action)
        forging.take_materials(conn, 1, pl)
        forging.finish_forge(conn, 1, pl, finished([20, 20, 20, 10, 5]), random.Random(seed))
        assert armor_key not in passives.slots(db.get_item(conn, 1, item["id"]))


def test_mythical_is_announced(conn):
    new_player(conn, exp=forge.BLACKSMITH_RANK_EXP[8])
    item = give_gear(conn, tier="divine")
    give_materials(conn, "divine")
    pl = forging.make_plan(conn, 1, item, "enchant")
    forging.take_materials(conn, 1, pl)
    out = forging.finish_forge(conn, 1, pl, finished([20] * 5, "divine"), random.Random(1))
    assert out["rarity"] == "Mythical" and "Mythical" in out["news"]


def test_rank_up_and_exp(conn):
    new_player(conn)
    item = give_gear(conn)
    exp = 0
    while forging.rank_of(exp) < 2:
        give_materials(conn)
        action = forging.actions_for(db.get_item(conn, 1, item["id"]))[0]
        pl = forging.make_plan(conn, 1, db.get_item(conn, 1, item["id"]), action)
        forging.take_materials(conn, 1, pl)
        out = forging.finish_forge(conn, 1, pl, finished([20] * 5), random.Random(1))
        exp = db.get_player(conn, 1)["blacksmith_exp"]
    assert out["rank_up"] == forging.rank_label(2)


def test_swift_hands_and_steady_hand_reach_the_game(conn):
    new_player(conn)
    give_gear(conn, "artifact", "treasure", passive_keys=["swift_hands", "steady_hand"], equip=True)
    item = give_gear(conn)
    give_materials(conn)
    pl = forging.make_plan(conn, 1, item, "enchant")
    g = forging.new_game(conn, 1, pl, random.Random(1))
    base = forging.Forge("ordinary", 1, random.Random(1))
    assert g.seconds == base.seconds + 0.5 and g.zone_width == base.zone_width + 2 and g.window == base.window + 2


# ── the card and the forge message ────────────────────────────────────

def test_card_renders_every_stage_and_both_results(conn):
    from bot import forge_card
    from cards.forge import render_forge
    new_player(conn, exp=forge.BLACKSMITH_RANK_EXP[6])
    item = give_gear(conn, "armor", "treasure", passive_keys=["sturdy", None])
    give_materials(conn, "treasure", "armor", extra=[("fuel:2", 1), ("liquid:2", 1)])
    pl = forging.make_plan(conn, 1, item, forging.actions_for(item)[0], fuel="fuel:2", liquid="liquid:2")
    g = forging.Forge("treasure", 6, random.Random(2), pl.fuel, pl.liquid)
    modes = set()
    while not g.done:
        data = forge_card.card_data(pl, g)
        modes.add(data["mode"])
        img = render_forge(data)
        assert img.size == (1200, 880)
        g.act(perfect(g))
    assert modes == set(forge.STAGES)
    forging.take_materials(conn, 1, pl)
    out = forging.finish_forge(conn, 1, pl, g, random.Random(1))
    assert render_forge(forge_card.card_data(pl, g, out)).size == (1200, 880)
    bad = zero(forging.Forge("treasure", 6, random.Random(2)))
    give_materials(conn, "treasure", "armor")
    pl2 = forging.make_plan(conn, 1, db.get_item(conn, 1, item["id"]), "reroll")
    forging.take_materials(conn, 1, pl2)
    out2 = forging.finish_forge(conn, 1, pl2, bad, random.Random(1))
    data = forge_card.card_data(pl2, bad, out2)
    assert data["mode"] == "failed" and render_forge(data).size == (1200, 880)


def test_button_icons_draw():
    from cards import forge_icons
    for key in forge_icons.ICONS:
        assert forge_icons.render_icon(key).getbbox()
        assert key in forge_icons.FALLBACK


def test_forge_view_from_pick_to_result(conn):
    from bot import forge_view
    new_player(conn)
    item = give_gear(conn)
    give_materials(conn, extra=[("fuel:1", 1)])

    class FakeBot:
        def __init__(self, c):
            self.conn, self.db_lock, self.busy = c, asyncio.Lock(), {(1, "forge")}

    class FakeInteraction:
        def __init__(self):
            self.edits = []
            self.deferred = False
            self.response = SimpleNamespace(edit_message=self.edit, defer=self.defer, is_done=lambda: self.deferred)

        async def defer(self):
            self.deferred = True

        async def edit(self, **kw):
            self.edits.append(kw)

        edit_original_response = edit

    async def go():
        view = forge_view.ForgeView(FakeBot(conn), 1, random.Random(1))
        assert item["name"] in str(view.picker.options[0].label)
        view.item_id = item["id"]
        await view.redraw(FakeInteraction())
        assert view.action == "enchant" and "Will use" in view.embed().description
        await view.on_fuel(FakeInteraction(), "fuel:1")
        assert "fuel +" in view.embed().description
        await view.on_begin(FakeInteraction())
        assert mats(conn) == {}
        for _ in range(100):
            if view.game.done:
                break
            view.timer.cancel()
            await view.resolve(perfect(view.game), 0.5, FakeInteraction())
        assert view.result_lines and db.get_player(conn, 1)["blacksmith_exp"] > 0
        assert "Forge Again" in [c.label for c in view.children]
        await view.on_again(FakeInteraction())
        assert "Missing" in view.embed().description            # the materials were used up
        view.finish()

    asyncio.run(go())
