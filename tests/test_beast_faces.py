"""The beasts' faces in the foe banner's ring (scripts/make_beast_faces.py, docs/web.md "Fights")."""
import json
import os

from PIL import Image

from scripts import make_beast_faces as mbf
from web.explore_play import beast_face

BEASTS = mbf.BEASTS


def test_every_beast_has_its_face():
    heads = json.load(open(os.path.join(BEASTS, "heads.json")))
    slugs = [f[:-4] for f in os.listdir(BEASTS) if f.endswith(".png") and f[:-4] in heads]
    assert len(slugs) >= 60
    for slug in slugs:
        path = os.path.join(BEASTS, "faces", slug + ".webp")
        assert os.path.exists(path), slug
        im = Image.open(path)
        assert im.size == (mbf.SIZE, mbf.SIZE), slug
        a = im.convert("RGBA").getchannel("A")
        assert a.getpixel((mbf.SIZE // 2, mbf.SIZE // 2)) > 0 or slug in mbf.FIX, slug      # something in the middle


def test_the_face_box_sits_behind_a_left_facing_mouth():
    im = Image.open(os.path.join(BEASTS, "mountain_tiger.png"))
    mouth = json.load(open(os.path.join(BEASTS, "heads.json")))["mountain_tiger"]
    l, t, r, b = mbf.face_box(im, mouth)
    mx = mouth[0] * im.width
    assert l <= mx <= r and (l + r) / 2 > mx                                   # the head reaches back from the mouth
    assert r - l == b - t


def test_the_fight_page_uses_the_face():
    assert beast_face("mountain_tiger") == "/art/beasts/faces/mountain_tiger.webp"
    assert beast_face("no_such_beast") is None and beast_face(None) is None
    assert 'class="eface" src="{{ F.enemy.face or F.enemy.art }}"' in open("web/templates/explore_play.html").read()
