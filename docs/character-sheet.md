# Character Sheet — /profile, /techniques, /equipment, /inventory, /balance

One message with five tabs. Each command opens it on its own tab, and buttons under the
card switch tabs in place, so players never have to type another command.

| Tab | Command | Shows |
|---|---|---|
| 👤 Profile | /profile | The avatar in a moon-gate ring (beads = the realm's layers), name, @username, talent, HP and Internal Qi bars, realm emblem with phase and layer, attributes with their buff %, the meridian figure (its dantian fills with Qi) with the four gear slots around it, equipped techniques with mastery arcs, the Deeds rail (beasts, herbs, breakthroughs, duels from /duel, server rank) and, for the owner, the purse |
| 📜 Techniques | /techniques | Attack, Defense and Flex stances (equipped, empty, or locked with what opens it), then every learned technique as a scroll: grade seal, power, passive, rest turns, effect and mastery. Equipped scrolls carry a ribbon; the rest say Ready to equip |
| ⚔️ Equipment | /equipment | Four display cases (weapon, armor, artifact I and II): tier seal, name, realm needed, buffs or effect, forged passive sockets; base → final stats with the bonus on each bar and its sources; the worn artifacts' effects; spare gear in the bag |
| 🎒 Inventory | /inventory | A category rail with counts, Materials groups, a 4 × 3 item grid with page beads, and an Inspect panel that also shows the buttons the item offers |
| 🪷 Purse | /balance | Lotus Coins and Moon Pearls only (short and exact amounts); the blessing is shown by /blessing |

## Look

Night Ink theme (cards/ink.py, on top of cards/theme.py): indigo ink backgrounds, gold frames with cut
corners, cloud curls (祥云) and diamond gems, Cinzel headings and icons drawn in code. Each card adds its
own accent so they feel related but distinct:

| Card | Accent | Identity |
|---|---|---|
| Profile | Indigo | Moon gate, meridian figure, Deeds rail |
| Techniques | Violet | Scripture pavilion: stances and unrolled scrolls with vermilion grade seals (凡 黄 玄 地 天) |
| Equipment | Steel | Armory: display cases on lit pedestals with tier seals (凡 精 灵 宝 神) |
| Inventory | Jade | Collection: category rail, rarity-glow tiles, Inspect panel |
| Purse | Gold | Treasury: a square-holed Lotus coin and a pearl on a crescent moon |
| /internal qi | Sea teal | Spirit Sea (灵海): the dantian vortex in a bagua ring, a meridian stream bar, jade tablets and the Flow of Qi |

- **Buttons:** the tabs, item actions and paging use octagon seal icons (cards/sheet_icons.py), uploaded
  as application emojis like the fight buttons; the open tab is the blurple button
- **Rarity colours** are shared by technique grades, weapon / armor / artifact tiers and chest tiers
- The ledger is still written for every coin change (economy.md) but the Purse card no longer lists it, and the
  Heavenly Blessing is shown by /blessing rather than the Purse

### Activity result cards

When a /spar, /train, /practice or /explore ends, its last message becomes a card in the same frame
(cards/activity.py), each with its own accent colour (`theme.ACCENTS`) so players can tell them apart:

| Activity | Accent | Shows |
| --- | --- | --- |
| /spar | Steel blue | Victory / Defeat / Forfeit, both HP bars, mastery EXP per technique, the last exchange and notes |
| /train, /practice | Jade green | Score ring, Qi gained with the layer bar (or mastery EXP with the mastery bar), events and conditions |
| /explore | Amber | Returned or failed, steps reached, HP, Lotus Coins, beasts slain, item tiles (and items left behind), the last step |

Every step before the end is still the normal embed with buttons. If a card fails to render, the
text embed is sent instead.

## What each part shows (and what it does not)

| Part | Shows | Not shown, because the docs don't define it |
|---|---|---|
| Progress | Realm, phase, layer (pips = layers in the realm: 3 for Mortal, 10 after) | A numeric level |
| Attributes | HP, Attack, Defense: base, final, % buffs (stats.md) | Strength, Vitality, Intelligence, Dexterity |
| Internal Qi | Qi / layer capacity, Qi Rate, Qi waiting to be banked, time to a full bar, next gate (training.md) | Qi as a fight resource: it is never spent in fights |
| HP | Max HP, and an injury timer in the status line | Current HP: fights start at full HP; losing gives an injury instead |
| Techniques | Sockets: 1 attack + 1 defense, Flex from Martial Warrior (technique.md) | More slots |
| Equipment | One weapon, one armor and two artifact slots (equipment.md) | Accessories, more artifact slots at high realms |
| Bag | Chests, Manuals, Weapons, Armor, Artifacts (tiles show their drawn icon in the tier colour; manuals show the technique icon with a small grade emblem, pills their type emblem tinted by grade with pattern rings), Pills, Herbs (by kind and age), Materials | Elixirs, rare treasures |
| Title | — | Character titles |

## Item actions

| Item | Actions |
|---|---|
| Chest | Open, Discard |
| Manual | Learn (or reread for mastery EXP if already learned), Discard |
| Weapon, armor, artifact | Equip / Unequip, Discard (only when not equipped). Artifacts fill the first free slot; with both full, or with one of the same family worn, Equip says why and nothing changes |
| Qi pill, Heaven-Defying Pill | Take, Discard |
| Herb | Discard (herbs have no use until alchemy exists) |

- **Inspect** shows name, icon, quantity, rarity, description, effects and notes (equipped, learned,
  realm needed)
- **Discard** asks for a confirm, and offers "×1" or "all" for stacks. No refund
- Techniques and weapons can't be swapped while exploring or sparring (technique.md: swaps happen
  outside of fights)

## Privacy

- Only the owner can press the sheet's buttons
- `/profile @member` shows that player's Profile card only, with their purse hidden and no buttons.
  Their bag, techniques tab, equipment tab and purse stay private

## Safety rules

- Every action re-reads the item or technique from the database under the bot's lock before it
  changes anything, and one click is handled at a time, so a stale card or a double click can't
  use, equip or discard twice
- Currency changes go through one function (bot/db.py `change_currency`) that refuses to go below 0
  and records each change in the ledger (see economy.md)

## Adding things later

| To add | Change |
|---|---|
| Cultivation attributes | Add a `"cultivation"` entry to `PATHS` in bot/sheet/attributes.py and pick it in `path_for()` |
| A new resource (e.g. Spirit Qi) | Add a function next to `qi_resource()` in bot/sheet/attributes.py and a panel in cards/profile.py |
| A new currency | Add its column to `CURRENCY_COLUMNS` in bot/db.py and a style in `CURRENCY_STYLE` (bot/sheet/data.py) |
| A new bag category | One entry in `CATEGORIES` and its details in `details()` (bot/sheet/items.py) |
| More gear slots | `worn()` / `gear_sockets()` / `equipment_data()` in bot/sheet/data.py, slots in cards/profile.py `armory` and cases in cards/equipment.py |
| Profile themes (shop) | Another set of renderers next to cards/; the ink-wash cards at the repo root are the first one |

## Files

| File | Job |
|---|---|
| bot/sheet/view.py | The tabbed Discord view and every button and menu |
| bot/sheet/data.py | Builds each card's data from the database |
| bot/sheet/attributes.py | Attributes and resources (the expandable part) |
| bot/sheet/items.py | Bag categories, Inspect details, allowed actions, discard |
| cards/theme.py | Shared drawing: background, frames, panels, bars, sockets, medallions, orb, portrait, icons |
| cards/ink.py | Night Ink palette, tab strip, plaques, ornate bars, gems, chips, ribbons, page beads |
| cards/profile.py, techniques.py, equipment.py, bag.py, purse.py | One card per tab |
| cards/dantian.py | The /internal qi card |
| cards/sheet_icons.py | Sheet button icons (application emojis) |
| scripts/render_sheet.py | Saves every card for a made-up player into previews/ |
| cards/activity.py, bot/result_cards.py | /spar, /train and /explore result cards and their data |
| scripts/render_results.py | Saves every result card with made-up data into previews/ |

## Icons and emblems

Cards draw pictures, not seal characters (Pillow only, no image files):

- **Techniques** (`cards/technique_icons.py`, `theme.icon(img, "tech:<key>")`): each of the 30 techniques has its own icon,
  its school's base shape (Fist, Palm, Finger, Leg, Body) plus a motif from its name, in its grade colour. Empty technique
  sockets show a faint outline of a school shape.
- **Emblems** (`cards/emblems.py`, `emblem(img, kind, key, center, size)` or `theme.icon(img, "emblem:<kind>:<key>")`):
  manual grades (scrolls and tablets), gear rarities (forged crests), realms (each realm's signature beast), beast tiers,
  elements and pill types. Each step looks more precious than the one before. Fine details are drawn only when large.
- **Other icons** (`cards/misc_icons.py`, `theme.icon(img, "misc:<name>")`): the /internal qi sources (realm emblem,
  talent crystal, technique, blessing cloud, Qi pill, blessed land, seclusion cave, toxicity flask), herb types, /craft stages
  and /craft buttons. Talents have their own emblem set (`emblem:talent:<name>`).
- Chinese characters stay only as decoration (the 万物录 title, scroll titles, realm calligraphy behind the portrait).
