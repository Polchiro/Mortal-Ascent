"""
The Mortal Ascent website (FastAPI). docs/web.md.

Pages:
  /           the front page: "Continue with Discord"
  /login      sends the player to Discord's permission page
  /callback   Discord sends the player back here; we log them in
  /profile    their character, read from the bot's own database
  /inventory  their bag: every tab, item and its details (viewing only)
  /forge      the blacksmith forge: choose, then play the five stages (bot/forging.py decides everything)
  /logout     forget the login (POST)
  /api/me     the same profile as JSON, for the pages that come next

The website only READS the game for now. Every number comes from the same code the bot uses.
"""
import os
import secrets
import urllib.parse
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from bot import db
from . import discord_oauth as oauth
from . import drawn, forge_play
from .inventory import inventory_view
from .profile import profile_view

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SESSION_DAYS = 14


@dataclass
class Settings:
    client_id: str
    client_secret: str
    redirect_uri: str = "http://localhost:8000/callback"
    db_path: str = os.path.join(ROOT, "mortal_ascent.db")
    session_secret: str = ""


def create_app(settings: Settings, on_ready=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        if on_ready:
            on_ready()
        yield

    app = FastAPI(title="Mortal Ascent", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(
        SessionMiddleware,
        secret_key=settings.session_secret or secrets.token_urlsafe(32),
        session_cookie="ma_session", max_age=SESSION_DAYS * 86400, same_site="lax",
        https_only=settings.redirect_uri.startswith("https://"),
    )
    @app.get("/art/drawn/{kind}.png")
    def drawn_icon(kind: str):
        """Icons with no painted file, drawn by the bot's card code (web/drawn.py)."""
        data = drawn.png(kind)
        if data is None:
            return Response(status_code=404)
        return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})

    app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
    for folder in ("icons", "scenes", "chests"):                       # only the art the pages use
        app.mount(f"/art/{folder}", StaticFiles(directory=os.path.join(ROOT, "art", folder)), name=f"art-{folder}")
    templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))

    def conn():
        return db.connect(settings.db_path)

    def current_user(request):
        u = request.session.get("user")
        return u if u and isinstance(u.get("id"), int) else None

    def page(request, name, status=200, **ctx):
        return templates.TemplateResponse(request, name, ctx, status_code=status)

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request):
        moved = other_address(request)
        if moved:
            return moved
        if current_user(request):
            return RedirectResponse("/profile", status_code=303)
        return page(request, "login.html", message=request.session.pop("flash", None))

    site = urllib.parse.urlsplit(settings.redirect_uri)

    def other_address(request):
        """The page opened at another address than the one Discord returns to (127.0.0.1 vs localhost):
        the login cookie would be lost on the way back, so move to the right address first."""
        if request.url.netloc != site.netloc:
            return RedirectResponse(f"{site.scheme}://{site.netloc}{request.url.path}", status_code=303)
        return None

    @app.get("/login")
    def login(request: Request):
        moved = other_address(request)
        if moved:
            return moved
        state = oauth.new_state()
        request.session["oauth_state"] = state
        return RedirectResponse(oauth.authorize_url(settings.client_id, settings.redirect_uri, state), status_code=303)

    @app.get("/callback")
    def callback(request: Request, code: str = "", state: str = "", error: str = ""):
        expected = request.session.pop("oauth_state", None)
        if error:                                            # the player pressed Cancel on Discord
            request.session["flash"] = "You cancelled. Nothing was shared with the game."
            return RedirectResponse("/", status_code=303)
        if not code or not expected or not secrets.compare_digest(state, expected):
            return page(request, "error.html", status=400,
                        message="That login link has expired. Please press Continue with Discord again. "
                                "(Use a normal browser like Chrome; the browser inside VS Code can't keep the login.)")
        try:
            token = oauth.exchange_code(settings.client_id, settings.client_secret, settings.redirect_uri, code)
            me = oauth.fetch_user(token)
        except oauth.LoginError as e:
            return page(request, "error.html", status=502, message=str(e))
        request.session.clear()                              # a fresh session for the new login
        request.session["user"] = {"id": me["id"], "username": me["username"], "avatar": me["avatar"]}
        return RedirectResponse("/profile", status_code=303)

    @app.get("/profile", response_class=HTMLResponse)
    def profile(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        c = conn()
        try:
            view = profile_view(c, user["id"], username=user["username"])
        finally:
            c.close()
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "profile.html", p=view, user=user, avatar=avatar)

    @app.get("/inventory", response_class=HTMLResponse)
    def inventory(request: Request, tab: str = "weapons", item: int | None = None):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        c = conn()
        try:
            view = inventory_view(c, user["id"], tab, item)
        finally:
            c.close()
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "inventory.html", v=view, user=user, avatar=avatar)

    @app.get("/api/me")
    def api_me(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"error": "not logged in"}, status_code=401)
        c = conn()
        try:
            view = profile_view(c, user["id"], username=user["username"])
        finally:
            c.close()
        return {"user": {"id": str(user["id"]), "username": user["username"]}, "profile": view}

    forges = app.state.forges = forge_play.Forges()

    def num(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    async def form_of(request):
        """A posted form as a plain dict (no extra library needed)."""
        body = (await request.body()).decode("utf-8", "replace")
        return {k: v[0] for k, v in urllib.parse.parse_qs(body).items()}

    def with_conn(fn, *args):
        c = conn()
        try:
            return fn(c, *args)
        finally:
            c.close()

    @app.get("/forge", response_class=HTMLResponse)
    def forge_page(request: Request, item: str = "", action: str = "", essence: str = "", fuel: str = "",
                   liquid: str = "", lock: str = ""):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        if with_conn(forges.catch_up, user["id"]):
            return RedirectResponse("/forge/play", status_code=303)
        view = with_conn(forge_play.setup_view, user["id"], num(item), action or None, essence or None,
                         fuel or None, liquid or None, num(lock))
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "forge.html", v=view, user=user, avatar=avatar, error=request.session.pop("forge_error", None))

    @app.post("/forge/begin")
    async def forge_begin(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        form = await form_of(request)

        def begin(c, uid):
            plan = forge_play.plan_from(c, uid, form)
            if plan is None:
                return "Pick a piece of gear first."
            return forges.start(c, uid, plan)[1]

        error = await run_in_threadpool(with_conn, begin, user["id"])
        if error:
            request.session["forge_error"] = error
            return RedirectResponse("/forge?" + urllib.parse.urlencode({k: v for k, v in form.items() if v}), status_code=303)
        return RedirectResponse("/forge/play", status_code=303)

    @app.get("/forge/play", response_class=HTMLResponse)
    def forge_playing(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        s = with_conn(forges.catch_up, user["id"])
        if not s:
            return RedirectResponse("/forge", status_code=303)
        p = with_conn(lambda c, uid: db.get_player(c, uid), user["id"])
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        return page(request, "forge_play.html", g=forge_play.play_view(s, forges.clock()), user=user, avatar=avatar,
                    coins=f"{p['lotus_coins']:,}", pearls=f"{p['moon_pearls']:,}")

    @app.post("/forge/act")
    async def forge_act(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        form = await form_of(request)
        await run_in_threadpool(with_conn, forges.act, user["id"], form.get("key", ""), num(form.get("turn")))
        return RedirectResponse("/forge/play", status_code=303)

    @app.post("/forge/done")
    def forge_done(request: Request):
        user = current_user(request)
        if user:
            s = forges.get(user["id"])
            if s and s.outcome is not None:
                forges.clear(user["id"])
        return RedirectResponse("/forge", status_code=303)

    @app.post("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    return app
