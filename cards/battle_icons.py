"""
Round medallion icons for the fight buttons (docs/combat.md). They are drawn in code and uploaded as the
bot's application emojis at startup (bot/emojis.py), so no image files are needed.

icon_png(key) -> PNG bytes, 128×128 with a transparent background.
"""
import io

from PIL import Image

from . import theme as T

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
    # technique schools
    "fist": ("拳", (226, 84, 72), True),
    "palm": ("掌", (110, 150, 232), True),
    "finger": ("指", (196, 110, 228), True),
    "leg": ("腿", (232, 160, 62), True),
    "body": ("体", (96, 196, 160), True),
}
FALLBACK = {"strike": "⚔️", "guard": "🛡️", "break": "💥", "pill": "❤️", "flee": "🏃", "attack_tech": "✨",
            "defense_tech": "🔰", "fist": "👊", "palm": "🖐️", "finger": "☝️", "leg": "🦵", "body": "🧘"}


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
