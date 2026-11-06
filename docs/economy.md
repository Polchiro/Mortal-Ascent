# Economy — Currencies, /balance and /recharge

## Currencies

| Currency | Type | How to get | Tradeable |
|---|---|---|---|
| 🪷 **Lotus Coins** | Main money | Chests, beasts, quests, bounties, selling items | Yes |
| 🌙 **Moon Pearls** | Premium | /recharge (real money) or trading with other players | Yes |
| 📜 Contribution Points | Sect money (later) | Sect activities | No |
| 💎 Spirit Stones | Act 2 money (later) | Cultivation world | — |

Contribution Points and Spirit Stones stay hidden until they unlock.

## /balance

Opens the **Purse** tab of the Character Sheet (see character-sheet.md), drawn in the
crimson-and-gold style of the other sheet cards (cards/purse.py):

- Title: **"<NAME>'S TREASURY"**, realm and talent underneath
- One panel per live currency:
  - 🪷 **Lotus Coins** in gold with a lotus medallion
  - 🌙 **Moon Pearls** in moon-blue with a pearl medallion
  - Each shows the short number large (128.45K) and the exact number small (128,450)
- **Heavenly Blessing** panel: tier name, its perks, and a bar showing days left out of 30
  (or "No active blessing · /blessing to view tiers")
- **Recent Transactions:** the last 8 changes to coins or pearls, with the reason, how long ago,
  the amount (+ green, − red) and the balance after

Contribution Points and Spirit Stones get their own panel once they unlock.

### Transaction rules

- Every change to a currency goes through one function that writes a ledger row in the same step
- A balance can never go below 0: a purchase you can't afford changes nothing
- If something can't be delivered after paying (e.g. a full bag), the price is refunded at once

## /recharge — Moon Pearl Pavilion

Buy Moon Pearls with real money. Bigger packages give more bonus pearls.

| Package | Price | Moon Pearls | Bonus |
|---|---|---|---|
| 🌙 Pearl Pouch | $2 | 200 | — |
| 🌙 Moonlit Satchel | $5 | 520 | +4% |
| 🌙 Jade Box | $10 | 1,080 | +8% |
| 🌙 Lotus Casket | $20 | 2,240 | +12% |
| 🌙 Moon Treasury | $50 | 5,800 | +16% |
| 🌙 Heavenly Vault | $100 | 12,000 | +20% |

- **First purchase:** double pearls on the first package a player ever buys
- Each package has a buy button; pearls are added automatically
- A receipt is sent to the player by DM

### ☯️ Heavenly Blessing — /blessing

Bought with **Moon Pearls**. Each purchase lasts **30 days**; effects stop when it expires.
Tiers are named after signs of heaven's favour, from a gentle breeze to the Dao itself.

| Tier | Moon Pearls | Qi Rate | Lotus Coins | Mastery EXP | Chest drops | Comprehension |
|---|---|---|---|---|---|---|
| 🍃 Gentle Breeze | 300 | +10% | — | — | — | — |
| 🌧️ Spring Rain | 700 | +20% | +5% | — | — | — |
| 🌕 Bright Moon | 1,500 | +30% | +10% | +5% | — | — |
| ☀️ Blazing Sun | 3,000 | +45% | +15% | +10% | +2.5% | — |
| ⚡ Rolling Thunder | 5,500 | +65% | +20% | +15% | +5% | +10% |
| 🌠 Starfall | 9,000 | +90% | +30% | +20% | +7.5% | +15% |
| 🐉 Heavenly Dragon | 15,000 | +120% | +40% | +30% | +10% | +20% |
| ☯️ Eternal Dao | 25,000 | +150% | +50% | +40% | +15% | +30% |

- **Qi Rate** adds to talent and technique bonuses (see training.md)
- **Chest drops** raise the chance a beast drops a chest — not the tier of what's inside
- **Comprehension** speeds up learning manuals
- Every tier shows a Blessing badge on the profile card; Rolling Thunder and above
  also get a coloured frame
- Buying the **same tier** again adds 30 days
- Buying a **different tier** replaces the current one with a fresh 30 days
  (no refund for days left)

## Moon Pearl shop (/shop)

What Moon Pearls can buy — **speed and style, never power**.

| Item | Moon Pearls | Notes |
|---|---|---|
| 🌟 Heavenly Fate Reroll | 600 | Talent reroll that never goes lower (see talent.md) |
| 💊 Ember Dantian Pill ×3 | 60 | Mortal grade; toxicity still applies |
| 💊 Clear Meridian Pill ×3 | 150 | Yellow grade; toxicity still applies |
| 💊 Jade Marrow Pill ×1 | 120 | Mystic grade; highest grade sold |
| 🎒 Inventory expansion (+20 slots) | 300 | |
| ✏️ Name change | 200 | |
| 🔏 Seal Stone | 30 | Locks one passive slot for a /forge Replace (docs/forge.md) |
| 🖼️ Profile card themes | 400–800 | Cosmetic only (e.g. Night Scroll, Autumn Maple) |

### Never sold for real money
- Combat stats (HP, Attack, Defense)
- Earth or Heaven manuals
- Treasure or Divine weapons
- Earth or Heaven pills, or Breakthrough pills
- Guaranteed breakthroughs
- Anything that wins PvP fights

## Herbs and pills in the economy

Alchemy (alchemy.md) adds a grind that must not print money:

| Rule | Why |
|---|---|
| /gather has no limit, but the NPC merchant **never buys herbs** | Unlimited gathering can't create Lotus Coins |
| Herbs are sold to other players on the market (5% tax, once the market exists) | Gatherers earn from players, and the tax removes coins |
| The Wandering Merchant sells a 10-year herb of your tier for 🪷 10 × realm scale | A small coin sink for players who don't want to gather |
| The Wandering Merchant sells Qi pills: Mortal 🪷 40, Yellow 🪷 120, Mystic 🪷 400 (× realm scale) | Coin sink; crafted pills can be stronger (pill patterns) |
| The Moon Pearl shop sells only Mortal to Mystic Qi pills | Earth and Heaven pills, and every Breakthrough pill, must be crafted |

Herb and pill purchases show in the Purse tab's transaction list like every other coin change.

## Trading Moon Pearls

- Players can sell items to each other for Moon Pearls or Lotus Coins
  (via the player market / trade command)
- This lets free players earn Moon Pearls by farming rare drops
- Every market trade has a **5% tax** (removes coins and pearls from the game)
- Selling items or pearls for real money **outside** the game is not allowed

## Lotus Coin uses

| Spend on | Example |
|---|---|
| 🧳 Wandering Merchant | Herbs (10-year, your tier), Qi pills |
| 📜 Comprehension | Hire a teacher to learn a manual faster |
| ⚡ Breakthrough guidance | + breakthrough success chance |
| 🩹 Physician | Heal injuries faster |
| ⚒️ Forging | Repair or upgrade weapons |
| 🎲 Fate Reroll | Talent reroll (see talent.md) |
| 🏛️ Entry fees | PvP tournaments, special events |
| 🏪 Market tax | 5% of every trade |

Prices: set later when balancing.

## Payments

- Take payments only through Discord's own app monetization or a proper
  payment provider — never by hand
- Check Discord's developer rules on paid features before launch
