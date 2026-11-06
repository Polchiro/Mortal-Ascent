"""
Round medallion icons for the /explore and /gather buttons, in the same style as the fight buttons
(cards/battle_icons.py). They are uploaded as the bot's application emojis at startup (bot/emojis.py),
named ma_<key>.

icon_png(key) -> PNG bytes, 128×128 with a transparent background.
"""
import io

from PIL import Image, ImageDraw

from . import theme as T
from .theme import P, S, font, mix

SIZE = 128
PATH_COLOR = {"left": (236, 96, 80), "middle": (246, 196, 86), "right": (150, 196, 236)}
JADE = (92, 214, 170)
# key: (what is drawn, colour)
ICONS = {
    "path_left": ("arrow:left", PATH_COLOR["left"]),
    "path_middle": ("arrow:middle", PATH_COLOR["middle"]),
    "path_right": ("arrow:right", PATH_COLOR["right"]),
    "explore_return": ("lantern", (236, 110, 70)),
    "explore_deeper": ("arrow:middle", (236, 170, 80)),
    "gather_stop": ("lantern", (236, 110, 70)),
    "gather_again": ("herb", JADE),
    **{f"gather_{n}": (f"num:{n}", JADE) for n in range(1, 7)},
}
FALLBACK = {"path_left": "⬅️", "path_middle": "⬆️", "path_right": "➡️", "explore_return": "🏮",
            "explore_deeper": "🔦", "gather_stop": "🏮", "gather_again": "🌿",
            **{f"gather_{n}": f"{n}\N{VARIATION SELECTOR-16}\N{COMBINING ENCLOSING KEYCAP}" for n in range(1, 7)}}


def lantern(img, center, size, color):
    """A paper lantern: red body, gold caps, a warm glow."""
    cx, cy = center
    s = size / 2
    T.soft_glow(img, (cx - s, cy - s, cx + s, cy + s), T.alpha((255, 170, 80), 150), s * 0.3)
    d = ImageDraw.Draw(img)
    d.line(P(cx, cy - s, cx, cy - s * 0.7), fill=T.GOLD, width=max(1, round(s * 0.1 * S)))
    d.rounded_rectangle(P(cx - s * 0.55, cy - s * 0.62, cx + s * 0.55, cy + s * 0.62), radius=round(s * 0.4 * S),
                        fill=(226, 64, 44, 255))
    d.ellipse(P(cx - s * 0.22, cy - s * 0.32, cx + s * 0.22, cy + s * 0.32), fill=(255, 210, 120, 255))
    for yy in (-0.66, 0.6):
        d.rectangle(P(cx - s * 0.4, cy + s * yy - s * 0.08, cx + s * 0.4, cy + s * yy + s * 0.1), fill=T.GOLD)
    d.line(P(cx, cy + s * 0.7, cx, cy + s * 0.95), fill=T.GOLD, width=max(1, round(s * 0.08 * S)))


def draw_glyph(img, glyph, center, size, color):
    """Draw one button glyph inside a medallion (also used on the cards)."""
    from .expedition import arrow
    cx, cy = center
    light = mix(color, (255, 255, 255), 0.35)
    if glyph.startswith("arrow:"):
        arrow(ImageDraw.Draw(img), cx, cy, size * 0.42, glyph[6:], light)
    elif glyph.startswith("num:"):
        d = ImageDraw.Draw(img)
        T.text(d, (cx, cy + size * 0.02), glyph[4:], font("Cinzel.ttf", round(size * 0.78), "Black"), light, "mm")
    elif glyph == "lantern":
        lantern(img, center, size * 0.95, color)
    else:
        T.icon(img, glyph, center, size * 0.7, light)


def render_icon(key):
    glyph, color = ICONS[key]
    img = Image.new("RGBA", P(SIZE, SIZE), (0, 0, 0, 0))
    c, r = SIZE / 2, SIZE / 2 - 10
    T.medallion(img, (c, c), r, " ", color, cjk_char=True)       # an empty seal, then the drawn glyph
    draw_glyph(img, glyph, (c, c), r * 1.1, color)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def icon_png(key):
    buf = io.BytesIO()
    render_icon(key).save(buf, format="PNG")
    return buf.getvalue()
