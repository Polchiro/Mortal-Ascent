"""
Hunting locations and team hunt numbers (docs/hunting.md).

A location covers a range of realms. Its beasts are the existing roster of those realms (beasts.BEASTS): nothing
new is invented and no beast is renamed. Every member of a party must be inside the range to enter.

Change a location's realms, art or text here; nothing else needs to change.
"""
import beasts
import explore

# key → name, the realms it covers (in order), its text and its pictures (art/scenes/<name>.jpg)
LOCATIONS = [
    {"key": "moon_forest", "name": "Moon Forest",
     "realms": ["Mortal", "Martial Apprentice"],
     "text": "Bamboo and old moonlight. Boars root in the leaf litter, foxes and falcons hunt the clearings, "
             "and something larger leaves claw marks on the trunks.",
     "card": "region_bamboo_forest", "arena": "battle_bamboo_forest"},
    {"key": "crimson_gorge", "name": "Crimson Gorge",
     "realms": ["Martial Warrior", "Martial Expert"],
     "text": "Red stone arches over a dry riverbed. Pythons sun on the ledges and venom-tailed things wait in the shade.",
     "card": "region_red_cliff_gorge", "arena": "battle_red_cliff_gorge"},
    {"key": "frostpeak_mountains", "name": "Frostpeak Mountains",
     "realms": ["Martial Master", "Grandmaster"],
     "text": "Ice fields under a green aurora. Frost wolves run the passes and great shapes move beneath the ice.",
     "card": "region_northern_sea_wilds", "arena": "battle_northern_sea_wilds"},
    {"key": "thunderfall_valley", "name": "Thunderfall Valley",
     "realms": ["Martial Lord", "Martial King"],
     "text": "Lightning strikes the same peaks every night. The beasts here are old, quick and drunk on storm Qi.",
     "card": "region_thunder_peaks", "arena": "battle_thunder_peaks"},
    {"key": "ancient_battlefield", "name": "Ancient Battlefield",
     "realms": ["Martial Emperor", "Martial Ancestor"],
     "text": "A broken arena from a forgotten war. Beasts of legend come to feed on the Qi still soaked into the stone.",
     "card": "arena_ruins", "arena": "arena_ruins"},
    {"key": "celestial_forbidden_lands", "name": "Celestial Forbidden Lands",
     "realms": ["Martial Saint"],
     "text": "A hidden glade where the heavens touch the earth. Only Saints may walk here, and the four Sacred "
             "Beasts answer to no one.",
     "card": "encounter_blessed_land", "arena": "battle_misty_pine_valley"},
]
BY_KEY = {loc["key"]: loc for loc in LOCATIONS}

MAX_PARTY = 4                         # including the leader
MAX_ENCOUNTERS = explore.MAX_STEPS    # one hunt = up to 5 beasts, like the 5 steps of /explore

# Which kind of beast an encounter is. An Elite or a Beast King comes up exactly as often per step as an Elite
# lair or a Beast King's den does in /explore (explore.ENCOUNTERS, with the same deeper-step boost); every other
# encounter is a Normal beast. So a hunt meets Elites and Kings no more often than /explore does.
TIER_ENCOUNTER = {"elite": "elite_lair", "beast_king": "beast_king_den"}


def location(key):
    return BY_KEY.get(key)


def location_for(realm):
    """The location a realm belongs to, or None."""
    return next((loc for loc in LOCATIONS if realm in loc["realms"]), None)


def requirement(loc):
    """'Mortal – Martial Apprentice' or 'Martial Saint'."""
    a, b = loc["realms"][0], loc["realms"][-1]
    return a if a == b else f"{a} – {b}"


def eligible(player, loc):
    """None if this player may hunt here, else why not."""
    if player is None:
        return "No character yet."
    if player["realm"] not in loc["realms"]:
        return f"{player['name']} is {player['realm']}: {loc['name']} is for {requirement(loc)}."
    return None


def pool(loc):
    """Every beast of this location: (name, tier, role, home realm), straight from beasts.BEASTS."""
    return [(name, tier, role, realm) for realm in loc["realms"] for (name, tier, role) in beasts.BEASTS[realm]]


def tier_odds(step, luck=0.0):
    """Chances of a Normal, Elite and Beast King encounter at this step (sum 1)."""
    from bot.expedition import encounter_odds
    odds = encounter_odds(step, luck)
    rare = {tier: odds[enc] for tier, enc in TIER_ENCOUNTER.items()}
    return {"normal": 1 - sum(rare.values()), **rare}
