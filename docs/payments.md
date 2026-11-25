# Payments — buying Moon Pearls with real money

Status: **being built, test mode only.** No real money can be taken yet.

| Step | What | State |
|---|---|---|
| 1 | Purchase records and the engine that gives / takes back pearls (`bot/purchases.py`) | done |
| 2 | Signed confirmations from the payment company (webhook), refunds, chargebacks | next |
| 3 | Moon Pearl Pavilion page on the website, checkout | |
| 4 | Purchase history for players, owner lookup page | |
| 5 | Legal pages (terms, refund policy, privacy) | |
| — | Trading rules: bought pearls not tradeable for 7 days, no pearl trades while in debt | before going live |

Payment company: a "merchant of record" that runs the checkout page and handles sales tax
(Xsolla, or Paddle if Paddle confirms in writing that it allows in-game currency). To be chosen in step 2.

## How a purchase works

1. The player presses **Buy** on a pack. The page sends only the pack's key (e.g. `jade_box`).
2. The server looks the price and pearls up in `economy.PEARL_PACKS` and makes an **order** (`pending`)
   with a random order number like `MP-3F9A0C51D27E4B86`. No pearls yet.
3. The player pays on the payment company's own page. Card details only ever go to them.
4. The payment company tells our server directly, in a message signed with a secret key. Only after the
   signature is checked does the server call `purchases.grant`, which checks that the player, the pack and
   test/real mode all match the order, then gives the pearls.
5. The browser coming back saying "I paid" gives nothing.

## Safety rules

| Rule | How |
|---|---|
| Prices come from the server | `economy.PEARL_PACKS` is the only price list; the order stores the price it was made at |
| Pearls only for a confirmed payment | Only `grant` adds bought pearls, called only after the signature check |
| Each payment gives pearls once | The order moves pending → paid in one step only one message can win; the payment company's transaction number is unique in the table |
| All or nothing | Pearls, ledger line and purchase record are written in one transaction |
| Test money can't buy real pearls | Each order is test or real; a payment from the other mode is refused |
| Refunds and chargebacks take pearls back | `purchases.revoke` removes what the player has; spent pearls become `pearl_debt` |
| Every purchase is kept | `pearl_purchases` is never trimmed (the ledger keeps only 100 lines per player) |
| No button spamming | At most 10 unpaid orders per player per hour |

## Packs (launch)

| Key | Pack | Price | Moon Pearls |
|---|---|---|---|
| `pearl_pouch` | 🌙 Pearl Pouch | $2 | 200 |
| `moonlit_satchel` | 🌙 Moonlit Satchel | $5 | 520 |
| `jade_box` | 🌙 Jade Box | $10 | 1,080 |
| `lotus_casket` | 🌙 Lotus Casket | $20 | 2,240 |
| `moon_treasury` | 🌙 Moon Treasury | $50 | 5,800 |

- **First purchase:** double pearls on the first pack a player ever pays for. A refunded first purchase
  still uses up the bonus, so it can't be farmed.
- The $100 Heavenly Vault is left out at launch (big packs draw stolen-card fraud); it can be added later.

## Refunds, chargebacks and pearl debt

- A refund or chargeback takes back the pearls that purchase gave.
- If some were already spent, the rest is recorded as **pearl debt** (`players.pearl_debt`).
- Any pearls the player gets later (quests, gifts, purchases) pay the debt off first; the ledger line says so.
- While a player has pearl debt they can't buy more pearls.
- A refund that arrives before the "paid" message closes the order, so a late "paid" message gives nothing.

## Purchase record (`pearl_purchases`)

| Column | Meaning |
|---|---|
| `order_id` | our order number (`MP-...`), shown to the player |
| `user_id`, `pack`, `price_cents` | who, which pack, price in US cents when ordered |
| `status` | `pending`, `paid`, `refunded`, `chargeback` |
| `live` | 0 = test mode, 1 = real money |
| `pearls`, `bonus` | pearls given, and the first-purchase part of it |
| `provider`, `payment_id` | the payment company and its transaction number |
| `taken_back`, `debt_added` | after a refund: pearls removed, and pearls added to the debt |
| `created_at`, `paid_at`, `refunded_at` | times |

Look-ups: `purchases.find(conn, order_id=...)`, `purchases.find(conn, payment_id=...)`,
`purchases.history(conn, user_id)`.
