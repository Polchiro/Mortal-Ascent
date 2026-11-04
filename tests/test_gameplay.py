"""Tests for /inventory, /explore and /train game logic (no Discord connection needed)."""
import asyncio
import random
import sqlite3
import time

import pytest

import explore
import equipments
from bot import combat, db, loot, trainer
from bot import player as rules
from bot.expedition import CLUES, Expedition, encounter_odds


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, talent="Genius"):
    return db.create_player(conn, uid, f"P{uid}", talent, rules.STARTING_LOTUS_COINS, rules.starting_techniques())


# ── storage ───────────────────────────────────────────────────────────

def test_old_database_gets_new_columns(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("CREATE TABLE players (user_id INTEGER PRIMARY KEY, name TEXT NOT NULL, talent TEXT NOT NULL,"
                      " realm TEXT NOT NULL DEFAULT 'Mortal', layer INTEGER NOT NULL DEFAULT 1, qi REAL NOT NULL DEFAULT 0,"
                      " lotus_coins INTEGER NOT NULL DEFAULT 0, moon_pearls INTEGER NOT NULL DEFAULT 0,"
                      " blessing_tier TEXT, blessing_expires REAL, beasts_slain INTEGER NOT NULL DEFAULT 0,"
                      " breakthroughs INTEGER NOT NULL DEFAULT 0, failed_breakthroughs INTEGER NOT NULL DEFAULT 0,"
                      " created_at REAL NOT NULL);"
                      "INSERT INTO players (user_id, name, talent, created_at) VALUES (7, 'Old', 'Gifted', 0);")
    old.commit()
    old.close()
    conn = db.connect(str(path))
    p = db.get_player(conn, 7)
    assert p["bag_capacity"] == 60 and p["toxicity"] == 0 and p["injured_until"] is None


def test_bag_stacks_and_capacity(conn):
    new_player(conn)
    assert db.add_item(conn, 1, **loot.chest("wooden"))
    assert db.add_item(conn, 1, **loot.chest("wooden"))
    assert db.get_items(conn, 1, "chests")[0]["qty"] == 2
    db.update_player(conn, 1, bag_capacity=2)
    assert db.add_item(conn, 1, **loot.roll_weapon("ordinary", random.Random(1)))
    assert not db.add_item(conn, 1, **loot.roll_weapon("ordinary", random.Random(2)))   # full
    assert db.add_item(conn, 1, **loot.chest("wooden"))                                  # stacking still fine
    assert db.slots_used(conn, 1) == 2


def test_cooldowns(conn):
    db.set_cooldown(conn, 1, "explore", 60, now=1000)
    assert db.cooldown_left(conn, 1, "explore", now=1030) == 30
    assert db.cooldown_left(conn, 1, "explore", now=2000) == 0
    assert db.cooldown_left(conn, 1, "train") == 0


# ── loot and using items ──────────────────────────────────────────────

def test_weapon_roll_matches_equipment_md():
    rng = random.Random(3)
    for _ in range(200):
        w = loot.roll_weapon("spirit", rng)
        for stat, val in w["data"]["buffs"].items():
            lo, hi = equipments.WEAPON_BUFFS[w["key"]]["spirit"][stat]
            assert lo - 1e-9 <= val <= hi + 1e-9
        assert w["name"].split()[-1] in equipments.WEAPON_NAMES["spirit"][w["key"]]


def test_open_chest_gives_coins_and_removes_it(conn):
    new_player(conn)
    db.add_item(conn, 1, **loot.chest("jade"))
    item = db.get_items(conn, 1, "chests")[0]
    msg = loot.use_item(conn, 1, item["id"], random.Random(0))
    assert "Lotus Coins" in msg
    assert db.get_items(conn, 1, "chests") == []
    assert db.get_player(conn, 1)["lotus_coins"] >= 50 + 200


def test_equip_weapon_changes_profile(conn):
    p = new_player(conn)
    db.add_item(conn, 1, **loot.roll_weapon("ordinary", random.Random(5)))
    w = db.get_items(conn, 1, "weapons")[0]
    assert "equip" in loot.use_item(conn, 1, w["id"]).lower()
    weapon = db.equipped_weapon(conn, 1)
    data = rules.profile_data(p, db.get_techniques(conn, 1), 1, weapon=weapon)
    assert data["weapon"]["name"] == w["name"] and data["weapon"]["tier"] == "ordinary"


def test_refined_weapon_needs_apprentice(conn):
    new_player(conn)
    db.add_item(conn, 1, **loot.roll_weapon("refined", random.Random(5)))
    w = db.get_items(conn, 1, "weapons")[0]
    assert "Martial Apprentice" in loot.use_item(conn, 1, w["id"])
    assert db.equipped_weapon(conn, 1) is None


def test_learn_manual_and_duplicate_insight(conn):
    new_player(conn)
    db.add_item(conn, 1, **loot.manual("twin_palm_strike"), qty=2)
    m = db.get_items(conn, 1, "manuals")[0]
    loot.use_item(conn, 1, m["id"])
    equipped = [t["name"] for t in db.get_techniques(conn, 1)]
    assert equipped == ["Horse Stance Guard", "Twin Palm Strike"]
    msg = loot.use_item(conn, 1, m["id"])
    assert "insight" in msg
    assert db.get_items(conn, 1, "manuals") == []


def test_pill_raises_qi_rate_and_does_not_stack(conn):
    new_player(conn, talent="Ordinary")
    db.add_item(conn, 1, **loot.pill("Mortal"), qty=2)
    pid = db.get_items(conn, 1, "pills")[0]["id"]
    now = time.time()
    loot.use_item(conn, 1, pid, now=now)
    p = db.get_player(conn, 1)
    assert rules.qi_rate(p, now)[1] == pytest.approx(1.2)
    assert "still working" in loot.use_item(conn, 1, pid, now=now)
    assert db.get_items(conn, 1, "pills")[0]["qty"] == 1


def test_toxicity_weakens_pills():
    assert rules.pill_effect_mult(3) == 1.0
    assert rules.pill_effect_mult(4) == 0.5
    assert rules.pill_effect_mult(7) == 0.25
    p = {"toxicity": 5, "toxicity_at": 0}
    assert rules.current_toxicity(p, now=2 * 86400 + 1) == 3


# ── Qi and breakthroughs ──────────────────────────────────────────────

def test_qi_rate_includes_best_technique():
    p = {"talent": "Genius", "realm": "Mortal"}
    techs = [{"grade": "Mortal", "mastery_exp": 0}, {"grade": "Yellow", "mastery_exp": 0}]
    assert rules.qi_rate(p, techniques=techs)[1] == pytest.approx(1 + 0.20 + 0.10)


def test_layers_and_mortal_breakthrough_always_succeeds(conn):
    p = new_player(conn)
    p, events = rules.add_qi(p, 10 + 10 + 10 + 3, rng=random.Random(0))
    assert (p["realm"], p["layer"]) == ("Martial Apprentice", 1)
    assert p["qi"] == pytest.approx(3)
    assert any("Realm breakthrough" in e for e in events)


def test_phase_bottleneck_can_fail():
    class AlwaysFail:
        def random(self):
            return 0.99
    p = {"realm": "Martial Apprentice", "layer": 3, "qi": 0, "breakthroughs": 0, "failed_breakthroughs": 0}
    p, events = rules.add_qi(p, 20, rng=AlwaysFail())
    assert p["layer"] == 3 and p["failed_breakthroughs"] == 1 and p["qi"] == pytest.approx(16)


def test_martial_master_needs_mastery():
    p = {"realm": "Martial Expert", "layer": 10, "qi": 0, "breakthroughs": 0, "failed_breakthroughs": 0}
    techs = [{"grade": "Mortal", "mastery_exp": 0}]
    p, events = rules.add_qi(p, 10 ** 6, techs, rng=random.Random(0))
    assert p["realm"] == "Martial Expert" and "Entering the Hall" in events[-1]


# ── combat and /explore ───────────────────────────────────────────────

def test_same_layer_normal_beast_is_beatable_most_of_the_time(conn):
    p = new_player(conn)
    techs = db.get_techniques(conn, 1)
    hp, atk, dfn = rules.final_stats(p, techs)
    wins = 0
    rng = random.Random(1)
    for _ in range(200):
        hero = {"hp": hp, "max_hp": hp, "attack": atk, "defense": dfn}
        enemy = combat.beast_stats(p, ("Wild Boar", "normal", "brute"))
        wins += combat.fight(hero, enemy, techs, rng)["won"]
    assert wins > 150


def test_encounter_odds_sum_to_one_and_rares_grow():
    for step in range(1, 6):
        assert sum(encounter_odds(step).values()) == pytest.approx(1.0)
    assert encounter_odds(5)["beast_king_den"] == pytest.approx(2 * encounter_odds(1)["beast_king_den"])


@pytest.mark.parametrize("enc", list(CLUES))
def test_every_encounter_runs(conn, enc):
    new_player(conn)
    db.update_player(conn, 1, lotus_coins=1000)
    e = Expedition(conn, 1, random.Random(4))
    e.next_step()
    e.paths["left"] = (enc, "clue")
    e.choose("left")
    if e.pending == "hazard":
        e.hazard["shown_at"] = time.time()
        e.dodge("left" if e.hazard["danger"] != "left" else "right")
    elif e.pending == "stranger":
        e.help_stranger("coins")
    if enc == "wandering_merchant":
        assert e.buy("pill") is None
        assert e.buy("pill") == "You already bought that."
    assert e.story
    e.finish()
    assert e.over and db.cooldown_left(conn, 1, "explore") > 0


def test_defeat_halves_found_coins_and_injures(conn):
    new_player(conn)
    e = Expedition(conn, 1, random.Random(0))
    e.next_step()
    e.coins = 100
    e.items = [dict(loot.herb(name="Spirit Grass"), qty=4), loot.manual("iron_fist")]
    e.hp = 0
    e._defeat()
    p = db.get_player(conn, 1)
    assert p["lotus_coins"] == 50 + 50
    assert rules.injured_for(p) > 3000
    assert db.get_items(conn, 1, "materials")[0]["qty"] == 2
    assert len(db.get_items(conn, 1, "manuals")) == 1


def test_slow_dodge_fails(conn):
    new_player(conn)
    e = Expedition(conn, 1, random.Random(0))
    e.next_step()
    e._hazard()
    e.hazard["shown_at"] = time.time() - 10
    safe = next(p for p in explore.PATHS if p != e.hazard["danger"])
    e.dodge(safe)
    assert e.hp < e.max_hp


def test_full_expedition_until_return(conn):
    new_player(conn)
    e = Expedition(conn, 1, random.Random(11))
    e.next_step()
    while not e.over:
        e.choose("middle")
        if e.pending == "hazard":
            e.dodge("left")
        elif e.pending == "stranger":
            e.help_stranger("leave")
        if e.over:
            break
        if e.can_go_deeper:
            e.next_step()
        else:
            e.finish()
    assert e.step <= explore.MAX_STEPS


# ── /train ────────────────────────────────────────────────────────────

def test_roll_session_uses_built_challenges_and_avoids_repeat():
    rng = random.Random(0)
    for _ in range(100):
        s = trainer.roll_session({"realm": "Mortal", "last_challenge": "endless_waves"}, rng)
        if s["event"] != "wandering_hermit":
            assert s["challenge"] == "read_the_master" and s["conditions"] == []
        assert set(s["conditions"]) <= set(trainer.APPLIES_TO[s["challenge"]])


def test_deceptive_tell_carries_hidden_sign():
    rng = random.Random(2)
    tell = trainer.make_tell("guard", True, rng)
    assert trainer.HIDDEN_SIGNS["guard"] in tell


def test_endless_waves_scoring():
    w = trainer.Waves(1, [])
    for _ in range(5):
        w.answer("strike", "guard", 0.5, 3.0)       # fast counters
    assert w.done and w.score == 1.0 and w.stamina == 100 - 5 * 5
    w = trainer.Waves(1, [])
    w.answer("strike", "break", 0.5, 3.0)
    assert w.done and w.score == 0
    w = trainer.Waves(1, ["old_injury"])
    w.answer("break", "strike", 2.0, 3.0)
    assert w.stamina == 80 and w.points == 0.5


def test_train_reward_and_cooldown(conn):
    new_player(conn, talent="Ordinary")
    s = {"challenge": "read_the_master", "conditions": [], "tier": 1, "event": None}
    qi, events, p = trainer.finish(conn, 1, s, 1.0, rng=random.Random(0))
    assert qi == pytest.approx(2.5 * 1.05 * 4)              # base × (1 + Iron Fist 5%) × 4h
    assert (p["layer"], db.get_player(conn, 1)["layer"]) == (2, 2)
    assert db.cooldown_left(conn, 1, "train") > 3500
    low, _, _ = trainer.finish(conn, 1, s, 0.4, rng=random.Random(0))
    assert low == pytest.approx(2.5 * 1.05 * 4 * 0.4 * 0.1)


# ── /inventory card ───────────────────────────────────────────────────

def test_inventory_card_renders_every_category(conn):
    from bot.views import inventory_data
    from inventory_card import render_inventory
    new_player(conn)
    rng = random.Random(0)
    for it in [loot.chest("bronze"), loot.manual("iron_fist"), loot.manual("viper_fang_finger"),
               loot.roll_weapon("spirit", rng), loot.pill("Yellow"), loot.herb(rng)]:
        db.add_item(conn, 1, **it)
    for cat in ("manuals", "weapons", "pills", "materials", "chests"):
        data, page_items, pages = inventory_data(conn, 1, cat, 1)
        assert page_items and pages == 1
        assert render_inventory(data).size[0] == 1200
    data, _, _ = inventory_data(conn, 1, "manuals", 1)
    assert data["items"][0]["status"] == "Learned"


def test_views_build_without_discord_connection(conn):
    from bot.views import ExploreView, InventoryView, TrainView

    class FakeBot:
        def __init__(self, c):
            self.conn, self.db_lock, self.busy = c, asyncio.Lock(), set()

    new_player(conn)

    async def go():
        bot = FakeBot(conn)
        ev = ExploreView(bot, 1, random.Random(0))
        assert len(ev.children) == 3 and ev.embed().title.startswith("🌲")
        iv = InventoryView(bot, 1)
        f = await iv.render()
        assert f.filename == "inventory.png"
        tv = TrainView(bot, 1, trainer.roll_session(db.get_player(conn, 1), random.Random(0)))
        assert tv.intro().description
    asyncio.run(go())
