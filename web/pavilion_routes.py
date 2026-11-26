"""
The Moon Pavilion (docs/web.md "The Moon Pavilion"): the Moon Pearl shop and the Heavenly Blessings
(web/pavilion_play.py; the purchases are bot/shop.py's, the same as Discord's /shop and /blessing).

  GET  /pavilion[?tab=blessing]                    the two tabs
  POST /pavilion/buy    token, key[, name]         buy a shop item
  POST /pavilion/bless  token, tier                receive (or extend) a blessing
Each form carries the page's token, so a stale or repeated form can't spend pearls twice.
"""
import secrets

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, RedirectResponse

from . import pavilion_play as pv
from .profile import number


def add_routes(app, page, current_user, with_conn, form_of):
    def go(url):
        return RedirectResponse(url, status_code=303)

    @app.get("/pavilion", response_class=HTMLResponse)
    def pavilion_page(request: Request, tab: str = "shop"):
        user = current_user(request)
        if not user:
            return go("/")
        v = with_conn(pv.view, user["id"])
        if v is None:
            return go("/")
        token = request.session["pavilion_token"] = secrets.token_urlsafe(16)
        done = request.session.pop("pavilion_notice", None)
        resp = page(request, "pavilion.html", v=v, user=user, notice=done, token=token,
                    tab="blessing" if tab == "blessing" else "shop",
                    coins=number(v["coins"]), pearls=number(v["pearls"]))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def step(tab, act):
        async def run(request: Request):
            user = current_user(request)
            if not user:
                return go("/")
            form = await form_of(request)
            token = request.session.pop("pavilion_token", None)
            if not token or form.get("token") != token:
                request.session["pavilion_notice"] = {"ok": False, "text": "That page was old. Nothing was bought; try again."}
            else:
                ok, text = await run_in_threadpool(with_conn, act, user["id"], form)
                request.session["pavilion_notice"] = {"ok": ok, "text": text}
            return go(f"/pavilion?tab={tab}")
        return run

    app.post("/pavilion/buy")(step("shop", lambda conn, uid, f: pv.buy(conn, uid, f.get("key", ""), f.get("name"))))
    app.post("/pavilion/bless")(step("blessing", lambda conn, uid, f: pv.bless(conn, uid, f.get("tier", ""))))
