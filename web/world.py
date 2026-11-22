"""
The World Map (docs/world.md): the painted scroll that joins the town and the six hunting grounds into one world.

You come to it through the town gate (web/town.py EXITS) and go from it to a hunting ground, or back to town. Each
place on the scroll is a marker drawn by the page over SHOAIB's painting (art/maps/world.webp, cut out by
scripts/make_world_map.py), at `at`: its spot on the picture, as shares of its width and height (0..1), measured on
the painting. The names, the glow and the locks are the page's, as Gemini garbles writing.

The world decides nothing new. A hunting ground is the hunting grounds' own (hunting.LOCATIONS: its realms, beasts
and rewards); setting out there is a Solo Hunt on the walkable map (web/hunt_play.py), with the same checks as
/explore: the ground's lowest realm or higher (hunting.eligible), not injured, not resting from the last expedition
(Hunts.blocked). The server makes every one of those checks again when you set out (/world/go), whatever the page
showed.
"""
import hunting

NAME = "The World Map"
ART = "/art/maps/world.webp"

# Where each place is painted on the scroll (x, y: shares of the picture's width and height).
AT = {
    "town": (0.175, 0.605),
    "moon_forest": (0.330, 0.800),
    "crimson_gorge": (0.500, 0.505),
    "frostpeak_mountains": (0.215, 0.240),
    "thunderfall_valley": (0.825, 0.215),
    "ancient_battlefield": (0.800, 0.545),
    "celestial_forbidden_lands": (0.510, 0.190),
}

TOWN = {"key": "town", "name": "Azure Cloud Town", "kind": "town",
        "text": "Home: the forge, the alchemy hall, the arena and the townsfolk, behind safe walls.",
        "go": "/town"}                     # you come back in at the gate (web/town.py START)


def place(key):
    """A hunting ground's location (hunting.LOCATIONS), or None."""
    return hunting.location(key)


def markers(player, blocked=None):
    """The scroll's markers for this player: the town, then each hunting ground with whether they may set out there.

    `blocked`: why this player can't set out at all right now (injured, resting: Hunts.blocked), or None.
    A ground is `open` (set out now), `waiting` (the realm is right, but injured or resting: `why`, and `short`:
    "Injured" or "Resting") or `locked` (the realm is too low: it needs `requirement`)."""
    out = [{**TOWN, "at": AT["town"], "state": "home"}]
    short = ("Injured" if blocked.startswith("injured") else "Resting") if blocked else None
    for loc in hunting.LOCATIONS:
        why = hunting.eligible(player, loc)
        state = "locked" if why else "waiting" if blocked else "open"
        out.append({"key": loc["key"], "name": loc["name"], "kind": "hunt", "text": loc["text"], "at": AT[loc["key"]],
                    "requirement": hunting.requirement(loc), "realms": hunting.home_realms(loc),
                    "here": player["realm"] in loc["realms"], "state": state,
                    "why": why if why else (blocked if blocked else None), "short": short})
    return out
