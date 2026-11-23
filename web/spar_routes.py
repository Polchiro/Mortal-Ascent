"""
The training yard's routes (docs/technique.md "On the website"): /training (the Martial Master's yard) and /spar
(the fight). Every POST only asks web/spar_play.Hall; it decides.

  GET  /training          the yard: your techniques' mastery, Spar, and a trial for each full bar
  POST /training/spar     technique=<id> (optional: that technique's mastery trial)   begin
  GET  /spar              the fight page       GET /spar/state   the fight as JSON
  POST /spar/pick         move=..., turn=n     play a move (answers JSON: an error, and the new state)
  POST /spar/yield                             walk away (nothing earned)
  POST /spar/done                              leave the result
"""
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bot import db

from . import discord_oauth as oauth
from .profile import number
from .spar_play import Hall


def add_routes(app, page, current_user, with_conn, form_of, num):
    hall = app.state.hall = Hall()

    def go(url):
        return RedirectResponse(url, status_code=303)

    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def purse(c, uid):
        p = db.get_player(c, uid)
        return {"coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"])} if p else {}

    def in_duel(uid):
        arena = getattr(app.state, "arena", None)
        return bool(arena and arena.busy(uid))

    @app.get("/training", response_class=HTMLResponse)
    def training_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        got = with_conn(lambda c: (hall.hall(c, uid), purse(c, uid)))
        avatar = oauth.avatar_url(uid, user.get("avatar"))
        if got[0] is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        view, money = got
        if view["in_spar"]:
            return go("/spar")
        return no_store(page(request, "training.html", v=view, user=user, avatar=avatar,
                             notice=request.session.pop("training_notice", None), **money))

    @app.post("/training/spar")
    async def training_spar(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        form = await form_of(request)
        if in_duel(user["id"]):
            why = "Finish your duel first."
        else:
            why = await run_in_threadpool(with_conn, hall.start, user["id"], num(form.get("technique")))
        if why:
            request.session["training_notice"] = why
            return go("/training")
        return go("/spar")

    @app.get("/spar", response_class=HTMLResponse)
    def spar_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        state, money = with_conn(lambda c: (hall.state(c, uid), purse(c, uid)))
        if state is None:
            return go("/training")
        return no_store(page(request, "spar.html", s=state, user=user,
                             avatar=oauth.avatar_url(uid, user.get("avatar")), **money))

    @app.get("/spar/state")
    def spar_state(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        s = with_conn(hall.state, user["id"])
        return no_store(JSONResponse(s if s else {"gone": True}))

    @app.post("/spar/pick")
    async def spar_pick(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        form = await form_of(request)

        def play(c, uid):
            why = hall.pick(c, uid, form.get("move", ""), num(form.get("turn")))
            return {"error": why, "state": hall.state(c, uid) or {"gone": True}}
        return no_store(JSONResponse(await run_in_threadpool(with_conn, play, user["id"])))

    @app.post("/spar/yield")
    async def spar_yield(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})

        def leave(c, uid):
            hall.give_up(c, uid)
            return hall.state(c, uid) or {"gone": True}
        return no_store(JSONResponse(await run_in_threadpool(with_conn, leave, user["id"])))

    @app.post("/spar/done")
    def spar_done(request: Request):
        user = current_user(request)
        if user:
            hall.done(user["id"])
        return go("/training")

    return hall
