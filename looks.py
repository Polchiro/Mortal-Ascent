"""
Character appearance: male or female. docs/appearance.md.

The look is only a picture. It never touches stats, fights or anything else in the game.

Each gender has one painting of the cultivator in white and blue robes (art/portraits/hero_<gender>.webp,
see-through background) and a round face (art/portraits/hero_<gender>_face.webp). In website fights each has
three sword poses (art/portraits/fight/hero_<gender>_{idle,windup,strike}.webp). A player who hasn't chosen a look shows the male painting.
"""
import json

GENDERS = {"male": "Male", "female": "Female"}
DEFAULT_GENDER = "male"             # the painting shown until a player chooses
FREE_CHANGES = 1                    # choosing your first look costs nothing
CHANGE_PEARLS = 200                 # every change after that, in Moon Pearls


def parse(raw):
    """A stored appearance (JSON text) as a clean dict, or None if the player hasn't chosen one.
    Looks saved while hairstyles and hair colours existed carry "hair" and "color"; only the gender counts now."""
    if not raw:
        return None
    try:
        return clean(json.loads(raw).get("gender"))
    except (ValueError, AttributeError):
        return None


def clean(gender):
    """{'gender'} if it is a real option, else None."""
    return {"gender": gender} if gender in GENDERS else None


def dump(look):
    return json.dumps({"gender": look["gender"]}, sort_keys=True)


def describe(look):
    """'Female'."""
    return GENDERS[look["gender"]]


def change_cost(player):
    """Moon Pearls the next change costs (0 while the free one is left)."""
    return 0 if (player.get("appearance_changes") or 0) < FREE_CHANGES else CHANGE_PEARLS


def of_player(player):
    """The player's chosen look, or None (they still show the default painting)."""
    return parse(player.get("appearance")) if player else None


def gender_of(look):
    return look["gender"] if look else DEFAULT_GENDER


def portrait(look):
    """The full painting (profile, Appearance page), as a website path."""
    return f"/art/portraits/hero_{gender_of(look)}.webp"


POSES = ("idle", "windup", "strike")
SWORD_POSES = {"male": 0.66, "female": 0.82}   # genders painted in the sword poses: how far the blade reaches (0-1)
# genders whose sword attack plays frame by frame (scripts/make_hero_attack.py cuts it from SHOAIB's video):
# a grid of 320 x 360 frames that web/static/fight.js steps through; the stills above come from the same video.
ATTACK_SHEETS = {"male": {"src": "/art/portraits/fight/hero_male_attack.webp", "frames": 41, "cols": 8, "rows": 6}}

# the same for Guard: he blocks with the blade, a gold flash and sparks where the blow lands (SHOAIB's second video)
GUARD_SHEETS = {"male": {"src": "/art/portraits/fight/hero_male_guard.webp", "frames": 37, "cols": 8, "rows": 5}}

# the shared movements techniques play (web/technique_fx.py "motion"), frame by frame, in the same 320 x 360 cells.
# "fist": SHOAIB's punch video (scripts/make_hero_fist.py): on guard (0-1), a jab (out at `jab`), the fist drawn
# back (7-8), a lunging punch (out at `release`), held, drawn back (21-27), on guard again (28-35). `shift`: he was
# moved left inside his cells so the lunge isn't cut off, by this share of a cell; the page moves him back.
# "palm": SHOAIB's palm video (scripts/make_hero_palm.py): on guard (0-4), both arms drawn back (5-9), a lunging
# two-handed palm push (out at `release`), held, then rising back to guard (`back` on).
# `hand`: where the fist or palms are at the release, as shares of the fighter's box (effects fly from there).
MOTION_SHEETS = {"fist": {"male": {"src": "/art/portraits/fight/hero_male_fist.webp", "frames": 36, "cols": 8, "rows": 5,
                                   "jab": 5, "release": 12, "back": 21, "shift": 18 / 320, "hand": [0.685, 0.287]}},
                 "palm": {"male": {"src": "/art/portraits/fight/hero_male_palm.webp", "frames": 48, "cols": 8, "rows": 6,
                                   "jab": 12, "release": 14, "back": 40, "shift": 7 / 320, "hand": [0.66, 0.231]}}}


def fighter(look, pose="idle"):
    """The fighter on the 1024 x 559 fight canvas, facing right, in one of POSES (web/static/fight.js swaps them)."""
    gender = gender_of(look)
    if gender in SWORD_POSES:
        return f"/art/portraits/fight/hero_{gender}_{pose}.webp"
    return f"/art/portraits/fight/hero_{gender}.webp"


def sword_tip(look):
    """How far across the fight canvas the weapon reaches in the strike pose (0-1), or None for a single painting."""
    return SWORD_POSES.get(gender_of(look))


def attack_sheet(look):
    """The frame-by-frame sword attack for this look (ATTACK_SHEETS), or None to swing through the three poses."""
    return ATTACK_SHEETS.get(gender_of(look))


def guard_sheet(look):
    """The frame-by-frame sword block for this look (GUARD_SHEETS), or None to stand in the idle pose behind the ring."""
    return GUARD_SHEETS.get(gender_of(look))


def motion_sheet(look, motion):
    """The frame-by-frame movement a technique plays (MOTION_SHEETS), or None to play it through the three poses."""
    return MOTION_SHEETS.get(motion, {}).get(gender_of(look))


def face(look):
    """The square head-and-shoulders picture (shown in a circle on the fight card)."""
    return f"/art/portraits/hero_{gender_of(look)}_face.webp"
