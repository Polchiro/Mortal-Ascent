"""Herbs and /gather (docs/alchemy.md): herb items, ages, the old-herb swap, gathering rounds, /index pages."""
import random

import pytest

import alchemy
from bot import compendium, db, gathering, loot
from bot import player as rules
from bot.expedition import Expedition
from bot.sheet import data as sheet
from bot.sheet import items


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, realm="Mortal"):
    db.create_player(conn, uid, f"P{uid}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(conn, uid, realm=realm)
    return db.get_player(conn, uid)


# ── herb items ────────────────────────────────────────────────────────

def test_herbs_stack_by_kind_and_age(conn):
    new_player(conn)
    loot.store(conn, 1, [loot.herb("Mortal", "qi", 10), loot.herb("Mortal", "qi", 10), loot.herb("Mortal", "qi", 50),
                         loot.herb("Mortal", "purity", 10)])
    bag = {(h["name"], h["data"]["age"]): h["qty"] for h in db.get_items(conn, 1, "herbs")}
    assert bag == {("Spirit Grass", 10): 2, ("Spirit Grass", 50): 1, ("Dew Leaf", 10): 1}
    assert loot.describe(dict(loot.herb("Yellow", "purity", 50), qty=3)) == "🌿 50-year Silver Moss ×3"


def test_age_odds_add_up_and_streak_raises_old_herbs():
    for streak in (0, 10, 25, 50):
        assert abs(sum(loot.age_odds(streak).values()) - 1) < 1e-9
    assert loot.age_odds(50)[1000] == alchemy.HERB_AGES[1000]["chance"] * 3
    assert loot.age_odds(9)[50] == alchemy.HERB_AGES[50]["chance"]


def test_every_grade_can_be_found_at_every_realm():
    for realm in alchemy.HERB_TIER_BY_REALM:
        odds = alchemy.herb_grade_odds(realm)
        assert set(odds) == set(alchemy.GRADES)
        assert abs(sum(odds.values()) - 1) < 1e-9
        assert all(c > 0 for c in odds.values())
        assert max(odds, key=odds.get) == "Mortal"          # Mortal herbs never become rare


def test_mortal_odds_follow_the_weight_table():
    odds = alchemy.herb_grade_odds("Mortal")
    total = sum(alchemy.HERB_GRADE_WEIGHTS.values())
    for g, w in alchemy.HERB_GRADE_WEIGHTS.items():
        assert odds[g] == pytest.approx(w / total)
    rng = random.Random(1)
    tiers = [loot.herb_tier("Mortal", rng) for _ in range(5000)]
    assert 0.77 < tiers.count("Mortal") / len(tiers) < 0.83
    assert "Mystic" in tiers                                  # rare grades really drop for a Mortal


def test_higher_realms_are_luckier_for_rare_herbs():
    order = list(alchemy.REALM_HERB_LUCK)
    for grade in ["Mystic", "Earth", "Heaven"]:
        chances = [alchemy.herb_grade_odds(r)[grade] for r in order]
        assert chances == sorted(chances)
    assert alchemy.herb_grade_odds("Martial Saint")["Mortal"] > 0.25
    assert alchemy.herb_grade_odds("Mortal")["Heaven"] < 0.01


def test_old_herbs_are_swapped_for_new_ones(tmp_path):
    path = tmp_path / "old.db"
    conn = db.connect(str(path))
    new_player(conn)
    with conn:
        conn.execute("INSERT INTO items (user_id, category, key, name, qty) VALUES (1, 'materials', "
                     "'Tiger Bone Moss', 'Tiger Bone Moss', 3)")
        conn.execute("INSERT INTO items (user_id, category, key, name, qty) VALUES (1, 'materials', "
                     "'Dew Lotus Petal', 'Dew Lotus Petal', 2)")
        conn.execute("INSERT INTO items (user_id, category, key, name, qty) VALUES (1, 'materials', "
                     "'Moonlight Fern', 'Moonlight Fern', 1)")
    conn.close()
    conn = db.connect(str(path))
    assert db.get_items(conn, 1, "materials") == []
    bag = {h["name"]: h["qty"] for h in db.get_items(conn, 1, "herbs")}
    assert bag == {"Iron Root": 3, "Dew Leaf": 3}
    assert not hasattr(loot, "HERBS")                         # the old herb list is gone


def test_herbs_show_in_their_own_bag_tab(conn):
    p = new_player(conn)
    loot.store(conn, 1, [loot.herb("Mortal", "breakthrough", 500)])
    data, _, _, sel = sheet.bag_data(conn, 1, "herbs")
    assert ("herbs", "Herbs", "herb") in data["categories"]
    assert data["tiles"][0]["rarity"] == "500-year"
    d = items.details(sel, p)
    assert d["kind"] == "Mortal Breakthrough herb" and "Breakthrough pills" in d["effects"][0]
    assert items.actions(sel) == ["discard"]


# ── /explore gives the new herbs ──────────────────────────────────────

def test_herb_patch_gives_herbs_of_any_grade(conn):
    new_player(conn, realm="Martial Warrior")
    e = Expedition(conn, 1, random.Random(3))
    for _ in range(20):
        e._herb_patch()
    herbs = [i for i in e.items]
    assert herbs and all(h["category"] == "herbs" and h["grade"] in alchemy.GRADES for h in herbs)
    lo, hi = alchemy.HERB_PATCH_HERBS
    assert lo * 20 <= len(herbs) <= hi * 20


def test_merchant_sells_a_new_herb(conn):
    new_player(conn)
    db.add_coins(conn, 1, 1000)
    e = Expedition(conn, 1, random.Random(2))
    e._wandering_merchant()
    assert e.merchant["herb"] in {n for n, _ in alchemy.HERBS["Mortal"].values()}
    assert e.buy("herb") is None
    assert db.get_items(conn, 1, "herbs")[0]["name"] == e.merchant["herb"]


# ── /gather rounds ────────────────────────────────────────────────────

def test_a_round_has_the_herb_and_a_decoy(conn):
    new_player(conn)
    g = gathering.Gathering(conn, 1, random.Random(5))
    for _ in range(30):
        r = g._herb_round(g.player)
        assert len(r.options) in (alchemy.GATHER_CHOICES, alchemy.OLD_HERB_CHOICES)
        labels = [label for _, label, _ in r.options]
        assert len(set(labels)) == len(labels)
        right = dict((k, label) for k, label, _ in r.options)[r.answer]
        name, desc = alchemy.HERBS[r.herb["grade"]][r.herb["data"]["type"]]
        assert right == alchemy.LOOKS[name] and right != desc       # the look, never the description's words
        assert r.names[r.answer] == name and r.place
        assert r.decoys and r.answer not in r.decoys


def test_every_herb_and_decoy_has_its_own_look():
    plants = [p for t in alchemy.HERBS.values() for p in t.values()] + [p for d in alchemy.DECOYS.values() for p in d]
    assert set(alchemy.LOOKS) == {name for name, _ in plants}
    for name, desc in plants:
        look = alchemy.LOOKS[name]
        assert look.lower() != desc.lower() and look not in desc and desc not in look
    for tier in alchemy.HERBS:                 # within a tier no two plants look alike
        looks = [alchemy.LOOKS[n] for n, _ in alchemy.HERBS[tier].values()] + [alchemy.LOOKS[n] for n, _ in alchemy.DECOYS[tier]]
        assert len(set(looks)) == len(looks)


def test_right_pick_gathers_and_builds_the_streak(conn):
    new_player(conn)
    g = gathering.Gathering(conn, 1, random.Random(5))
    r = g.next_round()
    text = g.answer(r.answer, 1.0)
    assert "gather" in text.lower()
    p = g.player
    assert p["herb_streak"] == 1 and p["herbs_gathered"] == 1
    assert db.get_items(conn, 1, "herbs")[0]["key"] == r.herb["key"]


def test_decoy_poisons_and_resets_the_streak(conn):
    new_player(conn)
    db.update_player(conn, 1, herb_streak=12)
    g = gathering.Gathering(conn, 1, random.Random(5))
    r = g.next_round()
    text = g.answer(next(iter(r.decoys)), 1.0)
    assert "☠️" in text and g.hp == g.max_hp - round(g.max_hp * alchemy.DECOY_HP_LOSS)
    assert g.player["herb_streak"] == 0 and db.get_items(conn, 1, "herbs") == []
    g.hp = 1
    r = g.next_round()
    g.answer(next(iter(r.decoys)), 1.0)
    assert g.hp == 1                                           # never below 1


def test_too_slow_gathers_nothing(conn):
    new_player(conn)
    g = gathering.Gathering(conn, 1, random.Random(5))
    r = g.next_round()
    assert "Too slow" in g.answer(r.answer, r.seconds + gathering.TIMER_GRACE_SECONDS + 0.5)
    assert db.get_items(conn, 1, "herbs") == []


def test_three_missed_spirit_checks_pause_gathering(conn):
    new_player(conn)
    g = gathering.Gathering(conn, 1, random.Random(5))
    for n in range(alchemy.SPIRIT_CHECK_FAILS_TO_PAUSE):
        db.update_player(conn, 1, spirit_check_in=0)
        r = g.next_round()
        assert r.kind == "spirit"
        wrong = next(k for k, _, _ in r.options if k != r.answer)
        g.answer(wrong, 1.0, now=1000)
    assert g.over
    assert "Gather again" in gathering.gather_blocked(g.player, now=1000)
    assert gathering.gather_blocked(g.player, now=1000 + alchemy.SPIRIT_CHECK_PAUSE_MINUTES * 60 + 1) is None


def test_passing_a_spirit_check_resets_it(conn):
    new_player(conn)
    db.update_player(conn, 1, spirit_check_in=0, spirit_check_fails=2)
    g = gathering.Gathering(conn, 1, random.Random(5))
    r = g.next_round()
    g.answer(r.answer, 1.0)
    p = g.player
    assert p["spirit_check_fails"] == 0 and p["spirit_check_in"] >= alchemy.SPIRIT_CHECK_EVERY[0]


def test_inhumanly_fast_picks_are_flagged(conn):
    new_player(conn)
    g = gathering.Gathering(conn, 1, random.Random(5))
    db.update_player(conn, 1, spirit_check_in=999)
    for _ in range(alchemy.FLAG_AVG_OVER_GATHERS):
        r = g.next_round()
        g.answer(r.answer, 0.1)
    assert "average pick" in g.player["gather_flag"]


# ── /index ────────────────────────────────────────────────────────────

def test_index_lists_every_herb_decoy_and_pill():
    text = "\n".join(f"{t['name']}\n" + "\n".join(t["lines"])
                     for key in ("herbs", "pills")
                     for tier in [compendium.OVERVIEW] + [t[0] for t in compendium.tiers(key)]
                     for n in range(compendium.tier_page(key, tier)["pages"])
                     for t in compendium.tier_page(key, tier, n)["tiles"])
    for tier in alchemy.GRADES:
        for name, _ in alchemy.HERBS[tier].values():
            assert name in text
        for name, _ in alchemy.DECOYS[tier]:
            assert name in text
        assert alchemy.QI_PILLS[tier]["name"] in text
    assert "2 Spirit Grass + 1 Dew Leaf" in text
    assert "1 Beast King Core" in text


# ── the gathering message ─────────────────────────────────────────────

def test_gather_view_plays_rounds_and_times_out(conn):
    import asyncio

    new_player(conn)

    class FakeBot:
        def __init__(self, c):
            self.conn, self.db_lock, self.busy = c, asyncio.Lock(), {(1, "gather")}

    class Response:
        def __init__(self, it):
            self.it, self.done = it, False

        def is_done(self):
            return self.done

        async def defer(self, **kw):
            self.done = True

        async def edit_message(self, **kw):
            self.done = True
            self.it.edits.append(kw)

    class FakeInteraction:
        def __init__(self):
            self.edits = []
            self.response = Response(self)

        async def edit_original_response(self, **kw):
            self.edits.append(kw)

        async def original_response(self):
            return FakeMessage()

    class FakeMessage:
        def __init__(self):
            self.edits = []

        async def edit(self, **kw):
            self.edits.append(kw)

    async def go():
        bot = FakeBot(conn)
        view = gathering.GatherView(bot, 1, random.Random(5))
        r = view.g.round
        n = len(r.options)
        assert [c.label for c in view.children] == [str(i + 1) for i in range(n)] + ["Stop"]
        it = FakeInteraction()
        await view.send(it)
        view.timer.cancel()
        kw = it.edits[-1]
        assert kw["attachments"][0].filename == "gather.jpg" and r.herb["name"] in kw["content"]
        assert r.options[0][1] in kw["content"]                    # the looks are readable in the text too
        it = FakeInteraction()
        await view.resolve(r.answer, 1.0, it)
        assert "Gather Again" in [c.label for c in view.children]
        assert "✅" in it.edits[-1]["content"] and it.edits[-1]["attachments"]
        it = FakeInteraction()
        await view.on_again(it)
        r2 = view.g.round
        assert r2 is not None
        view.message = FakeMessage()
        r2.seconds = 0.01                                   # let the round run out
        view.timer.cancel()
        gathering.TIMER_GRACE_SECONDS, grace = 0.0, gathering.TIMER_GRACE_SECONDS
        try:
            view.start_timer()
            await asyncio.sleep(1.5)
        finally:
            gathering.TIMER_GRACE_SECONDS = grace
        assert view.g.round is None and "Too slow" in view.message.edits[-1]["content"]
        await view.on_stop(FakeInteraction())
        assert (1, "gather") not in bot.busy
        view.timer.cancel()

    asyncio.run(go())


def test_stop_during_a_round_counts_it_as_missed(conn):
    import asyncio

    new_player(conn)
    db.update_player(conn, 1, herb_streak=7, spirit_check_in=99)

    class FakeBot:
        def __init__(self, c):
            self.conn, self.db_lock, self.busy = c, asyncio.Lock(), {(1, "gather")}

    class Response:
        done = False

        def is_done(self):
            return self.done

        async def defer(self, **kw):
            self.done = True

    class FakeInteraction:
        def __init__(self):
            self.response, self.edits = Response(), []

        async def edit_original_response(self, **kw):
            self.edits.append(kw)

    async def go():
        view = gathering.GatherView(FakeBot(conn), 1, random.Random(5))
        it = FakeInteraction()
        await view.on_stop(it)
        assert view.g.over and db.get_player(conn, 1)["herb_streak"] == 0
        assert "head home" in it.edits[-1]["content"] and it.edits[-1]["view"] is None
    asyncio.run(go())



@pytest.mark.parametrize("tier", alchemy.GRADES)
def test_rare_finds_get_their_own_lines_and_announcement(conn, tier, monkeypatch):
    new_player(conn)
    monkeypatch.setattr(gathering.loot, "herb_tier", lambda realm, rng=None: tier)
    g = gathering.Gathering(conn, 1, random.Random(5))
    r = g.next_round()
    appear, gathered = alchemy.HERB_RARITY[tier][2:]
    assert (appear in r.prompt) if appear else True
    text = g.answer(r.answer, 1.0)
    assert text.startswith(("✅", "✨"))
    assert (gathered in text) if gathered else "\n" not in text
    assert (g.announce is not None) == alchemy.is_announced(tier)
    if g.announce:
        msg = gathering.rare_find_announcement("Lin", g.announce)
        assert "Lin" in msg and tier in msg and alchemy.HERB_RARITY[tier][0].upper() in msg
