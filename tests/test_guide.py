import beasts
import discord
import equipments
import technique

from bot import compendium, guide
from bot import player as rules


def all_pages():
    """Every page of every tier (Overview included) of every section."""
    for key in compendium.SECTIONS:
        for tier in [compendium.OVERVIEW] + [t[0] for t in compendium.tiers(key)]:
            first = compendium.tier_page(key, tier)
            for n in range(first["pages"]):
                yield compendium.tier_page(key, tier, n)


def fits_discord(e):
    return (len(e) <= 6000 and len(e.fields) <= 25 and len(e.title or "") <= 256
            and len(e.description or "") <= 4096
            and all(len(f.name) <= 256 and len(f.value) <= 1024 for f in e.fields))


def all_names():
    return "\n".join(f"{t['name']}\n" + "\n".join(t["lines"]) for p in all_pages() for t in p["tiles"])


def test_tutorial_pages_fit_discord_limits():
    assert len(guide.LESSONS) <= len(guide.SCROLL_NUMBERS)
    assert len(guide.LESSONS) <= 25   # the jump menu holds at most 25 options
    for i in range(len(guide.LESSONS)):
        assert fits_discord(guide.lesson_embed(i))


def test_tutorial_teaches_craft_and_forge_step_by_step():
    """The /craft and /forge lessons name the real buttons, so a new player can follow them."""
    text = "\n".join(f"{t}\n{w}\n" + "\n".join(f"{n}\n{v}" for n, v in fields) for t, w, fields in guide.LESSONS)
    for button in ["Begin", "Stoke", "Fan", "Hold", "Condense", "Circulate", "Compress", "Use oldest herbs",
                   "Choose a pill to craft", "Choose gear to forge", "Enchant", "Reroll", "Replace", "Pump", "Vent",
                   "Keep heating", "Pull it out", "Strike Hard", "Strike Light", "Reheat", "Water", "Oil",
                   "Wait a breath", "Plunge"]:
        assert button in text, button
    import alchemy
    from bot import crafting
    assert crafting.PULSES[4] in text   # the moment to press Condense
    assert alchemy.QI_PILLS["Mortal"]["name"] in text
    assert sum("Step 1" in n for _, _, fields in guide.LESSONS for n, _ in fields) == 2


def test_every_section_and_tier_renders():
    from cards.compendium import render_compendium
    seen = set()
    for p in all_pages():
        img = render_compendium(p)
        assert img.size[0] == 1200 and 600 < img.size[1] < 1400, (p["section"], p["tier"], img.size)
        seen.add((p["section"], p["tier"]))
        e = guide.page_embed(p)
        assert fits_discord(e), (p["section"], p["tier"])
        assert 1 <= len(p["tiles"]) <= compendium.PER_PAGE
        for t in p["tiles"]:
            assert t["name"] and 1 <= len(t["lines"]) <= 3
    for key in compendium.SECTIONS:
        assert (key, compendium.OVERVIEW) in seen
        for tier in compendium.tiers(key):
            assert (key, tier[0]) in seen


def test_tier_menus_follow_the_sections():
    assert [t[0] for t in compendium.tiers("beasts")] == rules.REALM_ORDER
    assert [t[0] for t in compendium.tiers("techniques")] == list(technique.GRADES)
    for key in ("weapons", "armor", "artifacts"):
        assert [t[0] for t in compendium.tiers(key)] == equipments.TIERS
        assert [t[1] for t in compendium.tiers(key)] == ["emblem:rarity:" + t for t in equipments.TIERS]
    assert [t[1] for t in compendium.tiers("herbs")] == ["emblem:grade:" + g for g in technique.GRADES]
    assert [t[0] for t in compendium.tiers("chests")] == ["common", "uncommon", "rare", "epic", "legendary", "mythic"]
    assert [t[2] for t in compendium.tiers("pills")] == ["Qi", "Qi Burst", "Mending", "Cleansing", "Breakthrough"]


def test_index_menus_fit_discord_limits():
    import asyncio

    async def go():
        for key in compendium.SECTIONS:
            view = guide.IndexView(1, key)
            view.page_data()
            view.build()
            selects = [c for c in view.children if isinstance(c, discord.ui.Select)]
            assert len(selects) == 2 and len(selects[1].options) <= 25
            assert selects[1].options[0].label == "Overview"
            for s in selects:
                for o in s.options:
                    assert len(o.label) <= 100 and len(o.description or "") <= 100
    asyncio.run(go())


def test_back_and_next_only_when_a_tier_overflows():
    import asyncio

    async def go():
        view = guide.IndexView(1, "weapons", "spirit")
        view.page_data()
        view.build()
        assert not [c for c in view.children if isinstance(c, discord.ui.Button)]
        view = guide.IndexView(1, "artifacts", "treasure")
        view.page_data()
        view.build()
        labels = [c.label for c in view.children if isinstance(c, discord.ui.Button)]
        assert labels == ["Back", "Page 1 of 2", "Next"]
    asyncio.run(go())


def test_artifact_groups_stay_together():
    pages = compendium.paginate(compendium.artifacts_page("treasure")["tiles"])
    assert [{t["group"] for t in p} for p in pages] == [{"Combat"}, {"Cultivation", "Exploration"}]


def test_index_lists_every_beast_technique_and_weapon():
    text = all_names()
    for realm in beasts.BEASTS.values():
        for name, _, _ in realm:
            assert name in text
    for t in technique.TECHNIQUES.values():
        assert t["name"] in text
    for names in equipments.WEAPON_NAMES.values():
        for name in names.values():
            assert name in text


def test_index_numbers_come_from_the_data():
    p = compendium.tier_page("weapons", "spirit")
    lo, hi = equipments.WEAPON_BUFFS["saber"]["spirit"]["attack"]
    saber = next(t for t in p["tiles"] if t["name"] == equipments.WEAPON_NAMES["spirit"]["saber"])
    assert f"+{round(lo * 100)}–{round(hi * 100)}% ATK" in saber["lines"][1]
    p = compendium.tier_page("artifacts", "treasure", 1)
    qi = next(t for t in p["tiles"] if t["name"] == equipments.ARTIFACT_FAMILIES["qi"]["names"][3])
    assert f"{equipments.ARTIFACT_FAMILIES['qi']['values'][3] * 100:g}%" in qi["lines"][1]


def test_search_jumps_to_the_page():
    assert compendium.search("Qilin") == ("beasts", "Martial King", 0, "Qilin")
    assert compendium.search("  qilin ") == ("beasts", "Martial King", 0, "Qilin")
    assert compendium.search("legendary chest") == ("chests", "legendary", 0, None)
    assert compendium.search("azur frost swrd")[3] == "Azure Frost Sword"           # close spelling
    name = equipments.ARTIFACT_FAMILIES["hunter"]["names"][3]
    assert compendium.search(name) == ("artifacts", "treasure", 1, name)            # second page
    assert compendium.search("zzzz nothing") is None
    p = compendium.tier_page("beasts", "Martial King", 0, found="Qilin")
    assert [t["name"] for t in p["tiles"] if t["found"]] == ["Qilin"]
    assert "▶ **Qilin**" in compendium.text_version(p)
    names = compendium.search_names("drag")
    assert names and len(names) <= 25 and all("drag" in n.lower() for n in names)


def test_index_runs_from_a_message():
    import asyncio
    from bot import prefix
    from bot.client import MortalAscent
    from tests.test_prefix import FakeInput

    async def make():
        return MortalAscent(":memory:")
    bot = asyncio.run(make())
    msg = FakeInput("m index search:Qilin")
    assert asyncio.run(prefix.handle_message(bot, msg))
    sent = msg.channel.sent[-1]
    assert sent.kw["file"].filename == "compendium.png"
    assert "Qilin" in sent.kw["embed"].description


def test_beast_multipliers():
    hp, atk, dfn = guide.beast_multipliers("normal", "brute")
    assert (round(hp, 2), round(atk, 2), round(dfn, 2)) == (1.2, 0.72, 0.18)
    assert guide.beast_multipliers("normal", "armored")[2] == 0.8 * 0.25 * 2


def test_pct():
    assert guide.pct(0.25) == "25%"
    assert guide.pct(0.005) == "0.5%"
    assert guide.pct(0.0005) == "0.05%"
