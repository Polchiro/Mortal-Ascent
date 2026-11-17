"""
The Arena's routes (docs/pvp.md "On the website"): /arena (challenge, the queue, answering challenges) and /duel
(the fight). Every POST only asks web/duel_play.Arena; it decides.

  GET  /arena            the lobby (or straight into your duel)
  GET  /arena/v          what the pages poll: the lobby's and the duel's version numbers, seconds left this turn
  POST /arena/challenge  name=...          challenge a cultivator by name
  POST /arena/withdraw                     take your challenge back
  POST /arena/answer     id=..., accept=1  accept or decline a challenge
  POST /arena/queue      join=1|0          find a match / stop looking
  GET  /duel             the fight page      GET /duel/state  the fight as JSON (the page swaps it in)
  POST /duel/pick        move=..., turn=n  lock in a move (answers JSON: an error, or nothing)
  POST /duel/flee                          forfeit
  POST /duel/done                          leave the result
"""
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bot import db

from . import discord_oauth as oauth
from .duel_play import Arena
from .profile import number


def add_routes(app, page, current_user, with_conn, form_of, num):
    arena = app.state.arena = Arena()

    def go(url):
        return RedirectResponse(url, status_code=303)

    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def purse(c, uid):
        p = db.get_player(c, uid)
        return {"coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"])} if p else None

    @app.get("/arena", response_class=HTMLResponse)
    def arena_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]

        def build(c):
            if db.get_player(c, uid) is None:
                return None
            return arena.lobby(c, uid), purse(c, uid)
        got = with_conn(build)
        avatar = oauth.avatar_url(uid, user.get("avatar"))
        if got is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        lobby, money = got
        if lobby["in_duel"]:
            return go("/duel")
        return no_store(page(request, "arena.html", v=lobby, user=user, avatar=avatar,
                             notice=request.session.pop("arena_notice", None), **money))

    @app.get("/arena/v")
    def arena_version(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        return no_store(JSONResponse(with_conn(arena.version, user["id"])))

    async def post(request, fn, *keys):
        user = current_user(request)
        if not user:
            return None, None
        form = await form_of(request)
        why = await run_in_threadpool(with_conn, fn, user["id"], *[form.get(k) for k in keys])
        if why:
            request.session["arena_notice"] = why
        return user, form

    @app.post("/arena/challenge")
    async def arena_challenge(request: Request):
        await post(request, lambda c, uid, name: arena.challenge(c, uid, name), "name")
        return go("/arena")

    @app.post("/arena/withdraw")
    async def arena_withdraw(request: Request):
        await post(request, lambda c, uid: arena.withdraw(uid))
        return go("/arena")

    @app.post("/arena/answer")
    async def arena_answer(request: Request):
        await post(request, lambda c, uid, who, yes: arena.answer(c, uid, num(who), yes == "1"), "id", "accept")
        return go("/arena")

    @app.post("/arena/queue")
    async def arena_queue(request: Request):
        await post(request, lambda c, uid, join: arena.join_queue(c, uid) if join == "1" else arena.leave_queue(uid),
                   "join")
        return go("/arena")

    @app.get("/duel", response_class=HTMLResponse)
    def duel_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]

        def build(c):
            s = arena.state(c, uid)
            return (s, purse(c, uid)) if s else None
        got = with_conn(build)
        if got is None:
            return go("/arena")
        state, money = got
        return no_store(page(request, "duel.html", s=state, user=user,
                             avatar=oauth.avatar_url(uid, user.get("avatar")), **money))

    @app.get("/duel/state")
    def duel_state(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        s = with_conn(arena.state, user["id"])
        return no_store(JSONResponse(s if s else {"gone": True}))

    @app.post("/duel/pick")
    async def duel_pick(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        form = await form_of(request)
        why = await run_in_threadpool(with_conn, arena.pick, user["id"], form.get("move", ""), num(form.get("turn")))
        return no_store(JSONResponse({"error": why}))

    @app.post("/duel/flee")
    async def duel_flee(request: Request):
        user = current_user(request)
        if user:
            await run_in_threadpool(with_conn, arena.flee, user["id"])
        return no_store(JSONResponse({}))

    @app.post("/duel/done")
    def duel_done(request: Request):
        user = current_user(request)
        if user:
            arena.done(user["id"])
        return go("/arena")

    return arena
