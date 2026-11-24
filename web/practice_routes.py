"""
Practice's routes (docs/technique.md "Practice on the website"): a real-time drill with Senior Sister Xue, who
stands in Azure Cloud Town (web/town.py NPCS "sister"); /practice is her page when no drill is running. Every POST only asks web/practice_play.Hall; it decides and it grades.

  POST /practice/start     technique=<id>            set the drill up (the rest starts now, as on Discord)
  GET  /practice           her page, or the drill           GET /practice/state   the drill as JSON
  POST /practice/go                                  the countdown is over: the drill's clock starts
  POST /practice/submit    JSON {"inputs": [[t ms, lane, "d" | "u"], ...]}   grade and pay it (answers the result)
  POST /practice/yield                               walk away (nothing earned, the rest stays)
  POST /practice/done                                leave the result
"""
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bot import db

from . import discord_oauth as oauth
from .practice_play import Hall
from .profile import number


def add_routes(app, page, current_user, with_conn, form_of, num):
    hall = app.state.practice = Hall()

    def go(url):
        return RedirectResponse(url, status_code=303)

    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def purse(c, uid):
        p = db.get_player(c, uid)
        return {"coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"])} if p else {}

    def elsewhere(uid):
        """Busy in a duel or a spar: one thing at a time."""
        arena, spar = getattr(app.state, "arena", None), getattr(app.state, "hall", None)
        if arena and arena.busy(uid):
            return "Finish your duel first."
        if spar and getattr(spar, "busy", None) and spar.busy(uid):
            return "Finish your spar first."
        train = getattr(app.state, "train", None)
        if train and train.busy(uid):
            return "Finish your meditation first."
        return None

    @app.post("/practice/start")
    async def practice_start(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        form = await form_of(request)
        uid = user["id"]
        if hall.busy(uid):
            return go("/practice")
        why = elsewhere(uid) or await run_in_threadpool(with_conn, hall.start, uid, num(form.get("technique")))
        if why:
            request.session["practice_notice"] = why
        return go("/practice")

    @app.get("/practice", response_class=HTMLResponse)
    def practice_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        state = hall.state(uid)
        if state is None:                                        # no drill: Senior Sister Xue, and what to practise
            view, money = with_conn(lambda c: (hall.hall(c, uid), purse(c, uid)))
            if view is None:
                return go("/")
            return no_store(page(request, "practice_hall.html", pv=view, user=user,
                                 avatar=oauth.avatar_url(uid, user.get("avatar")),
                                 notice=request.session.pop("practice_notice", None), **money))
        money = with_conn(purse, uid)
        return no_store(page(request, "practice.html", s=state, user=user,
                             avatar=oauth.avatar_url(uid, user.get("avatar")), **money))

    @app.get("/practice/state")
    def practice_state(request: Request):
        user = current_user(request)
        s = hall.state(user["id"]) if user else None
        return no_store(JSONResponse(s if s else {"gone": True}))

    @app.post("/practice/go")
    def practice_go(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        why = hall.go(user["id"])
        return no_store(JSONResponse({"error": why} if why else {"ok": True}))

    @app.post("/practice/submit")
    async def practice_submit(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        try:
            body = await request.json()
            inputs = body.get("inputs") if isinstance(body, dict) else None
        except ValueError:
            inputs = None
        result, why = await run_in_threadpool(with_conn, hall.submit, user["id"], inputs)
        return no_store(JSONResponse({"error": why, "result": result}))

    @app.post("/practice/yield")
    def practice_yield(request: Request):
        user = current_user(request)
        if user:
            hall.give_up(user["id"])
        return go("/practice")

    @app.post("/practice/done")
    def practice_done(request: Request):
        user = current_user(request)
        if user:
            hall.done(user["id"])
        return go("/practice")

    return hall
