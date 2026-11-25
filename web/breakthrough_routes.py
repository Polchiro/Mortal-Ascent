"""
Breakthrough's routes (docs/web.md "Breakthrough"). The Break through button on the player plate (every map screen)
and on the profile opens the page; the attempt is the bot's own (web/breakthrough_play.py).

  GET  /breakthrough?from=<page>    the gate: its assessment, then the ceremony and the result
  GET  /breakthrough/view           the assessment as JSON (with a fresh token when it can be tried)
  POST /breakthrough/attempt        JSON {"token": ..., "keep_pill": bool}: the attempt (answers the result)
"""
import json
import os

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import looks
from bot import db

from .breakthrough_play import Gates
from .profile import number
from .train_play import hero_art, scene_art

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = "/art/breakthrough"
_ends = {}


def there(url):
    return url if url and os.path.exists(os.path.join(ROOT, url.lstrip("/"))) else None


def ends_art(gender):
    """The inner breakthrough and realm ascension (art/breakthrough/hero/<gender>/sheets.json), or {}."""
    if gender not in _ends:
        try:
            with open(os.path.join(ROOT, "art", "breakthrough", "hero", gender, "sheets.json")) as fh:
                _ends[gender] = json.load(fh).get("ends", {})
        except (OSError, ValueError):
            _ends[gender] = {}
    return _ends[gender]


def stage_art(gender):
    """Every picture, video and sound the page may need, by look; missing art is left out (the page draws in code)."""
    hero = hero_art(gender)
    ends = dict(hero.get("ends", {})) if hero else {}
    ends.update(ends_art(gender))
    chamber = scene_art()
    return {
        "hero": {"loop": hero["loop"], "ends": ends} if hero else None,
        "inner": {"picture": chamber["picture"], "video": chamber["video"], "sound": chamber["sound"],
                  "loop": True},
        "dawn": {"picture": there(f"{ART}/dawn.jpg"), "lit": there(f"{ART}/dawn_lit.jpg"),
                 "video": there(f"{ART}/dawn.mp4"), "sound": there(f"{ART}/dawn.mp3"), "loop": False},
        "storm": {"picture": there(f"{ART}/storm.jpg"), "video": there(f"{ART}/storm.mp4"),
                  "sound": there(f"{ART}/storm.mp3"), "loop": True},
    }


def safe_back(url):
    """Where Back goes: a page of this site only."""
    if not url or not url.startswith("/") or url.startswith("//") or url.startswith("/breakthrough"):
        return "/town"
    return url[:300]


def add_routes(app, page, current_user, with_conn, form_of, num):
    gates = app.state.gates = Gates()

    def go(url):
        return RedirectResponse(url, status_code=303)

    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.get("/breakthrough", response_class=HTMLResponse)
    def breakthrough_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        uid = user["id"]
        back = request.query_params.get("from")
        if back is not None:
            request.session["bt_from"] = safe_back(back)
        back = request.session.get("bt_from") or "/town"

        def load(c, uid):
            p = db.get_player(c, uid)
            if p is None:
                return None
            return {"a": gates.view(c, uid), "gender": looks.gender_of(looks.of_player(p)),
                    "coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"])}
        got = with_conn(load, uid)
        if got is None:
            return go("/")
        s = {"a": got["a"], "art": stage_art(got["gender"]), "gender": got["gender"], "back": back,
             "last": None}
        return no_store(page(request, "breakthrough.html", s=s, user=user, coins=got["coins"], pearls=got["pearls"]))

    @app.get("/breakthrough/view")
    def breakthrough_view(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        return no_store(JSONResponse(with_conn(gates.view, user["id"]) or {"gone": True}))

    @app.post("/breakthrough/attempt")
    async def breakthrough_attempt(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        try:
            body = await request.json()
        except ValueError:
            body = {}
        if not isinstance(body, dict):
            body = {}
        token = body.get("token") if isinstance(body.get("token"), str) else None
        keep = body.get("keep_pill") is True
        result, why = await run_in_threadpool(with_conn, gates.attempt, user["id"], token, keep)
        out = {"result": result, "error": why}
        if why:
            out["view"] = await run_in_threadpool(with_conn, gates.view, user["id"])
        return no_store(JSONResponse(out))

    return gates
