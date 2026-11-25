"""
Economy data. Design rules are explained in docs/economy.md.
"""
import forge


CURRENCIES = {
    "lotus_coins": {"name": "Lotus Coins", "emoji": "🪷", "tradeable": True},
    "moon_pearls": {"name": "Moon Pearls", "emoji": "🌙", "tradeable": True, "premium": True},
    # later:
    # "contribution": {"name": "Contribution Points", "emoji": "📜", "tradeable": False},
    # "spirit_stones": {"name": "Spirit Stones", "emoji": "💎"},
}

BALANCE_EMBED_COLOR = 0xB02C22   # vermilion

# ── /recharge packages: (name, price USD, pearls) ─────────────────────

# The ONLY place pack prices and sizes live (docs/payments.md). The website sends just a pack key; the server
# looks the price and pearls up here, so nobody can change a price from the page.
# Heavenly Vault ($100, 12,000) is left out at launch: big packs draw stolen-card fraud. Add it back later.
PEARL_PACKS = {
    "pearl_pouch":     {"name": "Pearl Pouch",     "price_cents": 200,  "pearls": 200},
    "moonlit_satchel": {"name": "Moonlit Satchel", "price_cents": 500,  "pearls": 520},
    "jade_box":        {"name": "Jade Box",        "price_cents": 1000, "pearls": 1080},
    "lotus_casket":    {"name": "Lotus Casket",    "price_cents": 2000, "pearls": 2240},
    "moon_treasury":   {"name": "Moon Treasury",   "price_cents": 5000, "pearls": 5800},
}
RECHARGE_PACKAGES = [(p["name"], p["price_cents"] // 100, p["pearls"]) for p in PEARL_PACKS.values()]
FIRST_PURCHASE_MULTIPLIER = 2       # a player's first paid pack gives double pearls, once per account

BLESSING_DURATION_DAYS = 30

# tier → price in Moon Pearls and boosts (fractions)
BLESSING_TIERS = {
    "Gentle Breeze":     {"price": 300,   "qi_rate": 0.10, "lotus_coins": 0.00, "mastery_exp": 0.00, "chest_drop": 0.000, "comprehension": 0.00},
    "Spring Rain":       {"price": 700,   "qi_rate": 0.20, "lotus_coins": 0.05, "mastery_exp": 0.00, "chest_drop": 0.000, "comprehension": 0.00},
    "Bright Moon":       {"price": 1500,  "qi_rate": 0.30, "lotus_coins": 0.10, "mastery_exp": 0.05, "chest_drop": 0.000, "comprehension": 0.00},
    "Blazing Sun":       {"price": 3000,  "qi_rate": 0.45, "lotus_coins": 0.15, "mastery_exp": 0.10, "chest_drop": 0.025, "comprehension": 0.00},
    "Rolling Thunder":   {"price": 5500,  "qi_rate": 0.65, "lotus_coins": 0.20, "mastery_exp": 0.15, "chest_drop": 0.050, "comprehension": 0.10},
    "Starfall":          {"price": 9000,  "qi_rate": 0.90, "lotus_coins": 0.30, "mastery_exp": 0.20, "chest_drop": 0.075, "comprehension": 0.15},
    "Heavenly Dragon":       {"price": 15000, "qi_rate": 1.20, "lotus_coins": 0.40, "mastery_exp": 0.30, "chest_drop": 0.100, "comprehension": 0.20},
    "Eternal Dao":       {"price": 25000, "qi_rate": 1.50, "lotus_coins": 0.50, "mastery_exp": 0.40, "chest_drop": 0.150, "comprehension": 0.30},
}
BLESSING_FRAME_FROM = "Rolling Thunder"     # coloured profile frame from this tier up

# ── Moon Pearl shop: item → price in pearls ───────────────────────────

PEARL_SHOP = {
    "heavenly_fate_reroll": 300,
    "mortal_qi_pill_x3": 60,
    "yellow_qi_pill_x3": 150,
    "mystic_qi_pill_x1": 120,
    "inventory_expansion_20": 300,
    "name_change": 200,
    "seal_stone": forge.SEAL_STONE_PEARLS,      # forging (docs/forge.md)
    "profile_theme": (400, 800),
}

MARKET_TAX = 0.05
