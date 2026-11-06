"""
Drawn icons for the 30 techniques (like the weapon and gear icons).

theme.icon(img, "tech:iron_fist", ...) draws one. Each technique has its own icon: the base shape of its
school (Fist = clenched fist, Palm = open palm, Finger = two pointing fingers, Leg = kicking leg,
Body = standing figure or torso) plus a motif from its name. "school:Fist" draws the plain base shape.

Each function takes (d, cx, cy, s, color, dark), like cards/gear_icons.py: s is half the icon size and
dark a shaded version of color. The silhouettes are bold so they read at 24 px; fine details (sparks,
scales, extra lines) are only added when the icon is large. Pillow only, no image files.
"""
import math

from .drawkit import Pen, tint

WHITE = (255, 255, 255)
VOIDC = (10, 6, 7)


# ── school base shapes (drawn with a Pen, in icon units -1..1) ──────────

def fist(p, c, dk, plain=False):
    """A clenched fist seen from the front, knuckles up, wrist below."""
    p.rrect(-0.36, 0.45, 0.36, 1.0, 0.06, dk if not plain else c)
    p.rrect(-0.6, -0.42, 0.62, 0.58, 0.26, c)
    for i, x in enumerate((-0.44, -0.15, 0.15, 0.44)):
        p.circle(x, -0.42, 0.17, c)
    if p.size >= 7:
        for x in (-0.3, 0.0, 0.3):
            p.line([(x, -0.52), (x, -0.12)], dk, 0.07)
    # thumb folded across the fingers
    p.capsule((-0.66, 0.16), (0.12, 0.06), 0.3, tint(c, 0.12), dk, 0.06)


def palm(p, c, dk):
    """An open palm, fingers up, thumb out to the left."""
    p.rrect(-0.27, 0.62, 0.27, 1.0, 0.05, dk)
    p.poly([(-0.5, -0.05), (0.5, -0.05), (0.46, 0.5), (0.3, 0.72), (-0.3, 0.72), (-0.48, 0.48)], c)
    for x, top in ((-0.37, -0.55), (-0.12, -0.86), (0.13, -0.92), (0.37, -0.68)):
        p.capsule((x, 0.05), (x, top), 0.23, c)
    p.capsule((-0.42, 0.45), (-0.86, -0.05), 0.24, c)
    if p.size >= 7:
        for x in (-0.25, 0.0, 0.25):
            p.line([(x, -0.06), (x, 0.08)], dk, 0.06)
        p.arc(-0.05, 0.2, 0.3, 200, 320, dk, 0.05)


def fingers(p, c, dk):
    """Two fingers pointing up (the sword-finger hand), the others folded under the thumb."""
    p.rrect(-0.28, 0.55, 0.28, 1.0, 0.05, dk)
    p.rrect(-0.46, -0.08, 0.48, 0.66, 0.22, c)
    p.capsule((-0.17, 0.05), (-0.17, -0.95), 0.25, c)
    p.capsule((0.11, 0.05), (0.11, -0.84), 0.25, c)
    p.circle(0.33, -0.04, 0.16, c)
    if p.size >= 7:
        p.line([(-0.03, -0.75), (-0.03, -0.05)], dk, 0.06)
    p.capsule((-0.5, 0.3), (0.2, 0.22), 0.26, tint(c, 0.12), dk, 0.06)


def leg(p, c, dk):
    """A flying side kick: thigh and shin rising to the right, the foot flexed with its toes up and the
    sole striking forward."""
    q = p.sub(-0.02, 0.1, 1.08, rot=-26)
    q.capsule((-0.78, 0.7), (-0.2, 0.22), 0.46, c)                    # thigh
    q.poly([(-0.26, 0.0), (0.42, -0.06), (0.44, 0.17), (-0.2, 0.45)], c)  # shin
    q.circle(-0.2, 0.22, 0.23, c)                                       # knee
    q.poly([(0.34, -0.08), (0.48, -0.24), (0.5, -0.72), (0.6, -0.86), (0.76, -0.8), (0.8, 0.12), (0.66, 0.26),
            (0.38, 0.22)], c)                                            # foot, toes up
    q.line([(0.36, -0.1), (0.38, 0.22)], dk, 0.1)                       # ankle wrap
    if q.size >= 7:
        q.line([(0.79, -0.7), (0.8, 0.08)], tint(c, 0.4), 0.06)         # sole
        q.line([(-0.62, 0.2), (-0.42, 0.42)], dk, 0.06)                    # trouser fold


def figure(p, c, dk, pose="stand"):
    """A martial artist. pose: stand, wide (horse stance), seated (lotus), stride."""
    p.circle(0, -0.72, 0.21, c)
    if pose == "seated":
        p.poly([(-0.36, -0.46), (0.36, -0.46), (0.3, 0.3), (-0.3, 0.3)], c)
        p.poly([(-0.36, -0.42), (-0.6, 0.1), (-0.25, 0.25)], c)
        p.poly([(0.36, -0.42), (0.6, 0.1), (0.25, 0.25)], c)
        p.ellipse(0, 0.48, 0.86, 0.28, c)
        p.line([(-0.5, 0.48), (0.5, 0.48)], dk, 0.07)
        return
    p.poly([(-0.38, -0.46), (0.38, -0.46), (0.28, 0.2), (-0.28, 0.2)], c)
    if pose == "wide":
        p.poly([(-0.28, 0.12), (-0.05, 0.2), (-0.5, 0.62), (-0.42, 1.0), (-0.68, 1.0), (-0.78, 0.6)], c)
        p.poly([(0.28, 0.12), (0.05, 0.2), (0.5, 0.62), (0.42, 1.0), (0.68, 1.0), (0.78, 0.6)], c)
        for sd in (-1, 1):
            p.capsule((sd * 0.34, -0.4), (sd * 0.62, -0.05), 0.2, c)
            p.circle(sd * 0.62, -0.05, 0.15, c)
    elif pose == "stride":
        p.poly([(-0.28, 0.12), (0.0, 0.2), (-0.32, 0.6), (-0.62, 0.98), (-0.84, 0.88), (-0.55, 0.5)], c)
        p.poly([(0.28, 0.12), (0.0, 0.2), (0.3, 0.55), (0.62, 0.62), (0.66, 0.84), (0.26, 0.8), (0.08, 0.5)], c)
        p.capsule((-0.34, -0.4), (-0.72, -0.05), 0.2, c)
        p.capsule((0.34, -0.4), (0.74, -0.62), 0.2, c)
    else:
        p.poly([(-0.28, 0.12), (0.28, 0.12), (0.34, 1.0), (0.08, 1.0), (0.0, 0.42), (-0.08, 1.0), (-0.34, 1.0)], c)
        for sd in (-1, 1):
            p.capsule((sd * 0.36, -0.4), (sd * 0.52, 0.2), 0.2, c)
    if p.size >= 7:
        p.line([(-0.3, 0.1), (0.3, 0.1)], dk, 0.08)       # sash


def torso(p, c, dk):
    """A bare muscled torso (shoulders to waist)."""
    p.circle(0, -0.78, 0.2, c)
    p.poly([(-0.95, -0.42), (-0.55, -0.6), (0.55, -0.6), (0.95, -0.42), (0.78, -0.1), (0.5, 0.0), (0.42, 0.9),
            (-0.42, 0.9), (-0.5, 0.0), (-0.78, -0.1)], c)
    p.line([(0.0, -0.45), (0.0, 0.85)], dk, 0.06)
    p.arc(-0.24, -0.24, 0.22, 20, 160, dk, 0.06)
    p.arc(0.24, -0.24, 0.22, 20, 160, dk, 0.06)
    if p.size >= 7:
        for y in (0.2, 0.45, 0.68):
            p.line([(-0.22, y), (0.22, y)], dk, 0.05)


BASE = {"Fist": fist, "Palm": palm, "Finger": fingers, "Leg": leg, "Body": figure}


def _pen(d, cx, cy, s):
    return Pen(d, cx, cy, s)


def school(name):
    """The plain base shape of a school as an icon function."""
    def draw(d, cx, cy, s, color, dark):
        BASE[name](_pen(d, cx, cy, s), color, dark)
    return draw


# ── Mortal ──────────────────────────────────────────────────────────────

def iron_fist(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    fist(p, c, dk)
    for y in (0.62, 0.82):
        p.line([(-0.38, y), (0.38, y)], tint(c, 0.35), 0.08)
    if p.big:
        for x in (-0.3, 0.0, 0.3):
            p.circle(x, -0.48, 0.05, tint(c, 0.6))


def twin_palm_strike(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    palm(p.sub(-0.38, 0.06, 0.66, rot=-14, flip=True), tint(c, -0.15), dk)
    palm(p.sub(0.38, 0.0, 0.66, rot=14), c, dk)


def crescent_sweep(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    p.crescent(0.05, 0.0, 0.98, tint(c, -0.35), angle=-130, shift=0.32)
    leg(p.sub(0.06, 0.08, 0.8), c, dk)


def horse_stance_guard(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    figure(p, c, dk, "wide")
    p.line([(-0.95, 1.0), (0.95, 1.0)], dk, 0.08)


def parrying_arm(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    p.capsule((-0.55, 0.85), (0.2, -0.25), 0.42, c)
    fist(p.sub(0.32, -0.45, 0.5, rot=30), c, dk)
    hit = tint(c, 0.5)
    for a, ln in ((-60, 0.3), (-20, 0.38), (20, 0.3)):
        r = math.radians(a)
        x0, y0 = 0.38 + math.cos(r) * 0.25, 0.05 + math.sin(r) * 0.25
        p.line([(x0, y0), (x0 + math.cos(r) * ln, y0 + math.sin(r) * ln)], hit, 0.09)
    p.arc(-0.1, 0.25, 0.7, -80, -10, tint(c, -0.3), 0.08)


def calm_breath_stance(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    figure(p.sub(0, 0.22, 0.78), c, dk, "seated")
    p.spiral(0.0, -0.6, 0.4, tint(c, 0.4), 0.08, turns=1.4)


# ── Yellow ──────────────────────────────────────────────────────────────

def _claw_hand(p, c, dk):
    p.rrect(-0.27, 0.62, 0.27, 1.0, 0.05, dk)
    p.poly([(-0.5, -0.05), (0.5, -0.05), (0.46, 0.5), (0.3, 0.72), (-0.3, 0.72), (-0.48, 0.48)], c)
    for x, top in ((-0.38, -0.5), (-0.12, -0.72), (0.14, -0.74), (0.38, -0.55)):
        p.capsule((x, 0.05), (x, top + 0.1), 0.22, c)
        p.poly([(x - 0.1, top + 0.12), (x + 0.1, top + 0.12), (x + 0.16, top - 0.22)], tint(c, 0.55))
    p.capsule((-0.42, 0.45), (-0.82, 0.0), 0.22, c)
    p.poly([(-0.9, 0.06), (-0.74, -0.08), (-0.98, -0.3)], tint(c, 0.55))


def fierce_tiger_claw(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    _claw_hand(p.sub(-0.22, 0.08, 0.82), c, dk)
    for i in range(3):
        x = 0.42 + i * 0.2
        p.poly([(x, -0.85), (x + 0.07, -0.85), (x + 0.02, 0.55), (x - 0.04, 0.5)], (236, 72, 52))


def _bird(p, x, y, k, c):
    """A swallow: swept wings and a forked tail."""
    p.poly([(x - 0.9 * k, y - 0.25 * k), (x - 0.1 * k, y + 0.05 * k), (x + 0.2 * k, y - 0.1 * k),
            (x + 0.95 * k, y - 0.35 * k), (x + 0.3 * k, y + 0.2 * k), (x + 0.15 * k, y + 0.35 * k),
            (x + 0.05 * k, y + 0.9 * k), (x - 0.05 * k, y + 0.45 * k), (x - 0.3 * k, y + 0.85 * k),
            (x - 0.18 * k, y + 0.25 * k)], c)
    p.circle(x + 0.12 * k, y - 0.02 * k, 0.16 * k, c)


def swift_swallow_kick(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    leg(p.sub(0.08, 0.16, 0.84), c, dk)
    _bird(p, -0.42, -0.58, 0.5, tint(c, 0.45))


def raging_bull_fist(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    horn = tint(c, 0.55)
    for sd in (-1, 1):
        p.poly([(sd * 0.32, -0.25), (sd * 0.72, -0.3), (sd * 0.98, -0.62), (sd * 0.92, -1.0), (sd * 0.8, -0.62),
                (sd * 0.56, -0.48), (sd * 0.32, -0.45)], horn)
    fist(p.sub(0, 0.18, 0.8), c, dk)


def iron_cloth_body(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    torso(p, c, dk)
    sheen = tint(c, 0.6)
    p.poly([(-0.55, -0.35), (-0.38, -0.45), (0.25, 0.55), (0.08, 0.62)], sheen)
    if p.big:
        p.poly([(0.1, -0.5), (0.2, -0.55), (0.48, -0.1), (0.38, -0.05)], sheen)
        p.sparkle(0.62, -0.52, 0.22, WHITE)


def flowing_stream_palm(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    palm(p.sub(0.05, -0.18, 0.76), c, dk)
    water = tint(c, 0.4)
    for i, y in enumerate((0.55, 0.78, 1.0)):
        p.wave(-0.95, 0.95, y, 0.07, water if i != 1 else tint(c, -0.2), 0.09, waves=2, phase=i)


def crane_wing_deflection(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    fe = tint(c, 0.35)
    for i in range(5):
        a = math.radians(200 + i * 22)
        x1, y1 = -0.15 + math.cos(a) * 0.95, 0.35 + math.sin(a) * 0.9
        p.capsule((-0.05, 0.4), (x1, y1), 0.24 - i * 0.015, fe if i % 2 == 0 else tint(c, 0.15))
    p.capsule((-0.05, 0.4), (0.6, -0.45), 0.3, c)
    palm(p.sub(0.68, -0.6, 0.42, rot=35), c, dk)
    p.circle(-0.05, 0.4, 0.2, c)


# ── Mystic ──────────────────────────────────────────────────────────────

def rolling_thunder_palm(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    palm(p.sub(-0.12, 0.08, 0.84), c, dk)
    p.bolt(0.55, -0.38, 0.62, (255, 236, 120), rot=12)
    if p.big:
        p.bolt(0.55, -0.38, 0.4, WHITE, rot=12)


def viper_fang_finger(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    fingers(p.sub(0, 0.14, 0.84), c, dk)
    fang = (244, 240, 226)
    for sd in (-1, 1):
        x = sd * 0.62
        p.poly([(x - 0.17, -0.82), (x + 0.17, -0.82), (x + 0.06, -0.4), (x - sd * 0.02, -0.05), (x - 0.08, -0.45)], fang)
        if p.big:
            p.circle(x - sd * 0.01, -0.02, 0.05, (130, 220, 90))


def autumn_wind_kick(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    p.arc(0.0, 0.1, 0.9, 190, 300, tint(c, -0.3), 0.08)
    leg(p.sub(0.1, 0.12, 0.82), c, dk)
    for x, y, a, col in ((-0.62, -0.52, -30, (226, 120, 50)), (-0.2, -0.82, 40, (236, 172, 60)),
                         (0.62, 0.42, 10, (206, 80, 40))):
        p.leaf(x, y, 0.42, 0.13, a, col, tint(col, -0.4) if p.big else None)


def moon_mirror_palm(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    p.crescent(0.0, -0.1, 0.92, tint(c, 0.55), angle=-25, shift=0.42)
    palm(p.sub(0.06, 0.2, 0.7), c, dk)


def _footprint(p, x, y, k, c, flip=False):
    sd = -1 if flip else 1
    p.ellipse(x, y + 0.12 * k, 0.24 * k, 0.42 * k, c)
    p.ellipse(x - sd * 0.02 * k, y + 0.62 * k, 0.17 * k, 0.17 * k, c)
    for i, (tx, ty, r) in enumerate(((-0.2, -0.42, 0.1), (-0.04, -0.5, 0.085), (0.1, -0.48, 0.075),
                                     (0.21, -0.4, 0.065), (0.28, -0.28, 0.055))):
        p.circle(x + sd * tx * k, y + ty * k, r * k, c)


def drifting_mist_steps(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    mist = tint(c, -0.4)
    for i, y in enumerate((-0.15, 0.35, 0.82)):
        p.wave(-1.0, 1.0, y, 0.06, mist, 0.11, waves=1.5, phase=i * 1.3)
    _footprint(p, -0.36, 0.25, 0.75, c, flip=True)
    _footprint(p, 0.36, -0.35, 0.75, tint(c, 0.15))


def _mountain(p, c, dk, peak=(0.0, -0.3), base=0.98, half=0.98, snow=None):
    px_, py_ = peak
    p.poly([(-half, base), (px_ - 0.35, py_ + 0.42), (px_ - 0.15, py_ + 0.3), (px_, py_), (px_ + 0.25, py_ + 0.3),
            (px_ + 0.55, py_ + 0.18), (half, base)], c)
    if snow is not None:
        p.poly([(px_ - 0.2, py_ + 0.28), (px_, py_), (px_ + 0.22, py_ + 0.27), (px_ + 0.08, py_ + 0.2),
                (px_ - 0.06, py_ + 0.3)], snow)
    p.line([(px_, py_ + 0.05), (px_ - 0.18, base)], dk, 0.06)


def rooted_mountain_stance(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    _mountain(p, tint(c, -0.35), tint(c, -0.6), peak=(0.0, 0.2))
    figure(p.sub(0, -0.42, 0.56), c, dk, "wide")


# ── Earth ───────────────────────────────────────────────────────────────

def mountain_shattering_fist(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    _mountain(p, tint(c, -0.35), tint(c, -0.6), peak=(0.25, -0.15))
    crack = (255, 226, 160)
    p.line([(0.2, -0.05), (0.32, 0.25), (0.15, 0.5), (0.3, 0.75), (0.22, 0.98)], crack, 0.07)
    p.line([(0.32, 0.25), (0.6, 0.45)], crack, 0.05)
    if p.big:
        for x, y in ((0.45, -0.3), (0.05, -0.32), (0.62, -0.05)):
            p.poly([(x, y), (x + 0.1, y - 0.06), (x + 0.07, y + 0.07)], tint(c, -0.1))
    fist(p.sub(-0.42, -0.42, 0.56, rot=-35), c, dk)


def thousand_shadow_palm(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    palm(p.sub(-0.4, 0.02, 0.76), tint(c, -0.62), tint(c, -0.75))
    palm(p.sub(-0.2, 0.04, 0.76), tint(c, -0.4), tint(c, -0.6))
    palm(p.sub(0.18, 0.06, 0.8), c, dk)


def river_splitting_finger(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    water = tint(c, 0.25)
    for sd in (-1, 1):
        p.poly([(sd * 0.25, 1.0), (sd * 0.35, 0.45), (sd * 0.62, 0.05), (sd * 0.98, -0.1), (sd * 0.82, 0.12),
                (sd * 0.98, 0.25), (sd * 0.72, 0.4), (sd * 1.0, 1.0)], water)
        if p.big:
            p.arc(sd * 0.75, 0.62, 0.22, 180 if sd < 0 else 0, 270 if sd < 0 else -90, tint(c, 0.6), 0.05)
    fingers(p.sub(0, -0.12, 0.72), c, dk)


def golden_bell_cover(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    bell = tint(c, 0.2)
    p.capsule((-0.12, -0.9), (0.12, -0.9), 0.16, bell)
    p.poly([(-0.42, -0.78), (0.42, -0.78), (0.62, -0.2), (0.68, 0.55), (0.95, 0.82), (-0.95, 0.82), (-0.68, 0.55),
            (-0.62, -0.2)], bell)
    p.rrect(-1.0, 0.75, 1.0, 0.92, 0.06, tint(c, -0.2))
    figure(p.sub(0, 0.1, 0.56), tint(c, -0.62), tint(c, -0.62))
    if p.big:
        p.line([(-0.58, -0.35), (0.58, -0.35)], tint(c, -0.3), 0.05)
        p.sparkle(0.72, -0.62, 0.22, WHITE)


def ancient_turtle_shell_art(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    p.ellipse(0, 0.05, 0.98, 0.9, tint(c, -0.3))
    p.ellipse(0, 0.05, 0.84, 0.76, c)
    p.ngon(0, 0.05, 6, 0.3, tint(c, 0.3), dk, 0.06, turn=0)
    for i in range(6):
        a = math.radians(i * 60)
        x, y = math.cos(a) * 0.3, 0.05 + math.sin(a) * 0.3
        p.line([(x, y), (math.cos(a) * 0.82, 0.05 + math.sin(a) * 0.74)], dk, 0.07)
    if p.big:
        p.ring(0, 0.05, 0.6, dk, 0.04)


def thousand_hands_deflection(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    n = 7
    for i in range(n):
        a = -78 + i * (156 / (n - 1))
        r = math.radians(a - 90)
        col = c if i == n // 2 else tint(c, -0.15 - abs(i - n // 2) * 0.1)
        palm(p.sub(math.cos(r) * 0.55, 0.62 + math.sin(r) * 0.55, 0.42, rot=a), col, dk)
    p.circle(0, 0.72, 0.2, tint(c, 0.3))


# ── Heaven ──────────────────────────────────────────────────────────────

def heaven_rending_palm(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    rift = (255, 248, 226)
    p.poly([(-0.85, -0.72), (-0.45, -0.88), (-0.2, -0.62), (0.15, -0.95), (0.4, -0.66), (0.82, -0.9), (0.95, -0.6),
            (0.42, -0.42), (0.18, -0.6), (-0.12, -0.36), (-0.42, -0.6), (-0.8, -0.46)], rift)
    if p.big:
        for x in (-0.6, 0.0, 0.6):
            p.line([(x, -0.62), (x * 1.2, -1.0)], tint(c, 0.7), 0.04)
    palm(p.sub(0, 0.28, 0.72), c, dk)


def _dragon(p, c, dk, x, top, bottom, sd=1, amp=0.18):
    """A coiled dragon: a wavy tapering body rising from the bottom, head with horns at the top."""
    n = 14
    pts = [(x + math.sin(i / n * 3.3 * math.pi) * amp * sd, top + (bottom - top) * i / n) for i in range(n + 1)]
    for i in range(n):
        w = 0.26 - 0.16 * i / n
        p.capsule(pts[i], pts[i + 1], w, c)
    if p.big:
        for i in range(1, n, 2):
            p.circle(pts[i][0], pts[i][1], 0.04, tint(c, 0.45))
    hx, hy = pts[0]
    p.poly([(hx - sd * 0.16, hy + 0.12), (hx - sd * 0.1, hy - 0.1), (hx + sd * 0.16, hy - 0.08), (hx + sd * 0.36, hy + 0.04),
            (hx + sd * 0.3, hy + 0.16), (hx + sd * 0.06, hy + 0.2)], c)
    p.line([(hx - sd * 0.06, hy - 0.06), (hx - sd * 0.22, hy - 0.3), (hx - sd * 0.12, hy - 0.4)], tint(c, 0.35), 0.06)
    p.circle(hx + sd * 0.1, hy + 0.0, 0.05, (255, 90, 60))


def nine_dragons_ascending_fist(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    gold = (246, 210, 110)
    _dragon(p, tint(gold, -0.25), dk, -0.66, -0.7, 0.92, sd=-1)
    _dragon(p, gold, dk, 0.66, -0.82, 0.92, sd=1)
    fist(p.sub(0, 0.12, 0.6), c, dk)


def meteor_falling_kick(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    fire = (255, 168, 70)
    for i, off in enumerate((-0.14, 0.0, 0.14)):
        p.line([(-0.92 + off, -0.95 - off), (-0.3 + off * 0.3, -0.42 - off * 0.3)], tint(fire, -0.1 * i), 0.1)
    p.circle(-0.28, -0.38, 0.26, (255, 210, 120))
    if p.big:
        p.circle(-0.32, -0.42, 0.11, WHITE)
    lp = p.sub(0.12, 0.12, 0.88, rot=62)
    leg(lp, c, dk)


def void_mirror_stance(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    p.circle(0, 0, 0.98, tint(c, 0.15))
    p.circle(0, 0, 0.78, VOIDC)
    if p.big:
        p.ring(0, 0, 0.88, tint(c, -0.4), 0.04)
        for a in range(0, 360, 45):
            r = math.radians(a)
            p.circle(math.cos(r) * 0.88, math.sin(r) * 0.88, 0.05, tint(c, 0.6))
    figure(p.sub(0, 0.05, 0.62), c, dk, "wide")


def _lotus(p, x, y, k, c, dk):
    for ang, ln, col in ((-70, 0.62, tint(c, -0.3)), (70, 0.62, tint(c, -0.3)), (-38, 0.8, c), (38, 0.8, c),
                         (0, 0.9, tint(c, 0.25))):
        a = math.radians(ang - 90)
        p.leaf(x + math.cos(a) * ln * k * 0.5, y + math.sin(a) * ln * k * 0.5, ln * k, 0.2 * k, ang - 90, col)


def immortal_lotus_body(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    pink = (246, 170, 190)
    _lotus(p, 0, 0.98, 1.1, pink, dk)
    figure(p.sub(0, -0.25, 0.66), c, dk, "seated")
    if p.big:
        p.ring(0, -0.72, 0.42, tint(c, 0.6), 0.04)


def cloud_walking_shadow(d, cx, cy, s, c, dk):
    p = _pen(d, cx, cy, s)
    cloud = (226, 230, 244)
    figure(p.sub(0.02, -0.22, 0.72), c, dk, "stride")
    p.cloud(-0.42, 0.62, 0.5, cloud, tint(cloud, -0.3) if p.big else None)
    p.cloud(0.5, 0.44, 0.42, tint(cloud, -0.12), tint(cloud, -0.35) if p.big else None)


TECH_ICON = {
    "iron_fist": iron_fist, "twin_palm_strike": twin_palm_strike, "crescent_sweep": crescent_sweep,
    "horse_stance_guard": horse_stance_guard, "parrying_arm": parrying_arm, "calm_breath_stance": calm_breath_stance,
    "fierce_tiger_claw": fierce_tiger_claw, "swift_swallow_kick": swift_swallow_kick,
    "raging_bull_fist": raging_bull_fist, "iron_cloth_body": iron_cloth_body,
    "flowing_stream_palm": flowing_stream_palm, "crane_wing_deflection": crane_wing_deflection,
    "rolling_thunder_palm": rolling_thunder_palm, "viper_fang_finger": viper_fang_finger,
    "autumn_wind_kick": autumn_wind_kick, "moon_mirror_palm": moon_mirror_palm,
    "drifting_mist_steps": drifting_mist_steps, "rooted_mountain_stance": rooted_mountain_stance,
    "mountain_shattering_fist": mountain_shattering_fist, "thousand_shadow_palm": thousand_shadow_palm,
    "river_splitting_finger": river_splitting_finger, "golden_bell_cover": golden_bell_cover,
    "ancient_turtle_shell_art": ancient_turtle_shell_art, "thousand_hands_deflection": thousand_hands_deflection,
    "heaven_rending_palm": heaven_rending_palm, "nine_dragons_ascending_fist": nine_dragons_ascending_fist,
    "meteor_falling_kick": meteor_falling_kick, "void_mirror_stance": void_mirror_stance,
    "immortal_lotus_body": immortal_lotus_body, "cloud_walking_shadow": cloud_walking_shadow,
}
SCHOOL_ICON = {name: school(name) for name in BASE}


def tech_key(name):
    """'Mountain-Shattering Fist' → 'mountain_shattering_fist' (the keys of technique.TECHNIQUES)."""
    return "".join(ch if ch.isalnum() else "_" for ch in (name or "").lower()).strip("_")


def tech_kind(name, school="Body"):
    """theme.icon kind for a technique by name: its own icon, or its school's base shape if unknown."""
    key = tech_key(name)
    return "tech:" + key if key in TECH_ICON else "school:" + (school if school in SCHOOL_ICON else "Body")
