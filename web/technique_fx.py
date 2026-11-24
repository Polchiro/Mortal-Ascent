"""How each martial technique *looks* on the website fight screen: which shared movement the cultivator plays and
which of its own effect pictures fly. Presentation only (docs/web.md "Techniques"): nothing here is read by the
engine, and the engine's damage, Battle Qi, cooldowns and effects (technique.py, battle.py, bot/fight.py) never
read it. Keyed by the technique's id in technique.TECHNIQUES; a technique missing here keeps its CSS look.

    motion   the shared movement (looks.MOTION_SHEETS): "fist" is SHOAIB's punch video, a jab then a lunging punch;
             "palm" his palm video, a lunging two-handed palm push; "kick" a kick, shared by both genders: its
             timing and effects are defined once, and each look plays it with its own frames (looks.MOTION_SHEETS)
             or, until it has them, with its own three poses and a lunge and hop (fight.js `technique`): she has
             hers (hero_female_kick.webp, scripts/make_heroine_set.py), he has none yet;
             "finger" his finger-jab video, a lunge with two fingers thrust out; "brace" his brace video, arms
             crossed up into guard in a wide stance: the Body defense techniques that stand their ground, played
             inside the beast's attack (fight.js `braced`); "deflect" the deflection videos (MOVES_FX below, hers
             and his): meeting the blow and turning it aside, inside the beast's attack (fight.js `deflected`);
             "sidestep" (MOVES_FX): slipping the beast's Break (fight.js `sidestepped`)
    play    how fight.js `technique` plays the pictures (PLAYS)
    art      its pictures in art/fx/tech/ (scripts/make_fist_fx.py), the first being its main one
    punches  how many dragons fly from each punch, one punch after another (Nine Dragons Ascending Fist only)
    mirror   the main picture faces left and is turned to face the beast
"""
import technique as techniques

PLAYS = ("burst", "claw", "charge", "vortex", "rise", "dragons", "prints", "fan", "descend",
         "sweep", "streak", "whirl", "meteor", "beam",
         "dust", "mist", "sheen", "roots", "bell", "shell", "lotus", "parry",
         "glance", "stream", "crane", "moon", "hands", "void", "mist_steps", "cloud_steps")
MOTIONS = ("fist", "palm", "kick", "finger", "brace", "deflect", "sidestep")

TECH_FX = {
    # the punch techniques, from SHOAIB's designs (Gemini)
    "iron_fist": {"motion": "fist", "play": "burst", "art": ["iron_fist"]},
    "fierce_tiger_claw": {"motion": "fist", "play": "claw", "art": ["fierce_tiger_claw"]},
    "raging_bull_fist": {"motion": "fist", "play": "charge", "art": ["raging_bull_fist"], "mirror": True},
    "mountain_shattering_fist": {"motion": "fist", "play": "rise", "art": ["mountain_shattering_fist"]},
    "nine_dragons_ascending_fist": {"motion": "fist", "play": "dragons", "punches": [1, 2, 3, 3],    # nine in all
                                    # moving, from SHOAIB's videos (scripts/make_dragon_fx.py): one dragon flying, played
                                    # for each dragon loosed; and the finale, the dragons coiling up and exploding
                                    # (`boom`: the frame of the explosion, where the damage lands)
                                    "art": ["nine_dragons_finale", "nine_dragons_fly"],
                                    "sheets": {"fly": {"frames": 16, "cols": 8, "rows": 2},
                                               "finale": {"frames": 50, "cols": 8, "rows": 7, "boom": 29}}},
    # the palm techniques, from SHOAIB's designs (Gemini), all played with the palm push
    "twin_palm_strike": {"motion": "palm", "play": "prints", "art": ["twin_palm_strike_1", "twin_palm_strike_2"]},
    "rolling_thunder_palm": {"motion": "palm", "play": "vortex", "art": ["rolling_thunder_palm"]},
    "thousand_shadow_palm": {"motion": "palm", "play": "fan", "art": ["thousand_shadow_palm"]},
    "heaven_rending_palm": {"motion": "palm", "play": "descend", "art": ["heaven_rending_palm"]},
    # the kick techniques, from SHOAIB's designs (Gemini, scripts/make_kick_fx.py), all played with the kick
    "crescent_sweep": {"motion": "kick", "play": "sweep", "art": ["crescent_sweep"]},
    "swift_swallow_kick": {"motion": "kick", "play": "streak", "art": ["swift_swallow_kick"], "mirror": True},
    "autumn_wind_kick": {"motion": "kick", "play": "whirl", "art": ["autumn_wind_kick"]},
    "meteor_falling_kick": {"motion": "kick", "play": "meteor", "art": ["meteor_falling_kick"]},
    # the finger techniques, from SHOAIB's designs (Gemini, scripts/make_finger_fx.py), both played with the jab:
    # a beam whose tail stays on the fingertip and whose head reaches the beast
    "viper_fang_finger": {"motion": "finger", "play": "beam", "art": ["viper_fang_finger"]},
    "river_splitting_finger": {"motion": "finger", "play": "beam", "art": ["river_splitting_finger"], "part": True},
    # the Body defense techniques that brace, from SHOAIB's designs (Gemini, scripts/make_brace_fx.py): the effect
    # forms as the fighter settles into the stance and takes the beast's blow. Parrying Arm has no design: the brace,
    # sparks and its counter. Drifting Mist Steps and Cloud-Walking Shadow (evades) keep their CSS look.
    "horse_stance_guard": {"motion": "brace", "play": "dust", "art": ["horse_stance_guard"]},
    "parrying_arm": {"motion": "brace", "play": "parry", "art": []},
    "calm_breath_stance": {"motion": "brace", "play": "mist", "art": ["calm_breath_stance"]},
    "iron_cloth_body": {"motion": "brace", "play": "sheen", "art": ["iron_cloth_body"]},
    "rooted_mountain_stance": {"motion": "brace", "play": "roots", "art": ["rooted_mountain_stance"]},
    "golden_bell_cover": {"motion": "brace", "play": "bell", "art": ["golden_bell_cover"]},
    "ancient_turtle_shell_art": {"motion": "brace", "play": "shell", "art": ["ancient_turtle_shell_art"]},
    "immortal_lotus_body": {"motion": "brace", "play": "lotus", "art": ["immortal_lotus_body"]},
}

# The deflections and sidesteps, from SHOAIB's designs (Gemini, scripts/make_deflect_fx.py, make_sidestep_fx.py), for
# both cultivators, each with their own movement (looks.MOTION_SHEETS "deflect" and "sidestep", hers and his). The
# deflections play with the deflection (fight.js `deflected`): inside the beast's attack the cultivator meets the
# blow and turns it aside, then settles back on guard; no guarding stance.
MOVES_FX = {
    "parrying_arm": {"motion": "deflect", "play": "glance", "art": ["parrying_arm"]},
    "flowing_stream_palm": {"motion": "deflect", "play": "stream", "art": ["flowing_stream_palm"]},
    "crane_wing_deflection": {"motion": "deflect", "play": "crane", "art": ["crane_wing_deflection"]},
    "moon_mirror_palm": {"motion": "deflect", "play": "moon", "art": ["moon_mirror_palm"]},
    "thousand_hands_deflection": {"motion": "deflect", "play": "hands", "art": ["thousand_hands_deflection"]},
    "void_mirror_stance": {"motion": "deflect", "play": "void", "art": ["void_mirror_stance"]},
    # the sidesteps, both played with the sidestep (fight.js `sidestepped`), and only `on` a turn the technique left
    # the cultivator untouched (explore_play.untouched): the Break slipped, or a Strike taken with a full block; the
    # blow passes through the afterimages. When a Break gets through (held in part), the technique keeps its CSS look.
    "drifting_mist_steps": {"motion": "sidestep", "play": "mist_steps", "art": ["drifting_mist_steps"], "on": "evade"},
    "cloud_walking_shadow": {"motion": "sidestep", "play": "cloud_steps", "art": ["cloud_walking_shadow"], "on": "evade"},
}
BY_GENDER = {"female": MOVES_FX, "male": MOVES_FX}   # looks one cultivator could have in place of TECH_FX

# how long a cast lasts on screen, by grade (ms): higher grades get more time for more spectacle
GRADE_MS = {"Mortal": 1100, "Yellow": 1300, "Mystic": 1600, "Earth": 2100, "Heaven": 2700}

_BY_NAME = {t["name"]: tid for tid, t in techniques.TECHNIQUES.items()}


def technique_id(name):
    return _BY_NAME.get(name)


def of(name, grade, gender=None, happened=None):
    """The look of the technique with this name, for the page, as the cultivator of this gender plays it (looks.GENDERS);
    None to keep the CSS look. `happened`: the effect it had this turn (explore_play.cast); a look that plays only
    `on` one effect (her sidesteps: "evade") gives way to the shared look, or the CSS one, on any other turn."""
    tid = technique_id(name)
    fx = BY_GENDER.get(gender, {}).get(tid)
    if fx and fx.get("on") and fx["on"] != happened:
        fx = None
    fx = fx or TECH_FX.get(tid)
    if not fx:
        return None
    return {"motion": fx["motion"], "play": fx["play"], "mirror": bool(fx.get("mirror")), "part": bool(fx.get("part")),
            "punches": fx.get("punches", [1]), "ms": GRADE_MS.get(grade, 1100), "sheets": fx.get("sheets"),
            "art": [f"/art/fx/tech/{a}.webp" for a in fx["art"]]}


def assets(name, gender=None):
    """Everything the page may show for this technique, whatever happens on the turn: its movements (MOTIONS) and its
    pictures, so the fight can load them before they are needed (explore_play.preload)."""
    tid = technique_id(name)
    looks_ = [fx for fx in (BY_GENDER.get(gender, {}).get(tid), TECH_FX.get(tid)) if fx]
    return ([fx["motion"] for fx in looks_], [f"/art/fx/tech/{a}.webp" for fx in looks_ for a in fx["art"]])
