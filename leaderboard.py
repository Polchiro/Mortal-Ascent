"""
Leaderboard data. Design rules are explained in docs/leaderboard.md.
"""

TOP_N = 10                       # players shown on a board
AVATAR_CACHE_SECONDS = 600       # the top three's Discord avatars are kept this long before fetching again

# board key → how it is shown. The order here is the order of the buttons.
BOARDS = {
    "realm":       {"label": "Realm",       "title": "Realm",       "icon": "art:index/techniques_heaven"},
    "lotus_coins": {"label": "Lotus Coins", "title": "Lotus Coins", "icon": "lotus"},
    "moon_pearls": {"label": "Moon Pearls", "title": "Moon Pearls", "icon": "pearl"},
}
