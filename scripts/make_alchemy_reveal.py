"""Turn SHOAIB's reveal video (Gemini, 1280 x 720, 10 s: a bronze cauldron's lid blasts open and golden light pours up
out of it, on black) into the clip the pill reveal plays (art/fx/alchemy/reveal.mp4; alchemy_play.html .rlight,
docs/web.md "The pill reveal").

The video brings its own cauldron, which is not the game's, so only its light is kept:
- cut to the middle (x 160-1120: Gemini's mark at about 1160, 600 falls outside), 640 x 480;
- darks crushed (curves), so the dull bronze goes black;
- the cauldron's body masked out with a soft-edged black box below its rim (the light lights the bronze up);
- 0.8 s to 7.3 s: from just before the lid glows to the last sparks.
The page lays it over the game's cauldron with `screen`, its rim on the cauldron's mouth, tinted to the pill's grade.

    python -m scripts.make_alchemy_reveal video.mp4
Needs ffmpeg and Pillow.
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "fx", "alchemy", "reveal.mp4")
BODY = (150, 240, 495, 480)      # the video cauldron's body in the 640 x 480 cut, masked out
START, LENGTH = 0.8, 6.5


def main(video):
    with tempfile.TemporaryDirectory() as tmp:
        mask = os.path.join(tmp, "mask.png")
        m = Image.new("L", (640, 480), 255)
        ImageDraw.Draw(m).rounded_rectangle(BODY, radius=40, fill=0)
        m.filter(ImageFilter.GaussianBlur(14)).convert("RGB").save(mask)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(START), "-t", str(LENGTH), "-i", video, "-loop", "1",
                        "-i", mask, "-an", "-filter_complex",
                        "[0:v]crop=960:720:160:0,curves=all='0/0 0.2/0 0.45/0.35 1/1',scale=640:480,fps=24,format=gbrp[v];"
                        "[1:v]scale=640:480,format=gbrp[m];[v][m]blend=all_mode=multiply:shortest=1,format=yuv420p",
                        "-c:v", "libx264", "-crf", "24", "-movflags", "+faststart", OUT], check=True)
    print("wrote", OUT, f"{os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1])
