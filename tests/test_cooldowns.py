import time

from bot import cooldowns, db
from bot import player as rules

NOW = 1_800_000_000.0   # fixed clock


def setup():
    conn = db.connect(":memory:")
    db.create_player(conn, 1, "Lin", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return conn


def text(sections):
    return {title: "\n".join(lines) for title, lines in sections}


def test_fresh_player_is_ready():
    conn = setup()
    s = text(cooldowns.timer_sections(conn, db.get_player(conn, 1), NOW))
    assert s["Martial Pursuits"].count(cooldowns.READY) == 4
    assert "Mastery Trials" not in s
    assert "0 / 5 at full gain" in s["Daily Discipline"]
    assert "meridians whole" in s["Body & Meridians"]


def test_timers_show_discord_timestamps():
    conn = setup()
    db.set_cooldown(conn, 1, "explore", 600, NOW)
    db.set_cooldown(conn, 1, "trial:1", 3600, NOW)
    for _ in range(6):
        db.bump_daily(conn, 1, "practice", NOW)
    db.update_player(conn, 1, injured_until=NOW + 120, seclusion_start=NOW, seclusion_end=NOW + 8 * 3600,
                     pill_grade="Mortal", pill_mult=1.2, pill_expires=NOW + 900,
                     blessing_tier="Spring Rain", blessing_expires=NOW + 86400)
    s = text(cooldowns.timer_sections(conn, db.get_player(conn, 1), NOW))
    assert f"<t:{int(NOW + 600)}:R> · <t:{int(NOW + 600)}:t>" in s["Martial Pursuits"]
    assert "Barred, 🧘 in seclusion" in s["Martial Pursuits"]          # spar blocked
    assert f"<t:{int(NOW + 3600)}:R>" in s["Mastery Trials"]
    assert "6 done · now at 50% gain" in s["Daily Discipline"]
    assert f"<t:{int(NOW + 8 * 3600)}:R>" in s["Body & Meridians"]
    assert f"<t:{int(NOW + 120)}:R>" in s["Body & Meridians"]
    assert "Ember Dantian Pill" in s["Heavenly Boons"]


def test_next_utc_midnight():
    m = cooldowns.next_utc_midnight(NOW)
    assert m > NOW and m - NOW <= 86400 and m % 86400 == 0
