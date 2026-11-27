"""
Techniques (docs/web.md "Techniques"): see what you have learned and choose what is equipped (web/techniques_play.py).

  GET  /techniques                         the sockets and every learned technique
  POST /techniques/equip    form tech=<id> slot=<1-3>  equip it into that slot (what is there comes off; no slot: a free one, else the oldest)
  POST /techniques/unequip  form tech=<id>  take it off (one attack and one defense always stay)
"""
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse

from . import techniques_play as tp
from .profile import number


def add_routes(app, page, current_user, with_conn, form_of, num):
    def go(url):
        return RedirectResponse(url, status_code=303)

    @app.get("/techniques", response_class=HTMLResponse)
    def techniques_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        v = with_conn(tp.view, user["id"])
        if v is None:
            return go("/")
        done = request.session.pop("tech_notice", None)
        resp = page(request, "techniques.html", v=v, user=user, notice=done,
                    coins=number(v["coins"]), pearls=number(v["pearls"]))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def step(fn):
        async def run(request: Request):
            user = current_user(request)
            if not user:
                return go("/")
            form = await form_of(request)
            busy = tp.fighting(app.state, user["id"])
            extra = (num(form.get("slot")),) if form.get("slot") else ()
            ok, message = await run_in_threadpool(with_conn, fn, user["id"], num(form.get("tech")), busy, *extra)
            request.session["tech_notice"] = {"ok": ok, "text": message}
            return go("/techniques")
        return run

    app.post("/techniques/equip")(step(tp.equip))
    app.post("/techniques/unequip")(step(tp.unequip))
