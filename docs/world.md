# The world: walking from the town to the wilds, and the World Map

The town, the Crossroads and the Moon Forest are **one world you walk through**. Walk out of **Azure Cloud Town**'s
gate and you are on **the Crossroads**; walk down the Moon Forest road and you are in the **Moon Forest**. No menus,
no "Enter" button: reaching the gate or the end of a road takes you through. Herbs grow at random spots to pick,
beasts roam the forest, and now and then something glints in the grass. The **World Map** (press **M**) is only a
picture of the land: you can't travel from it.

Nothing here adds rewards or changes the game's numbers. Every herb, beast and find is the bot's own: the gathering
round (`bot/gathering.py`), the hunting ground's beasts and odds (`hunting.py`), `/explore`'s finds and their loot
(`bot/expedition.py`), the 5 encounters and the 30-minute rest. Discord's commands are unchanged.

```
 Azure Cloud Town ══the gate══► THE CROSSROADS ══the Moon Forest road══► MOON FOREST
   safe: no herbs,                 herbs to pick                          herbs, beasts, finds
   your trip is banked here        (no beasts)                            (a trip of 5 encounters)
                                       └── the other five roads: still the old Solo Hunt (below)
```

Code: `web/overworld.py` (the places, the entrances, what grows and roams, the checks), `web/world_routes.py` (the
pages and `/world/...` requests), `web/static/town.js` (the one script that walks every place),
`web/templates/_walkui.html`, `town.html`, `place.html`; the trip in `web/hunt_play.py` (`world_fight`, `world_find`,
`world_home`). Tests: `tests/test_overworld.py`, `tests/test_web_gather.py`, `tests/test_crossroads.py`.

## Walking between places

- **Entrances** (`overworld.ENTRANCES`): the town gate ↔ the Crossroads' gate; the end of the Moon Forest road ↔ the
  forest's path out. Walk within `TRIGGER` (0.75 tiles) of one and the screen fades to the next place, a few steps
  in from the matching entrance. The page doesn't reload: the script swaps the map (`load`), so it is quick.
- **You can't bounce.** An entrance only works after you have walked a little away from where you arrived.
- **The server knows where you are.** The page reports your position (`/world/pos`); the server checks each step could
  really be walked (the hunting map's speed check) and that you are at the entrance before letting you through
  (`/world/move`). Typing `/wild/moon_forest` in the address bar while you stand in town just shows you the town.
- **Reload or come back later:** you are where you were (for 30 minutes, `FRESH`; after that, or after the website
  restarts, in town).
- **A place you can't enter:** a road whose realm you haven't reached stays sealed, as before.

## Herbs (the Crossroads and the Moon Forest)

- **Where:** a few glowing herbs at a time (5 on the Crossroads, 6 in the forest), at random spots inside each place's
  herb areas (`PLACES[...]["herbs"]["areas"]`), never on a rock, in the pond, or by an entrance. **Each player has
  their own herbs**: nobody can take yours.
- **Picking one:** walk up (within 1.6 tiles) and press **E**. A panel opens over the map with **one round of the
  gathering game**: the herb to find, the look-alike plants, the timer. Right pick → the herb goes in your bag;
  wrong or too slow → it is lost, exactly as in `/gather` (poisonous look-alikes, the Herbal Insight streak, the
  Wandering Spirit check and old herbs all work the same; it is the same `Gathering` object).
- **Which herb:** its **grade** follows your realm as always (`alchemy.herb_grade_odds`), so rare herbs are exactly as
  rare as in `/gather`. Its **type** follows the region (`alchemy.REGION_HERB_TYPES`):

| Region | Qi | Healing | Purity | Breakthrough |
|---|---|---|---|---|
| `/gather` in Discord (unchanged) | 30% | 20% | 35% | 15% |
| The Crossroads | 40% | 30% | 25% | 5% |
| Moon Forest | 25% | 35% | 30% | 10% |

  (The other five regions have their rows ready for when their maps are built.) The glow shows the grade's colour
  and the plant's picture, so you can see a rare one from across the clearing.
- **Growing back:** a picked (or lost) herb regrows at a **different** random spot 45 to 90 seconds later
  (`HERB_REGROW`). Walking from herb to herb is what limits you: about 4 a minute at the very best, which is
  fewer than the old Gather page gave, so herbs are not easier to farm than before.
- **Beasts never interrupt.** While the gathering panel (or a find, or a dialogue) is open, beasts stand still and
  can't start a fight. The server refuses one too.
- **No limit from the trip.** Herbs can be picked while resting, injured, or with the trip's encounters spent.
- **The Gather page is gone from the website** (`/gather` sends you to town with a note; the Gather tab and the Gate
  Warden's "Gather herbs" are removed). Discord's `/gather` is untouched.

## Beasts and finds (the Moon Forest)

- **A trip** is the open world's expedition: it starts with your first encounter, holds **5 encounters**
  (`hunting.MAX_ENCOUNTERS`), and starts the **30-minute explore rest** when it starts, exactly as a hunt or
  `/explore` does. Beasts and finds both count. A line at the bottom shows *Trip: 2 of 5 · HP · what you carry*.
- **Beasts:** three roam the forest. Come near and one may notice you (a **!**), then charge: that is the fight. Or
  walk up and press **E** to attack first. The fight is the hunt's own fight screen, with the same beast strength
  and the same rewards. Win and you are back on the same spot, HP and loot carried on.
- **Which beasts:** for each step of the trip the server makes **one** roll with the hunt's own odds
  (`hunting.tier_odds`): one of the three is that kind, the other two are Normal. So an Elite or a Beast King is on
  offer no more often than a hunt would meet one.
- **Finds:** a soft golden glint, one at a time, sometimes at one of the forest's four secret spots. Press **E**: it
  is one of `/explore`'s own finds with `/explore`'s own loot: a treasure chest, a herb patch, a peaceful clearing,
  an ore vein, a stone tablet, a blessed land or a wandering hermit (`overworld.FINDS`, at their `/explore` odds
  among themselves; a secret spot gives only the last three). A new one appears elsewhere 4 to 8 minutes later.
- **Banking:** what you win is **carried** until you walk back through the **town gate**; then it is added to your
  bag (`Expedition.finish`, the same as Return home). A banner in town lists it.
- **Defeat:** the hunt's own rule: half the carried coins and herbs are lost, you are injured, and you wake in town.
- **After 5 encounters,** or while **resting** or **injured**: the beasts keep their distance (they back away, and
  can't be attacked), nothing glints, and a line says why. You can still walk everywhere and pick herbs. A new trip
  can start when the rest is over.
- **Left the page mid-trip?** After the hunt's idle time the trip ends by itself and banks what you carried.
- **The server referees:** you must be standing near the beast or the find (`hunt_map.engaged`, `HERB_REACH`), each
  can be used once, and the 5-encounter cap, the rest and injuries are checked on the server for every request.

### Not in this first version

- `/explore`'s other encounters (bandits, hazards, merchants, strangers, beast lairs) need a choice screen of their
  own; they come later. Until then the forest's finds are the seven above.
- You choose which encounters to take (walk past a beast, look for glints), so a trip's mix can differ from
  `/explore`'s. The total is still 5 per rest.
- Teams still gather in the lobby (`/explore`) and hunt the old way. Other players are not shown on the map.
- A look without a walking sheet can read the town's list and use Discord's `/gather` and `/explore`.
- Where you stand and your herbs are kept in the website's memory: a restart puts everyone back in town (a trip
  under way ends as a hunt does).

## The Crossroads (`/crossroads`)

Code: `web/crossroads.py` (the layout, the roads), the page in `web/world_routes.py`, `web/templates/place.html`.
Tests: `tests/test_crossroads.py`.

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
- **The ways out:**

| Way out | Where | What it does |
|---|---|---|
| The town gate | the top-left edge; its doorway lit blue | walk in: you are in town (a trip is banked) |
| The Moon Forest road | the south edge | walk off its end: you are in the Moon Forest |
| The other five roads | the map's edge in each one's direction on the World Map | walk up and press **E**: **Enter …** starts the old Solo Hunt there (`POST /crossroads/go/<key>`, docs/hunting.md), until that ground gets its own map |

- **A road's end** carries the place's name and realms: **open** (a ring of warm light), **resting / injured** (grey
  mist, for the five old roads) or **sealed** (a turning disc of golden runes, *Sealed: needs …*: your realm is too
  low). The server checks again whatever the page showed.
- **Teams** still gather and set out from `/explore` (the Gate Warden's **Hunt with a team**).

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

- **The Crossroads' look:** its trees are the town's and were scattered by code; SHOAIB is making new pieces (or a
  painting) for it, with the signpost, bamboo, meadow flowers and road markers.
- **SHOAIB's picking animations** for kneeling at a herb.
- **The other five hunting grounds as walkable places,** each with its herbs (`REGION_HERB_TYPES` is ready), then
  `/explore`'s remaining encounters.
