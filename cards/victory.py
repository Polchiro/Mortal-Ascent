"""
The painted victory pieces (art/scenes/): the crest for a win (one per tier) or a loss, the burst of light
behind it, and the silk cloth the spoils are laid on. Used by the fight result (cards/beast_fight.py), the
explore fight result (cards/explore_v2.py) and the spar and training results (cards/results.py).

Every function draws on a card canvas at S× and silently draws nothing when its art file is missing.
"""
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw

from . import theme as T
from .scenes import subject
from .theme import S, font

CREST = {None: "victory_crest", "Wild": "victory_crest", "Elite": "victory_crest_elite",
         "Beast King": "victory_crest_king"}
WARM = (244, 236, 222)


def crest_name(result, tier=None):
    if result in ("won", "victory"):
        return CREST.get(tier, "victory_crest")
    if result in ("lost", "defeat"):
        return "defeat_crest"
    return None


@lru_cache(maxsize=24)
def _sized(name, height, fade=1.0):
    art = subject(name)
    if art is None:
        return None
    h = round(height * S)
    art = art.resize((max(1, round(art.size[0] * h / art.size[1])), h), Image.LANCZOS)
    if fade < 1:
        art.putalpha(art.getchannel("A").point(lambda v: round(v * fade)))
    return art


def place(img, name, center, height, fade=1.0):
    """Paste the art `name` with its centre at `center` (card units). Returns True if drawn."""
    art = _sized(name, round(height), fade)
    if art is None:
        return False
    img.alpha_composite(art, (round(center[0] * S - art.size[0] / 2), round(center[1] * S - art.size[1] / 2)))
    return True


def rays(img, center, size, strength=0.85):
    """The burst of light, added on top (screen) so it only ever brightens."""
    art = _sized("victory_rays", round(size), strength)
    if art is None:
        return
    x, y = round(center[0] * S - art.size[0] / 2), round(center[1] * S - art.size[1] / 2)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    layer.alpha_composite(art, (x, y))
    lit = Image.new("RGB", img.size, (0, 0, 0))
    lit.paste(layer.convert("RGB"), mask=layer.getchannel("A"))
    rgb = ImageChops.screen(img.convert("RGB"), lit)
    rgb.putalpha(img.getchannel("A"))
    img.paste(rgb)


def crest(img, center, height, result, tier=None):
    """Rays (for a win) and the crest. Returns True if the crest art exists."""
    name = crest_name(result, tier)
    if name is None:
        return False
    if name != "defeat_crest":
        rays(img, (center[0], center[1] + height * 0.02), height * 2.3,
             0.95 if tier == "Beast King" else 0.8)
    else:
        T.soft_glow(img, (center[0] - height * 0.7, center[1] - height * 0.6, center[0] + height * 0.7,
                          center[1] + height * 0.6), (90, 20, 14, 120), 40)
    return place(img, name, center, height)


def spoils(img, box, tiles, max_n=5):
    """The silk cloth across `box` with up to max_n spoils in one row."""
    spoils_rows(img, box, [tiles[:max_n]])


ROW_H = 150      # one row of spoils on the cloth: seal, ×qty, a two-line name, "left behind"
CLOTH_PAD = 40   # the embroidered border above and below the rows


def spoils_layout(n, per_row=7):
    """Split n spoils into rows (as even as possible). Returns the number in each row."""
    if n <= 0:
        return []
    rows = -(-n // per_row)
    base, extra = divmod(n, rows)
    return [base + (1 if i < extra else 0) for i in range(rows)]


def spoils_height(n, per_row=7):
    return 2 * CLOTH_PAD + max(1, len(spoils_layout(n, per_row))) * ROW_H


def spoils_rows(img, box, rows):
    """The silk cloth across `box`, stretched to fit, with every row of spoils laid on it."""
    x0, y0, x1, y1 = box
    cloth = subject("spoils_cloth")
    if cloth is not None:
        cloth = cloth.resize((round((x1 - x0) * S), round((y1 - y0) * S)), Image.LANCZOS)
        img.alpha_composite(cloth, (round(x0 * S), round(y0 * S)))
    else:
        T.soft_glow(img, box, (90, 14, 18, 200), 18, "rect")
    rows = [r for r in rows if r]
    if not rows:
        d = ImageDraw.Draw(img)
        T.text(d, ((x0 + x1) / 2, (y0 + y1) / 2), "Nothing to carry home", font("Inter.ttf", 26, "SemiBold"),
               (230, 206, 170), "mm")
        return
    row_h = (y1 - y0 - 2 * CLOTH_PAD) / len(rows)
    for r, tiles in enumerate(rows):
        step = min(150, (x1 - x0 - 80) / len(tiles))
        cy = y0 + CLOTH_PAD + r * row_h + row_h * 0.30
        first = (x0 + x1) / 2 - step * (len(tiles) - 1) / 2
        for i, it in enumerate(tiles):
            _spoil(img, first + i * step, cy, step, it)


def _spoil(img, cx, cy, step, it):
    col = it.get("color") or T.RARITY.get(it.get("color_key"), T.RARITY[None])
    if it.get("lost"):
        col = (110, 100, 96)
    T.seal(img, (cx, cy), 32, it["icon"], col)
    d = ImageDraw.Draw(img)
    qty = it.get("qty", 1)
    if qty > 1:
        T.text(d, (cx + 34, cy - 26), f"×{qty}", font("Inter.ttf", 22, "Black"), (250, 220, 150), "mm")
    f = font("Inter.ttf", 20, "Bold")
    name = it["label"] if it.get("name") == "Lotus Coins" else it["name"]
    lines = T.wrap(d, name, f, step - 10, lines=2)
    for j, line in enumerate(lines):
        T.text(d, (cx, cy + 52 + j * 24), line, f, (176, 150, 140) if it.get("lost") else WARM, "mm")
    if it.get("lost"):
        T.text(d, (cx, cy + 54 + len(lines) * 24), "left behind", font("Inter.ttf", 17, "SemiBold"),
               (240, 130, 110), "mm")
