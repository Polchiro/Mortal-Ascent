"""
Drawn wilderness pieces shared by the /explore crossroads card (cards/expedition.py) and the /gather herb field
card (cards/herbfield.py): skies, ridges, trees, mist, water, rocks and glows. Pillow only.

Every helper draws on an RGBA layer in card pixels (scaled by S through theme.P), so the scenes come out
smooth after theme.finish().
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from . import theme as T
from .theme import P, S, alpha, mix


def layer(w, h):
    return Image.new("RGBA", P(w, h), (0, 0, 0, 0))


def sky(w, h, top, bottom):
    return T.vgradient(P(w, h), top, bottom)


def blur(img, r):
    return img.filter(ImageFilter.GaussianBlur(r * S))


def glow(img, cx, cy, rx, ry, color, a, r):
    """A soft blurred ellipse of light."""
    g = layer(*(v / S for v in img.size))
    ImageDraw.Draw(g).ellipse(P(cx - rx, cy - ry, cx + rx, cy + ry), fill=alpha(color, a))
    img.alpha_composite(blur(g, r))


def feather(img, left=True, right=True, frac=0.22):
    """Fade the layer out towards its left/right edges (so moods blend into each other)."""
    w, h = img.size
    ramp = Image.new("L", (w, 1))
    edge = max(1, int(w * frac))
    ramp.putdata([round(255 * min(1.0, (x / edge if left else 1.0), ((w - 1 - x) / edge if right else 1.0)))
                  for x in range(w)])
    ramp = ramp.resize((w, h))
    a = img.getchannel("A")
    img.putalpha(Image.composite(a, Image.new("L", (w, h), 0), ramp))
    return img


def ridge(d, w, base, amp, seed, color, peaks=6):
    """A jagged mountain ridge filled down to the bottom."""
    r = random.Random(seed)
    pts = [(0, base)]
    n = peaks * 2
    for i in range(n + 1):
        x = w * i / n
        y = base - (amp * r.uniform(0.55, 1.0) if i % 2 else amp * r.uniform(0.0, 0.3))
        pts.append((x, y))
    pts += [(w, base + 2000), (0, base + 2000)]
    d.polygon([P(*p) for p in pts], fill=color)


def pine(d, x, base, height, fill):
    """A layered pine silhouette."""
    tiers = 4
    for i in range(tiers):
        top = base - height + i * height * 0.2
        bot = top + height * 0.42
        half = height * (0.16 + 0.07 * i)
        d.polygon([P(x, top), P(x + half, bot), P(x - half, bot)], fill=fill)
    d.rectangle(P(x - height * 0.025, base - height * 0.25, x + height * 0.025, base), fill=fill)


def bamboo(d, x, base, height, fill, width=9, seed=0):
    r = random.Random(seed)
    d.rectangle(P(x - width / 2, base - height, x + width / 2, base), fill=fill)
    y = base
    while y > base - height:
        y -= r.uniform(46, 70)
        d.line(P(x - width / 2 - 2, y, x + width / 2 + 2, y), fill=mix(fill[:3], (0, 0, 0), 0.4) + (fill[3],),
               width=round(2 * S))
        if r.random() < 0.5:
            side = r.choice((-1, 1))
            d.polygon([P(x, y), P(x + side * 46, y - 18), P(x + side * 50, y - 10)], fill=fill)


def bare_tree(d, x, base, height, fill, seed=0, wd=5):
    """A dead tree: trunk and a few forked branches."""
    r = random.Random(seed)
    top = base - height
    d.line(P(x, base, x, top), fill=fill, width=round(wd * S))

    def branch(bx, by, ang, ln, w):
        if ln < 14 or w < 1:
            return
        ex, ey = bx + math.cos(ang) * ln, by - math.sin(ang) * ln
        d.line(P(bx, by, ex, ey), fill=fill, width=max(1, round(w * S)))
        branch(ex, ey, ang + r.uniform(0.25, 0.6), ln * 0.62, w * 0.65)
        branch(ex, ey, ang - r.uniform(0.25, 0.6), ln * 0.6, w * 0.65)
    for i in range(3):
        by = top + height * (0.1 + 0.18 * i)
        branch(x, by, math.pi / 2 + r.choice((-1, 1)) * r.uniform(0.5, 1.0), height * 0.32, wd * 0.7)


def mist(img, w, y, h, color, a=120, seed=0, n=10):
    """Soft bands of mist across the layer."""
    g = layer(w, img.size[1] / S)
    d = ImageDraw.Draw(g)
    r = random.Random(seed)
    for _ in range(n):
        cx, cy = r.uniform(-40, w + 40), y + r.uniform(-h / 2, h / 2)
        rw, rh = r.uniform(120, 260), r.uniform(h * 0.25, h * 0.5)
        d.ellipse(P(cx - rw, cy - rh, cx + rw, cy + rh), fill=alpha(color, r.randint(a // 2, a)))
    img.alpha_composite(blur(g, 16))


def motes(d, w, h, color, n, seed, y0=0, r0=1.2, r1=3.0):
    r = random.Random(seed)
    for _ in range(n):
        x, y = r.uniform(0, w), r.uniform(y0, h)
        rad = r.uniform(r0, r1)
        d.ellipse(P(x - rad, y - rad, x + rad, y + rad), fill=alpha(color, r.randint(120, 255)))


def eyes(img, cx, cy, size, color):
    """A pair of glowing eyes in the dark."""
    glow(img, cx, cy, size * 3.2, size * 1.6, color, 120, size * 0.9)
    d = ImageDraw.Draw(img)
    for sx in (-1, 1):
        ex = cx + sx * size * 1.25
        d.ellipse(P(ex - size, cy - size * 0.6, ex + size, cy + size * 0.6), fill=alpha(color, 255))
        d.ellipse(P(ex - size * 0.35, cy - size * 0.3, ex + size * 0.35, cy + size * 0.3),
                  fill=alpha(mix(color, (255, 255, 255), 0.7), 255))


def rock(d, cx, base, w, h, fill, seed=0, light=None):
    r = random.Random(seed)
    pts = [(cx - w / 2, base)]
    for i in range(1, 6):
        t = i / 6
        pts.append((cx - w / 2 + w * t + r.uniform(-w * 0.05, w * 0.05),
                    base - h * math.sin(math.pi * t) * r.uniform(0.8, 1.1)))
    pts.append((cx + w / 2, base))
    d.polygon([P(*p) for p in pts], fill=fill)
    if light:
        d.line([P(*p) for p in pts[1:4]], fill=light, width=max(1, round(1.5 * S)))


def water(img, x0, y0, x1, y1, color, shine):
    """A still lake: flat ellipse, horizontal shimmer lines."""
    d = ImageDraw.Draw(img)
    d.ellipse(P(x0, y0, x1, y1), fill=alpha(color, 235))
    r = random.Random(int(x0 + y0))
    cy = (y0 + y1) / 2
    for i in range(12):
        yy = y0 + (y1 - y0) * (0.2 + 0.6 * r.random())
        half = (x1 - x0) / 2 * math.sqrt(max(0.0, 1 - ((yy - cy) / ((y1 - y0) / 2)) ** 2)) * r.uniform(0.2, 0.7)
        xc = (x0 + x1) / 2 + r.uniform(-30, 30)
        d.line(P(xc - half, yy, xc + half, yy), fill=alpha(shine, r.randint(60, 150)), width=max(1, round(1.5 * S)))


def smoke(img, x, base, height, color, a=150, seed=0):
    """A curling column of smoke."""
    g = layer(*(v / S for v in img.size))
    d = ImageDraw.Draw(g)
    r = random.Random(seed)
    for i in range(14):
        t = i / 13
        cx = x + math.sin(t * 5 + seed) * 18 * t
        cy = base - height * t
        rad = 8 + 26 * t
        d.ellipse(P(cx - rad, cy - rad, cx + rad, cy + rad), fill=alpha(color, round(a * (1 - t * 0.7))))
    img.alpha_composite(blur(g, 7))


def flame(d, cx, base, size):
    d.polygon([P(cx - size * 0.5, base), P(cx - size * 0.3, base - size * 0.8), P(cx, base - size * 1.4),
               P(cx + size * 0.3, base - size * 0.8), P(cx + size * 0.5, base)], fill=(246, 120, 40, 255))
    d.polygon([P(cx - size * 0.25, base), P(cx, base - size * 0.8), P(cx + size * 0.25, base)], fill=(255, 220, 130, 255))


def rays(img, cx, cy, length, color, n=9, spread=70, a=70, seed=0):
    """Soft god-rays falling from (cx, cy)."""
    g = layer(*(v / S for v in img.size))
    d = ImageDraw.Draw(g)
    r = random.Random(seed)
    for i in range(n):
        ang = math.radians(90 + (i - (n - 1) / 2) * spread / n + r.uniform(-3, 3))
        w = r.uniform(10, 26)
        ex, ey = cx + math.cos(ang) * length, cy + math.sin(ang) * length
        nx, ny = -math.sin(ang) * w, math.cos(ang) * w
        d.polygon([P(cx, cy), P(ex + nx, ey + ny), P(ex - nx, ey - ny)], fill=alpha(color, r.randint(a // 2, a)))
    img.alpha_composite(blur(g, 6))


def grass_tufts(d, w, base, color, n, seed, h0=10, h1=26):
    r = random.Random(seed)
    for _ in range(n):
        x = r.uniform(0, w)
        y = base + r.uniform(-4, 30)
        for k in range(3):
            hh = r.uniform(h0, h1)
            d.line(P(x + k * 3, y, x + k * 3 + r.uniform(-6, 6), y - hh), fill=color, width=max(1, round(1.4 * S)))
