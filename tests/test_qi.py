import time

import pytest

from bot import db
from bot import player as rules
from bot import qi


@pytest.fixture
def conn():
    return db.connect(":memory:")


def make(conn, talent="Genius"):
    p = db.create_player(conn, 1, "P1", talent, rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    return p, db.get_techniques(conn, 1)


def test_rate_matches_meditate_formula(conn):
    p, techs = make(conn)
    now = time.time()
    d = qi.qi_data(p, techs, now)
    assert d["rate"] == pytest.approx(rules.qi_rate(p, now, techs)[0])
    assert d["formula"].endswith(f"= {d['rate']:,.2f} Qi/h")
    labels = [r["label"] for r in d["sources"]]
    assert labels[:3] == ["Realm base", "Talent", "Technique"]
    assert {r["label"]: r["active"] for r in d["sources"]}["Qi Pill"] is False


def test_boosts_show_up(conn):
    p, techs = make(conn)
    now = time.time()
    p.update(blessing_tier="Bright Moon", blessing_expires=now + 5 * 86400,
             pill_grade="Yellow", pill_mult=1.4, pill_expires=now + 3600,
             blessed_land="dragon_vein", blessed_land_expires=now + 600)
    d = qi.qi_data(p, techs, now)
    rows = {r["label"]: r for r in d["sources"]}
    assert rows["Heavenly Blessing"]["value"] == "+30%" and rows["Heavenly Blessing"]["active"]
    assert rows["Qi Pill"]["value"] == "×1.40"
    assert rows["Blessed Land"]["value"] == "×3" and "Dragon Vein" in rows["Blessed Land"]["detail"]
    assert d["mult"] == pytest.approx(rules.qi_rate(p, now, techs)[1])


def test_eta_counts_waiting_qi_and_seclusion(conn):
    p, techs = make(conn)
    now = p["created_at"] + 3600            # one hour of passive Qi stored
    d = qi.qi_data(p, techs, now)
    need = rules.qi_needed("Mortal", 1)
    assert d["pending"] == pytest.approx(min(need, d["rate"]))
    p.update(seclusion_start=now, seclusion_end=now + 8 * 3600)
    d = qi.qi_data(p, techs, now)
    assert d["secluded"] and d["status"].startswith("In seclusion")


def test_full_bar_at_gate(conn):
    p, techs = make(conn)
    p.update(layer=3, qi=rules.qi_needed("Mortal", 3))
    d = qi.qi_data(p, techs)
    assert d["status"] == "Bar full · use /breakthrough" and d["eta"] == "Ready now"
    assert d["gate"] == "Martial Apprentice"


def test_card_renders(conn, monkeypatch):
    import profile_card
    from qi_card import H_QI, render_qi

    p, techs = make(conn)
    assert render_qi(qi.qi_data(p, techs)).size == (1200, H_QI)
    monkeypatch.setattr(profile_card, "FALLBACK_FONTS", ["no-such-font.ttf"])
    monkeypatch.setattr(profile_card, "CJK_CANDIDATES", ["no-such-cjk.otf"])
    assert render_qi(qi.qi_data(p, techs)).size == (1200, H_QI)
