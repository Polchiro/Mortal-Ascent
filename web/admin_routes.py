"""
The admin panel's routes (docs/web.md "Admin panel"; the tools are web/admin_panel.py). Only ADMIN_IDS see it.

  GET  /admin?who=<user id>          the panel, working on that player (default: you)
  POST /admin/do                     one tool (a form with "action"); back to the panel with what happened
  GET  /admin/search?kind=item|beast|technique&q=...   the pick lists, as you type
"""
import secrets

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from bot import db

from . import admin_panel as ap
from .profile import number


def add_routes(app, page, current_user, with_conn, form_of, num):

    def admin_of(request):
        user = current_user(request)
        return user if user and ap.is_admin(user["id"]) else None

    def not_found():
        return Response("Not Found", status_code=404)

    def token(request):
        t = request.session.get("admin_token")
        if not t:
            t = request.session["admin_token"] = secrets.token_urlsafe(16)
        return t

    @app.get("/admin", response_class=HTMLResponse)
    def admin_page(request: Request):
        user = admin_of(request)
        if not user:
            return not_found()
        try:
            who = int(request.query_params.get("who") or user["id"])
        except ValueError:
            who = user["id"]

        def load(c):
            me = db.get_player(c, user["id"])
            return {"players": ap.players(c), "target": ap.target_view(c, who), "cooldowns": ap.cooldowns_status(c),
                    "coins": number(me["lotus_coins"]) if me else "0", "pearls": number(me["moon_pearls"]) if me else "0"}
        got = with_conn(load)
        s = {"players": got["players"], "target": got["target"], "who": who, "me": user["id"],
             "cooldowns": got["cooldowns"], "choices": ap.choices(), "token": token(request),
             "done": request.session.pop("admin_done", None)}
        resp = page(request, "admin.html", s=s, user=user, page="admin", coins=got["coins"], pearls=got["pearls"])
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.post("/admin/do")
    async def admin_do(request: Request):
        user = admin_of(request)
        if not user:
            return not_found()
        form = await form_of(request)
        if not form.get("token") or form.get("token") != request.session.get("admin_token"):
            request.session["admin_done"] = {"ok": False, "lines": ["The page was out of date: try again."]}
            return RedirectResponse("/admin", status_code=303)
        try:
            who = int(form.get("who") or user["id"])
        except ValueError:
            who = user["id"]
        ok, lines = await run_in_threadpool(with_conn, ap.act, user["id"], who, form)
        request.session["admin_done"] = {"ok": ok, "lines": lines[:40], "action": form.get("action")}
        section = form.get("action") or ""
        return RedirectResponse(f"/admin?who={who}#{section}", status_code=303)

    @app.get("/admin/search")
    def admin_search(request: Request):
        if not admin_of(request):
            return not_found()
        kind, q = request.query_params.get("kind"), request.query_params.get("q", "")[:80]
        fn = {"item": ap.search_items, "beast": ap.search_beasts, "technique": ap.search_techniques}.get(kind)
        return JSONResponse(fn(q) if fn else [])
