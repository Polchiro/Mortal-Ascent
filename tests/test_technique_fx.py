"""The website's technique looks (web/technique_fx.py) are presentation only: they name real techniques, point at
art that exists, and never touch what a technique does."""
import os

import looks
import technique
from web import explore_play, technique_fx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_look_is_an_existing_technique_with_its_art():
    for tid, fx in technique_fx.TECH_FX.items():
        assert tid in technique.TECHNIQUES, tid
        assert fx["play"] in technique_fx.PLAYS
        assert fx["motion"] in looks.MOTION_SHEETS
        for name in fx["art"]:
            assert os.path.exists(os.path.join(ROOT, "art", "fx", "tech", name + ".webp")), name


def test_the_punch_techniques_have_their_looks():
    fist = {tid for tid, t in technique.TECHNIQUES.items() if t["school"] == "Fist"}
    assert fist <= set(technique_fx.TECH_FX)
    assert "rolling_thunder_palm" in technique_fx.TECH_FX


def test_nine_dragons_looses_nine_dragons_one_to_three_a_punch():
    punches = technique_fx.TECH_FX["nine_dragons_ascending_fist"]["punches"]
    assert sum(punches) == 9 and all(1 <= n <= 3 for n in punches)


def test_a_look_carries_its_grade_length_and_art_urls():
    fx = technique_fx.of("Raging Bull Fist", "Yellow")
    assert fx["ms"] == technique_fx.GRADE_MS["Yellow"] and fx["mirror"]
    assert fx["art"] == ["/art/fx/tech/raging_bull_fist.webp"]
    assert technique_fx.of("Horse Stance Guard", "Mortal") is None            # no look yet: keeps its CSS one


def test_the_punch_frames_exist_for_the_male_cultivator():
    sheet = looks.motion_sheet({"gender": "male"}, "fist")
    assert os.path.exists(os.path.join(ROOT, sheet["src"].lstrip("/")))
    assert 0 < sheet["jab"] < sheet["release"] < sheet["back"] < sheet["frames"]
    assert looks.motion_sheet({"gender": "female"}, "fist") is None           # she plays it through her poses


def test_a_technique_event_carries_its_damage():
    class F:
        name = "Shoaib"
        atk_t = {"name": "Iron Fist", "type": "attack", "grade": "Mortal"}
        def_t = None
    ev = explore_play.events([("fist", "Shoaib — Iron Fist: 1,234 dmg, blows clash")], F)
    assert ev == [{"who": "me", "act": "tech", "hit": True, "dmg": 1234}]
    ev = explore_play.events([("fist", "Shoaib — Iron Fist: dodged!")], F)
    assert ev == [{"who": "me", "act": "tech", "hit": False, "dmg": 0}]


def test_technique_data_is_untouched_by_the_looks():
    """The looks add nothing to the game's technique data (names, grades, schools, effects stay as they are)."""
    for tid in technique_fx.TECH_FX:
        assert set(technique.TECHNIQUES[tid]) == {"name", "type", "grade", "school", "effect"}
