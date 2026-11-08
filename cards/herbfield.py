"""
The /gather "herb field" card that the bot edits every round (docs/alchemy.md section 2).

  ┌ scene window: the place being searched (misty slope, riverbank, old pines, waterfall, meadow,
  │   shrine ruins, bamboo grove), in jade night colours
  │   over it: "Herb field · place · tier", the "You are looking for" plate (herb icon, name, tier, type,
  │   what it is used for, the description), a countdown ring and the Herbal Insight streak with its bonus
  ├ 4 (6 for old herbs) choice cards: a number, a drawn plant (cards/plants.py) and its LOOK text
  └ "This session" (herbs gathered with ages, best find) and "Careful" (what a mistake costs, HP)

After a pick the same card shows the result: the right plant ringed in green, a wrong pick in red.
The Wandering Spirit check has its own small card (render_spirit).

Both take plain data (bot/gather_card.py) so they can run off the event loop. Place scenes and plant
pictures are cached. Discord shows the card at under half size on a computer, so nothing is under 24px.
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from . import theme as T
from .scenes import photo, subject
from . import wilds as Wd
from .battle import _shrink
from .plants import PH, PW, plant
from .theme import P, S, alpha, font, mix

W, H = 1200, 940
H_SPIRIT = 560
SCENE = (16, 16, 1184, 398)
SW, SH = SCENE[2] - SCENE[0], SCENE[3] - SCENE[1]
CHOICES_Y = (412, 734)
SESSION = (16, 748, 790, 924)
CAREFUL = (802, 748, 1184, 924)

JADE = (92, 214, 170)
JADE_HI = (150, 240, 200)
JADE_DK = (24, 70, 58)
PANEL_FILL = (8, 22, 20)
WHITE = (255, 248, 232)
GREEN_OK = (110, 226, 130)
RED_BAD = (236, 70, 56)
TYPE_LABEL = {"qi": "Qi", "healing": "Healing", "purity": "Purity", "breakthrough": "Breakthrough"}
TYPE_USE = {"qi": "for Qi pills", "healing": "for Mending pills", "purity": "used in every recipe",
            "breakthrough": "for Breakthrough pills"}
TYPE_SHORT = {"qi": "Qi pills", "healing": "Mending pills", "purity": "all recipes",
              "breakthrough": "Breakthrough pills"}
HERB_COLOR = {"qi": (110, 170, 240), "healing": (232, 96, 96), "purity": (100, 206, 196),
              "breakthrough": (204, 150, 92)}
HERB_ICON = {"qi": "misc:herb_qi", "healing": "misc:herb_healing", "purity": "misc:herb_purity",
             "breakthrough": "misc:herb_breakthrough"}
# plate colour for rare grades (Common and Uncommon keep the bronze frame)
RARITY_COLOR = {"Rare": (120, 190, 255), "Very Rare": (200, 140, 255), "Legendary": (255, 205, 90)}

OUTCOME = {"gathered": ("Gathered", GREEN_OK, "check"), "full": ("Bag full", (236, 196, 90), "check"),
           "poison": ("Poisoned", RED_BAD, "skull"), "wrong": ("Wrong plant", (236, 150, 70), "cross"),
           "slow": ("Too slow", (190, 180, 160), "hourglass"), "passed": ("Passed", GREEN_OK, "check"),
           "failed": ("Wrong sign", RED_BAD, "cross")}


# ── the places (cached) ───────────────────────────────────────────────

PLACES = ("the misty slope", "the riverbank", "the shade of old pines", "the foot of a waterfall",
          "a sunlit meadow", "the ruins of a mountain shrine", "the edge of a bamboo grove")
PLACE_NAME = {"the misty slope": "Misty Slope", "the riverbank": "Riverbank", "the shade of old pines": "Old Pines",
              "the foot of a waterfall": "Waterfall",
              "a sunlit meadow": "Sunlit Meadow", "the ruins of a mountain shrine": "Shrine Ruins",
              "the edge of a bamboo grove": "Bamboo Grove"}


PLACE_ART = {"the misty slope": "gather_misty_slope", "the riverbank": "gather_riverbank",
             "the shade of old pines": "gather_old_pines",
             "the foot of a waterfall": "gather_waterfall", "a sunlit meadow": "gather_sunlit_meadow",
             "the ruins of a mountain shrine": "gather_shrine_ruins", "the edge of a bamboo grove": "gather_bamboo_grove"}


@lru_cache(maxsize=10)
def place_scene(place, spirit=False):
    """The searched place as the scene window background (S×, RGBA): the painting (art/scenes/gather_*.jpg),
    dimmed a little so the text on it reads, or a drawn scene when the painting is missing."""
    h = SH if not spirit else H_SPIRIT - 32
    art = photo(PLACE_ART.get(place), SW * S, round(h * S))
    if art is not None:
        art = art.copy()
        shade = Image.new("RGBA", art.size, (6, 10, 10, 70))
        art.alpha_composite(shade)
        return art
    return _drawn_scene(place, h)


def _drawn_scene(place, h):
    """The old drawn scene, used when a place has no painting."""
    sunny = place == "a sunlit meadow"
    top, bottom = ((26, 60, 54), (70, 120, 96)) if sunny else ((6, 18, 18), (26, 66, 58))
    img = Wd.sky(SW, h, top, bottom).convert("RGBA")
    r = random.Random(place)
    d = ImageDraw.Draw(img)
    Wd.motes(d, SW, h * 0.6, (220, 250, 240), 40, 1, r0=0.8, r1=1.8)
    mx, my = SW * 0.78, 80
    Wd.glow(img, mx, my, 90, 90, (230, 250, 230) if not sunny else (255, 240, 180), 130, 30)
    d = ImageDraw.Draw(img)
    d.ellipse(P(mx - 40, my - 40, mx + 40, my + 40), fill=(236, 244, 226, 235) if not sunny else (255, 244, 200, 240))
    base = h * 0.72
    Wd.ridge(d, SW, base - 50, 80, 11, (22, 56, 50, 255), peaks=5)
    Wd.ridge(d, SW, base, 60, 4, (14, 40, 36, 255), peaks=7)
    if place == "the misty slope":
        d.polygon([P(0, base - 40), P(SW, base + 60), P(SW, h), P(0, h)], fill=(16, 44, 38, 255))
        Wd.mist(img, SW, base, 90, (200, 236, 226), 130, seed=2, n=14)
    elif place == "the riverbank":
        d.polygon([P(0, base + 10), P(SW, base - 10), P(SW, base + 50), P(0, base + 70)], fill=(40, 90, 100, 255))
        for k in range(14):
            x = r.uniform(0, SW)
            d.line(P(x, base + 20 + r.uniform(0, 30), x + 50, base + 20 + r.uniform(0, 30)), fill=(150, 210, 220, 150),
                   width=max(1, round(1.5 * S)))
    elif place == "the shade of old pines":
        for i in range(16):
            Wd.pine(d, i * 80 + r.uniform(-20, 20), base + 30, r.uniform(160, 280), (8, 26, 22, 255))
    elif place == "the foot of a waterfall":
        d.polygon([P(SW * 0.35, 0), P(SW * 0.65, 0), P(SW * 0.62, base + 20), P(SW * 0.38, base + 20)],
                  fill=(20, 46, 44, 255))
        for k in range(10):
            x = SW * 0.44 + k * 14
            d.line(P(x, 0, x + r.uniform(-4, 4), base + 20), fill=(190, 230, 240, 170), width=round(4 * S))
        Wd.mist(img, SW, base + 20, 60, (220, 245, 250), 160, seed=5)
    elif place == "a sunlit meadow":
        Wd.rays(img, mx, my, h, (255, 246, 210), n=8, spread=60, a=60, seed=3)
        d = ImageDraw.Draw(img)
        for _ in range(120):
            x, y = r.uniform(0, SW), r.uniform(base + 10, h)
            col = r.choice([(255, 236, 150), (250, 250, 240), (240, 160, 200)])
            d.ellipse(P(x - 3, y - 3, x + 3, y + 3), fill=alpha(col, 220))
    elif place == "the ruins of a mountain shrine":
        x = SW * 0.32
        for px, ph in ((x - 80, 150), (x + 80, 110), (x + 220, 60)):
            d.rectangle(P(px - 12, base + 20 - ph, px + 12, base + 20), fill=(30, 50, 46, 255))
        d.polygon([P(x - 120, base - 130), P(x + 120, base - 130), P(x + 100, base - 112), P(x - 100, base - 112)],
                  fill=(30, 50, 46, 255))
    elif place == "the edge of a bamboo grove":
        for i in range(26):
            x = i * 46 + r.uniform(-10, 10)
            if SW * 0.25 < x < SW * 0.75 and r.random() < 0.7:
                continue
            Wd.bamboo(d, x, h, r.uniform(h * 0.7, h), (12, 40, 30, 255), width=r.uniform(8, 12), seed=r.random())
    d = ImageDraw.Draw(img)
    Wd.grass_tufts(d, SW, h - 30, (40, 90, 70, 255), 120, 7, 10, 30)
    return img


# ── pieces ────────────────────────────────────────────────────────────

GLASS_EDGE = (255, 255, 255, 52)
TEXT = (246, 242, 232)
SOFT = (200, 206, 200)


def _backdrop(place):
    """The whole card behind the panels: the place's painting, blurred and dimmed (or the old canvas)."""
    art = photo(PLACE_ART.get(place), W * S, H * S)
    if art is None:
        return T.canvas(W, H, seed=37, accent="train")
    img = art.filter(ImageFilter.GaussianBlur(14 * S))
    img.alpha_composite(Image.new("RGBA", img.size, (6, 10, 12, 150)))
    # darker towards the bottom, where the text sits
    fade = Image.linear_gradient("L").resize(img.size).point(lambda v: round(v * 0.45))
    layer = Image.new("RGBA", img.size, (4, 6, 8, 0))
    layer.putalpha(fade)
    img.alpha_composite(layer)
    return img


def _glass(img, box, tint=(10, 16, 18), a=96, edge=GLASS_EDGE, r=18):
    """A frosted glass panel: what is behind it blurred, a light tint, a thin bright edge, round corners."""
    x0, y0, x1, y1 = (round(v * S) for v in box)
    rr = round(r * S)
    region = img.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(10 * S))
    tinted = Image.new("RGBA", region.size, tint + (a,))
    region.alpha_composite(tinted)
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, region.size[0] - 1, region.size[1] - 1), radius=rr, fill=255)
    img.paste(region, (x0, y0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0, y0, x1, y1), radius=rr, outline=edge, width=max(1, round(1.2 * S)))
    # a faint highlight along the top edge
    d.line((x0 + rr, y0 + round(1.5 * S), x1 - rr, y0 + round(1.5 * S)), fill=(255, 255, 255, 40), width=max(1, S))


def _scrim(img, box, a=200):
    x0, y0, x1, y1 = box
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rectangle(P(x0, y0, x1, y1), fill=alpha((4, 14, 12), a))
    img.alpha_composite(layer)


def _frame_box(img, box, color=T.BRONZE, glow=None, width=2):
    x0, y0, x1, y1 = box
    if glow:                                    # a glow around the edge only, so the plant stays visible
        T.soft_glow(img, (x0 - 6, y0 - 6, x1 + 6, y0 + 6), alpha(glow, 140), 6, "rect")
        T.soft_glow(img, (x0 - 6, y1 - 6, x1 + 6, y1 + 6), alpha(glow, 140), 6, "rect")
        T.soft_glow(img, (x0 - 6, y0, x0 + 6, y1), alpha(glow, 140), 6, "rect")
        T.soft_glow(img, (x1 - 6, y0, x1 + 6, y1), alpha(glow, 140), 6, "rect")
    d = ImageDraw.Draw(img)
    d.rectangle(P(x0, y0, x1, y1), outline=alpha(color, 255), width=round(width * S))
    for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        T.stud(d, cx, cy, 4)


def ring(img, center, r, seconds, outcome=None):
    """The countdown ring: full at the start of the round (Discord can't animate it, the text has a live timer)."""
    cx, cy = center
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6), fill=(4, 14, 12, 230), outline=alpha(T.BRONZE, 220),
              width=round(2 * S))
    if outcome:
        label, color, glyph = OUTCOME[outcome]
        d.arc(P(cx - r, cy - r, cx + r, cy + r), 0, 360, fill=alpha(color, 255), width=round(10 * S))
        _mark(img, (cx, cy - 6), r * 0.62, glyph, color)
        return
    T.soft_glow(img, (cx - r, cy - r, cx + r, cy + r), alpha(JADE, 60), 10)
    d = ImageDraw.Draw(img)
    d.arc(P(cx - r, cy - r, cx + r, cy + r), 0, 360, fill=alpha(JADE, 255), width=round(10 * S))
    T.gold_text(img, (cx, cy - 2), f"{seconds:g}s", font("Cinzel.ttf", 48, "Black"), "mm")


def _mark(img, center, size, glyph, color):
    d = ImageDraw.Draw(img)
    cx, cy = center
    s = size / 2
    if glyph == "check":
        d.line([P(cx - s, cy), P(cx - s * 0.3, cy + s * 0.7), P(cx + s, cy - s * 0.75)], fill=alpha(color, 255),
               width=round(size * 0.16 * S), joint="curve")
    elif glyph == "cross":
        for a, b in (((-1, -1), (1, 1)), ((-1, 1), (1, -1))):
            d.line(P(cx + a[0] * s * 0.7, cy + a[1] * s * 0.7, cx + b[0] * s * 0.7, cy + b[1] * s * 0.7),
                   fill=alpha(color, 255), width=round(size * 0.16 * S))
    else:
        T.icon(img, glyph, center, size, color)


def number_badge(img, center, n, color=JADE, r=22):
    cx, cy = center
    d = ImageDraw.Draw(img)
    T.soft_glow(img, (cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4), alpha(color, 110), 5)
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=(6, 20, 18, 255), outline=alpha(T.GOLD, 255), width=round(2 * S))
    d.ellipse(P(cx - r + 4, cy - r + 4, cx + r - 4, cy + r - 4), outline=alpha(color, 230), width=round(1.5 * S))
    T.text(d, (cx, cy + 1), str(n), font("Cinzel.ttf", 28, "Black"), mix(color, WHITE, 0.4), "mm")


def _streak(img, x, y, data):
    """The Herbal Insight streak, in two short lines."""
    T.icon(img, "flame", (x + 18, y), 40, (246, 150, 60))
    T.gold_text(img, (x + 48, y), f"×{data['streak']}", font("Cinzel.ttf", 44, "Black"), "lm")
    d = ImageDraw.Draw(img)
    w = T.width(d, f"×{data['streak']}", font("Cinzel.ttf", 44, "Black"))
    T.text(d, (x + 60 + w, y + 4), "streak", font("Inter.ttf", 30, "Bold"), TEXT, "lm")
    parts = []
    if data["streak_mult"] > 1:
        parts.append(f"old herbs ×{data['streak_mult']:g}")
    nxt = data.get("streak_next")
    if nxt:
        parts.append(f"×{nxt[1]:g} at {nxt[0]}")
    if parts:
        T.text(d, (x, y + 46), "  ·  ".join(parts), font("Inter.ttf", 27, "SemiBold"), SOFT, "lm")


def _choice(img, box, n, ch, result, color=JADE):
    """One choice card: the number, the drawn plant and its look text. After a pick: green for the herb,
    red for a wrong pick."""
    x0, y0, x1, y1 = box
    state = None
    if result:
        if ch["key"] == result["answer"]:
            state = GREEN_OK
        elif ch["key"] == result.get("picked"):
            state = RED_BAD
    _glass(img, box, tint=(8, 14, 16) if not state else mix(state, (8, 14, 16), 0.8), a=110 if state else 92,
           edge=alpha(state, 230) if state else GLASS_EDGE)
    pic = (x0 + 12, y0 + 10, x1 - 12, y0 + 10 + (x1 - x0 - 24) * PH / PW)
    if pic[3] > y0 + 160:
        pic = (x0 + 12, y0 + 10, x1 - 12, y0 + 160)
    pw, ph = pic[2] - pic[0], pic[3] - pic[1]
    T.soft_glow(img, (pic[0] + pw * 0.2, pic[1] + ph * 0.15, pic[2] - pw * 0.2, pic[3] - ph * 0.05),
                (200, 240, 220, 46), 26)
    scale = min(pw / PW, ph / PH)
    im = plant(ch["name"])
    im = im.resize((round(PW * scale * S), round(PH * scale * S)), Image.LANCZOS)
    img.alpha_composite(im, (round((pic[0] + (pw - PW * scale) / 2) * S), round((pic[1] + (ph - PH * scale) / 2) * S)))
    number_badge(img, (pic[0] + 26, pic[1] + 26), n, color)
    d = ImageDraw.Draw(img)
    room = x1 - x0 - 28
    text, f = ch["look"], None
    max_lines = 3 if room > 220 else 4
    for size in (31, 29, 27, 25):
        f = font("Inter.ttf", size, "SemiBold")
        lines = T.wrap(d, text, f, room, lines=max_lines)
        if " ".join(lines).replace(" …", "") == text or size == 25:
            break
    top = pic[3] + 8
    space = y1 - 12 - top
    step = f.size / S + 6
    ty = top + max(0, (space - step * len(lines)) / 2) + step / 2
    for i, line in enumerate(lines):
        T.text(d, ((x0 + x1) / 2, ty + i * step), line, f, TEXT if not state else mix(state, WHITE, 0.55), "mm")
    if state:
        T.soft_glow(img, (x0 - 4, y0 - 4, x1 + 4, y1 + 4), alpha(state, 70), 12, "rect")
        cx, cy = pic[2] - 28, pic[3] - 28
        d = ImageDraw.Draw(img)
        d.ellipse(P(cx - 20, cy - 20, cx + 20, cy + 20), fill=(6, 16, 14, 255), outline=alpha(state, 255),
                  width=round(2 * S))
        _mark(img, (cx, cy), 24, "check" if state == GREEN_OK else "cross", state)


def _heading(img, box, title):
    x0, y0, x1, _ = box
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 24, "Bold")
    T.spaced(d, (x0 + 24, y0 + 32), title.upper(), f, (236, 210, 150), 2.4)


def session_panel(img, data):
    box = SESSION
    _glass(img, box)
    _heading(img, box, f"Gathered  ·  {data['gathered']}")
    x0, y0, x1, y1 = box
    rows = data["session"]
    d = ImageDraw.Draw(img)
    if not rows:
        T.text(d, (x0 + 26, y0 + 98), "Nothing yet", font("Inter.ttf", 30, "Medium"), SOFT, "lm")
        return
    tw = (x1 - x0 - 30) / 3
    for i, row in enumerate(rows[:3]):
        x, cy = x0 + 22 + i * tw, y0 + 98
        col = HERB_COLOR.get(row["type"], JADE)
        T.seal(img, (x + 28, cy), 27, HERB_ICON.get(row["type"], "herb"), col)
        d = ImageDraw.Draw(img)
        f = font("Inter.ttf", 27, "Bold")
        T.text(d, (x + 64, cy - 16), T.fit(d, row["name"], f, tw - 70), f, TEXT, "lm")
        T.text(d, (x + 64, cy + 18), f"{row['age']}-yr ×{row['qty']}", font("Inter.ttf", 26, "Medium"),
               JADE_HI if row["age"] >= 100 else SOFT, "lm")
    if data.get("best"):
        f = font("Inter.ttf", 26, "SemiBold")
        T.text(d, (x0 + 26, y1 - 24), T.fit(d, f"Best: {data['best']}", f, x1 - x0 - 50), f, (250, 214, 120), "lm")


def careful_panel(img, data):
    box = CAREFUL
    _glass(img, box)
    x0, y0, x1, y1 = box
    T.icon(img, "skull", (x0 + 36, y0 + 46), 32, RED_BAD)
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 28, "Bold")
    T.text(d, (x0 + 66, y0 + 46), "Poison", f, (255, 150, 130), "lm")
    f2 = font("Inter.ttf", 26, "Medium")
    for i, line in enumerate(T.wrap(d, data["decoy_note"], f2, x1 - x0 - 50, lines=2)):
        T.text(d, (x0 + 26, y0 + 86 + i * 32), line, f2, SOFT, "lm")
    T.icon(img, "heart", (x0 + 36, y1 - 30), 28, (226, 84, 72))
    d = ImageDraw.Draw(img)
    T.text(d, (x0 + 66, y1 - 30), f"HP {data['hp']:,} / {data['max_hp']:,}", f, TEXT, "lm")


# ── the cards ─────────────────────────────────────────────────────────

def render_field(data):
    """data: place, tier, name, type, age, old, desc, seconds, streak, streak_mult, streak_next (n, mult) or None,
    choices [{key, name, look}], result None or {answer, picked, outcome, text}, session [{name, type, age, qty}],
    gathered, best, hp, max_hp, decoy_note."""
    img = _backdrop(data["place"])
    img.alpha_composite(place_scene(data["place"]), P(SCENE[0], SCENE[1]))
    T.frame(img, SCENE, 0.8)
    x0, y0, x1, y1 = SCENE
    d = ImageDraw.Draw(img)
    T.spaced(d, (x0 + 30, y0 + 34), PLACE_NAME.get(data["place"], data["place"]).upper(),
             font("Cinzel.ttf", 26, "Bold"), mix(T.GOLD, WHITE, 0.2), 2.4)
    rarity = data.get("rarity", "Common")
    rare_col = RARITY_COLOR.get(rarity)

    # the "you are looking for" plate (framed in the rarity's colour for Rare and above)
    plate = (x0 + 24, y0 + 64, x0 + 790, y1 - 22)
    _scrim(img, plate, 205)
    _frame_box(img, plate, rare_col or T.BRONZE)
    px0, py0, px1, py1 = plate
    col = HERB_COLOR.get(data["type"], JADE)
    T.seal(img, (px0 + 66, py0 + 120), 48, HERB_ICON.get(data["type"], "herb"), col)
    d = ImageDraw.Draw(img)
    tx = px0 + 132
    T.spaced(d, (tx, py0 + 34), f"FIND  ·  {rarity.upper()}" if rare_col else "FIND",
             font("Cinzel.ttf", 26, "Bold"), rare_col or T.GOLD, 2.4)
    name = (f"{data['age']}-year " if data["old"] else "") + data["name"]
    name, nf = _shrink(d, name.upper(), "Cinzel.ttf", "Black", (62, 54, 46, 38), px1 - tx - 16)
    T.gold_text(img, (tx, py0 + 90), name, nf, "lm",
                glow=rare_col or (col if not data["old"] else (250, 220, 120)))
    d = ImageDraw.Draw(img)
    meta = f"{data['tier']}  ·  {TYPE_SHORT.get(data['type'], data['type'])}"
    f = font("Inter.ttf", 30, "SemiBold")
    T.text(d, (tx, py0 + 146), T.fit(d, meta, f, px1 - tx - 16), f, JADE_HI, "lm")
    f = font("Inter.ttf", 34, "Medium")
    lines = T.wrap(d, data["desc"], f, px1 - px0 - 48, lines=2)
    for i, line in enumerate(lines):
        T.text(d, (px0 + 26, py0 + 206 + i * 42), line, f, TEXT, "lm")
    if data["old"]:
        T.text(d, (px0 + 26, py1 - 20), "Old herb: less time, more choices",
               font("Inter.ttf", 27, "Bold"), (250, 214, 120), "lm")

    # countdown ring and streak
    result = data.get("result")
    rcx = x0 + 900
    ring(img, (rcx, y0 + 98), 58, data["seconds"], result and result["outcome"])
    d = ImageDraw.Draw(img)
    if result:
        T.text(d, (rcx, y0 + 188), OUTCOME[result["outcome"]][0], font("Inter.ttf", 30, "Bold"),
               OUTCOME[result["outcome"]][1], "mm")
    _streak(img, x0 + 836, y0 + 250, data)

    # the choices
    ch = data["choices"]
    n = len(ch)
    gap = 12
    cw = (W - 32 - gap * (n - 1)) / n
    for i, c in enumerate(ch):
        bx = 16 + i * (cw + gap)
        _choice(img, (bx, CHOICES_Y[0], bx + cw, CHOICES_Y[1]), i + 1, c, result)
    session_panel(img, data)
    careful_panel(img, data)
    return T.finish(img)


def _spirit(img, cx, base, h):
    """A pale floating spirit: hooded head, trailing robe, two dark eyes."""
    Wd.glow(img, cx, base - h * 0.5, h * 0.5, h * 0.6, (200, 240, 255), 120, 24)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    d.ellipse(P(cx - h * 0.18, base - h, cx + h * 0.18, base - h * 0.64), fill=(226, 244, 250, 220))
    pts = [(cx - h * 0.2, base - h * 0.8), (cx + h * 0.2, base - h * 0.8), (cx + h * 0.32, base - h * 0.3),
           (cx + h * 0.1, base), (cx - h * 0.05, base - h * 0.12), (cx - h * 0.2, base - h * 0.02),
           (cx - h * 0.32, base - h * 0.3)]
    d.polygon([P(*p) for p in pts], fill=(214, 236, 246, 190))
    for sx in (-1, 1):
        d.ellipse(P(cx + sx * h * 0.07 - 6, base - h * 0.84, cx + sx * h * 0.07 + 6, base - h * 0.78), fill=(20, 40, 50, 255))
        d.line(P(cx + sx * h * 0.2, base - h * 0.7, cx + sx * h * 0.42, base - h * 0.55), fill=(214, 236, 246, 200),
               width=round(10 * S))
    img.alpha_composite(Wd.blur(layer, 1.2))


def render_spirit(data):
    """data: place, sign (word, e.g. 'the moon'), seconds, fails_left, result None or {outcome, text}."""
    img = T.canvas(W, H_SPIRIT, seed=41, accent="train")
    sc = place_scene(data["place"], spirit=True)
    img.alpha_composite(sc, P(16, 16))
    Wd.mist(img, W, H_SPIRIT - 160, 180, (210, 236, 240), 150, seed=9, n=16)
    ghost = subject("gather_wandering_spirit")
    if ghost is not None:
        gh = round(470 * S)
        ghost = ghost.resize((round(ghost.size[0] * gh / ghost.size[1]), gh), Image.LANCZOS)
        Wd.glow(img, 930, H_SPIRIT - 280, 200, 260, (170, 230, 250), 110, 30)
        img.alpha_composite(ghost, (round(930 * S - ghost.size[0] / 2), round((H_SPIRIT - 40) * S) - gh))
    else:
        _spirit(img, 920, H_SPIRIT - 70, 360)
    T.frame(img, (16, 16, W - 16, H_SPIRIT - 16), 0.8)
    plate = (40, 60, 760, H_SPIRIT - 50)
    _scrim(img, plate, 205)
    _frame_box(img, plate, T.BRONZE)
    px0, py0, px1, py1 = plate
    d = ImageDraw.Draw(img)
    T.spaced(d, (px0 + 30, py0 + 40), "A WANDERING SPIRIT", font("Cinzel.ttf", 24, "Bold"), T.GOLD, 2.2)
    T.gold_text(img, (px0 + 30, py0 + 100), "IT BLOCKS YOUR PATH", font("Cinzel.ttf", 40, "Black"), "lm", glow=JADE)
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 30, "SemiBold")
    T.text(d, (px0 + 30, py0 + 170), "“Press the button showing", f, T.PARCHMENT, "lm")
    T.text(d, (px0 + 30, py0 + 214), f"{data['sign']},” it whispers.", f, JADE_HI, "lm")
    result = data.get("result")
    f2 = font("Inter.ttf", 25, "Medium")
    if result:
        lines = T.wrap(d, result["text"], f2, px1 - px0 - 60, lines=3)
        for i, line in enumerate(lines):
            T.text(d, (px0 + 30, py0 + 280 + i * 34), line, f2, OUTCOME[result["outcome"]][1], "lm")
    else:
        T.text(d, (px0 + 30, py0 + 280), "It checks that you are not a puppet.", f2, T.ASH, "lm")
        T.text(d, (px0 + 30, py0 + 316), f"{data['fails_left']} wrong answer{'s' if data['fails_left'] != 1 else ''} "
               f"pause gathering.", f2, T.ASH, "lm")
    ring(img, (1080, 110), 58, data["seconds"], result and result["outcome"])
    return T.finish(img)
