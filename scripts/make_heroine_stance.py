"""Build the female cultivator's fighting stance from SHOAIB's video of her (looks.IDLE_SHEETS): the loop she plays
while she stands between moves, in beast fights (web/templates/explore_play.html) and duels (web/templates/duel.html),
in place of her still idle picture. docs/web.md "The stance".

The video (Gemini, 720 x 1280, 24 fps, 10 s) is her standing on guard on a grey backdrop, sword held low in her
right hand, her left hand at her chest, breathing, her sleeves, hair and skirts stirring. The script finds the
stretch (3-6 s) whose last frame best meets its first (scripts/make_heroine_walk.stride), takes COLS x ROWS frames
evenly from it, cuts her out (rembg, as every heroine script does; only_her drops Gemini's sparkle mark), and places
her exactly where her still idle picture stands: as tall, feet on the same line (scripts/make_hero_fist.place), and her
feet over the still's feet (`on_her_feet`), so she doesn't move when she changes from the stance to a pose.

    python -m scripts.make_heroine_stance path/to/her_stance.mp4

Writes art/portraits/fight/hero_female_stance.webp (COLS x ROWS frames of 320 x 360) and prints the loop length, for
looks.IDLE_SHEETS. Needs ffmpeg, numpy, Pillow, scipy and rembg.
"""
import os
import sys
import tempfile

from scripts.make_hero_attack import COLS, OUT, cut, frames, grid
from scripts.make_hero_fist import place
from scripts.make_heroine_deflect import only_her
from scripts.make_heroine_guard import edge_clean
from scripts.make_heroine_moves import in_cells
from scripts.make_heroine_walk import probe, stride

ROWS = 9                         # COLS x ROWS frames fill the grid exactly, so the page can step through it in CSS
SPAN = (72, 144)                 # one loop: 3-6 s of video
FPS = 24


def feet_x(im):
    """The middle of her feet: the solid pixels in the lowest 4% of her height."""
    import numpy as np
    a = np.asarray(im.getchannel("A")) > 128
    ys, xs = np.where(a)
    low = ys >= ys.max() - (ys.max() - ys.min()) * 0.04
    return float(xs[low].mean())


def on_her_feet(images, ref):
    """Move every frame sideways so her feet stand where the still idle picture's feet do: place() lines up the
    whole outline, sword and sleeves included, and her sword points the other way here, so that alone left her
    standing further right than the still and its strike poses (she would jump sideways between them)."""
    from PIL import Image
    dx = round(feet_x(ref) - feet_x(images[0]))
    out = []
    for im in images:
        cell = Image.new("RGBA", im.size, (0, 0, 0, 0))
        cell.alpha_composite(im.crop((max(0, -dx), 0, im.width - max(0, dx), im.height)), (max(0, dx), 0))
        out.append(cell)
    return out, dx


def main(video):
    w, h = probe(video)
    a, n = stride(video, 0, SPAN)
    count = COLS * ROWS
    picks = [a + round(j * n / count) for j in range(count)]       # the loop's own end (a + n) is the next start
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=(w, h, 0, 0), start=0, length=(a + n + 1) / FPS,
                      numbers=[i + 1 for i in picks])
    ref = in_cells(os.path.join(OUT, "hero_female_idle.webp"))
    images, scale, _ = place([only_her(im) for im in cut(clip)], ref)
    images, dx = on_her_feet([only_her(edge_clean(im)) for im in images], ref)
    lost = [i for i, im in enumerate(images) if im.getchannel("A").crop((0, 0, 1, im.height)).getextrema()[1] > 40
            or im.getchannel("A").crop((im.width - 1, 0, im.width, im.height)).getextrema()[1] > 40]
    if lost:
        sys.exit(f"frames {lost} run past the cell's edge")
    rows = grid(images, "hero_female_stance.webp")
    print(f"hero_female_stance.webp: {count} frames, {COLS} x {rows}, video frames {a}-{a + n}, "
          f"loop {n / FPS:.2f} s, scale {scale:.2f}, moved {dx:+d} px onto the still's feet (no shift)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
