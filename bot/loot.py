"""
Loot: rolling chests, manuals, weapons and herbs (alchemy.py), and using items from the bag.

Odds come from explore.py and equipments.py. Numbers the design docs leave
open (chest coin amounts, merchant prices) are marked DEFAULT.
"""
import random
import time

import alchemy
import economy
import equipments
import explore
import talent
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


# ── Herbs (alchemy.py, docs/alchemy.md) ──────────────────────────────

AGE_EMOJI = {10: "🌱", 50: "🌿", 100: "🍃", 500: "🌳", 1000: "🏵️"}
TYPE_EMOJI = {"qi": "🌀", "healing": "❤️", "purity": "💧", "breakthrough": "🏔️"}
TYPE_LABEL = {"qi": "Qi", "healing": "Healing", "purity": "Purity", "breakthrough": "Breakthrough"}


def herb_tier(realm, rng=random):
    """The tier of herb a cultivator of this realm finds: their own, or 15% of the time one lower."""
    tier = alchemy.HERB_TIER_BY_REALM[realm]
    i = alchemy.GRADES.index(tier)
    if i > 0 and rng.random() < alchemy.LOWER_TIER_CHANCE:
        return alchemy.GRADES[i - 1]
    return tier


def age_odds(streak=0):
    """{age: chance}. The Herbal Insight streak multiplies the 50-year-and-older chances;
    the 10-year chance takes whatever is left."""
    mult = next(m for min_streak, m in alchemy.STREAK_BONUS if streak >= min_streak)
    odds = {age: a["chance"] * (mult if age > 10 else 1) for age, a in alchemy.HERB_AGES.items()}
    odds[10] = max(0.0, 1 - sum(v for age, v in odds.items() if age > 10))
    return odds


def roll_herb_type(rng=random):
    return pick(alchemy.HERB_TYPE_CHANCE, rng)


def roll_age(rng=random, streak=0):
    return pick(age_odds(streak), rng)


def herb(tier="Mortal", type_=None, age=10, rng=random):
    """A herb ready for the bag. Herbs of the same kind and age stack."""
    type_ = type_ or roll_herb_type(rng)
    name = alchemy.HERBS[tier][type_][0]
    return {"category": "herbs", "key": f"{tier}:{type_}:{age}", "name": name, "grade": tier,
            "data": {"tier": tier, "type": type_, "age": age}}


def roll_herb(realm, rng=random, streak=0):
    """A random herb for this realm with a rolled type and age (herb patches, rewards)."""
    return herb(herb_tier(realm, rng), roll_herb_type(rng), roll_age(rng, streak))


def herb_label(item):
    """'🌿 50-year Silver Moss'."""
    age = (item.get("data") or {}).get("age", 10)
    return f"{AGE_EMOJI.get(age, '🌱')} {age}-year {item['name']}"


# Herbs from before alchemy, turned into the Mortal herb closest to them (db.connect runs this once)
OLD_HERBS = {"Spirit Grass": "qi", "Dew Lotus Petal": "purity", "Red Ginseng Root": "healing",
             "Moonlight Fern": "purity", "Tiger Bone Moss": "breakthrough"}


def pill(grade):
    return {"category": "pills", "key": grade, "name": alchemy.QI_PILLS[grade]["name"], "grade": grade}


HEAVEN_DEFYING = {"category": "pills", "key": "heaven_defying", "name": "Heaven-Defying Pill", "grade": "Heaven"}


def announcement(player_name, item):
    """Server-wide announcement text for a rare find, or None (equipment.md / explore.md)."""
    if item["category"] == "weapons" and item["grade"] in equipments.ANNOUNCE_TIERS:
        return f"📢 **{player_name}** has found a Divine weapon: **{item['name']}**! The heavens take notice."
    if item["category"] == "manuals" and item["grade"] in explore.ANNOUNCE_MANUAL_GRADES:
        return f"📢 **{player_name}** has found a Heaven-grade manual: **{item['name']}**!"
    if item.get("key") == "heaven_defying":
        return f"📢 **{player_name}** has found a **Heaven-Defying Pill**!"
    return None


def talent_announcement(player_name, talent_name):
    if talent_name in talent.ANNOUNCE_TALENTS:
        return f"📢 The Aptitude Stone blazes! **{player_name}** has **{talent_name} Talent**!"
    return None


def open_chest(player, tier, rng=random):
    """Roll a chest's contents. Returns (coins, [items])."""
    coins = roll_coins(player, CHEST_COINS[tier], rng)
    items = []
    if rng.random() < explore.CHEST_MANUAL_CHANCE[tier]:
        items.append(roll_manual(pick(explore.CHEST_MANUAL_GRADE_ODDS[tier], rng), rng))
    if rng.random() < equipments.CHEST_WEAPON_CHANCE[tier]:
        items.append(roll_weapon(pick(equipments.CHEST_TIER_ODDS[tier], rng), rng))
    if tier == "jade" and rng.random() < talent.HEAVEN_DEFYING_PILL["jade_chest_chance"]:
        items.append(dict(HEAVEN_DEFYING))
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
    name = herb_label(item) if item["category"] == "herbs" else item["name"]
    return name + (f" ×{qty}" if qty > 1 else "")


def store(conn, user_id, items):
    """Put items in the bag. Returns (stored, left_behind)."""
    stored, lost = [], []
    for it in items:
        ok = db.add_item(conn, user_id, it["category"], it["key"], it["name"], it.get("grade"),
                         it.get("qty", 1), it.get("data"))
        (stored if ok else lost).append(it)
    return stored, lost


# ── Using items from the bag ──────────────────────────────────────────

def use_item(conn, user_id, item_id, rng=random, now=None, announce=None):
    """Use one item. Returns a message for the player. Rare finds are appended to `announce`."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    item = db.get_item(conn, user_id, item_id)
    if not item:
        return "That item is no longer in your bag."
    cat = item["category"]

    if cat == "chests":
        coins, found = open_chest(p, item["key"], rng)
        db.remove_item(conn, item_id)
        db.add_coins(conn, user_id, coins, f"Opened {item['name']}")
        stored, lost = store(conn, user_id, found)
        if announce is not None:
            announce += [a for a in (announcement(p["name"], i) for i in stored) if a]
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
            from . import mastery
            exp, note = mastery.gain(conn, p, learned[0], INSIGHT_EXP * technique.GRADE_EXP_MULTIPLIER[t["grade"]],
                                     bonus=False)
            msg = f"📜 You already know **{t['name']}**. Rereading it gives you insight: **+{exp} mastery EXP**."
            return msg + (f"\n{note}" if note else "")
        db.learn_technique(conn, user_id, t["name"], t["type"], t["grade"], rules.technique_slots(p["realm"]))
        return (f"📜 You comprehend **{t['name']}** ({t['grade']} {t['type']}) and equip it "
                f"in your {t['type']} slot.")

    if cat == "pills" and item["key"] == "heaven_defying":
        new = rules.talent_up(p["talent"])
        if new == p["talent"]:
            return f"Your talent is already **{p['talent']}**. The pill would be wasted."
        db.remove_item(conn, item_id)
        db.update_player(conn, user_id, talent=new)
        if announce is not None and talent_announcement(p["name"], new):
            announce.append(talent_announcement(p["name"], new))
        return f"🔥 The pill burns through your meridians... Your talent rises from **{p['talent']}** to **{new}**!"

    if cat == "pills":
        current = rules.active_pill(p, now)
        if current:
            return f"Your **{alchemy.QI_PILLS[current[0]]['name']}** is still working ({rules.fmt_duration(current[2])} left). Pills do not stack."
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

    if cat == "herbs":
        return f"**{item['name']}** goes into pills. Alchemy (/craft) opens soon; keep gathering with /gather."
    return f"**{item['name']}** has no use yet."
