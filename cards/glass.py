"""Frosted glass panels: what is behind them blurred, a light tint, a thin bright edge, round corners."""
from PIL import Image, ImageDraw, ImageFilter

from .theme import S

GLASS_EDGE = (255, 255, 255, 52)


def glass(img, box, tint=(10, 16, 18), a=96, edge=GLASS_EDGE, r=18):
    """A frosted glass panel: what is behind it blurred, a light tint, a thin bright edge, round corners."""
    x0, y0, x1, y1 = (round(v * S) for v in box)
    rr = round(r * S)
    region = img.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(10 * S))
    tinted = Image.new("RGBA", region.size, tint + (a,))
    region.alpha_composite(tinted)
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, region.size[0] - 1, region.size[1] - 1), radius=rr, fill=255)
    img.paste(region, (x0, y0), mask)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((x0, y0, x1, y1), radius=rr, outline=edge, width=max(1, round(1.2 * S)))
    # a faint highlight along the top edge
    d.line((x0 + rr, y0 + round(1.5 * S), x1 - rr, y0 + round(1.5 * S)), fill=(255, 255, 255, 40), width=max(1, S))
