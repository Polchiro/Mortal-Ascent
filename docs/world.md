# The world: the Crossroads, the roads and the World Map

You travel by **walking**. Out of **Azure Cloud Town**'s gate lies **the Crossroads**, and from it a road leads to
each hunting ground. The **World Map** is a painted scroll you open to see where everything is (press **M**). It is
only a map: you can't travel from it. Nothing here adds rules. A hunting ground is the hunting grounds' own
(docs/hunting.md), and going down its road is a Solo Hunt with the same checks, beasts, rest and rewards.

```
 Azure Cloud Town ══the gate══► THE CROSSROADS ──a road──► a hunting ground (its walkable map)
        ▲                           │      ▲                          │
        └──── the gate (E) ─────────┘      └─ the path home (E) / Return home ┘
```

## The Crossroads (`/crossroads`)

Code: `web/crossroads.py` (the layout, the roads), the `/crossroads` routes in `web/hunt_routes.py`,
`web/templates/crossroads.html`. It is walked by the town's own page script (`web/static/town.js`), which gets
the same kind of data. Tests: `tests/test_crossroads.py`.

- **Built like the town, from the town's pieces.** The ground is painted in code from the town's textures by
  `python -m scripts.make_town_ground crossroads` (`art/maps/crossroads.webp`): grass, the forest floor beyond the
  rim, and the dirt roads (`GROUND["roads"]`: segments at any angle, `ROAD_W` wide). On it stand:
  - the town wall and gate along the top-left edge, seen from outside, with the gate's doors at `DOOR`;
  - a forest of pines, bushes, blossom trees and boulders round the rim (`_forest`: placed once, the same every
    time, never on a road, by a road's end or before the wall, and further from a road on the side nearer the
    camera, so a crown doesn't hide you);
  - lantern posts at the junction.
  The pieces SHOAIB is making (a signpost for the junction, bamboo for the Moon Forest road's edge, meadow flowers,
  road-marker pillars) drop in when they come.
- **Same size and feel as the town:** the same 2:1 tiles, `SCALE`, camera, night and walking. You come out of the gate
  (`START`, a few steps down its road). Back from a hunt, you stand at the end of the road you came along.
- **The ways out** (`EXITS`: walk up and press **E**, like talking to the townsfolk):

| Way out | Where | What it does |
|---|---|---|
| The town gate | the top-left edge; its doorway lit blue | **Enter the town** (`/town`, just inside the gate) |
| Each hunting ground's road | the map's edge in its direction on the World Map: Celestial Forbidden Lands up the top corner, Frostpeak north-west, Thunderfall north-east, Crimson Gorge east, the Ancient Battlefield south-east, Moon Forest south | see below |

- **A road's end** carries the place's name and realms, and is one of:
  - **Open** (a ring of warm light): **Enter …** starts the Solo Hunt there (`POST /crossroads/go/<key>`), and the
    30-minute explore rest. You walk its map (docs/hunting.md "The map").
  - **Resting / Injured** (grey mist): your realm is right but you can't set out yet, and it says for how long.
  - **Sealed** (a turning disc of golden runes, *Sealed: needs …*): your realm is too low.
  Each road carries on past its end off the map (`ROAD_ON`), so it looks like it goes somewhere.
- **The server decides.** `/crossroads/go` makes every check again, whatever the page showed: the ground's lowest
  realm or higher (`hunting.eligible`), not injured, not resting (`Hunts.blocked`). If one fails, nothing is started
  (no party left behind, no rest) and you're back at that road's end with the reason. In a team, or already out
  hunting, `/crossroads` sends you to `/hunt`. A Solo Hunt still choosing its ground is dropped. Walking about
  changes nothing in the game, so, as in town, the server doesn't follow where you walk.
- **A look without a walking sheet** sees the ground and chooses a road (or the gate) from a list.
- **Teams** still gather and set out from `/explore` (the Gate Warden's **Hunt with a team**).

## Coming back

On a hunting ground the path you came in by glows. Walk away and back onto it and press **E**: **Head home** is the
same as **Return home**. The result page leads **Back to the Crossroads**, to the end of that road
(`/crossroads?near=road_<key>`). From there the gate takes you into town.

## The town gate

Walk to the gate and its doorway lights up. **Leave town** (**E**) → *The Town Gate* → **Go out to the Crossroads**.
See docs/town.md "Going out".

## The World Map (`/world`)

Code: `web/world.py`, `web/templates/world.html`, `web/static/world.js`. The picture: `art/maps/world.webp`, cut by
`scripts/make_world_map.py`. Tests: `tests/test_world.py`.

- **Opening it:** press **M** in town, on the Crossroads or on a hunting ground, or use the **World Map** button. You
  can also ask the Gate Warden. **Back**, **M** or **Esc** takes you back where you were. It opens from anywhere, even
  mid-hunt, and changes nothing.
- **The markers:** Azure Cloud Town (blue), and each hunting ground: gold when open (green for your own realm's),
  amber when you're resting or injured, grey and *Needs …* when sealed. Press one for its card: what lives there,
  whether you may enter, and that its road starts at the Crossroads.
- **The picture:** SHOAIB's Gemini painting of the whole land on a silk scroll. `scripts/make_world_map.py` removes
  Gemini's sparkle (looked for just inside the paper's bottom-right corner, painted over from the paper around it)
  and cuts the scroll out of its grey backdrop (GrabCut, the paper's straight edges smoothed). To replace it:
  `python -m scripts.make_world_map new_map.png` (add `sparkle=x,y,r` if the star is elsewhere). `world.AT` gives each
  place's spot on the picture (shares of its width and height). A new painting with places moved needs these moved.
- **On a phone** the scroll is wider than the screen: swipe across it.

## Still to come

- **SHOAIB's pieces for the Crossroads:** the signpost, bamboo, meadow flowers, road markers, and the rune seal video.
- **Herbs to pick on the map,** each a round of the existing gathering game (bot/gathering.py), with his picking
  animations.
- **A walkable map for each hunting ground** still drawn in code (all but Moon Forest), each with its entrance on the
  side its road comes from.
