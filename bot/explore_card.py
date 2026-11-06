"""
Plain data for the live /explore cards (cards/expedition.py), built from a running Expedition.

Only reads the expedition: it never changes a rule or a number. A path is drawn from its clue (what the
player is told), so a misleading clue shows the mood it describes, never the real encounter.
"""
import re

import challenges
import explore

from .expedition import BLESSED_LAND_NAMES, CLUES
from .sheet import items as sheet_items

# clue text → the kind of encounter it describes (a misleading clue still describes its own kind)
CLUE_KIND = {clue: kind for kind, clues in CLUES.items() for clue in clues}

# clue text → the short label on the path's arrow badge
CLUE_LABEL = {
    "You hear low growling...": "Low growling", "Fresh claw marks scar the trees.": "Claw marks",
    "Something heavy breathes in the brush.": "Heavy breathing",
    "Something glints between the roots.": "A glint", "A faint golden glow...": "A golden glow",
    "An old cart lies overturned.": "An old cart",
    "A sweet, earthy smell drifts by.": "A sweet smell", "Dew sparkles on thick green leaves.": "Thick leaves",
    "Bees hum over wild flowers.": "Humming bees",
    "Rock glitters along a cliff face.": "Glittering rock", "The clink of loose stones rings like metal.": "Ringing stones",
    "Rust-red streaks run down the rocks.": "Rust-red streaks",
    "Complete silence.": "Too quiet", "Soft sunlight through the leaves.": "Soft sunlight",
    "Birds sing calmly.": "Birdsong",
    "The air smells sour.": "Sour air", "Loose stones trickle down the slope.": "Loose stones",
    "A thin mist clings to the ground.": "Thin mist",
    "Muffled voices and laughter.": "Voices", "A campfire's smoke rises ahead.": "Campfire smoke",
    "Boot prints, many of them.": "Boot prints",
    "A bell jingles in the distance.": "A bell", "The creak of a heavy pack.": "A heavy pack",
    "Someone hums a trader's tune.": "A trader's tune",
    "A weak voice calls for help.": "A weak voice", "Drops of blood on the path.": "Blood drops",
    "A torn sleeve hangs on a branch.": "A torn sleeve",
    "Moss-covered stones in a ring.": "A stone ring", "Carved characters peek through vines.": "Carvings",
    "An old shrine, long forgotten.": "An old shrine",
    "Bones are piled by a cave mouth.": "Piled bones", "The ground trembles with heavy steps.": "Heavy steps",
    "Every bird has fled.": "No birds",
    "The air feels light and pure.": "Pure air", "Qi ripples like warm water.": "Rippling Qi",
    "Flowers bloom out of season.": "Odd blooms",
    "A flute plays a lonely melody.": "A flute", "An old voice recites scripture.": "Scripture",
    "Incense smoke curls through the trees.": "Incense",
    "A roar shakes the whole forest.": "A roar", "The trees are torn from their roots.": "Torn trees",
    "A crushing pressure fills the air.": "Crushing aura",
}

# Regions are not designed yet (docs/explore.md "Not decided yet"): this is only the name on the card.
REGION_BY_TIER = {1: "Bamboo Forest", 2: "Misty Pine Valley", 3: "Red Cliff Gorge", 4: "Thunder Peaks",
                  5: "Northern Sea Wilds"}
CORE_SHORT = {"Normal Beast Core": "Beast Core", "Elite Beast Core": "Elite Core", "Beast King Core": "King Core"}
FIGHT_TITLE = {"won": "Victory", "lost": "Defeated", "fled": "You Escaped", "escaped": "It Got Away"}
BANDIT_TITLE = {"won": "Bandits Driven Off", "lost": "Robbed", "fled": "You Slipped Away", "escaped": "They Scattered"}


def clue_kind(clue):
    return CLUE_KIND.get(clue, "peaceful_clearing")


def place(kind):
    from cards.expedition import MOOD
    return MOOD[kind][1]


def _tiles(items):
    """Found items as card tiles; herbs of the same kind and age (and same chests) are counted together."""
    tiles, index = [], {}
    for it in items:
        label, key = sheet_items.rarity(it)
        name = it["name"]
        if it["category"] == "materials" and it["key"].startswith("core:"):
            name = CORE_SHORT.get(name, name)
        sig = (name, label)
        if sig in index:
            index[sig]["qty"] += it.get("qty", 1)
            continue
        tile = {"name": name, "qty": it.get("qty", 1), "icon": sheet_items.item_icon(it), "color_key": key,
                "label": label}
        index[sig] = tile
        tiles.append(tile)
    return tiles


def _bonus(step):
    if step <= 1:
        return "No depth bonus yet"
    return f"Beasts +{(step - 1) * explore.BEAST_STAT_BONUS_PER_STEP:.0%}  ·  rare ×{explore.RARE_CHANCE_BY_STEP[step]:g}"


def _common(exp):
    p = exp.player
    return {"region": REGION_BY_TIER.get(exp.tier, "The Wilds"), "realm": p["realm"], "step": exp.step,
            "max_steps": explore.MAX_STEPS, "hp": exp.hp, "max_hp": exp.max_hp, "coins": exp.coins,
            "items": _tiles(exp.items), "bonus": _bonus(exp.step),
            "defeat_note": f"If defeated: lose {explore.DEFEAT_LOOT_LOSS:.0%} of these coins and herbs."}


def crossroads_data(exp):
    paths = {}
    for key, (_, clue) in exp.paths.items():
        kind = clue_kind(clue)
        paths[key] = {"kind": kind, "label": CLUE_LABEL.get(clue, "?").upper(), "place": place(kind), "clue": clue}
    lie = explore.MISLEADING_CLUE_CHANCE[challenges.REALM_TIER[exp.player["realm"]]]
    return dict(_common(exp), paths=paths, lie_note=f"Clues can lie at your realm ({lie:.0%})" if lie else "")


def coins_words(text):
    """'+🪷 6' → '+6 coins': the card fonts have no emoji."""
    return re.sub(r"🪷\s*([\d,]+)", r"\1 coins", text)


def story_lines(exp):
    from cards.activity import clean
    return [t for t in (clean(coins_words(s))[0] for s in exp.story) if t]


def encounter_data(exp, notice=None):
    """The card after a path was chosen: the real encounter (or the fight that just ended)."""
    kind = exp.encounter or "peaceful_clearing"
    data = dict(_common(exp), kind=kind, story=story_lines(exp), outcome=None)
    title = TITLE.get(kind, "Encounter")
    b = exp.last_battle if kind in ("wild_beast", "bandits") and exp.pending is None else None
    if b is not None:
        e = b.enemy
        data["fight"] = {"palette": e.get("element", "Earth"), "body": e.get("body", "human"), "slug": e.get("slug")}
        title = (FIGHT_TITLE if exp.enemy_kind == "beast" else BANDIT_TITLE).get(b.result, title)
        data["outcome"] = "good" if b.result == "won" else ("bad" if b.result == "lost" else None)
        sub = e["name"]
    elif exp.pending == "hazard" and exp.hazard:
        h = exp.hazard
        data["hazard"] = {"danger": h["danger"], "kind": h["kind"]}
        title = "Poison Mist!" if h["kind"] == "poison mist" else "Landslide!"
        data["outcome"] = "bad"
        sub = "Leap away, quickly"
    else:
        sub = place(kind)
        if kind == "blessed_land" and exp.player.get("blessed_land") in BLESSED_LAND_NAMES:
            from cards.activity import clean
            title = clean(BLESSED_LAND_NAMES[exp.player["blessed_land"]])[0]
    m = exp.merchant
    if kind == "wandering_merchant" and m and exp.pending is None:
        import alchemy
        wares = [(alchemy.QI_PILLS[m["pill"]]["name"], m["pill_price"], "pill"), (m["herb"], m["herb_price"], "herb")]
        data["story"].append("Wares: " + "  ·  ".join(f"{name}, {price:,} coins" + (" (bought)" if key in m["bought"] else "")
                                                     for name, price, key in wares))
    if notice:
        from cards.activity import clean
        data["story"].append(clean(notice)[0])
    data.update(title=title, subtitle=f"Step {exp.step}  ·  {sub}")
    return data


TITLE = {
    "wild_beast": "Wild Beast", "treasure_chest": "Treasure Chest", "herb_patch": "Herb Patch", "ore_vein": "Ore Vein",
    "peaceful_clearing": "Peaceful Clearing", "hazard": "Hazard", "bandits": "Bandits",
    "wandering_merchant": "Wandering Merchant", "injured_stranger": "Injured Stranger",
    "stone_tablet": "Ancient Stone Tablet", "elite_lair": "Elite Beast Lair", "blessed_land": "Blessed Land",
    "wandering_hermit": "Wandering Hermit", "beast_king_den": "Beast King's Den",
}
