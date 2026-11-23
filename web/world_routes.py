"""
The open world's pages (web/overworld.py, docs/world.md):

  /town               Azure Cloud Town (web/town.py)
  /crossroads         outside the town gate (web/crossroads.py)
  /wild/<key>         a wild place: Moon Forest
  /world/pos          the page saying where you are (a few times a second while you walk)
  /world/move         through an entrance: the next place's page data, swapped in without a reload
  /world/state        what is out there now (herbs regrown, beasts, finds, the trip)
  /world/gather       kneel at a herb: a round of the gathering game (web/gather_play.py)
  /world/gather/pick  your choice; /world/gather/away walks away from it
  /world/engage       a beast and you meet: the fight (/hunt)
  /world/discover     look at what glints: one of /explore's finds
  /gather             the old gathering page: herbs grow in the world now

Every POST asks web/overworld.py, which asks the game's own engines; the page only shows what it answers.
"""
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.concurrency import run_in_threadpool

from bot import db

from . import crossroads, gather_play, overworld, town
from . import discord_oauth as oauth
from .forge_play import rich
from .profile import number


def add_routes(app, page, current_user, with_conn, form_of, num):
    hunts, gathers, explores = app.state.hunts, app.state.gathers, app.state.explores
    parties = hunts.parties
    world = app.state.world = overworld.World(hunts, gathers)

    def go(url):
        return RedirectResponse(url, status_code=303)

    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def avatar(user):
        return oauth.avatar_url(user["id"], user.get("avatar"))

    def away(uid, place):
        """Where you must go instead of walking about here, or None: an expedition under way, a team's hunt or a
        hunt on its own map, a fight out in the world. In town only a fight calls you away."""
        trip = hunts.trip(uid)
        if trip is not None:
            seen = trip.battle is not None or (trip.ended is not None and uid not in trip.acked)
            return "/hunt" if seen else None
        if place == "town":
            return None
        s = with_conn(explores.catch_up, uid)
        if s and not explores._finished(s):
            return "/explore/play"
        party = parties.of(uid)
        if party is not None:
            h = hunts.get(party.id)
            if party.solo and not party.hunting and not (h and h.world and uid in h.results):
                parties.leave(uid)
            elif not (party.solo and h and h.world):
                return "/hunt"
        return None

    def place_page(request, place, near=""):
        import looks
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        elsewhere = away(uid, place)
        if elsewhere:
            return go(elsewhere)

        def build(c):
            p = db.get_player(c, uid)
            if p is None:
                return None
            banked = world.enter(c, uid, place, near or None)
            blocked = hunts.blocked(c, uid)
            sheet = looks.walk_sheet(looks.of_player(p))
            data = overworld.page_data(c, world, uid, place, sheet, p, blocked, near or None) if sheet else None
            return {"p": p, "data": data, "banked": banked, "blocked": blocked,
                    "exits": crossroads.exits(p, blocked) if place == "crossroads" else []}

        v = with_conn(build)
        if v is None:
            return page(request, "no_character.html", user=user, avatar=avatar(user))
        p = v["p"]
        notice = request.session.pop("town_notice", None) or request.session.pop("hunt_error", None)
        if v["banked"]:                                      # walked back in from a trip: what was banked
            notice = " ".join(v["banked"])
        ctx = dict(user=user, avatar=avatar(user), walking=v["data"] is not None, place=place,
                   info=overworld.PLACES[place], map_json=town.page_json(v["data"]) if v["data"] else "",
                   realm=p["realm"], coins=number(p["lotus_coins"]), pearls=number(p["moon_pearls"]),
                   notice=notice, notice_html=bool(v["banked"]))
        if place == "town":
            request.session.pop("alchemy_pass", None)        # back in town: the alchemy hall needs Lan again
            return no_store(page(request, "town.html", town_name=town.NAME, ground=town.ART, npcs=town.NPCS, **ctx))
        ground = crossroads.ART if place == "crossroads" else overworld.wild_data(None, place, (0, 0))["ground"]
        return no_store(page(request, "place.html", ground=ground, exits=v["exits"], **ctx))

    @app.get("/town", response_class=HTMLResponse)
    def town_page(request: Request, near: str = ""):
        """The town hub (web/town.py). Everyone walks it whose look has a walking sheet (looks.WALK_SHEETS); a look
        without one sees the painting and speaks to the townsfolk from a list. Walking back in banks a trip."""
        return place_page(request, "town", near)

    @app.get("/crossroads", response_class=HTMLResponse)
    def crossroads_page(request: Request, near: str = ""):
        return place_page(request, "crossroads", near)

    @app.get("/wild/{key}", response_class=HTMLResponse)
    def wild_page(request: Request, key: str):
        if key not in overworld.WILD:
            return go("/crossroads")
        user = current_user(request)
        w = world.walker(user["id"]) if user else None
        if user and (w is None or w.place != key):           # you walk here: through the Crossroads' road
            return go(overworld.url(w.place) if w else "/town")
        return place_page(request, key)

    # ── the page talking to the server ───────────────────────────────

    async def post_json(request, fn, *keys):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        form = await form_of(request)
        out = await run_in_threadpool(with_conn, fn, user["id"], *[form.get(k) for k in keys])
        return no_store(JSONResponse(out))

    @app.post("/world/pos")
    async def world_pos(request: Request):
        return await post_json(request, lambda c, uid, place, x, y: world.report(c, uid, place, x, y),
                               "place", "x", "y")

    @app.post("/world/move")
    async def world_move(request: Request):
        """Through an entrance. Answers the next place's page data (swapped in without a reload), or where you are."""
        import looks

        def move(c, uid, place, key, x, y):
            done = world.move(c, uid, place, key, x, y)
            if done is None:
                w = world.walker(uid)
                return {"stay": True, "x": w.x if w else None, "y": w.y if w else None}
            to, banked = done
            p = db.get_player(c, uid)
            sheet = looks.walk_sheet(looks.of_player(p))
            data = overworld.page_data(c, world, uid, to, sheet, p, hunts.blocked(c, uid))
            return {"to": to, "url": overworld.url(to), "data": data,
                    "notice": " ".join(banked) if banked else None}

        return await post_json(request, move, "place", "key", "x", "y")

    @app.post("/world/state")
    async def world_state(request: Request):
        return await post_json(request, lambda c, uid, place: world.state(c, uid, place) or {"gone": True}, "place")

    def gather_out(c, uid, s, why):
        if s is None:
            return {"error": rich(why) if why else None}
        out = gather_play.play_view(c, s, gathers.clock())
        w = world.walker(uid)
        out["world"] = world.state(c, uid, w.place) if w else None
        return out

    @app.post("/world/gather")
    async def world_gather(request: Request):
        def start(c, uid, place, hid, x, y):
            s, why = world.gather(c, uid, place, num(hid), x, y)
            return gather_out(c, uid, s, why)
        return await post_json(request, start, "place", "id", "x", "y")

    @app.post("/world/gather/pick")
    async def world_gather_pick(request: Request):
        def pick(c, uid, key, turn):
            return gather_out(c, uid, world.pick(c, uid, key or "", num(turn)), None)
        return await post_json(request, pick, "key", "turn")

    @app.post("/world/gather/away")
    async def world_gather_away(request: Request):
        def away_(c, uid, turn):
            return gather_out(c, uid, world.walk_away(c, uid, num(turn)), None)
        return await post_json(request, away_, "turn")

    @app.post("/world/engage")
    async def world_engage(request: Request):
        def engage(c, uid, place, bid, x, y):
            why = world.engage(c, uid, place, num(bid), x, y)
            return {"fight": "/hunt"} if why is None else {"error": rich(why), "world": world.state(c, uid, place)}
        return await post_json(request, engage, "place", "id", "x", "y")

    @app.post("/world/discover")
    async def world_discover(request: Request):
        def look(c, uid, place, fid, x, y):
            lines, why = world.discover(c, uid, place, num(fid), x, y)
            return {"lines": lines, "error": rich(why) if why else None, "world": world.state(c, uid, place)}
        return await post_json(request, look, "place", "id", "x", "y")

    # ── the old gathering page ───────────────────────────────────────

    @app.get("/gather")
    def gather_page(request: Request):
        """Gathering is out in the world now: herbs grow outside the town gate and in the wilds."""
        if not current_user(request):
            return go("/")
        request.session["town_notice"] = ("Herbs grow out in the world now: walk out of the town gate and look for "
                                          "them glowing in the grass.")
        return go("/town")

    @app.get("/gather/plant/{turn}/{key}.png")
    def gather_plant(request: Request, turn: int, key: str):
        """A choice's drawn plant, asked for by its place on the panel (never by name)."""
        from fastapi.responses import Response
        user = current_user(request)
        data = gathers.plant_png(user["id"], turn, key) if user else None
        if data is None:
            return Response(status_code=404)
        return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})

    return world
