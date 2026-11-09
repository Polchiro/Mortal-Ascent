"""
Passive Qi (docs/training.md): Qi gathers on its own at the full Qi Rate, with no limit on how long a
player is away. Nobody has to collect it. It is banked into the player's row:

- every minute for every player, by the background task in client.py (bank_everyone), so profiles
  and the server rank stay current without any command;
- before every command (client.before_command), so a command always sees the latest Qi.

Both go through bank(), which adds the Qi gathered since qi_collected_at and moves qi_collected_at
to now, so the same minutes are never counted twice.

/seclusion was removed. Anyone still in seclusion from an older version is let out when the bot
starts (release_secluded), with ×2 Qi for the hours they spent inside.

When banking makes a player's bar full at a gate they can break through, they get one ping in the
channel where they last used the bot ("@player, your Qi is full: use /breakthrough!"), once per gate,
unless they turned pings off in /settings.
"""
import time

from . import db
from . import player as rules

BANK_EVERY_SECONDS = 60     # how often the background task banks everyone's passive Qi
BATCH_SIZE = 200            # players banked per database transaction


def ping_text(user_id):
    return f"<@{user_id}>, your Qi is full: use **/breakthrough**!"


def wants_ping(player, techniques=()):
    """True when the bar is full at a gate the player can break through now, they have not been
    pinged about this gate yet, pings are on, and we know a channel to post in."""
    return (bool(player.get("qi_pings", 1)) and player.get("last_channel_id") is not None
            and player.get("qi_ping_gate") != rules.gate_key(player)
            and rules.ready_to_break(player, techniques))


def bank(conn, user_id, now=None, commit=True):
    """Bank the passive Qi gathered since the last bank. Returns (qi_added, events, ping) where ping is
    (channel_id, text) when a "your Qi is full" message should be posted, else None."""
    now = time.time() if now is None else now
    p = db.get_player(conn, user_id)
    if not p:
        return 0.0, [], None
    techs = db.get_techniques(conn, user_id)
    was_ready = rules.ready_to_break(p, techs)
    qi, _ = rules.passive_qi(p, techs, now)
    p, events = rules.add_qi(p, qi, techs, now=now)
    fields = dict(qi=p["qi"], qi_overflow=p["qi_overflow"], layer=p["layer"], qi_collected_at=now)
    ping = None
    if not was_ready and wants_ping(p, techs):
        ping = (p["last_channel_id"], ping_text(user_id))
        fields["qi_ping_gate"] = rules.gate_key(p)
    if commit:
        db.update_player(conn, user_id, **fields)
    else:
        cols = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(f"UPDATE players SET {cols} WHERE user_id = ?", (*fields.values(), user_id))
    return qi, events, ping


def player_ids(conn):
    """Every player, in a fixed order."""
    return [r[0] for r in conn.execute("SELECT user_id FROM players ORDER BY user_id")]


OLD_SECLUSION_MULTIPLIER = 2.0   # what the removed /seclusion paid for a finished stay


def release_secluded(conn, now=None):
    """Let out everyone still in seclusion from before /seclusion was removed. They get ×2 Qi for the
    hours spent inside (up to the end they chose), even if it had not finished, since the command is
    gone and they could not leave on their own. Passive Qi starts again from now. Returns the user ids."""
    now = time.time() if now is None else now
    rows = conn.execute("SELECT user_id FROM players WHERE seclusion_start IS NOT NULL").fetchall()
    for (uid,) in rows:
        p = db.get_player(conn, uid)
        techs = db.get_techniques(conn, uid)
        start = p["seclusion_start"]
        end = p["seclusion_end"] if p["seclusion_end"] is not None else now
        hours = max(0.0, min(now, end) - start) / 3600
        qi = rules.qi_rate(p, now, techs)[0] * OLD_SECLUSION_MULTIPLIER * hours
        p, _ = rules.add_qi(p, qi, techs, now=now)
        db.update_player(conn, uid, **rules.progress_fields(p),
                         seclusion_start=None, seclusion_end=None, qi_collected_at=now)
    return [uid for (uid,) in rows]


def batches(ids, size=BATCH_SIZE):
    for i in range(0, len(ids), size):
        yield ids[i:i + size]


def bank_batch(conn, ids, now=None):
    """Bank one batch in a single transaction. Returns the pings to send: [(user_id, channel_id, text)]."""
    now = time.time() if now is None else now
    pings = []
    with conn:
        for uid in ids:
            _, _, ping = bank(conn, uid, now, commit=False)
            if ping:
                pings.append((uid, *ping))
    return pings


def bank_everyone(conn, now=None):
    """Bank every player's passive Qi (all batches at once; the client yields between batches)."""
    pings = []
    for ids in batches(player_ids(conn)):
        pings += bank_batch(conn, ids, now)
    return pings


def remember_channel(conn, user_id, channel_id):
    if channel_id is not None:
        db.update_player(conn, user_id, last_channel_id=channel_id)
