"""
Character appearance: gender, hairstyle and hair colour. docs/appearance.md.

The look is only a picture. It never touches stats, fights or anything else in the game.

Each hairstyle is one painted picture of the cultivator in the plain robe with silver-grey hair
(art/looks/<gender>_<hair>.webp), plus a mask of just the hair (<gender>_<hair>_hair.png). A colour is
painted on inside the mask, keeping the hair's own light and shade, so one picture serves every colour.
Finished pictures are cached in art/.looks/ (not in git), so each look is only drawn once.
"""
import io
import json
import os

from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(ROOT, "art", "looks")
CACHE = os.path.join(ROOT, "art", ".looks")

GENDERS = {"male": "Male", "female": "Female"}
HAIRSTYLES = {                      # (key, name), in the order the Appearance screen shows them
    "male": [("topknot", "Topknot"), ("long", "Long & Loose")],
    "female": [("ponytail", "High Ponytail"), ("twin_buns", "Twin Buns"), ("long_straight", "Long Straight"),
               ("braid", "Single Braid"), ("crown_bun", "Crown Bun")],
}
COLORS = {                          # key: (name, RGB or None for the painted silver)
    "silver": ("Silver White", None),
    "black": ("Ink Black", (30, 28, 33)),
    "brown": ("Dark Brown", (70, 50, 38)),
    "chestnut": ("Chestnut", (108, 70, 48)),
    "crimson": ("Crimson", (110, 42, 48)),
    "azure": ("Azure Night", (46, 58, 84)),
}
FREE_CHANGES = 1                    # choosing your first look costs nothing
CHANGE_PEARLS = 200                 # every change after that, in Moon Pearls
FACE_BOX = (63, 2, 193, 132)        # the head in a look picture (260 x 540), for round avatars
FACE_SIZE = 256


def parse(raw):
    """A stored appearance (JSON text) as a clean dict, or None if the player hasn't chosen one."""
    if not raw:
        return None
    try:
        a = json.loads(raw)
        return clean(a.get("gender"), a.get("hair"), a.get("color"))
    except (ValueError, AttributeError):
        return None


def clean(gender, hair, color):
    """{'gender', 'hair', 'color'} if every part is a real option, else None."""
    if gender not in GENDERS or hair not in dict(HAIRSTYLES[gender]) or color not in COLORS:
        return None
    return {"gender": gender, "hair": hair, "color": color}


def dump(look):
    return json.dumps({"gender": look["gender"], "hair": look["hair"], "color": look["color"]}, sort_keys=True)


def key(look):
    """'female_braid_azure': names the finished picture."""
    return f"{look['gender']}_{look['hair']}_{look['color']}"


def from_key(k):
    """The look a key names, or None."""
    for g in GENDERS:
        for h, _ in HAIRSTYLES[g]:
            for c in COLORS:
                if k == f"{g}_{h}_{c}":
                    return {"gender": g, "hair": h, "color": c}
    return None


def describe(look):
    """'Female · Single Braid · Azure Night'."""
    return f"{GENDERS[look['gender']]} · {dict(HAIRSTYLES[look['gender']])[look['hair']]} · {COLORS[look['color']][0]}"


def change_cost(player):
    """Moon Pearls the next change costs (0 while the free one is left)."""
    return 0 if (player.get("appearance_changes") or 0) < FREE_CHANGES else CHANGE_PEARLS


def tint(img, mask, color):
    """Paint `color` onto the hair inside `mask`, keeping its light and shade. Pure numpy, no other library."""
    import numpy as np
    if color is None:
        return img
    a = np.asarray(img).astype(float)
    m = np.asarray(mask.filter(ImageFilter.GaussianBlur(0.8))).astype(float)[..., None] / 255.0
    lum = (a[..., :3] @ [0.3, 0.59, 0.11])[..., None] / 255.0
    sel = m[..., 0] > 0.5
    if not sel.any():
        return img
    lo, hi = np.percentile(lum[sel], 2), np.percentile(lum[sel], 98)
    shade = np.clip((lum - lo) / max(1e-3, hi - lo), 0, 1)
    hue = np.array(color, float)
    hair = np.clip(hue * (0.4 + 1.15 * shade) + 150 * np.clip(shade - 0.8, 0, 1), 0, 255)
    a[..., :3] = a[..., :3] * (1 - m) + hair * m
    return Image.fromarray(a.astype("uint8"), "RGBA")


def render(look):
    """The full-body picture for a look, as RGBA."""
    base = os.path.join(ART, f"{look['gender']}_{look['hair']}")
    img = Image.open(base + ".webp").convert("RGBA")
    mask = Image.open(base + "_hair.png").convert("L")
    return tint(img, mask, COLORS[look["color"]][1])


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
