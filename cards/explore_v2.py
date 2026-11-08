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
from .scenes import REGION, photo
from .theme import P, S, alpha, font, mix

W, H = 1200, 840
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
    _spaced(d, (48, 56), kicker.upper(), 18, mix(accent, WARM, 0.35))
    name, nf = X._shrink(d, title, "Cinzel.ttf", "Bold", (60, 52, 44), 760)
    T.text(d, (46, 122), name, nf, WARM, "lm")
    if sub:
        T.text(d, (48, 176), sub, font("Inter.ttf", 22, "Medium"), MUTED, "lm")
    # depth: the step and five marks, top right
    T.text(d, (W - 48, 62), f"Step {data['step']} / {data['max_steps']}", font("Inter.ttf", 30, "Black"), WARM, "rm")
    n = data["max_steps"]
    for i in range(n):
        x1 = W - 48 - (n - 1 - i) * 30
        on = i < data["step"]
        col = mix((240, 170, 60), (232, 70, 50), i / max(1, n - 1)) if on else (60, 54, 50)
        d.rounded_rectangle(P(x1 - 22, 94, x1, 100), radius=round(3 * S), fill=col + (255,))


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
        X.badge(img, (x0 + 34, 470), 30, key, color)
        d = ImageDraw.Draw(img)
        _spaced(d, (x0 + 78, 456), SIDE[key].upper(), 15, mix(color, WARM, 0.4), tracking=2.6)
        label, lf = X._shrink(d, p["label"].title(), "Inter.ttf", "Black", (27, 25, 23), cw - 96)
        T.text(d, (x0 + 78, 484), label, lf, mix(color, WARM, 0.55), "lm")
        f = font("Inter.ttf", 21, "Medium")
        for j, line in enumerate(T.wrap(d, p["clue"], f, cw - 30, lines=2)):
            T.text(d, (x0 + 4, 530 + j * 28), line, f, WARM, "lm")
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
    outcome = data.get("outcome")
    tone = {"bad": (232, 76, 58), "good": (120, 220, 140)}.get(outcome, color)
    sub = data["subtitle"].split("·", 1)[-1].strip() if "·" in data["subtitle"] else data["subtitle"]
    sub = sub[:1].upper() + sub[1:]
    _head(img, data, data["title"], f"{data['region']}   ·   {data['realm']}", tone, sub)
    d = ImageDraw.Draw(img)
    if data.get("hazard"):
        h = data["hazard"]
        _spaced(d, (48, 236), f"{h['kind'].upper()}!   IT COMES FROM THE {h['danger'].upper()}", 20, (255, 120, 96),
                tracking=3)
    story = [s for s in data["story"] if s][:4]
    if story:
        y = 610 - 36 * len(story) - 22
        d.line(P(48, y - 6, 48, y + 36 * len(story) - 20), fill=tone, width=round(4 * S))
        f = font("Inter.ttf", 23, "Medium")
        for line in story:
            T.text(d, (66, y + 8), T.fit(d, line, f, 760), f, WARM, "lm")
            y += 36
    _band(img, data)
    return T.finish(img)


# ── The band below the scene: you, depth, finds ───────────────────────

def _band(img, data):
    d = ImageDraw.Draw(img)
    y = 660
    _spaced(d, (48, y), "YOU", 15, MUTED, tracking=3)
    frac = data["hp"] / data["max_hp"] if data["max_hp"] else 0
    low = frac <= 0.25
    K.ornate_bar(img, (66, y + 26, 470, y + 58), frac, (214, 64, 52) if low else (196, 70, 58), "heart",
                 f"{max(0, round(data['hp'])):,} / {data['max_hp']:,}")
    d = ImageDraw.Draw(img)
    T.text(d, (514, y + 43), f"{frac:.0%}", font("Inter.ttf", 30, "Black"), WARM, "lm")
    T.text(d, (48, y + 98), data["bonus"], font("Inter.ttf", 20, "SemiBold"), T.LOTUS, "lm")
    T.text(d, (48, y + 132), data["defeat_note"], font("Inter.ttf", 17, "Medium"), DIM, "lm")
    # found so far
    x0 = 660
    _spaced(d, (x0, y), "FOUND SO FAR", 15, MUTED, tracking=3)
    finds = []
    if data["coins"]:
        finds.append({"name": "Lotus Coins", "label": f"{data['coins']:,}", "icon": "lotus", "color": T.LOTUS})
    finds += data["items"]
    if not finds:
        T.text(d, (x0, y + 52), "Nothing yet", font("Inter.ttf", 24, "Medium"), DIM, "lm")
        return
    shown = finds[:5]
    for i, it in enumerate(shown):
        cx = x0 + 36 + i * 102
        col = it.get("color") or T.RARITY.get(it.get("color_key"), T.RARITY[None])
        T.seal(img, (cx, y + 58), 30, it["icon"], col)
        d = ImageDraw.Draw(img)
        qty = it.get("qty", 1)
        if qty > 1:
            T.text(d, (cx + 30, y + 34), f"×{qty}", font("Inter.ttf", 18, "Black"), (246, 214, 150), "mm")
        label = it.get("label") if it.get("name") == "Lotus Coins" else it["name"]
        f = font("Inter.ttf", 15, "SemiBold")
        for j, line in enumerate(T.wrap(d, label, f, 96, lines=2)):
            T.text(d, (cx, y + 104 + j * 18), line, f, WARM, "mm")
    if len(finds) > len(shown):
        T.text(d, (x0 + 36 + len(shown) * 102 - 40, y + 58), f"+{len(finds) - len(shown)}",
               font("Inter.ttf", 24, "Black"), MUTED, "lm")


__all__ = ["render_crossroads", "render_encounter", "W", "H", "alpha"]
