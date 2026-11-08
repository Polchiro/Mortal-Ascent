"""
Beast Fight v3 — the encounter as a page of an ancient bestiary (prototype for review; same data as
cards.battle.render_battle).

No boxes. The scene fills the card; text sits on ink-wash shading, laid out asymmetrically:
  left        the beast's character in large dry-brush calligraphy behind its name, its tier and realm, danger
              marks, an ink-brush HP stroke, and its next move written on the scene (a red brush swipe behind it
              for a charged attack)
  right       the beast, lit in its element's colour, in an atmosphere of its own (embers, snow, wisps,
              lightning, spores, dust, leaves, petals)
  top right   the turn as a round vermilion chop
  bottom      your name and brush HP stroke, your techniques as seal stamps, the last turn in two lines
Tiers are composed differently, not recoloured:
  Normal      plain ink, no ornament
  Elite       silver-gold cloud ornaments in two opposite corners, a silver name
  Beast King  a gold-leaf name and calligraphy, a fine gold border with cloud corners, a halo behind the beast
"""
import math
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import battle as B
from . import ink as K
from . import theme as T
from .beast_art import painted, spline, taper
from .theme import P, S, alpha, font, mix

W, H = 1200, 860
VERMILION = (198, 52, 38)
INK = (14, 10, 10)
PAPER = (240, 230, 210)
TIER_KEY = {"Normal": 1, "Elite": 2, "Beast King": 3, "Bandits": 1, "Master": 2}
ATMOS = {"Flame": "embers", "Frost": "snow", "Shadow": "wisps", "Thunder": "lightning", "Venom": "spores",
         "Earth": "dust", "Jade": "leaves", "Blood": "petals", "Master": "leaves", "Courtyard": "leaves"}


def _tier(data):
    tags = data["enemy"]["tags"]
    return tags[0] if tags and tags[0] in TIER_KEY else "Normal"


# ── Brush tools ───────────────────────────────────────────────────────

def _rough(poly, amount, seed):
    rng = random.Random(seed)
    return [(x + rng.uniform(-amount, amount), y + rng.uniform(-amount, amount)) for x, y in poly]


def brush_mask(size, pts, w0, w1, mid, rough=1.5, seed=3):
    """A ragged ink stroke along `pts` (card pixels) as an L mask at S×."""
    m = Image.new("L", size, 0)
    path = spline([(x * S, y * S) for x, y in pts], closed=False, n=24)
    poly = _rough(taper(path, w0 * S, w1 * S, mid * S), rough * S, seed)
    ImageDraw.Draw(m).polygon(poly, fill=255)
    grain = Image.effect_noise((size[0] // 4 + 1, size[1] // 4 + 1), 60).resize(size, Image.BILINEAR)
    streak = grain.point(lambda v: 255 if v > 70 else 150)          # dry-brush streaks
    return ImageChops.multiply(m.filter(ImageFilter.GaussianBlur(0.8 * S)), streak)


def _fill(img, mask, color, a=255):
    layer = Image.new("RGBA", img.size, color + (0,))
    layer.putalpha(mask.point(lambda v: round(v * a / 255)))
    img.alpha_composite(layer)


def ink_bar(img, x0, x1, y, h, frac, color, lost=0.0, seed=5):
    """An HP bar painted as a brush stroke: dark ink behind, the colour laid over up to `frac`, the HP just lost
    as a pale stretch after it."""
    pts = [(x0, y + 2), ((x0 + x1) / 2, y - 3), (x1, y + 1)]
    back = brush_mask(img.size, pts, h * 0.9, h * 0.55, h * 1.05, rough=1.8, seed=seed)
    _fill(img, back, INK, 235)
    front = brush_mask(img.size, pts, h * 0.72, h * 0.42, h * 0.86, rough=1.2, seed=seed + 1)
    fx = x0 + (x1 - x0) * max(0.0, min(1.0, frac))
    cut = Image.new("L", img.size, 0)
    ImageDraw.Draw(cut).rectangle(P(x0 - 20, y - h, fx, y + h), fill=255)
    if lost > 0:
        lx = min(x1 + 20, fx + (x1 - x0) * lost)
        pale = Image.new("L", img.size, 0)
        ImageDraw.Draw(pale).rectangle(P(fx, y - h, lx, y + h), fill=255)
        _fill(img, ImageChops.multiply(front, pale), (250, 236, 206), 220)
    g = T.vgradient(img.size, mix(color, (255, 250, 230), 0.35), mix(color, (0, 0, 0), 0.35),
                    round((y - h / 2) * S), round((y + h / 2) * S))
    g.putalpha(ImageChops.multiply(front, cut))
    img.alpha_composite(g)


def calligraphy(img, center, glyph, size, color, a=90, seed=9):
    """A large dry-brush character."""
    layer = Image.new("L", img.size, 0)
    ImageDraw.Draw(layer).text(P(*center), glyph, font=T.cjk(size).font_variant(size=round(size * S)), fill=255,
                               anchor="mm")
    grain = Image.effect_noise((img.size[0] // 3 + 1, img.size[1] // 3 + 1), 70).resize(img.size, Image.BILINEAR)
    m = ImageChops.multiply(layer, grain.point(lambda v: 255 if v > 60 else 110))
    _fill(img, m.filter(ImageFilter.GaussianBlur(0.6 * S)), color, a)


def chop(img, center, r, lines, color=VERMILION, rot=-6):
    """A round seal stamp with white carved text, slightly tilted and worn."""
    cx, cy = center
    size = round(2 * r * S + 8 * S)
    st = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    c = size / 2
    d.ellipse((c - r * S, c - r * S, c + r * S, c + r * S), fill=color + (235,))
    d.ellipse((c - (r - 5) * S, c - (r - 5) * S, c + (r - 5) * S, c + (r - 5) * S), outline=PAPER + (230,),
              width=round(2 * S))
    y = c - (len(lines) - 1) * 14 * S
    for text, fsize in lines:
        d.text((c, y), text, font=font("Cinzel.ttf", fsize, "Black").font_variant(size=round(fsize * S)),
               fill=PAPER + (255,), anchor="mm")
        y += 28 * S
    wear = Image.effect_noise((size, size), 80).point(lambda v: 0 if v < 40 else 255)
    st.putalpha(ImageChops.multiply(st.getchannel("A"), wear))
    st = st.rotate(rot, resample=Image.BICUBIC)
    img.alpha_composite(st, (round(cx * S - size / 2), round(cy * S - size / 2)))


def square_seal(img, center, s, icon, ready, label):
    """A technique as a square vermilion seal with its icon carved in; faded with the turns left while resting."""
    cx, cy = center
    col = VERMILION if ready else (96, 70, 64)
    size = round(s * S)
    st = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(st)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=round(5 * S), fill=col + (240,))
    d.rounded_rectangle((round(5 * S), round(5 * S), size - round(5 * S), size - round(5 * S)), radius=round(3 * S),
                        outline=PAPER + (220,), width=round(2 * S))
    wear = Image.effect_noise((size, size), 70).point(lambda v: 0 if v < 34 else 255)
    st.putalpha(ImageChops.multiply(st.getchannel("A"), wear))
    st = st.rotate(3 if ready else -2, resample=Image.BICUBIC, expand=False)
    img.alpha_composite(st, (round((cx - s / 2) * S), round((cy - s / 2) * S)))
    T.icon(img, icon, (cx, cy), s * 0.62, PAPER if ready else (170, 150, 140))
    d = ImageDraw.Draw(img)
    if not ready:
        num = "".join(ch for ch in label[1] if ch.isdigit())
        if num:
            T.text(d, (cx + s / 2 - 4, cy - s / 2 + 4), num, font("Cinzel.ttf", 26, "Black"), (255, 214, 160), "mm")
    T.text(d, (cx, cy + s / 2 + 20), T.fit(d, label[0], font("Inter.ttf", 19, "SemiBold"), 150),
           font("Inter.ttf", 19, "SemiBold"), PAPER if ready else (150, 136, 126), "mm")


# ── Atmosphere ────────────────────────────────────────────────────────

def atmosphere(img, kind, color, box, seed=4):
    x0, y0, x1, y1 = box
    rng = random.Random(seed)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    if kind == "lightning":
        for _ in range(2):
            x, y = rng.uniform(x0 + 200, x1 - 100), y0
            pts = [(x, y)]
            while y < y0 + 260:
                x += rng.uniform(-30, 30)
                y += rng.uniform(20, 40)
                pts.append((x, y))
            d.line([P(*q) for q in pts], fill=mix(color, (255, 255, 255), 0.6) + (230,), width=round(3 * S),
                   joint="curve")
        img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(4 * S)))
        img.alpha_composite(layer)
        return
    for _ in range(70):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.uniform(1.5, 4.5)
        a = rng.randint(60, 200)
        if kind == "embers":
            d.ellipse(P(x - r * 0.6, y - r, x + r * 0.6, y + r), fill=(255, rng.randint(120, 200), 60, a))
        elif kind == "snow":
            d.ellipse(P(x - r, y - r, x + r, y + r), fill=(240, 248, 255, a))
        elif kind == "wisps":
            d.ellipse(P(x - r * 6, y - r * 2, x + r * 6, y + r * 2), fill=color + (a // 4,))
        elif kind == "spores":
            d.ellipse(P(x - r, y - r, x + r, y + r), fill=mix(color, (230, 255, 160), 0.4) + (a,))
        elif kind == "dust":
            d.ellipse(P(x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7), fill=(200, 170, 120, a // 2))
        elif kind == "leaves":
            ang = rng.uniform(0, math.pi)
            dx, dy = math.cos(ang) * r * 2.4, math.sin(ang) * r * 2.4
            d.line(P(x - dx, y - dy, x + dx, y + dy), fill=mix(color, (200, 240, 200), 0.3) + (a,), width=round(r * S))
        else:   # petals
            d.ellipse(P(x - r * 1.6, y - r * 0.8, x + r * 1.6, y + r * 0.8), fill=(220, 60, 60, a))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.8 * S)))


# ── Composition ───────────────────────────────────────────────────────

def _scene(data, acc):
    size = (W * S, H * S)
    img = B._sky(acc, size, 7)
    B._moon(img, acc, size[0] * 0.66, size[1] * 0.2, size[1] * 0.09)
    (B._courtyard if data.get("backdrop") == "courtyard" else B._landscape)(img, acc, 7)
    return img


def _beast(img, data, acc, tier):
    e = data["enemy"]
    body = "master" if e["body"] == "master" else e["body"]
    bw, bh = 660, 540
    x0, y0 = 500, 640 - bh
    if tier == "Beast King":          # a halo of light behind a Beast King
        T.soft_glow(img, (x0 + 60, y0 - 40, x0 + bw - 60, y0 + bh - 40), alpha((255, 196, 90), 120), 50)
        d = ImageDraw.Draw(img)
        cx, cy = x0 + bw / 2, y0 + bh * 0.42
        for i in range(36):
            a = math.radians(i * 10)
            d.line(P(cx + 150 * math.cos(a), cy + 150 * math.sin(a), cx + 300 * math.cos(a), cy + 300 * math.sin(a)),
                   fill=(255, 220, 140, 40), width=round(3 * S))
    art = B._art(e.get("slug")) or painted(body, data["palette"], bw * S, bh * S)
    if art is None:
        art = Image.new("RGBA", (bw * S, bh * S), (0, 0, 0, 0))
        B._creature(art, acc, body, None)
    elif art.size != (bw * S, bh * S):
        sc = min(bw * S / art.size[0], bh * S / art.size[1])
        art = art.resize((round(art.size[0] * sc), round(art.size[1] * sc)), Image.LANCZOS)
    mask = art.getchannel("A")
    rim = Image.new("RGBA", art.size, acc.rim + (0,))
    rim.putalpha(mask.filter(ImageFilter.GaussianBlur(10 * S)).point(lambda v: min(255, round(v * 1.2))))
    ox, oy = round(x0 * S + (bw * S - art.size[0]) / 2), round(y0 * S + (bh * S - art.size[1]))
    img.alpha_composite(rim, (ox, oy))
    img.alpha_composite(art, (ox, oy))


def _wash(img):
    """Ink-wash shading where the text sits: from the left edge, and up from the bottom."""
    w, h = img.size
    left = Image.linear_gradient("L").rotate(90, expand=True).resize((w, h))     # 255 at left → 0 at right
    left = left.point(lambda v: round(max(0, v - 90) * 1.35))
    bottom = Image.linear_gradient("L").resize((w, h))                              # 0 top → 255 bottom
    bottom = bottom.point(lambda v: round(min(255, max(0, v - 128) * 2.6)))
    m = ImageChops.lighter(left, bottom)
    _fill(img, m.filter(ImageFilter.GaussianBlur(20 * S)), (8, 6, 8), 235)


def _ornaments(img, tier, color):
    d = ImageDraw.Draw(img)
    gold = (226, 196, 120)
    if tier == "Beast King":
        for inset, wdt, a in ((14, 2.2, 230), (20, 1, 150)):
            d.rectangle(P(inset, inset, W - inset, H - inset), outline=gold + (a,), width=round(wdt * S))
        corners = ((14, 14, 1, 1), (W - 14, 14, -1, 1), (14, H - 14, 1, -1), (W - 14, H - 14, -1, -1))
    elif tier == "Elite":
        corners = ((14, 14, 1, 1), (W - 14, H - 14, -1, -1))
        silver = (206, 210, 226)
        for cx, cy, fx, fy in corners:
            d.line(P(cx, cy, cx + fx * 120, cy), fill=silver + (200,), width=round(2 * S))
            d.line(P(cx, cy, cx, cy + fy * 120), fill=silver + (200,), width=round(2 * S))
        gold = silver
    else:
        return
    for cx, cy, fx, fy in corners:
        K.cloud_curl(d, cx + fx * 26, cy + fy * 26, 16, gold + (255,), flip=fx, width=2.6)
        K.cloud_curl(d, cx + fx * 54, cy + fy * 14, 9, gold + (220,), flip=fx, width=2)
        K.cloud_curl(d, cx + fx * 14, cy + fy * 54, 9, gold + (220,), flip=fx, width=2)


def _title(img, data, acc, tier):
    e = data["enemy"]
    king = tier == "Beast King"
    gold = (236, 200, 120)
    ch = B.seal_char(e["name"], e["body"]) if e["body"] != "master" else "师"
    calligraphy(img, (190, 210), ch, 330, gold if king else mix(acc.rim, (255, 255, 255), 0.2), 70 if king else 55)
    # the name, up to two lines, left aligned
    words = e["name"].upper().split()
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 64, "Black")
    lines, cur = [], ""
    for wd in words:
        trial = (cur + " " + wd).strip()
        if T.width(d, trial, f) > 520 and cur:
            lines.append(cur)
            cur = wd
        else:
            cur = trial
    lines.append(cur)
    if len(lines) > 2:
        lines = [lines[0], " ".join(lines[1:])]
    y = 96
    for line in lines:
        line, lf = B._shrink(d, line, "Cinzel.ttf", "Black", (64, 56, 48), 540)
        if king:
            T.gold_text(img, (50, y), line, lf, "lm", glow=(255, 150, 60))
        elif tier == "Elite":
            T.gold_text(img, (50, y), line, lf, "lm", top=(244, 246, 255), bottom=(150, 156, 180), glow=None)
        else:
            T.text(ImageDraw.Draw(img), (50, y), line, lf, PAPER, "lm")
        y += 66
    # brush underline
    _fill(img, brush_mask(img.size, [(46, y - 22), (260, y - 28), (430, y - 20)], 6, 1, 9, seed=11),
          VERMILION if not king else (230, 170, 70), 230)
    d = ImageDraw.Draw(img)
    # tier and realm, then danger marks; role and element under
    realm = e["tags"][-1] if len(e["tags"]) > 1 else ""
    tline = f"{tier.upper()}  ·  {realm.upper()}" if realm else tier.upper()
    T.spaced(d, (52, y + 2), tline, font("Cinzel.ttf", 22, "Bold"), mix(PAPER, acc.rim, 0.2), 2.4)
    tw = sum(T.width(d, c, font("Cinzel.ttf", 22, "Bold")) for c in tline) + 2.4 * len(tline)
    for i in range(3):
        on = i < TIER_KEY.get(tier, 1)
        x = 52 + tw + 24 + i * 24
        _fill(img, brush_mask(img.size, [(x - 6, y + 10), (x, y - 6), (x + 6, y - 10)], 7, 2, 9, seed=20 + i),
              VERMILION if on else (70, 60, 56), 255 if on else 160)
    d = ImageDraw.Draw(img)
    traits = " · ".join(t for t in e["tags"][1:-1])
    stats = f"ATK {e['atk']:,}  ·  DEF {e['def']:,}" if e.get("atk") else ""
    T.text(d, (52, y + 38), "   ".join(s for s in (traits, stats) if s), font("Inter.ttf", 22, "SemiBold"),
           mix(PAPER, (0, 0, 0), 0.2), "lm")
    return y + 96


def _hp(img, data, acc, y):
    e = data["enemy"]
    mx = e["max_hp"] or 1
    ink_bar(img, 50, 520, y + 30, 30, e["hp"] / mx, acc.hp, lost=max(0, -e.get("delta", 0)) / mx)
    d = ImageDraw.Draw(img)
    T.text(d, (52, y - 6), e.get("bar_label") or f"{e['hp']:,}", font("Cinzel.ttf", 40, "Black"), PAPER, "lm")
    if not e.get("bar_label"):
        nw = T.width(d, f"{e['hp']:,}", font("Cinzel.ttf", 40, "Black"))
        T.text(d, (60 + nw, y + 2), f"/ {e['max_hp']:,} HP", font("Inter.ttf", 22, "SemiBold"), T.ASH, "lm")
    if e.get("delta", 0) < 0:
        B._damage(img, (520, y - 6), e["delta"], (255, 214, 120), anchor="rm", big=-e["delta"] >= 0.2 * mx)
    return y + 70


def _intent(img, data, acc, y):
    head, hint = data["warning"]
    if not head:
        return
    danger = data.get("danger")
    if danger:
        _fill(img, brush_mask(img.size, [(36, y + 34), (300, y + 22), (560, y + 30)], 70, 30, 86, rough=3, seed=31),
              (150, 24, 20), 215)
        d = ImageDraw.Draw(img)
        T.spaced(d, (52, y - 8), "POWERFUL ATTACK" if danger == "charged" else "SIGNATURE MOVE",
                 font("Cinzel.ttf", 20, "Black"), (255, 196, 150), 3)
    else:
        _fill(img, brush_mask(img.size, [(40, y + 10), (44, y + 40), (40, y + 64)], 5, 2, 6, seed=33), VERMILION, 230)
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 27, "Bold")
    lines = T.wrap(d, head, f, 480, lines=2)
    for i, line in enumerate(lines):
        T.text(d, (60, y + 22 + i * 32), line, f, (255, 246, 230), "lm")
    hf = font("Inter.ttf", 20, "Medium")
    T.text(d, (60, y + 22 + len(lines) * 32 + 4), T.fit(d, hint, hf, 480), hf, (226, 210, 190), "lm")


def _turn(img, data):
    if data.get("result"):
        return
    chop(img, (1118, 82), 52, [(data.get("turn_label") or f"TURN {data['turn']}", 17),
                               (data.get("seconds_label") or f"{data['seconds']}s", 22)])
    d = ImageDraw.Draw(img)
    y = 168
    for label in data["enemy"]["statuses"][:3]:
        T.spaced(d, (W - 40, y), label.upper(), font("Cinzel.ttf", 18, "Black"), (255, 214, 170), 2.4, "r")
        y += 30


def _player(img, data, acc):
    members = data["party"]
    if len(members) > 1:
        return _party(img, data, acc)
    m = members[0]
    low, color = B._bar_color(m)
    d = ImageDraw.Draw(img)
    T.text(d, (50, 650), m["name"], font("Cinzel.ttf", 34, "Black"), (240, 96, 80) if low else PAPER, "lm")
    nw = T.width(d, m["name"], font("Cinzel.ttf", 34, "Black"))
    T.text(d, (66 + nw, 654), f"{m['realm']} {m['layer']}", font("Inter.ttf", 20, "SemiBold"), T.ASH, "lm")
    ink_bar(img, 50, 560, 700, 26, m["hp"] / m["max_hp"] if m["max_hp"] else 0, color, seed=41)
    d = ImageDraw.Draw(img)
    T.text(d, (572, 700), m.get("bar_label") or f"{m['hp']:,} / {m['max_hp']:,}", font("Inter.ttf", 22, "Bold"),
           PAPER, "lm")
    if m.get("delta"):
        B._damage(img, (560, 650), m["delta"], (236, 80, 70) if m["delta"] < 0 else (110, 230, 160), anchor="rm")
    items = data.get("loadout", [])[:3]
    for i, it in enumerate(items):
        square_seal(img, (790 + i * 140, 676), 74, it["seal"], it["ready"], (it["name"], it["state"]))


def _party(img, data, acc):
    members = data["party"][:6]
    cols = 2 if len(members) > 3 else 1
    rows = math.ceil(len(members) / cols)
    for i, m in enumerate(members):
        c, r = i // rows, i % rows
        x, y = 50 + c * 560, 640 + r * 42
        low, color = B._bar_color(m)
        d = ImageDraw.Draw(img)
        mark = "› " if m.get("arrow") else ""
        T.text(d, (x, y), T.fit(d, mark + m["name"], font("Inter.ttf", 22, "Bold"), 160), font("Inter.ttf", 22, "Bold"),
               (240, 96, 80) if low or m.get("ko") else PAPER, "lm")
        ink_bar(img, x + 180, x + 450, y + 2, 18, m["hp"] / m["max_hp"] if m["max_hp"] else 0, color, seed=50 + i)
        d = ImageDraw.Draw(img)
        T.text(d, (x + 462, y + 2), "KO" if m.get("ko") else f"{m['hp']:,}", font("Inter.ttf", 19, "Bold"), PAPER, "lm")


def _log(img, data):
    events = list(data.get("log") or [])[-2:]
    y = 790 if len(data["party"]) == 1 else 800
    for i, (kind, text) in enumerate(events):
        _fill(img, brush_mask(img.size, [(50, y + i * 34 - 4), (56, y + i * 34), (62, y + i * 34 + 4)], 6, 2, 8,
                              seed=60 + i), VERMILION, 230)
        B._log_line(img, 64, y + i * 34, kind, text, 1080, 23)


def _result(img, data, tier):
    label, color = B.RESULT.get(data["result"], (str(data["result"]).upper(), K.GOLD))
    _fill(img, brush_mask(img.size, [(560, 470), (840, 452), (1150, 466)], 110, 50, 130, rough=4, seed=71),
          (10, 8, 8), 220)
    T.gold_text(img, (850, 446), label, font("Cinzel.ttf", 84, "Black"), "mm",
                top=mix(color, (255, 255, 255), 0.55), bottom=mix(color, (0, 0, 0), 0.25), glow=alpha(color, 160))
    if data["result"] == "won" and tier in ("Elite", "Beast King"):
        d = ImageDraw.Draw(img)
        T.spaced(d, (850, 510), "BEAST KING SLAIN" if tier == "Beast King" else "ELITE SLAIN",
                 font("Cinzel.ttf", 24, "Black"), mix(color, (255, 255, 255), 0.4), 4, "m")


def render_beast_fight(data):
    acc = T.ELEMENT_ACCENTS[data["palette"]]
    tier = _tier(data)
    img = _scene(data, acc)
    atmosphere(img, ATMOS.get(data["palette"], "dust"), acc.rim, (0, 0, W, 600))
    _beast(img, data, acc, tier)
    _wash(img)
    y = _title(img, data, acc, tier)
    y = _hp(img, data, acc, y)
    if data.get("result"):
        _result(img, data, tier)
    else:
        _intent(img, data, acc, y + 6)
        _turn(img, data)
    _player(img, data, acc)
    _log(img, data)
    _ornaments(img, tier, acc.rim)
    d = ImageDraw.Draw(img)
    d.rectangle(P(0, 0, W - 1, H - 1), outline=(0, 0, 0, 255), width=round(3 * S))
    return T.finish(img)
