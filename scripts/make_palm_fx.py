"""Turn SHOAIB's Gemini designs for the palm techniques into the effect pictures the fight plays (web/static/fight.js,
`technique`; docs/web.md "Techniques"), cleaned the same way as the punch designs (scripts/make_fist_fx.py: the
painted checkerboard and Gemini's sparkle removed).

    python -m scripts.make_palm_fx twin.png heaven.png shadows.png

    twin.png      Twin Palm Strike: two palm prints in rings, side by side. Saved as its left and right print
                  (twin_palm_strike_1, _2), one for each of the technique's two hits.
    heaven.png    Heaven-Rending Palm: a giant golden palm in clouds (heaven_rending_palm).
    shadows.png   Thousand Shadow Palm: a fan of spectral palms (thousand_shadow_palm). Its palms are dim and
                  half-see-through, no brighter than the checker, and Gemini's checker flips light-for-dark in
                  patches, so neither brightness keying nor rembg works: the checker is rebuilt square by square
                  (`key_checker`) and taken away.

Rolling Thunder Palm keeps the thunder design already made by make_fist_fx (rolling_thunder_palm.webp).
Writes art/fx/tech/<name>.webp.
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

from scripts.make_fist_fx import SPARKLE, key_glow, save


def trim(im, pad=18):
    box = im.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
    return im.crop((max(0, box[0] - pad), max(0, box[1] - pad), min(im.width, box[2] + pad), min(im.height, box[3] + pad)))


# ── the checker, rebuilt: its square edges are read off the empty top and left bands; every empty square says
# whether its patch starts light or dark and what its two tones are; squares under the design get the phase that
# leaves the smoothest picture once taken away, and the tones of the nearest empty squares ──
def edges(profile):
    """Where the checker's squares change, along one row or column: strong steps 8-9 px apart (doubled ones merged,
    missed ones put back)."""
    d = np.abs(np.diff(profile))
    thr = d.max() * 0.35
    xs = [i + 1 for i in range(1, len(d) - 1) if d[i] > thr and d[i] >= d[i - 1] and d[i] >= d[i + 1]]
    out = []
    for x in xs:
        if out and x - out[-1] < 5: continue          # a doubled edge
        while out and x - out[-1] > 12: out.append(out[-1] + round((x - out[-1]) / round((x - out[-1]) / 8.5)))   # a missed one
        out.append(x)
    return np.array(out)
def rebuild(path, band=24):
    """The square grid: edges, and which pixels lie on a seam between squares."""
    im = Image.open(path).convert('RGB'); a = np.asarray(im).astype(np.float32); h, w = a.shape[:2]
    g = a.mean(-1)
    xe = edges(np.median(g[:band], 0)); ye = edges(np.median(g[:, :band], 1))
    # square index of each column / row: how many edges lie at or before it
    ix = np.searchsorted(xe, np.arange(w), side='right'); iy = np.searchsorted(ye, np.arange(h), side='right')
    par = (ix[None, :] + iy[:, None]) % 2
    # tone of each parity from the corner band
    corner = par[:band, :band]; cg = a[:band, :band]
    t0 = np.median(cg[corner == 0], 0); t1 = np.median(cg[corner == 1], 0)
    B = np.where(par[..., None] == 0, t0, t1)
    near = np.zeros((h, w), bool)
    for x in xe: near[:, max(0, x - 1):x + 1] = True
    for y in ye: near[max(0, y - 1):y + 1, :] = True
    return a, B, near, xe, ye
def key_patched(path, band=24):
    """The design over a rebuilt checker: colours and alpha."""
    a, _, near, xe, ye = rebuild(path, band)
    h, w = a.shape[:2]
    xs = np.concatenate([[0], xe, [w]]); ys = np.concatenate([[0], ye, [h]])
    nx, ny = len(xs) - 1, len(ys) - 1
    med = np.zeros((ny, nx, 3)); std = np.zeros((ny, nx)); grey = np.zeros((ny, nx))
    for j in range(ny):
        for i in range(nx):
            c = a[ys[j] + 1:max(ys[j] + 2, ys[j + 1] - 1), xs[i] + 1:max(xs[i] + 2, xs[i + 1] - 1)].reshape(-1, 3)
            med[j, i] = np.median(c, 0); std[j, i] = c.std(0).max(); grey[j, i] = np.ptp(med[j, i])
    v = med.max(-1)
    sure = (std < 7) & (grey < 10)
    # light or dark: split the sure squares' brightness in two
    thr = (np.percentile(v[sure], 10) + np.percentile(v[sure], 90)) / 2
    light = v > thr
    chk = (np.add.outer(np.arange(ny), np.arange(nx)) % 2).astype(bool)
    phase = light ^ chk
    # local tones: nearest sure square of each kind
    tones = {}
    for kind in (True, False):
        m = sure & (light == kind)
        ii = ndimage.distance_transform_edt(~m, return_distances=False, return_indices=True)
        tones[kind] = med[ii[0], ii[1]]
    # under the design: the phase that leaves the smoothest picture once the checker is taken away
    mean = np.zeros((ny, nx, 3))
    for j in range(ny):
        for i in range(nx):
            mean[j, i] = a[ys[j]:ys[j + 1], xs[i]:xs[i + 1]].reshape(-1, 3).mean(0)
    rough = []
    for p in (False, True):
        lit = (np.zeros((ny, nx), bool) | p) ^ chk
        r = (mean - np.where(lit[..., None], tones[True], tones[False])).mean(-1)
        m1 = ndimage.uniform_filter(r, 5); m2 = ndimage.uniform_filter(r * r, 5)
        rough.append(m2 - m1 * m1)
    guess = rough[1] < rough[0]
    phase_f = np.where(sure, phase, guess)
    phase_f = ndimage.median_filter(phase_f.astype(np.uint8), 5).astype(bool)   # patches are big: a majority vote
    phase_f = np.where(sure, phase, phase_f)
    is_light = phase_f ^ chk
    tone = np.where(is_light[..., None], tones[True], tones[False])
    cx = np.searchsorted(xs, np.arange(w), side='right') - 1; cy = np.searchsorted(ys, np.arange(h), side='right') - 1
    B = tone[cy[:, None], cx[None, :]]
    D = a - B                                                    # what the design adds over (or takes from) the checker
    # whatever is left of the checker alternates square by square: take each square's offset from its neighbours away
    M = np.zeros((ny, nx, 3))
    for jj in range(ny):
        for ii in range(nx):
            M[jj, ii] = D[ys[jj]:ys[jj + 1], xs[ii]:xs[ii + 1]].reshape(-1, 3).mean(0)
    N = np.stack([(ndimage.uniform_filter(M[..., c], 3) * 9 - M[..., c]) / 8 for c in range(3)], -1)
    C = (M - N)[cy[:, None], cx[None, :]]
    D = D - C
    # what is still there: the checker as a +-amplitude pattern, square by square; fitted per patch and taken away
    sign = np.where(((np.add.outer(cy, cx)) % 2)[..., None] == 1, 1.0, -1.0)
    amp = ndimage.gaussian_filter((D * sign).mean(-1), 14)
    D = D - (amp[..., None] * sign)
    D = np.where(near[..., None], ndimage.uniform_filter(D, (3, 3, 1)), D)   # and the 1-px seams
    alpha = np.clip((np.abs(D).max(-1) - 10) / 55, 0, 1)
    alpha = ndimage.gaussian_filter(alpha, 0.7)
    alpha = np.where(alpha < 0.08, 0, alpha)
    Bavg = ndimage.uniform_filter(B, (17, 17, 1))                # the checker's average grey, not its squares
    rgb = Bavg + D / np.maximum(alpha[..., None], 0.08)
    return rgb.clip(0, 255), alpha


def key_checker(path, edge=6):
    rgb, alpha = key_patched(path)
    h, w = alpha.shape
    alpha[h - SPARKLE[1]:h - SPARKLE[3], w - SPARKLE[0]:w - SPARKLE[2]] = 0
    alpha[:edge] = alpha[-edge:] = 0; alpha[:, :edge] = alpha[:, -edge:] = 0          # the picture's own border marks
    lone = ndimage.binary_opening(alpha > 0.15, iterations=2)                          # thin dashed lines along the edges
    alpha *= ndimage.binary_dilation(lone, iterations=3)
    return Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")


def twin(path):
    """The two prints, split down the gap between their rings (the darkest column in the middle third)."""
    keyed = key_glow(Image.open(path), trim=False)
    a = np.asarray(keyed.getchannel("A")).astype(np.float32)
    w = keyed.width
    cut = w // 3 + int(np.argmin(a[:, w // 3: 2 * w // 3].sum(0)))
    save(trim(keyed.crop((0, 0, cut, keyed.height))), "twin_palm_strike_1")
    save(trim(keyed.crop((cut, 0, w, keyed.height))), "twin_palm_strike_2")


def main(paths):
    if len(paths) != 3:
        sys.exit(__doc__)
    twin_png, heaven_png, shadows_png = paths
    twin(twin_png)
    save(key_glow(Image.open(heaven_png)), "heaven_rending_palm")
    save(trim(key_checker(shadows_png)), "thousand_shadow_palm")


if __name__ == "__main__":
    main(sys.argv[1:])
