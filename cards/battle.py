"""
The fight screen: one card that the bot edits every turn (docs/combat.md).

  ┌ scene window: sky, moon, mist, mountains and the enemy (art/beasts/<slug>.png, or a drawn silhouette)
  │   over its bottom: seal, name, tier · role · element · realm, HP bar, element seal, status chips
  │   top right: turn number and seconds to choose
  ├ "Hunting Party" (or "You" with your techniques and pills when solo): big HP bars
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

# Discord shrinks the card to well under half size on a computer, so the card keeps only the big things
# (HP bars, names, the warning) in large type: nothing under 24px. The details (technique effects, the
# turn log) go in the text under the card, which Discord shows at normal reading size (bot/fight_view).
W, H = 1200, 780
SCENE = (16, 16, 1184, 396)
PARTY = (16, 408, 1184, 652)
WARN = (16, 664, 1184, 764)
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


def _ledge(img, acc, seed):
    """The duelling ground: a stone ledge high above a sea of clouds, peaks at dusk, two old pines."""
    w, h = img.size
    far = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(far).polygon(_ridge(w, h, h * 0.6, h * 0.34, seed, 7), fill=alpha(mix(acc.mist, acc.sky[0], 0.6), 255))
    img.alpha_composite(far)
    clouds = Image.new("RGBA", img.size, acc.mist + (0,))
    cd = ImageDraw.Draw(clouds)
    r = random.Random(seed)
    for _ in range(14):
        cx, cy = r.uniform(-0.1, 1.1) * w, r.uniform(0.6, 0.78) * h
        rw, rh = r.uniform(0.12, 0.26) * w, r.uniform(0.05, 0.09) * h
        cd.ellipse((cx - rw, cy - rh, cx + rw, cy + rh), fill=alpha(mix(acc.mist, acc.moon, 0.35), 150))
    img.alpha_composite(clouds.filter(ImageFilter.GaussianBlur(h * 0.025)))
    ground = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ground)
    rock = alpha(mix(acc.sky[0], (0, 0, 0), 0.45), 255)
    d.polygon([(0, h * 0.8), (w * 0.08, h * 0.76), (w * 0.92, h * 0.76), (w, h * 0.8), (w, h), (0, h)], fill=rock)
    d.line([(w * 0.08, h * 0.76), (w * 0.92, h * 0.76)], fill=alpha(acc.rim, 160), width=max(1, round(1.5 * S)))
    for k in range(11):                                  # flagstones fanning out from the middle
        x = w * k / 10
        d.line([(w / 2 + (x - w / 2) * 0.55, h * 0.77), (x, h)], fill=alpha(acc.mist, 45), width=max(1, S))
    dark = alpha(mix(acc.sky[0], (0, 0, 0), 0.7), 255)
    for x, ht in ((0.035, 0.42), (0.965, 0.38)):
        _pine(d, w * x, h * 0.8, h * ht, dark)
    img.alpha_composite(ground)


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
    backdrop: "wild" (moonlit mountains), "courtyard" (the training ground) or "ledge" (the duelling ground).
    body None: no creature (duels draw both fighters over the scene)."""
    acc = T.ELEMENT_ACCENTS[palette]
    size = _scene_size()
    img = _sky(acc, size, seed)
    w, h = size
    if backdrop == "ledge":      # between the left fighter and the turn number, clear of both
        _moon(img, acc, w * 0.31, h * 0.2, h * 0.12)
    else:
        _moon(img, acc, w * 0.74, h * 0.26, h * 0.14)
    {"courtyard": _courtyard, "ledge": _ledge}.get(backdrop, _landscape)(img, acc, seed)
    if body:
        _creature(img, acc, body, slug)
    # darken the bottom so the name and HP bar read clearly
    shade = Image.new("RGBA", size, (0, 0, 0, 0))
    shade.putalpha(Image.linear_gradient("L").resize(size).point(lambda v: max(0, v - 90) * 1.5))
    img.alpha_composite(shade)
    return img


# ── Card pieces ───────────────────────────────────────────────────────

def _shrink(d, s, face, weight, sizes, max_w):
    """The largest of `sizes` that fits; the smallest one shortened with an ellipsis otherwise."""
    for size in sizes:
        f = font(face, size, weight)
        if T.width(d, s, f) <= max_w:
            return s, f
    return T.fit(d, s, f, max_w), f


def _chip(img, x, y, label, color, anchor="l"):
    """A rounded status chip at (x, y); anchor "r" grows it to the left. Returns its width."""
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 24, "Bold")
    tw = T.width(d, label.upper(), f)
    w = tw + 34
    if anchor == "r":
        x -= w
    d.rounded_rectangle(P(x, y - 21, x + w, y + 21), radius=21 * S, fill=alpha(mix(color, (0, 0, 0), 0.6), 240),
                        outline=alpha(color, 255), width=round(2 * S))
    T.text(d, (x + w / 2, y), label.upper(), f, mix(color, (255, 255, 255), 0.6), "mm")
    return w


def _heading(img, box, title):
    x0, y0, x1, _ = box
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 26, "Bold")
    T.spaced(d, (x0 + 22, y0 + 30), title.upper(), f, T.GOLD, 2.6)
    tw = sum(T.width(d, ch, f) for ch in title.upper()) + 2.6 * (len(title) - 1)
    T.rule(d, x0 + 40 + tw, x1 - 20, y0 + 30)


def _enemy_plate(img, data, acc):
    e = data["enemy"]
    x0, y0, x1, y1 = SCENE
    d = ImageDraw.Draw(img)
    T.seal(img, (x0 + 72, y1 - 72), 50, e["seal"], acc.rim)
    name, nf = _shrink(d, e["name"].upper(), "Cinzel.ttf", "Black", (54, 48, 42, 36), x1 - x0 - 170)
    T.gold_text(img, (x0 + 140, y1 - 108), name, nf, "ls", glow=alpha(acc.rim, 120))
    d = ImageDraw.Draw(img)
    sub = " · ".join(e["tags"]).upper()
    T.spaced(d, (x0 + 142, y1 - 86), T.fit(d, sub, font("Cinzel.ttf", 24, "Bold"), 700),
             font("Cinzel.ttf", 24, "Bold"), mix(T.GOLD_HI, acc.rim, 0.2), 1.6)
    frac = e["hp"] / e["max_hp"] if e["max_hp"] else 0
    T.bar(img, (x0 + 142, y1 - 66, x1 - 96, y1 - 14), frac, acc.hp,
          e.get("bar_label") or f"{e['hp']:,} / {e['max_hp']:,} HP")
    # element seal at the end of the bar, status chips under the timer at the top right
    T.seal(img, (x1 - 50, y1 - 40), 34, e["element_seal"], acc.rim)
    cx = x1 - 24
    for label in e["statuses"][:3]:
        cx -= _chip(img, cx, y0 + 148, label, acc.rim, "r") + 10


def _corner(img, data, acc):
    x0, y0, x1, y1 = SCENE
    d = ImageDraw.Draw(img)
    T.spaced(d, (x0 + 24, y0 + 34), T.fit(d, data["header"].upper(), font("Cinzel.ttf", 26, "Bold"), 620),
             font("Cinzel.ttf", 26, "Bold"), T.GOLD_HI, 2.2)
    if data.get("result"):
        label = {"won": "VICTORY", "lost": "DEFEAT", "fled": "ESCAPED", "escaped": "IT GOT AWAY"}.get(
            data["result"], str(data["result"]).upper())
        T.gold_text(img, (x1 - 26, y0 + 50), label, font("Cinzel.ttf", 48, "Black"), "rm", glow=alpha(acc.rim, 120))
        return
    T.gold_text(img, (x1 - 26, y0 + 46), data.get("turn_label") or f"TURN {data['turn']}",
                font("Cinzel.ttf", 46, "Black"), "rm")
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 28, "SemiBold")
    label = data.get("seconds_label") or f"{data['seconds']}s to choose"
    tw = T.width(d, label, f)
    T.icon(img, "hourglass", (x1 - 46 - tw, y0 + 98), 26, T.GOLD)
    T.text(d, (x1 - 26, y0 + 98), label, f, T.PARCHMENT, "rm")


def _bar_color(m):
    low = m["max_hp"] and m["hp"] / m["max_hp"] <= LOW_HP and not m.get("bar_color")
    return low, m.get("bar_color") or ((206, 64, 52) if low else (82, 176, 120))


def _arrow(img, x0, x1, yc, half, acc):
    hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(hl).rectangle(P(x0 + 4, yc - half, x1 - 4, yc + half),
                                 fill=alpha(mix(acc.panel, (255, 255, 255), 0.12), 210))
    img.alpha_composite(hl)
    ImageDraw.Draw(img).polygon([P(x0 + 6, yc - 12), P(x0 + 20, yc), P(x0 + 6, yc + 12)], fill=T.PARCHMENT)


def _solo(img, data, acc):
    """One fighter, large: seal, name, realm, a big HP bar, the last move, then the loadout in one row."""
    x0, y0, x1, y1 = PARTY
    m = data["party"][0]
    low, color = _bar_color(m)
    y = y0 + 96
    T.seal(img, (x0 + 58, y), 36, "emblem:realm:" + m["realm"], MEMBER_COLORS[0])
    d = ImageDraw.Draw(img)
    nf, rf = font("Inter.ttf", 34, "Bold"), font("Inter.ttf", 26, "Medium")
    T.text(d, (x0 + 108, y - 18), T.fit(d, m["name"], nf, 250), nf, (240, 90, 76) if low or m.get("ko") else
           (250, 240, 222), "lm")
    T.text(d, (x0 + 108, y + 20), T.fit(d, f"{m['realm']} {m['layer']}", rf, 250), rf, T.ASH, "lm")
    bx0, bx1 = x0 + 380, x1 - 26
    frac = m["hp"] / m["max_hp"] if m["max_hp"] else 0
    T.bar(img, (bx0, y - 28, bx1, y + 26), frac, color, m.get("bar_label") or f"{m['hp']:,} / {m['max_hp']:,} HP")
    items = data.get("loadout", [])[:3]
    if not items:
        return
    d = ImageDraw.Draw(img)
    T.rule(d, x0 + 24, x1 - 24, y0 + 150)
    cw = (x1 - x0 - 24) / len(items)
    f, sf = font("Inter.ttf", 26, "Bold"), font("Inter.ttf", 26, "SemiBold")
    for i, item in enumerate(items):
        cx0 = x0 + 12 + i * cw
        cy = y0 + 198
        T.seal(img, (cx0 + 36, cy), 24, item["seal"], item["color"] or T.GOLD)
        d = ImageDraw.Draw(img)
        state = item["state"]
        sw = T.width(d, state, sf)
        T.text(d, (cx0 + 70, cy), T.fit(d, item["name"], f, cw - 100 - sw), f, (246, 236, 216), "lm")
        T.text(d, (cx0 + cw - 18, cy), state, sf, (120, 226, 150) if item["ready"] else (210, 186, 160), "rm")


def _team(img, data, acc):
    """Up to six fighters in two columns: seal, name and a big HP bar each."""
    x0, y0, x1, y1 = PARTY
    members = data["party"]
    shown = members[:6] if len(members) <= 6 else members[:5]
    cols = 1 if len(shown) <= 3 else 2
    rows = math.ceil(len(shown) / cols)
    cw = (x1 - x0 - 16) / cols
    rh = min(70, (y1 - y0 - 62) / max(1, rows))
    nf = font("Inter.ttf", 28, "Bold")
    for i, m in enumerate(shown):
        c, r = (i // rows, i % rows) if cols == 2 else (0, i)
        cx0, cx1 = x0 + 8 + c * cw, x0 + 8 + (c + 1) * cw
        yc = y0 + 58 + rh * r + rh / 2
        if m.get("arrow"):
            _arrow(img, cx0, cx1, yc, rh / 2 - 3, acc)
        low, color = _bar_color(m)
        T.seal(img, (cx0 + 50, yc), 24, "emblem:realm:" + m["realm"], MEMBER_COLORS[i % len(MEMBER_COLORS)])
        d = ImageDraw.Draw(img)
        name_w = 210 if cols == 2 else 300
        T.text(d, (cx0 + 84, yc), T.fit(d, m["name"], nf, name_w), nf,
               (240, 90, 76) if low or m.get("ko") else (250, 240, 222), "lm")
        frac = m["hp"] / m["max_hp"] if m["max_hp"] else 0
        label = ("Fled" if m.get("move") == "Fled" else "KO" if m.get("ko") else
                 f"{m['hp']:,} / {m['max_hp']:,}")
        T.bar(img, (cx0 + 96 + name_w, yc - 21, cx1 - 18, yc + 21), frac, color, m.get("bar_label") or label)
    if len(members) > len(shown):
        d = ImageDraw.Draw(img)
        T.text(d, (x1 - 30, y0 + 30), f"+{len(members) - len(shown)} more", font("Inter.ttf", 24, "SemiBold"), T.ASH,
               "rm")


def _party(img, data, acc):
    T.panel(img, PARTY, None, fill=mix(acc.panel, (0, 0, 0), 0.25), glow=True, accent=acc)
    members = data["party"]
    title = data["party_title"]
    if len(members) == 1:
        _heading(img, PARTY, title)
        _solo(img, data, acc)
    else:
        _heading(img, PARTY, f"{title} · {len(members)}")
        _team(img, data, acc)


def _warning(img, data, acc, box=WARN):
    x0, y0, x1, y1 = box
    head, hint = data["warning"]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    g = T.vgradient((round((x1 - x0) * S), round((y1 - y0) * S)), mix(acc.warn, (255, 255, 255), 0.06),
                    mix(acc.warn, (0, 0, 0), 0.4))
    layer.alpha_composite(g, P(x0, y0))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.rectangle(P(x0, y0, x1, y1), outline=mix(acc.rim, (255, 255, 255), 0.3), width=round(2 * S))
    T.soft_glow(img, (x0 + 18, y0 + 20, x0 + 70, y1 - 20), alpha(acc.eyes, 120), 6)
    T.icon(img, data.get("warning_icon", "flame"), (x0 + 44, (y0 + y1) / 2), 36, mix(acc.eyes, (255, 255, 255), 0.3))
    d = ImageDraw.Draw(img)
    mw = x1 - x0 - 110
    head, hf = _shrink(d, head, "Inter.ttf", "Bold", (36, 32, 28), mw)
    if not hint:
        T.text(d, (x0 + 86, (y0 + y1) / 2), head, hf, (255, 248, 232), "lm")
        return
    T.text(d, (x0 + 86, y0 + 32), head, hf, (255, 248, 232), "lm")
    hint, sf = _shrink(d, hint, "Inter.ttf", "Medium", (27, 25, 23), mw)
    T.text(d, (x0 + 86, y0 + 72), hint, sf, mix(acc.moon, (255, 255, 255), 0.55), "lm")


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
    _warning(img, data, acc)
    T.frame(img, (6, 6, W - 6, H - 6), 1.0)
    return T.finish(img)


# ── Duels (docs/pvp.md) ───────────────────────────────────────────────
# The same frame: the scene shows both fighters facing each other on the duelling ground, the panel
# below has one big half per player, and the bottom bar shows the last turn (or the result).
# Picks stay secret: a side only shows "LOCKED IN", never what was picked, until the reveal.

DUEL_SIDE_COLORS = [(92, 150, 236), (232, 120, 72)]
DUEL_AVATAR = [(230, 214), (970, 214)]
DUEL_AVATAR_R = 116


def _robed(size, color):
    """A robed silhouette with rim light, for a fighter without an avatar."""
    w = h = size
    mask = Image.new("L", (w, h), 0)
    _human(ImageDraw.Draw(mask), w, h, hat=False)
    img = T.vgradient((w, h), mix(color, (0, 0, 0), 0.55), (10, 8, 12))
    glow = Image.new("RGBA", (w, h), color + (0,))
    glow.putalpha(mask.filter(ImageFilter.GaussianBlur(6 * S)))
    img.alpha_composite(glow)
    body = T.vgradient((w, h), (22, 18, 24), (4, 4, 6))
    body.putalpha(mask)
    img.alpha_composite(body)
    return img


def _avatar(img, center, r, side, acc):
    """The fighter's Discord avatar (or a robed silhouette) in a round gold frame."""
    cx, cy = center
    color = DUEL_SIDE_COLORS[side["index"] % 2]
    if side.get("winner"):
        T.soft_glow(img, (cx - r - 30, cy - r - 30, cx + r + 30, cy + r + 30), alpha(T.GOLD_HI, 170), 14)
    else:
        T.soft_glow(img, (cx - r - 18, cy - r - 18, cx + r + 18, cy + r + 18), alpha(color, 130), 12)
    size = round(2 * r * S)
    face = None
    if side.get("avatar_bytes"):
        try:
            import io
            face = Image.open(io.BytesIO(side["avatar_bytes"])).convert("RGBA").resize((size, size), Image.LANCZOS)
        except Exception:
            face = None
    if face is None:
        face = _robed(size, color)
    if side.get("loser"):
        grey = face.convert("L").convert("RGBA")
        face = Image.blend(face, grey, 0.75)
        face.alpha_composite(Image.new("RGBA", face.size, (0, 0, 0, 90)))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size - 1, size - 1), fill=255)
    face.putalpha(mask)
    img.alpha_composite(face, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    for off, col, wdt in ((-6, T.BRONZE_DK, 6), (-2, T.GOLD, 2.4), (3, alpha(T.BRONZE, 200), 1.2)):
        d.ellipse(P(cx - r + off, cy - r + off, cx + r - off, cy + r - off), outline=col, width=round(wdt * S))
    for a in (0, 90, 180, 270):                  # studs around the ring
        x, y = cx + math.cos(math.radians(a)) * (r + 4), cy + math.sin(math.radians(a)) * (r + 4)
        T.stud(d, x, y, 6)


def _check(d, x, y, size, color):
    """A drawn tick mark (emoji don't render on the card)."""
    s = size / 2
    d.line([P(x - s, y), P(x - s * 0.3, y + s * 0.7), P(x + s, y - s * 0.75)], fill=color, width=round(size * 0.22 * S),
           joint="curve")


def _lock_chip(img, center, locked, acc):
    cx, cy = center
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 26, "Bold")
    if locked:
        label, color = "LOCKED IN", (96, 206, 128)
    else:
        label, color = "CHOOSING...", (176, 164, 150)
    tw = T.width(d, label, f)
    w = tw + (82 if locked else 40)
    x0 = cx - w / 2
    d.rounded_rectangle(P(x0, cy - 24, x0 + w, cy + 24), radius=24 * S, fill=alpha(mix(color, (0, 0, 0), 0.7), 245),
                        outline=alpha(color, 255), width=round(2.4 * S))
    if locked:
        _check(d, x0 + 34, cy, 26, mix(color, (255, 255, 255), 0.3))
        T.text(d, (x0 + 58, cy), label, f, mix(color, (255, 255, 255), 0.55), "lm")
    else:
        T.text(d, (cx, cy), label, f, mix(color, (255, 255, 255), 0.4), "mm")


def _duel_scene(img, data, acc):
    x0, y0, x1, y1 = SCENE
    d = ImageDraw.Draw(img)
    hf = font("Cinzel.ttf", 26, "Bold")
    T.spaced(d, (x0 + 24, y0 + 34), "FRIENDLY DUEL", hf, T.GOLD_HI, 2.2)
    if data.get("fair_label"):
        lab = data["fair_label"].upper()
        lw = sum(T.width(d, ch, hf) for ch in lab) + 2.2 * (len(lab) - 1)
        T.spaced(d, (x1 - 24 - lw, y0 + 34), lab, hf, T.GOLD_HI, 2.2)
    for i, side in enumerate(data["sides"]):
        _avatar(img, DUEL_AVATAR[i], DUEL_AVATAR_R, dict(side, index=i), acc)
        if not data.get("result"):
            _lock_chip(img, (DUEL_AVATAR[i][0], y1 - 34), side.get("locked"), acc)
    mid = (x0 + x1) / 2
    res = data.get("result")
    if res:
        T.gold_text(img, (mid, y0 + 130), "DRAW" if res.get("draw") else "WINNER", font("Cinzel.ttf", 40, "Black"), "mm",
                    glow=alpha(acc.rim, 140))
        name, nf = _shrink(ImageDraw.Draw(img), res["title"].upper(), "Cinzel.ttf", "Black", (60, 52, 44, 38, 32), 470)
        T.gold_text(img, (mid, y0 + 200), name, nf, "mm", glow=alpha(acc.rim, 160))
        d = ImageDraw.Draw(img)
        f = font("Inter.ttf", 28, "SemiBold")
        T.text(d, (mid, y0 + 268), T.fit(d, res.get("sub", ""), f, 470), f, T.PARCHMENT, "mm")
        return
    T.gold_text(img, (mid, y0 + 78), f"TURN {data['turn']}", font("Cinzel.ttf", 50, "Black"), "mm")
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 28, "SemiBold")
    label = data.get("seconds_label") or f"{data['seconds']}s to choose"
    tw = T.width(d, label, f)
    T.icon(img, "hourglass", (mid - tw / 2 - 18, y0 + 128), 26, T.GOLD)
    T.text(ImageDraw.Draw(img), (mid + 14, y0 + 128), label, f, T.PARCHMENT, "mm")
    T.gold_text(img, (mid, y0 + 214), "VS", font("Cinzel.ttf", 96, "Black"), "mm", glow=alpha(acc.rim, 170))
    if data.get("intensity"):
        label = f"RISING INTENSITY +{data['intensity']:.0%}"
        d = ImageDraw.Draw(img)
        cf = font("Inter.ttf", 26, "Bold")
        w = T.width(d, label, cf) + 40
        y = y0 + 300
        T.soft_glow(img, (mid - w / 2 - 8, y - 30, mid + w / 2 + 8, y + 30), alpha(acc.eyes, 110), 8, "rect")
        d = ImageDraw.Draw(img)
        d.rounded_rectangle(P(mid - w / 2, y - 24, mid + w / 2, y + 24), radius=24 * S,
                            fill=alpha(mix(acc.rim, (0, 0, 0), 0.55), 245), outline=alpha(acc.eyes, 255),
                            width=round(2.4 * S))
        T.text(d, (mid, y), label, cf, (255, 240, 214), "mm")


def _duel_side(img, box, side, i, acc):
    """One player's half of the panel: talent seal, name, realm and layer, a big HP bar, the last move."""
    x0, y0, x1, y1 = box
    right = i == 1
    color = DUEL_SIDE_COLORS[i]
    seal_x = x1 - 62 if right else x0 + 62
    T.medallion(img, (seal_x, y0 + 64), 42, T.TALENT_CHAR.get(side["talent"], "凡"), T.TALENT.get(side["talent"], color))
    d = ImageDraw.Draw(img)
    nf, rf = font("Inter.ttf", 38, "Bold"), font("Inter.ttf", 27, "SemiBold")
    low = side["max_hp"] and side["hp"] / side["max_hp"] <= LOW_HP
    tx, anchor = (x1 - 122, "r") if right else (x0 + 122, "l")
    T.text(d, (tx, y0 + 46), T.fit(d, side["name"], nf, x1 - x0 - 150), nf,
           (240, 90, 76) if low else (250, 240, 222), anchor + "m")
    realm = f"{side['realm']} · {side['layer_label']}"
    T.text(d, (tx, y0 + 88), T.fit(d, realm, rf, x1 - x0 - 150), rf, mix(color, (255, 255, 255), 0.55), anchor + "m")
    frac = side["hp"] / side["max_hp"] if side["max_hp"] else 0
    bar_color = (206, 64, 52) if low else (82, 176, 120)
    T.bar(img, (x0 + 22, y0 + 124, x1 - 22, y0 + 184), frac, bar_color, f"{side['hp']:,} / {side['max_hp']:,} HP")
    d = ImageDraw.Draw(img)
    last = side.get("last")
    if last:
        lf = font("Inter.ttf", 28, "SemiBold")
        T.text(d, (x1 - 26 if right else x0 + 26, y0 + 216), T.fit(d, f"Last: {last}", lf, x1 - x0 - 50), lf,
               (236, 222, 196), anchor + "m")


def _duel_panel(img, data, acc):
    x0, y0, x1, y1 = PARTY
    T.panel(img, PARTY, None, fill=mix(acc.panel, (0, 0, 0), 0.25), glow=True, accent=acc)
    mid = (x0 + x1) / 2
    d = ImageDraw.Draw(img)
    d.line(P(mid, y0 + 18, mid, y1 - 18), fill=alpha(T.BRONZE, 200), width=round(2 * S))
    for i, side in enumerate(data["sides"]):
        _duel_side(img, (x0 + 4, y0, mid - 4, y1) if i == 0 else (mid + 4, y0, x1 - 4, y1), side, i, acc)


def render_duel(data):
    """The PvP duel card. data: see bot/duel_view.duel_card_data."""
    acc = T.ELEMENT_ACCENTS[data.get("palette", "Duel")]
    img = T.canvas(W, H, seed=13, accent=data.get("palette", "Duel").lower())
    sc = scene(data.get("palette", "Duel"), None, None, backdrop="ledge")
    img.alpha_composite(sc, P(SCENE[0], SCENE[1]))
    T.frame(img, SCENE, 0.8)
    _duel_scene(img, data, acc)
    _duel_panel(img, data, acc)
    _warning(img, dict(data, warning=data.get("bottom") or ("", "")), acc)
    T.frame(img, (6, 6, W - 6, H - 6), 1.0)
    return T.finish(img)
