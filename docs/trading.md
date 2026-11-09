# Trading

Players swap items and currencies with `/trade @player`.

## Flow

1. **Request**: `/trade @player` posts a request. The other player has 2 minutes to **Accept** or **Decline**.
2. **Trade window**: one card shows both offers side by side (your offer · their offer), with the
   buttons **Add Item · Add Currency · Remove · Review Trade · Cancel**. Everyone in the channel can
   watch; only the two traders can press.
3. **Add Item** (private to you): Category → Grade → Item → Quantity → Add to Offer.
   - Categories: Beast Cores, Herbs, Materials, Weapons, Armor, Artifacts, Pills, Other Items.
   - Grades are the game's own: herbs, pills, cores and manuals use Mortal / Yellow / Mystic / Earth /
     Heaven; gear uses Ordinary / Refined / Spirit / Treasure / Divine; forging materials use their tier.
   - Quantity: −10 −1 +1 +10, Max, or type an amount. The screen shows Owned and Offering.
4. **Add Currency** (private): Lotus Coins or Moon Pearls → type the amount. Shows your balance.
5. **Remove**: take a line back out of your offer.
6. **Review Trade**: the Trade Preview: You give / You receive, every line with its quantity. **Confirm**
   locks in your side.
7. When **both** have confirmed, the trade happens at once and the card shows **Trade Complete**.
   Any change to either offer clears both confirmations, so nobody confirms one deal and gets another.

## Rules

- **No tax.** What one side offers is exactly what the other receives.
- Equipped gear can't be offered (unequip it first). Bound items (the Heaven-Defying Pill) can't be traded.
- Up to 12 lines per side.
- When the trade completes, everything is checked again: each player must still own what they offered,
  have the coins and pearls, and the receiver must have bag space for what doesn't stack. If anything
  fails, nothing moves and the window says why.
- One trade at a time per player; not during a fight or a duel.
- The window closes after 15 minutes without a click (nothing changes hands).

Numbers: `trade.py`. Code: `bot/trading.py` (rules), `bot/trade_view.py` (Discord), `cards/trade.py` (card).
