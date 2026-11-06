"""Friendly PvP duels (docs/pvp.md): fair stats, secret picks, timeouts and forfeits, rising intensity,
the turn-20 decision, the fair-fight limits, the duel log and the /duel checks."""
import asyncio
import random
import time

import pytest

import pvp
import stats
from bot import admin, db, duel_view
from bot import duel as D
from bot import player as rules
from cards.battle import render_duel

from test_exploits import FakeInteraction


class FixedRng(random.Random):
    """Damage rolls at exactly 1.0 and every chance succeeds, so numbers are predictable."""

    def uniform(self, a, b):
        return 1.0

    def random(self):
        return 0.0


def tech(name, type_, grade="Mortal", tid=1, exp=0, stage=0):
    return {"id": tid, "name": name, "type": type_, "grade": grade, "mastery_exp": exp, "stage": stage}


TECHS = [tech("Iron Fist", "attack", tid=1), tech("Horse Stance Guard", "defense", tid=2)]


def player(uid, name, realm="Martial Warrior", layer=3, talent="Ordinary"):
    return {"user_id": uid, "name": name, "realm": realm, "layer": layer, "talent": talent}


def weapon(buffs):
    return {"name": "Test Blade", "data": {"buffs": buffs}}


def make(p1=None, p2=None, techs1=TECHS, techs2=TECHS, w1=None, w2=None, rng=None):
    return D.start(p1 or player(1, "Ana"), techs1, w1, p2 or player(2, "Bo"), techs2, w2, rng or FixedRng())


def play(d, m1, m2):
    a, b = d.sides
    if m1:
        assert d.choose(a.uid, m1) is None
    if m2:
        assert d.choose(b.uid, m2) is None
    return d.resolve()


# ── fair stats ────────────────────────────────────────────────────────

def test_both_fight_at_the_lower_players_realm_and_layer():
    hi, lo = player(1, "Hi", "Martial Expert", 7), player(2, "Lo", "Martial Warrior", 9)
    assert D.lower_of(hi, lo) == ("Martial Warrior", 9)
    assert D.lower_of(player(1, "A", "Mortal", 3), player(2, "B", "Mortal", 2)) == ("Mortal", 2)
    d = D.start(hi, [], None, lo, [], None)
    base = rules.base_stats("Martial Warrior", 9)
    for side in d.sides:
        assert (side.max_hp, side.attack, side.defense) == base     # no buffs: exactly the lower player's base stats
        assert side.hp == side.max_hp
    assert d.fair == ("Martial Warrior", 9)


def test_gear_and_technique_buffs_count_at_half():
    w = weapon({"attack": 0.20, "hp": 0.10})
    hp, atk, dfn = rules.base_stats("Martial Warrior", 3)
    got = D.fair_stats(player(1, "A"), TECHS, w, "Martial Warrior", 3)
    atk_pct = 0.20 + 0.02          # weapon + Iron Fist's passive (Mortal grade, no mastery)
    def_pct = 0.02                 # Horse Stance Guard's passive
    assert got == (round(hp * (1 + 0.10 * pvp.BUFF_SHARE)), round(atk * (1 + atk_pct * pvp.BUFF_SHARE)),
                   round(dfn * (1 + def_pct * pvp.BUFF_SHARE)))
    full = rules.final_stats(player(1, "A"), TECHS, w)
    assert got[1] < full[1] and got[0] < full[0]


def test_technique_effects_and_mastery_count_fully():
    master = tech("Iron Fist", "attack", exp=10 ** 6, stage=4)
    d = make(techs1=[master])
    skill, *_ = d._skill(d.sides[0], "attack_tech")
    assert skill == pytest.approx(1.20 * rules.mastery_mult(master))
    assert rules.mastery_mult(master) > 1


# ── secret picks ──────────────────────────────────────────────────────

def test_picks_stay_secret_until_both_have_picked():
    d = make()
    a, b = d.sides
    assert d.choose(a.uid, "break") is None
    assert d.locked(a) and not d.locked(b) and not d.both_picked()
    data_break, text_break = duel_view.duel_card_data(d), duel_view.duel_embed(d).description
    for other in ("strike", "guard", "attack_tech", "defense_tech"):   # whatever was picked, card and text are the same
        a.pick = other
        assert duel_view.duel_card_data(d) == data_break
        assert duel_view.duel_embed(d).description == text_break
    assert [s["locked"] for s in data_break["sides"]] == [True, False]
    assert "✅ locked in" in text_break
    a.pick = "break"
    assert a.hp == a.max_hp and b.hp == b.max_hp and d.turn == 1    # nothing resolved yet


def test_a_pick_is_locked_and_resting_techniques_are_refused():
    d = make()
    a, b = d.sides
    assert d.choose(a.uid, "guard") is None
    assert "already locked in" in d.choose(a.uid, "strike")
    assert d.choose(99, "strike") == "You are not in this duel."
    assert d.choose(b.uid, "pill") is not None                      # no pills in duels
    play(d, None, "attack_tech")
    assert "recovering" in d.choose(b.uid, "attack_tech")           # normal per-technique cooldown
    assert d.choose(b.uid, "strike") is None


def test_reveal_shows_both_moves():
    d = make()
    log = play(d, "strike", "defense_tech")
    assert log[0] == ("star", "Ana: Strike  ·  Bo: Horse Stance Guard")
    assert d.sides[0].last_move == "Strike" and d.sides[1].last_move == "Horse Stance Guard"


def test_view_answers_each_press_privately():
    async def go():
        conn = db.connect(":memory:")
        bot = type("Bot", (), {"conn": conn, "db_lock": asyncio.Lock(), "busy": set(), "emojis_ma": None})()
        d = make()
        view = duel_view.DuelView(bot, d)
        edits = []

        async def no_card():
            return None

        async def edit(interaction=None, **kw):
            edits.append(kw)
        view.card_file, view.edit = no_card, edit
        it = FakeInteraction(1)
        await view.on_pick(it, "guard")
        assert it.sent == ["You chose **Guard**. Waiting for Bo..."]
        assert d.turn == 1 and "Locked in: Ana" in edits[-1]["content"]
        it2 = FakeInteraction(2)
        await view.on_pick(it2, "break")
        assert it2.sent == ["You chose **Break**."]
        assert d.turn == 2 and d.sides[0].hp < d.sides[0].max_hp      # Break beats Guard
        view._cancel_timer()
        watcher = FakeInteraction(3)
        assert not await view.interaction_check(watcher)
        assert "watching" in watcher.sent[0]
    asyncio.run(go())


# ── counters ──────────────────────────────────────────────────────────

def test_counters_follow_the_beast_fight_rules():
    d = make()
    a, b = d.sides
    play(d, "strike", "break")                                       # Strike beats Break
    assert a.hp == a.max_hp and b.hp < b.max_hp
    d = make()
    a, b = d.sides
    play(d, "strike", "guard")                                       # Guard beats Strike
    assert a.hp == a.max_hp and b.hp == b.max_hp
    d = make()
    a, b = d.sides
    play(d, "break", "guard")                                        # Break beats Guard and staggers
    assert b.hp < b.max_hp and b.staggered and a.hp == a.max_hp
    d = make()
    a, b = d.sides
    play(d, "strike", "strike")                                      # clash: both at 50%
    clash = a.max_hp - a.hp
    d2 = make()
    play(d2, "strike", "break")
    assert clash == pytest.approx((d2.sides[1].max_hp - d2.sides[1].hp) * pvp.CLASH_DAMAGE, abs=1)


# ── timeouts and forfeits ─────────────────────────────────────────────

def test_a_timeout_is_a_guard_and_three_in_a_row_forfeit():
    d = make()
    a, b = d.sides
    log = play(d, "strike", None)
    assert ("hourglass", "Bo hesitated: Guard.") in log and b.hp == b.max_hp     # the timeout Guarded the Strike
    play(d, "guard", None)
    assert not d.over and b.timeouts == 2
    play(d, "guard", None)
    assert d.over and d.winner is a and d.reason == "timeouts"


def test_a_pick_resets_the_timeout_count():
    d = make()
    b = d.sides[1]
    play(d, "guard", None)
    play(d, "guard", None)
    play(d, "guard", "guard")
    assert b.timeouts == 0
    play(d, "guard", None)
    assert not d.over


def test_both_timing_out_is_a_draw():
    d = make()
    for _ in range(pvp.TIMEOUTS_TO_FORFEIT):
        d.resolve()
    assert d.over and d.result == "draw" and d.winner is None


def test_flee_is_a_forfeit():
    d = make()
    d.forfeit(1)
    assert d.over and d.winner is d.sides[1] and d.reason == "forfeit"


# ── fair-fight rules ──────────────────────────────────────────────────

def test_rising_intensity_from_turn_10():
    d = make()
    assert [d.intensity(t) for t in (1, 9, 10, 11, 15)] == [0, 0, 0.1, 0.2, 0.6]
    first = make(p1=player(1, "A", "Martial Saint", 10), p2=player(2, "B", "Martial Saint", 10))
    play(first, "strike", "break")
    early = first.sides[1].max_hp - first.sides[1].hp
    late = make(p1=player(1, "A", "Martial Saint", 10), p2=player(2, "B", "Martial Saint", 10))
    late.turn = 11
    play(late, "strike", "break")
    hit = late.sides[1].max_hp - late.sides[1].hp
    assert hit == pytest.approx(early * 1.2, abs=1)


def test_the_30_percent_cap_still_holds():
    d = make()
    d.turn = 20
    play(d, "attack_tech", "break")
    b = d.sides[1]
    assert b.max_hp - b.hp == round(b.max_hp * stats.MAX_HIT_PERCENT)


def test_turn_20_the_higher_hp_share_wins():
    d = make()
    a, b = d.sides
    d.turn = pvp.MAX_TURNS
    a.hp, b.hp = a.max_hp * 0.4, b.max_hp * 0.6
    play(d, "guard", "guard")
    assert d.over and d.winner is b and d.reason == "time"


def test_turn_20_equal_hp_is_a_draw():
    d = make()
    d.turn = pvp.MAX_TURNS - 1
    play(d, "guard", "guard")
    assert not d.over and d.turn == pvp.MAX_TURNS
    play(d, "guard", "guard")
    assert d.over and d.result == "draw" and d.winner is None


def test_recover_heals_at_most_half_max_hp_per_duel():
    calm = tech("Calm Breath Stance", "defense", tid=3)
    d = make(techs2=[calm])
    b = d.sides[1]
    b.hp = 1
    for _ in range(40):
        b.cooldowns["defense_tech"] = 0
        play(d, "strike", "defense_tech")
        d.turn = 1                                               # keep the duel going, no intensity
    assert b.healed == pytest.approx(b.max_hp * pvp.RECOVER_MAX_PER_DUEL, abs=1)
    assert b.hp <= 1 + b.max_hp * pvp.RECOVER_MAX_PER_DUEL


def test_evade_cannot_trigger_two_turns_in_a_row():
    mist = tech("Drifting Mist Steps", "defense", "Mystic", tid=3)
    d = make(techs2=[mist])
    b = d.sides[1]
    play(d, "break", "defense_tech")
    assert b.hp == b.max_hp                                      # evaded (the chance always succeeds here)
    b.cooldowns["defense_tech"] = 0
    play(d, "break", "defense_tech")
    assert b.hp < b.max_hp                                       # not again the very next turn
    b.cooldowns["defense_tech"] = 0
    hp = b.hp
    play(d, "break", "defense_tech")
    assert b.hp == hp                                            # a turn later it works again


def test_ko_ends_the_duel():
    d = make()
    a, b = d.sides
    b.hp = 1
    play(d, "strike", "break")
    assert d.over and d.winner is a and d.reason == "ko"


# ── the log and the profile counts ────────────────────────────────────

def test_save_duel_logs_every_move_and_counts_wins():
    conn = db.connect(":memory:")
    for uid, name in ((1, "Ana"), (2, "Bo")):
        db.create_player(conn, uid, name, "Ordinary", 50, rules.starting_techniques())
    d = make()
    play(d, "attack_tech", "guard")
    play(d, "break", None)
    d.forfeit(2)
    duel_id = db.save_duel(conn, d, channel_id=5)
    row = conn.execute("SELECT * FROM duels WHERE id = ?", (duel_id,)).fetchone()
    assert (row["p1_id"], row["p2_id"], row["winner_id"], row["reason"], row["turns"]) == (1, 2, 1, "forfeit", 2)
    assert row["fair_realm"] == "Martial Warrior 3" and "Iron Fist" in row["p1_techniques"]
    moves = conn.execute("SELECT * FROM duel_moves WHERE duel_id = ? ORDER BY turn, user_id", (duel_id,)).fetchall()
    assert [(m["turn"], m["user_id"], m["move"], m["technique"], m["timed_out"]) for m in moves] == [
        (1, 1, "attack_tech", "Iron Fist", 0), (1, 2, "guard", None, 0),
        (2, 1, "break", None, 0), (2, 2, "guard", None, 1)]
    assert db.get_player(conn, 1)["duels_won"] == 1 and db.get_player(conn, 2)["duels_lost"] == 1
    summary, rows = db.duel_stats(conn)
    assert summary["duels"] == 1
    iron = next(r for r in rows if r["name"] == "Iron Fist")
    assert (iron["picks"], iron["duels"], iron["wins"]) == (1, 1, 1)
    assert not any(r["name"] == "guard" and r["picks"] > 1 for r in rows)    # the timed-out Guard is left out
    text = admin.duelstats_text(conn)
    assert "Iron Fist" in text and "100%" in text


def test_a_draw_counts_for_nobody():
    conn = db.connect(":memory:")
    for uid, name in ((1, "Ana"), (2, "Bo")):
        db.create_player(conn, uid, name, "Ordinary", 50, rules.starting_techniques())
    d = make()
    for _ in range(pvp.TIMEOUTS_TO_FORFEIT):
        d.resolve()
    db.save_duel(conn, d)
    assert all(db.get_player(conn, u)["duels_won"] == db.get_player(conn, u)["duels_lost"] == 0 for u in (1, 2))


def test_profile_shows_duels():
    from bot.sheet import data as sheet
    conn = db.connect(":memory:")
    db.create_player(conn, 1, "Ana", "Ordinary", 50, rules.starting_techniques())
    db.update_player(conn, 1, duels_won=4, duels_lost=2)
    data = sheet.profile_data(conn, 1, "Ana")
    assert (data["duels_won"], data["duels_lost"]) == (4, 2)


# ── /duel checks ──────────────────────────────────────────────────────

class User:
    def __init__(self, uid, bot=False, name="X"):
        self.id, self.bot, self.display_name = uid, bot, name


def test_who_can_duel():
    conn = db.connect(":memory:")
    for uid in (1, 2):
        db.create_player(conn, uid, f"P{uid}", "Ordinary", 50, rules.starting_techniques())
    bot = type("Bot", (), {"conn": conn, "busy": set()})()
    me, them = User(1), User(2)
    assert duel_view.why_cannot_duel(bot, me, them) is None
    assert "yourself" in duel_view.why_cannot_duel(bot, me, User(1))
    assert "Bots" in duel_view.why_cannot_duel(bot, me, User(9, bot=True))
    assert "/start" in duel_view.why_cannot_duel(bot, me, User(3))
    bot.busy.add((2, "explore"))
    assert "busy" in duel_view.why_cannot_duel(bot, me, them)
    bot.busy.clear()
    bot.busy.add((2, "hunt"))
    assert "busy" in duel_view.why_cannot_duel(bot, me, them)
    bot.busy.clear()
    db.update_player(conn, 2, seclusion_start=time.time(), seclusion_end=time.time() + 3600)
    assert "seclusion" in duel_view.why_cannot_duel(bot, me, them)
    db.update_player(conn, 2, seclusion_start=None, seclusion_end=None, injured_until=time.time() + 600)
    assert "injured" in duel_view.why_cannot_duel(bot, me, them)
    db.update_player(conn, 2, injured_until=None)
    duel_view.set_pair_cooldown(conn, 1, 2)
    assert "breath" in duel_view.why_cannot_duel(bot, me, them)
    assert "breath" in duel_view.why_cannot_duel(bot, them, me)           # per pair, both ways
    db.create_player(conn, 3, "P3", "Ordinary", 50, rules.starting_techniques())
    assert duel_view.why_cannot_duel(bot, me, User(3)) is None


# ── the card ──────────────────────────────────────────────────────────

def test_duel_card_renders_every_stage():
    d = make()
    assert render_duel(duel_view.duel_card_data(d)).size == (1200, 780)
    d.choose(1, "guard")
    d.turn = 12
    data = duel_view.duel_card_data(d)
    assert data["intensity"] == pytest.approx(0.3) and data["sides"][0]["locked"]
    render_duel(data)
    d.forfeit(2)
    data = duel_view.duel_card_data(d)
    assert data["result"]["title"] == "Ana" and data["sides"][0]["winner"] and data["sides"][1]["loser"]
    render_duel(data)


def test_accept_starts_the_duel_and_decline_frees_the_challenger():
    async def go():
        conn = db.connect(":memory:")
        for uid in (1, 2):
            db.create_player(conn, uid, f"P{uid}", "Ordinary", 50, rules.starting_techniques())
        bot = type("Bot", (), {"conn": conn, "db_lock": asyncio.Lock(), "busy": set(), "emojis_ma": None})()
        ch, tg = User(1, name="P1"), User(2, name="P2")

        bot.busy.add((1, "duel"))                                   # set by /duel when the challenge is posted
        view = duel_view.ChallengeView(bot, ch, tg)
        it = FakeInteraction(2)
        await view.on_decline(it)
        assert (1, "duel") not in bot.busy and view.done

        bot.busy.add((1, "duel"))
        view = duel_view.ChallengeView(bot, ch, tg)
        outsider = FakeInteraction(3)
        await view.on_accept(outsider)
        assert "Only the challenged player" in outsider.sent[0] and not view.done
        it = FakeInteraction(2)
        it.channel = None
        await view.on_accept(it)
        assert view.done and {(1, "duel"), (2, "duel")} <= bot.busy
        assert db.cooldown_left(conn, 1, "duel:2") > 0
        again = FakeInteraction(2)
        await view.on_accept(again)                                 # a lagged double click starts nothing
        assert "over" in again.sent[0]
        for task in asyncio.all_tasks():
            if task is not asyncio.current_task():
                task.cancel()
    asyncio.run(go())


def test_startup_lists_the_synced_commands_and_flags_missing_ones():
    from bot.client import sync_report
    ok = sync_report(["duel", "spar"], ["spar", "duel"], "abc123")
    assert ok[0] == "Bot code version: abc123" and "duel, spar" in ok[1] and "All commands reached" in ok[2]
    bad = sync_report(["duel", "spar"], ["spar"])
    assert bad[-1] == "WARNING: these commands did not reach Discord: duel"
