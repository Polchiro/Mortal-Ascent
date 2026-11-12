"""
Game rules applied to a stored player: derived stats and the data dicts the
card renderers (profile_card.render_profile, balance_card.render_balance) expect.

All numbers come from the constants modules at the repo root.
"""
import alchemy
import random
import time

import economy
import realms
import stats
import talent
import technique
import training

from . import gear

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


def technique_slots(realm):
    """2 slots (1 attack + 1 defense); Martial Warrior adds a flex slot (technique.md)."""
    return 3 if realm_index(realm) >= realm_index("Martial Warrior") else 2


def realm_index(realm):
    return REALM_ORDER.index(realm)


def realm_scale(realm):
    """Lotus Coin amounts double with each realm (Mortal ×1, Martial Apprentice ×2, ...).
    Our default until economy.md sets real numbers."""
    return 2 ** realm_index(realm)


def roll_talent(rng=random):
    names = list(talent.TALENT_ROLL_ODDS)
    return rng.choices(names, weights=[talent.TALENT_ROLL_ODDS[n] for n in names])[0]


PHYSICIAN_COINS_PER_MINUTE = 1      # DEFAULT price (× realm scale) until economy.md sets one


def physician_cost(player, now=None):
    minutes = -(-injured_for(player, now) // 60)
    return int(max(1, minutes) * PHYSICIAN_COINS_PER_MINUTE * realm_scale(player["realm"]))


def fate_reroll_cost(player):
    """Flat price: every Fate Reroll costs the same. fate_rerolls is only a count for stats."""
    return talent.FATE_REROLL["cost"]


def reroll_talent(current, can_go_lower=True, rng=random):
    new = roll_talent(rng)
    if not can_go_lower and talent.TALENTS.index(new) < talent.TALENTS.index(current):
        return current
    return new


def talent_up(current):
    i = min(talent.TALENTS.index(current) + talent.HEAVEN_DEFYING_PILL["rank_increase"],
            talent.TALENTS.index(talent.HEAVEN_DEFYING_PILL["max_talent"]))
    return talent.TALENTS[i]


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
    """Final Qi Rate = Base Rate × (1 + Talent + Technique + Qi artifact + Blessing) × Pill × Blessed Land.
    Returns (rate, multiplier)."""
    bonus = (training.TALENT_QI_BONUS[player["talent"]] + technique_qi_bonus(techniques)
             + gear.artifact_bonus(player, "qi_rate"))          # Qi artifact (聚) adds like the other % buffs
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
    if not any((grade == "any" or t["grade"] == grade) and stage_of(t) >= need_idx for t in techniques):
        what = "a technique" if grade == "any" else f"a {grade} technique"
        return f"{what} at **{stage}**"
    need_king = req.get("beast_king_kill")
    if need_king:
        realm = player["realm"] if need_king == "own_realm" else need_king
        if realm not in king_kills(player):
            return f"a victory over the **{realm}** Beast King (find its den in /explore and hunt it with a team)"
    return None


def king_kills(player):
    return [r for r in (player.get("king_kills") or "").split(",") if r]


def next_gate(player):
    """What filling the current bar leads to: ("layer", None), ("phase", phase), ("realm", realm) or ("peak", None)."""
    realm, layer = player["realm"], player["layer"]
    if layer >= max_layer(realm):
        if realm == REALM_ORDER[-1]:
            return "peak", None
        return "realm", REALM_ORDER[realm_index(realm) + 1]
    if phase_for(layer) != phase_for(layer + 1):
        return "phase", phase_for(layer + 1)
    return "layer", None


def breakthrough_chance(player, bonus=0.0):
    """Chance to pass the gate ahead (None when there is no gate). Gates get harder at higher realms
    (training.PHASE_BOTTLENECK_SUCCESS / REALM_BREAKTHROUGH_SUCCESS). bonus: a Breakthrough pill's
    added chance. Pills and artifacts only help at realm gates, and never past BREAKTHROUGH_CHANCE_CAP."""
    kind, target = next_gate(player)
    if kind == "realm":
        if player["realm"] == "Mortal":
            return 1.0
        base = training.REALM_BREAKTHROUGH_SUCCESS[target]
        extra = gear.artifact_bonus(player, "breakthrough_chance") + (bonus or 0)
        return min(max(base, training.BREAKTHROUGH_CHANCE_CAP), base + extra)
    if kind == "phase":
        return training.PHASE_BOTTLENECK_SUCCESS[player["realm"]]
    return None


def pill_helps(player):
    """True when a Breakthrough pill could still raise the chance at this gate (realm gate, below the cap)."""
    return (next_gate(player)[0] == "realm"
            and breakthrough_chance(player) < training.BREAKTHROUGH_CHANCE_CAP)


def overflow(player):
    """Qi gathered while the bar was full at a gate: kept here, never lost (it flows on after a breakthrough)."""
    return player.get("qi_overflow") or 0.0


def refill_bar(player):
    """At a bottleneck or realm gate, top the bar back up from the Qi waiting in qi_overflow.
    The bar and qi_overflow are one pool of the player's Qi: a failed breakthrough takes its cost
    from the bar, and without this the waiting Qi could never refill it, so the player was stuck
    gathering the lost Qi again while hundreds sat unused behind the gate. Mutates `player`."""
    player["qi_overflow"] = overflow(player)
    if next_gate(player)[0] == "layer" or player["qi_overflow"] <= 0:
        return player
    room = qi_needed(player["realm"], player["layer"]) - player["qi"]
    if room > 0:
        move = min(room, player["qi_overflow"])
        player["qi"] += move
        player["qi_overflow"] -= move
    return player


def waiting_text(player):
    """", 180 Qi is waiting" style suffix for full-bar messages, or "" when nothing waits."""
    extra = overflow(player)
    return f": **{extra:,.0f} Qi** is waiting" if extra >= 0.5 else ""


def at_full_gate(player):
    """True when the bar is full and only /breakthrough (or nothing, at the peak) moves it on."""
    return (next_gate(player)[0] != "layer"
            and player["qi"] >= qi_needed(player["realm"], player["layer"]))


def ready_to_break(player, techniques=()):
    """Bar full at a phase bottleneck or realm gate whose other requirements are met."""
    kind, target = next_gate(player)
    if kind not in ("phase", "realm") or not at_full_gate(player):
        return False
    return kind == "phase" or not realm_requirement_missing(player, techniques, target)


def gate_key(player):
    """Names the gate the player stands at, so the full-bar ping is sent once per gate."""
    return f"{player['realm']}:{player['layer']}"


def progress_fields(player):
    """The columns add_qi / attempt_breakthrough change, ready for db.update_player."""
    return {"qi": player["qi"], "qi_overflow": overflow(player), "realm": player["realm"], "layer": player["layer"],
            "breakthroughs": player.get("breakthroughs", 0),
            "failed_breakthroughs": player.get("failed_breakthroughs", 0),
            "injured_until": player.get("injured_until")}


def add_qi(player, amount, techniques=(), rng=random, now=None):
    """Add Qi. Layer → layer within a phase is automatic (training.md); at a phase bottleneck or
    realm gate the bar stays exactly full and every extra point goes to player["qi_overflow"],
    which flows into the next layers after a successful /breakthrough. No Qi is ever thrown away.
    Mutates and returns `player`, plus a list of event strings."""
    events = []
    refill_bar(player)
    player["qi"] += amount
    while player["qi"] >= qi_needed(player["realm"], player["layer"]):
        need = qi_needed(player["realm"], player["layer"])
        kind, target = next_gate(player)
        if kind == "layer":
            player["qi"] -= need
            player["layer"] += 1
            events.append(f"⬆️ You reached the **{ordinal(player['layer'])} Layer**!")
            continue
        player["qi_overflow"] += player["qi"] - need
        player["qi"] = need
        waiting = waiting_text(player)
        if kind == "peak":
            events.append("You stand at the peak of the martial world. The Heavenly Tribulation awaits...")
        elif kind == "phase":
            events.append(f"⛰️ Your Qi is full and presses against the **{target}** bottleneck. "
                          f"Use **/breakthrough**{waiting}!")
        else:
            missing = realm_requirement_missing(player, techniques, target)
            if missing:
                events.append(f"🔒 Your Qi is full, but reaching **{target}** also needs {missing}."
                              + (f" {waiting[2:]} behind the gate." if waiting else ""))
            else:
                events.append(f"🌟 Your Qi is full! Use **/breakthrough**{waiting} to reach **{target}**.")
        break
    return player, events


def attempt_breakthrough(player, techniques=(), rng=random, now=None, bonus=0.0):
    """Try the phase or realm breakthrough. Mutates player. Returns (success or None if not possible, message).
    bonus: added chance from a Breakthrough pill (realm gates only).
    Success: the Qi waiting in qi_overflow flows into the new layer through add_qi (it can fill several
    layers and stops at the next gate again). Failure: lose 20% of the bar; Qi waiting in qi_overflow refills the bar (refill_bar)."""
    now = time.time() if now is None else now
    refill_bar(player)
    need = qi_needed(player["realm"], player["layer"])
    kind, target = next_gate(player)
    if kind in ("layer", "peak"):
        return None, "There is no bottleneck ahead of you. Layers within a phase open on their own as Qi fills."
    if player["qi"] < need:
        return None, f"Your Qi bar is not full yet: **{player['qi']:,.1f} / {need:,}**."
    if kind == "realm":
        missing = realm_requirement_missing(player, techniques, target)
        if missing:
            return None, f"🔒 To reach **{target}** you also need {missing}."
    chance = breakthrough_chance(player, bonus)
    if rng.random() < chance:
        carry = player["qi"] - need + overflow(player)
        player["qi"], player["qi_overflow"] = 0.0, 0.0
        player["breakthroughs"] += 1
        if kind == "realm":
            player["realm"], player["layer"] = target, 1
            msg = f"🌟 **Realm breakthrough!** Heaven and earth tremble. You are now **{target}**, 1st Layer!"
        else:
            player["layer"] += 1
            msg = f"⛰️ **Bottleneck broken!** You enter the **{target}**, {ordinal(player['layer'])} Layer."
        if carry > 0:
            player, events = add_qi(player, carry, techniques, rng, now)
            msg = "\n".join([msg, f"🌊 The **{carry:,.1f} Qi** that waited behind the gate floods in."] + events)
        return True, msg
    lost = player["qi"] * training.BREAKTHROUGH_FAIL_QI_LOSS
    player["qi"] -= lost
    player["failed_breakthroughs"] += 1
    waiting_before = overflow(player)
    refill_bar(player)          # the waiting Qi tops the bar back up, so the player can try again
    refilled = waiting_before - overflow(player)
    kept = ""
    if refilled >= 0.05:
        kept = f" {refilled:,.1f} of the Qi waiting behind the gate refills your bar"
        kept += (f", and {overflow(player):,.0f} Qi still waits." if overflow(player) >= 0.5 else ".")
    elif overflow(player) >= 0.5:
        kept = f" The {overflow(player):,.0f} Qi waiting behind the gate is safe."
    if kind == "realm":
        player["injured_until"] = now + training.INJURY_HOURS * 3600
        return False, (f"💥 **Breakthrough failed!** Your meridians recoil. You lose {lost:,.1f} Qi and are injured "
                       f"for {training.INJURY_HOURS} hours (no exploring or sparring).{kept}")
    return False, f"💢 **The bottleneck holds.** You lose {lost:,.1f} Qi. Gather it again and retry.{kept}"


# ── Passive Qi ────────────────────────────────────────────────────────

def passive_qi(player, techniques=(), now=None):
    """(Qi gathered by passive gathering since it was last banked, hours counted). It always gathers at
    the full Qi Rate, with no limit on how long the player is away."""
    now = time.time() if now is None else now
    since = player.get("qi_collected_at")
    if since is None:
        since = player["created_at"]
    hours = max(0.0, now - since) / 3600
    return qi_rate(player, now, techniques)[0] * hours, hours


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


def stage_of(tech):
    """Current mastery stage index. Stored techniques carry it (raised by passing a trial);
    plain dicts without it fall back to what their EXP would reach."""
    if tech.get("stage") is not None:
        return tech["stage"]
    return mastery_index(tech.get("mastery_exp", 0), tech["grade"])


def mastery_mult(tech):
    return technique.MASTERY_STAGES[stage_of(tech)]["multiplier"]


def mastery_cap(tech):
    """EXP needed to fill the bar for the next stage, or None at the last stage."""
    nxt = stage_of(tech) + 1
    if nxt >= len(technique.MASTERY_STAGES):
        return None
    return round(technique.MASTERY_STAGES[nxt]["exp_to_reach"] * technique.GRADE_EXP_MULTIPLIER[tech["grade"]])


def bar_full(tech):
    cap = mastery_cap(tech)
    return cap is not None and tech["mastery_exp"] >= cap


def mastery_bonus(player, now=None):
    """Multiplier on mastery EXP from a Heavenly Blessing, the Insight artifact (书) and a Blessed Land."""
    b = active_blessing(player, now)
    mult = 1 + (economy.BLESSING_TIERS[b[0]]["mastery_exp"] if b else 0) + gear.artifact_bonus(player, "mastery_exp")
    land = active_blessed_land(player, now)
    if land:
        mult *= training.BLESSED_LANDS[land[0]]["mastery_multiplier"]
    return mult


def daily_rate(rates, done_today):
    """rates like technique.PRACTICE_DAILY_RATES: [(sessions, rate), ..., (None, rate)]."""
    for n, rate in rates:
        if n is None or done_today < n:
            return rate
        done_today -= n
    return rates[-1][1]


# ── Final stats (stats.md: all % buffs of a stat add up, then apply once) ──

def weapon_buffs(weapon):
    return (weapon or {}).get("data", {}).get("buffs", {})


def buff_text(buffs):
    return "  ·  ".join(f"+{round(v * 100)}% {STAT_LABELS[k]}" for k, v in buffs.items()) or "No buffs"


def stat_buffs(techniques=(), weapon=None, armor=None):
    """Every % buff by stat, with where it comes from: {"hp": [(source, pct), ...], ...}.
    Armor buffs add in exactly like weapon buffs (equipment.md), and so do forged stat passives (Keen Edge...)."""
    from . import passives
    out = {"hp": [], "attack": [], "defense": []}
    for item in (weapon, armor):
        for k, v in weapon_buffs(item).items():
            out[k].append((item["name"], v))
    for name, k, v in passives.stat_passives([i for i in (weapon, armor) if i]):     # forged passives (forge.py)
        out[k].append((name, v))
    for t in techniques:
        table = technique.ATTACK_TECHNIQUE if t["type"] == "attack" else technique.DEFENSE_TECHNIQUE
        out["attack" if t["type"] == "attack" else "defense"].append((t["name"], table[t["grade"]][1] * mastery_mult(t)))
    return out


def attribute_points(realm, layer):
    """Strength / Vitality points earned at (realm, layer): one per layer climbed since Mortal layer 1."""
    climbed = sum(max_layer(r) for r in REALM_ORDER[:REALM_ORDER.index(realm)]) + layer - 1
    return climbed * stats.ATTRIBUTE_POINTS_PER_LAYER


def unspent_points(player):
    return max(0, attribute_points(player["realm"], player["layer"])
               - (player.get("strength") or 0) - (player.get("vitality") or 0) - (player.get("spirit") or 0))


def attribute_buffs(player, cap=None):
    """{"attack": [("Strength", pct)], "hp": [("Vitality", pct)]} from the points the player placed.
    cap: the most points that count (Fair Duels: what the lower player's level earns), shared in proportion."""
    s, v = (player.get("strength") or 0), (player.get("vitality") or 0)
    if cap is not None and s + v > cap:
        scale = cap / (s + v)
        s, v = s * scale, v * scale
    out = {"hp": [], "attack": [], "defense": []}
    if s:
        out["attack"].append(("Strength", s * stats.STRENGTH_ATTACK))
    if v:
        out["hp"].append(("Vitality", v * stats.VITALITY_HP))
    return out


def all_buffs(player, techniques=(), weapon=None, armor=None):
    """stat_buffs plus Strength and Vitality: everything final_stats adds to the realm's base."""
    out = stat_buffs(techniques, weapon, armor)
    for k, src in attribute_buffs(player).items():
        out[k] += src
    return out


def final_stats(player, techniques=(), weapon=None, armor=None):
    """(hp, attack, defense) after Strength / Vitality, weapon, armor and technique passive buffs."""
    hp, attack, defense = base_stats(player["realm"], player["layer"])
    pct = {k: sum(v for _, v in src) for k, src in all_buffs(player, techniques, weapon, armor).items()}
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
    decayed = int((now - player["toxicity_at"]) // (toxicity_decay_hours(player) * 3600))
    return min(toxicity_cap(player), max(0, tox - decayed))


def toxicity_cap(player):
    """The most toxicity this player can carry: Dao Heart (a forged artifact passive) caps it, else no cap."""
    from . import passives
    cap = passives.artifact_passive(player, "dao_heart", "max_toxicity")
    return cap if cap else float("inf")


def add_toxicity(player, tox_now, added):
    return min(toxicity_cap(player), tox_now + added)


def toxicity_fields(player, new_tox, now=None):
    """The toxicity and toxicity_at to save after a pill changes toxicity to new_tox.
    The fading clock keeps the time already spent toward the next point, so swallowing a pill
    (a Cleansing pill above all) never makes the next point of toxicity take longer to fade."""
    now = time.time() if now is None else now
    if not new_tox or not player.get("toxicity") or player.get("toxicity_at") is None:
        return {"toxicity": new_tox, "toxicity_at": now}
    period = toxicity_decay_hours(player) * 3600
    faded = min(player["toxicity"], int((now - player["toxicity_at"]) // period))
    if faded >= player["toxicity"]:                    # it had all faded: the clock starts fresh
        return {"toxicity": new_tox, "toxicity_at": now}
    return {"toxicity": new_tox, "toxicity_at": player["toxicity_at"] + faded * period}


def toxicity_decay_hours(player=None):
    """Hours for 1 toxicity to fade. The Purity artifact (玉) makes it fade that much faster."""
    return training.TOXICITY_DECAY_HOURS / (1 + gear.artifact_bonus(player, "toxicity_decay_faster"))


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
        parts.append(f"{alchemy.QI_PILLS[pill[0]]['name']} ({fmt_duration(pill[2])})")
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
                        "mastery": technique.MASTERY_STAGES[stage_of(t)]["name"]} for t in techniques[:3]],
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
