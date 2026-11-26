"""Ambience for the two fight places whose videos came without sound (Bamboo Forest, Red Cliff Gorge), made from
the other places' sound plus a little made in code, then looped like the rest (scripts/make_background_loop.py):

- Bamboo Forest: the Misty Pine Valley's birds and drips, the Northern Sea's wind made airy (only its middle
  frequencies), leaves rustling in gusts, and now and then hollow bamboo knocking together.
- Red Cliff Gorge: a warm low desert wind that swells and falls, dry grass hissing with the gusts, the Northern Sea's
  wind under it (only its lows) and one far hawk's cry with an echo off the cliffs.

    python -m scripts.make_ambience misty_pine_valley_video.mp4 northern_sea_wild_video.mp4

Writes art/scenes/battle_bamboo_forest.m4a and battle_red_cliff_gorge.m4a. Needs ffmpeg, numpy and scipy.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
import scipy.io.wavfile as w
from scipy import signal

from scripts.make_background_loop import loop_sound
R = 44100; T = 10.0; N = int(R * T)
rng = np.random.default_rng(7)
def load(video, tmp):
    wav = os.path.join(tmp, os.path.basename(video) + ".wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", str(R), wav], check=True)
    r, d = w.read(wav)
    d = d.astype(float) / 32768
    return np.pad(d, (0, max(0, N - len(d))))[:N]
def band(x, lo, hi, order=4):
    sos = signal.butter(order, [lo, hi], 'band', fs=R, output='sos'); return signal.sosfilt(sos, x)
def lp(x, f):
    return signal.sosfilt(signal.butter(4, f, 'low', fs=R, output='sos'), x)
def smooth_noise(rate, n=N):                      # a slow random curve 0..1 (rate: changes per second)
    k = int(T * rate) + 3
    pts = rng.random(k)
    return np.clip(np.interp(np.linspace(0, k - 3, n), np.arange(k), pts), 0, 1)
def save(tmp, scene, x):
    wav = os.path.join(tmp, scene + ".wav")
    w.write(wav, R, (np.clip(x, -1, 1) * 32767).astype(np.int16))
    loop_sound(scene, wav, T)


def norm(x, rms):
    return x / (np.sqrt((x ** 2).mean()) + 1e-9) * rms


def main(misty_video, north_video):
    with tempfile.TemporaryDirectory() as tmp:
        misty, north = load(misty_video, tmp), load(north_video, tmp)

        # Bamboo forest: the valley's birds and drips, the north's wind made airy, leaves rustling, now and then bamboo knocking
        wind = norm(band(north, 500, 3500), 0.012) * (0.6 + 0.4 * smooth_noise(0.4))
        rustle_env = smooth_noise(1.5) ** 2.5
        rustle = norm(band(rng.standard_normal(N), 2500, 8000), 0.006) * (0.3 + 1.7 * rustle_env)
        knock = np.zeros(N)
        for at, f in ((1.7, 640), (1.82, 720), (5.4, 560), (7.9, 690), (8.02, 610)):
            i = int(at * R); L = int(0.25 * R); tt = np.arange(L) / R
            k = (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 2.7 * tt)) * np.exp(-tt * 28)
            knock[i:i + L] += k[: N - i] * 0.05
        bamboo = norm(misty, 0.010) + wind + rustle + band(knock, 300, 4000)
        save(tmp, "battle_bamboo_forest", bamboo)

        # Red cliff gorge: warm low desert wind that swells and falls, dry grass hissing with the gusts, one far hawk
        gust = 0.35 + 0.65 * smooth_noise(0.35)
        desert = norm(band(rng.standard_normal(N), 120, 1100, 2), 0.02) * gust
        desert += norm(lp(north, 1200), 0.008)
        grass = norm(band(rng.standard_normal(N), 3000, 7500), 0.0045) * gust ** 2
        hawk = np.zeros(N)
        at, L = 6.2, int(0.9 * R); tt = np.arange(L) / R
        f = 2900 - 900 * (tt / tt[-1]) + 60 * np.sin(2 * np.pi * 7 * tt)
        ph = 2 * np.pi * np.cumsum(f) / R
        env = np.sin(np.pi * tt / tt[-1]) ** 1.5 * np.exp(-tt * 1.5)
        cry = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * band(rng.standard_normal(L), 2000, 6000)) * env
        i = int(at * R); hawk[i:i + L] += cry * 0.012
        echo = np.zeros(N); d = int(0.32 * R); echo[d:] = hawk[:-d] * 0.35
        gorge = desert + grass + lp(hawk + echo, 5000)
        save(tmp, "battle_red_cliff_gorge", gorge)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
