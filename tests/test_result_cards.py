"""Result cards for /spar, /train, /practice and /explore: data from real game runs, rendering and sending."""
import asyncio
import random
import sys

import pytest

from bot import db, result_cards, trainer
from bot import player as rules
from bot.expedition import Expedition
from cards import activity, results, theme


@pytest.fixture
def conn():
    return db.connect(":memory:")


class FakeBot:
    def __init__(self, conn):
        self.conn, self.db_lock, self.busy = conn, asyncio.Lock(), set()


def new_player(conn, uid=1):
    return db.create_player(conn, uid, f"P{uid}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())


def test_each_activity_has_its_own_accent():
    colours = {theme.ACCENTS[k].main for k in ("crimson", "spar", "train", "explore")}
    assert len(colours) == 4


def test_clean_strips_markdown_and_emoji():
    assert activity.clean("🏆 **You win the spar!**") == ("You win the spar!", False)
    assert activity.clean("*You have sparred a lot today: EXP ×0.5.*") == ("You have sparred a lot today: EXP ×0.5.", True)
    assert activity.clean("⬆️ You reached the **2nd Layer**!")[0] == "You reached the 2nd Layer!"


def spar_to_the_end(conn, forfeit=False):
    from bot.views import SparView

    async def go():        # discord views need a running event loop
        view = SparView(FakeBot(conn), 1, rng=random.Random(0))
        if forfeit:
            view.result = view.finish(forfeit=True)
        else:
            while not view.spar.over:
                view.last = view.spar.play(view.spar.choices()[0][0])
            view.result = view.finish()
        return view
    return asyncio.run(go())


def test_spar_card_from_a_real_spar(conn):
    new_player(conn)
    view = spar_to_the_end(conn)
    data = view.card
    assert data["outcome"] in ("victory", "defeat") and data["name"] == "P1"
    assert all(g["exp"] > 0 for g in data["gains"])
    assert results.render_spar(data).size == (1200, results.H)


def test_spar_card_after_walking_away(conn):
    new_player(conn)
    data = spar_to_the_end(conn, forfeit=True).card
    assert data["outcome"] == "forfeit" and data["gains"] == []
    results.render_spar(data)


def test_train_and_practice_cards(conn):
    new_player(conn)
    p = db.get_player(conn, 1)
    s = trainer.roll_session(p, random.Random(0))
    qi, events, p = trainer.finish(conn, 1, s, 0.8, rng=random.Random(0))
    need = rules.qi_needed(p["realm"], p["layer"])
    data = result_cards.train_data(p, s, 0.8, {"qi": qi, "total": p["qi"], "need": need, "realm": p["realm"],
                                               "layer": p["layer"]}, ["✅ Correct!"] + events, 60, "train")
    assert not any(ord(ch) > 0x2600 for ch in data["challenge"] + "".join(data["conditions"]))
    assert results.render_train(data).size == (1200, results.H)

    tech = db.get_techniques(conn, 1)[0]
    s = trainer.roll_session(p, random.Random(1), tech=tech)
    exp, _, _, tech = trainer.finish_practice(conn, 1, s, 0.3)
    data = result_cards.train_data(p, s, 0.3, {"technique": tech["name"], "exp": round(exp),
                                               "total": tech["mastery_exp"], "cap": rules.mastery_cap(tech)}, [], 30,
                                   "practise")
    results.render_train(data)


def test_explore_card_from_a_real_expedition(conn):
    new_player(conn)
    exp = Expedition(conn, 1, random.Random(3))
    for _ in range(3):
        exp.next_step()
        exp.choose("left")
        if exp.pending == "hazard":
            exp.dodge("middle")
        elif exp.pending == "stranger":
            exp.help_stranger("leave")
        if exp.over:
            break
    exp.finish()
    data = result_cards.explore_data(exp)
    assert data["coins"] == exp.banked["coins"] and len(data["items"]) == len(exp.banked["stored"])
    assert results.render_explore(data).size == (1200, results.H)


def test_explore_card_with_a_full_spoils_list(conn):
    new_player(conn)
    exp = Expedition(conn, 1, random.Random(0))
    exp.next_step()
    from bot import loot
    exp.items = [loot.chest("jade"), loot.herb("Mortal", "qi", 10), loot.pill("Yellow")] * 4
    exp.finish()
    results.render_explore(result_cards.explore_data(exp))


def test_result_cards_need_only_pillow(conn, monkeypatch):
    monkeypatch.setitem(sys.modules, "numpy", None)
    theme._background.cache_clear()
    new_player(conn)
    activity.render_spar(spar_to_the_end(conn).card)
    theme._background.cache_clear()


def test_spar_end_sends_the_card(conn):
    """The last click of a spar replaces the embed with the card image."""
    new_player(conn)
    sent = {}

    class Response:
        async def defer(self, **kw):
            pass

        async def edit_message(self, **kw):
            pass

    class Interaction:
        response = Response()

        async def edit_original_response(self, **kw):
            sent.update(kw)

    async def go():
        from bot.views import SparView
        view = SparView(FakeBot(conn), 1, rng=random.Random(0))
        while not view.result:
            await view.play(Interaction(), view.spar.choices()[0][0])
    asyncio.run(go())
    assert sent["embed"] is None and sent["attachments"][0].filename == "spar.png"


def test_expedition_card_and_button_show_every_item():
    """No '+N more': the cloth grows a row for every 7 spoils, and the button lists them all."""
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))), "scripts"))
    import render_results as R
    from bot.views import spoils_text
    many = dict(R.EXPLORE, items=R.EXPLORE["items"] * 4)          # 16 items + coins + 1 lost = 18 spoils
    assert results.render_explore(R.EXPLORE).size == (1200, results.H)
    assert results.render_explore(many).size[1] > results.H
    text = spoils_text(many)
    for it in many["items"] + many["lost"]:
        assert it["name"] in text
    assert "312" in text and "Left behind" in text
