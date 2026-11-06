"""
Numbers for friendly PvP duels (/duel). Rules are explained in docs/pvp.md.

The duel engine is bot/duel.py, the buttons bot/duel_view.py, the card cards/battle.py (render_duel).
Damage still follows stats.md (combat.damage), with the 30% per-hit cap.
"""

# ── The challenge ─────────────────────────────────────────────────────

ACCEPT_SECONDS = 60          # the challenged player has this long to Accept or Decline
PAIR_COOLDOWN_SECONDS = 60   # the same two players can't duel again for this long

# ── Turns ─────────────────────────────────────────────────────────────

TURN_SECONDS = 15            # time to pick a move (both pick secretly at the same time)
TIMEOUT_MOVE = "guard"       # what you do if your timer runs out
TIMEOUTS_TO_FORFEIT = 3      # this many timeouts in a row and you lose the duel
MAX_TURNS = 20               # after this turn, the higher % of HP left wins (a draw if equal)

# ── Fair duel: the same base stats for both ──────────────────────────
# Both fight with the base HP / Attack / Defense of the LOWER player's realm and layer (stats.md).
# Weapon and technique % buffs count at this share; technique effects and mastery count fully.

BUFF_SHARE = 0.5

# ── Counters (same as beast fights, battle.py) ───────────────────────
# Strike beats Break, Guard beats Strike, Break beats Guard.

CLASH_DAMAGE = 0.5           # same move on both sides: each Strike/Break lands at this share
BREAK_SKILL = 1.0            # Break damage multiplier (plain Strike uses stats.BASIC_ATTACK_MULTIPLIER)
STAGGER_DAMAGE_BONUS = 1.25  # a Break that beats a Guard staggers: the broken player takes +25% damage next turn

# ── Fair-fight rules ──────────────────────────────────────────────────

INTENSITY_START_TURN = 10    # rising intensity: from this turn on...
INTENSITY_PER_TURN = 0.10    # ...all damage +10% per turn (turn 10 = +10%, turn 11 = +20%, ...); the 30% cap still holds
RECOVER_MAX_PER_DUEL = 0.50  # Recover (defense technique) heals at most this share of max HP in one duel
EVADE_COOLDOWN_TURNS = 1     # after an Evade triggers, it can't trigger again the next turn
