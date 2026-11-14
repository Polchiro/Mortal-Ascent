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
        assert fx["motion"] in technique_fx.MOTIONS
        for name in fx["art"]:
            assert os.path.exists(os.path.join(ROOT, "art", "fx", "tech", name + ".webp")), name


def test_the_punch_techniques_have_their_looks():
    fist = {tid for tid, t in technique.TECHNIQUES.items() if t["school"] == "Fist"}
    assert fist <= set(technique_fx.TECH_FX)
    assert all(technique_fx.TECH_FX[t]["motion"] == "fist" for t in fist)


def test_the_palm_attack_techniques_share_the_palm_push():
    palm = {tid for tid, t in technique.TECHNIQUES.items() if t["school"] == "Palm" and t["type"] == "attack"}
    assert palm == {"twin_palm_strike", "rolling_thunder_palm", "thousand_shadow_palm", "heaven_rending_palm"}
    assert all(technique_fx.TECH_FX[t]["motion"] == "palm" for t in palm)
    assert len(technique_fx.TECH_FX["twin_palm_strike"]["art"]) == 2          # one print for each of its two hits


def test_nine_dragons_looses_nine_dragons_one_to_three_a_punch():
    punches = technique_fx.TECH_FX["nine_dragons_ascending_fist"]["punches"]
    assert sum(punches) == 9 and all(1 <= n <= 3 for n in punches)


def test_the_kick_techniques_share_one_kick_for_both_genders():
    leg = {tid for tid, t in technique.TECHNIQUES.items() if t["school"] == "Leg"}
    assert leg == {"crescent_sweep", "swift_swallow_kick", "autumn_wind_kick", "meteor_falling_kick"}
    assert all(technique_fx.TECH_FX[t]["motion"] == "kick" for t in leg)
    for gender in ("male", "female"):                      # one kick, the same effects and timing for each look
        for t in leg:
            fx = technique_fx.of(technique.TECHNIQUES[t]["name"], technique.TECHNIQUES[t]["grade"])
            assert fx["motion"] == "kick" and fx["art"]
        sheet = looks.motion_sheet({"gender": gender}, "kick")
        assert sheet is None or sheet["src"].endswith(f"hero_{gender}_kick.webp")   # frames, when added, are per look


def test_the_finger_techniques_share_the_jab_and_beam_from_the_fingertip():
    finger = {tid for tid, t in technique.TECHNIQUES.items() if t["school"] == "Finger"}
    assert finger == {"viper_fang_finger", "river_splitting_finger"}
    assert all(technique_fx.TECH_FX[t]["motion"] == "finger" and technique_fx.TECH_FX[t]["play"] == "beam" for t in finger)
    for gender in ("male", "female"):
        assert looks.motion_sheet({"gender": gender}, "finger")["hand"]           # where the beam leaves


def test_the_bracing_body_techniques_share_the_brace():
    body = {tid for tid, t in technique.TECHNIQUES.items() if t["school"] == "Body" and t["effect"] and t["effect"][0] != "evade"}
    assert body == {tid for tid, fx in technique_fx.TECH_FX.items() if fx["motion"] == "brace"}
    for gender in ("male", "female"):
        assert len(looks.motion_sheet({"gender": gender}, "brace")["body"]) == 4    # effects are placed around it


def test_a_defense_technique_event_says_what_it_did():
    class F:
        name = "Shoaib"
        atk_t = None
        def_t = {"name": "Golden Bell Cover", "type": "defense", "grade": "Earth"}
    ev = explore_play.events([("shield", "Shoaib — Golden Bell Cover: holds 70% of the Break")], F)
    assert ev[0]["hold"] == 70 and not ev[0]["blocked"]
    ev = explore_play.events([("shield", "Shoaib — Golden Bell Cover: blocked 100%, recovered 9, counters for 12")], F)
    assert ev[0]["blocked"] and ev[0]["heal"] == 9 and ev[0]["counter"] == 12


def test_a_look_carries_its_grade_length_and_art_urls():
    fx = technique_fx.of("Raging Bull Fist", "Yellow")
    assert fx["ms"] == technique_fx.GRADE_MS["Yellow"] and fx["mirror"]
    assert fx["art"] == ["/art/fx/tech/raging_bull_fist.webp"]
    assert technique_fx.of("Drifting Mist Steps", "Mystic") is None           # an evade: keeps its CSS look


def test_the_movement_frames_exist_for_both_cultivators():
    from PIL import Image
    for motion in looks.MOTION_SHEETS:
        for gender in ("male", "female"):
            sheet = looks.motion_sheet({"gender": gender}, motion)
            path = os.path.join(ROOT, sheet["src"].lstrip("/"))
            assert gender in sheet["src"] and Image.open(path).size == (320 * sheet["cols"], 360 * sheet["rows"])
            assert sheet["frames"] <= sheet["cols"] * sheet["rows"]
            assert 0 < sheet["jab"] <= sheet["release"] < sheet["back"] < sheet["frames"]
            assert all(0 < q < 1 for q in sheet["hand"])
        him, her = (looks.motion_sheet({"gender": g}, motion) for g in ("male", "female"))
        if motion in ("palm", "finger"):                  # made from his frames: the same movement, frame for frame
            assert all(him[k] == her[k] for k in ("frames", "jab", "release", "back"))   # (her punch and brace are her own)


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
