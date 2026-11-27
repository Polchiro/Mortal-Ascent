"""Free technique slots (technique.md "Slots", Shoaib Nov 28): three slots that each take an attack or a defense
technique, the third from Martial Warrior; you pick the slot; no minimum. Fights play each slot by its own kind."""
import random

import pytest

from bot import combat, db, duel, fight
from bot import player as rules

A = 1


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    db.create_player(c, A, "Lin Yue", "Gifted", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return c


def names(c):
    return {s: t["name"] for s, t in db.slotted(db.get_techniques(c, A)).items()}


def learn(c, name, type_="attack", grade="Mortal"):
    return db.learn_technique(c, A, name, type_, grade, equip=False)


def test_old_equips_keep_the_slots_they_held(conn):
    assert names(conn) == {1: "Iron Fist", 2: "Horse Stance Guard"}           # attack in 1, defense in 2, as before


def test_any_kind_in_any_slot_and_you_pick_it(conn):
    db.update_player(conn, A, realm="Martial Warrior")
    a, b = learn(conn, "Twin Palm Strike"), learn(conn, "Crescent Sweep")
    assert db.equip_technique(conn, A, a, 3, slot=2) == "Horse Stance Guard"   # an attack into the defense's old slot
    assert db.equip_technique(conn, A, b, 3, slot=3) is None
    assert names(conn) == {1: "Iron Fist", 2: "Twin Palm Strike", 3: "Crescent Sweep"}   # three attacks
    assert db.get_technique(conn, A, a)["slot"] == 2


def test_slot_three_waits_for_martial_warrior(conn):
    a = learn(conn, "Twin Palm Strike")
    assert db.equip_technique(conn, A, a, 2, slot=3) is None and not db.get_technique(conn, A, a)["equipped"]


def test_no_slot_picked_fills_a_free_one_else_the_oldest(conn):
    a = learn(conn, "Twin Palm Strike")
    assert db.equip_technique(conn, A, a, 2) == "Iron Fist"                   # both full: the one on longest
    assert names(conn) == {1: "Twin Palm Strike", 2: "Horse Stance Guard"}


def test_every_slot_can_be_emptied(conn):
    for t in db.get_techniques(conn, A):
        assert db.unequip_technique(conn, A, t["id"])
    assert db.get_techniques(conn, A) == [] and rules.split_techniques([]) == (None, None, None)


def test_a_fight_plays_each_slot_by_its_kind(conn):
    db.update_player(conn, A, realm="Martial Warrior")
    for n, name in ((2, "Twin Palm Strike"), (3, "Crescent Sweep")):
        db.equip_technique(conn, A, learn(conn, name), 3, slot=n)
    techs = db.get_techniques(conn, A)
    p = dict(db.get_player(conn, A))
    hp, atk, dfn = rules.base_stats("Mortal", 1)
    f = fight.Fighter(p, techs, hp, hp, atk, dfn)
    assert [f.tech(k)["name"] for k in fight.TECH_KEYS] == ["Iron Fist", "Twin Palm Strike", "Crescent Sweep"]
    assert [f.base(k) for k in fight.TECH_KEYS] == ["strike", "strike", "strike"]         # three Strikes
    d = duel.Duelist(p, techs, hp, atk, dfn)
    assert d.base("defense_tech") == "strike" and d.recorded("defense_tech") == "attack_tech"


def test_three_defenses_guard_from_every_slot(conn):
    db.update_player(conn, A, realm="Martial Warrior")
    iron = next(t for t in db.get_techniques(conn, A) if t["name"] == "Iron Fist")
    db.equip_technique(conn, A, learn(conn, "Parrying Arm", "defense"), 3, slot=1)
    db.equip_technique(conn, A, learn(conn, "Calm Breath Stance", "defense"), 3, slot=3)
    assert not db.get_technique(conn, A, iron["id"])["equipped"]
    techs = db.get_techniques(conn, A)
    hp, atk, dfn = rules.base_stats("Mortal", 1)
    f = fight.Fighter(dict(db.get_player(conn, A)), techs, hp, hp, atk, dfn)
    assert [f.base(k) for k in fight.TECH_KEYS] == ["guard", "guard", "guard"]
    beast = ("Wild Boar", "normal", "brute")
    enemy = fight.enemy_from_beast(combat.beast_stats(f.player, beast), beast[0])
    b = fight.Battle([f], enemy, random.Random(0))
    from web.explore_play import actions
    techs_menu = next(x for x in actions(b, f)[0] if x["key"] == "techniques")["techs"]
    assert [t["key"] for t in techs_menu] == ["attack_tech", "defense_tech", "flex_tech"]   # all three slots offered
