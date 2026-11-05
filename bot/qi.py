"""
/qi: everything about a player's Internal Qi in one place. Builds the data dict that
cards.dantian.render_dantian expects, using the same formulas as /meditate, /seclusion and /train
(bot/player.py, training.py).
"""
import alchemy
import time

import economy
import technique
import training

from . import player as rules

LAND_NAMES = {k: k.replace("_", " ").title() for k in training.BLESSED_LANDS}


def fmt_long(seconds):
    """Like rules.fmt_duration, but with days for long waits: 3d 4h, 5h 12m, 40m."""
    seconds = int(max(0, seconds))
    days, rest = divmod(seconds, 86400)
    if days:
        h = rest // 3600
        return f"{days}d {h}h" if h else f"{days}d"
    return rules.fmt_duration(rest)


def best_technique(techniques):
    """The equipped technique that gives the Qi bonus (only the best one counts), or None."""
    if not techniques:
        return None
    return max(techniques, key=lambda t: technique.TRAINING_EXP_BONUS[t["grade"]] * rules.mastery_mult(t))


def sources(player, techniques, now):
    """Every Qi Rate source, active or not: dicts with seal, label, detail, value, active."""
    rows = []
    base = training.BASE_QI_RATE[player["realm"]]
    rows.append({"seal": "根", "label": "Realm base", "detail": player["realm"],
                 "value": f"{base:g} Qi/h", "active": True})

    tb = training.TALENT_QI_BONUS[player["talent"]]
    rows.append({"seal": "才", "label": "Talent", "detail": player["talent"],
                 "value": f"+{tb:.0%}", "active": tb > 0})

    t = best_technique(techniques)
    bonus = rules.technique_qi_bonus(techniques)
    if t:
        stage = technique.MASTERY_STAGES[rules.stage_of(t)]["name"]
        rows.append({"seal": "功", "label": "Technique", "detail": f"{t['name']} · {stage}",
                     "value": f"+{bonus:.1%}".replace(".0%", "%"), "active": True})
    else:
        rows.append({"seal": "功", "label": "Technique", "detail": "None equipped · /techniques",
                     "value": "+0%", "active": False})

    b = rules.active_blessing(player, now)
    if b:
        rows.append({"seal": "福", "label": "Heavenly Blessing", "detail": f"{b[0]} · {b[1]}d left",
                     "value": f"+{economy.BLESSING_TIERS[b[0]]['qi_rate']:.0%}", "active": True})
    else:
        rows.append({"seal": "福", "label": "Heavenly Blessing", "detail": "None · /blessing",
                     "value": "+0%", "active": False})

    pill = rules.active_pill(player, now)
    if pill:
        rows.append({"seal": "丹", "label": "Qi Pill", "detail": f"{alchemy.QI_PILLS[pill[0]]['name']} · {fmt_long(pill[2])} left",
                     "value": f"×{pill[1]:.2f}", "active": True})
    else:
        rows.append({"seal": "丹", "label": "Qi Pill", "detail": "None · use one from /inventory",
                     "value": "×1", "active": False})

    land = rules.active_blessed_land(player, now)
    if land:
        mult = training.BLESSED_LANDS[land[0]]["qi_multiplier"]
        rows.append({"seal": "地", "label": "Blessed Land", "detail": f"{LAND_NAMES[land[0]]} · {fmt_long(land[1])} left",
                     "value": f"×{mult:g}", "active": True})
    else:
        rows.append({"seal": "地", "label": "Blessed Land", "detail": "None · found in /explore",
                     "value": "×1", "active": False})

    if rules.in_seclusion(player):
        left = player["seclusion_end"] - now
        detail = f"emerge in {fmt_long(left)}" if left > 0 else "complete · /seclusion"
        rows.append({"seal": "关", "label": "Seclusion", "detail": detail,
                     "value": f"×{training.SECLUSION_QI_MULTIPLIER:g}", "active": True})
    else:
        rows.append({"seal": "关", "label": "Seclusion", "detail": "Not secluded · /seclusion",
                     "value": "×1", "active": False})

    tox = rules.current_toxicity(player, now)
    eff = rules.pill_effect_mult(tox)
    detail = "Pills at full strength" if eff >= 1 else f"Next pill at {eff:.0%} strength"
    rows.append({"seal": "毒", "label": "Pill toxicity", "detail": f"{tox} · {detail}",
                 "value": "OK" if eff >= 1 else f"{eff:.0%}", "active": eff < 1, "warn": eff < 1})
    return rows


def formula(player, techniques, now):
    """The Final Qi Rate sum written out, e.g. 2.5 × (1 + 0.20 + 0.05) × 1.40 = 4.38 Qi/h."""
    adds = [training.TALENT_QI_BONUS[player["talent"]], rules.technique_qi_bonus(techniques)]
    b = rules.active_blessing(player, now)
    if b:
        adds.append(economy.BLESSING_TIERS[b[0]]["qi_rate"])
    parts = [f"{training.BASE_QI_RATE[player['realm']]:g}",
             "(1" + "".join(f" + {a:.3f}".rstrip("0").rstrip(".") for a in adds if a) + ")"]
    pill = rules.active_pill(player, now)
    if pill:
        parts.append(f"{pill[1]:.2f}")
    land = rules.active_blessed_land(player, now)
    if land:
        parts.append(f"{training.BLESSED_LANDS[land[0]]['qi_multiplier']:g}")
    rate = rules.qi_rate(player, now, techniques)[0]
    return " × ".join(parts) + f" = {rate:,.2f} Qi/h"


def gate_text(player, techniques):
    kind, target = rules.next_gate(player)
    if kind == "layer":
        return f"{rules.ordinal(player['layer'] + 1)} Layer", "opens on its own"
    if kind == "peak":
        return "The Peak", "no gate remains"
    chance = rules.breakthrough_chance(player)
    if kind == "phase":
        return target, f"bottleneck · {chance:.0%} chance"
    missing = rules.realm_requirement_missing(player, techniques, target)
    if missing:
        return target, "needs " + missing.replace("**", "")
    return target, f"realm gate · {chance:.0%} chance"


def qi_data(player, techniques, now=None):
    now = time.time() if now is None else now
    need = rules.qi_needed(player["realm"], player["layer"])
    qi = min(player["qi"], need)
    rate, mult = rules.qi_rate(player, now, techniques)
    kind, _ = rules.next_gate(player)
    secluded = rules.in_seclusion(player)

    # Qi gathered but not yet added to the bar
    if secluded:
        pending, hours, done = rules.seclusion_qi(player, techniques, now)
    else:
        pending, hours = rules.passive_qi(player, techniques, now)
    pending = min(pending, max(0.0, need - qi))

    # cultivation status line
    injured = rules.injured_for(player, now)
    if qi >= need and kind != "layer":
        status, tone = ("At the peak" if kind == "peak" else "Bar full · use /breakthrough"), "gold"
    elif secluded:
        left = player["seclusion_end"] - now
        status, tone = (("In seclusion · emerge in " + fmt_long(left)) if left > 0
                        else "Seclusion complete · /seclusion to emerge"), "jade"
    elif injured:
        status, tone = f"Injured · {fmt_long(injured)} to heal", "red"
    else:
        # passive Qi is banked before every command, so it rises on its own
        status, tone = "Gathering on its own", "jade"

    # time until the bar is full, at the current rate
    eff_rate = rate * (training.SECLUSION_QI_MULTIPLIER if secluded else 1)
    left_qi = need - qi - pending
    if kind == "peak" and qi >= need:
        eta = "—"
    elif left_qi <= 0:
        eta = "Ready now"
    else:
        eta = fmt_long(left_qi / eff_rate * 3600)

    gate, gate_note = gate_text(player, techniques)
    return {
        "name": player["name"],
        "realm": player["realm"],
        "phase": rules.phase_for(player["layer"]),
        "layer": player["layer"],
        "talent": player["talent"],
        "qi": qi,
        "qi_needed": need,
        "pending": pending,
        "pending_label": ("from seclusion (×2 when complete)" if secluded else "gathered, not yet banked"),
        "rate": rate,
        "mult": mult,
        "secluded": secluded,
        "eta": eta,
        "gate": gate,
        "gate_note": gate_note,
        "status": status,
        "status_tone": tone,
        "train_qi": rate * training.TRAIN_REWARD_HOURS,
        "sources": sources(player, techniques, now),
        "formula": formula(player, techniques, now),
    }
