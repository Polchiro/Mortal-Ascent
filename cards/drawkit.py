"""
A tiny drawing kit for the icon and emblem modules (cards/technique_icons.py, cards/emblems.py).

A Pen draws in "icon units": x and y run from -1 to 1 across the icon (y points down), and the pen
maps them to card pixels around a centre, with an optional offset, scale, rotation and mirror. So a
base shape (a fist, a palm) can be drawn once and reused smaller, tilted or flipped inside another icon.
Circles and rounded boxes are drawn as polygons, so rotation works for every shape. Pillow only.
"""
import math

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .theme import P, S, mix

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


class Pen:
    def __init__(self, d, cx, cy, s, ox=0.0, oy=0.0, k=1.0, rot=0.0, flip=False):
        self.d, self.cx, self.cy, self.s = d, cx, cy, s
        self.ox, self.oy, self.k, self.rot, self.flip = ox, oy, k, rot, flip

    # ── transforms ────────────────────────────────────────────────
    def sub(self, ox=0.0, oy=0.0, k=1.0, rot=0.0, flip=False):
        """A pen for a smaller copy: (ox, oy) is the copy's centre in this pen's units."""
        cx, cy = self.px(ox, oy)
        return Pen(self.d, cx, cy, self.s * self.k * k, rot=self.rot + (-rot if self.flip else rot),
                   flip=self.flip != flip)

    def px(self, x, y):
        """Icon units → card pixels."""
        if self.flip:
            x = -x
        x, y = x * self.k + self.ox, y * self.k + self.oy
        if self.rot:
            a = math.radians(self.rot)
            x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
        return self.cx + x * self.s, self.cy + y * self.s

    def w(self, u):
        """A line width in icon units → drawing pixels (at least 1)."""
        return max(1, round(u * self.s * self.k * S))

    @property
    def size(self):
        """Half the icon size in card pixels (what decides whether fine details are drawn)."""
        return self.s * self.k

    @property
    def big(self):
        return self.size >= 20

    # ── shapes ────────────────────────────────────────────────────
    def poly(self, pts, fill=None, outline=None, width=0.0):
        q = [P(*self.px(x, y)) for x, y in pts]
        if len(q) < 3:
            return
        if fill is not None:
            self.d.polygon(q, fill=fill)
        if outline is not None:
            self.d.line(q + [q[0]], fill=outline, width=self.w(width or 0.06), joint="curve")

    def line(self, pts, fill, width=0.08):
        q = [P(*self.px(x, y)) for x, y in pts]
        self.d.line(q, fill=fill, width=self.w(width), joint="curve")
        # round caps
        r = self.w(width) / 2
        if r >= 2:
            for x, y in (q[0], q[-1]):
                self.d.ellipse((x - r, y - r, x + r, y + r), fill=fill)

    def ellipse(self, x, y, rx, ry, fill=None, outline=None, width=0.0, n=32):
        pts = [(x + math.cos(2 * math.pi * i / n) * rx, y + math.sin(2 * math.pi * i / n) * ry) for i in range(n)]
        self.poly(pts, fill, outline, width)

    def circle(self, x, y, r, fill=None, outline=None, width=0.0):
        self.ellipse(x, y, r, r, fill, outline, width)

    def ring(self, x, y, r, fill, width):
        self.poly(arc_pts(x, y, r, 0, 360, 40), None, fill, width)

    def capsule(self, p0, p1, wd, fill, outline=None, width=0.0):
        """A rod with round ends from p0 to p1, wd wide."""
        self.poly(capsule_pts(p0, p1, wd), fill, outline, width)

    def rrect(self, x0, y0, x1, y1, r, fill=None, outline=None, width=0.0):
        self.poly(rrect_pts(x0, y0, x1, y1, r), fill, outline, width)

    def arc(self, x, y, r, a0, a1, fill, width=0.08, ry=None):
        self.line(arc_pts(x, y, r, a0, a1, ry=ry), fill, width)

    def crescent(self, x, y, r, fill, cut=0.55, shift=0.38, angle=-35):
        """A crescent moon: a disc of radius r minus a disc moved `shift`·r towards `angle` degrees."""
        self.poly(crescent_pts(x, y, r, r * (1 - cut * 0.25), r * shift, angle), fill)

    def star(self, x, y, n, r_out, r_in, fill=None, outline=None, width=0.0, turn=-90):
        pts = []
        for i in range(2 * n):
            r = r_out if i % 2 == 0 else r_in
            a = math.radians(turn + i * 180 / n)
            pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
        self.poly(pts, fill, outline, width)

    def ngon(self, x, y, n, r, fill=None, outline=None, width=0.0, turn=-90):
        pts = [(x + math.cos(math.radians(turn + i * 360 / n)) * r, y + math.sin(math.radians(turn + i * 360 / n)) * r)
               for i in range(n)]
        self.poly(pts, fill, outline, width)

    def bolt(self, x, y, k, fill, rot=0):
        """A lightning bolt, k tall-ish."""
        pts = [(0.15, -1), (-0.45, 0.12), (-0.02, 0.12), (-0.22, 1), (0.45, -0.18), (0.04, -0.18)]
        a = math.radians(rot)
        self.poly([(x + (px_ * math.cos(a) - py_ * math.sin(a)) * k, y + (px_ * math.sin(a) + py_ * math.cos(a)) * k)
                   for px_, py_ in pts], fill)

    def leaf(self, x, y, length, wd, angle, fill, vein=None):
        a = math.radians(angle)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        pts = []
        for i in range(11):
            t = i / 10
            w = math.sin(math.pi * t) * wd
            pts.append((x + ux * length * (t - 0.5) + nx * w, y + uy * length * (t - 0.5) + ny * w))
        for i in range(10, -1, -1):
            t = i / 10
            w = math.sin(math.pi * t) * wd
            pts.append((x + ux * length * (t - 0.5) - nx * w, y + uy * length * (t - 0.5) - ny * w))
        self.poly(pts, fill)
        if vein is not None:
            self.line([(x - ux * length * 0.45, y - uy * length * 0.45), (x + ux * length * 0.45, y + uy * length * 0.45)],
                      vein, 0.03)

    def wave(self, x0, x1, y, amp, fill, width=0.08, waves=2.0, phase=0.0):
        n = 24
        pts = [(x0 + (x1 - x0) * i / n, y + math.sin(phase + waves * 2 * math.pi * i / n) * amp) for i in range(n + 1)]
        self.line(pts, fill, width)

    def cloud(self, x, y, k, fill, shade=None):
        """A puffy cloud: a flat base with three bumps."""
        for bx, by, r in ((-0.55, 0.05, 0.38), (0.0, -0.2, 0.52), (0.55, 0.0, 0.42)):
            self.circle(x + bx * k, y + by * k, r * k, fill)
        self.rrect(x - 0.9 * k, y - 0.05 * k, x + 0.95 * k, y + 0.38 * k, 0.18 * k, fill)
        if shade is not None:
            self.line([(x - 0.75 * k, y + 0.3 * k), (x + 0.8 * k, y + 0.3 * k)], shade, 0.06 * k)

    def spiral(self, x, y, r, fill, width=0.07, turns=1.6):
        n = 40
        pts = []
        for i in range(n + 1):
            t = i / n
            a = t * turns * 2 * math.pi
            rr = r * (0.15 + 0.85 * t)
            pts.append((x + math.cos(a) * rr, y + math.sin(a) * rr))
        self.line(pts, fill, width)

    def sparkle(self, x, y, r, fill):
        """A four-point twinkle."""
        self.poly([(x, y - r), (x + r * 0.22, y - r * 0.22), (x + r, y), (x + r * 0.22, y + r * 0.22), (x, y + r),
                   (x - r * 0.22, y + r * 0.22), (x - r, y), (x - r * 0.22, y - r * 0.22)], fill)


# ── point lists ───────────────────────────────────────────────────────

def arc_pts(x, y, r, a0, a1, n=24, ry=None):
    ry = r if ry is None else ry
    return [(x + math.cos(math.radians(a0 + (a1 - a0) * i / n)) * r,
             y + math.sin(math.radians(a0 + (a1 - a0) * i / n)) * ry) for i in range(n + 1)]


def crescent_pts(x, y, r1, r2, dist, angle):
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    x2, y2 = x + ux * dist, y + uy * dist
    k = (r1 * r1 - r2 * r2 + dist * dist) / (2 * dist)
    h = math.sqrt(max(0.0, r1 * r1 - k * k))
    bx, by = x + ux * k, y + uy * k
    pa, pb = (bx - uy * h, by + ux * h), (bx + uy * h, by - ux * h)
    back = math.atan2(-uy, -ux)

    def sweep(cx, cy, rr, p0, p1, n=28):
        a0, a1 = math.atan2(p0[1] - cy, p0[0] - cx), math.atan2(p1[1] - cy, p1[0] - cx)
        # go the way that passes through `back` (the side facing away from the cut)
        d1 = (a1 - a0) % (2 * math.pi)
        db = (back - a0) % (2 * math.pi)
        span = d1 if db <= d1 else d1 - 2 * math.pi
        return [(cx + math.cos(a0 + span * i / n) * rr, cy + math.sin(a0 + span * i / n) * rr) for i in range(n + 1)]
    return sweep(x, y, r1, pa, pb) + sweep(x2, y2, r2, pb, pa)


def capsule_pts(p0, p1, wd):
    (x0, y0), (x1, y1) = p0, p1
    a = math.atan2(y1 - y0, x1 - x0)
    r = wd / 2
    pts = []
    for i in range(9):
        t = a + math.pi / 2 + math.pi * i / 8
        pts.append((x0 + math.cos(t) * r, y0 + math.sin(t) * r))
    for i in range(9):
        t = a - math.pi / 2 + math.pi * i / 8
        pts.append((x1 + math.cos(t) * r, y1 + math.sin(t) * r))
    return pts


def rrect_pts(x0, y0, x1, y1, r):
    r = min(r, (x1 - x0) / 2, (y1 - y0) / 2)
    pts = []
    for (cx, cy, a0) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        pts += arc_pts(cx, cy, r, a0, a0 + 90, 6)
    return pts


# ── image helpers ─────────────────────────────────────────────────────

def outline_of(img, draw_fn, center, size, color, thickness=1.6):
    """Draw only the outline of a silhouette: draw_fn(d, cx, cy, s, fill, dark) is drawn in white on a mask,
    the inside is eaten away, and the edge left over is painted in `color` (used for empty slots)."""
    cx, cy = center
    pad = size * 0.25
    x0, y0 = cx - size / 2 - pad, cy - size / 2 - pad
    w = round((size + 2 * pad) * S)
    mask = Image.new("L", (w, w), 0)
    md = ImageDraw.Draw(mask)
    draw_fn(md, size / 2 + pad, size / 2 + pad, size / 2, (255,), (255,))
    k = max(3, round(thickness * S)) | 1
    edge = ImageChops.subtract(mask, mask.filter(ImageFilter.MinFilter(k)))
    layer = Image.new("RGBA", (w, w), color[:3] + (0,))
    layer.putalpha(edge.point(lambda v: v * (color[3] if len(color) > 3 else 255) // 255))
    img.alpha_composite(layer, (round(x0 * S), round(y0 * S)))


def glow(img, center, r, color, strength=120, blur=None):
    """A soft round light behind an emblem."""
    from .theme import alpha, soft_glow
    cx, cy = center
    soft_glow(img, (cx - r, cy - r, cx + r, cy + r), alpha(color, max(0, min(255, strength))), blur or max(2, r * 0.25))


def tint(color, t):
    """Lighter (t > 0) or darker (t < 0) version of a colour."""
    return mix(color, WHITE, t) if t >= 0 else mix(color, BLACK, -t)
