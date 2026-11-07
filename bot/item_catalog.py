"""
Every item in the game, as a list the admin /admin item command can search and give.

Nothing here is a hand-written item list: weapons and armor come from equipments.py, artifacts from
equipments.ARTIFACT_FAMILIES, forging materials from forge.all_materials(), herbs, pills and Beast Cores
from alchemy.py, manuals from technique.py and chests from loot.py. Add an item to those modules and it
shows up here by itself.

Each entry has an id (the value Discord's autocomplete sends back), a label (what the admin sees and
types) and a kind. make(entry_id, qty, ...) turns an entry into bag items ready for loot.store.
"""
import random

import alchemy
import equipments
import forge
import technique

from . import crafting, loot, materials

# Weapon and armor quality: where the stats sit in their range (0 = worst, 1 = best).
QUALITY_POS = {"cracked": 0.10, "normal": 0.50, "fine": 0.85, "flawless": 1.0}
DEFAULT_PATTERNS = 5        # crafted pills with no pattern count picked (Qi pills then come as the shop pill)
GEAR_KINDS = ("weapon", "armor")
MAX_GEAR = 25               # gear does not stack: one bag item each
KIND_LABEL = {"weapon": "Weapon", "armor": "Armor", "artifact": "Artifact", "material": "Material",
              "core": "Beast Core", "herb": "Herb", "pill": "Pill", "manual": "Manual", "chest": "Chest"}


def _tier(t):
    return t.title()


def build():
    """{id: {"label", "kind", "name"}} for every item, grouped by kind."""
    out = {}

    def add(id_, kind, name, extra=""):
        label = f"{KIND_LABEL[kind]} · {name}" + (f" ({extra})" if extra else "")
        out[id_] = {"label": label[:100], "kind": kind, "name": name}

    for tier in equipments.TIERS:
        for w in equipments.WEAPON_TYPES:
            add(f"weapon:{tier}:{w}", "weapon", equipments.WEAPON_NAMES[tier][w], f"{_tier(tier)} {w}")
    for tier in equipments.TIERS:
        for a in equipments.ARMOR_TYPES:
            add(f"armor:{tier}:{a}", "armor", equipments.ARMOR_NAMES[tier][a], f"{_tier(tier)} {a}")
    for fam in equipments.ARTIFACT_FAMILIES:
        for tier in equipments.TIERS:
            add(f"artifact:{tier}:{fam}", "artifact", equipments.artifact_name(fam, tier), _tier(tier))
    for key, m in materials.MATERIALS.items():
        extra = f"{m['gear']} tier {m['tier']}" if m["kind"] == "base" else \
            f"{m['kind']} tier {m['tier']}" if "tier" in m else m["kind"]
        add(f"material:{key}", "material", m["name"], extra)
    for core, name in loot.CORE_NAMES.items():
        for grade in alchemy.GRADES:
            add(f"core:{core}:{grade}", "core", f"{grade} {name}")
    for tier in alchemy.GRADES:
        for type_, (name, _desc) in alchemy.HERBS[tier].items():
            add(f"herb:{tier}:{type_}", "herb", name, f"{tier} {loot.TYPE_LABEL.get(type_, type_)}")
    for kind, (label, _emoji, table, _recipe) in crafting.KINDS.items():
        for grade in table:
            add(f"pill:{kind}:{grade}", "pill", crafting.pill_name(kind, grade), f"{grade} {label}")
    add("pill:heaven_defying", "pill", loot.HEAVEN_DEFYING["name"], loot.HEAVEN_DEFYING["grade"])
    for key, t in technique.TECHNIQUES.items():
        add(f"manual:{key}", "manual", f"{t['name']} Manual", t["grade"])
    for tier in loot.CHEST_ORDER:
        add(f"chest:{tier}", "chest", loot.CHEST_NAMES[tier])
    return out


CATALOG = build()


def search(text, limit=25, kind=None, prefix=None):
    """[(id, label)] whose label holds every typed word, best first (names that start with the text).
    kind / prefix limit it to one kind of item or ids that start with prefix. With nothing typed and no
    kind, a few of every kind are shown (Discord shows at most 25, which would otherwise all be weapons)."""
    words = (text or "").lower().split()
    hits = [(i, e["label"]) for i, e in CATALOG.items() if all(w in e["label"].lower() for w in words)
            and (kind is None or e["kind"] == kind) and (prefix is None or i.startswith(prefix))]
    if not words and kind is None and prefix is None:
        per_kind = {}
        for h in hits:
            per_kind.setdefault(CATALOG[h[0]]["kind"], []).append(h)
        hits = [h for group in zip(*[g[:3] for g in per_kind.values()]) for h in group]
    said = " ".join(words)
    hits.sort(key=lambda h: not CATALOG[h[0]]["name"].lower().startswith(said))   # stable: keeps catalog order
    return hits[:limit]


def resolve(text):
    """The catalog id for what was typed or picked: an id, a label, or a unique item name / search.
    Returns (id, None), or (None, a message saying why not)."""
    text = (text or "").strip()
    if text in CATALOG:
        return text, None
    low = text.lower()
    for field in ("label", "name"):
        same = [i for i, e in CATALOG.items() if e[field].lower() == low]
        if len(same) == 1:
            return same[0], None
    hits = search(text, limit=1000)
    if len(hits) == 1:
        return hits[0][0], None
    if not hits:
        return None, f"No item matches **{text}**. Start typing and pick from the list."
    shown = "\n".join(f"• {label}" for _, label in hits[:10])
    more = f"\n…and {len(hits) - 10} more" if len(hits) > 10 else ""
    return None, f"**{text}** matches {len(hits)} items. Pick one:\n{shown}{more}"


def make(entry_id, qty=1, quality=None, age=None, patterns=None, rng=random):
    """Bag items for `qty` of this entry. Gear does not stack, so it is one item per copy.
    quality: cracked/normal/fine/flawless for weapons and armor (None = random, like a drop).
    age: herb age (None = 10 years). patterns: 1–9 for crafted pills (None = the shop Qi pill, or
    DEFAULT_PATTERNS for other pills)."""
    kind, _, rest = entry_id.partition(":")
    if kind in GEAR_KINDS:
        tier, type_ = rest.split(":")
        maker = loot.weapon if kind == "weapon" else loot.armor
        return [maker(type_, tier, QUALITY_POS[quality] if quality else rng.random()) for _ in range(qty)]
    if kind == "artifact":
        tier, fam = rest.split(":")
        return [loot.artifact(fam, tier) for _ in range(qty)]
    if kind == "material":
        return [materials.material(rest, qty)]
    if kind == "core":
        core, grade = rest.split(":")
        item = {"category": "materials", "key": f"core:{core}:{grade}", "name": loot.CORE_NAMES[core],
                "grade": grade, "data": {"core": core, "grade": grade}}
    elif kind == "herb":
        tier, type_ = rest.split(":")
        item = loot.herb(tier, type_, age or 10)
    elif kind == "pill":
        if rest == "heaven_defying":
            item = dict(loot.HEAVEN_DEFYING)
        else:
            pkind, grade = rest.split(":")
            if pkind == "qi" and not patterns:
                item = loot.pill(grade)
            else:
                item = crafting.crafted_pill(pkind, grade, patterns or DEFAULT_PATTERNS)
    elif kind == "manual":
        item = loot.manual(rest)
    elif kind == "chest":
        item = loot.chest(rest)
    else:
        raise KeyError(entry_id)
    return [dict(item, qty=qty)]


# ── one pick list per kind (/admin give_armor, give_herb, ...) ───────

def material_groups():
    """[(value, label)] for the material type pick list: the base materials, bindings, fuels, liquids,
    the Seal Stone and one entry per essence family (each holds a few materials, so all fit in a list)."""
    out, seen = [], set()
    for key, m in materials.MATERIALS.items():
        if m["kind"] == "base":
            value, label = f"base:{m['gear']}:", f"{m['gear'].title()} base material"
        elif m["kind"] == "essence":
            fam = m["family"]
            value, label = f"essence:{fam}:", f"{forge.FAMILIES[fam]['name']} essence"
        elif m["kind"] == "seal":
            value, label = "seal", m["name"]
        else:
            value, label = f"{m['kind']}:", {"binding": "Binding", "fuel": "Fuel",
                                             "liquid": "Quench liquid"}.get(m["kind"], m["kind"].title())
        if value not in seen:
            seen.add(value)
            out.append((value, label))
    return out


def herb_types():
    """[(type, label)], e.g. ('qi', 'Qi herb (Spirit Grass, ...)')."""
    first = alchemy.GRADES[0]
    return [(t, f"{loot.TYPE_LABEL.get(t, t.title())} herb ({name}, ...)") for t, (name, _) in alchemy.HERBS[first].items()]


def pill_kinds():
    """[(kind, label)] for the pill pick list, plus the Heaven-Defying Pill."""
    return [(k, v[0]) for k, v in crafting.KINDS.items()] + [("heaven_defying", loot.HEAVEN_DEFYING["name"])]


def artifact_families():
    """[(family, label)], e.g. ('fang', 'Fang: Extra damage when your Strike beats a Break')."""
    return [(f, f"{f.title()}: {v['text']}"[:100]) for f, v in equipments.ARTIFACT_FAMILIES.items()]
