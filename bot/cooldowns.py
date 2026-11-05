"""
/cooldown: every timer the bot keeps for one cultivator, read straight from the database.

timer_sections() is pure (it only reads), so tests can call it with a fixed `now`.
Each line shows "Ready" or a Discord relative timestamp plus the local clock time,
so every viewer sees the time in their own time zone.
"""
import calendar
import time

import explore
import technique
import training

from . import db
from . import player as rules

READY = "✅ Ready"


def stamp(when):
    """Discord timestamps: '<t:..:R>' (in 2 hours) and '<t:..:t>' (local clock time)."""
    t = int(when)
    return f"<t:{t}:R> · <t:{t}:t>"


def next_utc_midnight(now):
    day = time.gmtime(now)
    return calendar.timegm((day.tm_year, day.tm_mon, day.tm_mday, 0, 0, 0)) + 86400


def _cooldown(conn, uid, name, now):
    left = db.cooldown_left(conn, uid, name, now)
    return (now + left) if left else None


def _daily(rates, done):
    """'3 / 5 at full gain' style text from a diminishing-returns table."""
    full = rates[0][0]
    rate = rules.daily_rate(rates, done)
    if done < full:
        return f"{done} / {full} at full gain"
    return f"{done} done · now at {rate:.0%} gain"


def timer_sections(conn, player, now=None):
    """[(section title, [line, ...]), ...] for the /cooldown embed."""
    now = time.time() if now is None else now
    uid = player["user_id"]
    secluded = rules.in_seclusion(player)
    hurt = rules.injured_for(player, now)

    # ── Martial pursuits ─────────────────────────────────────────────
    blocked_by = "🧘 in seclusion" if secluded else ("🩹 injured" if hurt else None)
    rows = [
        ("🗺️", "Explore", "explore", f"{explore.EXPLORE_COOLDOWN_MINUTES}m", True),
        ("🥋", "Train", "train", f"{training.TRAIN_COOLDOWN_MINUTES}m", False),
        ("📜", "Practice", "practice", f"{technique.PRACTICE_COOLDOWN_MINUTES}m", False),
        ("⚔️", "Spar", "spar", f"{technique.SPAR_COOLDOWN_MINUTES // 60}h", True),
    ]
    pursuits = []
    for icon, label, key, base, needs_health in rows:
        until = _cooldown(conn, uid, key, now)
        if until:
            state = stamp(until)
        elif needs_health and blocked_by:
            state = f"Barred, {blocked_by}"
        else:
            state = READY
        pursuits.append(f"{icon} **{label}** ({base}) — {state}")

    # ── Technique trials ─────────────────────────────────────────────
    trials = []
    for t in db.get_techniques(conn, uid, equipped_only=False):
        until = _cooldown(conn, uid, f"trial:{t['id']}", now)
        if until:
            trials.append(f"🌀 **{t['name']}** — retry {stamp(until)}")
        elif rules.bar_full(t):
            where = "**/spar** to attempt" if t["equipped"] else "equip it to attempt"
            trials.append(f"🌀 **{t['name']}** — {READY}, {where}")

    # ── Daily discipline ─────────────────────────────────────────────
    daily = [
        f"📜 **Practice** — {_daily(technique.PRACTICE_DAILY_RATES, db.daily_count(conn, uid, 'practice', now))}",
        f"⚔️ **Spar** — {_daily(technique.SPAR_DAILY_RATES, db.daily_count(conn, uid, 'spar', now))}",
        f"🌅 Counts renew {stamp(next_utc_midnight(now))}",
    ]

    # ── Body and meridians ───────────────────────────────────────────
    body = []
    if secluded:
        end = player.get("seclusion_end") or now
        if end > now:
            body.append(f"🧘 **Closed-door seclusion** — emerges {stamp(end)}")
        else:
            body.append(f"🧘 **Closed-door seclusion** — complete, use **/seclusion** to step out")
    else:
        body.append(f"🧘 **Seclusion** — not in seclusion ({training.SECLUSION_MIN_HOURS}-"
                    f"{training.SECLUSION_MAX_HOURS}h at ×{training.SECLUSION_QI_MULTIPLIER:g} Qi)")
    if hurt:
        body.append(f"🩹 **Injury** — heals {stamp(now + hurt)} (or **/physician**)")
    else:
        body.append("🩹 **Injury** — meridians whole")
    tox = rules.current_toxicity(player, now)
    if tox and player.get("toxicity_at") is not None:
        clears = player["toxicity_at"] + (player.get("toxicity") or 0) * training.TOXICITY_DECAY_HOURS * 3600
        body.append(f"☠️ **Pill toxicity {tox}** — fully cleansed {stamp(clears)}")

    # ── Heavenly boons ───────────────────────────────────────────────
    boons = []
    if rules.active_blessing(player, now):
        boons.append(f"🌸 **{player['blessing_tier']} Blessing** — fades {stamp(player['blessing_expires'])}")
    pill = rules.active_pill(player, now)
    if pill:
        boons.append(f"💊 **{pill[0]} Qi Pill** (×{pill[1]:g} Qi) — wears off {stamp(now + pill[2])}")
    land = rules.active_blessed_land(player, now)
    if land:
        name = land[0].replace("_", " ").title()
        boons.append(f"✨ **{name}** — fades {stamp(now + land[1])}")
    if not boons:
        boons.append("No blessing, pill or blessed land at work. See **/blessing** and **/shop**.")

    # ── Pavilion ─────────────────────────────────────────────────────
    pavilion = [f"🎲 **Fate Reroll** — no waiting · next costs **{rules.fate_reroll_cost(player):,}** Lotus Coins"]

    sections = [("Martial Pursuits", pursuits)]
    if trials:
        sections.append(("Mastery Trials", trials))
    sections += [("Daily Discipline", daily), ("Body & Meridians", body),
                 ("Heavenly Boons", boons), ("Pavilion", pavilion)]
    return sections

