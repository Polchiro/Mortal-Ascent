"""Draws the Break's ground slam (web/static/fight.js, `slam`): the blade comes down into the ground in front of the
beast and splits it in a burst of blue Qi, as in SHOAIB's Break video (only the move and its effects are taken from it;
the cultivator keeps his own sword).

    art/fx/break_burst.webp    blue Qi spikes fanning up from the point of impact, seen from the side
    art/fx/break_crater.webp   the split ground under it: the Mountain Tiger's crater (scripts/make_crater.py) in blue

Run: python -m scripts.make_break_fx
"""
import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from scripts.make_crater import CX, CY, H as CH, RX, RY, W as CW, crack

FX = os.path.join(os.path.dirname(__file__), "..", "art", "fx")


def glow(mask, size, layers):
    """Colour a white mask: soft wide glows first, then sharper ones, then a white-hot core."""
    out = Image.new("RGBA", size, (0, 0, 0, 0))
    for blur, col, gain in layers:
        layer = Image.new("RGBA", size, col + (0,))
        layer.putalpha(mask.filter(ImageFilter.GaussianBlur(blur)).point(lambda v, g=gain: min(255, round(v * g))))
        out.alpha_composite(layer)
    core = Image.new("RGBA", size, (240, 252, 255, 0))
    core.putalpha(mask.point(lambda v: 255 if v > 210 else 0).filter(ImageFilter.MinFilter(3)))
    out.alpha_composite(core)
    return out


def burst(seed=5):
    """Sharp spikes of Qi fanning upwards from a point on the ground, longest in the middle, with flying shards."""
    rng = random.Random(seed)
    W, H = 900, 560
    bx, by = W / 2, H - 70
    mask = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(mask)
    for i in range(26):
        a = math.pi + math.pi * (0.06 + 0.88 * i / 25) + rng.uniform(-0.05, 0.05)    # 190° (left) to 350° (right)
        up = -math.sin(a)                                                            # 0 at the sides, 1 straight up
        length = rng.uniform(0.45, 1.0) * (150 + 330 * up ** 1.5)
        width = rng.uniform(7, 15) * (0.6 + 0.6 * up)
        tip = (bx + math.cos(a) * length, by + math.sin(a) * length * 0.95)
        side = (math.cos(a + math.pi / 2) * width, math.sin(a + math.pi / 2) * width)
        d.polygon([(bx + side[0], by + side[1]), tip, (bx - side[0], by - side[1])], fill=rng.randint(200, 255))
    for _ in range(34):                                                              # shards thrown out with it
        a = math.pi + rng.uniform(0.1, 0.9) * math.pi
        r = rng.uniform(120, 400)
        x, y = bx + math.cos(a) * r, by + math.sin(a) * r * 0.8
        s, t = rng.uniform(4, 11), rng.uniform(0, math.pi)
        d.polygon([(x + math.cos(t) * s * 2, y + math.sin(t) * s * 2), (x + math.cos(t + 2.2) * s, y + math.sin(t + 2.2) * s),
                   (x + math.cos(t + 4) * s, y + math.sin(t + 4) * s)], fill=rng.randint(170, 255))
    d.ellipse((bx - 60, by - 22, bx + 60, by + 22), fill=255)                        # the flash where the blade bit
    out = glow(mask, (W, H), ((30, (30, 110, 255), 0.85), (10, (60, 170, 255), 1.2), (3, (150, 225, 255), 1.6)))
    out.save(os.path.join(FX, "break_burst.webp"), "WEBP", quality=88, method=6)
    return out


def crater(seed=23):
    """The ground split open, as the Tiger's crater but in cold blue Qi and a little smaller."""
    rng = random.Random(seed)
    ground = Image.new("L", (CW, CH), 0)
    ImageDraw.Draw(ground).ellipse((CX - RX * 0.8, CY - RY * 0.76, CX + RX * 0.8, CY + RY * 0.76), fill=230)
    ground = ground.filter(ImageFilter.GaussianBlur(34))
    cracks = Image.new("L", (CW, CH), 0)
    d = ImageDraw.Draw(cracks)
    for i in range(16):
        a = i / 16 * math.tau + rng.uniform(-0.15, 0.15)
        crack(rng, d, CX + math.cos(a) * 26, CY + math.sin(a) * 10, a, rng.uniform(200, 400), rng.uniform(6, 10))
    d.ellipse((CX - 30, CY - 11, CX + 30, CY + 11), fill=255)
    cracks = ImageChops.multiply(cracks, ground.point(lambda v: min(255, v * 2)))
    out = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    earth = Image.new("RGBA", (CW, CH), (8, 14, 30, 0))
    earth.putalpha(ground.point(lambda v: round(v * 0.8)))
    out.alpha_composite(earth)
    out.alpha_composite(glow(cracks, (CW, CH), ((24, (20, 90, 255), 0.9), (8, (60, 160, 255), 1.2), (2.5, (160, 225, 255), 1.6))))
    d = ImageDraw.Draw(out)
    for _ in range(36):                                                              # loose stones and Qi sparks
        a, r = rng.uniform(0, math.tau), rng.uniform(0.2, 0.9)
        x, y = CX + math.cos(a) * RX * r, CY + math.sin(a) * RY * r
        s = rng.uniform(2, 6)
        d.ellipse((x - s, y - s * 0.7, x + s, y + s * 0.7), fill=(140, 210, 255, rng.randint(120, 230)) if rng.random() < 0.5
                  else (40, 40, 48, 230))
    out.save(os.path.join(FX, "break_crater.webp"), "WEBP", quality=88, method=6)
    return out


def main():
    for im, name in ((burst(), "break_burst"), (crater(), "break_crater")):
        print(name, im.size)


if __name__ == "__main__":
    main()
