"""The website's forge (docs/web.md, "The forge"): the bot's own engine, refereed on the server."""
import urllib.parse

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

import forge  # noqa: E402
from bot import db, forging, item_catalog, loot, materials  # noqa: E402
from bot import player as rules  # noqa: E402
from web import app as web_app  # noqa: E402
from web import discord_oauth as oauth  # noqa: E402

UID = 777


def gear_id(path):
    c = db.connect(path)
    i = db.get_items(c, UID, "weapons")[0]["id"]
    c.close()
    return i


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "ma.db")
    c = db.connect(path)
    db.create_player(c, UID, "Smith", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(c, UID, lotus_coins=50_000)
    loot.store(c, UID, item_catalog.make("weapon:ordinary:sword", 1, quality="normal"))
    recipe = forge.RECIPE["ordinary"]
    loot.store(c, UID, [materials.material(forge.material_key("base", 1, gear="weapon"), recipe["base"] * 3),
                        materials.material(forge.material_key("binding", 1), recipe["binding"] * 3)])
    c.close()
    return path


@pytest.fixture
def client(db_path, monkeypatch):
    monkeypatch.setattr(oauth, "exchange_code", lambda *a: "t")
    monkeypatch.setattr(oauth, "fetch_user", lambda t: {"id": UID, "username": "smith", "avatar": None})
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=db_path, session_secret="s"))
    c = TestClient(app, base_url="http://localhost:8000", follow_redirects=False)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(c.get("/login").headers["location"]).query)
    c.get("/callback", params={"code": "x", "state": q["state"][0]})
    c.now = [1000.0]
    app.state.forges.clock = lambda: c.now[0]
    c.forges = app.state.forges
    return c


def coins(path):
    c = db.connect(path)
    v = db.get_player(c, UID)["lotus_coins"]
    c.close()
    return v


def begin(client, db_path, controls="classic"):
    return client.post("/forge/begin", data={"item": gear_id(db_path), "action": "enchant", "controls": controls})


def test_forge_page_shows_gear_and_cost(client, db_path):
    page = client.get("/forge")
    assert page.status_code == 200 and "Choose your gear" in page.text
    assert "Enchant" in page.text and "Begin forging" in page.text and "disabled" not in page.text.split("Begin forging")[0][-80:]
    assert f'name="item" value="{gear_id(db_path)}"' in page.text


def test_begin_takes_the_materials_and_coins(client, db_path):
    before = coins(db_path)
    r = begin(client, db_path)
    assert r.status_code == 303 and r.headers["location"] == "/forge/play"
    assert coins(db_path) == before - forge.forge_coins("enchant", "ordinary")
    play = client.get("/forge/play")
    assert "STAGE 1 OF 5" in play.text and "Pump" in play.text
    assert client.get("/forge").headers["location"] == "/forge/play"     # one forge at a time
    assert begin(client, db_path).headers["location"].startswith("/forge?")


def test_missing_materials_refuse_to_begin(client, db_path):
    c = db.connect(db_path)
    for it in db.get_items(c, UID, "materials"):
        db.remove_item(c, it["id"], it["qty"])
    c.close()
    page = client.get("/forge")
    assert "Missing:" in page.text
    r = begin(client, db_path)
    assert r.headers["location"].startswith("/forge?") and "Still missing" in client.get(r.headers["location"]).text
    assert client.forges.get(UID) is None


def play_to_the_end(client):
    for _ in range(80):
        s = client.forges.get(UID)
        if s.outcome is not None:
            return s
        pr = s.game.prompt()
        client.post("/forge/act", data={"key": pr.options[0][0], "turn": s.turn})
    raise AssertionError("the forge never finished")


def test_playing_every_stage_finishes_with_a_result(client, db_path):
    begin(client, db_path)
    s = play_to_the_end(client)
    page = client.get("/forge/play")
    assert "POINTS" in page.text and "Forge again" in page.text and "blacksmith EXP" in page.text
    c = db.connect(db_path)
    assert db.get_player(c, UID)["blacksmith_exp"] > 0
    item = db.get_items(c, UID, "weapons")[0]
    c.close()
    if s.outcome["rarity"]:
        assert (item["data"] or {}).get("passives")
    r = client.post("/forge/done")
    assert r.headers["location"] == "/forge" and client.forges.get(UID) is None


def test_old_turns_and_unknown_buttons_are_ignored(client, db_path):
    begin(client, db_path)
    s = client.forges.get(UID)
    client.post("/forge/act", data={"key": "explode", "turn": s.turn})
    assert s.turn == 0
    client.post("/forge/act", data={"key": "hold", "turn": 5})
    assert s.turn == 0
    client.post("/forge/act", data={"key": "hold", "turn": 0})
    assert s.turn == 1
    client.post("/forge/act", data={"key": "hold", "turn": 0})          # the same page sent twice
    assert s.turn == 1


def test_running_out_of_time_plays_the_timed_out_move(client, db_path):
    begin(client, db_path)
    s = client.forges.get(UID)
    client.now[0] += s.game.seconds + forge.TIMER_GRACE_SECONDS + 0.5
    client.get("/forge/play")
    assert s.turn == 1 and s.game.stage == "ignite"
    client.now[0] += 10_000                                             # walked away: everything times out
    client.get("/forge/play")
    assert s.outcome is not None and s.outcome["score"] < forge.FAIL_BELOW


def test_the_page_never_shows_the_hidden_answers(client, db_path):
    begin(client, db_path)
    s = client.forges.get(UID)
    page = client.get("/forge/play").text
    for shown in (f"{s.game.heat}°", f"({s.game.zone_width}° wide)", "0° cold", "100° wild"):
        page = page.replace(shown, "")
    assert f"{s.game.zone_lo}°" not in page and "zone_lo" not in page



# ── the live forge (web/forge_live.py) ───────────────────────────────

def live(client):
    return client.get("/forge/live").json()


def lpress(client, n, **ev):
    return client.post("/forge/live/press", data=dict(id=n, **ev)).json()


def test_live_is_the_default_and_shows_the_smith(client, db_path):
    r = client.post("/forge/begin", data={"item": gear_id(db_path), "action": "enchant"})
    assert r.headers["location"] == "/forge/play" and "ma_forge_controls=live" in r.headers["set-cookie"]
    page = client.get("/forge/play").text
    assert 'id="flive"' in page and "forge_live.js" in page and "/art/forge/anvil.webp" in page
    assert 'class="fscene nosmith"' in page                     # the smith is hidden unless the player turns him on
    for fx in ('class="ffire"', 'class="ftool"', "fqsteam", "fqflare", "fqblank"):   # the effects that move without him
        assert fx in page, fx
    assert "male_hammer.webp" in page and "male_bellows.webp" in page
    lv = live(client)["live"]
    assert lv["stage"] == "ignite" and {"lo", "width", "gusts", "heat"} <= set(lv["pub"])


def test_live_forge_perfect_hands_score_the_live_stages(client, db_path):
    import forge as F
    from web import forge_live as L
    begin(client, db_path, "live")
    s = client.forges.get(UID)
    for _ in range(3):
        lv = live(client)["live"]
        client.post("/forge/live/begin", data={"id": lv["id"]})
        t0, p, n = client.now[0], lv["pub"], lv["id"]
        if lv["stage"] == "ignite":
            heat, sp, pump, t, vented = float(p["heat"]), 0.0, False, 0.0, -9.0
            mid = p["lo"] + p["width"] / 2
            while t < p["length"]:
                want = heat + sp * 0.35 < mid
                if heat > p["lo"] + p["width"] - 1 and t - vented >= p["cooldown"]:     # too hot: vent it
                    client.now[0] = t0 + t
                    lpress(client, n, do="vent")
                    heat, vented = heat - p["vent"], t
                if want != pump:
                    pump = want
                    client.now[0] = t0 + t
                    lpress(client, n, do="pump" if pump else "rest")
                rest = p["down"] * (1 + p["burn"] * t / p["length"])
                w = p["up"] if pump else -rest
                sp += (w - sp) * min(1, p["tick"] / p["ease"])
                heat = max(0, min(100, heat + (sp + L.push_at(p, t)) * p["tick"]))
                t += p["tick"]
            client.now[0] = t0 + p["length"] + 1
            assert live(client)["last"]["pts"] >= 12                       # a simple steady hand
        elif lv["stage"] == "heat":
            b = p["bounds"]
            client.now[0] = t0 + (b[p["target"]] + b[p["target"] + 1]) / 2
            lpress(client, n, do="pull")
        else:
            for st in p["strikes"]:
                want = F.HAMMER_STATES[st["state"]]["answer"]
                for u in (st["under"] if want != "reheat" else [st["start"] + 0.2]):
                    client.now[0] = t0 + u
                    lpress(client, n, do=want)
            client.now[0] = t0 + p["length"] + 1
            live(client)
    assert s.game.points["heat"] == 20 and s.game.points["hammer"] == 20 and s.game.points["ignite"] >= 12
    st = live(client)
    assert st["live"]["stage"] == "quench"                                     # every stage is live now


def test_live_forge_button_stages_and_walking_away(client, db_path):
    begin(client, db_path, "live")
    live(client)
    client.now[0] += 3600
    st = live(client)
    assert st["done"]
    s = client.forges.get(UID)
    assert s.outcome is not None and set(s.game.points) == {"ignite", "heat", "hammer", "quench", "inscribe"}


def test_hammer_judging():
    import forge as F
    from web import forge_live as L
    p = {"window": 0.16, "strikes": [{"state": "true", "start": 0, "end": 1.5, "under": [0.8], "decoy": 0.3},
                                     {"state": "cooling", "start": 2, "end": 3.5, "under": [2.8]},
                                     {"state": "dull", "start": 4, "end": 5.5, "under": [4.7, 5.1]}]}
    assert L.strike_good(p, 0, [(0.82, "hard")])
    assert not L.strike_good(p, 0, [(0.82, "light")])                    # the wrong blow
    assert not L.strike_good(p, 0, [(0.3, "hard")])                      # the decoy
    assert L.strike_good(p, 1, [(2.3, "reheat")]) and not L.strike_good(p, 1, [(2.8, "hard")])
    assert L.strike_good(p, 2, [(4.7, "light"), (5.12, "light")]) and not L.strike_good(p, 2, [(4.7, "light")])
    assert F.HAMMER_STATES["true"]["answer"] == "hard"


def test_the_forge_art_is_served(client):
    for path in ("/art/forge/workshop.jpg", "/art/forge/workshop.mp4", "/art/forge/anvil.webp", "/art/forge/male_hammer.webp", "/art/forge/sparks.mp4",
                 "/art/forge/fire.mp4", "/art/forge/steam.mp4", "/art/forge/oil_flare.mp4", "/art/forge/tool_hammer.webp"):
        assert client.get(path).status_code == 200, path



def quench_game(medium="water", tier="ordinary", seed=3):
    import random
    from web import forge_live as L
    g = forging.Forge(tier, forge.RANK_NEEDED[tier], random.Random(seed))
    while g.stage != "quench":
        g.settle(1.0)
    return g, L, L.make(g, g.rng, 0, 0)


def time_to(L, p, medium, temp):
    """Seconds after choosing until the blade reaches temp."""
    t = 0.0
    while L.quench_temp(p, medium, t) > temp:
        t += 0.02
    return t


def test_live_quench_uses_the_bots_points():
    g, L, lv = quench_game()
    p = lv.pub
    L.press(lv, g, 0.5, {"do": "water"})
    L.press(lv, g, 0.5 + time_to(L, p, "water", p["target"]), {"do": "plunge"})
    L.settle(lv, g, lv.length)
    assert g.points["quench"] == forge.QUENCH["water"]["max_points"] and g.medium == "water"
    g, L, lv = quench_game()
    L.press(lv, g, 0.5, {"do": "oil"})
    L.settle(lv, g, lv.length + 1)                                       # never plunged: it went cold
    assert g.points["quench"] == forge.QUENCH_MISS_POINTS and g.stage == "inscribe"
    g, L, lv = quench_game()
    assert L.press(lv, g, 0.5, {"do": "plunge"}) == {}                   # no plunging before choosing


def test_live_quench_harder_gear_adds_draughts_steam_and_a_rush():
    _, _, easy = quench_game(tier="ordinary")
    _, _, hard = quench_game(tier="divine")
    assert not easy.pub["wave"] and not easy.pub["steam"] and not easy.pub["rush"]
    assert hard.pub["wave"] and hard.pub["steam"] and hard.pub["rush"]


def test_live_inscribe_judges_each_drawn_stroke_against_the_true_order():
    import random
    from web import forge_live as L
    g = forging.Forge("treasure", forge.RANK_NEEDED["treasure"], random.Random(5))
    while g.stage != "inscribe":
        g.settle(1.0)
    lv = L.make(g, g.rng, 0, 0)
    assert lv.pub["fade"] and lv.pub["clue"] == g.clue and lv.pub["count"] == len(g.order)
    wrong = next(k for k in forge.STROKES if k != g.order[0])
    r = L.press(lv, g, 0.5, {"do": wrong})
    assert r["ok"] is False and r["want"] == g.order[0]
    for i, k in enumerate(g.order[1:], 1):
        assert L.press(lv, g, 0.5 + i, {"do": k})["ok"]
    L.settle(lv, g, lv.length)
    n = len(g.order)
    assert g.done and g.points["inscribe"] == round((n - 1) / n * forge.STAGE_MAX_POINTS)


def test_the_live_page_loads_its_script_once(client, db_path):
    begin(client, db_path, "live")
    page = client.get("/forge/play").text
    assert page.count("forge_live.js") == 1 and "<script" not in page.split("</title>")[0].split("<title>")[1]
    assert 'class="forgebg"' in page


def test_the_rarity_forecast_follows_the_bot_rules_and_the_cap():
    """forge_play.forecast: what the points lock in, the best still possible, and the gear's cap (never above it)."""
    import random
    from types import SimpleNamespace
    from web import forge_play as FP
    g = forging.Forge("treasure", forge.RANK_NEEDED["treasure"], random.Random(1))
    s = SimpleNamespace(game=g, plan=SimpleNamespace(tier="treasure", essence=None))
    f = FP.forecast(s)
    assert (f["total"], f["max"], f["locked"], f["best"], f["cap"]) == (0, 100, None, "Legendary", "Legendary")
    assert [m["name"] for m in f["marks"] if m["over"]] == ["Mythical"]          # beyond Treasure gear's cap
    g.points.update(ignite=20, heat=20, hammer=20, quench=20)
    f = FP.forecast(s)
    assert (f["total"], f["max"]) == (80, 100)
    assert f["locked"] == "Rare"              # 80 with a blank inscription: Epic and up need a good one
    assert f["best"] == "Legendary"           # 100 would be Mythical, but the tier caps it
    g.points["inscribe"] = 10
    f = FP.forecast(s)
    assert f["locked"] == f["best"] == "Rare"  # 90, but an inscription of 10 holds back Epic
    o = SimpleNamespace(game=forging.Forge("ordinary", 1, random.Random(1)), plan=SimpleNamespace(tier="ordinary", essence=None))
    assert FP.forecast(o)["best"] == FP.forecast(o)["cap"] == "Rare"


def test_the_live_forge_page_has_its_hud_and_forecast(client, db_path):
    begin(client, db_path, "live")
    page = client.get("/forge/play").text
    for part in ('id="fcast"', 'id="fcfill"', 'class="fcam"', 'class="fhud"', 'class="ffx"', 'id="fcombo"'):
        assert part in page, part
    state = client.get("/forge/live").json()
    assert state["forecast"]["cap"] == "Rare" and state["forecast"]["total"] == 0
