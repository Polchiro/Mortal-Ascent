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
    assert st["last"]["stage"] == 1 and st["last"]["score"] >= 0.95
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
    assert 'class="tier"' in client.get("/alchemy/play").text


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


def test_live_tribulation_uses_the_bots_strike_directions():
    import random
    from web import alchemy_live as L
    c = crafting.Craft("qi", "Mortal", 9, 1000, random.Random(2))
    c.settle(1.0)
    c.settle(1.0)
    assert c.tribulation == "pending"
    lv = L.make(c, c.rng, 0, 0)
    assert lv.stage == 6 and "from" not in str(lv.pub)
    for omen, bolt in lv.pub["strikes"]:
        assert L.press(lv, c, omen - 1.0, {"omen": True}).get("from") is None     # not before the clouds show it
        way = L.press(lv, c, omen + 0.1, {"omen": True})["from"]
        L.press(lv, c, omen + 0.2, {"shield": way})
    L.settle(lv, c, lv.length + 1)
    assert c.done and c.tribulation == "won" and c.result == 9


def test_live_seal_shatters_the_core_when_missed():
    import random
    from web import alchemy_live as L
    c = crafting.Craft("breakthrough", "Mortal", 9, 10, random.Random(5))
    while c.stage != 5:
        c.settle(1.0)
    lv = L.make(c, c.rng, 0, 0)
    L.settle(lv, c, lv.length + 1)
    assert c.done and c.core_lost and c.result == 0


def test_result_tiers():
    from web import alchemy_live as L
    assert [L.tier(n)["name"] for n in (0, 1, 3, 4, 6, 7, 8, 9)] == [
        "Failed", "Normal", "Normal", "High quality", "High quality", "Superior", "Superior", "Perfect"]
