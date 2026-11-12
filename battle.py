"""
Numbers for the interactive turn-based fights (/explore beasts and bandits,
Elite Lair and Beast King team hunts). Rules are explained in docs/combat.md.

The fight engine is bot/fight.py; the card is cards/battle.py.
Colours for each element live in cards/theme.py (ELEMENT_ACCENTS).
"""

# ── Turns ─────────────────────────────────────────────────────────────

TURN_SECONDS = 15            # time to pick a move
TIMEOUT_MOVE = "guard"       # what you do if the timer runs out
TIMEOUTS_TO_FLEE = 3         # this many timeouts in a row and you flee
MAX_TURNS = {"normal": 30, "bandit": 30, "elite": 60, "beast_king": 60}   # then the enemy escapes / the hunt fails

# ── Counters ──────────────────────────────────────────────────────────
# Strike beats Break, Guard beats Strike, Break beats Guard (challenges.COUNTERS).

CLASH_DAMAGE = 0.5           # same move on both sides: each Strike/Break lands at this share
BREAK_SKILL = 1.0            # Break damage multiplier (plain Strike uses stats.BASIC_ATTACK_MULTIPLIER)

# Breaking a Guard staggers the enemy: it loses its next turn and takes extra damage meanwhile.
STAGGER_TURNS = 1
STAGGER_DAMAGE_BONUS = 1.25

# ── How enemies pick their move (weights by role) ────────────────────

MOVE_WEIGHTS = {
    "brute":   {"strike": 0.45, "guard": 0.20, "break": 0.35},
    "hunter":  {"strike": 0.55, "guard": 0.15, "break": 0.30},
    "swift":   {"strike": 0.45, "guard": 0.25, "break": 0.30},
    "armored": {"strike": 0.30, "guard": 0.45, "break": 0.25},
    "bandit":  {"strike": 0.45, "guard": 0.25, "break": 0.30},
}
TELL_CHANCE = 0.7            # share of turns where the warning bar gives away the enemy's next move

# ── Telegraphed moves ─────────────────────────────────────────────────
# Every beast has an element move it announces one turn ahead in the warning bar.
#  • Elite and Beast King: a CHARGED attack that ignores the 30% cap and hits the whole party.
#  • Normal beasts: a signature strike (normal 30% cap) that always applies its element's status if it lands.
# A charged attack can only be answered by Guard (blocks part of it) or Break (interrupts it).

CHARGE_EVERY = 3             # Elite / Beast King: every 3rd enemy turn is charged
CHARGE_MULT = 1.5            # charged hit = 1.5 × a normal hit, no 30% cap
DEFENSE_TECH_BLOCKS_BREAK = True   # a defense technique also blocks its share of a Break (technique.md)
CHARGE_GUARD_BLOCK = 0.50    # plain Guard blocks this share of a charged hit; a defense technique adds its block
SIGNATURE_EVERY = 4          # Normal beasts: every 4th enemy turn is the signature strike
SIGNATURE_MULT = 1.2

# Battle Qi: the energy techniques spend in beast fights (explore, hunts). Separate from cultivation Qi.
# Simulated (1,200 fights per row, Nov 2026): balance unchanged, techniques used more often than with cooldowns.
BATTLE_QI_START = 100         # every fight starts full (+ the player's Spirit points, stats.SPIRIT_BATTLE_QI)
BATTLE_QI_PER_TURN = 10       # back at the end of every turn
BATTLE_QI_GOOD_GUARD = 25     # back when a Guard fully blocks a normal Strike
TECHNIQUE_QI_COST = {"Mortal": 30, "Yellow": 35, "Mystic": 40, "Earth": 45, "Heaven": 50}
CHILLED_QI_COST = 10          # techniques cost this much more while Chilled

# Reading the beast must beat spamming Strike (tested with 600-fight simulations per build, Nov 2026):
BLOCKED_STRIKE_STUN = True   # a Strike into the enemy's Guard leaves you Stunned (only Guard next turn)
GUARD_COUNTER = 0.5          # a Guard that blocks a normal Strike hits back with this share of a Strike

# ── Statuses ──────────────────────────────────────────────────────────
# on: who carries it. turns: how long it lasts.
#   dot: share of max HP lost at the end of each turn
#   cooldown_plus: techniques rest this many extra turns (duels, spars); in beast fights they cost CHILLED_QI_COST more
#   stun: you can only Guard next turn
#   dodge_strike: Strikes against the carrier miss (Break still lands and ends it)
#   damage_taken: carrier takes this share of damage
#   regen: carrier heals this share of max HP at the end of each turn

STATUSES = {
    "staggered": {"name": "Staggered", "on": "enemy",  "turns": STAGGER_TURNS},
    "bleeding":  {"name": "Bleeding",  "on": "player", "turns": 3, "dot": 0.04},
    "chilled":   {"name": "Chilled",   "on": "player", "turns": 2, "cooldown_plus": 1},
    "burning":   {"name": "Burning",   "on": "player", "turns": 3, "dot": 0.05},
    "hidden":    {"name": "Hidden",    "on": "enemy",  "turns": 2, "dodge_strike": True},
    "stunned":   {"name": "Stunned",   "on": "player", "turns": 1, "stun": True},
    "poisoned":  {"name": "Poisoned",  "on": "player", "turns": 4, "dot": 0.03},
    "stoneskin": {"name": "Stoneskin", "on": "enemy",  "turns": 2, "damage_taken": 0.70},
    "regrowth":  {"name": "Regrowth",  "on": "enemy",  "turns": 3, "regen": 0.04},
    "charged":   {"name": "Charged",   "on": "enemy",  "turns": 1},     # shown while a charged attack winds up
}
STATUS_ON_HIT_CHANCE = 0.30  # a normal enemy hit that lands applies its element's status this often

# ── Elements ──────────────────────────────────────────────────────────
# seal: character on the element seal · status: what the element adds
# move: the telegraphed attack's name · warn: warning bar headline ({name} = short beast name) and what the status does

ELEMENTS = {
    "Blood":   {"seal": "血", "status": "bleeding", "move": "Rending Fangs",
                "warn": ("The {name}'s eyes run red with blood-lust...", "Its fangs make you bleed for 3 turns.")},
    "Frost":   {"seal": "霜", "status": "chilled", "move": "Frost Breath",
                "warn": ("Frost gathers in the {name}'s jaws...", "Frost slows your techniques for 2 turns.")},
    "Flame":   {"seal": "炎", "status": "burning", "move": "Mane Blaze",
                "warn": ("The {name}'s mane flares white-hot...", "Or burn for 3 turns.")},
    "Shadow":  {"seal": "影", "status": "hidden", "move": "Shadow Claw",
                "warn": ("The {name} melts into the darkness...", "Strikes miss it while hidden; Break drags it out.")},
    "Thunder": {"seal": "雷", "status": "stunned", "move": "Thunder Pounce",
                "warn": ("Lightning crackles along the {name}'s fur...", "Or be stunned for a turn.")},
    "Venom":   {"seal": "毒", "status": "poisoned", "move": "Venom Fang",
                "warn": ("Venom drips from the {name}'s fangs...", "Or be poisoned for 4 turns.")},
    "Earth":   {"seal": "岩", "status": "stoneskin", "move": "Earthquake Slam",
                "warn": ("The {name}'s hide hardens like stone...", "It takes 30% less damage for 2 turns.")},
    "Jade":    {"seal": "玉", "status": "regrowth", "move": "Jade Surge",
                "warn": ("Green light knits the {name}'s wounds...", "It heals each turn. Keep up the pressure.")},
}
BANDIT_ELEMENT = "Blood"      # bandits fight with blades: Blood palette, Bleeding

# ── Fleeing and pills ─────────────────────────────────────────────────

FLEE_CHANCE = {"normal": 0.80, "bandit": 0.80, "elite": 0.50, "beast_king": 0.35}
PILLS_PER_FIGHT = 2           # Mending pills you can swallow in one fight (heal % from alchemy.MENDING_PILLS)
