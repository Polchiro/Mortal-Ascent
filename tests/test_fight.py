"""Interactive turn-based fights: turn resolution, explore and hunt hooks, the fight card (docs/combat.md)."""
import asyncio
import random

import pytest

import battle as data
import beasts
from bot import combat, db, fight, hunt
from bot import player as rules
from bot.expedition import Expedition
from bot.fight_view import card_data
from cards.battle import render_battle, scene

from test_exploits import FakeBot, FakeInteraction, new_player


@pytest.fixture
def conn():
    return db.connect(":memory:")


def player(uid=1, name="Shoaib", realm="Mortal", layer=1):
    return {"user_id": uid, "name": name, "realm": realm, "layer": layer}


TECHS = [{"id": 1, "name": "Iron Fist", "type": "attack", "grade": "Mortal", "mastery_exp": 0, "stage": 0},
         {"id": 2, "name": "Horse Stance Guard", "type": "defense", "grade": "Mortal", "mastery_exp": 0, "stage": 0}]


def make_battle(beast=("Wild Boar", "normal", "brute"), n=1, seed=0, techs=TECHS, pills=None):
    fighters = []
    for i in range(n):
        p = player(i + 1, f"F{i + 1}")
        hp, atk, dfn = rules.base_stats("Mortal", 1)
        fighters.append(fight.Fighter(p, techs, hp, hp, atk, dfn, pills=[dict(x) for x in (pills or [])]))
    enemy = fight.enemy_from_beast(combat.beast_stats(fighters[0].player, beast), beast[0])
    enemy["realm"] = "Mortal"
    enemy["dodge"] = 0
    return fight.Battle(fighters, enemy, random.Random(seed))


def force(b, move, kind="normal", target=0):
    b.enemy["statuses"].clear()
    b.intent = {"move": move, "kind": kind, "target": b.fighters[target], "name": "Test Move"}


# ── data ──────────────────────────────────────────────────────────────

def test_every_beast_has_an_element_and_a_body_type():
    names = [b[0] for realm in beasts.BEASTS.values() for b in realm]
    assert set(names) == set(beasts.TRAITS)
    for name in names:
        element, body = beasts.TRAITS[name]
        assert element in beasts.ELEMENTS and body in beasts.BODY_TYPES
    assert set(beasts.ELEMENTS) == set(data.ELEMENTS)
    assert beasts.slug("Flood Dragon (Jiao)") == "flood_dragon_jiao"


def test_every_element_has_a_status_and_a_palette():
    from cards import theme
    for name, el in data.ELEMENTS.items():
        assert el["status"] in data.STATUSES
        assert name in theme.ELEMENT_ACCENTS
    for weights in data.MOVE_WEIGHTS.values():
        assert sum(weights.values()) == pytest.approx(1.0)


# ── counters ──────────────────────────────────────────────────────────

def test_guard_beats_strike():
    b = make_battle()
    force(b, "strike")
    b.choose(1, "guard")
    b.resolve()
    f = b.fighters[0]
    assert f.hp == f.max_hp


def test_strike_beats_break():
    b = make_battle()
    force(b, "break")
    b.choose(1, "strike")
    b.resolve()
    assert b.fighters[0].hp == b.fighters[0].max_hp and b.enemy["hp"] < b.enemy["max_hp"]


def test_break_beats_guard_and_staggers():
    b = make_battle()
    force(b, "guard")
    b.choose(1, "break")
    b.resolve()
    assert b.enemy["hp"] < b.enemy["max_hp"]
    assert b.intent is None and "Staggered" in b.status_chips()      # it loses its next turn
    hp = b.enemy["hp"]
    b.choose(1, "strike")
    b.resolve()
    assert b.enemy["hp"] < hp and b.fighters[0].hp == b.fighters[0].max_hp
    assert "Staggered" not in b.status_chips()


def test_losing_the_exchange_hurts_and_the_cap_holds():
    b = make_battle()
    force(b, "strike")
    b.choose(1, "break")
    b.resolve()
    f = b.fighters[0]
    assert 0 < f.max_hp - f.hp <= f.max_hp * 0.3 + 1


def test_strike_into_a_guard_does_nothing():
    b = make_battle()
    force(b, "guard")
    b.choose(1, "strike")
    b.resolve()
    assert b.enemy["hp"] == b.enemy["max_hp"]


# ── charged attacks ───────────────────────────────────────────────────

def test_charged_attack_ignores_the_cap_unless_guarded_or_broken():
    hits = {}
    for move in ("strike", "guard", "break"):
        b = make_battle(("Grey Wolf", "elite", "hunter"), seed=1)
        b.enemy["attack"] *= 1.5
        force(b, "strike", "charged")
        b.choose(1, move)
        b.resolve()
        hits[move] = b.fighters[0].max_hp - b.fighters[0].hp
    assert hits["strike"] > b.fighters[0].max_hp * 0.3          # no 30% cap
    assert 0 < hits["guard"] <= hits["strike"] * (1 - data.CHARGE_GUARD_BLOCK) + 1
    assert hits["break"] == 0                                     # interrupted


def test_charged_attack_hits_the_whole_party():
    b = make_battle(("Grey Wolf", "elite", "hunter"), n=3)
    force(b, "strike", "charged")
    for f in b.fighters:
        b.choose(f.uid, "strike")
    b.resolve()
    assert all(f.hp < f.max_hp for f in b.fighters)


def test_elites_telegraph_every_third_turn():
    b = make_battle(("Grey Wolf", "elite", "hunter"), seed=3)
    kinds = []
    for _ in range(6):
        kinds.append(b.intent["kind"] if b.intent else "staggered")
        b.choose(1, "guard")
        b.resolve()
        if b.over:
            break
    assert kinds[2] == "charged" and kinds[5] == "charged"
    assert "Charged attack" in fight_warning_after(2)


def fight_warning_after(turns):
    b = make_battle(("Grey Wolf", "elite", "hunter"), seed=3)
    for _ in range(turns):
        b.choose(1, "guard")
        b.resolve()
    return b.warning[1]


# ── timer, techniques, pills, statuses ────────────────────────────────

def test_timeout_guards_and_three_timeouts_flee():
    b = make_battle()
    force(b, "strike")
    b.resolve()                                   # nobody picked: Guard
    f = b.fighters[0]
    assert f.hp == f.max_hp and f.last_move == "Guard"
    b.resolve()
    b.resolve()
    assert f.fled and b.result == "fled"


def test_picking_resets_the_timeout_count():
    b = make_battle()
    b.resolve()
    b.resolve()
    b.choose(1, "guard")
    b.resolve()
    b.resolve()
    assert not b.over


def test_technique_cooldown_and_chilled():
    b = make_battle()
    force(b, "guard")
    assert b.choose(1, "attack_tech") is None
    b.resolve()
    assert "recovering" in b.choose(1, "attack_tech")
    b.fighters[0].pick = None
    force(b, "guard")
    b.choose(1, "guard")
    b.resolve()
    assert b.choose(1, "attack_tech") is None              # Mortal: rests 1 turn
    b.fighters[0].statuses["chilled"] = 2
    force(b, "guard")
    b.resolve()
    assert b.fighters[0].cooldowns["attack_tech"] == 2      # +1 while Chilled


def test_pills_heal_and_are_limited():
    pills = [{"id": 5, "name": "Mending Pill", "heal": 0.3, "qty": 3}]
    b = make_battle(pills=pills)
    f = b.fighters[0]
    assert "no Mending pill" in b.choose(1, "pill")         # full HP: nothing to heal
    f.hp = 10
    for _ in range(2):
        force(b, "guard")
        assert b.choose(1, "pill") is None
        b.resolve()
    assert f.hp == 10 + 2 * round(f.max_hp * 0.3) and f.pills[0]["used"] == 2
    f.hp = 10
    assert b.choose(1, "pill") is not None                  # PILLS_PER_FIGHT reached


def test_flame_signature_burns_and_burning_ticks():
    b = make_battle(("Ember Lizard", "normal", "swift"))
    force(b, "strike", "signature")
    b.choose(1, "break")                                    # loses to the strike
    b.resolve()
    f = b.fighters[0]
    assert "burning" in f.statuses
    hp = f.hp
    force(b, "guard")
    b.choose(1, "guard")
    b.resolve()
    assert f.hp == hp - round(f.max_hp * data.STATUSES["burning"]["dot"])


def test_shadow_hides_and_break_reveals():
    b = make_battle(("Shadow Panther", "normal", "swift"))
    force(b, "guard")
    b.enemy["statuses"]["hidden"] = 2
    b.choose(1, "strike")
    b.resolve()
    assert b.enemy["hp"] == b.enemy["max_hp"]
    b.intent = {"move": "guard", "kind": "normal", "target": b.fighters[0], "name": "Guard"}
    b.choose(1, "break")
    b.resolve()
    assert b.enemy["hp"] < b.enemy["max_hp"] and "hidden" not in b.enemy["statuses"]


def test_stunned_fighter_can_only_guard():
    b = make_battle()
    b.fighters[0].statuses["stunned"] = 1
    assert "stunned" in b.choose(1, "strike")
    assert b.choose(1, "guard") is None


def test_team_turn_waits_for_every_member():
    b = make_battle(n=3)
    b.choose(1, "strike")
    b.choose(2, "guard")
    assert not b.all_picked() and [f.uid for f in b.waiting_for()] == [3]
    b.choose(3, "break")
    assert b.all_picked()


def test_winning_a_fight_reports_won():
    b = make_battle()
    b.enemy["hp"] = 1
    force(b, "guard")
    b.choose(1, "break")
    b.resolve()
    assert b.result == "won" and b.over


def test_turn_limit_lets_the_enemy_escape():
    b = make_battle()
    b.turn = data.MAX_TURNS["normal"]
    force(b, "guard")
    b.choose(1, "guard")
    b.resolve()
    assert b.result == "escaped"


# ── /explore and hunts ────────────────────────────────────────────────

def test_wild_beast_starts_an_interactive_fight_and_pays_on_win(conn):
    new_player(conn)
    e = Expedition(conn, 1, random.Random(2))
    e.next_step()
    e.paths["left"] = ("wild_beast", "clue")
    e.choose("left")
    assert e.pending == "fight" and e.battle.enemy["element"] in beasts.ELEMENTS
    assert not e.can_go_deeper
    e.battle.enemy["hp"] = 0
    e.battle.result = "won"
    e.end_fight()
    assert e.pending is None and e.beasts_slain == 1 and e.coins > 0 and e.can_go_deeper


def test_fleeing_a_beast_keeps_the_expedition_going(conn):
    new_player(conn)
    e = Expedition(conn, 1, random.Random(2))
    e.next_step()
    e._wild_beast()
    e.battle.result = "fled"
    e.end_fight()
    assert not e.over and e.beasts_slain == 0 and "escape" in e.story[0]


def test_losing_to_bandits_robs_and_ends_the_expedition(conn):
    new_player(conn)
    db.update_player(conn, 1, lotus_coins=1000)
    e = Expedition(conn, 1, random.Random(2))
    e.next_step()
    e._bandits()
    e.battle.fighters[0].hp = 0
    e.battle.result = "lost"
    e.end_fight()
    assert e.over and e.defeated and db.get_player(conn, 1)["lotus_coins"] < 1000 + 1000


def test_pills_swallowed_in_a_fight_leave_the_bag(conn):
    from bot import crafting, loot
    new_player(conn)
    loot.store(conn, 1, [dict(crafting.crafted_pill("mending", "Mortal", 5), qty=2)])
    pills = crafting.fight_pills(conn, 1)
    assert pills and pills[0]["heal"] == pytest.approx(0.30 * 1.05)
    e = Expedition(conn, 1, random.Random(2))
    e.next_step()
    e._wild_beast()
    f = e.battle.fighters[0]
    f.hp = 5
    force(e.battle, "guard")
    assert e.battle.choose(1, "pill") is None
    e.battle.resolve()
    crafting.bank_fight_pills(conn, f)
    crafting.bank_fight_pills(conn, f)                       # twice: still only one pill taken
    assert sum(i["qty"] for i in db.get_items(conn, 1, "pills")) == 1


def test_hunt_battle_pays_winners_but_not_those_who_fled(conn):
    for uid in (1, 2, 3):
        new_player(conn, uid)
    p = db.get_player(conn, 1)
    lair = hunt.roll_lair(p, "beast_king", random.Random(0))
    b = hunt.start_battle(conn, lair, [1, 2, 3], random.Random(0))
    assert b.team and b.enemy["tier"] == "beast_king"
    b.fighters[2].fled = True
    b.enemy["hp"] = 0
    b.result = "won"
    lines, news = hunt.pay(conn, lair, b)
    assert db.get_player(conn, 1)["beasts_slain"] == 1 and db.get_player(conn, 3)["beasts_slain"] == 0
    assert "Mortal" in rules.king_kills(db.get_player(conn, 2))
    assert news and "fled" in lines[-1]


def test_explore_view_plays_a_fight_with_buttons(conn):
    from bot.views import ExploreView
    new_player(conn)

    async def go():
        view = ExploreView(FakeBot(conn), 1, random.Random(0))
        view.exp.paths["left"] = ("wild_beast", "clue")
        await view.children[0].callback(FakeInteraction())
        assert view.exp.pending == "fight"
        assert [c.label for c in view.children][:3] == ["Strike", "Guard", "Break"]
        for _ in range(60):
            if not view.fight:
                break
            b = view.fight
            counter = {"strike": "guard", "guard": "break", "break": "strike"}[b.intent["move"]] if b.intent else "strike"
            button = next(c for c in view.children if getattr(c, "fight_key", None) == counter)
            await button.callback(FakeInteraction())
        assert view.exp.pending is None and view.exp.last_battle.over
        view.stop_fight()
    asyncio.run(go())


# ── the card ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("element,body", [(el, body) for el, body in zip(beasts.ELEMENTS, beasts.BODY_TYPES)]
                         + [("Blood", "human")])
def test_fight_card_renders_every_element_and_body(element, body):
    b = make_battle(n=1 if body != "dragon" else 3)
    b.enemy["element"], b.enemy["body"] = element, body
    img = render_battle(card_data(b, "Wild beast · Step 1 of 5"))
    assert img.size == (1200, 860)


def test_scene_is_cached():
    scene.cache_clear()
    scene("Frost", "cat", None)
    scene("Frost", "cat", None)
    assert scene.cache_info().hits == 1


# ── /spar on the fight screen ─────────────────────────────────────────

def test_spar_card_renders_with_the_master(conn):
    from bot.views import SparView
    new_player(conn)

    async def go():
        sv = SparView(FakeBot(conn), 1, rng=random.Random(0))
        sv.last = sv.spar.play("guard")
        data_ = sv.fight_card()
        assert data_["palette"] == "Master" and data_["enemy"]["body"] == "master"
        assert render_battle(data_).size == (1200, 860)
    asyncio.run(go())


def test_spar_timeouts_guard_then_forfeit(conn):
    from bot.views import SparView
    new_player(conn)

    async def go():
        sv = SparView(FakeBot(conn), 1, rng=random.Random(0))
        for i in range(3):
            sv._deadline = 0
            await sv._spar_timer(sv.spar.turn)
            if i < 2:
                assert not sv.result and sv.last_move == "Guard"
        assert sv.result and "walked away" in sv.result
        sv._cancel_timer()
    asyncio.run(go())
