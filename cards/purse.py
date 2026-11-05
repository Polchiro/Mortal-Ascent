"""
Character Sheet · Purse tab (Crimson Hall theme).

render_purse(data) draws bot.sheet.data.purse_data: every live currency with
its icon (Lotus Coins, Moon Pearls; economy.md keeps the later ones hidden),
the Heavenly Blessing, and the most recent transactions from the ledger.
"""
from PIL import ImageDraw

import economy

from . import theme as t
from .theme import P, font, short

H = 660


def render_purse(data):
    img = t.canvas(t.W, H, seed=11)
    t.tab_strip(img, "purse")
    t.frame(img, (6, 52, t.W - 6, H - 6))
    d = ImageDraw.Draw(img)
    t.gold_text(img, (40, 68), f"{data['name'].upper()}'S TREASURY", font("Cinzel.ttf", 34, "Black"), glow=t.EMBER)
    d = ImageDraw.Draw(img)
    t.text(d, (42, 126), f"{data['realm']}  ·  {data['talent']} Talent", font("Inter.ttf", 15, "Medium"), t.ASH)
    t.divider(d, 30, 1170, 150)

    y = 168
    for c in data["currencies"]:
        currency_panel(img, (30, y, 600, y + 128), c)
        y += 144
    blessing_panel(img, (30, y, 600, H - 30), data["blessing"])
    ledger_panel(img, (620, 168, 1170, H - 30), data["ledger"])
    return t.finish(img)


def currency_panel(img, box, c):
    x0, y0, x1, y1 = box
    t.panel(img, box)
    cy = (y0 + y1) / 2
    t.medallion(img, (x0 + 66, cy), 42, c["icon"], c["color"], cjk_char=False)
    d = ImageDraw.Draw(img)
    t.spaced(d, (x0 + 128, cy - 30), c["name"].upper(), font("Cinzel.ttf", 15, "Bold"), t.GOLD, 2)
    t.text(d, (x0 + 128, cy + 8), short(c["amount"]), font("Cinzel.ttf", 40, "Black"), c["color"], "lm")
    t.text(d, (x1 - 24, cy + 14), f"{c['amount']:,}", font("Inter.ttf", 16, "SemiBold"), t.PARCHMENT, "rm")
    t.text(d, (x1 - 24, cy - 28), c["note"], font("Inter.ttf", 12, "Medium"), t.ASH, "rm")


def blessing_panel(img, box, b):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Heavenly Blessing")
    d = ImageDraw.Draw(img)
    if not b:
        t.text(d, (x0 + 20, y0 + 64), "No active blessing", font("Inter.ttf", 18, "Bold"), t.PARCHMENT, "lm")
        t.text(d, (x0 + 20, y0 + 92), "Use /blessing to see the eight tiers", font("Inter.ttf", 13, "Medium"),
               t.ASH, "lm")
        return
    t.icon(img, "star", (x0 + 34, y0 + 64), 22, t.GOLD_HI)
    d = ImageDraw.Draw(img)
    t.text(d, (x0 + 54, y0 + 64), b["tier"], font("Cinzel.ttf", 22, "Bold"), t.GOLD_HI, "lm")
    t.text(d, (x0 + 20, y0 + 94), t.fit(d, b["perks"], font("Inter.ttf", 13, "Medium"), x1 - x0 - 40),
           font("Inter.ttf", 13, "Medium"), t.PARCHMENT, "lm")
    total = economy.BLESSING_DURATION_DAYS
    t.bar(img, (x0 + 20, y1 - 38, x1 - 20, y1 - 22), b["days_left"] / total, t.GOLD,
          f"{b['days_left']} of {total} days left")


def ledger_panel(img, box, rows):
    x0, y0, x1, y1 = box
    t.panel(img, box, "Recent Transactions")
    d = ImageDraw.Draw(img)
    if not rows:
        t.text(d, ((x0 + x1) / 2, (y0 + y1) / 2), "No transactions yet", font("Inter.ttf", 15, "Medium"), t.ASH, "mm")
        return
    y = y0 + 64
    step = min(52, (y1 - y0 - 70) / max(1, len(rows)))
    f_r = font("Inter.ttf", 15, "SemiBold")
    f_s = font("Inter.ttf", 12, "Medium")
    f_d = font("Inter.ttf", 17, "Bold")
    for r in rows:
        icon, color = ("lotus", t.LOTUS) if r["currency"] == "lotus_coins" else ("pearl", t.MOON)
        t.icon(img, icon, (x0 + 32, y), 20, color)
        d = ImageDraw.Draw(img)
        t.text(d, (x0 + 54, y - 8), t.fit(d, r["reason"], f_r, x1 - x0 - 210), f_r, t.PARCHMENT, "lm")
        t.text(d, (x0 + 54, y + 11), r["ago"], f_s, t.ASH, "lm")
        sign = "+" if r["delta"] > 0 else "−"
        t.text(d, (x1 - 22, y - 8), f"{sign}{abs(r['delta']):,}", f_d, t.JADE if r["delta"] > 0 else t.GLOW, "rm")
        t.text(d, (x1 - 22, y + 12), f"balance {r['balance']:,}", f_s, t.ASH_DK, "rm")
        d.line(P(x0 + 18, y + step / 2, x1 - 18, y + step / 2), fill=t.BRONZE_DK, width=max(1, t.S))
        y += step
