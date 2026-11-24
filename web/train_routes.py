"""
Train's routes (docs/training.md "Train on the website"): Meridian Circulation, a ~2-minute meditation chosen from the
training yard (/training). Every POST only asks web/train_play.Chamber; it decides and it scores.

  POST /train/start                                  set the session up (the 60-minute rest starts now, as on Discord)
  GET  /train          the meditation page           GET /train/state   the session as JSON
  POST /train/go                                     the page has begun: the session's clock starts
  POST /train/submit   JSON {"actions": [[t ms, what, which], ...]}   replay, score and pay it (answers the result)
  POST /train/yield                                  walk away (nothing earned, the rest stays)
  POST /train/done                                   leave the result
  GET  /town/visit/keeper                            Sister Jing in town seats you (the same as /train/start)
"""
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bot import db

from . import discord_oauth as oauth
from .profile import number
from .train_play import Chamber


def add_routes(app, page, current_user, with_conn, form_of, num):
    chamber = app.state.train = Chamber()

    def go(url):
        return RedirectResponse(url, status_code=303)

    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def purse_of(c, uid):
        p = db.get_player(c, uid)
        return {"coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"])} if p else {}

    def elsewhere(uid):
        """Busy in a duel, a spar or a drill: one thing at a time."""
        for key, why in (("arena", "Finish your duel first."), ("hall", "Finish your spar first."),
                         ("practice", "Finish your drill first.")):
            other = getattr(app.state, key, None)
            if other is not None and getattr(other, "busy", None) and other.busy(uid):
                return why
        return None

    @app.post("/train/start")
    async def train_start(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        if chamber.busy(uid):
            return go("/train")
        why = elsewhere(uid) or await run_in_threadpool(with_conn, chamber.start, uid)
        if why:
            request.session["training_notice"] = why
            return go("/training#train")
        return go("/train")

    @app.get("/town/visit/keeper")
    async def town_visit_keeper(request: Request):
        """Sister Jing of the Quiet Pavilion (web/town.py NPCS) seats you: the meditation is set up, as the yard's
        Train button does. Resting, or busy elsewhere: back to her, with why."""
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        if chamber.busy(uid):
            return go("/train")
        why = elsewhere(uid) or await run_in_threadpool(with_conn, chamber.start, uid)
        if why:
            request.session["town_notice"] = why
            return go("/town?near=keeper")
        request.session["train_from"] = "keeper"
        return go("/train")

    @app.get("/train", response_class=HTMLResponse)
    def train_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        state = chamber.state(uid)
        if state is None:
            return go("/training#train")
        money = with_conn(purse_of, uid)
        return no_store(page(request, "train.html", s=state, user=user,
                             from_keeper=request.session.get("train_from") == "keeper",
                             avatar=oauth.avatar_url(uid, user.get("avatar")), **money))

    @app.get("/train/state")
    def train_state(request: Request):
        user = current_user(request)
        s = chamber.state(user["id"]) if user else None
        return no_store(JSONResponse(s if s else {"gone": True}))

    @app.post("/train/go")
    def train_go(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        why = chamber.go(user["id"])
        return no_store(JSONResponse({"error": why} if why else {"ok": True}))

    @app.post("/train/submit")
    async def train_submit(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        try:
            body = await request.json()
            actions = body.get("actions") if isinstance(body, dict) else None
        except ValueError:
            actions = None
        result, why = await run_in_threadpool(with_conn, chamber.submit, user["id"], actions)
        return no_store(JSONResponse({"error": why, "result": result}))

    def back(request):
        """Where you came from: Sister Jing by the pond, or the training yard."""
        return go("/town?near=keeper" if request.session.pop("train_from", None) == "keeper" else "/training#train")

    @app.post("/train/yield")
    def train_yield(request: Request):
        user = current_user(request)
        if user:
            chamber.give_up(user["id"])
        return back(request)

    @app.post("/train/done")
    def train_done(request: Request):
        user = current_user(request)
        if user:
            chamber.done(user["id"])
        return back(request)

    return chamber
