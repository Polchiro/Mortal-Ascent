"""Turn SHOAIB's background video of a fight place (Gemini, 1280 x 720, 24 fps, 10 s, its first frame the place's
painting) into the seamless loop the fight plays behind the fighters (art/scenes/<scene>.mp4; web/static/ambient.js
PLACES[...].video; docs/web.md "Living backgrounds").

- Gemini's sparkle mark: filled from what is around it (OpenCV inpaint) on one frame, and that patch laid on every
  frame with a soft edge. The ground under the mark doesn't move, so the patch never shows. MARK: its middle and size.
- The loop: the video's last LOOP seconds fade into its first ones, and the clip ends where that fade began, so the
  end flows into the start with no jump (8.5 s from a 10 s video).
- H.264, no sound, quality 20 (a lower one shows its noise as a flick at the join), fast start for the web.

    python -m scripts.make_background_loop battle_northern_sea_wilds video.mp4

Needs ffmpeg, numpy, Pillow and opencv-python.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MARK = (1160, 598, 29)          # Gemini's sparkle on a 1280 x 720 video: its middle (x, y) and a radius that covers it
LOOP = 1.5                      # seconds faded from the end into the start
CRF = 20


def duration(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def main(scene, video):
    import cv2
    with tempfile.TemporaryDirectory() as tmp:
        still = os.path.join(tmp, "frame.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "5", "-i", video, "-frames:v", "1", still], check=True)
        frame = cv2.imread(still)
        x, y, r = MARK
        mask = np.zeros(frame.shape[:2], np.uint8)
        cv2.circle(mask, (x, y), r, 255, -1)
        fixed = cv2.inpaint(frame, mask, 8, cv2.INPAINT_TELEA)
        patch = Image.fromarray(cv2.cvtColor(fixed, cv2.COLOR_BGR2RGB)).convert("RGBA")
        patch.putalpha(Image.fromarray(mask).filter(ImageFilter.GaussianBlur(3)))
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


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
