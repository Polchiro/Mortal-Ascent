"""
Leaderboards (leaderboard.py, docs/leaderboard.md): the top players by realm, Lotus Coins or Moon Pearls,
and where the viewer stands.

Realm ranks by realm, then layer, then Qi (as server_rank does). Ties keep the older account first.
"""
import leaderboard as config

from . import db
from . import player as rules

FIELDS = "user_id, name, realm, layer, qi, qi_overflow, lotus_coins, moon_pearls, created_at"


def _key(board):
    if board == "realm":
        return lambda p: (-rules.realm_index(p["realm"]), -p["layer"], -(p["qi"] + (p["qi_overflow"] or 0)),
                          p["created_at"])
    return lambda p: (-p[board], p["created_at"])


def value_text(board, p):
    if board == "realm":
        return f"{rules.ordinal(p['layer'])} layer"
    return f"{p[board]:,}"


def ranking(conn, board):
    """Every player, best first. (Fine for SQLite now; a SQL ORDER BY when the game moves to PostgreSQL.)"""
    if board not in config.BOARDS:
        raise ValueError(board)
    rows = [dict(r) for r in conn.execute(f"SELECT {FIELDS} FROM players")]
    return sorted(rows, key=_key(board))


def board(conn, board_key, viewer_id):
    """The data for the leaderboard card: top N and the viewer's own rank."""
    order = ranking(conn, board_key)
    def row(i, p):
        return {"rank": i + 1, "user_id": p["user_id"], "name": p["name"], "realm": p["realm"],
                "layer": p["layer"], "value": value_text(board_key, p),
                "amount": p[board_key] if board_key != "realm" else None}
    top = [row(i, p) for i, p in enumerate(order[:config.TOP_N])]
    me = next((row(i, p) for i, p in enumerate(order) if p["user_id"] == viewer_id), None)
    return {"board": board_key, "boards": [(k, b["label"]) for k, b in config.BOARDS.items()],
            "title": config.BOARDS[board_key]["title"], "icon": config.BOARDS[board_key]["icon"],
            "top": top, "me": me, "players": len(order)}
