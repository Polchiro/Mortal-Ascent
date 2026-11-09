"""
/breakthrough result: four scenes, all drawn in code on the night sky of the other cards.

  realm success   heaven answers: a golden pillar of light, tribulation lightning, rays and rising
                  sparks around the cultivator's rune ring; "REALM BREAKTHROUGH", old realm → new realm
  phase success   a jade wave of Qi breaks the bottleneck: jade rays and sparks; "BOTTLENECK BROKEN"
  realm failure   Qi backlash: the ring cracks, crimson shards fly out, the cultivator greys;
                  "MERIDIANS RECOIL", the Qi lost and the injury
  phase failure   the gate holds: a cold grey-blue wall of Qi, a dimmed ring; "THE BOTTLENECK HOLDS"

Under the scene: the title, the transition (or what was at stake) and a glass strip with up to three
results (Qi carried, dew, pill, Qi lost, injury, next chance). The cultivator's Discord avatar sits in the
ring; without one, the ring's painted figure.

render_breakthrough(data) takes bot.breakthrough_card.card_data(...).
"""
import io
import math
import random
from functools import lru_cache

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import theme as T
from .compendium import EDGE, SOFT, TEXT, _glass
from .theme import P, S, alpha, cjk, font, mix

W, H = T.W, 900
CENTER = (W / 2, 300)
RING_R = 150

STYLE = {   # state → colours and words
    "realm_success": {"hi": (255, 222, 140), "lo": (200, 130, 40), "glow": (255, 200, 90), "sky": (40, 26, 8),
                      "title": "REALM BREAKTHROUGH", "seal": "破境", "line": "Heaven and earth tremble."},
    "phase_success": {"hi": (170, 250, 214), "lo": (40, 150, 110), "glow": (90, 230, 170), "sky": (6, 34, 30),
                      "title": "BOTTLENECK BROKEN", "seal": "破关", "line": "Your Qi surges through the gate."},
    "realm_failure": {"hi": (255, 128, 108), "lo": (150, 24, 20), "glow": (220, 40, 30), "sky": (40, 6, 8),
                      "title": "MERIDIANS RECOIL", "seal": "反噬", "line": "The Qi turns on you."},
    "phase_failure": {"hi": (186, 204, 232), "lo": (80, 96, 130), "glow": (110, 140, 200), "sky": (12, 18, 34),
                      "title": "THE BOTTLENECK HOLDS", "seal": "瓶颈", "line": "The gate does not yield. Not yet."},
}


def _art(name):
    import os
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "scenes", name)


@lru_cache(maxsize=4)
def _backdrop(state):
    """The sky, tinted by the outcome, with a soft glow behind the ring. Cached per state."""
    from .battle import _galaxy
    st = STYLE[state]
    img = _galaxy(W, H, seed=51).copy()
    tint = Image.new("RGBA", img.size, st["sky"] + (110,))
    img.alpha_composite(tint)
    cx, cy = CENTER
    T.soft_glow(img, (cx - 420, cy - 300, cx + 420, cy + 300), alpha(st["glow"], 80), 90)
    T.soft_glow(img, (cx - 240, cy - 220, cx + 240, cy + 220), alpha(st["glow"], 90), 50)
    if state == "realm_success":
        _pillar(img, st)
    if state.endswith("success"):
        _rays(img, st)
    if state == "phase_failure":
        _wall(img, st)
    return img


def _pillar(img, st):
    """A column of heavenly light falling on the cultivator."""
    cx, cy = CENTER
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for w_, a in ((150, 50), (96, 80), (52, 120), (20, 200)):
        d.rectangle(P(cx - w_ / 2, 0, cx + w_ / 2, cy + 40), fill=alpha(st["hi"], a))
    layer = layer.filter(ImageFilter.GaussianBlur(14 * S))
    fade = Image.linear_gradient("L").resize(img.size)           # strong at the top of the ring, fading upward too
    img.alpha_composite(Image.composite(layer, Image.new("RGBA", img.size, (0, 0, 0, 0)),
                                        ImageChops.lighter(fade, Image.new("L", img.size, 120))))


def _rays(img, st):
    rays = Image.open(_art("victory_rays.png")).convert("RGBA")
    px = round(760 * S)
    rays = rays.resize((px, px), Image.LANCZOS)
    tinted = ImageChops.multiply(rays, Image.new("RGBA", rays.size, st["hi"] + (255,)))
    tinted.putalpha(rays.getchannel("A").point(lambda v: v * 0.75))
    cx, cy = CENTER
    img.alpha_composite(tinted, (round(cx * S - px / 2), round(cy * S - px / 2)))


def _wall(img, st):
    """Faint horizontal bands of cold Qi: the bottleneck that would not give."""
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    cx, cy = CENTER
    for k in range(-3, 4):
        y = cy + k * 46
        d.rounded_rectangle(P(cx - 330 + abs(k) * 30, y - 8, cx + 330 - abs(k) * 30, y + 8), radius=8 * S,
                            fill=alpha(st["hi"], 46 - abs(k) * 8))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(6 * S)))


def _lightning(img, st, rng):
    """Two forks of tribulation lightning striking down beside the ring."""
    cx, cy = CENTER
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for side in (-1, 1):
        x, y = cx + side * rng.uniform(230, 300), 0
        pts = [(x, y)]
        while y < cy + 30:
            y += rng.uniform(26, 48)
            x += rng.uniform(-30, 30) - side * 6
            pts.append((x, y))
        for w_, c in ((10, alpha(st["glow"], 90)), (4, alpha(st["hi"], 230)), (1.6, (255, 255, 255, 255))):
            d.line([P(*p) for p in pts], fill=c, width=round(w_ * S), joint="curve")
    glow = layer.filter(ImageFilter.GaussianBlur(8 * S))
    img.alpha_composite(glow)
    img.alpha_composite(layer)


def _sparks(img, st, rng, up=True, n=70):
    """Motes of Qi: rising around a success, flung outward from a failure."""
    cx, cy = CENTER
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(n):
        if up:
            x = cx + rng.gauss(0, 170)
            y = cy + 160 - rng.random() ** 0.7 * 420
        else:
            a = rng.random() * math.tau
            dist = RING_R + 20 + rng.random() * 260
            x, y = cx + math.cos(a) * dist, cy + math.sin(a) * dist * 0.8
        r = rng.choice([1.5, 2, 2.5, 3.5])
        c = st["hi"] if rng.random() < 0.7 else (255, 255, 255)
        d.ellipse(P(x - r, y - r, x + r, y + r), fill=alpha(c, rng.randint(140, 255)))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(1.2 * S)))
    img.alpha_composite(layer)


def _shards(img, st, rng):
    """Crimson shards of the broken Qi, thrown out from the ring."""
    cx, cy = CENTER
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(26):
        a = rng.random() * math.tau
        dist = RING_R + 30 + rng.random() * 220
        x, y = cx + math.cos(a) * dist, cy + math.sin(a) * dist * 0.75
        s = rng.uniform(6, 16)
        rot = rng.random() * math.tau
        pts = [(x + math.cos(rot + k * 2.3) * s * (1.6 if k == 0 else 0.8), y + math.sin(rot + k * 2.3) * s)
               for k in range(3)]
        d.polygon([P(*p) for p in pts], fill=alpha(mix(st["hi"], st["lo"], rng.random()), 220))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(3 * S)))
    img.alpha_composite(layer)


def _cracks(img, st, rng, center, r):
    """Jagged glowing cracks running across the ring."""
    cx, cy = center
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for k in range(5):
        a = k * math.tau / 5 + rng.uniform(-0.3, 0.3)
        pts = [(cx + math.cos(a) * r * 0.15, cy + math.sin(a) * r * 0.15)]
        dist = r * 0.15
        while dist < r * 1.12:
            dist += rng.uniform(16, 30)
            a += rng.uniform(-0.28, 0.28)
            pts.append((cx + math.cos(a) * dist, cy + math.sin(a) * dist))
        for w_, c in ((9, alpha(st["glow"], 120)), (3.5, alpha(st["hi"], 255)), (1.2, (255, 240, 230, 255))):
            d.line([P(*p) for p in pts], fill=c, width=round(w_ * S), joint="curve")
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(5 * S)))
    img.alpha_composite(layer)


@lru_cache(maxsize=2)
def _ring_art(px):
    return Image.open(_art("duel_ring_left.png")).convert("RGBA").resize((px, px), Image.LANCZOS)


def _cultivator(img, state, avatar):
    """The cultivator in the rune ring: their avatar, or the ring's painted figure; grey on a failure."""
    from .battle import DUEL_FACE
    st = STYLE[state]
    cx, cy = CENTER
    px = round(2 * RING_R * 1.1 * S)
    layer = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    ring = _ring_art(px)
    face = None
    if avatar:
        try:
            fr = round(2 * RING_R * DUEL_FACE * S)
            face = Image.open(io.BytesIO(avatar)).convert("RGBA").resize((fr, fr), Image.LANCZOS)
            m = Image.new("L", (fr, fr), 0)
            ImageDraw.Draw(m).ellipse((0, 0, fr - 1, fr - 1), fill=255)
            face.putalpha(m)
        except Exception:
            face = None
    if face is not None:
        from .battle import _ring_band
        layer.alpha_composite(face, ((px - face.size[0]) // 2, (px - face.size[1]) // 2))
        layer.alpha_composite(_ring_band(0, px))
    else:
        layer.alpha_composite(ring)
    a = layer.getchannel("A")
    if state.endswith("failure"):
        grey = layer.convert("L").convert("RGBA")
        layer = Image.blend(layer, grey, 0.7 if state == "realm_failure" else 0.45)
        layer = ImageChops.multiply(layer, Image.new("RGBA", layer.size, mix(st["hi"], (255, 255, 255), 0.45) + (255,)))
    else:
        layer = ImageChops.screen(layer, Image.new("RGBA", layer.size, alpha(mix(st["glow"], (0, 0, 0), 0.75), 255)))
    layer.putalpha(a)
    img.alpha_composite(layer, (round(cx * S - px / 2), round(cy * S - px / 2)))
    d = ImageDraw.Draw(img)
    rr = RING_R * 1.02
    d.ellipse(P(cx - rr, cy - rr, cx + rr, cy + rr), outline=alpha(st["hi"], 200), width=round(2.5 * S))


def _seal(img, state):
    """A square vermilion-style seal with the outcome in two characters, stamped by the ring."""
    st = STYLE[state]
    x, y, s = CENTER[0] + RING_R + 70, CENTER[1] + RING_R - 70, 92
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    fill = st["lo"] if state != "phase_failure" else (70, 84, 112)
    d.rounded_rectangle(P(x - s / 2, y - s / 2, x + s / 2, y + s / 2), radius=10 * S, fill=alpha(fill, 235),
                        outline=alpha(st["hi"], 255), width=round(3 * S))
    d.rounded_rectangle(P(x - s / 2 + 7, y - s / 2 + 7, x + s / 2 - 7, y + s / 2 - 7), radius=6 * S,
                        outline=alpha(st["hi"], 150), width=round(1.4 * S))
    f = cjk(34)
    for i, ch in enumerate(st["seal"]):
        T.text(d, (x, y - 20 + i * 40), ch, f, mix(st["hi"], (255, 255, 255), 0.4), "mm", shadow=False)
    layer = layer.rotate(-8, center=(x * S, y * S), resample=Image.BICUBIC)
    img.alpha_composite(layer)


def _transition(img, data, st, y):
    """old → new (success) or the gate that was tried (failure), with realm emblems."""
    d = ImageDraw.Draw(img)
    f = font("Cinzel.ttf", 32, "Black")
    left, right = data["from"], data["to"]
    ok = data["success"]
    arrow_w = 90
    lw, rw = T.width(d, left, f), T.width(d, right, f)
    total = lw + arrow_w + rw
    x = W / 2 - total / 2
    T.text(d, (x, y), left, f, SOFT if ok else TEXT, "lm")
    ax = x + lw + arrow_w / 2
    c = st["hi"]
    if ok:
        d.line(P(ax - 28, y, ax + 22, y), fill=c, width=round(3 * S))
        d.polygon([P(ax + 30, y), P(ax + 16, y - 10), P(ax + 16, y + 10)], fill=c)
        T.gold_text(img, (x + lw + arrow_w, y), right, f, "lm", top=mix(c, (255, 255, 255), 0.5), bottom=st["lo"],
                    glow=alpha(st["glow"], 120))
    else:
        dim = mix(SOFT, (0, 0, 0), 0.35)          # the arrow, struck through: the way stays shut
        d.line(P(ax - 28, y, ax + 22, y), fill=dim, width=round(3 * S))
        d.polygon([P(ax + 30, y), P(ax + 16, y - 10), P(ax + 16, y + 10)], fill=dim)
        d.line(P(ax - 8, y + 16, ax + 10, y - 16), fill=c, width=round(4 * S))
        T.text(d, (x + lw + arrow_w, y), right, f, mix(SOFT, (0, 0, 0), 0.25), "lm")


def _facts(img, box, facts, st):
    """The glass strip of results: up to three (icon, big value, small label)."""
    _glass(img, box, edge=mix(st["hi"], EDGE, 0.4), a=195, width=1.8)
    x0, y0, x1, y1 = box
    n = max(1, len(facts))
    w = (x1 - x0) / n
    for i, (icon, value, label, color) in enumerate(facts):
        cx = x0 + w * (i + 0.5)
        if i:
            ImageDraw.Draw(img).line(P(x0 + w * i, y0 + 18, x0 + w * i, y1 - 18), fill=alpha(EDGE, 90),
                                     width=max(1, S))
        d = ImageDraw.Draw(img)
        vf = font("Inter.ttf", 32, "Bold")
        tw = T.width(d, value, vf)
        T.icon(img, icon, (cx - tw / 2 - 26, y0 + 44), 36, color)
        T.text(ImageDraw.Draw(img), (cx - tw / 2 + 2, y0 + 44), value, vf, mix(color, (255, 255, 255), 0.45), "lm")
        T.text(ImageDraw.Draw(img), (cx, y0 + 88), T.fit(d, label, font("Inter.ttf", 24, "Medium"), w - 30),
               font("Inter.ttf", 24, "Medium"), SOFT, "mm")


def render_breakthrough(data):
    state = ("realm_" if data["kind"] == "realm" else "phase_") + ("success" if data["success"] else "failure")
    st = STYLE[state]
    rng = random.Random(data.get("seed", 7))
    img = _backdrop(state).copy()
    if state == "realm_success":
        _lightning(img, st, rng)
    if state.endswith("success"):
        _sparks(img, st, rng, up=True, n=90 if state == "realm_success" else 60)
    elif state == "realm_failure":
        _shards(img, st, rng)
        _sparks(img, st, rng, up=False, n=50)
    _cultivator(img, state, data.get("avatar"))
    if state == "realm_failure":
        _cracks(img, st, rng, CENTER, RING_R)
    _seal(img, state)
    # words
    d = ImageDraw.Draw(img)
    T.text(d, (36, 40), data["name"].upper(), font("Cinzel.ttf", 24, "Bold"), (226, 230, 240), "lm")
    T.text(d, (W - 36, 40), f"{data['chance']:.0%} CHANCE", font("Cinzel.ttf", 24, "Bold"), (226, 230, 240), "rm")
    ty = CENTER[1] + RING_R + 74
    T.gold_text(img, (W / 2, ty), st["title"], font("Cinzel.ttf", 62, "Black"), "mm",
                top=mix(st["hi"], (255, 255, 255), 0.45), bottom=st["lo"], glow=alpha(st["glow"], 150))
    d = ImageDraw.Draw(img)
    T.text(d, (W / 2, ty + 56), data.get("line") or st["line"], font("Inter.ttf", 28, "Medium"), TEXT, "mm")
    _transition(img, data, st, ty + 116)
    _facts(img, (40, H - 160, W - 40, H - 36), data["facts"], st)
    ImageDraw.Draw(img).rounded_rectangle(P(5, 5, W - 5, H - 5), radius=12 * S, outline=alpha(st["hi"], 200),
                                          width=round(2 * S))
    return T.finish(img)
