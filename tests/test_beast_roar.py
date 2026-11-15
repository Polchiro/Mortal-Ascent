"""The beast roar (web/static/fight.js `roar`, scripts/make_roar_fx.py) is one shared effect: every beast picture has
its mouth on file, each tier has its wave, and it plays only as a beast winds up a big attack or roars itself."""
import json
import os

import beasts
from web import explore_play

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_beast_has_its_mouth_and_every_tier_its_wave():
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    for name in beasts.TRAITS:
        x, y, h = heads[beasts.slug(name)]
        assert 0 <= x <= 1 and 0 <= y <= 1 and 0 < h <= 1, name
    for wave in ("ring", "double", "burst"):
        assert os.path.exists(os.path.join(ROOT, "art", "fx", f"roar_{wave}.webp"))


def test_a_beast_roars_its_tier_and_colour():
    e = {"slug": "frost_wolf", "element": "Frost", "tier": "elite"}
    r = explore_play.beast_roar(e)
    assert r["head"] and r["wave"] == "double" and r["color"].startswith("#")
    assert explore_play.beast_roar({"slug": "someday_new", "tier": "normal"})["head"] is None   # a default on the page


def test_the_page_reads_the_roar_from_the_log_and_no_longer_roars_on_its_own():
    class F:
        name = "Shoaib"
        atk_t = def_t = None
    ev = explore_play.events([("roar", "Boar — Roar on Shoaib −42 (Shaken) (Stunned)")], F)
    assert ev == [{"who": "enemy", "act": "roar", "dmg": 42, "guard": False, "final": False, "stun": True,
                   "status": ["Shaken"]}]
    ev = explore_play.events([("roar", "Tiger — Final Roar on Ally −90 (Exposed), Shoaib −21 (guarded)")], F)
    assert ev[0]["final"] and ev[0]["guard"] and ev[0]["dmg"] == 21 and ev[0]["status"] == []
    assert not hasattr(explore_play, "roared")              # the windup's visual-only roar is gone


def test_every_quadruped_roars_as_itself_with_the_shared_movement():
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    move = beasts.ROAR_ANIMATIONS["quadruped"]
    assert len(move["ms"]) == len(move["keys"]) - 1 and 0 < move["burst"] <= move["hold"] < len(move["ms"])
    assert move["keys"][0] == move["keys"][-1] == (0.0, 0.0, 0.0)          # from standing, back to standing
    assert move["keys"][move["burst"]][2] > 0 > move["keys"][1][2]           # head down in the dip, up as it roars
    pics = set()
    for name in beasts.QUADRUPEDS:
        assert name in beasts.TRAITS and beasts.roar_category(name) == "quadruped"
        slug = beasts.slug(name)
        path = os.path.join(ROOT, "art", "beasts", slug + ".png")
        assert os.path.exists(path), name
        pics.add(open(path, "rb").read())                                    # its own picture, not a shared one
        assert slug in heads
        r = explore_play.beast_roar({"name": name, "slug": slug, "element": beasts.element_of(name), "tier": "normal"})
        assert r["motion"]["keys"][move["burst"]] == list(move["keys"][move["burst"]]) and r["head"] == heads[slug][:2]
    assert len(pics) == len(beasts.QUADRUPEDS) == 28


def test_other_beasts_keep_the_plain_roar():
    for name in ("Venom Scorpion", "Primordial Dragon Turtle"):
        assert beasts.roar_category(name) is None
        assert explore_play.beast_roar({"name": name, "slug": beasts.slug(name), "tier": "normal"})["motion"] is None


def test_the_redesigned_quadrupeds_face_left_and_stand_on_their_feet():
    from PIL import Image
    import numpy as np
    for name in beasts.QUADRUPEDS:
        a = np.asarray(Image.open(os.path.join(ROOT, "art", "beasts", beasts.slug(name) + ".png")).convert("RGBA"))[..., 3]
        h, w = a.shape
        assert max(h, w) <= 900, name
        assert a[-3:].max() > 128 and a[:, :3].max() > 0, name                 # trimmed: paws on the bottom edge
        x, y = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))[beasts.slug(name)][:2]
        assert x < 0.3, name                                                   # the mouth is at the left: it faces left


def test_an_open_mouthed_roar_picture_is_shown_only_when_it_exists():
    name = "Wild Boar"
    slug = beasts.slug(name)
    r = explore_play.beast_roar({"name": name, "slug": slug, "element": "Earth", "tier": "normal"})
    path = os.path.join(ROOT, "art", "beasts", "roar", slug + ".png")
    assert (r["art"] == f"/art/beasts/roar/{slug}.png") == os.path.exists(path)
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    for f in os.listdir(os.path.join(ROOT, "art", "beasts", "roar")) if os.path.isdir(os.path.join(ROOT, "art", "beasts", "roar")) else []:
        assert f[:-4] + "@roar" in heads, f                  # every roar picture has its open mouth on file
    assert explore_play.beast_roar({"name": "Venom Scorpion", "slug": "venom_scorpion", "tier": "normal"})["art"] is None


def test_every_quadruped_but_the_posed_tiger_has_its_open_mouthed_roar():
    from PIL import Image
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    for name in beasts.QUADRUPEDS:
        slug = beasts.slug(name)
        if name == "Mountain Tiger":
            continue                                          # roars from its own cut-out pose
        roar = os.path.join(ROOT, "art", "beasts", "roar", slug + ".png")
        assert os.path.exists(roar) and slug + "@roar" in heads, name
        assert Image.open(roar).size == Image.open(os.path.join(ROOT, "art", "beasts", slug + ".png")).size, name


def test_the_redesigned_flying_beasts_face_left_and_stand_on_their_feet():
    from PIL import Image
    import numpy as np
    import scripts.make_quadruped_art as art
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    for slug in art.FLYING:
        a = np.asarray(Image.open(os.path.join(ROOT, "art", "beasts", slug + ".png")).convert("RGBA"))[..., 3]
        assert max(a.shape) <= 900 and a[-3:].max() > 128, slug                # trimmed: feet on the bottom edge
        assert heads[slug][0] < 0.35, slug                                     # its beak at the left: it faces left
    assert "Cave Bat Swarm" not in beasts.TRAITS and "Wind-Feather Falcon" in beasts.TRAITS   # replaced


def test_every_flying_beast_screeches_as_itself_with_its_open_beak():
    from PIL import Image
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    move = beasts.ROAR_ANIMATIONS["flying"]
    assert move["style"] == "screech" and len(move["ms"]) == len(move["keys"]) - 1
    assert move["keys"][0] == move["keys"][-1] == (0.0, 0.0, 0.0)
    assert move["keys"][1][1] < 0 and move["keys"][1][2] > 0 > move["keys"][move["burst"]][2]   # rears up, then snaps forward
    for name in beasts.FLYING:
        slug = beasts.slug(name)
        assert beasts.roar_category(name) == "flying" and name in beasts.TRAITS and beasts.TRAITS[name][1] == "bird"
        r = explore_play.beast_roar({"name": name, "slug": slug, "element": beasts.element_of(name), "tier": "normal"})
        assert r["motion"]["style"] == "screech" and r["art"] == f"/art/beasts/roar/{slug}.png" and r["head_open"]
        roar = os.path.join(ROOT, "art", "beasts", "roar", slug + ".png")
        assert Image.open(roar).size == Image.open(os.path.join(ROOT, "art", "beasts", slug + ".png")).size
    birds = {n for n, (_, body) in beasts.TRAITS.items() if body == "bird"}
    assert birds == set(beasts.FLYING)                                      # every bird screeches


def test_the_redesigned_serpents_have_their_standing_and_open_mouthed_pictures():
    from PIL import Image
    import scripts.make_quadruped_art as art
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    serpents = {beasts.slug(n) for n, (_, body) in beasts.TRAITS.items() if body == "serpent"}
    assert serpents == set(art.SERPENTS)
    for slug in art.SERPENTS:
        still = Image.open(os.path.join(ROOT, "art", "beasts", slug + ".png"))
        roar = Image.open(os.path.join(ROOT, "art", "beasts", "roar", slug + ".png"))
        assert still.size == roar.size and max(still.size) <= 900, slug
        assert heads[slug][0] < 0.3 and slug + "@roar" in heads, slug             # faces left; open mouth on file


def test_every_serpent_hisses_with_the_serpent_movement_and_its_open_mouthed_picture():
    move = beasts.ROAR_ANIMATIONS["serpent"]
    assert move["style"] == "hiss" and len(move["ms"]) == len(move["keys"]) - 1
    for name in beasts.SERPENTS:
        assert beasts.roar_category(name) == "serpent"
        slug = beasts.slug(name)
        r = explore_play.beast_roar({"name": name, "slug": slug, "tier": "normal"})
        assert r["motion"]["style"] == "hiss" and r["art"] == f"/art/beasts/roar/{slug}.png" and r["head_open"]


def test_the_redesigned_amphibians_have_their_standing_and_open_mouthed_pictures():
    from PIL import Image
    import scripts.make_quadruped_art as art
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    for slug in art.AMPHIBIANS:
        still = Image.open(os.path.join(ROOT, "art", "beasts", slug + ".png"))
        roar = Image.open(os.path.join(ROOT, "art", "beasts", "roar", slug + ".png"))
        assert still.size == roar.size and max(still.size) <= 900, slug
        assert heads[slug][0] < 0.3 and slug + "@roar" in heads, slug


def test_every_amphibian_roars_with_the_amphibian_movement_and_its_open_mouthed_picture():
    move = beasts.ROAR_ANIMATIONS["amphibian"]
    assert move["style"] == "quake" and len(move["ms"]) == len(move["keys"]) - 1
    for name in beasts.AMPHIBIANS:
        assert beasts.roar_category(name) == "amphibian"
        slug = beasts.slug(name)
        r = explore_play.beast_roar({"name": name, "slug": slug, "tier": "normal"})
        assert r["motion"]["style"] == "quake" and r["art"] == f"/art/beasts/roar/{slug}.png" and r["head_open"]


def test_the_redesigned_dragons_have_their_standing_and_open_mouthed_pictures():
    from PIL import Image
    import scripts.make_quadruped_art as art
    heads = json.load(open(os.path.join(ROOT, "art", "beasts", "heads.json")))
    for slug in art.DRAGONS:
        still = Image.open(os.path.join(ROOT, "art", "beasts", slug + ".png"))
        roar = Image.open(os.path.join(ROOT, "art", "beasts", "roar", slug + ".png"))
        assert still.size == roar.size and max(still.size) <= 900, slug
        assert heads[slug][0] < 0.3 and slug + "@roar" in heads, slug


def test_both_dragons_roar_with_the_dragon_movement_and_their_open_mouthed_pictures():
    move = beasts.ROAR_ANIMATIONS["dragon"]
    assert move["style"] == "storm" and len(move["ms"]) == len(move["keys"]) - 1
    for name in beasts.DRAGONS:
        assert beasts.roar_category(name) == "dragon"
        slug = beasts.slug(name)
        r = explore_play.beast_roar({"name": name, "slug": slug, "tier": "normal"})
        assert r["motion"]["style"] == "storm" and r["art"] == f"/art/beasts/roar/{slug}.png" and r["head_open"]


def test_every_primate_roars_with_the_primate_movement_and_its_open_mouthed_picture():
    from PIL import Image
    import scripts.make_quadruped_art as art
    move = beasts.ROAR_ANIMATIONS["primate"]
    assert move["style"] == "pound" and len(move["ms"]) == len(move["keys"]) - 1
    assert "Ancient Golden Ape" not in beasts.QUADRUPEDS
    for name in beasts.PRIMATES:
        assert beasts.roar_category(name) == "primate"
        slug = beasts.slug(name)
        assert slug in art.PRIMATES
        still = Image.open(os.path.join(ROOT, "art", "beasts", slug + ".png"))
        roar = Image.open(os.path.join(ROOT, "art", "beasts", "roar", slug + ".png"))
        assert still.size == roar.size and max(still.size) <= 900, slug
        r = explore_play.beast_roar({"name": name, "slug": slug, "tier": "normal"})
        assert r["motion"]["style"] == "pound" and r["art"] == f"/art/beasts/roar/{slug}.png" and r["head_open"]
