"""Cut a beast's four animation videos (SHOAIB's, Gemini) into the frame sheets the fight plays
(art/beasts/sheets/<slug>/: idle, attack, hit, death + sheets.json; web/explore_play.beast_sheets, web/static/fight.js
`BeastSheets`; docs/web.md "Animated beasts").

    python -m scripts.make_beast_sheets grey_wolf idle.mp4 attack.mp4 hit.mp4 death.mp4 [--cache DIR]
    python -m scripts.make_beast_sheets --smooth-idle grey_wolf red_fox ...    (an existing idle sheet: `smooth_idle`)

Each video is 1280 x 720 at 24 fps (Flow's 1920 x 1080 is scaled down; one video may be given for two moves, its
seconds in CLIPS): one beast, side on, facing left (toward the cultivator), on a plain backdrop, the
camera still. What is taken from each (CLIPS):
- idle: the stretch (3-6 s) whose last frame best meets its first (scripts/make_heroine_walk.stride), looped;
- attack, hit, death: the part where the beast acts, from its first frame (standing as in idle) to the end of the move.
Every frame is cut out (rembg, as the beast art is), Gemini's sparkle mark and the floor shadow dropped, and a
painted slab under the paws cut away (`slab`: its top edge and how deep the paws sink into it). Then each video is placed on
the beast's own picture (art/beasts/<slug>.png), so the fight's beast never changes size or place between them: its
first frame scaled to the same size of outline and stood on the same ground under the same spot, and every frame of that video moved the same way. `match`: a video whose beast drifts in
colour (the grey wolf's death: lighter and greyer once it lies down) has each frame's colours brought to the named
video's first frame.

All frames share one cell, the box that holds every frame of all four (the attack lunges further left, the death lies
further right than the picture), at SCALE of the picture's pixels. sheets.json says where the picture sits in that
cell (`still`, cell px), so the page lays the frames exactly over it; and per sheet its frames (COLS wide, rows filled
exactly so the idle can be stepped in CSS), its length (`ms`), and for the attack the frame it bites on (`bite`) and
how far its jaws then reach ahead of the picture's nose (`reach`, a share of the picture's width) and where they are
(`bite_x`, a share of the cell's width); for the idle where its front is (`nose_x`); for the death the frame it lands
on (`impact`). The page uses `bite_x` and `nose_x` to keep the beast and the cultivator from running into each other.
Needs ffmpeg, numpy, Pillow, scipy and rembg. --cache keeps the cut frames, so a second run only places them.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

from scripts.make_heroine_walk import stride

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FPS = 24
STEP = 2                        # every 2nd video frame: 12 frames a second, as the cultivator's moves
COLS = 8
SCALE = 0.6                     # sheet pixels per pixel of the beast's picture
KINDS = ("idle", "attack", "hit", "death")
# per beast: the seconds taken from each video, a slab to cut (its top edge, a share of the frame's height), the
# videos to recolour (to whose colours), how long the attack plays in the fight (ms)
CLIPS = {
    "grey_wolf": {"attack": (0.0, 3.0), "hit": (0.0, 1.5), "death": (0.0, 2.5), "idle_span": (72, 144),
                  "slab": {"idle": (0.80, 0.12)}, "match": {"death": "hit"}, "attack_ms": 2200},
    "wild_boar": {"attack": (3.6, 6.1), "hit": (0.6, 1.45), "death": (4.42, 6.5), "idle_span": (84, 144),
                  "attack_ms": 2000, "bite": 16, "white": ("hit",)},
    "field_viper": {"attack": (2.5, 5.9), "hit": (1.6, 3.0), "death": (3.0, 5.6), "idle_span": (30, 50),
                    "idle_until": 2.1, "attack_ms": 2400, "fade": {"attack": 90}},
    "stray_dog_pack": {"attack": (2.6, 3.8), "hit": (1.4, 2.9), "death": (4.0, 6.2), "idle_span": (36, 60),
                       "idle_until": 2.5, "attack_ms": 1800, "pingpong": ("attack",)},
    "wild_ox": {"attack": (2.0, 5.6), "hit": (1.7, 3.4), "death": (4.4, 6.4), "idle_span": (30, 44),
                "idle_from": 5.95, "attack_ms": 2400, "bite": 33, "white": ("hit", "death")},
    # Nov 27 redesign: both videos clean (its gore and its collapse stayed inside the video), from the same picture
    # with the camera still, so every move is placed as the idle
    "steel_horn_bull": {"attack": (4.5, 6.6), "hit": (1.0, 2.3), "death": (3.3, 7.0), "idle_span": (36, 60),
                        "idle_until": 4.4, "attack_ms": 2200, "bite": 8,
                        "ease_in": {"attack": 2, "hit": 3, "death": 3}, "settle": {"attack": 3, "hit": 3},
                        "place_as": {"attack": "idle"}},
    # Nov 27 redesign: both videos clean but for a little dust where its fist hits the ground (those frames dropped);
    # every move eases in from the idle and the slam and the flinch settle back into it
    "golden_eyed_ape_king": {"attack": (3.3, 5.6), "hit": (1.25, 2.5), "death": (2.9, 7.0), "idle_span": (36, 60),
                             "idle_until": 3.2, "attack_ms": 2400, "drop": {"attack": ((4.58, 4.95),)},
                             "ease_in": {"attack": 2, "hit": 3, "death": 3}, "settle": {"attack": 3, "hit": 3},
                             "place_as": {"attack": "idle", "death": "hit"}},
    # Nov 27 redesign: its attack video was made from the uncleaned picture and Veo kept Gemini's sparkle on its rump,
    # redrawn solid and moving with it: cut away with the backdrop (`unstar`). Veo also drew that bear a little longer,
    # so its idle comes from the calm middle of the hit video (as its flinch and fall), and its swipe eases in and out
    "ironbark_bear": {"attack": (4.65, 6.4), "hit": (1.05, 2.2), "death": (3.9, 7.0), "idle_span": (36, 60),
                      "idle_from": 2.1, "idle_until": 4.0, "attack_ms": 2600,
                      "unstar": {"attack": (1000, 440, 1280, 700)},
                      "ease_in": {"attack": 4, "hit": 3, "death": 3}, "settle": {"attack": 4, "hit": 3},
                      "place_as": {"hit": "idle", "death": "idle"}},
    # Nov 27 redesign (pale: no `white` wipe): its bite ends in a burst of ice shards, so the bite is taken up to just
    # before them and plays there and back; its idle from the calm start of that video (Veo crept a little closer by
    # the bite, so the bite is placed by its own first frame and eases in and out)
    # Its idle (Nov 27 fix): the video's first second hardly moved, so the idle is the slight turn and dip of its head
    # just before the bite begins
    "frost_wolf": {"attack": (1.8, 4.55), "hit": (0.7, 2.25), "death": (2.3, 5.5), "idle_span": (12, 19),
                   "breathe": 0.035, "idle_from": 0.8, "idle_until": 1.6, "attack_ms": 2600, "pingpong": ("attack",),
                   "ease_in": {"attack": 3, "hit": 3, "death": 3}, "settle": {"attack": 3, "hit": 3},
                   "place_as": {"death": "hit"}},
    # Nov 27 redesign, standing (wings folded): its first attack and hit spread its wings off the video and drew a slash
    # arc, so they come from a remade video (idle, flinch, beak stab: wings folded); its fall from the first hit video
    # Its idle (Nov 27 fix): the turn of its head as it settles after the flinch, before the stab (the still frames at
    # the start looked frozen)
    "thunder_hawk": {"attack": (4.15, 7.0), "hit": (0.85, 3.0), "death": (2.5, 6.6), "idle_span": (10, 15),
                     "breathe": 0.035, "idle_from": 2.9, "idle_until": 3.55, "attack_ms": 2600,
                     "ease_in": {"attack": 2, "hit": 2, "death": 5}, "settle": {"attack": 3, "hit": 3},
                     "place_as": {"attack": "idle", "hit": "idle"}},
    # Nov 27 redesign: Veo grew its short tail long in every video, so each move is taken before the tail grows: its
    # idle, flinch and collapse from the remade hit + death video, its snapping bite from the first hit video (stopped
    # before a white spark the video drew on its head), each easing in from the idle
    # Its idle (Nov 27 fix): the remade video's first second hardly moved, so the idle is the gentle head dip and throat
    # swell at the start of its first video (before it opens its mouth); the flinch is then placed by its own first frame
    "ember_lizard": {"attack": (0.7, 1.55), "hit": (1.0, 1.85), "death": (4.0, 4.9), "idle_span": (8, 13),
                     "breathe": 0.035, "idle_from": 0.33, "idle_until": 0.88, "attack_ms": 1800,
                     "ease_in": {"attack": 3, "hit": 3, "death": 4}, "settle": {"attack": 3, "hit": 3}},
    # Nov 27 redesign: both videos clean (no remakes): its idle and its open-jawed strike from the attack video (taken
    # on until it is calm again, so it settles with no double head), its flinch and its sinking collapse (its neck
    # lowering till its head lies in front of its coils) from the hit video; the flinch is only its first jerk back
    # (it then reared its head high: cut before), played there and back so it returns the way it went. The snake drifts
    # slowly all through its video, so its idle is the calm second just before the strike winds up
    "frost_python": {"attack": (3.3, 6.4), "hit": (2.1, 2.7), "death": (4.6, 7.9), "idle_span": (16, 26),
                     "breathe": 0.035, "idle_from": 2.2, "idle_until": 3.35, "attack_ms": 2400, "pingpong": ("hit",),
                     "ease_in": {"attack": 2, "hit": 3, "death": 4}, "settle": {"attack": 3},
                     "ease_out": {"hit": 3}, "place_as": {"attack": "idle"}},
    "old_black_bear": {"attack": (2.3, 5.1), "hit": (2.05, 3.45), "death": (3.9, 6.4), "idle_span": (30, 46),
                       "idle_from": 5.8, "attack_ms": 2600, "bite": 27, "impact": 10, "white": ("death",)},
                       # its attack from the remade video with headroom (Nov 26): the first one's head left the video
    "iron_hide_boar": {"attack": (2.6, 4.45), "hit": (2.15, 3.3), "death": (4.2, 6.2), "idle_span": (20, 27),
                       "idle_from": 6.7, "attack_ms": 2000, "white": ("hit", "death"), "pingpong": ("attack",)},
    # the fox leapt out of the video's left edge mid-pounce: its stalk, its spring and its landing snap, joined
    "red_fox": {"attack": ((0.8, 1.75), (3.2, 3.8), (4.62, 5.6)), "hit": (0.3, 2.6), "death": (4.0, 6.1),
                "idle_span": (30, 44), "idle_from": 5.9, "attack_ms": 2400,
                "mark": ((1130, 565, 1195, 632), (1140, 338, 1202, 428)),
                "drop": {"hit": ((0.45, 0.78),), "death": ((4.52, 4.78),)}},
    # the first bird: one wingbeat as its idle (it flew higher and lost its wing tips off the top later in the video)
    "wind_feather_falcon": {"attack": (3.0, 6.85), "hit": (0.4, 1.9), "death": (4.2, 6.6), "idle_span": (40, 51),
                            "idle_until": 2.15, "attack_ms": 2600, "bite": 27, "fade": {"attack": ("top", 40)},
                            "place_as": {"death": "hit"}, "floor": ("attack", "hit", "death")},
    "shadow_wolf": {"attack": (4.2, 7.9), "hit": (1.0, 2.8), "death": (3.3, 5.8), "idle_span": (36, 60),
                    "idle_until": 4.1, "attack_ms": 2600},
    "horned_stag": {"attack": (4.1, 7.6), "hit": (1.0, 3.2), "death": (5.45, 7.6), "idle_span": (36, 60),
                    "idle_until": 4.1, "attack_ms": 2600},    "mountain_tiger": {"attack": (3.9, 8.0), "hit": (1.0, 2.5), "death": (4.0, 6.3), "idle_span": (36, 60),
                       "idle_until": 3.9, "attack_ms": 2800},
    # its coiled tail tip touched the video's right edge as it struck
    "rock_python": {"attack": (3.5, 7.5), "hit": (0.4, 2.4), "death": (3.9, 7.0), "idle_span": (36, 60),
                    "idle_until": 3.4, "attack_ms": 2600, "fade": {"attack": 40}},
    # Veo gave it a real red-crowned crane's black tail from its first move on: the idle from the calm end of the
    # strike video (black-tailed too), and its flapping wing tips brushed the top
    "spear_beak_crane": {"attack": (3.0, 5.9), "hit": (0.45, 2.6), "death": (3.6, 6.2), "idle_span": (30, 44),
                         "idle_from": 5.85, "attack_ms": 2200,
                         "fade": {"attack": 30, "hit": ("top", 30), "death": ("top", 30)}},
    # Veo stretched its tail out straight to the video's right edge from the bite on and never curled it back: the tail
    # tip fades at the edge, and the attack's last frames dissolve back into the standing idle (`settle`)
    "thornback_lizard": {"attack": (2.6, 6.6), "hit": (0.6, 3.0), "death": (3.0, 5.6), "idle_span": (30, 50),
                         "idle_until": 2.5, "attack_ms": 2800, "white": ("hit",), "fade": {"attack": 40},
                         "settle": 4, "place_as": {"attack": "idle", "death": "hit"}},
    # Nov 27, every move from whichever of its two videos had it clean (no remakes): its idle and its snarling lunge from
    # the hit video's calm start (it turned round after the lunge: the lunge plays there and back), its flinch and its
    # collapse from the attack video (whose start drew a white impact flash: dropped); the flinch and the collapse
    # start mid-move, so they ease in from the idle (`ease_in`), and the flinch settles back into it
    "bloodfang_wolf": {"attack": (3.4, 4.6), "hit": (0.85, 2.4), "death": (4.5, 7.0), "idle_span": (36, 60),
                       "idle_until": 3.3, "attack_ms": 2400, "pingpong": ("attack",), "white": ("hit",),
                       "ease_in": {"hit": 3, "death": 3}, "settle": {"hit": 3},
                       "place_as": {"attack": "idle", "hit": "idle", "death": "idle"}},
    # Nov 27, from its two videos as they were (no remakes): its idle from the hit video's calm middle (its attack
    # video's start puffed steam from its snout), its charge and tusk toss from the attack video (the white spit it threw
    # is wiped, `white`), its squealing flinch from the hit video after the spear it drew (the spear and blood: cut off before),
    # its fall from the same video; the flinch eases in from the idle and settles back, the charge settles back home
    "armored_boar_chief": {"attack": (3.2, 7.75), "hit": (0.9, 1.95), "death": (4.0, 6.6), "idle_span": (36, 60),
                           "idle_from": 2.0, "idle_until": 5.0, "attack_ms": 2800,
                           "white": ("attack",), "ease_in": {"hit": 3},
                           "settle": {"attack": 4, "hit": 3},
                           "place_as": {"attack": "idle", "hit": "idle", "death": "idle"}},
    # Nov 27: a WHITE beast, so the white-streak wiping (`white`) would wipe its fur: the frames with the video's white
    # slash arc (its swipe) and impact star (its flinch) are dropped instead; the flinch is only its first duck (it then
    # reared up, head too high: cut before, its ducked pose held a moment, `hold`); its picture had no sparkle (`mark` off, so its pale tail is never taken for one)
    "white_browed_tiger_king": {"attack": (3.0, 7.0), "hit": (0.58, 1.45), "death": (4.4, 7.0), "idle_span": (36, 60),
                                "idle_until": 3.0, "attack_ms": 2800,
                                "drop": {"attack": ((4.38, 5.12),), "hit": ((0.72, 1.12),)},
                                "settle": {"attack": 4, "hit": 3}, "hold": {"hit": 3}, "mark": ((0, 0, 1, 1),),
                                "place_as": {"attack": "idle", "hit": "idle", "death": "idle"}},
    # Nov 27, from its two videos as they were (no remakes): its idle from the attack video's calm stretch (before that
    # its pincers glowed), its tail-over-the-head strike from the same video (the green slash arc dropped), its jolt from
    # the hit video (its spark burst dropped), its sinking onto its belly from the same (stopped before the video turned
    # its pincers black); the video kept the picture's "AI" badge as well as the sparkle (`mark`: both boxes)
    "venom_scorpion": {"attack": (3.6, 6.5), "hit": (0.3, 1.75), "death": (3.3, 6.1), "idle_span": (24, 30),
                       "idle_from": 2.7, "idle_until": 4.0, "attack_ms": 2600,
                       "drop": {"attack": ((4.4, 4.95),), "hit": ((0.8, 1.2),)}, "ease_in": {"death": 2},
                       "settle": {"attack": 4, "hit": 3}, "mark": ((1100, 540, 1230, 660), (1190, 640, 1275, 708)),
                       "place_as": {"attack": "idle", "hit": "idle", "death": "idle"}},
    # Nov 27, from its two videos as they were (no remakes): its idle and its croaking hop from the attack video, its
    # jolt from the hit video with the white impact lines the video drew wiped (`white`: the toad has no white on it),
    # its slump from the same; its throat ballooned and turned pink in that video, so the jolt and the slump ease in
    # from the idle and the jolt settles back
    "poison_toad": {"attack": (3.9, 6.6), "hit": (0.6, 1.95), "death": (4.3, 6.6), "idle_span": (36, 60),
                    "idle_until": 3.9, "attack_ms": 2400, "white": ("hit",), "ease_in": {"hit": 2, "death": 2},
                    "settle": {"attack": 3, "hit": 3},
                    "place_as": {"attack": "idle", "hit": "idle", "death": "idle"}},
    # Nov 27: its idle and its on-the-spot swipe from its remade attack video (its short tail kept; the frame where it
    # turned toward the camera and the yellow spark at its hands dropped); its flinch and its collapse from the first
    # hit video, where Veo grew its tail long: cut back to a short stub (`trim_tail`); that video's white flash (on a
    # silver monkey: dropped, not wiped) is left out, so the flinch eases in from the idle
    "silver_monkey": {"attack": (3.3, 6.2), "hit": (1.15, 2.6), "death": (4.6, 6.6), "idle_span": (36, 60),
                      "idle_until": 3.2, "attack_ms": 2400, "drop": {"attack": ((4.15, 4.72),)},
                      "trim_tail": ("hit", "death"), "ease_in": {"hit": 3, "death": 2},
                      "settle": {"attack": 4, "hit": 3},
                      "place_as": {"attack": "idle", "hit": "idle", "death": "idle"}},
}
MARK = (1100, 540, 1230, 660)   # Gemini's sparkle sits in here (x0, y0, x1, y1 of the 1280 x 720 frame)
# (a beast's own `mark`: tighter boxes where its pale tail tip passes near the sparkle (the fox's), or a second sparkle
# the video drew; a pale blob with the beast all round it is its own fur, not the sparkle, and is kept)


def video_frames(video, numbers):
    """The video's frames with these numbers (0-based), as RGB pictures."""
    w, h = 1280, 720
    data = subprocess.run(["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={w}:{h}", "-f", "rawvideo",
                           "-pix_fmt", "rgb24", "-"],                # Flow's 1920 x 1080 brought to 1280 x 720
                          capture_output=True, check=True).stdout
    all_ = np.frombuffer(data, np.uint8).reshape(-1, h, w, 3)
    return [Image.fromarray(all_[n]) for n in numbers]


def off_slab(a, top, depth):
    """Cut a painted slab away: below its top edge (a share of the height) keep only the paws, which sink `depth`
    into it: what the cut-out kept under the legs' own columns, joined to the legs."""
    h = a.shape[0]
    y = int(h * top)
    legs = (a[y - 6:y, :, 3] > 128).any(0)
    cols = ndimage.binary_dilation(legs, iterations=14)
    keep = np.zeros(a.shape[:2], bool)
    keep[:y] = True
    keep[y:y + int(h * depth)] = cols[None, :]
    a[..., 3] = np.where(keep, a[..., 3], 0)
    lab, n = ndimage.label(a[..., 3] > 60)                   # what is left of the stone, no longer joined: dropped
    above = set(np.unique(lab[:y][a[:y, :, 3] > 60])) - {0}
    a[..., 3] = np.where(np.isin(lab, list(above)) | (a[..., 3] <= 60) & keep, a[..., 3], 0)
    return a


def star_mask(im, box):
    """Gemini's sparkle painted INTO the beast (a video made from the uncleaned picture: Veo kept the star on the bear's
    rump, redrawn solid, and moved it with the body): inside `box`, the pale colourless patch with a bright core,
    a little widened. It is cut away with the backdrop (a small notch at the beast's edge reads as nothing; a white
    star reads as a star)."""
    px = np.asarray(im).astype(np.int16)
    x0, y0, x1, y1 = box
    sub = px[y0:y1, x0:x1]
    spread, lum = sub.max(-1) - sub.min(-1), sub.mean(-1)
    bg = np.median(lum[spread < 10])                            # the backdrop around it: the star is paler than it
    pale = (lum > bg + 2) & (spread < 36)
    core = (lum > bg + 8) & pale
    lab, n = ndimage.label(pale)
    out = np.zeros(px.shape[:2], bool)
    if n and core.any():
        sizes = ndimage.sum(core, lab, range(1, n + 1))
        if sizes.max() >= 30:
            out[y0:y1, x0:x1] = ndimage.binary_dilation(lab == 1 + int(np.argmax(sizes)), iterations=3)
    return out


def cut_one(im, session, slab=None, white=False, fade=0, mark=MARK, star_box=None):
    """The beast alone: cut out, no mark, no slab, no shadow or loose bits. `white`: a white slash streak the video drew
    over it (the unseen blow) dropped too: near-white, colourless pixels. `star_box`: a sparkle painted into the beast
    (`star_mask`, the config's `unstar` box), cut away with the backdrop."""
    from rembg import remove
    a = np.asarray(remove(im, session=session)).copy()
    if white:
        px = np.asarray(im).astype(np.int16)
        streak = (px.min(-1) > 175) & ((px.max(-1) - px.min(-1)) < 30)
        a[..., 3] = np.where(ndimage.binary_dilation(streak, iterations=2), 0, a[..., 3])
    px = np.asarray(im).astype(np.float32)
    bg = np.median(np.concatenate([px[:20].reshape(-1, 3), px[:, :20].reshape(-1, 3)]), 0).mean()
    for x0, y0, x1, y1 in (mark if isinstance(mark[0], (tuple, list)) else [mark]):   # one box, or several
        box = px[y0:y1, x0:x1]                               # the sparkle: the biggest pale, colourless blob there
        pale = (box.mean(-1) > np.median(box.mean(-1)) + 8) & ((box.max(-1) - box.min(-1)) < 25)
        lab, n = ndimage.label(pale)
        if n:
            sizes = ndimage.sum(pale, lab, range(1, n + 1))
            star = ndimage.binary_dilation(lab == 1 + int(np.argmax(sizes)), iterations=3)
            ring = ndimage.binary_dilation(star, iterations=4) & ~star
            backdrop = ((box.max(-1) - box.min(-1)) < 18) & (np.abs(box.mean(-1) - bg) < 25)
            if not ring.any() or backdrop[ring].mean() > 0.4:   # set on the backdrop: the sparkle, not a pale
                a[y0:y1, x0:x1, 3] = np.where(star, 0, a[y0:y1, x0:x1, 3])   # tail tip lying over it (the fox's)
        grey = ((box.max(-1) - box.min(-1)) < 18) & (box.mean(-1) > bg - 35)     # the backdrop the cutter kept by
        lab, n = ndimage.label(grey)                                             # the mark: big patches, not the
        if n:                                                                    # paw's own pale specks
            sizes = ndimage.sum(grey, lab, range(1, n + 1))
            grey = np.isin(lab, 1 + np.flatnonzero(sizes >= 150))
            a[y0:y1, x0:x1, 3] = np.where(grey, 0, a[y0:y1, x0:x1, 3])
    if star_box:
        a[..., 3] = np.where(star_mask(im, star_box), 0, a[..., 3])
    if slab:
        a = off_slab(a, *slab)
    if fade:                                                 # the body ran off the video's edge: fade it out
        edge, px = fade if isinstance(fade, tuple) else ("right", fade)     # instead of a hard straight cut
        if edge == "right":
            ramp = np.clip(np.arange(a.shape[1])[::-1] / px, 0, 1)
            a[..., 3] = (a[..., 3] * ramp[None, :]).astype(np.uint8)
        else:                                                               # "top": a head reared out of the video
            ramp = np.clip(np.arange(a.shape[0]) / px, 0, 1)
            a[..., 3] = (a[..., 3] * ramp[:, None]).astype(np.uint8)
    alpha = a[..., 3] > 24
    lab, n = ndimage.label(ndimage.binary_dilation(alpha, iterations=3))
    if n > 1:                                                # the beast: its largest piece and what touches it
        sizes = ndimage.sum(alpha, lab, range(1, n + 1))
        a[..., 3] = np.where(lab == 1 + int(np.argmax(sizes)), a[..., 3], 0)
    a[..., 3] = np.where(a[..., 3] < 24, 0, a[..., 3])
    solid = np.flatnonzero((a[..., 3] > 128).any(1))
    if len(solid):
        a[solid.max() + 1:, :, 3] = 0                        # nothing below its lowest solid part: the floor shadow
    return Image.fromarray(a, "RGBA")


def trim_tail(im, r=27, keep=55, fade=35):
    """A tail Veo grew long cut back to a short stub (SHOAIB, Nov 27: the Silver Monkey's short tail grew long in its
    hit and death video). The body is what survives an opening with a disc of radius r (thicker than the tail, thinner
    than the arms and legs); the thin piece left over behind the body's middle is the tail, kept only `keep` px out from
    the body and faded out over `fade` px more. A faint half-cut tail tip the cutter left (alpha under 128) far from the
    body goes the same way."""
    a = np.asarray(im).copy()
    m = a[..., 3] > 128
    yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    body = ndimage.binary_opening(m, structure=(xx ** 2 + yy ** 2) <= r * r)
    lab, n = ndimage.label(body)
    if not n:
        return im
    body = lab == 1 + int(np.argmax(ndimage.sum(body, lab, range(1, n + 1))))
    thin = m & ~body
    lab, n = ndimage.label(thin)
    near = np.clip((keep + fade - ndimage.distance_transform_edt(~body)) / fade, 0, 1)
    if n:
        sizes = ndimage.sum(thin, lab, range(1, n + 1))
        mids = ndimage.center_of_mass(thin, lab, range(1, n + 1))
        middle = np.flatnonzero(body.any(0)).mean()
        behind = [i for i in range(n) if mids[i][1] > middle and sizes[i] > 1500]
        if behind:
            tail = ndimage.binary_dilation(lab == 1 + max(behind, key=lambda i: sizes[i]), iterations=2) & ~body
            a[..., 3] = np.where(tail, (a[..., 3] * near).astype(np.uint8), a[..., 3])
    a[..., 3] = np.where(~m, (a[..., 3] * near).astype(np.uint8), a[..., 3])
    return Image.fromarray(a, "RGBA")


def trim_tail_x(im, keep=18, fade=20, band=0.1, end=None):
    """A long tail cut back by where it is, not by how thin it is (the Wind Leopard's: thick at its root, so
    `trim_tail` takes it for body): whatever reaches further right than the beast's back feet (the right end of its
    lowest `band` of rows) by more than `keep` px fades out over `fade` px. The beast faces left, so nothing of its
    own body but the tail lies behind its back feet; lying dead, its stretched-out hind feet still mark the end."""
    a = np.asarray(im).copy()
    m = a[..., 3] > 128
    rows = np.flatnonzero(m.any(1))
    if not len(rows):
        return im
    if end is None:                                          # (a move lying down: the line its standing start drew)
        low = m[rows.max() - max(2, int(len(rows) * band)):rows.max() + 1]
        end = np.flatnonzero(low.any(0)).max() + keep
    ramp = np.clip((end + fade - np.arange(a.shape[1])) / fade, 0, 1)
    a[..., 3] = (a[..., 3] * ramp[None, :]).astype(np.uint8)
    return Image.fromarray(a, "RGBA"), end


def cut_clip(kind, video, numbers, cfg, cache, session):
    out, raw, tail_end = [], None, None
    for n in numbers:
        path = os.path.join(cache, kind, f"{n:03d}.png") if cache else None
        if path and os.path.exists(path):
            out.append(Image.open(path).convert("RGBA"))
            continue
        if session is None:
            from rembg import new_session
            session = new_session("isnet-general-use")
        if raw is None:
            raw = dict(zip(numbers, video_frames(video, numbers)))
        im = cut_one(raw[n], session, cfg.get("slab", {}).get(kind), kind in cfg.get("white", ()),
                     cfg.get("fade", {}).get(kind, 0), cfg.get("mark", MARK), cfg.get("unstar", {}).get(kind))
        if kind in cfg.get("trim_tail", ()):
            if not cfg.get("tail_x") or kind in cfg.get("tail_disc", ()):   # by thinness (a lying beast's thin tail)
                im = trim_tail(im, *cfg.get("tail_r", ()))
            until = cfg.get("tail_x_until", {}).get(kind)    # (lying down, its lowest part is no longer its feet)
            if cfg.get("tail_x") and (until is None or n < until * FPS):   # and where it reaches past its back feet;
                im, end = trim_tail_x(im, *cfg["tail_x"], end=tail_end)    # a move lying down keeps its first line
                if kind in cfg.get("tail_fixed", ()):
                    tail_end = end
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            im.save(path)
        out.append(im)
        print(f"  {kind} {n}", flush=True)
    return out, session


PINGPONG_MAX = 24          # an idle of up to this many frames plays forward then back; a longer one dissolves its end
BLEND = 6                  # into its start over this many frames (a doubled long idle would be too big a sheet)


def settle(frames, rest, n):
    """The move's end easing back into `rest` (the idle's first frame), so a beast that ends its move in another pose
    or spot than it started (the lizard: further along, its tail straightened) neither snaps nor shows a double body:
    over its last 2n frames it slides back so its front (its nose, its front feet) meets the idle's, and over the
    last n of them it dissolves into the idle (premultiplied, so the see-through edges stay clean)."""
    def nose(im):
        a = np.asarray(im.getchannel("A")) > 128
        cols = np.flatnonzero(a.any(0))
        front = a[:, cols.min():cols.min() + int(0.6 * (cols.max() - cols.min()))]   # its feet, not a low tail tip
        return cols.min(), np.flatnonzero(front.any(1)).max()
    (rx, ry), (lx, ly) = nose(rest), nose(frames[-1])
    dx, dy = rx - lx, ry - ly
    r = np.asarray(rest).astype(np.float32) / 255
    r[..., :3] *= r[..., 3:]
    k = min(2 * n, len(frames))
    out = frames[:len(frames) - k]
    for i, f in enumerate(frames[len(frames) - k:]):
        s = min(1, (i + 1) / (k - n))                       # the slide: done by the dissolve's start
        moved = Image.new("RGBA", f.size, (0, 0, 0, 0))
        moved.paste(f, (round(dx * s), round(dy * s)), f)
        w = max(0, (i + 1 - (k - n)) / n)                   # the dissolve
        a = np.asarray(moved).astype(np.float32) / 255
        a[..., :3] *= a[..., 3:]
        m = a * (1 - w) + r * w
        m[..., :3] /= np.maximum(m[..., 3:], 1e-6)
        out.append(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8), "RGBA"))
    return out


def ease_in(frames, rest, n):
    """The move's start eased out of `rest` (the idle's first frame), for a move cut from a video where the beast was
    already moving (a flinch that starts mid-duck, a lunge from another video): n frames are put in front that slide
    the idle's body toward the move's first frame (its front, as `settle`) and dissolve into it, so the cut never
    snaps from the standing beast into the moving one."""
    if not frames or n <= 0:
        return frames
    def nose(im):
        a = np.asarray(im.getchannel("A")) > 128
        cols = np.flatnonzero(a.any(0))
        front = a[:, cols.min():cols.min() + int(0.6 * (cols.max() - cols.min()))]
        return cols.min(), np.flatnonzero(front.any(1)).max()
    (rx, ry), (fx, fy) = nose(rest), nose(frames[0])
    f = np.asarray(frames[0]).astype(np.float32) / 255
    f[..., :3] *= f[..., 3:]
    out = []
    for i in range(n):
        s = (i + 1) / (n + 1)
        moved = Image.new("RGBA", rest.size, (0, 0, 0, 0))
        moved.paste(rest, (round((fx - rx) * s), round((fy - ry) * s)), rest)
        a = np.asarray(moved).astype(np.float32) / 255
        a[..., :3] *= a[..., 3:]
        m = a * (1 - s) + f * s
        m[..., :3] /= np.maximum(m[..., 3:], 1e-6)
        out.append(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8), "RGBA"))
    return out + list(frames)


def ease_out(frames, rest, n):
    """The move's calm last frame eased back into `rest` (the idle's first frame) over n more frames: `ease_in` run
    the other way, for a move from another video that ends calm but a little off the idle (the Frost Python's flinch,
    played there and back). Unlike `settle` it only uses the last frame, so a thin part that moved in the frames
    before (a flicking tongue) never drags the slide."""
    if not frames or n <= 0:
        return frames
    return list(frames) + ease_in([frames[-1]], rest, n)[:n][::-1]


def smooth_idle(frames, ms):
    """(frames, ms): the idle loop with no jump where it comes back round (SHOAIB, Nov 26: "it keeps resetting").
    Its last frame never quite meets its first (the measured jump was 2-7 times a normal step), so a short idle plays
    forward and then backward, breathing in and out (each end held a moment: the frame count stays a whole number of
    rows, which the CSS needs). A long one keeps going forward, its last BLEND frames dissolving into its first."""
    if len(frames) <= PINGPONG_MAX:
        return frames + frames[::-1], ms * 2
    out = list(frames)
    for j in range(BLEND):
        w = (j + 1) / (BLEND + 1)
        out[len(out) - BLEND + j] = Image.blend(frames[len(frames) - BLEND + j], frames[0], w)   # into the first
    return out, ms


BREATH_MS = 2400     # one slow breath


def breathe(frames, ms, amp=0.03):
    """(frames, ms): an idle that hardly moves in its video, given a slow, visible breath (SHOAIB, Nov 27: "they are
    still barely moving"). Its smooth loop is repeated to about one breath long, and over it the beast's body swells
    down and rises back from its planted feet (its back lower by up to `amp` of its height, less lower down: never
    taller, so nothing leaves its cell) while its head end sways a little back and forward. The loop's first frame is left as it was (the other moves start from it) and the breath
    comes round to it again, so it still loops with no jump."""
    reps = max(1, round(BREATH_MS / ms))
    frames = list(frames) * reps
    ms *= reps
    n = len(frames)
    out = []
    for i, f in enumerate(frames):
        phase = -(1 - np.cos(2 * np.pi * i / n)) / 2          # 0 at the loop's start, -1 halfway: never taller
        a = np.asarray(f).astype(np.float32) / 255
        box = f.getbbox()
        if not box or abs(phase) < 1e-6:
            out.append(f)
            continue
        x0, top, x1, feet = box
        tall = max(1, feet - top)
        hh, ww = a.shape[:2]
        yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
        up = np.clip((feet - yy) / tall, 0, None)             # 0 at the feet, 1 at the top of its back
        sy = feet - (feet - yy) / (1 + amp * phase * up)     # the body swells up from the feet, most at the top
        sx = xx - 0.012 * tall * phase * up ** 2             # and its head end sways a touch forward and back
        pm = a.copy()
        pm[..., :3] *= pm[..., 3:]
        warped = np.stack([ndimage.map_coordinates(pm[..., c], [sy, sx], order=1, mode="constant") for c in range(4)], -1)
        warped[..., :3] /= np.maximum(warped[..., 3:], 1e-6)
        out.append(Image.fromarray((np.clip(warped, 0, 1) * 255).astype(np.uint8), "RGBA"))
    return out, ms


def resmooth(slug):
    """Smooth an existing beast's idle sheet in place (`--smooth-idle`), from the sheet itself: no videos needed."""
    out_dir = os.path.join(ROOT, "art", "beasts", "sheets", slug)
    path = os.path.join(out_dir, "sheets.json")
    data = json.load(open(path))
    info, (cw, ch) = data["sheets"]["idle"], data["cell"]
    if info.get("smooth"):
        return print(slug, "already smooth")
    sheet = Image.open(os.path.join(out_dir, "idle.webp")).convert("RGBA")
    frames = [sheet.crop(((i % COLS) * cw, (i // COLS) * ch, (i % COLS + 1) * cw, (i // COLS + 1) * ch))
              for i in range(info["frames"])]
    frames, info["ms"] = smooth_idle(frames, info["ms"])
    rows = -(-len(frames) // COLS)
    out = Image.new("RGBA", (cw * COLS, ch * rows), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        out.alpha_composite(f, ((i % COLS) * cw, (i // COLS) * ch))
    out.save(os.path.join(out_dir, "idle.webp"), quality=84, method=6)
    info.update(frames=len(frames), rows=rows, smooth=True)
    with open(path, "w") as fh:
        json.dump(data, fh, indent=1)
    print(slug, info)


def spans(clip):
    """A move's seconds: one (start, end), or several joined ((start, end), ...)."""
    return list(clip) if isinstance(clip[0], (tuple, list)) else [clip]


def solid(im):
    return np.asarray(im.getchannel("A")) > 128


def feet_x(a):
    rows = np.flatnonzero(a.any(1))
    low = a[rows.max() - max(2, int(len(rows) * 0.08)):rows.max() + 1]
    return float(np.flatnonzero(low.any(0)).mean()), int(rows.max())


def placing(first, still):
    """(scale, dx, dy): this video's first frame onto the picture: the same size of outline (its width and height
    together; Gemini redrew the beast a little in each video, so its body fills its outline differently), the same
    ground line, its paws under the same spot."""
    a, b = solid(first), solid(still)
    def size(m):
        ys, xs = np.where(m)
        return xs.max() - xs.min() + 1, ys.max() - ys.min() + 1
    (wa, ha), (wb, hb) = size(a), size(b)
    s = (wb / wa * hb / ha) ** 0.5
    fa, ga = feet_x(a)
    fb, gb = feet_x(b)
    return s, fb - fa * s, (gb + 1) - (ga + 1) * s


def match(images, ref):
    """Each frame's body colours brought to the reference's (mean and spread per channel)."""
    def body(im):
        a = np.asarray(im).astype(np.float32)
        return a[..., :3][a[..., 3] > 200]
    r = body(ref)
    mu_r, sd_r = r.mean(0), r.std(0)
    out = []
    for im in images:
        a = np.asarray(im).astype(np.float32)
        g = body(im)
        a[..., :3] = ((a[..., :3] - g.mean(0)) / np.maximum(g.std(0), 1) * sd_r + mu_r).clip(0, 255)
        out.append(Image.fromarray(a.astype(np.uint8), "RGBA"))
    return out


def main(slug, videos, cache=None):
    cfg = CLIPS[slug]
    still = Image.open(os.path.join(ROOT, "art", "beasts", f"{slug}.png")).convert("RGBA")
    picks = {}
    idle_src = videos["idle"]
    if cfg.get("idle_until") or cfg.get("idle_from"):         # its breath only from a calm stretch of the video
        idle_src = os.path.join(cache or "/tmp", f"{slug}_idle_part.mp4")
        os.makedirs(os.path.dirname(idle_src), exist_ok=True)
        part = ["-ss", str(cfg.get("idle_from", 0))] + (["-to", str(cfg["idle_until"])] if cfg.get("idle_until") else [])
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", videos["idle"]] + part + ["-an", idle_src], check=True)
    a, n = stride(idle_src, 0, cfg["idle_span"])
    count = COLS * max(1, round(n / STEP / COLS))
    a += round(cfg.get("idle_from", 0) * FPS)                 # back to the whole video's frame numbers
    picks["idle"] = [a + round(j * n / count) for j in range(count)]          # its own end (a + n) is the next start
    idle_ms = round(n / FPS * 1000)
    for kind in KINDS[1:]:
        picks[kind] = []
        for s0, s1 in spans(cfg[kind]):                       # one stretch of the video, or several joined
            picks[kind] += list(range(round(s0 * FPS), round(s1 * FPS), STEP))
        for d0, d1 in cfg.get("drop", {}).get(kind, ()):      # frames an effect covered the beast in: left out
            picks[kind] = [n for n in picks[kind] if not d0 * FPS <= n < d1 * FPS]
    clips, session = {}, None
    for kind in KINDS:
        clips[kind], session = cut_clip(kind, videos[kind], picks[kind], cfg, cache, session)
    for kind in cfg.get("pingpong", ()):                      # it ran off the video mid-move: there and back again
        clips[kind] = clips[kind] + clips[kind][-2:0:-1]
    for kind, ref in cfg.get("match", {}).items():
        clips[kind] = match(clips[kind], clips[ref][0])

    # every frame on the picture's ground, in the picture's pixels; then the box that holds them all
    placed, places = {}, {}
    for kind in KINDS:
        places[kind] = placing(clips[kind][0], still)
    for kind, like in cfg.get("place_as", {}).items():        # the same video, the camera still: placed as that move
        places[kind] = places[like]                           # (the falcon flew further off before it died)
    for kind in KINDS:
        s, dx, dy = places[kind]
        placed[kind] = []
        for im in clips[kind]:
            big = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
            y = round(dy)
            if kind in cfg.get("floor", ()):                  # never below the ground the picture stands on: a bird
                y -= max(0, y + big.getbbox()[3] - still.height)    # drawn with its talons on it lands on it, dying
            placed[kind].append((big, round(dx), y))
    boxes = []
    for kind in KINDS:
        for big, x, y in placed[kind]:
            l, t, r, b = big.getbbox()
            boxes.append((l + x, t + y, r + x, b + y))
    X0, Y0 = min(b[0] for b in boxes) - 4, min(b[1] for b in boxes) - 4
    X1, Y1 = max(b[2] for b in boxes) + 4, max(b[3] for b in boxes) + 2
    cw, ch = round((X1 - X0) * SCALE), round((Y1 - Y0) * SCALE)

    def cell(big, x, y):
        return big.crop((X0 - x, Y0 - y, X1 - x, Y1 - y)).resize((cw, ch), Image.LANCZOS)   # outside it: transparent

    out_dir = os.path.join(ROOT, "art", "beasts", "sheets", slug)
    os.makedirs(out_dir, exist_ok=True)
    data = {"cell": [cw, ch], "still": [round(-X0 * SCALE, 2), round(-Y0 * SCALE, 2),
                                        round(still.width * SCALE, 2), round(still.height * SCALE, 2)],
            "sheets": {}}
    for kind in KINDS:
        frames = [cell(*p) for p in placed[kind]]
        if kind == "idle":
            rest = frames[0]
        n_settle = cfg.get("settle", 0)
        n_settle = n_settle.get(kind, 0) if isinstance(n_settle, dict) else (n_settle if kind == "attack" else 0)
        if cfg.get("hold", {}).get(kind):                    # a short move held on its last pose, then eased home
            frames = frames + [frames[-1]] * cfg["hold"][kind]
        if kind != "idle" and cfg.get("ease_in", {}).get(kind):
            frames = ease_in(frames, rest, cfg["ease_in"][kind])
        if n_settle:                                         # (an int: the attack's; a dict: per move)
            frames = settle(frames, rest, n_settle)
        if kind != "idle" and cfg.get("ease_out", {}).get(kind):
            frames = ease_out(frames, rest, cfg["ease_out"][kind])
        if kind == "idle":
            frames, idle_ms = smooth_idle(frames, idle_ms)
            if cfg.get("breathe"):
                frames, idle_ms = breathe(frames, idle_ms, cfg["breathe"])
        rows = -(-len(frames) // COLS)
        sheet = Image.new("RGBA", (cw * COLS, ch * rows), (0, 0, 0, 0))
        for i, f in enumerate(frames):
            sheet.alpha_composite(f, ((i % COLS) * cw, (i // COLS) * ch))
        sheet.save(os.path.join(out_dir, f"{kind}.webp"), quality=84, method=6)
        info = {"src": f"/art/beasts/sheets/{slug}/{kind}.webp", "frames": len(frames), "cols": COLS, "rows": rows}
        if kind == "idle":
            info["ms"] = idle_ms
            info["smooth"] = True
            info["nose_x"] = round(frames[0].getbbox()[0] / cw, 4)              # its front, standing
        elif kind == "attack":
            info["ms"] = cfg["attack_ms"]
            lefts = [f.getbbox()[0] for f in frames]
            lo, hi = len(frames) // 4, len(frames) * 3 // 4
            bite = cfg.get("bite", lo + int(np.argmin(lefts[lo:hi])))         # the jaws furthest forward (or set by eye)
            info["bite"] = bite
            info["reach"] = round(max(0, lefts[0] - lefts[bite]) / (still.width * SCALE), 4)
            info["bite_x"] = round(lefts[bite] / cw, 4)                         # its jaws, at the bite
        else:
            if (len(spans(cfg[kind])) > 1 or kind in cfg.get("drop", {}) or kind in cfg.get("ease_in", {})
                    or kind in cfg.get("hold", {})):
                info["ms"] = round(len(frames) * STEP / FPS * 1000)            # the frames it really plays
            else:
                s0, s1 = cfg[kind]
                info["ms"] = round((s1 - s0) * 1000)
            if kind == "death":
                tops = [f.getbbox()[1] for f in frames]
                info["impact"] = cfg.get("impact", next(i for i, t in enumerate(tops) if t >= tops[-1] - 0.04 * ch))   # down
        data["sheets"][kind] = info
        print(f"{kind}: {len(frames)} frames, {COLS} x {rows}, {info}")
    with open(os.path.join(out_dir, "sheets.json"), "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"cell {cw} x {ch}, the picture at {data['still']}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--smooth-idle"]:                         # python -m scripts.make_beast_sheets --smooth-idle slug ...
        for slug in args[1:]:
            resmooth(slug)
        sys.exit(0)
    cache = None
    if "--cache" in args:
        i = args.index("--cache")
        cache = args[i + 1]
        del args[i:i + 2]
    if len(args) != 5:
        sys.exit(__doc__)
    main(args[0], dict(zip(KINDS, args[1:])), cache)
