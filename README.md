# Mortal-Ascent
Every immortal started as a mortal, but cultivation isn’t where the journey begins. Train your martial arts to their peak, then undergo rebirth to cleanse the waste from your body. Only those who succeed earn a chance to enter the path of cultivation. Will you break through, or stay mortal?


## Repo layout

- `docs/` holds the design docs (realms, stats, talent, technique, training, beasts, explore, challenges, economy, equipment, tutorial).
- The `.py` files at the root hold the game data and the card renderers (`profile_card.py`, `balance_card.py`, `inventory_card.py`, `qi_card.py`).
- `fonts/` is where the card fonts go; see [fonts/README.md](fonts/README.md).

## Setup

```
pip install -r requirements.txt
python scripts/render_cards.py   # renders every card as a smoke check
```
