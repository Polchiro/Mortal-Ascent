"""Build the male cultivator's sidestep from SHOAIB's video of him (looks.MOTION_SHEETS "sidestep", web/static/fight.js
`sidestepped`; docs/web.md "Techniques"): what Drifting Mist Steps and Cloud-Walking Shadow play when they slip the
beast's Break, as hers does.

The video (Gemini, 1280 x 720, 24 fps) is a storyboard of six numbered panels, 3 x 2, each about 424 x 356, on white.
The bottom-left panel (x 0-424, y 362-718, its number at the top-left whited out) stands; from about 1.4 s he turns and
launches into a low dash, wrapped in swirls of blue Qi (about 1.7-2.3 s), and holds the dash to the end of the video:
it never comes back. So the sheet is his launch and dash (1.21-2.67 s), then his own launch frames played back
(1.62 back to 1.21 s), rising out of the dash onto his feet again. No frame is drawn or altered. The grey dust the
dash kicks up is the backdrop's colour and can't be cut out cleanly, so it is left out; the blue Qi is kept
(make_hero_deflect `qi`), and his robes are matched to his sword frames as there.

Every 2nd video frame is kept, so the page plays it at the video's own pace (12 frames a second).

    python -m scripts.make_hero_sidestep path/to/his_sidestep.mp4

Writes art/portraits/fight/hero_male_sidestep.webp: 24 frames of 320 x 360 in an 8-wide grid, for looks.MOTION_SHEETS.
Needs ffmpeg, numpy, Pillow, scipy and rembg, as make_hero_attack does.
"""
import sys
import tempfile

from scripts.make_hero_attack import frames
from scripts.make_hero_deflect import build, report

CELL = (424, 356, 0, 362)          # w, h, x, y: the bottom-left panel
LABEL = (0, 0, 34, 34)             # its painted number
START = 1.2                        # s
OUT_AND_DASH = range(1, 36, 2)     # 1.21-2.62 s: standing, the launch, the dash (18 frames)
BACK_UP = range(11, 0, -2)         # 1.62-1.21 s: his launch, played back (6 frames)


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        clip = frames(video, tmp, cell=CELL, start=START, length=1.5, numbers=list(OUT_AND_DASH) + list(BACK_UP))
    for im in clip:
        im.paste((246, 246, 246), LABEL)
    images, scale, shift, rows = build(clip, "hero_male_sidestep.webp")
    report(images, "hero_male_sidestep.webp", scale, shift, rows)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
