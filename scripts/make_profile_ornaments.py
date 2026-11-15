"""Vector ornaments for the profile page (art/ui/*.svg), drawn from code so they stay sharp on every screen.

  qi_aura_back.svg   the portrait's backdrop: jade mist lit from above, rays, xiangyun cloud curls each side
  qi_aura_front.svg  translucent Qi ribbons that sweep around (and over) the character
  jade_gem_on.svg / jade_gem_off.svg   a layer: a carved jade egg with lotus petals, lit or dormant
  qi_ribbon.svg      the carved jade scroll that rides the Internal Qi bar

The character is always the player's own picture; these only go behind and around it.
Run: python scripts/make_profile_ornaments.py
"""
import math
import os

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art", "ui")


def f(x):
    return f"{x:.1f}"


def spiral(cx, cy, r0, turns, scale=1.0, flip=False, rot=0.0, n=60):
    """A cloud curl: an inward spiral as a smooth polyline path."""
    pts = []
    for i in range(n + 1):
        t = i / n
        a = rot + (1 if not flip else -1) * t * turns * 2 * math.pi
        r = r0 * (1 - 0.82 * t)
        pts.append((cx + math.cos(a) * r * scale, cy + math.sin(a) * r))
    return "M" + " L".join(f"{f(x)} {f(y)}" for x, y in pts)


def wave(x0, y0, x1, y1, amp, waves, n=80, phase=0.0):
    pts = []
    for i in range(n + 1):
        t = i / n
        x = x0 + (x1 - x0) * t
        y = y0 + (y1 - y0) * t + math.sin(phase + t * waves * 2 * math.pi) * amp * math.sin(t * math.pi)
        pts.append((x, y))
    return "M" + " L".join(f"{f(x)} {f(y)}" for x, y in pts)


def aura_back():
    W, H = 550, 560
    curls = []
    for (cx, cy, r, turns, flip, rot, w, op) in [
        (70, 150, 70, 1.6, False, 3.4, 16, .55), (40, 330, 55, 1.5, True, 1.0, 13, .45), (95, 470, 80, 1.7, False, 4.6, 18, .5),
        (480, 170, 75, 1.6, True, 0.2, 16, .55), (510, 360, 58, 1.5, False, 2.2, 13, .45), (455, 480, 85, 1.7, True, 5.0, 18, .5),
        (160, 70, 40, 1.4, True, 2.0, 9, .35), (390, 60, 44, 1.4, False, 1.2, 9, .35)]:
        d = spiral(cx, cy, r, turns, flip=flip, rot=rot)
        curls.append(f'<path d="{d}" stroke="#7FE3C2" stroke-width="{w * 2.6:.1f}" stroke-linecap="round" fill="none" opacity="{op * .35:.2f}" filter="url(#mist)"/>'
                     f'<path d="{d}" stroke="url(#jade)" stroke-width="{w * 1.5:.1f}" stroke-linecap="round" fill="none" opacity="{op}" filter="url(#soft)"/>'
                     f'<path d="{d}" stroke="#D9FFF0" stroke-width="{max(1.5, w * .14):.1f}" stroke-linecap="round" fill="none" opacity="{op * .8:.2f}"/>')
    rays = "".join(f'<path d="M{275 + dx} -20 L{275 + dx * 3.2 - 40} {H} L{275 + dx * 3.2 + 40} {H} Z" fill="#BFF8E2" opacity="{op}"/>'
                   for dx, op in [(-60, .05), (-20, .07), (25, .06), (70, .045)])
    motes = "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#DFFFF3" opacity="{o}" filter="url(#glow)"/>'
                    for x, y, r, o in [(120, 220, 2.5, .8), (430, 260, 2, .7), (200, 120, 1.6, .6), (360, 400, 2.2, .7), (90, 400, 1.8, .6),
                                       (470, 100, 1.6, .6), (300, 90, 1.4, .5), (250, 480, 2, .5), (150, 520, 1.6, .5), (420, 530, 2, .6)])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">
<defs>
<radialGradient id="bg" cx="50%" cy="38%" r="75%"><stop offset="0" stop-color="#8FE6CF"/><stop offset=".22" stop-color="#3FA48F"/><stop offset=".5" stop-color="#1A5552"/><stop offset=".8" stop-color="#0E2A30"/><stop offset="1" stop-color="#091B21"/></radialGradient>
<radialGradient id="halo" cx="50%" cy="40%" r="40%"><stop offset="0" stop-color="#E6FFF6" stop-opacity=".55"/><stop offset="1" stop-color="#E6FFF6" stop-opacity="0"/></radialGradient>
<linearGradient id="jade" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#B8F7DE"/><stop offset=".5" stop-color="#49C79F"/><stop offset="1" stop-color="#1E7A62"/></linearGradient>
<linearGradient id="floor" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0B1E22" stop-opacity="0"/><stop offset="1" stop-color="#081519" stop-opacity=".85"/></linearGradient>
<filter id="soft" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="3.5"/></filter>
<filter id="mist" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="18"/></filter>
<filter id="glow" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="2"/></filter>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg)"/>
{rays}
<ellipse cx="275" cy="220" rx="190" ry="210" fill="url(#halo)"/>
<g filter="url(#mist)" opacity=".55"><ellipse cx="80" cy="300" rx="110" ry="60" fill="#5FCFAE"/><ellipse cx="470" cy="300" rx="110" ry="60" fill="#5FCFAE"/><ellipse cx="275" cy="520" rx="260" ry="50" fill="#9FE9D0"/></g>
{"".join(curls)}
{motes}
<rect y="{H * .6:.0f}" width="{W}" height="{H * .4:.0f}" fill="url(#floor)"/>
</svg>'''


def aura_front():
    W, H = 550, 560
    ribbons = []
    for (x0, y0, x1, y1, amp, waves, ph, w, op) in [
        (-20, 380, 570, 300, 60, 1.2, 0.3, 10, .5), (-20, 200, 260, 120, 40, 1.0, 1.2, 7, .45), (300, 470, 570, 380, 45, 1.1, 2.0, 8, .45),
        (520, 120, 360, 30, 30, .8, .5, 5, .35)]:
        d = wave(x0, y0, x1, y1, amp, waves, phase=ph)
        ribbons.append(f'<path d="{d}" stroke="url(#rib)" stroke-width="{w}" stroke-linecap="round" fill="none" opacity="{op}" filter="url(#s)"/>'
                       f'<path d="{d}" stroke="#E8FFF7" stroke-width="1.4" fill="none" opacity="{op * .9:.2f}"/>')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice">
<defs>
<linearGradient id="rib" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#7FF0C3" stop-opacity="0"/><stop offset=".3" stop-color="#9CF5D2"/><stop offset=".7" stop-color="#4FCB9F"/><stop offset="1" stop-color="#7FF0C3" stop-opacity="0"/></linearGradient>
<filter id="s" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="2.2"/></filter>
</defs>
{"".join(ribbons)}
</svg>'''


def gem(lit):
    """A carved jade egg: outer shell, three rows of lotus petals in relief, a glowing core when lit."""
    if lit:
        shell = ("#9BF7D3", "#2BB386", "#0B5A43"); edge = "#C9FFEA"; petal = "#7DEBC2"; vein = "#E4FFF5"; core = 1
    else:
        shell = ("#3B5550", "#1B2B28", "#0B1412"); edge = "#4E6E66"; petal = "#2C4440"; vein = "#5E7F77"; core = 0
    egg = "M30 2 C46 2 56 22 56 40 C56 58 44 70 30 70 C16 70 4 58 4 40 C4 22 14 2 30 2 Z"
    petals = []
    for row, (y, rx, ry, n, spread) in enumerate([(56, 9, 16, 5, 34), (46, 8, 14, 4, 26), (36, 7, 12, 3, 16)]):
        for k in range(n):
            x = 30 + (k - (n - 1) / 2) * (spread * 2 / max(n - 1, 1)) * .9
            ang = (x - 30) * 1.2
            tip = y - ry * 1.7                         # a lotus petal: rounded base, pointed tip
            d = (f"M{f(x)} {y} Q{f(x - rx * 1.3)} {f(y - ry * .7)} {f(x)} {f(tip)} Q{f(x + rx * 1.3)} {f(y - ry * .7)} {f(x)} {y} Z")
            petals.append(f'<path d="{d}" transform="rotate({f(ang)} {f(x)} {y})" fill="{petal}" fill-opacity=".6" '
                          f'stroke="{vein}" stroke-opacity=".7" stroke-width=".9"/>')
    glow = ('<circle cx="30" cy="34" r="11" fill="url(#core)"/><circle cx="30" cy="34" r="22" fill="url(#core)" opacity=".5"/>' if core else "")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 60 72">
<defs>
<radialGradient id="sh" cx="38%" cy="30%" r="75%"><stop offset="0" stop-color="{shell[0]}"/><stop offset=".55" stop-color="{shell[1]}"/><stop offset="1" stop-color="{shell[2]}"/></radialGradient>
<radialGradient id="core"><stop offset="0" stop-color="#FFFFFF"/><stop offset=".35" stop-color="#C8FFEC" stop-opacity=".9"/><stop offset="1" stop-color="#7FF0C3" stop-opacity="0"/></radialGradient>
<clipPath id="c"><path d="{egg}"/></clipPath>
</defs>
<path d="{egg}" fill="url(#sh)"/>
<g clip-path="url(#c)">{"".join(petals)}{glow}</g>
<path d="{egg}" fill="none" stroke="{edge}" stroke-opacity=".8" stroke-width="1.4"/>
<ellipse cx="21" cy="16" rx="6" ry="9" fill="#FFFFFF" opacity="{.35 if lit else .12}" transform="rotate(-25 21 16)"/>
</svg>'''


def ribbon():
    """A carved jade scroll band: a wave with curled ends and a central knot, beveled with highlights."""
    W, H = 600, 64
    top = wave(30, 32, 570, 32, 11, 2.0, phase=0.0)
    curls = []
    for cx, cy, r, flip, rot in [(30, 32, 18, True, 0.0), (570, 32, 18, False, math.pi), (300, 26, 14, False, 1.0), (300, 38, 12, True, 4.0),
                                 (160, 40, 10, True, 2.0), (440, 22, 10, False, 5.0)]:
        curls.append(spiral(cx, cy, r, 1.3, flip=flip, rot=rot, n=40))
    body = "".join(f'<path d="{d}" stroke="url(#j)" stroke-width="{w}" stroke-linecap="round" fill="none"/>'
                   for d, w in [(top, 20)] + [(c, 9) for c in curls])
    hi = "".join(f'<path d="{d}" stroke="#E9FFF7" stroke-width="{w}" stroke-linecap="round" fill="none" opacity=".75" transform="translate(0,-2)"/>'
                 for d, w in [(top, 3)] + [(c, 1.6) for c in curls])
    lo = f'<path d="{top}" stroke="#0A3A2C" stroke-width="3" fill="none" opacity=".6" transform="translate(0,4)"/>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" preserveAspectRatio="none">
<defs>
<linearGradient id="j" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#B9F8DF"/><stop offset=".45" stop-color="#3FBE95"/><stop offset="1" stop-color="#14684F"/></linearGradient>
<filter id="g" x="-10%" y="-60%" width="120%" height="220%"><feGaussianBlur stdDeviation="4"/></filter>
</defs>
<g filter="url(#g)" opacity=".6">{body}</g>
{lo}{body}{hi}
</svg>'''


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, svg in [("qi_aura_back", aura_back()), ("qi_aura_front", aura_front()), ("jade_gem_on", gem(True)),
                      ("jade_gem_off", gem(False)), ("qi_ribbon", ribbon())]:
        with open(os.path.join(OUT, name + ".svg"), "w") as fh:
            fh.write(svg)
        print(name, len(svg))


if __name__ == "__main__":
    main()
