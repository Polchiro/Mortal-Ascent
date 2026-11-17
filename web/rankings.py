"""
The rankings carved on the town's Stone Stele (/rankings, docs/town.md): the bot's leaderboards (bot/leaderboard.py:
realm, Lotus Coins, Moon Pearls) and one more, Duels: most duels won (players.duels_won, counted by db.save_duel).

The page shows a board's top players and, under them, where you stand.
"""
import leaderboard as config
from bot import leaderboard

TOP_N = config.TOP_N
BOARDS = [(k, b["label"]) for k, b in config.BOARDS.items()] + [("duels", "Duels")]


def _duels(conn):
    rows = [dict(r) for r in conn.execute(
        "SELECT user_id, name, realm, layer, duels_won, duels_lost, created_at FROM players")]
    return sorted(rows, key=lambda p: (-p["duels_won"], p["duels_lost"], p["created_at"]))


def view(conn, board, viewer_id):
    """The page's data: the board's tabs, its top players and the viewer's own row (None without a character)."""
    keys = [k for k, _ in BOARDS]
    board = board if board in keys else keys[0]
    if board == "duels":
        order = _duels(conn)

        def row(i, p):
            lost = f" · {p['duels_lost']} lost" if p["duels_lost"] else ""
            return {"rank": i + 1, "user_id": p["user_id"], "name": p["name"], "realm": p["realm"],
                    "layer": p["layer"], "value": f"{p['duels_won']} won{lost}"}
        top = [row(i, p) for i, p in enumerate(order[:TOP_N])]
        me = next((row(i, p) for i, p in enumerate(order) if p["user_id"] == viewer_id), None)
        players, title = len(order), "Duels won"
    else:
        b = leaderboard.board(conn, board, viewer_id)
        top, me, players, title = b["top"], b["me"], b["players"], b["title"]
    for r in top + ([me] if me else []):
        r["you"] = r["user_id"] == viewer_id
        r["where"] = f"{r['realm']}, {_ordinal(r['layer'])} layer"
    return {"board": board, "title": title, "tabs": [{"key": k, "label": label, "on": k == board} for k, label in BOARDS],
            "top": top, "me": me if me and me["rank"] > TOP_N else None, "players": players}


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"
