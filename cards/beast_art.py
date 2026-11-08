"""
Painted creatures for the fight screen: shaded shapes instead of flat silhouettes.

Every part (body, head, legs, horns...) is drawn as a mask and painted: a gradient fill, a shadow on the edges
away from the light (top left), a highlight on the edges facing it, and a dark outline. Details go on top: eyes
with slit pupils and a highlight, fangs, stripes, scales, whiskers.

painted(body, element, size) -> RGBA image at S× (transparent background), or None when the body type has no
painting yet (the fight card then uses the silhouette from cards/battle.py).
"""
import math
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import theme as T
from .theme import S, alpha, mix

# Element tints: the beast's colours lean toward its element
ELEMENT_TINT = {"Blood": (214, 70, 52), "Frost": (130, 190, 240), "Flame": (246, 140, 50), "Shadow": (150, 100, 220),
                "Thunder": (236, 210, 90), "Venom": (130, 210, 80), "Earth": (196, 150, 90), "Jade": (70, 200, 160)}


class _Pen:
    """ImageDraw for a part's mask: every shape is filled (255) unless told otherwise."""

    def __init__(self, d):
        self.d = d

    def __getattr__(self, name):
        fn = getattr(self.d, name)

        def call(*a, **k):
            k.setdefault("fill", 255)
            return fn(*a, **k)
        return call


class Painter:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    def X(self, x):
        return x * self.w

    def Y(self, y):
        return y * self.h

    def pts(self, pts):
        return [(self.X(x), self.Y(y)) for x, y in pts]

    def mask(self):
        return Image.new("L", (self.w, self.h), 0)

    def paint(self, mask, base, shade=0.5, light=0.25, outline=True, gloss=False):
        """Fill `mask` with a shaded `base` colour."""
        w, h = self.w, self.h
        box = mask.getbbox()
        if not box:
            return
        top, bottom = box[1], box[3]
        fill = T.vgradient((w, h), mix(base, (255, 255, 255), light * 0.6), mix(base, (0, 0, 0), shade * 0.7),
                           top, bottom)
        fill.putalpha(mask)
        self.img.alpha_composite(fill)
        k = max(2, round(min(w, h) * 0.022))
        # shadow on the bottom-right edges, highlight on the top-left edges
        sh = ImageChops.multiply(mask, ImageChops.invert(ImageChops.offset(mask, -k, -k)))
        sh = ImageChops.multiply(sh.filter(ImageFilter.GaussianBlur(k * 0.9)), mask)
        dark = Image.new("RGBA", (w, h), mix(base, (0, 0, 0), 0.75) + (0,))
        dark.putalpha(sh.point(lambda v: round(v * shade)))
        self.img.alpha_composite(dark)
        hl = ImageChops.multiply(mask, ImageChops.invert(ImageChops.offset(mask, k, k)))
        hl = ImageChops.multiply(hl.filter(ImageFilter.GaussianBlur(k * 0.7)), mask)
        lit = Image.new("RGBA", (w, h), mix(base, (255, 255, 255), 0.65) + (0,))
        lit.putalpha(hl.point(lambda v: round(v * light)))
        self.img.alpha_composite(lit)
        if gloss:
            g = mask.filter(ImageFilter.MinFilter(max(3, k * 2 + 1) | 1))
            sp = Image.new("RGBA", (w, h), (255, 255, 255, 0))
            sp.putalpha(ImageChops.multiply(g, ImageChops.invert(ImageChops.offset(g, round(k * 1.5), round(k * 1.5))))
                        .filter(ImageFilter.GaussianBlur(k)).point(lambda v: round(v * 0.35)))
            self.img.alpha_composite(sp)
        if outline:
            edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(3)))
            ol = Image.new("RGBA", (w, h), mix(base, (0, 0, 0), 0.82) + (0,))
            ol.putalpha(edge.point(lambda v: min(255, v * 2)))
            self.img.alpha_composite(ol)

    def part(self, base, draw, **kw):
        m = self.mask()
        draw(_Pen(ImageDraw.Draw(m)))
        self.paint(m, base, **kw)
        return m

    def clip(self, mask, draw_fn):
        """Draw details (stripes, scales) only inside `mask`."""
        layer = Image.new("RGBA", (self.w, self.h), (0, 0, 0, 0))
        draw_fn(ImageDraw.Draw(layer))
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
        self.img.alpha_composite(layer)

    def glow(self, mask, color, blur, strength=1.0):
        g = Image.new("RGBA", (self.w, self.h), color + (0,))
        g.putalpha(mask.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: min(255, round(v * strength))))
        self.img.alpha_composite(g)

    def eye(self, cx, cy, rx, ry, iris, angle=0, slit=True):
        """A fierce almond eye: glowing iris, slit pupil, a white highlight; tilted by `angle` degrees."""
        w, h = self.w, self.h
        size = round(max(rx, ry) * 2.6 * w)
        e = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        m = Image.new("L", (size, size), 0)
        md = ImageDraw.Draw(m)
        c = size / 2
        ax, ay = rx * w, ry * w
        md.polygon([(c - ax, c), (c - ax * 0.4, c - ay), (c + ax * 0.5, c - ay * 0.9), (c + ax, c - ay * 0.1),
                    (c + ax * 0.4, c + ay * 0.8), (c - ax * 0.5, c + ay * 0.75)], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(0.8 * S))
        g = Image.radial_gradient("L").resize((size, size))
        col = Image.composite(Image.new("RGBA", (size, size), mix(iris, (0, 0, 0), 0.35) + (255,)),
                              Image.new("RGBA", (size, size), mix(iris, (255, 255, 240), 0.55) + (255,)),
                              g.point(lambda v: min(255, v * 1.6)))
        col.putalpha(m)
        e.alpha_composite(col)
        d = ImageDraw.Draw(e)
        if slit:
            d.ellipse((c - ax * 0.12, c - ay * 0.85, c + ax * 0.12, c + ay * 0.75), fill=(12, 6, 6, 255))
        else:
            d.ellipse((c - ay * 0.45, c - ay * 0.45, c + ay * 0.45, c + ay * 0.45), fill=(12, 6, 6, 255))
        d.ellipse((c - ax * 0.42, c - ay * 0.62, c - ax * 0.18, c - ay * 0.3), fill=(255, 255, 255, 230))
        edge = ImageChops.subtract(m, m.filter(ImageFilter.MinFilter(3)))
        ol = Image.new("RGBA", (size, size), (10, 6, 6, 0))
        ol.putalpha(edge.point(lambda v: min(255, v * 3)))
        e.alpha_composite(ol)
        if angle:
            e = e.rotate(angle, resample=Image.BICUBIC)
        glow = Image.new("RGBA", (w, h), iris + (0,))
        gm = Image.new("L", (w, h), 0)
        ImageDraw.Draw(gm).ellipse((cx * w - ax * 1.6, cy * h - ay * 1.6, cx * w + ax * 1.6, cy * h + ay * 1.6), fill=200)
        glow.putalpha(gm.filter(ImageFilter.GaussianBlur(ax * 0.9)))
        self.img.alpha_composite(glow)
        self.img.alpha_composite(e, (round(cx * w - size / 2), round(cy * h - size / 2)))

    def fang(self, x, y, wdt, length, color=(246, 240, 226)):
        m = self.mask()
        ImageDraw.Draw(m).polygon(self.pts([(x - wdt, y), (x + wdt, y), (x + wdt * 0.15, y + length)]), fill=255)
        self.paint(m, color, shade=0.35, light=0.4)


# ── Tiger (cat bodies) ────────────────────────────────────────────────

def _cat(p, el):
    fur = mix((226, 128, 50), ELEMENT_TINT.get(el, (226, 128, 50)), 0.3)
    cream = (246, 236, 218)
    ink = (28, 16, 12)
    eye = mix((250, 220, 80), ELEMENT_TINT.get(el, (250, 220, 80)), 0.35)
    # body and shoulders
    body = p.part(fur, lambda d: d.ellipse(p.pts([(0.12, 0.5), (0.88, 1.22)])[0] + p.pts([(0.88, 1.22)])[0]),
                  shade=0.65)
    p.clip(body, lambda d: [d.line(p.pts([(0.5 + s * a, 0.58 + a * 0.4), (0.5 + s * (a + 0.12), 0.66 + a * 0.6),
                                          (0.5 + s * (a + 0.1), 0.78 + a * 0.5)]), fill=ink + (230,),
                                   width=round(p.w * 0.014), joint="curve")
                            for s in (-1, 1) for a in (0.16, 0.24, 0.31)])
    p.part(cream, lambda d: d.ellipse(p.pts([(0.36, 0.62), (0.64, 1.1)])[0] + p.pts([(0.64, 1.1)])[0]), shade=0.4,
           outline=False)
    # front legs and paws
    for s in (-1, 1):
        leg = p.part(fur, lambda d, s=s: d.rounded_rectangle(
            (p.X(0.5 + s * 0.17 - 0.07), p.Y(0.68), p.X(0.5 + s * 0.17 + 0.07), p.Y(1.02)), radius=round(p.w * 0.05)),
            shade=0.6)
        p.clip(leg, lambda d, s=s: [d.line(p.pts([(0.5 + s * 0.17 - 0.07, y), (0.5 + s * 0.17 + 0.02, y + 0.03)]),
                                           fill=ink + (220,), width=round(p.w * 0.012)) for y in (0.76, 0.84)])
        p.part(cream, lambda d, s=s: d.ellipse((p.X(0.5 + s * 0.17 - 0.095), p.Y(0.93), p.X(0.5 + s * 0.17 + 0.095),
                                                p.Y(1.05))), shade=0.45)
        for c in (-0.05, 0, 0.05):
            p.fang(0.5 + s * 0.17 + c, 1.0, 0.008, 0.03, (236, 230, 220))
    # cheek ruffs behind the head
    for s in (-1, 1):
        p.part(cream, lambda d, s=s: d.polygon(p.pts([(0.5 + s * 0.12, 0.34), (0.5 + s * 0.27, 0.42),
                                                       (0.5 + s * 0.23, 0.47), (0.5 + s * 0.29, 0.52),
                                                       (0.5 + s * 0.2, 0.58), (0.5 + s * 0.22, 0.63),
                                                       (0.5 + s * 0.1, 0.62)])), shade=0.45)
    # ears
    for s in (-1, 1):
        p.part(fur, lambda d, s=s: d.polygon(p.pts([(0.5 + s * 0.08, 0.16), (0.5 + s * 0.19, 0.03),
                                                     (0.5 + s * 0.215, 0.2)])), shade=0.6)
        p.part((70, 30, 26), lambda d, s=s: d.polygon(p.pts([(0.5 + s * 0.12, 0.15), (0.5 + s * 0.185, 0.07),
                                                              (0.5 + s * 0.195, 0.17)])), shade=0.3, outline=False)
    # head
    head = p.part(fur, lambda d: d.polygon(p.pts([(0.5, 0.08), (0.62, 0.11), (0.71, 0.22), (0.73, 0.36), (0.68, 0.5),
                                                   (0.6, 0.6), (0.5, 0.63), (0.4, 0.6), (0.32, 0.5), (0.27, 0.36),
                                                   (0.29, 0.22), (0.38, 0.11)])), shade=0.55, light=0.35)
    def head_stripes(d):
        w = round(p.w * 0.012)
        for s in (-1, 1):
            for k in range(3):
                y = 0.3 + k * 0.06
                d.polygon(p.pts([(0.5 + s * 0.24, y), (0.5 + s * 0.15, y + 0.025), (0.5 + s * 0.24, y + 0.035)]),
                          fill=ink + (235,))
            d.line(p.pts([(0.5 + s * 0.03, 0.12), (0.5 + s * 0.06, 0.2)]), fill=ink + (235,), width=w)
            d.line(p.pts([(0.5 + s * 0.09, 0.13), (0.5 + s * 0.12, 0.21)]), fill=ink + (235,), width=w)
        d.line(p.pts([(0.5, 0.1), (0.5, 0.2)]), fill=ink + (235,), width=w)
    p.clip(head, head_stripes)
    # muzzle and snarl
    p.part(cream, lambda d: d.ellipse(p.pts([(0.39, 0.41)])[0] + p.pts([(0.61, 0.6)])[0]), shade=0.35)
    p.part((24, 8, 10), lambda d: d.ellipse(p.pts([(0.44, 0.5)])[0] + p.pts([(0.56, 0.59)])[0]), shade=0.2,
           outline=False)
    p.part((176, 56, 60), lambda d: d.ellipse(p.pts([(0.465, 0.55)])[0] + p.pts([(0.535, 0.59)])[0]), shade=0.2,
           outline=False)
    for s in (-1, 1):
        p.fang(0.5 + s * 0.035, 0.5, 0.011, 0.055)
        p.fang(0.5 + s * 0.03, 0.59, 0.008, -0.035)
    p.part((60, 26, 24), lambda d: d.polygon(p.pts([(0.47, 0.43), (0.53, 0.43), (0.5, 0.48)])), shade=0.2)
    # angry brows and eyes
    for s in (-1, 1):
        p.part(ink, lambda d, s=s: d.polygon(p.pts([(0.5 + s * 0.03, 0.3), (0.5 + s * 0.16, 0.27),
                                                     (0.5 + s * 0.14, 0.305)])), shade=0.1, outline=False)
        p.eye(0.5 + s * 0.095, 0.345, 0.045, 0.026, eye, angle=s * -12)
    # whiskers
    d = ImageDraw.Draw(p.img)
    for s in (-1, 1):
        for k in range(3):
            d.line(p.pts([(0.5 + s * 0.07, 0.5 + k * 0.015), (0.5 + s * 0.2, 0.47 + k * 0.03),
                          (0.5 + s * 0.3, 0.46 + k * 0.045)]), fill=(250, 246, 236, 200), width=max(1, round(S)),
                   joint="curve")


# ── Dragon ────────────────────────────────────────────────────────────

def _bezier(p0, p1, p2, p3, n=40):
    out = []
    for i in range(n + 1):
        t = i / n
        a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t ** 2, t ** 3
        out.append((a * p0[0] + b * p1[0] + c * p2[0] + e * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + e * p3[1]))
    return out


def _dragon(p, el):
    scale_c = mix((40, 150, 120), ELEMENT_TINT.get(el, (40, 150, 120)), 0.55)
    belly = (240, 214, 150)
    mane = mix((236, 90, 60), ELEMENT_TINT.get(el, (236, 90, 60)), 0.25)
    horn = (240, 226, 196)
    eye = (255, 210, 80)
    coil = [(0.14, 1.05), (0.1, 0.6), (0.36, 0.64), (0.45, 0.8), (0.55, 0.98), (0.86, 1.02), (0.88, 0.6),
            (0.76, 0.42)]
    path = _bezier(*coil[0:4]) + _bezier(coil[3], coil[4], coil[5], coil[6])[1:] + [(0.76, 0.42), (0.62, 0.42)]
    tube_w = round(p.w * 0.13)
    # body coils
    m = p.mask()
    ImageDraw.Draw(m).line(p.pts(path), fill=255, width=tube_w, joint="curve")
    for x, y in (path[0], path[-1]):
        ImageDraw.Draw(m).ellipse((p.X(x) - tube_w / 2, p.Y(y) - tube_w / 2, p.X(x) + tube_w / 2, p.Y(y) + tube_w / 2),
                                  fill=255)
    p.paint(m, scale_c, shade=0.7, light=0.3)
    def scales(d):
        step = p.w * 0.03
        for row in range(int(p.h / step) + 2):
            for col in range(int(p.w / step) + 2):
                x = col * step + (step / 2 if row % 2 else 0)
                y = row * step * 0.8
                d.arc((x - step * 0.6, y - step * 0.6, x + step * 0.6, y + step * 0.6), 20, 160,
                      fill=mix(scale_c, (0, 0, 0), 0.5) + (150,), width=max(1, round(S * 0.9)))
    p.clip(m, scales)
    bm = p.mask()
    ImageDraw.Draw(bm).line(p.pts([(x, y + 0.03) for x, y in path]), fill=255, width=round(tube_w * 0.32), joint="curve")
    bm = ImageChops.multiply(bm, m)
    p.paint(bm, belly, shade=0.35, outline=False)
    p.clip(bm, lambda d: [d.line((p.X(x) - tube_w * 0.2, p.Y(y + 0.03), p.X(x) + tube_w * 0.2, p.Y(y + 0.03)),
                                 fill=(170, 130, 70, 200), width=max(1, S)) for x, y in path[::3]])
    # dorsal spikes along the coils
    for i in range(2, len(path) - 4, 4):
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        ang = math.atan2(y1 - y0, x1 - x0) - math.pi / 2
        ox, oy = math.cos(ang) * 0.06, math.sin(ang) * 0.06 * p.w / p.h
        p.part(mane, lambda d, x0=x0, y0=y0, ox=ox, oy=oy: d.polygon(p.pts(
            [(x0 - 0.015, y0), (x0 + ox, y0 + oy), (x0 + 0.02, y0 + 0.01)])), shade=0.5)
    # claw reaching forward
    p.part(scale_c, lambda d: d.line(p.pts([(0.3, 0.7), (0.24, 0.82), (0.3, 0.9)]), fill=255, width=round(p.w * 0.05),
                                     joint="curve"), shade=0.6)
    for k in range(3):
        p.fang(0.28 + k * 0.025, 0.9, 0.008, 0.045, horn)
    # mane behind the head
    flames = []
    for k in range(9):
        a = math.radians(-160 + k * 17)
        flames.append((0.5 + math.cos(a) * 0.22, 0.3 + math.sin(a) * 0.24 * 1.1))
    p.part(mane, lambda d: [d.polygon(p.pts([(0.5, 0.32), (fx - 0.04, fy + 0.04), (fx, fy), (fx + 0.03, fy + 0.06)]))
                            for fx, fy in flames], shade=0.55, light=0.35)
    # horns (antlers)
    for s in (-1, 1):
        p.part(horn, lambda d, s=s: d.line(p.pts([(0.5 + s * 0.06, 0.2), (0.5 + s * 0.12, 0.06), (0.5 + s * 0.2, -0.02)]),
                                           fill=255, width=round(p.w * 0.022), joint="curve"), shade=0.5, light=0.4)
        p.part(horn, lambda d, s=s: d.line(p.pts([(0.5 + s * 0.11, 0.09), (0.5 + s * 0.17, 0.08)]), fill=255,
                                           width=round(p.w * 0.014)), shade=0.5)
    # head: skull and long snout
    head = p.part(scale_c, lambda d: d.polygon(p.pts([(0.38, 0.22), (0.44, 0.13), (0.56, 0.13), (0.62, 0.22),
                                                       (0.63, 0.34), (0.6, 0.46), (0.57, 0.55), (0.43, 0.55),
                                                       (0.4, 0.46), (0.37, 0.34)])), shade=0.6, light=0.4, gloss=True)
    p.clip(head, lambda d: [d.arc((p.X(0.5 + c) - p.w * 0.02, p.Y(y) - p.w * 0.02, p.X(0.5 + c) + p.w * 0.02,
                                   p.Y(y) + p.w * 0.02), 20, 160, fill=mix(scale_c, (0, 0, 0), 0.45) + (170,),
                                  width=max(1, S)) for c in (-0.05, 0, 0.05) for y in (0.16, 0.2)])
    p.part(belly, lambda d: d.polygon(p.pts([(0.44, 0.44), (0.56, 0.44), (0.55, 0.53), (0.45, 0.53)])), shade=0.35)
    # open jaw with fangs
    p.part((40, 10, 14), lambda d: d.polygon(p.pts([(0.43, 0.53), (0.57, 0.53), (0.55, 0.62), (0.45, 0.62)])),
           shade=0.2, outline=False)
    p.part(scale_c, lambda d: d.polygon(p.pts([(0.42, 0.6), (0.58, 0.6), (0.55, 0.67), (0.45, 0.67)])), shade=0.6)
    for s in (-1, 1):
        p.fang(0.5 + s * 0.045, 0.53, 0.01, 0.05)
        p.fang(0.5 + s * 0.04, 0.61, 0.008, -0.035)
    # nostrils and brows
    for s in (-1, 1):
        p.part((20, 30, 26), lambda d, s=s: d.ellipse(p.pts([(0.5 + s * 0.03 - 0.008, 0.45)])[0] +
                                                         p.pts([(0.5 + s * 0.03 + 0.008, 0.47)])[0]), shade=0.1,
               outline=False)
        p.part(horn, lambda d, s=s: d.polygon(p.pts([(0.5 + s * 0.02, 0.24), (0.5 + s * 0.15, 0.2),
                                                      (0.5 + s * 0.12, 0.26)])), shade=0.45)
        p.eye(0.5 + s * 0.075, 0.285, 0.04, 0.024, eye, angle=s * -14)
    # whiskers
    d = ImageDraw.Draw(p.img)
    for s in (-1, 1):
        d.line(p.pts(_bezier((0.5 + s * 0.05, 0.47), (0.5 + s * 0.2, 0.46), (0.5 + s * 0.24, 0.62),
                             (0.5 + s * 0.36, 0.58))), fill=horn + (230,), width=round(2.2 * S), joint="curve")


# ── The Master (spar and practice) ────────────────────────────────────

def _master(p, el):
    robe = (226, 222, 210)
    sash = (60, 70, 96)
    trim = (176, 60, 52)
    skin = (226, 186, 150)
    beard = (240, 238, 232)
    # robe body with wide sleeves crossed over the chest
    body = p.part(robe, lambda d: d.polygon(p.pts([(0.24, 1.08), (0.3, 0.66), (0.4, 0.55), (0.6, 0.55), (0.7, 0.66),
                                                   (0.76, 1.08)])), shade=0.55, light=0.3)
    p.clip(body, lambda d: [d.line(p.pts([(0.5 + s * 0.02, 0.56), (0.5 - s * 0.08, 0.9)]), fill=trim + (255,),
                                   width=round(p.w * 0.018)) for s in (-1, 1)])
    p.part(sash, lambda d: d.rectangle((p.X(0.32), p.Y(0.84), p.X(0.68), p.Y(0.9))), shade=0.4)
    for s in (-1, 1):
        sl = p.part(robe, lambda d, s=s: d.polygon(p.pts([(0.5 + s * 0.17, 0.62), (0.5 + s * 0.27, 0.7),
                                                          (0.5 + s * 0.24, 0.82), (0.5 - s * 0.02, 0.8),
                                                          (0.5 - s * 0.04, 0.74), (0.5 + s * 0.08, 0.7)])),
                    shade=0.5, light=0.35)
        p.clip(sl, lambda d, s=s: d.line(p.pts([(0.5 + s * 0.27, 0.7), (0.5 + s * 0.24, 0.82)]), fill=trim + (255,),
                                         width=round(p.w * 0.014)))
    # neck and head
    p.part(skin, lambda d: d.rectangle((p.X(0.47), p.Y(0.46), p.X(0.53), p.Y(0.57))), shade=0.5)
    head = p.part(skin, lambda d: d.ellipse(p.pts([(0.425, 0.24)])[0] + p.pts([(0.575, 0.5)])[0]), shade=0.5,
                  light=0.3)
    # hair, topknot and pin
    p.clip(head, lambda d: d.chord(p.pts([(0.42, 0.22)])[0] + p.pts([(0.58, 0.4)])[0], 180, 360,
                                   fill=(40, 38, 40, 255)))
    p.part((40, 38, 40), lambda d: d.ellipse(p.pts([(0.475, 0.15)])[0] + p.pts([(0.525, 0.24)])[0]), shade=0.4)
    p.part((216, 180, 90), lambda d: d.line(p.pts([(0.44, 0.19), (0.56, 0.19)]), fill=255, width=round(p.w * 0.008)),
           shade=0.3)
    # brows, calm narrowed eyes, long beard and moustache
    for s in (-1, 1):
        p.part(beard, lambda d, s=s: d.polygon(p.pts([(0.5 + s * 0.012, 0.33), (0.5 + s * 0.07, 0.32),
                                                       (0.5 + s * 0.1, 0.36), (0.5 + s * 0.06, 0.345)])), shade=0.3)
        p.eye(0.5 + s * 0.035, 0.365, 0.02, 0.008, (120, 200, 255), slit=False)
    p.part(beard, lambda d: d.polygon(p.pts([(0.45, 0.43), (0.55, 0.43), (0.56, 0.52), (0.52, 0.7), (0.5, 0.74),
                                             (0.48, 0.7), (0.44, 0.52)])), shade=0.4, light=0.3)
    for s in (-1, 1):
        p.part(beard, lambda d, s=s: d.line(p.pts([(0.5, 0.425), (0.5 + s * 0.05, 0.44), (0.5 + s * 0.08, 0.5)]),
                                            fill=255, width=round(p.w * 0.01), joint="curve"), shade=0.3)


PAINTERS = {"cat": _cat, "dragon": _dragon, "master": _master}


@lru_cache(maxsize=24)
def painted(body, element, w, h):
    """The painted creature as an RGBA image w×h (pixels), or None if this body type isn't painted yet."""
    fn = PAINTERS.get(body)
    if not fn:
        return None
    p = Painter(w, h)
    fn(p, element)
    return p.img


__all__ = ["painted", "PAINTERS", "alpha"]
