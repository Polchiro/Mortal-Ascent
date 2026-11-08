"""
Octagon seal icons for the Character Sheet buttons (tabs, item actions, paging), in the Night Ink colours of
each tab (cards/ink.py). Like the fight and forge icons they are uploaded as the bot's application emojis at
startup (bot/emojis.py, named ma_<key>); if that fails the buttons keep plain emojis (FALLBACK).

icon_png(key) -> PNG bytes, 128×128 with a transparent background.
"""
import io
import math

from PIL import Image, ImageDraw, ImageFilter

from . import ink as k
from . import theme as T
from .theme import P, S, alpha, mix

SIZE = 128
RED = (226, 96, 84)
# key: (drawn icon, colour)
ICONS = {
    "sheet_tab_profile": ("star", k.accent("profile")),
    "sheet_tab_techniques": ("scroll", k.accent("techniques")),
    "sheet_tab_equipment": ("sword", k.accent("equipment")),
    "sheet_tab_inventory": ("chest", k.accent("inventory")),
    "sheet_tab_purse": ("lotus", k.accent("purse")),
    "sheet_open": ("chest", k.accent("inventory")),
    "sheet_learn": ("scroll", k.accent("techniques")),
    "sheet_equip": ("sword", k.accent("equipment")),
    "sheet_take": ("pill", k.accent("inventory")),
    "sheet_unequip": ("fist", k.accent("equipment")),
    "sheet_discard": ("skull", RED),
    "sheet_prev": ("misc:arrow_left", k.GOLD),
    "sheet_next": ("misc:arrow_right", k.GOLD),
    "sheet_cancel": ("misc:hold", k.ASH),
}
FALLBACK = {"sheet_tab_profile": "👤", "sheet_tab_techniques": "📜", "sheet_tab_equipment": "⚔️",
            "sheet_tab_inventory": "🎒", "sheet_tab_purse": "🪷", "sheet_open": "✨", "sheet_learn": "✨",
            "sheet_equip": "✨", "sheet_take": "✨", "sheet_unequip": "🤜", "sheet_discard": "🗑️",
            "sheet_prev": "◀️", "sheet_next": "▶️", "sheet_cancel": "✖️"}
USE_KEY = {"Open": "sheet_open", "Learn": "sheet_learn", "Equip": "sheet_equip", "Take": "sheet_take"}


def render_icon(key):
    kind, color = ICONS[key]
    img = Image.new("RGBA", (SIZE * S, SIZE * S), (0, 0, 0, 0))
    c, r = SIZE / 2, SIZE / 2 - 8
    g = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(g).ellipse(P(6, 6, SIZE - 6, SIZE - 6), fill=alpha(color, 100))
    img.alpha_composite(g.filter(ImageFilter.GaussianBlur(5 * S)))
    d = ImageDraw.Draw(img)

    def octo(rr):
        return [P(c + rr * math.cos(math.radians(22.5 + i * 45)), c + rr * math.sin(math.radians(22.5 + i * 45)))
                for i in range(8)]
    outer = octo(r)
    d.polygon(outer, fill=alpha(mix(color, k.VOID, 0.72), 255))
    d.line(outer + [outer[0]], fill=k.GOLD, width=round(4 * S), joint="curve")
    inner = octo(r - 9)
    d.line(inner + [inner[0]], fill=alpha(color, 210), width=round(2 * S), joint="curve")
    core = Image.radial_gradient("L").resize(P(r * 1.6, r * 1.6))
    ci = Image.new("RGBA", core.size, alpha(mix(color, (255, 255, 255), 0.1), 0))
    ci.putalpha(core.point(lambda v: round((255 - v) * 0.55)))
    img.alpha_composite(ci, P(c - r * 0.8, c - r * 0.8))
    T.icon(img, kind, (c, c), r * 1.15, (250, 252, 250))
    return img.resize((SIZE, SIZE), Image.LANCZOS)


def icon_png(key):
    buf = io.BytesIO()
    render_icon(key).save(buf, format="PNG")
    return buf.getvalue()
