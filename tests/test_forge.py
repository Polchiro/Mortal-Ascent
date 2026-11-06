"""Forging data (docs/forge.md, forge.py): slots, passives, materials, recipes, drops, rarity caps, EXP, costs."""
import random
from collections import Counter

import pytest

import alchemy
import equipments
import forge


def test_slots_and_rarity_caps_by_tier():
    assert [forge.PASSIVE_SLOTS[t]["slots"] for t in forge.TIERS] == [1, 1, 1, 2, 2]
    assert [forge.PASSIVE_SLOTS[t]["max_rarity"] for t in forge.TIERS] == \
        ["Rare", "Epic", "Epic", "Legendary", "Mythical"]
    assert set(forge.PASSIVE_SLOTS) == set(equipments.TIERS)


def test_passive_counts_match_the_design():
    counts = {g: Counter(p["rarity"] for p in ps.values()) for g, ps in forge.PASSIVES.items()}
    assert [counts["weapon"][r] for r in forge.RARITIES] == [5, 5, 5, 4, 3, 3]
    assert [counts["armor"][r] for r in forge.RARITIES] == [5, 5, 5, 4, 3, 3]
    assert [counts["artifact"][r] for r in forge.RARITIES] == [4, 4, 4, 3, 3, 2]


def test_every_passive_family_belongs_to_its_gear():
    for gear, passives in forge.PASSIVES.items():
        for key, p in passives.items():
            assert p["rarity"] in forge.RARITIES, key
            assert gear in forge.FAMILIES[p["family"]]["gear"], key
            assert p["text"] and p["fx"], key


def test_passive_names_are_unique():
    names = [p["name"] for ps in forge.PASSIVES.values() for p in ps.values()]
    assert len(names) == len(set(names))


def test_seventy_material_types():
    mats = forge.all_materials()
    assert len(mats) == 70
    kinds = Counter(m["kind"] for m in mats.values())
    assert kinds == {"base": 15, "binding": 5, "essence": 39, "fuel": 5, "liquid": 5, "seal": 1}
    assert len(forge.FAMILIES) == 13
    assert forge.FAMILIES["shadow"]["gear"] == ["weapon", "armor"]      # shared Shadow essence


def test_essence_families_drop_from_matching_beast_elements():
    import beasts
    elements = {f["element"] for f in forge.FAMILIES.values() if f["element"]}
    assert elements == set(beasts.ELEMENTS)                            # every beast element drops an essence


def test_recipe_costs():
    assert [forge.RECIPE[t]["base"] for t in forge.TIERS] == [3, 4, 5, 6, 8]
    assert [forge.RECIPE[t]["binding"] for t in forge.TIERS] == [2, 2, 3, 3, 4]
    assert [forge.REROLL_COINS[t] for t in forge.TIERS] == [500, 2_000, 8_000, 30_000, 100_000]
    assert forge.forge_coins("replace", "divine") == 200_000
    assert forge.forge_coins("reroll", "spirit") == 8_000
    assert forge.REPLACE_TIERS == ["treasure", "divine"] and forge.REPLACE_SEAL_STONES == 1


def test_drop_rates_from_the_design():
    assert forge.ORE_VEIN == {"metal": (2, 4), "fuel_chance": 0.30, "metal_shard_chance": 0.10}
    assert forge.BEAST_DROPS["normal"]["essence"] == {"shard": 0.08}
    assert forge.BEAST_DROPS["elite"]["essence"] == {"crystal": 0.05}
    assert forge.BEAST_DROPS["beast_king"]["essence"] == {"heart": 0.02, "crystal": 0.20}
    for tier, odds in forge.CHEST_FORTUNE.items():
        assert sum(odds.values()) < 1
    assert 0 < forge.SEAL_STONE_PEARLS


def test_material_tier_follows_realm_like_cores():
    assert forge.tier_for_realm("Mortal") == 1
    assert forge.tier_for_realm("Martial Warrior") == 2
    assert forge.tier_for_realm("Martial Saint") == 5


@pytest.mark.parametrize("score,rarity", [
    (49, None), (50, "Common"), (64, "Common"), (65, "Uncommon"), (75, "Rare"), (84, "Rare"),
    (85, "Epic"), (92, "Epic"), (93, "Legendary"), (97, "Legendary"), (98, "Mythical"), (100, "Mythical")])
def test_score_to_rarity(score, rarity):
    assert forge.rarity_for_score(score) == rarity


def test_weak_inscription_holds_back_top_rarities():
    assert forge.rarity_for_score(100, inscribe=18) == "Legendary"
    assert forge.rarity_for_score(100, inscribe=10) == "Rare"
    assert forge.rarity_for_score(80, inscribe=0) == "Rare"            # Rare and below need no inscription


def test_rarity_capped_by_gear_tier_and_essence_grade():
    assert forge.capped_rarity("Mythical", "ordinary") == "Rare"
    assert forge.capped_rarity("Mythical", "spirit") == "Epic"
    assert forge.capped_rarity("Mythical", "treasure") == "Legendary"
    assert forge.capped_rarity("Mythical", "divine") == "Mythical"
    assert forge.capped_rarity("Mythical", "divine", "shard") == "Uncommon"
    assert forge.capped_rarity("Mythical", "divine", "crystal") == "Epic"
    assert forge.capped_rarity("Common", "divine", "heart") == "Common"
    assert forge.capped_rarity(None, "divine") is None


def test_pick_never_beats_the_caps():
    rng = random.Random(1)
    for gear in forge.GEAR_KINDS:
        for tier in forge.TIERS:
            for _ in range(30):
                key = forge.pick_passive(gear, tier, "Mythical", rng=rng)
                got = forge.RARITIES.index(forge.PASSIVES[gear][key]["rarity"])
                assert got <= forge.RARITIES.index(forge.PASSIVE_SLOTS[tier]["max_rarity"])


def test_essence_picks_only_its_family():
    rng = random.Random(2)
    for _ in range(50):
        key = forge.pick_passive("weapon", "divine", "Mythical", essence=("thunder", "heart"), rng=rng)
        assert forge.PASSIVES["weapon"][key]["family"] == "thunder"
        key = forge.pick_passive("armor", "divine", "Legendary", essence=("shadow", "crystal"), rng=rng)
        assert forge.PASSIVES["armor"][key]["family"] == "shadow"
        assert forge.PASSIVES["armor"][key]["rarity"] in ("Common", "Uncommon", "Rare", "Epic")


def test_essence_falls_to_the_best_rarity_below_never_above():
    # Flame has no Rare/Epic weapon passive: an Epic result gives an Uncommon Flame passive
    key = forge.pick_passive("weapon", "divine", "Epic", essence=("flame", "heart"), rng=random.Random(3))
    assert forge.PASSIVES["weapon"][key]["rarity"] == "Uncommon"
    # Blood has nothing at Uncommon or below on weapons
    assert forge.pick_passive("weapon", "divine", "Mythical", essence=("blood", "shard")) is None
    assert not forge.usable_essence("weapon", "divine", "blood", "shard")
    assert forge.usable_essence("weapon", "divine", "blood", "crystal")
    assert not forge.usable_essence("armor", "divine", "metal", "heart")      # Metal is weapons only


def test_no_duplicate_passives():
    owned = forge.candidates("weapon", "Common")[:-1]       # the character has 4 of the 5 Commons
    for seed in range(20):
        key = forge.pick_passive("weapon", "ordinary", "Common", exclude=owned, rng=random.Random(seed))
        assert key not in owned
    everything = set(forge.PASSIVES["armor"])
    assert forge.pick_passive("armor", "divine", "Mythical", exclude=everything) is None


def test_blacksmith_rank_uses_the_alchemist_curve():
    assert forge.BLACKSMITH_RANK_EXP == alchemy.ALCHEMIST_RANK_EXP
    assert [forge.RANK_NEEDED[t] for t in forge.TIERS] == [1, 2, 4, 6, 8]
    assert forge.RANK_RELIEF["seconds_bonus"] == 0.5 and forge.RANK_RELIEF["zone_degrees"] == 2


def test_forge_exp_more_on_success():
    fail = forge.forge_exp("spirit", None)
    common = forge.forge_exp("spirit", "Common")
    epic = forge.forge_exp("spirit", "Epic")
    assert 0 < fail < common < epic
    assert forge.forge_exp("spirit", "Common", ranks_above=3) < common


def test_difficulty_gets_harder_each_tier():
    d = [forge.DIFFICULTY[t] for t in forge.TIERS]
    assert [x["name"] for x in d] == ["Normal", "Hard", "Very Hard", "Extreme", "Super Hard"]
    for a, b in zip(d, d[1:]):
        assert b["seconds"] <= a["seconds"] and b["zone"] < a["zone"] and b["quench_window"] < a["quench_window"]
        assert b["misleading"] >= a["misleading"] and b["strikes"] > a["strikes"]
    assert forge.STAGE_MAX_POINTS * len(forge.STAGES) == 100
    assert set(forge.HEAT_TARGET.values()) <= set(forge.HEAT_COLORS)


def test_failed_forge_loses_materials_by_rule():
    assert forge.FAIL_LOSES_ALL_MATERIALS
    assert forge.FAIL_BELOW == 50
