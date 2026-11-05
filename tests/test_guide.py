import beasts
import equipments
import technique

from bot import guide
from bot import player as rules


def all_index_embeds():
    for key, (_, _, build, _) in guide.SECTIONS.items():
        for page in range(len(build())):
            yield key, page, guide.index_embed(key, page)[0]


def fits_discord(e):
    return (len(e) <= 6000 and len(e.fields) <= 25 and len(e.title) <= 256
            and len(e.description or "") <= 4096
            and all(len(f.name) <= 256 and len(f.value) <= 1024 for f in e.fields))


def test_tutorial_pages_fit_discord_limits():
    assert len(guide.LESSONS) <= len(guide.SCROLL_NUMBERS)
    assert len(guide.LESSONS) <= 25   # the jump menu holds at most 25 options
    for i in range(len(guide.LESSONS)):
        assert fits_discord(guide.lesson_embed(i))


def test_index_pages_fit_discord_limits():
    for key, page, e in all_index_embeds():
        assert fits_discord(e), (key, page)


def test_index_lists_every_beast_technique_and_weapon():
    text = "\n".join(f.name for _, _, e in all_index_embeds() for f in e.fields)
    for realm in beasts.BEASTS.values():
        for name, _, _ in realm:
            assert name in text
    for t in technique.TECHNIQUES.values():
        assert t["name"] in text
    for names in equipments.WEAPON_NAMES.values():
        for name in names.values():
            assert name in text


def test_beast_pages_follow_realm_order():
    pages = guide.beast_pages()
    assert [p[0] for p in pages] == [f"Beasts · {r}" for r in rules.REALM_ORDER]


def test_beast_multipliers():
    hp, atk, dfn = guide.beast_multipliers("normal", "brute")
    assert (round(hp, 2), round(atk, 2), round(dfn, 2)) == (1.2, 0.72, 0.18)
    assert guide.beast_multipliers("normal", "armored")[2] == 0.8 * 0.25 * 2


def test_pct():
    assert guide.pct(0.25) == "25%"
    assert guide.pct(0.005) == "0.5%"
    assert guide.pct(0.0005) == "0.05%"
