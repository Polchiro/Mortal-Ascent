"""Breakthrough odds drop as the realms get higher (training.py, bot/player.py)."""
from types import SimpleNamespace

import pytest

import training
from bot import player as rules


def at_gate(realm, layer):
    p = {"realm": realm, "layer": layer, "qi_overflow": 0.0, "breakthroughs": 0, "failed_breakthroughs": 0,
         "equipped_artifacts": None, "injured_until": None}
    p["qi"] = float(rules.qi_needed(realm, layer))
    return p


def realm_gate(realm):
    return at_gate(realm, rules.max_layer(realm))


def test_every_realm_has_odds():
    for realm in rules.REALM_ORDER[1:]:
        assert realm in training.PHASE_BOTTLENECK_SUCCESS
        assert realm in training.REALM_BREAKTHROUGH_SUCCESS


def test_realm_gates_get_harder_the_higher_you_climb():
    chances = [rules.breakthrough_chance(realm_gate(r)) for r in rules.REALM_ORDER[:-1]]
    assert chances[0] == 1.0                                   # Mortal → Martial Apprentice always works
    assert all(a > b for a, b in zip(chances, chances[1:]))
    assert chances[1] == pytest.approx(training.REALM_BREAKTHROUGH_SUCCESS["Martial Warrior"])
    assert chances[-1] == pytest.approx(training.REALM_BREAKTHROUGH_SUCCESS["Martial Saint"])


def test_phase_gates_get_harder_the_higher_you_climb():
    chances = [rules.breakthrough_chance(at_gate(r, 3)) for r in rules.REALM_ORDER[1:]]
    assert all(a > b for a, b in zip(chances, chances[1:]))
    assert rules.breakthrough_chance(at_gate("Martial King", 6)) == training.PHASE_BOTTLENECK_SUCCESS["Martial King"]


def test_pills_add_but_never_past_the_cap():
    low, high = realm_gate("Martial Apprentice"), realm_gate("Martial Ancestor")    # into Warrior, into Saint
    assert rules.breakthrough_chance(low, 0.60) == training.BREAKTHROUGH_CHANCE_CAP
    assert rules.breakthrough_chance(high, 0.15) == pytest.approx(training.REALM_BREAKTHROUGH_SUCCESS["Martial Saint"] + 0.15)
    assert rules.breakthrough_chance(at_gate("Martial King", 3), 0.15) == training.PHASE_BOTTLENECK_SUCCESS["Martial King"]
    assert rules.pill_helps(high) and not rules.pill_helps(realm_gate("Mortal"))
    assert not rules.pill_helps(at_gate("Martial King", 3))


def test_the_attempt_uses_the_realm_odds():
    p = realm_gate("Martial Emperor")                        # 3% into Martial Ancestor (no extra requirement)
    ok, _ = rules.attempt_breakthrough(p, rng=SimpleNamespace(random=lambda: 0.05))
    assert ok is False
    p = realm_gate("Martial Emperor")
    ok, _ = rules.attempt_breakthrough(p, rng=SimpleNamespace(random=lambda: 0.05), bonus=0.05)
    assert ok is True and p["realm"] == "Martial Ancestor"
