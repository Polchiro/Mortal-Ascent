# Onboarding — /start, Tutorial and /profile

## /start

A short story opening, then the talent roll:

> 🏮 *You arrive at the gates of the Jianghu. An old master looks you over...*
> *"Place your hand on the Aptitude Stone."*
> ⏳ *The stone begins to glow...*
> ✨ **Genius Talent!** *"Hmm... not bad, young one."*

The player starts with:
- **Realm:** Mortal, 1st Layer
- **Techniques:** Iron Fist (attack) + Horse Stance Guard (defense)
- **50 Lotus Coins**
- The tutorial begins automatically

One character per Discord account. Talent rules: see talent.md.

## Tutorial — "The Old Master's Lessons"

A guided path through the Mortal realm. The Old Master gives one lesson at a time.

- **No cooldowns during the tutorial**, so new players are never stuck waiting
- Each lesson must be done to unlock the next
- Players can type **/tutorial** anytime to see their current lesson

| # | Lesson | What the player does | Reward |
|---|---|---|---|
| 1 | Know Yourself | Use **/profile** | 20 Lotus Coins |
| 2 | First Training | Use **/train** and finish a challenge (Mortal → 2nd Layer) | 20 Lotus Coins |
| 3 | Sharpen Your Fist | Use **/practice** on Iron Fist | 20 Lotus Coins |
| 4 | Breathe | Open **/internal qi** to see Qi gathering on its own (no collecting needed) | 1 Mortal Qi Pill |
| 5 | Into the Wild | Use **/explore** — the first expedition always meets a Wild Boar | — |
| 6 | First Battle | Defeat the Wild Boar. The Old Master explains Strike / Guard / Break and techniques during the fight | — |
| 7 | Spoils | Open the guaranteed Common Chest from the boar | Chest contents |
| 8 | The First Gate | Reach Mortal 3rd Layer and **break through** to Martial Apprentice (guaranteed success) | 100 Lotus Coins |

After lesson 8:
> *"You have taken your first step on the martial path. The rest, you must walk alone."*

Normal cooldowns and odds apply from then on.

## /profile

/profile shows a generated **image card** in an ink-wash scroll style
(rendered by profile_card.py), with buttons below it.

### Card layout

**Left side**
- Realm name in Chinese calligraphy down the edge (e.g. 武王 for Martial King)
- Avatar on a soft ink wash, inside a **jade Qi ring** with tick marks —
  the ring fills as the current layer's Qi bar fills, with a marker at the current point
- "% to next layer" under the ring
- Name, talent badge (coloured by rank), server rank
- Red 武 seal in the bottom corner

**Right side**
- Realm name in large letters with a red brush stroke underneath
- Phase and layer, plus **layer pips**: 10 dots on a path (the Peak dot is bigger)
- Plum blossom branch and faint red sun in the top-right corner
- Internal Qi (current / needed) and Qi Rate with its multiplier
- Four stat tablets with icons: ❤ HP, ⚔ Attack, 🛡 Defense, 🪷 Lotus Coins
- Equipped techniques: grade seal, name, grade and type, mastery stage with 5 diamonds
- Weapon: tier seal, name with quality prefix, stat buffs
- Footer: beasts slain, breakthroughs, failed breakthroughs, and any status
  (active pill, Seclusion, Injured, Blessed Land)

Big numbers are shortened: 18,240 → 18.24K, 83,370,000,000,000 → 83.37T.

### Seals

| Item | Characters |
|---|---|
| Technique grade | 凡 Mortal · 黄 Yellow · 玄 Mystic · 地 Earth · 天 Heaven |
| Weapon tier | 凡 Ordinary · 精 Refined · 灵 Spirit · 宝 Treasure · 神 Divine |
| Realm (calligraphy) | 凡人 · 武徒 · 武者 · 武师 · 武宗 · 大武宗 · 武尊 · 武王 · 武帝 · 武祖 · 武圣 |

### Colours

| Item | Colours |
|---|---|
| Talent | Ordinary grey · Gifted green · Genius blue · Prodigy purple · Heavenly gold · Saint orange · Divine red |
| Technique grade | Mortal grey · Yellow gold · Mystic blue · Earth brown · Heaven red |
| Weapon tier | Ordinary grey · Refined green · Spirit blue · Treasure purple · Divine orange |

### Buttons

| Button | Shows |
|---|---|
| Techniques | All learned techniques, mastery EXP, equipped slots |
| Inventory | Manuals, weapons, pills, herbs, materials |
| Stats | Beasts slain, duels won, Beast Kings defeated, breakthroughs |

## /inventory

Shows an **image card** of the player's bag in the same ink-wash style
(rendered by inventory_card.py). Also opened by the Inventory button on /profile.

### Card layout
- 行囊 ("traveller's bag") in calligraphy down the left edge, with a red 藏 seal
- Title: **"<NAME>'S BAG"** with a red brush stroke
- **Category tabs** with item counts: Manuals · Weapons · Pills · Herbs · Materials · Chests
  (the open tab is underlined in red)
- **Item grid:** 4 × 3 tiles per page. Each tile shows:
  - A seal with the grade or tier character, in its colour
    (凡 黄 玄 地 天 for manuals and pills, 凡 精 灵 宝 神 for weapons,
    木 铜 银 玉 for chests, 草 for herbs and materials; herbs show their age, e.g. 50-year)
  - Item name
  - One line of detail (e.g. "Attack · Pierce 25%", "+13% ATK · +9% HP", "×1.7 Qi · 4h")
  - Quantity badge (×2) when holding more than one
  - Status: LEARNED (manuals) or EQUIPPED (weapons, with a coloured border)
- Footer: page number, item count, and bag space used (turns red when nearly full)

### Buttons and menus (under the card)

| Control | Does |
|---|---|
| Category menu | Switch tab (Manuals, Weapons, Pills, Herbs, Materials, Chests) |
| ◀ Prev / Next ▶ | Change page |
| Item menu | Pick an item on this page to use it: learn a manual, equip a weapon, take a pill, open a chest |

- Bag size starts at 60 slots; more can be bought in the Moon Pearl shop
- A duplicate of a learned manual can be turned into insight (mastery EXP)
