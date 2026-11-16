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

- **The painting:** `art/maps/town.webp`, 4096 x 2048: a 32 x 32 tile diamond (2:1, 128 x 64 px tiles), its
  corners on the image's edges, as `art/maps/moon_forest.webp` is for 24 x 24. Painted by SHOAIB in Gemini
  (1024 px), cropped from 16:9 to 2:1, the Gemini marks painted out, then upscaled 4x with Real-ESRGAN (x4plus).
  A sharper painting of the same layout can replace the file as it is.
- **Where you can walk:** `town.AREA`, a polygon in tiles (the plaza, the training yard, the lanes to the forge,
  the herb shop and the pond), minus `town.BLOCKED` circles (the well, the stele, the arena's ring, the training
  dummies and racks). Measured on the painting with the grid over it; press **G** on the page to see the grid,
  the walkable outline, the circles and your position. The page and `town.walkable` share the one test.
- **Feeling big:** the painting is drawn at full size and the camera is zoomed so a wide screen shows about **12
  tiles** across (`VIEW` in town.js); a tall phone zooms less, so the cultivator stays readable. The camera stops
  at the painting's edges. A night vignette darkens everything away from you.
- **Coming in:** at the gate (`town.START`). After you leave through someone's dialogue, coming back puts you in
  front of them (the page remembers it for the browser tab).
- **The server doesn't follow you.** Nothing on the map changes the game, so unlike the hunting map there are no
  position reports.

## The townsfolk

`town.NPCS`: where each stands (x, y in tiles, the feet), name, title, what they say, and the pages they send you
to. Walk within `REACH` (1.5 tiles) and a **Talk to …** button appears; press **E** (or Enter, Space, or tap it)
for the dialogue. **Esc** or **Leave** closes it. Walking stops while it is open.

| Who | Where | Sends you to |
|---|---|---|
| Gate Warden | the gate | Hunt beasts (`/explore`), Gather herbs (`/gather`) |
| Blacksmith Tie | the forge | `/forge` |
| Herbalist Lan | the herb shop | `/alchemy` |
| Silk Merchant | the silk stalls | `/appearance` |
| Village Elder | the lane to the pond and pavilion | `/profile`, `/inventory` |
| Martial Master | the training yard | not open on the website yet: says so |
| Arena Keeper | the arena | not open yet |
| Stone Stele | the plaza (a thing, not a person) | not open yet (the rankings) |

**Pictures:** until a townsperson has one, the page draws a lantern glow, a floating marker and their name. Give
one a picture with `"src": "/art/portraits/town/<key>.webp"` in `town.NPCS`: one full-body painting, see-through,
facing right, feet at the bottom middle; it is drawn 128 px tall (the cultivator is about 120) and turned to face
you.
