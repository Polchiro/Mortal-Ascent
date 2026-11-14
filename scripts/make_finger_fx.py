"""Turn SHOAIB's Gemini designs for the finger techniques into the effect pictures the fight plays (web/static/fight.js,
`technique`; docs/web.md "Techniques"), cleaned like the punch designs (scripts/make_fist_fx.py: the painted
checkerboard and Gemini's sparkle removed). Both are beams pointing right, their tail where the fingertip is.

    python -m scripts.make_finger_fx viper.png river.png

    viper.png    Viper Fang Finger: an emerald beam with a viper's head at its tip (viper_fang_finger)
    river.png    River-Splitting Finger: a blue beam parting two walls of water (river_splitting_finger)

Writes art/fx/tech/<technique id>.webp.
"""
import sys

from PIL import Image

from scripts.make_fist_fx import key_glow, save


def main(paths):
    if len(paths) != 2:
        sys.exit(__doc__)
    for tid, path in zip(("viper_fang_finger", "river_splitting_finger"), paths):
        save(key_glow(Image.open(path)), tid)


if __name__ == "__main__":
    main(sys.argv[1:])
