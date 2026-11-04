"""
Auto-resolved fights for /explore, using the damage formula in docs/stats.md.

The full Strike / Guard / Break combat screen is not designed yet, so for now
fights play out on their own and the player gets a short battle report.
The player strikes with their equipped attack technique every turn (Heavy
techniques alternate with a basic strike), and their defense technique
catches about a third of incoming hits. Each use gives +20 mastery EXP
(technique.COMBAT_EXP_PER_USE).
"""
import random

import beasts
import stats
import technique

from . import player as rules

GUARD_CHANCE = 0.35        # DEFAULT: share of enemy hits the defense technique catches
MAX_ROUNDS = 40
BANDIT_STRENGTH = 0.9      # DEFAULT: bandits have 90% of a same-layer player's HP and Attack
BANDIT_NAMES = ["Mountain Bandits", "Black Wind Robbers", "Highway Thugs", "Red Scarf Gang"]


def damage(attack, defense, target_max_hp, skill=1.0, pierce=0.0, rng=random):
    defense *= (1 - pierce)
    reduction = defense / (defense + attack) if defense + attack else 0
    dmg = attack * skill * (1 - reduction) * rng.uniform(stats.DAMAGE_RANDOM_MIN, stats.DAMAGE_RANDOM_MAX)
    return min(dmg, target_max_hp * stats.MAX_HIT_PERCENT)


def beast_stats(player, beast, step=1):
    """beast = (name, tier, role) from beasts.BEASTS. Stats follow beast.md."""
    name, tier, role = beast
    hp, attack, _ = rules.base_stats(player["realm"], player["layer"])
    t, r = beasts.BEAST_TIERS[tier], beasts.ROLES[role]
    step_bonus = 1 + (step - 1) * 0.10
    hp = hp * t["hp"] * r.get("hp", 1) * step_bonus
    atk = attack * t["attack"] * r.get("attack", 1) * step_bonus
    dfn = atk * beasts.BEAST_DEFENSE_RATIO * r.get("defense", 1)
    return {"name": name, "tier": tier, "role": role, "hp": round(hp), "max_hp": round(hp),
            "attack": atk, "defense": dfn, "dodge": r.get("dodge", 0)}


def bandit_stats(player, rng=random):
    hp, attack, defense = rules.base_stats(player["realm"], player["layer"])
    hp = round(hp * BANDIT_STRENGTH)
    return {"name": rng.choice(BANDIT_NAMES), "tier": "bandit", "role": None, "hp": hp, "max_hp": hp,
            "attack": attack * BANDIT_STRENGTH, "defense": defense, "dodge": 0}


def fight(hero, enemy, techniques, rng=random):
    """hero: {"hp", "max_hp", "attack", "defense"}. Mutates both hp values.
    Returns {"won", "rounds", "attack_uses", "guard_uses", "log"}."""
    atk_t = next((t for t in techniques if t["type"] == "attack"), None)
    def_t = next((t for t in techniques if t["type"] == "defense"), None)
    atk_eff = rules.TECH_BY_NAME.get(atk_t["name"], {}).get("effect") if atk_t else None
    def_eff = rules.TECH_BY_NAME.get(def_t["name"], {}).get("effect") if def_t else None
    atk_mult = technique.ATTACK_TECHNIQUE[atk_t["grade"]][0] * rules.mastery_mult(atk_t) if atk_t else 1.0
    block = min(technique.MAX_DAMAGE_BLOCKED,
                technique.DEFENSE_TECHNIQUE[def_t["grade"]][0] * rules.mastery_mult(def_t)) if def_t else 0
    res = {"won": False, "rounds": 0, "attack_uses": 0, "guard_uses": 0, "dodged": 0, "log": []}
    heavy_last = False

    for rnd in range(1, MAX_ROUNDS + 1):
        res["rounds"] = rnd
        # hero's turn
        kind, val = atk_eff or (None, None)
        use_tech = atk_t is not None and not (kind == "heavy" and heavy_last)
        heavy_last = use_tech and kind == "heavy"
        if use_tech:
            res["attack_uses"] += 1
        skill = atk_mult if use_tech else stats.BASIC_ATTACK_MULTIPLIER
        hits, per_hit, pierce = 1, 1.0, 0.0
        if use_tech and kind == "combo":
            hits, per_hit = val
        elif use_tech and kind == "pierce":
            pierce = val
        elif use_tech and kind == "heavy":
            skill *= val
        total = 0.0
        for _ in range(hits):
            if enemy["dodge"] and rng.random() < enemy["dodge"]:
                res["dodged"] += 1
                continue
            total += damage(hero["attack"], enemy["defense"], enemy["max_hp"], skill * per_hit, pierce, rng)
        total = min(total, enemy["max_hp"] * stats.MAX_HIT_PERCENT)   # cap is per turn (technique.md)
        enemy["hp"] = max(0, enemy["hp"] - total)
        if enemy["hp"] <= 0:
            res["won"] = True
            break

        # enemy's turn
        dmg = damage(enemy["attack"], hero["defense"], hero["max_hp"], rng=rng)
        if def_t and rng.random() < GUARD_CHANCE:
            res["guard_uses"] += 1
            dkind, dval = def_eff or (None, None)
            if dkind == "evade" and rng.random() < dval:
                dmg = 0
            else:
                blocked = dmg * block
                dmg -= blocked
                if dkind == "counter":
                    enemy["hp"] = max(0, enemy["hp"] - blocked * dval)
                elif dkind == "recover":
                    hero["hp"] = min(hero["max_hp"], hero["hp"] + hero["max_hp"] * dval)
        hero["hp"] = max(0, hero["hp"] - dmg)
        if enemy["hp"] <= 0:
            res["won"] = True
            break
        if hero["hp"] <= 0:
            break

    hero["hp"], enemy["hp"] = round(hero["hp"]), round(enemy["hp"])
    if atk_t and res["attack_uses"]:
        res["log"].append(f"You struck with **{atk_t['name']}** {res['attack_uses']}×.")
    if def_t and res["guard_uses"]:
        res["log"].append(f"You caught {res['guard_uses']} blow(s) with **{def_t['name']}**.")
    if res["dodged"]:
        res["log"].append(f"The {enemy['name']} dodged {res['dodged']} of your hits.")
    return res
