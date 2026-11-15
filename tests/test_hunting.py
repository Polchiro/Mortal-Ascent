"""Hunting parties and team hunts (docs/hunting.md): web/parties.py, web/hunt_play.py, hunting.py."""
import random

import pytest

import beasts
import hunting
from bot import db
from bot import player as rules
from web import hunt_play
from web.hunt_play import Hunts
from web.parties import PRESENCE_SECONDS, Parties


@pytest.fixture
def conn(tmp_path):
    c = db.connect(str(tmp_path / "h.db"))
    for uid, name, realm in ((1, "Lead", "Martial Apprentice"), (2, "Two", "Mortal"), (3, "Three", "Martial Apprentice"),
                             (4, "Four", "Martial Apprentice"), (5, "Five", "Martial Apprentice"), (9, "Saint", "Martial Saint")):
        db.create_player(c, uid, name, "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, uid, realm=realm, layer=5)
    yield c
    c.close()


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def world(conn):
    clock = Clock()
    parties = Parties(clock=clock)
    hunts = Hunts(parties, clock=clock, rng_factory=lambda: random.Random(11))
    return parties, hunts, clock


# ── locations ────────────────────────────────────────────────────────

def test_locations_use_the_existing_roster_only():
    names = {n for realm in beasts.BEASTS.values() for n, *_ in realm}
    seen = []
    for loc in hunting.LOCATIONS:
        for name, tier, role, home in hunting.pool(loc):
            assert name in names and (name, tier, role) in beasts.BEASTS[home]
            seen.append(name)
    assert sorted(seen) == sorted(names)                       # every beast lives somewhere, once
    covered = [r for loc in hunting.LOCATIONS for r in loc["realms"]]
    assert sorted(covered) == sorted(rules.REALM_ORDER) and len(covered) == len(set(covered))


def test_tier_odds_match_explore_rare_encounters():
    from bot.expedition import encounter_odds
    for step in range(1, 6):
        o, e = hunting.tier_odds(step), encounter_odds(step)
        assert o["elite"] == pytest.approx(e["elite_lair"]) and o["beast_king"] == pytest.approx(e["beast_king_den"])
        assert sum(o.values()) == pytest.approx(1)


def test_entry_needs_the_lowest_realm_and_higher_realms_go_anywhere(conn):
    forest, gorge = hunting.location("moon_forest"), hunting.location("crimson_gorge")
    assert hunting.eligible(db.get_player(conn, 2), forest) is None             # Mortal
    assert hunting.eligible(db.get_player(conn, 1), forest) is None             # Martial Apprentice
    assert "needs Martial Warrior or higher" in hunting.eligible(db.get_player(conn, 1), gorge)
    for loc in hunting.LOCATIONS:                                               # a Martial Saint goes anywhere
        assert hunting.eligible(db.get_player(conn, 9), loc) is None


# ── parties ──────────────────────────────────────────────────────────

def test_create_join_full_and_one_party_each(conn, world):
    parties, _, _ = world
    p, why = parties.create(conn, 1, "Moon Wolves", True)
    assert why is None and p.public and p.code is None and p in parties.public()
    assert parties.create(conn, 1, "Another", True)[1].startswith("You are already")
    for uid in (2, 3, 4):
        assert parties.join_public(conn, uid, p.id)[1] is None
    assert len(p.members) == 4 and p.full
    assert "full" in parties.join_public(conn, 5, p.id)[1]
    assert parties.join_public(conn, 2, p.id)[1] is None and len(p.members) == 4     # already in: no duplicate
    q, _ = parties.create(conn, 5, "Other", True)
    assert parties.join_public(conn, 5, p.id)[1]                                        # in another party
    assert parties.of(5) is q


@pytest.mark.parametrize("bad", ["", "ab", "x" * 25, "<script>"])
def test_party_names_are_checked(conn, world, bad):
    parties, _, _ = world
    assert parties.create(conn, 1, bad, True)[1]


def test_private_party_invitation_id(conn, world):
    parties, _, _ = world
    p, _ = parties.create(conn, 1, "Hidden Lotus", False)
    assert p.code and len(p.code) == 6 and p not in parties.public()
    assert parties.join_public(conn, 2, p.id)[1] == "That party is gone."           # not by its handle
    old = p.code
    assert parties.new_code(2) is not None                                           # only the leader
    assert parties.new_code(1) is None and p.code != old
    assert parties.join_code(conn, 2, old)[1].startswith("No party")                 # the old ID is dead
    assert parties.join_code(conn, 2, " " + p.code.lower() + " ")[1] is None         # forgiving about case and spaces


def test_wrong_invitation_ids_are_rate_limited(conn, world):
    parties, _, clock = world
    p, _ = parties.create(conn, 1, "Hidden Lotus", False)
    for _ in range(10):
        parties.join_code(conn, 2, "ZZZZZZ")
    assert "Too many" in parties.join_code(conn, 2, p.code)[1]
    clock.t += 601
    parties.seen(1)                                                                   # (the leader is still there)
    assert parties.join_code(conn, 2, p.code)[1] is None


def test_leader_rights_and_succession(conn, world):
    parties, _, _ = world
    p, _ = parties.create(conn, 1, "Moon Wolves", True)
    parties.join_public(conn, 2, p.id)
    parties.join_public(conn, 3, p.id)
    assert parties.kick(2, 3) == "Only the leader can remove members."
    assert parties.set_location(conn, 2, "moon_forest").startswith("Only the leader")
    assert parties.disband(2).startswith("Only the leader")
    assert parties.kick(1, 3) is None and parties.of(3) is None
    parties.leave(1)                                                                  # the leader goes: the oldest member leads
    assert p.leader == 2 and parties.of(1) is None
    assert parties.disband(2) is None and parties.of(2) is None and parties.get(p.id) is None


def test_location_needs_the_leaders_realm_and_blocks_low_joiners(conn, world):
    parties, _, _ = world
    p, _ = parties.create(conn, 1, "Wolves", True)
    assert "needs Martial Warrior or higher" in parties.set_location(conn, 1, "crimson_gorge")
    q, _ = parties.create(conn, 9, "Saints", True)
    assert parties.set_location(conn, 9, "moon_forest") is None                 # a Saint may lead a Moon Forest hunt
    assert parties.set_location(conn, 9, "celestial_forbidden_lands") is None
    assert "needs Martial Saint or higher" in parties.join_public(conn, 3, q.id)[1]


def test_a_saint_hunts_moon_forest_beasts_at_its_own_strength(conn, world):
    from bot import combat
    p, h = _party(conn, world, uids=(9, 1))
    b = h.battle
    assert b.enemy["name"] in {n for n, *_ in hunting.pool(hunting.location("moon_forest"))}
    assert b.enemy["realm"] == "Martial Saint"                                  # measured on the strongest member


def test_silent_members_leave_the_lobby(conn, world):
    parties, _, clock = world
    p, _ = parties.create(conn, 1, "Moon Wolves", True)
    parties.join_public(conn, 2, p.id)
    clock.t += PRESENCE_SECONDS - 5
    parties.seen(2)
    clock.t += 10
    parties.sweep()
    assert p.uids() == [2] and p.leader == 2                                          # the silent leader is out


def test_start_needs_place_readiness_and_rest(conn, world):
    parties, hunts, clock = world
    p, _ = parties.create(conn, 1, "Moon Wolves", True)
    parties.join_public(conn, 2, p.id)
    assert hunts.start(conn, 2) == "Only the leader can start the expedition."
    assert hunts.start(conn, 1) == "Choose where to hunt."
    parties.set_location(conn, 1, "moon_forest")
    assert hunts.start(conn, 1) == "Two is not ready."
    parties.set_ready(2, True)
    db.set_cooldown(conn, 2, "explore", 600, clock())
    assert hunts.start(conn, 1).startswith("Two: resting")
    db.set_cooldown(conn, 2, "explore", 0, clock())
    assert hunts.start(conn, 1) is None and p.hunting
    assert db.cooldown_left(conn, 1, "explore", clock()) > 0 and db.cooldown_left(conn, 2, "explore", clock()) > 0
    assert parties.join_public(conn, 3, p.id)[1].startswith("That party is already out")     # nobody joins halfway


# ── the hunt ─────────────────────────────────────────────────────────

def _party(conn, world, uids=(1, 3), loc="moon_forest"):
    parties, hunts, _ = world
    p, _ = parties.create(conn, uids[0], "Moon Wolves", True)
    parties.set_location(conn, uids[0], loc)
    for u in uids[1:]:
        parties.join_public(conn, u, p.id)
        parties.set_ready(u, True)
    assert hunts.start(conn, uids[0]) is None
    return p, hunts.get(p.id)


def _play_fight(conn, hunts, h, move="strike"):
    n = 0
    while h.battle is not None and n < 200:
        n += 1
        for f in h.battle.fighters:
            if f.active and f.pick is None:
                hunts.act(conn, f.uid, "move", "guard" if f.stunned else move, hunts.version(h, f.uid))


def test_team_fight_uses_the_location_pool_and_everyone_fights(conn, world):
    p, h = _party(conn, world)
    b = h.battle
    assert {f.uid for f in b.fighters} == {1, 3}
    assert b.enemy["name"] in {n for n, *_ in hunting.pool(hunting.location("moon_forest"))}
    assert h.loc["arena"] == "battle_bamboo_forest"


def test_one_move_each_and_the_turn_waits_for_all(conn, world):
    _, hunts, _ = world
    p, h = _party(conn, world)
    b = h.battle
    v1 = hunts.version(h, 1)
    hunts.act(conn, 1, "move", "guard", v1)
    assert b.turn == 1 and b.fighter(1).pick == "guard"
    hunts.act(conn, 1, "move", "strike", v1)                                          # a second press: ignored
    assert b.fighter(1).pick == "guard"
    hunts.act(conn, 1, "move", "strike", hunts.version(h, 1))                          # still waiting: ignored
    assert b.fighter(1).pick == "guard"
    hunts.act(conn, 3, "move", "guard", hunts.version(h, 3))
    assert b.turn == 2                                                                 # both picked: resolved


def test_a_silent_member_guards_when_the_team_turn_runs_out(conn, world):
    _, hunts, clock = world
    p, h = _party(conn, world)
    hunts.act(conn, 1, "move", "guard", hunts.version(h, 1))
    clock.t += hunt_play.TEAM_TURN_SECONDS + 5
    hunts.catch_up(conn, 1)
    assert h.battle.turn == 2 and h.battle.fighter(3).timeouts == 1


def test_each_member_rolls_their_own_normal_beast_rewards(conn, world, monkeypatch):
    monkeypatch.setattr(hunting, "tier_odds", lambda step, luck=0: {"normal": 1.0})
    _, hunts, _ = world
    p, h = _party(conn, world)
    for f in h.battle.fighters:                                                        # a quick, sure win
        f.attack *= 50
    _play_fight(conn, hunts, h)
    assert h.battle is None and h.ended is not None
    assert all(any("falls in" in line for line in h.lines[u]) for u in (1, 3))
    assert h.exps[1].coins > 0 and h.exps[3].coins > 0 and h.exps[1].beasts_slain == 1 == h.exps[3].beasts_slain
    coins0 = {u: db.get_player(conn, u)["lotus_coins"] for u in (1, 3)}
    hunts.act(conn, 3, "continue", "", hunts.version(h, 3))
    hunts.act(conn, 1, "continue", "", hunts.version(h, 1))
    hunts.act(conn, 3, "return", "", hunts.version(h, 3))                              # only the leader
    assert not h.over
    hunts.act(conn, 1, "return", "", hunts.version(h, 1))
    assert h.over and not p.hunting and set(h.results) == {1, 3}
    for u in (1, 3):
        assert db.get_player(conn, u)["lotus_coins"] > coins0[u]                       # banked on the walk home
        assert db.get_player(conn, u)["beasts_slain"] == 1


def test_elite_pays_like_a_lair_hunt(conn, world, monkeypatch):
    monkeypatch.setattr(hunting, "tier_odds", lambda step, luck=0: {"elite": 1.0})
    calls = []
    real = hunt_play.hunt._pay

    def spy(conn_, lair, rows, won, name, head, now=None, rng=random):
        calls.append((lair["tier"], won, [r["p"]["user_id"] for r in rows if not r["fled"]]))
        return real(conn_, lair, rows, won, name, head, now, rng)
    monkeypatch.setattr(hunt_play.hunt, "_pay", spy)
    _, hunts, _ = world
    p, h = _party(conn, world)
    assert h.battle.enemy["tier"] == "elite"
    for f in h.battle.fighters:
        f.attack *= 200
    _play_fight(conn, hunts, h)
    assert calls == [("elite", True, [1, 3])]
    assert db.get_player(conn, 1)["beasts_slain"] == 1


def test_a_fallen_member_goes_home_defeated_and_the_rest_hunt_on(conn, world, monkeypatch):
    monkeypatch.setattr(hunting, "tier_odds", lambda step, luck=0: {"normal": 1.0})
    parties, hunts, clock = world
    p, h = _party(conn, world)
    b = h.battle
    b.enemy["attack"] *= 1000                                                          # it kills whoever it hits ...
    b.fighter(1).hp = b.fighter(1).max_hp = 10 ** 12                                   # ... except the leader
    b.fighter(3).hp = 1
    n = 0
    while h.battle is not None and b.fighter(3).hp > 0 and n < 60:
        n += 1
        for f in b.fighters:
            if f.active and f.pick is None:
                hunts.act(conn, f.uid, "move", "strike" if f.uid == 3 and not f.stunned else "guard", hunts.version(h, f.uid))
    assert b.fighter(3).hp <= 0 and 3 in h.exps                                         # fallen: watches the fight end
    b.fighter(1).attack *= 1000
    _play_fight(conn, hunts, h)
    assert 3 not in h.exps and h.results[3]["defeated"]
    assert rules.injured_for(db.get_player(conn, 3), clock()) > 0
    assert parties.of(3) is p and 1 in h.exps                                           # still in the party; the leader hunts on


def test_members_can_leave_between_beasts_and_keep_their_loot(conn, world, monkeypatch):
    monkeypatch.setattr(hunting, "tier_odds", lambda step, luck=0: {"normal": 1.0})
    parties, hunts, _ = world
    p, h = _party(conn, world)
    for f in h.battle.fighters:
        f.attack *= 50
    _play_fight(conn, hunts, h)
    assert hunts.leave_party(conn, 3) is None
    assert parties.of(3) is None and 3 not in h.exps and db.get_player(conn, 3)["beasts_slain"] == 1
    hunts.act(conn, 1, "deeper", "", hunts.version(h, 1))
    assert h.step == 2 and [f.uid for f in h.battle.fighters] == [1]
    assert hunts.leave_party(conn, 1) == "Finish the fight first (or Flee)."


def test_idle_party_heads_home(conn, world, monkeypatch):
    monkeypatch.setattr(hunting, "tier_odds", lambda step, luck=0: {"normal": 1.0})
    _, hunts, clock = world
    p, h = _party(conn, world)
    for f in h.battle.fighters:
        f.attack *= 50
    _play_fight(conn, hunts, h)
    clock.t += hunt_play.IDLE_SECONDS + 1
    hunts.catch_up(conn, 1)
    assert h.over and not p.hunting


def test_solo_hunt_is_a_hidden_party_of_one(conn, world):
    parties, hunts, _ = world
    p, _ = parties.create(conn, 1, "", True, solo=True)
    assert p.solo and not p.public and p not in parties.public() and p.code is None
    assert parties.join_public(conn, 2, p.id)[1] == "That party is gone."
    parties.set_location(conn, 1, "moon_forest")
    assert hunts.start(conn, 1) is None
    assert len(hunts.get(p.id).battle.fighters) == 1
