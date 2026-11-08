"""
/internal qi card · the dantian ("Spirit Sea" 灵海, the Night Ink family: cards/ink.py).

render_dantian(data) draws the dict built by bot/qi.py:qi_data:
- the dantian as a vortex of jade Qi inside a bagua ring, filled to the bar's level;
- the realm, phase and layer, the cultivation status, and the Qi bar as a meridian stream
  (banked Qi, plus Qi gathered but not yet banked shown hatched after it);
- three hanging jade tablets: Qi Rate, time to a full bar, the next gate;
- the Flow of Qi: every active Qi Rate source on one stream that ends in the final rate, then the
  dormant sources and pill toxicity on one line.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter, ImageChops

from . import ink as k
from . import theme as t
from .theme import P, font, short, mix, alpha

W, H = 1200, 760
INK = (3, 10, 15)
SEA_DEEP = (6, 30, 40)
SEA = (34, 140, 186)
JADE = (70, 222, 196)
JADE_HI = (184, 255, 240)
GOLD = (226, 200, 140)
GOLD_DK = (96, 82, 56)
TXT = (234, 244, 240)
MUTED = (128, 160, 164)
DIM = (66, 92, 100)
TRIGRAMS = ["111", "110", "101", "100", "011", "010", "001", "000"]


def fmt(n):
    return short(n) if n >= 10000 else f"{n:,.0f}"


# ── Background ────────────────────────────────────────────────────────

def background():
    w, h = W * t.S, H * t.S
    img = t.vgradient((w, h), (4, 12, 18), (2, 8, 12)).convert("RGBA")
    # sea glow behind the dantian and a cooler one top-right
    t.soft_glow(img, (60, 90, 440, 470), (20, 110, 120, 150), 60)
    t.soft_glow(img, (760, -80, 1260, 200), (20, 60, 110, 90), 70)
    # ink-wash mountains at the bottom
    rng = random.Random(5)
    for layer, (base, amp, col, a) in enumerate(((520, 60, (10, 34, 42), 160), (575, 46, (8, 26, 34), 200),
                                                (640, 34, (5, 16, 22), 230))):
        pts = [(0, H)]
        ph = rng.uniform(0, 6)
        for x in range(0, W + 20, 20):
            y = base - amp * (0.55 * math.sin(x / 140 + ph) + 0.3 * math.sin(x / 57 + ph * 2) + 0.15 * math.sin(x / 23))
            pts.append((x, y))
        pts.append((W, H))
        m = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(m).polygon([P(*q) for q in pts], fill=col + (a,))
        img.alpha_composite(m.filter(ImageFilter.GaussianBlur(1.5 * t.S)))
    # mist bands
    mist = Image.new("RGBA", img.size, (0, 0, 0, 0))
    md = ImageDraw.Draw(mist)
    for y, a in ((560, 26), (628, 20), (700, 16)):
        md.rectangle(P(0, y - 8, W, y + 8), fill=(160, 220, 220, a))
    img.alpha_composite(mist.filter(ImageFilter.GaussianBlur(12 * t.S)))
    # spirit motes
    d = ImageDraw.Draw(img)
    for _ in range(140):
        x, y = rng.uniform(0, W), rng.uniform(0, H)
        r = rng.choice((0.6, 0.8, 1.0, 1.4, 2.0))
        a = rng.randint(40, 170)
        if r >= 1.4:
            t.soft_glow(img, (x - 4, y - 4, x + 4, y + 4), alpha(JADE, a // 2), 2)
            d = ImageDraw.Draw(img)
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=alpha(mix(JADE_HI, GOLD, rng.random() * 0.4), a))
    return img


def frame(img):
    d = ImageDraw.Draw(img)
    x0, y0, x1, y1 = 8, 8, W - 8, H - 8
    d.rectangle(P(x0, y0, x1, y1), outline=alpha(GOLD_DK, 255), width=round(3 * t.S))
    d.rectangle(P(x0 + 2, y0 + 2, x1 - 2, y1 - 2), outline=alpha(GOLD, 200), width=max(1, round(1.2 * t.S)))
    d.rectangle(P(x0 + 7, y0 + 7, x1 - 7, y1 - 7), outline=alpha(JADE, 60), width=max(1, t.S))
    for cx, cy, fx, fy in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
        d.polygon([P(cx, cy), P(cx + fx * 34, cy), P(cx, cy + fy * 34)], fill=alpha(INK, 255))
        d.line(P(cx + fx * 34, cy, cx, cy + fy * 34), fill=GOLD, width=round(1.4 * t.S))
        k.cloud_curl(d, cx + fx * 16, cy + fy * 16, 8, alpha(GOLD, 255), flip=fx, width=1.6)


# ── Dantian vortex ────────────────────────────────────────────────────

def dantian(img, center, r, frac, qi, cap):
    cx, cy = center
    t.soft_glow(img, (cx - r - 20, cy - r - 20, cx + r + 20, cy + r + 20), alpha(JADE, round(60 + 90 * frac)), 26)
    d = ImageDraw.Draw(img)
    # bagua ring
    for rr, a in ((r + 66, 70), (r + 50, 110)):
        d.ellipse(P(cx - rr, cy - rr, cx + rr, cy + rr), outline=alpha(GOLD, a), width=max(1, t.S))
    for i, tri in enumerate(TRIGRAMS):
        ang = math.radians(-90 + i * 45)
        tx, ty = -math.sin(ang), math.cos(ang)
        for j, bit in enumerate(tri):
            rr = r + 26 + j * 6.5
            px, py = cx + rr * math.cos(ang), cy + rr * math.sin(ang)
            hl = 12
            col = alpha(GOLD, 220)
            if bit == "1":
                d.line(P(px - tx * hl, py - ty * hl, px + tx * hl, py + ty * hl), fill=col, width=round(3 * t.S))
            else:
                for s0, s1 in ((-hl, -3), (3, hl)):
                    d.line(P(px + tx * s0, py + ty * s0, px + tx * s1, py + ty * s1), fill=col, width=round(3 * t.S))
        # small gem between trigrams
        ga = math.radians(-90 + i * 45 + 22.5)
        k.gem(d, cx + (r + 33) * math.cos(ga), cy + (r + 33) * math.sin(ga), 3.2, JADE)
    # outer cradle ring with ticks
    d.ellipse(P(cx - r - 12, cy - r - 12, cx + r + 12, cy + r + 12), outline=alpha(GOLD_DK, 255), width=round(7 * t.S))
    d.ellipse(P(cx - r - 15, cy - r - 15, cx + r + 15, cy + r + 15), outline=alpha(GOLD, 220), width=max(1, round(1.2 * t.S)))
    d.ellipse(P(cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8), outline=alpha(GOLD, 160), width=max(1, t.S))
    for i in range(72):
        a = math.radians(i * 5)
        l = 3 if i % 6 else 6
        d.line(P(cx + (r + 9) * math.cos(a), cy + (r + 9) * math.sin(a), cx + (r + 9 + l) * math.cos(a),
                 cy + (r + 9 + l) * math.sin(a)), fill=alpha(GOLD, 150), width=max(1, t.S))
    # the sea inside
    side = round(2 * r * t.S)
    sph = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    base = Image.radial_gradient("L").resize((side, side))
    sph = Image.composite(Image.new("RGBA", (side, side), (2, 8, 12, 255)),
                          Image.new("RGBA", (side, side), (10, 40, 52, 255)), base)
    level = side * (1 - frac)
    amp = side * 0.018
    wave = [(0, side)] + [(x, level + amp * math.sin(x / side * 2 * math.pi * 2.2 + 0.6))
                          for x in range(0, side + 1, max(1, side // 80))] + [(side, side)]
    lm = Image.new("L", (side, side), 0)
    ImageDraw.Draw(lm).polygon(wave, fill=255)
    liq = t.vgradient((side, side), mix(JADE_HI, JADE, 0.3), (8, 70, 110), round(level - amp), side)
    liq.putalpha(lm)
    sph.alpha_composite(liq)
    # vortex arms swirling round the centre
    sw = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sw)
    c = side / 2
    for arm in range(5):
        pts = []
        for n in range(120):
            th = n / 120 * 2.6 * math.pi + arm * 2 * math.pi / 5
            rr = side * 0.04 + side * 0.46 * (n / 120) ** 1.15
            pts.append((c + rr * math.cos(th), c + rr * math.sin(th)))
        sd.line(pts, fill=(200, 255, 245, 70), width=round(2.2 * t.S), joint="curve")
    sw = sw.filter(ImageFilter.GaussianBlur(1.2 * t.S))
    sph.alpha_composite(sw)
    # surface line + rising motes
    sdd = ImageDraw.Draw(sph)
    sdd.line(wave[1:-1], fill=(220, 255, 250, 210), width=round(1.6 * t.S))
    rng = random.Random(9)
    for _ in range(26):
        x = rng.uniform(side * 0.15, side * 0.85)
        y = rng.uniform(level + side * 0.05, side * 0.95)
        rr = rng.uniform(1, 2.6) * t.S
        sdd.ellipse((x - rr, y - rr, x + rr, y + rr), fill=(230, 255, 250, rng.randint(70, 180)))
    # inner shadow at the rim
    rim = Image.radial_gradient("L").resize((side, side)).point(lambda v: max(0, v - 150) * 2.4)
    dark = Image.new("RGBA", (side, side), (0, 0, 0, 255))
    dark.putalpha(rim)
    sph.alpha_composite(dark)
    cm = Image.new("L", (side, side), 0)
    ImageDraw.Draw(cm).ellipse((0, 0, side - 1, side - 1), fill=255)
    sph.putalpha(ImageChops.multiply(cm, sph.getchannel("A")))
    img.alpha_composite(sph, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    hl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(hl).ellipse(P(cx - r * 0.62, cy - r * 0.86, cx - r * 0.02, cy - r * 0.56), fill=(255, 255, 255, 46))
    img.alpha_composite(hl.filter(ImageFilter.GaussianBlur(5 * t.S)))
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), outline=alpha(JADE_HI, 150), width=max(1, round(1.2 * t.S)))
    # readout
    f_pct = font("Cinzel.ttf", 58, "Black")
    pct = f"{frac:.0%}"
    t.soft_glow(img, (cx - 70, cy - 46, cx + 70, cy + 20), (0, 0, 0, 150), 14)
    d = ImageDraw.Draw(img)
    t.text(d, (cx, cy - 12), pct, f_pct, (250, 255, 252), "mm")
    t.text(d, (cx, cy + 34), f"{fmt(qi)} / {fmt(cap)}", font("Inter.ttf", 15, "SemiBold"), JADE_HI, "mm")
    # 丹田 seal under the ring
    t.text(d, (cx, cy + r + 88), "丹 田", t.cjk(20), alpha(GOLD, 230), "mm")


# ── Header and stream bar ─────────────────────────────────────────────

def header(img, data, x0, x1):
    d = ImageDraw.Draw(img)
    t.spaced(d, (x0, 52), f"{data['name'].upper()}'S DANTIAN", font("Cinzel.ttf", 13, "Bold"), MUTED, 3)
    f_r = font("Cinzel.ttf", 36, "Black")
    t.gold_text(img, (x0 - 2, 70), data["realm"].upper(), f_r, top=(255, 238, 200), bottom=(176, 146, 86))
    d = ImageDraw.Draw(img)
    rw = t.width(d, data["realm"].upper(), f_r)
    t.text(d, (x0 + rw + 18, 92), f"{data['phase']}  ·  {t.ordinal(data['layer'])} Layer", font("Inter.ttf", 15, "SemiBold"),
           MUTED, "lm")
    # status chip, top right
    tone = {"jade": JADE, "gold": GOLD, "red": (240, 110, 90)}.get(data.get("status_tone"), JADE)
    s = data["status"]
    f_s = font("Inter.ttf", 12, "Bold")
    sw = t.width(d, s, f_s) + 40
    bx = x1 - sw
    d.rounded_rectangle(P(bx, 46, x1, 70), radius=round(12 * t.S), fill=alpha(mix(tone, INK, 0.82), 255),
                        outline=alpha(tone, 200), width=max(1, t.S))
    t.soft_glow(img, (bx + 9, 52, bx + 21, 64), alpha(tone, 220), 3)
    d = ImageDraw.Draw(img)
    d.ellipse(P(bx + 12, 55, bx + 18, 61), fill=mix(tone, (255, 255, 255), 0.4))
    t.text(d, (bx + 26, 58.5), s, f_s, mix(tone, (255, 255, 255), 0.45), "lm")


def stream_bar(img, data, box):
    x0, y0, x1, y1 = box
    h = y1 - y0
    need = data["qi_needed"]
    frac = min(1.0, data["qi"] / need) if need else 1
    pend = min(1 - frac, data.get("pending", 0) / need) if need else 0
    d = ImageDraw.Draw(img)
    # numbers above
    f_big = font("Cinzel.ttf", 40, "Black")
    cur = f"{data['qi']:,.0f}"
    t.text(d, (x0, y0 - 28), cur, f_big, TXT, "ls")
    cw = t.width(d, cur, f_big)
    t.text(d, (x0 + cw + 8, y0 - 30), f"/ {need:,} Qi", font("Inter.ttf", 17, "SemiBold"), MUTED, "ls")
    if data.get("overflow_text"):              # Qi held behind a bottleneck or gate (kept, flows on after it)
        over = data["overflow_text"].replace("Qi bar full · ", "")
        t.text(d, (x1, y0 - 30), over, font("Inter.ttf", 13, "SemiBold"), GOLD, "rs")
    elif data.get("pending", 0) >= 1:
        t.text(d, (x1, y0 - 30), f"+{fmt(data['pending'])} waiting to bank", font("Inter.ttf", 13, "SemiBold"),
               JADE_HI, "rs")
    # tube
    t.soft_glow(img, (x0, y0 - 4, x0 + (x1 - x0) * frac, y1 + 4), alpha(JADE, 90), 12, "rect")
    d = ImageDraw.Draw(img)
    rr = h / 2
    d.rounded_rectangle(P(x0 - 5, y0 - 5, x1 + 5, y1 + 5), radius=round((rr + 5) * t.S), fill=(2, 8, 10, 255),
                        outline=alpha(GOLD_DK, 255), width=round(3 * t.S))
    d.rounded_rectangle(P(x0 - 5, y0 - 5, x1 + 5, y1 + 5), radius=round((rr + 5) * t.S), outline=alpha(GOLD, 200),
                        width=max(1, round(1.1 * t.S)))
    tw, th = round((x1 - x0) * t.S), round(h * t.S)
    tube = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    fx = round(tw * frac)
    if fx > 0:
        g = Image.linear_gradient("L").rotate(90, expand=True).resize((fx, th))
        g = g.transpose(Image.FLIP_LEFT_RIGHT)
        body = Image.composite(Image.new("RGBA", (fx, th), alpha(mix(JADE, JADE_HI, 0.2), 255)),
                               Image.new("RGBA", (fx, th), alpha((14, 70, 120), 255)), g)
        # vertical shading
        sh = t.vgradient((fx, th), (255, 255, 255), (0, 0, 0))
        sh.putalpha(Image.linear_gradient("L").resize((fx, th)).point(lambda v: abs(v - 110) * 0.45))
        body.alpha_composite(sh)
        # flowing strands
        st = Image.new("RGBA", (fx, th), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        for freq, ph, a, wd in ((2.6, 0.0, 150, 1.6), (4.1, 1.7, 110, 1.2), (6.3, 3.1, 90, 1.0),
                                     (1.6, 4.2, 120, 2.2)):
            pts = [(x, th * (0.5 + 0.32 * math.sin(x / tw * 2 * math.pi * freq * 3 + ph)))
                   for x in range(0, fx + 1, max(1, t.S * 2))]
            sd.line(pts, fill=(230, 255, 250, a), width=max(1, round(wd * t.S)), joint="curve")
        body.alpha_composite(st.filter(ImageFilter.GaussianBlur(0.6 * t.S)))
        tube.alpha_composite(body)
    if pend > 0:
        pw = max(2, round(tw * pend))
        ghost = Image.new("RGBA", (pw, th), alpha(JADE, 40))
        gd = ImageDraw.Draw(ghost)
        for sx in range(-th, pw, round(9 * t.S)):
            gd.line((sx, th, sx + th, 0), fill=alpha(JADE_HI, 70), width=max(1, t.S))
        tube.alpha_composite(ghost, (fx, 0))
    m = Image.new("L", (tw, th), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, tw - 1, th - 1), radius=round(rr * t.S), fill=255)
    tube.putalpha(ImageChops.multiply(m, tube.getchannel("A")))
    img.alpha_composite(tube, P(x0, y0))
    d = ImageDraw.Draw(img)
    # bright head of the stream
    hx = x0 + (x1 - x0) * frac
    if 0 < frac < 1:
        t.soft_glow(img, (hx - 14, y0 - 8, hx + 6, y1 + 8), alpha(JADE_HI, 230), 6)
        d = ImageDraw.Draw(img)
        d.line(P(hx, y0 + 2, hx, y1 - 2), fill=(240, 255, 252), width=round(2 * t.S))
        for n in range(6):
            sx = hx + 6 + n * 7
            d.ellipse(P(sx - 1.2, (y0 + y1) / 2 - 1.2 + (n % 2) * 4 - 2, sx + 1.2, (y0 + y1) / 2 + 1.2 + (n % 2) * 4 - 2),
                      fill=alpha(JADE_HI, 200 - n * 30))
    # quarter nodes
    for q in (0.25, 0.5, 0.75):
        nx = x0 + (x1 - x0) * q
        k.gem(d, nx, y1 + 6, 4, JADE if q <= frac else DIM)
    # end caps
    for ex, side in ((x0 - 8, -1), (x1 + 8, 1)):
        k.cloud_curl(d, ex + side * 12, (y0 + y1) / 2 - 4, 9, alpha(GOLD, 255), flip=-side, width=1.8)
        k.gem(d, ex, (y0 + y1) / 2, 6, JADE)


# ── Jade tablets ──────────────────────────────────────────────────────

def tablet(img, box, icon, label, value, note, color=JADE, value_color=TXT):
    x0, y0, x1, y1 = box
    mx = (x0 + x1) / 2
    d = ImageDraw.Draw(img)
    # cord from a ring above
    ry = y0 - 26
    d.line(P(mx, ry + 5, x0 + 22, y0), fill=alpha(GOLD, 170), width=round(1.4 * t.S))
    d.line(P(mx, ry + 5, x1 - 22, y0), fill=alpha(GOLD, 170), width=round(1.4 * t.S))
    d.ellipse(P(mx - 5, ry - 5, mx + 5, ry + 5), outline=GOLD, width=round(1.6 * t.S))
    # body
    c = 14
    shape = [P(x0 + c, y0), P(x1 - c, y0), P(x1, y0 + c), P(x1, y1 - c), P(x1 - c, y1), P(x0 + c, y1), P(x0, y1 - c),
             P(x0, y0 + c)]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(shape, fill=(255, 255, 255, 255))
    m = layer.getchannel("A")
    g = t.vgradient(img.size, mix(color, INK, 0.78), mix(color, INK, 0.93), round(y0 * t.S), round(y1 * t.S))
    g.putalpha(m.point(lambda v: v * 0.94))
    img.alpha_composite(g)
    d = ImageDraw.Draw(img)
    d.line(shape + [shape[0]], fill=alpha(GOLD, 220), width=round(1.6 * t.S), joint="curve")
    inner = [P(x0 + c + 2, y0 + 5), P(x1 - c - 2, y0 + 5), P(x1 - 5, y0 + c + 2), P(x1 - 5, y1 - c - 2),
             P(x1 - c - 2, y1 - 5), P(x0 + c + 2, y1 - 5), P(x0 + 5, y1 - c - 2), P(x0 + 5, y0 + c + 2)]
    d.line(inner + [inner[0]], fill=alpha(color, 70), width=max(1, t.S))
    # icon seal on the top edge
    t.medallion(img, (mx, y0 + 2), 20, icon, color, cjk_char=False)
    d = ImageDraw.Draw(img)
    t.spaced(d, (mx, y0 + 40), label, font("Cinzel.ttf", 11, "Bold"), MUTED, 2.4, "m")
    size = 27
    while size > 16 and t.width(d, value, font("Inter.ttf", size, "Bold")) > x1 - x0 - 22:
        size -= 1
    f_v = font("Inter.ttf", size, "Bold")
    t.text(d, (mx, y0 + 76), t.fit(d, value, f_v, x1 - x0 - 20), f_v, value_color, "mm")
    if note:
        t.text(d, (mx, y0 + 108), note, font("Inter.ttf", 12, "Medium"), alpha(color, 255), "mm")
    # tassel
    ty = y1
    k.gem(d, mx, ty + 2, 4.5, color)
    for j in (-3, -1, 1, 3):
        d.line(P(mx + j, ty + 7, mx + j * 1.6, ty + 26), fill=alpha(mix(color, GOLD, 0.4), 200), width=max(1, t.S))


# ── Flow of Qi ────────────────────────────────────────────────────────

def flow(img, data, y):
    d = ImageDraw.Draw(img)
    mx = W / 2
    f = font("Cinzel.ttf", 14, "Bold")
    t.spaced(d, (mx, y), "FLOW OF QI", f, GOLD, 4, "m")
    for side in (-1, 1):
        x = mx + side * 92
        d.line(P(x, y, x + side * 140, y), fill=alpha(GOLD, 110), width=max(1, t.S))
        k.gem(d, x + side * 146, y, 4, JADE)
        k.cloud_curl(d, x + side * 4, y - 1, 6, alpha(GOLD, 255), flip=-side, width=1.4)

    active = [s for s in data["sources"] if s["active"] and s["label"] != "Pill toxicity"]
    dormant = [s for s in data["sources"] if not s["active"] and s["label"] != "Pill toxicity"]
    tox = next((s for s in data["sources"] if s["label"] == "Pill toxicity"), None)

    sx0, sx1 = 70, 900
    cy = y + 76
    # the stream: a glowing sine ribbon
    pts = [(x, cy + 7 * math.sin((x - sx0) / 70)) for x in range(sx0, 1010, 4)]
    gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(gl).line([P(*q) for q in pts], fill=alpha(JADE, 170), width=round(8 * t.S), joint="curve")
    img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(5 * t.S)))
    d = ImageDraw.Draw(img)
    d.line([P(*q) for q in pts], fill=alpha(JADE_HI, 230), width=round(1.6 * t.S), joint="curve")

    n = len(active)
    step = (sx1 - sx0) / max(1, n - 1)
    f_v = font("Inter.ttf", 17, "Bold")
    f_l = font("Cinzel.ttf", 10, "Bold")
    for i, s in enumerate(active):
        x = sx0 + step * i
        yy = cy + 7 * math.sin((x - sx0) / 70)
        if i:
            ox = x - step / 2
            oy = cy + 7 * math.sin((ox - sx0) / 70)
            op = "×" if s["value"].startswith("×") else "+"
            d.ellipse(P(ox - 10, oy - 10, ox + 10, oy + 10), fill=(4, 14, 18, 255), outline=alpha(GOLD, 200),
                      width=max(1, t.S))
            t.text(d, (ox, oy), op, font("Inter.ttf", 15, "Bold"), GOLD, "mm", shadow=False)
        t.soft_glow(img, (x - 30, yy - 30, x + 30, yy + 30), alpha(JADE, 70), 8)
        t.seal(img, (x, yy), 25, s["seal"], JADE)
        d = ImageDraw.Draw(img)
        val = s["value"].lstrip("+×") if i else s["value"]
        t.text(d, (x, cy + 46), val, f_v, TXT, "mm")
        lab = s["label"].upper()
        while len(lab) > 4 and t.width(d, lab, f_l) + 1.6 * len(lab) > step - 10:
            lab = lab.rsplit(" ", 1)[-1] if " " in lab else lab[:-1]
        t.spaced(d, (x, cy + 66), lab, f_l, MUTED, 1.6, "m")

    # result node
    rx, ry = 1076, cy
    t.soft_glow(img, (rx - 70, ry - 70, rx + 70, ry + 70), alpha(JADE, 150), 18)
    d = ImageDraw.Draw(img)
    d.ellipse(P(1010 - 11, ry - 11, 1010 + 11, ry + 11), fill=(4, 14, 18, 255), outline=alpha(GOLD, 220), width=max(1, t.S))
    t.text(d, (1010, ry), "=", font("Inter.ttf", 16, "Bold"), GOLD, "mm", shadow=False)
    for rr, col, wd in ((58, GOLD_DK, 6), (61, GOLD, 1.2), (52, alpha(JADE, 160), 1)):
        d.ellipse(P(rx - rr, ry - rr, rx + rr, ry + rr), outline=col, width=round(wd * t.S))
    inner = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(inner).ellipse(P(rx - 50, ry - 50, rx + 50, ry + 50), fill=(6, 36, 44, 240))
    img.alpha_composite(inner)
    d = ImageDraw.Draw(img)
    t.text(d, (rx, ry - 8), f"{data['rate']:,.0f}", font("Cinzel.ttf", 30, "Black"), JADE_HI, "mm")
    t.spaced(d, (rx, ry + 20), "QI / HOUR", font("Cinzel.ttf", 10, "Bold"), MUTED, 2, "m")

    # dormant line
    by = cy + 104
    x = 70
    t.spaced(d, (x, by), "DORMANT", font("Cinzel.ttf", 10, "Bold"), DIM, 2.4)
    x += 92
    f_d = font("Inter.ttf", 13, "SemiBold")
    f_h = font("Inter.ttf", 12, "Medium")
    limit = W - 330 if tox else W - 60             # stop before the toxicity meter
    hints = [s["detail"].split("·")[-1].strip() if "·" in s["detail"] else "" for s in dormant]

    def span(with_hints):
        return sum(24 + t.width(d, s["label"], f_d) + (8 + t.width(d, h, f_h) if with_hints and h else 0) + 30
                   for s, h in zip(dormant, hints))
    show_hints = x + span(True) <= limit
    for s, hint in zip(dormant, hints):
        lw = t.width(d, s["label"], f_d) + (8 + t.width(d, hint, f_h) if show_hints and hint else 0)
        if x + 24 + lw > limit:
            t.text(d, (x, by), f"+{len(dormant) - dormant.index(s)} more", f_h, DIM, "lm")
            break
        t.icon(img, s["seal"], (x + 8, by), 18, DIM)
        d = ImageDraw.Draw(img)
        t.text(d, (x + 24, by), s["label"], f_d, MUTED, "lm")
        if show_hints and hint:
            t.text(d, (x + 32 + t.width(d, s["label"], f_d), by), hint, f_h, DIM, "lm")
        x += 24 + lw + 30
    if tox:
        tv = float(tox["detail"].split("·")[0]) if tox["detail"][:1].isdigit() else 0
        warn = tox.get("warn")
        tcol = (240, 110, 90) if warn else ((226, 196, 90) if tv >= 2 else JADE)
        gx1 = W - 118
        gx0 = gx1 - 120
        t.text(d, (gx0 - 12, by), "Toxicity", f_d, MUTED, "rm")
        d.rounded_rectangle(P(gx0, by - 4, gx1, by + 4), radius=round(4 * t.S), fill=(2, 8, 10, 255),
                            outline=alpha(GOLD_DK, 255), width=max(1, t.S))
        if tv > 0:
            d.rounded_rectangle(P(gx0, by - 4, gx0 + (gx1 - gx0) * min(1, tv / 10), by + 4), radius=round(4 * t.S),
                                fill=tcol)
        t.text(d, (gx1 + 10, by), "Clean" if tv == 0 else (f"{tv:g} · {tox['value']}" if warn else f"{tv:g}"),
               font("Inter.ttf", 12, "Bold"), tcol, "lm")


# ── Card ──────────────────────────────────────────────────────────────

def render_dantian(data):
    img = background()
    frame(img)
    need = data["qi_needed"]
    frac = min(1.0, data["qi"] / need) if need else 1.0
    dantian(img, (238, 268), 138, frac, data["qi"], need)
    header(img, data, 500, 1160)
    stream_bar(img, data, (508, 190, 1150, 222))
    tw, gap = 196, 27
    rate_note = f"×{data['mult']:.2f} boosted" if data["mult"] > 1.0001 else None
    tablet(img, (504, 286, 504 + tw, 420), "flame", "QI RATE", f"{data['rate']:,.0f} / h", rate_note)
    full = data["eta"]
    ready = full == "Ready now"
    tablet(img, (504 + tw + gap, 286, 504 + 2 * tw + gap, 420), "hourglass", "FULL BAR IN", full,
           None if ready else "at your current rate", value_color=JADE_HI if ready else TXT)
    tablet(img, (504 + 2 * (tw + gap), 286, 504 + 3 * tw + 2 * gap, 420), "star", "NEXT GATE", data["gate"],
           data["gate_note"], color=(226, 196, 120))
    flow(img, data, 500)
    return t.finish(img)


