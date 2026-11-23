"""Fight sounds taken from SHOAIB's animation videos (scripts/make_fight_sound.py, web/static/fight_sound.js)."""
import json
import os
import shutil
import subprocess

import pytest

from scripts import make_fight_sound as mfs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
needs_ffmpeg = pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="needs ffmpeg")


def _video(path, sound=True):
    """A 3 s test video: silent, but for noise from 1.0 to 1.5 s."""
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=24:d=3"]
    if sound:
        cmd += ["-f", "lavfi", "-i", "anoisesrc=d=3:c=pink:a=0.5", "-af", "volume='if(between(t,1,1.5),1,0)':eval=frame",
                "-c:a", "aac", "-shortest"]
    subprocess.run(cmd + ["-c:v", "libx264", "-pix_fmt", "yuv420p", path], check=True)


def test_the_list_the_page_reads_is_there_and_names_real_sounds():
    with open(os.path.join(ROOT, "art", "fx", "sounds", "sounds.json"), encoding="utf-8") as f:
        data = json.load(f)
    for name, takes in data.items():
        assert name.split("@")[0].split(":")[0] in mfs.NAMES, name
        if "@" in name:
            import beasts
            assert name.split("@")[1] in beasts.BODY_TYPES, name
        for t in takes:
            path = os.path.join(ROOT, "art", "fx", "sounds", t["file"])
            assert os.path.exists(path) and 2_000 < os.path.getsize(path) < 120_000, t   # there, and small
            assert 0 <= t["lead"] < 4
    js = open(os.path.join(ROOT, "web", "static", "fight_sound.js"), encoding="utf-8").read()
    assert "/art/fx/sounds/" in js and "sounds.json" in js
    for name in mfs.NAMES:                                                # the script and the page agree on the names
        assert f"    {name}: function (t" in js, name


@needs_ffmpeg
def test_a_sound_is_found_cut_and_listed(tmp_path, monkeypatch):
    monkeypatch.setattr(mfs, "OUT", str(tmp_path / "sounds"))
    monkeypatch.setattr(mfs, "LIST", str(tmp_path / "sounds" / "sounds.json"))
    video = str(tmp_path / "v.mp4")
    _video(video)
    assert mfs.has_sound(video)
    parts = mfs.loud_parts(video)
    assert len(parts) == 1 and abs(parts[0][0] - 1.0) < 0.15 and abs(parts[0][1] - 1.5) < 0.15   # where it is loud
    length = mfs.cut(video, "hit_big", 1.0, 1.5)
    assert 0.4 < length < 0.7 and os.path.getsize(tmp_path / "sounds" / "hit_big.mp3") > 1000
    mfs.add("hit:big", "hit_big")
    mfs.cut(video, "hit_big2", 1.1, 1.4)
    data = mfs.add("hit:big", "hit_big2")
    mfs.add("hit:big", "hit_big2")                                        # twice: listed once
    assert data == mfs.listed() and [t["file"] for t in data["hit:big"]] == ["hit_big.mp3", "hit_big2.mp3"]
    assert all(0 <= t["lead"] < 0.5 for t in data["hit:big"])


@needs_ffmpeg
def test_a_video_without_sound_says_so(tmp_path):
    video = str(tmp_path / "quiet.mp4")
    _video(video, sound=False)
    assert not mfs.has_sound(video)
