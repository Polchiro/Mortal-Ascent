"""
Game rules applied to a stored player: derived stats and the data dicts the
card renderers (profile_card.render_profile, balance_card.render_balance) expect.

All numbers come from the constants modules at the repo root.
"""
import random
import time

import economy
import realms
import stats
import talent
import technique
import training

REALM_ORDER = ["Mortal"] + realms.REALMS

STARTING_LOTUS_COINS = 50                       # docs/tutorial.md: /start
STARTING_TECHNIQUE_NAMES = {                    # docs/tutorial.md: /start
    "attack": "Iron Fist",
    "defense": "Horse Stance Guard",
}
NO_WEAPON = {"name": "Bare Hands", "tier": "ordinary", "buffs": "No weapon equipped"}


def roll_talent(rng=random):
    names = list(talent.TALENT_ROLL_ODDS)
    return rng.choices(names, weights=[talent.TALENT_ROLL_ODDS[n] for n in names])[0]


def starting_techniques():
    return [{"name": STARTING_TECHNIQUE_NAMES[t["type"]], "type": t["type"], "grade": t["grade"]}
            for t in technique.STARTING_TECHNIQUES]


def phase_for(layer):
    for name, (lo, hi) in realms.PHASES.items():
        if lo <= layer <= hi:
            return name
    raise ValueError(f"layer {layer} out of range")


def layer_hp_multiplier(layer):
    if layer >= realms.LAYERS_PER_REALM:
        return stats.PEAK_LAYER_MULTIPLIER
    return 1 + stats.HP_BONUS_PER_LAYER * (layer - 1)


def base_stats(realm, layer):
    hp = stats.BASE_HP[realm] * layer_hp_multiplier(layer)
    attack = hp * stats.ATTACK_RATIO
    defense = attack * stats.DEFENSE_RATIO
    return round(hp), round(attack), round(defense)


def active_blessing(player, now=None):
    """Return (tier_name, days_left) or None."""
    tier, expires = player.get("blessing_tier"), player.get("blessing_expires")
    now = time.time() if now is None else now
    if not tier or not expires or expires <= now or tier not in economy.BLESSING_TIERS:
        return None
    days_left = max(1, int((expires - now) // 86400) + (1 if (expires - now) % 86400 else 0))
    return tier, min(days_left, economy.BLESSING_DURATION_DAYS)


def qi_rate(player, now=None):
    """Final Qi Rate = Base Rate × (1 + Talent + Technique + Blessing) × Pill. Returns (rate, multiplier).
    Technique and pill bonuses are 0 / ×1 until those systems exist."""
    bonus = training.TALENT_QI_BONUS[player["talent"]]
    b = active_blessing(player, now)
    if b:
        bonus += economy.BLESSING_TIERS[b[0]]["qi_rate"]
    mult = 1 + bonus
    return training.BASE_QI_RATE[player["realm"]] * mult, mult


def qi_needed(realm, layer):
    return round(training.QI_PER_LAYER[realm] * training.PHASE_QI_MULTIPLIER[phase_for(layer)])


def mastery_stage(exp):
    name = technique.MASTERY_STAGES[0]["name"]
    for stage in technique.MASTERY_STAGES:
        if exp >= stage["exp_to_reach"]:
            name = stage["name"]
    return name


def blessing_perks(tier):
    labels = {"qi_rate": "Qi Rate", "lotus_coins": "Lotus Coins", "mastery_exp": "Mastery EXP",
              "chest_drop": "Chest Drops", "comprehension": "Comprehension"}
    t = economy.BLESSING_TIERS[tier]
    return "  ·  ".join(f"+{t[k] * 100:g}% {label}" for k, label in labels.items() if t[k])


def profile_data(player, techniques, rank, avatar_path=None, now=None):
    hp, attack, defense = base_stats(player["realm"], player["layer"])
    rate, mult = qi_rate(player, now)
    b = active_blessing(player, now)
    return {
        "name": player["name"],
        "talent": player["talent"],
        "rank": rank,
        "realm": player["realm"],
        "phase": phase_for(player["layer"]),
        "layer": player["layer"],
        "qi": player["qi"],
        "qi_needed": qi_needed(player["realm"], player["layer"]),
        "qi_rate": rate,
        "qi_mult": mult,
        "hp": hp,
        "attack": attack,
        "defense": defense,
        "coins": player["lotus_coins"],
        "techniques": [{"name": t["name"], "grade": t["grade"], "type": t["type"],
                        "mastery": mastery_stage(t["mastery_exp"])} for t in techniques[:3]],
        "weapon": NO_WEAPON,
        "beasts": player["beasts_slain"],
        "breakthroughs": player["breakthroughs"],
        "failed": player["failed_breakthroughs"],
        "status": f"{b[0]} Blessing active" if b else "",
        "avatar_path": avatar_path,
    }


def balance_data(player, now=None):
    b = active_blessing(player, now)
    return {
        "name": player["name"],
        "realm": player["realm"],
        "talent": player["talent"],
        "coins": player["lotus_coins"],
        "pearls": player["moon_pearls"],
        "blessing": {"tier": b[0], "days_left": b[1], "perks": blessing_perks(b[0])} if b else None,
    }
