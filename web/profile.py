"""
The profile page's data. docs/web.md, "The profile page".

All numbers come from bot/sheet/data.profile_data, the same function the bot's /profile card uses,
so the website and Discord always agree. This module only turns them into text and picture links.
"""
import os
import time

import looks
import stats

from bot import crafting, db, forging, points
from bot import player as rules
from bot.sheet import data as sheet
from cards import art_icons

ATTR_ICON = "/art/icons/attr/{}.webp"
ART_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "art")


def art_url(kind):
    """'/art/icons/tech/iron_fist.webp' for an icon kind like 'tech:iron_fist', or None."""
    found = art_icons.resolve(kind) if kind else None
    if not found:
        return None
    rel = os.path.relpath(found[0], ART_ROOT).replace(os.sep, "/")
    return fresh("/art/" + rel)


def fresh(url):
    """'/art/icons/tech/iron_fist.webp' -> '/art/icons/tech/iron_fist.webp?v=1731420000': the file's change time
    rides along, so a browser that kept an old copy of a picture (say a cut-off icon fixed since) fetches the
    new one as soon as the file changes, instead of showing the old one from its cache."""
    if not url.startswith("/art/"):
        return url
    try:
        return f"{url}?v={int(os.path.getmtime(os.path.join(ART_ROOT, url[5:])))}"
    except OSError:
        return url


def number(x):
    """12480 -> '12,480'; 3.125 -> '3.1'."""
    if isinstance(x, float) and not x.is_integer():
        return f"{x:,.1f}"
    return f"{int(x):,}"


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def eta_text(eta):
    """'2h 33m' -> 'full in 2h 33m'; words like 'Ready now' stay as they are."""
    if not eta:
        return None
    return f"full in {eta}" if eta[0].isdigit() else eta


def pct(x):
    """0.025 -> '+2.5%'."""
    v = round(x * 100, 1)
    return f"{'+' if v >= 0 else ''}{v:g}%"


def attribute_rows(attrs, qi):
    """HP, Internal Qi, Attack, Defense: the number, its realm base and every bonus on top (name, %)."""
    rows = []
    for key in ("hp", "attack", "defense"):
        a = attrs[key]
        rows.append({"key": key, "label": "HP" if key == "hp" else a["label"], "icon": ATTR_ICON.format(key),
                     "value": number(a["final"]), "base": number(a["base"]),
                     "bonus": pct(a["bonus"]) if a["bonus"] else None,
                     "sources": [(name, pct(v)) for name, v in a["sources"]]})
    rows.insert(1, {"key": "qi", "label": "Internal Qi", "icon": ATTR_ICON.format("qi"),
                    "value": number(qi["qi"]), "base": None, "of": number(qi["capacity"]), "bonus": None,
                    "sources": [("Flows in", f"+{number(float(qi['rate']))} / hour")]})
    return rows


def titles(player):
    """The character's standing: talent and crafting ranks (the game has no other titles yet)."""
    out = [(f"{player['talent']} Talent", "talent")]
    a, b = crafting.rank_of(player["alchemy_exp"]), forging.rank_of(player["blacksmith_exp"])
    if player["alchemy_exp"]:
        out.append((f"{crafting.rank_label(a)} Alchemist", "craft"))
    if player["blacksmith_exp"]:
        out.append((f"{forging.rank_label(b)} Blacksmith", "craft"))
    return out


ROMAN = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII")


def realm_track(realm, layer, max_layer):
    """Realm n of N, the layer pips and the next realm's name."""
    order = rules.REALM_ORDER
    i = order.index(realm)
    return {"no": i + 1, "of": len(order),
            # the realm's emblem on the page: its number, and a lotus with one more petal every realm
            "roman": ROMAN[i] if i < len(ROMAN) else str(i + 1), "petals": 5 + i,
            "next": order[i + 1] if i + 1 < len(order) else None,
            "pips": [{"n": n, "on": n <= layer, "now": n == layer} for n in range(1, max_layer + 1)]}


def development(conn, user_id):
    """The Strength / Vitality panel: points, what they give, and what the page needs to preview a choice."""
    from bot.sheet.data import worn
    p = db.get_player(conn, user_id)
    techs = db.get_techniques(conn, user_id)
    weapon, armor, _ = worn(conn, user_id)
    hp, attack, _ = rules.base_stats(p["realm"], p["layer"])
    other = {k: sum(v for _, v in src) for k, src in rules.stat_buffs(techs, weapon, armor).items()}
    cost = points.reset_cost(p)
    import battle
    return {"strength": p["strength"], "vitality": p["vitality"], "spirit": p["spirit"], "free": rules.unspent_points(p),
            "bqi": battle.BATTLE_QI_START + p["spirit"] * stats.SPIRIT_BATTLE_QI, "per_spi": stats.SPIRIT_BATTLE_QI,
            "earned": rules.attribute_points(p["realm"], p["layer"]),
            "str_pct": pct(p["strength"] * stats.STRENGTH_ATTACK), "vit_pct": pct(p["vitality"] * stats.VITALITY_HP),
            "per_str": pct(stats.STRENGTH_ATTACK), "per_vit": pct(stats.VITALITY_HP),
            "reset_cost": cost, "can_reset": bool(p["strength"] or p["vitality"] or p["spirit"]),
            "pearls": p["moon_pearls"],
            # the preview uses the same formula as player.final_stats: round(base × (1 + every % bonus))
            "calc": {"hp": hp, "attack": attack, "hp_pct": other["hp"], "atk_pct": other["attack"],
                     "s": p["strength"], "v": p["vitality"], "ps": stats.STRENGTH_ATTACK, "pv": stats.VITALITY_HP,
                     "q": p["spirit"], "pq": stats.SPIRIT_BATTLE_QI, "bq": battle.BATTLE_QI_START}}


def profile_view(conn, user_id, username=None):
    """Everything profile.html shows, or None when this Discord account has no character yet."""
    player = db.get_player(conn, user_id)
    if player is None:
        return None
    look = looks.of_player(player)
    d = sheet.profile_data(conn, user_id, username=username)
    qi = d["qi"]
    cap = qi["capacity"] or 1
    attrs = {a["key"]: a for a in d["attributes"]}
    slots = []
    for s in d["slots"]:
        t = s.get("tech")
        slots.append({
            "slot": s["slot"], "locked": s["locked"], "note": s.get("note"),
            "name": t["name"] if t else None, "grade": t["grade"] if t else None,
            "mastery": t["stage_name"] if t else None, "power": t["power"] if t else None,
            "icon": art_url(t["icon"]) if t else None,
        })
    return {
        "name": d["name"], "talent": d["talent"], "realm": d["realm"], "phase": d["phase"],
        "layer": ordinal(d["layer"]), "max_layer": d["max_layer"], "rank": d["rank"],
        "qi": number(qi["qi"]), "qi_cap": number(qi["capacity"]), "qi_pct": max(0, min(100, round(qi["qi"] / cap * 100))),
        "qi_rate": number(float(qi["rate"])), "qi_eta": eta_text(qi["eta"]), "qi_status": qi["status"],
        "qi_gate": qi["gate"], "qi_gate_note": qi["gate_note"],
        "hp": number(attrs["hp"]["final"]), "attack": number(attrs["attack"]["final"]),
        "defense": number(attrs["defense"]["final"]),
        "injured": d["hp"]["injured_for"] > 0,
        "coins": number(d["coins"]), "pearls": number(d["pearls"]),
        "slots": slots,
        "weapon": d["weapon"]["name"] if d.get("weapon") else None,
        "stats": [("Beasts slain", number(d["beasts"])), ("Herbs gathered", number(d["herbs"])),
                  ("Breakthroughs", number(d["breakthroughs"])),
                  ("Duels won", number(d["duels_won"]))],
        # the Journey plaques' icons, in the same order as "stats" (existing index art)
        "stat_icons": [fresh(f"/art/icons/index/{k}.webp") for k in ("ov_toxicity", "ov_types", "ov_insight", "ov_elite")],
        "status": d["status"],
        "portrait": looks.portrait(look),
        "look": looks.describe(look) if look else None,
        "dev": development(conn, user_id),
        "layer_no": d["layer"],
        "titles": titles(db.get_player(conn, user_id)),
        "track": realm_track(d["realm"], d["layer"], d["max_layer"]),
        "attributes": attribute_rows(attrs, qi),
        "qi_tone": qi["status_tone"],
        "gate": gate_of(conn, user_id),
        "passives": passives_view(conn, user_id),
        "tox": toxicity_of(conn, user_id),
    }


PASSIVE_GROUPS = ("Combat", "Cultivation", "Fortune", "Crafting")
CULTIVATION = {"qi_rate", "mastery_exp", "pill_effect", "toxicity_decay_faster", "breakthrough_chance",
               "practice_mastery_exp", "max_toxicity"}
FORTUNE = {"lotus_coins", "extra_chest_roll", "jade_chest_chance", "rare_encounters", "misleading_clue_less",
           "beast_core_chance", "uses_per_week"}
STAT_NAMES = {"attack": "Attack", "hp": "HP", "defense": "Defense"}


def passives_view(conn, user_id):
    """Every passive on your worn weapon, armour and artifacts, by what it helps (bot/passives.py). A passive on two
    worn items counts once (forge.NO_DUPLICATE_PASSIVES): the second is marked so."""
    import forge
    from bot import passives
    weapon, armor, artifacts = sheet.worn(conn, user_id)
    groups = {g: [] for g in PASSIVE_GROUPS}
    seen, stats = {}, {}
    for it in [x for x in (weapon, armor, *artifacts) if x]:
        kind = passives.gear_kind(it)
        if not kind:
            continue
        for key in passives.slots(it):
            if not key:
                continue
            spec = forge.PASSIVES[kind][key]
            fx = set(spec["fx"])
            group = ("Combat" if kind != "artifact" else "Cultivation" if fx & CULTIVATION else
                     "Fortune" if fx & FORTUNE else "Crafting")
            first = seen.get(key)
            groups[group].append({"name": spec["name"], "rarity": spec["rarity"], "text": spec["text"],
                                  "color": "rgb({}, {}, {})".format(*forge.RARITY_COLORS[spec["rarity"]]),
                                  "item": it["name"], "counted": first is None, "first": first})
            if first is None:
                seen[key] = it["name"]
                if kind != "artifact":
                    for stat, v in spec["fx"].items():
                        if stat in STAT_NAMES:
                            got = stats.setdefault(stat, [0.0, 0])
                            got[0] += v
                            got[1] += 1
    totals = [f"{STAT_NAMES[k]} +{v[0]:.0%} from {v[1]} passive{'s' if v[1] > 1 else ''}" for k, v in stats.items()]
    out = [{"group": g, "rows": rows} for g, rows in groups.items() if rows]
    return {"groups": out, "totals": totals, "count": sum(len(g["rows"]) for g in out)}


def toxicity_of(conn, user_id):
    """Pill toxicity for the gourd beside the Qi bar (web/dantian_play.toxicity), or None when clean."""
    from .dantian_play import toxicity
    t = toxicity(db.get_player(conn, user_id), time.time())
    return t if t["n"] else None


def gate_of(conn, user_id):
    """The Break through button beside the Qi bar (web/breakthrough_play.plate), or None when the bar isn't full."""
    from .breakthrough_play import now_player, plate
    me, techs = now_player(conn, user_id)
    g = plate(me, techs) if me else None
    return g if g and g["full"] else None
