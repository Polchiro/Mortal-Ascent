"""The Flex slot (technique.md): a third equipped technique that is its own move in every fight. It plays as a
Strike if it is an attack technique and as a Guard if it is a defense one, with that kind's rules and effects."""
import random

from bot import sparring
from bot import player as rules

from test_duel import play
from test_duel import make as make_duel
from test_duel import player as duel_player
from test_duel import tech
from test_fight import force, make_battle

ATK2 = [tech("Iron Fist", "attack", tid=1), tech("Horse Stance Guard", "defense", tid=2),
        tech("Twin Palm Strike", "attack", tid=3)]                                    # aggressive: 2 attack + 1 defense
DEF2 = [tech("Iron Fist", "attack", tid=1), tech("Horse Stance Guard", "defense", tid=2),
        tech("Parrying Arm", "defense", tid=4)]                                       # tank: 1 attack + 2 defense


def test_the_flex_technique_is_the_one_beyond_the_attack_and_defense_slots():
    atk, dfn, flex = rules.split_techniques(ATK2)
    assert (atk["name"], dfn["name"], flex["name"]) == ("Iron Fist", "Horse Stance Guard", "Twin Palm Strike")
    assert rules.split_techniques(DEF2)[2]["name"] == "Parrying Arm"
    assert rules.split_techniques(ATK2[:2])[2] is None


def test_a_flex_attack_technique_strikes_with_its_own_effect():
    b = make_battle(techs=ATK2, seed=3)
    f = b.fighters[0]
    assert f.ready("flex_tech") and f.move_label("flex_tech") == "Twin Palm Strike"
    assert f.base("flex_tech") == "strike"
    force(b, "guard")                                      # the beast holds back: the blow lands freely
    b.choose(f.uid, "flex_tech")
    log = b.resolve()
    assert any(t.startswith("F1 — Twin Palm Strike") for _, t in log)
    assert f.atk_uses == 1 and b.mastery_uses(f) == {3: 1}                             # mastery for the Flex technique


def test_a_flex_defense_technique_guards_with_its_own_effect():
    b = make_battle(techs=DEF2, seed=4)
    f = b.fighters[0]
    assert f.base("flex_tech") == "guard"
    force(b, "strike")
    b.choose(f.uid, "flex_tech")
    log = b.resolve()
    line = next(t for _, t in log if t.startswith("F1 — Parrying Arm"))
    assert "blocked" in line and "countered" in line                                  # Parrying Arm's counter
    assert b.mastery_uses(f) == {4: 1}


def test_the_flex_technique_costs_battle_qi_and_is_refused_without_it():
    b = make_battle(techs=ATK2)
    f = b.fighters[0]
    f.bqi = f.qi_cost("flex_tech") - 1
    assert b.choose(f.uid, "flex_tech").startswith("Not enough Battle Qi")
    b2 = make_battle()                                    # no Flex technique equipped
    assert b2.choose(b2.fighters[0].uid, "flex_tech") == "You have no technique in that slot."


def test_three_techniques_in_a_duel():
    d = make_duel(techs1=ATK2, techs2=DEF2)
    a, b = d.sides
    assert a.base("flex_tech") == "strike" and b.base("flex_tech") == "guard"
    log = play(d, "flex_tech", "flex_tech")
    assert any("Twin Palm Strike" in t for _, t in log) and any("Parrying Arm" in t for _, t in log)
    assert a.cooldowns["flex_tech"] > 0 and a.cooldowns["attack_tech"] == 0            # each slot rests on its own
    assert d.history[-1]["moves"][0]["move"] == "attack_tech"                          # recorded by its kind
    assert d.history[-1]["moves"][1]["move"] == "defense_tech"
    assert d.choose(a.uid, "flex_tech").startswith("That technique is still recovering")
    assert d.choose(a.uid, "attack_tech") is None                                      # the Attack slot is still free


def test_a_duelist_without_a_flex_technique_is_refused():
    d = make_duel()
    assert d.choose(d.sides[0].uid, "flex_tech") == "You have no technique of that kind equipped."


def test_sparring_offers_the_flex_technique():
    p = dict(duel_player(1, "Ana"), strength=0, vitality=0, spirit=0, weapon_id=None)
    sp = sparring.Spar(p, ATK2, rng=random.Random(1))
    assert ("flex_tech", "Twin Palm Strike") in sp.choices()
    sp.master = "guard"
    sp.play("flex_tech")
    assert sp.cooldowns["flex_tech"] > 0 and sp.cooldowns["attack_tech"] == 0
