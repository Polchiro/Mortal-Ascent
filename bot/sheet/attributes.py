"""
Character attributes and resources shown on the Character Sheet.

The Martial path has three attributes, HP, Attack and Defense (docs/stats.md),
all worked out from realm + layer and raised by the weapon and the equipped
techniques' passive buffs. Cards draw whatever this module lists, so a later
path (Cultivation) adds its own entries to PATHS without touching the cards.

Resources: Internal Qi (docs/training.md: it fills the layer bar; it is never
spent in fights) and HP (fights start at full HP; losing gives an injury timer,
so there is no stored current HP to show).
"""
from dataclasses import dataclass

from .. import player as rules
from .. import qi as qi_rules


@dataclass(frozen=True)
class Attribute:
    key: str        # name used in buffs (weapon data, technique passives)
    label: str
    icon: str       # cards.theme.icon kind
    color: tuple    # RGB used for the icon


MARTIAL = (
    Attribute("hp", "HP", "heart", (226, 64, 58)),
    Attribute("attack", "Attack", "sword", (232, 186, 102)),
    Attribute("defense", "Defense", "shield", (120, 170, 226)),
)

# path name -> attributes. Add "cultivation": (...) here when that system is designed.
PATHS = {"martial": MARTIAL}


def path_for(player):
    """Which attribute set a player uses. Everyone is on the Martial path until Cultivation exists."""
    return "martial"


def attribute_values(player, techniques=(), weapon=None):
    """[{key, label, icon, color, base, final, bonus, sources: [(name, pct)]}] for the player's path."""
    base = dict(zip(("hp", "attack", "defense"), rules.base_stats(player["realm"], player["layer"])))
    final = dict(zip(("hp", "attack", "defense"), rules.final_stats(player, techniques, weapon)))
    buffs = rules.stat_buffs(techniques, weapon)
    out = []
    for a in PATHS[path_for(player)]:
        src = buffs.get(a.key, [])
        out.append({"key": a.key, "label": a.label, "icon": a.icon, "color": a.color,
                    "base": base[a.key], "final": final[a.key], "bonus": sum(v for _, v in src), "sources": src})
    return out


def qi_resource(player, techniques=(), now=None):
    """Internal Qi as the dantian shows it: current / layer capacity, rate, Qi waiting to be banked,
    time to a full bar and the next gate (reuses the /internal qi numbers)."""
    d = qi_rules.qi_data(player, techniques, now)
    return {"qi": d["qi"], "capacity": d["qi_needed"], "pending": d["pending"], "pending_label": d["pending_label"],
            "rate": d["rate"], "mult": d["mult"], "eta": d["eta"], "gate": d["gate"], "gate_note": d["gate_note"],
            "status": d["status"], "status_tone": d["status_tone"]}


def hp_resource(player, techniques=(), weapon=None, now=None):
    return {"max": rules.final_stats(player, techniques, weapon)[0], "injured_for": rules.injured_for(player, now)}
