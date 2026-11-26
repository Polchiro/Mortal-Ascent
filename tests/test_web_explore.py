"""Exploring and fighting on the website (docs/web.md, "Explore"): the bot's expedition and fight engines."""
import random
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import battle as battle_rules  # noqa: E402
from bot import db  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

UID = 795


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, realm="Martial Apprentice", layer=3)
    c.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "s", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=db_path, session_secret="s"))
    c = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c.get("/login").headers["location"]).query)
    c.get("/callback", params={"code": "x", "state": q["state"][0]})
    import time
    c.now = [time.time()]
    app.state.explores.clock = lambda: c.now[0]
    app.state.explores.rng_factory = lambda: random.Random(7)
    c.explores = app.state.explores
    c.path = db_path
    return c


def run(client):
    return client.explores.get(UID)


def act(client, what, arg=""):
    return client.post("/explore/act", data={"what": what, "arg": arg, "turn": run(client).turn})


def force_paths(client, enc):
    e = run(client).exp
    e.paths = {p: (enc, "A clue.") for p in e.paths}


def begin(client):
    r = client.post("/explore/begin")
    assert r.headers["location"] == "/explore/play"
    return run(client)


def test_explore_page_and_setting_out_starts_the_rest(client):
    page = client.get("/explore").text
    assert "Solo Hunt" in page and "Find a Team" in page and 'href="/explore"' in page     # the hunting entry
    begin(client)
    page = client.get("/explore/play").text
    assert "THREE PATHS LIE AHEAD" in page and "Return safely" in page
    c = db.connect(client.path)
    assert db.cooldown_left(c, UID, "explore") > 0                 # Discord can't start a second one meanwhile
    c.close()
    assert client.get("/explore").headers["location"] == "/explore/play"


def test_rest_or_injury_blocks_setting_out(client):
    c = db.connect(client.path)
    db.set_cooldown(c, UID, "explore", 600)
    c.close()
    assert "resting from the last expedition" in client.get("/explore").text
    r = client.post("/explore/begin")
    assert r.headers["location"] == "/explore" and run(client) is None


def fight(client):
    begin(client)
    force_paths(client, "wild_beast")
    act(client, "path", "left")
    s = run(client)
    assert s.battle is not None
    return s


def test_a_beast_fight_shows_the_fight_screen(client):
    s = fight(client)
    page = client.get("/explore/play").text
    e = s.battle.enemy
    assert e["name"] in page and f"/art/beasts/{e['slug']}.png" in page
    for label in ("Strike", "Guard", "Break", "Flee", "Iron Fist", "Horse Stance Guard"):
        assert label in page, label
    assert page.count('class="actbtn') == 4 and "BATTLE HISTORY" in page and "blog" not in page             # Strike, Techniques, Guard, Break
    assert page.count('class="sidebtn') == 2 and "Techniques" in page             # Pill and Flee on the side
    assert 'id="tfill"' not in page and "no turn timer" in page
    assert client.get(f"/art/beasts/{e['slug']}.png").status_code == 200
    assert client.get("/art/icons/actions/break.webp").status_code == 200


def test_a_move_plays_one_turn_with_the_engine(client):
    s = fight(client)
    b = s.battle
    turn, t0 = s.turn, b.turn
    act(client, "move", "break")
    assert b.turn == t0 + 1 and s.turn > turn and b.log
    page = client.get("/explore/play").text
    assert f"Turn {t0}" in page and 'class="toast' in page                  # this turn called out, and in the history


def test_old_pages_and_impossible_moves_are_ignored(client):
    s = fight(client)
    b = s.battle
    t0 = b.turn
    client.post("/explore/act", data={"what": "move", "arg": "strike", "turn": s.turn - 1})
    act(client, "move", "dance")
    assert b.turn == t0
    b.fighters[0].statuses["stunned"] = 2
    act(client, "move", "strike")                                    # refused: stunned
    assert b.turn == t0 and "stunned" in client.get("/explore/play").text.lower()
    act(client, "path", "left")                                      # no path while fighting
    assert s.battle is b


def test_no_reaction_time_but_a_forgotten_fight_still_ends(client):
    from web import explore_play
    s = fight(client)
    b = s.battle
    t0 = b.turn
    client.now[0] += battle_rules.TURN_SECONDS * 4                # thinking is fine: the turn waits
    client.get("/explore/play")
    assert b.turn == t0
    client.now[0] += explore_play.TURN_LIMIT
    client.get("/explore/play")
    assert b.turn == t0 + 1 and any("hesitated" in t for _, t in b.history[-1])


def test_a_turn_shows_the_result_word(client):
    s = fight(client)
    b = s.battle
    b.intent = {"move": "strike", "kind": "normal", "target": b.fighters[0], "name": "Strike"}
    act(client, "move", "guard")
    page = client.get("/explore/play").text
    assert "Countered!" in page or s.battle is None


def test_winning_ends_the_fight_and_the_expedition_goes_on(client):
    s = fight(client)
    b = s.battle
    for _ in range(40):
        if s.battle is None:
            break
        b.enemy["hp"] = 1
        b.enemy["statuses"].clear()
        b.intent = {"move": "break", "kind": "normal", "target": b.fighters[0], "name": "Break"}
        act(client, "move", "strike")
    assert s.battle is None and s.exp.beasts_slain == 1
    assert "Victory!" in client.get("/explore/play").text       # the victory sequence comes first
    act(client, "continue")
    page = client.get("/explore/play").text
    assert "falls" in page and ("Go deeper" in page or "Return safely" in page)


def test_return_home_banks_and_back_clears(client, db_path):
    s = begin(client)
    force_paths(client, "peaceful_clearing")
    act(client, "path", "middle")
    act(client, "return")
    assert s.exp.over
    page = client.get("/explore/play").text
    assert "You return safely" in page and "Back" in page
    assert client.get("/explore").headers.get("location") is None          # finished: the start page again
    client.post("/explore/done")
    assert run(client) is None
    assert "resting from the last expedition" in client.get("/explore").text


def test_a_hazard_is_timed_from_when_it_is_seen(client):
    s = begin(client)
    force_paths(client, "hazard")
    act(client, "path", "left")
    assert s.exp.pending == "hazard"
    client.get("/explore/play")                                       # on screen: the clock starts
    assert s.exp.hazard["shown_at"] == client.now[0]
    hp = s.exp.hp
    client.now[0] += 10
    client.get("/explore/play")
    assert s.exp.pending is None and s.exp.hp < hp


def test_walking_away_ends_the_expedition(client):
    s = begin(client)
    client.now[0] += 1000
    assert "night falls" in client.get("/explore/play").text and s.exp.over


def test_a_lair_can_be_hunted_alone_after_the_expedition(client, db_path):
    s = begin(client)
    force_paths(client, "elite_lair")
    act(client, "path", "right")
    assert s.exp.lair and "hunt it alone" in client.get("/explore/play").text
    act(client, "return")
    page = client.get("/explore/play").text
    assert "Hunt it alone" in page and s.exp.lair["beast"][0] in page
    act(client, "hunt")
    assert s.lair_battle is not None
    page = client.get("/explore/play").text
    assert "Elite lair" in page and page.count('class="actbtn') == 4
    act(client, "move", "flee")
    for _ in range(20):
        if s.lair_result is not None:
            break
        act(client, "move", "flee")
    assert s.lair_result is not None
    assert "Back" in client.get("/explore/play").text


def test_a_technique_turn_plays_its_own_animation(client):
    s = fight(client)
    b = s.battle
    f = b.fighters[0]
    f.bqi = f.max_bqi
    b.enemy["statuses"].clear()
    b.intent = {"move": "break", "kind": "normal", "target": f, "name": "Break"}
    act(client, "move", "attack_tech")
    page = client.get("/explore/play").text
    assert "casting cast-attack cast-fist" in page and "cast-landed" in page
    assert 'class="castcall"' in page and "Mortal technique" in page and "--tc: #" in page


def test_the_fight_scene_has_the_poses_and_the_turns_events(client):
    s = fight(client)
    b = s.battle
    b.enemy["statuses"].clear()
    b.intent = {"move": "break", "kind": "normal", "target": b.fighters[0], "name": "Break"}
    act(client, "move", "strike")
    page = client.get("/explore/play").text
    for pose in ("windup", "strike"):                                  # (the idle still gives way to his stance loop)
        assert f'class="pose p-{pose}" src="/art/portraits/fight/hero_male_{pose}.webp"' in page
    assert 'src="/art/fx/slash.webp"' in page and client.get("/art/fx/slash.webp").status_code == 200
    assert 'data-pose="idle"' in page and 'data-bar="me"' in page and 'data-bar="enemy"' in page
    assert "data-events='[{" in page and '"act": "strike"' in page


def test_the_male_sword_attack_plays_frame_by_frame(client):
    import looks
    fight(client)
    page = client.get("/explore/play").text
    from PIL import Image
    import os
    assert 'class="sheetfx asheet" data-act="strike"' in page and 'class="sheetfx asheet" data-act="break"' in page
    assert " sheeted" in page and "data-blade" in page                # his own sheets and timing, as hers (Nov 24)
    for act in ("strike", "break"):
        sheet = looks.ATTACK_SHEETS["male"][act]
        assert sheet["src"] in page and client.get(sheet["src"]).status_code == 200
        im = Image.open(os.path.join(os.path.dirname(os.path.dirname(__file__)), sheet["src"].lstrip("/")))
        cell = (im.size[0] / sheet["cols"], im.size[1] / sheet["rows"])
        assert abs(cell[0] * 1.5 - sheet["box"][2] * 1024) < 2 and abs(cell[1] * 1.5 - sheet["box"][3] * 559) < 2
        keys = sheet["blade"]["keys"]
        assert keys[-1][1] == sheet["frames"] - 1 and keys == sorted(keys) and sheet["blade"]["end"] >= 1900   # no faster than hers
    assert set(looks.attack_sheets({"gender": "female"})) == {"strike", "break"}   # hers: her own sheets (test below)


def test_break_slams_the_ground_with_its_own_effects(client):
    fight(client)
    for name in ("break_burst", "break_crater"):                 # scripts/make_break_fx.py, played by fight.js `slam`
        assert client.get(f"/art/fx/{name}.webp").status_code == 200
    js = client.get("/static/fight.js").text
    assert "slam: true" in js and "/art/fx/break_burst.webp" in js


def test_the_male_guard_plays_frame_by_frame(client):
    import os
    import looks
    from PIL import Image
    fight(client)
    page = client.get("/explore/play").text
    sheet = looks.GUARD_SHEETS["male"]
    assert 'class="sheetfx gsheet"' in page and sheet["src"] in page and client.get(sheet["src"]).status_code == 200
    im = Image.open(os.path.join(os.path.dirname(os.path.dirname(__file__)), sheet["src"].lstrip("/")))
    cell = (im.size[0] / sheet["cols"], im.size[1] / sheet["rows"])
    assert abs(cell[0] * 1.5 - sheet["box"][2] * 1024) < 2 and sheet["frames"] <= sheet["cols"] * sheet["rows"]
    assert f'data-first="{sheet["first"]}"' in page and sheet["ms"] == looks.GUARD_SHEETS["female"]["ms"]    # his own, at her pace


def test_the_female_guard_plays_frame_by_frame_with_its_own_timing(client):
    import json
    import os
    import looks
    from PIL import Image
    c = db.connect(client.path)
    db.update_player(c, UID, appearance=json.dumps({"gender": "female"}))
    c.close()
    fight(client)
    page = client.get("/explore/play").text
    sheet = looks.GUARD_SHEETS["female"]
    assert looks.guard_sheet({"gender": "female"}) == sheet and sheet["src"].endswith("hero_female_guard.webp")
    assert 'class="sheetfx gsheet"' in page and sheet["src"] in page and client.get(sheet["src"]).status_code == 200
    assert f'data-first="{sheet["first"]}"' in page and f'data-ms="{sheet["ms"]}"' in page
    assert f'left: {sheet["box"][0] * 100}%' in page                           # her Guard has a cell of its own on the canvas
    im = Image.open(os.path.join(os.path.dirname(os.path.dirname(__file__)), sheet["src"].lstrip("/")))
    assert abs(im.width / sheet["cols"] * 1.5 - sheet["box"][2] * 1024) < 2 and sheet["frames"] <= sheet["cols"] * sheet["rows"]
    assert 0 < sheet["first"] < sheet["frames"] and 0 < sheet["ready"] <= 700      # raised before the beast's blow lands (the quickest: 720 ms, fight.js RECIPES.gore)


def test_battle_history_keeps_every_turn(client):
    s = fight(client)
    b = s.battle
    page = client.get("/explore/play").text
    assert 'class="bhist"' in page and "The fight begins" in page            # before any move: the opening line
    for _ in range(3):
        if s.battle is None:
            break
        b.intent = {"move": "guard", "kind": "normal", "target": b.fighters[0], "name": "Guard"}
        act(client, "move", "guard")
    page = client.get("/explore/play").text
    if s.battle is not None:
        turns = len(b.history)
        assert turns >= 2 and all(f"Turn {n}" in page for n in range(1, turns + 1))
        assert page.index(f"Turn {turns}") < page.index("Turn 1<")          # newest turn first


def tiger_fight(client):
    import beasts
    from bot import combat
    from bot import fight as engine
    s = fight(client)
    b = s.battle
    b.enemy = engine.enemy_from_beast(combat.beast_stats(b.fighters[0].player, ("Mountain Tiger", "beast_king", "hunter")),
                                      "Mountain Tiger")
    b.enemy.update(realm="Martial Apprentice", slug=beasts.slug("Mountain Tiger"))
    b.fighters[0].max_hp = b.fighters[0].hp = 10 ** 6
    b.enemy_turns, b.charges = 2, 0
    b.enemy["statuses"].clear()
    b._plan()
    return s, b


def test_the_tiger_pounce_winds_up_and_is_acted_out(client):
    s, b = tiger_fight(client)
    page = client.get("/explore/play").text
    assert "skill-pounce" in page and 'class="qiring"' in page and "bwarn danger skill" in page
    assert client.get("/art/fx/crater.webp").status_code == 200
    act(client, "move", "strike")
    page = client.get("/explore/play").text
    assert '"act": "pounce"' in page and '"stun": true' in page and " roused" in page
    assert "skill-pounce" not in page


def test_a_guarded_pounce_is_one_event():
    from bot.fight import Fighter  # noqa: F401
    from web.explore_play import events

    class F:
        name, atk_t, def_t = "Shoaib", None, None
    log = [("shield", "Shoaib — Guard: blocked 50%"),
           ("skull", "Tiger — Mountain-Splitting Pounce on Shoaib −40"),
           ("roar", "Tiger — Mountain-Splitting Pounce: it roars...")]
    assert events(log, F) == [{"who": "enemy", "act": "pounce", "dmg": 40, "guard": True, "stun": False}]
    assert events(log[:1] + log[2:], F) == [{"who": "enemy", "act": "pounce", "dmg": 0, "guard": True, "stun": False}]


def test_each_region_fights_on_its_own_battleground():
    import os
    from bot.explore_card import REGION_BY_TIER
    from web.explore_play import arena

    class Exp:
        tier = 0
    seen = set()
    for tier in REGION_BY_TIER:
        Exp.tier = tier
        path = arena(Exp)
        assert path.startswith("/art/scenes/battle_") and os.path.exists(path.lstrip("/")), path
        seen.add(path)
    assert len(seen) == len(REGION_BY_TIER)


def test_a_fight_uses_the_explored_regions_battleground(client):
    from web.explore_play import arena
    s = fight(client)
    page = client.get("/explore/play").text
    assert f"--arena: url({arena(s.exp)})" in page and "battle_" in page


def test_the_tiger_is_drawn_from_its_cut_out_poses(client):
    from web.explore_play import beast_poses
    poses = beast_poses("mountain_tiger")
    assert set(poses["poses"]) == {"idle", "crouch", "leap", "slam", "roar"}
    for p in poses["poses"].values():
        assert client.get(p["src"]).status_code == 200
    assert beast_poses("wild_boar") is None and beast_poses(None) is None
    s, b = tiger_fight(client)
    page = client.get("/explore/play").text
    assert 'class="beast posed"' in page and "data-poses='" in page
    assert 'src="/art/beasts/poses/mountain_tiger/crouch.webp" alt="" data-pose="crouch"' in page   # winding up
    act(client, "move", "guard")
    page = client.get("/explore/play").text
    assert 'data-pose="idle"' in page and "/art/beasts/poses/mountain_tiger/idle.webp" in page


def test_admin_web_fight_starts_a_test_fight_when_explore_opens(client, db_path):
    from bot import admin
    row = next(r for r in admin.all_beasts() if r[1] == "Mountain Tiger")
    c = db.connect(db_path)
    admin.queue_web_fight(c, UID, row)
    coins = db.get_player(c, UID)["lotus_coins"]
    c.close()
    assert client.get("/explore").headers["location"] == "/explore/play"
    s = run(client)
    assert s.test and s.battle.enemy["name"] == "Mountain Tiger" and s.battle.enemy["tier"] == "beast_king"
    page = client.get("/explore/play").text
    assert "Admin test fight" in page and 'class="beast posed"' in page
    for _ in range(40):                                   # flee until it is over
        if s.lair_result is not None:
            break
        act(client, "move", "flee")
    page = client.get("/explore/play").text
    assert "Test fight: no rewards" in page
    c = db.connect(db_path)
    assert db.get_player(c, UID)["lotus_coins"] == coins and db.cooldown_left(c, UID, "explore") == 0
    assert admin.take_web_fight(c, UID) is None           # used up
    c.close()
    client.post("/explore/done")
    assert "Solo Hunt" in client.get("/explore").text        # back to normal


# ── The victory sequence (docs/web.md) ──────────────────────────────────────────────────────────────────

def win(client, s):
    """Strike the beast down from 1 HP."""
    for _ in range(40):
        b = s.battle
        if b is None:
            break
        b.enemy["hp"] = 1
        b.enemy["statuses"].clear()
        b.intent = {"move": "break", "kind": "normal", "target": b.fighters[0], "name": "Break"}
        act(client, "move", "strike")
    assert s.battle is None


def test_a_won_fight_stays_on_screen_until_continue(client):
    s = fight(client)
    win(client, s)
    assert s.ended and s.ended["battle"].result == "won"
    page = client.get("/explore/play").text
    assert 'class="battle' in page and " slain" in page and "data-end=" in page
    assert "Victory!" in page and "defeated in" in page and "falls" in page and ">Continue<" in page
    assert page.count('class="actbtn off"') == 3 and "Go deeper" not in page      # no fight button works any more
    assert '"act": "strike"' in page                                # the last blow is still acted out


def test_the_win_pays_once_whatever_the_page_does(client):
    s = fight(client)
    win(client, s)
    e = s.exp
    paid = (e.coins, list(e.items), e.beasts_slain, e.step, round(e.hp))
    turn = s.turn
    for _ in range(3):                                              # reloads
        assert "Victory!" in client.get("/explore/play").text
    for what, arg in (("move", "strike"), ("move", "flee"), ("deeper", ""), ("return", ""), ("path", "left")):
        act(client, what, arg)                                      # nothing but Continue is heard
    assert s.ended and not e.over and s.turn == turn
    assert (e.coins, list(e.items), e.beasts_slain, e.step, round(e.hp)) == paid
    client.post("/explore/act", data={"what": "continue", "arg": "", "turn": 0})    # even from an old page
    assert s.ended is None and s.turn == turn + 1
    client.post("/explore/act", data={"what": "continue", "arg": "", "turn": 0})    # a double click does nothing
    assert s.turn == turn + 1
    assert (e.coins, list(e.items), e.beasts_slain, e.step, round(e.hp)) == paid
    assert "Victory!" not in client.get("/explore/play").text


def test_losing_or_fleeing_has_no_victory_sequence(client):
    s = fight(client)
    for _ in range(40):
        if s.battle is None:
            break
        act(client, "move", "flee")
    assert s.ended is None and "Victory!" not in client.get("/explore/play").text


def test_quadrupeds_share_one_death_movement_and_keep_their_own_picture(client):
    import os
    import beasts
    from web import death
    views = {}
    for name in ("Iron-Hide Boar", "Red Fox", "Shadow Wolf", "Horned Stag", "Mountain Tiger"):
        v = views[name] = death.view({"kind": "beast", "name": name, "slug": beasts.slug(name)})
        assert v["kind"] == "warp" and v["category"] == "quadruped"
        assert len(v["motion"]) == len(v["ms"]) == 8 and v["motion"][0]["h"] == [1.0] * 12     # it starts standing
        assert all(0.2 <= x <= 1.15 for m in v["motion"] for x in m["h"]) and max(v["motion"][-1]["h"]) < 0.75
        assert 0 <= v["box"][0] < v["box"][2] <= 1 and 0 <= v["box"][1] < v["box"][3] <= 1
        assert "src" not in v                                       # numbers only: no picture but the beast's own
    assert views["Red Fox"]["motion"] == views["Iron-Hide Boar"]["motion"]     # one movement for all of them
    assert not os.path.exists(os.path.join(death.ROOT, "art", "fx", "death"))  # no wolf frames in the game
    assert client.get("/art/death/quadruped/red_fox.webp").status_code == 404
    assert death.view({"kind": "beast", "name": "Rock Python", "slug": "rock_python"})["kind"] == "fall"
    assert death.view({"kind": "beast", "name": "Rock Python", "slug": "rock_python"})["side"] in (1, -1)
    assert death.view({"kind": "bandit", "name": "Bandits"})["kind"] == "rout"


def test_the_beast_dies_as_its_own_picture(client):
    s = fight(client)
    b = s.battle
    b.enemy.update(name="Red Fox", slug="red_fox")
    win(client, s)
    page = client.get("/explore/play").text
    assert '<canvas class="deathfx">' in page and "death-warp" in page
    assert page.count("/art/beasts/red_fox.png") >= 2 and "/art/death/" not in page and "quadruped.webp" not in page


def test_a_won_test_fight_ends_with_finish_and_pays_nothing(client, db_path):
    from bot import admin
    row = next(r for r in admin.all_beasts() if r[1] == "Mountain Tiger")
    c = db.connect(db_path)
    admin.queue_web_fight(c, UID, row)
    coins = db.get_player(c, UID)["lotus_coins"]
    c.close()
    client.get("/explore")
    s = run(client)
    win(client, s)
    page = client.get("/explore/play").text
    assert "Victory!" in page and "Test fight: no rewards" in page and ">Finish<" in page and 'action="/explore/done"' in page
    client.post("/explore/done")
    c = db.connect(db_path)
    assert db.get_player(c, UID)["lotus_coins"] == coins
    c.close()
    assert "Solo Hunt" in client.get("/explore").text


# ── one action per turn (docs/web.md) ────────────────────────────────────────────────────────────────

def test_the_fight_page_carries_the_action_state(client):
    from web import explore_play
    s = fight(client)
    assert explore_play.phase(s) == explore_play.PLAYER_TURN
    page = client.get("/explore/play").text
    assert 'data-phase="player_turn"' in page and f'data-round="{s.battle.turn}"' in page and 'class="turnchip"' in page
    js = client.get("/static/fight.js").text
    for name in explore_play.PHASES:                                  # the screen and the server use the same names
        assert name in js, name
    assert "click the scene to skip" not in js                        # a turn's animation can't be cut short


def test_many_requests_for_one_turn_play_one_turn(client, monkeypatch):
    """A double click, a retry, a script: of all the moves sent for the same turn only one is played."""
    import threading
    s = fight(client)
    b = s.battle
    b.enemy["hp"] = b.enemy["max_hp"] = 10 ** 9                       # nobody dies in one turn
    turn, t0, n = s.turn, b.turn, 8
    ex, gate = client.explores, threading.Barrier(8)
    caught = ex.catch_up

    def together(conn, uid):                                          # every request is past the clocks before one acts
        out = caught(conn, uid)
        gate.wait(timeout=5)
        return out
    monkeypatch.setattr(ex, "catch_up", together)

    def press():
        c = db.connect(client.path)
        try:
            ex.act(c, UID, "move", "strike", turn)
        finally:
            c.close()
    threads = [threading.Thread(target=press) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    assert b.turn == t0 + 1 and len(b.history) == 1                   # one turn, not eight
    assert s.turn == turn + 1 and s.refused == n - 1


def test_a_repeated_move_is_answered_with_the_fight_as_it_stands(client):
    """The answer to a move is lost and the page sends it again: nothing is played twice, and it is told where
    the fight stands now (the next turn), so it can go on."""
    s = fight(client)
    b = s.battle
    b.enemy["hp"] = b.enemy["max_hp"] = 10 ** 9
    old, t0 = s.turn, b.turn
    data = {"what": "move", "arg": "guard", "turn": old}
    assert client.post("/explore/act", data=data).headers["location"] == "/explore/play"
    hp = (b.enemy["hp"], b.fighters[0].hp, b.fighters[0].bqi)
    again = client.post("/explore/act", data=data)
    assert again.headers["location"] == "/explore/play"
    assert b.turn == t0 + 1 and (b.enemy["hp"], b.fighters[0].hp, b.fighters[0].bqi) == hp
    assert f'data-turn="{s.turn}"' in client.get("/explore/play").text and s.turn == old + 1


def test_the_winning_blow_pays_once_however_often_it_is_sent(client, db_path):
    from web import explore_play
    s = fight(client)
    b = s.battle
    b.enemy["hp"] = 1
    b.intent = {"kind": "normal", "move": "break"}                    # your Strike beats its Break
    turn = s.turn
    data = {"what": "move", "arg": "strike", "turn": turn}
    client.post("/explore/act", data=data)
    assert b.result == "won" and s.battle is None
    assert explore_play.phase(s) == explore_play.FINISHED             # the victory sequence: no fight to act in
    assert 'data-phase="finished"' in client.get("/explore/play").text
    found = (s.exp.coins, list(s.exp.items))
    for _ in range(3):
        client.post("/explore/act", data=data)
    assert (s.exp.coins, list(s.exp.items)) == found and s.exp.last_battle is b
    act(client, "continue")
    assert explore_play.phase(s) is None                              # the expedition goes on
    assert (s.exp.coins, list(s.exp.items)) == found


def test_the_female_stance_plays_while_she_stands(client):
    import json
    import os
    import looks
    from PIL import Image
    c = db.connect(client.path)
    db.update_player(c, UID, appearance=json.dumps({"gender": "female"}))
    c.close()
    fight(client)
    page = client.get("/explore/play").text
    sheet = looks.IDLE_SHEETS["female"]
    assert looks.idle_sheet({"gender": "female"}) == sheet and sheet["src"].endswith("hero_female_stance.webp")
    assert " stanced" in page and 'class="sheetfx isheet"' in page and sheet["src"] in page
    assert "hero_female_idle.webp" not in page and "p-idle" not in page     # the stance is her only standing picture
    assert "hero_female_windup.webp" in page and "hero_female_strike.webp" in page
    assert client.get(sheet["src"]).status_code == 200
    im = Image.open(os.path.join(os.path.dirname(os.path.dirname(__file__)), sheet["src"].lstrip("/")))
    assert im.size == (320 * sheet["cols"], 360 * sheet["rows"]) and sheet["frames"] == sheet["cols"] * sheet["rows"]
    assert f"--loop: {sheet['loop']}s" in page and f"--cols: {sheet['cols']}" in page and f"--rows: {sheet['rows']}" in page
    css = client.get("/static/style.css").text
    assert ".fighter.stanced[data-pose=idle] .isheet{visibility:visible}" in css and "@keyframes stancex" in css
    assert "querySelectorAll('.asheet')" in client.get("/static/fight.js").text   # only .asheet is an attack, never the stance


def test_the_male_cultivator_has_his_stance_too(client):
    import looks
    fight(client)
    page = client.get("/explore/play").text
    sheet = looks.idle_sheet({"gender": "male"})
    assert sheet["src"].endswith("hero_male_stance.webp") and sheet["frames"] == sheet["cols"] * sheet["rows"]
    assert " stanced" in page and sheet["src"] in page and client.get(sheet["src"]).status_code == 200
    assert 'data-voice="male"' in page                                 # his own recordings are asked for (fight_sound.js)


# ── Animated beasts (web/beast_sheets.py, art/beasts/sheets/<slug>/; docs/web.md "Animated beasts") ──────────────

def wolf_fight(client):
    import beasts
    from bot import combat
    from bot import fight as engine
    s = fight(client)
    b = s.battle
    b.enemy = engine.enemy_from_beast(combat.beast_stats(b.fighters[0].player, ("Grey Wolf", "elite", "hunter")),
                                      "Grey Wolf")
    b.enemy.update(realm="Martial Apprentice", slug=beasts.slug("Grey Wolf"))
    b.enemy["statuses"].clear()
    b._plan()
    return s, b


def test_the_grey_wolf_has_its_four_animations_on_one_cell():
    import os
    from PIL import Image
    from web import beast_sheets
    d = beast_sheets.sheets("grey_wolf")
    assert d and set(d["sheets"]) == {"idle", "attack", "hit", "death"}
    cw, ch = d["cell"]
    x, y, w, h = d["still"]                                       # the still picture, inside the cell
    assert 0 <= x and 0 <= y and x + w <= cw + 1 and y + h <= ch + 1
    root = os.path.dirname(os.path.dirname(__file__))
    for kind, sh in d["sheets"].items():
        im = Image.open(os.path.join(root, sh["src"].lstrip("/")))
        assert im.size == (cw * sh["cols"], ch * sh["rows"]) and sh["frames"] <= sh["cols"] * sh["rows"]
        assert sh["ms"] > 0
    idle = d["sheets"]["idle"]
    assert idle["frames"] == idle["cols"] * idle["rows"]                  # stepped through in CSS: the grid is full
    attack = d["sheets"]["attack"]
    assert attack["ms"] == 2200 and 0 < attack["bite"] < attack["frames"] - 1 and 0 <= attack["reach"] < 0.5
    assert 0 <= attack["bite_x"] < idle["nose_x"] < 0.3                   # the bite reaches further forward than it stands
    death_ = d["sheets"]["death"]
    assert 0 < death_["impact"] < death_["frames"]
    assert beast_sheets.sheets("red_fox") is None and beast_sheets.sheets("../etc") is None


def test_only_the_grey_wolf_dies_in_its_own_animation():
    import beasts
    from web import death
    v = death.view({"kind": "beast", "name": "Grey Wolf", "slug": "grey_wolf"})
    assert v["kind"] == "sheet" and v["ms"] == 2500 and 0 < v["impact"] < v["ms"] and v["linger"] == death.LINGER_MS
    v = death.view({"kind": "beast", "name": "Shadow Wolf", "slug": beasts.slug("Shadow Wolf")})
    assert v["kind"] == "warp"                                    # every other beast as before


def test_the_grey_wolf_fight_draws_its_frames_over_its_picture(client):
    s, b = wolf_fight(client)
    page = client.get("/explore/play").text
    assert 'class="beast sheeted"' in page and 'data-anim="idle"' in page and "data-sheets=" in page
    for kind in ("idle", "attack", "hit", "death"):
        assert f'class="bs bs-{kind}"' in page and f"/art/beasts/sheets/grey_wolf/{kind}.webp" in page
        assert client.get(f"/art/beasts/sheets/grey_wolf/{kind}.webp").status_code == 200
    assert "/art/beasts/grey_wolf.png" in page                    # its still picture stays underneath
    assert "--loop:" in page and "--xend:" in page
    css, js = client.get("/static/style.css").text, client.get("/static/fight.js").text
    assert ".beast.sheeted>img{visibility:hidden}" in css and "@keyframes bsx" in css     # its still is never drawn
    assert "function BeastSheets" in js and "BS.hit()" in js and "BS.frame('attack'" in js and "BS.frame('death'" in js
    assert "BS.edge('bite')" in js and "BS.edge('nose')" in js and "'still'" not in js   # kept apart; no still mode


def test_the_wild_boar_is_animated_from_its_own_videos():
    """SHOAIB's redesigned Wild Boar (Nov 26): its four animations, cut from three videos (idle; hit + attack; death)."""
    from web import beast_sheets, death
    d = beast_sheets.sheets("wild_boar")
    assert d and set(d["sheets"]) == {"idle", "attack", "hit", "death"}
    cw, ch = d["cell"]
    x, y, w, h = d["still"]
    assert 0 <= x and 0 <= y and x + w <= cw + 1 and y + h <= ch + 1
    a = d["sheets"]["attack"]
    assert 0 < a["bite"] < a["frames"] and 0 <= a["bite_x"] < 1 and a["ms"] == 2000      # the tusk toss
    assert 0 < d["sheets"]["death"]["impact"] < d["sheets"]["death"]["frames"]
    v = death.view({"kind": "beast", "name": "Wild Boar", "slug": "wild_boar"})
    assert v["kind"] == "sheet"


def test_the_wild_boar_speaks_with_its_own_voice_others_with_their_bodys():
    """Its squeal, gore, thud and roar come from its own videos ("<sound>@wild_boar"); other beasts keep their body's."""
    import json
    import os
    from web import explore_play
    keys = json.load(open(os.path.join("art", "fx", "sounds", "sounds.json")))
    for sound in ("hit", "lunge", "death", "roar", "roar:big"):
        assert f"{sound}@wild_boar" in keys
        for take in keys[f"{sound}@wild_boar"]:
            assert os.path.exists(os.path.join("art", "fx", "sounds", take["file"]))
    assert explore_play.beast_body("Wild Boar") == "wild_boar"
    assert explore_play.beast_body("Grey Wolf") == "wolf" and explore_play.beast_body("Iron-Hide Boar") == "wolf"
    assert explore_play.beast_body("No Such Beast") is None


def test_the_field_viper_is_animated_from_its_own_videos_with_its_own_voice():
    """SHOAIB's redesigned Field Viper (Nov 26, a true snake): idle + strike from one video, hit + death from another;
    its roar picture is its own video's open-jawed hiss; its sounds come from its videos."""
    import json
    import os
    from web import beast_sheets, death, explore_play
    d = beast_sheets.sheets("field_viper")
    assert d and set(d["sheets"]) == {"idle", "attack", "hit", "death"}
    assert d["sheets"]["attack"]["reach"] > 0.3                   # the strike stretches it far out of its coils
    assert death.view({"kind": "beast", "name": "Field Viper", "slug": "field_viper"})["kind"] == "sheet"
    assert os.path.exists(os.path.join("art", "beasts", "roar", "field_viper.png"))
    keys = json.load(open(os.path.join("art", "fx", "sounds", "sounds.json")))
    for sound in ("hit", "lunge", "death", "roar", "roar:big"):
        assert f"{sound}@field_viper" in keys
    assert explore_play.beast_body("Field Viper") == "field_viper"


def test_an_animated_beast_opens_its_jaws_when_it_roars(client):
    """Its roar shows its open-mouthed roar picture over its frames (Nov 26: the boar roared with its mouth shut)."""
    css, js = client.get("/static/style.css").text, client.get("/static/fight.js").text
    assert ".beast.sheeted.roaring>img{visibility:visible}" in css and ".beast.sheeted.roaring .bsheets{visibility:hidden}" in css
    assert "if (BS) beastBox.classList.toggle('roaring', open)" in js and "beastBox.classList.remove('roaring')" in js


def test_other_beasts_keep_their_pictures(client):
    fight(client)
    page = client.get("/explore/play").text
    assert "beast sheeted" not in page and "bsheets" not in page and "data-anim" not in page


def test_the_grey_wolf_goes_down_in_its_death_animation(client):
    s, b = wolf_fight(client)
    win(client, s)
    page = client.get("/explore/play").text
    assert " slain" in page and "death-sheet" in page and '"kind": "sheet"' in page and "bs-death" in page


def test_style_and_scripts_are_never_stale(client):
    import re
    fight(client)
    page = client.get("/explore/play").text
    css = re.search(r'href="(/static/style\.css\?v=[0-9a-f]{10})"', page)
    js = re.search(r'src="(/static/fight\.js\?v=[0-9a-f]{10})"', page)
    assert css and js                                           # each address carries its file's version
    r = client.get(css.group(1))
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"      # and the browser checks each time
    from web import app as web_app
    assert web_app.asset("style.css") == css.group(1) and web_app.asset("nothing.js") == "/static/nothing.js"
def test_the_fight_background_is_alive_behind_the_fighters(client):
    fight(client)
    page = client.get("/explore/play").text
    assert "/static/ambient.js?v=" in page
    js, css = client.get("/static/ambient.js").text, client.get("/static/style.css").text
    for place in ("bamboo_forest", "misty_pine_valley", "northern_sea_wilds", "red_cliff_gorge", "thunder_peaks", "arena_ruins"):
        assert place + ":" in js                                   # every fight background has its own weather
    assert "prefers-reduced-motion" in js and "document.hidden" in js
    assert ".bscene>canvas.ambient{" in css and "pointer-events:none;z-index:-1" in css   # at the back, never in the way


def test_her_strike_and_break_play_frame_by_frame_from_her_stance(client):
    import json
    import os
    import looks
    from PIL import Image
    c = db.connect(client.path)
    db.update_player(c, UID, appearance=json.dumps({"gender": "female"}))
    c.close()
    fight(client)
    page = client.get("/explore/play").text
    root = os.path.dirname(os.path.dirname(__file__))
    for act in ("strike", "break"):
        sh = looks.ATTACK_SHEETS["female"][act]
        assert f'class="sheetfx asheet" data-act="{act}"' in page and sh["src"] in page and "data-blade=" in page
        assert client.get(sh["src"]).status_code == 200
        im = Image.open(os.path.join(root, sh["src"].lstrip("/")))
        cw, ch = im.size[0] // sh["cols"], im.size[1] // sh["rows"]
        assert sh["frames"] <= sh["cols"] * sh["rows"] and abs(cw / ch - sh["box"][2] * 1024 / (sh["box"][3] * 559)) < 0.02
        keys = sh["blade"]["keys"]
        assert keys[0] == [0, 0] and keys[-1][1] == sh["frames"] - 1                # stance to stance
        assert all(a[0] <= b[0] for a, b in zip(keys, keys[1:]))
        assert sh["blade"]["dash"][1] <= sh["blade"]["hit"] <= sh["blade"]["back"][0] < sh["blade"]["end"]
    assert looks.ATTACK_SHEETS["female"]["break"]["blade"]["slam"]                    # the fight's own Break burst
    js = client.get("/static/fight.js").text
    assert "sweep(ev, asheets[ev.act])" in js and "sheet.dataset.blade" in js


def test_frostpeak_plays_its_background_video_behind_the_fight(client):
    import os
    import subprocess
    js, css = client.get("/static/ambient.js").text, client.get("/static/style.css").text
    assert "video: '/art/scenes/battle_northern_sea_wilds.mp4'" in js and "skip: ['aurora']" in js
    r = client.get("/art/scenes/battle_northern_sea_wilds.mp4")
    assert r.status_code == 200 and r.headers["content-type"] == "video/mp4"
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "art", "scenes", "battle_northern_sea_wilds.mp4")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,codec_name,width,height",
                            "-of", "csv=p=0", path], capture_output=True, text=True).stdout.split()
    assert probe == ["h264,video,1280,720"] or probe == ["video,h264,1280,720"] or (len(probe) == 1 and "h264" in probe[0])
    assert os.path.getsize(path) < 4 * 1024 * 1024                              # light enough for a page background
    assert "main.battle.bglive{isolation:isolate}" in css and "video.bgloop{" in css and "z-index:-1" in css
    assert "saveData" in js                                                     # not when the browser saves data


def test_the_fight_loads_its_sheets_and_technique_pictures_up_front(client):
    """Every picture a turn may need is named on the page when the fight opens (fight.js `keep`), so no move plays over
    a sheet that is still loading; and her movements carry their own least time (looks `ms`). Presentation only."""
    import json
    import re
    import looks
    c = db.connect(client.path)
    db.update_player(c, UID, appearance=json.dumps({"gender": "female"}))
    c.close()
    fight(client)
    page = client.get("/explore/play").text
    listed = json.loads(re.search(r"data-preload='([^']+)'", page).group(1).replace("&#34;", '"'))
    assert looks.GUARD_SHEETS["female"]["src"] in listed and looks.ATTACK_SHEETS["female"]["strike"]["src"] in listed
    assert looks.MOTION_SHEETS["fist"]["female"]["src"] in listed and "/art/fx/tech/iron_fist.webp" in listed   # Iron Fist, equipped
    assert len(listed) == len(set(listed))
    for src in listed:
        assert client.get(src).status_code == 200, src
    for motion in ("kick", "fist", "palm", "finger"):                          # nearer the beast's own pace than a 1.1 s cast
        assert 1800 <= looks.MOTION_SHEETS[motion]["female"]["ms"] <= 2600
    js = client.get("/static/fight.js").text
    assert "function whenReady" in js and "msheet.dataset.ms" in js
