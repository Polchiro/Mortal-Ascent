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
    "craft_hold": ("misc:hold", (206, 164, 86), False),
    "craft_fan": ("misc:wind", (110, 150, 232), False),
    "craft_qi": ("misc:herb_qi", (110, 170, 240), False),
    "craft_healing": ("misc:herb_healing", (232, 96, 96), False),
    "craft_purity": ("misc:herb_purity", (100, 206, 196), False),
    "craft_breakthrough": ("misc:herb_breakthrough", (204, 150, 92), False),
    "craft_circulate": ("misc:circulate", (176, 140, 250), False),
    "craft_compress": ("misc:compress", (196, 150, 90), False),
    "craft_cool": ("misc:snowflake", (120, 190, 240), False),
    "craft_ignite": ("flame", (246, 140, 60), False),
    "craft_condense": ("pill", (82, 186, 120), False),
    "craft_wait": ("hourglass", (190, 176, 150), False),
    "craft_left": ("misc:arrow_left", (178, 142, 250), False),
    "craft_above": ("misc:arrow_up", (178, 142, 250), False),
    "craft_right": ("misc:arrow_right", (178, 142, 250), False),
    "craft_again": ("gear:furnace", (236, 170, 80), False),
}
# These used to be seal characters; the new names make the bot upload the drawn versions instead of
# reusing the old emojis. Names are at most 32 characters ("ma_" + this).
EMOJI_NAME = {k: k + "_v2" for k in ("craft_hold", "craft_fan", "craft_qi", "craft_healing", "craft_purity",
                                     "craft_breakthrough", "craft_circulate", "craft_compress", "craft_cool",
                                     "craft_ignite", "craft_left", "craft_above", "craft_right", "craft_again")}
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
