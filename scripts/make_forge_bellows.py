"""The bellows in SHOAIB's workshop picture (art/forge/workshop.jpg) cut out, so the live forge can work them when you
pump (static/forge_live.js, docs/web.md "Live forge"):

- art/forge/bellows.webp: the bellows alone (the picture inside OUTLINE, a soft edge), laid exactly over themselves;
- art/forge/bellows_wall.webp: the wall behind them, filled in from around (OpenCV inpaint), under the cut-out, so when
  the bellows squeeze the picture's own bellows never show twice.
Both are BOX of the picture; the page places them by BOX in percent (workshop.jpg is 1024 x 572).

    python -m scripts.make_forge_bellows
Needs numpy, Pillow and opencv-python.
"""
import json
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "art", "forge")
# the bellows' outline in the picture's pixels: the handle at the top, the leather body, the nozzle at the bottom right
OUTLINE = [(139, 127), (152, 124), (160, 165), (178, 170), (204, 193), (220, 226), (232, 254), (252, 284), (254, 297),
           (240, 295), (205, 281), (165, 265), (128, 248), (115, 232), (117, 205), (127, 186), (143, 172), (146, 165)]
BOX = (96, 112, 268, 308)          # x0, y0, x1, y1


def main():
    import cv2
    pic = Image.open(os.path.join(ART, "workshop.jpg")).convert("RGB")
    W, H = pic.size
    mask = Image.new("L", pic.size, 0)
    ImageDraw.Draw(mask).polygon(OUTLINE, fill=255)
    soft = mask.filter(ImageFilter.GaussianBlur(1.6))
    cut = pic.convert("RGBA")
    cut.putalpha(soft)
    cut.crop(BOX).save(os.path.join(ART, "bellows.webp"), quality=90, method=6)

    grown = np.array(mask.filter(ImageFilter.MaxFilter(13)))
    bgr = cv2.cvtColor(np.array(pic), cv2.COLOR_RGB2BGR)
    wall = cv2.inpaint(bgr, grown, 12, cv2.INPAINT_TELEA)
    wall = Image.fromarray(cv2.cvtColor(wall, cv2.COLOR_BGR2RGB)).filter(ImageFilter.GaussianBlur(1.2)).convert("RGBA")
    wall.putalpha(Image.fromarray(grown).filter(ImageFilter.GaussianBlur(4)))
    wall.crop(BOX).save(os.path.join(ART, "bellows_wall.webp"), quality=85, method=6)
    x0, y0, x1, y1 = BOX
    print(json.dumps({"left": round(x0 / W * 100, 2), "top": round(y0 / H * 100, 2),
                      "width": round((x1 - x0) / W * 100, 2), "height": round((y1 - y0) / H * 100, 2),
                      "nozzle": [round(253 / W, 3), round(296 / H, 3)]}))


if __name__ == "__main__":
    main()
