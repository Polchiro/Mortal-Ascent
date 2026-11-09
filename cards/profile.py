"""
Character Sheet · Profile tab ("Moon Gate", Night Ink theme: cards/ink.py).

render_profile(data) draws cards built by bot.sheet.data.profile_data:
- the hero band: the avatar in a moon-gate ring whose beads are the realm's layers, the name and talent,
  ornate HP and Internal Qi bars, and the realm emblem with phase and layer;
- Attributes (HP, Attack, Defense with their buff %), the meridian figure whose dantian fills with Qi and
  the four gear slots around it, and the equipped techniques with their mastery arcs;
- the Deeds rail: beasts, herbs, breakthroughs, duels, rank and (for the owner) the purse.
"""
import io
import math

from PIL import Image, ImageDraw, ImageFilter, ImageChops

from . import ink as k
from . import theme as t
from .emblems import emblem, empty_slot
from .theme import P, font, short, mix, alpha

W, H = 1200, 830


def rules_duration(seconds):
    h, m = divmod(int(seconds // 60), 60)
    return f"{h}h {m}m" if h else f"{m}m"


def avatar_image(data):
    """The Discord avatar (or None, then the gate shows a dark lacquer disc with the initial)."""
    raw = data.get("avatar_bytes")
    if not raw:
        return None
    try:
        return Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        return None


# ── Hero band ─────────────────────────────────────────────────────────

def moon_gate(img, center, r, face, layer, total, aura, realm, initial=None):
    cx, cy = center
    t.soft_glow(img, (cx - r - 34, cy - r - 34, cx + r + 34, cy + r + 34), alpha(aura, 130), 22)
    d = ImageDraw.Draw(img)
    # rotating rune ring behind the gate
    f = t.cjk(10)
    ring = "天地玄黄宇宙洪荒日月盈昃辰宿列张寒来暑往秋收冬藏"
    for i, ch in enumerate(ring):
        a = i / len(ring) * 2 * math.pi
        if 55 < math.degrees(a) < 125:
            continue
        t.text(d, (cx + (r + 27) * math.cos(a), cy + (r + 27) * math.sin(a)), ch, f, alpha(t.GOLD, 70), "mm",
               shadow=False)
    # outer bronze ring
    for rr, col, wdt in ((r + 17, (0, 0, 0, 200), 3), (r + 14, k.BRONZE_DK, 9), (r + 18, t.GOLD, 1.6),
                         (r + 9.5, t.GOLD, 1.4)):
        d.ellipse(P(cx - rr, cy - rr, cx + rr, cy + rr), outline=col, width=round(wdt * t.S))
    # face
    side = round(2 * r * t.S)
    if face is None:
        face = t.vgradient((side, side), (40, 62, 108), (10, 16, 32))
        ImageDraw.Draw(face).text((side / 2, side / 2), (initial or "?")[:1].upper(), fill=k.GOLD_HI, anchor="mm",
                                  font=font("Cinzel.ttf", round(r * 0.9), "Black").font_variant(size=round(r * 0.9 * t.S)))
    else:
        w, h = face.size
        sq = min(w, h)
        face = face.crop(((w - sq) // 2, (h - sq) // 2, (w - sq) // 2 + sq, (h - sq) // 2 + sq))
    face = face.resize((side, side), Image.LANCZOS)
    m = Image.new("L", (side, side), 0)
    ImageDraw.Draw(m).ellipse((0, 0, side - 1, side - 1), fill=255)
    shade = Image.radial_gradient("L").resize((side, side)).point(lambda v: max(0, v - 120) * 1.4)
    dark = Image.new("RGBA", (side, side), (0, 0, 0, 255))
    dark.putalpha(shade)
    face = face.copy()
    face.alpha_composite(dark)
    face.putalpha(ImageChops.multiply(m, face.getchannel("A")))
    img.alpha_composite(face, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), outline=t.GOLD_HI, width=round(1.4 * t.S))
    # layer beads on the ring (gap at the bottom for the realm seal)
    span0, span1 = 90 + 42, 90 + 318
    for i in range(total):
        a = math.radians(span0 + (span1 - span0) * i / (total - 1))
        bx, by = cx + (r + 14) * math.cos(a), cy + (r + 14) * math.sin(a)
        br = 5.2
        if i < layer:
            if i == layer - 1:
                t.soft_glow(img, (bx - 10, by - 10, bx + 10, by + 10), alpha(k.SKY, 220), 4)
                d = ImageDraw.Draw(img)
            d.ellipse(P(bx - br, by - br, bx + br, by + br), fill=t.EMBER, outline=t.GOLD_HI, width=max(1, t.S))
            d.ellipse(P(bx - br * 0.45 - 1, by - br * 0.45 - 1, bx - 0.5, by - 0.5), fill=(255, 210, 190, 200))
        else:
            d.ellipse(P(bx - br, by - br, bx + br, by + br), fill=(14, 10, 10), outline=k.BRONZE, width=max(1, t.S))
    # cloud curls at the sides of the gate
    for side in (-1, 1):
        k.cloud_curl(d, cx + side * (r + 30), cy + r * 0.62, 11, t.GOLD, flip=-side, width=2)
        k.cloud_curl(d, cx + side * (r + 44), cy + r * 0.62 + 10, 7, alpha(k.BRONZE, 255), flip=-side, width=1.6)
    # realm seal at the bottom of the gate
    t.medallion(img, (cx, cy + r + 10), 22, t.REALM_CHAR.get(realm, "武"), t.EMBER)


def hero(img, data, face):
    d = ImageDraw.Draw(img)
    aura = t.TALENT.get(data["talent"], t.EMBER)
    moon_gate(img, (152, 182), 92, face, data["layer"], data["max_layer"], aura, data["realm"], data["name"])

    # name + talent
    x = 300
    f_name = font("Cinzel.ttf", 44, "Black")
    name = t.fit(ImageDraw.Draw(img), data["name"].upper(), f_name, 440)
    t.gold_text(img, (x, 70), name, f_name, glow=t.EMBER)
    d = ImageDraw.Draw(img)
    nw = t.width(d, name, f_name)
    f_b = font("Cinzel.ttf", 12, "Bold")
    badge = f"{data['talent'].upper()} TALENT"
    bw = t.width(d, badge, f_b) + 34
    bx, by = x + nw + 18, 84
    d.polygon([P(bx, by + 11), P(bx + 9, by), P(bx + bw - 9, by), P(bx + bw, by + 11), P(bx + bw - 9, by + 22),
               P(bx + 9, by + 22)], fill=mix(aura, (0, 0, 0), 0.68) + (255,), outline=aura)
    t.text(d, (bx + bw / 2, by + 11.5), badge, f_b, mix(aura, (255, 255, 255), 0.35), "mm")
    if data.get("username"):
        t.text(d, (x + 2, 130), f"@{data['username']}", font("Inter.ttf", 14, "Medium"), k.ASH)

    # HP and Qi
    hp = data["hp"]                      # HP is full outside fights; an injury shows on the bar instead
    injured = hp.get("injured_for", 0) > 0
    label = f"{hp['max']:,} HP" + (f"  ·  injured {rules_duration(hp['injured_for'])}" if injured else "")
    k.ornate_bar(img, (x + 30, 170, 820, 198), 1.0, (150, 70, 60) if injured else (214, 44, 40), "heart", label,
                 tag="HP")
    qi = data["qi"]
    frac = qi["qi"] / qi["capacity"] if qi["capacity"] else 0
    k.ornate_bar(img, (x + 30, 224, 820, 246), frac, k.AZURE, "flame",
               f"{short(qi['qi'])} / {short(qi['capacity'])} Qi", tag="QI")

    # realm plaque
    rx0, rx1 = 880, 1170
    mx = (rx0 + rx1) / 2
    emblem(img, "realm", data["realm"], (mx, 112), 88)
    d = ImageDraw.Draw(img)
    f_realm = font("Cinzel.ttf", 26, "Black")
    realm = data["realm"].upper()
    if t.width(d, realm, f_realm) > rx1 - rx0:
        f_realm = font("Cinzel.ttf", 21, "Black")
    t.gold_text(img, (mx, 184), realm, f_realm, anchor="mm")
    d = ImageDraw.Draw(img)
    t.spaced(d, (mx, 214), f"{data['phase'].upper()}  ·  {t.ordinal(data['layer']).upper()} LAYER",
             font("Cinzel.ttf", 12, "Bold"), k.SKY, 1.8, "m")
    # a slim vertical rule between name block and realm plaque
    for y in range(70, 250, 2):
        a = round(160 * math.sin((y - 70) / 180 * math.pi))
        d.line(P(856, y, 856, y + 1), fill=alpha(t.GOLD, a), width=max(1, t.S))
    t.stud(d, 856, 160, 4)


# ── Middle row ────────────────────────────────────────────────────────

def attributes(img, data, box):
    x0, y0, x1, y1 = box
    k.plaque(img, box, "Attributes")
    f_lab = font("Cinzel.ttf", 15, "Bold")
    f_val = font("Cinzel.ttf", 30, "Black")
    y = y0 + 70
    for a in data["attributes"]:
        tb = (x0 + 16, y - 34, x1 - 16, y + 38)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(layer).rectangle(P(*tb), fill=alpha(mix(a["color"], (0, 0, 0), 0.82), 200))
        img.alpha_composite(layer)
        d = ImageDraw.Draw(img)
        d.line(P(tb[0], tb[1], tb[0], tb[3]), fill=a["color"], width=round(3 * t.S))
        d.rectangle(P(*tb), outline=alpha(k.BRONZE_DK, 255), width=max(1, t.S))
        t.medallion(img, (x0 + 46, y + 2), 20, a["icon"], a["color"], cjk_char=False)
        d = ImageDraw.Draw(img)
        t.spaced(d, (x0 + 76, y - 9), a["label"].upper(), f_lab, k.PARCHMENT, 1.6)
        if a["bonus"]:
            chip = f"+{a['bonus']:.0%}"
            fc = font("Inter.ttf", 11, "Bold")
            cw = t.width(d, chip, fc) + 12
            cx0 = x0 + 76
            d.rounded_rectangle(P(cx0, y + 4, cx0 + cw, y + 20), radius=round(8 * t.S),
                                fill=mix(a["color"], (0, 0, 0), 0.6) + (255,), outline=alpha(a["color"], 255),
                                width=max(1, t.S // 2))
            t.text(d, (cx0 + cw / 2, y + 12), chip, fc, mix(a["color"], (255, 255, 255), 0.5), "mm", shadow=False)
        t.gold_text(img, (x1 - 28, y + 2), f"{a['final']:,}", f_val, anchor="rm")
        y += 96


def meridian_figure(img, cx, cy, frac, realm):
    """A seated martial artist in silhouette, meridians lit by the Qi bar, the dantian glowing in the belly."""
    # rune halo + giant realm character
    d = ImageDraw.Draw(img)
    for rr, a in ((150, 55), (138, 30)):
        d.ellipse(P(cx - rr, cy - 64 - rr, cx + rr, cy - 64 + rr), outline=alpha(t.GOLD, a), width=max(1, t.S))
    for i in range(36):
        a = math.radians(i * 10)
        r0, r1 = 138, 150 if i % 3 == 0 else 144
        d.line(P(cx + r0 * math.cos(a), cy - 64 + r0 * math.sin(a), cx + r1 * math.cos(a), cy - 64 + r1 * math.sin(a)),
               fill=alpha(t.GOLD, 60), width=max(1, t.S))

    sz = img.size
    mask = Image.new("L", sz, 0)
    md = ImageDraw.Draw(mask)
    md.ellipse(P(cx - 23, cy - 166, cx + 23, cy - 118), fill=255)                         # head
    md.polygon([P(cx - 11, cy - 124), P(cx + 11, cy - 124), P(cx + 13, cy - 108), P(cx - 13, cy - 108)], fill=255)
    md.polygon([P(cx - 16, cy - 110), P(cx + 16, cy - 110), P(cx + 60, cy - 94), P(cx + 54, cy - 30),
                P(cx + 44, cy + 4), P(cx - 44, cy + 4), P(cx - 54, cy - 30), P(cx - 60, cy - 94)], fill=255)  # torso
    for s in (-1, 1):                                                                      # arms resting on knees
        md.line([P(cx + s * 52, cy - 88), P(cx + s * 76, cy - 40), P(cx + s * 86, cy + 2)], fill=255,
                width=round(24 * t.S), joint="curve")
        md.ellipse(P(cx + s * 86 - 12, cy - 8, cx + s * 86 + 12, cy + 12), fill=255)
        md.polygon([P(cx + s * 50, cy - 90), P(cx + s * 92, cy + 4), P(cx + s * 40, cy + 6)], fill=255)   # sleeves
    md.ellipse(P(cx - 128, cy - 14, cx + 128, cy + 40), fill=255)                         # crossed legs
    md.polygon([P(cx - 46, cy - 6), P(cx + 46, cy - 6), P(cx + 30, cy + 34), P(cx - 30, cy + 34)], fill=255)
    # topknot
    md.ellipse(P(cx - 9, cy - 178, cx + 9, cy - 160), fill=255)

    rim = mask.filter(ImageFilter.GaussianBlur(9 * t.S))
    glow = Image.new("RGBA", sz, alpha(k.SKY, 0))
    glow.putalpha(rim.point(lambda v: min(255, v * 0.7)))
    img.alpha_composite(glow)
    body = t.vgradient(sz, (30, 42, 68), (8, 12, 22), round((cy - 180) * t.S), round((cy + 40) * t.S))
    body.putalpha(mask)
    img.alpha_composite(body)
    edge = mask.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.MaxFilter(3))
    e = Image.new("RGBA", sz, alpha(t.GOLD, 0))
    e.putalpha(edge.point(lambda v: v * 0.55))
    img.alpha_composite(e)

    # meridians
    lit = mix((90, 40, 40), k.AZURE_HI, frac)
    lines = [[(cx, cy - 150), (cx, cy - 30)],
             [(cx, cy - 92), (cx - 46, cy - 86), (cx - 74, cy - 40), (cx - 86, cy + 2)],
             [(cx, cy - 92), (cx + 46, cy - 86), (cx + 74, cy - 40), (cx + 86, cy + 2)],
             [(cx, cy - 30), (cx - 60, cy + 14), (cx - 108, cy + 14)],
             [(cx, cy - 30), (cx + 60, cy + 14), (cx + 108, cy + 14)]]
    gl = Image.new("RGBA", sz, (0, 0, 0, 0))
    gd = ImageDraw.Draw(gl)
    for ln in lines:
        gd.line([P(*q) for q in ln], fill=alpha(k.AZURE, 200), width=round(5 * t.S), joint="curve")
    img.alpha_composite(gl.filter(ImageFilter.GaussianBlur(4 * t.S)))
    d = ImageDraw.Draw(img)
    for ln in lines:
        d.line([P(*q) for q in ln], fill=alpha(lit, 230), width=round(1.4 * t.S), joint="curve")
    for py in (cy - 150, cy - 128, cy - 92):                                              # crown, brow, heart points
        t.soft_glow(img, (cx - 7, py - 7, cx + 7, py + 7), alpha(k.AZURE_HI, 200), 3)
        d = ImageDraw.Draw(img)
        d.ellipse(P(cx - 2.5, py - 2.5, cx + 2.5, py + 2.5), fill=(235, 248, 255))
    dantian(img, (cx, cy - 34), 18, frac)


def dantian(img, center, r, frac):
    """A small glass orb in a gold cradle, filled with azure Qi up to frac."""
    cx, cy = center
    t.soft_glow(img, (cx - r * 1.6, cy - r * 1.6, cx + r * 1.6, cy + r * 1.6), alpha(k.AZURE, round(80 + 120 * frac)), 8)
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6), fill=k.BRONZE_DK, outline=t.GOLD, width=round(1.6 * t.S))
    for n in range(12):
        a = math.radians(n * 30)
        x, y = cx + math.cos(a) * (r + 3), cy + math.sin(a) * (r + 3)
        d.ellipse(P(x - 1.4, y - 1.4, x + 1.4, y + 1.4), fill=t.GOLD_HI)
    side = round(2 * r * t.S)
    sph = Image.new("RGBA", (side, side), (6, 12, 22, 255))
    level = side * (1 - frac)
    liq = t.vgradient((side, side), (200, 236, 255), (20, 70, 140), round(level), side)
    lm = Image.new("L", (side, side), 0)
    ImageDraw.Draw(lm).rectangle((0, level, side, side), fill=255)
    liq.putalpha(lm)
    sph.alpha_composite(liq)
    ImageDraw.Draw(sph).line((0, level, side, level), fill=(220, 245, 255, 200), width=t.S)
    cm = Image.new("L", (side, side), 0)
    ImageDraw.Draw(cm).ellipse((0, 0, side - 1, side - 1), fill=255)
    sph.putalpha(cm)
    img.alpha_composite(sph, P(cx - r, cy - r))
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r * 0.5, cy - r * 0.7, cx - r * 0.05, cy - r * 0.35), fill=(255, 255, 255, 60))


def gear_slot(img, center, s, color):
    """Hexagonal hotbar slot with a tier glow and corner gems."""
    cx, cy, h = center[0], center[1], s / 2
    c = s * 0.22
    t.soft_glow(img, (cx - h, cy - h, cx + h, cy + h), alpha(color, 120), 9)
    d = ImageDraw.Draw(img)
    shape = [P(cx - h + c, cy - h), P(cx + h - c, cy - h), P(cx + h, cy - h + c), P(cx + h, cy + h - c),
             P(cx + h - c, cy + h), P(cx - h + c, cy + h), P(cx - h, cy + h - c), P(cx - h, cy - h + c)]
    d.polygon(shape, fill=(10, 6, 7, 255))
    g = Image.radial_gradient("L").resize(P(s - 8, s - 8)).point(lambda v: 255 - v)
    tint = Image.new("RGBA", g.size, alpha(mix(color, (0, 0, 0), 0.45), 0))
    tint.putalpha(g.point(lambda v: v * 0.45))
    img.alpha_composite(tint, P(cx - h + 4, cy - h + 4))
    d = ImageDraw.Draw(img)
    d.line(shape + [shape[0]], fill=k.BRONZE_DK, width=round(4 * t.S), joint="curve")
    d.line(shape + [shape[0]], fill=color, width=round(1.6 * t.S), joint="curve")
    k.gem(d, cx, cy - h, 4.5, color)


def armory(img, data, box):
    x0, y0, x1, y1 = box
    k.plaque(img, box, "Meridians & Gear")
    cx = (x0 + x1) / 2
    qi = data["qi"]
    frac = qi["qi"] / qi["capacity"] if qi["capacity"] else 0
    meridian_figure(img, cx, y0 + 250, frac, data["realm"])
    d = ImageDraw.Draw(img)
    t.spaced(d, (cx, y0 + 312), f"DANTIAN  {frac:.0%}", font("Cinzel.ttf", 13, "Bold"), k.AZURE_HI, 2.2, "m")

    pos = [(x0 + 66, y0 + 92), (x1 - 66, y0 + 92), (x0 + 66, y0 + 222), (x1 - 66, y0 + 222)]
    f_name = font("Inter.ttf", 11, "Bold")
    f_line = font("Inter.ttf", 10, "SemiBold")
    for (sx, sy), g in zip(pos, data.get("gear") or []):
        empty = "empty" in g
        color = k.ASH_DK if empty else t.RARITY.get(g["tier"], k.ASH)
        gear_slot(img, (sx, sy), 62, color)
        if empty:
            kind = g["slot"][:8]
            if kind in ("armor", "artifact"):
                empty_slot(img, kind, (sx, sy), 38)
            else:
                t.icon(img, "fist", (sx, sy), 28, k.ASH_DK)
        else:
            t.icon(img, g["icon"], (sx, sy), 40, mix(color, (255, 255, 255), 0.2))
        d = ImageDraw.Draw(img)
        # connector to the figure
        tx = cx - 70 if sx < cx else cx + 70
        for n in range(10):
            a, b = n / 10, (n + 0.5) / 10
            d.line(P(sx + (tx - sx) * a + (31 if sx < cx else -31) * (1 - a), sy + (sy - sy) * a,
                     sx + (tx - sx) * b + (31 if sx < cx else -31) * (1 - b), sy), fill=alpha(color, 90),
                   width=max(1, t.S))
        ty = sy + 42
        if empty:
            for j, line in enumerate(t.wrap(d, g["empty"], f_line, 116, lines=2)):
                t.text(d, (sx, ty + 15 + j * 13), line, f_line, k.ASH_DK, "mm")
        else:
            t.text(d, (sx, ty + 6), t.fit(d, g["name"], f_name, 124), f_name, k.PARCHMENT, "mm")
            t.text(d, (sx, ty + 21), t.fit(d, g["line"], f_line, 124), f_line, mix(color, (255, 255, 255), 0.35), "mm")


def techniques(img, data, box):
    x0, y0, x1, y1 = box
    k.plaque(img, box, "Techniques")
    y = y0 + 40
    for slot in data["slots"]:
        technique_row(img, (x0 + 16, y, x1 - 16, y + 84), slot)
        y += 98


def technique_row(img, box, slot):
    x0, y0, x1, y1 = box
    tech = slot["tech"]
    cy = (y0 + y1) / 2
    color = t.RARITY.get(tech["grade"]) if tech else k.ASH_DK
    # row backing
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(P(x0 + 30, y0 + 10, x1, y1 - 10), radius=round(8 * t.S),
                                            fill=alpha(mix(color, (0, 0, 0), 0.85), 210))
    img.alpha_composite(layer)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle(P(x0 + 30, y0 + 10, x1, y1 - 10), radius=round(8 * t.S), outline=alpha(k.BRONZE_DK, 255),
                        width=max(1, t.S))
    # round ability medallion (glowing ring like a skill icon)
    r = 32
    mx = x0 + r + 4
    t.soft_glow(img, (mx - r - 4, cy - r - 4, mx + r + 4, cy + r + 4), alpha(color, 120 if tech else 30), 6)
    d = ImageDraw.Draw(img)
    d.ellipse(P(mx - r, cy - r, mx + r, cy + r), fill=(10, 6, 7, 255), outline=k.BRONZE_DK, width=round(4 * t.S))
    d.ellipse(P(mx - r + 3, cy - r + 3, mx + r - 3, cy + r - 3), outline=t.GOLD if tech else k.ASH_DK,
              width=round(1.5 * t.S))
    if tech:
        core = Image.radial_gradient("L").resize(P(2 * r - 12, 2 * r - 12))
        c_img = Image.composite(Image.new("RGBA", core.size, alpha(mix(color, (0, 0, 0), 0.75), 255)),
                                Image.new("RGBA", core.size, alpha(mix(color, (0, 0, 0), 0.25), 255)), core)
        cm = Image.new("L", core.size, 0)
        ImageDraw.Draw(cm).ellipse((0, 0, core.size[0] - 1, core.size[1] - 1), fill=255)
        c_img.putalpha(cm)
        img.alpha_composite(c_img, P(mx - r + 6, cy - r + 6))
        t.icon(img, tech.get("icon") or "school:" + tech["school"], (mx, cy), 40, (250, 244, 232))
        # mastery arc around the medallion
        d = ImageDraw.Draw(img)
        stage = tech["stage"] + 1
        for i in range(5):
            a0 = -90 - 70 + i * 28
            d.arc(P(mx - r - 5, cy - r - 5, mx + r + 5, cy + r + 5), a0, a0 + 22,
                  fill=k.SKY if i < stage else (40, 26, 24), width=round(3 * t.S))
    elif not slot["locked"]:
        empty_slot(img, "school:" + {"Attack": "Fist", "Defense": "Body"}.get(slot["slot"], "Palm"), (mx, cy), 36)
    else:
        t.icon(img, "lock", (mx, cy), 24, k.ASH_DK)
    d = ImageDraw.Draw(img)
    tx = mx + r + 16
    t.spaced(d, (tx, y0 + 21), f"{slot['slot'].upper()}", font("Cinzel.ttf", 10, "Bold"), k.BRONZE, 1.8)
    if tech:
        f_n = font("Inter.ttf", 16, "Bold")
        t.text(d, (tx, cy - 3), t.fit(d, tech["name"], f_n, x1 - tx - 10), f_n, k.PARCHMENT, "lm")
        sub = f"{tech['grade']} · {tech['school']}"
        f_s = font("Inter.ttf", 11, "SemiBold")
        t.text(d, (tx, cy + 16), sub, f_s, color, "lm")
        # grade tag on the right of the header line
        t.text(d, (x1 - 10, y0 + 21), tech.get("power", ""), font("Inter.ttf", 10, "Bold"), t.GOLD, "rm")
    else:
        msg = slot.get("note") if slot["locked"] else "Empty slot"
        t.text(d, (tx, cy + 4), msg, font("Inter.ttf", 14, "Medium"), k.ASH_DK, "lm")


# ── Deeds rail ────────────────────────────────────────────────────────

def deeds(img, data, box):
    x0, y0, x1, y1 = box
    mid = (y0 + y1) / 2
    # rail body with scroll ends
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    body = [P(x0 + 30, y0), P(x1 - 30, y0), P(x1 - 10, mid), P(x1 - 30, y1), P(x0 + 30, y1), P(x0 + 10, mid)]
    ld.polygon(body, fill=(10, 15, 27, 238))
    img.alpha_composite(layer)
    g = t.vgradient((round((x1 - x0 - 60) * t.S), round(26 * t.S)), (34, 54, 96), (12, 20, 40))
    img.alpha_composite(g, P(x0 + 30, y0 + 1))
    d = ImageDraw.Draw(img)
    d.line(body + [body[0]], fill=t.GOLD, width=round(2 * t.S), joint="curve")
    d.line(P(x0 + 30, y0 + 27, x1 - 30, y0 + 27), fill=alpha(t.GOLD, 120), width=max(1, t.S))
    for side, ex in ((-1, x0 + 10), (1, x1 - 10)):
        k.cloud_curl(d, ex + side * 4, mid - 10, 14, t.GOLD, flip=side, width=2.4)
        k.cloud_curl(d, ex + side * 2, mid + 14, 9, alpha(k.BRONZE, 255), flip=side, width=1.8)
        k.gem(d, ex, mid, 7, t.EMBER)
    t.spaced(d, ((x0 + x1) / 2, y0 + 14), "DEEDS OF THE JIANGHU", font("Cinzel.ttf", 12, "Bold"), t.GOLD_HI, 3, "m")

    items = [("deed:beasts", "Beasts", f"{data['beasts']:,}", (210, 120, 90)),
             ("deed:herbs", "Herbs", f"{data.get('herbs', 0):,}", t.JADE),
             ("deed:breakthroughs", "Breakthroughs", f"{data['breakthroughs']:,}", k.SKY),
             ("deed:duels", "Duels", f"{data.get('duels_won', 0)}W · {data.get('duels_lost', 0)}L", (226, 200, 120)),
             ("deed:rank", "Rank", f"#{data['rank']}", t.GOLD_HI)]
    purse = []
    if data.get("coins") is not None:
        purse = [("deed:lotus_coin", "Lotus Coins", short(data["coins"]), t.LOTUS),
                 ("deed:moon_pearl", "Moon Pearls", short(data["pearls"]), t.MOON)]
    allx = x1 - x0 - 140
    n = len(items) + len(purse)
    step = allx / n
    f_k = font("Cinzel.ttf", 10, "Bold")
    f_v = font("Inter.ttf", 18, "Bold")
    for i, (ic, label, v, col) in enumerate(items + purse):
        cx = x0 + 70 + step * (i + 0.5) + (14 if i >= len(items) else 0)
        cy = y0 + 56
        t.medallion(img, (cx, cy), 22, ic, col, cjk_char=False, icon_scale=1.4)
        d = ImageDraw.Draw(img)
        t.text(d, (cx, cy + 33), v, f_v, col if i >= len(items) else k.PARCHMENT, "mm")
        t.spaced(d, (cx, cy + 52), label.upper(), f_k, k.ASH, 1.4, "m")
    if purse:
        sx = x0 + 70 + step * len(items) + 7
        for y in range(int(y0 + 36), int(y1 - 8), 2):
            d.line(P(sx, y, sx, y + 1), fill=alpha(t.GOLD, 120), width=max(1, t.S))
        k.gem(d, sx, mid + 12, 5, t.LOTUS)


# ── Card ──────────────────────────────────────────────────────────────

def render_profile(data):
    img = k.canvas(W, H, "profile", seed=11)
    k.sheet_frame(img, "profile")
    hero(img, data, avatar_image(data))
    d = ImageDraw.Draw(img)
    t.divider(d, 30, W - 30, 282)
    attributes(img, data, (28, 312, 380, 646))
    armory(img, data, (396, 312, 804, 646))
    techniques(img, data, (820, 312, 1172, 646))
    if data.get("status"):
        d = ImageDraw.Draw(img)
        t.text(d, (W / 2, 668), t.fit(d, data["status"], font("Inter.ttf", 13, "SemiBold"), 900),
               font("Inter.ttf", 13, "SemiBold"), k.SKY, "mm")
    deeds(img, data, (24, 690, W - 24, 812))
    return t.finish(img)


