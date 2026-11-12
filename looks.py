"""
Character appearance: male or female. docs/appearance.md.

The look is only a picture. It never touches stats, fights or anything else in the game.

Each gender has one painting of the cultivator in white and blue robes with blue Qi streams
(art/portraits/hero_<gender>.webp, see-through background). The same painting, turned to face the beast,
is the fighter in website fights (art/portraits/fight/hero_<gender>.webp), and its head is the round face
(art/portraits/hero_<gender>_face.webp). A player who hasn't chosen a look shows the male painting.
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


def fighter(look):
    """The painting facing right, on the 1024 x 559 fight canvas."""
    return f"/art/portraits/fight/hero_{gender_of(look)}.webp"


def face(look):
    """The square head-and-shoulders picture (shown in a circle on the fight card)."""
    return f"/art/portraits/hero_{gender_of(look)}_face.webp"
