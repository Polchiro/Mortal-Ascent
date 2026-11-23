# Environment pieces: rocks, logs, plants, mushrooms

The maps' small natural pieces are flat pictures (sprites), one file each, placed as many times as wanted. The game
draws them in its 2D canvas like the town's buildings: back to front with you and the beasts among them, so you walk
behind a rock and in front of a fern. There is no 3D engine: a piece is a picture of an object, drawn at the map's
camera angle (docs/town.md, docs/hunting.md "The map").

Code: `web/env.py` (what each asset is, where each map's pieces stand), `scripts/make_env_assets.py` (cuts the
pictures), `web/hunt_map.py` (a map's pieces and their blocks), `web/static/huntmap.js` (drawing them).
Tests: `tests/test_env.py`.

## The assets

| Asset | Folder | Drawn | Blocks |
|---|---|---|---|
| `rock_small_01` | `common/rocks` | 56 px tall | a circle, 0.36 tiles |
| `boulder_01` | `common/rocks` | 124 px tall | 0.75 tiles |
| `stones_cluster_01` | `common/rocks` | 104 px tall | 0.8 tiles |
| `log_long_01` | `common/logs` | 380 px long | a row of circles along its 4.4 tiles |
| `log_broken_01` | `common/logs` | 200 px long | along its 2.2 tiles |
| `grass_01`, `fern_01`, `flowers_01` | `common/plants` | 44, 70, 40 px tall | nothing |
| `mushroom_01` | `common/mushrooms` | 40 px tall | nothing |
| `spirit_mushroom_01` | `moon_forest/mushrooms` | 44 px tall, glows blue | nothing |

The cultivator is about 120 px tall; a tile is roughly one stride. Shared assets live in `art/env/common/`, a region's
own in `art/env/<region>/`. `art/env/catalog.json` (written by the script) has each picture's size and foot (the pixel
where it touches the ground).

## Making a new asset

1. **In Gemini** (SHOAIB): one object, no ground slab under it (it ends where it touches the ground, its base
   visible), no cast shadow, no glow spreading onto the background, wide margins, on one flat colour: grey-green
   (about `#7A8476`), or light grey (`#B0B0B0`) for green things. Attach the town's pine as the style and angle
   reference. 1:1, or 16:9 for long things; a log lies from lower-left to upper-right.
2. **Add it** to `ASSETS` in `web/env.py`: its region and category, its drawn size (`h`, or `w` for a long thing), what
   it blocks (`block`, and `length` for a log), `glow` (a colour) and `lit` (keeps more colour in the dark) for glowing
   things.
3. **Cut it:** `python -m scripts.make_env_assets name=picture.png` (several at once is fine). The original is only
   read. The script removes the backdrop (rembg plus a colour key), drops Gemini's sparkle and loose specks, cleans
   the edges (the backdrop's colour taken out of see-through edge pixels, so no grey or green fringe), crops it, makes
   it at most 640 px on its long side, measures its foot, and writes the `.webp` and `catalog.json`. It warns when an
   object touches the picture's edge or the backdrop isn't flat. Per-picture fixes go in its `FIX`:
   `cut_below` (a share of the picture's height: everything below is cut, e.g. the fern's bare roots) and `rim` (removes
   the pale blue rim line Gemini paints along some rocks).
4. **Place it** in `PLACED` (below).

## Placing pieces

`PLACED[map]` is a list of `(asset, x, y, scale, flip)`: x and y in tiles where its foot stands (a log: the middle of its
length), scale about 0.6–1.4, flip mirrored left to right. A flat picture can't turn round, so variety comes from
mirroring, scale and variants (`_02`, `_03`). A log as drawn lies along the map's y axis (on screen lower-left to
upper-right), mirrored along the x axis. Press **G** on the map for the tile grid, your position and every blocked
circle, to place by eye. Placing pieces by hand, in groups that fit the painting, looks better than scattering them.

## How they are drawn

- **Depth:** a piece is drawn back to front by its point (x + y), a log by its footprint; you and the beast go after
  every piece you overlap on screen and stand in front of. Behind a tall piece your silhouette shows through it.
- **Each map's light:** `TONE[map]` (red, green and blue: how much each keeps) tints a map's pieces to its night,
  once per picture when it loads. A glowing piece keeps more of its colour. Moon Forest: `[0.56, 0.64, 0.80]`.
- **Shadows:** a soft ellipse under each piece (along a log), drawn on the ground in code. The pictures have none.
- **Glow:** a `glow` piece is a light like the map's painted lamps (`hunt_map.MAPS[...]["lights"]`), small and gently
  pulsing, round its caps.
- **Performance:** each file is loaded and tinted once however often it's placed; pieces off the screen aren't drawn.

## The server agrees

Pieces that block join the map's blocked circles (`hunt_map.MAPS[map]["blocked"]`), so the server's walkable test
(where you may stand, where a beast may appear) and the page's are the same. `tests/test_env.py` checks every bit of
open ground can still be reached, the way in is clear and the stepping stones still cross.

## Moon Forest

41 pieces from the 10 assets: rocks along the stream and under the bamboo, a long log in the east clearing and two short
ones off the paths, ferns and mushrooms in the shade of the old tree, the stump and the shrine, spirit mushrooms where the
light is cold (the shrine's blue lanterns, the pond), grass and flowers in the open. The other hunting grounds have no
pieces yet. The town and the Crossroads keep their own (docs/town.md, docs/world.md).
