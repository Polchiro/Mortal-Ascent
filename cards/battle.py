"""
The fight screen: one card that the bot edits every turn (docs/combat.md).

  ┌ scene window: sky, moon, mist, mountains and the enemy (art/beasts/<slug>.png, or a drawn silhouette)
  │   over its bottom: seal, name, tier · role · element · realm, HP bar, element seal, status chips
  │   top right: turn number and seconds to choose
  ├ bottom left: "Hunting Party" (or "You" with your techniques and pills when solo)
  ├ bottom right: "Last turn" log with small icons
  └ warning bar: the enemy's telegraphed next move

render_battle(data) takes plain data (see bot/fight_view.card_data) so it is safe to run off the
event loop. The scene behind the enemy is cached per enemy + element, so only the panels are redrawn.
"""
import math
import os
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import theme as T
from .theme import P, S, alpha, font, mix

# Discord shows the card at roughly half size on a computer, so text is drawn large (body text 20px+).
W, H = 1200, 920
SCENE = (24, 24, 1176, 420)
PARTY = (24, 440, 584, 790)
LOG = (604, 440, 1176, 790)
WARN = (24, 810, 1176, 896)
ART_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "beasts")

MEMBER_COLORS = [(92, 150, 236), (232, 150, 62), (82, 186, 120), (196, 110, 228), (226, 84, 72), (226, 206, 96),
                 (96, 206, 214), (210, 160, 120)]
LOW_HP = 0.25

SEAL_BY_WORD = {
    "Tiger": "虎", "Lion": "狮", "Leopard": "豹", "Panther": "豹", "Lynx": "猞", "Fox": "狐", "Wolf": "狼", "Hound": "犬",
    "Dog": "犬", "Boar": "猪", "Bear": "熊", "Ox": "牛", "Bull": "牛", "Rhino": "犀", "Stag": "鹿", "Steed": "马",
    "Crane": "鹤", "Hawk": "鹰", "Eagle": "鹰", "Vulture": "鹫", "Crow": "鸦", "Bat": "蝠", "Bird": "雀",
    "Toad": "蟾", "Scorpion": "蝎", "Spider": "蛛", "Centipede": "蜈", "Crocodile": "鳄", "Lizard": "蜥",
    "Monkey": "猴", "Ape": "猿", "Weasel": "鼬", "Tortoise": "龟", "Turtle": "龟", "Dragon": "龙", "Python": "蟒",
    "Serpent": "蛇", "Viper": "蛇", "Qilin": "麟", "Pixiu": "貔", "Taotie": "饕", "Qiongqi": "穷", "Kun-Peng": "鲲",
    "Shanxiao": "魈",
}
SEAL_BY_BODY = {"cat": "豹", "wolf": "狼", "bird": "鹰", "serpent": "蛇", "ape": "猿", "turtle": "龟", "insect": "虫",
                "dragon": "龙", "human": "匪", "master": "师", "courtyard": "院"}


def seal_char(name, body):
    for word in name.replace(",", " ").replace("(", " ").replace(")", " ").split():
        if word in SEAL_BY_WORD:
            return SEAL_BY_WORD[word]
    return SEAL_BY_BODY.get(body, "兽")


# ── Scene (cached) ────────────────────────────────────────────────────

def _scene_size():
    x0, y0, x1, y1 = SCENE
    return round((x1 - x0) * S), round((y1 - y0) * S)


def _sky(acc, size, seed):
    w, h = size
    img = T.vgradient(size, acc.sky[0], acc.sky[1])
    d = ImageDraw.Draw(img)
    r = random.Random(seed)
    for _ in range(140):
        x, y = r.uniform(0, w), r.uniform(0, h * 0.7)
        rad = r.uniform(0.4, 1.3) * S
        d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=alpha(mix(acc.moon, (255, 255, 255), 0.5), r.randint(60, 200)))
    return img


def _moon(img, acc, cx, cy, r):
    glow = Image.new("RGBA", img.size, acc.moon + (0,))
    ImageDraw.Draw(glow).ellipse((cx - r * 2.4, cy - r * 2.4, cx + r * 2.4, cy + r * 2.4), fill=alpha(acc.rim, 70))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(r * 0.9)))
    d = ImageDraw.Draw(img)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=acc.moon + (255,))
    rr = random.Random(3)
    for _ in range(7):
        a, dist, cr = rr.uniform(0, 6.28), rr.uniform(0, r * 0.7), rr.uniform(r * 0.07, r * 0.18)
        x, y = cx + math.cos(a) * dist, cy + math.sin(a) * dist
        d.ellipse((x - cr, y - cr, x + cr, y + cr), fill=mix(acc.moon, (90, 90, 100), 0.25) + (255,))
    shade = Image.new("L", img.size, 0)
    ImageDraw.Draw(shade).ellipse((cx - r * 0.55, cy - r * 1.05, cx + r * 1.45, cy + r * 0.95), fill=110)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    img.paste(Image.new("RGBA", img.size, (30, 30, 40, 255)), (0, 0),
              ImageChops.multiply(shade, mask).filter(ImageFilter.GaussianBlur(r * 0.15)))


def _ridge(w, h, base, amp, seed, peaks=7):
    r = random.Random(seed)
    pts = [(0, h)]
    n = peaks * 2
    for i in range(n + 1):
        x = w * i / n
        y = base - (amp * r.uniform(0.55, 1.0) if i % 2 else amp * r.uniform(0.0, 0.3))
        pts.append((x, y))
    pts.append((w, h))
    return pts


def _pine(d, x, base, height, fill):
    for k in range(4):
        top = base - height * (1 - k * 0.22)
        half = height * (0.18 + k * 0.06)
        d.polygon([(x, top), (x + half, base - height * (0.55 - k * 0.17)), (x - half, base - height * (0.55 - k * 0.17))],
                  fill=fill)
    d.rectangle((x - height * 0.03, base - height * 0.15, x + height * 0.03, base), fill=fill)


def _landscape(img, acc, seed):
    w, h = img.size
    far = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(far).polygon(_ridge(w, h, h * 0.62, h * 0.3, seed, 6), fill=alpha(mix(acc.mist, acc.sky[0], 0.55), 255))
    img.alpha_composite(far)
    # mist between the ranges
    mist = Image.new("RGBA", img.size, acc.mist + (0,))
    md = ImageDraw.Draw(mist)
    md.ellipse((-w * 0.1, h * 0.52, w * 0.55, h * 0.8), fill=alpha(acc.mist, 90))
    md.ellipse((w * 0.45, h * 0.5, w * 1.1, h * 0.82), fill=alpha(acc.mist, 80))
    img.alpha_composite(mist.filter(ImageFilter.GaussianBlur(h * 0.06)))
    near = Image.new("RGBA", img.size, (0, 0, 0, 0))
    nd = ImageDraw.Draw(near)
    nd.polygon(_ridge(w, h, h * 0.78, h * 0.22, seed + 1, 5), fill=alpha(mix(acc.sky[0], (0, 0, 0), 0.35), 255))
    dark = alpha(mix(acc.sky[0], (0, 0, 0), 0.6), 255)
    for x, ht in ((0.07, 0.24), (0.11, 0.17), (0.92, 0.2), (0.96, 0.27)):
        _pine(nd, w * x, h * 0.86, h * ht, dark)
    img.alpha_composite(near)


def _courtyard(img, acc, seed):
    """The training courtyard: far peaks, a temple hall with curved eaves, red pillars, lanterns, stone floor."""
    w, h = img.size
    far = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(far).polygon(_ridge(w, h, h * 0.55, h * 0.25, seed, 5), fill=alpha(mix(acc.mist, acc.sky[0], 0.6), 255))
    img.alpha_composite(far)
    mist = Image.new("RGBA", img.size, acc.mist + (0,))
    ImageDraw.Draw(mist).ellipse((-w * 0.1, h * 0.45, w * 1.1, h * 0.75), fill=alpha(acc.mist, 70))
    img.alpha_composite(mist.filter(ImageFilter.GaussianBlur(h * 0.06)))
    hall = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(hall)
    dark = alpha(mix(acc.sky[0], (0, 0, 0), 0.55), 255)
    wall = alpha(mix(acc.sky[0], (0, 0, 0), 0.3), 255)
    for x0, x1, top in ((0.0, 0.3, 0.5), (0.7, 1.0, 0.5)):
        d.rectangle((w * x0, h * (top + 0.1), w * x1, h), fill=wall)                       # hall body
        d.polygon([(w * (x0 - 0.04), h * (top + 0.12)), (w * (x0 + 0.02), h * top), (w * (x1 - 0.02), h * top),
                   (w * (x1 + 0.04), h * (top + 0.12)), (w * x1, h * (top + 0.1)), (w * x0, h * (top + 0.1))],
                  fill=dark)                                                                 # curved eaves
        for k in range(4):
            px = w * (x0 + 0.03 + k * (x1 - x0 - 0.06) / 3)
            d.rectangle((px - w * 0.006, h * (top + 0.12), px + w * 0.006, h * 0.86),
                        fill=alpha(mix((150, 40, 32), acc.sky[0], 0.45), 255))                # red pillars
    d.rectangle((0, h * 0.84, w, h), fill=alpha(mix(acc.sky[0], (0, 0, 0), 0.65), 255))       # stone floor
    for k in range(9):
        x = w * k / 8
        d.line([(w / 2 + (x - w / 2) * 0.35, h * 0.84), (x, h)], fill=alpha(acc.mist, 40), width=max(1, S))
    img.alpha_composite(hall)
    glow = Image.new("RGBA", img.size, (255, 170, 80, 0))
    gd = ImageDraw.Draw(glow)
    for lx in (0.08, 0.22, 0.78, 0.92):
        gd.ellipse((w * lx - h * 0.05, h * 0.66 - h * 0.05, w * lx + h * 0.05, h * 0.66 + h * 0.05),
                   fill=(255, 170, 80, 150))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(h * 0.03)))
    d = ImageDraw.Draw(img)
    for lx in (0.08, 0.22, 0.78, 0.92):
        d.ellipse((w * lx - h * 0.018, h * 0.66 - h * 0.025, w * lx + h * 0.018, h * 0.66 + h * 0.025),
                  fill=(236, 92, 52, 255))


# ── Silhouettes, drawn in a unit box (x, y from 0 to 1 over the scene) ──
# each returns (eyes, fangs): eye centres and fang tips in unit coordinates

def _poly(d, w, h, pts, fill=255):
    d.polygon([(x * w, y * h) for x, y in pts], fill=fill)


def _ell(d, w, h, box, fill=255):
    x0, y0, x1, y1 = box
    d.ellipse((x0 * w, y0 * h, x1 * w, y1 * h), fill=fill)


def _cat(d, w, h):
    _ell(d, w, h, (0.17, 0.58, 0.83, 1.4))
    _poly(d, w, h, [(0.33, 0.62), (0.36, 0.38), (0.41, 0.28), (0.5, 0.25), (0.59, 0.28), (0.64, 0.38), (0.67, 0.62),
                    (0.58, 0.72), (0.42, 0.72)])
    _poly(d, w, h, [(0.36, 0.34), (0.385, 0.1), (0.45, 0.27)])
    _poly(d, w, h, [(0.64, 0.34), (0.615, 0.1), (0.55, 0.27)])
    _poly(d, w, h, [(0.34, 0.5), (0.28, 0.6), (0.36, 0.64)])
    _poly(d, w, h, [(0.66, 0.5), (0.72, 0.6), (0.64, 0.64)])
    return [(0.455, 0.4), (0.545, 0.4)], [(0.478, 0.68), (0.522, 0.68)]


def _wolf(d, w, h):
    _ell(d, w, h, (0.2, 0.64, 0.8, 1.4))
    _poly(d, w, h, [(0.38, 0.6), (0.4, 0.36), (0.45, 0.27), (0.5, 0.25), (0.55, 0.27), (0.6, 0.36), (0.62, 0.6),
                    (0.56, 0.66), (0.54, 0.78), (0.46, 0.78), (0.44, 0.66)])
    _poly(d, w, h, [(0.405, 0.36), (0.41, 0.05), (0.47, 0.28)])
    _poly(d, w, h, [(0.595, 0.36), (0.59, 0.05), (0.53, 0.28)])
    _poly(d, w, h, [(0.36, 0.55), (0.3, 0.7), (0.4, 0.68)])
    _poly(d, w, h, [(0.64, 0.55), (0.7, 0.7), (0.6, 0.68)])
    return [(0.465, 0.42), (0.535, 0.42)], [(0.485, 0.8), (0.515, 0.8)]


def _ape(d, w, h):
    _poly(d, w, h, [(0.14, 1.05), (0.24, 0.6), (0.36, 0.5), (0.64, 0.5), (0.76, 0.6), (0.86, 1.05)])
    _ell(d, w, h, (0.13, 0.55, 0.3, 1.1))
    _ell(d, w, h, (0.7, 0.55, 0.87, 1.1))
    _ell(d, w, h, (0.41, 0.22, 0.59, 0.56))
    _ell(d, w, h, (0.385, 0.33, 0.43, 0.42))
    _ell(d, w, h, (0.57, 0.33, 0.615, 0.42))
    _ell(d, w, h, (0.43, 0.4, 0.57, 0.6))
    return [(0.465, 0.37), (0.535, 0.37)], [(0.485, 0.57), (0.515, 0.57)]


def _bird(d, w, h):
    _ell(d, w, h, (0.42, 0.34, 0.58, 0.95))
    for side in (-1, 1):
        cx = 0.5
        pts = [(cx + side * 0.04, 0.42), (cx + side * 0.2, 0.3), (cx + side * 0.36, 0.14), (cx + side * 0.45, 0.12),
               (cx + side * 0.42, 0.24), (cx + side * 0.46, 0.27), (cx + side * 0.4, 0.38), (cx + side * 0.43, 0.42),
               (cx + side * 0.34, 0.52), (cx + side * 0.36, 0.56), (cx + side * 0.24, 0.62), (cx + side * 0.06, 0.66)]
        _poly(d, w, h, pts)
    _ell(d, w, h, (0.445, 0.2, 0.555, 0.38))
    _poly(d, w, h, [(0.48, 0.32), (0.52, 0.32), (0.5, 0.47)])
    _poly(d, w, h, [(0.44, 0.9), (0.5, 1.1), (0.56, 0.9)])
    return [(0.475, 0.28), (0.525, 0.28)], []


def _serpent(d, w, h, lw=None):
    for box in ((0.2, 0.78, 0.8, 1.25), (0.28, 0.7, 0.72, 1.0), (0.36, 0.64, 0.64, 0.86)):
        _ell(d, w, h, box)
    _poly(d, w, h, [(0.44, 0.78), (0.45, 0.5), (0.47, 0.36), (0.53, 0.36), (0.55, 0.5), (0.56, 0.78)])
    _poly(d, w, h, [(0.4, 0.32), (0.44, 0.22), (0.5, 0.2), (0.56, 0.22), (0.6, 0.32), (0.57, 0.42), (0.53, 0.46),
                    (0.47, 0.46), (0.43, 0.42)])
    _poly(d, w, h, [(0.38, 0.36), (0.33, 0.55), (0.45, 0.5)])
    _poly(d, w, h, [(0.62, 0.36), (0.67, 0.55), (0.55, 0.5)])
    return [(0.465, 0.31), (0.535, 0.31)], [(0.485, 0.5), (0.515, 0.5)]


def _turtle(d, w, h):
    _ell(d, w, h, (0.16, 0.42, 0.84, 1.3))
    _ell(d, w, h, (0.1, 0.8, 0.28, 1.05))
    _ell(d, w, h, (0.72, 0.8, 0.9, 1.05))
    _ell(d, w, h, (0.42, 0.52, 0.58, 0.78))
    return [(0.47, 0.62), (0.53, 0.62)], [(0.49, 0.77), (0.51, 0.77)]


def _insect(d, w, h):
    _ell(d, w, h, (0.36, 0.5, 0.64, 1.05))
    _ell(d, w, h, (0.42, 0.34, 0.58, 0.56))
    for side in (-1, 1):
        for k, (ex, ey) in enumerate(((0.3, 0.28), (0.36, 0.5), (0.38, 0.72), (0.34, 0.95))):
            x0, y0 = 0.5 + side * 0.08, 0.55 + k * 0.08
            mx, my = 0.5 + side * (ex - 0.06), ey - 0.12
            x1, y1 = 0.5 + side * ex, ey + 0.12
            d.line([(x0 * w, y0 * h), (mx * w, my * h), (x1 * w, y1 * h)], fill=255, width=round(w * 0.012), joint="curve")
        _poly(d, w, h, [(0.5 + side * 0.03, 0.5), (0.5 + side * 0.12, 0.58), (0.5 + side * 0.05, 0.62)])
    return [(0.47, 0.42), (0.53, 0.42), (0.455, 0.46), (0.545, 0.46)], [(0.48, 0.6), (0.52, 0.6)]


def _dragon(d, w, h):
    # coils behind
    for box in ((0.05, 0.62, 0.45, 1.05), (0.55, 0.55, 0.97, 0.98), (0.25, 0.72, 0.75, 1.3)):
        _ell(d, w, h, box)
    _poly(d, w, h, [(0.4, 0.6), (0.4, 0.34), (0.46, 0.25), (0.54, 0.25), (0.6, 0.34), (0.6, 0.6), (0.56, 0.76),
                    (0.44, 0.76)])
    for side in (-1, 1):
        _poly(d, w, h, [(0.5 + side * 0.06, 0.28), (0.5 + side * 0.13, 0.08), (0.5 + side * 0.11, 0.0),
                        (0.5 + side * 0.17, 0.07), (0.5 + side * 0.09, 0.3)])
        d.line([(w * (0.5 + side * 0.05), h * 0.66), (w * (0.5 + side * 0.2), h * 0.72), (w * (0.5 + side * 0.3), h * 0.62)],
               fill=255, width=round(w * 0.006), joint="curve")
        _poly(d, w, h, [(0.5 + side * 0.09, 0.42), (0.5 + side * 0.17, 0.5), (0.5 + side * 0.1, 0.55)])
    return [(0.46, 0.4), (0.54, 0.4)], [(0.48, 0.74), (0.52, 0.74)]


def _human(d, w, h, hat=True):
    _poly(d, w, h, [(0.26, 1.05), (0.34, 0.66), (0.42, 0.56), (0.58, 0.56), (0.66, 0.66), (0.74, 1.05)])
    _ell(d, w, h, (0.445, 0.3, 0.555, 0.52))
    if hat:     # straw hat
        _poly(d, w, h, [(0.36, 0.38), (0.5, 0.2), (0.64, 0.38)])
    else:       # topknot and long beard
        _ell(d, w, h, (0.475, 0.24, 0.525, 0.32))
        _poly(d, w, h, [(0.46, 0.47), (0.54, 0.47), (0.5, 0.68)])
        _poly(d, w, h, [(0.32, 0.78), (0.2, 0.86), (0.28, 0.9), (0.4, 0.82)])   # sleeve
        _poly(d, w, h, [(0.68, 0.78), (0.8, 0.86), (0.72, 0.9), (0.6, 0.82)])
    return [(0.48, 0.42), (0.52, 0.42)], []


BODIES = {"cat": _cat, "wolf": _wolf, "ape": _ape, "bird": _bird, "serpent": _serpent, "turtle": _turtle,
          "insect": _insect, "dragon": _dragon, "human": _human, "master": lambda d, w, h: _human(d, w, h, hat=False)}


def _art(slug):
    path = os.path.join(ART_DIR, f"{slug}.png") if slug else None
    if path and os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            return None
    return None


def _creature(img, acc, body, slug):
    """Silhouette (or art) with rim light, glowing eyes and fangs, standing in the scene."""
    w, h = img.size
    art = _art(slug)
    eyes, fangs = [], []
    mw = min(w, round(h * 1.7))          # silhouettes are drawn in a box 1.7× as wide as the scene is tall
    ox = (w - mw) // 2
    if art is not None:
        scale = min(w * 0.62 / art.size[0], h * 0.92 / art.size[1])
        art = art.resize((max(1, round(art.size[0] * scale)), max(1, round(art.size[1] * scale))), Image.LANCZOS)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        layer.alpha_composite(art, ((w - art.size[0]) // 2, h - art.size[1]))
        mask = layer.getchannel("A")
    else:
        local = Image.new("L", (mw, h), 0)
        eyes, fangs = BODIES.get(body, _cat)(ImageDraw.Draw(local), mw, h)
        mask = Image.new("L", img.size, 0)
        mask.paste(local, (ox, 0))
        layer = None
    # rim light: a soft glow and a thin bright edge
    glow = Image.new("RGBA", img.size, acc.rim + (0,))
    glow.putalpha(mask.filter(ImageFilter.GaussianBlur(9 * S)).point(lambda v: min(255, v * 1.4)))
    img.alpha_composite(glow)
    edge = ImageChops.subtract(mask.filter(ImageFilter.MaxFilter(5)), mask)
    rim = Image.new("RGBA", img.size, mix(acc.rim, (255, 255, 255), 0.35) + (0,))
    rim.putalpha(edge.filter(ImageFilter.GaussianBlur(0.6 * S)))
    if layer is not None:
        img.alpha_composite(layer)
    else:
        fill = T.vgradient(img.size, (16, 14, 20), (3, 3, 5), 0, h)
        fill.putalpha(mask)
        img.alpha_composite(fill)
        d = ImageDraw.Draw(img)
        if body in ("cat", "wolf"):     # stripes / brow marks in the accent ink
            ink = alpha(mix(acc.rim, (0, 0, 0), 0.55), 220)
            X = lambda x: ox + x * mw   # noqa: E731
            for side in (-1, 1):
                for k in range(3):
                    y = 0.5 + k * 0.035
                    d.line([(X(0.5 + side * 0.07), h * y), (X(0.5 + side * 0.135), h * (y + 0.025))], fill=ink,
                           width=round(1.6 * S))
            d.line([(X(0.5), h * 0.3), (X(0.5), h * 0.34)], fill=ink, width=round(1.6 * S))
            for side in (-1, 1):
                d.line([(X(0.5 + side * 0.02), h * 0.31), (X(0.5 + side * 0.03), h * 0.355)], fill=ink,
                       width=round(1.6 * S))
        for fx, fy in fangs:
            fw, fx = mw * 0.008, ox + fx * mw
            d.polygon([(fx - fw, (fy - 0.06) * h), (fx + fw, (fy - 0.06) * h), (fx, fy * h)],
                      fill=(236, 230, 220, 255))
    img.alpha_composite(rim)
    if eyes:
        eyes = [((ox + ex * mw) / w, ey) for ex, ey in eyes]
        eg = Image.new("RGBA", img.size, acc.eyes + (0,))
        ed = ImageDraw.Draw(eg)
        for ex, ey in eyes:
            ed.ellipse((ex * w - mw * 0.026, ey * h - h * 0.03, ex * w + mw * 0.026, ey * h + h * 0.03), fill=alpha(acc.eyes, 200))
        img.alpha_composite(eg.filter(ImageFilter.GaussianBlur(5 * S)))
        d = ImageDraw.Draw(img)
        for ex, ey in eyes:
            rx, ry = mw * 0.014, h * 0.014
            d.polygon([(ex * w - rx, ey * h), (ex * w, ey * h - ry), (ex * w + rx, ey * h), (ex * w, ey * h + ry)],
                      fill=mix(acc.eyes, (255, 255, 255), 0.5) + (255,))
            d.ellipse((ex * w - rx * 0.25, ey * h - ry * 0.7, ex * w + rx * 0.25, ey * h + ry * 0.7), fill=(10, 10, 14, 255))


@lru_cache(maxsize=48)
def scene(palette, body, slug, seed=7, backdrop="wild"):
    """The scene window as an S× RGBA image (cached per enemy + element).
    backdrop: "wild" (moonlit mountains) or "courtyard" (the training ground)."""
    acc = T.ELEMENT_ACCENTS[palette]
    size = _scene_size()
    img = _sky(acc, size, seed)
    w, h = size
    _moon(img, acc, w * 0.74, h * 0.26, h * 0.14)
    (_courtyard if backdrop == "courtyard" else _landscape)(img, acc, seed)
    _creature(img, acc, body, slug)
    # darken the bottom so the name and HP bar read clearly
    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    shade.putalpha(Image.linear_gradient("L").resize(size).point(lambda v: max(0, v - 120) * 1.7))
    img.alpha_composite(shade)
    return img


# ── Card pieces ───────────────────────────────────────────────────────

def _chip(img, x, y, label, color):
    """A rounded status chip; returns its width."""
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 16, "Bold")
    tw = T.width(d, label.upper(), f)
    w = tw + 26
    d.rounded_rectangle(P(x, y - 15, x + w, y + 15), radius=15 * S, fill=alpha(mix(color, (0, 0, 0), 0.6), 240),
                        outline=alpha(color, 255), width=round(1.6 * S))
    T.text(d, (x + w / 2, y), label.upper(), f, mix(color, (255, 255, 255), 0.6), "mm")
    return w


def _heading(img, box, title):
    """Panel title, larger than the sheet cards' so it reads at half size."""
    x0, y0, x1, _ = box
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 19, "Bold")
    T.spaced(d, (x0 + 20, y0 + 26), title.upper(), f, T.GOLD, 2.4)
    tw = sum(T.width(d, ch, f) for ch in title.upper()) + 2.4 * (len(title) - 1)
    T.rule(d, x0 + 34 + tw, x1 - 18, y0 + 26)


def _enemy_plate(img, data, acc):
    e = data["enemy"]
    x0, y0, x1, y1 = SCENE
    d = ImageDraw.Draw(img)
    T.medallion(img, (x0 + 66, y1 - 66), 40, e["seal"], acc.rim)
    nf = font("Cinzel.ttf", 42, "Black")
    name = T.fit(d, e["name"].upper(), nf, 760)
    T.gold_text(img, (x0 + 120, y1 - 92), name, nf, "ls", glow=alpha(acc.rim, 120))
    d = ImageDraw.Draw(img)
    sub = " · ".join(e["tags"]).upper()
    T.spaced(d, (x0 + 122, y1 - 74), sub, font("Cinzel.ttf", 17, "Bold"), mix(T.GOLD_HI, acc.rim, 0.2), 2.0)
    frac = e["hp"] / e["max_hp"] if e["max_hp"] else 0
    T.bar(img, (x0 + 122, y1 - 54, x0 + 780, y1 - 24), frac, acc.hp,
          e.get("bar_label") or f"HP  {e['hp']:,} / {e['max_hp']:,}")
    # element seal and status chips on the right
    sx = x0 + 826
    T.medallion(img, (sx, y1 - 40), 26, e["element_seal"], acc.rim)
    cx = sx + 36
    for label in e["statuses"][:2]:
        cx += _chip(img, cx, y1 - 40, label, acc.rim) + 8


def _corner(img, data, acc):
    x0, y0, x1, y1 = SCENE
    d = ImageDraw.Draw(img)
    T.spaced(d, (x0 + 22, y0 + 28), data["header"].upper(), font("Cinzel.ttf", 17, "Bold"), T.GOLD_HI, 2.2)
    if data.get("result"):
        label = {"won": "VICTORY", "lost": "DEFEAT", "fled": "ESCAPED", "escaped": "IT GOT AWAY"}.get(
            data["result"], str(data["result"]).upper())
        T.gold_text(img, (x1 - 24, y0 + 44), label, font("Cinzel.ttf", 34, "Black"), "rm", glow=alpha(acc.rim, 120))
        return
    T.gold_text(img, (x1 - 24, y0 + 42), data.get("turn_label") or f"TURN {data['turn']}",
                font("Cinzel.ttf", 32, "Black"), "rm")
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 20, "SemiBold")
    label = data.get("seconds_label") or f"{data['seconds']}s to choose"
    tw = T.width(d, label, f)
    T.icon(img, "hourglass", (x1 - 36 - tw, y0 + 76), 18, T.GOLD)
    T.text(d, (x1 - 24, y0 + 76), label, f, T.PARCHMENT, "rm")


def _member_row(img, m, y, x0, x1, color, acc, arrow, tall):
    """One fighter: seal, name, realm, HP bar and their move under the bar."""
    d = ImageDraw.Draw(img)
    if arrow:
        hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(hl).rectangle(P(x0 + 20, y - tall / 2 + 2, x1 - 14, y + tall / 2 - 2),
                                     fill=alpha(mix(acc.panel, (255, 255, 255), 0.1), 210))
        img.alpha_composite(hl)
        d = ImageDraw.Draw(img)
        d.polygon([P(x0 + 9, y - 9), P(x0 + 20, y), P(x0 + 9, y + 9)], fill=T.PARCHMENT)
    T.medallion(img, (x0 + 50, y), 20, T.REALM_CHAR.get(m["realm"], "武"), color)
    d = ImageDraw.Draw(img)
    low = m["max_hp"] and m["hp"] / m["max_hp"] <= LOW_HP and not m.get("bar_color")
    name_col = (240, 90, 76) if low or m.get("ko") else (250, 240, 222)
    nf = font("Inter.ttf", 22, "Bold")
    T.text(d, (x0 + 80, y - 12), T.fit(d, m["name"], nf, 170), nf, name_col, "lm")
    T.text(d, (x0 + 80, y + 14), T.fit(d, f"{m['realm']} {m['layer']}", font("Inter.ttf", 16, "Medium"), 170),
           font("Inter.ttf", 16, "Medium"), T.ASH, "lm")
    bx0, bx1 = x0 + 262, x1 - 22
    frac = m["hp"] / m["max_hp"] if m["max_hp"] else 0
    T.bar(img, (bx0, y - 28, bx1, y - 1), frac, m.get("bar_color") or ((206, 64, 52) if low else (82, 176, 120)),
          m.get("bar_label") or f"{m['hp']:,} / {m['max_hp']:,} HP")
    d = ImageDraw.Draw(img)
    move = m.get("move")
    if move:
        mf = font("Inter.ttf", 17, "Medium")
        T.text(d, (bx0 + 2, y + 15), T.fit(d, move, mf, bx1 - bx0), mf,
               T.ASH if move in ("Waiting...", "Knocked out", "Fled") else (236, 222, 196), "lm")


def _party(img, data, acc):
    x0, y0, x1, y1 = PARTY
    T.panel(img, PARTY, None, fill=mix(acc.panel, (0, 0, 0), 0.25), glow=True, accent=acc)
    _heading(img, PARTY, data["party_title"])
    members = data["party"]
    rows = members[:4]
    tall = 68 if len(rows) > 1 else 72
    y = y0 + 52 + tall / 2
    for i, m in enumerate(rows):
        _member_row(img, m, y, x0, x1, MEMBER_COLORS[i % len(MEMBER_COLORS)], acc, m.get("arrow"), tall)
        y += tall
    d = ImageDraw.Draw(img)
    if len(members) > 4:
        T.text(d, (x0 + 30, y1 - 18), f"+{len(members) - 4} more fighters", font("Inter.ttf", 16, "Medium"), T.ASH, "lm")
    if len(members) == 1:
        y = y0 + 52 + tall + 30
        f = font("Inter.ttf", 21, "Medium")
        sf = font("Inter.ttf", 19, "SemiBold")
        df = font("Inter.ttf", 16, "Medium")
        items = data.get("loadout", [])[:4]
        step = 58 if any(i.get("desc") for i in items) else 50
        for item in items:
            T.medallion(img, (x0 + 50, y), 17, item["seal"], item["color"] or T.GOLD)
            d = ImageDraw.Draw(img)
            ny = y - 10 if item.get("desc") else y
            T.text(d, (x0 + 80, ny), T.fit(d, item["name"], f, 320), f, (246, 236, 216), "lm")
            if item.get("desc"):
                T.text(d, (x0 + 80, y + 14), T.fit(d, item["desc"], df, x1 - x0 - 110), df, (196, 182, 166), "lm")
            col = (120, 226, 150) if item["ready"] else (200, 180, 160)
            T.text(d, (x1 - 24, ny), item["state"], sf, col, "rm")
            y += step


LOG_ICON_COLOR = {"sword": (236, 96, 80), "shield": (140, 172, 240), "fist": (240, 178, 80), "skull": None,
                  "star": (246, 216, 116), "pill": (240, 110, 122), "flee": (190, 192, 204), "hourglass": T.GOLD,
                  "flame": (246, 150, 66), "herb": (100, 210, 140)}


def _log(img, data, acc):
    x0, y0, x1, y1 = LOG
    T.panel(img, LOG, None, fill=mix(acc.panel, (0, 0, 0), 0.25), glow=True, accent=acc)
    _heading(img, LOG, data.get("log_title", "Last turn"))
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 20, "Medium")
    lines = []
    for kind, line in data["log"]:          # long lines wrap onto a second row
        parts = T.wrap(d, line, f, x1 - x0 - 76, lines=2)
        lines += [(kind if i == 0 else None, part) for i, part in enumerate(parts)]
    lines = lines[-9:]
    y = y0 + 70
    gap = 32 if len(lines) <= 8 else 30
    for kind, line in lines:
        if kind:
            T.icon(img, kind, (x0 + 32, y), 18, LOG_ICON_COLOR.get(kind) or acc.eyes)
        d = ImageDraw.Draw(img)
        T.text(d, (x0 + 54, y), line, f, (244, 234, 214), "lm")
        y += gap


def _warning(img, data, acc):
    x0, y0, x1, y1 = WARN
    head, hint = data["warning"]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    g = T.vgradient((round((x1 - x0) * S), round((y1 - y0) * S)), mix(acc.warn, (255, 255, 255), 0.06),
                    mix(acc.warn, (0, 0, 0), 0.4))
    layer.alpha_composite(g, P(x0, y0))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.rectangle(P(x0, y0, x1, y1), outline=mix(acc.rim, (255, 255, 255), 0.3), width=round(1.8 * S))
    T.soft_glow(img, (x0 + 18, y0 + 18, x0 + 56, y1 - 18), alpha(acc.eyes, 120), 6)
    T.icon(img, "flame", (x0 + 38, (y0 + y1) / 2), 28, mix(acc.eyes, (255, 255, 255), 0.3))
    d = ImageDraw.Draw(img)
    hf = font("Inter.ttf", 25, "Bold")
    T.text(d, (x0 + 72, y0 + 28), T.fit(d, head, hf, x1 - x0 - 96), hf, (255, 248, 232), "lm")
    sf = font("Inter.ttf", 19, "Medium")
    T.text(d, (x0 + 72, y0 + 62), T.fit(d, hint, sf, x1 - x0 - 96), sf, mix(acc.moon, (255, 255, 255), 0.55), "lm")


def render_battle(data):
    acc = T.ELEMENT_ACCENTS[data["palette"]]
    img = T.canvas(W, H, seed=11, accent=data["palette"].lower())
    e = data["enemy"]
    sc = scene(data["palette"], e["body"], e.get("slug"), backdrop=data.get("backdrop", "wild"))
    img.alpha_composite(sc, P(SCENE[0], SCENE[1]))
    T.frame(img, SCENE, 0.8)
    _corner(img, data, acc)
    _enemy_plate(img, data, acc)
    _party(img, data, acc)
    _log(img, data, acc)
    _warning(img, data, acc)
    T.frame(img, (8, 8, W - 8, H - 8), 1.0)
    return T.finish(img)
