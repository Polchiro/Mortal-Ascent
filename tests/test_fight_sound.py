"""Fight sounds taken from SHOAIB's animation videos (scripts/make_fight_sound.py, web/static/fight_sound.js)."""
import json

import looks
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
        assert name.split("#")[0].split("@")[0].split(":")[0] in mfs.NAMES, name
        if "#" in name:                                                   # a cultivator's own take
            assert name.split("#")[1] in ("male", "female") and "@" not in name, name
        if "@" in name:
            import beasts
            who = name.split("#")[0].split("@")[1]                        # a body's voice, or a beast's own
            assert who in beasts.BODY_TYPES or who in {beasts.slug(n) for n in beasts.TRAITS}, name
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


def test_the_recorded_footsteps_are_listed_and_the_maps_ask_for_them_by_gait():
    """Her running footsteps, cut from the running videos (scripts/make_step_sound.py, docs/world.md "Sound")."""
    from scripts import make_step_sound as mss
    listed = json.load(open(mss.LIST))
    assert {k.split("#")[0] for k in listed} <= set(mss.GAITS) and len(listed["run"]) == mss.TAKES
    assert len(listed["walk#male"]) == len(listed["run#male"]) == mss.TAKES      # the new male's own (Nov 25)
    for names in listed.values():
        for name in names:
            path = os.path.join(mss.OUT, name)
            assert os.path.exists(path) and 1000 < os.path.getsize(path) < 12000, name      # a short, small take
    sound = open(os.path.join(ROOT, "web", "static", "sound.js")).read()
    town = open(os.path.join(ROOT, "web", "static", "town.js")).read()
    assert "steps.json" in sound and "function recordedStep" in sound
    assert "snd('step', PLACE === 'town' ? 'stone' : 'earth', hero.running ? 'run' : 'walk')" in town
    assert "gait + '#' + window.MASound.voice" in sound and "MASound.voice = SH.voice" in town   # his own steps for him
    assert looks.WALK_SHEETS["male"]["voice"] == "male" and "voice" not in looks.WALK_SHEETS["female"]


@needs_ffmpeg
def test_footfalls_are_found_and_the_cleanest_cut(tmp_path, monkeypatch):
    from scripts import make_step_sound as mss
    monkeypatch.setattr(mss, "OUT", str(tmp_path / "sounds"))
    monkeypatch.setattr(mss, "LIST", str(tmp_path / "sounds" / "steps.json"))
    video = str(tmp_path / "steps.mp4")                       # 8 s: a short knock of noise every half second
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=160x90:r=24:d=8",
                    "-f", "lavfi", "-i", "anoisesrc=d=8:c=pink:a=0.5:seed=7", "-af", "volume='if(lt(mod(t,0.5),0.06),1,0)':eval=frame",
                    "-c:a", "aac", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", video], check=True)
    falls = mss.footfalls(mss.sound(video))
    assert 12 <= len(falls) <= 17 and all(abs((b[0] - a[0]) - 0.5) < 0.06 for a, b in zip(falls, falls[1:]))
    mss.main("walk", [video])
    listed = json.load(open(mss.LIST))
    assert listed == {"walk": [f"step_walk_{i}.mp3" for i in range(1, mss.TAKES + 1)]}
    assert all(os.path.getsize(os.path.join(mss.OUT, n)) > 500 for n in listed["walk"])


def test_the_new_male_has_his_own_recordings_and_the_page_asks_for_them():
    """His swing, Break, block and four technique sounds are from his Nov 24 videos ("#male"); she keeps the plain ones."""
    with open(os.path.join(ROOT, "art", "fx", "sounds", "sounds.json"), encoding="utf-8") as f:
        data = json.load(f)
    for name in ("swing:strike", "swing:break", "gather", "boom", "guardup", "block",
                 "cast:fist", "cast:kick", "cast:palm", "cast:finger"):
        assert name in data and name + "#male" in data, name
        assert data[name][0]["file"] != data[name + "#male"][0]["file"]
    js = open(os.path.join(ROOT, "web", "static", "fight_sound.js"), encoding="utf-8").read()
    assert "name + ':' + narrow + '#' + voice" in js and "name + '#' + voice" in js
    assert "FightSound.voice = fighter.dataset.voice" in open(os.path.join(ROOT, "web", "static", "fight.js"), encoding="utf-8").read()
    assert 'data-voice="{{ F.me.voice }}"' in open(os.path.join(ROOT, "web", "templates", "explore_play.html"), encoding="utf-8").read()


def test_his_three_defences_have_their_own_recordings():
    """The new male's brace, deflect and sidestep sound as in his videos; each is asked for by the move's own name."""
    with open(os.path.join(ROOT, "art", "fx", "sounds", "sounds.json"), encoding="utf-8") as f:
        data = json.load(f)
    for name in ("guardup:brace#male", "guardup:deflect#male", "block:deflect#male", "dodge:step#male"):
        assert name in data, name
    js = open(os.path.join(ROOT, "web", "static", "fight.js"), encoding="utf-8").read()
    assert "[0, 'guardup', 'brace']" in js and "[0, 'guardup', 'deflect']" in js
    assert "fs('block', /^Deflected/.test(text) ? 'deflect' : '')" in js
    assert "stepped = fs('dodge', 'step', 0, {exact: true}) === true" in js       # as he drops, and not again on the word
    fsjs = open(os.path.join(ROOT, "web", "static", "fight_sound.js"), encoding="utf-8").read()
    assert "opts.exact" in fsjs                                        # only its own recording: she gets nothing extra
    for motion in ("brace", "deflect", "sidestep"):                    # and the pictures are the new male's
        him = looks.motion_sheet({"gender": "male"}, motion)
        assert "box" in him and (him.get("pace") == 1.5 or him.get("fps") == 10)
