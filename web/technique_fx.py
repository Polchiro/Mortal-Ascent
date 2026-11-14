"""How each martial technique *looks* on the website fight screen: which shared movement the cultivator plays and
which of its own effect pictures fly. Presentation only (docs/web.md "Techniques"): nothing here is read by the
engine, and the engine's damage, Battle Qi, cooldowns and effects (technique.py, battle.py, bot/fight.py) never
read it. Keyed by the technique's id in technique.TECHNIQUES; a technique missing here keeps its CSS look.

    motion   the shared movement (looks.MOTION_SHEETS): "fist" is SHOAIB's punch video, a jab then a lunging punch
    play     how fight.js `technique` plays the pictures (PLAYS)
    art      its pictures in art/fx/tech/ (scripts/make_fist_fx.py), the first being its main one
    punches  how many dragons fly from each punch, one punch after another (Nine Dragons Ascending Fist only)
    mirror   the main picture faces left and is turned to face the beast
"""
import technique as techniques

PLAYS = ("burst", "claw", "charge", "vortex", "rise", "dragons")

TECH_FX = {
    # the punch techniques, from SHOAIB's designs (Gemini)
    "iron_fist": {"motion": "fist", "play": "burst", "art": ["iron_fist"]},
    "fierce_tiger_claw": {"motion": "fist", "play": "claw", "art": ["fierce_tiger_claw"]},
    "raging_bull_fist": {"motion": "fist", "play": "charge", "art": ["raging_bull_fist"], "mirror": True},
    "rolling_thunder_palm": {"motion": "fist", "play": "vortex", "art": ["rolling_thunder_palm"]},   # a Palm technique, thrown with the punch
    "mountain_shattering_fist": {"motion": "fist", "play": "rise", "art": ["mountain_shattering_fist"]},
    "nine_dragons_ascending_fist": {"motion": "fist", "play": "dragons", "punches": [1, 2, 3, 3],    # nine in all
                                    "art": ["nine_dragons_ascending_fist", "nine_dragons_head_1", "nine_dragons_head_2",
                                            "nine_dragons_head_3"]},
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
    return {"motion": fx["motion"], "play": fx["play"], "mirror": bool(fx.get("mirror")),
            "punches": fx.get("punches", [1]), "ms": GRADE_MS.get(grade, 1100),
            "art": [f"/art/fx/tech/{a}.webp" for a in fx["art"]]}
