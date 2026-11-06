"""Tests for /inventory, /explore and /train game logic (no Discord connection needed)."""
import asyncio
import random
import sqlite3
import time

import pytest

import explore
import equipments
import technique
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
    assert p["qi_overflow"] == 0 and p["qi_pings"] == 1 and p["qi_ping_gate"] is None


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
    assert rules.qi_rate(p, now)[1] == pytest.approx(1.3)
    assert "still working" in loot.use_item(conn, 1, pid, now=now)
    assert db.get_items(conn, 1, "pills")[0]["qty"] == 1


def test_toxicity_weakens_pills():
    assert rules.pill_effect_mult(3) == 1.0
    assert rules.pill_effect_mult(4) == 0.5
    assert rules.pill_effect_mult(7) == 0.25
    p = {"toxicity": 5, "toxicity_at": 0}
    assert rules.current_toxicity(p, now=2 * 8 * 3600 + 1) == 3   # 1 toxicity fades every 8 hours


# ── Qi and breakthroughs ──────────────────────────────────────────────

def test_qi_rate_includes_best_technique():
    p = {"talent": "Genius", "realm": "Mortal"}
    techs = [{"grade": "Mortal", "mastery_exp": 0}, {"grade": "Yellow", "mastery_exp": 0}]
    assert rules.qi_rate(p, techniques=techs)[1] == pytest.approx(1 + 0.20 + 0.10)


def test_layers_fill_then_mortal_breakthrough_always_succeeds(conn):
    p = new_player(conn)
    p, events = rules.add_qi(p, 8 + 8 + 8 + 3, rng=random.Random(0))
    assert (p["realm"], p["layer"], p["qi"]) == ("Mortal", 3, 8)     # stops at a full bar
    assert p["qi_overflow"] == 3                                      # the extra waits behind the gate
    assert "/breakthrough" in events[-1]
    ok, msg = rules.attempt_breakthrough(p, rng=random.Random(0))
    assert ok and (p["realm"], p["layer"], p["qi"], p["qi_overflow"]) == ("Martial Apprentice", 1, 3, 0)


def test_breakthrough_needs_full_bar():
    p = {"realm": "Martial Apprentice", "layer": 3, "qi": 5, "breakthroughs": 0, "failed_breakthroughs": 0}
    ok, msg = rules.attempt_breakthrough(p)
    assert ok is None and "not full" in msg
    p["layer"] = 2
    assert rules.attempt_breakthrough(p)[0] is None


class AlwaysFail:
    def random(self):
        return 0.99


def test_phase_bottleneck_can_fail():
    p = {"realm": "Martial Apprentice", "layer": 3, "qi": 0, "breakthroughs": 0, "failed_breakthroughs": 0}
    p, _ = rules.add_qi(p, 30)
    assert p["qi"] == 16
    ok, _ = rules.attempt_breakthrough(p, rng=AlwaysFail())
    assert ok is False and p["layer"] == 3 and p["failed_breakthroughs"] == 1 and p["qi"] == pytest.approx(12.8)
    assert not p.get("injured_until")


def test_failed_realm_breakthrough_injures():
    p = {"realm": "Martial Apprentice", "layer": 10, "qi": 40, "breakthroughs": 0, "failed_breakthroughs": 0}
    ok, _ = rules.attempt_breakthrough(p, rng=AlwaysFail(), now=0)
    assert ok is False and p["injured_until"] == 6 * 3600


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
    e.items = [dict(loot.herb("Mortal", "qi", 10), qty=4), loot.manual("iron_fist")]
    e.hp = 0
    e._defeat()
    p = db.get_player(conn, 1)
    assert p["lotus_coins"] == 50 + 50
    assert rules.injured_for(p) > 3000
    assert db.get_items(conn, 1, "herbs")[0]["qty"] == 2
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


def test_views_build_without_discord_connection(conn):
    from bot.views import ExploreView, TrainView

    class FakeBot:
        def __init__(self, c):
            self.conn, self.db_lock, self.busy = c, asyncio.Lock(), set()

    new_player(conn)

    async def go():
        bot = FakeBot(conn)
        ev = ExploreView(bot, 1, random.Random(0))
        assert len(ev.children) == 4 and ev.embed().title.startswith("🌲")
        tv = TrainView(bot, 1, trainer.roll_session(db.get_player(conn, 1), random.Random(0)))
        assert tv.intro().description
    asyncio.run(go())


# ── passive Qi and /seclusion ─────────────────────────────────────────

def test_passive_qi_has_no_cap(conn):
    p = new_player(conn, talent="Ordinary")
    techs = db.get_techniques(conn, 1)
    p["qi_collected_at"] = 0
    qi, hours = rules.passive_qi(p, techs, now=3 * 3600)
    assert hours == 3 and qi == pytest.approx(2.5 * 1.05 * 3)
    assert rules.passive_qi(p, techs, now=100 * 3600)[1] == 100


def test_seclusion_doubles_only_when_completed(conn):
    p = new_player(conn, talent="Ordinary")
    techs = db.get_techniques(conn, 1)
    p["seclusion_start"], p["seclusion_end"] = 0, 8 * 3600
    qi, hours, done = rules.seclusion_qi(p, techs, now=10 * 3600)
    assert done and hours == 8 and qi == pytest.approx(2.5 * 1.05 * 2 * 8)
    qi, hours, done = rules.seclusion_qi(p, techs, now=4 * 3600)
    assert not done and qi == pytest.approx(2.5 * 1.05 * 4)
    assert rules.passive_qi(p, techs, now=4 * 3600) == (0.0, 0.0)


# ── mastery, /practice, /spar ─────────────────────────────────────────

def test_mastery_caps_until_trial(conn):
    from bot import mastery
    p = new_player(conn)
    t = db.get_techniques(conn, 1)[0]
    gained, note = mastery.gain(conn, p, t, 10_000)
    assert gained == 500 and "trial" in note
    assert mastery.gain(conn, p, t, 50)[0] == 0
    assert mastery.pass_trial(conn, t) == "Entering the Hall"
    t = db.get_techniques(conn, 1)[0]
    assert t["stage"] == 1 and rules.mastery_mult(t) == 1.10 and rules.mastery_cap(t) == 2000


def test_daily_rates():
    rates = technique.PRACTICE_DAILY_RATES
    assert [rules.daily_rate(rates, n) for n in (0, 4, 5, 9, 10, 30)] == [1, 1, 0.5, 0.5, 0.1, 0.1]
    assert rules.daily_rate(technique.SPAR_DAILY_RATES, 3) == 0.5


def test_practice_session(conn):
    new_player(conn)
    p = db.get_player(conn, 1)
    t = db.get_techniques(conn, 1)[0]
    s = trainer.roll_session(p, random.Random(0), tech=t)
    assert s["mode"] == "practice" and s["tier"] == 1
    s["conditions"], s["challenge"] = [], "read_the_master"
    exp, daily, note, tech = trainer.finish_practice(conn, 1, s, 1.0)
    assert exp == 40 and daily == 1 and tech["mastery_exp"] == 40
    assert db.cooldown_left(conn, 1, "practice") > 1700
    for _ in range(5):
        trainer.finish_practice(conn, 1, s, 1.0)
    assert trainer.finish_practice(conn, 1, s, 1.0)[1] == 0.5


def test_spar_reading_the_master_wins_and_awards_timed_uses(conn):
    from bot.sparring import Spar
    p = new_player(conn)
    techs = db.get_techniques(conn, 1)
    sp = Spar(p, techs, rng=random.Random(1))
    while not sp.over:
        if sp.blocked_strike and sp.ready("attack_tech"):
            sp.play("attack_tech")
        elif sp.master == "strike":
            sp.play("defense_tech" if sp.ready("defense_tech") else "guard")
        else:
            sp.play({"guard": "break", "break": "strike"}[sp.master])
    assert sp.won
    awards = sp.mastery_awards()
    assert awards and all(v >= technique.SPAR_WIN_EXP + technique.SPAR_EXP_PER_TIMED_USE for v in awards.values())


def test_spar_without_techniques_timing_gives_nothing(conn):
    from bot.sparring import Spar
    p = new_player(conn)
    sp = Spar(p, db.get_techniques(conn, 1), rng=random.Random(2))
    while not sp.over:
        sp.play("strike")
    assert sp.mastery_awards() == {}


def test_spar_techniques_have_cooldowns(conn):
    from bot.sparring import Spar
    p = new_player(conn)
    sp = Spar(p, db.get_techniques(conn, 1), rng=random.Random(3))
    assert sp.ready("attack_tech")
    sp.play("attack_tech")
    assert not sp.ready("attack_tech") and sp.ready("strike")
    turn = sp.turn
    assert "recovering" in sp.play("attack_tech") and sp.turn == turn   # refused, no turn spent
    sp.play("strike")
    assert sp.ready("attack_tech")                                     # Mortal: rests 1 turn


def test_cooldown_turns_scale_with_grade_and_heavy():
    def cd(name):
        t = rules.TECH_BY_NAME[name]
        return combat.cooldown_turns({"name": name, "grade": t["grade"]})
    assert cd("Iron Fist") == 1
    assert cd("Raging Bull Fist") == 2          # Yellow 1 + Heavy 1
    assert cd("Viper Fang Finger") == 2
    assert cd("Meteor-Falling Kick") == 4       # Heaven 3 + Heavy 1
    assert combat.cooldown_turns(None) == 0


def test_auto_fight_respects_attack_cooldown(conn):
    p = new_player(conn)
    techs = db.get_techniques(conn, 1)
    hp, atk, dfn = rules.final_stats(p, techs)
    hero = {"hp": hp * 100, "max_hp": hp * 100, "attack": atk * 0.01, "defense": dfn}
    enemy = combat.beast_stats(p, ("Wild Boar", "normal", "brute"))
    res = combat.fight(hero, enemy, techs, random.Random(0))
    assert res["rounds"] == combat.MAX_ROUNDS
    assert res["attack_uses"] == combat.MAX_ROUNDS // 2               # every other turn


def test_spar_view_greys_out_cooling_technique(conn):
    from bot.views import SparView

    class FakeBot:
        def __init__(self, c):
            self.conn, self.db_lock, self.busy = c, asyncio.Lock(), set()

    new_player(conn)

    async def go():
        sv = SparView(FakeBot(conn), 1, rng=random.Random(0))
        sv.spar.play("attack_tech")
        sv.build()
        b = next(c for c in sv.children if c.spar_key == "attack_tech")
        assert b.disabled and "1 turn" in b.label
        assert not next(c for c in sv.children if c.spar_key == "strike").disabled
    asyncio.run(go())


def test_flex_slot_from_martial_warrior(conn):
    new_player(conn)
    a = db.learn_technique(conn, 1, "Twin Palm Strike", "attack", "Mortal", slots=2)
    assert [t["name"] for t in db.get_techniques(conn, 1)] == ["Horse Stance Guard", "Twin Palm Strike"]
    iron = next(t for t in db.get_techniques(conn, 1, equipped_only=False) if t["name"] == "Iron Fist")
    assert db.equip_technique(conn, 1, iron["id"], slots=3) is None       # flex slot takes it
    assert len(db.get_techniques(conn, 1)) == 3
    assert db.unequip_technique(conn, 1, a)
    guard = next(t for t in db.get_techniques(conn, 1) if t["type"] == "defense")
    assert not db.unequip_technique(conn, 1, guard["id"])                 # must keep one defense


def test_spar_view_builds(conn):
    from bot.views import SparView

    class FakeBot:
        def __init__(self, c):
            self.conn, self.db_lock, self.busy = c, asyncio.Lock(), set()

    new_player(conn)

    async def go():
        sv = SparView(FakeBot(conn), 1, rng=random.Random(0))
        assert len(sv.children) == 5 and sv.embed().title
    asyncio.run(go())


def test_all_commands_register():
    from bot.client import MortalAscent

    async def go():
        bot = MortalAscent(":memory:")
        names = {c.name for c in bot.tree.get_commands()}
        for c in bot.tree.get_commands():
            c.to_dict(bot.tree)
        return names
    assert asyncio.run(go()) == {"start", "profile", "balance", "inventory", "explore", "train",
                                 "seclusion", "breakthrough", "internal", "practice", "spar", "techniques", "equipment",
                                 "shop", "blessing", "recharge", "reroll", "physician", "bestiary", "cooldown", "settings", "admin",
                                 "tutorial", "index", "gather", "craft", "duel"}


# ── tier 2 challenges ─────────────────────────────────────────────────

def test_ambush_one_counter_can_stop_both():
    a = trainer.Ambush(2, random.Random(0))
    a.moves, a.strong = ["strike", "strike"], 0
    assert "both" in a.answer("guard", 0.5, 2.5) and a.hp == 3 and a.survived == 1
    a.moves, a.strong = ["strike", "break"], 0
    a.answer("strike", 0.5, 2.5)            # stops the Break, the strong Strike hits for 2
    assert a.hp == 1
    a.moves, a.strong = ["guard", "guard"], 1
    a.answer(None, 9, 2.5)
    assert a.hp == 0 and a.done and a.score == pytest.approx(2 / 5)


def test_weakness_feedback_and_score():
    assert trainer.weakness_feedback(["strike", "guard", "break"], ["guard", "guard", "strike"]) == (1, 1)
    w = trainer.Weakness(2, random.Random(0))
    w.secret = ["strike", "strike", "guard"]
    w.guess(["guard", "guard", "guard"])
    w.guess(["strike", "strike", "guard"])
    assert w.solved and w.score == 1.0
    w = trainer.Weakness(2, random.Random(0))
    w.secret = ["break"] * 3
    for _ in range(w.tries):
        w.guess(["guard"] * 3)
    assert w.done and w.score == 0


def test_tier_two_pool_includes_new_challenges():
    rng = random.Random(1)
    seen = {trainer.roll_session({"realm": "Martial Expert"}, rng)["challenge"] for _ in range(200)}
    assert {"ambush", "find_the_weakness"} <= seen


# ── economy, hunts, chests ────────────────────────────────────────────

def test_shop_purchases(conn):
    from bot.views import buy_shop_item
    new_player(conn, talent="Gifted")
    msg, _ = buy_shop_item(conn, 1, "mortal_qi_pill_x3")
    assert "need" in msg
    db.update_player(conn, 1, moon_pearls=2000)
    buy_shop_item(conn, 1, "mortal_qi_pill_x3")
    assert db.get_items(conn, 1, "pills")[0]["qty"] == 3
    buy_shop_item(conn, 1, "inventory_expansion_20")
    buy_shop_item(conn, 1, "name_change", "Iron Lotus")
    buy_shop_item(conn, 1, "heavenly_fate_reroll", rng=random.Random(0))
    p = db.get_player(conn, 1)
    assert p["bag_capacity"] == 80 and p["name"] == "Iron Lotus"
    assert rules.talent.TALENTS.index(p["talent"]) >= 1          # never lower than Gifted
    assert p["moon_pearls"] == 2000 - 60 - 300 - 200 - 600


def test_blessing_same_tier_extends_other_replaces(conn):
    from bot.views import buy_blessing
    new_player(conn)
    db.update_player(conn, 1, moon_pearls=5000)
    buy_blessing(conn, 1, "Gentle Breeze", now=0)
    buy_blessing(conn, 1, "Gentle Breeze", now=0)
    assert db.get_player(conn, 1)["blessing_expires"] == 60 * 86400
    buy_blessing(conn, 1, "Spring Rain", now=86400)
    p = db.get_player(conn, 1)
    assert p["blessing_tier"] == "Spring Rain" and p["blessing_expires"] == 31 * 86400
    assert p["moon_pearls"] == 5000 - 300 - 300 - 700


def test_fate_reroll_cost_grows():
    assert rules.fate_reroll_cost({"fate_rerolls": 0}) == 10000
    assert rules.fate_reroll_cost({"fate_rerolls": 2}) == 22500


def test_heaven_defying_pill_raises_talent(conn):
    new_player(conn, talent="Heavenly")
    db.add_item(conn, 1, **loot.HEAVEN_DEFYING)
    news = []
    loot.use_item(conn, 1, db.get_items(conn, 1, "pills")[0]["id"], announce=news)
    assert db.get_player(conn, 1)["talent"] == "Saint" and news     # Saint is announced
    assert db.get_items(conn, 1, "pills") == []


def test_rare_drop_announcements():
    assert loot.announcement("A", loot.roll_weapon("divine", random.Random(0)))
    assert loot.announcement("A", loot.manual("heaven_rending_palm"))
    assert loot.announcement("A", loot.roll_weapon("spirit", random.Random(0))) is None
    assert loot.talent_announcement("A", "Saint") and not loot.talent_announcement("A", "Genius")


def test_physician_cost(conn):
    p = new_player(conn)
    p["injured_until"] = 3600
    assert rules.physician_cost(p, now=0) == 60


def test_team_hunt_elite_and_king(conn):
    from bot import hunt
    for uid in (1, 2, 3):
        new_player(conn, uid)
    p = db.get_player(conn, 1)
    lair = hunt.roll_lair(p, "elite", random.Random(0))
    beast = hunt.team_beast(lair, [db.get_player(conn, u) for u in (1, 2, 3, 4) if db.get_player(conn, u)])
    assert beast["max_hp"] >= rules.base_stats("Mortal", 1)[0] * 5 * 0.85 - 1
    won, lines, _ = hunt.resolve(conn, lair, [1, 2, 3], random.Random(3))
    assert len(lines) >= 4
    if won:
        assert db.get_player(conn, 2)["beasts_slain"] == 1
    else:
        assert rules.injured_for(db.get_player(conn, 2)) > 0
    king = dict(hunt.roll_lair(p, "beast_king", random.Random(0)))
    for _ in range(30):
        won, _, news = hunt.resolve(conn, king, [1], random.Random(1))
        assert not won                       # one Mortal can't kill a ×12 HP Beast King
        db.update_player(conn, 1, injured_until=None)


def test_king_kill_unlocks_realm_requirement():
    p = {"realm": "Martial Grandmaster", "king_kills": ""}
    techs = [{"grade": "Mystic", "mastery_exp": 0, "stage": 2}]
    assert "Beast King" in rules.realm_requirement_missing(p, techs, "Martial King")
    p["king_kills"] = "Martial Grandmaster"
    assert rules.realm_requirement_missing(p, techs, "Martial King") is None


def test_explore_lair_creates_hunt(conn):
    new_player(conn)
    e = Expedition(conn, 1, random.Random(0))
    e.next_step()
    e.paths["left"] = ("beast_king_den", "clue")
    e.choose("left")
    assert e.lair and e.lair["tier"] == "beast_king"


def test_passive_qi_rises_before_every_command(conn):
    from bot.client import sync_passive_qi
    new_player(conn, talent="Ordinary")
    db.update_player(conn, 1, qi_collected_at=0)
    qi, events = sync_passive_qi(conn, 1, now=2 * 3600)
    p = db.get_player(conn, 1)
    assert qi == pytest.approx(2.5 * 1.05 * 2) and p["qi_collected_at"] == 2 * 3600
    assert (p["layer"], p["qi"]) == (1, pytest.approx(5.25))
    assert sync_passive_qi(conn, 1, now=2 * 3600)[0] == 0          # nothing twice
    db.update_player(conn, 1, seclusion_start=0, seclusion_end=8 * 3600)
    assert sync_passive_qi(conn, 1, now=5 * 3600)[0] == 0          # seclusion gathers its own way
