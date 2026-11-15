# Beast art

Drop a picture here to replace a beast's drawn silhouette on the fight screen (docs/combat.md).

- Name: the beast's name in lower case, with spaces and punctuation as `_`
  (`White-Browed Tiger King` → `white_browed_tiger_king.png`, `Flood Dragon (Jiao)` → `flood_dragon_jiao.png`).
- A **transparent PNG** works best: the bot adds the element's rim light around its outline.
- It is scaled to fit the scene window and stands on its bottom edge.

Without a file, the bot draws a silhouette for the beast's body type (`beasts.TRAITS`).

The redesigned four-legged beasts are made from SHOAIB's designs by `scripts/make_quadruped_art.py` (cut out, slab
dropped, facing left). After adding or replacing a picture, set its mouth in `scripts/make_roar_fx.py` `MOUTHS` and
`heads.json` so the roar bursts from the right place; a four-legged beast also goes in `beasts.QUADRUPEDS` to roar
with the shared movement.

The redesigned flying beasts (the birds) are made the same way,
`scripts/make_quadruped_art.py` `FLYING`: pedestals and rocks dropped (`STONE`), facing left.

The redesigned serpents are made the same way (`SERPENTS`), with their open-mouthed roar pictures in `roar/`.

The redesigned amphibians (Thornback Lizard, Poison Toad, Ember Lizard) are made the same way (`AMPHIBIANS`), with their open-mouthed roar pictures in `roar/`.
