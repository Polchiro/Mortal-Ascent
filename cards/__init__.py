"""
Character Sheet cards in the Crimson Hall theme (see cards/theme.py).

RENDERERS maps each sheet tab to its render function; each takes the dict that
bot.sheet.data builds for that tab and returns a PIL Image.
"""
from .bag import render_bag
from .equipment import render_equipment
from .profile import render_profile
from .purse import render_purse
from .techniques import render_techniques

RENDERERS = {
    "profile": render_profile,
    "techniques": render_techniques,
    "equipment": render_equipment,
    "inventory": render_bag,
    "purse": render_purse,
}
