"""
Round medallion icons for the fight buttons (docs/combat.md). They are drawn in code and uploaded as the
bot's application emojis at startup (bot/emojis.py), so no image files are needed.

icon_png(key) -> PNG bytes, 128×128 with a transparent background.
"""
import io

from PIL import Image

import technique

from . import theme as T
from .technique_icons import tech_key

SIZE = 128
# key: (drawn icon or CJK character, colour, is_character)
ICONS = {
    "strike": ("sword", (226, 84, 72), False),
    "guard": ("shield", (110, 150, 232), False),
    "break": ("fist", (232, 160, 62), False),
    "pill": ("pill", (236, 96, 112), False),
    "flee": ("flee", (180, 182, 196), False),
    "attack_tech": ("star", (240, 200, 100), False),
    "defense_tech": ("lotus", (96, 196, 160), False),
    # technique schools: the drawn base shapes (cards/technique_icons.py)
    "fist": ("school:Fist", (226, 84, 72), False),
    "palm": ("school:Palm", (110, 150, 232), False),
    "finger": ("school:Finger", (196, 110, 228), False),
    "leg": ("school:Leg", (232, 160, 62), False),
    "body": ("school:Body", (96, 196, 160), False),
}
FALLBACK = {"strike": "⚔️", "guard": "🛡️", "break": "💥", "pill": "❤️", "flee": "🏃", "attack_tech": "✨",
            "defense_tech": "🔰", "fist": "👊", "palm": "🖐️", "finger": "☝️", "leg": "🦵", "body": "🧘"}

# every technique has its own button icon, "t_<technique key>", in its grade colour
TECH_SCHOOL = {}
for _key, _t in technique.TECHNIQUES.items():
    ICONS["t_" + _key] = ("tech:" + _key, T.RARITY[_t["grade"]], False)
    TECH_SCHOOL["t_" + _key] = _t["school"].lower()
    FALLBACK["t_" + _key] = FALLBACK[_t["school"].lower()]

# Emoji names already uploaded with the old seal-character pictures get a new name, so the bot uploads the
# drawn version instead of reusing the old one. Names are at most 32 characters ("ma_" + this).
EMOJI_NAME = {k: k + "_v2" for k in ("fist", "palm", "finger", "leg", "body")}


def tech_emoji_key(name):
    """Button icon key for a technique by name ('Iron Fist' → 't_iron_fist')."""
    return "t_" + tech_key(name)


def _flee(img, center, size, color):
    """An arrow leaving through a gate."""
    from PIL import ImageDraw
    d = ImageDraw.Draw(img)
    cx, cy = center
    s = size / 2
    d.polygon([T.P(cx - s * 0.8, cy - s * 0.18), T.P(cx + s * 0.1, cy - s * 0.18), T.P(cx + s * 0.1, cy - s * 0.6),
               T.P(cx + s * 0.9, cy), T.P(cx + s * 0.1, cy + s * 0.6), T.P(cx + s * 0.1, cy + s * 0.18),
               T.P(cx - s * 0.8, cy + s * 0.18)], fill=color)


def render_icon(key):
    glyph, color, is_char = ICONS[key]
    img = Image.new("RGBA", T.P(SIZE, SIZE), (0, 0, 0, 0))
    c, r = SIZE / 2, SIZE / 2 - 10
    if glyph == "flee":
        T.medallion(img, (c, c), r, " ", color, cjk_char=True)     # empty seal, then the arrow
        _flee(img, (c, c), r * 1.1, T.mix(color, (255, 255, 255), 0.25))
    else:
        T.medallion(img, (c, c), r, glyph, color, cjk_char=is_char)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def icon_png(key):
    buf = io.BytesIO()
    render_icon(key).save(buf, format="PNG")
    return buf.getvalue()
