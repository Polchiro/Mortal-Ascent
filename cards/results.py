"""
The /spar and /train (/practice) result cards, in the painted encounter style: the hall or the courtyard fills
the card, text sits on soft shade, no boxes. Same data as before (bot/result_cards.py: spar_data, train_data).

  render_spar(data)    the Master in the dawn hall; the crest and the word; you and him; mastery gained
  render_train(data)   the courtyard at sunset; the reward; progress; the score ring
"""
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import ink as K
from . import theme as T
from . import victory as V
from .activity import clean, fmt_num, note_lines
from .battle import _art
from .scenes import REGION, photo, subject
from .theme import P, S, alpha, font, mix

W, H = 1200, 760
WARM = (244, 236, 222)
MUTED = (186, 176, 164)
DIM = (140, 130, 120)
GOLD = (246, 200, 96)
EMBER = (226, 80, 64)
STEEL = (150, 186, 236)
JADE = (120, 220, 160)


def _fill(img, mask, color, a=255):
    layer = Image.new("RGBA", img.size, color + (0,))
    layer.putalpha(mask.point(lambda v: round(v * a / 255)))
    img.alpha_composite(layer)


def _canvas(scene, fallback=(18, 14, 14)):
    img = Image.new("RGBA", (W * S, H * S), fallback + (255,))
    sc = photo(scene, W * S, H * S)
    if sc is not None:
        img.alpha_composite(sc)
    w, h = img.size
    left = Image.linear_gradient("L").rotate(90, expand=True).resize((w, h)).point(
        lambda v: min(255, round(max(0, v - 60) * 2.1)))
    bottom = Image.linear_gradient("L").resize((w, h)).point(lambda v: round(max(0, v - 150) * 2.2))
    m = ImageChops.lighter(left, bottom).filter(ImageFilter.GaussianBlur(10 * S))
    _fill(img, m, (8, 6, 8), 236)
    return img


def _spaced(d, xy, s, size, color, anchor="l", weight="Bold", tracking=3.0):
    T.spaced(d, xy, s, font("Inter.ttf", size, weight), color, tracking, anchor)


def _cooldown(img, label):
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 24, "SemiBold")
    x1 = W - 48
    T.text(d, (x1, 60), label, f, WARM, "rm")
    T.icon(img, "hourglass", (x1 - T.width(d, label, f) - 22, 60), 24, GOLD)


def _bar_row(img, y, name, hp, mx, color, icon):
    d = ImageDraw.Draw(img)
    T.text(d, (48, y), name, font("Inter.ttf", 28, "Black"), WARM, "lm")
    frac = max(0, hp) / mx if mx else 0
    K.ornate_bar(img, (66, y + 26, 520, y + 66), frac, color, icon, f"{max(0, round(hp)):,} / {round(mx):,}")
    d = ImageDraw.Draw(img)
    T.text(d, (562, y + 47), f"{frac:.0%}", font("Inter.ttf", 32, "Black"), WARM, "lm")


def _notes(img, lines, y, y_max, width=640, size=23):
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", size, "Medium")
    for text, muted in lines:
        for line in T.wrap(d, text, f, width, lines=2):
            if y > y_max:
                return y
            T.text(d, (48, y), line, f, DIM if muted else MUTED, "lm")
            y += size + 11
    return y


def _person(img, name, height, cx, bottom, dim=0.0):
    """A painted figure (art/scenes/<name>.png, else art/beasts/<name>.png) standing on the card's floor."""
    art = subject(name) or _art(name)
    if art is None:
        return
    h = round(height * S)
    art = art.resize((round(art.size[0] * h / art.size[1]), h), Image.LANCZOS)
    if dim:
        shade = Image.new("RGBA", art.size, (6, 4, 6, 0))
        shade.putalpha(art.getchannel("A").point(lambda v: round(v * dim)))
        art.alpha_composite(shade)
    glow = Image.new("RGBA", art.size, (255, 214, 150, 0))
    glow.putalpha(art.getchannel("A").filter(ImageFilter.GaussianBlur(14 * S)).point(lambda v: round(v * 0.35)))
    x, y = round(cx * S - art.size[0] / 2), round(bottom * S - art.size[1])
    img.alpha_composite(glow, (x, y))
    img.alpha_composite(art, (x, y))


# ── /spar ─────────────────────────────────────────────────────────────

OUTCOME = {"victory": ("Victory", GOLD), "defeat": ("Defeat", EMBER), "forfeit": ("Forfeit", (170, 170, 180))}


def render_spar(data):
    """data: name, realm, layer, title, outcome (victory/defeat/forfeit), turn, max_turns, hp, max_hp,
    m_hp, m_max, gains [{name, type, exp}], timed, notes [str], cooldown (str)."""
    img = _canvas("spar_hall_dawn")
    outcome = data["outcome"]
    word, color = OUTCOME.get(outcome, (outcome.title(), GOLD))
    _person(img, "master_approve" if outcome == "victory" else "master_stern", 700, 930, H + 4)
    _cooldown(img, data.get("cooldown") or "")
    # crest and word
    has_crest = V.crest(img, (140, 168), 200, outcome)
    tx = 262 if has_crest else 48
    d = ImageDraw.Draw(img)
    _spaced(d, (tx + 2, 96), "SPAR WITH THE MASTER", 20, mix(color, WARM, 0.4))
    T.gold_text(img, (tx, 166), word, font("Cinzel.ttf", 84, "Bold"), "lm",
                top=mix(color, (255, 255, 255), 0.6), bottom=mix(color, (0, 0, 0), 0.25))
    d = ImageDraw.Draw(img)
    sub = f"Exchange {min(data['turn'], data['max_turns'])} of {data['max_turns']}"
    title = clean(data.get("title") or "")[0]
    if title and "spar" not in title.lower():
        sub = f"{title}  ·  {sub}"
    T.text(d, (tx + 2, 232), T.fit(d, sub, font("Inter.ttf", 26, "Medium"), 760 - tx), font("Inter.ttf", 26, "Medium"),
           MUTED, "lm")
    # you and him
    _bar_row(img, 304, data["name"], data["hp"], data["max_hp"], (196, 70, 58), "heart")
    _bar_row(img, 396, "The Master", data["m_hp"], data["m_max"], (92, 120, 170), "school:Palm")
    # mastery gained
    d = ImageDraw.Draw(img)
    y = 506
    _spaced(d, (48, y), "MASTERY GAINED", 20, MUTED, tracking=3)
    gains = data["gains"][:3]
    y += 46
    if gains:
        for g in gains:
            f = font("Inter.ttf", 30, "Bold")
            T.icon(img, "fist" if g["type"] == "attack" else "shield", (62, y), 28,
                   (236, 170, 110) if g["type"] == "attack" else STEEL)
            d = ImageDraw.Draw(img)
            T.text(d, (92, y), T.fit(d, g["name"], f, 380), f, WARM, "lm")
            T.text(d, (620, y), f"+{g['exp']:,} EXP", font("Cinzel.ttf", 32, "Bold"), GOLD, "rm")
            y += 50
    else:
        if outcome == "forfeit":
            msg = "You walked away, so no mastery EXP this time."
        elif data.get("timed"):
            msg = "No mastery EXP this time."
        else:
            msg = "No technique landed at the right moment, so no mastery EXP."
        y = _notes(img, [(msg, False)], y, y + 40, 600, 26) + 6
    # the bout, in a line or two
    lines = [ln for ln in note_lines(data["notes"]) if "EXP" not in ln[0] or "×" in ln[0]]
    _notes(img, lines[-2:], max(y + 8, 668), H - 24, 560, 22)
    return T.finish(img)


# ── /train and /practice ──────────────────────────────────────────────

def _ring(img, center, r, score, color):
    cx, cy = center
    T.soft_glow(img, (cx - r - 50, cy - r - 50, cx + r + 50, cy + r + 50), alpha(color, round(40 + 110 * score)), 40)
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r - 14, cy - r - 14, cx + r + 14, cy + r + 14), fill=(10, 8, 9, 225))
    d.arc(P(cx - r, cy - r, cx + r, cy + r), 0, 360, fill=(52, 44, 40, 255), width=round(r * 0.11 * S))
    if score > 0:
        d.arc(P(cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * score, fill=color + (255,), width=round(r * 0.11 * S))
    d.ellipse(P(cx - r * 0.86, cy - r * 0.86, cx + r * 0.86, cy + r * 0.86), outline=(200, 160, 90, 150), width=max(1, S))
    T.gold_text(img, (cx, cy - r * 0.08), f"{score:.0%}", font("Cinzel.ttf", round(r * 0.5), "Bold"), "mm",
                top=mix(color, (255, 255, 255), 0.6), bottom=mix(color, (0, 0, 0), 0.2))
    d = ImageDraw.Draw(img)
    _spaced(d, (cx, cy + r * 0.4), "SCORE", max(14, round(r * 0.16)), MUTED, "m", tracking=3)


def render_train(data):
    """data: name, realm, layer, mode (train/practice), title, challenge, score, conditions [str],
    reward: train → {qi, total, need, realm, layer}; practice → {technique, exp, total, cap},
    notes [str], cooldown (str)."""
    img = _canvas("practice_courtyard_sunset")
    practice = data["mode"] == "practice"
    score = max(0.0, min(1.0, data["score"]))
    low = score < 0.5
    pose = "master_stern" if low else ("master_teach" if practice else "master_approve")
    _person(img, pose, 660, 940 if practice else 950, H + 4)
    ring_col = EMBER if low else (GOLD if not practice else JADE)
    _cooldown(img, data.get("cooldown") or "")
    d = ImageDraw.Draw(img)
    kicker = " · ".join([data["challenge"]] + list(data["conditions"]))
    _spaced(d, (48, 60), T.fit(d, kicker.upper(), font("Inter.ttf", 20, "Bold"), 640), 20, mix(GOLD, WARM, 0.4))
    T.gold_text(img, (46, 134), "Practice Complete" if practice else "Training Complete",
                font("Cinzel.ttf", 64, "Bold"), "lm", top=(255, 236, 190), bottom=(196, 146, 70))
    # the reward
    rw = data["reward"]
    if practice:
        big, unit, line = f"+{rw['exp']:,}", "mastery EXP", rw["technique"]
        frac = rw["total"] / rw["cap"] if rw["cap"] else 1
        value = f"{rw['total']:,} / {rw['cap']:,}" if rw["cap"] else f"{rw['total']:,}  ·  final stage"
        caption, icon, bar_col = "Mastery toward the next stage", "scroll", (64, 150, 110)
    else:
        big, unit = f"+{fmt_num(rw['qi'])}", "Internal Qi"
        line = f"{rw['realm']}  ·  {T.ordinal(rw['layer'])} Layer"
        frac = rw["total"] / rw["need"] if rw["need"] else 1
        value = f"{fmt_num(rw['total'])} / {fmt_num(rw['need'])}"
        caption, icon, bar_col = "Internal Qi toward the next layer", "lotus", (170, 120, 60)
    d = ImageDraw.Draw(img)
    fb = font("Cinzel.ttf", 80, "Bold")
    T.gold_text(img, (46, 260), big, fb, "lm", top=(255, 240, 200), bottom=(214, 160, 70))
    d = ImageDraw.Draw(img)
    T.text(d, (64 + T.width(d, big, fb), 270), unit, font("Inter.ttf", 32, "Bold"), WARM, "lm")
    T.text(d, (48, 334), T.fit(d, line, font("Inter.ttf", 28, "Medium"), 640), font("Inter.ttf", 28, "Medium"),
           MUTED, "lm")
    K.ornate_bar(img, (66, 380, 600, 422), max(0.0, min(1.0, frac)), bar_col, icon, value)
    d = ImageDraw.Draw(img)
    T.text(d, (48, 452), caption, font("Inter.ttf", 22, "Medium"), DIM, "lm")
    # the score: a ring and what it earned
    _ring(img, (118, 566), 64, score, ring_col)
    d = ImageDraw.Draw(img)
    msg = "Below 50%: only 10% reward" if low else ("A flawless session" if score >= 1 else "Full reward earned")
    T.text(d, (214, 548), msg, font("Inter.ttf", 30, "Bold"), (255, 150, 120) if low else WARM, "lm")
    if data["conditions"]:
        n = len(data["conditions"])
        T.text(d, (214, 588), f"+15% from {n} condition{'s' if n > 1 else ''}", font("Inter.ttf", 24, "Medium"),
               MUTED, "lm")
    # the session, in a line or two
    lines = note_lines(data["notes"]) or [("A quiet session. The master nods and walks away.", True)]
    _notes(img, lines, 672, H - 20, 600, 23)
    return T.finish(img)


# ── /explore: the expedition's end ────────────────────────────────────

def render_explore(data):
    """data: name, realm, layer, region, defeated, step, max_steps, hp, max_hp, coins, items, lost, beasts,
    story [str], notes [str], cooldown (str)."""
    img = _canvas(REGION.get(data.get("region"), ""), (16, 14, 12))
    defeated = data["defeated"]
    if defeated:
        veil = Image.new("RGBA", img.size, (40, 4, 4, 90))
        img.alpha_composite(veil)
    color = EMBER if defeated else GOLD
    _cooldown(img, data.get("cooldown") or "")
    V.crest(img, (124, 150), 180, "lost" if defeated else "won")
    d = ImageDraw.Draw(img)
    tx = 236
    region = data.get("region") or "The Wilds"
    _spaced(d, (tx + 2, 86), f"EXPEDITION  ·  {region.upper()}", 20, mix(color, WARM, 0.4))
    T.gold_text(img, (tx, 150), "Expedition Failed" if defeated else "You Return Safely",
                font("Cinzel.ttf", 62, "Bold"), "lm",
                top=mix(color, (255, 255, 255), 0.6), bottom=mix(color, (0, 0, 0), 0.25))
    d = ImageDraw.Draw(img)
    T.text(d, (tx + 2, 212), f"{data['name']}  ·  {data['realm']}, {T.ordinal(data['layer'])} Layer",
           font("Inter.ttf", 26, "Medium"), MUTED, "lm")
    # the trail: how deep you went
    n, reached = data["max_steps"], data["step"]
    y = 304
    x0, x1 = 70, 600
    seg = (x1 - x0) / max(1, n - 1)
    d.line(P(x0, y, x1, y), fill=(70, 60, 52, 255), width=round(4 * S))
    if reached > 1:
        d.line(P(x0, y, x0 + seg * (min(reached, n) - 1), y), fill=color + (255,), width=round(4 * S))
    for i in range(n):
        cx = x0 + seg * i
        on, last = i < reached, i == reached - 1
        if last:
            T.soft_glow(img, (cx - 34, y - 34, cx + 34, y + 34), alpha(color, 170), 12)
            d = ImageDraw.Draw(img)
        r = 15 if last else 11
        d.ellipse(P(cx - r, y - r, cx + r, y + r), fill=(color if on else (24, 20, 18)) + (255,),
                  outline=(255, 226, 170, 255) if on else (90, 80, 70, 255), width=round(2 * S))
        T.text(d, (cx, y + 38), f"Step {i + 1}", font("Inter.ttf", 21, "Bold" if last else "SemiBold"),
               WARM if on else DIM, "mm")
    # HP, on the right
    _spaced(d, (680, y - 46), "HEALTH", 20, MUTED, tracking=3)
    frac = max(0, data["hp"]) / data["max_hp"] if data["max_hp"] else 0
    K.ornate_bar(img, (698, y - 20, 1036, y + 20), frac, (214, 64, 52) if frac <= 0.25 else (196, 70, 58), "heart",
                 f"{max(0, round(data['hp'])):,} / {data['max_hp']:,}")
    d = ImageDraw.Draw(img)
    T.text(d, (1152, y), f"{frac:.0%}", font("Inter.ttf", 32, "Black"), WARM, "rm")
    # the spoils on the silk cloth
    y = 392
    _spaced(d, (48, y), "SPOILS", 20, MUTED, tracking=3)
    beasts = data["beasts"]
    slain = f"{beasts} beast{'s' if beasts != 1 else ''} slain"
    T.icon(img, "skull", (W - 48 - T.width(d, slain, font("Inter.ttf", 24, "SemiBold")) - 24, y), 24,
           (220, 200, 180) if beasts else DIM)
    d = ImageDraw.Draw(img)
    T.text(d, (W - 48, y), slain, font("Inter.ttf", 24, "SemiBold"), WARM if beasts else DIM, "rm")
    tiles = ([{"name": "Lotus Coins", "label": f"+{data['coins']:,} coins", "icon": "lotus", "color": (240, 196, 110)}]
             if data["coins"] else [])
    tiles += list(data["items"]) + [dict(it, lost=True) for it in data["lost"]]
    extra = max(0, len(tiles) - 6)
    V.spoils(img, (70, 416, 1130, 652), tiles[:6] if not extra else tiles[:5], max_n=6)
    d = ImageDraw.Draw(img)
    if extra:
        T.text(d, (1040, 506), f"+{len(tiles) - 5} more", font("Inter.ttf", 24, "Bold"), (250, 220, 150), "mm")
    # the last step, in a line or two
    lines = note_lines(data["story"])[-1:] + note_lines(data["notes"])[:1]
    y = 680
    if lines:
        d.line(P(48, y - 14, 48, y + 34 * min(2, len(lines)) - 20), fill=color + (255,), width=round(4 * S))
        f = font("Inter.ttf", 24, "Medium")
        for text, muted in lines[:2]:
            T.text(d, (66, y), T.fit(d, text, f, W - 120), f, DIM if muted else WARM, "lm")
            y += 34
    return T.finish(img)
