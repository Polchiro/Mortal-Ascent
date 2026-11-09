"""
/profession: a player's Alchemist and Blacksmith ranks, EXP, what each rank lets them make, and what the
next rank opens (alchemy.py, forge.py, docs/alchemy.md section 6, docs/forge.md section 6).
"""
import alchemy
import equipments
import forge

from . import crafting, forging

GRADE_CN = {1: "一品", 2: "二品", 3: "三品", 4: "四品", 5: "五品", 6: "六品", 7: "七品", 8: "八品", 9: "九品"}
PILL_WORD = {"qi": "Qi", "burst": "Qi Burst", "mending": "Mending", "cleansing": "Cleansing", "breakthrough": "Breakthrough"}


def pill_unlocks():
    """{rank: ['Yellow Qi', 'Yellow Mending']}: the pills each alchemist rank opens."""
    out = {}
    for kind, (_, _, specs, _) in crafting.KINDS.items():
        for grade, spec in specs.items():
            out.setdefault(spec["rank"], []).append(f"{grade} {PILL_WORD[kind]}")
    return out


def gear_unlocks():
    """{rank: ['Spirit gear']}: the gear tiers each blacksmith rank can forge."""
    out = {}
    for tier, rank in forge.RANK_NEEDED.items():
        out.setdefault(rank, []).append(equipments.TIER_DISPLAY[tier].split(" ", 1)[1])
    return out


def _side(exp, curve, rank_of, unlocks, title, word):
    rank = rank_of(exp)
    top = max(curve)
    nxt = rank + 1 if rank < top else None
    lo = curve[rank]
    hi = curve[nxt] if nxt else lo
    can = [u for r, us in sorted(unlocks.items()) if r <= rank for u in us]
    upcoming = next(((r, unlocks[r]) for r in sorted(unlocks) if r > rank), None)
    return {"title": title, "rank": rank, "max_rank": top, "label": crafting.rank_label(rank) + " " + word,
            "seal": GRADE_CN.get(rank, str(rank)), "exp": exp, "into": exp - lo, "span": hi - lo,
            "next": crafting.rank_label(nxt) if nxt else None, "to_next": (hi - exp) if nxt else 0,
            "can": can, "upcoming": upcoming and (crafting.rank_label(upcoming[0]), upcoming[1])}


def card_data(player):
    return {
        "name": player["name"],
        "sides": [
            dict(_side(player["alchemy_exp"], alchemy.ALCHEMIST_RANK_EXP, crafting.rank_of, pill_unlocks(),
                       "Alchemy", "Alchemist"),
                 key="alchemy", art="cauldron.png", command="/craft", what="pills",
                 hint="EXP from every craft; higher grades and more patterns give more."),
            dict(_side(player["blacksmith_exp"], forge.BLACKSMITH_RANK_EXP, forging.rank_of, gear_unlocks(),
                       "Blacksmith", "Blacksmith"),
                 key="forge", art="forge_success.png", command="/forge", what="gear",
                 hint="EXP from every forge; higher tiers and rarer passives give more."),
        ],
    }
