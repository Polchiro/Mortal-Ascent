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
  /explore    hunting: Solo Hunt, Create a Team, Find a Team; the lobby, locations and team fights (web/hunt_routes.py)
  /gather     herbs grow out in the world now (web/world_routes.py): the old page sends you to town
  /town       the town hub: walk up to the townsfolk, who send you on to the pages above (web/town.py)
  /crossroads outside the town gate: walk down a road to a hunting ground (web/crossroads.py, web/hunt_routes.py)
  /world      the World Map, only to look at (web/world.py)
  /rankings   the Stone Stele's rankings: realm, Lotus Coins, Moon Pearls, duels won (web/rankings.py)
  /arena      duels: challenge a cultivator or find a match, then /duel (web/duel_routes.py)
  /training   the Martial Master's yard: sparring and mastery trials, then /spar (web/spar_routes.py); and
              practice drills with Senior Sister Xue, then /practice (web/practice_routes.py); and Train, a
              meditation steering Qi through the meridians, then /train (web/train_routes.py)
  /logout     forget the login (POST)
  /api/me     the same profile as JSON, for the pages that come next

Every number comes from the same code the bot uses. The forge, alchemy and gathering write to the same character.
"""
import hashlib
import os
import secrets
import time
import urllib.parse
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool
from starlette.middleware.sessions import SessionMiddleware

from bot import appearance as appearance_rules
from bot import db, points
from . import discord_oauth as oauth
from . import (alchemy_play, breakthrough_routes, chest_routes, drawn, duel_routes, explore_play, forge_play, gather_play,
               hunt_routes, practice_routes, rankings, spar_routes, town, train_routes)
from . import world_routes
from . import inventory as bag
from .appearance import appearance_view
from .inventory import inventory_view
from .profile import number, profile_view

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


class FreshStatic(StaticFiles):
    """The site's own style and scripts (web/static/): the browser asks every time whether its copy is still the
    latest (an unchanged file answers 304, nothing re-sent). Without this a browser may keep an old style.css with a
    new page, and a fighter or a beast drawn by the new page goes missing or stands frozen."""
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


_asset_versions = {}


def asset(name):
    """The address of a file in web/static/ with its version: the first characters of a hash of its content, so a
    changed file has a new address and every browser fetches it fresh (templates: {{ asset("fight.js") }})."""
    path = os.path.join(HERE, "static", name)
    try:
        stamp = os.stat(path).st_mtime_ns
    except OSError:
        return f"/static/{name}"
    key = (name, stamp)
    if key not in _asset_versions:
        with open(path, "rb") as fh:
            _asset_versions[key] = hashlib.sha1(fh.read()).hexdigest()[:10]
    return f"/static/{name}?v={_asset_versions[key]}"


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
    @app.middleware("http")
    async def recheck_art(request, call_next):
        """Pictures under /art/ are checked with the server each time (a quick 'not changed' when they're the
        same), so a fixed icon shows up after a git pull without clearing the browser's cache."""
        response = await call_next(request)
        if request.url.path.startswith("/art/") and "cache-control" not in response.headers:
            response.headers["Cache-Control"] = "no-cache"
        return response

    @app.get("/art/drawn/{kind}.png")
    def drawn_icon(kind: str):
        """Icons with no painted file, drawn by the bot's card code (web/drawn.py)."""
        data = drawn.png(kind)
        if data is None:
            return Response(status_code=404)
        return Response(data, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"})

    app.mount("/static", FreshStatic(directory=os.path.join(HERE, "static")), name="static")
    for folder in ("icons", "scenes", "chests", "portraits", "beasts", "fx", "ui", "maps", "forge", "env", "spar", "practice", "train", "breakthrough", "chest"):            # only the art the pages use
        app.mount(f"/art/{folder}", StaticFiles(directory=os.path.join(ROOT, "art", folder)), name=f"art-{folder}")
    templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
    templates.env.filters["rich"] = forge_play.rich          # the bot's **bold** lines as safe HTML
    templates.env.globals["asset"] = asset                     # /static/<file>?v=<its content>: never a stale copy

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
                    points_notice=request.session.pop("points_notice", None),
                    look_done=request.session.pop("look_done", None))

    @app.get("/town/visit/alchemist")
    def town_visit_alchemist(request: Request):
        """Herbalist Lan opens the alchemy hall (web/town.py NPCS): the only way into /alchemy (alchemy_allowed)."""
        if not current_user(request):
            return RedirectResponse("/", status_code=303)
        request.session["alchemy_pass"] = time.time()
        return RedirectResponse("/alchemy", status_code=303)

    @app.get("/town/visit/blacksmith")
    def town_visit_blacksmith(request: Request):
        """Blacksmith Tie opens the forge (web/town.py NPCS): the only way into /forge (forge_allowed)."""
        if not current_user(request):
            return RedirectResponse("/", status_code=303)
        request.session["forge_pass"] = time.time()
        return RedirectResponse("/forge", status_code=303)

    @app.get("/rankings", response_class=HTMLResponse)
    def rankings_page(request: Request, board: str = "realm"):
        """The Stone Stele's rankings (web/rankings.py): read from the stele in town."""
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        c = conn()
        try:
            p = db.get_player(c, user["id"])
            v = rankings.view(c, board, user["id"])
        finally:
            c.close()
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if p is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "rankings.html", v=v, user=user, avatar=avatar,
                    coins=number(p["lotus_coins"]), pearls=number(p["moon_pearls"]))

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

    @app.get("/appearance", response_class=HTMLResponse)
    def appearance(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        c = conn()
        try:
            view = appearance_view(c, user["id"])
        finally:
            c.close()
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "appearance.html", v=view, user=user, avatar=avatar,
                    notice=request.session.pop("look_notice", None))

    @app.post("/appearance")
    async def choose_appearance(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        form = await form_of(request)
        ok, message = await run_in_threadpool(with_conn, appearance_rules.choose, user["id"],
                                              form.get("gender"))
        if ok:
            request.session["look_done"] = message
            return RedirectResponse("/profile", status_code=303)
        request.session["look_notice"] = message
        return RedirectResponse("/appearance", status_code=303)

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

    FORGE_PASS_SECONDS = 30 * 60                  # a visit to Tie lasts this long without a click in the forge

    def forge_allowed(request, uid):
        """The forge is reached only through Blacksmith Tie in town (/town/visit/blacksmith sets the pass), like
        alchemy through Lan. A forge in progress is always allowed, so a refresh mid-forge never throws you out. Each
        visit to the forge keeps the pass fresh; going back to town ends it."""
        if forges.get(uid):
            return True
        t = request.session.get("forge_pass")
        if t and time.time() - t < FORGE_PASS_SECONDS:
            request.session["forge_pass"] = time.time()
            return True
        return False

    def to_tie(request):
        request.session["town_notice"] = "Blacksmith Tie keeps the forge. Talk to him to forge your gear."
        return RedirectResponse("/town?near=blacksmith", status_code=303)

    @app.get("/forge", response_class=HTMLResponse)
    def forge_page(request: Request, item: str = "", action: str = "", essence: str = "", fuel: str = "",
                   liquid: str = "", lock: str = ""):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        if with_conn(forges.catch_up, user["id"]):
            return RedirectResponse("/forge/play", status_code=303)
        if not forge_allowed(request, user["id"]):
            return to_tie(request)
        view = with_conn(forge_play.setup_view, user["id"], num(item), action or None, essence or None,
                         fuel or None, liquid or None, num(lock))
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "forge.html", v=view, user=user, avatar=avatar, error=request.session.pop("forge_error", None),
                    controls=request.cookies.get("ma_forge_controls"), show_help=request.cookies.get("ma_help") != "off")

    @app.post("/forge/begin")
    async def forge_begin(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        if not forge_allowed(request, user["id"]):
            return to_tie(request)
        form = await form_of(request)

        def begin(c, uid):
            plan = forge_play.plan_from(c, uid, form)
            if plan is None:
                return "Pick a piece of gear first."
            controls = "classic" if form.get("controls") == "classic" else "live"
            return forges.start(c, uid, plan, controls=controls)[1]

        error = await run_in_threadpool(with_conn, begin, user["id"])
        if error:
            request.session["forge_error"] = error
            return RedirectResponse("/forge?" + urllib.parse.urlencode({k: v for k, v in form.items() if v}), status_code=303)
        r = RedirectResponse("/forge/play", status_code=303)
        r.set_cookie("ma_forge_controls", "classic" if form.get("controls") == "classic" else "live", max_age=31536000,
                     samesite="lax")
        r.set_cookie("ma_help", "on" if form.get("help") == "on" else "off", max_age=31536000, samesite="lax")
        return r

    # The live forge (web/forge_live.py, static/forge_live.js): the page plays each stage and the server times it.
    def forge_json(s):
        if not s:
            return JSONResponse({"gone": True}, headers={"Cache-Control": "no-store"})
        return JSONResponse(forge_play.live_view(s, forges.clock()), headers={"Cache-Control": "no-store"})

    @app.get("/forge/live")
    def forge_live_state(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"error": "not logged in"}, status_code=401)
        return forge_json(with_conn(forges.catch_up, user["id"]))

    @app.post("/forge/live/begin")
    async def forge_live_begin(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"error": "not logged in"}, status_code=401)
        form = await form_of(request)
        return forge_json(await run_in_threadpool(with_conn, forges.live_begin, user["id"], num(form.get("id"))))

    @app.post("/forge/live/press")
    async def forge_live_press(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"error": "not logged in"}, status_code=401)
        form = await form_of(request)
        ev = {"do": form["do"]} if form.get("do") else {}
        s, reply = await run_in_threadpool(with_conn, forges.live_press, user["id"], num(form.get("id")), ev)
        return JSONResponse({"reply": reply, "state": forge_play.live_view(s, forges.clock()) if s else {"gone": True}},
                            headers={"Cache-Control": "no-store"})

    @app.post("/forge/live/act")
    async def forge_live_act(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"error": "not logged in"}, status_code=401)
        form = await form_of(request)
        return forge_json(await run_in_threadpool(with_conn, forges.live_act, user["id"], form.get("key", ""),
                                                  num(form.get("turn"))))

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
                    coins=f"{p['lotus_coins']:,}", pearls=f"{p['moon_pearls']:,}", scene=forge_play.scene_view(s, p))

    @app.post("/forge/act")
    async def forge_act(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        form = await form_of(request)
        await run_in_threadpool(with_conn, forges.act, user["id"], form.get("key", ""), num(form.get("turn")))
        return RedirectResponse("/forge/play", status_code=303)

    @app.post("/forge/done")
    async def forge_done(request: Request):
        user = current_user(request)
        to_town = (await form_of(request)).get("to") == "town"
        if user:
            s = forges.get(user["id"])
            if s and s.outcome is not None:
                forges.clear(user["id"])
        return RedirectResponse("/town?near=blacksmith" if to_town else "/forge", status_code=303)

    crafts = app.state.crafts = alchemy_play.Crafts()
    ALCHEMY_PASS_SECONDS = 30 * 60                # a visit to Lan lasts this long without a click in the hall

    def alchemy_allowed(request, uid):
        """Alchemy is reached only through Herbalist Lan in town (/town/visit/alchemist sets the pass). A craft in
        progress is always allowed, so a refresh mid-craft never throws you out. Each visit to the hall keeps the pass
        fresh; going back to town ends it."""
        if crafts.get(uid):
            return True
        t = request.session.get("alchemy_pass")
        if t and time.time() - t < ALCHEMY_PASS_SECONDS:
            request.session["alchemy_pass"] = time.time()
            return True
        return False

    def to_lan(request):
        request.session["town_notice"] = "Herbalist Lan keeps the alchemy hall. Talk to her to refine pills."
        return RedirectResponse("/town?near=alchemist", status_code=303)

    @app.get("/alchemy", response_class=HTMLResponse)
    def alchemy_page(request: Request, pill: str = "", batch: str = "", prefer: str = ""):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        if with_conn(crafts.catch_up, user["id"]):
            return RedirectResponse("/alchemy/play", status_code=303)
        if not alchemy_allowed(request, user["id"]):
            return to_lan(request)
        view = with_conn(alchemy_play.setup_view, user["id"], pill or None, num(batch), prefer or None)
        avatar = oauth.avatar_url(user["id"], user.get("avatar"))
        if view is None:
            return page(request, "no_character.html", user=user, avatar=avatar)
        return page(request, "alchemy.html", v=view, user=user, avatar=avatar,
                    error=request.session.pop("alchemy_error", None), controls=request.cookies.get("ma_controls"),
                    show_help=request.cookies.get("ma_help") != "off")

    @app.post("/alchemy/begin")
    async def alchemy_begin(request: Request):
        user = current_user(request)
        if not user:
            return RedirectResponse("/", status_code=303)
        if not alchemy_allowed(request, user["id"]):
            return to_lan(request)
        form = await form_of(request)

        def begin(c, uid):
            pill = alchemy_play.parse_pill(form.get("pill"))
            if pill is None:
                return "Pick a pill first."
            controls = "classic" if form.get("controls") == "classic" else "live"
            return crafts.start(c, uid, *pill, prefer=form.get("prefer") or "young", batch=num(form.get("batch")) or 1,
                                controls=controls)[1]

        error = await run_in_threadpool(with_conn, begin, user["id"])
        if error:
            request.session["alchemy_error"] = error
            return RedirectResponse("/alchemy?" + urllib.parse.urlencode({k: v for k, v in form.items() if v}),
                                    status_code=303)
        r = RedirectResponse("/alchemy/play", status_code=303)
        r.set_cookie("ma_controls", "classic" if form.get("controls") == "classic" else "live", max_age=31536000,
                     samesite="lax")
        r.set_cookie("ma_help", "on" if form.get("help") == "on" else "off", max_age=31536000, samesite="lax")
        return r

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

    # Live controls (web/alchemy_live.py, static/alchemy_live.js): the page plays each stage and the server times it.
    def live_json(s):
        if not s:
            return JSONResponse({"gone": True}, headers={"Cache-Control": "no-store"})
        return JSONResponse(alchemy_play.live_view(s, crafts.clock()), headers={"Cache-Control": "no-store"})

    @app.get("/alchemy/live")
    def alchemy_live_state(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"error": "not logged in"}, status_code=401)
        return live_json(with_conn(crafts.catch_up, user["id"]))

    @app.post("/alchemy/live/begin")
    async def alchemy_live_begin(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"error": "not logged in"}, status_code=401)
        form = await form_of(request)
        return live_json(await run_in_threadpool(with_conn, crafts.live_begin, user["id"], num(form.get("id"))))

    @app.post("/alchemy/live/press")
    async def alchemy_live_press(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"error": "not logged in"}, status_code=401)
        form = await form_of(request)
        ev = {k: form[k] for k in ("herb", "bolt", "act") if form.get(k)}
        if form.get("pump") in ("0", "1"):
            ev["pump"] = form["pump"] == "1"
        if form.get("omen"):
            ev["omen"] = True
        s, reply = await run_in_threadpool(with_conn, crafts.live_press, user["id"], num(form.get("id")), ev)
        return JSONResponse({"reply": reply, "state": alchemy_play.live_view(s, crafts.clock()) if s else {"gone": True}},
                            headers={"Cache-Control": "no-store"})

    @app.post("/alchemy/done")
    async def alchemy_done(request: Request):
        user = current_user(request)
        to_town = (await form_of(request)).get("to") == "town"
        back = "/alchemy"
        if user:
            s = crafts.get(user["id"])
            if s and s.outcome is not None:
                back = "/alchemy?" + urllib.parse.urlencode({"pill": f"{s.kind}:{s.grade}", "batch": s.craft.batch})
                crafts.clear(user["id"])
        return RedirectResponse("/town?near=alchemist" if to_town else back, status_code=303)

    explores = app.state.explores = explore_play.Explores()

    # Explore: hunting alone or as a party (web/hunt_routes.py); /explore/play below still runs an expedition
    # already under way and the /admin web_fight test fights.
    hunt_routes.add_routes(app, page, current_user, with_conn, form_of, num)
    # Duels at the Arena (web/duel_routes.py, web/duel_play.py)
    duel_routes.add_routes(app, page, current_user, with_conn, form_of, num)
    # The Martial Master's training yard: sparring and mastery trials (web/spar_routes.py, web/spar_play.py)
    spar_routes.add_routes(app, page, current_user, with_conn, form_of, num)
    # Practice with Senior Sister Xue: a real-time drill of one technique (web/practice_routes.py, web/practice_play.py)
    practice_routes.add_routes(app, page, current_user, with_conn, form_of, num)
    # Train: Meridian Circulation, a meditation of Qi pulses (web/train_routes.py, web/train_play.py, train_sim.py)
    train_routes.add_routes(app, page, current_user, with_conn, form_of, num)
    # Breakthrough: the plate's Break through button opens the gate (web/breakthrough_routes.py, breakthrough_play.py)
    breakthrough_routes.add_routes(app, page, current_user, with_conn, form_of, num)
    # The Treasure Shelf: opening chests (web/chest_routes.py, web/chest_play.py)
    chest_routes.add_routes(app, page, current_user, with_conn, form_of, num)

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

    # The open world: the town, the Crossroads, the wilds, herbs, beasts and finds (web/world_routes.py)
    world_routes.add_routes(app, page, current_user, with_conn, form_of, num)

    @app.post("/logout")
    def logout(request: Request):
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    return app
