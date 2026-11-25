"""
The admin panel on the website (docs/web.md "Admin panel"): Discord's /admin testing tools on one page, for the
same people. Each tool calls the same helper in bot/admin.py as the Discord command, so it does exactly the same:

  Reset          cooldowns, daily limits and the injury of a player   (/admin reset)
  Cooldowns      off for everyone for a set time, back on, status       (/admin cooldowns)
  Give           Lotus Coins, Moon Pearls, Qi                           (/admin give)
  Give an item   any item in the game, with quality, age, patterns      (/admin item, give_weapon, ...)
  Chests         one press per tier, so chest opening can be tested     (/admin item chest:<tier>)
  Realm          realm and layer                                        (/admin set_realm)
  Techniques     teach one or all; set mastery                          (/admin give_technique, set_mastery)
  Crafts         alchemist and blacksmith rank, foraging                (/admin set_alchemy, set_blacksmith, set_foraging)
  Test fight     any beast, waiting in Explore on the website           (/admin web_fight)
  Duel stats                                                            (/admin duelstats)

Who: the user IDs in ADMIN_IDS (.env), as for Discord's /admin (the bot owner is also recognised there, through
Discord; the website can't ask Discord who owns the app, so put your own ID in ADMIN_IDS). Everyone else gets "not
found": the page doesn't show that it exists.
"""
import html
import re
import time

import alchemy
import beasts
import equipments
import forge
import technique as tech_data
from bot import admin as bot_admin
from bot import crafting, db, forging, item_catalog
from bot import player as rules

from .forge_play import rich

CHEST_TIERS = ["common", "uncommon", "rare", "epic", "legendary", "mythic"]


def is_admin(uid):
    return bool(uid) and int(uid) in bot_admin.admin_ids_from_env()


def plain(text):
    """A Discord reply as safe HTML: **bold** kept, <@id> mentions and <t:...> times made readable."""
    text = re.sub(r"<t:(\d+):R>", lambda m: "in " + rules.fmt_duration(max(0, int(m.group(1)) - time.time())), text)
    text = re.sub(r"<t:(\d+)(?::\w)?>", lambda m: time.strftime("%H:%M %d %b", time.localtime(int(m.group(1)))), text)
    text = re.sub(r"<@!?\d+>", "them", text)
    return str(rich(text))


def players(conn):
    rows = conn.execute("SELECT user_id, name, realm, layer FROM players ORDER BY name COLLATE NOCASE").fetchall()
    return [{"id": r["user_id"], "label": f"{r['name']} · {r['realm']} {rules.ordinal(r['layer'])}"} for r in rows]


def choices():
    """The pick lists the forms show (the same as the Discord commands' choices)."""
    return {
        "realms": rules.REALM_ORDER,
        "stages": [(i, s["name"]) for i, s in enumerate(tech_data.MASTERY_STAGES)],
        "ranks": [(r, crafting.rank_label(r)) for r in sorted(alchemy.ALCHEMIST_RANK_EXP)],
        "smith_ranks": [(r, forging.rank_label(r)) for r in sorted(forge.BLACKSMITH_RANK_EXP)],
        "qualities": list(item_catalog.QUALITY_POS),
        "ages": sorted(alchemy.HERB_AGES),
        "tiers": [(t, bot_admin.TIER_LABEL[t]) for t in beasts.BEAST_TIERS],
        "chests": [(t, item_catalog.CATALOG[f"chest:{t}"]["name"]) for t in CHEST_TIERS],
        "gear_tiers": [(t, equipments.TIER_DISPLAY[t]) for t in equipments.TIERS],
    }


def target_view(conn, uid):
    p = db.get_player(conn, uid)
    if p is None:
        return None
    techs = db.get_techniques(conn, uid, equipped_only=False)
    return {"id": uid, "name": p["name"], "realm": p["realm"], "layer": rules.ordinal(p["layer"]),
            "qi": f"{p['qi']:,.1f} / {rules.qi_needed(p['realm'], p['layer']):,}",
            "coins": f"{p['lotus_coins']:,}", "pearls": f"{p['moon_pearls']:,}",
            "injured": rules.fmt_duration(rules.injured_for(p)) if rules.injured_for(p) else None,
            "slots": f"{db.slots_used(conn, uid)} / {p['bag_capacity']}",
            "techniques": [{"id": t["id"], "name": t["name"],
                            "stage": tech_data.MASTERY_STAGES[rules.stage_of(t)]["name"]} for t in techs]}


def cooldowns_status(conn, now=None):
    now = time.time() if now is None else now
    until = db.cooldowns_off_until(conn, now)
    if until:
        return f"Off for everyone until {time.strftime('%H:%M %d %b', time.localtime(until))} ({rules.fmt_duration(until - now)} left)"
    return "On, as normal"


def number(form, key, lo=0, hi=10 ** 9, default=0):
    try:
        v = int(str(form.get(key, "")).strip().replace(",", "") or default)
    except ValueError:
        return default
    return max(lo, min(hi, v))


def act(conn, me, target, form):
    """Do one admin action from the panel's form. Returns (ok, [html lines])."""
    what = form.get("action")
    if what == "cooldowns":                                          # for everyone: no target needed
        how = form.get("how") if form.get("how") in ("off", "on", "status") else "status"
        text, _ = bot_admin.cooldowns_switch(conn, how, number(form, "hours", 0, bot_admin.MAX_COOLDOWNS_OFF_HOURS),
                                             number(form, "minutes", 0, 59 * 24))
        return True, [plain(text)]
    if what == "duelstats":
        return True, [plain(line) for line in bot_admin.duelstats_text(conn).split("\n")]
    if db.get_player(conn, target) is None:
        return False, ["That player has not used /start yet."]
    who = "you" if target == me else db.get_player(conn, target)["name"]

    if what == "reset":
        done = bot_admin.reset_player(conn, target)
        return True, [f"Everything is ready again for {html.escape(who)}."] + [html.escape(d) for d in done or ["Nothing was on cooldown."]]

    if what == "give":
        coins, pearls, qi = number(form, "coins", 0, 10_000_000), number(form, "pearls", 0, 1_000_000), number(form, "qi", 0, 100_000_000)
        if not (coins or pearls or qi):
            return False, ["Enter Lotus Coins, Moon Pearls or Qi to give."]
        events = bot_admin.give(conn, target, coins, pearls, qi)
        p = db.get_player(conn, target)
        got = ", ".join(s for n, s in ((coins, f"{coins:,} Lotus Coins"), (pearls, f"{pearls:,} Moon Pearls"), (qi, f"{qi:,} Qi")) if n)
        return True, [f"Gave {got} to {html.escape(who)}.",
                      f"Now: {p['realm']}, {rules.ordinal(p['layer'])} Layer · Qi {p['qi']:,.1f} / "
                      f"{rules.qi_needed(p['realm'], p['layer']):,} · {p['lotus_coins']:,} coins · {p['moon_pearls']:,} pearls"] + [plain(e) for e in events]

    if what in ("item", "chest"):
        text = form.get("item", "") if what == "item" else f"chest:{form.get('tier', '')}"
        entry_id, problem = item_catalog.resolve(text)
        if problem:
            return False, [plain(problem)]
        amount = number(form, "amount", 1, 100_000, 1)
        if item_catalog.CATALOG[entry_id]["kind"] in item_catalog.GEAR_KINDS + ("artifact",):
            amount = min(amount, item_catalog.MAX_GEAR)
        quality = form.get("quality") if form.get("quality") in item_catalog.QUALITY_POS else None
        age = number(form, "age", 0, 10_000) or None
        age = age if age in alchemy.HERB_AGES else None
        patterns = number(form, "patterns", 0, 9) or None
        stored, lost = bot_admin.give_item(conn, target, entry_id, amount, quality, age, patterns)
        return bool(stored), [plain(bot_admin.item_reply(entry_id, stored, lost, who, "Their" if target != me else "Your"))]

    if what == "realm":
        realm = form.get("realm")
        if realm not in rules.REALM_ORDER:
            return False, ["Pick a realm."]
        got = bot_admin.set_realm(conn, target, realm, number(form, "layer", 1, 10, 1))
        return True, [f"Realm set to <b>{realm}, {rules.ordinal(got)} Layer</b> (Qi 0 / {rules.qi_needed(realm, got):,})."]

    if what == "technique":
        found = bot_admin.find_catalog_techniques(form.get("technique", ""))
        text = form.get("technique", "").strip().lower()
        if not found:
            return False, ["No technique matches that."]
        if len(found) > 1 and text not in ("all", "all techniques"):
            return False, ["More than one matches: " + html.escape(", ".join(t["name"] for _, t in found[:15])) + ". Be more exact."]
        learned, known = bot_admin.give_techniques(conn, target, found)
        lines = [f"Learned: {html.escape(', '.join(learned))}" if learned else "Nothing new learned."]
        if known:
            lines.append(f"Already known: {len(known)}")
        return True, lines

    if what == "mastery":
        techs = db.get_techniques(conn, target, equipped_only=False)
        hit = bot_admin.find_techniques(techs, form.get("technique", "all"))
        stage = number(form, "stage", 0, len(tech_data.MASTERY_STAGES) - 1)
        if not hit:
            return False, ["No technique matches that."]
        return True, [plain(x) for x in bot_admin.set_mastery(conn, hit, stage, form.get("full_bar") == "on")]

    if what == "alchemy":
        rank = number(form, "rank", 1, max(alchemy.ALCHEMIST_RANK_EXP), 1)
        return True, [plain(bot_admin.set_alchemy_rank(conn, target, rank))]
    if what == "blacksmith":
        rank = number(form, "rank", 1, max(forge.BLACKSMITH_RANK_EXP), 1)
        return True, [plain(bot_admin.set_blacksmith_rank(conn, target, rank))]
    if what == "foraging":
        insight = form.get("insight", "").strip()
        herbs = form.get("herbs", "").strip()
        if not insight and not herbs:
            return False, ["Enter Herbal Insight and/or herbs gathered."]
        lines = bot_admin.set_foraging(conn, target, number(form, "insight", 0, 100_000) if insight else None,
                                       number(form, "herbs", 0, 10_000_000) if herbs else None)
        return True, [plain(x) for x in lines]

    if what == "fight":
        if target != me:
            return False, ["A test fight waits in your own Explore: pick yourself."]
        found = bot_admin.find_beasts(form.get("beast", ""))
        if len(found) != 1:
            names = ", ".join(r[1] for r in found[:12])
            return False, ["Pick one beast" + (f": {html.escape(names)}" if found else ": nothing matches that")]
        tier = form.get("tier") if form.get("tier") in beasts.BEAST_TIERS else None
        bot_admin.queue_web_fight(conn, me, found[0], tier, form.get("home_realm") == "on")
        return True, [f"<b>{html.escape(found[0][1])}</b> is waiting: open <a href=\"/explore\">Explore</a> and the fight starts. "
                      "Test fight: no rewards, no injury, no cooldown."]
    return False, ["Unknown action."]


def search_items(q):
    return [{"id": i, "label": label} for i, label in item_catalog.search(q or "", limit=30)]


def search_beasts(q):
    rows = bot_admin.find_beasts(q) if (q or "").strip() else bot_admin.all_beasts()
    return [{"id": bot_admin.beast_key(r), "label": bot_admin.beast_label(r)} for r in rows[:30]]


def search_techniques(q):
    rows = bot_admin.find_catalog_techniques(q) if (q or "").strip() else list(tech_data.TECHNIQUES.items())
    return [{"id": k, "label": bot_admin.technique_label(t)} for k, t in rows[:30]]
