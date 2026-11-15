"""The beast roar as a move of its own (battle.ROAR, bot/fight.py `_roars`, `_roar`): only four-legged beasts, never
early, by tier, more likely when pressed or wounded, a final roar near death, a cooldown; a Guard halves it and shrugs
off its effects. Other beasts fight exactly as before."""
import random

import battle
import beasts
from bot import fight

from test_fight import make_battle


def plan_until_roar(b, turns=60):
    for _ in range(turns):
        b.enemy_turns += 1
        if b._roars():
            return b.enemy_turns
    return None


def test_only_four_legged_flying_and_serpent_beasts_roar_and_never_in_their_first_turns():
    b = make_battle(beast=("Stone-Shell Tortoise", "normal", "armored"))
    assert plan_until_roar(b, 200) is None
    for seed in range(40):
        b = make_battle(beast=("Wild Boar", "normal", "brute"), seed=seed)
        b.enemy_turns = 0
        first = plan_until_roar(b, 200)
        assert first is None or first > battle.ROAR_QUIET_TURNS


def test_roars_get_rarer_by_tier_and_have_a_cooldown():
    def roars(tier, turns=3000):
        b = make_battle(beast=("Grey Wolf", tier, "hunter"))
        b.enemy_turns, n, last = battle.ROAR_QUIET_TURNS, 0, -99
        for _ in range(turns):
            b.enemy_turns += 1
            if b._roars():
                assert b.enemy_turns - last > battle.ROAR_COOLDOWN
                n, last = n + 1, b.enemy_turns
        return n
    normal, elite, king = roars("normal"), roars("elite"), roars("beast_king")
    assert 0 < normal < elite < king


def test_pressing_or_wounding_it_makes_a_roar_likelier():
    def rate(streak=0, hp=1.0, tries=4000):
        n = 0
        for i in range(tries):
            b = make_battle(beast=("Grey Wolf", "normal", "hunter"), seed=i)
            b.enemy_turns, b.attack_streak = 10, streak
            b.enemy["hp"] = b.enemy["max_hp"] * hp
            n += b._roars()
        return n / tries
    base, pressed, wounded = rate(), rate(streak=2), rate(hp=0.6)
    n = battle.ROAR["normal"]["chance"]
    assert abs(base - n) < 0.03 and abs(pressed - (n + battle.ROAR_STREAK_BONUS)) < 0.03
    assert abs(wounded - (n + battle.ROAR_WOUNDED_BONUS)) < 0.03


def test_the_final_roar_comes_once_near_death_and_hits_harder():
    b = make_battle(beast=("Wild Boar", "normal", "brute"), seed=3)
    b.enemy["hp"] = b.enemy["max_hp"] * 0.15
    b.enemy_turns = 10
    finals = 0
    for _ in range(50):
        b.enemy_turns += 1
        if b._roars() and b.roared["final"] == b.enemy_turns:
            finals += 1
    assert finals == 1


def roar_turn(tier, pick, final=False, seed=0):
    b = make_battle(beast=("Wild Boar", tier, "brute"), seed=seed)
    f = b.fighters[0]
    b.intent = {"move": "roar", "kind": "normal", "target": f, "skill": None, "name": "Roar", "final": final}
    hp = f.hp
    b.choose(f.uid, pick)
    log = b.resolve()
    return f, hp - f.hp, log


def test_what_a_roar_does_by_tier_and_that_a_guard_halves_it():
    f, dmg, log = roar_turn("normal", "strike")
    assert dmg > 0 and "shaken" in f.statuses and "stunned" not in f.statuses
    assert any(i == "roar" and "— Roar on" in t for i, t in log)
    f, dmg_k, _ = roar_turn("beast_king", "strike")
    assert "exposed" in f.statuses and "stunned" in f.statuses and dmg_k > dmg
    f, guarded, _ = roar_turn("beast_king", "guard")
    assert not f.statuses and 0 < guarded < dmg_k
    _, final, log = roar_turn("normal", "strike", final=True)
    assert final > dmg and any("— Final Roar on" in t for _, t in log)


def test_your_move_lands_in_full_while_it_roars():
    b = make_battle(beast=("Wild Boar", "normal", "brute"), seed=1)
    f = b.fighters[0]
    b.intent = {"move": "roar", "kind": "normal", "target": f, "skill": None, "name": "Roar", "final": False}
    hp = b.enemy["hp"]
    b.choose(f.uid, "strike")
    log = b.resolve()
    assert b.enemy["hp"] < hp and not any("clash" in t or "missed" in t for _, t in log)


def test_shaken_and_exposed_change_damage():
    b = make_battle(beast=("Wild Boar", "normal", "brute"))
    f = b.fighters[0]
    assert fight.status_mult(f, "attack_mult") == 1.0
    f.statuses["shaken"] = 2
    f.statuses["exposed"] = 2
    assert fight.status_mult(f, "attack_mult") == battle.STATUSES["shaken"]["attack_mult"]
    assert fight.status_mult(f, "defense_mult") == battle.STATUSES["exposed"]["defense_mult"]


def test_a_beast_that_cannot_roar_fights_exactly_as_before():
    b1 = make_battle(beast=("Stone-Shell Tortoise", "normal", "armored"), seed=9)
    rolls = [b1.rng.random() for _ in range(5)]
    b2 = make_battle(beast=("Stone-Shell Tortoise", "normal", "armored"), seed=9)
    b2.enemy_turns = 20
    b2._roars()
    assert [b2.rng.random() for _ in range(5)] == rolls                      # its own dice: the fight's untouched


def test_most_fights_see_a_roar():
    """Not a rare sight: two in three Normal fights, nearly every Elite and Beast King fight (several times)."""
    def share(tier, n=150):
        seen = roars = 0
        for seed in range(n):
            b = make_battle(beast=("Sky Lynx", tier, "hunter"), seed=seed)
            f = b.fighters[0]
            f.hp = f.max_hp = f.max_hp * 5
            got = 0
            while not b.over and b.turn < 40:
                b.choose(f.uid, random.Random(seed * 99 + b.turn).choice(["strike", "strike", "break", "guard"]))
                got += sum("Roar on" in t for _, t in b.resolve())
            seen += got > 0
            roars += got
        return seen / n, roars / n
    assert share("normal")[0] > 0.55
    assert share("elite")[0] > 0.9 and share("beast_king")[1] > 2
