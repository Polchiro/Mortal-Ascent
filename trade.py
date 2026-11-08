"""
Player trading (docs/trading.md). All trading numbers live here.

No tax: what one player offers is exactly what the other receives.
"""
INVITE_SECONDS = 120          # how long the other player has to accept a trade request
SESSION_SECONDS = 15 * 60     # a trade window closes after this long without a click
MAX_LINES = 12                # most items (lines) one side can offer at once
MIN_REALM = None              # e.g. "Martial Warrior": the lowest realm allowed to trade (None = everyone)
QTY_STEPS = (1, 10)           # the − / + buttons on the quantity screen

# Items that can never change hands (key per category).
UNTRADEABLE = {"pills": {"heaven_defying"}}

# The trade picker's categories, in order: (key, label, emoji). "cores" are the Beast Core materials,
# "other" is chests and manuals.
CATEGORIES = [
    ("cores", "Beast Cores", "🔴"),
    ("herbs", "Herbs", "🌿"),
    ("materials", "Materials", "⛏️"),
    ("weapons", "Weapons", "🗡️"),
    ("armor", "Armor", "🥋"),
    ("artifacts", "Artifacts", "🔮"),
    ("pills", "Pills", "💊"),
    ("other", "Other Items", "📦"),
]

CURRENCIES = [("lotus_coins", "Lotus Coins", "🪷"), ("moon_pearls", "Moon Pearls", "🌙")]
