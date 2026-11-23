"""Footsteps recorded from the walking videos (scripts/make_step_sound.py, web/static/sound.js, docs/world.md
"Sound")."""
import json
import os

import numpy as np

import looks
from scripts import make_step_sound as ms

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_every_walking_look_has_recorded_steps():
    table = json.load(open(ms.LIST))
    for gender, sheet in looks.WALK_SHEETS.items():
        takes = table.get(sheet["steps"])
        assert takes and len(takes) >= 3, gender
        for t in takes:
            assert os.path.getsize(os.path.join(ms.OUT, t["file"])) > 1000


def test_steps_are_found_where_the_feet_come_down():
    rate = ms.RATE
    x = np.random.default_rng(1).normal(0, 0.001, rate * 4)          # a quiet room
    for at in (0.5, 1.2, 1.9, 2.6, 3.3):                                # five steps, a click each
        a = int(at * rate)
        x[a:a + 400] += np.sin(np.arange(400) / 3) * np.exp(-np.arange(400) / 80) * 0.5
    found = [round(at, 1) for at, _, _ in ms.steps(x)]
    assert found == [0.5, 1.2, 1.9, 2.6, 3.3]


def test_a_cut_is_evened_and_never_clicks():
    x = np.zeros(ms.RATE)
    x[ms.RATE // 2] = 0.2
    y = ms.cut(x, 0.5)
    assert abs(np.abs(y).max() - 10 ** (ms.PEAK / 20)) < 1e-6
    assert abs(y[0]) < 1e-6 and abs(y[-1]) < 1e-6
    assert ms.cut(x, 0.01) is None                                       # too near the start to keep its lead-in
