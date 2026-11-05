"""
Render the /spar, /train, /practice and /explore result cards with made-up data and save them as PNGs.

    python scripts/render_results.py          # writes previews/result_*.png

Useful to check the look after changing cards/activity.py (no Discord needed).
"""
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from cards.activity import render_explore, render_spar, render_train   # noqa: E402

WHO = {"name": "Shoaib", "realm": "Martial King", "layer": 8}

SPAR = dict(WHO, title="Sparring with the Master", outcome="victory", turn=9, max_turns=12,
            hp=1840, max_hp=3200, m_hp=0, m_max=3500,
            gains=[{"name": "Rolling Thunder Palm", "type": "attack", "exp": 120},
                   {"name": "Golden Bell Cover", "type": "defense", "exp": 80}],
            notes=["✅ You Guard his Strike and answer with **Rolling Thunder Palm**! The master staggers back.",
                   "*You have sparred a lot today: EXP ×0.5.*"],
            cooldown="Spar again in 2 hours")
SPAR_LOSS = dict(SPAR, outcome="defeat", hp=0, m_hp=1210, gains=[],
                 title="Mastery Trial: Golden Bell Cover → Entering the Hall",
                 notes=["❌ He breaks your Guard and you fall.",
                        "The trial failed. No EXP is lost; you may retry in 12 hours."])
TRAIN = dict(WHO, mode="train", challenge="Read the Master", conditions=["Heavy Rain", "Night Training"], score=0.875,
             reward={"qi": 3862.4, "total": 22102.4, "need": 53760, "realm": "Martial King", "layer": 8},
             notes=["✅ Correct! He was going to **Break**.", "💡 **Epiphany!** Something clicks: +50% Qi."],
             cooldown="Train again in 60 min")
PRACTICE = dict(WHO, mode="practice", challenge="Endless Waves", conditions=[], score=0.42,
                reward={"technique": "Viper Fang Finger", "exp": 18, "total": 918, "cap": 2000},
                notes=["You scored **5** of 12 points."], cooldown="Practise again in 30 min")
EXPLORE = dict(WHO, defeated=False, step=4, max_steps=5, hp=2210, max_hp=3200, coins=312, beasts=3,
               items=[{"name": "Silver Chest", "qty": 1, "icon": "chest", "color_key": "silver", "label": "Silver"},
                      {"name": "Red Ginseng Root", "qty": 3, "icon": "herb", "color_key": None, "label": "Common"},
                      {"name": "Fine Spirit Saber", "qty": 1, "icon": "saber", "color_key": "spirit", "label": "Spirit"},
                      {"name": "Iron Cloth Body Manual", "qty": 1, "icon": "scroll", "color_key": "Yellow",
                       "label": "Yellow Grade"}],
               lost=[{"name": "Mystic Qi Pill", "qty": 1, "icon": "pill", "color_key": "Mystic", "label": "Mystic Grade"}],
               story=["You head back the way you came, loot in hand."],
               notes=["🏯 **Golden Bell Cover** is ready for its Mastery Trial. Use /spar to attempt it."],
               cooldown="Explore again in 30 min")
EXPLORE_FAIL = dict(EXPLORE, defeated=True, step=5, hp=0, coins=156, beasts=1, items=[EXPLORE["items"][1]], lost=[],
                    story=["🐾 A **Shadow Fang Wolf** (Normal) leaps out (+40% stronger this deep)!",
                           "The wolf lunges, you guard, it breaks through.", "The Shadow Fang Wolf overwhelms you..."],
                    notes=[])


def main():
    out = os.path.join(ROOT, "previews")
    os.makedirs(out, exist_ok=True)
    for name, fn, data in (("spar", render_spar, SPAR), ("spar_defeat", render_spar, SPAR_LOSS),
                           ("train", render_train, TRAIN), ("practice", render_train, PRACTICE),
                           ("explore", render_explore, EXPLORE), ("explore_defeat", render_explore, EXPLORE_FAIL)):
        t0 = time.perf_counter()
        path = os.path.join(out, f"result_{name}.png")
        fn(data).save(path)
        print(f"{path}  ({time.perf_counter() - t0:.2f}s)")


if __name__ == "__main__":
    main()
