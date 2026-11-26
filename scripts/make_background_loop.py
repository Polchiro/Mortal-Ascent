"""Turn SHOAIB's background video of a fight place (Gemini, 1280 x 720, 24 fps, 10 s, its first frame the place's
painting) into the seamless loop the fight plays behind the fighters (art/scenes/<scene>.mp4; web/static/ambient.js
PLACES[...].video; docs/web.md "Living backgrounds").

- Gemini's sparkle mark: covered with the ground just left of it (a soft-edged copy) on one frame, and that patch
  laid on every frame. The ground under the mark doesn't move, so the patch never shows. MARK: its middle and size.
- The loop: the video's last LOOP seconds fade into its first ones, and the clip ends where that fade began, so the
  end flows into the start with no jump (8.5 s from a 10 s video).
- H.264, no sound, quality 20 (a lower one shows its noise as a flick at the join), fast start for the web.
- Its sound (Veo's ambience: wind, rain, thunder...) looped the same way, into art/scenes/<scene>.m4a: the end
  fades into the start over LOOP seconds, so it never clicks or jumps. A video without sound makes no file.
- With the painting given too, the painting is cleaned of the same marks and written as art/scenes/<scene>.jpg
  (the picture the fight shows until the video plays, and on reduced motion).
- EXTRA_MARKS: a scene's other marks (Gemini's "AI" badge on some), on a 1280 x 720 video.

    python -m scripts.make_background_loop battle_northern_sea_wilds video.mp4 [painting.png]

Needs ffmpeg, numpy, Pillow and opencv-python.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = (1160, 598, 29)          # Gemini's sparkle on a 1280 x 720 video: its middle (x, y) and a radius that covers it
EXTRA_MARKS = {"battle_red_cliff_gorge": [(1229, 660, 30)]}
FROM_BELOW = {"battle_thunder_peaks"}   # left of the mark is a puddle that flashes with the lightning: take the stone below     # the "AI" badge on that one
LOOP = 1.5                      # seconds faded from the end into the start
CRF = 20


def duration(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def marks(scene, w, h):
    """The scene's marks, scaled from the 1280 x 720 video to a picture of w x h."""
    k = w / 1280
    return [(round(x * k), round(y * h / 720), round(r * k)) for x, y, r in [MARK] + EXTRA_MARKS.get(scene, [])]


def cover(img, x, y, r, below=False):
    """Paint a mark over with the ground just left of it (a soft-edged copy, like a clone stamp): the texture stays
    sharp, where an inpaint leaves a smudge."""
    R = int(r * 1.35)
    dx = int(r * 2.6)
    h, w = img.shape[:2]
    y0, y1, x0, x1 = max(0, y - R), min(h, y + R), max(0, x - R), min(w, x + R)
    sx0, sx1 = x0 - dx, x1 - dx
    if below:
        dy = min(dx, h - y1)
        sx0, sx1, sy0, sy1 = x0, x1, y0 + dy, y1 + dy
    elif sx0 < 0:                                   # no room on the left: take it from above
        sx0, sx1, sy0, sy1 = x0, x1, y0 - dx, y1 - dx
    else:
        sy0, sy1 = y0, y1
    src = img[sy0:sy1, sx0:sx1].astype(np.float32)
    yy, xx = np.mgrid[y0:y1, x0:x1]
    d = np.hypot(xx - x, yy - y) / R
    a = np.clip((1 - d) / 0.35, 0, 1)[..., None]      # solid in the middle, fading over the outer third
    out = img.copy()
    out[y0:y1, x0:x1] = (src * a + img[y0:y1, x0:x1].astype(np.float32) * (1 - a)).astype(np.uint8)
    return out, (x0, y0, x1, y1), a[..., 0]


def has_audio(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                          "-of", "csv=p=0", video], capture_output=True, text=True).stdout
    return bool(out.strip())


def clean_painting(scene, painting):
    import cv2
    fixed = cv2.imread(painting)
    h, w = fixed.shape[:2]
    for x, y, r in marks(scene, w, h):
        fixed = cover(fixed, x, y, r, scene in FROM_BELOW)[0]
    out = os.path.join(ROOT, "art", "scenes", f"{scene}.jpg")
    cv2.imwrite(out, fixed, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"wrote {out}: {w} x {h}, {os.path.getsize(out) // 1024} KB")


def loop_sound(scene, video, T):
    """The video's ambience as a seamless loop of the same length as the video's loop (art/scenes/<scene>.m4a)."""
    out = os.path.join(ROOT, "art", "scenes", f"{scene}.m4a")
    graph = (f"[0:a]atrim=0:{T},asetpts=PTS-STARTPTS,asplit=3[a][b][c];"
             f"[a]atrim=0:{LOOP},asetpts=PTS-STARTPTS,afade=t=in:d={LOOP}[head];"
             f"[b]atrim={T - LOOP}:{T},asetpts=PTS-STARTPTS,afade=t=out:d={LOOP}[tail];"
             f"[c]atrim={LOOP}:{T - LOOP},asetpts=PTS-STARTPTS[mid];"
             f"[tail][head]amix=inputs=2:normalize=0:duration=longest[xf];"
             f"[xf][mid]concat=n=2:v=0:a=1,loudnorm=I=-20:TP=-2[out]")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-filter_complex", graph, "-map", "[out]", "-vn",
                    "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-movflags", "+faststart", out], check=True)
    print(f"wrote {out}: {duration(out):.1f} s, {os.path.getsize(out) // 1024} KB")


def main(scene, video, painting=None):
    import cv2
    if painting:
        clean_painting(scene, painting)
    with tempfile.TemporaryDirectory() as tmp:
        still = os.path.join(tmp, "frame.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "5", "-i", video, "-frames:v", "1", still], check=True)
        frame = cv2.imread(still)
        fixed, alpha = frame, np.zeros(frame.shape[:2], np.float32)
        for x, y, r in marks(scene, frame.shape[1], frame.shape[0]):
            fixed, (x0, y0, x1, y1), a = cover(fixed, x, y, r, scene in FROM_BELOW)
            alpha[y0:y1, x0:x1] = np.maximum(alpha[y0:y1, x0:x1], a)
        patch = Image.fromarray(cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)).convert("RGBA")
        patch.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)))
        patch_path = os.path.join(tmp, "patch.png")
        patch.save(patch_path)
        T = duration(video)
        out = os.path.join(ROOT, "art", "scenes", f"{scene}.mp4")
        graph = (f"[0:v][1:v]overlay=shortest=1,format=yuv420p,split=3[a][b][c];"
                 f"[a]trim=0:{LOOP},setpts=PTS-STARTPTS[head];"
                 f"[b]trim={T - LOOP}:{T},setpts=PTS-STARTPTS[tail];"
                 f"[c]trim={LOOP}:{T - LOOP},setpts=PTS-STARTPTS[mid];"
                 f"[tail][head]xfade=transition=fade:duration={LOOP}:offset=0[xf];"
                 f"[xf][mid]concat=n=2:v=1:a=0[out]")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-loop", "1", "-i", patch_path,
                        "-filter_complex", graph, "-map", "[out]", "-an", "-c:v", "libx264", "-preset", "veryfast",
                        "-crf", str(CRF), "-tune", "grain", "-pix_fmt", "yuv420p", "-movflags", "+faststart", "-r", "24",
                        out], check=True)
    print(f"wrote {out}: {duration(out):.1f} s, {os.path.getsize(out) // 1024} KB")
    if has_audio(video):
        loop_sound(scene, video, T)
    else:
        print(f"{video} has no sound: no ambience for {scene}")


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    main(*sys.argv[1:])
