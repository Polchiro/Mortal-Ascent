"""
Opening chests on the website (docs/web.md "Opening a chest"): the Treasure Shelf and the vault.

The bot rolls and grants every chest, with its own functions: loot.begin_chest rolls it (with Fate Weaver) and
loot.claim_chest grants it (coins, items, the daily quest), exactly as Discord's reveal does. The page only shows what
came out. What this adds around it:

  - the bag-space guard (approved): a chest opens only when the bag has room for the most it could give, so nothing
    is ever left behind on the website. "The most" counts each kind of reward that chest tier can roll (a manual, a
    weapon, armour, an artifact, the Heaven-Defying Pill; forging materials go to their pouch and take no slot), twice
    over when an artifact gives an extra roll. Open all opens as many as there is room for, at most OPEN_ALL_MAX.
    (Discord keeps its own way: it shows what was left behind.)
  - one opening per press: the page sends a nonce; the same nonce again answers the same result.
  - rewards still waiting from a reveal nobody finished (the bot restarted mid-reveal) can be collected here too.

The look of each opening grows with the chest's tier (seals to break, how long), never with what is inside: the tier
is known before you open it, the contents are not.
"""
import threading
import time

import equipments
import explore
import forge
import talent
from bot import chest_reveal, db, gear, loot

from .forge_play import rich
from .inventory import item_picture

TIERS = loot.CHEST_ORDER                                   # common .. mythic
TIER_RARITY = dict(zip(TIERS, forge.RARITIES))             # the light of a chest is its tier's rarity colour
SEALS = {"common": 0, "uncommon": 1, "rare": 1, "epic": 2, "legendary": 3, "mythic": 3}
OPEN_ALL_MAX = 20                                          # approved: Open all opens up to 20 at a time
SPOTLIGHT = ("Epic", "Legendary", "Mythical")              # rewards that rise to the middle with their flavour line
MOMENT = ("Legendary", "Mythical")                         # ...and fill the screen


def css(rgb):
    return "rgb({}, {}, {})".format(*rgb)


def max_new_slots(player, tier):
    """The most bag slots one chest of this tier could need: one for each kind of slot-taking reward it can roll,
    twice when an artifact gives the chest an extra roll (loot._chest_items)."""
    kinds = sum(1 for chance in (explore.CHEST_MANUAL_CHANCE[tier], equipments.CHEST_WEAPON_CHANCE[tier],
                                 talent.HEAVEN_DEFYING_PILL["chest_chance"].get(tier, 0),
                                 equipments.CHEST_ARMOR_CHANCE[tier], equipments.CHEST_ARTIFACT_CHANCE[tier])
                if chance > 0)
    if forge.MATERIALS_USE_BAG_SLOTS:
        kinds += 3
    return kinds * (2 if gear.artifact_bonus(player, "extra_chest_roll") > 0 else 1)


def room(conn, uid):
    p = db.get_player(conn, uid)
    return max(0, p["bag_capacity"] - db.slots_used(conn, uid))


def shelf(conn, uid):
    """The Treasure Shelf: your chests by tier (only the ones you have), the room in the bag, and rewards waiting."""
    p = db.get_player(conn, uid)
    if p is None:
        return None
    free = room(conn, uid)
    have = {}
    for it in db.get_items(conn, uid, "chests"):
        if it["key"] in have:
            have[it["key"]]["qty"] += it["qty"]
        else:
            have[it["key"]] = it | {}
    tiers = []
    for tier in TIERS:
        rarity = TIER_RARITY[tier]
        it = have.get(tier)
        need = max_new_slots(p, tier)
        tiers.append({"key": tier, "name": loot.CHEST_NAMES[tier], "qty": it["qty"] if it else 0,
                      "item": it["id"] if it else None, "picture": item_picture({"category": "chests", "key": tier}),
                      "rarity": rarity, "color": css(forge.RARITY_COLORS[rarity]), "seals": SEALS[tier],
                      "need": need, "fits": free // need if need else 99})
    waiting = db.unclaimed_chests(conn, uid)
    return {"tiers": tiers, "room": free, "capacity": p["bag_capacity"], "max_all": OPEN_ALL_MAX,
            "total": sum(t["qty"] for t in tiers),
            "waiting": [{"id": w["id"], "name": w["chest_name"]} for w in waiting]}


def reward(item, player, lost=False):
    rv = chest_reveal.reward_view(item, player)
    return {"name": rv["name"], "qty": rv["qty"], "rarity": rv["rarity"], "color": css(rv["color"]),
            "kind": rv["kind"], "line": rv["line"], "flavor": rv["flavor"], "picture": item_picture(item),
            "lost": lost, "rank": forge.RARITIES.index(rv["rarity"])}


def opened(result, player):
    """One chest's rewards, worst first (the best comes out last), with its coins and notes."""
    lost_ids = {id(x) for x in result["lost"]}
    items = result["stored"] + result["lost"]
    rewards = sorted((reward(it, player, id(it) in lost_ids) for it in items), key=lambda r: r["rank"])
    return {"key": result["chest_key"], "name": result["chest_name"], "coins": result["coins"],
            "rewards": rewards, "notes": [str(rich(n)) for n in result["notes"]],
            "best": rewards[-1]["rarity"] if rewards else None}


def grouped(chests):
    """Open all's summary: the same reward from several chests as one line, best first."""
    out = {}
    for c in chests:
        for r in c["rewards"]:
            k = (r["name"], r["rarity"], r["lost"])
            if k in out:
                out[k]["qty"] += r["qty"]
            else:
                out[k] = dict(r)
    return sorted(out.values(), key=lambda r: (-r["rank"], r["name"]))


class Chests:
    """Openings, one at a time per player, and the last answer kept for its nonce."""

    def __init__(self, clock=time.time, rng=None):
        self.clock = clock
        self.rng = rng
        self._guard = threading.Lock()
        self._locks = {}
        self._done = {}                                    # uid -> (nonce, answer)

    def _lock(self, uid):
        with self._guard:
            return self._locks.setdefault(uid, threading.Lock())

    def _again(self, uid, nonce):
        d = self._done.get(uid)
        return d[1] if d and nonce and d[0] == nonce else None

    def _keep(self, uid, nonce, answer):
        if nonce:
            with self._guard:
                self._done[uid] = (nonce, answer)
        return answer

    def open(self, conn, uid, item_id, count=1, nonce=None):
        """Open `count` (1 .. OPEN_ALL_MAX) chests of the stack `item_id`. Returns (result, why)."""
        with self._lock(uid):
            seen = self._again(uid, nonce)
            if seen:
                return seen
            p = db.get_player(conn, uid)
            item = db.get_item(conn, uid, item_id) if p else None
            if not item or item["category"] != "chests" or item["key"] not in TIERS:
                return self._keep(uid, nonce, (None, "That chest is no longer in your bag."))
            tier = item["key"]
            need, free = max_new_slots(p, tier), room(conn, uid)
            if free < need:
                return self._keep(uid, nonce, (None, (
                    f"Your bag has {free} free slot{'s' if free != 1 else ''}. A {item['name']} can give up to "
                    f"{need} items that need one, so make room first: nothing is ever left behind here.")))
            n = max(1, min(int(count or 1), OPEN_ALL_MAX, item["qty"], free // need))
            now = self.clock()
            chests = []
            for _ in range(n):
                kw = {"now": now}
                if self.rng is not None:
                    kw["rng"] = self.rng
                pending = loot.begin_chest(conn, uid, item_id, **kw)
                if pending is None:
                    break
                res = loot.claim_chest(conn, uid, pending["id"], now=now)
                if res:
                    chests.append(opened(res, p))
            if not chests:
                return self._keep(uid, nonce, (None, "That chest is no longer in your bag."))
            return self._keep(uid, nonce, (self.answer(conn, uid, tier, chests, count), None))

    def collect(self, conn, uid, nonce=None):
        """Rewards still waiting from a reveal nobody finished: collected, and shown like an opening."""
        with self._lock(uid):
            seen = self._again(uid, nonce)
            if seen:
                return seen
            p = db.get_player(conn, uid)
            waiting = db.unclaimed_chests(conn, uid) if p else []
            if not waiting:
                return self._keep(uid, nonce, (None, "Nothing is waiting."))
            free = room(conn, uid)
            if free < sum(len(w["items"]) for w in waiting):
                return self._keep(uid, nonce, (None, f"Your bag has {free} free slots: make room first."))
            chests = []
            for w in waiting:
                res = loot.claim_chest(conn, uid, w["id"], now=self.clock())
                if res:
                    chests.append(opened(res, p))
            if not chests:
                return self._keep(uid, nonce, (None, "Nothing is waiting."))
            return self._keep(uid, nonce, (self.answer(conn, uid, chests[-1]["key"], chests, len(chests)), None))

    def answer(self, conn, uid, tier, chests, asked):
        rarity = TIER_RARITY.get(tier, "Common")
        coins = sum(c["coins"] for c in chests)
        left = sum(it["qty"] for it in db.get_items(conn, uid, "chests") if it["key"] == tier)
        all_items = [r for c in chests for r in c["rewards"]]
        return {"tier": tier, "name": loot.CHEST_NAMES.get(tier, chests[0]["name"]), "rarity": rarity,
                "color": css(forge.RARITY_COLORS[rarity]), "seals": SEALS.get(tier, 0),
                "picture": item_picture({"category": "chests", "key": tier}),
                "opened": len(chests), "asked": asked, "chests": chests, "coins": coins,
                "summary": grouped(chests), "best": max((r["rank"] for r in all_items), default=-1),
                "left": left, "room": room(conn, uid),
                "lost": [r["name"] for r in all_items if r["lost"]]}
