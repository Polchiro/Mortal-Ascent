"""
Beast Fight v4 — a cinematic encounter (prototype for review; same data as cards.battle.render_battle).

Art direction
  Low-key lighting. The beast stands mostly in shadow, lit by a strong rim of its element's colour from behind;
  only its eyes, fangs and flames keep their full light. Misty ridges drawn from soft noise (no geometric
  mountains, no moon), drifting particles of its element, ground fog over its feet.
  Two typefaces only: Cinzel for the beast's name and the result word, Inter for everything else.
  No boxes, no corner ornaments: the scene runs edge to edge and text sits on soft shade.

Composition by kind of beast (cards.beast_fight.STAGING)
  predators (cats, wolves)  close and low, leaning out of the right edge
  dragons and serpents      large and rising, mist streaming past
  giants (apes, turtles)    filling the lower half, seen from below
  winged (birds, insects)   high in the frame, wings wide
  dark beasts (Shadow)      deep fog, almost only the eyes and the rim
  Beast Kings               a column of light behind them, a gold-leaf name

Layout
  top left     tier · realm, the name, role · element, ATK / DEF
  under it     the HP bar of the Profile card with the HP % beside it
  top right    the turn and the seconds left
  lower left   the beast's next move (red, with POWERFUL ATTACK, when it is charging)
  bottom       you: name, HP bar with %, the last turn; your techniques as medallions with full names
  result       the scene dims; the outcome, then the fight in numbers (turns, damage dealt, damage taken, HP left)
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import battle as B
from . import ink as K
from . import theme as T
from .beast_art import painted
from .theme import P, S, alpha, font, mix

W, H = 1200, 820
SCENE_H = 620
WARM = (244, 236, 222)
MUTED = (176, 166, 156)
DIM = (120, 112, 106)
DANGER = (226, 70, 52)
TIER_LABEL_COLOR = {"Normal": (176, 166, 156), "Elite": (206, 212, 232), "Beast King": (236, 198, 120),
                    "Bandits": (214, 120, 96), "Master": (186, 206, 236)}
ATMOS = {"Flame": "embers", "Frost": "snow", "Shadow": "wisps", "Thunder": "sparks", "Venom": "spores",
         "Earth": "dust", "Jade": "motes", "Blood": "ash", "Master": "motes"}

# body -> (kind, width, height, centre x, feet y): where and how big the beast stands
STAGING = {
    "cat": ("predator", 760, 560, 800, 690), "wolf": ("predator", 720, 540, 810, 680),
    "dragon": ("dragon", 760, 500, 850, 690), "serpent": ("dragon", 680, 500, 850, 680),
    "ape": ("giant", 820, 620, 790, 700), "turtle": ("giant", 900, 560, 780, 700),
    "bird": ("winged", 820, 520, 790, 560), "insect": ("winged", 720, 520, 800, 640),
    "human": ("predator", 560, 600, 820, 660), "master": ("master", 640, 560, 800, 650),
}


def _tier(data):
    tags = data["enemy"]["tags"]
    return tags[0] if tags and tags[0] in TIER_LABEL_COLOR else "Normal"


def _fill(img, mask, color, a=255):
    layer = Image.new("RGBA", img.size, color + (0,))
    layer.putalpha(mask.point(lambda v: round(v * a / 255)))
    img.alpha_composite(layer)


# ── The world behind the beast ────────────────────────────────────────

def _ridge(w, base, amp, seed, rough=1.0):
    """A soft mountain line from summed waves (organic, never triangular)."""
    rng = random.Random(seed)
    waves = [(rng.uniform(0.6, 1.4) / f, rng.uniform(0, 6.3), f) for f in (380, 170, 70, 28)]
    pts = []
    for x in range(0, w + 8, 8):
        y = base
        for amp_k, ph, f in waves:
            y -= amp * amp_k * math.sin(x / f + ph) * (0.6 if f < 60 else 1) * (rough if f < 60 else 1) * 0.6
        pts.append((x, y))
    return pts


def _world(data, acc, kind, seed=7):
    w, h = W * S, H * S
    sky = acc.sky if hasattr(acc, "sky") else ((10, 8, 12), (40, 30, 30))
    img = T.vgradient((w, h), mix(sky[0], (0, 0, 0), 0.25), mix(sky[1], (0, 0, 0), 0.15), 0, SCENE_H * S)
    # a large soft light low in the sky, behind where the beast stands (the backlight)
    _, bw, bh, cx, feet = STAGING.get(data["enemy"]["body"], STAGING["cat"])
    T.soft_glow(img, (cx - 380, feet - bh - 40, cx + 380, feet + 40), alpha(mix(acc.rim, acc.moon, 0.4), 120), 90)
    # misty ridges, far to near: each darker and sharper
    for i, (base, amp, a, blur) in enumerate(((330, 70, 90, 6), (410, 60, 150, 4), (500, 45, 210, 2.5))):
        m = Image.new("L", (w, h), 0)
        pts = [(x * S, y * S) for x, y in _ridge(W, base, amp, seed + i)] + [(w, h), (0, h)]
        ImageDraw.Draw(m).polygon(pts, fill=255)
        col = mix(sky[1], (0, 0, 0), 0.35 + 0.18 * i)
        _fill(img, m.filter(ImageFilter.GaussianBlur(blur * S)), col, a)
        # mist pooled in the valley below each ridge
        mist = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mist).rectangle((0, round((base + 30) * S), w, round((base + 90) * S)), fill=255)
        _fill(img, mist.filter(ImageFilter.GaussianBlur(40 * S)), mix(acc.mist, (255, 255, 255), 0.1), 34 - 8 * i)
    if data.get("palette") == "Master":       # the training hall: warm lantern lights far off
        rng = random.Random(3)
        for _ in range(12):
            x, y = rng.uniform(40, 700), rng.uniform(300, 520)
            T.soft_glow(img, (x - 10, y - 10, x + 10, y + 10), (255, 170, 80, 120), 6)
    return img


def _particles(img, kind, color, seed=4):
    rng = random.Random(seed)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(90):
        x, y = rng.uniform(0, W), rng.uniform(0, SCENE_H)
        r = rng.uniform(1, 3.2)
        a = rng.randint(50, 190)
        if kind == "embers":
            c = (255, rng.randint(110, 190), 60)
        elif kind == "snow":
            c = (236, 244, 255)
        elif kind == "ash":
            c = (200, 120, 110)
        elif kind == "sparks":
            c = mix(color, (255, 255, 255), 0.5)
            d.line(P(x, y, x + rng.uniform(-6, 6), y + rng.uniform(4, 10)), fill=c + (a,), width=round(1.4 * S))
            continue
        elif kind == "wisps":
            d.ellipse(P(x - r * 8, y - r * 2, x + r * 8, y + r * 2), fill=color + (a // 5,))
            continue
        else:
            c = mix(color, (255, 255, 255), 0.35)
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=c + (a,))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(0.7 * S)))


# ── The beast, lit from behind ────────────────────────────────────────

def _art_for(e, palette, bw, bh):
    """(image at S×, is_real_art). Real art (art/beasts/<slug>.png) keeps more of its own light."""
    art = B._art(e.get("slug"))
    real = art is not None
    if art is None:
        art = painted("master" if e["body"] == "master" else e["body"], palette, bw * S, bh * S)
    if art is None:
        art = Image.new("RGBA", (bw * S, bh * S), (0, 0, 0, 0))
        B._creature(art, T.ELEMENT_ACCENTS[palette], e["body"], None)
        bbox = art.getchannel("A").getbbox()
        if bbox:
            art = art.crop(bbox)
    sc = min(bw * S / art.size[0], bh * S / art.size[1])
    art = art.resize((max(1, round(art.size[0] * sc)), max(1, round(art.size[1] * sc))), Image.LANCZOS)
    return art, real


def _light(art, acc, real, dark):
    """Low-key lighting: shadow over the body, the brightest bits (eyes, fangs, flame) kept, a rim of light."""
    mask = art.getchannel("A")
    lum = art.convert("L")
    if not real:
        shade = Image.new("RGBA", art.size, mix(acc.panel, (0, 0, 0), 0.4) + (0,))
        shade.putalpha(mask.point(lambda v: round(v * dark)))
        lit = art.copy()
        lit.alpha_composite(shade)
        # light falls from the top: the upper body keeps more of its colour
        grad = Image.linear_gradient("L").resize(art.size).point(lambda v: round(v * 0.55))
        under = Image.new("RGBA", art.size, (0, 0, 0, 0))
        under.putalpha(ImageChops.multiply(grad, mask))
        lit.alpha_composite(under)
        keep = lum.point(lambda v: 255 if v > 205 else 0).filter(ImageFilter.GaussianBlur(1))
        keep = ImageChops.multiply(keep, mask)
        bright = art.copy()
        bright.putalpha(keep)
        lit.alpha_composite(bright)
        art = lit
    k = max(3, round(min(art.size) * 0.012))
    if real:      # light only the solid body: faint dust and smoke in painted art would get pale streaks
        mask = mask.point(lambda v: 255 if v > 200 else 0).filter(ImageFilter.MinFilter(3))
    rim = ImageChops.subtract(mask, ImageChops.offset(mask, -k, k // 2))         # light from behind, upper right
    rim = rim.filter(ImageFilter.GaussianBlur(k * 0.6))
    out = Image.new("RGBA", art.size, (0, 0, 0, 0))
    halo = Image.new("RGBA", art.size, acc.rim + (0,))
    halo.putalpha(mask.filter(ImageFilter.GaussianBlur(k * 3)).point(lambda v: round(v * 0.5)))
    out.alpha_composite(halo)
    out.alpha_composite(art)
    edge = Image.new("RGBA", art.size, mix(acc.rim, (255, 255, 255), 0.45) + (0,))
    edge.putalpha(rim.point(lambda v: min(255, round(v * (1.2 if real else 2.2)))))
    out.alpha_composite(edge)
    return out


def _beast(img, data, acc, tier):
    e = data["enemy"]
    kind, bw, bh, cx, feet = STAGING.get(e["body"], STAGING["cat"])
    if e["body"] != "master" and data["palette"] == "Shadow":
        kind = "dark"
    if tier == "Beast King":
        bw, bh = round(bw * 1.06), round(bh * 1.06)
        col = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(col).polygon(P(cx - 90, 0, cx + 90, 0, cx + 260, feet, cx - 260, feet), fill=(255, 220, 150, 60))
        img.alpha_composite(col.filter(ImageFilter.GaussianBlur(30 * S)))
    art, real = _art_for(e, data["palette"], bw, bh)
    dark = {"dark": 0.82, "giant": 0.62, "dragon": 0.52, "predator": 0.58, "winged": 0.55, "master": 0.3}.get(kind, 0.55)
    art = _light(art, acc, real, dark)
    x = round(cx * S - art.size[0] / 2)
    y = round(feet * S - art.size[1])
    img.alpha_composite(art, (x, y))
    # ground fog over the feet
    fog = Image.new("L", img.size, 0)
    ImageDraw.Draw(fog).ellipse(P(cx - bw * 0.7, feet - 60, cx + bw * 0.7, feet + 70), fill=255)
    _fill(img, fog.filter(ImageFilter.GaussianBlur(26 * S)), mix(acc.mist, (20, 18, 20), 0.55), 200)
    if kind == "dark":
        veil = Image.new("L", img.size, 0)
        ImageDraw.Draw(veil).ellipse(P(cx - bw * 0.6, feet - bh * 0.7, cx + bw * 0.6, feet + 40), fill=255)
        _fill(img, veil.filter(ImageFilter.GaussianBlur(60 * S)), (6, 4, 10), 110)
    if kind == "dragon":
        streak = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(streak)
        rng = random.Random(8)
        for _ in range(7):
            y0 = rng.uniform(120, 520)
            sd.line(P(cx - 520, y0, cx + 420, y0 - 60), fill=acc.mist + (40,), width=round(rng.uniform(8, 22) * S))
        img.alpha_composite(streak.filter(ImageFilter.GaussianBlur(14 * S)))
    return cx, feet - bh * 0.6


# ── Type and bars ─────────────────────────────────────────────────────

def _shade_left(img):
    """Soft darkness behind the text on the left and along the bottom (no boxes)."""
    w, h = img.size
    left = Image.linear_gradient("L").rotate(90, expand=True).resize((w, h)).point(lambda v: round(max(0, v - 110) * 1.7))
    bottom = Image.linear_gradient("L").resize((w, h)).point(lambda v: round(min(255, max(0, v - 150) * 3)))
    _fill(img, ImageChops.lighter(left, bottom).filter(ImageFilter.GaussianBlur(24 * S)), (6, 5, 7), 230)


def _spaced(d, xy, s, size, color, anchor="l", weight="SemiBold", tracking=2.0):
    T.spaced(d, xy, s, font("Inter.ttf", size, weight), color, tracking, anchor)


def _hp(img, x0, x1, y, h, hp, mx, color, icon, label=None, delta=0):
    """The Profile's ornate bar, with the HP % in large type after it."""
    frac = hp / mx if mx else 0
    K.ornate_bar(img, (x0 + 18, y - h / 2, x1, y + h / 2), frac, color, icon, label or f"{hp:,} / {mx:,}")
    d = ImageDraw.Draw(img)
    T.text(d, (x1 + 46, y + 1), f"{frac:.0%}" if label is None else "", font("Inter.ttf", round(h * 0.95), "Black"),
           WARM, "lm")
    if delta:
        T.text(d, (x1 - 6, y - h / 2 - 22), f"−{-delta:,}" if delta < 0 else f"+{delta:,}", font("Inter.ttf", 28, "Black"),
               (255, 120, 96) if delta < 0 else (130, 230, 170), "rm")


def _identity(img, data, acc, tier):
    e = data["enemy"]
    d = ImageDraw.Draw(img)
    realm = e["tags"][-1] if len(e["tags"]) > 1 else ""
    label_col = TIER_LABEL_COLOR.get(tier, MUTED)
    is_tier = bool(e["tags"]) and e["tags"][0] in TIER_LABEL_COLOR
    line = (f"{tier.upper()}   ·   {realm.upper()}" if realm else tier.upper()) if is_tier else \
        "   ·   ".join(t.upper() for t in e["tags"])          # training: the challenge, its tier, the mode
    _spaced(d, (48, 56), line, 18, label_col, weight="Bold", tracking=3.2)
    if tier in ("Elite", "Beast King"):
        tw = T.width(d, tier.upper(), font("Inter.ttf", 18, "Bold")) + 3.2 * len(tier)
        d.line(P(48, 72, 48 + tw, 72), fill=label_col + (200,), width=round(1.5 * S))
    name, nf = B._shrink(d, e["name"], "Cinzel.ttf", "Bold", (62, 54, 46, 40), 640)
    if tier == "Beast King":
        T.gold_text(img, (46, 124), name, nf, "lm", top=(255, 236, 190), bottom=(196, 146, 70))
    else:
        T.text(d, (46, 124), name, nf, WARM, "lm")
    d = ImageDraw.Draw(img)
    traits = " · ".join(e["tags"][1:-1]) if is_tier else ""
    x = 48
    f = font("Inter.ttf", 22, "Medium")
    if traits:
        T.text(d, (x, 178), traits, f, MUTED, "lm")
        x += T.width(d, traits, f) + 30
    if e.get("atk"):
        for icon, val, col in (("sword", e["atk"], (236, 170, 110)), ("shield", e["def"], (150, 186, 236))):
            T.icon(img, icon, (x + 10, 178), 22, col)
            d = ImageDraw.Draw(img)
            T.text(d, (x + 28, 178), f"{val:,}", font("Inter.ttf", 22, "Bold"), WARM, "lm")
            x += 28 + T.width(d, f"{val:,}", font("Inter.ttf", 22, "Bold")) + 26
    _hp(img, 48, 600, 232, 34, e["hp"], e["max_hp"], acc.hp, e["element_seal"], e.get("bar_label"), e.get("delta", 0))


def _corner(img, data):
    if data.get("result"):
        return
    d = ImageDraw.Draw(img)
    T.text(d, (W - 48, 62), data.get("turn_label") or f"Turn {data['turn']}", font("Inter.ttf", 30, "Black"), WARM, "rm")
    sec = data.get("seconds_label") or f"{data['seconds']}s to act"
    T.text(d, (W - 48, 98), sec, font("Inter.ttf", 20, "SemiBold"), MUTED, "rm")
    y = 140
    for label in data["enemy"]["statuses"][:3]:
        _spaced(d, (W - 48, y), label.upper(), 16, (255, 196, 160), "r", "Bold", 2.4)
        y += 28


def _intent(img, data, acc):
    head, hint = data["warning"]
    if not head:
        return
    danger = data.get("danger")
    d = ImageDraw.Draw(img)
    y = 420
    col = DANGER if danger else mix(acc.rim, (255, 255, 255), 0.35)
    if danger:
        T.soft_glow(img, (20, y - 30, 560, y + 90), (160, 20, 10, 120), 30)
        d = ImageDraw.Draw(img)
    d.line(P(48, y - 12, 48, y + 70), fill=col, width=round(4 * S))
    label = {"charged": "POWERFUL ATTACK", "signature": "SIGNATURE MOVE"}.get(danger, "NEXT MOVE")
    _spaced(d, (66, y - 2), label, 16, col, weight="Black", tracking=3)
    f = font("Inter.ttf", 26, "Bold")
    for i, line in enumerate(T.wrap(d, head, f, 500, lines=2)):
        T.text(d, (66, y + 30 + i * 32), line, f, WARM, "lm")


# ── You ───────────────────────────────────────────────────────────────

def _you(img, data, acc):
    members = data["party"]
    d = ImageDraw.Draw(img)
    if len(members) > 1:
        return _party(img, data)
    m = members[0]
    low, color = B._bar_color(m)
    T.text(d, (48, 664), m["name"], font("Inter.ttf", 30, "Black"), (246, 110, 92) if low else WARM, "lm")
    nw = T.width(d, m["name"], font("Inter.ttf", 30, "Black"))
    T.text(d, (62 + nw, 666), f"{m['realm']} {m['layer']}", font("Inter.ttf", 20, "Medium"), MUTED, "lm")
    _hp(img, 48, 560, 716, 32, m["hp"], m["max_hp"], color, "star" if m.get("bar_label") else "heart",
        m.get("bar_label"), m.get("delta", 0))
    events = list(data.get("log") or [])[-2:]
    for i, (kind, text) in enumerate(events):
        B._log_line(img, 44, 766 + i * 30, kind, text, 640, 20)
    _moves(img, data.get("loadout", [])[:3])


def _moves(img, items):
    """Techniques and pills as medallions: lit when ready, dark with the turns left; names in full (2 lines)."""
    if not items:
        return
    xs = [790, 920, 1050][:len(items)] if len(items) == 3 else [860, 1010, 1130][:len(items)]
    cy = 702
    for x, it in zip(xs, items):
        col = it["color"] or K.GOLD
        ready = it["ready"]
        r = 40
        d = ImageDraw.Draw(img)
        d.ellipse(P(x - r, cy - r, x + r, cy + r), fill=(12, 10, 12, 255),
                  outline=mix(col, (255, 255, 255), 0.3) if ready else (70, 64, 60), width=round(2.5 * S))
        if ready:
            core = Image.radial_gradient("L").resize(P(2 * r - 10, 2 * r - 10))
            ci = Image.composite(Image.new("RGBA", core.size, (12, 10, 12, 255)),
                                 Image.new("RGBA", core.size, alpha(mix(col, (0, 0, 0), 0.3), 255)), core)
            cm = Image.new("L", core.size, 0)
            ImageDraw.Draw(cm).ellipse((0, 0, core.size[0] - 1, core.size[1] - 1), fill=255)
            ci.putalpha(cm)
            img.alpha_composite(ci, P(x - r + 5, cy - r + 5))
        T.icon(img, it["seal"], (x, cy), 50, (250, 246, 236) if ready else (96, 90, 86))
        d = ImageDraw.Draw(img)
        if not ready:
            num = "".join(ch for ch in it["state"] if ch.isdigit())
            T.text(d, (x, cy), num or "—", font("Inter.ttf", 34, "Black"), (236, 206, 160), "mm")
        f = font("Inter.ttf", 17, "SemiBold")
        lines = T.wrap(d, it["name"], f, 124, lines=2)
        for j, line in enumerate(lines):
            T.text(d, (x, cy + r + 18 + j * 20), line, f, WARM if ready else DIM, "mm")
        if ready and it["state"] not in ("Ready", ""):     # pill count, or a training counter
            T.text(d, (x + r - 2, cy - r + 6), it["state"], font("Inter.ttf", 16, "Black"), (246, 214, 150), "mm")


def _party(img, data):
    members = data["party"][:6]
    cols = 2 if len(members) > 3 else 1
    rows = math.ceil(len(members) / cols)
    for i, m in enumerate(members):
        c, r = i // rows, i % rows
        x, y = 48 + c * 570, 662 + r * 46
        low, color = B._bar_color(m)
        d = ImageDraw.Draw(img)
        T.text(d, (x, y), T.fit(d, ("› " if m.get("arrow") else "") + m["name"], font("Inter.ttf", 22, "Bold"), 170),
               font("Inter.ttf", 22, "Bold"), (246, 110, 92) if low or m.get("ko") else WARM, "lm")
        frac = m["hp"] / m["max_hp"] if m["max_hp"] else 0
        T.bar(img, (x + 190, y - 14, x + 520, y + 14), frac, color, "KO" if m.get("ko") else f"{m['hp']:,} / {m['max_hp']:,}")


# ── Result ────────────────────────────────────────────────────────────

def _result(img, data, acc, tier):
    label, color = B.RESULT.get(data["result"], (str(data["result"]).upper(), K.GOLD))
    label = label.title() if label != "IT GOT AWAY" else "It got away"
    veil = Image.new("RGBA", img.size, (4, 3, 5, 150))
    img.alpha_composite(veil)
    T.soft_glow(img, (W / 2 - 420, 160, W / 2 + 420, 460), alpha(color, 70), 70)
    d = ImageDraw.Draw(img)
    e, m = data["enemy"], data["party"][0]
    won = data["result"] == "won"
    sub = (f"{e['name']} slain" if won else f"Defeated by the {e['name']}" if data["result"] == "lost"
           else e["name"])
    if won and tier in ("Elite", "Beast King"):
        _spaced(d, (W / 2, 210), ("BEAST KING" if tier == "Beast King" else "ELITE") + " · " + (e["tags"][-1] or "").upper(),
                18, TIER_LABEL_COLOR[tier], "m", "Bold", 4)
    T.gold_text(img, (W / 2, 290), label, font("Cinzel.ttf", 92, "Bold"), "mm",
                top=mix(color, (255, 255, 255), 0.6), bottom=mix(color, (0, 0, 0), 0.2))
    d = ImageDraw.Draw(img)
    T.text(d, (W / 2, 370), sub, font("Inter.ttf", 26, "Medium"), MUTED, "mm")
    dealt = max(0, e["max_hp"] - e["hp"])
    taken = max(0, m["max_hp"] - m["hp"])
    stats = [("Turns", f"{data['turn']}"), ("Damage dealt", f"{dealt:,}"), ("Damage taken", f"{taken:,}"),
             ("HP left", f"{m['hp'] / m['max_hp']:.0%}" if m["max_hp"] else "—")]
    cw = 220
    x0 = W / 2 - cw * len(stats) / 2
    for i, (k, v) in enumerate(stats):
        cx = x0 + cw * (i + 0.5)
        T.text(d, (cx, 450), v, font("Inter.ttf", 40, "Black"), WARM, "mm")
        _spaced(d, (cx, 492), k.upper(), 15, MUTED, "m", "Bold", 2.4)
        if i:
            d.line(P(x0 + cw * i, 430, x0 + cw * i, 500), fill=(255, 255, 255, 40), width=max(1, S))


@lru_cache(maxsize=32)
def _backdrop(palette, body, slug, tier):
    """Sky, beast and shading: the same every turn of a fight, so drawn once (about 1s) and reused."""
    acc = T.ELEMENT_ACCENTS[palette]
    data = {"palette": palette, "enemy": {"body": body, "slug": slug}}
    img = _world(data, acc, STAGING.get(body, STAGING["cat"])[0])
    _particles(img, ATMOS.get(palette, "motes"), acc.rim)
    _beast(img, data, acc, tier)
    _shade_left(img)
    return img


def render_beast_fight(data):
    acc = T.ELEMENT_ACCENTS[data["palette"]]
    tier = _tier(data)
    e = data["enemy"]
    img = _backdrop(data["palette"], e["body"], e.get("slug"), tier).copy()
    if data.get("result"):
        _result(img, data, acc, tier)
    else:
        _identity(img, data, acc, tier)
        _corner(img, data)
        _intent(img, data, acc)
    _you(img, data, acc)
    return T.finish(img)
