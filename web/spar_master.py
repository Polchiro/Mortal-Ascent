"""The Martial Master's movements for the spar (art/spar/master/: stance, strike, guard, break, bow + sheets.json, cut
from SHOAIB's videos by scripts/make_master_sheets.py; docs/technique.md "On the website").

Each sheet is a grid of frames with each frame's own time (`at`, ms), where its cell sits on his standing figure
(`box`), the moment the blow lands (`hit`), the frame he holds as his tell (`tell`) and the video's own sound
(`sound`). web/static/spar.js plays them; without the sheets it falls back to his still picture."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEEDED = {"stance", "strike", "guard", "break"}
STILL = "/art/spar/master/still.webp"
_cache = []


def sheets():
    """{aspect, sheets: {name: sheet}} or None."""
    if not _cache:
        try:
            with open(os.path.join(ROOT, "art", "spar", "master", "sheets.json")) as fh:
                data = json.load(fh)
            _cache.append(data if NEEDED <= set(data["sheets"]) else None)
        except (OSError, ValueError, KeyError):
            _cache.append(None)
    return _cache[0]


def still():
    """His standing picture (the stance video's first frame), or the town's painting if it isn't there."""
    return STILL if os.path.exists(os.path.join(ROOT, "art", "spar", "master", "still.webp")) else "/art/portraits/town/master.webp"
