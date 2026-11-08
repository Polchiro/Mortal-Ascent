"""
Chest opening cards (Night Ink theme: cards/ink.py). render_chest(data) draws one stage of the reveal that
bot/chest_reveal.py builds from a pending chest:

- "sealed": the chest bound by a talisman over a glowing formation array, before the seal is broken;
- "opening": the lid thrown back and a pillar of light whose colour hints at the best reward inside;
- "reveal": the rewards, best first: a highlight panel for an Epic or better find, then a tile for every
  reward styled by its rarity (Common plain ... Mythical with a prismatic frame and sparkles);
- "collected": the same rewards stamped as added to the bag, and anything left behind because the bag was full.
"""
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from . import ink as k
from . import theme as t
from .theme import P, S, alpha, font, mix

W = 1200
RARITIES = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythical"]
# Chest bodies by tier: (wood or metal, bands, lid)
CHEST_LOOK = {
    "wooden": ((112, 72, 42), (150, 110, 60), (132, 86, 50)),
    "bronze": ((140, 88, 46), (226, 176, 92), (162, 104, 56)),
    "silver": ((120, 130, 148), (226, 232, 242), (146, 156, 174)),
    "jade": ((40, 128, 100), (232, 196, 110), (54, 156, 122)),
}
OPENING_LINE = {
    "Common": "The seal gives way with a soft click...",
    "Uncommon": "A gentle green light seeps from the cracks...",
    "Rare": "Azure light spills out of the chest!",
    "Epic": "Violet qi surges out. Something precious stirs within!",
    "Legendary": "Golden radiance floods the secret realm!",
    "Mythical": "The heavens tremble! A crimson aurora tears across the sky!",
}
BEST_TITLE = {"Epic": "AN EPIC FIND", "Legendary": "A LEGENDARY FIND", "Mythical": "A MYTHICAL FIND"}


def rank(rarity):
    return RARITIES.index(rarity) if rarity in RARITIES else 0


# ── The chest ─────────────────────────────────────────────────────────

def light_pillar(img, base, width, height, color, strength):
    """A widening beam of light rising from the chest, with rays."""
    cx, by = base
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    top = by - height
    ld.polygon([P(cx - width * 0.32, by), P(cx + width * 0.32, by), P(cx + width * 0.9, top), P(cx - width * 0.9, top)],
               fill=alpha(color, round(90 * strength)))
    ld.polygon([P(cx - width * 0.16, by), P(cx + width * 0.16, by), P(cx + width * 0.4, top), P(cx - width * 0.4, top)],
               fill=alpha(mix(color, (255, 255, 255), 0.6), round(120 * strength)))
    for i in range(14):
        a = math.radians(-90 + (i - 6.5) * 11)
        ln = height * (0.7 + 0.3 * ((i * 37) % 7) / 7)
        ld.line(P(cx, by, cx + ln * math.cos(a), by + ln * math.sin(a)), fill=alpha(color, round(70 * strength)),
                width=round(6 * S))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(10 * S)))
    t.soft_glow(img, (cx - width * 0.5, by - 30, cx + width * 0.5, by + 20), alpha(mix(color, (255, 255, 255), 0.5),
                                                                                   round(220 * strength)), 12)


def draw_chest(img, center, w, tier, opened=False, sealed=False):
    """A treasure chest: body with metal bands and a lock plate; the lid closed (with a talisman seal) or open."""
    cx, cy = center
    body, band, lid = CHEST_LOOK.get(tier, CHEST_LOOK["wooden"])
    h = w * 0.5
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h * 0.2, cy + h * 0.8
    d = ImageDraw.Draw(img)
    d.ellipse(P(x0 - 10, y1 - 10, x1 + 10, y1 + 16), fill=(0, 0, 0, 150))         # shadow
    if opened:                                                                     # lid thrown back
        lh = h * 0.55
        d.polygon([P(x0 + 4, y0), P(x1 - 4, y0), P(x1 - w * 0.06, y0 - lh), P(x0 + w * 0.06, y0 - lh)],
                  fill=mix(lid, (0, 0, 0), 0.35), outline=band)
        d.line(P(x0 + w * 0.06, y0 - lh, x1 - w * 0.06, y0 - lh), fill=band, width=round(4 * S))
        for bx in (0.24, 0.76):
            d.line(P(x0 + w * bx, y0, x0 + w * (bx * 0.88 + 0.06), y0 - lh), fill=band, width=round(7 * S))
    g = t.vgradient(P(w, h), mix(body, (255, 255, 255), 0.12), mix(body, (0, 0, 0), 0.45))
    img.alpha_composite(g, P(x0, y0))
    d = ImageDraw.Draw(img)
    for i in range(1, 5):                                                          # planks
        yy = y0 + h * i / 5
        d.line(P(x0 + 3, yy, x1 - 3, yy), fill=alpha(mix(body, (0, 0, 0), 0.5), 160), width=max(1, S))
    d.rectangle(P(x0, y0, x1, y1), outline=band, width=round(5 * S))
    for bx in (0.24, 0.76):
        d.rectangle(P(x0 + w * bx - 7, y0, x0 + w * bx + 7, y1), fill=band)
        for yy in (y0 + 10, y1 - 10):
            d.ellipse(P(x0 + w * bx - 3, yy - 3, x0 + w * bx + 3, yy + 3), fill=mix(band, (0, 0, 0), 0.4))
    if opened:
        d.ellipse(P(x0 + 10, y0 - 12, x1 - 10, y0 + 14), fill=(20, 12, 8, 255))     # the dark inside
    else:
        lh = h * 0.42
        d.chord(P(x0, y0 - lh, x1, y0 + lh), 180, 360, fill=lid, outline=band, width=round(5 * S))
        for bx in (0.24, 0.76):
            d.line(P(x0 + w * bx, y0, x0 + w * bx, y0 - lh * (1 - (bx - 0.5) ** 2 * 3.2)), fill=band,
                   width=round(14 * S))
    # lock plate
    ly = y0 + (6 if opened else 0)
    d.rounded_rectangle(P(cx - 20, ly - 6, cx + 20, ly + 34), radius=round(5 * S), fill=band,
                        outline=mix(band, (0, 0, 0), 0.4), width=round(2 * S))
    d.ellipse(P(cx - 5, ly + 6, cx + 5, ly + 16), fill=(20, 14, 10))
    d.polygon([P(cx - 3, ly + 14), P(cx + 3, ly + 14), P(cx + 2, ly + 26), P(cx - 2, ly + 26)], fill=(20, 14, 10))
    if sealed:                                                                     # paper talisman 封
        tw, th = 46, 110
        tx, ty = cx, y0 - 20
        paper = Image.new("RGBA", P(tw, th), (232, 206, 120, 255))
        pd = ImageDraw.Draw(paper)
        pd.rectangle((round(4 * S), round(4 * S), paper.size[0] - round(4 * S), paper.size[1] - round(4 * S)),
                     outline=(176, 40, 30, 255), width=round(2 * S))
        pd.text((paper.size[0] / 2, paper.size[1] * 0.32), "封", font=t.cjk(30).font_variant(size=round(30 * S)),
                fill=(176, 30, 24, 255), anchor="mm")
        pd.text((paper.size[0] / 2, paper.size[1] * 0.7), "印", font=t.cjk(24).font_variant(size=round(24 * S)),
                fill=(176, 30, 24, 255), anchor="mm")
        paper = paper.rotate(-6, expand=True, resample=Image.BICUBIC)
        img.alpha_composite(paper, P(tx - paper.size[0] / S / 2, ty - th / 2))


def formation(img, center, r, color):
    """A glowing formation array (rune circle) under the sealed chest."""
    cx, cy = center
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ry = r * 0.32
    for rr, a in ((1.0, 200), (0.82, 140), (0.6, 110)):
        ld.ellipse(P(cx - r * rr, cy - ry * rr, cx + r * rr, cy + ry * rr), outline=alpha(color, a), width=round(2 * S))
    for i in range(8):
        a = math.radians(i * 45 + 22.5)
        ld.line(P(cx + r * 0.6 * math.cos(a), cy + ry * 0.6 * math.sin(a), cx + r * math.cos(a), cy + ry * math.sin(a)),
                fill=alpha(color, 150), width=round(1.5 * S))
    glyphs = "乾坤震巽坎离艮兑"
    for i, ch in enumerate(glyphs):
        a = math.radians(i * 45)
        t.text(ld, (cx + r * 0.91 * math.cos(a), cy + ry * 0.91 * math.sin(a)), ch, t.cjk(13), alpha(color, 230), "mm",
               shadow=False)
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(3 * S)))
    img.alpha_composite(layer)


def motes(img, box, color, n, seed):
    rng = random.Random(seed)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    for _ in range(n):
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        r = rng.choice((1, 1.4, 2, 2.6))
        if r > 1.5:
            t.soft_glow(img, (x - 5, y - 5, x + 5, y + 5), alpha(color, 160), 3)
            d = ImageDraw.Draw(img)
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=alpha(mix(color, (255, 255, 255), 0.5), rng.randint(120, 230)))


def sparkle(d, cx, cy, s, color):
    for a, ln in ((0, s), (90, s), (45, s * 0.45), (135, s * 0.45)):
        dx, dy = math.cos(math.radians(a)) * ln, math.sin(math.radians(a)) * ln
        d.line(P(cx - dx, cy - dy, cx + dx, cy + dy), fill=color, width=round(1.6 * S))


# ── Stage cards ───────────────────────────────────────────────────────

def base(h, color, seed):
    img = k.canvas(W, h, "purse", seed=seed)
    t.soft_glow(img, (W / 2 - 360, 40, W / 2 + 360, h - 40), alpha(color, 70), 70)
    t.frame(img, (6, 6, W - 6, h - 6), corners=True)
    return img


def tier_color(tier):
    return t.RARITY.get(tier, k.GOLD)


def render_sealed(data):
    h = 520
    col = tier_color(data["chest_key"])
    img = base(h, col, 3)
    formation(img, (W / 2, 380), 240, col)
    draw_chest(img, (W / 2, 300), 300, data["chest_key"], sealed=True)
    motes(img, (200, 60, 1000, 440), col, 26, 5)
    d = ImageDraw.Draw(img)
    t.gold_text(img, (W / 2, 58), data["chest_name"].upper(), font("Cinzel.ttf", 40, "Black"), anchor="mm",
                glow=mix(col, (0, 0, 0), 0.4))
    d = ImageDraw.Draw(img)
    t.text(d, (W / 2, 104), "Sealed by an ancient formation", font("Inter.ttf", 20, "Medium"), k.ASH, "mm")
    t.text(d, (W / 2, 486), "Break the seal to see what lies within", font("Cinzel.ttf", 21, "Bold"), k.GOLD, "mm")
    return t.finish(img)


def render_opening(data):
    h = 520
    best = data["best"]
    col = k.accent("purse") if best == "Common" else data["rarity_colors"][best]
    img = base(h, col, 4)
    strength = 0.55 + 0.1 * rank(best)
    light_pillar(img, (W / 2, 290), 300 + 30 * rank(best), 300, col, strength)
    draw_chest(img, (W / 2, 330), 300, data["chest_key"], opened=True)
    motes(img, (180, 40, 1020, 460), col, 30 + 14 * rank(best), 7)
    if rank(best) >= rank("Legendary"):
        d = ImageDraw.Draw(img)
        rng = random.Random(2)
        for _ in range(10 if best == "Legendary" else 18):
            sparkle(d, rng.uniform(200, 1000), rng.uniform(60, 300), rng.uniform(6, 14), alpha((255, 250, 230), 230))
    d = ImageDraw.Draw(img)
    t.gold_text(img, (W / 2, 58), data["chest_name"].upper(), font("Cinzel.ttf", 40, "Black"), anchor="mm",
                glow=mix(col, (0, 0, 0), 0.3))
    d = ImageDraw.Draw(img)
    line = OPENING_LINE[best]
    t.text(d, (W / 2, 476), line, font("Cinzel.ttf", 24, "Bold"), mix(col, (255, 255, 255), 0.45), "mm")
    return t.finish(img)


def tile_frame(img, box, rarity, color, dim=False):
    """A reward tile, styled by rarity."""
    x0, y0, x1, y1 = box
    r = rank(rarity)
    if r >= 2 and not dim:
        t.soft_glow(img, (x0, y0, x1, y1), alpha(color, 50 + 25 * r), 6 + 2 * r, "rect")
    d = ImageDraw.Draw(img)
    shape = k.octagon(box, 9)
    d.polygon(shape, fill=alpha(mix(color, k.PANEL, 0.86 if r else 0.94), 250))
    if r == 5 and not dim:                       # Mythical: a prismatic frame
        hues = [(240, 64, 72), (246, 160, 52), (246, 222, 110), (110, 220, 170), (110, 160, 246), (190, 110, 240)]
        n = len(shape)
        for i in range(n):
            d.line([shape[i], shape[(i + 1) % n]], fill=hues[i % len(hues)], width=round(3 * S))
    else:
        width = (1.2, 1.4, 1.8, 2.0, 2.6, 3)[r]
        d.line(shape + [shape[0]], fill=alpha(color if r else k.BRONZE, 255 if not dim else 120),
               width=round(width * S), joint="curve")
    if r >= 4 and not dim:                       # Legendary and up: an inner gold line and corner gems
        inner = k.octagon((x0 + 5, y0 + 5, x1 - 5, y1 - 5), 7)
        d.line(inner + [inner[0]], fill=alpha(k.GOLD_HI, 150), width=max(1, S), joint="curve")
        for gx, gy in ((x0 + 6, y0 + 6), (x1 - 6, y0 + 6), (x0 + 6, y1 - 6), (x1 - 6, y1 - 6)):
            k.gem(d, gx, gy, 4, color)
    if r >= 3 and not dim:
        d.rectangle(P(x0 + 9, y0 + 1, x1 - 9, y0 + 4), fill=alpha(color, 220))


def reward_tile(img, box, rw, collected=False):
    x0, y0, x1, y1 = box
    color = rw["color"]
    lost = rw.get("lost")
    tile_frame(img, box, rw["rarity"], color, dim=lost)
    d = ImageDraw.Draw(img)
    ix, iy = x0 + 54, (y0 + y1) / 2
    t.soft_glow(img, (ix - 38, iy - 38, ix + 38, iy + 38), alpha(color, 90 if not lost else 30), 10)
    t.icon(img, rw["icon"], (ix, iy), 64, mix(color, (255, 255, 255), 0.15) if not lost else k.ASH_DK)
    d = ImageDraw.Draw(img)
    tx = x0 + 102
    f_n = font("Inter.ttf", 19, "Bold")
    name = rw["name"] + (f" ×{rw['qty']:,}" if rw["qty"] > 1 else "")
    lines = t.wrap(d, name, f_n, x1 - tx - 12, lines=2)
    ny = y0 + 30 - (len(lines) - 1) * 11
    for j, line in enumerate(lines):
        t.text(d, (tx, ny + j * 22), line, f_n, k.PARCHMENT if not lost else k.ASH_DK, "lm")
    t.text(d, (tx, y0 + 70), rw["rarity"].upper(), font("Cinzel.ttf", 14, "Bold"),
           mix(color, (255, 255, 255), 0.35) if not lost else k.ASH_DK, "lm")
    t.text(d, (tx, y0 + 96), t.fit(d, rw["line"], font("Inter.ttf", 16, "SemiBold"), x1 - tx - 12),
           font("Inter.ttf", 16, "SemiBold"), k.GOLD_HI if not lost else k.ASH_DK, "lm")
    if lost:
        k.chip(img, ((x0 + x1) / 2, y1 - 2), "Left behind · bag full", (220, 100, 90), size=13, anchor="m")


def highlight(img, box, rw):
    """The best reward, given a stage of its own (Epic and up)."""
    x0, y0, x1, y1 = box
    color = rw["color"]
    r = rank(rw["rarity"])
    tile_frame(img, box, rw["rarity"], color)
    cx, cy = x0 + 92, (y0 + y1) / 2
    t.soft_glow(img, (cx - 70, cy - 70, cx + 70, cy + 70), alpha(color, 170), 18)
    d = ImageDraw.Draw(img)
    for i in range(16 if r >= 4 else 0):        # rays behind the icon
        a = math.radians(i * 22.5)
        d.line(P(cx + 34 * math.cos(a), cy + 34 * math.sin(a), cx + 66 * math.cos(a), cy + 66 * math.sin(a)),
               fill=alpha(mix(color, (255, 255, 255), 0.4), 120), width=round(2 * S))
    for rr, col, wd in ((52, k.BRONZE_DK, 5), (55, k.GOLD, 1.3)):
        d.ellipse(P(cx - rr, cy - rr, cx + rr, cy + rr), outline=col, width=round(wd * S))
    d.ellipse(P(cx - 48, cy - 48, cx + 48, cy + 48), fill=alpha(mix(color, (0, 0, 0), 0.75), 255))
    t.icon(img, rw["icon"], (cx, cy), 68, mix(color, (255, 255, 255), 0.18))
    d = ImageDraw.Draw(img)
    if r == 5:
        rng = random.Random(9)
        for _ in range(12):
            sparkle(d, rng.uniform(x0 + 20, x1 - 20), rng.uniform(y0 + 10, y1 - 10), rng.uniform(4, 9),
                    alpha((255, 244, 230), 220))
    tx = x0 + 176
    k.ribbon(img, (tx, y0 + 14, tx + 200, y0 + 40), BEST_TITLE.get(rw["rarity"], rw["rarity"].upper()), color)
    f = font("Cinzel.ttf", 30, "Black")
    name = t.fit(ImageDraw.Draw(img), rw["name"].upper(), f, x1 - tx - 20)
    t.gold_text(img, (tx, y0 + 52), name, f, glow=mix(color, (0, 0, 0), 0.3))
    d = ImageDraw.Draw(img)
    t.text(d, (tx, y0 + 106), t.fit(d, rw["line"] or rw["kind"], font("Inter.ttf", 19, "Bold"), x1 - tx - 20),
           font("Inter.ttf", 19, "Bold"), mix(color, (255, 255, 255), 0.45), "lm")
    if rw.get("flavor"):
        t.text(d, (tx, y0 + 136), t.fit(d, rw["flavor"], font("Inter.ttf", 17, "Medium"), x1 - tx - 20),
               font("Inter.ttf", 17, "Medium"), k.PARCHMENT, "lm")


def render_rewards(data):
    """The reveal (or, with data['collected'], the collected receipt)."""
    rewards = data["rewards"]
    best = data["best"]
    col = data["rarity_colors"][best] if best != "Common" else k.accent("purse")
    top = rewards[0] if rewards and rank(rewards[0]["rarity"]) >= rank("Epic") else None
    rest = rewards[1:] if top else rewards
    cols = 3
    rows = max(1, math.ceil(len(rest) / cols)) if rest else 0
    tile_h, gap = 124, 14
    y = 142
    hl_h = 156
    h = y + (hl_h + 18 if top else 0) + rows * (tile_h + gap) + 28 * len(data["notes"]) + 56
    h = max(h, 340)
    img = base(h, col, 6)
    # header: opened chest, title and coins
    light_pillar(img, (104, 72), 110, 60, col, 0.6 + 0.08 * rank(best))
    draw_chest(img, (104, 80), 100, data["chest_key"], opened=True)
    t.gold_text(img, (200, 26), data["chest_name"].upper(), font("Cinzel.ttf", 36, "Black"),
                glow=mix(col, (0, 0, 0), 0.4))
    d = ImageDraw.Draw(img)
    n = len(rewards)
    found = f"{n} treasure{'s' if n != 1 else ''}" if n else "Lotus Coins"
    sub = f"{found} added to your bag" if data["collected"] else f"{found} revealed"
    t.text(d, (202, 94), sub, font("Cinzel.ttf", 20, "Bold"), mix(col, (255, 255, 255), 0.4), "lm")
    # Lotus Coins
    t.medallion(img, (W - 240, 66), 32, "lotus", k.LOTUS, cjk_char=False)
    d = ImageDraw.Draw(img)
    t.text(d, (W - 196, 56), f"+{data['coins']:,}", font("Inter.ttf", 34, "Bold"), k.LOTUS, "lm")
    t.spaced(d, (W - 194, 92), "LOTUS COINS", font("Cinzel.ttf", 13, "Bold"), k.ASH, 2)
    t.divider(d, 30, W - 30, 128)
    if top:
        highlight(img, (30, y, W - 30, y + hl_h), top)
        y += hl_h + 18
    tw = (W - 60 - gap * (cols - 1)) / cols
    for i, rw in enumerate(rest):
        r, c = divmod(i, cols)
        x0, y0 = 30 + c * (tw + gap), y + r * (tile_h + gap)
        reward_tile(img, (x0, y0, x0 + tw, y0 + tile_h), rw, data["collected"])
    y += rows * (tile_h + gap)
    if not rewards:
        d = ImageDraw.Draw(img)
        t.text(d, (W / 2, y + 60), "Only Lotus Coins this time. Nothing else lay inside.",
               font("Inter.ttf", 19, "Medium"), k.ASH, "mm")
        y += 110
    d = ImageDraw.Draw(img)
    for note in data["notes"]:
        plain = note.replace("**", "")
        plain = plain.split(" ", 1)[1] if plain and not plain[0].isascii() else plain   # drop the leading emoji
        t.text(d, (W / 2, y + 14), plain, font("Inter.ttf", 17, "SemiBold"), k.GOLD_HI, "mm")
        y += 28
    if data["collected"]:
        stamp(img, (W - 360, 72), "收", "COLLECTED")
    return t.finish(img)


def stamp(img, center, glyph, word):
    """A vermilion seal stamp, slightly tilted."""
    cx, cy = center
    s = 46
    layer = Image.new("RGBA", P(2 * s + 20, 2 * s + 40), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    o = 10 * S
    ld.rounded_rectangle((o, o, o + 2 * s * S, o + 2 * s * S), radius=round(6 * S), outline=(214, 60, 48, 230),
                         width=round(4 * S))
    ld.text((o + s * S, o + s * S), glyph, font=t.cjk(52).font_variant(size=round(52 * S)), fill=(214, 60, 48, 230),
            anchor="mm")
    ld.text((o + s * S, o + (2 * s + 18) * S), word, font=font("Cinzel.ttf", 13, "Black").font_variant(size=round(13 * S)),
            fill=(214, 60, 48, 230), anchor="mm")
    layer = layer.rotate(-10, expand=True, resample=Image.BICUBIC)
    img.alpha_composite(layer, P(cx - layer.size[0] / S / 2, cy - layer.size[1] / S / 2))


def render_chest(data):
    stage = data["stage"]
    if stage == "sealed":
        return render_sealed(data)
    if stage == "opening":
        return render_opening(data)
    return render_rewards(data)
