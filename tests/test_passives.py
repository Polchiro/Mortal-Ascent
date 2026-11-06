"""Forged passives at work (docs/forge.md Part 4): in fights and duels, on stats, on cards, and artifact passives
across the game."""
import random

import pytest

import alchemy
import forge
import stats
import training
from bot import combat, crafting, db, fight, gathering, gear, loot, materials, passives
from bot import duel as D
from bot import player as rules
from bot.sheet import data as sheet
from cards.equipment import render_equipment

from test_forging import give_gear, new_player


@pytest.fixture
def conn():
    return db.connect(":memory:")


TECHS = [{"id": 1, "name": "Iron Fist", "type": "attack", "grade": "Mortal", "mastery_exp": 0, "stage": 0},
         {"id": 2, "name": "Horse Stance Guard", "type": "defense", "grade": "Mortal", "mastery_exp": 0, "stage": 0}]


def player(uid=1, name="Shoaib", keys=(), artifact=()):
    return {"user_id": uid, "name": name, "realm": "Mortal", "layer": 1, "gear_passives": list(keys),
            "artifact_passives": {k: forge.PASSIVES["artifact"][k]["fx"] for k in artifact}}


def battle(keys=(), n=1, seed=0, beast=("Wild Boar", "normal", "brute"), hp=None, others=()):
    fighters = []
    for i in range(n):
        p = player(i + 1, f"F{i + 1}", keys if i == 0 else (others[i - 1] if others else ()))
        h, atk, dfn = rules.base_stats("Mortal", 1)
        fighters.append(fight.Fighter(p, TECHS, hp or h, h, atk, dfn))
    enemy = fight.enemy_from_beast(combat.beast_stats(fighters[0].player, beast), beast[0])
    enemy.update(realm="Mortal", dodge=0)
    return fight.Battle(fighters, enemy, random.Random(seed))


def force(b, move, kind="normal", target=0):
    b.enemy["statuses"].clear()
    b.intent = {"move": move, "kind": kind, "target": b.fighters[target], "name": "Test Move"}


def texts(log):
    return " | ".join(t for _, t in log)


# ── stats and the kit ─────────────────────────────────────────────────

def test_stat_passives_add_to_final_stats(conn):
    new_player(conn)
    w = give_gear(conn, "weapon", "ordinary", passive_keys=["keen_edge"])
    a = give_gear(conn, "armor", "ordinary", passive_keys=["thick_hide"])
    plain_w, plain_a = dict(w, data=dict(w["data"], passives=[None])), dict(a, data=dict(a["data"], passives=[None]))
    p = dict(db.get_player(conn, 1), realm=list(stats.BASE_HP)[-1], layer=9)   # big numbers so 3% shows
    hp0, atk0, _ = rules.final_stats(p, (), plain_w, plain_a)
    hp1, atk1, _ = rules.final_stats(p, (), w, a)
    assert atk1 > atk0 and hp1 > hp0
    names = [n for n, _ in rules.stat_buffs((), w, a)["attack"]]
    assert "Keen Edge" in names


def test_worn_passives_reach_the_player(conn):
    new_player(conn)
    give_gear(conn, "weapon", "treasure", passive_keys=["lifesteal", "keen_edge"], equip=True)
    give_gear(conn, "armor", "ordinary", passive_keys=["thorns"], equip=True)
    give_gear(conn, "weapon", "ordinary", passive_keys=["breaker"])           # in the bag: not worn
    assert sorted(db.get_player(conn, 1)["gear_passives"]) == ["keen_edge", "lifesteal", "thorns"]


def test_fair_duels_halve_strengths_but_not_counts():
    k = passives.Kit(["lifesteal", "phoenix_rebirth", "rhythm", "dragons_wrath", "mountain_stance"],
                     forge.DUEL_PASSIVE_STRENGTH)
    assert k.fx("lifesteal", "heal_of_damage") == pytest.approx(0.02)
    assert k.fx("phoenix_rebirth", "uses_per_fight") == 1 and k.fx("rhythm", "max_stacks") == 3
    assert k.fx("dragons_wrath", "mult") == pytest.approx(1.25)
    assert k.fx("mountain_stance", "max_hit") == pytest.approx(0.40)
    assert passives.Kit(["lifesteal"]).fx("lifesteal", "heal_of_damage") == pytest.approx(0.04)


# ── fights ────────────────────────────────────────────────────────────

def test_lifesteal_heals_and_shows_in_the_log():
    b = battle(["lifesteal"], hp=20)
    b.fighters[0].attack *= 10                                           # a big enough hit that 4% shows
    force(b, "break")
    b.choose(1, "strike")
    log = b.resolve()
    assert "Lifesteal: +" in texts(log) and b.fighters[0].hp > 20


def test_the_30_percent_cap_holds_after_every_passive():
    keys = ["dragons_wrath", "opening_strike", "hunters_edge", "sunder", "breaker", "executioner", "blood_frenzy",
            "flash_step"]
    for seed in range(30):
        b = battle(keys, seed=seed, hp=100)
        k = b.fighters[0].kit
        k.chance = lambda key, field="chance": True                       # every chance passive fires
        b.fighters[0].attack *= 50
        start = b.enemy["hp"]
        force(b, "break")                     # Strike beats Break: a clean hit, no stagger bonus on top
        b.choose(1, "strike")
        b.resolve()
        assert start - b.enemy["hp"] <= b.enemy["max_hp"] * stats.MAX_HIT_PERCENT + 1e-9


def test_phoenix_rebirth_once_per_fight():
    b = battle(["phoenix_rebirth"], hp=1)
    b.enemy["attack"] *= 20
    force(b, "strike")
    b.choose(1, "strike")
    b.fighters[0].pick = "break"                                      # Break loses to Strike: the hit lands
    log = b.resolve()
    f = b.fighters[0]
    assert "Phoenix Rebirth!" in texts(log) and f.hp == round(f.max_hp * 0.20)
    f.hp = 1
    force(b, "strike")
    b.choose(1, "break")
    b.resolve()
    assert f.hp == 0 and b.result == "lost"


def test_undying_blade_survives_at_1_hp():
    b = battle(["undying_blade"], hp=1)
    b.enemy["attack"] *= 20
    force(b, "strike")
    b.choose(1, "break")
    log = b.resolve()
    assert b.fighters[0].hp == 1 and "Undying Blade" in texts(log)


def test_reflect_is_capped_at_20_percent():
    k = passives.Kit(["spiked_plates", "thorns"])
    owner = type("O", (), {"max_hp": 10_000, "hp": 10_000})()
    k.rng = random.Random(1)
    _, back, _ = k.taken(owner, 1000, 2, mirror_artifact=0.18)
    assert back == pytest.approx(1000 * (forge.REFLECT_CAP - 0.18))
    _, back, _ = k.taken(owner, 1000, 2)
    assert back == pytest.approx(1000 * 0.09)


def test_defensive_passives():
    owner = type("O", (), {"max_hp": 1000, "hp": 1000})()
    k = passives.Kit(["golden_body", "mountain_stance"], rng=random.Random(1))
    dmg, _, lines = k.taken(owner, 600, 2)
    assert dmg == 200 and "Golden Body" in texts(lines)                 # −50%, then held to 20% max HP
    dmg, _, _ = k.taken(owner, 150, 2)
    assert dmg == 150                                                    # Golden Body is the first hit only
    k = passives.Kit(["black_tortoise_shell"], rng=random.Random(1))
    got = [k.taken(owner, 100, 2)[0] for _ in range(8)]
    assert got == [100, 100, 100, 0, 100, 100, 100, 0]


def test_thunder_edge_stops_the_next_guard():
    b = battle(["thunder_edge"])
    b.fighters[0].kit.chance = lambda key, field="chance": key == "thunder_edge"
    force(b, "break")
    b.choose(1, "strike")
    b.resolve()
    assert b.intent["move"] != "guard"


def test_heavenly_aegis_protects_allies_only():
    b = battle(n=2, others=[["heavenly_aegis"]])
    assert b._aura(b.fighters[0]) == pytest.approx(0.10) and b._aura(b.fighters[1]) == 0


def test_immortal_body_blocks_bleeding():
    k = passives.Kit(["immortal_body"])
    assert k.immune("bleeding") and k.immune("poisoned") and not k.immune("burning")


def test_whole_fights_with_every_passive_run_to_the_end():
    keys = list(forge.PASSIVES["weapon"]) + list(forge.PASSIVES["armor"])
    for seed in range(25):
        rng = random.Random(seed)
        b = battle(rng.sample(keys, 8), n=2, seed=seed, others=[rng.sample(keys, 6)],
                   beast=rng.choice([("Wild Boar", "normal", "brute"), ("Thunder Hawk", "elite", "swift")])
                   if False else ("Wild Boar", "normal", "brute"))
        for _ in range(60):
            if b.over:
                break
            for f in b.active():
                options = [m for m in ("strike", "guard", "break", "attack_tech", "defense_tech") if f.ready(m)]
                b.choose(f.uid, rng.choice(options))
            b.resolve()
        assert all(0 <= f.hp <= f.max_hp for f in b.fighters) and b.enemy["hp"] >= 0


# ── duels ─────────────────────────────────────────────────────────────

def duel(keys_a=(), keys_b=(), seed=0):
    a = D.make_duelist(dict(player(1, "A", keys_a), realm="Martial Warrior", layer=3), TECHS, None,
                       "Martial Warrior", 3)
    b = D.make_duelist(dict(player(2, "B", keys_b), realm="Martial Warrior", layer=3), TECHS, None,
                       "Martial Warrior", 3)
    return D.Duel(a, b, random.Random(seed))


def test_duel_passives_work_at_half_strength():
    d = duel(["lifesteal"])
    a, b = d.sides
    assert a.kit.scale == forge.DUEL_PASSIVE_STRENGTH
    a.hp = a.max_hp // 2
    d.choose(1, "strike")
    d.choose(2, "break")
    log = d.resolve()
    assert "Lifesteal" in texts(log)


def test_duel_thunder_edge_blocks_guard_next_turn():
    d = duel(["thunder_edge"])
    d.sides[0].kit.chance = lambda key, field="chance": key == "thunder_edge"
    d.choose(1, "break")
    d.choose(2, "guard")
    d.resolve()
    assert d.choose(2, "guard") and "stunned" in d.choose(2, "guard")
    assert d.choose(2, "strike") is None


def test_whole_duels_with_passives_run_to_the_end():
    keys = list(forge.PASSIVES["weapon"]) + list(forge.PASSIVES["armor"])
    for seed in range(25):
        rng = random.Random(seed)
        d = duel(rng.sample(keys, 8), rng.sample(keys, 8), seed)
        for _ in range(40):
            if d.over:
                break
            for x in d.sides:
                options = [m for m in D.CHOICES if x.ready(m)]
                d.choose(x.uid, rng.choice(options))
            d.resolve()
        assert d.over


# ── artifact passives ─────────────────────────────────────────────────

def test_artifact_passives_add_to_artifact_effects():
    p = player(artifact=["qi_flow", "lucky_coin"])
    assert gear.artifact_bonus(p, "qi_rate") == pytest.approx(0.02)
    assert gear.artifact_bonus(p, "lotus_coins") == pytest.approx(0.02)


def test_heavens_favor_and_dao_heart():
    base = dict(player(), realm="Martial Warrior", layer=9, qi=0)
    with_favor = dict(base, artifact_passives={"heavens_favor": forge.PASSIVES["artifact"]["heavens_favor"]["fx"]})
    if rules.next_gate(base)[0] == "realm":
        assert rules.breakthrough_chance(with_favor) == pytest.approx(rules.breakthrough_chance(base) + 0.05)
    dao = dict(base, artifact_passives={"dao_heart": forge.PASSIVES["artifact"]["dao_heart"]["fx"]})
    assert rules.add_toxicity(dao, 4, 3) == 5 and rules.add_toxicity(base, 4, 3) == 7


def test_treasure_sense_and_deep_pockets():
    tiers = {"wooden": 50, "bronze": 30, "silver": 15, "jade": 5}
    assert loot.chest_odds(tiers, 0, 0.20)["jade"] == pytest.approx(6)
    p = dict(player(artifact=["deep_pockets"]), lotus_coins=0)
    p["artifact_passives"]["deep_pockets"] = {"extra_chest_roll": 1.0}       # always, for the test
    notes = []
    loot.open_chest(p, "jade", random.Random(1), notes)
    assert notes and "Deep Pockets" in notes[0]


def test_fate_weaver_once_a_week(conn):
    new_player(conn)
    give_gear(conn, "artifact", "divine", passive_keys=["fate_weaver", None], equip=True)
    p = db.get_player(conn, 1)
    now = 1_800_000_000
    assert loot.fate_weaver_ready(conn, 1, p, now)
    loot.store(conn, 1, [loot.chest("bronze"), loot.chest("bronze")])
    chests = db.get_items(conn, 1, "chests")
    msg = loot.use_item(conn, 1, chests[0]["id"], random.Random(1), now)
    assert "Fate Weaver" in msg and not loot.fate_weaver_ready(conn, 1, p, now)
    assert loot.fate_weaver_ready(conn, 1, p, now + 7 * 86400)


def test_prospector_raises_material_drops():
    assert materials.prospector(player(artifact=["prospector"])) == pytest.approx(0.05)


def test_alchemy_sage_swift_hands_and_steady_hand_in_craft():
    plain = crafting.Craft("qi", "Mortal", 1, 10, random.Random(1))
    helped = crafting.Craft("qi", "Mortal", 1, 10, random.Random(1), 2, 0.5, 1)
    assert helped.max_patterns == min(9, plain.max_patterns + 1)
    assert helped.seconds == plain.seconds + 0.5 and helped.zone_width == plain.zone_width + 2


def test_second_chance_saves_a_failed_craft(conn):
    new_player(conn)
    give_gear(conn, "artifact", "spirit", passive_keys=["second_chance"], equip=True)
    loot.store(conn, 1, [dict(loot.herb("Mortal", "qi", 10), qty=2)])
    herb = db.get_items(conn, 1, "herbs")[0]
    db.remove_item(conn, herb["id"], 2)
    c = crafting.Craft("qi", "Mortal", 1, 10, random.Random(1))
    c.result = 0
    lines, _ = crafting.finish_craft(conn, 1, c, now=1_000_000, ingredients=[(herb, 2)])
    assert "Second Chance" in lines[0] and db.get_items(conn, 1, "herbs")[0]["qty"] == 2


def test_swift_hands_in_gather(conn):
    new_player(conn)
    give_gear(conn, "artifact", "ordinary", passive_keys=["swift_hands"], equip=True)
    bonus = forge.PASSIVES["artifact"]["swift_hands"]["fx"]["decision_seconds"]
    seen = 0
    for seed in range(40):
        g = gathering.Gathering(conn, 1, random.Random(seed))
        r = g._herb_round(g.player)
        if not r.old:
            assert r.seconds == alchemy.GATHER_SECONDS[r.herb["grade"]] + bonus
            seen += 1
    assert seen


# ── the equipment card ────────────────────────────────────────────────

def test_equipment_card_shows_passives_and_empty_slots(conn):
    new_player(conn)
    db.update_player(conn, 1, realm="Martial King")
    give_gear(conn, "weapon", "treasure", passive_keys=["dragons_wrath", None], equip=True)
    give_gear(conn, "artifact", "ordinary", passive_keys=["qi_flow"], equip=True)
    data = sheet.equipment_data(conn, 1)
    assert data["weapon"]["passives"] == [{"name": "Dragon's Wrath", "rarity": "Legendary",
                                           "text": forge.PASSIVES["weapon"]["dragons_wrath"]["text"]}, None]
    assert any(e["group"] == "passive" and "Qi Flow" in e["name"] for e in data["effects"])
    assert render_equipment(data).size[0] > 0
