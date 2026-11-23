"""Take footsteps out of SHOAIB's walking videos (Gemini / Veo videos carry sound) for the walkable places
(web/static/sound.js, docs/world.md "Sound").

    python -m scripts.make_step_sound WHO video.mp4 [video.mp4 ...] [--takes 6]

WHO is the look whose steps they are ("female", "male": looks.WALK_SHEETS[...]["steps"]). The script finds every
footstep in the videos' sound (a short, loud hit well above the quiet around it), keeps the cleanest `--takes` of
them spread over the videos, cuts each from just before its hit to the end of its tail, evens their loudness, fades
their ends so they never click, and writes art/fx/sounds/step_<WHO>_<n>.mp3. It lists them in
art/fx/sounds/steps.json under WHO (replacing any earlier ones); sound.js plays one of them at random for each
step, instead of the step it makes in code.
"""
import argparse
import json
import os
import subprocess

import numpy as np

from scripts.make_fight_sound import OUT, has_sound

LIST = os.path.join(OUT, "steps.json")    # {look: [{"file": ..., "lead": ...}]}, apart from the fights' sounds.json

RATE = 44100
HOP = RATE // 100                       # the loudness is looked at every 10 ms
BEFORE, AFTER = 0.04, 0.26              # seconds kept before and after a step's loudest moment
LOUD = 18                               # dB above the quiet of its video that a step must reach
GAP = 0.35                              # seconds between two steps at least
PEAK = -3.0                             # dBFS every step is evened to (its loudest sample)
FADE = 0.012


def sound(video):
    data = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vn", "-ac", "1", "-ar", str(RATE), "-f", "s16le",
                           "-"], capture_output=True, check=True).stdout
    return np.frombuffer(data, np.int16).astype(np.float64) / 32768


def steps(x):
    """[(second, how far above the quiet in dB, how quiet just around it in dB)] for every footstep in `x`."""
    n = len(x) // HOP
    db = 20 * np.log10(np.sqrt((x[:n * HOP].reshape(n, HOP) ** 2).mean(1)) + 1e-9)
    quiet = np.percentile(db, 20)
    found = []
    for k in range(3, n - 3):
        if db[k] == db[k - 3:k + 4].max() and db[k] > quiet + LOUD:
            if found and k - found[-1] < GAP * 100:
                continue
            found.append(k)
    out = []
    for k in found:
        lo, hi = max(0, k - 30), min(n, k + 30)                          # 0.3 s either side, the step itself left out
        around = np.concatenate([db[lo:max(lo, k - 5)], db[min(hi, k + 27):hi]])
        out.append((k / 100, db[k] - quiet, float(np.median(around)) if len(around) else quiet))
    return out


def cut(x, at):
    a, b = int((at - BEFORE) * RATE), int((at + AFTER) * RATE)
    if a < 0 or b > len(x):
        return None
    y = x[a:b].copy()
    y -= y.mean()
    y *= 10 ** (PEAK / 20) / max(1e-6, np.abs(y).max())
    f = int(FADE * RATE)
    ramp = np.linspace(0, 1, f)
    y[:f] *= ramp
    y[-f:] *= ramp[::-1]
    return y


def write(y, path):
    pcm = (np.clip(y, -1, 1) * 32767).astype("<i2").tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(RATE), "-ac", "1", "-i", "-",
                    "-af", "highpass=f=70", "-c:a", "libmp3lame", "-b:a", "64k", path], input=pcm, check=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("who")
    ap.add_argument("videos", nargs="+")
    ap.add_argument("--takes", type=int, default=6)
    args = ap.parse_args(argv)
    candidates = []                                     # (cleanness, video number, second, sound)
    for v, video in enumerate(args.videos):
        if not has_sound(video):
            print(f"{video}: no sound")
            continue
        x = sound(video)
        for at, above, around in steps(x):
            y = cut(x, at)
            if y is not None:
                candidates.append((above + (-around) * 0.25, v, at, y))
    if not candidates:
        raise SystemExit("no footsteps found")
    candidates.sort(key=lambda c: -c[0])
    picked, per = [], {}
    limit = -(-args.takes // len(args.videos))         # spread over the videos
    for c in candidates:
        if per.get(c[1], 0) < limit:
            picked.append(c)
            per[c[1]] = per.get(c[1], 0) + 1
        if len(picked) == args.takes:
            break
    os.makedirs(OUT, exist_ok=True)
    for f in os.listdir(OUT):
        if f.startswith(f"step_{args.who}_") and f.endswith(".mp3"):
            os.remove(os.path.join(OUT, f))
    listed = []
    for n, (_, v, at, y) in enumerate(sorted(picked, key=lambda c: (c[1], c[2])), 1):
        name = f"step_{args.who}_{n}.mp3"
        write(y, os.path.join(OUT, name))
        listed.append({"file": name, "lead": BEFORE})
        print(f"{name}: {args.videos[v]} at {at:.2f} s")
    table = {}
    if os.path.exists(LIST):
        with open(LIST) as f:
            table = json.load(f)
    table[args.who] = listed
    with open(LIST, "w") as f:
        json.dump(dict(sorted(table.items())), f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
