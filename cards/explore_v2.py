"""
Explore cards in the encounter-screen style (cards/beast_fight.py): the region's painting fills the card, text
sits on soft shade, no boxes. Same data as cards/expedition.py (bot/explore_card.py).

  render_crossroads(data)  the region, its realm and step, the three paths (arrow, clue, what it looks like)
  render_encounter(data)   the place or subject, what happened, the outcome
Both end in the same band: your HP (the Profile's bar with %), how deep you are, and what you found so far.
"""
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from . import expedition as X
from . import ink as K
from . import theme as T
from . import victory as V
from .scenes import REGION, photo
from .theme import P, S, alpha, font, mix

W, H = 1200, 866
SCENE_H = 610
WARM = (244, 236, 222)
MUTED = (176, 166, 156)
DIM = (128, 120, 112)
SIDE = {"left": "Left", "middle": "Ahead", "right": "Right"}


def _fill(img, mask, color, a=255):
    layer = Image.new("RGBA", img.size, color + (0,))
    layer.putalpha(mask.point(lambda v: round(v * a / 255)))
    img.alpha_composite(layer)


def _cover(sc):
    """A scene from cards/expedition (the old window size) scaled to cover the new one."""
    w, h = W * S, SCENE_H * S
    k = max(w / sc.size[0], h / sc.size[1])
    sc = sc.resize((round(sc.size[0] * k), round(sc.size[1] * k)), Image.LANCZOS)
    x = (sc.size[0] - w) // 2
    return sc.crop((x, 0, x + w, h))


def _canvas(scene):
    img = Image.new("RGBA", (W * S, H * S), (8, 7, 8, 255))
    img.alpha_composite(scene)
    w, h = img.size
    # shade: from the left for the title, and a long fall into the dark band below the scene
    left = Image.linear_gradient("L").rotate(90, expand=True).resize((w, h)).point(lambda v: round(max(0, v - 120) * 1.8))
    top = Image.linear_gradient("L").resize((w, h)).transpose(Image.FLIP_TOP_BOTTOM).point(
        lambda v: round(max(0, v - 200) * 3))
    bottom = Image.new("L", (w, h), 0)
    g = Image.linear_gradient("L").resize((w, round(260 * S)))
    bottom.paste(g, (0, round((SCENE_H - 260) * S)))
    ImageDraw.Draw(bottom).rectangle((0, SCENE_H * S, w, h), fill=255)
    m = ImageChops.lighter(ImageChops.lighter(left, top), bottom).filter(ImageFilter.GaussianBlur(12 * S))
    _fill(img, m, (8, 7, 8), 238)
    return img


def _spaced(d, xy, s, size, color, anchor="l", weight="Bold", tracking=3.0):
    T.spaced(d, xy, s, font("Inter.ttf", size, weight), color, tracking, anchor)


def _head(img, data, title, kicker, accent, sub=None):
    d = ImageDraw.Draw(img)
    _spaced(d, (48, 58), kicker.upper(), 22, mix(accent, WARM, 0.35))
    if title is None:
        return _step(d, data)
    name, nf = X._shrink(d, title, "Cinzel.ttf", "Bold", (70, 62, 52, 46), 780)
    T.text(d, (46, 130), name, nf, WARM, "lm")
    if sub:
        T.text(d, (48, 192), T.fit(d, sub, font("Inter.ttf", 27, "Medium"), 1100), font("Inter.ttf", 27, "Medium"), MUTED, "lm")
    _step(d, data)


def _step(d, data):
    """Depth: the step and five marks, top right."""
    T.text(d, (W - 48, 62), f"Step {data['step']} / {data['max_steps']}", font("Inter.ttf", 38, "Black"), WARM, "rm")
    n = data["max_steps"]
    for i in range(n):
        x1 = W - 48 - (n - 1 - i) * 36
        on = i < data["step"]
        col = mix((240, 170, 60), (232, 70, 50), i / max(1, n - 1)) if on else (60, 54, 50)
        d.rounded_rectangle(P(x1 - 28, 98, x1, 106), radius=round(4 * S), fill=col + (255,))


# ── Crossroads ────────────────────────────────────────────────────────

def render_crossroads(data):
    paths = data["paths"]
    sc = photo(REGION.get(data["region"]), W * S, SCENE_H * S)
    if sc is None:
        sc = _cover(X.crossroads_scene(paths["left"]["kind"], paths["middle"]["kind"], paths["right"]["kind"]))
    img = _canvas(sc)
    accent = T.ACCENTS["explore"].bright
    _head(img, data, data["region"], f"{data['realm']}   ·   choose your path", accent,
          data.get("lie_note") or None)
    # the three paths, side by side over the bottom of the scene: arrow, what you notice, the clue
    cw = (W - 96) / 3
    for i, key in enumerate(("left", "middle", "right")):
        p = paths[key]
        color = X.MOOD[p["kind"]][0]
        x0 = 48 + i * cw
        X.badge(img, (x0 + 36, 452), 34, key, color)
        d = ImageDraw.Draw(img)
        _spaced(d, (x0 + 84, 434), SIDE[key].upper(), 19, mix(color, WARM, 0.4), tracking=2.6)
        label, lf = X._shrink(d, p["label"].title(), "Inter.ttf", "Black", (33, 30, 27, 24), cw - 96)
        T.text(d, (x0 + 84, 468), label, lf, mix(color, WARM, 0.55), "lm")
        f = font("Inter.ttf", 26, "Medium")
        for j, line in enumerate(T.wrap(d, p["clue"], f, cw - 26, lines=3)):
            T.text(d, (x0 + 4, 522 + j * 33), line, f, WARM, "lm")
    _band(img, data)
    return T.finish(img)


# ── Encounter ─────────────────────────────────────────────────────────

def render_encounter(data):
    kind = data["kind"]
    color = X.MOOD[kind][0]
    if data.get("fight"):
        f = data["fight"]
        sc = X.fight_scene(f["palette"], f["body"], f.get("slug"), data.get("region"))
    else:
        sc = X.encounter_scene(kind, region=data.get("region"),
                               hazard=data["hazard"]["kind"] if data.get("hazard") else None)
    img = _canvas(_cover(sc))
    if data.get("victory"):
        return _fight_result(img, data)
    outcome = data.get("outcome")
    tone = {"bad": (232, 76, 58), "good": (120, 220, 140)}.get(outcome, color)
    sub = data["subtitle"].split("·", 1)[-1].strip() if "·" in data["subtitle"] else data["subtitle"]
    sub = sub[:1].upper() + sub[1:]
    _head(img, data, data["title"], f"{data['region']}   ·   {data['realm']}", tone, sub)
    d = ImageDraw.Draw(img)
    if data.get("hazard"):
        h = data["hazard"]
        _spaced(d, (48, 246), f"{h['kind'].upper()}!   IT COMES FROM THE {h['danger'].upper()}", 24, (255, 120, 96),
                tracking=3)
    story = [s for s in data["story"] if s][:4]
    if story:
        f = font("Inter.ttf", 28, "Medium")
        lines = []
        for s_ in story:
            lines += T.wrap(d, s_, f, 640, lines=3)
        lines = lines[:5]
        y = 612 - 42 * len(lines) - 20
        d.line(P(48, y - 8, 48, y + 42 * len(lines) - 22), fill=tone, width=round(5 * S))
        for line in lines:
            T.text(d, (68, y + 8), line, f, WARM, "lm")
            y += 42
    _band(img, data)
    return T.finish(img)


def _fight_result(img, data):
    """After a fight: the beast sinks into shadow, the crest and the word, then the spoils on the silk cloth
    (a win) or what the loss cost (a defeat)."""
    v = data["victory"]
    won = v["result"] == "won"
    veil = Image.new("RGBA", img.size, (6, 4, 6, 0))
    ImageDraw.Draw(veil).rectangle((0, 0, img.size[0], SCENE_H * S), fill=(6, 4, 6, 150))
    img.alpha_composite(veil)
    color = (246, 200, 96) if won else (226, 80, 64)
    _head(img, data, None, f"{data['region']}   ·   {data['realm']}", color)
    V.crest(img, (W / 2, 168), 220, v["result"])
    title = data["title"]
    T.gold_text(img, (W / 2, 330), title, font("Cinzel.ttf", 78 if len(title) < 14 else 62, "Bold"), "mm",
                top=mix(color, (255, 255, 255), 0.6), bottom=mix(color, (0, 0, 0), 0.25))
    d = ImageDraw.Draw(img)
    turns = f"{v['turns']} turn{'s' if v['turns'] != 1 else ''}"
    if won:
        sub = (f"{v['name']} driven off in {turns}" if v["bandits"] else f"{v['name']} slain in {turns}")
    else:
        sub = f"The {v['name']} was too strong this time"
    T.text(d, (W / 2, 390), sub, font("Inter.ttf", 30, "SemiBold"), WARM, "mm")
    if won:
        V.spoils(img, (210, 424, 990, 628), v["spoils"])
    else:
        lines = [s for s in data["story"] if s][-2:]
        f = font("Inter.ttf", 26, "Medium")
        for i, line in enumerate(lines):
            T.text(d, (W / 2, 470 + i * 40), T.fit(d, line, f, 1000), f, MUTED, "mm")
    _band(img, data)
    return T.finish(img)


# ── The band below the scene: you, depth, finds ───────────────────────

def _band(img, data):
    d = ImageDraw.Draw(img)
    y = 662
    _spaced(d, (48, y), "YOU", 20, MUTED, tracking=3)
    frac = data["hp"] / data["max_hp"] if data["max_hp"] else 0
    low = frac <= 0.25
    K.ornate_bar(img, (66, y + 30, 470, y + 72), frac, (214, 64, 52) if low else (196, 70, 58), "heart",
                 f"{max(0, round(data['hp'])):,} / {data['max_hp']:,}")
    d = ImageDraw.Draw(img)
    T.text(d, (512, y + 51), f"{frac:.0%}", font("Inter.ttf", 36, "Black"), WARM, "lm")
    T.text(d, (48, y + 120), T.fit(d, data["bonus"], font("Inter.ttf", 25, "SemiBold"), 580), font("Inter.ttf", 25, "SemiBold"), T.LOTUS, "lm")
    T.text(d, (48, y + 160), T.fit(d, data["defeat_note"], font("Inter.ttf", 21, "Medium"), 580), font("Inter.ttf", 21, "Medium"), DIM, "lm")
    # found so far
    x0 = 650
    _spaced(d, (x0, y), "FOUND SO FAR", 20, MUTED, tracking=3)
    finds = []
    if data["coins"]:
        finds.append({"name": "Lotus Coins", "label": f"{data['coins']:,}", "icon": "lotus", "color": T.LOTUS})
    finds += data["items"]
    if not finds:
        T.text(d, (x0, y + 52), "Nothing yet", font("Inter.ttf", 30, "Medium"), DIM, "lm")
        return
    shown = finds[:4]
    for i, it in enumerate(shown):
        cx = x0 + 52 + i * 128
        col = it.get("color") or T.RARITY.get(it.get("color_key"), T.RARITY[None])
        T.seal(img, (cx, y + 70), 38, it["icon"], col)
        d = ImageDraw.Draw(img)
        qty = it.get("qty", 1)
        if qty > 1:
            T.text(d, (cx + 38, y + 40), f"×{qty}", font("Inter.ttf", 23, "Black"), (246, 214, 150), "mm")
        label = it.get("label") if it.get("name") == "Lotus Coins" else it["name"]
        f = font("Inter.ttf", 20, "SemiBold")
        for j, line in enumerate(T.wrap(d, label, f, 122, lines=2)):
            T.text(d, (cx, y + 128 + j * 24), line, f, WARM, "mm")
    if len(finds) > len(shown):
        T.text(d, (x0 + 52 + len(shown) * 128 - 56, y + 70), f"+{len(finds) - len(shown)}",
               font("Inter.ttf", 30, "Black"), MUTED, "lm")


__all__ = ["render_crossroads", "render_encounter", "W", "H", "alpha"]
