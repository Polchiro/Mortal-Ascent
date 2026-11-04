"""
Loot: rolling chests, manuals, weapons and herbs, and using items from the bag.

Odds come from explore.py and equipments.py. Numbers the design docs leave
open (chest coin amounts, herb names, merchant prices) are marked DEFAULT.
"""
import random
import time

import economy
import equipments
import explore
import technique
import training

from . import db
from . import player as rules

CHEST_NAMES = {"wooden": "Wooden Chest", "bronze": "Bronze Chest", "silver": "Silver Chest", "jade": "Jade Chest"}
CHEST_EMOJI = {"wooden": "🪵", "bronze": "🥉", "silver": "🥈", "jade": "💚"}
TIER_ORDER = equipments.TIERS
GRADE_ORDER = list(technique.GRADES)

# DEFAULT: Lotus Coins in a chest at Mortal (×2 per realm, see rules.realm_scale)
CHEST_COINS = {"wooden": (10, 25), "bronze": (30, 60), "silver": (80, 150), "jade": (200, 400)}
# DEFAULT: herbs for future pills (explore.md only says "materials")
HERBS = ["Spirit Grass", "Dew Lotus Petal", "Red Ginseng Root", "Moonlight Fern", "Tiger Bone Moss"]
# DEFAULT: duplicate of a learned manual turns into this much mastery EXP (× grade EXP multiplier)
INSIGHT_EXP = 100


def pick(odds, rng=random):
    keys = list(odds)
    return rng.choices(keys, weights=[odds[k] for k in keys])[0]


def coin_bonus(player, now=None):
    b = rules.active_blessing(player, now)
    return 1 + (economy.BLESSING_TIERS[b[0]]["lotus_coins"] if b else 0)


def roll_coins(player, lo_hi, rng=random):
    lo, hi = lo_hi
    return round(rng.randint(lo, hi) * rules.realm_scale(player["realm"]) * coin_bonus(player))


# ── Item makers (dicts ready for db.add_item(**item)) ────────────────

def manual(key):
    t = technique.TECHNIQUES[key]
    return {"category": "manuals", "key": key, "name": f"{t['name']} Manual", "grade": t["grade"]}


def roll_manual(grade, rng=random):
    keys = [k for k, t in technique.TECHNIQUES.items() if t["grade"] == grade]
    return manual(rng.choice(keys))


def roll_weapon(tier, rng=random):
    wtype = rng.choice(equipments.WEAPON_TYPES)
    ranges = equipments.WEAPON_BUFFS[wtype][tier]
    pos = rng.random()           # one roll position for all stats, so the quality prefix is honest
    buffs = {k: round(lo + (hi - lo) * pos, 3) for k, (lo, hi) in ranges.items()}
    prefix = next(name for threshold, name in equipments.QUALITY_PREFIXES if pos >= threshold)
    base = equipments.WEAPON_NAMES[tier][wtype]
    return {"category": "weapons", "key": wtype, "name": f"{prefix} {base}".strip(), "grade": tier,
            "data": {"buffs": buffs, "type": wtype}}


def chest(tier):
    return {"category": "chests", "key": tier, "name": CHEST_NAMES[tier], "grade": tier}


def herb(rng=random, name=None):
    name = name or rng.choice(HERBS)
    return {"category": "materials", "key": name, "name": name, "grade": None}


def pill(grade):
    return {"category": "pills", "key": grade, "name": f"{grade} Qi Pill", "grade": grade}


def open_chest(player, tier, rng=random):
    """Roll a chest's contents. Returns (coins, [items])."""
    coins = roll_coins(player, CHEST_COINS[tier], rng)
    items = []
    if rng.random() < explore.CHEST_MANUAL_CHANCE[tier]:
        items.append(roll_manual(pick(explore.CHEST_MANUAL_GRADE_ODDS[tier], rng), rng))
    if rng.random() < equipments.CHEST_WEAPON_CHANCE[tier]:
        items.append(roll_weapon(pick(equipments.CHEST_TIER_ODDS[tier], rng), rng))
    return coins, items


def beast_chest(player, beast_tier, rng=random):
    """Chest dropped by a beast, or None. Blessing 'chest_drop' raises the chance (economy.md)."""
    spec = explore.BEAST_CHEST[beast_tier]
    b = rules.active_blessing(player)
    bonus = economy.BLESSING_TIERS[b[0]]["chest_drop"] if b else 0
    if rng.random() < spec["chance"] + bonus:
        return chest(pick(spec["tiers"], rng))
    return None


def describe(item):
    qty = item.get("qty", 1)
    return f"{item['name']}" + (f" ×{qty}" if qty > 1 else "")


def store(conn, user_id, items):
    """Put items in the bag. Returns (stored, left_behind)."""
    stored, lost = [], []
    for it in items:
        ok = db.add_item(conn, user_id, it["category"], it["key"], it["name"], it.get("grade"),
                         it.get("qty", 1), it.get("data"))
        (stored if ok else lost).append(it)
    return stored, lost


# ── Using items from the bag ──────────────────────────────────────────

def use_item(conn, user_id, item_id, rng=random, now=None):
    """Use one item. Returns a message for the player."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    item = db.get_item(conn, user_id, item_id)
    if not item:
        return "That item is no longer in your bag."
    cat = item["category"]

    if cat == "chests":
        coins, found = open_chest(p, item["key"], rng)
        db.remove_item(conn, item_id)
        db.add_coins(conn, user_id, coins)
        stored, lost = store(conn, user_id, found)
        lines = [f"{CHEST_EMOJI[item['key']]} You open the **{item['name']}**...", f"🪷 **{coins:,}** Lotus Coins"]
        lines += [f"✨ **{describe(i)}**" for i in stored]
        lines += [f"⚠️ Your bag is full, so you left **{describe(i)}** behind." for i in lost]
        if len(lines) == 2:
            lines.append("*Nothing else inside.*")
        return "\n".join(lines)

    if cat == "weapons":
        need = equipments.TIER_REALM_REQUIREMENT[item["grade"]]
        if rules.realm_index(p["realm"]) < rules.realm_index(need):
            return f"You must reach **{need}** to wield a {item['grade'].title()} weapon."
        if item["equipped"]:
            return f"**{item['name']}** is already equipped."
        db.equip_weapon(conn, user_id, item_id)
        return f"⚔️ You equip **{item['name']}** ({rules.buff_text(rules.weapon_buffs(item))})."

    if cat == "manuals":
        t = technique.TECHNIQUES[item["key"]]
        need = technique.GRADES[t["grade"]]
        if rules.realm_index(p["realm"]) < rules.realm_index(need):
            return f"You must reach **{need}** to comprehend a {t['grade']} manual."
        learned = [x for x in db.get_techniques(conn, user_id, equipped_only=False) if x["name"] == t["name"]]
        db.remove_item(conn, item_id)
        if learned:
            exp = round(INSIGHT_EXP * technique.GRADE_EXP_MULTIPLIER[t["grade"]])
            db.add_mastery(conn, learned[0]["id"], exp)
            return f"📜 You already know **{t['name']}**. Rereading it gives you insight: **+{exp} mastery EXP**."
        db.learn_technique(conn, user_id, t["name"], t["type"], t["grade"])
        return (f"📜 You comprehend **{t['name']}** ({t['grade']} {t['type']}) and equip it "
                f"in your {t['type']} slot.")

    if cat == "pills":
        current = rules.active_pill(p, now)
        if current:
            return f"Your **{current[0]} Qi Pill** is still working ({rules.fmt_duration(current[2])} left). Pills do not stack."
        tox = rules.current_toxicity(p, now) + 1
        effect = rules.pill_effect_mult(tox)
        mult = 1 + (training.QI_PILLS[item["grade"]] - 1) * effect
        db.remove_item(conn, item_id)
        db.update_player(conn, user_id, pill_grade=item["grade"], pill_mult=mult,
                         pill_expires=now + training.QI_PILL_DURATION_HOURS * 3600,
                         toxicity=tox, toxicity_at=now)
        msg = (f"💊 You swallow the **{item['name']}**. Qi Rate ×{mult:.2f} for "
               f"{training.QI_PILL_DURATION_HOURS} hours. Toxicity: {tox}.")
        if effect < 1:
            msg += " ☠️ Your body is clogged with pill toxins, so the pill works less well."
        return msg

    return f"**{item['name']}** will be used for pills once alchemy arrives."
