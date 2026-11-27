"""
The Treasure Shelf and opening chests (docs/web.md "Opening a chest"). The bag's Chests tab and the chest's Open
button lead here; every opening is the bot's own (web/chest_play.py).

  GET  /chests?from=<page>[&open=<item id>]   the shelf (and the vault, when it opens)
  GET  /chests/shelf                          the shelf as JSON
  POST /chests/open      JSON {"item": id, "count": 1..20, "nonce": str}   open (answers what came out)
  POST /chests/collect   JSON {"nonce": str}                               rewards still waiting from a reveal
"""
import os

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from bot import db

from .chest_play import Chests, shelf
from .profile import number

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = "/art/chest"


def there(url):
    return url if os.path.exists(os.path.join(ROOT, url.lstrip("/"))) else None


def art():
    return {"shelf": there(f"{ART}/shelf.jpg"), "vault": there(f"{ART}/vault.jpg"), "vault_video": there(f"{ART}/vault.mp4"),
            "vault_sound": there(f"{ART}/vault.mp3"), "burst": there(f"{ART}/burst.mp4"),
            "burst_sound": there(f"{ART}/burst.mp3"), "glow_in": there(f"{ART}/glow_in.mp4"),
            "glow": there(f"{ART}/glow.mp4"), "glow_sound": there(f"{ART}/glow.mp3"), "slip": there(f"{ART}/slip.webp"),
            "lid": there(f"{ART}/lid.webp"), "seal": there("/art/train/fx/seal.webp"),
            "crack": there("/art/train/fx/crack.webp"),
            # the Epic, Legendary and Mythic openings (scripts/make_chest_rite_art.py)
            "rite": {k: there(f"{ART}/rite/{k}.{ext}") for k, ext in (("seal", "jpg"), ("ring", "webp"), ("dragon", "jpg"), ("beam", "jpg"),
                                                                     ("crack", "jpg"), ("galaxy", "jpg"), ("stamp", "webp"))}}


def safe_back(url):
    if not url or not url.startswith("/") or url.startswith("//") or url.startswith("/chests"):
        return "/inventory?tab=chests"
    return url[:300]


def add_routes(app, page, current_user, with_conn, form_of, num):
    chests = app.state.chests = Chests()

    def go(url):
        return RedirectResponse(url, status_code=303)

    def no_store(resp):
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def body_of(raw):
        return raw if isinstance(raw, dict) else {}

    @app.get("/chests", response_class=HTMLResponse)
    def chests_page(request: Request):
        user = current_user(request)
        if not user:
            return go("/")
        back = request.query_params.get("from")
        if back is not None:
            request.session["chest_from"] = safe_back(back)
        back = request.session.get("chest_from") or "/inventory?tab=chests"

        def load(c, uid):
            p = db.get_player(c, uid)
            if p is None:
                return None
            return {"shelf": shelf(c, uid), "coins": number(p["lotus_coins"]), "pearls": number(p["moon_pearls"])}
        got = with_conn(load, user["id"])
        if got is None:
            return go("/")
        try:
            want = int(request.query_params.get("open") or 0)
        except ValueError:
            want = 0
        s = {"shelf": got["shelf"], "art": art(), "back": back, "open": want}
        return no_store(page(request, "chests.html", s=s, user=user, coins=got["coins"], pearls=got["pearls"]))

    @app.get("/chests/shelf")
    def chests_shelf(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        return no_store(JSONResponse(with_conn(shelf, user["id"]) or {"gone": True}))

    @app.post("/chests/open")
    async def chests_open(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        try:
            b = body_of(await request.json())
        except ValueError:
            b = {}
        item, count, nonce = b.get("item"), b.get("count", 1), b.get("nonce")
        if not isinstance(item, int) or not isinstance(count, int) or not 1 <= count <= 99:
            return no_store(JSONResponse({"result": None, "error": "Pick a chest to open."}))
        nonce = nonce if isinstance(nonce, str) and len(nonce) <= 64 else None
        result, why = await run_in_threadpool(with_conn, chests.open, user["id"], item, count, nonce)
        out = {"result": result, "error": why}
        out["shelf"] = await run_in_threadpool(with_conn, shelf, user["id"])
        return no_store(JSONResponse(out))

    @app.post("/chests/collect")
    async def chests_collect(request: Request):
        user = current_user(request)
        if not user:
            return JSONResponse({"gone": True})
        try:
            b = body_of(await request.json())
        except ValueError:
            b = {}
        nonce = b.get("nonce") if isinstance(b.get("nonce"), str) and len(b.get("nonce")) <= 64 else None
        result, why = await run_in_threadpool(with_conn, chests.collect, user["id"], nonce)
        out = {"result": result, "error": why}
        out["shelf"] = await run_in_threadpool(with_conn, shelf, user["id"])
        return no_store(JSONResponse(out))

    return chests
