# The town hub

**Azure Cloud Town** (`/town`, the **Town** tab) is a walkable 2.5D isometric town. You walk the cultivator about it
and up to the townsfolk; each, after a word, sends you on to a page the website already has. The town itself
decides nothing: no fights, rewards or costs happen in it.

Code: `web/town.py` (the layout and the townsfolk), the `/town` route in `web/app.py`, `web/templates/town.html`,
`web/static/town.js`. Tests: `tests/test_town.py`.

## Who walks it

Everyone whose look has a walking sheet (`looks.WALK_SHEETS`, docs/hunting.md "The map": the male cultivator for
now). A look without one sees the painting and speaks to the townsfolk from a list, with the same words and
buttons; it walks the town as soon as its sheet is added. No admin check, unlike the hunting map.

## The map

- **Built from pieces.** Nothing is a stretched painting. The ground (`art/maps/town.webp`, 6144 x 3072 for the
  32 x 32 tile diamond, 2:1, 128 x 64 world px a tile) is painted in code by `scripts/make_town_ground.py` from
  four textures (`art/maps/town/tex/`: grass, dirt, stone paving, forest floor; the top faces of SHOAIB's Gemini
  ground tiles, lifted flat and blended into seamless tiles) and `town.GROUND`: grass inside the walls, forest floor
  outside, the paved plaza, dirt roads and yards, a soft shadow at each building's foot, dimmed to dusk. On it stand
  the walls (one straightened one-tile slice of SHOAIB's wall per tile, so they run straight and
  unbroken), a corner piece at each corner (`make_town_kit` CORNERS: an outer, an inner and a side corner, the
  side one mirrored for the other side), the gate (a tower built into a stretch of the same wall, spliced into the south-east wall:
  `make_town_kit` GATE), the buildings, trees, the pond, rocks and props, each its own Gemini picture
  (`art/maps/town/`, cut by `scripts/make_town_kit.py`), so each is as sharp as it was drawn.
- **Spacing:** no two stone bases touch: there is at least a fifth of a tile of ground between footprints
  (`tests/test_town.py`).
- **Placing a building:** `town.BUILDINGS` gives each its footprint in tiles (x0, y0, a, b). Each building picture is one
  building on a square stone base at the map's angle; `scripts/make_town_kit.py` cuts it out (making sure the base
  is whole), measures the base's left, right and bottom corners (`art/maps/town/kit.json`) and the page fits
  those onto the footprint's corners, so a picture's size doesn't matter. A picture's door faces the bottom-right;
  `mirror` turns it to face the bottom-left (saved as `<img>_m`). Props (`town.PROPS`) stand on one point, drawn
  `h` world px tall.
- **Walking behind things:** the pieces are drawn back to front with you and the townsfolk among them: you are
  drawn after every piece you overlap on screen and stand in front of (beyond a footprint's back edges, or nearer
  than a prop), so a building hides you when you walk behind it, and whatever hides you fades to see-through.
- **Where you can walk:** inside `town.AREA` (a polygon: the town inside its walls), off every footprint (you can
  step `INSET` onto its paved edge), props and `town.BLOCKED` (the pond). Press **G** on the page to see the grid,
  the walkable outline, the footprints and circles, and your position. The page and `town.walkable` share the test.
- **Feeling big:** the camera shows about **12 tiles** across a wide screen (`VIEW` in town.js); a tall phone zooms
  less, so the cultivator stays readable. It stops at the ground's edges. A night vignette darkens everything away
  from you. And the town is drawn **1.4x** bigger against you than the ground's own scale (`town.SCALE`): you, the
  townsfolk and your walking speed on screen stay the same, so the streets are longer and the buildings tower over
  you.
- **Coming in:** at the gate (`town.START`). After you leave through someone's dialogue, coming back puts you in
  front of them (the page remembers it for the browser tab).
- **The server doesn't follow you.** Nothing on the map changes the game, so unlike the hunting map there are no
  position reports.

## The townsfolk

`town.NPCS`: where each stands (x, y in tiles, the feet), name, title, what they say, and the pages they send you
to. They stand at least 3 tiles apart. Walk within `REACH` (1.5 tiles) and a **Talk to …** button appears; press **E** (or Enter, Space, or tap it)
for the dialogue. **Esc** or **Leave** closes it. Walking stops while it is open.

| Who | Where | Sends you to |
|---|---|---|
| Gate Warden | the gate | Hunt beasts (`/explore`), Gather herbs (`/gather`) |
| Blacksmith Tie | the forge | `/forge` |
| Herbalist Lan | the herb shop | `/alchemy` |
| Silk Merchant | the silk stalls | `/appearance` |
| Village Elder | the lane to the pond and pavilion | `/profile`, `/inventory` |
| Martial Master | the training yard, in front of the dummies | not open on the website yet: says so |
| Arena Keeper | in front of the arena, on its gate side | not open yet |
| Stone Stele | the west side of the plaza (a thing, not a person) | not open yet (the rankings) |

**Pictures:** `art/portraits/town/<key>.webp`, cut from SHOAIB's Gemini pictures (one person, full body, on a plain
grey-green backdrop) by `scripts/make_town_npcs.py`: rembg plus a colour key for thin things like the warden's spear,
the cast shadow and Gemini's sparkle dropped, cropped tight with the feet at the bottom middle. In `town.NPCS`,
`src` is the picture, `h` how tall it is drawn in world px (the cultivator is about 120), and `flip` marks a picture
that faces left; the page turns everyone toward you. Every townsperson has theirs; one without a picture shows a lantern glow, a floating marker and their name.
