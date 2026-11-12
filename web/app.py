"""
The Mortal Ascent website (FastAPI). docs/web.md.

Pages:
  /           the front page: "Continue with Discord"
  /login      sends the player to Discord's permission page
  /callback   Discord sends the player back here; we log them in
  /profile    their character, read from the bot's own database
  /inventory  their bag: every tab, item and its details; Equip / Unequip for weapons, armor and artifacts
  /forge      the blacksmith forge: choose, then play the five stages (bot/forging.py decides everything)
  /alchemy    the alchemy cauldron (/craft): choose a pill, then refine it (bot/crafting.py decides everything)
  /explore    an expedition: five steps, encounters and turn-based fights (bot/expedition.py, bot/fight.py)
  /gather     gathering herbs (/gather): find the right plant before time runs out (bot/gathering.py decides)
  /logout     forget the login (POST)
  /api/me     the same profile as JSON, for the pages that come next

Every number comes from the same code the bot uses. The forge, alchemy and gathering write to the same character.
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

from bot import db, points
from . import discord_oauth as oauth
from . import alchemy_play, drawn, explore_play, forge_play, gather_play
from . import inventory as bag
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
    for folder in ("icons", "scenes", "chests", "portraits", "beasts"):                     # only the art the pages use
        app.mount(f"/art/{folder}", StaticFiles(directory=os.path.join(ROOT, "art", folder)), name=f"art-{folder}")
    templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
    templates.env.filters["rich"] = forge_play.rich          # the bot's **bold** lines as safe HTML

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
            worn = bag.worn_view(c, user["id"]) if view else None
        finally:
            c.close()
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "profile.html", p=view, worn=worn, user=user, avatar=avatar,
                    notice=request.session.pop("gear_notice", None),
                    points_notice=request.session.pop("points_notice", None))

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
        return page(request, "inventory.html", v=view, user=user, avatar=avatar,
                    notice=request.session.pop("gear_notice", None))

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

    def gear_step(fn):
        async def step(request: Request):
            user = current_user(request)
            if not user:
                return RedirectResponse("/", status_code=303)
            form = await form_of(request)
            item_id = num(form.get("item"))
            tab, message = await run_in_threadpool(with_conn, fn, user["id"], item_id)
            request.session["gear_notice"] = message
            if form.get("back") == "profile":
                return RedirectResponse("/profile", status_code=303)
            where = {"tab": tab, "item": item_id} if tab else {}
            return RedirectResponse("/inventory?" + urllib.parse.urlencode(where), status_code=303)
        return step

    async def points_step(request: Request, reset=False):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        form = await form_of(request)
        if reset:
            ok, message = await run_in_threadpool(with_conn, points.reset, user["id"])
        else:
            ok, message = await run_in_threadpool(with_conn, points.place, user["id"],
                                                  num(form.get("strength")) or 0, num(form.get("vitality")) or 0,
                                                  num(form.get("spirit")) or 0)
        request.session["points_notice"] = message
        return RedirectResponse("/profile#develop", status_code=303)

    @app.post("/profile/attributes")
    async def place_points(request: Request):
        return await points_step(request)

    @app.post("/profile/attributes/reset")
    async def reset_points(request: Request):
        return await points_step(request, reset=True)

    app.post("/inventory/equip")(gear_step(bag.equip))
    app.post("/inventory/unequip")(gear_step(bag.unequip))

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

    crafts = app.state.crafts = alchemy_play.Crafts()

    @app.get("/alchemy", response_class=HTMLResponse)
    def alchemy_page(request: Request, pill: str = "", batch: str = "", prefer: str = ""):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        if with_conn(crafts.catch_up, user["id"]):
            return RedirectResponse("/alchemy/play", status_code=303)
        view = with_conn(alchemy_play.setup_view, user["id"], pill or None, num(batch), prefer or None)
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "alchemy.html", v=view, user=user, avatar=avatar,
                    error=request.session.pop("alchemy_error", None))

    @app.post("/alchemy/begin")
    async def alchemy_begin(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        form = await form_of(request)

        def begin(c, uid):
            pill = alchemy_play.parse_pill(form.get("pill"))
            if pill is None:
                return "Pick a pill first."
            return crafts.start(c, uid, *pill, prefer=form.get("prefer") or "young", batch=num(form.get("batch")) or 1)[1]

        error = await run_in_threadpool(with_conn, begin, user["id"])
        if error:
            request.session["alchemy_error"] = error
            return RedirectResponse("/alchemy?" + urllib.parse.urlencode({k: v for k, v in form.items() if v}),
                                    status_code=303)
        return RedirectResponse("/alchemy/play", status_code=303)

    @app.get("/alchemy/play", response_class=HTMLResponse)
    def alchemy_playing(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        s = with_conn(crafts.catch_up, user["id"])
        if not s:
            return RedirectResponse("/alchemy", status_code=303)
        p = with_conn(lambda c, uid: db.get_player(c, uid), user["id"])
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        return page(request, "alchemy_play.html", g=alchemy_play.play_view(s, crafts.clock()), user=user,
                    avatar=avatar, coins=f"{p['lotus_coins']:,}", pearls=f"{p['moon_pearls']:,}",
                    rank=alchemy_play.rank_view(p))

    @app.post("/alchemy/act")
    async def alchemy_act(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        form = await form_of(request)
        await run_in_threadpool(with_conn, crafts.act, user["id"], form.get("key", ""), num(form.get("turn")))
        return RedirectResponse("/alchemy/play", status_code=303)

    @app.post("/alchemy/done")
    def alchemy_done(request: Request):
        user = current_user(request)
        back = "/alchemy"
        if user:
            s = crafts.get(user["id"])
            if s and s.outcome is not None:
                back = "/alchemy?" + urllib.parse.urlencode({"pill": f"{s.kind}:{s.grade}", "batch": s.craft.batch})
                crafts.clear(user["id"])
        return RedirectResponse(back, status_code=303)

    explores = app.state.explores = explore_play.Explores()

    @app.get("/explore", response_class=HTMLResponse)
    def explore_page(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        s = with_conn(explores.catch_up, user["id"])
        if s and not explores._finished(s):
            return RedirectResponse("/explore/play", status_code=303)
        view = with_conn(explore_play.home_view, user["id"], explores)
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "explore.html", v=view, user=user, avatar=avatar,
                    error=request.session.pop("explore_error", None))

    @app.post("/explore/begin")
    async def explore_begin(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)

        def begin(c, uid):
            s = explores.get(uid)
            if s and explores._finished(s):
                explores.clear(uid)
            return explores.start(c, uid)[1]

        error = await run_in_threadpool(with_conn, begin, user["id"])
        if error:
            request.session["explore_error"] = error
            return RedirectResponse("/explore", status_code=303)
        return RedirectResponse("/explore/play", status_code=303)

    @app.get("/explore/play", response_class=HTMLResponse)
    def explore_playing(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)

        def view(c, uid):
            s = explores.catch_up(c, uid)
            if not s:
                return None
            explores.seen(uid)
            return explore_play.play_view(c, s, explores.clock())

        g = with_conn(view, user["id"])
        if g is None:
            return RedirectResponse("/explore", status_code=303)
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        resp = page(request, "explore_play.html", g=g, user=user, avatar=avatar, coins=g["coins"], pearls=g["pearls"])
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.post("/explore/act")
    async def explore_act(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        form = await form_of(request)
        await run_in_threadpool(with_conn, explores.act, user["id"], form.get("what", ""), form.get("arg", ""),
                                num(form.get("turn")))
        return RedirectResponse("/explore/play", status_code=303)

    @app.post("/explore/done")
    def explore_done(request: Request):
        user = current_user(request)
        if user:
            s = explores.get(user["id"])
            if s and explores._finished(s):
                explores.clear(user["id"])
        return RedirectResponse("/explore", status_code=303)

    gathers = app.state.gathers = gather_play.Gathers()

    @app.get("/gather", response_class=HTMLResponse)
    def gather_page(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        if with_conn(gathers.catch_up, user["id"]):
            return RedirectResponse("/gather/play", status_code=303)
        view = with_conn(gather_play.home_view, user["id"], gathers.clock())
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "gather.html", v=view, user=user, avatar=avatar,
                    error=request.session.pop("gather_error", None))

    @app.post("/gather/begin")
    async def gather_begin(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)

        def begin(c, uid):
            s = gathers.get(uid)
            if s and s.g.over:                       # a finished trip: start a fresh one
                gathers.clear(uid)
            return gathers.start(c, uid)[1]

        error = await run_in_threadpool(with_conn, begin, user["id"])
        if error:
            request.session["gather_error"] = error
            return RedirectResponse("/gather", status_code=303)
        return RedirectResponse("/gather/play", status_code=303)

    @app.get("/gather/play", response_class=HTMLResponse)
    def gather_playing(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)

        def view(c, uid):
            s = gathers.catch_up(c, uid)
            return gather_play.play_view(c, s, gathers.clock()) if s else None

        g = with_conn(view, user["id"])
        if g is None:
            return RedirectResponse("/gather", status_code=303)
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        resp = page(request, "gather_play.html", g=g, user=user, avatar=avatar, coins=g["coins"], pearls=g["pearls"])
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def gather_step(name):
        async def step(request: Request):
            user = current_user(request)
            if not user:
                return RedirectResponse("/", status_code=303)
            form = await form_of(request)
            turn = num(form.get("turn"))
            if name == "pick":
                await run_in_threadpool(with_conn, gathers.pick, user["id"], form.get("key", ""), turn)
            else:
                await run_in_threadpool(with_conn, getattr(gathers, name), user["id"], turn)
            return RedirectResponse("/gather/play", status_code=303)
        return step

    for _name in ("pick", "again", "stop"):
        app.post(f"/gather/{_name}")(gather_step(_name))

    @app.post("/gather/done")
    def gather_done(request: Request):
        user = current_user(request)
        if user:
            s = gathers.get(user["id"])
            if s and s.g.over:
                gathers.clear(user["id"])
        return RedirectResponse("/gather", status_code=303)

    @app.get("/gather/plant/{turn}/{key}.png")
    def gather_plant(request: Request, turn: int, key: str):
        """A choice's drawn plant, asked for by its place on the page (never by name)."""
        user = current_user(request)
        data = gathers.plant_png(user["id"], turn, key) if user else None
        if data is None:
            return Response(status_code=404)
        return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})

    @app.post("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    return app
