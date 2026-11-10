"""
Pictures for items that have no painted file (essences, some emblems): drawn by the bot's own card code
(cards/theme.icon → cards/material_icons.py ...), so they look exactly like the Discord cards.

Served at /art/drawn/<kind>.png, e.g. /art/drawn/mat:essence:venom:shard.png. Each picture is drawn once and
kept in memory. Only short kinds of known shapes are drawn.
"""
import io
import re
from functools import lru_cache

from PIL import Image

from cards import theme as T

KIND = re.compile(r"^(mat|emblem|chest|seal|gear|art|tech|passive):[A-Za-z0-9:_\-]{1,60}$")
PX = 168                      # drawn at 2× the largest size the pages show


def allowed(kind):
    return bool(KIND.match(kind or ""))


@lru_cache(maxsize=256)
def png(kind):
    """The icon as PNG bytes, or None when it can't be drawn."""
    if not allowed(kind):
        return None
    img = Image.new("RGBA", (PX * T.S, PX * T.S), (0, 0, 0, 0))     # card units are drawn at S×, like the cards
    try:
        T.icon(img, kind, (PX / 2, PX / 2), PX * 0.76, T.GOLD)   # room for the glow
    except Exception:
        return None
    img = img.resize((PX, PX), Image.LANCZOS)
    if img.getchannel("A").getbbox() is None:      # nothing was drawn
        return None
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def url(kind):
    return f"/art/drawn/{kind}.png" if allowed(kind) else None
