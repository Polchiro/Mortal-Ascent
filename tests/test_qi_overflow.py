"""Qi above a full bar at a gate is never lost (qi_overflow), and passive Qi is banked on its own."""
import random

import pytest

from bot import db, passive
from bot import player as rules
from bot import qi as qi_rules
from bot.client import sync_passive_qi


class AlwaysFail:
    def random(self):
        return 0.99


class AlwaysWin:
    def random(self):
        return 0.0


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, talent="Ordinary", **fields):
    db.create_player(conn, uid, f"P{uid}", talent, rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    if fields:
        db.update_player(conn, uid, **fields)
    return db.get_player(conn, uid)


def at(realm, layer, qi=0.0, overflow=0.0):
    return {"realm": realm, "layer": layer, "qi": qi, "qi_overflow": overflow, "talent": "Ordinary",
            "breakthroughs": 0, "failed_breakthroughs": 0}


def plain(text):
    return text.replace("**", "")


# ── the bug: Qi above a full bar was thrown away ──────────────────────

def test_qi_above_a_full_bar_waits_behind_the_bottleneck():
    p = at("Martial Apprentice", 3)                   # 3rd layer: the Middle Phase bottleneck
    need = rules.qi_needed("Martial Apprentice", 3)   # 16
    p, events = rules.add_qi(p, 200)
    assert p["qi"] == need and p["qi_overflow"] == pytest.approx(200 - need)
    assert f"Use /breakthrough: {200 - need:,} Qi is waiting" in plain(events[-1])


def test_successful_breakthrough_pours_the_waiting_qi_into_the_next_layers():
    p, _ = rules.add_qi(at("Martial Apprentice", 3), 200)          # bar 16, 184 waiting
    ok, msg = rules.attempt_breakthrough(p, rng=AlwaysWin())
    assert ok and "184.0 Qi" in msg
    # Middle Phase: 4th, 5th and 6th layers need 19 each. 184 fills the 4th and 5th, then the 6th
    # layer is the next bottleneck (Late Phase): its bar stays full and the rest waits again.
    need = rules.qi_needed("Martial Apprentice", 4)
    assert (p["layer"], p["qi"]) == (6, need)
    assert p["qi_overflow"] == pytest.approx(184 - 3 * need)
    assert p["qi"] + p["qi_overflow"] + 2 * need == pytest.approx(184)      # not a point lost


def test_small_overflow_just_starts_the_next_layer():
    p, _ = rules.add_qi(at("Martial Apprentice", 3), 16 + 10)
    ok, _ = rules.attempt_breakthrough(p, rng=AlwaysWin())
    assert ok and (p["layer"], p["qi"], p["qi_overflow"]) == (4, 10, 0)


def test_failed_phase_breakthrough_refills_the_bar_from_the_overflow():
    p, _ = rules.add_qi(at("Martial Apprentice", 3), 200)   # bar 16, 184 waiting
    ok, msg = rules.attempt_breakthrough(p, rng=AlwaysFail())
    assert ok is False and p["layer"] == 3
    lost = 16 * 0.2                                          # still loses 20% of the bar only
    assert p["qi"] == 16                                     # the waiting Qi refills the bar
    assert p["qi_overflow"] == pytest.approx(184 - lost)
    assert p["qi"] + p["qi_overflow"] == pytest.approx(200 - lost)
    assert "refills your bar" in plain(msg)
    p, _ = rules.add_qi(p, 5)                                # new Qi goes behind the gate
    assert p["qi"] == 16 and p["qi_overflow"] == pytest.approx(184 - lost + 5)


def test_realm_gate_keeps_and_then_releases_the_overflow():
    need = rules.qi_needed("Martial Apprentice", 10)         # 32 (Peak ×2)
    p, events = rules.add_qi(at("Martial Apprentice", 10), 100)
    assert p["qi"] == need and p["qi_overflow"] == pytest.approx(68)
    assert "68 Qi is waiting" in plain(events[-1])
    ok, _ = rules.attempt_breakthrough(p, rng=AlwaysFail(), now=0)
    assert ok is False and p["injured_until"] and p["qi"] == need     # the waiting Qi refills the bar
    assert p["qi_overflow"] == pytest.approx(68 - need * 0.2)
    p, _ = rules.add_qi(p, need)                             # more Qi waits behind the gate
    ok, _ = rules.attempt_breakthrough(p, rng=AlwaysWin())
    assert ok and (p["realm"], p["layer"]) == ("Martial Warrior", 2)          # 64 for the 1st layer, then 2nd
    total = 68 + need * 0.8          # 68 + 32 more, minus the 6.4 the failure cost
    assert p["qi"] == pytest.approx(total - 64) and p["qi_overflow"] == 0


def test_locked_realm_gate_keeps_the_qi_too():
    p = at("Martial Expert", 10)
    techs = [{"grade": "Mortal", "mastery_exp": 0}]          # not at Entering the Hall: Martial Master is locked
    p, events = rules.add_qi(p, 10 ** 6, techs)
    need = rules.qi_needed("Martial Expert", 10)
    assert p["qi"] == need and p["qi_overflow"] == pytest.approx(10 ** 6 - need)
    assert "Entering the Hall" in events[-1]


# ── passive Qi ────────────────────────────────────────────────────────

def test_passive_qi_banked_at_a_gate_goes_to_overflow(conn):
    p = new_player(conn, realm="Martial Apprentice", layer=3, qi=16, qi_collected_at=0)
    techs = db.get_techniques(conn, 1)
    rate = rules.qi_rate(p, 10 * 3600, techs)[0]
    qi, _ = sync_passive_qi(conn, 1, now=10 * 3600)
    p = db.get_player(conn, 1)
    assert qi == pytest.approx(rate * 10)
    assert p["qi"] == 16 and p["qi_overflow"] == pytest.approx(rate * 10)


def test_three_days_away_gives_72_hours_at_the_full_rate(conn):
    p = new_player(conn, realm="Martial Warrior", qi_collected_at=0)
    techs = db.get_techniques(conn, 1)
    rate = rules.qi_rate(p, 0, techs)[0]
    qi, hours = rules.passive_qi(p, techs, now=3 * 86400)
    assert hours == 72 and qi == pytest.approx(rate * 72)


def test_background_banking_and_command_banking_never_double_count(conn):
    new_player(conn, 1, qi_collected_at=0)
    new_player(conn, 2, qi_collected_at=0)
    rate = rules.qi_rate(db.get_player(conn, 1), 0, db.get_techniques(conn, 1))[0]
    assert passive.player_ids(conn) == [1, 2]
    for minute in range(1, 61):                               # the task, once a minute for an hour
        passive.bank_everyone(conn, now=minute * 60)
    passive.bank_everyone(conn, now=3600)                     # the same minute again adds nothing
    sync_passive_qi(conn, 1, now=3600)                        # a command right after: nothing new
    sync_passive_qi(conn, 1, now=2 * 3600)                    # a command an hour later: one more hour
    passive.bank_everyone(conn, now=2 * 3600)
    total = lambda uid: (db.get_player(conn, uid)["qi"] + db.get_player(conn, uid)["qi_overflow"]
                         + sum(rules.qi_needed("Mortal", layer) for layer in range(1, db.get_player(conn, uid)["layer"])))
    assert total(1) == pytest.approx(rate * 2)
    assert total(2) == pytest.approx(rate * 2)


def test_players_left_in_the_removed_seclusion_are_let_out(conn):
    """/seclusion was removed: anyone still inside gets ×2 Qi for the hours spent and gathers again."""
    new_player(conn, 1, qi_collected_at=0, seclusion_start=0, seclusion_end=8 * 3600)    # finished
    new_player(conn, 2, qi_collected_at=0, seclusion_start=0, seclusion_end=24 * 3600)   # 4h in
    new_player(conn, 3, qi_collected_at=0)
    rate = rules.qi_rate(db.get_player(conn, 1), 0, db.get_techniques(conn, 1))[0]
    total = lambda uid: (db.get_player(conn, uid)["qi"] + db.get_player(conn, uid)["qi_overflow"]
                         + sum(rules.qi_needed("Mortal", layer) for layer in range(1, db.get_player(conn, uid)["layer"])))
    assert passive.release_secluded(conn, now=12 * 3600) == [1, 2]
    assert total(1) == pytest.approx(rate * 2 * 8)
    p2 = db.get_player(conn, 2)
    assert p2["seclusion_start"] is None and p2["seclusion_end"] is None and p2["qi_collected_at"] == 12 * 3600
    assert total(2) == pytest.approx(rate * 2 * 12)
    assert total(3) == 0 and db.get_player(conn, 3)["qi_collected_at"] == 0       # others untouched
    assert passive.release_secluded(conn, now=13 * 3600) == []


def test_batches_split_everyone():
    assert list(passive.batches(list(range(5)), 2)) == [[0, 1], [2, 3], [4]]


# ── the "your Qi is full" ping ────────────────────────────────────────

def test_full_bar_ping_is_sent_once_per_gate(conn):
    new_player(conn, realm="Martial Apprentice", layer=3, qi=15, qi_collected_at=0, last_channel_id=555)
    assert passive.bank_everyone(conn, now=60) == []          # not full yet
    pings = passive.bank_everyone(conn, now=3600)             # fills the bar at the bottleneck
    assert pings == [(1, 555, "<@1>, your Qi is full: use **/breakthrough**!")]
    assert passive.bank_everyone(conn, now=7200) == []        # already told about this gate
    # a failed breakthrough, then the bar refills at the same gate: still no second ping
    p = db.get_player(conn, 1)
    rules.attempt_breakthrough(p, rng=AlwaysFail())
    db.update_player(conn, 1, **rules.progress_fields(p))
    assert passive.bank_everyone(conn, now=10 * 3600) == []
    # a new gate pings again
    p = db.get_player(conn, 1)
    rules.attempt_breakthrough(p, rng=AlwaysWin())
    db.update_player(conn, 1, **dict(rules.progress_fields(p), qi=0, qi_overflow=0, qi_collected_at=10 * 3600))
    pings = passive.bank_everyone(conn, now=40 * 3600)
    assert db.get_player(conn, 1)["layer"] == 6 and [x[0] for x in pings] == [1]


def test_no_ping_when_turned_off_or_no_channel_or_locked(conn):
    new_player(conn, 1, realm="Martial Apprentice", layer=3, qi=15, qi_collected_at=0, last_channel_id=5, qi_pings=0)
    new_player(conn, 2, realm="Martial Apprentice", layer=3, qi=15, qi_collected_at=0)
    new_player(conn, 3, realm="Martial Expert", layer=10, qi=0, qi_collected_at=0, last_channel_id=5)
    assert passive.bank_everyone(conn, now=100 * 3600) == []
    assert db.get_player(conn, 1)["qi_overflow"] > 0          # Qi still banked, just no ping


def test_command_banking_returns_the_ping(conn):
    new_player(conn, realm="Martial Apprentice", layer=3, qi=15, qi_collected_at=0, last_channel_id=9)
    _, _, ping = passive.bank(conn, 1, now=3600)
    assert ping == (9, passive.ping_text(1))
    assert passive.bank(conn, 1, now=7200)[2] is None


# ── what the cards show ───────────────────────────────────────────────

def test_cards_show_the_waiting_qi(conn):
    from bot.sheet import data as sheet
    from cards import RENDERERS
    from cards.dantian import render_dantian

    p = new_player(conn, realm="Martial Apprentice", layer=3, qi=16, qi_overflow=180)
    p["qi_collected_at"] = 1e12                                # nothing pending, just the stored overflow
    d = qi_rules.qi_data(p, db.get_techniques(conn, 1), now=1e12)
    assert d["overflow_text"] == "Qi bar full · +180 Qi waiting behind the bottleneck"
    assert d["status"] == "Bar full · use /breakthrough" and d["eta"] == "Ready now"
    render_dantian(d)
    prof = sheet.profile_data(conn, 1, "tester")
    assert prof["qi"]["overflow_text"] == "Qi bar full · +180 Qi waiting behind the bottleneck"
    assert RENDERERS["profile"](prof).size[0] == 1200


def test_server_rank_counts_the_waiting_qi(conn):
    new_player(conn, 1, realm="Martial Apprentice", layer=3, qi=16, qi_overflow=50)
    new_player(conn, 2, realm="Martial Apprentice", layer=3, qi=16)
    assert db.server_rank(conn, 1, rules.REALM_ORDER) == 1 and db.server_rank(conn, 2, rules.REALM_ORDER) == 2


def test_settings_command_toggles_pings(conn):
    import asyncio
    from types import SimpleNamespace
    from bot.client import MortalAscent

    sent = []

    class Response:
        async def send_message(self, *a, **kw):
            sent.append(kw.get("embed"))

    async def go():
        bot = MortalAscent(":memory:")
        new_player(bot.conn, 1)
        cmd = bot.tree.get_command("settings")
        it = SimpleNamespace(user=SimpleNamespace(id=1), response=Response())
        await cmd.callback(it, qi_pings=SimpleNamespace(value="off"))
        off = db.get_player(bot.conn, 1)["qi_pings"]
        await cmd.callback(it, qi_pings=SimpleNamespace(value="on"))
        return off, db.get_player(bot.conn, 1)["qi_pings"]
    assert asyncio.run(go()) == (0, 1)
    assert "Off" in sent[0].description and "On" in sent[1].description
