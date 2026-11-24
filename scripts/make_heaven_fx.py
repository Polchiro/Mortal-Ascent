"""Build the Heaven techniques' moving effects from SHOAIB's videos (Gemini / Veo, 1920 x 1080, 24 fps, light on
black; docs/web.md "Heaven techniques: the long play"), one strip of frames each, as Nine Dragons' are
(scripts/make_dragon_fx.py, whose tools this uses: black becomes clear, each pixel's opacity is its brightness):

- meteor_falling_kick: a blazing meteor falls from the top left (video frames 0-64) and strikes the ground (68, `boom`):
  a flash, fire and rocks thrown up, glowing cracks, embers;
- heaven_rending_palm: the sky splits and a colossal golden hand comes down (0-80), slams the ground (84, `boom`),
  and bursts into golden shards and pillars of light (114 on);
- void_mirror_stance: a violet mirror-sphere ringed with runes hangs still (0-28), the blow strikes it and violet
  lightning shoots back to the right (30, `boom`), it shatters into shards (114 on);
- immortal_lotus_body: a pink lotus blooms open (0-48), a pillar of golden light rises from its heart (60, `boom`),
  petals drift, it closes (144 on);
- cloud_walking_shadow: a figure of cloud stands (0-24), turns (30-44) and is gone to the right, leaving long trails
  of white and golden cloud (48 on, `boom` at 54) that thin into sparkles.

The slow parts are thinned (PICKS). Writes art/fx/tech/<technique>_fx.webp and prints the frame counts for
web/technique_fx.py.

    python -m scripts.make_heaven_fx meteor_falling_kick=meteor.mp4 heaven_rending_palm=palm.mp4 ...

Needs ffmpeg, numpy and Pillow.
"""
import json
import sys

from scripts.make_dragon_fx import frames, lit, sheet

CELL = (400, 225)


def r(a, b, step=2):
    return list(range(a, b + 1, step))


# technique: (video frames kept, the video frame of the moment the blow lands, black below this is clear)
PICKS = {
    "meteor_falling_kick": (r(0, 64) + r(66, 110) + r(114, 150, 4), 68, 14),
    "heaven_rending_palm": (r(0, 80) + r(82, 112) + r(114, 150, 3), 84, 14),
    "void_mirror_stance": (r(0, 28, 4) + r(30, 60) + r(64, 108, 6) + r(110, 150), 30, 30),
    "immortal_lotus_body": (r(0, 48) + r(50, 140, 5) + r(144, 186, 3), 60, 12),
    "cloud_walking_shadow": (r(0, 44, 4) + r(46, 100) + r(104, 130, 4), 54, 14),
}


def build(name, video):
    picks, boom, floor = PICKS[name]
    cells = [lit(f, floor) for f in frames(video, picks, CELL)]
    out = sheet(cells, f"{name}_fx.webp")
    del out["src"]
    return dict(out, boom=picks.index(boom))


if __name__ == "__main__":
    pairs = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
    if not pairs or set(pairs) - set(PICKS):
        sys.exit(__doc__)
    print(json.dumps({k: build(k, v) for k, v in pairs.items()}))
