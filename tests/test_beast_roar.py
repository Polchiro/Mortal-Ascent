"""The beast roar (web/static/fight.js `roar`, scripts/make_roar_fx.py) is one shared effect: every beast picture has
its mouth on file, each tier has its wave, and it plays only as a beast winds up a big attack or roars itself."""
import json
import os

import beasts
from web import explore_play

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_beast_has_its_mouth_and_every_tier_its_wave():
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    for name in beasts.TRAITS:
        x, y, h = heads[beasts.slug(name)]
        assert 0 <= x <= 1 and 0 <= y <= 1 and 0 < h <= 1, name
    for wave in ("ring", "double", "burst"):
        assert os.path.exists(os.path.join(ROOT, "art", "fx", f"roar_{wave}.webp"))


def test_a_beast_roars_its_tier_and_colour():
    e = {"slug": "frost_wolf", "element": "Frost", "tier": "elite"}
    r = explore_play.beast_roar(e)
    assert r["head"] and r["wave"] == "double" and r["color"].startswith("#")
    assert explore_play.beast_roar({"slug": "someday_new", "tier": "normal"})["head"] is None   # a default on the page


def test_it_roars_only_when_winding_up_and_only_once():
    class B:
        log = [("fist", "x")]
    assert explore_play.roared([], B, "charged", True)[-1] == {"who": "enemy", "act": "roar", "why": "windup"}
    assert explore_play.roared([], B, "signature", True)[-1]["act"] == "roar"
    assert explore_play.roared([], B, None, True) == []                       # an ordinary turn: no roar
    assert explore_play.roared([], B, "charged", False) == []                 # bandits, or the fight is over
    once = explore_play.roared([{"who": "enemy", "act": "roar"}], B, "charged", True)
    assert sum(x["act"] == "roar" for x in once) == 1
