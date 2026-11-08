"""Armor and artifacts (docs/equipment.md): chest drops, equipping rules, the bag and /index, stats,
every artifact effect, and the Profile / Equipment cards. Every number is read from equipments.py."""
import random

import pytest

import alchemy
import beasts
import equipments as eq
import explore
import pvp
import training
from bot import combat, compendium, db, fight, gear, loot
from bot import duel as D
from bot import player as rules
from bot.crafting import Craft
from bot.expedition import encounter_odds
from bot.sheet import data as sheet
from bot.sheet import items
from bot.sparring import Spar
from cards import RENDERERS


class Always(random.Random):
    """Every chance succeeds, damage rolls are exactly 1.0, choices take the first option."""

    def random(self):
        return 0.0

    def uniform(self, a, b):
        return 1.0


class Never(Always):
    """Every chance fails."""

    def random(self):
        return 0.999999


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, realm="Mortal", layer=1, name="Shoaib"):
    db.create_player(conn, uid, name, "Ordinary", 0, rules.starting_techniques())
    db.update_player(conn, uid, realm=realm, layer=layer)
    return db.get_player(conn, uid)


def give(conn, uid, item):
    assert db.add_item(conn, uid, **item)
    return db.get_items(conn, uid, item["category"])[-1]


def fx_player(effect=None, value=None, uid=1, name="Ana", realm="Mortal", layer=1):
    p = {"user_id": uid, "name": name, "realm": realm, "layer": layer, "talent": "Ordinary"}
    p["artifact_fx"] = {effect: value} if effect else {}
    return p


def value(family, tier):
    return eq.artifact_value(family, tier)


# ── drops ─────────────────────────────────────────────────────────────

def test_chests_roll_armor_and_artifacts_separately_from_weapons():
    p = {"realm": "Mortal"}
    for tier in eq.CHEST_WEAPON_CHANCE:
        _, found = loot.open_chest(p, tier, Always())
        cats = [i["category"] for i in found]
        assert cats.count("weapons") == cats.count("armor") == cats.count("artifacts") == 1
        _, found = loot.open_chest(p, tier, Never())
        assert not [i for i in found if i["category"] in ("weapons", "armor", "artifacts")]


def test_drop_rates_follow_the_tables():
    rng = random.Random(7)
    n = 40000
    counts = {"armor": 0, "artifacts": 0, "weapons": 0}
    for _ in range(n):
        for i in loot.open_chest({"realm": "Mortal"}, "legendary", rng)[1]:
            if i["category"] in counts:
                counts[i["category"]] += 1
    assert counts["armor"] / n == pytest.approx(eq.CHEST_ARMOR_CHANCE["legendary"], abs=0.01)
    assert counts["artifacts"] / n == pytest.approx(eq.CHEST_ARTIFACT_CHANCE["legendary"], abs=0.008)
    assert counts["weapons"] / n == pytest.approx(eq.CHEST_WEAPON_CHANCE["legendary"], abs=0.01)


def test_armor_rolls_buffs_and_a_quality_prefix_like_weapons():
    rng = random.Random(3)
    for _ in range(300):
        tier = rng.choice(eq.TIERS)
        a = loot.roll_armor(tier, rng)
        assert a["category"] == "armor" and a["grade"] == tier and a["key"] in eq.ARMOR_TYPES
        base = eq.ARMOR_NAMES[tier][a["key"]]
        assert a["name"].endswith(base)
        prefix = a["name"][: -len(base)].strip()
        assert prefix in {name for _, name in eq.QUALITY_PREFIXES}
        for stat, v in a["data"]["buffs"].items():
            lo, hi = eq.ARMOR_BUFFS[a["key"]][tier][stat]
            assert lo - 1e-9 <= v <= hi + 1e-9


def test_artifacts_have_their_own_name_and_a_fixed_value():
    for fam, spec in eq.ARTIFACT_FAMILIES.items():
        for i, tier in enumerate(eq.TIERS):
            a = loot.artifact(fam, tier)
            assert a["name"] == spec["names"][i] and a["grade"] == tier
            assert gear.artifact_value(a) == spec["values"][i]


def test_artifact_tiers_follow_their_own_odds():
    rng = Always()          # random() == 0: an artifact always drops, and pick() takes the first tier listed
    for chest, odds in eq.CHEST_ARTIFACT_TIER_ODDS.items():
        art = [i for i in loot.open_chest({"realm": "Mortal"}, chest, rng)[1] if i["category"] == "artifacts"][0]
        assert art["grade"] in odds
    assert "treasure" not in eq.CHEST_ARTIFACT_TIER_ODDS["rare"]      # Treasure / Divine only from Jade


def test_divine_armor_and_artifacts_are_announced():
    assert "Divine armor" in loot.announcement("Ana", loot.roll_armor("divine", random.Random(1)))
    assert "Divine artifact" in loot.announcement("Ana", loot.artifact("lotus", "divine"))
    assert loot.announcement("Ana", loot.artifact("lotus", "treasure")) is None
    assert loot.announcement("Ana", loot.roll_armor("treasure", random.Random(1))) is None


# ── equipping ─────────────────────────────────────────────────────────

def test_armor_needs_the_realm_of_its_tier(conn):
    new_player(conn)
    a = give(conn, 1, loot.roll_armor("refined", random.Random(1)))
    msg = loot.use_item(conn, 1, a["id"])
    assert eq.TIER_REALM_REQUIREMENT["refined"] in msg and db.equipped_armor(conn, 1) is None
    db.update_player(conn, 1, realm=eq.TIER_REALM_REQUIREMENT["refined"])
    loot.use_item(conn, 1, a["id"])
    assert db.equipped_armor(conn, 1)["id"] == a["id"]


def test_one_armor_slot(conn):
    new_player(conn)
    a = give(conn, 1, loot.roll_armor("ordinary", random.Random(1)))
    b = give(conn, 1, loot.roll_armor("ordinary", random.Random(2)))
    loot.use_item(conn, 1, a["id"])
    loot.use_item(conn, 1, b["id"])
    assert [i["id"] for i in db.get_items(conn, 1, "armor") if i["equipped"]] == [b["id"]]


def test_two_artifact_slots_from_the_start(conn):
    new_player(conn)
    a = give(conn, 1, loot.artifact("fang", "ordinary"))
    b = give(conn, 1, loot.artifact("qi", "ordinary"))
    c = give(conn, 1, loot.artifact("lotus", "ordinary"))
    assert "slot 1" in loot.use_item(conn, 1, a["id"])
    assert "slot 2" in loot.use_item(conn, 1, b["id"])
    assert "full" in loot.use_item(conn, 1, c["id"])
    assert [x["id"] for x in db.equipped_artifacts(conn, 1)] == [a["id"], b["id"]]
    db.unequip_item(conn, 1, a["id"])
    assert "slot 1" in loot.use_item(conn, 1, c["id"])
    assert len(db.equipped_artifacts(conn, 1)) == eq.ARTIFACT_SLOTS


def test_two_artifacts_of_one_family_are_blocked(conn):
    new_player(conn, realm="Martial Apprentice")
    a = give(conn, 1, loot.artifact("mirror", "ordinary"))
    b = give(conn, 1, loot.artifact("mirror", "refined"))
    loot.use_item(conn, 1, a["id"])
    msg = loot.use_item(conn, 1, b["id"])
    assert "same family" in msg
    assert [x["id"] for x in db.equipped_artifacts(conn, 1)] == [a["id"]]


def test_artifacts_need_the_realm_of_their_tier(conn):
    new_player(conn)
    a = give(conn, 1, loot.artifact("qi", "spirit"))
    assert eq.TIER_REALM_REQUIREMENT["spirit"] in loot.use_item(conn, 1, a["id"])
    assert db.equipped_artifacts(conn, 1) == []


def test_worn_gear_cant_be_discarded(conn):
    new_player(conn)
    a = give(conn, 1, loot.artifact("qi", "ordinary"))
    loot.use_item(conn, 1, a["id"])
    ok, _ = items.discard(conn, 1, a["id"])
    assert not ok
    assert items.actions(db.get_item(conn, 1, a["id"])) == ["unequip"]


def test_get_player_carries_the_worn_artifacts_effects(conn):
    new_player(conn)
    assert db.get_player(conn, 1)["artifact_fx"] == {}
    a = give(conn, 1, loot.artifact("qi", "ordinary"))
    loot.use_item(conn, 1, a["id"])
    assert db.get_player(conn, 1)["artifact_fx"] == {"qi_rate": value("qi", "ordinary")}


# ── bag and /index ────────────────────────────────────────────────────

def test_bag_has_armor_and_artifact_tabs_with_drawn_icons(conn):
    new_player(conn)
    give(conn, 1, loot.roll_armor("ordinary", random.Random(1)))
    give(conn, 1, loot.artifact("lotus", "ordinary"))
    assert {"armor", "artifacts"} <= set(items.CATEGORIES)
    d, *_ = sheet.bag_data(conn, 1, "artifacts")
    assert d["tiles"][0]["icon"] == "gear:lotus"
    assert d["tiles"][0]["rarity_key"] == "ordinary"
    assert d["inspect"]["effects"][0] == gear.effect_text(loot.artifact("lotus", "ordinary"))
    d, *_ = sheet.bag_data(conn, 1, "armor")
    assert d["tiles"][0]["icon"][5:] in eq.ARMOR_TYPE_DISPLAY
    assert items.CATEGORIES["armor"].icon == "gear:robe" and items.CATEGORIES["artifacts"].icon == "pearl"
    for cat in ("armor", "artifacts"):
        RENDERERS["inventory"](sheet.bag_data(conn, 1, cat)[0])


def test_index_lists_every_armor_and_artifact():
    text = "\n".join(f"{t['name']}\n" + "\n".join(t["lines"])
                     for key in ("armor", "artifacts")
                     for tier in [compendium.OVERVIEW] + [t[0] for t in compendium.tiers(key)]
                     for n in range(compendium.tier_page(key, tier)["pages"])
                     for t in compendium.tier_page(key, tier, n)["tiles"])
    for names in eq.ARMOR_NAMES.values():
        for name in names.values():
            assert name in text
    for spec in eq.ARTIFACT_FAMILIES.values():
        for name in spec["names"]:
            assert name in text


# ── stats ─────────────────────────────────────────────────────────────

def test_armor_buffs_add_to_the_stat_totals():
    p = {"realm": "Mortal", "layer": 1}
    hp, atk, dfn = rules.base_stats("Mortal", 1)
    weapon = {"name": "Blade", "data": {"buffs": {"defense": 0.10}}}
    armor = {"name": "Plate", "data": {"buffs": {"defense": 0.20, "hp": 0.10}}}
    assert rules.final_stats(p, (), weapon, armor) == (round(hp * 1.10), round(atk), round(dfn * 1.30))
    sources = rules.stat_buffs((), weapon, armor)["defense"]
    assert ("Plate", 0.20) in sources and ("Blade", 0.10) in sources


def test_fair_duels_count_armor_at_half():
    p = {"realm": "Mortal", "layer": 1}
    hp, _, dfn = rules.base_stats("Mortal", 1)
    armor = {"name": "Plate", "data": {"buffs": {"defense": 0.20}}}
    _, _, fair = D.fair_stats(p, (), None, "Mortal", 1, armor)
    assert fair == round(dfn * (1 + 0.20 * pvp.BUFF_SHARE))


# ── combat artifacts in fights ────────────────────────────────────────

def battle(effect=None, val=None, rng=None, beast=("Wild Boar", "normal", "brute")):
    p = fx_player(effect, val)
    hp, atk, dfn = rules.base_stats("Mortal", 1)
    techs = [{"id": 1, "name": "Iron Fist", "type": "attack", "grade": "Mortal", "mastery_exp": 0, "stage": 0},
             {"id": 2, "name": "Horse Stance Guard", "type": "defense", "grade": "Mortal", "mastery_exp": 0, "stage": 0}]
    f = fight.Fighter(p, techs, hp, hp, atk, dfn)
    enemy = fight.enemy_from_beast(combat.beast_stats(p, beast), beast[0])
    enemy["dodge"] = 0
    enemy["hp"] = enemy["max_hp"] = 10 ** 6       # never knocked out, so the 30% cap stays out of the way
    return fight.Battle([f], enemy, rng or Never())


def force(b, move, kind="normal"):
    b.enemy["statuses"].clear()
    b.intent = {"move": move, "kind": kind, "target": b.fighters[0], "name": "Test Move"}


def enemy_loss(b, mine, theirs, kind="normal"):
    force(b, theirs, kind)
    start = b.enemy["hp"]
    b.choose(b.fighters[0].uid, mine)
    b.resolve()
    return start - b.enemy["hp"]


def test_fang_strike_beats_break_harder():
    v = value("fang", "divine")
    plain = enemy_loss(battle(rng=Never()), "strike", "break")
    fang = enemy_loss(battle("strike_vs_break_damage", v, Never()), "strike", "break")
    assert fang == pytest.approx(plain * (1 + v), rel=1e-6)


def test_bell_softens_charged_attacks():
    v = value("bell", "divine")
    for b in (plain := battle(rng=Never()), bell := battle("charged_damage_reduction", v, Never())):
        force(b, "strike", "charged")
        b.choose(1, "strike")
        b.resolve()
    lost_plain = plain.fighters[0].max_hp - plain.fighters[0].hp
    lost_bell = bell.fighters[0].max_hp - bell.fighters[0].hp
    assert lost_bell == pytest.approx(lost_plain * (1 - v), abs=1)


def test_mirror_reflects_guarded_damage():
    v = value("mirror", "divine")
    assert enemy_loss(battle(rng=Never()), "guard", "strike") == 0
    b = battle("guard_reflect", v, Never())
    hit = combat.damage(b.enemy["attack"], b.fighters[0].defense, b.fighters[0].max_hp, rng=Always())
    assert enemy_loss(b, "guard", "strike") == pytest.approx(hit * v, rel=1e-6)


def test_thunder_break_can_stagger():
    b = battle("break_stagger_chance", value("thunder", "divine"), Always())
    force(b, "break")                      # Break vs Break clash: no guard shattered
    b.choose(1, "break")
    b.resolve()
    assert "staggered" in b.enemy["statuses"]
    b = battle("break_stagger_chance", value("thunder", "divine"), Never())
    force(b, "break")
    b.choose(1, "break")
    b.resolve()
    assert "staggered" not in b.enemy["statuses"]


def test_lotus_heals_every_turn():
    v = value("lotus", "divine")
    b = battle("heal_per_turn", v, Never())
    f = b.fighters[0]
    f.hp = f.max_hp // 2
    force(b, "guard")
    b.choose(1, "guard")
    b.resolve()
    assert f.hp == f.max_hp // 2 + round(f.max_hp * v)


def test_feather_dodges_a_hit():
    b = battle("dodge_chance", value("feather", "divine"), Always())
    force(b, "strike")
    b.choose(1, "break")                   # Strike beats Break: the hit would land
    b.resolve()
    assert b.fighters[0].hp == b.fighters[0].max_hp
    b = battle(rng=Always())
    force(b, "strike")
    b.choose(1, "break")
    b.resolve()
    assert b.fighters[0].hp < b.fighters[0].max_hp


def test_focus_can_reset_a_cooldown():
    b = battle("cooldown_reset_chance", value("focus", "divine"), Always())
    force(b, "guard")
    b.choose(1, "attack_tech")
    b.resolve()
    assert b.fighters[0].cooldowns["attack_tech"] == 0
    b = battle(rng=Always())
    force(b, "guard")
    b.choose(1, "attack_tech")
    b.resolve()
    assert b.fighters[0].cooldowns["attack_tech"] > 0


def test_team_hunt_fighters_carry_their_artifacts(conn):
    from bot import hunt
    new_player(conn, 1)
    new_player(conn, 2, name="Bo")
    a = give(conn, 1, loot.artifact("lotus", "ordinary"))
    loot.use_item(conn, 1, a["id"])
    beast = next(b for b in beasts.BEASTS["Mortal"] if b[1] == "elite")
    lair = {"tier": "elite", "realm": "Mortal", "beast": beast}
    b = hunt.start_battle(conn, lair, [1, 2], random.Random(1))
    assert b.fighters[0].fx == {"heal_per_turn": value("lotus", "ordinary")}
    assert b.fighters[1].fx == {}


# ── combat artifacts in /spar and duels ───────────────────────────────

def spar(effect=None, val=None, rng=None):
    s = Spar(fx_player(effect, val), [], None, 1.0, rng or Never())
    s.m_hp = s.m_max = 10 ** 6
    return s


def test_spar_fang_mirror_and_lotus():
    v = value("fang", "divine")
    a, b = spar(rng=Never()), spar("strike_vs_break_damage", v, Never())
    for s in (a, b):
        s.master = "break"
        s.play("strike")
    assert (b.m_max - b.m_hp) == pytest.approx((a.m_max - a.m_hp) * (1 + v), rel=1e-6)

    s = spar("guard_reflect", value("mirror", "divine"), Never())
    s.master = "strike"
    s.play("guard")
    assert s.m_hp < s.m_max

    s = spar("heal_per_turn", value("lotus", "divine"), Never())
    s.hp = s.max_hp / 2
    s.master = "guard"
    s.play("guard")
    assert s.hp == pytest.approx(s.max_hp / 2 + s.max_hp * value("lotus", "divine"))


def test_spar_feather_thunder_and_focus():
    s = spar("dodge_chance", value("feather", "divine"), Always())
    s.master = "strike"
    s.play("break")                    # his Strike beats Break: it would hit
    assert s.hp == s.max_hp

    s = spar("break_stagger_chance", value("thunder", "divine"), Always())
    s.master = "guard"
    s.play("break")
    assert s.m_staggered

    s = Spar(fx_player("cooldown_reset_chance", value("focus", "divine")),
             [{"id": 1, "name": "Iron Fist", "type": "attack", "grade": "Mortal", "mastery_exp": 0, "stage": 0}],
             None, 1.0, Always())
    s.master = "guard"
    s.play("attack_tech")
    assert s.cooldowns["attack_tech"] == 0


def duel(fx1=None, fx2=None, rng=None):
    p1, p2 = fx_player(uid=1, name="Ana"), fx_player(uid=2, name="Bo")
    p1["artifact_fx"], p2["artifact_fx"] = fx1 or {}, fx2 or {}
    d = D.start(p1, [], None, p2, [], None, rng or Never())
    for side in d.sides:
        side.hp = side.max_hp = 10 ** 6
    return d


def test_duels_use_combat_artifacts_at_half_strength():
    v = value("fang", "divine")
    d = duel({"strike_vs_break_damage": v, "qi_rate": 0.5})
    assert d.sides[0].fx == {"strike_vs_break_damage": v * eq.DUEL_COMBAT_ARTIFACT_STRENGTH}


def test_duel_fang_and_mirror():
    v = value("fang", "divine")
    plain, fang = duel(rng=Never()), duel({"strike_vs_break_damage": v}, rng=Never())
    for d in (plain, fang):
        d.choose(1, "strike")
        d.choose(2, "break")
        d.resolve()
    lost = lambda d: d.sides[1].max_hp - d.sides[1].hp      # noqa: E731
    assert lost(fang) == pytest.approx(lost(plain) * (1 + v * eq.DUEL_COMBAT_ARTIFACT_STRENGTH), abs=1)

    d = duel(fx2={"guard_reflect": value("mirror", "divine")})
    d.choose(1, "strike")
    d.choose(2, "guard")
    d.resolve()
    assert d.sides[0].hp < d.sides[0].max_hp and d.sides[1].hp == d.sides[1].max_hp


def test_duel_lotus_feather_thunder_focus():
    d = duel({"heal_per_turn": value("lotus", "divine")})
    d.sides[0].hp = d.sides[0].max_hp // 2
    d.choose(1, "guard")
    d.choose(2, "guard")
    d.resolve()
    assert d.sides[0].hp > d.sides[0].max_hp // 2

    d = duel(fx2={"dodge_chance": value("feather", "divine")}, rng=Always())
    d.choose(1, "strike")
    d.choose(2, "break")
    d.resolve()
    assert d.sides[1].hp == d.sides[1].max_hp

    d = duel({"break_stagger_chance": value("thunder", "divine")}, rng=Always())
    d.choose(1, "break")
    d.choose(2, "break")
    d.resolve()
    assert d.sides[1].staggered

    p1, p2 = fx_player(uid=1, name="Ana"), fx_player(uid=2, name="Bo")
    p1["artifact_fx"] = {"cooldown_reset_chance": value("focus", "divine")}
    techs = [{"id": 1, "name": "Iron Fist", "type": "attack", "grade": "Mortal", "mastery_exp": 0, "stage": 0}]
    d = D.start(p1, techs, None, p2, [], None, Always())
    d.choose(1, "attack_tech")
    d.choose(2, "guard")
    d.resolve()
    assert d.sides[0].cooldowns["attack_tech"] == 0


# ── cultivation, crafting, exploration and wealth artifacts ───────────

def test_qi_artifact_adds_to_qi_rate():
    p = fx_player()
    p.update(realm="Mortal", talent="Ordinary")
    base_rate, base_mult = rules.qi_rate(p, now=0)
    p["artifact_fx"] = {"qi_rate": value("qi", "divine")}
    rate, mult = rules.qi_rate(p, now=0)
    assert mult == pytest.approx(base_mult + value("qi", "divine"))
    assert rate == pytest.approx(training.BASE_QI_RATE["Mortal"] * mult)


def test_purity_artifact_makes_toxicity_fade_faster():
    v = value("purity", "divine")
    hours = training.TOXICITY_DECAY_HOURS / (1 + v)
    p = {"toxicity": 5, "toxicity_at": 0, "artifact_fx": {"toxicity_decay_faster": v}}
    now = hours * 3600 * 2 + 1                 # two faded with the artifact, only one without it
    assert rules.current_toxicity(p, now=now) == 3
    assert rules.current_toxicity(dict(p, artifact_fx={}), now=now) == 4


def test_furnace_artifact_widens_the_heat_zone():
    deg = value("furnace", "divine")
    plain = Craft("qi", "Mortal", 1, 10, random.Random(1))
    hot = Craft("qi", "Mortal", 1, 10, random.Random(1), zone_bonus=deg)
    assert hot.zone_width == plain.zone_width + deg


def test_gourd_artifact_raises_old_herb_odds():
    v = value("gourd", "divine")
    plain, gourd = loot.age_odds(0), loot.age_odds(0, v)
    for age in alchemy.HERB_AGES:
        if age > 10:
            assert gourd[age] == pytest.approx(plain[age] * (1 + v))
    assert sum(gourd.values()) == pytest.approx(1.0)


def test_insight_artifact_raises_mastery_exp():
    p = {"artifact_fx": {"mastery_exp": value("insight", "divine")}}
    assert rules.mastery_bonus(p, now=0) == pytest.approx(1 + value("insight", "divine"))


def test_compass_artifact_helps_explore_luck():
    v = value("compass", "divine")
    plain, lucky = encounter_odds(1), encounter_odds(1, v)
    for k, spec in explore.ENCOUNTERS.items():
        if spec["rare"]:
            assert lucky[k] == pytest.approx(plain[k] * (1 + v))
    assert sum(lucky.values()) == pytest.approx(1.0)
    tiers = explore.BEAST_CHEST["elite"]["tiers"]
    odds = loot.chest_odds(tiers, v)
    low = min(tiers, key=loot.CHEST_ORDER.index)
    for t, w in tiers.items():
        assert odds[t] == pytest.approx(w if t == low else w * (1 + v))


def test_fortune_artifact_adds_lotus_coins_from_fights_and_chests():
    v = value("fortune", "divine")
    p = {"realm": "Mortal", "artifact_fx": {"lotus_coins": v}}
    assert loot.roll_coins(p, (100, 100), Always(), fortune=True) == round(100 * (1 + v))
    assert loot.roll_coins(p, (100, 100), Always()) == 100        # other coins (e.g. a stranger's thanks)
    coins, _ = loot.open_chest(p, "common", Never())
    lo, hi = loot.CHEST_COINS["common"]
    assert coins >= round(lo * (1 + v))


def test_hunter_artifact_raises_beast_core_chance():
    v = value("hunter", "divine")
    chance = alchemy.BEAST_CORE_DROP["normal"]

    class At(random.Random):
        def random(self):
            return chance * (1 + v / 2)       # just above the normal chance, below the boosted one

    assert loot.roll_beast_core("normal", "Mortal", At()) is None
    assert loot.roll_beast_core("normal", "Mortal", At(), bonus=v) is not None


# ── cards ─────────────────────────────────────────────────────────────

def test_profile_gear_row_has_four_sockets(conn):
    new_player(conn)
    d = sheet.profile_data(conn, 1)
    assert [s["slot"] for s in d["gear"]] == ["weapon", "armor", "artifact1", "artifact2"]
    assert d["gear"][1]["empty"] == "Armor drops from chests"
    a = give(conn, 1, loot.artifact("mirror", "ordinary"))
    loot.use_item(conn, 1, a["id"])
    d = sheet.profile_data(conn, 1)
    s = d["gear"][2]
    assert s["icon"] == "gear:mirror" and s["tier"] == "ordinary" and s["name"] == a["name"]
    assert s["line"] == gear.effect_text(a, tiny=True)
    RENDERERS["profile"](d)


def test_equipment_tab_shows_all_slots_armor_stats_and_artifact_effects(conn):
    new_player(conn, realm="Martial Apprentice")
    arm = give(conn, 1, loot.roll_armor("refined", random.Random(5)))
    loot.use_item(conn, 1, arm["id"])
    art = give(conn, 1, loot.artifact("qi", "refined"))
    loot.use_item(conn, 1, art["id"])
    d = sheet.equipment_data(conn, 1)
    assert d["armor"]["name"] == arm["name"]
    assert d["artifacts"][0]["name"] == art["name"] and d["artifacts"][1] is None
    names = {name for a in d["attributes"] for name, _ in a["sources"]}
    assert arm["name"] in names
    assert d["effects"][0]["effect"] == gear.effect_text(art)
    RENDERERS["equipment"](d)



# ── the sheet's Equipment tab buttons ─────────────────────────────────

def test_equipment_tab_menus_and_no_gear_swaps_in_a_fight(conn):
    import asyncio
    from types import SimpleNamespace

    from bot.sheet.view import CharacterSheet
    from test_exploits import FakeBot
    from test_sheet import fake_user

    new_player(conn)
    for item in (loot.roll_weapon("ordinary", random.Random(1)), loot.roll_armor("ordinary", random.Random(2)),
                 loot.artifact("fang", "ordinary"), loot.artifact("qi", "ordinary"), loot.artifact("fortune", "ordinary")):
        give(conn, 1, item)
    bot = FakeBot(conn)

    class Press:
        def __init__(self, value=None):
            self.data = {"values": [str(value)]}
            self.response = SimpleNamespace(defer=self._noop)

        async def _noop(self, **_):
            pass

        async def edit_original_response(self, **kw):
            pass

    async def go():
        view = CharacterSheet(bot, fake_user(), "equipment")
        await view.render()
        selects = [c.placeholder for c in view.children if hasattr(c, "placeholder")]
        assert selects == ["Equip a weapon...", "Equip armor...", "Equip an artifact..."]
        art = db.get_items(conn, 1, "artifacts")[0]
        bot.busy.add((1, "duel"))
        await view.on_equip_gear(Press(art["id"]))
        assert db.equipped_artifacts(conn, 1) == []                       # not during a fight
        bot.busy.clear()
        await view.on_equip_gear(Press(art["id"]))
        assert [a["id"] for a in db.equipped_artifacts(conn, 1)] == [art["id"]]
        await view.render()
        remove = [c for c in view.children if getattr(c, "row", None) == 4]
        assert [c.label for c in remove] == [f"Remove {art['name']}"]
        await view.unequip(Press(), art["id"])
        assert db.equipped_artifacts(conn, 1) == []
    asyncio.run(go())
