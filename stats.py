BASE_HP = {
    "Mortal": 50,
    "Martial Apprentice": 100,
    "Martial Warrior": 200,
    "Martial Expert": 380,
    "Martial Master": 700,
    "Grand Martial Master": 1100,
    "Martial Grandmaster": 1800,
    "Martial King": 3000,
    "Martial Emperor": 5000,
    "Martial Ancestor": 8500,
    "Martial Saint": 15000,
}
 
HP_BONUS_PER_LAYER = 0.04
PEAK_LAYER_MULTIPLIER = 1.40
 
ATTACK_RATIO = 0.25    # Base Attack = Base HP × this
DEFENSE_RATIO = 0.25   # Base Defense = Base Attack × this
 
BASIC_ATTACK_MULTIPLIER = 1.0
DAMAGE_RANDOM_MIN = 0.9
DAMAGE_RANDOM_MAX = 1.1
MAX_HIT_PERCENT = 0.30  # one hit can never exceed 30% of target max HP
 

# ── Strength and Vitality (docs/attributes.md) ────────────────────────
# Points come on top of the realm growth above: one for every layer climbed since Mortal layer 1.
ATTRIBUTE_POINTS_PER_LAYER = 1
STRENGTH_ATTACK = 0.005      # each Strength point: +0.5% Attack
VITALITY_HP = 0.005          # each Vitality point: +0.5% max HP
SPIRIT_BATTLE_QI = 2         # each Spirit point: +2 Battle Qi in beast fights (battle.BATTLE_QI_START)
FREE_ATTRIBUTE_RESETS = 1    # the first reset costs nothing
ATTRIBUTE_RESET_PEARLS = 200 # every reset after that, in Moon Pearls
