"""/admin cooldowns: switch every cooldown off for everyone for a set time, back on, or see the status."""
from bot import admin, cooldowns, db, gathering
from bot import player as rules

NOW = 1_800_000_000.0


def setup():
    conn = db.connect(":memory:")
    for uid in (1, 2):
        db.create_player(conn, uid, f"P{uid}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return conn


def test_off_clears_and_blocks_every_cooldown_until_it_expires():
    conn = setup()
    db.set_cooldown(conn, 1, "explore", 1800, NOW)
    db.set_cooldown(conn, 2, "duel:1", 3600, NOW)
    text, public = admin.cooldowns_switch(conn, "off", hours=2, now=NOW)
    assert public and "2h" in text
    assert db.cooldown_left(conn, 1, "explore", NOW) == 0
    assert db.cooldown_left(conn, 2, "duel:1", NOW) == 0
    db.set_cooldown(conn, 1, "spar", 7200, NOW + 60)          # nothing is saved while off...
    assert db.cooldown_left(conn, 1, "spar", NOW + 60) == 0
    after = NOW + 2 * 3600 + 1                                  # ...and old timers were cleared,
    assert db.cooldowns_off_until(conn, after) == 0             # so when it expires everyone is ready
    assert db.cooldown_left(conn, 1, "spar", after) == 0
    assert db.cooldown_left(conn, 1, "explore", after) == 0
    db.set_cooldown(conn, 1, "explore", 1800, after)            # and cooldowns work again
    assert db.cooldown_left(conn, 1, "explore", after) > 0


def test_on_ends_it_early_and_status_reports():
    conn = setup()
    assert "on** as normal" in admin.cooldowns_switch(conn, "status", now=NOW)[0]
    admin.cooldowns_switch(conn, "off", minutes=30, now=NOW)
    assert "off" in admin.cooldowns_switch(conn, "status", now=NOW + 60)[0]
    assert db.cooldowns_off_until(conn, NOW) == NOW + 1800
    text, public = admin.cooldowns_switch(conn, "on", now=NOW + 60)
    assert public and "back on" in text
    assert db.cooldowns_off_until(conn, NOW + 61) == 0
    assert "already on" in admin.cooldowns_switch(conn, "on", now=NOW + 61)[0]


def test_default_is_one_hour_and_capped():
    conn = setup()
    admin.cooldowns_switch(conn, "off", now=NOW)
    assert db.cooldowns_off_until(conn, NOW) == NOW + 3600
    admin.cooldowns_switch(conn, "off", hours=10_000, now=NOW)
    assert db.cooldowns_off_until(conn, NOW) == NOW + admin.MAX_COOLDOWNS_OFF_HOURS * 3600


def test_survives_reconnect(tmp_path):
    path = str(tmp_path / "game.db")
    conn = db.connect(path)
    db.set_cooldowns_off(conn, 3600, NOW)
    conn.close()
    assert db.cooldowns_off_until(db.connect(path), NOW) == NOW + 3600


def test_gather_pause_and_cooldown_card():
    conn = setup()
    db.update_player(conn, 1, gather_paused_until=NOW + 600)
    p = db.get_player(conn, 1)
    assert gathering.gather_blocked(p, now=NOW, conn=conn)
    db.set_cooldowns_off(conn, 3600, NOW)
    assert gathering.gather_blocked(p, now=NOW, conn=conn) is None
    s = dict(cooldowns.timer_sections(conn, p, NOW))
    assert "🔓 Cooldowns Off" in s
    assert "paused" not in "\n".join(s["Martial Pursuits"])
