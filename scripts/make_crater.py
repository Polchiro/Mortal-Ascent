"""Draws art/fx/crater.webp: the split, glowing ground a Mountain Tiger leaves after its Mountain-Splitting Pounce
(battle.UNIQUE_SKILLS). Seen from the side, so the crater is a flat ellipse. Run: python -m scripts.make_crater"""
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

W, H = 1000, 340
CX, CY = W / 2, H * 0.52
RX, RY = W * 0.46, H * 0.40
OUT = os.path.join(os.path.dirname(__file__), "..", "art", "fx", "crater.webp")


def crack(rng, d, x, y, ang, length, width, depth=0):
    """A jagged crack from (x, y) outwards, squashed into the ground's ellipse, forking now and then."""
    pts = [(x, y)]
    step = 14
    for _ in range(int(length / step)):
        ang += rng.uniform(-0.45, 0.45)
        x += math.cos(ang) * step
        y += math.sin(ang) * step * (RY / RX)
        pts.append((x, y))
        if depth < 2 and rng.random() < 0.08:
            crack(rng, d, x, y, ang + rng.choice((-1, 1)) * rng.uniform(0.5, 1.0), length * 0.45, width * 0.6, depth + 1)
    for i in range(len(pts) - 1):
        w = max(1, round(width * (1 - i / len(pts))))
        d.line([pts[i], pts[i + 1]], fill=255, width=w)


def main(seed=11):
    rng = random.Random(seed)
    # scorched ground: a soft dark ellipse
    ground = Image.new("L", (W, H), 0)
    ImageDraw.Draw(ground).ellipse((CX - RX * 0.82, CY - RY * 0.78, CX + RX * 0.82, CY + RY * 0.78), fill=240)
    ground = ground.filter(ImageFilter.GaussianBlur(34))
    # the cracks
    cracks = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(cracks)
    for i in range(14):
        a = i / 14 * math.tau + rng.uniform(-0.15, 0.15)
        crack(rng, d, CX + math.cos(a) * 30, CY + math.sin(a) * 12, a, rng.uniform(220, 420), rng.uniform(7, 11))
    d.ellipse((CX - 34, CY - 12, CX + 34, CY + 12), fill=255)          # the impact point
    ring = Image.new("L", (W, H), 0)
    ImageDraw.Draw(ring).ellipse((CX - 210, CY - 72, CX + 210, CY + 72), outline=150, width=3)
    cracks = ImageChops.lighter(cracks, ring.filter(ImageFilter.GaussianBlur(1)))
    cracks = ImageChops.multiply(cracks, ground.point(lambda v: min(255, v * 2)))
    # colour: dark earth, then a wide orange glow, then the gold-white cracks themselves
    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    earth = Image.new("RGBA", (W, H), (26, 14, 8, 0))
    earth.putalpha(ground)
    out.alpha_composite(earth)
    for blur, col, gain in ((26, (255, 120, 20), 0.9), (9, (255, 170, 50), 1.2), (2.5, (255, 214, 120), 1.6)):
        layer = Image.new("RGBA", (W, H), col + (0,))
        layer.putalpha(cracks.filter(ImageFilter.GaussianBlur(blur)).point(lambda v, g=gain: min(255, round(v * g))))
        out.alpha_composite(layer)
    core = Image.new("RGBA", (W, H), (255, 246, 214, 0))
    core.putalpha(cracks.point(lambda v: 255 if v > 200 else 0).filter(ImageFilter.MinFilter(3)))
    out.alpha_composite(core)
    # a few embers and stones
    d = ImageDraw.Draw(out)
    for _ in range(40):
        a, r = rng.uniform(0, math.tau), rng.uniform(0.2, 0.9)
        x, y = CX + math.cos(a) * RX * r, CY + math.sin(a) * RY * r
        s = rng.uniform(2, 6)
        d.ellipse((x - s, y - s * 0.7, x + s, y + s * 0.7), fill=(255, 190, 90, rng.randint(120, 230)) if rng.random() < 0.5
                  else (58, 40, 30, 230))
    out.save(OUT, "WEBP", quality=88, method=6)
    print(OUT, out.size)


if __name__ == "__main__":
    main()
