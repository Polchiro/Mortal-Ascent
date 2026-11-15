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


def test_her_finger_jab_is_her_own():
    her = looks.motion_sheet({"gender": "female"}, "finger")
    assert her["src"].endswith("hero_female_finger.webp") and her["frames"] == 28
    assert 0 < her["jab"] <= her["windup"] < her["release"] < her["back"] < her["frames"]
    assert all(0 < q < 1 for q in her["hand"])


def test_her_palm_push_is_her_own():
    her = looks.motion_sheet({"gender": "female"}, "palm")
    assert her["src"].endswith("hero_female_palm.webp") and her["frames"] == 40
    assert 0 < her["windup"] < her["release"] < her["back"] < her["frames"]
    assert all(0 < q < 1 for q in her["hand"])


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
        genders = ("male", "female")
        assert set(looks.MOTION_SHEETS[motion]) == set(genders)
        for gender in genders:
            sheet = looks.motion_sheet({"gender": gender}, motion)
            path = os.path.join(ROOT, sheet["src"].lstrip("/"))
            assert gender in sheet["src"] and Image.open(path).size == (320 * sheet["cols"], 360 * sheet["rows"])
            assert sheet["frames"] <= sheet["cols"] * sheet["rows"]
            assert 0 < sheet["jab"] <= sheet["release"] < sheet["back"] < sheet["frames"]
            assert all(0 < q < 1 for q in sheet["hand"])
        if motion in ("deflect", "sidestep"):
            continue
        her = looks.motion_sheet({"gender": "female"}, motion)
        if "windup" in her:
            assert her["jab"] <= her["windup"] < her["release"]       # drawn back, then out


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
    for tid in list(technique_fx.TECH_FX) + list(technique_fx.MOVES_FX):
        assert set(technique.TECHNIQUES[tid]) == {"name", "type", "grade", "school", "effect"}


DEFLECTIONS = {"parrying_arm", "flowing_stream_palm", "crane_wing_deflection", "moon_mirror_palm",
               "thousand_hands_deflection", "void_mirror_stance"}


SIDESTEPS = {"drifting_mist_steps", "cloud_walking_shadow"}


def test_the_deflections_are_the_six_deflection_techniques_with_their_art():
    assert set(technique_fx.MOVES_FX) == DEFLECTIONS | SIDESTEPS
    for tid in DEFLECTIONS:
        fx = technique_fx.MOVES_FX[tid]
        assert technique.TECHNIQUES[tid]["type"] == "defense"
        assert fx["motion"] == "deflect" and fx["play"] in technique_fx.PLAYS
        assert fx["art"] == [tid]                                     # its own picture for each, no placeholder
        assert os.path.exists(os.path.join(ROOT, "art", "fx", "tech", tid + ".webp")), tid


def test_both_cultivators_deflect_each_with_their_own_frames():
    for tid in DEFLECTIONS:
        t = technique.TECHNIQUES[tid]
        for gender in ("female", "male"):
            fx = technique_fx.of(t["name"], t["grade"], gender)
            assert fx["motion"] == "deflect" and fx["art"] == [f"/art/fx/tech/{tid}.webp"]
    him, her = (looks.motion_sheet({"gender": g}, "deflect") for g in ("male", "female"))
    assert him["src"].endswith("hero_male_deflect.webp") and her["src"].endswith("hero_female_deflect.webp")
    # every technique looks the same for both (each played with their own frames)
    for tid, t in technique.TECHNIQUES.items():
        for happened in (None, "evade"):
            assert technique_fx.of(t["name"], t["grade"], "female", happened) == \
                technique_fx.of(t["name"], t["grade"], "male", happened)


def test_the_deflection_meets_the_blow_then_carries_it_aside_and_recovers():
    for gender in ("female", "male"):
        d = looks.motion_sheet({"gender": gender}, "deflect")
        assert 0 < d["jab"] < d["release"] < d["sweep"] < d["back"] < d["frames"]
        assert all(0 < q < 1 for q in d["hand"] + d["tip"]) and len(d["body"]) == 4
        assert d["hand"][0] > d["body"][0] > d["tip"][0]              # meets it in front, carries it behind


def test_the_sidesteps_are_the_two_evades_and_play_only_when_the_evade_worked():
    evades = {tid for tid, t in technique.TECHNIQUES.items() if t["effect"] and t["effect"][0] == "evade"}
    assert evades == SIDESTEPS
    for tid in SIDESTEPS:
        t = technique.TECHNIQUES[tid]
        fx = technique_fx.MOVES_FX[tid]
        assert fx["motion"] == "sidestep" and fx["play"] in technique_fx.PLAYS and fx["art"] == [tid]
        assert os.path.exists(os.path.join(ROOT, "art", "fx", "tech", tid + ".webp")), tid
        for gender in ("female", "male"):
            fx = technique_fx.of(t["name"], t["grade"], gender, "evade")
            assert fx["motion"] == "sidestep" and fx["art"] == [f"/art/fx/tech/{tid}.webp"]
            for other in (None, "", "hold"):                          # held the Break, or the beast only struck
                assert technique_fx.of(t["name"], t["grade"], gender, other) is None  # the CSS look, as before


def test_the_sidesteps_play_at_the_videos_pace_and_end_on_their_feet():
    her, him = (looks.motion_sheet({"gender": g}, "sidestep") for g in ("female", "male"))
    assert her["frames"] == 27 and him["frames"] == 24               # every 2nd frame of the 24 fps videos
    for d in (her, him):
        assert d["fps"] == 12
        assert 0 < d["jab"] < d["release"] < d["back"] < d["frames"]
        assert len(d["body"]) == 4 and all(0 < q < 1 for q in d["hand"])
    assert her["give"] > 0 and him["give"] == 0                     # she gives ground; he dashes in place


def test_a_slipped_break_is_the_evade_techniques_event():
    class F:
        name = "Shoaib"
        atk_t = None
        def_t = {"name": "Drifting Mist Steps", "type": "defense", "grade": "Mystic"}
    ev = explore_play.events([("shield", "Shoaib slipped away from the Leopard's Break")], F)
    assert ev == [{"who": "me", "act": "tech", "hit": False, "dmg": 0, "blocked": False, "hold": 0, "heal": 0,
                   "counter": 0, "evaded": True}]
    held = explore_play.events([("shield", "Shoaib — Drifting Mist Steps: holds 30% of the Break"),
                                ("skull", "Leopard — Break on Shoaib −120")], F)
    assert "evaded" not in held[0] and held[0]["hold"] == 30 and held[1]["dmg"] == 120
    F.def_t = None                                                   # no defense technique: nothing of the kind
    assert explore_play.events([("shield", "Shoaib slipped away from the Leopard's Break")], F) == []


def test_a_slipped_break_lands_the_cast_with_her_sidestep():
    class F:
        name = "Shoaib"
        atk_t = None
        def_t = {"name": "Cloud-Walking Shadow", "type": "defense", "grade": "Heaven"}
        last_move = "Cloud-Walking Shadow"
    class B:
        log = [("shield", "Shoaib slipped away from the Leopard's Break")]
    her = explore_play.cast(B, F, "female")
    assert her["landed"] and her["effect"] == "evade" and her["fx"]["motion"] == "sidestep"
    him = explore_play.cast(B, F, "male")
    assert him["landed"] and him["effect"] == "evade" and him["fx"]["motion"] == "sidestep"   # his own sidestep
    B.log = [("shield", "Shoaib — Cloud-Walking Shadow: holds 50% of the Break"), ("skull", "Leopard — Break on Shoaib −80")]
    held = explore_play.cast(B, F, "female")
    assert held["effect"] == "hold" and held["fx"] is None
