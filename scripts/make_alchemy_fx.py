"""Turn SHOAIB's alchemy videos (Gemini, 1280 x 720, 24 fps, 10 s, effects on black) into the clips the craft page
plays around the cauldron (art/fx/alchemy/<name>.mp4; web/templates/alchemy_play.html, docs/web.md "Alchemy
animations"). The Tribulation's storm is a whole scene: scripts/make_background_loop.py makes it
(art/scenes/alchemy_tribulation.mp4).

Each clip is cut to its own part of the frame (CLIPS: x, y, width, height), which also leaves out Gemini's mark (it
sits at about 1160, 600), and made smaller (`width`). The page lays them over the dark card with `screen`, so their
black is see-through.
- loops (fire, swirl, the pill pulsing): the last LOOP seconds fade into the start, so they loop with no jump;
- once (splash, the pill forming, the explosion, a lightning strike): the part where it happens.
H.264 (quality 26: flames and glow hide it), no sound, fast start.

    python -m scripts.make_alchemy_fx DIR      (DIR holds fire_low.mp4 ... lightning.mp4, the names in CLIPS)
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "fx", "alchemy")
LOOP = 1.2
FIRE = (240, 0, 800, 720)        # the three fires share one frame, so the flames don't move when the heat changes
# name: (video, (x, y, w, h) crop, output width, "loop" | (start, end) seconds)
CLIPS = {
    "fire_low": ("fire_low", FIRE, 480, "loop"),
    "fire_mid": ("fire_mid", FIRE, 480, "loop"),
    "fire_high": ("fire_high", FIRE, 480, "loop"),
    "swirl": ("swirl", (280, 0, 720, 720), 420, "loop"),
    "splash": ("splash", (280, 0, 720, 720), 400, (0.7, 5.2)),
    "condense_in": ("condense", (190, 0, 900, 720), 560, (0.0, 5.0)),
    "condense_loop": ("condense", (190, 0, 900, 720), 560, (5.0, 10.0, "loop")),
    "explode": ("explode", (160, 0, 960, 720), 640, (0.0, 9.8)),
    "lightning": ("lightning", (190, 0, 900, 720), 450, (0.3, 4.0)),
}
COMMON = ["-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
          "-r", "24"]


def length(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def make(name, src_dir):
    src, (x, y, w, h), width, span = CLIPS[name]
    video = os.path.join(src_dir, f"{src}.mp4")
    out = os.path.join(OUT, f"{name}.mp4")
    shape = f"crop={w}:{h}:{x}:{y},scale={width}:-2,format=yuv420p"
    if span == "loop" or (isinstance(span, tuple) and span[-1] == "loop"):
        a, b = (0.0, length(video)) if span == "loop" else span[:2]
        L = LOOP
        graph = (f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,{shape},split=3[p][q][r];"
                 f"[p]trim=0:{L},setpts=PTS-STARTPTS[head];"
                 f"[q]trim={b - a - L}:{b - a},setpts=PTS-STARTPTS[tail];"
                 f"[r]trim={L}:{b - a - L},setpts=PTS-STARTPTS[mid];"
                 f"[tail][head]xfade=transition=fade:duration={L}:offset=0[xf];[xf][mid]concat=n=2:v=1:a=0[out]")
    else:
        a, b = span
        graph = f"[0:v]trim={a}:{b},setpts=PTS-STARTPTS,{shape}[out]"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-filter_complex", graph, "-map", "[out]"] + COMMON + [out],
                   check=True)
    print(f"{name}: {length(out):.1f} s, {os.path.getsize(out) // 1024} KB")


def main(src_dir):
    os.makedirs(OUT, exist_ok=True)
    for name in CLIPS:
        make(name, src_dir)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
