"""Alchemy on the website (docs/web.md, "Alchemy"): the bot's own /craft engine, refereed on the server."""
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from bot import crafting, db, loot  # noqa: E402
from bot import player as rules  # noqa: E402
from web import alchemy_play  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

UID = 778
QI = "qi:Mortal"


def herb_count(path):
    c = db.connect(path)
    n = sum(h["qty"] for h in db.get_items(c, UID, "herbs"))
    c.close()
    return n


def pills(path):
    c = db.connect(path)
    out = db.get_items(c, UID, "pills")
    c.close()
    return out


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Alchemist", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    loot.store(c, UID, [dict(loot.herb("Mortal", "qi", 10), qty=6), dict(loot.herb("Mortal", "purity", 10), qty=3)])
    c.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "alch", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=db_path, session_secret="s"))
    c = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c.get("/login").headers["location"]).query)
    c.get("/callback", params={"code": "x", "state": q["state"][0]})
    c.now = [1000.0]
    app.state.crafts.clock = lambda: c.now[0]
    c.crafts = app.state.crafts
    return c


def begin(client, pill=QI, controls="classic"):
    return client.post("/alchemy/begin", data={"pill": pill, "batch": "1", "prefer": "young", "controls": controls})


def test_alchemy_page_shows_pills_and_recipe(client):
    page = client.get("/alchemy")
    assert "Classic buttons" in page.text and 'value="live" checked' in page.text
    assert page.status_code == 200 and "Choose a pill" in page.text
    assert "Ember Dantian Pill" in page.text and "Ready to craft" in page.text
    assert "2 × Spirit Grass" in page.text and "Begin refining" in page.text
    assert "disabled" not in page.text.split("Begin refining")[0][-80:]
    assert 'href="/alchemy"' in page.text                                # the nav tab


def test_begin_takes_the_herbs(client, db_path):
    before = herb_count(db_path)
    r = begin(client)
    assert r.status_code == 303 and r.headers["location"] == "/alchemy/play"
    assert herb_count(db_path) == before - 3
    play = client.get("/alchemy/play")
    assert "STAGE 1 OF" in play.text and "Stoke" in play.text
    assert client.get("/alchemy").headers["location"] == "/alchemy/play"   # one craft at a time
    assert begin(client).headers["location"].startswith("/alchemy?")
    assert herb_count(db_path) == before - 3


def test_missing_herbs_refuse_to_begin(client, db_path):
    page = client.get("/alchemy?pill=mending:Mortal")
    assert "Missing:" in page.text
    r = begin(client, "mending:Mortal")
    assert r.headers["location"].startswith("/alchemy?") and "Still missing" in client.get(r.headers["location"]).text
    assert client.crafts.get(UID) is None


def test_a_pill_above_the_rank_is_refused(client, db_path):
    r = begin(client, "qi:Heaven")
    assert "rank" in client.get(r.headers["location"]).text
    assert client.crafts.get(UID) is None
    assert "Heaven-Devouring" not in client.get("/alchemy").text


def play_to_the_end(client):
    for _ in range(80):
        s = client.crafts.get(UID)
        if s.outcome is not None:
            return s
        pr = s.craft.prompt()
        client.post("/alchemy/act", data={"key": pr.options[0][0], "turn": s.turn})
    raise AssertionError("the craft never finished")


def test_playing_every_stage_finishes_with_a_result(client, db_path):
    begin(client)
    s = play_to_the_end(client)
    page = client.get("/alchemy/play")
    assert "FINAL SCORE" in page.text and "Craft again" in page.text and "alchemy EXP" in page.text
    c = db.connect(db_path)
    assert db.get_player(c, UID)["alchemy_exp"] > 0
    c.close()
    if s.craft.result:
        assert [p["data"]["patterns"] for p in pills(db_path)] == [s.craft.result]
    else:
        assert pills(db_path) == []
    r = client.post("/alchemy/done")
    assert r.headers["location"].startswith("/alchemy?pill=qi") and client.crafts.get(UID) is None


def test_a_careful_craft_makes_a_pill(client, db_path):
    begin(client)
    s = client.crafts.get(UID)
    c = s.craft
    for _ in range(80):
        if s.outcome is not None:
            break
        pr = c.prompt()
        if pr.stage == 1:      # steer toward the middle of the hidden zone, as a player reading the hints would
            mid = c.zone_lo + c.zone_width / 2
            key = "stoke" if c.heat + c.drift < mid - 6 else "fan" if c.heat + c.drift > mid + 6 else "hold"
        elif pr.stage == 4:
            key = "condense" if c.pulse >= 3 else "wait"     # ≥70% here alone keeps the score above 40%
        else:
            key = pr.options[0][0]
        client.post("/alchemy/act", data={"key": key, "turn": s.turn})
    assert s.outcome is not None and c.result > 0
    assert len(pills(db_path)) == 1 and "纹" in client.get("/alchemy/play").text


def test_old_turns_and_unknown_buttons_are_ignored(client):
    begin(client)
    s = client.crafts.get(UID)
    client.post("/alchemy/act", data={"key": "explode", "turn": s.turn})
    assert s.turn == 0
    client.post("/alchemy/act", data={"key": "hold", "turn": 5})
    assert s.turn == 0
    client.post("/alchemy/act", data={"key": "hold", "turn": 0})
    assert s.turn == 1
    client.post("/alchemy/act", data={"key": "hold", "turn": 0})         # the same page sent twice
    assert s.turn == 1


def test_running_out_of_time_plays_the_timed_out_move(client, db_path):
    begin(client)
    s = client.crafts.get(UID)
    client.now[0] += s.craft.seconds + crafting.TIMER_GRACE_SECONDS + 0.5
    client.get("/alchemy/play")
    assert s.turn == 1 and s.craft.stage == 1
    client.now[0] += 10_000                                             # walked away: everything times out
    client.get("/alchemy/play")
    assert s.outcome is not None and s.craft.done


def test_the_page_never_shows_the_hidden_answers(client):
    begin(client)
    s = client.crafts.get(UID)
    page = client.get("/alchemy/play").text
    for shown in (f"{s.craft.heat}°", f"({s.craft.zone_width}° wide)", "<span>0°</span>", "<span>100°</span>"):
        page = page.replace(shown, "")
    assert f"{s.craft.zone_lo}°" not in page and "zone_lo" not in page


def test_batch_needs_the_rank_and_herbs_per_pill(client, db_path):
    c = db.connect(db_path)
    db.update_player(c, UID, alchemy_exp=100)                           # 2nd Grade: batches of 2
    c.close()
    page = client.get(f"/alchemy?pill={QI}&batch=2")
    assert "Pills at once" in page.text and "4 × Spirit Grass" in page.text
    before = herb_count(db_path)
    client.post("/alchemy/begin", data={"pill": QI, "batch": "9", "prefer": "young"})   # capped at 2
    s = client.crafts.get(UID)
    assert s.craft.batch == 2 and herb_count(db_path) == before - 6


def test_setup_view_matches_the_bot_plan(db_path):
    c = db.connect(db_path)
    v = alchemy_play.setup_view(c, UID, QI)
    pl = crafting.plan(c, UID, "qi", "Mortal")
    game = crafting.craft_for(db.get_player(c, UID), "qi", "Mortal", pl["age"])
    c.close()
    assert v["chosen"]["ready"] and not pl["missing"]
    assert v["chosen"]["difficulty"] == game.diff["name"] and v["chosen"]["zone"] == game.zone_width
    assert v["chosen"]["seconds"] == f"{game.seconds:g}"


def test_the_cauldron_comes_alive_stage_by_stage(client, db_path):
    import os
    begin(client)
    page = client.get("/alchemy/play").text
    assert 'class="cscene"' in page and 'data-stage="1"' in page and "/art/fx/alchemy/fire_" in page
    assert 'src="/art/scenes/cauldron.png"' in page and "/static/alchemy.js?v=" in page
    assert alchemy_play.fire_for(10) == "low" and alchemy_play.fire_for(60) == "mid" and alchemy_play.fire_for(90) == "high"
    s = client.crafts.get(UID)
    c = s.craft
    assert alchemy_play.scene_view(c, 3, "Mystic")["loop"].endswith("swirl.mp4")
    assert alchemy_play.scene_view(c, 2, "Yellow")["event"].endswith("splash.mp4")
    v4 = alchemy_play.scene_view(c, 4, "Mortal")
    assert v4["condense_in"].endswith("condense_in.mp4") and v4["condense"].endswith("condense_loop.mp4")
    v6 = alchemy_play.scene_view(c, 6, "Heaven")
    assert v6["storm"] == "/art/scenes/alchemy_tribulation.mp4" and v6["event"].endswith("lightning.mp4") and "fire" not in v6
    root = os.path.dirname(os.path.dirname(__file__))
    for name in ("fire_low", "fire_mid", "fire_high", "swirl", "splash", "condense_in", "condense_loop", "explode", "lightning"):
        path = os.path.join(root, "art", "fx", "alchemy", f"{name}.mp4")
        assert os.path.getsize(path) < 2 * 1024 * 1024
        assert client.get(f"/art/fx/alchemy/{name}.mp4").headers["content-type"] == "video/mp4"
    assert client.get("/art/scenes/alchemy_tribulation.mp4").status_code == 200
    css, js = client.get("/static/style.css").text, client.get("/static/alchemy.js").text
    assert "mix-blend-mode:screen" in css and ".cscene .cfx.on{opacity:1}" in css
    assert "prefers-reduced-motion" in js and "sessionStorage" in js


def test_an_exploded_craft_plays_the_explosion(client, db_path):
    begin(client)
    s = client.crafts.get(UID)
    s.craft.done, s.craft.result = True, 0
    s.outcome = {"lines": ["The cauldron explodes!"]}
    page = client.get("/alchemy/play").text
    assert 'class="cscene boom"' in page and "/art/fx/alchemy/explode.mp4" in page and "cauldron_burst.png" in page


# ── live controls (web/alchemy_live.py) ──────────────────────────────

def live(client):
    return client.get("/alchemy/live").json()


def lpress(client, n, **ev):
    return client.post("/alchemy/live/press", data=dict(id=n, **ev)).json()


def test_live_is_the_default_and_keeps_the_herb_order_secret(client):
    r = client.post("/alchemy/begin", data={"pill": QI, "batch": "1", "prefer": "young"})
    assert r.headers["location"] == "/alchemy/play" and "ma_controls=live" in r.headers["set-cookie"]
    page = client.get("/alchemy/play").text
    assert 'id="alive"' in page and "alchemy_live.js" in page and "Stoke" not in page
    st = live(client)
    lv = st["live"]
    assert lv["stage"] == 1 and not lv["began"]
    assert {"lo", "width", "gusts", "heat"} <= set(lv["pub"])          # the band is visible on purpose


def test_live_presses_before_begin_are_ignored_and_time_runs_from_the_begin(client):
    begin(client, controls="live")
    n = live(client)["live"]["id"]
    assert lpress(client, n, pump="1")["reply"] == {"stale": True}
    client.post("/alchemy/live/begin", data={"id": n})
    s = client.crafts.get(UID)
    assert s.live.t0 == client.now[0]
    client.now[0] += 1.0
    lpress(client, n, pump="1")
    assert s.live.data["holds"] == [(1.0, True)]


def test_live_perfect_hands_make_a_full_score_pill(client, db_path):
    """Heat held in the band by the server's own simulation, then Condense in the glint."""
    from web import alchemy_live as L
    begin(client, controls="live")
    s = client.crafts.get(UID)
    n = live(client)["live"]["id"]
    client.post("/alchemy/live/begin", data={"id": n})
    p, t0 = s.live.pub, client.now[0]
    heat, speed, pump, t = float(p["heat"]), 0.0, False, 0.0
    while t < p["length"]:                                    # a steady hand keeping to the band's middle
        mid = L.band_lo(p, t) + p["width"] / 2
        want = heat + speed * 0.3 < mid
        if want != pump:
            pump = want
            client.now[0] = t0 + t
            lpress(client, n, pump="1" if pump else "0")
        sp = p["up"] if pump else -p["down"]
        speed += (sp - speed) * min(1, p["tick"] / p["ease"])
        heat = max(0, min(100, heat + (speed + L.gust_at(p, t)) * p["tick"]))
        t += p["tick"]
    client.now[0] = t0 + p["length"] + 1
    st = live(client)
    assert st["last"]["stage"] == 1 and st["last"]["score"] >= 0.6         # a simple steady hand; 95% in band is full
    lv = st["live"]
    assert lv["stage"] == 4
    client.post("/alchemy/live/begin", data={"id": lv["id"]})
    t0 = client.now[0]
    q = lv["pub"]
    client.now[0] = t0 + (4 - q["start"] + 0.5) * q["pulse"]
    r = lpress(client, lv["id"])
    assert r["state"]["done"]
    assert s.craft.scores[4] == 1.0 and s.craft.result >= 4
    assert pills(db_path)
    page = client.get("/alchemy/play").text
    assert 'class="tier"' not in page and page.count('class="rpill"') == 1


def test_live_walking_away_runs_every_stage_out(client, db_path):
    begin(client, controls="live")
    live(client)
    client.now[0] += 600
    st = live(client)
    assert st["done"]
    s = client.crafts.get(UID)
    assert s.craft.scores[4] == crafting.CRACKED_SCORE and s.outcome is not None


def test_live_condense_too_early_and_too_late(client):
    from web import alchemy_live as L
    c = crafting.Craft("qi", "Mortal", 1, 10, __import__("random").Random(1))
    c.settle(1.0)
    lv = L.make(c, c.rng, 0, 0)
    L.press(lv, c, 0.01, {})
    L.settle(lv, c, 1)
    assert c.scores[4] == crafting.PULSE_SCORE[lv.pub["start"]]
    c = crafting.Craft("qi", "Mortal", 1, 10, __import__("random").Random(1))
    c.settle(1.0)
    lv = L.make(c, c.rng, 0, 0)
    L.settle(lv, c, lv.length + 1)
    assert c.scores[4] == crafting.CRACKED_SCORE


def test_live_herbs_wrong_herb_is_a_backlash_and_the_right_one_on_the_breath_is_full():
    import random
    from web import alchemy_live as L
    c = crafting.Craft("qi", "Yellow", 2, 10, random.Random(4))
    c.settle(1.0)
    assert c.stage == 2
    lv = L.make(c, c.rng, 0, 0)
    p = lv.pub
    wrong = next(h["key"] for h in p["herbs"] if h["key"] != c.order[0])
    r = L.press(lv, c, p["breath"] * 0.5, {"herb": wrong})
    assert r["marks"][0]["how"] == "wrong"
    t = p["breath"] * 1.5
    while not lv.over:
        L.press(lv, c, t, {"herb": c.order[lv.data["placed"]]})
        t += p["breath"]
    L.settle(lv, c, t)
    assert c.scores[2] == pytest.approx((p["count"] - 1) / p["count"])


def tribulation_craft(seed=2, grade="Mortal"):
    import random
    from web import alchemy_live as L
    c = crafting.Craft("qi", grade, 9, 1000, random.Random(seed))
    while c.tribulation is None:
        c.settle(1.0)
    assert c.tribulation == "pending"
    return c, L, L.make(c, c.rng, 0, 0)


def weather(L, lv, c, i, wrong=False, early=False):
    """The right answer to bolt i, as a player who read its warning would give it."""
    b = lv.pub["bolts"][i]
    info = L.press(lv, c, b["warn"], {"bolt": i, "omen": True})
    if b["kind"] == "blue":
        at = b["hit"] - (1.0 if early else 0.1)
        return L.press(lv, c, at, {"bolt": i, "act": "right" if wrong else "protect"})
    safe = info["safe"] if not info["flip"] else ("left" if info["safe"] == "right" else "right")
    if wrong:
        safe = "left" if safe == "right" else "right"
    return L.press(lv, c, b["hit"] - 0.1, {"bolt": i, "act": safe})


def test_live_tribulation_protect_and_dodge():
    c, L, lv = tribulation_craft()
    assert lv.stage == 6 and "safe" not in str(lv.pub)                     # where is safe stays on the server
    kinds = [b["kind"] for b in lv.pub["bolts"]]
    assert kinds == ["blue", "red", "blue"]                                # Mortal: one of each, gently
    b0 = lv.pub["bolts"][0]
    assert L.press(lv, c, b0["warn"] - 1.0, {"bolt": 0, "omen": True}) == {}   # no peeking before the warning
    for i in range(len(kinds)):
        assert weather(L, lv, c, i)["ok"]
    L.settle(lv, c, lv.length + 1)
    assert c.done and c.tribulation == "won" and c.result == 9


def test_live_tribulation_shield_raised_too_early_fades():
    c, L, lv = tribulation_craft()
    assert weather(L, lv, c, 0, early=True)["ok"] is False
    for i in (1, 2):
        weather(L, lv, c, i)
    L.settle(lv, c, lv.length + 1)
    assert c.tribulation == "lost" and c.result == 8


def test_live_tribulation_heaven_has_pairs_and_fakeouts():
    c, L, lv = tribulation_craft(seed=7, grade="Heaven")
    assert [len(r) for r in lv.pub["rounds"]] == [1, 2, 2]
    for i in range(len(lv.pub["bolts"])):
        weather(L, lv, c, i)
    L.settle(lv, c, lv.length + 1)
    assert c.tribulation == "won"


def test_live_seal_shatters_the_core_when_missed():
    import random
    from web import alchemy_live as L
    c = crafting.Craft("breakthrough", "Mortal", 9, 10, random.Random(5))
    while c.stage != 5:
        c.settle(1.0)
    lv = L.make(c, c.rng, 0, 0)
    L.settle(lv, c, lv.length + 1)
    assert c.done and c.core_lost and c.result == 0


def test_the_reveal_shows_one_pill_per_pill_crafted():
    assert [len(alchemy_play.pill_spots(n)) for n in (1, 2, 3, 4, 5)] == [1, 2, 3, 4, 5]


def test_live_tribulation_lists_every_strike():
    c, L, lv = tribulation_craft()
    weather(L, lv, c, 0)
    weather(L, lv, c, 1, wrong=True)                                      # dodged the wrong way
    weather(L, lv, c, 2)
    L.settle(lv, c, lv.length + 1)
    assert c.tribulation == "lost" and c.result == 8
    assert c.log == ["⛈️ The Tribulation: 🛡️ ⚡ 🛡️ · 2 of 3 strikes weathered. The pill survives, scarred: 8 patterns."]


def test_live_ignite_band_survives_a_big_batch():
    import random
    from web import alchemy_live as L
    c = crafting.Craft("qi", "Heaven", 9, 10, random.Random(1), batch=5)
    assert c.zone_width < L.IGNITE_MIN_BAND
    p = L.make(c, c.rng, 0, 0).pub
    assert p["width"] == L.IGNITE_MIN_BAND and p["sway"] == 0 and p["tempo"] <= L.IGNITE_MAX_TEMPO


def test_the_pill_reveal(client):
    begin(client, controls="live")
    s = client.crafts.get(UID)
    s.live = None
    s.craft.settle(1.0)                                        # a fine craft, played out
    s.craft.settle(0.8)
    page = client.get("/alchemy/play").text
    n = s.craft.result
    assert n and 'id="preveal"' in page and "alchemy_reveal.js" in page
    assert page.count("<circle") == n and f"{crafting.CN[n]}纹" in page and 'class="tier"' not in page


def test_live_tribulation_over_the_web(client):
    """The page's own requests: the warning, then the answer."""
    begin(client, controls="live")
    s = client.crafts.get(UID)
    s.live = None
    s.craft.age, s.craft.score_bonus, s.craft.max_patterns = 1000, 0.25, 9
    while s.craft.tribulation is None:
        s.craft.settle(1.0)
    lv = live(client)["live"]
    assert lv["stage"] == 6
    client.post("/alchemy/live/begin", data={"id": lv["id"]})
    t0 = client.now[0]
    b = lv["pub"]["bolts"][0]
    client.now[0] = t0 + b["warn"]
    info = lpress(client, lv["id"], bolt=0, omen="1")["reply"]
    assert info["kind"] == "blue"
    client.now[0] = t0 + b["hit"] - 0.1
    assert lpress(client, lv["id"], bolt=0, act="protect")["reply"]["ok"]


# ── the grade challenges and the rank margin ─────────────────────────

def craft_at(grade, stage, rank_above=0, seed=3, age=50):
    import random
    rank = crafting.pill_spec("qi", grade)["rank"] + rank_above
    c = crafting.Craft("qi", grade, rank, age, random.Random(seed))
    while c.stage != stage:
        c.settle(1.0)
    return c


def test_harder_grades_add_challenges_not_just_speed():
    from web import alchemy_live as L
    mortal = L.make(craft_at("Mortal", 1), __import__("random").Random(1), 0, 0).pub
    heaven = L.make(craft_at("Heaven", 1), __import__("random").Random(1), 0, 0).pub
    assert not mortal["jumps"] and not mortal["flares"]
    assert heaven["jumps"] and heaven["flares"]
    yellow = L.make(craft_at("Yellow", 2), __import__("random").Random(1), 0, 0).pub
    earth = L.make(craft_at("Earth", 2), __import__("random").Random(1), 0, 0).pub
    assert yellow["volatile"] is None and earth["volatile"] is not None and earth["shift"] is None
    mystic = L.make(craft_at("Mystic", 3), __import__("random").Random(1), 0, 0).pub
    heaven3 = L.make(craft_at("Heaven", 3), __import__("random").Random(1), 0, 0).pub
    assert not mystic["reverse"] and not mystic["chaos"] and heaven3["reverse"] and heaven3["chaos"]
    beats = L.make(craft_at("Earth", 4), __import__("random").Random(1), 0, 0).pub["beats"]
    gaps = [b - a for a, b in zip(beats, beats[1:])]
    assert all(g2 < g1 for g1, g2 in zip(gaps, gaps[1:]))                 # Earth's beats quicken


def test_the_volatile_herb_goes_in_on_the_out_breath():
    import random
    from web import alchemy_live as L
    c = craft_at("Earth", 2)
    lv = L.make(c, random.Random(2), 0, 0)
    p = lv.pub
    t = 0.0
    while not lv.over:
        i = lv.data["placed"]
        b = p["breath"]
        t = (int(t / b) + 1) * b + (0 if p["volatile"] == i else b / 2)       # out-breath for it, in-breath for the rest
        L.press(lv, c, t, {"herb": c.order[i]})
    assert [m["how"] for m in lv.data["marks"]] == ["precise"] * p["count"]


def test_a_tap_on_the_chaos_orb_is_unsteady():
    import random
    from web import alchemy_live as L
    c = craft_at("Heaven", 3)
    lv = L.make(c, random.Random(4), 0, 0)
    r = L.press(lv, c, lv.pub["chaos"][0], {})
    assert r["hit"] is False and r["chaos"] and lv.data["unsteady"] == 1


def test_timing_is_precise_good_or_rough():
    import random
    from web import alchemy_live as L
    c = craft_at("Mystic", 3)
    lv = L.make(c, random.Random(4), 0, 0)
    w, m = lv.pub["window"], lv.pub["meet"]
    assert L.press(lv, c, m[0], {})["how"] == "precise"
    assert L.press(lv, c, m[1] + w * 0.9 + L.GRACE, {})["how"] == "good"
    assert L.press(lv, c, m[2] + w * 1.6 + L.GRACE, {})["how"] == "rough"


def test_rank_widens_windows_but_keeps_the_challenges():
    import random
    from web import alchemy_live as L
    at = L.make(craft_at("Heaven", 3), random.Random(1), 0, 0).pub
    above = L.make(craft_at("Heaven", 3, rank_above=3), random.Random(1), 0, 0).pub
    assert above["window"] == pytest.approx(at["window"] * 1.18, rel=0.01)
    assert above["chaos"] and above["reverse"]


def test_the_explosion_carries_its_craft_id(client):
    """static/alchemy.js plays the explosion once per craft by this id (the live controls never pass through it)."""
    begin(client, controls="live")
    s = client.crafts.get(UID)
    s.live = None
    while not s.craft.done:
        s.craft.settle(0.0)
    page = client.get("/alchemy/play").text
    assert 'class="cscene boom"' in page and f'data-craft="{int(s.started * 1000)}"' in page


def test_fuse_every_meeting_counts_and_precise_is_tight():
    import random
    from web import alchemy_live as L
    c = craft_at("Heaven", 3)
    lv = L.make(c, random.Random(4), 0, 0)
    p = lv.pub
    assert len(p["meet"]) == p["need"] and p["rush"]                     # no spare meetings on Fuse
    p["chaos"] = []                                                      # (its timing is tested on its own)
    assert L.press(lv, c, p["meet"][0] + p["window"] / 2 + L.GRACE_PRECISE * 0.5, {})["how"] == "precise"
    assert L.press(lv, c, p["meet"][1] + p["window"] / 2 + L.GRACE_PRECISE * 2, {})["how"] == "good"
    for m in p["meet"][3:]:                                              # the third meeting goes by untouched
        L.press(lv, c, m, {})
    L.settle(lv, c, lv.length + 1)
    assert c.scores[3] == pytest.approx((1 + 0.8 + 0 + 1 + 1) / 5)
    assert "1 missed" in c.log[0]


def test_a_one_herb_recipe_is_still_timed_live_but_free_on_the_buttons():
    import random
    from web import alchemy_live as L
    rank = crafting.pill_spec("cleansing", "Heaven")["rank"]
    button = crafting.Craft("cleansing", "Heaven", rank, 1000, random.Random(1))
    button.settle(1.0)
    assert button.scores.get(2) == 1.0 and button.stage == 3                  # Discord / Classic: nothing to choose
    c = crafting.Craft("cleansing", "Heaven", rank, 1000, random.Random(1))
    c.time_one_herb = True
    c.settle(1.0)
    assert c.stage == 2 and 2 not in c.scores                                 # live: the stage is played
    lv = L.make(c, random.Random(1), 0, 0)
    assert lv.pub["count"] == 3 and "add each one on the breath" in lv.pub["clues"][0] and not lv.pub["insights"]
    L.settle(lv, c, lv.length + 1)                                            # nothing added: it all goes cold
    assert c.scores[2] < 1.0


def test_live_crafts_time_one_herb_recipes(client):
    begin(client, controls="live")
    assert client.crafts.get(UID).craft.time_one_herb
    client.crafts.clear(UID)


def test_classic_page_has_no_reloading_timer_script(client):
    begin(client)
    page = client.get("/alchemy/play").text
    assert "alchemy_classic.js" in page and "location.replace('/alchemy/play')" not in page
    assert 'class="timer" data-left=' in page
