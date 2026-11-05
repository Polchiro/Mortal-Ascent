"""
Crimson Hall theme: the shared look of the Character Sheet cards.

Black and deep crimson backgrounds, bronze and gold frames, Cinzel headings and
icons drawn in code (no image files), so cards render the same on Windows,
macOS and Linux. Every card module (profile, purse, bag, techniques,
equipment) builds on these helpers.

Coordinates are in card pixels; everything is drawn at S× and scaled down at
the end for smooth edges.
"""
import io
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from profile_card import S, cjk, font, ordinal, short   # shared font cache and number helpers

__all__ = ["S", "cjk", "font", "ordinal", "short"]

W = 1200

# ── Palette ───────────────────────────────────────────────────────────

VOID = (9, 6, 7)
BLOOD = (58, 8, 12)
CRIMSON = (128, 18, 24)
EMBER = (196, 38, 34)
GLOW = (236, 72, 52)
PANEL = (20, 12, 13)
PANEL_HI = (34, 18, 19)
BRONZE_DK = (70, 46, 24)
BRONZE = (138, 96, 48)
GOLD = (206, 164, 86)
GOLD_HI = (246, 216, 150)
PARCHMENT = (232, 216, 188)
ASH = (150, 132, 118)
ASH_DK = (98, 84, 76)
JADE = (82, 186, 140)
MOON = (150, 186, 236)
LOTUS = (236, 176, 92)

# Rarity colours: technique/pill grades, weapon tiers and chest tiers on one scale
RARITY = {
    "Mortal": (170, 160, 150), "Yellow": (222, 182, 70), "Mystic": (110, 150, 236),
    "Earth": (196, 132, 72), "Heaven": (236, 74, 60),
    "ordinary": (170, 160, 150), "refined": (96, 196, 110), "spirit": (90, 160, 240),
    "treasure": (178, 110, 228), "divine": (246, 150, 50),
    "wooden": (168, 122, 76), "bronze": (196, 132, 70), "silver": (186, 196, 210), "jade": (82, 196, 150),
    None: (150, 176, 120),
}
TALENT = {
    "Ordinary": (170, 160, 150), "Gifted": (96, 196, 110), "Genius": (90, 160, 240),
    "Prodigy": (178, 110, 228), "Heavenly": (232, 196, 80), "Saint": (246, 150, 50),
    "Divine": (240, 70, 58),
}
REALM_CHAR = {
    "Mortal": "凡", "Martial Apprentice": "徒", "Martial Warrior": "者", "Martial Expert": "师",
    "Martial Master": "宗", "Grand Martial Master": "宗", "Martial Grandmaster": "尊",
    "Martial King": "王", "Martial Emperor": "帝", "Martial Ancestor": "祖", "Martial Saint": "圣",
}
SCHOOL_CHAR = {"Fist": "拳", "Palm": "掌", "Finger": "指", "Leg": "腿", "Body": "体"}

# ── Accents: the same frame in another colour for each activity ──────
# deep: background glow · lacquer: banner gradient (top, bottom) · main/bright: bars, glows, seals · ink: faded marks

class Accent:
    def __init__(self, name, deep, lacquer, main, bright, ink):
        self.name, self.deep, self.lacquer, self.main, self.bright, self.ink = name, deep, lacquer, main, bright, ink


CRIMSON_HALL = Accent("crimson", BLOOD, ((96, 14, 18), (34, 6, 8)), EMBER, GLOW, CRIMSON)
ACCENTS = {
    "crimson": CRIMSON_HALL,
    "spar": Accent("spar", (10, 24, 46), ((26, 56, 98), (8, 18, 36)), (72, 132, 206), (128, 186, 246), (36, 72, 124)),
    "train": Accent("train", (6, 38, 28), ((18, 86, 62), (6, 28, 20)), (54, 170, 120), (112, 224, 172), (24, 98, 70)),
    "explore": Accent("explore", (50, 30, 6), ((124, 76, 16), (42, 24, 4)), (216, 140, 42), (252, 194, 96),
                      (132, 82, 20)),
}

TABS = [("profile", "Profile"), ("techniques", "Techniques"), ("equipment", "Equipment"),
        ("inventory", "Inventory"), ("purse", "Purse")]


def P(*v):
    """Card pixels → drawing pixels."""
    return tuple(round(x * S) for x in v)


def mix(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def alpha(c, a):
    return c[:3] + (a,)


# ── Text ──────────────────────────────────────────────────────────────

def text(d, xy, s, f, fill, anchor="la", shadow=True):
    if shadow:
        d.text(P(xy[0] + 1, xy[1] + 1.5), s, font=f, fill=(0, 0, 0, 200), anchor=anchor)
    d.text(P(*xy), s, font=f, fill=fill, anchor=anchor)


def width(d, s, f):
    return d.textlength(s, font=f) / S


def fit(d, s, f, max_w):
    """Shorten `s` with an ellipsis until it fits."""
    if width(d, s, f) <= max_w:
        return s
    while s and width(d, s + "…", f) > max_w:
        s = s[:-1]
    return s.rstrip() + "…"


def wrap(d, s, f, max_w, lines=2):
    out, line = [], ""
    for word in s.split():
        test = (line + " " + word).strip()
        if width(d, test, f) <= max_w:
            line = test
        else:
            if line:
                out.append(line)
            line = word
    if line:
        out.append(line)
    if len(out) > lines:
        out = out[:lines]
        out[-1] = fit(d, out[-1] + " …", f, max_w)
    return out


def spaced(d, xy, s, f, fill, spacing=2.0, anchor="l", shadow=True):
    """Letter-spaced caps. anchor: l (left), m (centre) or r (right) at xy."""
    total = sum(width(d, ch, f) for ch in s) + spacing * (len(s) - 1)
    x = {"l": xy[0], "m": xy[0] - total / 2, "r": xy[0] - total}[anchor]
    for ch in s:
        text(d, (x, xy[1]), ch, f, fill, "lm", shadow)
        x += width(d, ch, f) + spacing


def gold_text(img, xy, s, f, anchor="la", top=GOLD_HI, bottom=BRONZE, glow=None):
    """Text filled with a vertical gold gradient, a dark drop shadow and an optional glow."""
    d = ImageDraw.Draw(img)
    l, t, r, b = d.textbbox(P(*xy), s, font=f, anchor=anchor)
    pad = 12 * S
    box = (l - pad, t - pad, r + pad, b + pad)
    mask = Image.new("L", (box[2] - box[0], box[3] - box[1]), 0)
    md = ImageDraw.Draw(mask)
    md.text((P(*xy)[0] - box[0], P(*xy)[1] - box[1]), s, font=f, fill=255, anchor=anchor)
    if glow:
        g = Image.new("RGBA", mask.size, glow[:3] + (0,))
        g.putalpha(mask.filter(ImageFilter.GaussianBlur(7 * S)).point(lambda v: min(255, v * 2)))
        img.alpha_composite(g, (box[0], box[1]))
    sh = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    sh.putalpha(mask.filter(ImageFilter.GaussianBlur(1.5 * S)).point(lambda v: v * 0.9))
    img.alpha_composite(sh, (box[0] + S, box[1] + 2 * S))
    grad = vgradient(mask.size, top, bottom, t - box[1], b - box[1])
    grad.putalpha(mask)
    img.alpha_composite(grad, (box[0], box[1]))
    return (r - l) / S


def vgradient(size, top, bottom, y0=0, y1=None):
    w, h = size
    y1 = h if y1 is None else y1
    col = Image.new("RGBA", (1, h))
    for y in range(h):
        t = min(1, max(0, (y - y0) / max(1, y1 - y0)))
        col.putpixel((0, y), mix(top, bottom, t) + (255,))
    return col.resize((w, h))


# ── Background and frames ─────────────────────────────────────────────

@lru_cache(maxsize=12)
def _background(w, h, seed, accent="crimson"):
    """Black stone with a coloured glow (crimson unless an accent is given), stone grain, ember speckles
    and a dark vignette (cached per size). Pillow only, so no extra packages are needed."""
    a = ACCENTS[accent]
    W2, H2 = w * S, h * S
    # distance from a point a little above the centre, 0 there and 1 at the edges of an ellipse
    dist = Image.radial_gradient("L").resize((round(W2 * 1.24), round(H2 * 1.5)), Image.BILINEAR)
    cx, cy = dist.size[0] // 2, dist.size[1] // 2
    dist = dist.crop((cx - W2 // 2, cy - round(H2 * 0.42), cx - W2 // 2 + W2, cy - round(H2 * 0.42) + H2))
    glow = dist.point(lambda v: round(255 * max(0.0, 1 - v / 255 * 1.41) ** 1.6))
    out = Image.composite(Image.new("RGB", (W2, H2), a.deep), Image.new("RGB", (W2, H2), VOID), glow)
    # stone grain
    random.seed(seed)
    grain = Image.effect_noise((W2 // 4 + 1, H2 // 4 + 1), 24).resize((W2, H2), Image.NEAREST)
    out = Image.blend(out, Image.merge("RGB", (grain, grain, grain)), 0.035)
    # vignette
    shade = dist.point(lambda v: round(255 * min(0.85, max(0.0, v / 255 * 1.41 - 0.55) * 1.1)))
    out = Image.composite(Image.new("RGB", (W2, H2), (0, 0, 0)), out, shade).convert("RGBA")
    # embers
    d = ImageDraw.Draw(out)
    r = random.Random(seed)
    for _ in range(int(w * h / 9000)):
        x, y = r.uniform(0, w), r.uniform(0, h)
        rad = r.uniform(0.4, 1.4)
        d.ellipse(P(x - rad, y - rad, x + rad, y + rad), fill=alpha(mix(a.main, GOLD, r.random()), r.randint(30, 110)))
    return out


def canvas(w, h, seed=7, accent="crimson"):
    return _background(w, h, seed, accent).copy()


def frame(img, box, thick=1.0, corners=True):
    """Bronze-and-gold bevelled border with corner studs."""
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = box
    d.rectangle(P(x0 - 3, y0 - 3, x1 + 3, y1 + 3), outline=(0, 0, 0, 220), width=round(3 * S * thick))
    d.rectangle(P(x0, y0, x1, y1), outline=BRONZE_DK, width=round(4 * S * thick))
    d.rectangle(P(x0 + 1, y0 + 1, x1 - 1, y1 - 1), outline=GOLD, width=round(1.6 * S * thick))
    d.rectangle(P(x0 + 5, y0 + 5, x1 - 5, y1 - 5), outline=alpha(BRONZE, 200), width=max(1, round(S * thick)))
    if corners:
        for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            stud(d, cx, cy, 7 * thick)


def stud(d, cx, cy, r):
    d.polygon([P(cx, cy - r), P(cx + r, cy), P(cx, cy + r), P(cx - r, cy)], fill=BRONZE_DK, outline=GOLD)
    d.polygon([P(cx, cy - r * 0.45), P(cx + r * 0.45, cy), P(cx, cy + r * 0.45), P(cx - r * 0.45, cy)], fill=GOLD_HI)


def panel(img, box, title=None, fill=PANEL, glow=False, accent=CRIMSON_HALL):
    """A dark recessed panel with a thin gold frame and an optional engraved title."""
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rectangle(P(x0, y0, x1, y1), fill=alpha(fill, 228))
    if glow:
        ld.rectangle(P(x0, y0, x1, y0 + (y1 - y0) * 0.35), fill=alpha(accent.ink, 26))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.rectangle(P(x0, y0, x1, y1), outline=alpha(BRONZE, 235), width=round(1.6 * S))
    d.rectangle(P(x0 + 3, y0 + 3, x1 - 3, y1 - 3), outline=alpha(GOLD, 70), width=max(1, S // 2))
    for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        stud(d, cx, cy, 4)
    if title:
        heading(img, (x0 + 18, y0 + 22), title, x1 - 18)


def heading(img, xy, title, x_end=None):
    """Small engraved section title followed by a gold rule that ends in a diamond."""
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 14, "Bold")
    spaced(d, xy, title.upper(), f, GOLD, 2.2)
    tw = sum(width(d, ch, f) for ch in title.upper()) + 2.2 * (len(title) - 1)
    if x_end:
        rule(d, xy[0] + tw + 12, x_end, xy[1])


def rule(d, x0, x1, y, color=BRONZE):
    d.line(P(x0, y, x1 - 6, y), fill=alpha(color, 220), width=max(1, S))
    stud(d, x1 - 3, y, 3)


def divider(d, x0, x1, y):
    """Centre ornament: gold line fading out to both sides with a diamond in the middle."""
    mid = (x0 + x1) / 2
    steps = 24
    for i in range(steps):
        t0, t1 = i / steps, (i + 1) / steps
        a = round(220 * (1 - abs(t0 - 0.5) * 2) + 20)
        d.line(P(x0 + (x1 - x0) * t0, y, x0 + (x1 - x0) * t1, y), fill=alpha(GOLD, a), width=max(1, S))
    stud(d, mid, y, 5)


def banner(img, box, accent=CRIMSON_HALL):
    """Lacquer banner (crimson unless an accent is given) with gold rules above and below."""
    x0, y0, x1, y1 = box
    g = vgradient((round((x1 - x0) * S), round((y1 - y0) * S)), *accent.lacquer)
    img.alpha_composite(g, P(x0, y0))
    d = ImageDraw.Draw(img)
    for y in (y0, y1):
        d.line(P(x0, y, x1, y), fill=GOLD, width=round(1.5 * S))
        d.line(P(x0, y + (3 if y == y0 else -3), x1, y + (3 if y == y0 else -3)), fill=alpha(BRONZE, 160),
               width=max(1, S // 2))


def tab_strip(img, active, y=0, h=46):
    """The tab bar across the top of every sheet card (the buttons below the card do the switching)."""
    w = img.size[0] / S
    banner(img, (0, y, w, y + h))
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 15, "Bold")
    seg = (w - 80) / len(TABS)
    for i, (key, label) in enumerate(TABS):
        cx = 40 + seg * (i + 0.5)
        if key == active:
            soft_glow(img, (cx - seg * 0.42, y + 6, cx + seg * 0.42, y + h - 6), alpha(GLOW, 150), 10)
            d = ImageDraw.Draw(img)
            spaced(d, (cx, y + h / 2), label.upper(), f, GOLD_HI, 2.5, "m")
            d.line(P(cx - 34, y + h - 7, cx + 34, y + h - 7), fill=GOLD, width=round(1.5 * S))
        else:
            spaced(d, (cx, y + h / 2), label.upper(), f, alpha(ASH, 255), 2.5, "m")
        if i:
            stud(d, 40 + seg * i, y + h / 2, 3.5)


def soft_glow(img, box, color, blur, shape="ellipse"):
    """A blurred ellipse/rectangle of light, drawn on a small local layer (fast)."""
    x0, y0, x1, y1 = box
    pad = blur * 3
    lx0, ly0 = x0 - pad, y0 - pad
    layer = Image.new("RGBA", P(x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), color[:3] + (0,))
    ld = ImageDraw.Draw(layer)
    shape_box = P(pad, pad, pad + x1 - x0, pad + y1 - y0)
    (ld.ellipse if shape == "ellipse" else ld.rectangle)(shape_box, fill=color)
    layer = layer.filter(ImageFilter.GaussianBlur(blur * S))
    img.alpha_composite(layer, (max(0, round(lx0 * S)), max(0, round(ly0 * S))),
                        (max(0, -round(lx0 * S)), max(0, -round(ly0 * S))))


def finish(img):
    """Scale the S× drawing down to the final card."""
    w, h = img.size
    return img.resize((w // S, h // S), Image.LANCZOS).convert("RGB")


# ── Bars, sockets, medallions ─────────────────────────────────────────

def bar(img, box, frac, color=EMBER, label=None, sub=None):
    """A recessed groove with a glowing fill and an optional centred label."""
    x0, y0, x1, y1 = box
    frac = max(0.0, min(1.0, frac))
    d = ImageDraw.Draw(img)
    r = (y1 - y0) / 2
    d.rounded_rectangle(P(x0 - 2, y0 - 2, x1 + 2, y1 + 2), radius=round((r + 2) * S), fill=(0, 0, 0, 255),
                        outline=alpha(BRONZE, 220), width=max(1, S))
    if frac > 0:
        fx = x0 + (x1 - x0) * frac
        g = vgradient((max(1, round((fx - x0) * S)), round((y1 - y0) * S)), mix(color, (255, 240, 220), 0.35),
                      mix(color, (0, 0, 0), 0.45))
        m = Image.new("L", g.size, 0)
        ImageDraw.Draw(m).rounded_rectangle((0, 0, g.size[0] - 1, g.size[1] - 1), radius=round(r * S), fill=255)
        g.putalpha(m)
        img.alpha_composite(g, P(x0, y0))
        d = ImageDraw.Draw(img)
        d.line(P(x0 + r, y0 + 2, max(x0 + r, fx - r), y0 + 2), fill=(255, 255, 255, 70), width=max(1, S))
    if label:
        f = font("Inter.ttf", max(10, round((y1 - y0) * 0.62)), "Bold")
        text(d, ((x0 + x1) / 2, (y0 + y1) / 2), label, f, PARCHMENT, "mm")


def socket(img, box, color=GOLD, filled=True, locked=False, tint=True):
    """A square hotbar-style slot."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    d.rectangle(P(x0, y0, x1, y1), fill=(8, 5, 6, 255), outline=BRONZE_DK, width=round(3 * S))
    d.rectangle(P(x0 + 2, y0 + 2, x1 - 2, y1 - 2), outline=alpha(color if filled else ASH_DK, 255), width=round(1.5 * S))
    if filled and tint:
        soft_glow(img, (x0 + 4, y0 + 4, x1 - 4, y1 - 4), alpha(color, 46), 4, "rect")
    if locked:
        icon(img, "lock", ((x0 + x1) / 2, (y0 + y1) / 2), (y1 - y0) * 0.4, ASH_DK)


def medallion(img, center, r, glyph, color, cjk_char=True):
    """Round gold-ringed seal with a character (school, grade, realm) or a drawn icon inside."""
    cx, cy = center
    soft_glow(img, (cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4), alpha(color, 90), 5)
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=(10, 6, 7, 255), outline=BRONZE_DK, width=round(3 * S))
    d.ellipse(P(cx - r + 2, cy - r + 2, cx + r - 2, cy + r - 2), outline=GOLD, width=round(1.4 * S))
    d.ellipse(P(cx - r + 5, cy - r + 5, cx + r - 5, cy + r - 5), fill=alpha(mix(color, (0, 0, 0), 0.6), 255))
    if cjk_char:
        f = cjk(round(r * 1.05))
        text(d, (cx, cy + 1), glyph, f, mix(color, (255, 255, 255), 0.25), "mm")
    else:
        icon(img, glyph, (cx, cy), r * 1.1, mix(color, (255, 255, 255), 0.25))


def diamonds(d, x, y, filled, total=5, size=5, color=EMBER):
    """Mastery pips: filled diamonds for reached stages."""
    for i in range(total):
        cx = x + i * (size * 2.6)
        pts = [P(cx, y - size), P(cx + size, y), P(cx, y + size), P(cx - size, y)]
        if i < filled:
            d.polygon(pts, fill=color, outline=GOLD_HI)
        else:
            d.polygon(pts, fill=(20, 12, 12), outline=alpha(BRONZE, 255))


def pips(d, x, y, filled, total, r=5.5, gap=17):
    """Layer pips: one circle per layer of the realm, filled up to the current layer."""
    for i in range(total):
        cx = x + i * gap
        if i < filled:
            d.ellipse(P(cx - r, y - r, cx + r, y + r), fill=EMBER, outline=GOLD_HI, width=max(1, S))
        else:
            d.ellipse(P(cx - r, y - r, cx + r, y + r), fill=(16, 10, 10), outline=BRONZE, width=max(1, S))


def orb(img, center, r, frac, label=None):
    """The dantian orb: a glass sphere in a bronze cradle, filled with red Qi up to `frac`."""
    cx, cy = center
    frac = max(0.0, min(1.0, frac))
    soft_glow(img, (cx - r * 1.35, cy - r * 1.35, cx + r * 1.35, cy + r * 1.35), alpha(GLOW, round(60 + 110 * frac)), 16)
    d = ImageDraw.Draw(img)
    # cradle
    d.ellipse(P(cx - r - 9, cy - r - 9, cx + r + 9, cy + r + 9), fill=BRONZE_DK, outline=GOLD, width=round(2 * S))
    for a in range(0, 360, 30):
        x = cx + math.cos(math.radians(a)) * (r + 5)
        y = cy + math.sin(math.radians(a)) * (r + 5)
        d.ellipse(P(x - 2, y - 2, x + 2, y + 2), fill=GOLD_HI)
    # glass and liquid
    sphere = Image.new("RGBA", P(2 * r, 2 * r), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sphere)
    sd.ellipse((0, 0, sphere.size[0] - 1, sphere.size[1] - 1), fill=(16, 4, 6, 255))
    level = sphere.size[1] * (1 - frac)
    liquid = vgradient(sphere.size, (255, 96, 70), (90, 0, 8), level, sphere.size[1])
    lm = Image.new("L", sphere.size, 0)
    ImageDraw.Draw(lm).rectangle((0, level, sphere.size[0], sphere.size[1]), fill=255)
    circle = Image.new("L", sphere.size, 0)
    ImageDraw.Draw(circle).ellipse((0, 0, sphere.size[0] - 1, sphere.size[1] - 1), fill=255)
    from PIL import ImageChops
    liquid.putalpha(ImageChops.multiply(lm, circle))
    sphere.alpha_composite(liquid)
    sd = ImageDraw.Draw(sphere)
    if 0 < frac < 1:
        sd.line((0, level, sphere.size[0], level), fill=(255, 170, 130, 160), width=S)
    # highlight
    hl = Image.new("RGBA", sphere.size, (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse((sphere.size[0] * 0.24, sphere.size[1] * 0.12, sphere.size[0] * 0.5,
                                sphere.size[1] * 0.26), fill=(255, 255, 255, 40))
    sphere.alpha_composite(hl.filter(ImageFilter.GaussianBlur(3 * S)))
    img.alpha_composite(sphere, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), outline=alpha(GOLD, 200), width=max(1, S))
    if label:
        text(d, (cx, cy), label, font("Cinzel.ttf", round(r * 0.42), "Black"), GOLD_HI, "mm")


def portrait(img, box, avatar_bytes, name, realm, color=EMBER):
    """The character portrait: the Discord avatar in an arched gold frame over a red Qi aura,
    with the realm's character behind it. Falls back to the initial if there is no avatar."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    soft_glow(img, (x0 + w * 0.05, y0 + h * 0.05, x1 - w * 0.05, y1 - h * 0.12), alpha(color, 120), 28)
    d = ImageDraw.Draw(img)
    f = cjk(round(h * 0.62))
    text(d, ((x0 + x1) / 2, y0 + h * 0.42), REALM_CHAR.get(realm, "武"), f, alpha(CRIMSON, 120), "mm", shadow=False)

    # arch-shaped window
    ix0, iy0, ix1, iy1 = x0 + 28, y0 + 26, x1 - 28, y1 - 58
    mask = Image.new("L", P(ix1 - ix0, iy1 - iy0), 0)
    md = ImageDraw.Draw(mask)
    mw, mh = mask.size
    md.ellipse((0, 0, mw - 1, mw - 1), fill=255)
    md.rectangle((0, mw / 2, mw - 1, mh - 1), fill=255)
    face = None
    if avatar_bytes:
        try:
            face = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        except Exception:
            face = None
    if face is None:
        face = vgradient((mw, mh), (70, 14, 18), (18, 6, 8))
        fd = ImageDraw.Draw(face)
        fd.text((mw / 2, mh / 2), (name or "?")[:1].upper(), font=font("Cinzel.ttf", round(mh / S * 0.45), "Black"),
                fill=GOLD_HI, anchor="mm")
    else:
        side = max(mw, mh)
        face = face.resize((side, side), Image.LANCZOS).crop(((side - mw) // 2, (side - mh) // 2,
                                                              (side - mw) // 2 + mw, (side - mh) // 2 + mh))
        shade = vgradient((mw, mh), (0, 0, 0), (40, 0, 0), mh * 0.55, mh)
        shade.putalpha(Image.linear_gradient("L").resize((mw, mh)).point(lambda v: v * 0.55))
        face.alpha_composite(shade)
    face.putalpha(mask)
    img.alpha_composite(face, P(ix0, iy0))
    d = ImageDraw.Draw(img)
    # frame around the arch
    for off, col, wdt in ((-5, BRONZE_DK, 5), (-2, GOLD, 1.8), (3, alpha(BRONZE, 200), 1)):
        a0, b0, a1 = ix0 + off, iy0 + off, ix1 - off
        d.arc(P(a0, b0, a1, b0 + (a1 - a0)), 180, 360, fill=col, width=round(wdt * S))
        d.line(P(a0, b0 + (a1 - a0) / 2, a0, iy1 - off), fill=col, width=round(wdt * S))
        d.line(P(a1, b0 + (a1 - a0) / 2, a1, iy1 - off), fill=col, width=round(wdt * S))
        d.line(P(a0, iy1 - off, a1, iy1 - off), fill=col, width=round(wdt * S))
    stud(d, (ix0 + ix1) / 2, iy0 - 4, 8)
    # name plate
    plate = (x0 + 40, y1 - 48, x1 - 40, y1 - 14)
    banner(img, plate)
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 18, "Bold")
    text(d, ((plate[0] + plate[2]) / 2, (plate[1] + plate[3]) / 2), fit(d, name.upper(), f, plate[2] - plate[0] - 20),
         f, GOLD_HI, "mm")


# ── Icons (drawn, so no image files are needed) ───────────────────────

def icon(img, kind, center, size, color):
    """Draw a small icon centred at `center`, `size` pixels tall."""
    d = ImageDraw.Draw(img)
    cx, cy = center
    s = size / 2
    dark = mix(color, (0, 0, 0), 0.55)
    if kind == "heart":
        r = s * 0.55
        d.ellipse(P(cx - s, cy - s * 0.75, cx - s + 2 * r, cy - s * 0.75 + 2 * r), fill=color)
        d.ellipse(P(cx + s - 2 * r, cy - s * 0.75, cx + s, cy - s * 0.75 + 2 * r), fill=color)
        d.polygon([P(cx - s * 0.98, cy - s * 0.1), P(cx + s * 0.98, cy - s * 0.1), P(cx, cy + s)], fill=color)
    elif kind == "sword":
        d.polygon([P(cx - s * 0.12, cy + s * 0.35), P(cx - s * 0.12, cy - s * 0.75), P(cx, cy - s),
                   P(cx + s * 0.12, cy - s * 0.75), P(cx + s * 0.12, cy + s * 0.35)], fill=color)
        d.rectangle(P(cx - s * 0.5, cy + s * 0.35, cx + s * 0.5, cy + s * 0.5), fill=dark, outline=color)
        d.rectangle(P(cx - s * 0.09, cy + s * 0.5, cx + s * 0.09, cy + s * 0.88), fill=dark)
        d.ellipse(P(cx - s * 0.15, cy + s * 0.84, cx + s * 0.15, cy + s), fill=color)
    elif kind == "shield":
        d.polygon([P(cx - s * 0.8, cy - s * 0.8), P(cx + s * 0.8, cy - s * 0.8), P(cx + s * 0.8, cy - s * 0.05),
                   P(cx, cy + s), P(cx - s * 0.8, cy - s * 0.05)], fill=color)
        d.polygon([P(cx - s * 0.5, cy - s * 0.55), P(cx + s * 0.5, cy - s * 0.55), P(cx + s * 0.5, cy - s * 0.05),
                   P(cx, cy + s * 0.6), P(cx - s * 0.5, cy - s * 0.05)], fill=dark)
        d.line(P(cx, cy - s * 0.55, cx, cy + s * 0.6), fill=color, width=max(1, S))
    elif kind == "lotus":
        base = (cx, cy + s * 0.55)
        for ang, ln, col in ((-62, 0.8, dark), (62, 0.8, dark), (-30, 1.15, color), (30, 1.15, color),
                             (0, 1.45, mix(color, (255, 255, 255), 0.2))):
            petal(d, base, ang, s * ln, s * 0.42, col)
        d.chord(P(cx - s * 0.9, cy + s * 0.3, cx + s * 0.9, cy + s * 0.95), 0, 180, fill=dark)
    elif kind == "pearl":
        d.ellipse(P(cx - s, cy - s, cx + s, cy + s), fill=dark)
        d.ellipse(P(cx - s + 1, cy - s + 1, cx + s * 0.55, cy + s * 0.55), fill=color)
        d.ellipse(P(cx - s * 0.1, cy - s * 0.55, cx + s * 0.9, cy + s * 0.45), fill=dark)
        d.ellipse(P(cx + s * 0.2, cy + s * 0.2, cx + s * 0.62, cy + s * 0.62), fill=(240, 244, 255))
    elif kind == "flame":
        d.polygon([P(cx, cy - s), P(cx + s * 0.62, cy - s * 0.05), P(cx + s * 0.55, cy + s * 0.6), P(cx, cy + s),
                   P(cx - s * 0.55, cy + s * 0.6), P(cx - s * 0.62, cy - s * 0.05)], fill=color)
        d.ellipse(P(cx - s * 0.62, cy - s * 0.1, cx + s * 0.62, cy + s), fill=color)
        d.polygon([P(cx, cy - s * 0.25), P(cx + s * 0.3, cy + s * 0.3), P(cx, cy + s * 0.75),
                   P(cx - s * 0.3, cy + s * 0.3)], fill=(255, 226, 170))
    elif kind == "scroll":
        d.rectangle(P(cx - s * 0.6, cy - s * 0.7, cx + s * 0.6, cy + s * 0.7), fill=mix(color, PARCHMENT, 0.6))
        for yy in (-0.7, 0.7):
            d.rounded_rectangle(P(cx - s * 0.8, cy + s * yy - s * 0.16, cx + s * 0.8, cy + s * yy + s * 0.16),
                                radius=round(s * 0.16 * S), fill=color)
        for yy in (-0.3, 0, 0.3):
            d.line(P(cx - s * 0.35, cy + s * yy, cx + s * 0.35, cy + s * yy), fill=dark, width=max(1, S))
    elif kind == "chest":
        d.rounded_rectangle(P(cx - s, cy - s * 0.75, cx + s, cy - s * 0.05), radius=round(s * 0.4 * S), fill=color)
        d.rectangle(P(cx - s, cy - s * 0.15, cx + s, cy + s * 0.8), fill=dark, outline=color, width=max(1, S))
        d.rectangle(P(cx - s * 0.2, cy - s * 0.3, cx + s * 0.2, cy + s * 0.15), fill=GOLD_HI)
    elif kind == "pill":
        d.ellipse(P(cx - s * 0.85, cy - s * 0.85, cx + s * 0.85, cy + s * 0.85), fill=color)
        d.ellipse(P(cx - s * 0.5, cy - s * 0.6, cx - s * 0.05, cy - s * 0.15), fill=(255, 255, 255, 120))
        d.arc(P(cx - s * 0.85, cy - s * 0.85, cx + s * 0.85, cy + s * 0.85), 20, 160, fill=dark, width=max(1, S))
    elif kind == "herb":
        d.line(P(cx, cy + s, cx, cy - s * 0.3), fill=dark, width=round(1.5 * S))
        for side in (-1, 1):
            for yy, sz in ((-0.55, 0.55), (0.05, 0.7)):
                leaf = [P(cx, cy + s * yy), P(cx + side * s * sz, cy + s * (yy - 0.35)),
                        P(cx + side * s * (sz + 0.15), cy + s * (yy + 0.05)), P(cx + side * s * 0.1, cy + s * (yy + 0.3))]
                d.polygon(leaf, fill=color)
        d.ellipse(P(cx - s * 0.2, cy - s, cx + s * 0.2, cy - s * 0.6), fill=color)
    elif kind == "lock":
        d.arc(P(cx - s * 0.45, cy - s, cx + s * 0.45, cy - s * 0.1), 180, 360, fill=color, width=round(1.8 * S))
        d.line(P(cx - s * 0.45, cy - s * 0.55, cx - s * 0.45, cy - s * 0.2), fill=color, width=round(1.8 * S))
        d.line(P(cx + s * 0.45, cy - s * 0.55, cx + s * 0.45, cy - s * 0.2), fill=color, width=round(1.8 * S))
        d.rounded_rectangle(P(cx - s * 0.7, cy - s * 0.2, cx + s * 0.7, cy + s * 0.8), radius=round(s * 0.15 * S),
                            fill=color)
    elif kind == "fist":
        d.rounded_rectangle(P(cx - s * 0.7, cy - s * 0.55, cx + s * 0.7, cy + s * 0.45), radius=round(s * 0.3 * S),
                            fill=color)
        for i in range(4):
            x = cx - s * 0.7 + i * s * 0.35
            d.line(P(x + s * 0.35, cy - s * 0.55, x + s * 0.35, cy - s * 0.1), fill=dark, width=max(1, S))
        d.rectangle(P(cx - s * 0.45, cy + s * 0.4, cx + s * 0.45, cy + s), fill=color)
    elif kind == "star":
        pts = []
        for i in range(10):
            rr = s if i % 2 == 0 else s * 0.42
            a = math.radians(-90 + i * 36)
            pts.append(P(cx + math.cos(a) * rr, cy + math.sin(a) * rr))
        d.polygon(pts, fill=color)
    elif kind == "hourglass":
        d.polygon([P(cx - s * 0.6, cy - s), P(cx + s * 0.6, cy - s), P(cx, cy), P(cx + s * 0.6, cy + s),
                   P(cx - s * 0.6, cy + s), P(cx, cy)], fill=color)
        d.polygon([P(cx - s * 0.3, cy + s * 0.85), P(cx + s * 0.3, cy + s * 0.85), P(cx, cy + s * 0.4)], fill=dark)
    elif kind == "skull":
        d.ellipse(P(cx - s * 0.8, cy - s, cx + s * 0.8, cy + s * 0.5), fill=color)
        d.rectangle(P(cx - s * 0.45, cy + s * 0.3, cx + s * 0.45, cy + s * 0.85), fill=color)
        for side in (-1, 1):
            d.ellipse(P(cx + side * s * 0.38 - s * 0.22, cy - s * 0.35, cx + side * s * 0.38 + s * 0.22, cy + s * 0.05),
                      fill=dark)
    elif kind in WEAPON_ICON:
        WEAPON_ICON[kind](d, cx, cy, s, color, dark)
    else:   # unknown: a diamond
        d.polygon([P(cx, cy - s), P(cx + s, cy), P(cx, cy + s), P(cx - s, cy)], fill=color)


def petal(d, base, angle, length, half_width, color):
    """A pointed petal growing from `base` at `angle` degrees from straight up."""
    bx, by = base
    a = math.radians(angle)
    ux, uy = math.sin(a), -math.cos(a)          # along the petal
    px, py = -uy, ux                             # across it
    pts = []
    for i in range(13):
        tt = i / 12
        wdt = math.sin(math.pi * tt) * half_width
        pts.append((bx + ux * length * tt + px * wdt, by + uy * length * tt + py * wdt))
    for i in range(12, -1, -1):
        tt = i / 12
        wdt = math.sin(math.pi * tt) * half_width
        pts.append((bx + ux * length * tt - px * wdt, by + uy * length * tt - py * wdt))
    d.polygon([P(x, y) for x, y in pts], fill=color)


def _saber(d, cx, cy, s, color, dark):
    d.polygon([P(cx - s * 0.1, cy + s * 0.4), P(cx - s * 0.1, cy - s * 0.6), P(cx + s * 0.3, cy - s),
               P(cx + s * 0.22, cy + s * 0.4)], fill=color)
    d.rectangle(P(cx - s * 0.4, cy + s * 0.4, cx + s * 0.5, cy + s * 0.52), fill=dark, outline=color)
    d.rectangle(P(cx - s * 0.02, cy + s * 0.52, cx + s * 0.14, cy + s), fill=dark)


def _spear(d, cx, cy, s, color, dark):
    d.line(P(cx - s * 0.7, cy + s, cx + s * 0.45, cy - s * 0.45), fill=dark, width=round(1.8 * S))
    d.polygon([P(cx + s * 0.3, cy - s * 0.3), P(cx + s, cy - s), P(cx + s * 0.6, cy - s * 0.15)], fill=color)
    d.ellipse(P(cx + s * 0.1, cy - s * 0.2, cx + s * 0.35, cy + s * 0.05), fill=EMBER)


def _staff(d, cx, cy, s, color, dark):
    d.line(P(cx - s * 0.75, cy + s, cx + s * 0.75, cy - s), fill=color, width=round(2.4 * S))
    for t in (0.15, 0.85):
        x, y = cx - s * 0.75 + s * 1.5 * t, cy + s - 2 * s * t
        d.ellipse(P(x - s * 0.16, y - s * 0.16, x + s * 0.16, y + s * 0.16), fill=GOLD_HI)


def _gauntlets(d, cx, cy, s, color, dark):
    icon_fist = [P(cx - s * 0.75, cy - s * 0.5), P(cx + s * 0.75, cy + s * 0.5)]
    d.rounded_rectangle(icon_fist[0] + icon_fist[1], radius=round(s * 0.3 * S), fill=color)
    d.rectangle(P(cx - s * 0.55, cy + s * 0.45, cx + s * 0.55, cy + s), fill=dark, outline=color)
    for i in range(3):
        x = cx - s * 0.4 + i * s * 0.4
        d.ellipse(P(x - s * 0.09, cy - s * 0.15, x + s * 0.09, cy + s * 0.03), fill=GOLD_HI)


WEAPON_ICON = {
    "saber": _saber, "spear": _spear, "staff": _staff, "gauntlets": _gauntlets,
}
