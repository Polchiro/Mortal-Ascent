"""How each martial technique *looks* on the website fight screen: which shared movement the cultivator plays and
which of its own effect pictures fly. Presentation only (docs/web.md "Techniques"): nothing here is read by the
engine, and the engine's damage, Battle Qi, cooldowns and effects (technique.py, battle.py, bot/fight.py) never
read it. Keyed by the technique's id in technique.TECHNIQUES; a technique missing here keeps its CSS look.

    motion   the shared movement (looks.MOTION_SHEETS): "fist" is SHOAIB's punch video, a jab then a lunging punch;
             "palm" his palm video, a lunging two-handed palm push; "kick" a kick, shared by both genders: its
             timing and effects are defined once, and each look plays it with its own frames (looks.MOTION_SHEETS)
             or, until it has them, with its own three poses and a lunge and hop (fight.js `technique`);
             "finger" his finger-jab video, a lunge with two fingers thrust out; "brace" his brace video, arms
             crossed up into guard in a wide stance: the Body defense techniques that stand their ground, played
             inside the beast's attack (fight.js `braced`)
    play     how fight.js `technique` plays the pictures (PLAYS)
    art      its pictures in art/fx/tech/ (scripts/make_fist_fx.py), the first being its main one
    punches  how many dragons fly from each punch, one punch after another (Nine Dragons Ascending Fist only)
    mirror   the main picture faces left and is turned to face the beast
"""
import technique as techniques

PLAYS = ("burst", "claw", "charge", "vortex", "rise", "dragons", "prints", "fan", "descend",
         "sweep", "streak", "whirl", "meteor", "beam",
         "dust", "mist", "sheen", "roots", "bell", "shell", "lotus", "parry")
MOTIONS = ("fist", "palm", "kick", "finger", "brace")

TECH_FX = {
    # the punch techniques, from SHOAIB's designs (Gemini)
    "iron_fist": {"motion": "fist", "play": "burst", "art": ["iron_fist"]},
    "fierce_tiger_claw": {"motion": "fist", "play": "claw", "art": ["fierce_tiger_claw"]},
    "raging_bull_fist": {"motion": "fist", "play": "charge", "art": ["raging_bull_fist"], "mirror": True},
    "mountain_shattering_fist": {"motion": "fist", "play": "rise", "art": ["mountain_shattering_fist"]},
    "nine_dragons_ascending_fist": {"motion": "fist", "play": "dragons", "punches": [1, 2, 3, 3],    # nine in all
                                    "art": ["nine_dragons_ascending_fist", "nine_dragons_head_1", "nine_dragons_head_2",
                                            "nine_dragons_head_3"]},
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

# how long a cast lasts on screen, by grade (ms): higher grades get more time for more spectacle
GRADE_MS = {"Mortal": 1100, "Yellow": 1300, "Mystic": 1600, "Earth": 2100, "Heaven": 2700}

_BY_NAME = {t["name"]: tid for tid, t in techniques.TECHNIQUES.items()}


def technique_id(name):
    return _BY_NAME.get(name)


def of(name, grade):
    """The look of the technique with this name, for the page; None to keep the CSS look."""
    tid = technique_id(name)
    fx = TECH_FX.get(tid)
    if not fx:
        return None
    return {"motion": fx["motion"], "play": fx["play"], "mirror": bool(fx.get("mirror")), "part": bool(fx.get("part")),
            "punches": fx.get("punches", [1]), "ms": GRADE_MS.get(grade, 1100),
            "art": [f"/art/fx/tech/{a}.webp" for a in fx["art"]]}
