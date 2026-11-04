"""
Team hunts: Elite Lairs and Beast King Dens found in /explore (docs/beast.md, docs/explore.md).

The finder posts a hunt call; others join with a button while the lair is
open (30 min Elite, 60 min Beast King). The fight plays out on its own:
  • beast stats follow the team's highest realm and layer
  • each player beyond the intended team size adds +20% beast HP
  • Elite and Beast King beasts telegraph a charged attack every third turn,
    which ignores the 30% cap; most fighters raise their guard for it
Every winner rolls their own chest (explore.CHEST_ROLL_PER_PLAYER).
"""
import random
import time

import beasts
import explore
import stats
import technique

from . import combat, db, loot, mastery
from . import player as rules

MAX_TEAM = 8                     # DEFAULT hard cap on a hunt party
CHARGE_EVERY = 3                 # DEFAULT: a charged attack every 3rd beast turn
CHARGE_MULT = 1.5              # DEFAULT: charged hit = 1.5× a normal hit, ignores the 30% cap
CHARGE_GUARD_CHANCE = 0.75       # DEFAULT: warned fighters with a defense technique usually guard it
LOSS_INJURY_HOURS = 1            # DEFAULT: losing a hunt injures the team for 1 hour
HUNT_COINS = {"elite": (20, 40), "beast_king": (60, 120)}   # DEFAULT per player, × realm scale
MAX_ROUNDS = 60


def open_minutes(tier):
    return explore.ELITE_LAIR_OPEN_MINUTES if tier == "elite" else explore.BEAST_KING_DEN_OPEN_MINUTES


def roll_lair(player, tier, rng=random):
    """A lair found by `player`: dict with the beast and when it closes."""
    beast = rng.choice([b for b in beasts.BEASTS[player["realm"]] if b[1] == tier])
    return {"beast": beast, "tier": tier, "realm": player["realm"],
            "closes": time.time() + open_minutes(tier) * 60, "finder": player["user_id"]}


def team_beast(lair, team):
    """Beast stats for this team (players = list of player dicts)."""
    top = max(team, key=lambda p: (rules.realm_index(p["realm"]), p["layer"]))
    name, tier, role = lair["beast"]
    hp, attack, _ = rules.base_stats(top["realm"], top["layer"])
    t, r = beasts.BEAST_TIERS[tier], beasts.ROLES[role]
    extra = max(0, len(team) - t["team_size"])
    hp = hp * t["hp"] * r.get("hp", 1) * (1 + beasts.EXTRA_PLAYER_HP_BONUS * extra)
    atk = attack * t["attack"] * r.get("attack", 1)
    return {"name": name, "tier": tier, "role": role, "hp": round(hp), "max_hp": round(hp), "attack": atk,
            "defense": atk * beasts.BEAST_DEFENSE_RATIO * r.get("defense", 1), "dodge": r.get("dodge", 0)}


def _fighter(conn, p):
    techs = db.get_techniques(conn, p["user_id"])
    hp, atk, dfn = rules.final_stats(p, techs, db.equipped_weapon(conn, p["user_id"]))
    atk_t = next((t for t in techs if t["type"] == "attack"), None)
    def_t = next((t for t in techs if t["type"] == "defense"), None)
    return {"p": p, "techs": techs, "hp": hp, "max_hp": hp, "attack": atk, "defense": dfn,
            "atk_t": atk_t, "def_t": def_t, "atk_uses": 0, "guard_uses": 0, "heavy_last": False, "dealt": 0.0}


def team_fight(fighters, beast, rng=random):
    """Mutates fighters and beast. Returns (won, rounds, log lines)."""
    log, turn = [], 0
    charge_warned = False
    for rnd in range(1, MAX_ROUNDS + 1):
        alive = [f for f in fighters if f["hp"] > 0]
        if not alive:
            return False, rnd, log
        for f in alive:
            t = f["atk_t"]
            eff = rules.TECH_BY_NAME.get(t["name"], {}).get("effect") if t else None
            use = t is not None and not (eff and eff[0] == "heavy" and f["heavy_last"])
            f["heavy_last"] = bool(use and eff and eff[0] == "heavy")
            skill, hits, pierce = 1.0, 1, 0.0
            if use:
                f["atk_uses"] += 1
                skill = technique.ATTACK_TECHNIQUE[t["grade"]][0] * rules.mastery_mult(t)
                if eff and eff[0] == "combo":
                    hits, skill = eff[1][0], skill * eff[1][1]
                elif eff and eff[0] == "pierce":
                    pierce = eff[1]
                elif eff and eff[0] == "heavy":
                    skill *= eff[1]
            total = 0.0
            for _ in range(hits):
                if beast["dodge"] and rng.random() < beast["dodge"]:
                    continue
                total += combat.damage(f["attack"], beast["defense"], beast["max_hp"], skill, pierce, rng)
            total = min(total, beast["max_hp"] * stats.MAX_HIT_PERCENT)
            beast["hp"] = max(0, beast["hp"] - total)
            f["dealt"] += total
            if beast["hp"] <= 0:
                return True, rnd, log
        # beast's turn
        turn += 1
        alive = [f for f in fighters if f["hp"] > 0]
        target = rng.choice(alive)
        charged = beast["tier"] in beasts.CHARGED_ATTACK_TIERS and turn % CHARGE_EVERY == 0
        if beast["tier"] in beasts.CHARGED_ATTACK_TIERS and turn % CHARGE_EVERY == CHARGE_EVERY - 1 and not charge_warned:
            log.append(f"*The {beast['name']} crouches low, gathering power...*")
            charge_warned = True
        if charged:   # ignores the 30% cap (beast.md)
            dmg = combat.damage(beast["attack"], target["defense"], float("inf"), CHARGE_MULT, rng=rng)
        else:
            dmg = combat.damage(beast["attack"], target["defense"], target["max_hp"], rng=rng)
        guard_chance = CHARGE_GUARD_CHANCE if charged else combat.GUARD_CHANCE
        d = target["def_t"]
        if d and rng.random() < guard_chance:
            target["guard_uses"] += 1
            block = min(technique.MAX_DAMAGE_BLOCKED,
                        technique.DEFENSE_TECHNIQUE[d["grade"]][0] * rules.mastery_mult(d))
            eff = rules.TECH_BY_NAME.get(d["name"], {}).get("effect")
            if eff and eff[0] == "evade" and rng.random() < eff[1]:
                dmg = 0
            else:
                blocked = dmg * block
                dmg -= blocked
                if eff and eff[0] == "counter":
                    beast["hp"] = max(0, beast["hp"] - blocked * eff[1])
                elif eff and eff[0] == "recover":
                    target["hp"] = min(target["max_hp"], target["hp"] + target["max_hp"] * eff[1])
        target["hp"] = max(0, target["hp"] - dmg)
        if charged:
            log.append(f"💥 Charged attack on **{target['p']['name']}** (−{dmg:,.0f})!"
                       + (" They fall!" if target["hp"] <= 0 else ""))
            charge_warned = False
        elif target["hp"] <= 0:
            log.append(f"**{target['p']['name']}** is knocked out!")
        if beast["hp"] <= 0:
            return True, rnd, log
    return False, MAX_ROUNDS, log


def resolve(conn, lair, user_ids, rng=random, now=None):
    """Fight the hunt and save rewards. Returns (won, summary lines, announcements)."""
    now = time.time() if now is None else now
    team = [db.get_player(conn, u) for u in user_ids]
    fighters = [_fighter(conn, p) for p in team]
    beast = team_beast(lair, team)
    start_hp = beast["max_hp"]
    won, rounds, log = team_fight(fighters, beast, rng)
    lines = [f"**{beast['name']}** · {start_hp:,} HP · {len(team)} fighter(s) · {rounds} rounds"] + log[-6:]
    news = []
    tier = lair["tier"]
    for f in fighters:
        p = f["p"]
        uid = p["user_id"]
        bits = [f"dealt {f['dealt']:,.0f}"]
        for t in f["techs"]:
            uses = f["atk_uses"] if t["type"] == "attack" else f["guard_uses"]
            if uses:
                mastery.gain(conn, p, t, uses * technique.COMBAT_EXP_PER_USE)
        if won:
            coins = loot.roll_coins(p, HUNT_COINS[tier], rng)
            db.add_coins(conn, uid, coins)
            bits.append(f"🪷 {coins:,}")
            fields = {"beasts_slain": p["beasts_slain"] + 1}
            if tier == "beast_king" and lair["realm"] not in rules.king_kills(p):
                fields["king_kills"] = ",".join(rules.king_kills(p) + [lair["realm"]])
            db.update_player(conn, uid, **fields)
            c = loot.beast_chest(p, tier, rng)
            if c:
                stored, _ = loot.store(conn, uid, [c])
                bits.append(f"{loot.CHEST_EMOJI[c['key']]} {c['name']}" if stored else "bag full, chest lost")
        else:
            db.update_player(conn, uid, injured_until=now + LOSS_INJURY_HOURS * 3600)
            bits.append(f"injured {LOSS_INJURY_HOURS}h")
        lines.append(f"• **{p['name']}**: " + ", ".join(bits))
    if won and tier == "beast_king":
        news.append(f"📢 The Beast King **{beast['name']}** has fallen to "
                    + ", ".join(f"**{p['name']}**" for p in team) + "!")
    return won, lines, news


def can_join(player, now=None):
    """None if the player may join a hunt, else the reason."""
    if not player:
        return "You have not begun your journey yet. Use **/start**."
    if rules.in_seclusion(player):
        return "You are in seclusion."
    hurt = rules.injured_for(player, now)
    if hurt:
        return f"You are injured for {rules.fmt_duration(hurt)}."
    return None
