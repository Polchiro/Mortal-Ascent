"""
Result cards for /spar, /train (and /practice) and /explore, in the Character Sheet frame.

Each activity keeps the same black stone, bronze-and-gold frame and Cinzel headings as the
Character Sheet, with its own accent colour (see theme.ACCENTS):

    /spar      steel blue     render_spar(data)
    /train     jade green     render_train(data)
    /explore   amber          render_explore(data)

The data dicts are built in bot/views.py (spar, train) and bot/expedition.py (explore)
when the activity ends. Text from the game (story lines, notes) may contain Discord
markdown and emoji; clean() turns it into plain text the card fonts can draw.
"""
import re
import unicodedata

from PIL import ImageDraw

from . import theme as t
from .theme import P, font, short

H = 640           # spar and train; explore is taller to fit up to 8 item tiles
H_EXPLORE = 720
SEAL = {"spar": "sword", "train": "school:Fist", "explore": "gear:compass"}   # drawn icons
BANNER = {"spar": "SPARRING  ·  RESULT", "train": "TRAINING GROUND  ·  RESULT", "explore": "EXPEDITION  ·  RESULT"}


# ── Text from the game → plain card text ──────────────────────────────

def clean(s):
    """Strip Discord markdown and emoji. Returns (text, muted): muted for lines written in *italics*."""
    s = (s or "").strip()
    muted = s.startswith("*") and not s.startswith("**")
    s = s.replace("**", "").replace("*", "").replace("__", "").replace("→", "to")
    s = "".join(ch for ch in s if unicodedata.category(ch) not in ("So", "Cs", "Mn") and ch not in "‍️")
    s = re.sub(r"\s+", " ", s).strip(" ·")
    return s, muted


def note_lines(raw):
    """Game text (strings, possibly multi-line) → [(text, muted)] without empty lines."""
    out = []
    for block in raw:
        for line in (block or "").split("\n"):
            txt, muted = clean(line)
            if txt:
                out.append((txt, muted))
    return out


def fmt_num(n):
    if n >= 10000:
        return short(n)
    return f"{n:,.0f}" if n >= 100 or float(n).is_integer() else f"{n:,.1f}"


# ── Shared pieces ─────────────────────────────────────────────────────

def base(kind, seed, h=H):
    """Canvas, banner and frame in the activity's accent."""
    acc = t.ACCENTS[kind]
    img = t.canvas(t.W, h, seed=seed, accent=kind)
    t.banner(img, (0, 0, t.W, 46), acc)
    d = ImageDraw.Draw(img)
    t.spaced(d, (t.W / 2, 23), BANNER[kind], font("Cinzel.ttf", 15, "Bold"), t.GOLD_HI, 3, "m")
    t.frame(img, (6, 52, t.W - 6, h - 6))
    return img, acc


def header(img, kind, acc, title, sub, badge=None, title_color=None):
    """Seal medallion, big gold title, a subtitle and an optional cooldown badge on the right."""
    t.seal(img, (84, 118), 44, SEAL[kind], acc.main)
    t.gold_text(img, (148, 76), title.upper(), font("Cinzel.ttf", 38, "Black"), glow=title_color or acc.main)
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 16, "Medium")
    right = 1170
    if badge:
        right = cooldown_badge(img, badge, (1170, 92)) - 20
        d = ImageDraw.Draw(img)
    t.text(d, (150, 146), t.fit(d, sub, f, right - 150), f, t.ASH, "lm")


def cooldown_badge(img, label, anchor):
    """A rounded pill with an hourglass, right-aligned at anchor. Returns its left edge."""
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 14, "SemiBold")
    w = t.width(d, label, f) + 54
    x1, cy = anchor
    x0 = x1 - w
    d.rounded_rectangle(P(x0, cy - 17, x1, cy + 17), radius=round(17 * t.S), fill=(12, 8, 9, 235),
                        outline=t.alpha(t.BRONZE, 230), width=max(1, t.S))
    t.icon(img, "hourglass", (x0 + 22, cy), 16, t.GOLD)
    d = ImageDraw.Draw(img)
    t.text(d, (x0 + 38, cy), label, f, t.PARCHMENT, "lm")
    return x0


def stat_bar(img, box, label, value, frac, color, value_color=None):
    """Label on the left, value on the right, a bar underneath."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    t.spaced(d, (x0, y0 + 8), label.upper(), font("Cinzel.ttf", 13, "Bold"), t.GOLD, 1.6)
    t.text(d, (x1, y0 + 8), value, font("Inter.ttf", 15, "Bold"), value_color or t.PARCHMENT, "rm")
    t.bar(img, (x0, y0 + 24, x1, y1), frac, color)


def notes_block(img, box, lines, max_lines, f_size=15, accent=None):
    """Wrapped lines with a small diamond bullet each. Muted lines are drawn in ash."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", f_size, "Medium")
    step = f_size + 9
    y, used = y0, 0
    for txt, muted in lines:
        wrapped = t.wrap(d, txt, f, x1 - x0 - 22, lines=3)
        if used + len(wrapped) > max_lines:
            wrapped = wrapped[:max(0, max_lines - used)]
            if not wrapped:
                break
            wrapped[-1] = t.fit(d, wrapped[-1] + " …", f, x1 - x0 - 22)
        t.stud(d, x0 + 5, y + step / 2 - 2, 4 if not muted else 3)
        for i, line in enumerate(wrapped):
            t.text(d, (x0 + 20, y + step / 2 - 2), line, f, t.ASH if muted else t.PARCHMENT, "lm")
            y += step
            used += 1
        y += 4
        if used >= max_lines or y > y1 - step:
            break
    return y


def empty_note(img, box, msg):
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 15, "Medium")
    lines = t.wrap(d, msg, f, x1 - x0 - 40, lines=3)
    cy = (y0 + y1) / 2 - (len(lines) - 1) * 12
    for i, line in enumerate(lines):
        t.text(d, ((x0 + x1) / 2, cy + i * 24), line, f, t.ASH, "mm")


# ── /spar ─────────────────────────────────────────────────────────────

OUTCOME = {"victory": "Victory", "defeat": "Defeat", "forfeit": "Forfeit"}


def render_spar(data):
    """data: name, realm, layer, title, outcome (victory/defeat/forfeit), turn, max_turns, hp, max_hp,
    m_hp, m_max, gains [{name, type, exp}], timed (a technique hit at the right moment), notes [str],
    cooldown (str)."""
    img, acc = base("spar", seed=23)
    outcome = data["outcome"]
    title_color = acc.main if outcome == "victory" else (t.EMBER if outcome == "defeat" else t.ASH_DK)
    sub = f"{clean(data['title'])[0]}  ·  Exchange {min(data['turn'], data['max_turns'])}/{data['max_turns']}"
    header(img, "spar", acc, OUTCOME[outcome], sub, data.get("cooldown"), title_color)

    # the duel
    box = (30, 186, 590, 420)
    t.panel(img, box, "The Duel", accent=acc)
    x0, y0, x1, _ = box
    you = (round(data["hp"]), data["max_hp"])
    master = (round(data["m_hp"]), data["m_max"])
    for i, (label, (hp, mx), color, icon) in enumerate((
            (data["name"], you, acc.main, "fist"),
            ("The Master", master, t.EMBER, "skull" if outcome == "defeat" else "shield"))):
        y = y0 + 62 + i * 82
        t.medallion(img, (x0 + 46, y + 22), 24, icon, color, cjk_char=False)
        stat_bar(img, (x0 + 86, y, x1 - 24, y + 42), t.fit(ImageDraw.Draw(img), label, font("Cinzel.ttf", 13, "Bold"),
                                                            260),
                 f"{max(0, hp):,} / {mx:,} HP", hp / mx if mx else 0, color)

    # mastery gained
    box = (610, 186, 1170, 420)
    t.panel(img, box, "Mastery Gained", accent=acc)
    x0, y0, x1, y1 = box
    gains = data["gains"][:3]
    if not gains:
        if outcome == "forfeit":
            msg = "You walked away from the spar, so no mastery EXP this time."
        elif data.get("timed"):
            msg = "No mastery EXP this time."
        else:
            msg = "No technique was used at the right moment, so no mastery EXP this time."
        empty_note(img, (x0, y0 + 40, x1, y1), msg)
    for i, g in enumerate(gains):
        y = y0 + 80 + i * 62
        t.medallion(img, (x0 + 44, y), 22, "fist" if g["type"] == "attack" else "shield", acc.main, cjk_char=False)
        d = ImageDraw.Draw(img)
        f = font("Inter.ttf", 17, "Bold")
        t.text(d, (x0 + 80, y - 9), t.fit(d, g["name"], f, x1 - x0 - 250), f, t.PARCHMENT, "lm")
        t.text(d, (x0 + 80, y + 13), f"{g['type'].title()} technique", font("Inter.ttf", 13, "Medium"), t.ASH, "lm")
        t.text(d, (x1 - 24, y), f"+{g['exp']:,} EXP", font("Cinzel.ttf", 22, "Black"), acc.bright, "rm")

    # notes
    box = (30, 440, 1170, H - 24)
    t.panel(img, box, "The Bout", accent=acc)
    notes_block(img, (box[0] + 24, box[1] + 50, box[2] - 24, box[3] - 14), note_lines(data["notes"]), 5)
    return t.finish(img)


# ── /train and /practice ──────────────────────────────────────────────

def render_train(data):
    """data: name, realm, layer, mode (train/practice), title, challenge, score, conditions [str],
    reward: train → {qi, total, need, realm, layer}; practice → {technique, exp, total, cap},
    notes [str], cooldown (str)."""
    img, acc = base("train", seed=29)
    practice = data["mode"] == "practice"
    sub = data["challenge"] + (f"  ·  {', '.join(data['conditions'])}" if data["conditions"] else "")
    header(img, "train", acc, "Practice Complete" if practice else "Training Complete", sub, data.get("cooldown"))

    # score ring
    box = (30, 186, 370, H - 24)
    t.panel(img, box, "Score", accent=acc)
    x0, y0, x1, y1 = box
    cx, cy, r = (x0 + x1) / 2, y0 + 170, 100
    score = max(0.0, min(1.0, data["score"]))
    t.soft_glow(img, (cx - r - 20, cy - r - 20, cx + r + 20, cy + r + 20), t.alpha(acc.main, round(50 + 120 * score)), 16)
    d = ImageDraw.Draw(img)
    d.ellipse(P(cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8), fill=(8, 6, 6, 255), outline=t.BRONZE_DK,
              width=round(4 * t.S))
    d.arc(P(cx - r, cy - r, cx + r, cy + r), 0, 360, fill=t.alpha(t.mix(acc.ink, t.VOID, 0.4), 255), width=round(14 * t.S))
    if score > 0:
        d.arc(P(cx - r, cy - r, cx + r, cy + r), -90, -90 + 360 * score, fill=acc.main, width=round(14 * t.S))
    d.ellipse(P(cx - r + 14, cy - r + 14, cx + r - 14, cy + r - 14), outline=t.alpha(t.GOLD, 160), width=max(1, t.S))
    t.gold_text(img, (cx, cy - 4), f"{score:.0%}", font("Cinzel.ttf", 48, "Black"), "mm")
    d = ImageDraw.Draw(img)
    t.spaced(d, (cx, cy + 40), "SCORE", font("Cinzel.ttf", 12, "Bold"), t.GOLD, 2.4, "m")
    low = score < 0.5
    msg = "Below 50%: only 10% reward" if low else ("A flawless session" if score >= 1 else "Full reward earned")
    t.text(d, (cx, y0 + 308), msg, font("Inter.ttf", 14, "SemiBold"), t.GLOW if low else acc.bright, "mm")
    if data["conditions"]:
        t.text(d, (cx, y0 + 332), f"+15% each from {len(data['conditions'])} condition"
               f"{'s' if len(data['conditions']) > 1 else ''}", font("Inter.ttf", 13, "Medium"), t.ASH, "mm")
    t.divider(d, x0 + 40, x1 - 40, y0 + 364)
    t.text(d, (cx, y0 + 396), "练功", t.cjk(30), acc.main, "mm")

    # reward
    box = (390, 186, 1170, 404)
    t.panel(img, box, "Reward", accent=acc)
    x0, y0, x1, y1 = box
    rw = data["reward"]
    d = ImageDraw.Draw(img)
    if practice:
        big, unit = f"+{rw['exp']:,}", "mastery EXP"
        line = rw["technique"]
        frac = rw["total"] / rw["cap"] if rw["cap"] else 1
        label = "Mastery"
        value = f"{rw['total']:,} / {rw['cap']:,}" if rw["cap"] else f"{rw['total']:,} (final stage)"
    else:
        big, unit = f"+{fmt_num(rw['qi'])}", "Internal Qi"
        line = f"{rw['realm']}  ·  {t.ordinal(rw['layer'])} Layer"
        frac = rw["total"] / rw["need"] if rw["need"] else 1
        label = "Internal Qi"
        value = f"{fmt_num(rw['total'])} / {fmt_num(rw['need'])}"
    f_big = font("Cinzel.ttf", 44, "Black")
    t.medallion(img, (x0 + 60, y0 + 90), 32, "lotus" if not practice else "scroll", acc.main, cjk_char=False)
    d = ImageDraw.Draw(img)
    t.text(d, (x0 + 110, y0 + 84), big, f_big, acc.bright, "lm")
    t.text(d, (x0 + 122 + t.width(d, big, f_big), y0 + 92), unit, font("Inter.ttf", 18, "SemiBold"), t.PARCHMENT, "lm")
    t.text(d, (x0 + 112, y0 + 124), t.fit(d, line, font("Inter.ttf", 15, "Medium"), x1 - x0 - 140),
           font("Inter.ttf", 15, "Medium"), t.ASH, "lm")
    stat_bar(img, (x0 + 24, y0 + 150, x1 - 24, y0 + 194), label, value, frac, acc.main)

    # the session
    box = (390, 424, 1170, H - 24)
    t.panel(img, box, "The Session", accent=acc)
    lines = note_lines(data["notes"])
    if lines:
        notes_block(img, (box[0] + 24, box[1] + 50, box[2] - 24, box[3] - 14), lines, 5)
    else:
        empty_note(img, (box[0], box[1] + 40, box[2], box[3]), "A quiet session. The master nods and walks away.")
    return t.finish(img)


# ── /explore ──────────────────────────────────────────────────────────

def render_explore(data):
    """data: name, realm, layer, defeated, step, max_steps, hp, max_hp, coins, items [{name, qty, icon, color_key}],
    lost [same], beasts, story [str], notes [str], cooldown (str)."""
    img, acc = base("explore", seed=31, h=H_EXPLORE)
    defeated = data["defeated"]
    title = "Expedition Failed" if defeated else "You Return Safely"
    sub = f"{data['name']}  ·  {data['realm']}, {t.ordinal(data['layer'])} Layer  ·  reached step {data['step']} of " \
          f"{data['max_steps']}"
    header(img, "explore", acc, title, sub, data.get("cooldown"), t.EMBER if defeated else None)

    # the trail: depth reached and HP
    box = (30, 186, 1170, 290)
    t.panel(img, box, accent=acc)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    t.spaced(d, (x0 + 24, y0 + 26), "THE TRAIL", font("Cinzel.ttf", 13, "Bold"), t.GOLD, 2)
    n = data["max_steps"]
    tx0, tx1, ty = x0 + 60, x0 + 620, y0 + 66
    seg = (tx1 - tx0) / max(1, n - 1)
    reached = data["step"]
    d.line(P(tx0, ty, tx1, ty), fill=t.BRONZE_DK, width=round(3 * t.S))
    if reached > 1:
        d.line(P(tx0, ty, tx0 + seg * (reached - 1), ty), fill=acc.main, width=round(3 * t.S))
    for i in range(n):
        cx = tx0 + seg * i
        on = i < reached
        last = i == reached - 1
        if last:
            t.soft_glow(img, (cx - 20, ty - 20, cx + 20, ty + 20), t.alpha(t.EMBER if defeated else acc.bright, 150), 6)
            d = ImageDraw.Draw(img)
        r = 11 if last else 8
        fill = (t.EMBER if defeated else acc.bright) if last else (acc.main if on else (16, 10, 10))
        d.ellipse(P(cx - r, ty - r, cx + r, ty + r), fill=fill, outline=t.GOLD_HI if on else t.BRONZE, width=max(1, t.S))
        t.text(d, (cx, ty + 22), f"Step {i + 1}", font("Inter.ttf", 12, "SemiBold"), t.PARCHMENT if on else t.ASH_DK, "mm")
    stat_bar(img, (x0 + 680, y0 + 30, x1 - 24, y0 + 72), "Health",
             f"{max(0, round(data['hp'])):,} / {data['max_hp']:,} HP", data["hp"] / data["max_hp"] if data["max_hp"] else 0,
             t.EMBER if defeated else acc.main)

    # spoils
    box = (30, 310, 720, H_EXPLORE - 24)
    t.panel(img, box, "Spoils", accent=acc)
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(img)
    # coins and beasts in one row
    t.icon(img, "lotus", (x0 + 40, y0 + 72), 30, t.LOTUS)
    d = ImageDraw.Draw(img)
    coins = f"{data['coins']:,}"
    f_c = font("Cinzel.ttf", 30, "Black")
    t.text(d, (x0 + 66, y0 + 72), coins, f_c, t.GOLD_HI, "lm")
    t.text(d, (x0 + 76 + t.width(d, coins, f_c), y0 + 76), "Lotus Coins", font("Inter.ttf", 15, "SemiBold"), t.ASH, "lm")
    t.icon(img, "skull", (x1 - 150, y0 + 72), 22, t.ASH)
    d = ImageDraw.Draw(img)
    t.text(d, (x1 - 132, y0 + 72), f"{data['beasts']} beast{'s' if data['beasts'] != 1 else ''} slain",
           font("Inter.ttf", 15, "SemiBold"), t.PARCHMENT if data["beasts"] else t.ASH_DK, "lm")
    d.line(P(x0 + 20, y0 + 104, x1 - 20, y0 + 104), fill=t.BRONZE_DK, width=max(1, t.S))
    tiles = [(it, False) for it in data["items"]] + [(it, True) for it in data["lost"]]
    if not tiles:
        empty_note(img, (x0, y0 + 110, x1, y1), "No items this time." if data["coins"] else "You return empty-handed.")
    cols, tw, th, gap = 2, (x1 - x0 - 60) / 2, 58, 10
    shown = tiles[:8] if len(tiles) <= 8 else tiles[:7]
    for i, (it, lost) in enumerate(shown):
        c, rr = i % cols, i // cols
        bx, by = x0 + 20 + c * (tw + 20), y0 + 120 + rr * (th + gap)
        item_tile(img, (bx, by, bx + tw, by + th), it, lost)
    if len(tiles) > len(shown):
        i = len(shown)
        bx, by = x0 + 20 + (i % cols) * (tw + 20), y0 + 120 + (i // cols) * (th + gap)
        d = ImageDraw.Draw(img)
        t.text(d, (bx + tw / 2, by + th / 2), f"+{len(tiles) - len(shown)} more in your bag",
               font("Inter.ttf", 15, "SemiBold"), t.ASH, "mm")

    # last step
    box = (740, 310, 1170, H_EXPLORE - 24)
    t.panel(img, box, "Last Step", accent=acc)
    lines = note_lines(data["story"]) + note_lines(data["notes"])
    notes_block(img, (box[0] + 24, box[1] + 50, box[2] - 20, box[3] - 14), lines, 13, f_size=14)
    return t.finish(img)


def item_tile(img, box, it, lost=False):
    x0, y0, x1, y1 = box
    color = t.RARITY.get(it.get("color_key"), t.RARITY[None])
    d = ImageDraw.Draw(img)
    d.rectangle(P(x0, y0, x1, y1), fill=(12, 8, 8, 235), outline=t.BRONZE_DK, width=max(1, t.S))
    t.socket(img, (x0 + 6, y0 + 6, x0 + 52, y1 - 6), t.GLOW if lost else color)
    t.icon(img, it["icon"], (x0 + 29, (y0 + y1) / 2), 26, t.ASH_DK if lost else color)
    d = ImageDraw.Draw(img)
    f = font("Inter.ttf", 15, "Bold")
    qty = f"×{it['qty']}" if it.get("qty", 1) > 1 else ""
    qw = t.width(d, qty, f) + 10 if qty else 0
    t.text(d, (x0 + 64, y0 + 20), t.fit(d, it["name"], f, x1 - x0 - 76 - qw), f, t.ASH if lost else t.PARCHMENT, "lm")
    if qty:
        t.text(d, (x1 - 10, y0 + 20), qty, f, t.GOLD_HI, "rm")
    sub = "Bag full: left behind" if lost else it.get("label", "")
    t.text(d, (x0 + 64, y0 + 40), sub, font("Inter.ttf", 12, "Medium"), t.GLOW if lost else color, "lm")
