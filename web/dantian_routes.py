"""
The Dantian screen's routes (docs/web.md "The Dantian"). The Qi bar on the player plate and on the Profile opens it;
everything it shows and does is the bot's own (web/dantian_play.py).

  GET  /dantian?from=<page>      the inner sea: your Qi ledger, layers, toxicity and pills
  GET  /dantian/view             the same as JSON
  POST /dantian/eat     JSON {"item": id, "nonce": str}    eat a pill (answers what it did)
  POST /dantian/pings   JSON {"on": bool}                  the Qi-full ping in Discord (/settings qi_pings)
"""
import os

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bot import db

from .dantian_play import Pills, set_pings, view
from .profile import number

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def there(url):
    return url if os.path.exists(os.path.join(ROOT, url.lstrip("/"))) else None


def art():
    return {"sea": there("/art/dantian/sea.jpg"), "sea_video": there("/art/dantian/sea.mp4"),
            "sea_sound": there("/art/dantian/sea.mp3"), "absorb": there("/art/dantian/absorb.mp4"),
            "absorb_sound": there("/art/dantian/absorb.mp3"), "gourd": there("/art/icons/attr/toxicity.webp"),
            "qi": there("/art/icons/attr/qi.webp")}


def safe_back(url):
    if not url or not url.startswith("/") or url.startswith("//") or url.startswith("/dantian"):
        return "/profile"
    return url[:300]


def add_routes(app, page, current_user, with_conn, form_of, num):
    pills = app.state.pills = Pills()

    def go(url):
        return RedirectResponse(url, status_code=303)

    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    async def body(request):
        try:
            b = await request.json()
        except ValueError:
            b = {}
        return b if isinstance(b, dict) else {}

    @app.get("/dantian", response_class=HTMLResponse)
    def dantian_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        back = request.query_params.get("from")
        if back is not None:
            request.session["dantian_from"] = safe_back(back)
        back = request.session.get("dantian_from") or "/profile"

        def load(c, uid):
            p = db.get_player(c, uid)
            if p is None:
                return None
            return {"v": view(c, uid), "coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"])}
        got = with_conn(load, user["id"])
        if got is None:
            return go("/")
        s = {"v": got["v"], "art": art(), "back": back}
        return no_store(page(request, "dantian.html", s=s, user=user, coins=got["coins"], pearls=got["pearls"]))

    @app.get("/dantian/view")
    def dantian_view(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        return no_store(JSONResponse(with_conn(view, user["id"]) or {"gone": True}))

    @app.post("/dantian/eat")
    async def dantian_eat(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        b = await body(request)
        item, nonce = b.get("item"), b.get("nonce")
        if not isinstance(item, int):
            return no_store(JSONResponse({"result": None, "error": "Pick a pill."}))
        nonce = nonce if isinstance(nonce, str) and len(nonce) <= 64 else None
        result, why = await run_in_threadpool(with_conn, pills.eat, user["id"], item, nonce)
        out = {"result": result, "error": why}
        if why:
            out["view"] = await run_in_threadpool(with_conn, view, user["id"])
        return no_store(JSONResponse(out))

    @app.post("/dantian/pings")
    async def dantian_pings(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        b = await body(request)
        on = await run_in_threadpool(with_conn, set_pings, user["id"], b.get("on") is True)
        return no_store(JSONResponse({"pings": on}))

    return pills
