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
TECH_BY_NAME = {t["name"]: dict(t, key=k) for k, t in technique.TECHNIQUES.items()}
STAT_LABELS = {"attack": "ATK", "defense": "DEF", "hp": "HP"}


def fmt_duration(seconds):
    seconds = int(max(0, seconds))
    h, m = divmod(seconds // 60, 60)
    if h:
        return f"{h}h {m}m" if m else f"{h}h"
    return f"{max(1, m)}m" if seconds >= 60 else f"{seconds}s"


def realm_index(realm):
    return REALM_ORDER.index(realm)


def realm_scale(realm):
    """Lotus Coin amounts double with each realm (Mortal ×1, Martial Apprentice ×2, ...).
    Our default until economy.md sets real numbers."""
    return 2 ** realm_index(realm)


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


def qi_rate(player, now=None, techniques=()):
    """Final Qi Rate = Base Rate × (1 + Talent + Technique + Blessing) × Pill × Blessed Land.
    Returns (rate, multiplier)."""
    bonus = training.TALENT_QI_BONUS[player["talent"]] + technique_qi_bonus(techniques)
    b = active_blessing(player, now)
    if b:
        bonus += economy.BLESSING_TIERS[b[0]]["qi_rate"]
    mult = 1 + bonus
    pill = active_pill(player, now)
    if pill:
        mult *= pill[1]
    land = active_blessed_land(player, now)
    if land:
        mult *= training.BLESSED_LANDS[land[0]]["qi_multiplier"]
    return training.BASE_QI_RATE[player["realm"]] * mult, mult


def qi_needed(realm, layer):
    return round(training.QI_PER_LAYER[realm] * training.PHASE_QI_MULTIPLIER[phase_for(layer)])


def max_layer(realm):
    return 3 if realm == "Mortal" else realms.LAYERS_PER_REALM


def realm_requirement_missing(player, techniques, target_realm):
    """Text describing what's still missing for target_realm, or None if nothing."""
    req = training.REALM_REQUIREMENTS.get(target_realm)
    if not req:
        return None
    grade, stage = req["technique_mastery"]
    need_idx = [s["name"] for s in technique.MASTERY_STAGES].index(stage)
    if not any((grade == "any" or t["grade"] == grade)
               and mastery_index(t["mastery_exp"], t["grade"]) >= need_idx for t in techniques):
        what = "a technique" if grade == "any" else f"a {grade} technique"
        return f"{what} at **{stage}**"
    if req.get("beast_king_kill"):
        return "a Beast King kill (team hunts are not in the game yet)"
    return None


def add_qi(player, amount, techniques=(), rng=random, now=None):
    """Add Qi and run breakthroughs (training.md). Mutates and returns `player`, plus a list of
    event strings. Layer→layer is automatic; phase bottlenecks roll 90%, realm breakthroughs 70%.
    Mortal → Martial Apprentice always succeeds (tutorial lesson 8)."""
    now = time.time() if now is None else now
    events = []
    player["qi"] += amount
    while player["qi"] >= qi_needed(player["realm"], player["layer"]):
        need = qi_needed(player["realm"], player["layer"])
        realm, layer = player["realm"], player["layer"]
        top = layer >= max_layer(realm)
        if top and realm == REALM_ORDER[-1]:
            player["qi"] = need
            events.append("You stand at the peak of the martial world. The Heavenly Tribulation awaits...")
            break
        if top:
            target = REALM_ORDER[realm_index(realm) + 1]
            missing = realm_requirement_missing(player, techniques, target)
            if missing:
                player["qi"] = need
                events.append(f"🔒 Your Qi is full, but reaching **{target}** also needs {missing}.")
                break
            chance = 1.0 if realm == "Mortal" else training.REALM_BREAKTHROUGH_SUCCESS
            if rng.random() < chance:
                player["qi"] -= need
                player["realm"], player["layer"] = target, 1
                player["breakthroughs"] += 1
                events.append(f"🌟 **Realm breakthrough!** You are now **{target}**, 1st Layer!")
                continue
            lost = player["qi"] * training.BREAKTHROUGH_FAIL_QI_LOSS
            player["qi"] -= lost
            player["failed_breakthroughs"] += 1
            player["injured_until"] = now + training.INJURY_HOURS * 3600
            events.append(f"💥 Your breakthrough to **{target}** failed! You lost {lost:,.0f} Qi and are "
                          f"injured for {training.INJURY_HOURS} hours (no exploring).")
            break
        if phase_for(layer) != phase_for(layer + 1):
            if rng.random() >= training.PHASE_BOTTLENECK_SUCCESS:
                lost = player["qi"] * training.BREAKTHROUGH_FAIL_QI_LOSS
                player["qi"] -= lost
                player["failed_breakthroughs"] += 1
                events.append(f"💢 You hit the bottleneck into the **{phase_for(layer + 1)}** and failed. "
                              f"You lost {lost:,.0f} Qi.")
                break
            player["breakthroughs"] += 1
            player["qi"] -= need
            player["layer"] += 1
            events.append(f"⛰️ Bottleneck broken! **{phase_for(player['layer'])}**, {ordinal(player['layer'])} Layer.")
            continue
        player["qi"] -= need
        player["layer"] += 1
        events.append(f"⬆️ You reached the **{ordinal(player['layer'])} Layer**!")
    return player, events


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def mastery_index(exp, grade="Mortal"):
    """Index into technique.MASTERY_STAGES. Higher grades need more EXP (technique.md)."""
    mult = technique.GRADE_EXP_MULTIPLIER.get(grade, 1.0)
    idx = 0
    for i, stage in enumerate(technique.MASTERY_STAGES):
        if exp >= stage["exp_to_reach"] * mult:
            idx = i
    return idx


def mastery_stage(exp, grade="Mortal"):
    return technique.MASTERY_STAGES[mastery_index(exp, grade)]["name"]


def mastery_mult(tech):
    return technique.MASTERY_STAGES[mastery_index(tech["mastery_exp"], tech["grade"])]["multiplier"]


# ── Final stats (stats.md: all % buffs of a stat add up, then apply once) ──

def weapon_buffs(weapon):
    return (weapon or {}).get("data", {}).get("buffs", {})


def buff_text(buffs):
    return "  ·  ".join(f"+{round(v * 100)}% {STAT_LABELS[k]}" for k, v in buffs.items()) or "No buffs"


def final_stats(player, techniques=(), weapon=None):
    """(hp, attack, defense) after weapon and technique passive buffs."""
    hp, attack, defense = base_stats(player["realm"], player["layer"])
    pct = {"hp": 0.0, "attack": 0.0, "defense": 0.0}
    for k, v in weapon_buffs(weapon).items():
        pct[k] += v
    for t in techniques:
        table = technique.ATTACK_TECHNIQUE if t["type"] == "attack" else technique.DEFENSE_TECHNIQUE
        pct["attack" if t["type"] == "attack" else "defense"] += table[t["grade"]][1] * mastery_mult(t)
    return (round(hp * (1 + pct["hp"])), round(attack * (1 + pct["attack"])),
            round(defense * (1 + pct["defense"])))


# ── Status effects ────────────────────────────────────────────────────

def injured_for(player, now=None):
    now = time.time() if now is None else now
    return max(0.0, (player.get("injured_until") or 0) - now)


def active_pill(player, now=None):
    now = time.time() if now is None else now
    if player.get("pill_grade") and (player.get("pill_expires") or 0) > now:
        return player["pill_grade"], player["pill_mult"], player["pill_expires"] - now
    return None


def current_toxicity(player, now=None):
    now = time.time() if now is None else now
    tox = player.get("toxicity") or 0
    if not tox or player.get("toxicity_at") is None:
        return tox
    decayed = int((now - player["toxicity_at"]) // (training.TOXICITY_DECAY_HOURS * 3600))
    return max(0, tox - decayed)


def pill_effect_mult(toxicity):
    for min_tox, mult in training.PILL_TOXICITY_PENALTY:
        if toxicity >= min_tox:
            return mult
    return 1.0


def active_blessed_land(player, now=None):
    now = time.time() if now is None else now
    if player.get("blessed_land") and (player.get("blessed_land_expires") or 0) > now:
        return player["blessed_land"], player["blessed_land_expires"] - now
    return None


def technique_qi_bonus(techniques):
    """Best equipped technique's training bonus × its mastery multiplier (only the best counts)."""
    return max((technique.TRAINING_EXP_BONUS[t["grade"]] * mastery_mult(t) for t in techniques), default=0.0)


def blessing_perks(tier):
    labels = {"qi_rate": "Qi Rate", "lotus_coins": "Lotus Coins", "mastery_exp": "Mastery EXP",
              "chest_drop": "Chest Drops", "comprehension": "Comprehension"}
    t = economy.BLESSING_TIERS[tier]
    return "  ·  ".join(f"+{t[k] * 100:g}% {label}" for k, label in labels.items() if t[k])


def weapon_card(weapon):
    if not weapon:
        return NO_WEAPON
    return {"name": weapon["name"], "tier": weapon["grade"], "buffs": buff_text(weapon_buffs(weapon))}


def status_text(player, now=None):
    parts = []
    b = active_blessing(player, now)
    if b:
        parts.append(f"{b[0]} Blessing active")
    pill = active_pill(player, now)
    if pill:
        parts.append(f"{pill[0]} Qi Pill ({fmt_duration(pill[2])})")
    land = active_blessed_land(player, now)
    if land:
        parts.append(f"{land[0].replace('_', ' ').title()} ({fmt_duration(land[1])})")
    inj = injured_for(player, now)
    if inj:
        parts.append(f"Injured ({fmt_duration(inj)})")
    return "  ·  ".join(parts)


def profile_data(player, techniques, rank, avatar_path=None, now=None, weapon=None):
    hp, attack, defense = final_stats(player, techniques, weapon)
    rate, mult = qi_rate(player, now, techniques)
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
                        "mastery": mastery_stage(t["mastery_exp"], t["grade"])} for t in techniques[:3]],
        "weapon": weapon_card(weapon),
        "beasts": player["beasts_slain"],
        "breakthroughs": player["breakthroughs"],
        "failed": player["failed_breakthroughs"],
        "status": status_text(player, now),
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
