"""
Beast data. Design rules are explained in docs/beast.md.
Stats are multipliers on a player of the same realm and layer (see stats.py).
"""

# ── Tiers ─────────────────────────────────────────────────────────────

BEAST_TIERS = {
    "normal":     {"hp": 1.0,  "attack": 0.8, "team_size": 1},
    "elite":      {"hp": 5.0,  "attack": 1.3, "team_size": 3},
    "beast_king": {"hp": 12.0, "attack": 1.6, "team_size": 5},
}
BEAST_DEFENSE_RATIO = 0.25          # Defense = Attack × this
EXTRA_PLAYER_HP_BONUS = 0.20        # per player beyond team_size

# ── Roles ─────────────────────────────────────────────────────────────

ROLES = {
    "brute":   {"hp": 1.20, "attack": 0.90},
    "hunter":  {"hp": 0.85, "attack": 1.20},
    "swift":   {"dodge": 0.15},
    "armored": {"defense": 2.0},
}

# ── Special rules ─────────────────────────────────────────────────────

CHARGED_ATTACK_TIERS = ["elite", "beast_king"]   # telegraphed, ignores 30% cap
BREAK_STAGGER_SKIPS_TURN = True

# ── Roster: realm → list of (name, tier, role) ────────────────────────

BEASTS = {
    "Mortal": [
        ("Wild Boar", "normal", "brute"),
        ("Field Viper", "normal", "hunter"),
        ("Stray Dog Pack", "normal", "swift"),
        ("Grey Wolf", "elite", "hunter"),
        ("Wild Ox", "elite", "brute"),
        ("Old Black Bear", "beast_king", "brute"),
    ],
    "Martial Apprentice": [
        ("Iron-Hide Boar", "normal", "armored"),
        ("Red Fox", "normal", "swift"),
        ("Cave Bat Swarm", "normal", "swift"),
        ("Shadow Wolf", "elite", "hunter"),
        ("Horned Stag", "elite", "brute"),
        ("Mountain Tiger", "beast_king", "hunter"),
    ],
    "Martial Warrior": [
        ("Thornback Lizard", "normal", "armored"),
        ("Rock Python", "normal", "brute"),
        ("Spear-Beak Crane", "normal", "swift"),
        ("Bloodfang Wolf", "elite", "hunter"),
        ("Armored Boar Chief", "elite", "armored"),
        ("White-Browed Tiger King", "beast_king", "hunter"),
    ],
    "Martial Expert": [
        ("Venom Scorpion", "normal", "hunter"),
        ("Poison Toad", "normal", "brute"),
        ("Silver Monkey", "normal", "swift"),
        ("Thunder Hawk", "elite", "swift"),
        ("Steel-Horn Bull", "elite", "armored"),
        ("Golden-Eyed Ape King", "beast_king", "brute"),
    ],
    "Martial Master": [
        ("Ironbark Bear", "normal", "armored"),
        ("Frost Wolf", "normal", "hunter"),
        ("Ember Lizard", "normal", "swift"),
        ("Frost Python", "elite", "brute"),
        ("Wind Leopard", "elite", "swift"),
        ("Flame-Maned Lion", "beast_king", "hunter"),
    ],
    "Grand Martial Master": [
        ("Stone-Shell Tortoise", "normal", "armored"),
        ("Lightning Weasel", "normal", "swift"),
        ("Bone Vulture", "normal", "hunter"),
        ("Storm Eagle", "elite", "swift"),
        ("Jade-Scaled Crocodile", "elite", "armored"),
        ("Black Water Serpent", "beast_king", "brute"),
    ],
    "Martial Grandmaster": [
        ("Earth-Splitting Rhino", "normal", "armored"),
        ("Shadow Panther", "normal", "swift"),
        ("Iron-Feather Crow", "normal", "hunter"),
        ("Crimson Fire Hawk", "elite", "hunter"),
        ("Thousand-Year Centipede", "elite", "armored"),
        ("Flood Dragon (Jiao)", "beast_king", "brute"),
    ],
    "Martial King": [
        ("Cloud Leopard", "normal", "swift"),
        ("Shanxiao Mountain Spirit", "normal", "hunter"),
        ("Golden Silk Spider", "normal", "armored"),
        ("Nine-Tailed Fox", "elite", "swift"),
        ("Bifang Fire Crane", "elite", "hunter"),
        ("Qilin", "beast_king", "armored"),
    ],
    "Martial Emperor": [
        ("Thunder Rhino", "normal", "brute"),
        ("Fire-Hoof Steed", "normal", "swift"),
        ("Sky Lynx", "normal", "hunter"),
        ("Pixiu", "elite", "armored"),
        ("Tiangou, the Heavenly Hound", "elite", "hunter"),
        ("Taotie, the Devourer", "beast_king", "brute"),
    ],
    "Martial Ancestor": [
        ("Ancient Golden Ape", "normal", "brute"),
        ("Abyss Crocodile", "normal", "armored"),
        ("Ghost-Fire Wolf", "normal", "swift"),
        ("Vermilion Bird", "elite", "hunter"),
        ("Qiongqi, the Winged Tiger", "elite", "swift"),
        ("Black Tortoise (Xuanwu)", "beast_king", "armored"),
    ],
    "Martial Saint": [
        ("Primordial Dragon Turtle", "normal", "armored"),
        ("Void Serpent", "normal", "swift"),
        ("Ancient Flame Lion", "normal", "hunter"),
        ("Azure Dragon", "elite", "swift"),
        ("White Tiger", "elite", "hunter"),
        ("Kun-Peng, Fish of the Northern Sea", "beast_king", "brute"),
    ],
}
