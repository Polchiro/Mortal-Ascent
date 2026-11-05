"""
Render every Character Sheet card for a made-up player and save them as PNGs.

    python scripts/render_sheet.py            # writes previews/sheet_*.png

Useful to check the look after changing cards/ (no Discord needed).
"""
import os
import random
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from bot import db, loot                          # noqa: E402
from bot import player as rules                   # noqa: E402
from bot.sheet import data as sheet               # noqa: E402
from cards import RENDERERS                       # noqa: E402


def demo_player(conn, uid=1):
    rng = random.Random(4)
    db.create_player(conn, uid, "Shoaib", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    now = time.time()
    db.update_player(conn, uid, realm="Martial King", layer=8, qi=18240, beasts_slain=1284, breakthroughs=74,
                     failed_breakthroughs=9, qi_collected_at=now - 3 * 3600, pill_grade="Mystic", pill_mult=1.7,
                     pill_expires=now + 7200)
    for key in ("rolling_thunder_palm", "golden_bell_cover", "viper_fang_finger", "crescent_sweep"):
        t = loot.technique.TECHNIQUES[key]
        db.learn_technique(conn, uid, t["name"], t["type"], t["grade"], slots=3)
    for tid, exp, stage in ((3, 4000, 2), (4, 900, 1), (5, 9000, 3)):
        db.set_mastery(conn, tid, exp, stage)
    w = loot.roll_weapon("treasure", rng)
    db.add_item(conn, uid, **w)
    db.equip_weapon(conn, uid, db.get_items(conn, uid, "weapons")[0]["id"])
    for item in (loot.roll_weapon("spirit", rng), loot.chest("jade"), dict(loot.chest("silver"), qty=3),
                 dict(loot.pill("Mystic"), qty=2), dict(loot.HEAVEN_DEFYING), loot.manual("meteor_falling_kick"),
                 dict(loot.herb(name="Red Ginseng Root"), qty=7), loot.manual("iron_cloth_body")):
        db.add_item(conn, uid, item["category"], item["key"], item["name"], item.get("grade"), item.get("qty", 1),
                    item.get("data"))
    db.change_currency(conn, uid, "lotus_coins", 128400, "Opened Jade Chest", now=now - 86400 * 2)
    db.change_currency(conn, uid, "moon_pearls", 2240, "Admin gift", now=now - 86400)
    db.spend(conn, uid, "moon_pearls", 1500, "Blessing: Bright Moon")
    db.update_player(conn, uid, blessing_tier="Bright Moon", blessing_expires=now + 86400 * 21)
    db.spend(conn, uid, "lotus_coins", 640, "Physician")
    db.add_coins(conn, uid, 312, "Expedition loot")
    return uid


def main():
    conn = db.connect(":memory:")
    uid = demo_player(conn)
    out = os.path.join(ROOT, "previews")
    os.makedirs(out, exist_ok=True)
    cards = {
        "profile": sheet.profile_data(conn, uid, "shoaib"),
        "techniques": sheet.techniques_data(conn, uid),
        "equipment": sheet.equipment_data(conn, uid),
        "inventory": sheet.bag_data(conn, uid, "chests")[0],
        "purse": sheet.purse_data(conn, uid),
    }
    for name, data in cards.items():
        t0 = time.perf_counter()
        path = os.path.join(out, f"sheet_{name}.png")
        RENDERERS[name](data).save(path)
        print(f"{path}  ({time.perf_counter() - t0:.2f}s)")


if __name__ == "__main__":
    main()
