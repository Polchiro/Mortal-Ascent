"""
Character appearance: male or female. docs/appearance.md.

The look is only a picture. It never touches stats, fights or anything else in the game.

Each gender has one painting of the cultivator in white and blue robes (art/portraits/hero_<gender>.webp,
see-through background) and a round face (art/portraits/hero_<gender>_face.webp). In website fights the male
has three sword poses (art/portraits/fight/hero_male_{idle,windup,strike}.webp); the female has one painting
for now (art/portraits/fight/hero_female.webp). A player who hasn't chosen a look shows the male painting.
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
SWORD_POSES = {"male"}              # genders painted in all three sword poses; the others use one painting


def fighter(look, pose="idle"):
    """The fighter on the 1024 x 559 fight canvas, facing right, in one of POSES (web/static/fight.js swaps them)."""
    gender = gender_of(look)
    if gender in SWORD_POSES:
        return f"/art/portraits/fight/hero_{gender}_{pose}.webp"
    return f"/art/portraits/fight/hero_{gender}.webp"


def sword_tip(look):
    """How far across the fight canvas the weapon reaches in the strike pose (0-1), or None for a single painting."""
    return 0.91 if gender_of(look) in SWORD_POSES else None


def face(look):
    """The square head-and-shoulders picture (shown in a circle on the fight card)."""
    return f"/art/portraits/hero_{gender_of(look)}_face.webp"
