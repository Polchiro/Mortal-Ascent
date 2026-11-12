"""
Character appearance: gender and hairstyle. docs/appearance.md.

The look is only a picture. It never touches stats, fights or anything else in the game.

Each hairstyle is one painted picture of the cultivator in the plain robe with silver hair
(art/looks/<gender>_<hair>.webp). Everyone's hair is silver: there are no hair colours.
Web-ready copies are cached in art/.looks/ (not in git), so each look is only prepared once.
"""
import io
import json
import os

from PIL import Image

ROOT = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(ROOT, "art", "looks")
CACHE = os.path.join(ROOT, "art", ".looks")

GENDERS = {"male": "Male", "female": "Female"}
HAIRSTYLES = {                      # (key, name), in the order the Appearance screen shows them
    "male": [("topknot", "Topknot"), ("long", "Long & Loose")],
    "female": [("ponytail", "High Ponytail"), ("twin_buns", "Twin Buns"), ("long_straight", "Long Straight"),
               ("braid", "Single Braid"), ("crown_bun", "Crown Bun")],
}
FREE_CHANGES = 1                    # choosing your first look costs nothing
CHANGE_PEARLS = 200                 # every change after that, in Moon Pearls
FACE_BOX = (63, 2, 193, 132)        # the head in a look picture (260 x 540), for round avatars
FACE_SIZE = 256


def parse(raw):
    """A stored appearance (JSON text) as a clean dict, or None if the player hasn't chosen one.
    Looks saved while hair colours existed carry a "color"; it is ignored (everyone is silver now)."""
    if not raw:
        return None
    try:
        a = json.loads(raw)
        return clean(a.get("gender"), a.get("hair"))
    except (ValueError, AttributeError):
        return None


def clean(gender, hair):
    """{'gender', 'hair'} if both are real options, else None."""
    if gender not in GENDERS or hair not in dict(HAIRSTYLES[gender]):
        return None
    return {"gender": gender, "hair": hair}


def dump(look):
    return json.dumps({"gender": look["gender"], "hair": look["hair"]}, sort_keys=True)


def key(look):
    """'female_braid': names the picture."""
    return f"{look['gender']}_{look['hair']}"


def from_key(k):
    """The look a key names, or None."""
    for g in GENDERS:
        for h, _ in HAIRSTYLES[g]:
            if k == f"{g}_{h}":
                return {"gender": g, "hair": h}
    return None


def describe(look):
    """'Female · Single Braid'."""
    return f"{GENDERS[look['gender']]} · {dict(HAIRSTYLES[look['gender']])[look['hair']]}"


def change_cost(player):
    """Moon Pearls the next change costs (0 while the free one is left)."""
    return 0 if (player.get("appearance_changes") or 0) < FREE_CHANGES else CHANGE_PEARLS


def render(look):
    """The full-body picture for a look, as RGBA."""
    return Image.open(os.path.join(ART, key(look) + ".webp")).convert("RGBA")


def _cached(name, make):
    path = os.path.join(CACHE, name)
    if not os.path.exists(path):
        os.makedirs(CACHE, exist_ok=True)
        data = make()
        tmp = path + f".{os.getpid()}.tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)                       # two drawers at once can't leave half a file
    with open(path, "rb") as f:
        return f.read()


def full_webp(look):
    """The full-body picture as WebP bytes (cached)."""
    def make():
        out = io.BytesIO()
        render(look).save(out, "WEBP", quality=90, method=6)
        return out.getvalue()
    return _cached(key(look) + ".webp", make)


def face_png(look):
    """A square head-and-shoulders picture as PNG bytes (cached), for the round face on the website fight card."""
    def make():
        img = render(look).crop(FACE_BOX).resize((FACE_SIZE, FACE_SIZE), Image.LANCZOS)
        bg = Image.new("RGBA", img.size, (20, 24, 32, 255))     # avatars are drawn in circles: no see-through
        bg.alpha_composite(img)
        out = io.BytesIO()
        bg.convert("RGB").save(out, "PNG", optimize=True)
        return out.getvalue()
    return _cached(key(look) + "_face.png", make)


def of_player(player):
    """The player's chosen look, or None (they still use the default portrait)."""
    return parse(player.get("appearance")) if player else None
