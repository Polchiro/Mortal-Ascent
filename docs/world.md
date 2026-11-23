# The world: walking from the town to the wilds, and the World Map

The town, the Crossroads and the Moon Forest are **one world you walk through**. Walk out of **Azure Cloud Town**'s
gate and you are on **the Crossroads**; walk down the Moon Forest road and you are in the **Moon Forest**, three
large lands deep. No menus,
no "Enter" button: reaching the gate or the end of a road takes you through. Herbs grow at random spots to pick,
beasts roam the forest, and now and then something glints in the grass. The **World Map** (press **M**) is only a
picture of the land: you can't travel from it.

Nothing here adds rewards or changes the game's numbers. Every herb, beast and find is the bot's own: the gathering
round (`bot/gathering.py`), the hunting ground's beasts and odds (`hunting.py`), `/explore`'s finds and their loot
(`bot/expedition.py`), the 5 encounters and the 30-minute rest. Discord's commands are unchanged.

```
 Azure Cloud Town ═gate═► THE CROSSROADS ═road═► FOREST EDGE ═path═► DEEP WOODS ═path═► SHRINE GROVE
   safe: no herbs,          60 x 60 tiles          70 x 70             70 x 70             70 x 70
   your trip is              herbs                  └────────── Moon Forest: herbs, beasts, finds ──────────┘
   banked here               (no beasts)                        (one trip of 5 encounters across all three)
                                └── the other five roads: closed, "not open yet"
```

**The land is empty for now, on purpose.** Outside the town there is only ground: grass, forest floor, dirt roads
and paths, a paved junction and clearings. The lands are laid out and sized first so the world can be walked and
judged; trees, rocks and buildings are then placed on it piece by piece. The earlier painted Moon Forest clearing and
its pieces (docs/environment.md) are set aside until then (team hunts still use that painting, docs/hunting.md).
Walking from the town gate to the Shrine Grove takes about four minutes.

Code: `web/land.py` (the lands: size, ground, paths, gates), `scripts/make_land.py` (paints their ground),
`web/overworld.py` (the places, the entrances, what grows and roams, the checks), `web/world_routes.py` (the
pages and `/world/...` requests), `web/static/town.js` (the one script that walks every place),
`web/templates/_walkui.html`, `town.html`, `place.html`; the trip in `web/hunt_play.py` (`world_fight`, `world_find`,
`world_home`). Tests: `tests/test_overworld.py`, `tests/test_web_gather.py`, `tests/test_crossroads.py`.

## The lands (`web/land.py`)

- **A land** is a diamond of the town's own 2:1 tiles, any size (`LANDS[key]["size"]`). Its entry says what the
  ground is: the base texture, the paths (waypoints, drawn as smooth curves), round patches of other ground
  (clearings, the paved junction), its light (`tint`), and its gates.
- **The ground is painted in code** from the town's four textures (grass, dirt, forest floor, stone paving):
  `python -m scripts.make_land` (or `python -m scripts.make_land forest_edge` for one; about a minute each). Change
  a path or a size in `land.py`, run it, and the land is repainted.
- **In chunks.** The picture of a 70-tile land would be 8960 x 4480 px, so it is cut into 1024 px squares
  (`art/maps/land/<key>/c_<col>_<row>.webp`, about 1 MB a land in all). The page fetches only the squares near the
  camera, over a small preview of the whole land. A land can be as big as you like at no cost to the player.
- **One size everywhere.** Every land is drawn as big against you as the town is (`land.SCALE` 1.4), so grass, paths
  and later trees are the same size from the gate to the grove. Outside the town the camera stands further back
  (`land.ZOOM` 0.7): you see more land around you.
- **Everything is walkable** except the dark rim (`edge` tiles in from the diamond's side) and, on the Crossroads,
  the town's wall and gate. Nothing else stands there yet.
- **Adding a land:** an entry in `LANDS` with a gate on the edge facing its neighbour, one line in
  `overworld.ENTRANCES` (`_join`) and, for a new region, its key in `overworld.WILD`. Then paint it.

## Walking between places

- **Entrances** (`overworld.ENTRANCES`): the town gate ↔ the Crossroads' gate; the Moon Forest road ↔ Forest Edge;
  Forest Edge ↔ Deep Woods; Deep Woods ↔ Shrine Grove. Each is the **mouth** of a road at a land's edge: walk out
  through it (anywhere across the road's width) and a short fade takes you to the next land. The page doesn't
  reload: the script swaps the map (`load`).
- **You keep walking.** You come out as far to the side of the road as you went in, facing the same way, with your
  keys still held, so you walk straight on. A land's gate is always on the edge opposite its partner's, and the road
  carries on past the rim in the same ground, so the next land picks it up.
- **You can't bounce.** You arrive a couple of tiles inside, and the mouth only takes you when you walk back out to it.
- **The server knows where you are.** The page reports your position (`/world/pos`); the server checks each step could
  really be walked (the hunting map's speed check) and that you are in the mouth before letting you through
  (`/world/move`). Typing `/wild/deep_woods` in the address bar while you stand in town just shows you the town.
- **Reload or come back later:** you are where you were (for 30 minutes, `FRESH`; after that, at the start of the
  place you open).
- **A restart keeps where you stood.** Your place and spot are saved in the database (`world_spots`: place, x, y,
  time), when you come into a place and at most every 10 seconds while you walk (`SAVE_EVERY`). After the website
  restarts, opening any map page puts you back there (`World.restore`). Only the place and spot are kept: a trip under
  way still ends with a restart, as a hunt does, and herbs simply grow again.
- **The five other roads are closed.** Mist lies over each, *Not open yet*, until its land is built. Nothing starts
  there: the old menu hunt is gone from the roads (`/crossroads/go` no longer exists). A road above your realm
  still shows its seal.

## Herbs (the Crossroads and the Moon Forest)

- **Where:** glowing herbs (10 at a time on the Crossroads, 14 in each forest land), at random spots anywhere off
  the paths, never by an entrance. The lands are far bigger than before, so herbs are further apart. **Each player has
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

## Beasts and finds (the Moon Forest's three lands)

- **A trip** is the open world's expedition: it starts with your first encounter, holds **5 encounters**
  (`hunting.MAX_ENCOUNTERS`), and starts the **30-minute explore rest** when it starts, exactly as a hunt or
  `/explore` does. Beasts and finds both count. A line at the bottom shows *Trip: 2 of 5 · HP · what you carry*.
- **Beasts:** five roam each land. Come near and one may notice you (a **!**), then charge: that is the fight. Or
  walk up and press **E** to attack first. The fight is the hunt's own fight screen, with the same beast strength
  and the same rewards. Win and you are back on the same spot, HP and loot carried on.
- **Which beasts:** for each step of the trip the server makes **one** roll with the hunt's own odds
  (`hunting.tier_odds`): in each land one beast is that kind and the rest are Normal, and walking from land to land
  doesn't roll again. So an Elite or a Beast King is on offer no more often than a hunt would meet one.
- **Finds:** a soft golden glint, one at a time in each land, sometimes at one of its secret spots (the far
  clearings at the ends of the side paths). Press **E**: it
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
- Teams still gather in the lobby (`/explore`) and hunt the old way.
- A look without a walking sheet can read the town's list and use Discord's `/gather` and `/explore`.
- Your herbs, beasts and finds are kept in the website's memory: a restart rolls them again (a trip under way ends
  as a hunt does). Where you stand is saved (above).

## Other players

Everyone walking the same place sees each other: their own walking sheet (male or female), their name in blue and
their realm and layer over their head, walking smoothly to where the server last saw them. The page asks
`/world/others` about once a second; the server answers the others in your place whose page spoke to it in the last
15 seconds (`OTHERS_FRESH`; a closed tab fades out), the nearest 30 at most (`OTHERS_MAX`). They are shown by a
random tag, never by their Discord id. Seeing is all for now: no talking, trading or fighting each other on the map,
and they don't block your way. Code: `World.others` in `web/overworld.py`, `pollOthers` / `drawOther` in `town.js`.

## How many players

`python -m scripts.load_test` measures it: it starts its own copy of the website with a throw-away database, logs in
50, 100, 200, 300 and 500 test players, stands them all in the town and has each "page" send what a walking page
sends, then reports how long the server takes to answer (`--idle 0.5`: half of them standing still; `--place`:
another land). Measured on a 2-core machine shared with the test's own fake players (Nov 2026), everyone walking
non-stop:

| Players in one place | Before | Now |
|---|---|---|
| 50 | smooth | smooth |
| 100 | laggy (1 answer in 20 took 0.5 s) | smooth (8 ms) |
| 200 | broken (1 s) | smooth (76 ms) |
| 300 | broken | ok (0.2 s) |
| 500 | broken | broken (1.1 s) |

What made the difference:
- **The database is set up once**, not on every connection (`bot/db.py` `connect`): making the tables and renaming
  old data read whole tables, and the website connects for every request. That was three quarters of the server's work.
- **A step needs no database** (`/world/pos`, `/world/others`): they only touch the world in memory. Where you stand
  is still saved every 10 seconds, on its own connection, outside the world's lock.
- **One message instead of two while walking:** the answer to your step also says who else is here (about once a
  second), so a walking page no longer asks separately; a page standing still asks once a second. Steps are sent
  every 0.4 s (was 0.3 s).

The limit now is one processor core running one copy of the website (about 700 answers a second on that machine).
Past roughly 300 players walking at once, the next steps are channels (several copies of a place, about 40 players
each, so nobody's screen is a crowd) and more than one copy of the website, which needs the world's memory shared
between them. Not built yet.

## Today's tasks

Three tasks a day, the same all day and new at **midnight UTC**, picked for each player from five
(`web/world_tasks.py`, `TASKS`):

| Task | Counts | Pays (Mortal; × realm) |
|---|---|---|
| Pick 5 herbs out in the world | a herb gathered (not a look-alike or a miss) | 🪷 120 |
| Defeat 2 beasts in the Moon Forest | a beast beaten out in the world | 🪷 150 |
| Look into 2 glints in the grass | a find looked into | 🪷 120 |
| Walk all the way to the Shrine Grove | coming into the Shrine Grove | 🪷 100 |
| Bring a trip's finds home to town | a trip banked at the town gate | 🪷 120 |

- A task **pays the moment it is done**; finishing all three adds 🪷 150 (`ALL_DONE_COINS`). Coins grow with the realm
  exactly like the Discord quests (`bot/quests.coin_scale`: Mortal ×1 ... Martial Saint ×3.5). Every payment is in the
  ledger ("World task: ...").
- Progress is counted in the existing `daily_counts` table as `world:<task>`.
- They are separate from the Discord `/daily` quests, which are unchanged; the same herb or beast counts for both.
- On the map: **Today's Tasks** at the top right (click its title to fold it; folded at first on a phone), and a line
  with a bell when one is done.

## Sound

Made in the browser (`web/static/sound.js`, Web Audio, no sound files but the footsteps). Each kind of place has its own bed, which
crossfades as you walk on: the town (soft wind, the street's murmur, wind chimes), the Crossroads (wind over grass,
a few crickets, birds) and the Moon Forest (wind in the trees, crickets all round, a far-off owl, a creaking branch).
Little sounds: footsteps (recorded, see below; stone in town, earth outside), a whoosh into the next land, a growl when a beast notices
you (deeper for an Elite or a Beast King), kneeling at a herb, a chime when it is picked (a dull note when not), a
glint's sparkle and a bell for a finished task. **Settings** (the gear) has Sound On / Off, a volume and Music On / Off,
kept on the device. Browsers allow sound only after a click or key press, so it starts with your first one, and it goes quiet
while the tab is hidden.

**Footsteps from the videos (Nov 23).** SHOAIB's walking and running videos carry sound: one footfall after
another. `python -m scripts.make_step_sound run front.mp4 ...` finds the footfalls, keeps the six most ordinary
clean ones (from as many of the videos as it can), and writes them as `art/fx/sounds/step_run_1..6.mp3` (0.3 s each,
about 4 KB), listed by gait in `art/fx/sounds/steps.json`. On every footfall (twice a stride, as before) `town.js`
tells `sound.js` the ground and the gait (`step('stone' | 'earth', 'run' | 'walk')`), and it plays one of that
gait's takes: never the same twice running, a little different in pitch and loudness each time, duller and softer
on earth than on the town's stone. Running steps are from her five running videos. **Walking has no takes of its
own yet** (her walk videos were not given with them): until `make_step_sound walk ...` is run on them, a walking
step plays a running take, quieter and a little lower. With no takes at all (or before they have loaded) the step
made in code is kept.

**Music.** Over each bed a quiet tune plays, made up as it goes (no recording): plucked strings in the manner of a
guzheng on a five-note scale, a low string at the start of each phrase and a bamboo flute now and then, with rests
between phrases. The town is warm and unhurried, the Crossroads open and light, the forest slow, low and sparse
(`MUSIC` in `sound.js`: each place's root note, scale, pace, phrase and rest lengths). Music On / Off in Settings
turns only the tune off; the wind, crickets and little sounds stay.

**Talking.** Walking up to someone and pressing E unrolls a scroll and plays a few notes of their "voice" (no
words): each of the town's people has their own pitch and manner (`VOICES` in `sound.js`, by the NPC's key), and
some a sound of their trade (the blacksmith's anvil, the merchant's coins, Lan's dried herbs, the Arena's gong; the
Stone Stele grinds like stone, a road's end sighs with wind). A choice clicks; leaving rustles.

## The Crossroads (`/crossroads`)

Code: `web/crossroads.py` (the wall and gate, the roads' ends), its land in `web/land.py`, the page in
`web/world_routes.py`, `web/templates/place.html`. Tests: `tests/test_crossroads.py`.

- **An open meadow, 60 x 60 tiles,** with a paved junction in the middle and seven winding dirt roads: one from the
  town gate and one to each hunting ground, at the land's edge in its direction on the World Map (Celestial Forbidden
  Lands up the top corner, Frostpeak north-west, Thunderfall north-east, Crimson Gorge east, the Ancient Battlefield
  south-east, Moon Forest south). Toward the Moon Forest road the forest's floor creeps into the grass.
- **The only things standing on it** are the town's own wall and gate along the x0 edge, seen from outside.
- **The ways out:**

| Way out | What it does |
|---|---|
| The town gate (its doorway lit blue) | walk in: you are in town (a trip is banked) |
| The Moon Forest road | walk off its end: you are in the forest's edge |
| The other five roads | mist, *Not open yet*; or the seal of runes if your realm is too low |

- **Teams** still gather and set out from `/explore` (the Gate Warden's **Hunt with a team**), on the old hunting map.

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

- **Objects, in rounds:** SHOAIB makes a batch (trees first), they are placed by hand, he looks, we adjust. Trees and
  rocks will block the way and hide you as the town's buildings do (the drawing and collision code is already there).
- **The painted Moon Forest clearing** back as a landmark inside the forest, if still wanted.
- **SHOAIB's picking animations** for kneeling at a herb.
- **The other five hunting grounds** as lands of their own (`REGION_HERB_TYPES` is ready), then `/explore`'s
  remaining encounters.
