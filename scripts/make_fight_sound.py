"""Take a fight sound out of one of SHOAIB's animation videos (Gemini / Veo videos carry sound) and give it to the
fights (web/static/fight_sound.js, docs/web.md "Fight sounds").

    python -m scripts.make_fight_sound --listen video.mp4
        Prints where the video is loud (start, end, peak), so the moment of the swing or the hit can be found.

    python -m scripts.make_fight_sound NAME video.mp4 [--from 1.20] [--to 2.05] [--gain 0] [--as KEY]
        Cuts that part of the video's sound, makes it one channel, evens its loudness, fades its ends so it never
        clicks, and writes art/fx/sounds/<KEY>.mp3. Then lists it in art/fx/sounds/sounds.json, which the fight page
        reads: a sound listed there is played instead of the one made in code.

NAME is one of fight_sound.js's sounds: press swing hit hurt block miss dodge guardup gather boom cast lunge roar
heal stun death victory defeat. It can be narrowed with a colon, as the fight asks for it: "swing:break",
"hit:big", "roar:big" (the plain name is used when there is no narrower one). Giving the same NAME again with
another --as KEY adds a second take: the fight picks one of a sound's takes at random, so it doesn't repeat itself.

A beast's voice can be kept to its body type (beasts.BODY_TYPES) with an @: "roar@wolf", "death@wolf", "hit@wolf"
(the yelp of a wolf that is struck). Other beasts keep the sound made in code until they have their own. A technique
is narrowed by its movement (web/technique_fx.py): "cast:fist", "cast:palm", "cast:kick", "cast:finger".

Each take's `lead` is written beside it: how many seconds into the cut its loudest moment is. The fight uses it to
make a technique's recording land on the blow.

--fade S fades the end out over S seconds (for a long sound cut short). --also NAME ... lists the same take under
more names (one roar for several bodies).

--gain (dB) makes one sound louder or quieter than the rest after the evening-out.
"""
import argparse
import json
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "art", "fx", "sounds")
LIST = os.path.join(OUT, "sounds.json")
NAMES = ("press", "swing", "hit", "hurt", "block", "miss", "dodge", "guardup", "gather", "boom", "cast", "lunge",
         "roar", "heal", "stun", "death", "victory", "defeat")
LOUDNESS = -16          # LUFS every sound is evened to, before its own --gain
FADE = 0.012            # seconds faded in and out at the cut


def has_sound(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_name",
                          "-of", "csv=p=0", video], capture_output=True, text=True).stdout
    return bool(out.strip())


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                         capture_output=True, text=True).stdout
    return float(out.strip() or 0)


def loud_parts(video, floor=-32, gap=0.12):
    """[(start, end)] of the video's sound above `floor` dB, parts closer than `gap` seconds joined."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", video, "-vn", "-af",
                          f"silencedetect=noise={floor}dB:d={gap}", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    total = duration(video)
    quiet = [(float(a), float(b)) for a, b in zip(re.findall(r"silence_start: ([\d.]+)", err),
                                                  re.findall(r"silence_end: ([\d.]+)", err))]
    if len(re.findall(r"silence_start: ([\d.]+)", err)) > len(quiet):       # silent to the end
        quiet.append((float(re.findall(r"silence_start: ([\d.]+)", err)[-1]), total))
    parts, at = [], 0.0
    for a, b in quiet:
        if a - at > 0.03:
            parts.append((round(at, 2), round(a, 2)))
        at = b
    if total - at > 0.03:
        parts.append((round(at, 2), round(total, 2)))
    return parts


def peak(video, start, end):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(start), "-to", str(end), "-i", video, "-vn", "-af",
                          "volumedetect", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"max_volume: (-?[\d.]+) dB", err)
    return float(m.group(1)) if m else None


def cut(video, key, start=None, end=None, gain=0.0, fade=None):
    """Write art/fx/sounds/<key>.mp3 from the video's sound between start and end (seconds). Its length."""
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, key + ".mp3")
    length = (end if end is not None else duration(video)) - (start or 0)
    if length <= 0.03:
        raise SystemExit("That part is empty: check --from and --to.")
    chain = [f"loudnorm=I={LOUDNESS}:TP=-1.5:LRA=11", f"volume={gain}dB",
             f"afade=t=in:d={FADE}", f"afade=t=out:st={max(0, length - (fade or FADE * 4)):.3f}:d={fade or FADE * 4}"]
    cmd = ["ffmpeg", "-v", "error", "-y"]
    if start is not None:
        cmd += ["-ss", str(start)]
    if end is not None:
        cmd += ["-to", str(end)]
    cmd += ["-i", video, "-vn", "-ac", "1", "-ar", "44100", "-af", ",".join(chain), "-c:a", "libmp3lame", "-q:a", "4", out]
    subprocess.run(cmd, check=True)
    return round(duration(out), 2)


def listed():
    try:
        with open(LIST, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def lead(path):
    """Seconds from the start of a sound file to its loudest moment (20 ms steps)."""
    import array
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", "8000", "-f", "s16le", "-"],
                         capture_output=True, check=True).stdout
    x = array.array("h", raw[:len(raw) // 2 * 2])
    step, best, at = 160, -1, 0
    for i in range(0, max(1, len(x) - step), step):
        e = sum(v * v for v in x[i:i + step])
        if e > best:
            best, at = e, i
    return round(at / 8000, 2)


def add(name, key):
    """List <key>.mp3 as a take of `name` in sounds.json (once; cut again, its lead is measured again)."""
    data = listed()
    takes = [t for t in data.get(name, []) if (t if isinstance(t, str) else t["file"]) != key + ".mp3"]
    takes.append({"file": key + ".mp3", "lead": lead(os.path.join(OUT, key + ".mp3"))})
    data[name] = takes
    with open(LIST, "w", encoding="utf-8") as f:
        json.dump(dict(sorted(data.items())), f, indent=1)
        f.write("\n")
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("name", help="the sound (e.g. swing, hit:big), or --listen")
    ap.add_argument("video", nargs="?")
    ap.add_argument("--listen", action="store_true", help="only print where the video is loud")
    ap.add_argument("--from", dest="start", type=float)
    ap.add_argument("--to", dest="end", type=float)
    ap.add_argument("--gain", type=float, default=0.0)
    ap.add_argument("--as", dest="key")
    ap.add_argument("--fade", type=float, help="seconds the end fades out over (a long roar cut short: 0.5)")
    ap.add_argument("--also", nargs="*", default=[], help="more names this same take answers (roar@cat roar@ape)")
    a = ap.parse_args()
    video = a.video or a.name
    if not has_sound(video):
        raise SystemExit(f"{video} has no sound in it.")
    if a.listen or a.video is None:
        for s, e in loud_parts(video):
            print(f"  {s:6.2f} - {e:6.2f} s   peak {peak(video, s, e)} dB")
        return
    base = a.name.split("@")[0].split(":")[0]
    if base not in NAMES:
        raise SystemExit(f"'{base}' is not one of the fight's sounds: {', '.join(NAMES)}")
    key = a.key or a.name.replace(":", "_").replace("@", "_")
    length = cut(video, key, a.start, a.end, a.gain, a.fade)
    for name in [a.name] + a.also:
        add(name, key)
    print(f"art/fx/sounds/{key}.mp3 ({length} s) is now the fight's '{a.name}'.")


if __name__ == "__main__":
    main()
