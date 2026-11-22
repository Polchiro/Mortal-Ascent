# The World Map

**The World Map** (`/world`) joins the town and the six hunting grounds into one world. You leave
**Azure Cloud Town** through its gate, the scroll shows every place, and from it you set out to a hunting ground or
go back to town. It adds no new rules: a hunting ground is the hunting grounds' own (docs/hunting.md), and setting
out is a Solo Hunt with the same checks, beasts, rest and rewards.

Code: `web/world.py` (the places on the scroll), the `/world` routes in `web/hunt_routes.py`,
`web/templates/world.html`, `web/static/world.js`. The picture: `art/maps/world.webp`, cut by
`scripts/make_world_map.py`. Tests: `tests/test_world.py`.

## How the world fits together

```
 Azure Cloud Town ──the gate──► The World Map ──set out──► a hunting ground (walkable map)
        ▲                          │    ▲                          │
        └──── Back to town ────────┘    └── the path home / Return home ┘
```

- **Out of town:** walk to the gate (the doorway glows) and press **E**: *The Town Gate · Leave town*, then
  **Go out into the world**. The town's **World Map** button and the Gate Warden go there too. On a look without a
  walking sheet, the townsfolk list has the gate as well.
- **The scroll:** every place is a marker over the painting. Press one for its card.
  - **Azure Cloud Town** (blue): **Return to town**. You come back in just inside the gate.
  - **A hunting ground:** its realms and text, and one of:
    - **Open** (gold; green when it is your own realm's ground): **Set out alone**.
    - **Resting** or **Injured** (amber): the realm is right but you can't set out yet, and the card says for how long.
    - **Sealed** (grey, *Needs …*): your realm is too low. It shows the realm it needs.
  - **Hunt with a team** opens the team pages (`/explore`): teams still use the lobby.
- **Setting out** (`POST /world/go/<key>`) is a Solo Hunt on that ground's walkable map (docs/hunting.md "The
  map"): it starts the shared 30-minute explore rest.
- **Back from a hunting ground:** walk back onto the path you came in by (a ring of pale blue light; it wakes once
  you've walked away from it) and press **E**: *Leave …? Head home* is the same as the **Return home** button. The
  result page's **Back to the World Map** brings you back to the scroll.

## The server decides

The page only shows and hides cards. `/world/go` makes every check again, whatever the page showed: the ground's
lowest realm or higher (`hunting.eligible`), not injured, not resting (`Hunts.blocked`). If one fails, nothing is
started (no party left behind, no rest) and the scroll says why. In a team, or already out hunting, `/world` sends
you to `/hunt`. A Solo Hunt still on the "choose a ground" page is dropped when you open the scroll.

## The scroll

- **The picture:** SHOAIB's Gemini painting of the whole land on a silk scroll. `scripts/make_world_map.py` removes
  Gemini's sparkle (looked for just inside the paper's bottom-right corner, painted over from the paper around it)
  and cuts the scroll out of its grey backdrop (GrabCut, the paper's straight edges smoothed), so it sits on the
  page's dark ground. To replace it: `python -m scripts.make_world_map new_map.png` (add `sparkle=x,y,r` if the star
  is somewhere else).
- **The markers:** `world.AT` gives each place's spot on the picture as shares of its width and height (0..1). A new
  painting with the places moved needs these moved too. The names, glow and locks are drawn by the page, as Gemini
  garbles writing.

## Still to come

The plan for the world, in order: the Outskirts (a walkable map just outside the gate, with the herb meadow and a
waystone to the scroll), then a walkable map for each hunting ground still drawn in code, built from small pieces
(ground tiles, trees, rocks, a landmark) like the town, then a doorway effect video and a realm seal for locked places.
