"""How many players can walk the world at once? A load test of the website (docs/world.md "How many players").

    python -m scripts.load_test                      # 50, 100, 200, 300 and 500 players, 20 s each
    python -m scripts.load_test 100 400 --seconds 30 # your own sizes
    python -m scripts.load_test --place forest_edge  # everyone in one forest land instead of the town

It starts its OWN copy of the website on a spare port with a throw-away database (your real game and its save are
never touched), creates that many test players, logs each in, stands them all in the same place (the worst case:
everyone sees everyone) and makes each one's "page" do what a real walking page does:

    its position        every 0.4 s while walking; the answer also says who else is here   (/world/pos)
    the other players   once a second, only while standing still                         (/world/others)
    what is out there   every 10 seconds                                                 (/world/state)

By default everyone walks the whole time, which is the heaviest a page can be. --idle 0.5 makes half of them stand
still (reading a menu, talking to someone), which is closer to a real evening.

and measures how long the server takes to answer. A game feels smooth while most answers come back in well under
a quarter of a second; past that, other players start to stutter, and past a second the map feels broken.

The fake players and the server share this computer's processor, so a real server of the same size does a little
better than this says. Run it on the machine you will host on for numbers you can trust.
"""
import argparse
import asyncio
import os
import random
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORT = 8791
BASE = f"http://localhost:{PORT}"
FIRST_ID = 900_000


# ── the test's own website ──────────────────────────────────────────────────────────────────────────────────────

def serve(db_path, players):
    """(internal, --serve) The website on the test port, with a login that needs no Discord: the login `code` is
    the test player's id. Makes the players first."""
    import logging
    import uvicorn
    from bot import db
    from bot import player as rules
    from web import app as web_app
    from web import discord_oauth as oauth
    c = db.connect(db_path)
    for i in range(players):
        uid = FIRST_ID + i
        db.create_player(c, uid, f"Tester {i + 1}", "Genius", rules.STARTING_LOTUS_COINS, rules.starting_techniques())
        db.update_player(c, uid, realm="Martial Warrior", layer=1 + i % 9,
                         appearance='{"gender": "%s"}' % ("female" if i % 2 else "male"))
    c.close()
    oauth.exchange_code = lambda cid, secret, uri, code: code
    oauth.fetch_user = lambda token: {"id": int(token), "username": f"t{token}", "avatar": None}
    app = web_app.create_app(web_app.Settings("cid", "sec", redirect_uri=f"{BASE}/callback", db_path=db_path,
                                              session_secret="load-test"))
    logging.getLogger("uvicorn.access").disabled = True
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")


# ── the fake players ────────────────────────────────────────────────────────────────────────────────────────────

class Stats:
    def __init__(self):
        self.times = {"pos": [], "others": [], "state": []}
        self.errors = 0
        self.seen = 0

    def add(self, kind, seconds, ok):
        self.times[kind].append(seconds)
        if not ok:
            self.errors += 1


def pct(xs, p):
    if not xs:
        return 0.0
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(len(xs) * p))]


async def login(client, uid):
    import urllib.parse
    r = await client.get("/login")
    state = urllib.parse.parse_qs(urllib.parse.urlparse(r.headers["location"]).query)["state"][0]
    await client.get("/callback", params={"code": str(uid), "state": state})


async def player(uid, place, url, stats, until, start_gate, idle=False):
    import httpx
    import json
    import re
    async with httpx.AsyncClient(base_url=BASE, timeout=20, follow_redirects=False) as cl:
        await login(cl, uid)
        r = await cl.get(url if place != "town" else "/town")
        if place != "town":                                   # walked there, as a player would: gate, road, path
            await cl.get("/crossroads?near=town_gate")
            r = await cl.get("/crossroads")
        m = re.search(r'id="mapdata">(.*?)</script>', r.text, re.S)
        if not m:
            stats.errors += 1
            return
        data = json.loads(m.group(1))
        x, y = data["hero"]["x"], data["hero"]["y"]
        at = data["place"]
        await start_gate.wait()                               # everyone starts walking together
        rng = random.Random(uid)
        await asyncio.sleep(rng.random())                     # ... but not on the same tick
        nxt = {"others" if idle else "pos": 0.0, "state": rng.random() * 10}
        every = {"pos": 0.4, "others": 1.0, "state": 10.0}
        t0 = time.monotonic()
        while time.monotonic() < until:
            now = time.monotonic() - t0
            kind = min(nxt, key=nxt.get)
            if nxt[kind] > now:
                await asyncio.sleep(min(0.05, nxt[kind] - now))
                continue
            nxt[kind] = now + every[kind]
            body = {"place": at}
            if kind == "pos":                                 # a small step and back: always a spot you can stand on
                body.update(x=f"{x + rng.choice((0, 0.04)):.3f}", y=f"{y:.3f}")
            a = time.monotonic()
            try:
                r = await cl.post(f"/world/{kind}", data=body)
                ok = r.status_code == 200 and not r.json().get("gone")
                if ok and "others" in r.json():
                    stats.seen = max(stats.seen, len(r.json()["others"]))
            except Exception:
                ok = False
            stats.add(kind, time.monotonic() - a, ok)


async def run(players, seconds, place, idle=0.0):
    url = "/town" if place == "town" else f"/wild/{place}"
    stats, gate = Stats(), asyncio.Event()
    until = time.monotonic() + seconds + 3 + players * 0.03     # time to log everyone in, then the test
    tasks = [asyncio.create_task(player(FIRST_ID + i, place, url, stats, until, gate, idle=i < players * idle))
             for i in range(players)]
    await asyncio.sleep(2 + players * 0.03)
    gate.set()
    began = time.monotonic()
    await asyncio.gather(*tasks)
    took = max(0.001, time.monotonic() - began)
    allt = stats.times["pos"] + stats.times["others"] + stats.times["state"]
    if not stats.seen and players > 1:
        stats.errors += 1                                     # nobody saw anybody: the test itself is broken
    return {"players": players, "requests": len(allt), "per_second": len(allt) / took, "errors": stats.errors,
            "typical": pct(allt, 0.5), "slow": pct(allt, 0.95), "worst": pct(allt, 0.99),
            "others_typical": pct(stats.times["others"], 0.5), "others_slow": pct(stats.times["others"], 0.95),
            "seen": stats.seen}


def verdict(r):
    if r["errors"] > r["requests"] * 0.01 or r["slow"] > 1.0:
        return "broken"
    if r["slow"] > 0.25:
        return "laggy"
    if r["slow"] > 0.1:
        return "ok"
    return "smooth"


def wait_up():
    import httpx
    for _ in range(100):
        try:
            if httpx.get(BASE + "/", timeout=1).status_code < 500:
                return True
        except Exception:
            time.sleep(0.2)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sizes", nargs="*", type=int, default=[50, 100, 200, 300, 500])
    ap.add_argument("--seconds", type=int, default=20)
    ap.add_argument("--place", default="town")
    ap.add_argument("--idle", type=float, default=0.0, help="share of the players standing still (0 to 1)")
    ap.add_argument("--serve", nargs=2, metavar=("DB", "PLAYERS"), help=argparse.SUPPRESS)
    a = ap.parse_args()
    if a.serve:
        return serve(a.serve[0], int(a.serve[1]))
    print(f"{'players':>8} {'asks/s':>8} {'typical':>9} {'slow (1 in 20)':>15} {'worst (1 in 100)':>17} {'failed':>7}   feels")
    out = []
    for n in a.sizes:
        with tempfile.TemporaryDirectory() as tmp:
            srv = subprocess.Popen([sys.executable, "-m", "scripts.load_test", "--serve", os.path.join(tmp, "t.db"), str(n)],
                                   cwd=ROOT)
            try:
                if not wait_up():
                    sys.exit("The test website did not start.")
                r = asyncio.run(run(n, a.seconds, a.place, a.idle))
            finally:
                srv.terminate()
                srv.wait(timeout=10)
        out.append(r)
        print(f"{n:>8} {r['per_second']:>8.0f} {r['typical'] * 1000:>7.0f}ms {r['slow'] * 1000:>13.0f}ms "
              f"{r['worst'] * 1000:>15.0f}ms {r['errors']:>7}   {verdict(r)}", flush=True)
    return out


if __name__ == "__main__":
    main()
