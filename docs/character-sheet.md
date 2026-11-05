# Character Sheet — /profile, /techniques, /equipment, /inventory, /balance

One message with five tabs. Each command opens it on its own tab, and buttons under the
card switch tabs in place, so players never have to type another command.

| Tab | Command | Shows |
|---|---|---|
| 👤 Profile | /profile | Name, @username, talent, realm, phase, layer pips, attributes, Internal Qi, the portrait, equipped techniques, weapon, deeds (beasts slain, herbs gathered, breakthroughs, server rank), the dantian orb, purse |
| 📜 Techniques | /techniques | Attack, Defense and Flex sockets, then every learned technique |
| ⚔️ Equipment | /equipment | The weapon slot, base → final stats and where every buff comes from |
| 🎒 Inventory | /inventory | Category tabs, a 4 × 3 item grid with pages, and an Inspect panel |
| 🪷 Purse | /balance | Lotus Coins, Moon Pearls, Heavenly Blessing, recent transactions |

## Look

Crimson Hall theme (cards/theme.py): black stone and deep crimson backgrounds, bronze and gold
frames, Cinzel headings, a glowing tab strip across the top, and icons drawn in code.

- **Portrait:** the player's Discord avatar in an arched gold frame, over an aura in their talent's
  colour, with their realm's character behind it
- **Dantian orb:** a glass orb at the bottom of the Profile card that fills with red Qi as the layer
  bar fills
- **Rarity colours** are shared by technique grades, weapon tiers and chest tiers

## What each part shows (and what it does not)

| Part | Shows | Not shown, because the docs don't define it |
|---|---|---|
| Progress | Realm, phase, layer (pips = layers in the realm: 3 for Mortal, 10 after) | A numeric level |
| Attributes | HP, Attack, Defense: base, final, % buffs (stats.md) | Strength, Vitality, Intelligence, Dexterity |
| Internal Qi | Qi / layer capacity, Qi Rate, Qi waiting to be banked, time to a full bar, next gate (training.md) | Qi as a fight resource: it is never spent in fights |
| HP | Max HP, and an injury timer in the status line | Current HP: fights start at full HP; losing gives an injury instead |
| Techniques | Sockets: 1 attack + 1 defense, Flex from Martial Warrior (technique.md) | More slots |
| Equipment | One weapon slot (equipment.md) | Armor, artifacts, accessories |
| Bag | Chests, Manuals, Weapons, Pills, Herbs (by kind and age), Materials | Beast cores, elixirs, rare treasures |
| Title | — | Character titles |

## Item actions

| Item | Actions |
|---|---|
| Chest | Open, Discard |
| Manual | Learn (or reread for mastery EXP if already learned), Discard |
| Weapon | Equip / Unequip, Discard (only when not equipped) |
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
| Armor or artifact slots | Once designed in equipment.md: a slot list in bot/sheet/data.py `equipment_data()` and sockets in cards/equipment.py |
| Profile themes (shop) | Another set of renderers next to cards/; the ink-wash cards at the repo root are the first one |

## Files

| File | Job |
|---|---|
| bot/sheet/view.py | The tabbed Discord view and every button and menu |
| bot/sheet/data.py | Builds each card's data from the database |
| bot/sheet/attributes.py | Attributes and resources (the expandable part) |
| bot/sheet/items.py | Bag categories, Inspect details, allowed actions, discard |
| cards/theme.py | Shared drawing: background, frames, panels, bars, sockets, medallions, orb, portrait, icons |
| cards/profile.py, techniques.py, equipment.py, bag.py, purse.py | One card per tab |
| scripts/render_sheet.py | Saves every card for a made-up player into previews/ |
