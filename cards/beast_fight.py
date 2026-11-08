"""
Beast Fight v2 — the encounter screen (prototype for review; same data as cards.battle.render_battle).

  boss frame  : tier crest, the beast's name, ATK / DEF / role / element / realm, a long segmented HP bar where
                the HP it just lost shows as a pale trailing chunk, and the turn seal
  the encounter: the beast large in its element's sky (painted art, art/beasts/<slug>.png, or a silhouette),
                its next move on an angled card (red with POWERFUL ATTACK for a charged attack), a burst with
                the damage it just took
  console     : your portrait, name, realm and HP; your skill orbs (techniques and pills, like the buttons);
                the last turn's events
Tiers look different: Normal a bronze crest, Elite a violet crest with wings, Beast King a gold crowned crest
with flame, a double-rimmed HP bar and a red-gold sky.
"""
import math

from PIL import Image, ImageDraw, ImageFilter

from . import battle as B
from . import ink as K
from . import theme as T
from .beast_art import painted
from .theme import P, S, alpha, font, mix

W, H = 1200, 880
SKY_H = 600
TIER = {   # crest colour, frame colour, label
    "Normal": ((176, 150, 110), (130, 108, 76)),
    "Elite": ((178, 120, 246), (120, 80, 180)),
    "Beast King": ((246, 190, 70), (200, 140, 40)),
    "Bandits": ((214, 96, 76), (150, 60, 50)),
    "Master": ((150, 186, 236), (100, 130, 180)),
}


def _tier(data):
    tags = data["enemy"]["tags"]
    return tags[0] if tags and tags[0] in TIER else "Normal"


# ── Background and the beast ──────────────────────────────────────────

def _sky(data, acc):
    size = (W * S, SKY_H * S)
    img = B._sky(acc, size, 7)
    B._moon(img, acc, size[0] * 0.8, size[1] * 0.3, size[1] * 0.11)
    (B._courtyard if data.get("backdrop") == "courtyard" else B._landscape)(img, acc, 7)
    if _tier(data) == "Beast King":          # a red-gold storm behind a Beast King
        g = Image.new("RGBA", size, (0, 0, 0, 0))
        ImageDraw.Draw(g).ellipse(P(250, 60, 950, 640), fill=(255, 140, 40, 70))
        img.alpha_composite(g.filter(ImageFilter.GaussianBlur(60 * S)))
    return img


def _beast(img, data, acc):
    e = data["enemy"]
    body = "master" if e["body"] == "master" else e["body"]
    bw, bh = 640, 470
    x0, y0 = (W - bw) / 2 + 40, SKY_H - bh + 10
    art = B._art(e.get("slug"))
    if art is None:
        art = painted(body, data["palette"], bw * S, bh * S)
    if art is None:                           # no painting yet: the silhouette, drawn by the old card
        layer = Image.new("RGBA", (bw * S, bh * S), (0, 0, 0, 0))
        B._creature(layer, acc, body, None)
        art = layer
    else:
        art = art.copy()
        if art.size != (bw * S, bh * S):
            sc = min(bw * S / art.size[0], bh * S / art.size[1])
            art = art.resize((round(art.size[0] * sc), round(art.size[1] * sc)), Image.LANCZOS)
    # rim light in the element's colour, then a shadow on the ground
    mask = art.getchannel("A")
    rim = Image.new("RGBA", art.size, acc.rim + (0,))
    rim.putalpha(mask.filter(ImageFilter.GaussianBlur(10 * S)).point(lambda v: min(255, round(v * 1.3))))
    ox, oy = round(x0 * S + (bw * S - art.size[0]) / 2), round(y0 * S + (bh * S - art.size[1]))
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse(P(x0 + 90, SKY_H - 40, x0 + bw - 90, SKY_H + 10), fill=(0, 0, 0, 170))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12 * S)))
    img.alpha_composite(rim, (ox, oy))
    img.alpha_composite(art, (ox, oy))


# ── Boss frame ────────────────────────────────────────────────────────

def _crest(img, center, tier, seal, acc):
    cx, cy = center
    col, frame = TIER.get(tier, TIER["Normal"])
    r = 50
    if tier == "Beast King":
        T.soft_glow(img, (cx - 80, cy - 90, cx + 80, cy + 70), alpha((255, 150, 50), 170), 20)
    d = ImageDraw.Draw(img)
    if tier in ("Elite", "Beast King"):      # wings
        for s in (-1, 1):
            pts = [(cx + s * 30, cy - 10), (cx + s * 86, cy - 40), (cx + s * 74, cy - 14), (cx + s * 92, cy - 6),
                   (cx + s * 66, cy + 8), (cx + s * 76, cy + 22), (cx + s * 34, cy + 18)]
            d.polygon([P(*q) for q in pts], fill=alpha(mix(col, (0, 0, 0), 0.25), 255), outline=K.GOLD_HI)
    if tier == "Beast King":                 # crown
        pts = [(cx - 34, cy - 44), (cx - 40, cy - 78), (cx - 18, cy - 58), (cx, cy - 88), (cx + 18, cy - 58),
               (cx + 40, cy - 78), (cx + 34, cy - 44)]
        d.polygon([P(*q) for q in pts], fill=(246, 196, 80, 255), outline=(255, 240, 190))
        for x, y in ((cx - 40, cy - 78), (cx, cy - 88), (cx + 40, cy - 78)):
            K.gem(d, x, y, 6, (230, 50, 40))
    hexa = [P(cx + r * math.cos(math.radians(a)), cy + r * math.sin(math.radians(a))) for a in range(-90, 270, 60)]
    d.polygon(hexa, fill=(16, 12, 14, 255))
    d.line(hexa + [hexa[0]], fill=frame, width=round(7 * S), joint="curve")
    d.line(hexa + [hexa[0]], fill=col, width=round(2.4 * S), joint="curve")
    T.seal(img, (cx, cy), 34, seal, col)


def _boss_bar(img, box, e, color, double=False):
    """A long segmented HP bar; the HP lost last turn shows as a pale chunk trailing the fill."""
    x0, y0, x1, y1 = box
    mx = e["max_hp"] or 1
    frac = max(0.0, e["hp"] / mx)
    lost = max(0.0, -e.get("delta", 0) / mx)
    d = ImageDraw.Draw(img)
    pad = 8 if double else 5
    d.rounded_rectangle(P(x0 - pad, y0 - pad, x1 + pad, y1 + pad), radius=round(6 * S), fill=(6, 4, 6, 255),
                        outline=K.GOLD, width=round(2 * S))
    if double:
        d.rounded_rectangle(P(x0 - 3, y0 - 3, x1 + 3, y1 + 3), radius=round(4 * S), outline=alpha(K.GOLD_HI, 160),
                            width=max(1, S))
    fx = x0 + (x1 - x0) * frac
    if lost:
        lx = min(x1, fx + (x1 - x0) * lost)
        d.rectangle(P(fx, y0, lx, y1), fill=(255, 236, 200, 230))
    if frac > 0:
        g = T.vgradient((max(1, round((fx - x0) * S)), round((y1 - y0) * S)), mix(color, (255, 250, 230), 0.4),
                        mix(color, (0, 0, 0), 0.5))
        img.alpha_composite(g, P(x0, y0))
        d = ImageDraw.Draw(img)
        d.line(P(x0, y0 + 3, fx, y0 + 3), fill=(255, 255, 255, 100), width=max(1, S))
    for i in range(1, 10):
        tx = x0 + (x1 - x0) * i / 10
        d.line(P(tx, y0, tx, y1), fill=(0, 0, 0, 170), width=round(2 * S))
    T.text(d, ((x0 + x1) / 2, (y0 + y1) / 2 + 1), e.get("bar_label") or f"{e['hp']:,} / {e['max_hp']:,}",
           font("Inter.ttf", round((y1 - y0) * 0.66), "Black"), (255, 250, 240), "mm")


def _stat(img, x, y, icon, text, color):
    T.icon(img, icon, (x + 12, y), 24, color)
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 26, "Bold")
    T.text(d, (x + 32, y), text, f, (246, 238, 222), "lm")
    return 32 + T.width(d, text, f) + 26


def _turn_seal(img, center, data):
    cx, cy = center
    d = ImageDraw.Draw(img)
    r = 46
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=(12, 8, 10, 230), outline=K.BRONZE_DK, width=round(6 * S))
    d.arc(P(cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4), -90, 270, fill=K.GOLD, width=round(3 * S))
    T.text(d, (cx, cy - 10), data.get("turn_label") or f"TURN {data['turn']}", font("Cinzel.ttf", 18, "Black"),
           K.GOLD_HI, "mm")
    T.text(d, (cx, cy + 16), data.get("seconds_label") or f"{data['seconds']}s", font("Inter.ttf", 20, "Bold"),
           (246, 238, 222), "mm")


def _boss_frame(img, data, acc):
    e = data["enemy"]
    tier = _tier(data)
    col = TIER.get(tier, TIER["Normal"])[0]
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    g = T.vgradient((W * S, 220 * S), (0, 0, 0), (0, 0, 0))
    g.putalpha(Image.linear_gradient("L").resize(g.size).transpose(Image.FLIP_TOP_BOTTOM).point(lambda v: round(v * 0.8)))
    shade.alpha_composite(g)
    img.alpha_composite(shade)
    _crest(img, (96, 84), tier, e["seal"], acc)
    d = ImageDraw.Draw(img)
    name, nf = B._shrink(d, e["name"].upper(), "Cinzel.ttf", "Black", (50, 44, 38), 820)
    T.gold_text(img, (186, 66), name, nf, "ls", glow=alpha(col, 150))
    d = ImageDraw.Draw(img)
    nw = T.width(d, name, nf)
    T.spaced(d, (204 + nw, 50), tier.upper(), font("Cinzel.ttf", 18, "Black"), mix(col, (255, 255, 255), 0.3), 2.6)
    x = 186
    if e.get("atk"):
        x += _stat(img, x, 96, "sword", f"{e['atk']:,}", (246, 170, 90))
        x += _stat(img, x, 96, "shield", f"{e['def']:,}", (130, 186, 246))
    d = ImageDraw.Draw(img)
    T.text(d, (x, 96), " · ".join(e["tags"][1:]), font("Inter.ttf", 24, "SemiBold"), mix(col, (255, 255, 255), 0.55),
           "lm")
    _boss_bar(img, (40, 140, 1060, 178), e, acc.hp, double=tier == "Beast King")
    if data.get("result"):
        return
    _turn_seal(img, (1124, 112), data)
    y = 222
    for label in e["statuses"][:3]:
        B._chip(img, W - 30, y, label, acc.rim, "r", size=22)
        y += 48


# ── The encounter: intent card, damage burst, result ──────────────────

def _intent(img, data, acc):
    head, hint = data["warning"]
    if not head:
        return
    danger = data.get("danger")
    tone = (214, 56, 44) if danger == "charged" else ((226, 130, 50) if danger == "signature" else acc.rim)
    x0, y0, x1, y1 = 30, 232, 430, 360
    c = 26
    shape = [P(x0, y0), P(x1 - c, y0), P(x1, y0 + c), P(x1, y1), P(x0 + c, y1), P(x0, y1 - c)]
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(shape, fill=alpha(mix(tone, (8, 6, 8), 0.78), 230))
    img.alpha_composite(layer)
    if danger:
        T.soft_glow(img, (x0, y0, x1, y1), alpha(tone, 120), 14, "rect")
    d = ImageDraw.Draw(img)
    d.line(shape + [shape[0]], fill=mix(tone, (255, 255, 255), 0.25), width=round((3 if danger else 2) * S),
           joint="curve")
    if danger:
        lab = "POWERFUL ATTACK" if danger == "charged" else "SIGNATURE MOVE"
        B._chip(img, x0 + 20, y0, lab, (255, 170, 110), size=18)
    T.icon(img, "flame" if danger else "star", (x0 + 40, y0 + 52), 34, mix(tone, (255, 255, 255), 0.4))
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 25, "Bold")
    lines = T.wrap(d, head, f, x1 - x0 - 90, lines=2)
    for i, line in enumerate(lines):
        T.text(d, (x0 + 74, y0 + 40 + i * 30), line, f, (255, 248, 232), "lm")
    hf = font("Inter.ttf", 19, "Medium")
    T.text(d, (x0 + 22, y1 - 22), T.fit(d, hint, hf, x1 - x0 - 44), hf, mix(tone, (255, 255, 255), 0.6), "lm")


def _burst(img, center, amount):
    """An impact star behind the damage the beast just took."""
    if not amount or amount > 0:
        return
    cx, cy = center
    pts = []
    for i in range(24):
        r = 70 if i % 2 == 0 else 34
        a = math.radians(i * 15)
        pts.append(P(cx + r * math.cos(a) * 1.4, cy + r * math.sin(a)))
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).polygon(pts, fill=(255, 200, 90, 150))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(2 * S)))
    B._damage(img, (cx, cy), amount, (255, 220, 120), anchor="mm", big=True)


def _result(img, data, acc):
    label, color = B.RESULT.get(data["result"], (str(data["result"]).upper(), K.GOLD))
    tier = _tier(data)
    mid, cy = W / 2, 330
    big = data["result"] == "won" and tier in ("Elite", "Beast King")
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    if data["result"] == "won":
        for i in range(28 if big else 16):
            a = math.radians(i * 360 / (28 if big else 16))
            ld.polygon([P(mid, cy), P(mid + 700 * math.cos(a - 0.04), cy + 700 * math.sin(a - 0.04)),
                        P(mid + 700 * math.cos(a + 0.04), cy + 700 * math.sin(a + 0.04))], fill=alpha(color, 50))
    ld.rectangle(P(0, cy - 70, W, cy + 70), fill=(0, 0, 0, 170))
    layer = layer.filter(ImageFilter.GaussianBlur(3 * S))
    ImageDraw.Draw(layer).rectangle(P(0, SKY_H, W, H), fill=(0, 0, 0, 0))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    for yy in (cy - 70, cy + 70):
        d.line(P(0, yy, W, yy), fill=alpha(color, 230), width=round(2 * S))
    T.gold_text(img, (mid, cy - (14 if big else 0)), label, font("Cinzel.ttf", 92, "Black"), "mm",
                top=mix(color, (255, 255, 255), 0.55), bottom=mix(color, (0, 0, 0), 0.25), glow=alpha(color, 170))
    if big:
        d = ImageDraw.Draw(img)
        T.spaced(d, (mid, cy + 46), "BEAST KING SLAIN" if tier == "Beast King" else "ELITE SLAIN",
                 font("Cinzel.ttf", 24, "Black"), mix(color, (255, 255, 255), 0.4), 4, "m")


# ── Console ───────────────────────────────────────────────────────────

def _console(img, data, acc):
    y0 = SKY_H
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.rectangle(P(0, y0, W, H), fill=(10, 8, 10, 250))
    g = T.vgradient((W * S, (H - y0) * S), mix(acc.panel, (0, 0, 0), 0.2), (6, 5, 7))
    layer.alpha_composite(g, (0, y0 * S))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.line(P(0, y0, W, y0), fill=K.GOLD, width=round(3 * S))
    d.line(P(0, y0 + 6, W, y0 + 6), fill=alpha(K.BRONZE, 160), width=max(1, S))
    # notch in the middle of the gold edge
    d.polygon([P(W / 2 - 60, y0), P(W / 2 + 60, y0), P(W / 2 + 40, y0 + 16), P(W / 2 - 40, y0 + 16)], fill=K.BRONZE_DK,
              outline=K.GOLD)
    K.gem(d, W / 2, y0 + 7, 7, acc.rim)
    members = data["party"]
    if len(members) == 1:
        _you(img, data, acc)
    else:
        _party(img, data, acc)
    _events(img, data, acc)


def _you(img, data, acc):
    m = data["party"][0]
    low, color = B._bar_color(m)
    cx, cy = 86, 690
    T.soft_glow(img, (cx - 64, cy - 64, cx + 64, cy + 64), alpha(acc.rim, 110), 12)
    ImageDraw.Draw(img).ellipse(P(cx - 56, cy - 56, cx + 56, cy + 56), fill=(12, 10, 12, 255), outline=K.GOLD, width=round(3 * S))
    T.seal(img, (cx, cy), 44, "emblem:realm:" + m["realm"], (110, 160, 240))
    d = ImageDraw.Draw(img)
    T.text(d, (162, 652), T.fit(d, m["name"], font("Inter.ttf", 32, "Black"), 300), font("Inter.ttf", 32, "Black"),
           (240, 90, 76) if low or m.get("ko") else (250, 242, 226), "lm")
    T.text(d, (164, 684), f"{m['realm']} {m['layer']}", font("Inter.ttf", 22, "SemiBold"), T.ASH, "lm")
    frac = m["hp"] / m["max_hp"] if m["max_hp"] else 0
    K.ornate_bar(img, (210, 712, 730, 748), frac, color, "star" if m.get("bar_label") else "heart",
                 m.get("bar_label") or f"{m['hp']:,} / {m['max_hp']:,}")
    if m.get("delta"):
        B._damage(img, (730, 662), m["delta"], (236, 80, 70) if m["delta"] < 0 else (110, 230, 160), anchor="rm")
    _orbs(img, data.get("loadout", [])[:3], acc)


def _orbs(img, items, acc):
    """Skill orbs, one per technique (and pills): bright when ready, dark with the turns left while resting."""
    if not items:
        return
    xs = [850, 972, 1094][-len(items):] if len(items) < 3 else [850, 972, 1094]
    cy = 680
    for x, it in zip(xs, items):
        col = it["color"] or K.GOLD
        ready = it["ready"]
        r = 44
        if ready:
            T.soft_glow(img, (x - r - 12, cy - r - 12, x + r + 12, cy + r + 12), alpha(col, 150), 10)
        d = ImageDraw.Draw(img)
        d.ellipse(P(x - r, cy - r, x + r, cy + r), fill=(10, 8, 10, 255), outline=K.BRONZE_DK, width=round(6 * S))
        d.ellipse(P(x - r + 5, cy - r + 5, x + r - 5, cy + r - 5), outline=K.GOLD if ready else (90, 84, 80),
                  width=round(2 * S))
        core = Image.radial_gradient("L").resize(P(2 * r - 16, 2 * r - 16))
        ci = Image.composite(Image.new("RGBA", core.size, alpha(mix(col, (0, 0, 0), 0.75), 255)),
                             Image.new("RGBA", core.size, alpha(mix(col, (0, 0, 0), 0.2 if ready else 0.7), 255)), core)
        cm = Image.new("L", core.size, 0)
        ImageDraw.Draw(cm).ellipse((0, 0, core.size[0] - 1, core.size[1] - 1), fill=255)
        ci.putalpha(cm)
        img.alpha_composite(ci, P(x - r + 8, cy - r + 8))
        T.icon(img, it["seal"], (x, cy), 54, (250, 246, 236) if ready else (130, 124, 118))
        d = ImageDraw.Draw(img)
        if not ready:
            num = "".join(ch for ch in it["state"] if ch.isdigit()) or "–"
            d.ellipse(P(x - r + 6, cy - r + 6, x + r - 6, cy + r - 6), fill=(0, 0, 0, 140))
            T.text(d, (x, cy), num, font("Cinzel.ttf", 40, "Black"), (246, 210, 150), "mm")
        T.text(d, (x, cy + r + 18), T.fit(d, it["name"], font("Inter.ttf", 18, "Bold"), 118), font("Inter.ttf", 18, "Bold"),
               (240, 232, 216) if ready else (140, 132, 124), "mm")


def _party(img, data, acc):
    members = data["party"][:6]
    cols = 2 if len(members) > 3 else 1
    rows = math.ceil(len(members) / cols)
    cw = 1140 / cols
    for i, m in enumerate(members):
        c, r = (i // rows, i % rows)
        x0, yc = 30 + c * cw, 640 + r * 46
        low, color = B._bar_color(m)
        if m.get("arrow"):
            d = ImageDraw.Draw(img)
            d.polygon([P(x0, yc - 10), P(x0 + 14, yc), P(x0, yc + 10)], fill=(255, 120, 90))
        T.seal(img, (x0 + 40, yc), 18, "emblem:realm:" + m["realm"], B.MEMBER_COLORS[i % len(B.MEMBER_COLORS)])
        d = ImageDraw.Draw(img)
        T.text(d, (x0 + 66, yc), T.fit(d, m["name"], font("Inter.ttf", 24, "Bold"), 170), font("Inter.ttf", 24, "Bold"),
               (240, 90, 76) if low or m.get("ko") else (250, 240, 222), "lm")
        frac = m["hp"] / m["max_hp"] if m["max_hp"] else 0
        label = "KO" if m.get("ko") else ("Fled" if m.get("move") == "Fled" else f"{m['hp']:,} / {m['max_hp']:,}")
        T.bar(img, (x0 + 246, yc - 16, x0 + cw - 30, yc + 16), frac, color, label)


def _events(img, data, acc):
    events = list(data.get("log") or [])[-3:]
    y = 800 if len(data["party"]) == 1 else 788
    d = ImageDraw.Draw(img)
    d.line(P(30, y - 22, W - 30, y - 22), fill=alpha(K.BRONZE, 120), width=max(1, S))
    if len(events) <= 2:
        for i, (kind, text) in enumerate(events):
            B._log_line(img, 30 + i * 580, y + 18, kind, text, 540, 23)
    else:
        for i, (kind, text) in enumerate(events):
            col, row = (0, i) if i < 2 else (1, 0)
            B._log_line(img, 30 + col * 580, y + 2 + row * 34, kind, text, 540, 22)


def render_beast_fight(data):
    acc = T.ELEMENT_ACCENTS[data["palette"]]
    img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 255))
    img.alpha_composite(_sky(data, acc))
    _beast(img, data, acc)
    _boss_frame(img, data, acc)
    if data.get("result"):
        _result(img, data, acc)
    else:
        _intent(img, data, acc)
        _burst(img, (900, 420), data["enemy"].get("delta"))
    _console(img, data, acc)
    T.frame(img, (6, 6, W - 6, H - 6), 1.0)
    return T.finish(img)
