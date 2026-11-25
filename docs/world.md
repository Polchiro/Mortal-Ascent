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
                              ╚═road═► THE IRONVEIN QUARRY (40 x 40, safe: seams to mine)
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

## Running

The player chooses whether to **run or walk** (Nov 24, `town.js` `gait`), the same way on a phone and a computer:

- the round **Run / Walk button** at the bottom right, above the dock (it shows the current one; one tap switches);
- **R** on a keyboard; **Shift** held gives the other one for as long as it is held;
- **Settings** (the gear): Movement, Run or Walk.

The choice is kept on the device (`localStorage` `ma.gait`); running is the default. **Walking** is the speed the
maps always had (`SPEED`, 150 screen px a second) with the walk frames and walking footsteps. **Running** is
`RUN_K` = 1.25 times that, with the run frames (where the look has them) and running footsteps. The joystick pushed
gently slows either, as before. The old Shift "stroll" (0.45 of full speed) is gone: walking is the slow choice now.

Two things were set against that speed. The server's check on reported positions (`hunt_map.SPEED`, tiles a second,
with its slack) now allows for a run, so a runner isn't snapped back. And a run (4.25 tiles a second straight up) is
kept a little under a hunting beast's chase (4.4 for an ordinary beast, more for elites and kings), so a beast that
has seen you still catches you: running gets you about the map sooner, it is not a way out of every fight. Other
players are shown running when they move faster than midway between the two speeds.

## Herbs (the Crossroads and the Moon Forest)

- **Where:** glowing herbs (10 at a time on the Crossroads, 14 in each forest land), at random spots anywhere off
  the paths, never by an entrance. The lands are far bigger than before, so herbs are further apart. **Each player has
  their own herbs**: nobody can take yours.
- **On the map** each herb is its own painting (art/herbs/, one per herb), rooted where it grew: its foot on the
  spot, a soft shadow, swaying a little from its base. Its grade shows from afar by more than colour: a Mortal herb
  is plain and small; Yellow is bigger with a warm glow; Mystic glows and sheds rising motes; round an Earth herb a
  ring ripples out over the ground; a Heaven herb stands under a thin pillar of light. Within 4 tiles a label says
  how rare it is and what kind (*Uncommon qi herb*), **not which plant**: you learn that by kneeling.
- **Picking one:** walk up (within 1.6 tiles) and press **E**. You **kneel** (the hero's own kneeling animation, cut
  from SHOAIB's video, with its sound), the camera eases in, and a **close-up** opens low on the screen (a bottom
  sheet on a phone) with **one round of the gathering game**: the herb to find and its description, the grade's four
  plants as paintings with their looks, and the timer as an incense stick burning down. Pick with a click, a tap or
  **1-4**; *Walk away* sits in the corner, away from the plants. Right pick → your hands lift, the herb rises out of
  them with a few clods of soil and goes in your bag; wrong or too slow → it is lost, exactly as in `/gather` (the
  Herbal Insight streak, the Wandering Spirit check and old herbs all work the same; it is the same `Gathering`
  object). *Walk on* and you stand back up.
- **The clock is fair.** The kneel plays before the round is asked for, and the four paintings come **inside** the
  round (web/gather_art.py `choice`, as data: addresses), so the page has every picture before the timer matters.
  (They used to be fetched one by one after the server's clock had started.) No address names a plant.
- **Where each herb sprouts** (`overworld.HABITAT`): which herb grows is rolled as always; only its **spot** follows
  its habitat. Grasses, ginsengs and flowers stand in open grass; berries, mushrooms and moss on the forest's floor;
  roots by a road or path; lotuses, lilies, the peach and Star Dew in clearings among the trees. With no room on
  ground that suits it, a herb sprouts anywhere herbs may, so the odds never depend on the land.
- **Old herbs sink.** A 100-year+ herb trembles and sinks into the earth on the map as its (shorter) time runs out;
  lost, it goes under in a puff of dust. Any other lost herb wilts grey. This only draws the server's timer.
- **What you see when you get one:** the result shows the herb's **age as rings** (1 to 5: 10 to 1000 years), and
  anything found beside it as a chip with its picture: a spring wells up from the ground for Spring Water, jade glints
  in the turned soil for a Jade Shard (the same 8% and 3% as ever, `bot/gathering.py` `found`).
- **The Wandering Spirit** stands on the map beside the herb you knelt at, pale in its mist; the close-up holds the
  signs to press. Same check, same rules.
- **Quick gather** (Settings → Gathering → Quick, kept on the device): no kneeling, camera or pulling; the plants
  open at once. Reduced motion does the same.
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

## A heavenly phenomenon: shared rare herb events

A trial (SHOAIB approved it Nov 25 2026). **Website only**; ordinary gathering is untouched and every player keeps
their own herbs. Code: `web/herb_events.py` (the events and the claim), `World.gather_event` / `pick` in
`web/overworld.py`, `Gathers.pick(claim=)` / `call_off` in `web/gather_play.py`, `eventNews` / `drawEvent` in
`town.js`; table `world_events`. Tests: `tests/test_herb_events.py`. Switch it off with `MA_HERB_EVENTS=off`.

- **Twice a day** (UTC), at random moments, a light rises somewhere in the **Moon Forest**: one spirit herb everyone
  can see, at one of the three lands' far clearings (`PER_DAY`, the lands' `secret` spots). It stands **20 minutes**
  (`MINUTES`) unless someone pulls it free.
- **Everyone on the website is told**, wherever they are: a bell, the line *A strange light rises over the Moon
  Forest*, and a small bar at the top with the minutes left. Not which land, not the spot, not the herb.
- **Finding it:** on its own land a pillar of light stands over it (SHOAIB's video, added as light, with a beam
  carrying on up so it shows from far off). The bar says whether it is in this part of the forest or another.
- **Kneeling:** the ordinary round, your own four plants, the old-herb rules (it is **500 years old**: `AGE`). The
  Wandering Spirit never interrupts it. Each player may kneel at each event once.
- **The first right answer the server handles pulls it free.** It gives a 500-year herb of the event's type, at the
  **grade the claimant's own realm rolls**, so it is worth having at every realm. The claim is one database update
  that only succeeds while nobody has claimed it and it hasn't ended: two right answers at once cannot both win.
- **Beaten to it?** Your round is called off at no cost: nothing lost, your streak kept. A wrong or slow pick costs
  what it always does, and the herb stays for the others.
- **One claim a day** per player (`WINS_PER_DAY`), so no one takes them all.
- **A restart keeps the events** (they are in the database); who has knelt at which is kept in memory.
- **Not yet:** nothing is posted to Discord; other lands' edges don't glow toward it (the bar's words do that job);
  other players aren't drawn kneeling.

## The Ironvein Quarry (`/wild/ironvein_quarry`)

A small safe land where forging materials are mined (SHOAIB approved the rules Nov 25 2026). **Website only:**
Discord's `/explore` keeps its Ore Vein encounter, and no Discord command changed.

Code: `web/quarry.py` (what stands on the land, the seams' spots, the keeper), `web/mine_play.py` (the referee),
the numbers in `forge.py` (`SEAM_KINDS`, `SEAMS`, `SEAMS_PER_DAY`) and `bot/materials.roll_seam`; on the page
`town.js` (`mine`, `strike`, `drawSeam`). Tests: `tests/test_web_mine.py`.

- **Getting there:** a new road leaves the town-gate road on the Crossroads and runs south to the land's edge
  (`road_quarry`); walk off its end, as for the Moon Forest. About a minute from the gate. The World Map has its marker.
- **The place:** 40 x 40 tiles of bare earth with a worked stone floor, rock walls round it, the keeper's hut by the
  way in and **Old Shen** leaning on his pick (talk to him: how it works, how many seams you have left today). No
  beasts, no herbs. Its own wind-over-stone sound and a slow tune.
- **Seams:** 8 at a time, each player's own, at the foot of the walls (`quarry.SPOTS`): **iron** (60% of seams),
  **coal** (30%), **jade** (10%). One that is dug opens again at another spot 2 to 4 minutes later.
- **Mining:** walk up (1.9 tiles) and press **E**. A small card says what it holds (*It holds Black Iron*). Strike
  with **E**, **Space** or the **Strike** button; hold to keep swinging. Iron and coal take 3 blows, jade 5. The hero
  swings the pick (SHOAIB's video, its own sound on each blow), chips fly, cracks spread, and on the last blow it
  breaks open: the materials pop out, with your pouch's new count. **Esc** steps back; a dig left half done waits 10
  minutes with its cracks. *Quick* in Settings: no swing animation, the blows land by themselves.
- **What a seam gives**, all at your realm's tier (as Beast Cores and every other material):

| Seam | Always | Sometimes |
|---|---|---|
| Iron | 1-2 weapon metal (Iron Ore ... Heavenly Gold) | 10% a fuel · 2% a Metal Shard |
| Coal | 1 fuel (Charcoal ... Sunflame Stone) | 5% a second |
| Jade | 1 artifact jade (Green ... Primordial Jade) | |

  The Prospector passive raises the "sometimes" chances, as everywhere. Materials go to the pouch (no bag slots).
- **24 seams a day** (`forge.SEAMS_PER_DAY`, new at midnight UTC, counted in `daily_counts` as `world:seams`). The
  count shows at the top left. After that the seams are dull: *The rock needs rest.*
- **The server referees**, as for Train and Practice. Starting on a seam makes the plan from a seed: its blows and
  **exactly what it holds, decided then**. The page notes each blow that lands (its own clock) and sends them when
  the seam breaks; the server checks there were enough, at least 0.42 s apart, that the dig took that long by its own
  clock, that you stand by the seam and that it wasn't dug before, then pays the plan. The blows change nothing about
  what you get. No tool to buy.
- **Not yet:** other players don't see you swinging; Blacksmith Tie doesn't mention the quarry; no daily task for it.

## Gathering art

`python -m scripts.make_gather_art` cuts SHOAIB's pictures and videos (Nov 25 2026) into what the map uses
(`web/gather_art.py` reads it):

| What | Where | From |
|---|---|---|
| The 20 herbs, each rooted in its soil | `art/herbs/<herb>.webp`, `catalog.json` (size, foot) | five pictures of four plants (a grade each) and four single Heaven herbs |
| Kneel, search, lift, rise (each hero) | `art/gather/hero_<gender>_kneel.webp` | an 8 s video on a flat backdrop, 12 pictures a second, blended on the page |
| One swing of the pick (each hero) | `art/gather/hero_<gender>_swing.webp` | the same, 24 pictures a second (for the quarry) |
| Sounds: kneeling, the hands in the leaves, rising, the pick's blows, the light pillar | `art/gather/sounds/*.mp3` | the videos' own sound |
| The pick, the quarry keeper | `art/gather/pick.webp`, `keeper.webp` | one picture each |
| Ponds, a mossy rock, the quarry's walls, seams and hut | `art/env/` (web/env.py `ASSETS`) | cut by `scripts/make_env_assets.py` |

`art/gather/sheets.json` says how each sheet is laid out: its cell, the point between the feet, frames, pictures a
second and **marks** (the frame where each part of the move begins). The hero in every frame is as tall as on the
walking sheets, so the page draws a move in place of the walk with nothing to line up (`town.js` `pose`).

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
| Pick 5 herbs out in the world | a herb gathered (not a wrong plant or a miss) | 🪷 120 |
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
gait's takes (his own first for the new male, Nov 25: `--voice male` cuts them from his walking and running videos
into `step_walk_male_*` / `step_run_male_*`, listed as `walk#male` / `run#male`; the map sets `MASound.voice` from
the sheet's `voice`; the hunting-ground map now plays running steps too): never the same twice running, a little different in pitch and loudness each time, duller and softer
on earth than on the town's stone. Running steps are from her five running videos; walking steps
(`step_walk_1..6.mp3`) from her front-right, right and back-right walking videos, the three with a quiet floor (her
front walk hisses and her back walk's steps are faint). A gait with no takes of its own would borrow the other's,
quieter and a little lower; with no takes at all (or before they have loaded) the step made in code is kept. A
party's hunting map (`hunt_map.html`, `huntmap.js`) has the same walking steps on earth.

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
- **Ponds and mossy rocks** on the lands (cut and ready in art/env/), for lotuses and moss to sprout at, placed with
  the trees and rocks.
- **The other five hunting grounds** as lands of their own (`REGION_HERB_TYPES` is ready), then `/explore`'s
  remaining encounters.
