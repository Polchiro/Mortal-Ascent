# Beast art

Drop a picture here to replace a beast's drawn silhouette on the fight screen (docs/combat.md).

- Name: the beast's name in lower case, with spaces and punctuation as `_`
  (`White-Browed Tiger King` → `white_browed_tiger_king.png`, `Flood Dragon (Jiao)` → `flood_dragon_jiao.png`).
- A **transparent PNG** works best: the bot adds the element's rim light around its outline.
- It is scaled to fit the scene window and stands on its bottom edge.

Without a file, the bot draws a silhouette for the beast's body type (`beasts.TRAITS`).
