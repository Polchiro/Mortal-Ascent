"""The /breakthrough result card (bot/breakthrough_card.py, cards/breakthrough.py)."""
import random

import training
from bot import breakthrough_card as bc, materials
from bot import player as rules


def player(realm="Martial Expert", layer=10, qi=None):
    p = {"realm": realm, "layer": layer, "qi_overflow": 0.0, "breakthroughs": 3, "equipped_artifacts": None}
    p["qi"] = float(rules.qi_needed(realm, layer)) if qi is None else qi
    return p


def test_success_and_failure_data_match_the_attempt():
    before = player(layer=3)
    after = dict(before)
    ok, _ = rules.attempt_breakthrough(after, rng=random.Random(1))       # Martial Expert phase gates succeed 90%
    assert ok
    d = bc.card_data("A", before, after, "phase", "Middle Phase", ok, 0.9, dew=materials.breakthrough_dew("phase"))
    assert d["from"] == "Early Phase" and d["to"] == "Middle Phase"
    assert d["facts"][0][1] == "4th Layer" and len(d["facts"]) <= 3
    d = bc.card_data("A", player(), dict(player(), realm="Martial Master", layer=1), "realm", "Martial Master",
                     True, 1.0)
    assert d["facts"][0][1] == "1st Layer" and d["to"] == "Martial Master"

    before = player(layer=6)
    after = dict(before, qi=before["qi"] * (1 - training.BREAKTHROUGH_FAIL_QI_LOSS))
    d = bc.card_data("A", before, after, "phase", "Late Phase", False, 0.9)
    assert d["from"] == "Middle Phase" and d["facts"][0][1].startswith("−")
    d = bc.card_data("A", player(), player(), "realm", "Martial Master", False, 0.7,
                     pill={"name": "Earth Breakthrough Pill", "grade": "Earth"})
    assert any(f[1] == f"{training.INJURY_HOURS}h injury" for f in d["facts"])


def test_every_scene_renders():
    from cards.breakthrough import W, render_breakthrough
    for kind, target in (("realm", "Martial Master"), ("phase", "Late Phase")):
        for ok in (True, False):
            d = bc.card_data("A", player(layer=10 if kind == "realm" else 6), player(), kind, target, ok, 0.8)
            assert render_breakthrough(d).size[0] == W
