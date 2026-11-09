"""Leaderboards (bot/leaderboard.py, docs/leaderboard.md)."""
from bot import db, leaderboard
from bot import player as rules


def make(conn, uid, realm, layer, coins, pearls):
    db.create_player(conn, uid, f"P{uid}", "Genius", 100, rules.starting_techniques())
    db.update_player(conn, uid, realm=realm, layer=layer, lotus_coins=coins, moon_pearls=pearls)


def test_boards_rank_and_show_my_rank():
    conn = db.connect(":memory:")
    make(conn, 1, "Martial King", 3, 500, 10)
    make(conn, 2, "Martial King", 7, 100, 900)
    make(conn, 3, "Martial Master", 10, 9000, 0)
    for i in range(4, 16):
        make(conn, i, "Mortal", 1, i, i)
    realm = leaderboard.board(conn, "realm", 1)
    assert [r["user_id"] for r in realm["top"][:3]] == [2, 1, 3] and len(realm["top"]) == 10
    assert realm["me"]["rank"] == 2 and realm["top"][0]["value"] == "7th layer"
    coins = leaderboard.board(conn, "lotus_coins", 15)
    assert coins["top"][0]["user_id"] == 3 and coins["top"][0]["value"] == "9,000"
    assert coins["me"]["rank"] == 4                     # P15 has 15 coins: after 9,000, 500 and 100
    assert leaderboard.board(conn, "moon_pearls", 3)["me"]["rank"] == 15
    assert leaderboard.board(conn, "realm", 999)["me"] is None


def test_card_renders_every_board_and_an_empty_one():
    from cards.leaderboard import render_leaderboard
    conn = db.connect(":memory:")
    assert render_leaderboard(leaderboard.board(conn, "realm", 1)).size[0] == 1200
    for i in range(1, 6):
        make(conn, i, "Martial Warrior", i, i * 10, i)
    for key in ("realm", "lotus_coins", "moon_pearls"):
        assert render_leaderboard(dict(leaderboard.board(conn, key, 2), avatars={})).size[0] == 1200
