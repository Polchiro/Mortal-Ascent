"""
The /explore cards that the bot edits at every step (docs/explore.md).

Crossroads (render_crossroads):
  ┌ scene window: three paths fan out from the bottom centre. Each third of the scene shows the mood of the
  │   clue on that path (dark pines and red eyes for growling, a golden glow, a misty lake for silence ...).
  │   A misleading clue is drawn as what it SAYS, never as what is really there.
  │   Over the scene: region, realm, "Step X / 5" with dots, an arrow badge and a short label on each path.
  ├ three clue cards: Left / Middle / Right with the full clue
  └ "Found so far" (loot tiles, what a defeat costs) and "You" (HP, danger meter, the deeper-step bonuses)

Encounter (render_encounter): the same frame with the real encounter's own scene (the chest, the merchant's
cart, the hermit ...), a title plate, "What happened" and the same two bottom panels. Fights hand over to
the fight screen (cards/battle.py); after a fight the result is drawn over that beast's own scene.

Both take plain data (bot/explore_card.py), so they can run off the event loop. The mood pieces and the
encounter scenes are cached; only the badges, text and panels are drawn each time. Discord shows the card at
under half size on a computer, so nothing on it is under 24px.
"""
import math
import random
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter

from . import theme as T
from . import wilds as Wd
from .battle import _shrink
from .theme import P, S, alpha, font, mix

W, H = 1200, 910
SCENE = (16, 16, 1184, 470)
SW, SH = SCENE[2] - SCENE[0], SCENE[3] - SCENE[1]
CLUES = [(16, 484, 397, 630), (409, 484, 791, 630), (803, 484, 1184, 630)]
STORY = (16, 484, 1184, 630)
FOUND = (16, 644, 820, 894)
YOU = (832, 644, 1184, 894)

HORIZON = 322                         # scene-local y where the ground starts
MOOD_W = 540                          # width of one path's mood on the crossroads
PATH_X = {"left": 196, "middle": SW / 2, "right": SW - 196}   # scene-local x of each path's far end
PATH_END_Y = {"left": 338, "middle": 326, "right": 338}
BADGE_Y = {"left": 238, "middle": 206, "right": 238}
SIDE = {"left": "Left", "middle": "Middle", "right": "Right"}
WHITE = (255, 248, 232)

# encounter kind → (mood colour, the place it is drawn as, card icon)
MOOD = {
    "wild_beast":         ((236, 84, 62), "the dark pines", "skull"),
    "treasure_chest":     ((246, 196, 86), "the golden hollow", "chest"),
    "herb_patch":         ((110, 214, 120), "the flower meadow", "herb"),
    "ore_vein":           ((214, 150, 96), "the glittering cliff", "mat:base:weapon:1"),
    "peaceful_clearing":  ((150, 196, 236), "the misty lake", "lotus"),
    "hazard":             ((196, 214, 82), "the crumbling slope", "skull"),
    "bandits":            ((240, 140, 60), "the smoky camp", "sword"),
    "wandering_merchant": ((236, 176, 92), "the old trade road", "pill"),
    "injured_stranger":   ((226, 96, 96), "the bloodied trail", "heart"),
    "stone_tablet":       ((150, 200, 170), "the stone circle", "scroll"),
    "elite_lair":         ((222, 120, 70), "the bone cave", "skull"),
    "blessed_land":       ((250, 232, 160), "the shining glade", "star"),
    "wandering_hermit":   ((186, 160, 240), "the incense path", "scroll"),
    "beast_king_den":     ((255, 60, 50), "the torn forest", "skull"),
}


# ── the moods (one per clue kind, cached) ─────────────────────────────

def _dark(c, t=0.75):
    return alpha(mix(c, (0, 0, 0), t), 255)


def _m_beast(img, w, h, r):
    d = ImageDraw.Draw(img)
    Wd.glow(img, w / 2, h * 0.62, w * 0.45, h * 0.3, (120, 20, 16), 120, 30)
    d = ImageDraw.Draw(img)
    for i in range(int(w / 70) + 2):
        Wd.pine(d, -20 + i * 70 + r.uniform(-14, 14), HORIZON + 10, r.uniform(200, 290), (70, 26, 20, 255))
    for i in range(int(w / 90) + 2):
        Wd.pine(d, -40 + i * 90 + r.uniform(-20, 20), HORIZON + 30, r.uniform(240, 340), (14, 6, 6, 255))
    for i in range(max(2, int(w / 220))):
        Wd.eyes(img, w * (0.18 + 0.64 * i / max(1, int(w / 220) - 1)) + r.uniform(-20, 20), HORIZON - r.uniform(30, 70),
                4.5, (255, 70, 46))


def _m_treasure(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 40, w * 0.32, h * 0.38, (255, 186, 70), 200, 34)
    Wd.glow(img, w / 2, HORIZON - 30, w * 0.12, h * 0.14, (255, 236, 170), 230, 16)
    d = ImageDraw.Draw(img)
    for i in range(int(w / 48) + 2):
        x = -10 + i * 48 + r.uniform(-10, 10)
        if abs(x - w / 2) < w * 0.12:
            continue
        Wd.bamboo(d, x, HORIZON + 30, r.uniform(240, 380), (30, 22, 8, 255), width=r.uniform(7, 11), seed=r.random())
    Wd.motes(d, w, HORIZON, (255, 214, 120), int(w / 16), r.random(), y0=60)


def _m_herbs(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON, w * 0.45, h * 0.25, (60, 140, 60), 120, 30)
    d = ImageDraw.Draw(img)
    Wd.ridge(d, w, HORIZON + 4, 60, int(r.random() * 999), (16, 34, 16, 255), peaks=3)
    for _ in range(int(w / 9)):
        x, y = r.uniform(0, w), HORIZON - r.uniform(-20, 40)
        col = r.choice([(240, 150, 190), (255, 236, 150), (250, 250, 240), (180, 140, 240)])
        rad = r.uniform(2.5, 5)
        d.ellipse(P(x - rad, y - rad, x + rad, y + rad), fill=alpha(col, 230))
        d.line(P(x, y + rad, x + r.uniform(-3, 3), y + rad + 16), fill=(40, 90, 40, 255), width=max(1, round(1.4 * S)))
    for _ in range(int(w / 40)):
        x = r.uniform(0, w)
        for side in (-1, 1):
            d.polygon([P(x, HORIZON + 6), P(x + side * 22, HORIZON - 30), P(x + side * 6, HORIZON - 6)],
                      fill=(36, 96, 44, 255))
    Wd.motes(d, w, HORIZON, (220, 255, 230), int(w / 30), r.random(), y0=HORIZON - 60)


def _m_ore(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 20, w * 0.45, h * 0.25, (150, 90, 50), 120, 30)
    d = ImageDraw.Draw(img)
    Wd.ridge(d, w, HORIZON - 20, 120, int(r.random() * 999), (40, 32, 30, 255), peaks=3)
    for _ in range(int(w / 7)):                 # glittering ore flecks in the rock
        x, y = r.uniform(0, w), HORIZON - r.uniform(-10, 90)
        col = r.choice([(236, 196, 120), (200, 210, 226), (226, 120, 70)])
        rad = r.uniform(1.5, 3.5)
        d.polygon([P(x, y - rad * 2), P(x + rad, y), P(x, y + rad * 2), P(x - rad, y)], fill=alpha(col, 230))
    Wd.motes(d, w, HORIZON, (255, 220, 170), int(w / 40), r.random(), y0=HORIZON - 80)


def _m_calm(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 30, w * 0.5, h * 0.25, (150, 180, 210), 110, 30)
    d = ImageDraw.Draw(img)
    Wd.ridge(d, w, HORIZON - 30, 50, int(r.random() * 999), (40, 52, 66, 255), peaks=3)
    Wd.water(img, -w * 0.05, HORIZON - 40, w * 1.05, HORIZON + 50, (70, 92, 112), (220, 236, 250))
    d = ImageDraw.Draw(img)
    Wd.bare_tree(d, w * 0.78, HORIZON - 20, 190, (24, 22, 26, 255), seed=r.random())
    for _ in range(int(w / 30)):
        x = r.uniform(0, w * 0.4)
        d.line(P(x, HORIZON + 30, x + r.uniform(-4, 4), HORIZON + 30 - r.uniform(20, 46)), fill=(30, 34, 30, 255),
               width=max(1, round(1.5 * S)))
    Wd.mist(img, w, HORIZON - 20, 70, (210, 226, 240), 150, seed=int(r.random() * 99))


def _m_hazard(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 20, w * 0.5, h * 0.35, (140, 160, 40), 120, 30)
    d = ImageDraw.Draw(img)
    d.polygon([P(0, 60), P(w * 0.62, HORIZON + 10), P(0, HORIZON + 40)], fill=(44, 40, 26, 255))
    d.polygon([P(w, 110), P(w * 0.5, HORIZON + 20), P(w, HORIZON + 40)], fill=(34, 30, 20, 255))
    for _ in range(int(w / 40)):
        x = r.uniform(0, w)
        y = r.uniform(80, HORIZON)
        Wd.rock(d, x, y, r.uniform(10, 24), r.uniform(8, 18), (70, 64, 44, 255), seed=r.random())
    Wd.mist(img, w, HORIZON - 10, 80, (170, 190, 80), 140, seed=int(r.random() * 99))


def _m_bandits(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 10, w * 0.3, h * 0.2, (240, 120, 40), 150, 24)
    d = ImageDraw.Draw(img)
    for i, x in enumerate((w * 0.22, w * 0.72)):
        s = r.uniform(70, 90)
        d.polygon([P(x - s, HORIZON + 10), P(x, HORIZON + 10 - s * 1.1), P(x + s, HORIZON + 10)], fill=(26, 16, 10, 255))
        d.polygon([P(x - s * 0.2, HORIZON + 10), P(x, HORIZON + 10 - s * 0.6), P(x + s * 0.2, HORIZON + 10)],
                  fill=(70, 34, 14, 255))
    Wd.smoke(img, w / 2, HORIZON - 10, 230, (120, 110, 104), 160, seed=int(r.random() * 9))
    d = ImageDraw.Draw(img)
    for k in range(5):
        a = math.radians(-160 + k * 30)
        d.line(P(w / 2, HORIZON + 4, w / 2 + math.cos(a) * 18, HORIZON + 4 + math.sin(a) * 6), fill=(50, 30, 20, 255),
               width=round(3 * S))
    Wd.flame(d, w / 2, HORIZON + 2, 24)


def _cart(d, x, base, s, fill, wheel):
    d.rectangle(P(x - s, base - s * 0.9, x + s, base - s * 0.3), fill=fill)
    d.polygon([P(x - s * 0.9, base - s * 0.9), P(x - s * 0.6, base - s * 1.5), P(x + s * 0.5, base - s * 1.6),
               P(x + s * 0.9, base - s * 0.9)], fill=mix(fill[:3], (90, 60, 30), 0.4) + (255,))
    d.line(P(x + s, base - s * 0.5, x + s * 1.9, base - s * 0.2), fill=fill, width=round(4 * S))
    for wx in (x - s * 0.6, x + s * 0.6):
        d.ellipse(P(wx - s * 0.32, base - s * 0.62, wx + s * 0.32, base + 0.02 * s), outline=wheel, width=round(3 * S))


def _lantern(img, x, y, size, color=(255, 196, 96)):
    Wd.glow(img, x, y, size * 3, size * 3, color, 170, size)
    d = ImageDraw.Draw(img)
    d.line(P(x, y - size * 1.6, x, y - size * 0.9), fill=(40, 26, 14, 255), width=max(1, round(1.5 * S)))
    d.rounded_rectangle(P(x - size * 0.7, y - size * 0.9, x + size * 0.7, y + size * 0.9), radius=round(size * 0.4 * S),
                        fill=alpha(color, 255), outline=(90, 30, 20, 255), width=max(1, S))
    d.rectangle(P(x - size * 0.75, y - size, x + size * 0.75, y - size * 0.8), fill=(90, 30, 20, 255))
    d.rectangle(P(x - size * 0.75, y + size * 0.8, x + size * 0.75, y + size), fill=(90, 30, 20, 255))


def _m_merchant(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 20, w * 0.35, h * 0.2, (230, 150, 60), 110, 26)
    d = ImageDraw.Draw(img)
    Wd.ridge(d, w, HORIZON, 70, int(r.random() * 999), (34, 22, 12, 255), peaks=4)
    _cart(d, w * 0.5, HORIZON + 14, 46, (92, 58, 30, 255), (150, 110, 60, 255))
    d.line(P(w * 0.5 - 50, HORIZON - 60, w * 0.5 - 50, HORIZON + 10), fill=(92, 58, 30, 255), width=round(3 * S))
    _lantern(img, w * 0.5 - 50, HORIZON - 40, 9)


def _figure(d, x, base, s, fill, slumped=False):
    """A robed person: head, shoulders and a robe; slumped against something when hurt."""
    if slumped:
        d.ellipse(P(x - s * 0.9, base - s * 0.9, x + s * 0.9, base + s * 0.1), fill=fill)
        d.ellipse(P(x + s * 0.4, base - s * 1.5, x + s * 1.0, base - s * 0.9), fill=fill)
        return
    d.ellipse(P(x - s * 0.28, base - s * 2.4, x + s * 0.28, base - s * 1.85), fill=fill)
    d.polygon([P(x - s * 0.45, base - s * 1.85), P(x + s * 0.45, base - s * 1.85), P(x + s * 0.75, base),
               P(x - s * 0.75, base)], fill=fill)


def _m_stranger(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON, w * 0.3, h * 0.2, (120, 30, 30), 100, 24)
    d = ImageDraw.Draw(img)
    for i in range(int(w / 110) + 1):
        Wd.bare_tree(d, 40 + i * 110 + r.uniform(-20, 20), HORIZON + 20, r.uniform(150, 230), (24, 14, 14, 255),
                     seed=r.random(), wd=6)
    x = w * 0.58
    d.line(P(x - 60, HORIZON - 120, x + 40, HORIZON - 150), fill=(34, 20, 18, 255), width=round(5 * S))
    d.polygon([P(x - 10, HORIZON - 138), P(x + 8, HORIZON - 141), P(x + 14, HORIZON - 96), P(x - 2, HORIZON - 100)],
              fill=(200, 190, 170, 255))
    for k in range(7):
        bx, by = w * 0.35 + k * 26 + r.uniform(-6, 6), HORIZON + 30 + r.uniform(-6, 10)
        d.ellipse(P(bx - 3.5, by - 2.5, bx + 3.5, by + 2.5), fill=(200, 30, 30, 255))


def _m_tablet(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 40, w * 0.3, h * 0.25, (110, 160, 140), 110, 26)
    d = ImageDraw.Draw(img)
    n = 6
    for i in range(n):
        a = math.radians(200 + i * (140 / (n - 1)))
        x = w / 2 + math.cos(a) * w * 0.28
        base = HORIZON + 10 + math.sin(a) * 30
        sh = r.uniform(70, 110)
        d.rectangle(P(x - 16, base - sh, x + 16, base), fill=(58, 62, 58, 255))
        d.ellipse(P(x - 18, base - sh - 8, x + 18, base - sh + 10), fill=(60, 110, 70, 255))
        for k in range(3):
            d.line(P(x - 6, base - sh + 24 + k * 16, x + 6, base - sh + 24 + k * 16), fill=(34, 38, 34, 255),
                   width=max(1, round(2 * S)))


def _m_lair(img, w, h, r):
    d = ImageDraw.Draw(img)
    Wd.rock(d, w / 2, HORIZON + 30, w * 0.9, 250, (34, 26, 22, 255), seed=r.random())
    Wd.glow(img, w / 2, HORIZON - 20, 80, 60, (200, 50, 30), 160, 16)
    d = ImageDraw.Draw(img)
    d.chord(P(w / 2 - 80, HORIZON - 110, w / 2 + 80, HORIZON + 90), 180, 360, fill=(6, 3, 3, 255))
    d.rectangle(P(w / 2 - 80, HORIZON - 12, w / 2 + 80, HORIZON + 30), fill=(6, 3, 3, 255))
    for k in range(9):
        bx = w / 2 - 110 + k * 26 + r.uniform(-8, 8)
        by = HORIZON + 30 + r.uniform(-4, 6)
        a = r.uniform(-0.6, 0.6)
        d.line(P(bx - 14 * math.cos(a), by - 14 * math.sin(a), bx + 14 * math.cos(a), by + 14 * math.sin(a)),
               fill=(220, 210, 186, 255), width=round(3 * S))
    d.ellipse(P(w / 2 + 70, HORIZON + 14, w / 2 + 96, HORIZON + 36), fill=(230, 220, 196, 255))


def _m_blessed(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 60, w * 0.4, h * 0.4, (255, 240, 190), 150, 34)
    Wd.rays(img, w / 2, 0, HORIZON + 40, (255, 246, 210), n=10, spread=90, a=90, seed=int(r.random() * 99))
    d = ImageDraw.Draw(img)
    for x in (w * 0.2, w * 0.8):
        d.line(P(x, HORIZON + 20, x, HORIZON - 90), fill=(40, 30, 26, 255), width=round(6 * S))
        for _ in range(60):
            a, rr = r.uniform(0, 2 * math.pi), r.uniform(0, 70)
            px, py = x + math.cos(a) * rr, HORIZON - 120 + math.sin(a) * rr * 0.6
            rad = r.uniform(3, 6)
            d.ellipse(P(px - rad, py - rad, px + rad, py + rad), fill=alpha(r.choice([(250, 190, 210), (255, 220, 230),
                                                                                         (240, 160, 190)]), 230))
    for k in range(3):
        rx = 60 + k * 50
        d.ellipse(P(w / 2 - rx, HORIZON + 6 - rx * 0.18, w / 2 + rx, HORIZON + 6 + rx * 0.18),
                  outline=(255, 240, 200, 150 - k * 40), width=max(1, round(1.5 * S)))
    Wd.motes(d, w, HORIZON, (255, 250, 220), int(w / 14), r.random(), y0=40)


def _m_hermit(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 30, w * 0.4, h * 0.25, (140, 120, 200), 110, 30)
    d = ImageDraw.Draw(img)
    Wd.ridge(d, w, HORIZON - 10, 80, int(r.random() * 999), (30, 26, 44, 255), peaks=3)
    x = w * 0.5
    d.polygon([P(x - 90, HORIZON - 110), P(x + 90, HORIZON - 110), P(x + 110, HORIZON - 96), P(x - 110, HORIZON - 96)],
              fill=(22, 18, 30, 255))
    d.polygon([P(x - 70, HORIZON - 130), P(x + 70, HORIZON - 130), P(x + 90, HORIZON - 110), P(x - 90, HORIZON - 110)],
              fill=(28, 22, 38, 255))
    for px in (x - 70, x + 70):
        d.rectangle(P(px - 5, HORIZON - 100, px + 5, HORIZON + 14), fill=(22, 18, 30, 255))
    d.rectangle(P(x - 90, HORIZON + 8, x + 90, HORIZON + 18), fill=(22, 18, 30, 255))
    for k, sx in enumerate((x - 150, x + 160)):
        Wd.smoke(img, sx, HORIZON + 10, 180, (200, 186, 230), 120, seed=k + int(r.random() * 9))
    d = ImageDraw.Draw(img)
    for sx in (x - 150, x + 160):
        d.line(P(sx, HORIZON + 14, sx, HORIZON - 6), fill=(230, 120, 60, 255), width=round(2 * S))


def _m_king(img, w, h, r):
    Wd.glow(img, w / 2, HORIZON - 80, w * 0.5, h * 0.4, (150, 10, 10), 170, 34)
    d = ImageDraw.Draw(img)
    for i in range(int(w / 80) + 2):
        x = -20 + i * 80 + r.uniform(-20, 20)
        hh = r.uniform(90, 200)
        lean = r.uniform(-0.5, 0.5)
        d.line(P(x, HORIZON + 30, x + lean * hh, HORIZON + 30 - hh), fill=(18, 6, 6, 255), width=round(r.uniform(8, 14) * S))
        d.polygon([P(x + lean * hh - 10, HORIZON + 30 - hh), P(x + lean * hh + 12, HORIZON + 30 - hh - 30),
                   P(x + lean * hh + 6, HORIZON + 30 - hh + 6)], fill=(18, 6, 6, 255))
    Wd.eyes(img, w / 2, HORIZON - 150, 11, (255, 50, 30))


MOOD_FN = {"wild_beast": _m_beast, "treasure_chest": _m_treasure, "herb_patch": _m_herbs, "ore_vein": _m_ore,
           "peaceful_clearing": _m_calm, "hazard": _m_hazard, "bandits": _m_bandits,
           "wandering_merchant": _m_merchant, "injured_stranger": _m_stranger, "stone_tablet": _m_tablet,
           "elite_lair": _m_lair, "blessed_land": _m_blessed, "wandering_hermit": _m_hermit,
           "beast_king_den": _m_king}


@lru_cache(maxsize=32)
def mood(kind, w=MOOD_W, feathered=True):
    """One clue's mood as a transparent layer (S×), w wide and as tall as the scene."""
    img = Wd.layer(w, SH)
    MOOD_FN[kind](img, w, SH, random.Random(f"{kind}{w}"))
    return Wd.feather(img) if feathered else img


# ── the scene base (cached) ───────────────────────────────────────────

@lru_cache(maxsize=2)
def _backdrop():
    """Dusk sky, sun, far ridges: the empty crossroads before any mood is drawn."""
    img = Wd.sky(SW, SH, (26, 14, 10), (110, 54, 24)).convert("RGBA")
    Wd.glow(img, SW / 2, HORIZON - 30, 200, 120, (255, 170, 80), 120, 40)
    d = ImageDraw.Draw(img)
    Wd.ridge(d, SW, HORIZON - 40, 90, 3, (88, 44, 30, 255), peaks=7)
    Wd.ridge(d, SW, HORIZON - 4, 60, 9, (54, 28, 20, 255), peaks=9)
    g = T.vgradient(P(SW, SH - HORIZON), (40, 24, 14), (12, 7, 4))
    img.alpha_composite(g, P(0, HORIZON))
    d = ImageDraw.Draw(img)
    Wd.grass_tufts(d, SW, HORIZON + 30, (60, 40, 20, 255), 70, 5, 6, 16)
    Wd.motes(d, SW, SH, (255, 200, 120), 50, 4)
    return img


def _ground(img, single=False):
    """The dark ground and the dirt paths: three from the bottom centre, or one straight ahead."""
    d = ImageDraw.Draw(img)
    base_l, base_r = SW / 2 - 110, SW / 2 + 110
    ends = {"middle": (SW / 2, PATH_END_Y["middle"])} if single else {k: (PATH_X[k], PATH_END_Y[k]) for k in PATH_X}
    for key, (ex, ey) in ends.items():
        hw = 14
        if key == "left":
            poly = [P(base_l, SH), P(SW / 2 + 10, SH), P(ex + hw, ey), P(ex - hw, ey)]
        elif key == "right":
            poly = [P(SW / 2 - 10, SH), P(base_r, SH), P(ex + hw, ey), P(ex - hw, ey)]
        else:
            poly = [P(SW / 2 - 80, SH), P(SW / 2 + 80, SH), P(ex + 12, ey), P(ex - 12, ey)]
        d.polygon(poly, fill=(132, 98, 62, 200))
    edge = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(edge).rectangle(P(0, SH - 50, SW, SH + 20), fill=(0, 0, 0, 150))
    img.alpha_composite(Wd.blur(edge, 14))
    Wd.motes(ImageDraw.Draw(img), SW, SH, (255, 190, 110), 26, 12, y0=HORIZON + 20, r0=1, r1=2.2)


def _shade_painted(img, strength=170):
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i in range(30):                       # darken the top so the header reads
        sd.rectangle(P(0, i * 6, SW, i * 6 + 6), fill=(0, 0, 0, round(strength * (1 - i / 30) ** 1.6)))
    img.alpha_composite(shade)
    return img


def painted_scene(name, dim=60):
    """A painting from art/scenes fitted to the scene window (S×), dimmed a little; None if missing."""
    from .scenes import photo
    im = photo(name, round(SW * S), round(SH * S))
    if im is None:
        return None
    im = im.copy()
    im.alpha_composite(Image.new("RGBA", im.size, (0, 0, 0, dim)))
    return _shade_painted(im)


def place_subject(img, sub, height, base=0.96, glow=(255, 214, 150)):
    """Stand a transparent subject (chest, bandits...) in the middle of the scene, on a soft shadow."""
    sub = sub.copy()
    sc = height * S / sub.size[1]
    sub = sub.resize((max(1, round(sub.size[0] * sc)), max(1, round(sub.size[1] * sc))), Image.LANCZOS)
    x = round(SW * S * 0.62 - sub.size[0] / 2)          # right of centre: the title sits on the left
    y = round(SH * S * base - sub.size[1])
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((x + sub.size[0] * 0.1, y + sub.size[1] * 0.9, x + sub.size[0] * 0.9,
                                y + sub.size[1] * 1.04), fill=(0, 0, 0, 160))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10 * S)))
    halo = Image.new("RGBA", sub.size, glow + (0,))
    halo.putalpha(sub.getchannel("A").filter(ImageFilter.GaussianBlur(14 * S)).point(lambda v: round(v * 0.45)))
    img.alpha_composite(halo, (x, y))
    img.alpha_composite(sub, (x, y))


@lru_cache(maxsize=24)
def crossroads_scene(left, middle, right, region=None):
    from .scenes import REGION
    painted = painted_scene(REGION.get(region))
    if painted is not None:
        return painted
    """The crossroads with the mood of each path's clue kind (S×, RGBA)."""
    img = _backdrop().copy()
    for kind, key in ((left, "left"), (right, "right"), (middle, "middle")):
        _paste(img, mood(kind), PATH_X[key] - MOOD_W / 2)
    _ground(img)
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i in range(30):                       # darken the top so the header reads
        sd.rectangle(P(0, i * 6, SW, i * 6 + 6), fill=(0, 0, 0, round(170 * (1 - i / 30) ** 1.6)))
    img.alpha_composite(shade)
    return img


def _paste(img, piece, x):
    """alpha_composite that allows the piece to stick out on the left/right."""
    px = round(x * S)
    src_x = max(0, -px)
    dst_x = max(0, px)
    wdt = min(piece.size[0] - src_x, img.size[0] - dst_x)
    if wdt > 0:
        img.alpha_composite(piece.crop((src_x, 0, src_x + wdt, piece.size[1])), (dst_x, 0))


# ── encounter scenes (cached) ─────────────────────────────────────────

def _chest(d, cx, base, s):
    wood, dark, gold = (120, 74, 34, 255), (60, 34, 16, 255), (236, 190, 90, 255)
    d.rounded_rectangle(P(cx - s, base - s * 1.25, cx + s, base - s * 0.6), radius=round(s * 0.35 * S), fill=wood,
                        outline=dark, width=round(2 * S))
    d.rectangle(P(cx - s, base - s * 0.72, cx + s, base), fill=wood, outline=dark, width=round(2 * S))
    for x in (cx - s * 0.7, cx + s * 0.7):
        d.rectangle(P(x - s * 0.08, base - s * 1.2, x + s * 0.08, base), fill=gold)
    d.rectangle(P(cx - s * 0.16, base - s * 0.86, cx + s * 0.16, base - s * 0.5), fill=gold, outline=dark,
                width=max(1, S))


def _tablet(d, cx, base, s):
    d.polygon([P(cx - s * 0.8, base), P(cx - s * 0.7, base - s * 2.4), P(cx, base - s * 2.7), P(cx + s * 0.7, base - s * 2.4),
               P(cx + s * 0.8, base)], fill=(86, 90, 84, 255), outline=(40, 44, 40, 255))
    d.ellipse(P(cx - s * 0.8, base - s * 2.8, cx + s * 0.2, base - s * 2.3), fill=(60, 120, 76, 255))
    for k in range(4):
        y = base - s * 2.0 + k * s * 0.42
        for j in range(3):
            x = cx - s * 0.4 + j * s * 0.4
            d.line(P(x - s * 0.1, y, x + s * 0.1, y + s * 0.12), fill=(40, 44, 40, 255), width=round(2.4 * S))


def _encounter_subject(img, kind, sub):
    d = ImageDraw.Draw(img)
    cx = SW / 2
    if kind == "treasure_chest":
        Wd.glow(img, cx, HORIZON + 40, 120, 60, (255, 200, 90), 170, 18)
        _chest(ImageDraw.Draw(img), cx, HORIZON + 80, 56)
    elif kind == "stone_tablet":
        _tablet(d, cx, HORIZON + 60, 52)
    elif kind == "wandering_merchant":
        _figure(d, cx + 130, HORIZON + 70, 46, (64, 40, 24, 255))
        d.polygon([P(cx + 96, HORIZON - 44), P(cx + 164, HORIZON - 44), P(cx + 130, HORIZON - 74)], fill=(120, 90, 50, 255))
        _lantern(img, cx + 190, HORIZON - 10, 14)
    elif kind == "injured_stranger":
        _figure(d, cx, HORIZON + 70, 46, (40, 20, 18, 255), slumped=True)
        for k in range(5):
            d.ellipse(P(cx - 80 + k * 30, HORIZON + 76, cx - 72 + k * 30, HORIZON + 82), fill=(210, 30, 30, 255))
    elif kind == "wandering_hermit":
        _figure(d, cx, HORIZON + 60, 40, (36, 28, 52, 255))
        d.line(P(cx - 30, HORIZON - 30, cx + 40, HORIZON - 40), fill=(200, 170, 110, 255), width=round(3 * S))
    elif kind == "herb_patch":
        r = random.Random(3)
        for k in range(6):
            x = cx - 170 + k * 68 + r.uniform(-10, 10)
            base = HORIZON + 86 + r.uniform(-8, 8)
            for j in range(9):
                a = math.radians(-160 + j * 17.5)
                ln = r.uniform(26, 40)
                ex, ey = x + math.cos(a) * ln, base + math.sin(a) * ln
                d.line(P(x, base, ex, ey), fill=(40, 110, 50, 255), width=round(2 * S))
                d.ellipse(P(ex - 9, ey - 5, ex + 9, ey + 5), fill=(70, 170, 80, 255))
            fx, fy = x + r.uniform(-8, 8), base - 44
            d.ellipse(P(fx - 7, fy - 7, fx + 7, fy + 7), fill=r.choice([(250, 220, 120, 255), (240, 150, 190, 255)]))
    elif kind == "ore_vein":
        r = random.Random(5)
        d.polygon([P(cx - 190, HORIZON + 96), P(cx - 120, HORIZON - 60), P(cx - 20, HORIZON - 110), P(cx + 110, HORIZON - 70),
                   P(cx + 190, HORIZON + 96)], fill=(54, 44, 40, 255), outline=(26, 20, 18, 255))
        for k in range(5):                      # the vein: a jagged bright seam through the rock
            x0, y0 = cx - 140 + k * 60, HORIZON + 40 - k * 24 + r.uniform(-6, 6)
            d.line(P(x0, y0, x0 + 60, y0 - 24 + r.uniform(-8, 8)), fill=(232, 176, 96, 255), width=round(5 * S))
        Wd.glow(img, cx, HORIZON - 10, 120, 50, (255, 190, 110), 120, 16)
        d = ImageDraw.Draw(img)
        d.line(P(cx + 90, HORIZON + 90, cx + 150, HORIZON + 10), fill=(110, 76, 44, 255), width=round(5 * S))   # pickaxe
        d.arc(P(cx + 110, HORIZON - 12, cx + 190, HORIZON + 34), 190, 330, fill=(170, 176, 186, 255), width=round(6 * S))
    elif kind == "blessed_land":
        Wd.glow(img, cx, HORIZON + 30, 140, 40, (255, 250, 220), 200, 16)


@lru_cache(maxsize=16)
def encounter_scene(kind, sub="", region=None, hazard=None):
    """The real encounter, drawn across the whole scene (S×, RGBA). With art/scenes: the place's painting, or
    the region's painting with the encounter's subject standing in it."""
    from .scenes import PLACE, REGION, subject
    place = painted_scene(PLACE.get(hazard or kind))
    if place is not None:
        return place
    from .scenes import SUBJECT
    obj = subject(SUBJECT.get(kind))
    base = painted_scene(REGION.get(region), dim=110)
    if base is not None and (obj is not None or kind not in MOOD_FN):
        if obj is not None:
            tall = kind in ("bandits", "wandering_merchant", "injured_stranger", "wandering_hermit", "stone_tablet")
            place_subject(base, obj, SH * (0.78 if tall else 0.56))
        return base
    img = _backdrop().copy()
    img.alpha_composite(mood(kind, SW, feathered=False))
    _ground(img, single=True)
    _encounter_subject(img, kind, sub)
    shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i in range(30):
        sd.rectangle(P(0, i * 6, SW, i * 6 + 6), fill=(0, 0, 0, round(170 * (1 - i / 30) ** 1.6)))
    img.alpha_composite(shade)
    return img


def _rim_colors():
    return {k: v.rim for k, v in T.ELEMENT_ACCENTS.items()}


ELEMENT_RIM = {}


def fight_scene(palette, body, slug, region=None):
    """After a fight: the beast (or the bandits) in the region's painting; else its scene from the fight screen."""
    from .battle import _art
    from .scenes import REGION, subject
    base = painted_scene(REGION.get(region), dim=110)
    art = _art(slug) or (subject("subject_bandits") if body == "human" else None)
    if not ELEMENT_RIM:
        ELEMENT_RIM.update(_rim_colors())
    if base is not None and art is not None:
        place_subject(base, art, SH * 0.82, base=1.0, glow=ELEMENT_RIM.get(palette, (255, 214, 150)))
        return base
    from .battle import scene
    sc = scene(palette, body, slug)
    scale = max(SW * S / sc.size[0], SH * S / sc.size[1])
    sc = sc.resize((round(sc.size[0] * scale), round(sc.size[1] * scale)), Image.LANCZOS)
    x = (sc.size[0] - round(SW * S)) // 2
    sc = sc.crop((x, 0, x + round(SW * S), round(SH * S))).copy()
    shade = Image.new("RGBA", sc.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shade)
    for i in range(30):
        sd.rectangle(P(0, i * 6, SW, i * 6 + 6), fill=(0, 0, 0, round(190 * (1 - i / 30) ** 1.6)))
    sc.alpha_composite(shade)
    return sc


def hazard_overlay(img, danger, kind):
    """The mist or the landslide pouring in from the side it comes from (drawn on the card, card coords)."""
    x0, y0, x1, y1 = SCENE
    cx = {"left": x0 + 200, "middle": (x0 + x1) / 2, "right": x1 - 200}[danger]
    col = (170, 200, 70) if kind == "poison mist" else (120, 100, 70)
    Wd.glow(img, cx, y0 + 260, 260, 170, col, 200, 30)
    if kind != "poison mist":
        d = ImageDraw.Draw(img)
        r = random.Random(danger)
        for _ in range(24):
            Wd.rock(d, cx + r.uniform(-180, 180), y0 + r.uniform(120, 400), r.uniform(16, 40), r.uniform(12, 30),
                    (82, 70, 54, 255), seed=r.random(), light=(150, 130, 100, 255))


# ── pieces ────────────────────────────────────────────────────────────

def arrow(d, cx, cy, s, direction, color, width=None):
    """A bold drawn arrow pointing left, up (middle) or right."""
    wd = width or max(2, round(s * 0.26 * S))
    if direction == "middle":
        d.line(P(cx, cy + s, cx, cy - s * 0.4), fill=color, width=wd)
        d.polygon([P(cx - s * 0.62, cy - s * 0.15), P(cx, cy - s), P(cx + s * 0.62, cy - s * 0.15)], fill=color)
        return
    k = -1 if direction == "left" else 1
    d.line(P(cx - k * s, cy, cx + k * s * 0.4, cy), fill=color, width=wd)
    d.polygon([P(cx + k * s * 0.15, cy - s * 0.62), P(cx + k * s, cy), P(cx + k * s * 0.15, cy + s * 0.62)], fill=color)


def badge(img, center, r, direction, color):
    """The glowing round arrow badge on a path."""
    cx, cy = center
    T.soft_glow(img, (cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14), alpha(color, 170), 9)
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r, cy - r, cx + r, cy + r), fill=(12, 8, 6, 255), outline=alpha(color, 255), width=round(4 * S))
    d.ellipse(P(cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6), outline=alpha(T.GOLD, 160), width=max(1, round(1.4 * S)))
    arrow(d, cx, cy, r * 0.5, direction, mix(color, WHITE, 0.55))


def label_chip(img, center, label, color, size=24):
    cx, cy = center
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", size, "Bold")
    tw = T.width(d, label, f)
    w, h = tw + 40, size + 22
    d.rounded_rectangle(P(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), radius=round(h / 2 * S),
                        fill=(10, 6, 6, 235), outline=alpha(color, 255), width=round(2 * S))
    T.text(d, (cx, cy + 1), label, f, mix(color, WHITE, 0.7), "mm")


def step_dots(img, right, y, step, total, color):
    d = ImageDraw.Draw(img)
    gap, r = 44, 11
    x0 = right - gap * (total - 1)
    for i in range(total):
        cx = x0 + i * gap
        if i < step:
            big = i == step - 1
            rr = r + 2 if big else r
            if big:
                T.soft_glow(img, (cx - 20, y - 20, cx + 20, y + 20), alpha(color, 170), 6)
                d = ImageDraw.Draw(img)
            d.ellipse(P(cx - rr, y - rr, cx + rr, y + rr), fill=alpha(color, 255), outline=T.GOLD_HI, width=max(1, S))
        else:
            d.ellipse(P(cx - r, y - r, cx + r, y + r), fill=(14, 9, 6, 255), outline=alpha(T.GOLD, 220),
                      width=round(1.6 * S))


def header(img, data, title, subtitle, emblem="gear:compass", emblem_color=None, title_glow=None):
    """Over the scene: medallion, big title, small caps subtitle; step and dots on the right."""
    acc = T.ACCENTS["explore"]
    x0, y0 = SCENE[0], SCENE[1]
    T.seal(img, (x0 + 66, y0 + 70), 46, emblem, emblem_color or acc.bright)
    d = ImageDraw.Draw(img)
    title, tf = _shrink(d, title.upper(), "Cinzel.ttf", "Black", (52, 46, 40, 34), 700)
    T.gold_text(img, (x0 + 130, y0 + 66), title, tf, "lm", glow=title_glow or acc.main)
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 24, "Bold")
    T.spaced(d, (x0 + 132, y0 + 120), T.fit(d, subtitle.upper(), f, 640), f, mix(T.GOLD, WHITE, 0.15), 1.6)
    right = SCENE[2] - 34
    T.gold_text(img, (right, y0 + 48), f"STEP {data['step']} / {data['max_steps']}", font("Cinzel.ttf", 40, "Black"),
                "rm", glow=acc.main)
    step_dots(img, right - 10, y0 + 106, data["step"], data["max_steps"], acc.bright)


def _mini_heading(img, box, title):
    x0, y0, x1, _ = box
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 24, "Bold")
    T.spaced(d, (x0 + 24, y0 + 34), title.upper(), f, T.GOLD, 2.4)
    tw = sum(T.width(d, ch, f) for ch in title.upper()) + 2.4 * (len(title) - 1)
    T.rule(d, x0 + 44 + tw, x1 - 22, y0 + 34)


def _panel(img, box, fill=(22, 14, 8)):
    T.panel(img, box, fill=fill)


def found_panel(img, data):
    box = FOUND
    _panel(img, box)
    _mini_heading(img, box, "Found so far")
    x0, y0, x1, y1 = box
    tiles = []
    if data["coins"]:
        tiles.append({"name": "Lotus Coins", "label": f"+{data['coins']:,}", "icon": "lotus", "color": T.LOTUS})
    tiles += data["items"]
    d = ImageDraw.Draw(img)
    if not tiles:
        T.text(d, ((x0 + x1) / 2, y0 + 118), "Nothing yet. Pick a path!", font("Inter.ttf", 26, "Medium"), T.ASH, "mm")
    cols, tw = 3, (x1 - x0 - 30) / 3
    shown = tiles[:6] if len(tiles) <= 6 else tiles[:5]
    for i, it in enumerate(shown):
        cx = x0 + 22 + (i % cols) * tw
        cy = y0 + 92 + (i // cols) * 72
        _tile(img, (cx, cy), tw - 12, it)
    if len(tiles) > len(shown):
        i = len(shown)
        d = ImageDraw.Draw(img)
        T.text(d, (x0 + 22 + (i % cols) * tw + 20, y0 + 92 + (i // cols) * 72), f"+{len(tiles) - len(shown)} more",
               font("Inter.ttf", 26, "SemiBold"), T.ASH, "lm")
    d = ImageDraw.Draw(img)
    T.text(d, (x0 + 26, y1 - 26), T.fit(d, data["defeat_note"], font("Inter.ttf", 24, "Medium"), x1 - x0 - 50),
           font("Inter.ttf", 24, "Medium"), T.ASH, "lm")


def _tile(img, left_center, width, it):
    x, cy = left_center
    color = it.get("color") or T.RARITY.get(it.get("color_key"), T.RARITY[None])
    T.seal(img, (x + 30, cy), 28, it["icon"], color)
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 24, "Bold")
    qty = f" ×{it['qty']}" if it.get("qty", 1) > 1 else ""
    T.text(d, (x + 68, cy - 15), T.fit(d, it["name"] + qty, f, width - 72), f, T.PARCHMENT, "lm")
    T.text(d, (x + 68, cy + 17), T.fit(d, it.get("label", ""), font("Inter.ttf", 24, "Medium"), width - 72),
           font("Inter.ttf", 24, "Medium"), mix(color, WHITE, 0.25), "lm")


def you_panel(img, data):
    box = YOU
    _panel(img, box)
    _mini_heading(img, box, "You")
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 25, "Bold")
    T.text(d, (x0 + 24, y0 + 88), "HP", f, T.ASH, "lm")
    frac = data["hp"] / data["max_hp"] if data["max_hp"] else 0
    T.bar(img, (x0 + 84, y0 + 70, x1 - 24, y0 + 106), frac, (206, 64, 54) if frac > 0.25 else (236, 50, 40),
          label=f"{max(0, round(data['hp'])):,} / {data['max_hp']:,}")
    d = ImageDraw.Draw(img)
    T.text(d, (x0 + 24, y0 + 148), "Danger", f, T.ASH, "lm")
    n, filled = data["max_steps"], data["step"]
    sx, seg = x0 + 140, (x1 - 24 - (x0 + 140)) / n
    for i in range(n):
        a, b = sx + i * seg + 4, sx + (i + 1) * seg - 6
        on = i < filled
        col = mix((240, 150, 40), (236, 60, 40), i / max(1, n - 1))
        d.polygon([P(a + 6, y0 + 132), P(b + 6, y0 + 132), P(b - 2, y0 + 164), P(a - 2, y0 + 164)],
                  fill=alpha(col, 255) if on else (30, 20, 16, 255), outline=alpha(T.BRONZE, 230))
    bonus, bf = _shrink(d, data["bonus"], "Inter.ttf", "SemiBold", (25, 24), x1 - x0 - 44)
    T.text(d, (x0 + 22, y0 + 206), bonus, bf, T.LOTUS, "lm")


# ── the cards ─────────────────────────────────────────────────────────

def _base():
    img = T.canvas(W, H, seed=31, accent="explore")
    return img


def render_crossroads(data):
    """data: region, realm, step, max_steps, paths {left/middle/right: {kind, label, place, clue}}, lie_note,
    hp, max_hp, coins, items [{name, qty, icon, color_key, label}], defeat_note, bonus."""
    img = _base()
    paths = data["paths"]
    sc = crossroads_scene(paths["left"]["kind"], paths["middle"]["kind"], paths["right"]["kind"], data.get("region"))
    img.alpha_composite(sc, P(SCENE[0], SCENE[1]))
    T.frame(img, SCENE, 0.8)
    header(img, data, data["region"], f"{data['realm']}  ·  Choose your path")
    for key in ("left", "middle", "right"):          # one big arrow per path; its clue is read in the panel below
        p = paths[key]
        color = MOOD[p["kind"]][0]
        cx = SCENE[0] + PATH_X[key]
        cy = SCENE[1] + BADGE_Y[key]
        badge(img, (cx, cy + 20), 48, key, color)

    for box, key in zip(CLUES, ("left", "middle", "right")):
        p = paths[key]
        color = MOOD[p["kind"]][0]
        _panel(img, box)
        x0, y0, x1, y1 = box
        cx, cy = x0 + 40, y0 + 40
        d = ImageDraw.Draw(img)
        d.ellipse(P(cx - 20, cy - 20, cx + 20, cy + 20), fill=(12, 8, 6, 255), outline=alpha(color, 255), width=round(3 * S))
        arrow(d, cx, cy, 10, key, mix(color, WHITE, 0.5))
        room = x1 - cx - 46
        title, tf = _shrink(d, p["label"], "Inter.ttf", "Black", (30, 28, 26, 24), room)
        T.text(d, (cx + 32, cy), title, tf, mix(color, WHITE, 0.25), "lm")
        f = font("Inter.ttf", 26, "Medium")
        lines = T.wrap(d, p["clue"], f, x1 - x0 - 48, lines=2)
        for i, line in enumerate(lines):
            T.text(d, (x0 + 24, y0 + 88 + i * 34), line, f, T.PARCHMENT, "lm")
    if data.get("lie_note"):
        d = ImageDraw.Draw(img)
        T.text(d, (SCENE[0] + 30, SCENE[3] - 28), data["lie_note"], font("Inter.ttf", 24, "SemiBold"),
               mix(T.PARCHMENT, (0, 0, 0), 0.1), "lm")
    found_panel(img, data)
    you_panel(img, data)
    return T.finish(img)


def render_encounter(data):
    """data: as render_crossroads (without paths) plus kind, title, subtitle, story [str], and optionally
    fight {palette, body, slug} (after a fight), hazard {danger, kind}, outcome ("good", "bad", None)."""
    img = _base()
    kind = data["kind"]
    color = MOOD[kind][0]
    if data.get("fight"):
        f = data["fight"]
        sc = fight_scene(f["palette"], f["body"], f.get("slug"), data.get("region"))
    else:
        sc = encounter_scene(kind, region=data.get("region"),
                             hazard=data["hazard"]["kind"] if data.get("hazard") else None)
    img.alpha_composite(sc, P(SCENE[0], SCENE[1]))
    if data.get("hazard"):
        hazard_overlay(img, data["hazard"]["danger"], data["hazard"]["kind"])
    T.frame(img, SCENE, 0.8)
    outcome = data.get("outcome")
    glow = {"bad": (226, 60, 44), "good": (110, 214, 120)}.get(outcome, color)
    header(img, data, data["title"], data["subtitle"], emblem=MOOD[kind][2], emblem_color=color, title_glow=glow)
    if data.get("hazard"):
        h = data["hazard"]
        cx = {"left": SCENE[0] + 200, "middle": (SCENE[0] + SCENE[2]) / 2, "right": SCENE[2] - 200}[h["danger"]]
        label_chip(img, (cx, SCENE[1] + 300), h["kind"].upper() + "!", (226, 70, 50), 28)

    box = STORY
    _panel(img, box)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 26, "Medium")
    y, max_y = y0 + 36, y1 - 16
    for raw in data["story"][:5]:
        lines = T.wrap(d, raw, f, x1 - x0 - 70, lines=2)
        if y + 17 > max_y:
            break
        T.stud(d, x0 + 32, y, 5)
        for line in lines:
            if y + 17 > max_y:
                break
            T.text(d, (x0 + 50, y), line, f, T.PARCHMENT, "lm")
            y += 34
        y += 4
    found_panel(img, data)
    you_panel(img, data)
    return T.finish(img)
