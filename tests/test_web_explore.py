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
    assert "Set out" in page and "Explore the Wilds" in page and 'href="/explore"' in page
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
    assert "legs still ache" in client.get("/explore").text
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
    assert "legs still ache" in client.get("/explore").text


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
    for pose in ("idle", "windup", "strike"):
        assert f'class="pose p-{pose}" src="/art/portraits/fight/hero_male_{pose}.webp"' in page
    assert 'src="/art/fx/slash.webp"' in page and client.get("/art/fx/slash.webp").status_code == 200
    assert 'data-pose="idle"' in page and 'data-bar="me"' in page and 'data-bar="enemy"' in page
    assert "data-events='[{" in page and '"act": "strike"' in page


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
