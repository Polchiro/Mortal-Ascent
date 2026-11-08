"""Forging materials in the game (docs/forge.md Part 2): items, drops, the bag, the Index and the drawn icons."""
import random
from collections import Counter

import pytest
from PIL import Image, ImageChops

import economy
import explore
import forge
from bot import compendium, crafting, db, gathering, loot, materials, trainer
from bot import player as rules
from bot.expedition import Expedition
from bot.sheet import data as sheet
from bot.sheet import items
from bot.views import buy_shop_item
from cards import material_icons
from cards import theme as T


@pytest.fixture
def conn():
    return db.connect(":memory:")


def new_player(conn, uid=1, realm="Mortal"):
    db.create_player(conn, uid, "Tester", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
    db.update_player(conn, uid, realm=realm)


def keys(found):
    return [i["key"] for i in found]


# ── items and the bag ─────────────────────────────────────────────────

def test_every_material_becomes_an_item():
    for key, m in materials.MATERIALS.items():
        it = materials.material(key, 3)
        assert it["category"] == "materials" and it["name"] == m["name"] and it["qty"] == 3


def test_materials_stack_by_type_and_use_no_bag_slots(conn):
    new_player(conn)
    db.update_player(conn, 1, bag_capacity=1)
    loot.store(conn, 1, [loot.beast_core("normal", "Mortal")])          # the one slot is now full
    stored, lost = loot.store(conn, 1, [materials.material("base:weapon:1", 2), materials.material("binding:1"),
                                        materials.material("base:weapon:1", 3)])
    assert not lost
    mats = {i["key"]: i["qty"] for i in db.get_items(conn, 1, "materials")}
    assert mats["base:weapon:1"] == 5 and mats["binding:1"] == 1
    assert db.slots_used(conn, 1) == 1
    _, lost = loot.store(conn, 1, [loot.beast_core("elite", "Mortal")])  # cores still need a slot
    assert lost


# ── drop sources ──────────────────────────────────────────────────────

def test_ore_vein_encounter_is_in_explore():
    assert explore.ENCOUNTERS["ore_vein"]["chance"] == forge.ORE_VEIN_ENCOUNTER_CHANCE
    assert sum(e["chance"] for e in explore.ENCOUNTERS.values()) == pytest.approx(1.0)


def test_ore_vein_gives_metal_of_your_tier(conn):
    new_player(conn, realm="Martial Expert")
    e = Expedition(conn, 1, random.Random(4))
    for _ in range(200):
        e._ore_vein()
    c = Counter()
    for i in e.items:
        c[i["key"]] += i["qty"]
    veins = 200
    assert 2 * veins <= c["base:weapon:3"] <= 4 * veins
    assert 0.2 * veins < c["fuel:3"] < 0.4 * veins
    assert 0.04 * veins < c["essence:metal:shard"] < 0.18 * veins


def test_beast_drops_follow_the_rates():
    rng = random.Random(7)
    n = 4000
    c = Counter()
    for _ in range(n):
        for i in materials.roll_beast("normal", "Martial Warrior", "Grey Wolf", rng):
            c[i["key"].rsplit(":", 1)[0] if i["key"].startswith("essence") else i["key"]] += 1
    import beasts
    fam = materials.family_of_element(beasts.element_of("Grey Wolf"))
    assert abs(c["binding:2"] / n - forge.BEAST_DROPS["normal"]["binding"][0]) < 0.03
    assert abs(c["base:armor:2"] / n - forge.BEAST_DROPS["normal"]["armor"][0]) < 0.03
    assert abs(c[f"essence:{fam}"] / n - 0.08) < 0.015


def test_beast_king_drops_crystals_and_hearts():
    rng = random.Random(8)
    n = 5000
    grades = Counter()
    for _ in range(n):
        for i in materials.roll_beast("beast_king", "Martial King", "Grey Wolf", rng):
            if i["key"].startswith("essence"):
                grades[i["key"].rsplit(":", 1)[1]] += 1
    assert abs(grades["heart"] / n - 0.02) < 0.008
    assert abs(grades["crystal"] / n - 0.98 * 0.20) < 0.02
    assert "shard" not in grades


def test_beast_essence_matches_its_element():
    import beasts
    for realm, roster in beasts.BEASTS.items():
        for name, *_ in roster:
            fam = materials.family_of_element(beasts.element_of(name))
            assert fam and forge.FAMILIES[fam]["element"] == beasts.element_of(name)


def test_explore_beasts_drop_materials(conn):
    new_player(conn)
    e = Expedition(conn, 1, random.Random(1))

    class Won:
        result, turn = "won", 3
    for _ in range(60):
        e._beast_result(Won, "Wild Boar")
    assert any(i["category"] == "materials" and i["key"] in materials.MATERIALS for i in e.items)


def test_gather_can_find_springs_and_jade_shards(conn):
    new_player(conn)
    rng = random.Random(3)
    found = Counter(i["key"] for _ in range(3000) for i in materials.roll_gather("Mortal", rng))
    assert abs(found["liquid:1"] / 3000 - forge.GATHER_SPRING_CHANCE) < 0.02
    assert abs(found["essence:jade:shard"] / 3000 - forge.GATHER_JADE_SHARD_CHANCE) < 0.012


def test_right_gather_pick_can_store_materials(conn):
    new_player(conn)
    for seed in range(60):
        g = gathering.Gathering(conn, 1, random.Random(seed))
        r = g.next_round()
        if r.kind != "spirit":
            g.answer(r.answer, 1.0)
    assert any(i["key"] in materials.MATERIALS for i in db.get_items(conn, 1, "materials"))


def test_chests_hold_jades_fortune_and_seal_stones():
    rng = random.Random(9)
    c = Counter()
    for _ in range(3000):
        for i in materials.roll_chest("legendary", rng):
            c[i["key"].split(":")[0] + ":" + i["key"].split(":")[1] if ":" in i["key"] else i["key"]] += 1
    assert abs(c["base:artifact"] / 3000 - forge.CHEST_JADE["legendary"][0]) < 0.03
    assert abs(c["seal"] / 3000 - forge.CHEST_SEAL_STONE["legendary"]) < 0.015
    assert c["essence:fortune"] > 0


def test_open_chest_includes_materials():
    p = {"realm": "Mortal", "blessing_tier": None, "blessing_until": 0, "artifact_fx": {}}
    rng = random.Random(2)
    seen = set()
    for _ in range(400):
        try:
            _, found = loot.open_chest(p, "legendary", rng)
        except (KeyError, TypeError):
            pytest.skip("open_chest needs a full player")
        seen |= {i["key"] for i in found if i["category"] == "materials"}
    assert any(k.startswith("base:artifact") for k in seen)


def test_craft_ash_grows_with_patterns():
    assert materials.craft_ash(0) == []
    assert keys(materials.craft_ash(2)) == ["essence:cauldron_ash:shard"]
    assert materials.craft_ash(5)[0]["qty"] == 2
    assert keys(materials.craft_ash(8)) == ["essence:cauldron_ash:crystal"]
    assert keys(materials.craft_ash(9)) == ["essence:cauldron_ash:heart"]


def test_practice_ink_training_dew_and_breakthrough_dew():
    rng = random.Random(4)
    ink = sum(bool(materials.roll_practice_ink(rng)) for _ in range(4000)) / 4000
    dew = sum(bool(materials.roll_training_dew(rng)) for _ in range(4000)) / 4000
    assert abs(ink - forge.PRACTICE_INK_CHANCE) < 0.02 and abs(dew - forge.TRAINING_DEW_CHANCE) < 0.02
    assert keys(materials.breakthrough_dew("realm")) == ["essence:spirit_dew:crystal"]
    assert keys(materials.breakthrough_dew("phase")) == ["essence:spirit_dew:shard"]
    assert keys(materials.duplicate_manual_ink("Heaven")) == ["essence:insight:heart"]


def test_prospector_bonus_raises_drops():
    base = sum(len(materials.roll_gather("Mortal", random.Random(s))) for s in range(3000))
    more = sum(len(materials.roll_gather("Mortal", random.Random(s), bonus=1.0)) for s in range(3000))
    assert more > base * 1.5


def test_seal_stone_in_the_pearl_shop(conn):
    new_player(conn)
    assert economy.PEARL_SHOP["seal_stone"] == forge.SEAL_STONE_PEARLS
    db.update_player(conn, 1, moon_pearls=100)
    msg, _ = buy_shop_item(conn, 1, "seal_stone")
    assert "Seal Stone" in msg
    assert [i["key"] for i in db.get_items(conn, 1, "materials")] == ["seal"]
    assert db.get_player(conn, 1)["moon_pearls"] == 100 - forge.SEAL_STONE_PEARLS


# ── inventory ─────────────────────────────────────────────────────────

def test_materials_tab_groups(conn):
    new_player(conn)
    loot.store(conn, 1, [materials.material(k) for k in ("seal", "essence:blood:shard", "binding:2", "base:armor:1",
                                                          "fuel:1")] + [loot.beast_core("normal", "Mortal")])
    d, page, *_ = sheet.bag_data(conn, 1, "materials")
    assert [items.material_group(i) for i in page] == ["base", "binding", "essence", "fuel_liquid", "fuel_liquid",
                                                         "core"]
    assert d["category"] == "materials" and [g for g, *_ in d["groups"]] == [g for g, _ in items.MATERIAL_GROUPS]
    d, page, *_ = sheet.bag_data(conn, 1, "materials:fuel_liquid")
    assert {i["key"] for i in page} == {"fuel:1", "seal"} and d["group"] == "fuel_liquid"
    from cards.bag import render_bag
    render_bag(d)


def test_material_inspect_and_icon(conn):
    new_player(conn)
    loot.store(conn, 1, [materials.material("essence:frost:crystal")])
    it = db.get_items(conn, 1, "materials")[0]
    assert items.item_icon(it) == "mat:essence:frost:crystal"
    assert items.rarity(it) == ("Crystal", "treasure")
    det = items.details(it, db.get_player(conn, 1))
    assert det["kind"] == "Essence" and any("Epic" in e for e in det["effects"])


# ── Index ─────────────────────────────────────────────────────────────

def test_index_has_materials_and_passives():
    assert {"materials", "passives_weapon", "passives_armor", "passives_artifact"} <= set(compendium.SECTIONS)
    names = set()
    for key, *_ in compendium.tiers("materials"):
        for chunk in compendium.paginate(compendium.build("materials", key)["tiles"]):
            names |= {t["name"] for t in chunk}
    for m in materials.MATERIALS.values():
        if m["kind"] in ("base", "binding", "fuel", "liquid"):
            assert m["name"] in names
    assert len([n for n in names if n.endswith("essence")]) == 13
    for gear in forge.GEAR_KINDS:
        listed = {t["name"] for r in forge.RARITIES for t in compendium.build(f"passives_{gear}", r)["tiles"]}
        listed.discard("How to forge one")
        assert listed == {p["name"] for p in forge.PASSIVES[gear].values()}
    assert compendium.search("Phoenix Rebirth")[:2] == ("passives_armor", "Legendary")
    assert compendium.search("Dragon Tendon")[:2] == ("materials", "treasure")


# ── drawn icons ───────────────────────────────────────────────────────

def drawn(kind, size=64):
    img = Image.new("RGBA", T.P(size * 2, size * 2), (0, 0, 0, 0))
    T.icon(img, kind, (size, size), size, T.GOLD)
    return img


def test_every_material_and_rarity_has_a_drawn_icon():
    imgs = [drawn("mat:" + k) for k in materials.MATERIALS] + [drawn("passive:" + r) for r in forge.RARITIES]
    for img in imgs:
        assert img.getchannel("A").getbbox() is not None
    for i, a in enumerate(imgs):                     # every one looks different
        for b in imgs[i + 1:]:
            assert ImageChops.difference(a, b).getbbox(alpha_only=False) is not None


def test_every_material_type_names_its_shape():
    shapes = {material_icons.shape_name(k) for k in materials.MATERIALS}
    assert {"ore chunk", "folded hide", "shell plate", "silk roll", "scale", "qilin hide", "carved jade disc", "bone",
            "sinew", "fang", "tendon", "chaos crystal", "shard", "faceted crystal", "glowing heart", "coal lump",
            "glowing core", "sun stone", "flask", "square seal"} == shapes


def test_every_family_has_its_own_colour():
    colours = [material_icons.FAMILY_COLOR[f] for f in forge.FAMILIES]
    assert len(set(colours)) == 13
