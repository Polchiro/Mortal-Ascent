"""
Explore's hunting pages (docs/hunting.md):

  /explore            the entry: Solo Hunt, Create a Team, Find a Team
  /explore/teams      the public team browser and the invitation ID box
  /explore/create     make a party (name, Public or Private)
  /hunt               your party: the lobby, the hunt (its fight screen) or the hunt's result
  /hunt/locations     the location cards (the leader picks one)
  /hunt/v             a small JSON version number the lobby and hunt pages poll to know when to reload
  /hunt/pos           the map page reporting where you walk (web/hunt_map.py)
  /world              the World Map: the town and the hunting grounds on one painted scroll (web/world.py), to look at
  /crossroads         outside the town gate: walk to a road's end (web/crossroads.py)
  /crossroads/go/<key>  set out down that road: a Solo Hunt on that ground's walkable map

Every POST only asks web/parties.py or web/hunt_play.py; they decide.
"""
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from . import crossroads, explore_play, hunt_pages, hunt_play, world
from . import discord_oauth as oauth
from .parties import Parties


def add_routes(app, page, current_user, with_conn, form_of, num):
    parties = app.state.parties = Parties()
    hunts = app.state.hunts = hunt_play.Hunts(parties)
    explores = app.state.explores

    def go(url):
        return RedirectResponse(url, status_code=303)

    def avatar(user):
        return oauth.avatar_url(user["id"], user.get("avatar"))

    def flash(request, error):
        if error:
            request.session["hunt_error"] = error

    def error(request):
        return request.session.pop("hunt_error", None)

    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # ── the entry ───────────────────────────────────────────────────

    @app.get("/explore", response_class=HTMLResponse)
    def explore_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        s = with_conn(explores.catch_up, uid)
        if s and not explores._finished(s):                      # an expedition already under way
            return go("/explore/play")
        if with_conn(explores.start_test, uid):                  # /admin web_fight queued a test fight
            return go("/explore/play")
        if parties.of(uid):
            return go("/hunt")
        v = with_conn(hunt_pages.entry_view, uid, parties, hunts)
        if v is None:
            return page(request, "no_character.html", user=user, avatar=avatar(user))
        return page(request, "explore.html", v=v, user=user, avatar=avatar(user), error=error(request))

    @app.post("/explore/solo")
    def explore_solo(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        _, why = with_conn(parties.create, user["id"], "", False, True)
        if why:
            flash(request, why)
            return go("/explore")
        return go("/hunt/locations")

    @app.get("/explore/teams", response_class=HTMLResponse)
    def explore_teams(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        if parties.of(user["id"]):
            return go("/hunt")
        v = with_conn(hunt_pages.teams_view, user["id"], parties)
        return no_store(page(request, "hunt_teams.html", v=v, user=user, avatar=avatar(user), error=error(request)))

    @app.get("/explore/create", response_class=HTMLResponse)
    def explore_create(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        if parties.of(user["id"]):
            return go("/hunt")
        v = with_conn(hunt_pages.entry_view, user["id"], parties, hunts)
        return page(request, "hunt_create.html", v=v, user=user, avatar=avatar(user), error=error(request))

    # ── parties ─────────────────────────────────────────────────────

    @app.post("/party/create")
    async def party_create(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        form = await form_of(request)
        _, why = await run_in_threadpool(with_conn, parties.create, user["id"], form.get("name", ""),
                                         form.get("visibility") == "public")
        if why:
            flash(request, why)
            return go("/explore/create")
        return go("/hunt")

    @app.post("/party/join")
    async def party_join(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        form = await form_of(request)
        if form.get("code") is not None:
            _, why = await run_in_threadpool(with_conn, parties.join_code, user["id"], form.get("code", ""))
        else:
            _, why = await run_in_threadpool(with_conn, parties.join_public, user["id"], form.get("id", ""))
        if why:
            flash(request, why)
            return go("/explore/teams")
        return go("/hunt")

    @app.post("/party/{what}")
    async def party_act(request: Request, what: str):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        form = await form_of(request)
        party = parties.of(uid)
        if party is None:
            return go("/explore")
        back = "/hunt"
        why = None
        if what == "ready":
            parties.set_ready(uid, form.get("ready") == "1")
        elif what == "leave":
            why = await run_in_threadpool(with_conn, hunts.leave_party, uid)
            if not why:
                return go("/explore")
        elif what == "kick":
            why = parties.kick(uid, num(form.get("uid")))
        elif what == "disband":
            why = parties.disband(uid)
            if not why:
                return go("/explore")
        elif what == "visibility":
            why = parties.set_public(uid, form.get("public") == "1")
        elif what == "code":
            why = parties.new_code(uid)
        elif what == "location":
            why = await run_in_threadpool(with_conn, parties.set_location, uid, form.get("key", ""))
            if why:
                back = "/hunt/locations"
            elif party.solo:                                     # alone: choosing the place is setting out
                why = await run_in_threadpool(with_conn, lambda c: hunts.start(c, uid, walk=hunt_play.walks(c, uid)))
                if why:
                    back = "/hunt/locations"
        elif what == "start":
            why = await run_in_threadpool(with_conn, hunts.start, uid)
        flash(request, why)
        return go(back)

    # ── the party's page ────────────────────────────────────────────

    @app.get("/hunt", response_class=HTMLResponse)
    def hunt_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]

        def build(c):
            h = hunts.catch_up(c, uid)
            party = parties.seen(uid)
            if party is None:
                return None, None
            if h is not None and (not h.over or uid in h.results) and (uid in h.exps or uid in h.results):
                return "hunt", hunt_play.view(c, hunts, h, uid)
            if party.solo:
                return "locations", None
            return "lobby", hunt_pages.lobby_view(c, uid, party, hunts)

        kind, v = with_conn(build)
        if kind is None:
            return go("/explore")
        if kind == "locations":
            return go("/hunt/locations")
        if kind == "lobby":
            return no_store(page(request, "hunt_lobby.html", v=v, user=user, avatar=avatar(user), error=error(request)))
        if v["mode"] == "map":                                   # walking the hunting ground (web/hunt_map.py)
            return no_store(page(request, "hunt_map.html", g=v, user=user, avatar=avatar(user), error=error(request)))
        if v["mode"] == "fight":                                 # the shared fight screen
            return no_store(page(request, "explore_play.html", g=v, user=user, avatar=avatar(user),
                                 coins=v["coins"], pearls=v["pearls"]))
        return no_store(page(request, "hunt_play.html", g=v, user=user, avatar=avatar(user), error=error(request)))

    @app.get("/hunt/locations", response_class=HTMLResponse)
    def hunt_locations(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        party = parties.seen(user["id"])
        if party is None:
            return go("/explore")
        if party.hunting:
            return go("/hunt")
        v = with_conn(hunt_pages.locations_view, user["id"], party)
        return no_store(page(request, "hunt_locations.html", v=v, user=user, avatar=avatar(user), error=error(request)))

    @app.get("/hunt/v")
    def hunt_version(request: Request):
        """What the lobby and hunt pages poll: they reload when a number changes. Also says 'still here'."""
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        uid = user["id"]

        def read(c):
            h = hunts.catch_up(c, uid)
            party = parties.seen(uid)
            if party is None:
                return {"gone": True}
            out = {"p": party.version, "h": None}
            if h is not None and (uid in h.exps or uid in h.results):     # only a hunt this page shows
                out["h"] = hunts.version(h, uid)
                if h.battle is not None:
                    out["left"] = max(0, round(h.turn_started + hunt_play.TEAM_TURN_SECONDS - hunts.clock()))
            return out

        return no_store(JSONResponse(with_conn(read)))

    @app.post("/hunt/pos")
    async def hunt_pos(request: Request):
        """The map page saying where you are (a few times a second while you walk). Answers where the server has
        you: the page puts you back there if it doesn't agree."""
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        form = await form_of(request)
        at = await run_in_threadpool(with_conn, hunts.report, user["id"], form.get("x"), form.get("y"))
        return no_store(JSONResponse({"gone": True} if at is None else {"x": at[0], "y": at[1]}))

    @app.post("/hunt/act")
    async def hunt_act(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        form = await form_of(request)
        await run_in_threadpool(with_conn, hunts.act, user["id"], form.get("what", ""), form.get("arg", ""),
                                num(form.get("turn")))
        return go("/hunt")

    @app.post("/hunt/done")
    def hunt_done(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        walked = hunts.walked(user["id"])                       # a walked Solo Hunt ends back at the Crossroads,
        party = hunts.dismiss(user["id"])                       # at the end of the road it went down
        return go("/hunt" if party else f"/crossroads?near=road_{walked}" if walked else "/explore")

    # ── the World Map (web/world.py, docs/world.md) ─────────────────

    @app.get("/world", response_class=HTMLResponse)
    def world_page(request: Request):
        """The World Map (web/world.py): only a map to look at, from anywhere; you travel by walking."""
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]

        def build(c):
            from bot import db
            p = db.get_player(c, uid)
            if p is None:
                return None
            return {**hunt_pages.purse(p), "realm": p["realm"], "markers": world.markers(p, hunts.blocked(c, uid))}

        v = with_conn(build)
        if v is None:
            return page(request, "no_character.html", user=user, avatar=avatar(user))
        return no_store(page(request, "world.html", v=v, art=world.ART, user=user, avatar=avatar(user)))

    def away(request, uid):
        """Where a player must go instead of walking about: an expedition under way, a team, or a hunt (None: free).
        A Solo Hunt still choosing its ground is dropped."""
        s = with_conn(explores.catch_up, uid)
        if s and not explores._finished(s):
            return "/explore/play"
        party = parties.of(uid)
        if party is not None:
            if party.solo and not party.hunting:
                parties.leave(uid)
            else:
                return "/hunt"
        return None

    @app.get("/crossroads", response_class=HTMLResponse)
    def crossroads_page(request: Request, near: str = ""):
        """Outside the town gate (web/crossroads.py): walked like the town, by everyone whose look has a walking
        sheet; a look without one chooses a road from a list."""
        import looks
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        elsewhere = away(request, uid)
        if elsewhere:
            return go(elsewhere)

        def build(c):
            from bot import db
            p = db.get_player(c, uid)
            if p is None:
                return None
            blocked = hunts.blocked(c, uid)
            sheet = looks.walk_sheet(looks.of_player(p))
            data = crossroads.page_data(sheet, p, blocked, near or None) if sheet else None
            return {**hunt_pages.purse(p), "realm": p["realm"], "data": data, "exits": crossroads.exits(p, blocked)}

        v = with_conn(build)
        if v is None:
            return page(request, "no_character.html", user=user, avatar=avatar(user))
        from . import town
        return no_store(page(request, "crossroads.html", user=user, avatar=avatar(user), notice=error(request),
                             walking=v["data"] is not None, ground=crossroads.ART, exits=v["exits"],
                             map_json=town.page_json(v["data"]) if v["data"] else "", realm=v["realm"],
                             coins=v["coins"], pearls=v["pearls"]))

    @app.post("/crossroads/go/{key}")
    def crossroads_go(request: Request, key: str):
        """Down a road from the Crossroads: a Solo Hunt on this ground. Every check is the Solo Hunt's own (realm,
        injury, rest: Parties.start_problems, Hunts.blocked); if one fails nothing is started."""
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        if world.place(key) is None:
            flash(request, "There is no such road.")
            return go("/crossroads")
        if parties.of(uid) is not None:
            return go("/hunt")

        def set_out(c):
            _, why = parties.create(c, uid, "", False, True)
            if why:
                return why
            why = parties.set_location(c, uid, key) or hunts.start(c, uid, walk=hunt_play.walks(c, uid))
            if why:
                parties.leave(uid)                               # nothing started: no party left behind
            return why

        why = with_conn(set_out)
        if why:
            flash(request, why)
            return go(f"/crossroads?near=road_{key}")
        return go("/hunt")

    return explore_play
