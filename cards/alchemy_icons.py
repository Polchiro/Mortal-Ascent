"""
Round medallion icons for the /craft buttons, in the same style as the fight buttons (cards/battle_icons.py).
They are uploaded as the bot's application emojis at startup (bot/emojis.py), named ma_craft_<action>.

icon_png(key) -> PNG bytes, 128×128 with a transparent background.
"""
import io

from PIL import Image

from . import theme as T

SIZE = 128
# key: (drawn icon or CJK character, colour, is_character). The keys are the craft actions in bot/crafting.py.
ICONS = {
    "craft_stoke": ("flame", (236, 96, 52), False),
    "craft_hold": ("守", (206, 164, 86), True),
    "craft_fan": ("风", (110, 150, 232), True),
    "craft_qi": ("气", (110, 170, 240), True),
    "craft_healing": ("愈", (232, 96, 96), True),
    "craft_purity": ("净", (100, 206, 196), True),
    "craft_breakthrough": ("破", (204, 150, 92), True),
    "craft_circulate": ("转", (176, 140, 250), True),
    "craft_compress": ("压", (196, 150, 90), True),
    "craft_cool": ("寒", (120, 190, 240), True),
    "craft_ignite": ("炎", (236, 96, 52), True),
    "craft_condense": ("pill", (82, 186, 120), False),
    "craft_wait": ("hourglass", (190, 176, 150), False),
    "craft_left": ("左", (178, 142, 250), True),
    "craft_above": ("上", (178, 142, 250), True),
    "craft_right": ("右", (178, 142, 250), True),
    "craft_again": ("丹", (236, 170, 80), True),
}
FALLBACK = {"craft_stoke": "🔥", "craft_hold": "✋", "craft_fan": "🌬️", "craft_qi": "🌀", "craft_healing": "❤️",
            "craft_purity": "💧", "craft_breakthrough": "🏔️", "craft_circulate": "🌀", "craft_compress": "🗜️",
            "craft_cool": "❄️", "craft_ignite": "🔥", "craft_condense": "💊", "craft_wait": "⏳", "craft_left": "⬅️",
            "craft_above": "⬆️", "craft_right": "➡️", "craft_again": "🏺"}


def render_icon(key):
    glyph, color, is_char = ICONS[key]
    img = Image.new("RGBA", T.P(SIZE, SIZE), (0, 0, 0, 0))
    c, r = SIZE / 2, SIZE / 2 - 10
    T.medallion(img, (c, c), r, glyph, color, cjk_char=is_char)
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def icon_png(key):
    buf = io.BytesIO()
    render_icon(key).save(buf, format="PNG")
    return buf.getvalue()
