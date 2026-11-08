"""
Painted creatures for the fight screen, drawn like an illustrator would: smooth curves, tapered brush strokes,
round light and a little paper grain, instead of flat silhouettes or straight-edged shapes.

Tools (Painter):
  curve(points)      a smooth closed shape through the points (Catmull-Rom spline)
  stroke(points, w)  a tapered brush stroke along a smooth path (thick in the middle, thin at the ends)
  paint(mask, color) fills a shape with round light from the top left, shade on the far side, a soft inked
                     edge and grain
painted(body, element, w, h) -> RGBA image (transparent background), or None when the body type has no
painting yet (the fight card then uses the silhouette from cards/battle.py). Designs: "cat" (a prowling tiger),
"dragon" (a coiling serpent dragon) and "master" (the seated elder of /spar and /practice).
"""
import math
import os
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import theme as T
from .theme import mix

ELEMENT_TINT = {"Blood": (214, 70, 52), "Frost": (130, 190, 240), "Flame": (246, 140, 50), "Shadow": (150, 100, 220),
                "Thunder": (236, 210, 90), "Venom": (130, 210, 80), "Earth": (196, 150, 90), "Jade": (60, 196, 160)}


# ── Geometry ──────────────────────────────────────────────────────────

def spline(pts, closed=True, n=14):
    """Catmull-Rom curve through `pts`."""
    if len(pts) < 3:
        return list(pts)
    P = list(pts)
    out = []
    count = len(P) if closed else len(P) - 1
    for i in range(count):
        p0 = P[i - 1] if (closed or i > 0) else P[0]
        p1, p2 = P[i], P[(i + 1) % len(P)]
        p3 = P[(i + 2) % len(P)] if (closed or i + 2 < len(P)) else P[-1]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not closed:
        out.append(P[-1])
    return out


def taper(path, w0, w1=None, mid=None):
    """Outline of a brush stroke along `path` (pixel points): width w0 at the start, w1 at the end, `mid` in
    the middle (a belly), as a closed polygon."""
    w1 = w0 * 0.1 if w1 is None else w1
    mid = max(w0, w1) if mid is None else mid
    n = len(path)
    left, right = [], []
    for i, (x, y) in enumerate(path):
        a = path[max(0, i - 1)]
        b = path[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1
        nx, ny = -dy / ln, dx / ln
        t = i / max(1, n - 1)
        w = (w0 * (1 - t) + w1 * t) if mid is None else (
            w0 + (mid - w0) * (t / 0.5) if t < 0.5 else mid + (w1 - mid) * ((t - 0.5) / 0.5))
        w = w * (0.8 + 0.2 * math.sin(math.pi * t)) / 2
        left.append((x + nx * w, y + ny * w))
        right.append((x - nx * w, y - ny * w))
    return left + right[::-1]


class Painter:
    def __init__(self, w, h, seed=1):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        self.rng = random.Random(seed)
        g = Image.effect_noise((w // 3 + 1, h // 3 + 1), 40).resize((w, h), Image.BILINEAR)
        self.grain = g

    def U(self, pts):
        return [(x * self.w, y * self.h) for x, y in pts]

    def mask(self):
        return Image.new("L", (self.w, self.h), 0)

    def curve_mask(self, pts, n=14):
        m = self.mask()
        ImageDraw.Draw(m).polygon(spline(self.U(pts), n=n), fill=255)
        return m.filter(ImageFilter.GaussianBlur(0.6))

    def stroke_mask(self, pts, w0, w1=None, mid=None):
        path = spline(self.U(pts), closed=False, n=16)
        m = self.mask()
        ImageDraw.Draw(m).polygon(taper(path, w0 * self.w, None if w1 is None else w1 * self.w,
                                        None if mid is None else mid * self.w), fill=255)
        return m.filter(ImageFilter.GaussianBlur(0.6))

    def paint(self, mask, base, light=(0.3, 0.15), shade=0.55, gloss=0.0, ink=0.7, grain=0.05):
        """Round light from `light` (unit position inside the shape's box), shade away from it, a soft inked edge."""
        box = mask.getbbox()
        if not box:
            return
        bx0, by0, bx1, by1 = box
        bw, bh = bx1 - bx0, by1 - by0
        size = max(bw, bh) * 2
        g = Image.radial_gradient("L").resize((size, size))
        lx, ly = bx0 + bw * light[0], by0 + bh * light[1]
        gl = Image.new("L", (self.w, self.h), 255)
        gl.paste(g, (round(lx - size / 2), round(ly - size / 2)))
        hi, lo = mix(base, (255, 248, 236), 0.28), mix(base, (8, 6, 12), shade)
        fill = Image.composite(Image.new("RGBA", (self.w, self.h), lo + (255,)),
                               Image.new("RGBA", (self.w, self.h), hi + (255,)), gl)
        if grain:
            gr = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
            gr.putalpha(ImageChops.invert(self.grain).point(lambda v: round(v * grain)))
            fill.alpha_composite(gr)
        fill.putalpha(mask)
        self.img.alpha_composite(fill)
        k = max(2, round(min(self.w, self.h) * 0.016))
        # occlusion along the far edges, a soft rim of light on the near ones
        sh = ImageChops.multiply(mask, ImageChops.invert(ImageChops.offset(mask, -k, -k)))
        sh = ImageChops.multiply(sh.filter(ImageFilter.GaussianBlur(k * 1.4)), mask)
        dark = Image.new("RGBA", (self.w, self.h), mix(base, (0, 0, 0), 0.8) + (0,))
        dark.putalpha(sh.point(lambda v: round(v * 0.55)))
        self.img.alpha_composite(dark)
        hl = ImageChops.multiply(mask, ImageChops.invert(ImageChops.offset(mask, k // 2 + 1, k // 2 + 1)))
        hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(k * 0.6)), mask)
        lit = Image.new("RGBA", (self.w, self.h), mix(base, (255, 255, 255), 0.6) + (0,))
        lit.putalpha(hl.point(lambda v: round(v * 0.3)))
        self.img.alpha_composite(lit)
        if gloss:
            core = mask.filter(ImageFilter.MinFilter(max(3, (k * 3) | 1)))
            sp = ImageChops.multiply(core, ImageChops.invert(ImageChops.offset(core, k * 2, k * 2)))
            s = Image.new("RGBA", (self.w, self.h), (255, 255, 255, 0))
            s.putalpha(sp.filter(ImageFilter.GaussianBlur(k * 1.2)).point(lambda v: round(v * gloss)))
            self.img.alpha_composite(s)
        if ink:
            edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(5)))
            heavy = ImageChops.multiply(edge, ImageChops.invert(ImageChops.offset(mask, -k, -k)).point(
                lambda v: 120 + v // 2))
            ol = Image.new("RGBA", (self.w, self.h), mix(base, (6, 4, 8), 0.85) + (0,))
            ol.putalpha(heavy.filter(ImageFilter.GaussianBlur(0.7)).point(lambda v: min(255, round(v * ink * 1.6))))
            self.img.alpha_composite(ol)

    def shape(self, pts, base, **kw):
        m = self.curve_mask(pts)
        self.paint(m, base, **kw)
        return m

    def brush(self, pts, w0, base, w1=None, mid=None, **kw):
        m = self.stroke_mask(pts, w0, w1, mid)
        self.paint(m, base, **kw)
        return m

    def ink(self, pts, w0, color, w1=None, mid=None, alpha=235, clip=None):
        """A flat tapered ink stroke (stripes, hair, whiskers), optionally only inside `clip`."""
        m = self.stroke_mask(pts, w0, w1, mid)
        if clip is not None:
            m = ImageChops.multiply(m, clip)
        layer = Image.new("RGBA", (self.w, self.h), color + (0,))
        layer.putalpha(m.point(lambda v: round(v * alpha / 255)))
        self.img.alpha_composite(layer)

    def glow(self, mask, color, blur, strength=1.0):
        g = Image.new("RGBA", (self.w, self.h), color + (0,))
        g.putalpha(mask.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, round(v * strength))))
        self.img.alpha_composite(g)

    def eye(self, cx, cy, size, iris, tilt=0.0, slit=True, lid=None):
        """An almond eye drawn from curves: glowing iris, slit or round pupil, a white catchlight, a heavy upper lid."""
        w = size
        pts = [(cx - w, cy + w * 0.05 + tilt), (cx - w * 0.3, cy - w * 0.42 - tilt * 0.3),
               (cx + w * 0.55, cy - w * 0.38 - tilt), (cx + w, cy - w * 0.02 - tilt),
               (cx + w * 0.35, cy + w * 0.36), (cx - w * 0.45, cy + w * 0.34 + tilt * 0.4)]
        m = self.curve_mask(pts)
        self.glow(m, iris, self.w * 0.012, 1.4)
        box = m.getbbox()
        bw = box[2] - box[0]
        g = Image.radial_gradient("L").resize((bw * 2, bw * 2))
        gl = Image.new("L", (self.w, self.h), 255)
        gl.paste(g, (round((box[0] + box[2]) / 2 - bw), round((box[1] + box[3]) / 2 - bw)))
        col = Image.composite(Image.new("RGBA", (self.w, self.h), mix(iris, (0, 0, 0), 0.3) + (255,)),
                              Image.new("RGBA", (self.w, self.h), mix(iris, (255, 255, 230), 0.6) + (255,)),
                              gl.point(lambda v: min(255, v * 2)))
        col.putalpha(m)
        self.img.alpha_composite(col)
        d = ImageDraw.Draw(self.img)
        X, Y = cx * self.w, cy * self.h
        if slit:
            pm = self.curve_mask([(cx, cy - w * 0.36), (cx + w * 0.09, cy), (cx, cy + w * 0.32), (cx - w * 0.09, cy)])
        else:
            pm = self.curve_mask([(cx - w * 0.18, cy), (cx, cy - w * 0.2), (cx + w * 0.18, cy), (cx, cy + w * 0.2)])
        pupil = Image.new("RGBA", (self.w, self.h), (14, 6, 8, 255))
        pupil.putalpha(ImageChops.multiply(pm, m))
        self.img.alpha_composite(pupil)
        r = w * self.w * 0.11
        d.ellipse((X - w * self.w * 0.32 - r, Y - w * self.h * 0.16 - r, X - w * self.w * 0.32 + r,
                   Y - w * self.h * 0.16 + r), fill=(255, 255, 255, 235))
        self.ink([(cx - w * 1.05, cy + w * 0.02), (cx - w * 0.2, cy - w * 0.5 - tilt * 0.4), (cx + w * 1.05, cy - tilt)],
                 w * 0.16, lid or (20, 10, 10), w1=w * 0.05, mid=w * 0.2)

    def fang(self, x, y, w, length, color=(244, 238, 222)):
        self.brush([(x, y), (x + w * 0.2, y + length * 0.55), (x + w * 0.05, y + length)], w, color, w1=w * 0.08,
                   mid=w * 0.9, shade=0.4, ink=0.5)


# ── The tiger (cat bodies) ────────────────────────────────────────────

def _cat(p, el):
    tint = ELEMENT_TINT.get(el, (226, 128, 50))
    fur = mix((214, 112, 40), tint, 0.25)
    cream = (246, 236, 216)
    stripe = (26, 14, 12)
    iris = mix((255, 214, 70), tint, 0.25)
    # hind body: a low, long crouch going back to the right
    body = p.shape([(0.3, 0.62), (0.46, 0.5), (0.7, 0.5), (0.9, 0.6), (0.96, 0.82), (0.88, 0.98), (0.6, 1.0),
                    (0.36, 0.96)], fur, light=(0.25, 0.1), shade=0.62)
    for k, x in enumerate((0.5, 0.58, 0.66, 0.74, 0.82)):
        p.ink([(x, 0.5 + k * 0.01), (x + 0.025, 0.62), (x - 0.01, 0.74)], 0.02, stripe, w1=0.002, mid=0.024, clip=body)
    # tail sweeping up behind
    tail = p.brush([(0.9, 0.7), (0.99, 0.55), (0.95, 0.36), (0.88, 0.3)], 0.05, fur, w1=0.03, mid=0.045, shade=0.6)
    for t in (0.6, 0.48, 0.38):
        p.ink([(0.92, t), (0.99, t + 0.02)], 0.022, stripe, w1=0.004, clip=tail)
    # back leg
    haunch = p.shape([(0.66, 0.62), (0.8, 0.6), (0.88, 0.72), (0.86, 0.86), (0.8, 0.9), (0.68, 0.84)], fur,
                     light=(0.3, 0.15), shade=0.62)
    p.ink([(0.7, 0.66), (0.78, 0.7), (0.8, 0.8)], 0.02, stripe, w1=0.003, clip=haunch)
    p.brush([(0.8, 0.84), (0.82, 0.94), (0.8, 1.0)], 0.07, fur, w1=0.06, mid=0.07, shade=0.6)
    p.shape([(0.76, 0.97), (0.84, 0.96), (0.86, 1.02), (0.75, 1.02)], cream, shade=0.4)
    # front legs: one planted, one reaching forward with claws out
    for (x0, y0), (x1, y1), x2 in (((0.42, 0.66), (0.4, 0.86), 0.36), ((0.28, 0.66), (0.2, 0.84), 0.12)):
        leg = p.brush([(x0, y0), (x1, y1), (x2 + 0.02, 0.98)], 0.11, fur, w1=0.085, mid=0.1, shade=0.6)
        p.ink([(x0 - 0.04, y0 + 0.08), (x0, y0 + 0.1)], 0.018, stripe, w1=0.003, clip=leg)
        p.ink([(x0 - 0.045, y0 + 0.15), (x0 - 0.005, y0 + 0.17)], 0.018, stripe, w1=0.003, clip=leg)
        p.shape([(x2 - 0.05, 0.96), (x2 + 0.01, 0.93), (x2 + 0.08, 0.95), (x2 + 0.09, 1.01), (x2 - 0.04, 1.02)], cream,
                shade=0.4)
        for c in (-0.03, 0.01, 0.05):
            p.fang(x2 + c, 1.0, 0.012, 0.035)
    # chest ruff
    p.shape([(0.26, 0.56), (0.36, 0.54), (0.44, 0.62), (0.42, 0.74), (0.34, 0.8), (0.27, 0.76), (0.24, 0.66)],
            cream, light=(0.3, 0.2), shade=0.42)
    # head, low and forward, with spiky cheek fur
    hc = (0.3, 0.42)
    spikes = []
    for i in range(22):
        a = math.radians(i * (360 / 22))
        rr = 0.16 if i % 2 else 0.2
        if 4 <= i <= 10:     # smoother on top of the skull
            rr = 0.165
        spikes.append((hc[0] + math.cos(a) * rr * 0.95, hc[1] + math.sin(a) * rr * 1.25))
    head = p.shape(spikes, fur, light=(0.3, 0.2), shade=0.58, gloss=0.1)
    # ears
    for s in (-1, 1):
        p.shape([(hc[0] + s * 0.07, 0.25), (hc[0] + s * 0.12, 0.12), (hc[0] + s * 0.16, 0.26)], fur, shade=0.6)
        p.shape([(hc[0] + s * 0.09, 0.24), (hc[0] + s * 0.12, 0.16), (hc[0] + s * 0.14, 0.25)], (70, 32, 30),
                shade=0.3, ink=0.2)
    # face stripes (tapered, like brush marks)
    for s in (-1, 1):
        for k in range(3):
            y = 0.36 + k * 0.055
            p.ink([(hc[0] + s * 0.19, y), (hc[0] + s * 0.13, y + 0.012), (hc[0] + s * 0.1, y + 0.03)], 0.02, stripe,
                  w1=0.002, clip=head)
        p.ink([(hc[0] + s * 0.02, 0.25), (hc[0] + s * 0.05, 0.31)], 0.012, stripe, w1=0.002, clip=head)
    p.ink([(hc[0], 0.24), (hc[0], 0.31)], 0.014, stripe, w1=0.002, clip=head)
    # muzzle, snarl, fangs, nose
    p.shape([(hc[0] - 0.085, 0.47), (hc[0] - 0.04, 0.43), (hc[0], 0.445), (hc[0] + 0.04, 0.43), (hc[0] + 0.085, 0.47),
             (hc[0] + 0.07, 0.56), (hc[0], 0.6), (hc[0] - 0.07, 0.56)], cream, shade=0.38)
    p.shape([(hc[0] - 0.055, 0.52), (hc[0], 0.5), (hc[0] + 0.055, 0.52), (hc[0] + 0.04, 0.575), (hc[0], 0.59),
             (hc[0] - 0.04, 0.575)], (36, 10, 12), shade=0.2, ink=0.3)
    p.shape([(hc[0] - 0.03, 0.56), (hc[0], 0.55), (hc[0] + 0.03, 0.56), (hc[0], 0.585)], (190, 70, 74), shade=0.3,
            ink=0.0)
    for s in (-1, 1):
        p.fang(hc[0] + s * 0.035, 0.505, 0.016, 0.05)
        p.fang(hc[0] + s * 0.028, 0.585, 0.012, -0.03)
    p.shape([(hc[0] - 0.025, 0.455), (hc[0] + 0.025, 0.455), (hc[0], 0.49)], (56, 26, 26), shade=0.3, ink=0.3)
    # brows and eyes
    for s in (-1, 1):
        p.ink([(hc[0] + s * 0.02, 0.37), (hc[0] + s * 0.08, 0.35), (hc[0] + s * 0.13, 0.36)], 0.02, stripe, w1=0.004)
        p.eye(hc[0] + s * 0.073, 0.395, 0.034, iris, tilt=-s * 0.006)
    # whiskers
    for s in (-1, 1):
        for k in range(3):
            p.ink([(hc[0] + s * 0.06, 0.51 + k * 0.012), (hc[0] + s * 0.16, 0.5 + k * 0.025),
                   (hc[0] + s * 0.25, 0.51 + k * 0.045)], 0.004, (250, 246, 236), w1=0.001, alpha=210)


# ── The serpent dragon ────────────────────────────────────────────────

def _dragon(p, el):
    tint = ELEMENT_TINT.get(el, (60, 150, 170))
    scale_c = mix((44, 110, 140), tint, 0.45)
    belly = (232, 214, 170)
    fin = mix(tint, (240, 250, 255), 0.35)
    horn = (236, 222, 190)
    iris = (255, 220, 90)
    spine = [(0.86, 0.98), (0.95, 0.78), (0.82, 0.62), (0.58, 0.7), (0.42, 0.88), (0.2, 0.86), (0.12, 0.66),
             (0.24, 0.5), (0.42, 0.46), (0.5, 0.36)]
    path = spline(p.U(spine), closed=False, n=18)
    # fins along the back, behind the body
    fins = p.mask()
    fd = ImageDraw.Draw(fins)
    for i in range(6, len(path) - 6, 7):
        (x0, y0), (x1, y1) = path[i - 1], path[i + 1]
        ang = math.atan2(y1 - y0, x1 - x0)
        nx, ny = math.cos(ang - math.pi / 2), math.sin(ang - math.pi / 2)
        bx, by = path[i]
        L = p.w * 0.11
        tip = (bx + nx * L - math.cos(ang) * L * 0.6, by + ny * L - math.sin(ang) * L * 0.6)
        fd.polygon(spline([(bx - math.cos(ang) * L * 0.4, by - math.sin(ang) * L * 0.4),
                           ((bx + tip[0]) / 2 + nx * L * 0.15, (by + tip[1]) / 2 + ny * L * 0.15), tip,
                           (bx + math.cos(ang) * L * 0.3, by + math.sin(ang) * L * 0.3)], n=8), fill=255)
    fins = fins.filter(ImageFilter.GaussianBlur(1))
    p.glow(fins, tint, p.w * 0.01, 0.9)
    p.paint(fins, fin, shade=0.45, ink=0.5, grain=0.03)
    # the body: one long tapered coil, thick at the shoulders, thin at the tail
    m = p.mask()
    ImageDraw.Draw(m).polygon(taper(path, p.w * 0.04, p.w * 0.17, p.w * 0.2), fill=255)
    body = m.filter(ImageFilter.GaussianBlur(0.8))
    p.paint(body, scale_c, light=(0.3, 0.1), shade=0.68, gloss=0.18)
    # scales: overlapping arcs, smaller toward the tail
    sc = Image.new("RGBA", (p.w, p.h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sc)
    for i, (x, y) in enumerate(path[::2]):
        r = p.w * (0.012 + 0.014 * i / (len(path) / 2))
        for dx in (-1.6, 0, 1.6):
            for dy in (-1.2, 0, 1.2):
                cx, cy = x + dx * r, y + dy * r
                sd.arc((cx - r, cy - r, cx + r, cy + r), 30, 150, fill=mix(scale_c, (0, 0, 0), 0.5) + (150,),
                       width=max(1, round(r * 0.18)))
    sc.putalpha(ImageChops.multiply(sc.getchannel("A"), body))
    p.img.alpha_composite(sc)
    # belly plates down the inside of the coil
    bp = [(x + 0, y + p.h * 0.05) for x, y in path]
    bm = p.mask()
    ImageDraw.Draw(bm).polygon(taper(bp, p.w * 0.014, p.w * 0.065, p.w * 0.08), fill=255)
    bm = ImageChops.multiply(bm.filter(ImageFilter.GaussianBlur(0.8)), body)
    p.paint(bm, belly, shade=0.4, ink=0.2)
    pl = Image.new("RGBA", (p.w, p.h), (0, 0, 0, 0))
    pd = ImageDraw.Draw(pl)
    for x, y in bp[::3]:
        pd.line((x - p.w * 0.025, y - p.h * 0.01, x + p.w * 0.025, y + p.h * 0.01), fill=(150, 116, 70, 200),
                width=max(1, round(p.w * 0.003)))
    pl.putalpha(ImageChops.multiply(pl.getchannel("A"), bm))
    p.img.alpha_composite(pl)
    # a clawed arm reaching out
    arm = p.brush([(0.3, 0.56), (0.2, 0.58), (0.13, 0.52)], 0.05, scale_c, w1=0.035, mid=0.05, shade=0.62)
    for k, a in enumerate((-0.6, -0.1, 0.4)):
        p.fang(0.12 + math.cos(a) * 0.01, 0.5 + k * 0.012, 0.012, -0.045, horn)
    del arm
    # head (facing left): mane, horns, skull, jaws
    hx, hy = 0.5, 0.26
    mane = p.mask()
    md = ImageDraw.Draw(mane)
    for k in range(9):
        a = math.radians(-30 + k * 22)
        base = p.U([(hx + 0.06, hy + 0.02)])[0]
        tip = p.U([(hx + 0.06 + math.cos(a) * 0.27, hy + 0.02 + math.sin(a) * 0.3)])[0]
        md.polygon(taper(spline([base, ((base[0] + tip[0]) / 2 - p.w * 0.03, (base[1] + tip[1]) / 2), tip],
                                closed=False, n=10), p.w * 0.09, p.w * 0.002), fill=255)
    p.glow(mane, tint, p.w * 0.012, 0.8)
    p.paint(mane, fin, shade=0.5, ink=0.5)
    for dx, dy, ln in ((0.0, -0.03, 0.26), (0.05, 0.02, 0.22)):
        p.brush([(hx + 0.02 + dx, hy + dy), (hx + 0.14 + dx, hy - 0.08 + dy), (hx + 0.12 + dx + ln * 0.5, hy - 0.22 + dy)],
                0.034, horn,
                w1=0.004, mid=0.025, shade=0.5, gloss=0.2)
    skull = p.shape([(hx - 0.2, hy + 0.06), (hx - 0.14, hy - 0.01), (hx - 0.04, hy - 0.05), (hx + 0.06, hy - 0.06),
                     (hx + 0.12, hy + 0.0), (hx + 0.1, hy + 0.08), (hx - 0.02, hy + 0.08), (hx - 0.16, hy + 0.1)],
                    scale_c, light=(0.3, 0.1), shade=0.6, gloss=0.25)
    p.ink([(hx - 0.13, hy + 0.0), (hx - 0.02, hy - 0.035), (hx + 0.08, hy - 0.03)], 0.01, mix(scale_c, (0, 0, 0), 0.6),
          w1=0.002, clip=skull)
    p.shape([(hx - 0.19, hy + 0.1), (hx - 0.05, hy + 0.11), (hx + 0.06, hy + 0.1), (hx + 0.02, hy + 0.15),
             (hx - 0.12, hy + 0.15)], (46, 12, 18), shade=0.2, ink=0.3)
    p.shape([(hx - 0.17, hy + 0.15), (hx - 0.04, hy + 0.14), (hx + 0.06, hy + 0.11), (hx + 0.04, hy + 0.17),
             (hx - 0.1, hy + 0.2)], scale_c, shade=0.62)
    for k in range(4):
        p.fang(hx - 0.17 + k * 0.045, hy + 0.085, 0.012, 0.04)
        p.fang(hx - 0.14 + k * 0.045, hy + 0.15, 0.01, -0.03)
    p.shape([(hx - 0.21, hy + 0.06), (hx - 0.185, hy + 0.04), (hx - 0.17, hy + 0.07)], (20, 24, 26), shade=0.2,
            ink=0.0)
    # brow ridge, eye, whiskers
    p.brush([(hx - 0.1, hy - 0.025), (hx - 0.03, hy - 0.05), (hx + 0.03, hy - 0.035)], 0.02, horn, w1=0.004, mid=0.02,
            shade=0.45)
    p.eye(hx - 0.045, hy - 0.005, 0.03, iris, tilt=0.006)
    for dy, sx in ((0.07, 0.36), (0.1, 0.3)):
        p.ink([(hx - 0.19, hy + dy), (hx - 0.3, hy + dy + 0.02), (hx - 0.36, hy + dy + 0.14), (hx - sx, hy + dy + 0.26)],
              0.008, horn, w1=0.001, mid=0.007, alpha=230)


# ── The elder (spar and practice) ─────────────────────────────────────

def _master(p, el):
    robe = (232, 230, 224)
    inner = (52, 76, 122)
    trim = (36, 34, 44)
    sash = (150, 46, 40)
    skin = (226, 188, 152)
    hair = (214, 210, 206)
    jade = (110, 200, 160)
    flame = (255, 150, 60)
    # long hair falling behind the shoulders
    for k in range(9):
        x = 0.36 + k * 0.035
        p.ink([(0.5, 0.2), (x, 0.4), (x - 0.04 + k * 0.012, 0.66)], 0.05, mix(hair, (60, 60, 70), 0.25),
              w1=0.006, mid=0.05, alpha=255)
    # seated robe: a wide flowing base
    base = p.shape([(0.12, 0.98), (0.2, 0.8), (0.34, 0.7), (0.66, 0.7), (0.82, 0.8), (0.9, 0.98), (0.7, 1.04),
                    (0.3, 1.04)], robe, light=(0.3, 0.1), shade=0.42)
    p.ink([(0.18, 0.96), (0.4, 0.86), (0.6, 0.86), (0.84, 0.96)], 0.03, trim, w1=0.02, mid=0.03, clip=base)
    p.shape([(0.34, 0.86), (0.5, 0.82), (0.66, 0.86), (0.62, 0.98), (0.38, 0.98)], inner, shade=0.5)
    # torso and crossed collar
    torso = p.shape([(0.36, 0.72), (0.4, 0.46), (0.5, 0.42), (0.6, 0.46), (0.64, 0.72), (0.5, 0.76)], robe,
                    light=(0.3, 0.1), shade=0.45)
    for s in (-1, 1):
        p.ink([(0.5 - s * 0.04, 0.44), (0.5 + s * 0.02, 0.56), (0.5 + s * 0.06, 0.7)], 0.026, trim, w1=0.02,
              clip=torso)
    p.shape([(0.47, 0.44), (0.53, 0.44), (0.51, 0.54), (0.49, 0.54)], inner, shade=0.4, ink=0.2)
    p.shape([(0.37, 0.64), (0.63, 0.64), (0.64, 0.7), (0.36, 0.7)], sash, shade=0.45)
    jd = p.shape([(0.47, 0.67), (0.5, 0.645), (0.53, 0.67), (0.5, 0.695)], jade, shade=0.35, gloss=0.35)
    p.glow(jd, jade, p.w * 0.01, 0.8)
    # sleeves: one resting on the knee, one raised with a qi flame above the palm
    p.brush([(0.38, 0.5), (0.28, 0.66), (0.3, 0.82)], 0.12, robe, w1=0.11, mid=0.13, shade=0.45)
    p.ink([(0.25, 0.8), (0.34, 0.84)], 0.02, trim, w1=0.018)
    for k in range(3):
        p.ink([(0.34 - k * 0.02, 0.56 + k * 0.03), (0.3 - k * 0.015, 0.66 + k * 0.03)], 0.008, (170, 166, 160),
              w1=0.001, alpha=200)
    p.shape([(0.28, 0.83), (0.33, 0.82), (0.35, 0.86), (0.3, 0.88)], skin, shade=0.45)
    p.brush([(0.62, 0.5), (0.72, 0.58), (0.74, 0.44)], 0.11, robe, w1=0.08, mid=0.11, shade=0.45)
    p.ink([(0.7, 0.47), (0.78, 0.45)], 0.02, trim, w1=0.018)
    for k in range(3):
        p.ink([(0.64 + k * 0.02, 0.53 + k * 0.01), (0.69 + k * 0.015, 0.58)], 0.008, (170, 166, 160), w1=0.001,
              alpha=200)
    for k in range(4):
        p.ink([(0.24 + k * 0.1, 0.84), (0.22 + k * 0.11, 0.98)], 0.008, (180, 176, 170), w1=0.001, alpha=160)
    p.shape([(0.73, 0.43), (0.76, 0.36), (0.79, 0.37), (0.78, 0.43)], skin, shade=0.42)
    fl = p.mask()
    ImageDraw.Draw(fl).polygon(spline(p.U([(0.765, 0.32), (0.75, 0.27), (0.765, 0.2), (0.78, 0.25), (0.79, 0.29)])),
                               fill=255)
    p.glow(fl, flame, p.w * 0.03, 2.0)
    p.glow(fl, (255, 230, 160), p.w * 0.008, 2.0)
    # head: face, eyebrows, closed eyes, beard, topknot and pin
    p.shape([(0.47, 0.42), (0.53, 0.42), (0.53, 0.46), (0.47, 0.46)], skin, shade=0.5, ink=0.2)
    face = p.shape([(0.455, 0.29), (0.5, 0.25), (0.545, 0.29), (0.55, 0.36), (0.53, 0.42), (0.5, 0.44), (0.47, 0.42),
                    (0.45, 0.36)], skin, light=(0.35, 0.2), shade=0.45)
    del face
    p.shape([(0.44, 0.3), (0.47, 0.22), (0.5, 0.2), (0.53, 0.22), (0.56, 0.3), (0.53, 0.26), (0.5, 0.25),
             (0.47, 0.26)], hair, shade=0.45)
    p.shape([(0.48, 0.2), (0.5, 0.15), (0.52, 0.2), (0.5, 0.215)], hair, shade=0.5)
    p.ink([(0.46, 0.18), (0.54, 0.17)], 0.008, (210, 170, 90), w1=0.008)
    for s in (-1, 1):
        p.ink([(0.5 + s * 0.008, 0.315), (0.5 + s * 0.04, 0.31), (0.5 + s * 0.075, 0.34)], 0.012, hair, w1=0.002)
        p.ink([(0.5 + s * 0.012, 0.335), (0.5 + s * 0.028, 0.34), (0.5 + s * 0.042, 0.335)], 0.005, (40, 28, 26),
              w1=0.002)
    for k in range(7):
        x = 0.475 + k * 0.008
        p.ink([(x, 0.39), (x + (k - 3) * 0.004, 0.48), (0.5 + (k - 3) * 0.006, 0.6)], 0.012, hair, w1=0.002, alpha=245)
    for s in (-1, 1):
        p.ink([(0.5, 0.385), (0.5 + s * 0.04, 0.395), (0.5 + s * 0.06, 0.45)], 0.01, hair, w1=0.002)
    # long hair flowing over both shoulders
    for s in (-1, 1):
        for k in range(6):
            p.ink([(0.5 + s * 0.04, 0.24), (0.5 + s * (0.075 + k * 0.01), 0.36),
                   (0.5 + s * (0.09 + k * 0.016), 0.5), (0.5 + s * (0.1 + k * 0.022), 0.66)],
                  0.016, mix(hair, (120, 116, 120), (k % 3) * 0.15), w1=0.002, mid=0.018, alpha=240)


PAINTERS = {"cat": _cat, "dragon": _dragon, "master": _master}


CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", ".painted")
VERSION = 2          # bump when a painting changes, so old saved copies are redrawn


@lru_cache(maxsize=24)
def painted(body, element, w, h):
    """The painted creature as an RGBA image w×h (pixels), or None if this body type isn't painted yet.
    A painting takes a few seconds, so each one is saved under art/.painted/ the first time it is drawn."""
    fn = PAINTERS.get(body)
    if not fn:
        return None
    path = os.path.join(CACHE_DIR, f"v{VERSION}_{body}_{element}_{w}x{h}.png")
    try:
        if os.path.exists(path):
            return Image.open(path).convert("RGBA")
    except Exception:
        pass
    p = Painter(w, h)
    fn(p, element)
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        p.img.save(path)
    except OSError:
        pass
    return p.img


_ = T
