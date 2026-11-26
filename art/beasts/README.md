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

The redesigned dragons (Flood Dragon (Jiao), Azure Dragon) are made the same way (`DRAGONS`), with their open-mouthed roar pictures in `roar/`.

The redesigned primates (Silver Monkey, Golden-Eyed Ape King, Ancient Golden Ape, Shanxiao Mountain Spirit) are made the same way (`PRIMATES`; the Shanxiao's thin staff kept whole by `SOLID`), with their open-mouthed roar pictures in `roar/`.

The redesigned insects and arthropods (Venom Scorpion, Golden Silk Spider, Thousand-Year Centipede) are made the same way (`INSECTS`; their thin legs kept whole by `SOLID`), with their open-mouthed roar pictures in `roar/`.

The redesigned crocodiles (Jade-Scaled Crocodile, Abyss Crocodile) are made the same way (`CROCODILES`), with their open-mouthed roar pictures in `roar/`.

The redesigned tortoises (Stone-Shell Tortoise, Black Tortoise (Xuanwu), Primordial Dragon Turtle) are made the same way (`TORTOISES`), with their open-mouthed roar pictures in `roar/` (the Xuanwu's serpent opens its jaws too).

The **Wild Boar** was redesigned again (Nov 26, Nano Banana Pro, 16:9, strict side view facing left on flat grey, no slab)
and is animated from its own videos (`sheets/wild_boar/`, scripts/make_beast_sheets.py), with its own sounds. The **Field Viper**
followed (a true snake, no legs; its roar picture is the open-jawed hiss from its own hit video). The **Stray Dog Pack** is now
one gaunt stray (SHOAIB's choice: one dog animates cleanly; the name is unchanged), and the **Wild Ox** a real shaggy ox
(no longer a horned boar; the breath steam and Gemini's mark painted out). The **Old Black Bear**, the
Mortal Beast King, is now a colossal silver-streaked bear with hunters' arrows in its back (kept whole: `SOLID`). The **Iron-Hide Boar** is
now clearly the armoured one: forged iron plates with glowing amber cracks. The **Red Fox** is now a lean crimson fox
with one ember-tipped tail (no flames leaving the body; no longer on a slab). The **Wind-Feather Falcon** is the
first animated bird: a dark falcon with a normal fan tail (the long trailing plumes were dropped: Veo could not keep
them), drawn flying with no perch or stone. The **Shadow Wolf** (Elite) is a big scarred black wolf whose shadow is
painted into its fur (charcoal legs, dark stripes, violet eyes: no smoke, which Veo cannot keep). The **Horned Stag** (Elite) has a solid crown of jade crystal antlers and flat moss
on its back (no loose leaves or floating crystals; no longer on a slab). The **Mountain Tiger**, the Martial Apprentice
Beast King, is a colossal scarred tiger with a blood-red glowing eye, animated from its own videos (its old cut-out
poses in `poses/` are retired). That completes the Martial Apprentice realm. The **Rock Python** (Martial Warrior) is a giant stone-patterned
python, no longer coiled round a boulder. Gemini's sparkle, when it lands on the beast, is lifted off by un-blending
it (it is a see-through white star: measured once on a plain backdrop, then removed from scales underneath). The **Spear-Beak Crane** stands and fights on its feet (no longer flying), with a long
steel-grey spear beak; Veo gave it a real red-crowned crane's black tail in every move, so its idle is taken from a
black-tailed stretch too (its picture keeps the icy-blue tail). The **Thornback Lizard** is a heavy sand-brown lizard
with cracked earth scales and grey stone thorns, now drawn facing left (no longer mirrored). The **Bloodfang Wolf**
(Elite) is a huge dark blood-red wolf with a shaggy ruff and oversized ivory fangs, drawn facing left (no longer
mirrored); every move is taken from whichever of its two videos had it clean. The **Armored Boar Chief** (Elite) is a giant
wild boar in dented bronze plates with short broken spear stubs in its hide; its idle comes from the calm middle of
its hit video, since its attack video began with steam puffing from its snout. The **White-Browed Tiger King**, the Martial
Warrior Beast King, is a colossal white tiger with icy-blue stripes; its picture was mirrored to face left and its
backdrop evened out before its videos, and its video effects are dropped frame by frame (wiping white would wipe its fur). The beasts are
being redone one at a time in roster order the same way.
