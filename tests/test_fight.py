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


def test_techniques_spend_battle_qi_and_it_comes_back():
    b = make_battle()
    f = b.fighters[0]
    assert f.bqi == f.max_bqi == data.BATTLE_QI_START
    cost = data.TECHNIQUE_QI_COST[f.atk_t["grade"]]
    force(b, "break")                                       # a Strike into a Guard would stun now
    assert b.choose(1, "attack_tech") is None
    b.resolve()
    assert f.bqi == data.BATTLE_QI_START - cost + data.BATTLE_QI_PER_TURN
    assert b.choose(1, "attack_tech") is None              # no cooldown: usable again while Qi lasts
    f.pick = None
    f.bqi = cost - 1
    assert "Not enough Battle Qi" in b.choose(1, "attack_tech")
    f.statuses["chilled"] = 2
    assert f.qi_cost("attack_tech") == cost + data.CHILLED_QI_COST


def test_a_good_guard_gives_battle_qi_and_it_never_passes_the_max():
    b = make_battle()
    f = b.fighters[0]
    f.bqi = 10
    force(b, "strike")
    b.choose(1, "guard")
    b.resolve()
    assert f.bqi == 10 + data.BATTLE_QI_GOOD_GUARD + data.BATTLE_QI_PER_TURN
    assert any("Battle Qi" in t for _, t in b.log)
    f.bqi = f.max_bqi
    force(b, "break")
    b.choose(1, "break")
    b.resolve()
    assert f.bqi == f.max_bqi


def test_spirit_points_raise_battle_qi():
    import stats
    b = make_battle()
    p = dict(b.fighters[0].player, spirit=10)
    f = fight.Fighter(p, b.fighters[0].techs, 100, 100, 10, 5)
    assert f.max_bqi == data.BATTLE_QI_START + 10 * stats.SPIRIT_BATTLE_QI


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
    assert img.size == (1200, battle_card_height())


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
        assert render_battle(data_).size == (1200, battle_card_height())
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


def battle_card_height():
    from cards.battle import H
    return H


# ── /train in the framed card style ──────────────────────────────────

@pytest.mark.parametrize("challenge,tier", [("read_the_master", 1), ("endless_waves", 1), ("ambush", 2),
                                            ("find_the_weakness", 2)])
def test_training_steps_show_courtyard_cards(conn, challenge, tier):
    import time
    from bot import trainer
    from bot.views import TrainView
    new_player(conn)
    shown = []

    class Interaction:
        async def edit_original_response(self, **kw):
            shown.append(kw)

    async def go():
        tv = TrainView(FakeBot(conn), 1, trainer.roll_session(db.get_player(conn, 1), random.Random(0)))
        tv.session.update(challenge=challenge, tier=tier, conditions=["night_training"] if tier == 1 else [])
        tv.interaction = Interaction()
        assert tv.intro_card()["palette"] == "Courtyard"

        async def answer():
            while True:
                await asyncio.sleep(0.005)
                if tv.future and not tv.future.done():
                    tv.future.set_result(("guard", time.monotonic()))
        bot = asyncio.create_task(answer())
        run = {"read_the_master": lambda: tv.read_master(tier, tv.session["conditions"]),
               "endless_waves": lambda: tv.endless_waves(tier, tv.session["conditions"]),
               "ambush": lambda: tv.ambush(tier, tv.session["conditions"]),
               "find_the_weakness": lambda: tv.weakness(tier)}[challenge]
        await run()
        bot.cancel()
    asyncio.run(go())
    assert shown and all(kw["embed"] is None and kw["attachments"][0].filename == "train_step.jpg" for kw in shown)


def test_card_carries_the_turn_so_no_text_box_is_needed():
    from bot.fight_view import card_embed, details_embed, snapshot
    b = make_battle()
    prev = snapshot(b)
    force(b, "guard")
    b.choose(b.fighters[0].uid, "strike")
    b.resolve()
    data_ = card_data(b, "Wild beast · Step 1 of 5", prev)
    assert card_embed(data_) is None                       # nothing repeated under the card
    assert data_["party"][0]["delta"] == round(b.fighters[0].hp) - prev["party"][b.fighters[0].uid]
    assert all(i.get("short") for i in data_["loadout"])
    text = details_embed(data_).description                 # the long text still exists for the fallback
    assert "Wild Boar" in text and "**Last turn**" in text and "Iron Fist" in text
    assert render_battle(data_).size == (1200, battle_card_height())


def test_damage_numbers_and_danger_flag():
    from bot.fight_view import snapshot
    b = make_battle(("Mountain Tiger", "elite", "hunter"))
    prev = snapshot(b)
    force(b, "break")
    b.choose(b.fighters[0].uid, "strike")
    b.resolve()
    data_ = card_data(b, "x", prev)
    assert data_["enemy"]["delta"] < 0                      # the Strike landed
    b.intent = {"move": "strike", "kind": "charged", "target": b.fighters[0], "name": "x"}
    assert card_data(b, "x")["danger"] == "charged" and card_data(b, "x")["enemy"]["delta"] == 0
    b.enemy["hp"] = 0
    b.result = "won"
    assert render_battle(card_data(b, "x", prev)).size == (1200, battle_card_height())

# ── The encounter screen (cards/beast_fight.py) and the beast art ────

def test_every_beast_has_art_and_the_master_too():
    import os
    from cards.battle import ART_DIR
    names = [n for rows in beasts.BEASTS.values() for n, _, _ in rows] + ["The Master"]
    missing = [n for n in names if not os.path.exists(os.path.join(ART_DIR, beasts.slug(n) + ".png"))]
    assert missing == []


@pytest.mark.parametrize("beast,n", [(("Mountain Tiger", "beast_king", "hunter"), 1), (("Wild Boar", "normal", "brute"), 4),
                                     (("Shadow Panther", "normal", "swift"), 1)])
def test_encounter_screen_renders_fights_hunts_and_results(beast, n):
    from bot.fight_view import snapshot
    from cards.beast_fight import H as EH, W as EW, render_beast_fight
    b = make_battle(beast, n=n)
    b.enemy["slug"] = beasts.slug(beast[0])
    prev = snapshot(b)
    force(b, "break")
    for f in b.fighters:
        b.choose(f.uid, "strike")
    b.resolve()
    assert render_beast_fight(card_data(b, "x", prev)).size == (EW, EH)
    b.enemy["hp"], b.result = 0, "won"
    assert render_beast_fight(card_data(b, "x", prev)).size == (EW, EH)
    b.enemy["slug"] = None                                   # no art file: the drawn creature
    assert render_beast_fight(card_data(b, "x")).size == (EW, EH)


def test_a_strike_into_a_guard_stuns_you_for_the_next_turn():
    b = make_battle()
    force(b, "guard")
    b.choose(1, "strike")
    b.resolve()
    f = b.fighters[0]
    assert f.stunned and "stunned" in b.choose(1, "strike").lower()
    assert any("Stunned" in t for _, t in b.log)
    force(b, "guard")
    b.choose(1, "guard")
    b.resolve()
    assert not f.stunned                                    # one turn only


def test_a_good_guard_counters_a_strike():
    b = make_battle()
    before = b.enemy["hp"]
    force(b, "strike")
    b.choose(1, "guard")
    b.resolve()
    assert b.enemy["hp"] < before and any("counters for" in t for _, t in b.log)
    b = make_battle()
    force(b, "strike", "signature")                         # not against signature or charged attacks
    before = b.enemy["hp"]
    b.choose(1, "guard")
    b.resolve()
    assert b.enemy["hp"] == before


def test_a_beasts_stun_holds_on_your_next_turn():
    b = make_battle(seed=1)
    b.enemy["element"] = next(k for k, v in data.ELEMENTS.items() if v["status"] == "stunned")
    force(b, "strike", "signature")                         # a signature strike always applies its status
    b.choose(1, "strike")
    b.resolve()
    assert b.fighters[0].stunned


# ── defense techniques against a Break (technique.md) ─────────────────

def break_damage(choice, techs=TECHS):
    b = make_battle(techs=techs, seed=4)
    f = b.fighters[0]
    f.bqi = f.max_bqi
    force(b, "break")
    b.choose(1, choice)
    b.resolve()
    return f.max_hp - f.hp, b


def test_defense_technique_holds_its_block_of_a_break():
    plain, _ = break_damage("guard")
    held, b = break_damage("defense_tech")
    assert plain > 0
    assert held == pytest.approx(plain * 0.8, abs=2)                    # Mortal: holds 20%
    assert any("holds 20% of the Break" in text for _, text in b.log)


def test_unbreakable_halves_what_gets_past_the_block():
    iron = [TECHS[0], {"id": 3, "name": "Iron Cloth Body", "type": "defense", "grade": "Yellow",
                       "mastery_exp": 0, "stage": 0}]
    plain, _ = break_damage("guard", iron)
    held, _ = break_damage("defense_tech", iron)
    assert held == pytest.approx(plain * 0.75 * 0.5, abs=2)             # Yellow 25%, then half the rest


def test_without_the_rule_a_break_goes_through_as_before(monkeypatch):
    monkeypatch.setattr(data, "DEFENSE_TECH_BLOCKS_BREAK", False)
    plain, _ = break_damage("guard")
    held, _ = break_damage("defense_tech")
    assert held == plain


def test_horse_stance_guard_recovers_on_a_block():
    b = make_battle()
    f = b.fighters[0]
    f.bqi, f.hp = f.max_bqi, f.max_hp // 2
    force(b, "strike")
    b.choose(1, "defense_tech")
    b.resolve()
    assert f.hp == f.max_hp // 2 + round(f.max_hp * 0.02)


# ── technique animations on the website (web/explore_play.cast) ───────

def cast_after(tech, enemy_move):
    from web.explore_play import cast
    b = make_battle(techs=[TECHS[0], TECHS[1], tech] if tech["type"] == "attack" else [TECHS[0], tech])
    f = b.fighters[0]
    if tech["type"] == "attack":
        f.atk_t = tech
    f.bqi = f.max_bqi
    force(b, enemy_move)
    b.choose(1, f"{tech['type']}_tech")
    b.resolve()
    return cast(b, f)


def T(name, type_, grade):
    return {"id": 9, "name": name, "type": type_, "grade": grade, "mastery_exp": 0, "stage": 0}


def test_each_technique_shows_its_school_effect_and_grade():
    c = cast_after(T("Thousand Shadow Palm", "attack", "Earth"), "break")
    assert (c["school"], c["effect"], c["landed"], c["grade"]) == ("palm", "combo", True, "Earth")
    assert c["icon"] == "/art/icons/tech/thousand_shadow_palm.webp" and c["color"].startswith("#")
    c = cast_after(T("River-Splitting Finger", "attack", "Earth"), "break")
    assert (c["school"], c["effect"]) == ("finger", "pierce")
    c = cast_after(T("Moon Mirror Palm", "defense", "Mystic"), "strike")
    assert (c["school"], c["effect"], c["landed"]) == ("palmdef", "counter", True)
    c = cast_after(T("Golden Bell Cover", "defense", "Earth"), "break")
    assert (c["school"], c["effect"]) == ("body", "unbreakable")


def test_a_blocked_technique_shows_no_hit():
    c = cast_after(T("Raging Bull Fist", "attack", "Yellow"), "guard")
    assert c["landed"] is False and c["effect"] == ""


def test_a_plain_move_casts_nothing():
    from web.explore_play import cast
    b = make_battle()
    force(b, "strike")
    b.choose(1, "guard")
    b.resolve()
    assert cast(b, b.fighters[0]) is None


def test_technique_icons_are_whole_circles():
    """The 30 icons were re-cut: a centred medallion, nothing outside the circle (no stray text or paper)."""
    import glob
    from PIL import Image
    files = glob.glob("art/icons/tech/*.webp")
    assert len(files) == 30
    for path in files:
        im = Image.open(path).convert("RGBA")
        assert im.size == (160, 160)
        a = im.getchannel("A")
        for x, y in ((2, 2), (157, 2), (2, 157), (157, 157), (80, 2), (80, 157)):
            assert a.getpixel((x, y)) <= 8, path                   # corners and edges clear
        assert a.getpixel((80, 150)) >= 250 and a.getpixel((80, 10)) >= 250, path   # the full circle is there


def test_index_and_pill_icons_are_whole():
    """The /index section icons were cut off at the bottom; pills had a stray seal in a corner."""
    import glob
    import numpy as np
    from PIL import Image
    for path in glob.glob("art/icons/index/*.webp"):
        a = np.asarray(Image.open(path).convert("RGBA"))[..., 3]
        rows = np.where((a > 200).sum(1) > a.shape[1] * 0.35)[0]
        cols = np.where((a > 200).sum(0) > a.shape[0] * 0.25)[0]
        assert rows.max() - rows.min() >= cols.max() - cols.min() - 8, path      # as tall as wide: nothing cut


# ── the turn acted out on the website (web/explore_play.events, web/static/fight.js) ──

def events_after(mine, enemy_move):
    from web.explore_play import events
    b = make_battle(seed=3)
    f = b.fighters[0]
    f.bqi = f.max_bqi
    force(b, enemy_move)
    b.choose(1, mine)
    b.resolve()
    return events(b.log, f), b


def test_events_list_the_turn_in_order():
    ev, b = events_after("strike", "strike")                       # a clash: you hit, then it hits
    assert [e["who"] for e in ev] == ["me", "enemy"]
    assert ev[0]["act"] == "strike" and ev[0]["hit"] and ev[0]["dmg"] > 0
    assert ev[1] == {"who": "enemy", "act": "attack", "dmg": ev[1]["dmg"]} and ev[1]["dmg"] > 0
    f = b.fighters[0]
    assert round(f.max_hp - f.hp) == ev[1]["dmg"]                   # the number shown is the damage dealt


def test_events_for_blocked_missed_guard_and_techniques():
    ev, _ = events_after("strike", "guard")
    assert ev == [{"who": "me", "act": "strike", "hit": False, "dmg": 0, "blocked": True}]
    ev, _ = events_after("break", "strike")
    assert ev[0] == {"who": "me", "act": "break", "hit": False, "dmg": 0, "blocked": False} and ev[1]["who"] == "enemy"
    ev, _ = events_after("guard", "strike")
    assert len(ev) == 1 and ev[0]["who"] == "me" and ev[0]["act"] == "guard" and "counter" in ev[0]
    ev, _ = events_after("attack_tech", "break")
    assert ev[0] == {"who": "me", "act": "tech"}
    ev, _ = events_after("guard", "guard")
    assert ev == []
