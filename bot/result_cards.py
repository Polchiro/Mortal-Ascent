"""
Data for the /spar, /train and /explore result cards (cards/activity.py), and sending them.

Only presentation lives here: the game logic has already run when these are called.
If a card fails to render, card_file returns None and the caller keeps its text embed.
"""
import io
import logging

import discord

import explore
import technique

from . import render as card_render
from .sheet import items as sheet_items

log = logging.getLogger("mortal-ascent")


def png(image, filename):
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return discord.File(buf, filename=filename)


def _who(player):
    return {"name": player["name"], "realm": player["realm"], "layer": player["layer"]}


def spar_data(view, outcome, gains, notes):
    """outcome: victory / defeat / forfeit. gains: [(technique, exp)]."""
    from .sparring import MAX_TURNS
    sp = view.spar
    hours = technique.SPAR_COOLDOWN_MINUTES / 60
    return dict(_who(view.player), title=view.title_plain, outcome=outcome, turn=sp.turn, max_turns=MAX_TURNS,
                hp=sp.hp, max_hp=sp.max_hp, m_hp=sp.m_hp, m_max=sp.m_max,
                gains=[{"name": tech["name"], "type": tech["type"], "exp": round(exp)} for tech, exp in gains],
                timed=bool(sp.timed), notes=notes, cooldown=f"Spar again in {hours:g} hour{'s' if hours != 1 else ''}")


def train_data(player, session, score, reward, notes, cooldown_minutes, verb):
    from cards.activity import clean
    from . import trainer
    return dict(_who(player), mode=session["mode"], challenge=clean(trainer.CHALLENGE_NAMES[session["challenge"]])[0],
                conditions=[clean(trainer.CONDITION_NAMES[c])[0] for c in session["conditions"]],
                score=score, reward=reward, notes=notes, cooldown=f"{verb.title()} again in {cooldown_minutes:g} min")


def _tile(item):
    label, key = sheet_items.rarity(item)
    return {"name": item["name"], "qty": item.get("qty", 1), "icon": sheet_items.item_icon(item),
            "color_key": key, "label": label}


def explore_data(exp):
    b = exp.banked or {"coins": 0, "stored": [], "lost": []}
    from .explore_card import REGION_BY_TIER
    return dict(_who(exp.player), defeated=exp.defeated, step=exp.step, max_steps=explore.MAX_STEPS,
                region=REGION_BY_TIER.get(getattr(exp, "tier", None), ""),
                hp=exp.hp, max_hp=exp.max_hp, coins=b["coins"], beasts=exp.beasts_slain,
                items=[_tile(i) for i in b["stored"]], lost=[_tile(i) for i in b["lost"]],
                story=list(exp.story), notes=list(exp.notes),
                cooldown=f"Explore again in {explore.EXPLORE_COOLDOWN_MINUTES:g} min")


async def card_file(fn, data, filename):
    """Render off the event loop. Returns a discord.File, or None if rendering failed."""
    try:
        return png(await card_render.render(fn, data), filename)
    except Exception:
        log.exception("Could not render %s", filename)
        return None
