"""Take footsteps out of SHOAIB's walking or running videos (Gemini / Veo videos carry sound) and give them to the
maps (web/static/sound.js `step`, docs/world.md "Sound").

    python -m scripts.make_step_sound run front.mp4 front_right.mp4 right.mp4 back_right.mp4 back.mp4
    python -m scripts.make_step_sound walk walk_front.mp4 ...
    python -m scripts.make_step_sound run --voice male run_front.mp4 ...

`--voice male` keeps a cultivator's own footsteps apart (Nov 25: the new male's, from his walking and running videos):
they are written to step_<gait>_male_<n>.mp3 and listed under "<gait>#male"; the map plays them for him and keeps
the plain ones for her.

In those videos she walks or runs in place, so the sound is one footfall after another (about two a second when she
runs). The script finds the footfalls (the peaks of the loudness), leaves out the first SKIP seconds (she turns to
face her way) and any footfall with another too close to cut cleanly, and keeps the TAKES most ordinary ones, from as
many of the videos as it can (so no take is an odd scuff). Each is cut from just before the foot lands to LENGTH
seconds on, made one channel, brought to the same level, faded at both ends so it never clicks, and written to
art/fx/sounds/step_<gait>_<n>.mp3. art/fx/sounds/steps.json lists them by gait ("run", "walk"); the map plays one of
a gait's takes on every footfall, never the same twice running, and keeps the step made in code for a gait with none.

Needs ffmpeg, numpy and scipy.
"""
import json
import os
import subprocess
import sys
import wave

import numpy as np
from scipy.signal import find_peaks

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "fx", "sounds")
LIST = os.path.join(OUT, "steps.json")
GAITS = ("run", "walk")
RATE = 44100
SKIP = 2.2            # seconds left out at the start of each video
BEFORE, LENGTH = 0.05, 0.3      # a take: from this long before the footfall's peak, this long in all
APART = 0.34          # a footfall is kept only if its neighbours are at least this far away
TAKES = 6
PEAK = 0.7            # every take's loudest sample (of 1.0)


def sound(video):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-ac", "1", "-ar", str(RATE), "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(float) / 32768


def footfalls(x):
    """[(time of the peak, how loud)] for every footfall in the sound."""
    hop = RATE // 100
    rms = np.array([np.sqrt((x[k:k + hop] ** 2).mean()) for k in range(0, len(x) - hop, hop)])
    peaks, _ = find_peaks(rms, height=np.percentile(rms, 75), distance=12, prominence=rms.max() * 0.08)
    return [(p * hop / RATE, float(rms[p])) for p in peaks]


def takes(videos):
    found = []
    for v, video in enumerate(videos):
        x = sound(video)
        falls = footfalls(x)
        for i, (t, level) in enumerate(falls):
            before = t - falls[i - 1][0] if i else 9
            after = falls[i + 1][0] - t if i + 1 < len(falls) else 9
            if t < SKIP or t + LENGTH > len(x) / RATE or min(before, after) < APART:
                continue
            a = int((t - BEFORE) * RATE)
            found.append({"video": v, "at": t, "level": level, "cut": x[a:a + int(LENGTH * RATE)].copy()})
    if not found:
        sys.exit("No clean footfalls found in those videos.")
    mid = float(np.median([f["level"] for f in found]))
    found.sort(key=lambda f: abs(f["level"] - mid))               # the most ordinary first
    picked, per_video = [], {}
    for f in found:                                                # ... from as many videos as can be
        if per_video.get(f["video"], 0) < -(-TAKES // len(videos)) and len(picked) < TAKES:
            picked.append(f)
            per_video[f["video"]] = per_video.get(f["video"], 0) + 1
    return picked


def shape(cut):
    """The same loudest sample for every take, a short fade in and a longer one out."""
    cut = cut - cut.mean()
    cut = cut / (np.abs(cut).max() or 1) * PEAK
    n_in, n_out = int(0.004 * RATE), int(0.09 * RATE)
    cut[:n_in] *= np.linspace(0, 1, n_in)
    cut[-n_out:] *= np.linspace(1, 0, n_out) ** 2
    return cut


def write(cut, path):
    tmp = path[:-4] + ".wav"
    with wave.open(tmp, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(cut, -1, 1) * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", tmp, "-codec:a", "libmp3lame", "-q:a", "4", path], check=True)
    os.remove(tmp)


def main(gait, videos, voice=None):
    os.makedirs(OUT, exist_ok=True)
    listed = json.load(open(LIST)) if os.path.exists(LIST) else {}
    names = []
    for i, f in enumerate(takes(videos), 1):
        name = f"step_{gait}_{voice + '_' if voice else ''}{i}.mp3"
        write(shape(f["cut"]), os.path.join(OUT, name))
        names.append(name)
        print(f"{name}: video {f['video'] + 1}, the footfall at {f['at']:.2f} s")
    listed[gait + ("#" + voice if voice else "")] = names
    with open(LIST, "w") as fh:
        json.dump(listed, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"{len(names)} {gait} steps listed in {os.path.relpath(LIST, ROOT)}")


if __name__ == "__main__":
    args = sys.argv[1:]
    voice = None
    if "--voice" in args:
        i = args.index("--voice")
        voice = args[i + 1]
        del args[i:i + 2]
    if len(args) < 2 or args[0] not in GAITS:
        sys.exit(__doc__)
    main(args[0], args[1:], voice)
