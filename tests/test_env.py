"""Environment pieces (web/env.py, docs/environment.md): the cut pictures, their catalog, and Moon Forest's pieces."""
import math
import os

from PIL import Image

from web import env, hunt_map, town

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_asset_is_cut_and_in_the_catalog():
    cat = env.catalog()
    for name, a in env.ASSETS.items():
        assert ("h" in a) != ("w" in a), name                              # drawn by its height or its width
        im = Image.open(os.path.join(ROOT, env.path(name)))
        c = cat[name]
        assert im.mode == "RGBA" and (im.width, im.height) == (c["w"], c["h"]) and max(im.size) <= 640, name
        fx, fy = c["foot"]
        assert 0 < fx < c["w"] and c["h"] * 0.4 < fy <= c["h"], name       # it stands near its bottom
        alpha = im.getchannel("A")
        for corner in ((0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)):
            assert alpha.getpixel(corner) == 0, (name, corner)             # the backdrop is gone
        assert alpha.getextrema()[1] == 255                                 # and the object is there


def test_every_placed_piece_is_a_known_asset_on_the_ground():
    for key, placed in env.PLACED.items():
        m = hunt_map.plan(key)
        for name, x, y, s, flip in placed:
            assert name in env.ASSETS and 0.6 <= s <= 1.4 and isinstance(flip, bool)
            assert m["edge"] - 0.5 < x < hunt_map.SIZE - m["edge"] + 0.5, (name, x, y)
            assert m["edge"] - 0.5 < y < hunt_map.SIZE - m["edge"] + 0.5, (name, x, y)


def test_one_picture_per_asset_however_often_it_is_placed():
    ps = env.pieces("moon_forest")
    assert len(ps) == len(env.PLACED["moon_forest"])
    assert len({p["src"] for p in ps}) == len(env.ASSETS)                   # all ten used, each file once


def test_the_server_and_the_page_block_the_same_rocks_and_logs():
    m = hunt_map.plan("moon_forest")
    for c in env.blocks("moon_forest"):
        assert c in m["blocked"]
        assert not hunt_map.walkable(c[0], c[1], m)
    assert [list(c) for c in m["blocked"]] == hunt_map.page_data("moon_forest")["blocked"]
    # a log blocks along its length, a plant not at all
    log = next(p for p in env.PLACED["moon_forest"] if p[0] == "log_long_01")
    assert not hunt_map.walkable(log[1], log[2] + 1.5, m) and not hunt_map.walkable(log[1], log[2] - 1.5, m)
    fern = next(p for p in env.PLACED["moon_forest"] if p[0] == "fern_01")
    assert hunt_map.walkable(fern[1], fern[2], m)


def test_nothing_walls_off_the_forest():
    m = hunt_map.plan("moon_forest")
    step = 0.25
    cells = {(i, j) for i in range(int(hunt_map.SIZE / step)) for j in range(int(hunt_map.SIZE / step))
             if hunt_map.walkable(i * step, j * step, m)}
    sx, sy = hunt_map.start(m)
    todo = [(round(sx / step), round(sy / step))]
    seen = set(todo)
    while todo:
        i, j = todo.pop()
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (i + di, j + dj)
            if n in cells and n not in seen:
                seen.add(n)
                todo.append(n)
    assert len(seen) / len(cells) > 0.98                                    # every bit of open ground is reachable
    assert hunt_map.walkable(12, 20, m)                                     # the stepping stones still cross
    for c in env.blocks("moon_forest"):                                     # and nothing stands on the way in
        assert math.dist(c[:2], hunt_map.start(m)) > c[2] + 1.5


def test_pieces_are_drawn_where_they_stand():
    for p in env.pieces("moon_forest"):
        x, y = p["at"]
        sx, sy = (x - y) * 64, (x + y) * 32
        r = p["rect"]
        assert r[0] - 1 <= sx <= r[0] + r[2] + 1 and r[1] < sy <= r[1] + r[3] + 1    # its foot is inside its picture
        assert "fp" in p or "shadow" in p


def test_spirit_mushrooms_glow_and_the_town_is_untouched():
    glows = env.lights("moon_forest")
    assert len(glows) == sum(1 for p in env.PLACED["moon_forest"] if p[0] == "spirit_mushroom_01")
    assert all(g[2] == env.ASSETS["spirit_mushroom_01"]["glow"] for g in glows)
    lights = hunt_map.page_data("moon_forest")["lights"]
    assert [list(g) for g in glows] == lights[-len(glows):]
    assert all("/art/env/" not in p["src"] for p in town.placed())          # the town keeps its own pieces
    assert hunt_map.page_data("crimson_gorge")["pieces"] == []              # other grounds: none yet


def test_the_pictures_are_served(tmp_path, monkeypatch):
    import pytest
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    from web import app as web_app
    app = web_app.create_app(web_app.Settings("cid", "sec", db_path=str(tmp_path / "x.db"), session_secret="s"))
    c = TestClient(app)
    for name in env.ASSETS:
        assert c.get("/" + env.path(name)).status_code == 200


# ── the open lands, dressed in groups (web/env.py GROUPS / DRESSED, web/land.py) ────────────────────────────────
import pytest  # noqa: E402

from web import land  # noqa: E402


def test_a_lands_groups_are_made_of_known_pieces_and_stand_on_its_ground():
    cat = env.catalog()
    for key, groups in env.DRESSED.items():
        assert key in land.LANDS
        n, e = land.size(key), land.LANDS[key]["edge"]
        for group, x, y, mirror, scale in groups:
            assert group in env.GROUPS and 0.6 <= scale <= 1.4
        for name, x, y, s, flip in env.LAND_PLACED[key]:
            assert name in env.ASSETS and name in cat
            assert e < x < n - e and e < y < n - e, (key, name, x, y)       # on the ground you can walk
    for group, items in env.GROUPS.items():                                 # a group is small: an arrangement, not a field
        assert all(math.hypot(dx, dy) <= 2.2 for _, dx, dy, _, _ in items), group


def test_mirroring_a_group_mirrors_it_on_screen():
    env.DRESSED["_t"] = [("boulders", 10, 10, False, 1.0), ("boulders", 10, 10, True, 1.0)]
    try:
        d = env.dressed("_t")
    finally:
        del env.DRESSED["_t"]
    half = len(d) // 2
    for a, b in zip(d[:half], d[half:]):
        assert a[0] == b[0] and a[4] != b[4]                                 # the same piece, flipped
        assert (a[1] - 10, a[2] - 10) == pytest.approx((b[2] - 10, b[1] - 10))   # its offset's axes swapped


def test_nothing_blocks_a_lands_roads_gates_or_hidden_spots():
    for key in env.DRESSED:
        cfg = land.LANDS[key]
        for bx, by, r in land.blocks(key):
            assert land.off_path(key, bx, by, room=r + 0.3), (key, bx, by)   # clear of every road and path
            for g in cfg["gates"].values():
                assert math.dist((bx, by), g["at"]) > 4
            for s in cfg.get("secret", []):
                assert math.dist((bx, by), s) > r + 1.0                      # you can stand on a hidden spot


def test_a_lands_pieces_are_your_size_and_block_for_the_server_and_the_page_alike():
    from web import overworld
    key = "forest_edge"
    d = overworld.wild_data({"src": "x", "cell": 256, "feet": [128, 232], "stand": [0] * 8}, key, (40.0, 6.5))
    assert [tuple(c) for c in d["blocked"]] == land.blocks(key) and d["blocked"]     # the same circles
    bx, by, r = land.blocks(key)[0]
    assert not land.walkable(key, bx, by) and land.walkable(key, bx + r + 0.2, by)
    assert len(d["pieces"]) == len(env.LAND_PLACED[key]) > 300
    boulder = next(p for p in d["pieces"] if p["src"].endswith("boulder_01.webp"))
    scale = next(s for n, _, _, s, _ in env.LAND_PLACED[key] if n == "boulder_01")
    assert boulder["rect"][3] == pytest.approx(124 * scale / land.SCALE, abs=0.2)    # as big beside you as on the old map
    assert boulder["env"] and boulder["pass"] and d["tone"] and d["lights"]          # tinted to the night; mushrooms glow
    half = land.size(key) * 64
    assert all(0 < p["rect"][0] < 2 * half for p in d["pieces"])                     # on the land's own picture


def test_every_corner_of_a_dressed_land_can_still_be_walked_to():
    key = "forest_edge"
    cfg, n, step = land.LANDS[key], land.size(key), 0.5
    cells = int(n / step)
    ok = [[land.walkable(key, i * step, j * step) for j in range(cells)] for i in range(cells)]
    sx, sy = cfg["start"]
    seen, todo = {(int(sx / step), int(sy / step))}, [(int(sx / step), int(sy / step))]
    while todo:
        i, j = todo.pop()
        for a, b in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
            if 0 <= a < cells and 0 <= b < cells and ok[a][b] and (a, b) not in seen:
                seen.add((a, b))
                todo.append((a, b))
    free = sum(v for row in ok for v in row)
    assert len(seen) == free                                              # no pocket is walled off by rocks and logs
    for g in cfg["gates"].values():
        assert (int(g["at"][0] / step), int(g["at"][1] / step)) in seen
