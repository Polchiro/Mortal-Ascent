"""
Profile card renderer — ink-wash scroll style.
render_profile(data) returns a PIL Image; the bot sends it as a PNG.

Fonts (put in a fonts/ folder next to this file):
  Cinzel.ttf, Inter.ttf      — free from Google Fonts
  NotoSerifSC-Bold.otf       — free from Google Fonts (Chinese characters)
"""
import os
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")
CJK_CANDIDATES = [
    os.path.join(FONT_DIR, "NotoSerifSC-Bold.otf"),
    "/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc",
]

S = 2                      # render at 2x, downscale for smooth edges
W, H = 1200, 720

PAPER = (241, 232, 212)
PAPER_DARK = (229, 217, 192)
INK = (30, 27, 25)
INK_SOFT = (110, 100, 88)
VERMILION = (176, 44, 34)
JADE = (40, 124, 100)
JADE_LIGHT = (200, 222, 208)
GOLD = (176, 128, 34)

# 凡 黄 玄 地 天 — classic grade characters
GRADES = {
    "Mortal": ("凡", (128, 120, 110)), "Yellow": ("黄", (190, 140, 24)),
    "Mystic": ("玄", (70, 92, 170)), "Earth": ("地", (126, 88, 48)),
    "Heaven": ("天", (186, 52, 36)),
}
TIERS = {
    "ordinary": ("凡", (128, 120, 110)), "refined": ("精", (52, 136, 70)),
    "spirit": ("灵", (50, 106, 186)), "treasure": ("宝", (126, 66, 156)),
    "divine": ("神", (210, 116, 26)),
}
TALENT_COLORS = {
    "Ordinary": (128, 120, 110), "Gifted": (52, 136, 70), "Genius": (50, 106, 186),
    "Prodigy": (126, 66, 156), "Heavenly": (190, 140, 24), "Saint": (210, 116, 26),
    "Divine": (176, 44, 34),
}
REALM_CHINESE = {
    "Mortal": "凡人", "Martial Apprentice": "武徒", "Martial Warrior": "武者",
    "Martial Expert": "武师", "Martial Master": "武宗", "Grand Martial Master": "大武宗",
    "Martial Grandmaster": "武尊", "Martial King": "武王", "Martial Emperor": "武帝",
    "Martial Ancestor": "武祖", "Martial Saint": "武圣",
}
MASTERY_STAGES = ["Glimpsing the Gate", "Entering the Hall", "Pure Flame",
                  "Divine Transformation", "Return to Simplicity"]


# ── helpers ───────────────────────────────────────────────────────────

def font(name, size, weight=None):
    try:
        f = ImageFont.truetype(os.path.join(FONT_DIR, name), size * S)
        if weight:
            f.set_variation_by_name(weight)
        return f
    except Exception:
        return ImageFont.truetype("DejaVuSans.ttf", size * S)


def cjk(size):
    for path in CJK_CANDIDATES:
        if os.path.exists(path):
            return ImageFont.truetype(path, size * S)
    return ImageFont.truetype("DejaVuSans.ttf", size * S)


def short(n):
    """18240 -> 18.24K, 83370000000000 -> 83.37T"""
    for value, suffix in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if n >= value:
            return f"{n / value:.2f}".rstrip("0").rstrip(".") + suffix
    return f"{n:,.0f}"


def p(*xy):
    return tuple(v * S for v in xy)


def text(d, xy, s, f, fill, anchor="la"):
    d.text(p(*xy), s, font=f, fill=fill, anchor=anchor)


def spaced(d, xy, s, f, fill, spacing=2.0):
    """Letter-spaced small caps label."""
    x, y = xy
    for ch in s:
        d.text(p(x, y), ch, font=f, fill=fill)
        x += d.textlength(ch, font=f) / S + spacing


def brush_stroke(d, x1, x2, y, thick, color):
    """Tapered horizontal brush stroke."""
    pts_top, pts_bot = [], []
    steps = 40
    for i in range(steps + 1):
        t = i / steps
        x = x1 + (x2 - x1) * t
        w = thick * (0.25 + 0.75 * (1 - abs(2 * t - 0.7) ** 1.6)) if t < 0.95 else thick * 0.2
        wobble = 0.6 * ((i * 37) % 7 - 3) / 3
        pts_top.append(p(x, y - w / 2 + wobble))
        pts_bot.append(p(x, y + w / 2 + wobble))
    d.polygon(pts_top + pts_bot[::-1], fill=color)


def seal_square(img, char, xy, size, color, rotate=0):
    s = Image.new("RGBA", p(size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(s)
    d.rounded_rectangle((0, 0, size * S - 1, size * S - 1), radius=max(3, size // 8) * S, fill=color + (240,))
    inset = max(2, size // 12)
    d.rounded_rectangle(p(inset, inset, size - inset, size - inset), radius=max(2, size // 12) * S,
                        outline=PAPER + (210,), width=max(1, size // 30) * S)
    d.text(p(size / 2, size / 2 + size * 0.03), char, font=cjk(int(size * 0.6)), fill=PAPER, anchor="mm")
    if rotate:
        s = s.rotate(rotate, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(s, tuple(int(v) for v in p(*xy)))


# ── background ────────────────────────────────────────────────────────

def background(h=H):
    rnd = random.Random(7)
    img = Image.new("RGBA", p(W, h), PAPER + (255,))

    # paper grain
    noise = Image.effect_noise(p(W, h), 18).convert("L")
    grain = Image.merge("RGBA", [noise, noise, noise, Image.new("L", noise.size, 22)])
    img = Image.alpha_composite(img, grain)

    # vignette (darker, warmer edges)
    vig = Image.new("L", p(W, h), 0)
    ImageDraw.Draw(vig).ellipse(p(-160, -140, W + 160, h + 140), fill=255)
    vig = vig.filter(ImageFilter.GaussianBlur(90 * S))
    edge = Image.new("RGBA", img.size, (120, 92, 52, 70))
    edge.putalpha(ImageChops.invert(vig).point(lambda v: v * 70 // 255))
    img = Image.alpha_composite(img, edge)

    # faint red sun behind the title
    sun = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sun).ellipse(p(1000, 50, 1130, 180), fill=VERMILION + (30,))
    img = Image.alpha_composite(img, sun.filter(ImageFilter.GaussianBlur(2 * S)))

    # layered ink-wash mountains, fading downward into mist
    for base_y, peaks, alpha, blur in ((h - 160, 7, 70, 5), (h - 120, 9, 95, 4), (h - 70, 6, 125, 3)):
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        m = ImageDraw.Draw(layer)
        pts = [p(0, h)]
        x = -40
        while x < W + 80:
            pts.append(p(x, base_y - rnd.randint(30, 110)))
            x += rnd.randint(70, 160)
            pts.append(p(x, base_y - rnd.randint(0, 30)))
            x += rnd.randint(40, 90)
        pts.append(p(W, h))
        m.polygon(pts, fill=INK + (alpha,))
        # mist: fade the lower part of each range
        fade = Image.linear_gradient("L").resize(img.size)
        fade = fade.point(lambda v: 255 - v)
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), fade))
        img = Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(blur * S)))

    img = plum_branch(img, rnd)

    d = ImageDraw.Draw(img)
    # frame with corner ornaments
    d.rectangle(p(18, 18, W - 18, h - 18), outline=INK + (255,), width=3 * S)
    d.rectangle(p(27, 27, W - 27, h - 27), outline=INK_SOFT + (140,), width=1 * S)
    for cx, cy, sx, sy in ((18, 18, 1, 1), (W - 18, 18, -1, 1), (18, h - 18, 1, -1), (W - 18, h - 18, -1, -1)):
        d.line(p(cx + sx * 14, cy + sy * 40, cx + sx * 14, cy + sy * 14, cx + sx * 40, cy + sy * 14),
               fill=VERMILION + (255,), width=2 * S)
    return img



def plum_branch(img, rnd):
    """Classic ink plum-blossom branch drawn procedurally (top-right corner)."""
    import math
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    blossoms = []

    def grow(x, y, angle, length, width, depth):
        segs = 6
        for _ in range(segs):
            angle += rnd.uniform(-0.25, 0.25)
            nx = x + math.cos(angle) * length / segs
            ny = y + math.sin(angle) * length / segs
            d.line(p(x, y, nx, ny), fill=(42, 34, 30, 235), width=max(1, int(width)) * S)
            d.ellipse(p(nx - width / 2, ny - width / 2, nx + width / 2, ny + width / 2), fill=(42, 34, 30, 235))
            x, y = nx, ny
            width *= 0.88
            if rnd.random() < 0.35:
                blossoms.append((x + rnd.uniform(-5, 5), y + rnd.uniform(-5, 5), rnd.uniform(4, 6)))
        if depth == 0 or length < 18:
            blossoms.append((x, y, rnd.uniform(6, 8)))
            return
        grow(x, y, angle + rnd.uniform(0.3, 0.6), length * 0.62, width, depth - 1)
        grow(x, y, angle - rnd.uniform(0.2, 0.5), length * 0.7, width, depth - 1)

    grow(1172, 36, math.radians(172), 120, 7, 2)
    grow(1172, 36, math.radians(138), 62, 5, 1)

    for bx, by, r in blossoms:
        if by > 128 or bx < 950:   # keep clear of title and pips
            continue
        rot = rnd.uniform(0, 72)
        for k in range(5):
            a = math.radians(rot + k * 72)
            px_, py_ = bx + math.cos(a) * r * 0.6, by + math.sin(a) * r * 0.6
            d.ellipse(p(px_ - r * 0.55, py_ - r * 0.55, px_ + r * 0.55, py_ + r * 0.55),
                      fill=(206, 74, 70, 225))
        d.ellipse(p(bx - r * 0.25, by - r * 0.25, bx + r * 0.25, by + r * 0.25), fill=(240, 196, 92, 255))
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle(p(945, 30, W - 30, 132), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(6 * S))
    layer.putalpha(ImageChops.multiply(layer.getchannel("A"), mask))
    return Image.alpha_composite(img, layer)


def ink_wash(img, center, radius, rnd):
    """Soft irregular ink blot behind the avatar."""
    import math
    cx, cy = center
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    pts = []
    for i in range(36):
        a = math.radians(i * 10)
        r = radius * rnd.uniform(0.82, 1.08)
        pts.append(p(cx + math.cos(a) * r, cy + math.sin(a) * r))
    ImageDraw.Draw(layer).polygon(pts, fill=INK + (22,))
    return Image.alpha_composite(img, layer.filter(ImageFilter.GaussianBlur(16 * S)))


def icon(d, kind, x, y, color):
    """Tiny stat icons, ~16px, top-left at (x, y)."""
    if kind == "heart":
        d.ellipse(p(x, y + 1, x + 9, y + 10), fill=color)
        d.ellipse(p(x + 7, y + 1, x + 16, y + 10), fill=color)
        d.polygon([p(x + 0.5, y + 7), p(x + 15.5, y + 7), p(x + 8, y + 16)], fill=color)
    elif kind == "sword":
        d.line(p(x + 2, y + 14, x + 14, y + 2), fill=color, width=3 * S)
        d.line(p(x + 2, y + 8, x + 8, y + 14), fill=color, width=2 * S)
        d.ellipse(p(x - 1, y + 13, x + 4, y + 18), fill=color)
    elif kind == "shield":
        d.polygon([p(x + 8, y), p(x + 16, y + 3), p(x + 15, y + 10), p(x + 8, y + 16),
                   p(x + 1, y + 10), p(x, y + 3)], fill=color)
    elif kind == "lotus":
        d.ellipse(p(x + 5, y, x + 11, y + 13), fill=color)
        d.ellipse(p(x, y + 5, x + 9, y + 14), fill=color)
        d.ellipse(p(x + 7, y + 5, x + 16, y + 14), fill=color)
        d.line(p(x, y + 15, x + 16, y + 15), fill=color, width=2 * S)

# ── sections ──────────────────────────────────────────────────────────

def qi_ring(img, center, radius, pct, data):
    cx, cy = center
    ring = radius + 18
    # glow
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).arc(p(cx - ring, cy - ring, cx + ring, cy + ring), -90, -90 + 360 * pct,
                             fill=JADE + (70,), width=14 * S)
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(7 * S)))
    d = ImageDraw.Draw(img)
    d.ellipse(p(cx - ring, cy - ring, cx + ring, cy + ring), outline=JADE_LIGHT, width=8 * S)
    d.arc(p(cx - ring, cy - ring, cx + ring, cy + ring), -90, -90 + 360 * pct, fill=JADE, width=8 * S)
    # tick marks
    import math
    for i in range(40):
        a = math.radians(-90 + i * 9)
        r1, r2 = ring + 9, ring + (15 if i % 5 == 0 else 12)
        d.line(p(cx + r1 * math.cos(a), cy + r1 * math.sin(a), cx + r2 * math.cos(a), cy + r2 * math.sin(a)),
               fill=INK_SOFT, width=1 * S)
    # end dot
    a = math.radians(-90 + 360 * pct)
    ex, ey = cx + ring * math.cos(a), cy + ring * math.sin(a)
    d.ellipse(p(ex - 8, ey - 8, ex + 8, ey + 8), fill=PAPER, outline=JADE, width=3 * S)

    # avatar
    if data.get("avatar_path") and os.path.exists(data["avatar_path"]):
        av = Image.open(data["avatar_path"]).convert("RGBA").resize(p(radius * 2, radius * 2))
    else:
        av = Image.new("RGBA", p(radius * 2, radius * 2), PAPER_DARK + (255,))
        ImageDraw.Draw(av).text(p(radius, radius + 4), data["name"][0].upper(),
                                font=font("Cinzel.ttf", 76, "Bold"), fill=INK, anchor="mm")
    mask = Image.new("L", av.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0) + av.size, fill=255)
    img.paste(av, p(cx - radius, cy - radius), mask)
    d.ellipse(p(cx - radius, cy - radius, cx + radius, cy + radius), outline=INK, width=3 * S)


def mastery_pips(d, x, y, stage_index):
    for i in range(5):
        cx = x + i * 13
        if i <= stage_index:
            d.polygon([p(cx, y - 5), p(cx + 5, y), p(cx, y + 5), p(cx - 5, y)], fill=VERMILION)
        else:
            d.polygon([p(cx, y - 5), p(cx + 5, y), p(cx, y + 5), p(cx - 5, y)], outline=INK_SOFT)


def item_row(img, d, x, y, w, seal_char, color, name, sub, right, f_name, f_sub):
    d.line(p(x, y + 48, x + w, y + 48), fill=INK_SOFT + (90,), width=1 * S)
    seal_square(img, seal_char, (x, y + 6), 34, color)
    text(d, (x + 48, y + 8), name, f_name, INK)
    text(d, (x + 48, y + 31), sub, f_sub, color)
    return right


# ── main ──────────────────────────────────────────────────────────────

def render_profile(data):
    img = background()
    d = ImageDraw.Draw(img)

    f_realm = font("Cinzel.ttf", 54, "Black")
    f_label = font("Cinzel.ttf", 13, "Bold")
    f_name = font("Cinzel.ttf", 30, "Bold")
    f_body = font("Inter.ttf", 18, "SemiBold")
    f_sub = font("Inter.ttf", 13, "Medium")
    f_small = font("Inter.ttf", 14, "Medium")
    f_pill = font("Inter.ttf", 14, "Bold")
    f_stat = font("Inter.ttf", 28, "Bold")

    pct = min(1.0, data["qi"] / data["qi_needed"])

    # ── left column ──────────────────────────────────────────────────
    # vertical calligraphy of the realm
    chars = REALM_CHINESE.get(data["realm"], "武")
    f_cal = cjk(46)
    for i, ch in enumerate(chars):
        d.text(p(70, 92 + i * 58), ch, font=f_cal, fill=INK + (200,), anchor="mm")

    img = ink_wash(img, (232, 214), 150, random.Random(3))
    d = ImageDraw.Draw(img)
    qi_ring(img, (232, 214), 96, pct, data)
    d = ImageDraw.Draw(img)
    text(d, (232, 352), f"{pct * 100:.0f}% to next layer", f_small, JADE, "mm")

    text(d, (232, 400), data["name"], f_name, INK, "mm")

    talent = f"{data['talent'].upper()} TALENT"
    tw = d.textlength(talent, font=f_pill) / S + 30
    tx = 232 - tw / 2
    d.rounded_rectangle(p(tx, 428, tx + tw, 458), radius=4 * S, fill=TALENT_COLORS[data["talent"]])
    d.rounded_rectangle(p(tx + 3, 431, tx + tw - 3, 455), radius=3 * S, outline=PAPER + (160,), width=1 * S)
    text(d, (232, 443), talent, f_pill, PAPER, "mm")

    text(d, (232, 486), f"Server Rank  #{data['rank']}", f_small, INK_SOFT, "mm")

    # vertical divider brush
    for i in range(3):
        d.line(p(420 + i, 70, 420 + i, 640), fill=INK + (40 + i * 30,), width=1 * S)

    # ── right column ─────────────────────────────────────────────────
    x0, wcol = 456, 700

    text(d, (x0, 56), data["realm"].upper(), f_realm, INK)
    realm_w = d.textlength(data["realm"].upper(), font=f_realm) / S
    brush_stroke(d, x0, x0 + realm_w + 10, 128, 9, VERMILION + (230,))
    spaced(d, (x0, 144), f"{data['phase'].upper()}  ·  {data['layer']}TH LAYER", f_label, VERMILION, 1.6)

    # layer path: 10 pips joined by a line
    px0 = x0 + 400
    d.line(p(px0, 151, px0 + 9 * 26, 151), fill=VERMILION + (120,), width=2 * S)
    for i in range(10):
        cx = px0 + i * 26
        r = 6 if i < 9 else 9
        filled = i < data["layer"]
        d.ellipse(p(cx - r, 151 - r, cx + r, 151 + r), fill=VERMILION if filled else PAPER,
                  outline=VERMILION, width=2 * S)

    # Qi + rate
    spaced(d, (x0, 186), "INTERNAL QI", f_label, INK_SOFT)
    text(d, (x0, 206), f"{short(data['qi'])}", f_stat, INK)
    qx = x0 + d.textlength(short(data["qi"]), font=f_stat) / S
    text(d, (qx + 6, 214), f"/ {short(data['qi_needed'])}", f_body, INK_SOFT)

    spaced(d, (x0 + 380, 186), "QI RATE", f_label, INK_SOFT)
    rate = f"{short(data['qi_rate'])}/h"
    text(d, (x0 + 380, 206), rate, f_stat, JADE)
    rx = x0 + 380 + d.textlength(rate, font=f_stat) / S
    text(d, (rx + 8, 216), f"×{data['qi_mult']:.2f}", f_small, INK_SOFT)

    # stat tablets with coloured top accent
    stats = [("HP", data["hp"], VERMILION, "heart"), ("ATTACK", data["attack"], INK, "sword"),
             ("DEFENSE", data["defense"], JADE, "shield"), ("LOTUS COINS", data["coins"], GOLD, "lotus")]
    tw_, gap = (wcol - 3 * 14) / 4, 14
    for i, (label, val, color, ic) in enumerate(stats):
        x = x0 + i * (tw_ + gap)
        d.rectangle(p(x, 262, x + tw_, 334), fill=PAPER_DARK + (200,))
        d.rectangle(p(x, 262, x + tw_, 266), fill=color)
        spaced(d, (x + 14, 276), label, f_label, INK_SOFT, 1.2)
        icon(d, ic, x + tw_ - 30, 276, color)
        text(d, (x + 14, 296), short(val), f_stat, color if label == "LOTUS COINS" else INK)

    # techniques
    spaced(d, (x0, 358), "TECHNIQUES", f_label, INK_SOFT)
    for i, t in enumerate(data["techniques"]):
        y = 376 + i * 54
        char, color = GRADES[t["grade"]]
        item_row(img, d, x0, y, wcol, char, color, t["name"],
                 f"{t['grade']} Grade · {t['type'].title()}", None, f_body, f_sub)
        stage = MASTERY_STAGES.index(t["mastery"])
        text(d, (x0 + wcol, y + 10), t["mastery"], f_small, INK, "ra")
        mastery_pips(d, x0 + wcol - 58, y + 36, stage)

    # weapon
    w = data["weapon"]
    spaced(d, (x0, 552), "WEAPON", f_label, INK_SOFT)
    char, color = TIERS[w["tier"]]
    item_row(img, d, x0, 570, wcol, char, color, w["name"], f"{w['tier'].title()} Tier", None, f_body, f_sub)
    text(d, (x0 + wcol, 584), w["buffs"], f_small, color, "ra")

    # footer
    foot = f"Beasts slain {data['beasts']:,}   ·   Breakthroughs {data['breakthroughs']}   ·   Failed {data['failed']}"
    text(d, (x0, 646), foot, f_sub, INK_SOFT)
    if data.get("status"):
        text(d, (x0 + wcol, 646), data["status"], f_sub, VERMILION, "ra")

    # artist's seal, bottom-left
    seal_square(img, "武", (52, 596), 64, VERMILION, rotate=-5)

    return img.resize((W, H), Image.LANCZOS).convert("RGB")


SAMPLE = {
    "name": "Shoaib",
    "talent": "Genius",
    "rank": 12,
    "realm": "Martial King",
    "phase": "Late Phase",
    "layer": 8,
    "qi": 18240,
    "qi_needed": 53760,
    "qi_rate": 512,
    "qi_mult": 1.60,
    "hp": 4186,
    "attack": 1085,
    "defense": 268,
    "coins": 128450,
    "techniques": [
        {"name": "Rolling Thunder Palm", "grade": "Mystic", "type": "attack", "mastery": "Pure Flame"},
        {"name": "Viper Fang Finger", "grade": "Mystic", "type": "attack", "mastery": "Divine Transformation"},
        {"name": "Golden Bell Cover", "grade": "Earth", "type": "defense", "mastery": "Entering the Hall"},
    ],
    "weapon": {"name": "Fine Dragon-Scale Spear", "tier": "treasure", "buffs": "+13% ATK  ·  +9% HP"},
    "beasts": 1284,
    "breakthroughs": 74,
    "failed": 9,
    "status": "Mystic Qi Pill active · 2h left",
}

if __name__ == "__main__":
    render_profile(SAMPLE).save(os.path.join(HERE, "profile_preview.png"))
    print("saved profile_preview.png")
