"""/profession (bot/profession.py) and the shop / blessing confirmations and cards."""
import time

import economy
from bot import profession
from bot.views import blessing_data, pearl_confirm_embed


def test_ranks_unlocks_and_card():
    from cards.profession import render_profession
    d = profession.card_data({"name": "A", "alchemy_exp": 450, "blacksmith_exp": 0})
    alc, smith = d["sides"]
    assert alc["rank"] == 3 and alc["next"] == "4th Grade" and alc["to_next"] == 750
    assert "Yellow Qi" in alc["can"] and "Mystic Qi" not in alc["can"]
    assert smith["rank"] == 1 and smith["can"] == ["Ordinary"] and smith["upcoming"][1] == ["Refined"]
    top = profession.card_data({"name": "A", "alchemy_exp": 10 ** 7, "blacksmith_exp": 10 ** 7})
    assert top["sides"][0]["next"] is None and top["sides"][0]["upcoming"] is None
    assert render_profession(d).size[0] == render_profession(top).size[0] == 1200


def test_confirm_shows_price_balance_and_shortfall():
    e = pearl_confirm_embed({"moon_pearls": 500}, "Buy **Seal Stone**", "Seal Stone", 30)
    assert "500 → **🌙 470**" in e.description
    e = pearl_confirm_embed({"moon_pearls": 10}, "Buy **Seal Stone**", "Seal Stone", 30)
    assert "need **🌙 20 more**" in e.description


def test_blessing_card_marks_the_active_tier():
    from cards.blessings import render_blessings
    p = {"moon_pearls": 2000, "blessing_tier": "Spring Rain", "blessing_expires": time.time() + 5 * 86400}
    d = blessing_data(p)
    assert [t["name"] for t in d["tiers"]] == list(economy.BLESSING_TIERS)
    assert [t["name"] for t in d["tiers"] if t["active"]] == ["Spring Rain"] and d["active"][1] == 5
    assert render_blessings(d).size[0] == 1200
    assert render_blessings(blessing_data({"moon_pearls": 0})).size[0] == 1200
