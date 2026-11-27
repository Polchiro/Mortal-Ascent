# Website (web game, step 1: login and profile)

The website is the same game as the Discord bot, in a browser. It shares the bot's **database** and
**game rules**, so a character is one character everywhere: progress made in Discord shows up on the
website, and later the other way round.

**Built:** Discord login, the player's real profile page, the inventory, the **forge**, **alchemy**, **gathering**
and **exploring (hunting alone or in parties of up to 4, docs/hunting.md) with turn-based fights** (all fully playable, saved to the same character), logout, and `/api/me` (the profile as JSON for the next pages).

Also built: **sparring with the Martial Master and mastery trials** (`/training`, `/spar`: "The training yard" below),
**Practice** with Senior Sister Xue (`/practice`, a real-time drill of one technique), and **Train** (`/train`,
Meridian Circulation: a meditation steering Qi through the meridians; tiers 1-2 so far, with their art).

**Next:** using items (Open, Take) from the inventory, and the rest of Train (tiers 3-5, then its art).
Every action's result is decided **on the server** with the bot's own rules; the browser only shows it,
so players can't cheat by editing the page.

## Running it on your computer

1. `pip install -r requirements-web.txt`
2. Discord Developer Portal > your app > **OAuth2**:
   - copy the **Client ID** and **Client Secret** into `.env` (see `.env.example`)
   - under **Redirects**, add `http://localhost:8000/callback` and press **Save Changes**
3. Optional: put any long random text in `WEB_SESSION_SECRET` so logins survive a restart.
4. From the repo root: `python -m web`, then open <http://localhost:8000>.

The bot and the website can run at the same time; they use the same `mortal_ascent.db`.
By default the website only listens on your own computer (`127.0.0.1`).
To run it in Docker instead, see [docker.md](docker.md). `/healthz` answers `{"ok": true}` (no login, no
redirect) so Docker or a host can check the site is up.

## Logging in

| Step | What happens |
|---|---|
| 1 | The player presses **Continue with Discord** (`/login`) |
| 2 | We send them to Discord's own permission page, asking only for the `identify` scope |
| 3 | They press **Authorize**; Discord sends them back to `/callback` with a one-time code |
| 4 | The server swaps the code for a token, asks Discord who they are, and logs them in |

- We get their **Discord ID, display name and avatar**. Never their email, messages or password.
- The token is used once and **not stored**. The login lives in a signed cookie (`ma_session`, 14 days,
  HttpOnly, SameSite=Lax, Secure when the site uses https).
- A random `state` value is checked on the way back, so a forged or reused login link is refused.
- **Cancel** on Discord returns to the front page: "You cancelled. Nothing was shared with the game."
- A Discord account with no character sees "No character yet" and is told to use `/start` in Discord.

## The profile page

All numbers come from `bot/sheet/data.profile_data`, the same function the `/profile` card uses:
realm, layer and phase, talent, realm rank, Internal Qi (with rate and time to full), HP / Attack / Defense,
Lotus Coins and Moon Pearls, the technique slots with their painted icons, beasts slain, herbs gathered,
breakthroughs, duels won and the weapon.

**Look.** A xianxia hall: gold-trimmed lacquer panels with a cloud crest on top (`.xprofile .xpanel`, `.phead.orn`),
the portrait in a jade aura with the dragon corners (`art/ui/dragon_corner_top_sm.webp`, a small copy of
`dragon_corner_top.png`), layers as jade gems, Internal Qi as a jade current, gear in jade cards under a gold
diamond, and the Journey as a parchment scroll with a wooden plaque per deed (the painted journey icons `art/icons/journey/{beasts,herbs,breakthroughs,duels}.webp`,
`stat_icons` in `web/profile.py`). It is all CSS over the same template and data: nothing in the numbers,
forms or links changed. The appearance page keeps the plain panels (`.xpanel` without `.xprofile`).

**The cultivator's stage** (Nov 23, `.portrait.stage` in `style.css`). The left panel is a tall stage instead of a
small framed picture: the player's painting (`looks.portrait`, cut by `scripts/make_hero_portrait.py` from SHOAIB's
new paintings of the male and female cultivator) stands large under a pale moon, on a slowly turning Qi formation,
with motes of Qi rising round them, the realm's emblem faint behind (slowly turning), and a gentle float. **The
realm emblem** (the `emblem` macro in `profile.html`, `realm_track` in `web/profile.py`) is a gold lotus that opens
one more petal with every realm (5 for Mortal), with the realm's number in Roman numerals in the middle; it also
stands in the Cultivation panel's medallion, in place of the Chinese character shown before. At their sides are the four
gear slots (weapon, armor, the two artifacts: `worn`, the same data as the Equipment panel), each a link to that
item or tab in the bag, coloured by rarity, a `+` when empty. Under the stage a name plate (name, realm and layer),
the title chips, and HP / Attack / Defense as three plaques (`p.hp`, `p.attack`, `p.defense`, the Attributes panel's
own numbers). With reduced motion nothing moves. Presentation only: no number, form or rule changed.

**Painted (Nov 27, `scripts/make_ui_art.py`, the last block of the profile styles in `style.css`).** SHOAIB's paintings replace
the drawn pieces: each realm has its own seal (`art/icons/realms/<realm>.webp`, `realm_track(...)["seal"]`), shown in
the Cultivation panel and big and faint behind the hero (the old `emblem` lotus macro is gone). Gear sits in carved
slot frames (`art/ui/slot_empty.webp`); an empty slot shows the ghost of what goes there (`slot_weapon`, `slot_armor`,
`slot_artifact`, picked by the `s-<tab>` class) instead of a `+`. The name sits on a gold plaque (`art/ui/name_plaque.webp`).
The Journey plaques use the journey pictures, and so do the Discord card's Deeds (`deed:beasts|herbs|breakthroughs|duels`
in `cards/art_icons.resolve`); `emblem:realm:<realm>` (battle and breakthrough cards) draws the realm's seal too.
On a wide screen the hero card stays on screen as you scroll (`position:sticky`, only when the window is tall
enough to show all of it), so the left side is no longer an empty strip. Pictures only: no number, form or rule changed.

Layout (a dark xianxia hall, `body.hallbg`, background `art/scenes/profile_hall.jpg`):

- **Identity:** the player's painting (docs/appearance.md): `art/portraits/hero_female.webp` or
  `hero_male.webp` (the male one until they choose), with a **Choose your look** (free) or **Change look** button. The portrait sits over the
  realm's seal character (`cards/theme.REALM_CHAR`), name, realm and layer, and title chips: talent, alchemist and
  blacksmith rank (once they have EXP) and the realm rank.
- **Cultivation:** realm n of 11, the layer pips, phase, the Internal Qi bar, rate, status and the next gate.
- **Attributes:** HP, Internal Qi, Attack, Defense (icons in `art/icons/attr/`), each with its realm base and
  every bonus on top (weapon, armor, technique passives), from `bot/sheet/attributes.attribute_values`.
- **Strength, Vitality & Spirit:** the points to place (docs/attributes.md), + and − buttons with a live preview of the new
  Attack, HP and Battle Qi (same formula as `player.final_stats`); type any amount or press **Max** to put every
  free point into one stat; Place points, and Reset (first free, then 200 Moon Pearls).
  Everything is checked again on the server (`bot/points.py`).
- **Equipment:** weapon, armor and the two artifact slots, plus the three technique slots. Unequip from here.
- **Journey:** beasts slain, herbs gathered, breakthroughs, duels won.

Apart from placing and resetting points and unequipping gear, the page only shows.

## The appearance page

`/appearance` (from the profile's look button): Male or Female (round face thumbnails), with a live preview of
the painting. The first look is free, then each change costs 200 Moon Pearls; **Decide later** goes back
to the profile. Saving goes through `bot/appearance.py`. The pictures are plain files in `art/portraits/`
(`looks.portrait`, `looks.fighter`, `looks.face`).

## The inventory page

`/inventory` is the same bag as the bot's `/inventory`: the tabs (Chests, Manuals, Weapons, Armor,
Artifacts, Pills, Herbs, Materials) with how many items each holds, the items as painted tiles in
their rarity colour, and an Inspect panel for the chosen item. The tabs, items and Inspect text all come
from `bot/sheet` (`items.CATEGORIES`, `data.bag_items`, `items.details`), so they always match Discord.

- `?tab=<key>` picks a tab (an unknown one shows Weapons); `?item=<id>` picks an item. Only the
  logged-in player's own items can be picked.
- Pictures: each item's painting (`cards/art_icons.py`); chests use the website's painted chests
  (`art/chest/<rarity>.webp`, falling back to the bot's `art/chests/<rarity>.png`) and
  manuals their scroll or book (docs/equipment.md "Pictures"). Forging materials, essences included, are painted since Nov 26 2026 (docs/forge.md "Pictures"). An item
  with no painted file is drawn by the bot's own
  card code and served from `/art/drawn/<kind>.png` (`web/drawn.py`, drawn once and kept in memory), so they
  look exactly like the Discord cards.
- **Equip / Unequip** for weapons, armor and artifacts, in the Inspect panel. The rules are the bot's own
  (`loot.use_item`, `gear.equip_problem`): the realm a tier needs, one weapon and one armor, two artifacts of
  different families. Only the logged-in player's own gear can be changed, and the bot's message is shown.
- The profile page has an **Equipment** card: the four slots (weapon, armor, two artifacts) with what is worn,
  its effects, Unequip, and a link to the bag for an empty slot. HP / Attack / Defense follow at once.
- The website can't see a fight running in Discord. A fight reads the gear when it starts, so changing gear here
  during one counts from the next fight.
- **Chests** open on the website: a chest's **Open** in the Inspect panel, or the **Treasure Shelf** (see "Opening a
  chest" below). **Manuals** are learned here too: the Inspect panel says what will happen (docs/technique.md
  "Manuals") and offers **Learn & equip** and **Learn only**, or **Read it** for one already known. Learn & equip is
  held back during a fight on the website, as swapping techniques is. Using pills stays in Discord for now.

## The Moon Pavilion

**Merchant Qian** (once the Silk Merchant, by the silk stalls: `web/town.py` NPCS; looks are changed on the Profile
now) runs the **Moon Pavilion**
(`/pavilion`, `web/pavilion_play.py`, `web/pavilion_routes.py`): two tabs, **Pearl Shop** and **Heavenly Blessings**.
Everything is the bot's own, in `bot/shop.py` (moved out of `bot/views.py` so the website can use it without
Discord; Discord's `/shop` and `/blessing` use the same functions): the items and prices (`economy.PEARL_SHOP`), the
blessings and perks (`economy.BLESSING_TIERS`) and what a purchase does. Profile Card Themes show as "Coming soon",
like on Discord. Pressing Buy / Receive asks first, like Discord's confirm: the price, your pearls before → after,
and a note (your bag 100 → 120, "never goes lower" for the talent reroll, Extend or Replace for a blessing); Name
Change asks for the new name there. Each form carries a one-time token, so a repeated or stale form spends nothing.
Moon Pearls themselves are still bought on Discord (`/recharge`).

## Techniques

`/techniques` (the top bar's **Techniques**, or "Change techniques ›" on the Profile): Discord's `/techniques` on one
page (`web/techniques_play.py`, `web/techniques_routes.py`). At the top, the three sockets: **Attack**, **Defense** and
**Flex** (locked until Martial Warrior). Below, a card for every technique you have learned: grade, kind and school,
its mastery stage and EXP bar, power, passive, cooldown and special effect.

- **Equip** uses the bot's own `db.equip_technique`: it fills a free socket, or takes the place of the oldest equipped
  technique of the same kind. The card says which before you press ("Replaces Iron Fist" / "Goes into a free slot").
- **Unequip** (`db.unequip_technique`) only shows when another technique of the same kind stays equipped: one attack
  and one defense are always on.
- Nothing can be swapped during a fight on the website (a duel, a spar, a drill or a beast fight), like Discord.

## Opening a chest

Chests open with the bot's own functions: `loot.begin_chest` rolls one (with Fate Weaver) and `loot.claim_chest`
grants it (the coins, the items, the daily quest), exactly as Discord's reveal does (`web/chest_play.py`,
`web/chest_routes.py`, `web/templates/chests.html`, `web/static/chests.js` and `.css`). Nothing about what a chest
can hold is new.

**The Treasure Shelf** (`/chests`, from the bag's Chests tab): a lacquered shelf with your chests on it, the rarest at
the top (Mythic and Legendary, then Epic and Rare, then Uncommon and Common). Each tier you have glows in its colour
with a count; the ones you don't have are faint shadows. Pick one to see it beside the shelf: how many, how many
seals, how many bag slots it could need, **Open** and **Open all**. Back returns to the bag (or wherever you came
from: `?from=`, this site's pages only). A chest's **Open** in the bag goes straight into the vault.

**Nothing is ever left behind** (the approved bag guard): a chest opens only when the bag has room for the most it
could give that takes a slot, one for each kind of reward its tier can roll (a manual, a weapon, armour, an
artifact, and the Heaven-Defying Pill from Legendary and Mythic chests; forging materials go to their pouch), twice
over with an artifact that gives an extra roll. Otherwise it says how many slots it needs and how many you have.
Discord keeps its own way (it shows what was left behind).

**Open all** opens up to **20** of one kind at a time, or as many as there is room for, and says so ("Opened 2 of 25:
there was room in the bag for that many").

**The vault.** The chest is set on the altar in its tier's light. The ceremony grows with the chest's **tier**, which
you knew before opening it, never with what is inside:

| Chest | Seals to break (hold, or tap one at a time) |
|---|---|
| Common | none: tap it |
| Uncommon, Rare | one |
| Epic | two |
| Legendary | three; the chest burns brighter |
| Mythic | three; the room darkens and the chest rises |

The server opens the chest the moment you touch it (so the result is ready, and a second press can't open a second
one: each opening carries a nonce, and the same nonce answers the same result). The chest shakes, light leaks out, and
it **opens**: the lid snaps up with a little bounce (the closed picture swapped for the open one, drawn on the same
canvas so the body doesn't move), rays of the chest's colour turn out of it, sparks of that colour fly up and fall
back, and SHOAIB's **burst** video plays with its sound, tinted to the chest's colour. Everything comes **out of the
chest's mouth** (53% down the chest picture): the burst video's fountain foot is set there and the video sized to the
chest, the sparks start there and the rays turn around it, so nothing rises from the floor. The chest then **stays open**
on the altar, its light breathing softly, while the rewards come out. The **Lotus Coins** pour out with a
counting number, then every reward lands as the **same jade slip**, and they turn over one by one, **worst first**.
Each card's front shows its rarity: plain for Common, a coloured frame and band for Uncommon and Rare, turning rays
for Epic, Legendary and Mythical, a glow and a tremor for Mythical; each turn's note rises with the rarity.

**Epic and better** rise to the middle with the bot's flavour line ("Its aura is thick enough to taste."); a
**Legendary or Mythical** reward fills the screen, a ring of light turning behind it (the treasure moment video and
its sound, tinted to the reward's colour). A tap moves on. Then the **summary**: the coins and every reward, best
first (Open all groups the same reward from several chests into one line), the bot's notes (Fate Weaver), **Open
another** and **Back to the shelf**.

**Skip** jumps to the summary; **Quick opening** (remembered: `ma.chest.quick`) leaves out the seals and the burst.
Rewards still waiting from a reveal nobody finished (the bot restarted mid-reveal) show on the shelf with **Collect
them**.

**The art** (cut with `scripts/make_breakthrough_art.py`, into `art/chest/`): the shelf, the vault (a still, a loop
and its room tone), the burst and the treasure moment's ring (light on black, added onto the scene), the jade slip,
and the lid burst. The seals are Train's.

**The chests** (SHOAIB's paintings, closed and open, one pair per tier) are cut with `scripts/make_chest_art.py` into
`art/chest/<tier>.webp` and `<tier>_open.webp`: the grey backdrop is modelled from the border and removed, Gemini's
sparkle painted over, the floor shadow made see-through black, and the open picture scaled and moved until its base
matches the closed one's, on a shared 720×720 canvas (the base at 86% of the height). The page uses them on the shelf,
in the vault and in the bag; Discord keeps the bot's own `art/chests/`.

## The forge

`/forge` is the bot's `/forge` (docs/forge.md, section 5) in the browser, with the same engine:
`bot/forging.py` makes the plan, takes the materials, runs the five stages and writes the passive.

**Reached only through Blacksmith Tie in town**, the same way alchemy is through Lan. There is no Forge tab. Tie's
"Enter the forge" goes to `/town/visit/blacksmith`, which gives a pass (session) and opens `/forge`; opening `/forge`
or starting a forge without it sends you to the town, in front of Tie (`/town?near=blacksmith`), with a note. Each
click in the forge keeps the pass (it lapses after 30 idle minutes); arriving in town ends it. A forge in progress is
never locked out, so a refresh mid-forge is safe. "← Back to town" (on the gear page, and on the result next to Forge
again) returns you in front of Tie.

1. **Choose:** the player's weapons, armor and artifacts (worn first) with their passive slots; the action
   (Enchant / Reroll / Replace, and the slot to lock for Replace); an optional essence, fuel and quench liquid.
2. **Cost:** the materials (with how many they have), the Lotus Coins, the difficulty and anything missing.
   **Begin** is only active when nothing is missing; the plan is rebuilt from the database on Begin,
   never trusted from the page.
3. **Play:** one page per decision with the stage's picture, the engine's lines and the buttons it offers,
   a timer bar, and the points per stage. The hidden zone, true metal and temperatures stay on the server.
4. **Result:** the rarity, the new passives, the lines from `finish_forge` (EXP, rank up, Second Chance).

**The server referees the clock.** Every decision has a deadline (`seconds + forge.TIMER_GRACE_SECONDS`).
When the page comes back late, or is closed, each missed decision is played as a timeout (`act(None)`),
exactly like the bot's timer, so walking away can't help. Each page carries a turn number: an old or
repeated page, or a button that isn't on offer, is ignored. One forge at a time per player; a forge in
progress lives in the website's memory and is lost if the website restarts (like a bot restart).

## Alchemy

**Reached only through Herbalist Lan in town.** There is no Alchemy tab. Lan's "Enter the alchemy hall" goes to
`/town/visit/alchemist`, which gives a pass (session) and opens `/alchemy`; opening `/alchemy` or starting a craft
without it sends you to the town, in front of Lan, with a note. Each click in the hall keeps the pass (it lapses after
30 idle minutes); arriving in town ends it. A craft in progress is never locked out, so a refresh mid-craft is safe.
"← Back to town" (recipe page, and the result next to Craft again) returns you in front of Lan (`/town?near=alchemist`,
`town.page_data(near=)`).

`/alchemy` is the bot's `/craft` (docs/alchemy.md, section 5) in the browser, with the same engine:
`bot/crafting.py` picks the herbs (`plan`), takes them (`take_ingredients`), runs the stages (`Craft`, started by
`craft_for`, the same function `/craft` uses, so the Furnace artifact, Steady Hand, Swift Hands and Alchemy Sage
count on both) and stores the pill (`finish_craft`: EXP, rank up, quests, cauldron ash, Second Chance).

1. **Choose:** every pill the player's alchemist rank allows, each marked *Ready to craft* or *Missing herbs*.
2. **Recipe:** the herbs needed (with how many they have), the difficulty, seconds per decision, heat zone and
   stages; the batch size (from 2nd Grade, up to `alchemy.batch_cap`) and youngest / oldest herbs; then exactly
   which herbs go in, their average age and the most patterns it allows, and any rank relief.
   **Begin** is only active when nothing is missing; the plan is rebuilt from the database on Begin.
3. **Play:** one page per decision with the engine's lines and buttons, a timer bar, and the score per stage:
   a heat gauge (Ignite), the herb buttons (Add the Herbs), Yin and Yang bars (Fuse, Seal the Core), the glowing
   pill (Condense) and the Pill Tribulation. The safe heat zone, the herb order and the true pulse stay on the server.
4. **Result:** the pill and its patterns (e.g. *Jade Marrow Pill · 七纹*) or the explosion, with the lines from
   `finish_craft`. **Craft again** returns to the same recipe.

The server referees the clock exactly like the forge: every decision has a deadline (`seconds +
crafting.TIMER_GRACE_SECONDS`), late or missing pages play the timed-out move, old or repeated pages and buttons
that aren't on offer are ignored. One craft at a time per player, kept in the website's memory.
A nine-pattern pill is announced only when it is crafted in Discord (the website has no channel to post in).

## Rare herb events

Twice a day a light rises over the Moon Forest: one spirit herb for everyone on the website to race to (docs/world.md
"A heavenly phenomenon"; `web/herb_events.py`).

## Mining

The Ironvein Quarry, a safe land off the Crossroads: walk up to a seam, strike it with the pick, and it breaks open on
what the server decided when you began (docs/world.md "The Ironvein Quarry"; `web/quarry.py`, `web/mine_play.py`).

## Gathering

There is no Gather page any more. Herbs grow on the Crossroads and in the Moon Forest, each its own painting rooted
in the ground: walk up to one and press **E**, you kneel, and one round of the bot's gathering game opens in a
close-up low on the screen (docs/world.md "Herbs", "Gathering art"). The engine is
still `bot/gathering.py` (`Gathering`): it checks the pick, stores the herb and keeps the Herbal Insight streak, the
Wandering Spirit check and the review flags. Discord's `/gather` plays the same round. (The poisonous look-alikes
were removed from both on Nov 25 2026: the four choices are the grade's four herbs and nothing costs HP.)

**The server referees** (`web/gather_play.py`, `web/overworld.py`). Which choice is real stays on the server until the
pick: the panel has no plant names, and each choice's painting comes inside the round itself (a data: address, so
no address names a plant and nothing is fetched once the clock runs). The time for a pick is measured on the server, so a
late right answer is still "too slow". You must be standing by the herb, and each herb can be tried once. Rare finds
(Earth, Heaven) are announced only when gathered in Discord.

## The town

`/town` (the **Town** tab) is the walkable town hub: walk up to the townsfolk, who send you on to the pages
below. docs/town.md.

## The purse and the settings

- **The purse** (`web/templates/_purse.html`): Moon Pearls and Lotus Coins as two pills with their icons, at the top
  right of every page (the top bar, and beside the **?** and the gear on the walking pages). On the walking pages the numbers
  stay fresh without a reload (`/world/state` sends `purse`; `town.js` updates them, with a small pulse when one
  changes, e.g. when a trip is banked at the gate). The icons are drawn in code (SVG) until SHOAIB makes painted ones.
- **Settings** (the gear at the top right of the walking pages): **Character size**, Small / Normal / Large /
  Largest. It draws you and the land closer up or further away (`UZ` in `town.js`); it is only how the page looks
  and is kept on the device (`localStorage` `ma.size`), not in the game's save. Also **Sound** On / Off, a volume and **Music** On / Off
  (`ma.sound`, `ma.vol`, `ma.music`; docs/world.md "Sound").

## The map screen

**The frame is painted** (Nov 27 2026, "Painted UI"): at the top left the hero plate (`art/ui/hero_plate`) with your
face in its jade-and-gold ring, your name and realm tag, the HP and Qi vials (`vial_hp` / `vial_qi`: the empty glass
darkened behind, the full vial shown up to the bar's width; gold and breathing when the Qi is full at a gate, grey
when the gate is sealed), toxicity and injured / resting hanging just under it, and Break Through as a slim gold pill
(`fight_pill`, the gate's glowing seal in its socket, one line of text): beside the plate on a wide screen, so it
takes no room of its own, and tucked under the plate's bars on a phone (the big hanging `break_tab` took too much of
a phone's screen). A small round button at the right end of the medallions folds
them away or brings them back (`#dockFold` in `_walkui.html`; remembered on the device as `ma.dockFolded`); Run stays,
and M still opens the map. A round button before ? and the cog does the same for the top right: it folds the purse and
Today's Tasks away (`#topFold`, `body.topfolded`, remembered as `ma.topFolded`); the trip's panel stays, as it is the
hunt itself. A third, at the hero plate's right edge (its face's corner on a phone), folds the plate down to
your face: HP, Qi, toxicity, Break Through and the place's name go, the face still opens your character
(`#hudFold`, `body.hudfolded`, remembered as `ma.hudFolded`). At the bottom right, round medallions in gold rings (`ring`) with the
painted Bag, Character, Techniques and Map icons, and Run in the grand seal ring (`seal_ring`). The plate is 420 px
wide on a computer and up to 300 px on a phone (`--pw`); every size in it follows that width.

What the walking pages (the town, the Crossroads, the Moon Forest's lands) show around the map. One template,
`web/templates/_hud.html` (the frame, the place's name, the controls), plus the tracker and the dock in
`_walkui.html`; `web/static/town.js` keeps them fresh; the look is in `style.css` ("the map screen's frame").

- **The character frame** (top left): your round face (`looks.face`), name, realm and layer, an **HP bar** and, when
  it applies, **Injured · 12m** (red) or **Resting · 18m** (blue). The numbers come from `overworld.hero_view`, which
  only reads the game's own rules: HP is `player.final_stats` (full when you are not out on a trip); on a trip it is
  the trip's HP, which fights wear down; injured and resting are the same checks as `/explore`. `/world/state` sends
  it as `hero`, so the frame changes without a reload. Clicking the face opens the Profile.
- **The Qi line** under HP: your Internal Qi bar, counting the passive Qi gathered since the bot last banked it
  (`breakthrough_play.plate`). Jade while it fills; gold and breathing when it is full at a gate, a gold ring turning
  round the face, and the **Break through** seal under the frame (see "Breakthrough" below). The first time at each
  gate a short banner says "Your Qi presses against a gate" (`localStorage` `ma.bt.told.<realm · layer>`).
  The Qi line opens the **Dantian** (see "The Dantian" below). Under it a **toxicity badge** shows your pill toxicity when you
  have any (`overworld.tox_of`): the gourd, "Toxicity N", how fast it fades ("−1 every 8h") and what it does now in
  plain words ("Pills work at full power · one more halves them", "Pills only work at 50%"); jade up to 3, amber at 4
  and 5, red from 6 (a quarter, gently pulsing). Hovering explains it; it opens the Dantian. If
  you switched on "Tell me in this browser" on the Dantian, a notification says "Your Qi presses against a gate"
  once per gate while a map page is open in a background tab (`ma.notify.qi`).
- **The place's name** shows big in the middle of the screen for about three seconds when you arrive or walk into
  the next land, then stays only as a small line under the frame.
- **The trip tracker** (top right, under the purse; only outside town): five diamonds for the trip's encounters,
  "Encounter 2 of 5", what you carry (not yet banked) and a reminder that losing a fight costs half of it. With no
  trip but the wilds quiet (resting, injured, in a team) it shows why. Hidden in town and when there is nothing to say.
- **Today's tasks** (top right, above the trip tracker, in town too): the day's three world tasks with progress
  (docs/world.md "Today's tasks").
- **Other players** walking the same place, with their names and realms (docs/world.md "Other players").
- **Sound** and its settings (docs/world.md "Sound").
- **The dock** (bottom right): **Bag** (`/inventory`), **Character** (`/profile`), **Techniques**
  (`/profile#techniques`) and **Map** (`/world`, also the **M** key). Where you stood is kept, so you come back to the
  same spot.
- **The controls hint** (under the frame) shows for about 14 seconds on your first three visits on a device, then
  stays hidden; the **?** at the top right shows it again (`localStorage` `ma.keys`). On a phone it never shows (the
  joystick is there instead).

The frame, tracker, dock and hint change nothing in the game; the tasks are the one part that pays (docs/world.md).

## Admin panel

`/admin` on the website: Discord's `/admin` testing tools on one page (`web/admin_panel.py`, `web/admin_routes.py`,
`web/templates/admin.html`). Only the Discord user IDs in **`ADMIN_IDS`** (`.env`, the same list as Discord's
`/admin`) see it: they get an **Admin** tab in the top bar; everyone else gets "Not Found". (Discord also lets the
bot's owner in by asking Discord who owns the app; the website can't ask that, so put your own ID in `ADMIN_IDS`.)

**No reload (Nov 26).** The buttons are sent in the background: the page posts to `/admin/do` with
`X-Admin-Fetch: 1` and gets JSON back (`ok`, `lines`, and the fresh `target` card, `coins`, `pearls`, `cooldowns`),
shows the answer in a box at the bottom of the screen and updates the player card, the technique list, the purse and
the cooldown line, so the page stays where it was. Without script the form posts and comes back as before.
Pick the player to work on at the top (default: you). Each tool calls the same helper in `bot/admin.py` as the
Discord command, so it does exactly the same:

| Tool | Discord |
|---|---|
| **Give chests**: one press per tier (Common … Mythic), with how many; a link to the Treasure Shelf | `/admin item chest:<tier>` |
| **Give coins, pearls, Qi** (Qi levels up like normal Qi) | `/admin give` |
| **Reset**: every cooldown and daily limit, and the injury | `/admin reset` |
| **Give an item**: any item, picked as you type, with quality, herb age, pill patterns | `/admin item` |
| **Cooldowns for everyone**: off for hours and minutes, back on | `/admin cooldowns` |
| **Realm** and layer (the Qi bar starts empty) | `/admin set_realm` |
| **Techniques**: teach one or all; set mastery (and fill the bar) | `/admin give_technique`, `set_mastery` |
| **Crafts**: alchemist and blacksmith rank, Herbal Insight and herbs gathered | `/admin set_alchemy`, `set_blacksmith`, `set_foraging` |
| **Test fight**: any beast, waiting in your Explore (no rewards, no injury, no cooldown) | `/admin web_fight` |
| **Duel stats** | `/admin duelstats` |

Every form carries a token from your session, and what happened shows at the top of the panel.

## The Dantian

`/dantian` (from the Qi line on the player plate, the Profile's Qi bar, or the gourd): your Internal Qi laid open over
the **inner sea** (SHOAIB's video, looping, with its sound). The glowing orb in the water is your Dantian. Round it:
a ring that fills with your Qi bar (gold when it presses against a gate), Qi drifting in as fast as you gather it, and
dark wisps for pill toxicity. Under it, your Qi counting up at your rate, a second at a time, and when the bar will be
full. Nothing here is new: it is the bot's own rules read out (`web/dantian_play.py`, `web/dantian_routes.py`,
`web/templates/dantian.html`, `web/static/dantian.js` and `.css`).

**Where your Qi comes from** (left): the Final Qi Rate as `player.qi_rate` works it out, line by line, in its order:
realm base, talent, technique (the best one), artifacts (a Qi artifact and Qi passives such as Qi Flow), Heavenly
Blessing, then × Qi pill and × Blessed Land, each with its time left; what you don't have is greyed with where it
comes from. Then the sum written out (`10 × (1 + 0.1 + 0.05 + 0.02) × 1.27 = 14.92 Qi/h`), per hour, minute and
second; the gate ahead (with the Break through seal when it is ready); and the realm's layers with its gates marked.

**Pill toxicity** (right): the gourd, how much, a meter with the three zones (0 to 3 full strength, 4 and 5 half,
6 and over a quarter), when the next point fades and when you will be clean, Dao Heart's cap and a faster-fading
artifact when you have them (`player.current_toxicity`, `pill_effect_mult`, `toxicity_decay_hours`).

**Your pills**, each with what it would do to you now, worked out exactly as `crafting.use_pill` will: a Qi pill's
Qi Rate before and after and for how long, a Qi Burst's Qi, a Mending pill's injury before and after, a Cleansing
pill's toxicity, the toxicity a pill adds, and why it would be weaker (below your realm's grade, your toxicity). One
that can't be eaten says why (a Qi pill already working, not injured, a Breakthrough pill waits for the gate). **Eat**
shows the card; **Swallow it** eats it with the bot's own `loot.use_item` (passive Qi is banked first, as the bot does
before every command; one pill per press: a nonce). The pill dissolves into the orb (SHOAIB's absorb video and its
sound, tinted: blue for Qi, gold for Burst, green for Mending, pale violet for Cleansing, red for the Heaven-Defying
Pill), and as the light sinks in, the numbers change; the Heaven-Defying Pill shows "TALENT RISES · Gifted →
Genius".

**When your Qi is full**: the Discord ping (the same switch as `/settings qi_pings`) and "Tell me in this browser"
(see "The map screen").

**The Profile** gets the way in under its Qi bar (with your toxicity), and **Your passives**: every passive on your
worn weapon, armour and artifacts by what it helps (Combat, Cultivation, Fortune, Crafting), its rarity colour, which
piece gives it, and the totals ("Attack +3% from 1 passive"); a passive worn twice is marked "Not counted".

**The art** (`scripts/make_dantian_art.py`): the inner sea (a still, a loop, its sound), the absorb (light on black)
and its sound into `art/dantian/`, and the toxicity gourd as `art/icons/attr/toxicity.webp`.

## Breakthrough

The bot's **/breakthrough** on the website, with the same rules, chance, pill and Heaven's dew: the server calls the
bot's own `player.attempt_breakthrough` (`web/breakthrough_play.py`, `web/breakthrough_routes.py`,
`web/templates/breakthrough.html`, `web/static/breakthrough.js` and `.css`). Nothing about the odds is new.

**Where it is.** When your Qi bar is full at a phase bottleneck or a realm gate, a **Break through** seal appears
under the player plate on every map screen, and beside the Qi bar on the Profile. Its colour says which kind of gate
it is: jade blue for a phase gate, dawn gold for the first realms, storm violet with a lightning mark from Martial
Master on. It shows the kind and the chance ("Realm · 46%"). If something else is needed (a technique's mastery, a
Beast King), it shows a lock and what is missing: "Gate sealed · Needs a technique at Entering the Hall". Back on the
breakthrough page returns you to the page you came from (`?from=`, this site's pages only).

**The assessment** (a card at the right; a sheet at the bottom on a phone): where you are and where the gate leads,
with both realms' lotus emblems; the chance, large, and what makes it up (the gate's own chance, an artifact, the
pill); exactly what failing costs ("You lose 25.6 Qi (20% of your bar). The 218 Qi waiting behind the gate is safe
and refills it. And your meridians are injured for 6 hours", realm gates only); and if you are still injured, how
long (it doesn't stop you, as on Discord). The **best breakthrough pill** is used, as on Discord, unless you tick
**Keep the pill**. A phase gate starts with one press; a realm gate with a **1-second hold**, so an injury can't come
from a slip. The first gate (Mortal → Martial Apprentice) shows no cost: it cannot fail.

**The ceremony.** The server rolls the moment you begin; the page only shows the result it already has. Until the
result everything looks and sounds the same whatever is coming, so nothing gives it away early, and nothing in it
asks anything of you. Three looks (the look only):

| Gate | Where | What you see |
|---|---|---|
| Phase bottleneck | The meditation chamber (Train's) | Qi drifts into your Dantian, the world narrows, a heartbeat, quiet; then the **inner breakthrough** (a blue-white ring bursts out of you) |
| Realm gate into Martial Apprentice, Warrior, Expert | **Heaven's Light**: the peak at dawn | The clouds open and a golden beam comes down on you; three pulses; then the **realm ascension** (you rise in gold, a halo forms) and heaven's golden pillar |
| Realm gate into Martial Master and above | **Heavenly Tribulation**: the peak in the storm | Three lightning strikes, each stronger; then the realm ascension |

A failure plays Train's **Qi deviation** instead, the screen shakes, and the Qi bar drops by what was lost, then
refills from the Qi that waited. Then a **title card** (the new realm or phase with its emblem, "+2 more layers from
the Qi that waited", or "The gate holds · −12.8 Qi · injured for 6h") and the **result scroll**: before and after,
your chance, the pill used, Qi, the bot's own lines and Heaven's dew. **Try again** after a failure, **Back**.

**Skip** (top right, during the ceremony) jumps to the result; **Quick ceremony** (a tick on the card, remembered:
`ma.bt.quick`) shows only the result; a second try at the same gate leaves out the gathering
(`ma.bt.tries.<realm:layer>`).

**One attempt per press.** Each assessment hands out a token and the attempt needs the newest one. The same token
twice (a double click, a reload while it is sent) gets the first attempt's result again, never a second attempt; an
old page is told so and shown how things stand. The attempt is one write (`BEGIN IMMEDIATE`): it banks the passive
Qi as the bot would, checks the gate is still the same, attempts, saves, and uses the pill, together.

**Sound.** The videos' own sounds (the inner breakthrough, the ascension, the deviation, the dawn's wind and bell,
the storm's thunder as the place's ambience; the chamber's room tone), and the fight sounds for the rest (gather,
cast for the dawn's pulses, boom and stun for the strikes, victory and heal, defeat), a heartbeat made in the page
for the compression, and the meditation music.

**The art** (`scripts/make_breakthrough_art.py`, into `art/breakthrough/`): the storm peak (a still, a loop and its
sound), the dawn peak (a still, its one 8-second play with the beam, the lit still, its sound), and per character
the inner breakthrough and realm ascension, cut like Train's endings (a stacked-alpha video drawn over the scene,
its sound beside it, `hero/<gender>/sheets.json`). You meditate with Train's loop; a failure is Train's deviation.
Gemini's sparkle and Flow's mark are painted out (the tool also cut Train's chamber again without them).
The endings are then **tidied** (`make_breakthrough_art tidy art/breakthrough/hero/*/*.mp4`): everything outside the
figure's first-frame shape (the lightning, the ring, the thrown sleeves) fades out before the video's edges instead of
stopping on a straight line, which showed as a box round the figure (on a phone the video is smaller than the screen);
in the inner breakthrough, the flat grey a moving sleeve leaves behind and the corner mark cut out of the ring are
taken out too. On a tall phone the charging glow stays round the body instead of washing the whole screen.

## Fight sounds

The beast fight and the Arena's duels have sound, made in the browser like the map's (`web/static/fight_sound.js`,
no sound files). `fight.js` and `duel.js` tell it what just happened on screen (`FightSound.play(name)`); it never
decides anything.

| When | Sound |
|---|---|
| You choose a move | a tick |
| Strike / Break goes in | the blade's whoosh (heavier for Break); Break first gathers Qi, then the ground booms |
| Your blow lands | a cut and a thud (bigger when it takes a fifth of the enemy's HP or more) |
| You are hit | a duller blow (bigger likewise) |
| Blocked, Guarded, Deflected, Held | steel rings |
| Missed / Evaded | a whoosh through air / a quick double swish |
| A technique | Qi swells, then is let go: deeper and fuller the higher its grade (Mortal to Heaven) |
| The beast attacks / roars | a snarl as it springs / a long roar (bigger for its last, and after a pounce) |
| Heal, Stunned | a rising chime / a wobbling tone |
| The beast falls, the fight is won | a last cry and a thud, then a short victory phrase with a gong |
| A duel ends | victory or defeat |

The sounds are built from noise, impact and clashing metal, never a clean note on its own (a clean note is what
makes a game sound "beep"): a crack at the instant of contact, a dull thud for weight, filtered noise for a blade
through air, out-of-tune partials for steel, a rough buzz through throat shapes for the beast. They pass through a
little overdrive and a short echo, so a blow has punch and sits in a place. `LEVEL` in `fight_sound.js` sets how
loud each is against the others.

**Recorded sounds from the animation videos.** SHOAIB's Gemini / Veo videos carry sound, and a fight sound can be
taken from one: `python -m scripts.make_fight_sound --listen video.mp4` prints where the video is loud, and
`python -m scripts.make_fight_sound swing video.mp4 --from 1.2 --to 1.6` cuts that part into
`art/fx/sounds/swing.mp3` (one channel, loudness evened, ends faded) and lists it in `art/fx/sounds/sounds.json`.
A sound listed there is played instead of the one made in code; one not listed still plays the made one. A name can
be narrowed (`swing:break`, `hit:big`, `roar:big`), and a second take of the same sound (`--as swing2`) makes the
fight vary between them. `--gain` makes one louder (the beasts' voices are made loud this way); a limiter then
keeps its peaks under full scale so it never crackles.

What is recorded now (23 names, 22 files, about 220 KB, all from SHOAIB's videos):

| Sound | From |
|---|---|
| Strike's swing | her sword slash video |
| Break: Qi gathering, the swing, the ground's boom | her Break video |
| Guard raised, a blow blocked | her block video |
| Your blow landing (three takes) | her punch, palm and finger videos |
| You are hit; a miss; a dodge | her side kick and punch videos |
| Fist / palm / kick / finger techniques (`cast:fist` ...) | the same four videos, whole, timed so the loudest moment lands on the blow |
| A wolf-bodied beast springing, being struck (two takes), dying (`@wolf`) | the Grey Wolf's attack, hit and death videos |
| The Wild Boar's own squeal when struck, its gore, its death thud, its roar and big roar (`@wild_boar`) | its own hit + attack and death videos (Nov 26) |
| The Iron-Hide Boar's charge and metal crash, its clang and squeal, its plates crashing down, its squeals (`@iron_hide_boar`) | its own idle + charge and hit + death videos (Nov 26) |
| The Spear-Beak Crane's wingbeats and stabbing cry, its harsh cry when struck, its dying cry and fall, its call and big call (`@spear_beak_crane`) | its own idle + strike and hit + death videos (Nov 26) |
| The Thornback Lizard's growl and snapping bite, its hiss of pain when struck, its dying groan, its growl and big roar (`@thornback_lizard`) | its own idle + bite and hit + death videos (Nov 26) |
| The Bloodfang Wolf's snarling lunge, its yelp when struck, its dying whimper, its growl and big snarl (`@bloodfang_wolf`) | its own idle + attack and hit + death videos (Nov 27) |
| The Rock Python's strike and hiss, its angry hiss when struck, its fall, its hiss and long hiss (`@rock_python`) | its own idle + strike and hit + death videos (Nov 26) |
| The Mountain Tiger's pounce and roar, its pained snarl, its dying roar and fall, its roar and big roar (`@mountain_tiger`; also its Mountain-Splitting Pounce) | its own idle + pounce and hit + death videos (Nov 26) |
| The Horned Stag's snort and charging bellow, its pained bellow, its dying bellow and fall, its bellow and big bellow (`@horned_stag`) | its own idle + charge and hit + death videos (Nov 26) |
| The Shadow Wolf's lunge and snarl, its pained yelp, its dying howl and fall, its growl and howl (`@shadow_wolf`) | its own idle + lunge and hit + death videos (Nov 26) |
| The Wind-Feather Falcon's dive and screech, its cry when struck, its dying cry and fall, its screech and big screech (`@wind_feather_falcon`) | its own idle + dive and hit + death videos (Nov 26) |
| The Red Fox's pounce yip and snap, its yelp, its dying cry and fall, its yip and big snarl (`@red_fox`) | its own idle + pounce and hit + death videos (Nov 26) |
| The Old Black Bear's claw swipe, its pained roar, its dying fall, its roar and big roar (`@old_black_bear`) | its own idle + claw and hit + death videos (Nov 26) |
| The Wild Ox's charge and hooves, its pained bellow, its fall, its bellow and big bellow (`@wild_ox`) | its own idle + charge and hit + death videos (Nov 26) |
| The Stray Dog's lunge and snap, its yelp, its fall, its snarl and barking (`@stray_dog_pack`) | its own idle + lunge and hit + death videos (Nov 26) |
| The Field Viper's strike snap, its pained hiss, the thump as it drops, its hiss and big hiss (`@field_viper`) | its own idle + strike and hit + death videos (Nov 26) |
| The Armored Boar Chief's squealing tusk toss, its squeal when struck, its dying grunts as it falls, its snorts and big grunt (`@armored_boar_chief`) | its own idle + attack and hit + death videos (Nov 27) |
| The White-Browed Tiger King's roaring paw swipe, its snarl when struck, its dying growl, its growl and big roar (`@white_browed_tiger_king`) | its own idle + attack and hit + death videos (Nov 27) |
| The Venom Scorpion's hissing tail strike, its hiss when struck, its dying rattle, its hiss and big hiss (`@venom_scorpion`) | its own idle + attack and hit + death videos (Nov 27) |
| The Poison Toad's croaking hop, its croak when struck, its dying croak, its croak and big croak (`@poison_toad`) | its own idle + attack and hit + death videos (Nov 27) |
| The Silver Monkey's screeching swipe, its shriek when struck, its dying whimper, its chatter and big screech (`@silver_monkey`) | its own idle + attack and hit + death videos (Nov 27) |
| The Steel-Horn Bull's snorting goring hook, its grunt when struck, its dying bellow and fall, its snort and big bellow (`@steel_horn_bull`) | its own idle + attack and hit + death videos (Nov 27) |
| The Golden-Eyed Ape King's roaring fist slam, its grunt when struck, its dying groan and fall, its huff and big roar (`@golden_eyed_ape_king`) | its own idle + attack and hit + death videos (Nov 27) |
| The Ironbark Bear's growling claw swipe, its grunt when struck, its dying groan and fall, its huff and big roar (`@ironbark_bear`) | its own idle + attack and hit + death videos (Nov 27) |
| The Frost Wolf's snarling bite, its yelp when struck, its dying whimper and fall, its growl and big snarl (`@frost_wolf`) | its own idle + attack and hit + death videos (Nov 27) |
| The Thunder Hawk's screeching beak stab, its screech when struck, its dying cry and fall, its call and big screech (`@thunder_hawk`) | its own idle + flinch + attack video (remade) and hit + death video (Nov 27) |
| The Ember Lizard's hissing snap, its hiss when struck, its dying rasp and fall, its hiss and big hiss (`@ember_lizard`) | its own idle + attack video, its hit + death video and its remade hit + death video (Nov 27) |
| A roar, and a big roar, for wolf-, cat- and ape-bodied beasts | the quadruped roar video |

**His own sounds (Nov 24).** The new male's videos carry sound too, and his moves play it: his Strike's swing, his
Break (Qi gathering, the swing, the boom), his Guard raised and a blow blocked, and his fist, kick, palm and finger
techniques (10 takes, `*_male.mp3`). A cultivator's own take is listed with a `#`: `swing:strike#male`,
`cast:kick#male`. The fight page says whose moves it is playing (`data-voice` on the fighter, `FightSound.voice`),
and `fight_sound.js` tries the `#` take first, then the plain one, so she keeps hers and anything he has no take
for stays shared. Duels play the shared sounds for both fighters. His defences have theirs as well, asked for by the
move: the brace's stomp (`guardup:brace#male`), the deflect's step in and its spin away (`guardup:deflect#male`,
`block:deflect#male`, on the word "Deflected"), and the sidestep's rush as he drops (`dodge:step#male`, played with
`exact` so only a cultivator with that recording gets it, and the dodge sound on the word is then left out).

Still made in code: the move tick, heal, stun, victory and defeat, the defense techniques (brace, deflect,
sidestep), and the voices of birds, serpents, turtles, insects and dragons, until they have videos with sound.
A beast's voice is kept to its body type (`beasts.BODY_TYPES`, sent to the page as `data-body`) with an `@`:
`roar@wolf`. `--also` lists one take under several names.

In a duel both fighters' moves sound together, a moment apart. The sounds follow the map's settings (the gear on
the map: Sound On / Off and the volume), and start with your first click or key press on the page.

## The open world and the World Map

The town, the Crossroads and the Moon Forest's three lands are one world you walk through (`/town`, `/crossroads`,
`/wild/forest_edge`, `/wild/deep_woods`, `/wild/shrine_grove`): walking out through a gate or a road's mouth takes you
to the next place. The lands outside the town are big and, for now, bare ground (`web/land.py`), painted in code and
loaded in chunks. Herbs grow to pick, beasts
roam the forest and finds glint in the grass; beasts and finds make a trip of 5 encounters with the usual 30-minute
rest, banked when you walk back into town. The other five roads are closed until their lands are built. `/world` is the painted
scroll of the whole land, only to look at (**M**). docs/world.md.

## Painted UI

SHOAIB's Nano Banana pieces (Nov 27 2026), cut by `scripts/make_ui_art.py` (each picture's boxes and how each piece
is cut are in its JOBS table):

- **Heavenly Blessing orbs** (`art/icons/blessings/<tier>.webp`): a spirit pearl with the tier's sign of heaven
  inside, round and the same size, the glow lifted off as light (as the pills). The Moon Pavilion, the `/blessing`
  card and the profile badge show them.
- **Lotus Coin and Moon Pearl** (`art/icons/currency/`): the purse pills at the top of every page, the prices on the
  Moon Pavilion, and the Discord cards (`cards/purse.painted`, kinds `deed:lotus_coin` / `deed:moon_pearl`); a coin
  stack and a pearl heap for bigger amounts.
- **The map screen's frame** (`art/ui/`): hero plate, portrait and seal rings, HP and Qi vials, Break Through tab,
  dock icons (see "The map screen").
- **Realm seals** (`art/icons/realms/<realm>.webp`), **equipment slots** (`art/ui/slot_*`), **journey icons**
  (`art/icons/journey/`) and the **name plaque** (`art/ui/name_plaque`), for the profile.
- **The fight screens' top corners** (`art/ui/fight_*`, `foe_ring_*`; the beast fight, the spar and the duel all
  share the `.battle .bme` / `.benemy` plates). On a screen 901 px wide or more, your banner (`fight_me`: your face in
  the jade ring, grooves for name and realm, HP, Battle Qi) and the foe's mirror (`fight_foe`: iron and crimson, grooves
  for name, tags and HP, their face in the ring; the Martial Master's is his own picture, `s.master.img`). The pieces are
  cut as **panels**: the grooves and ring are filled with dark lacquer under the paint, so the text reads on any scene.
  Everything sits in the grooves by container units (`cqw`), so the banner can be any width (`--bw`: 30% of the
  window, at most 450 px). An Elite beast gets its violet rune ring and a Beast King its beast-head ring over the
  banner's (`rank-<tier>` on `.benemy`). The foe's next move is on the omen scroll (`fight_omen`, a 9-slice that grows
  with the text); the turn's call-outs and the duel's and spar's opening line on the jade plaque (`fight_toast`); Battle
  History on the gold pill with its icon in the socket (`fight_pill`). The other duellist's Battle Qi is a slim bar under
  their banner. On narrow desktops the spar's fifteen beads move under your banner. On a phone the plates keep their
  plain look (the grooves would be too small to read). `MEND` in the script repairs the two pieces Gemini's sparkle
  sat on from their own mirror image. Pictures only: no number, rule or move changed.
- **The fight screens' bottom** (`art/ui/move_*`, `fight_side_*`, `fight_info*`; beast fight, spar, duel). Each
  move sits in its own frame: steel for Strike, azure for Techniques, gold for Guard, crimson for Break (its corner,
  painted teal like Techniques', turned ember red by `RETINT`). The move's picture fills the round socket, its name
  the plate, its key the hanging diamond, and hovering lights the frame in its colour. The frame is picked by the
  picture in the button (`.actbtn:has(img[src*="/guard."])`; Techniques by `.techmenu`), so the bot-drawn spar and
  duel buttons need no change. The pill and Flee/Yield buttons sit on their small frames; the "Your turn" panel is
  the lacquer frame as a 9-slice with the gold tab for its heading (the tab is cut on its own by its outline,
  `SHAPES`, and painted out of the panel by `MIRROR_X` so the panel can stretch). Wide screens only, like the banners.
- **The move pictures** (`art/icons/actions/{strike,techniques,guard,break,flee}.webp`): round painted discs, each
  the same size in its square (`DISC_REACH`) with room for the sword, flames and sparks to spill over the socket.
  They replace the old pictures everywhere these files are shown: the fight buttons, the spar's beads, the explore
  page's guide and the Leave buttons of the practice and meditation screens (Flee's boot). Techniques now has its own
  picture (the book); `attack_tech` / `defense_tech` stay for the technique menu's fallbacks.

## Environment pieces

Rocks, logs, plants and mushrooms on the maps: one picture each, placed many times, cut from SHOAIB's Gemini pictures
by `scripts/make_env_assets.py` (`art/env/`, `web/env.py`). Moon Forest has the first ten. docs/environment.md.

## The Arena

`/arena` and `/duel`: friendly duels against other players, on the beast fight's screen. docs/pvp.md,
"On the website".

## The training yard

`/training` and `/spar`: Discord's `/spar` and mastery trials in the browser, reached by talking to the **Martial
Master** in town (no menu tab). The rules, the rewards and the page are in docs/technique.md, "On the website".
Code: `web/spar_play.py` (the referee), `web/spar_routes.py`, `web/templates/training.html`, `spar.html`,
`web/static/spar.js`, `spar.css`, `spar_music.js`, `web/spar_master.py` (the Master's movements, `art/spar/`).
Tests: `tests/test_web_spar.py`.

**Practice** (`/practice`, from Senior Sister Xue in town; `practice_hall.html` is her page): a half-minute real-time drill of one technique with
Senior Sister Xue (striking targets for attack techniques, meeting blows for defence techniques), graded by the server
and paid with the bot's own practice rewards. docs/technique.md, "Practice on the website". Code:
`web/practice_play.py` (pattern, grading, the pay), `web/practice_routes.py`, `web/templates/practice.html`,
`web/static/practice.js`, `practice.css`; art `art/practice/`. Tests: `tests/test_web_practice.py`.

**Train** (`/train`, from Sister Jing by the pond in town): Meridian Circulation, a two-minute meditation. Pulses of Qi flow
along the meridians of your seated body; turn junctions, close gates and hold your breath so gold reaches the Dantian
and dark Qi leaves by a palm or sole. Paid with the bot's own /train reward and its 60-minute rest. docs/training.md,
"Train on the website". Code: `web/train_play.py`, `web/train_sim.py` and its copy `web/static/train_sim.js`,
`web/train_routes.py`, `web/templates/train.html`, `web/static/train.js`, `train.css`; the meditation music is a mood
in `spar_music.js`. Reached from the yard's Train card or from Sister Jing by the pond in town. Art: `art/train/`
(the chamber's looping video and ambience, your meditation loop and three endings, the effects), cut by
`scripts/make_train_art.py`. Tests: `tests/test_web_train.py`.

## Rankings

`/rankings` is read from the Stone Stele in town: the bot's leaderboards (realm, Lotus Coins, Moon Pearls) and
most duels won, the top 10 and where you stand. `web/rankings.py`.

## Explore

**Since Nov 16 the Explore tab is hunting (docs/hunting.md):** Solo Hunt, Create a Team, Find a Team, the team
lobby, six realm-based hunting grounds and team fights for up to 4 players, on the same fight screen described
below (`data-play`, `data-team`: the screen polls `/hunt` in a team fight and shows the party's chips and turn bar).
What follows describes the single-player expedition it grew from, still served on `/explore/play` for an
expedition already under way and `/admin web_fight` tests.

`/explore` is the bot's `/explore` (docs/explore.md) in the browser, with the same engines: `bot/expedition.py` runs
the steps, encounters, loot and the walk home; every fight turn is `bot/fight.py` (the rules in docs/combat.md);
a lair is fought with `bot/hunt.py`.

1. **Set out:** the same checks as Discord (injury, the 30-minute rest). The rest starts when you set out and is
   saved, so Discord can't start a second expedition at the same time, and the other way round.
2. **Steps:** three paths with their clues, then the encounter: merchant, wounded stranger, hazard (a 3-second
   leap, timed from when the page shows it), herbs, ore, chests and so on. Go deeper or return safely.
3. **Fights** (`explore_play.html`, the arena `art/scenes/arena_ruins.jpg`): your card (portrait, realm, HP,
   Attack, Defense, statuses), the beast's plate (tier, role, element, realm, HP, statuses), your fighter
   (`looks.fighter`: the player's cultivator in three sword poses) facing the beast's painting (`art/beasts/`), and **four big moves** with keys 1–4 (`art/icons/actions/`): Strike, **Techniques** (a
   small menu with your attack and defense technique, their effect and Battle Qi cost), Guard, Break. **Mending Pill** (P)
   and **Flee** (F) are small buttons on the side. Hovering a move shows what it beats and its cooldown. After a
   turn a big word over your fighter says what happened (Countered!, Blocked!, Stunned!, Clash!, Guard broken!).
   The beast's warning about its next move (`F.warning`, the omen scroll) is still sent but **not shown** (Shoaib,
   Nov 27: it covered the beast's head and crowded the screen; you read the beast itself). The duel and spar keep
   theirs. The "Your turn" panel is a small one at the bottom right. The turn's call-outs ("A Wild Boar leaps from the
   brush!", each blow) show small at the top, in the gap between the two banners, not over the middle where a big
   beast stands (wide screens; `.bfeed`). On a computer, Battle History is a small pill (icon and turn) in the arena's
   bottom-left corner above the pill and flee buttons, its record opening upward. On a phone the two plates share
   one row, the "Your turn" panel is just its chip laid over the bottom of the arena (the move's explanation is only
   on computers), and the arena takes the height that frees (the spar and duel too). The foe banner's round ring shows the beast's **head**
   (`art/beasts/faces/<slug>.webp`, `beast_face`; cut by `scripts/make_beast_faces.py` round the mouth in
   `art/beasts/heads.json`, with `FIX` for the few odd shapes), not its whole body shrunk; a foe without one (bandits)
   shows its picture as before. The "Your turn" panel on a computer is 228 px wide with no keys line (each move's key
   is on its own diamond).
   A move is sent without leaving the page (`web/static/fight.js`), so the screen doesn't jump back to the top.
   Light animations are read from the engine's own log: a slash on a hit, a screen shake on Break, red claws when
   the beast hits, a blue ring on a block, green on a pill, damage numbers.
   **The fight is the whole screen:** during a fight the top bar and the footer are hidden, and on a computer the
   page fits one window with no scrolling. Each top corner has a plain HUD (round picture, name, HP bar; your
   Battle Qi under your HP; the beast's tell under its bar). Flee, or finishing the fight, brings the menus back.
   **Each region has its own battleground** (`explore_play.arena`): the fight takes place in
   `art/scenes/battle_<region>.jpg` for the region being explored (Bamboo Forest, Misty Pine Valley, Red Cliff
   Gorge, Thunder Peaks, Northern Sea Wilds), each with open ground across the bottom for the two fighters.
   **The turn is acted out** (`fight.js`, after a move is sent): the fighter and the beast stand apart. For a
   Strike or Break the fighter winds up, dashes in, strikes (the fight script swaps three pose
   pictures, `explore_play.look_poses`) with a
   trail, and steps back. The **male** cultivator's attack is played frame by frame from SHOAIB's video
   (`looks.ATTACK_SHEETS`, `art/portraits/fight/hero_male_attack.webp`, built by `scripts/make_hero_attack.py`):
   he raises the sword behind him, spins it in a blue Qi arc while closing in, lifts it overhead and cuts down
   through the beast (the blue slash trail and the hit land on that cut), then settles back on guard (`BLADE` in
   `fight.js`). His idle, wind-up and strike stills come from the same video.
   **Break** is the ground slam from SHOAIB's Break video, played with the cultivator's own sword (only the move
   and its effects come from the video, not its character or greatsword): blue Qi rings gather at his feet as he
   draws the blade back, he leaps in with it raised overhead (no spin), cuts down into the ground at the beast's
   feet and holds it there while spikes of blue Qi burst from the split ground (`art/fx/break_burst.webp`,
   `art/fx/break_crater.webp`, drawn by `scripts/make_break_fx.py`) with a shockwave, stones, rolling dust and a
   hard shake, then steps back on guard (`BLADE.break`, `gathered` and `slam` in `fight.js`). It slams whether it
   hits or misses; the female plays the same effects over her three poses (`RECIPES.break`). His **Guard** is frame by frame too (`looks.GUARD_SHEETS`, `hero_male_guard.webp`,
   from SHOAIB's second video, robes recoloured to match): he stands with the blade raised as the beast comes in,
   the blow bursts into a gold flash and sparks on the blade, he leans back under it and steadies (`block()` in
   `fight.js`; also used when he guards the Mountain Tiger's pounce). **Hers** is her own, with her sword, from SHOAIB's
   Nov 23 video of her (`hero_female_guard.webp`, `scripts/make_heroine_set.py`, "Her movements" below): she raises
   the blade across her body as the beast comes in, the blow lands on it in a burst of sparks with her sleeves and
   skirt whipping round, she steadies behind the blade and lowers it into her stance. Each sheet carries its own timing (`ready`, `first`, `ms` in
   `looks.GUARD_SHEETS`; his are `GUARD` in `fight.js`). **The stance:** while she stands between moves, in beast
   fights and in duels (mirrored when she is the other cultivator), the female cultivator plays her fighting stance
   (her still idle picture isn't on those pages at all): on guard, sword held low, breathing, her sleeves, hair and skirts stirring, a
   5.4 s loop (`looks.IDLE_SHEETS`, `hero_female_stance.webp`, 72 frames cut by `scripts/make_heroine_stance.py`
   from SHOAIB's video of her, her feet on the still's feet). The page steps through it in CSS (`.stanced`,
   `stancex`/`stancey` in `style.css`); with reduced motion she holds its first frame. He keeps his still picture.
   The beast is knocked back, flashes, and its HP bar and the damage number change at the
   moment of impact. Then the beast attacks in turn (its M1, `charge` with `RECIPES.gore`, from SHOAIB's beast attack
   video): it lowers its head, rears, charges in kicking up dust and gores, tossing its head up with its jaws open (its
   open-mouthed roar picture, where it has one); its mark torn across you as it hits (`mark`), and dust where it
   hits, you are knocked back, your HP drops then, and it trots home. **Every beast leaves its own marks**
   (`beasts.ATTACK_MARKS`, SHOAIB Nov 27: "every beast looks the same when it hits"): a main mark and, where its body
   has one, a second, picked at random each blow (the main one twice as often): claws (`art/fx/claw_marks.webp`), a
   bite, fangs, a horn gore, tusks, a beak, talons, a sting, a smash, a tail lash (`art/fx/marks/`, SHOAIB's white
   pictures cleaned by `scripts/make_element_fx.py`), or the one bright slash (`art/fx/beast_slash.webp`) for a beast
   not listed yet. Each is drawn in the beast's element colour (its shape filled with the colour and glowing, the
   picture's white light as a hot core) with a small burst of its element (`art/fx/elem/<element>_burst.webp`); an
   Elite's is bigger, a Beast King's bigger again and doubled. The six Martial Saints leave marks of their own
   (`beasts.SAINT_MARKS`: the Azure Dragon's scaled claw, the White Tiger's metal claws, the Kun-Peng's wing, the Void
   Serpent's space-cracking fangs, the Ancient Flame Lion's burning paw, the Primordial Dragon Turtle's shell slam).
   Presentation only.
   **Strong beasts look strong** (SHOAIB Nov 27; `explore_play.beast_power` from the beast's realm, 1 Martial King to
   4 Martial Saint). From Martial King up a beast stands in a dome of its element's aura the whole fight
   (`aura` in `fight.js`, `art/fx/elem/<element>_aura.webp`: two copies breathing out of step like a living flame,
   brighter each realm, gone as it falls), and a formation circle of its colour flares on the ground under it as it
   roars (`sigil`, `art/fx/elem/sigil_{1,2,3}.webp`: King and Emperor, Ancestor, Saint). From Martial Ancestor up its
   spirit rises behind it as it roars (`avatar`: a giant glowing ghost of its own picture in its element's light).
   SHOAIB's pictures, cleaned by `scripts/make_element_fx.py`. The aura moves with the beast as it lunges.
   Power and size both go by the beast's **own realm** (`beasts.home_realm`: where it sits in `beasts.BEASTS`), never
   the realm a fight scales it to (in a hunt every beast is scaled to the player, and a Wild Boar met by a Martial
   Saint must still look like a boar). Presentation only.
   **Strong beasts are bigger** (SHOAIB: "a Martial Saint beast like the Kun-Peng should be huge";
   `explore_play.beast_scale`, `sized` in `fight.js`): a Mortal beast stands as before, each realm up 6.5% bigger (a
   Martial Saint 65%), an Elite 8% more and a Beast King 16% more. The beast's frame itself is made bigger (not
   zoomed, so every movement, roar and mark keeps lining up), anchored where it stands so it grows up and toward you,
   but never so big that its picture leaves the top of the scene (80% of its height at most) or reaches the
   cultivator; on a narrow phone that caps every big beast at the same size. Re-measured on every new page and resize.
   **Phones** (SHOAIB Nov 27: most players will be on phones). *Lite effects* (`LITE` in `fight.js`, `.lite-fx` in
   `style.css`): on a phone-sized screen (700px or narrower) or with "reduce motion" on, the fight keeps every effect
   but draws about half the small particles, skips the full-scene impact-frame filter (the coloured flash and the
   shake stay), and drops the costly blurs, the soft glow copies of the blasts and the aura's second layer (a Saint's
   roar on a slowed phone-sized browser lost its worst 0.9 s freezes; most of the cost is drawing, which a real phone
   gives its graphics chip). *Layout* (480px or narrower): the two plates are slim HUD rows (the bars carry their own
   numbers), so the moves and the "your turn" panel fit on a phone screen; teammates are a row of round portraits,
   each ringed by its HP (`--hp`) with a dot for its state (green ready, gold choosing, grey fallen), and the
   message feed moves below them in a team fight. *Vibration* (`buzz`): a short buzz when a beast's blow or roar lands
   on you, stronger for a roar and for Elites and Beast Kings (Android; iPhones' browser has none; none with
   "reduce motion" on).
   **Team fights: whose turn** (SHOAIB Nov 27: "how do players know it's their turn, each character looks alike").
   Everyone picks at once each round. You are listed first, bigger, ringed gold and tagged YOU; each teammate keeps
   a colour all fight (`hunt_play.PARTY_COLORS`: blue, purple, teal, coral) on their portrait's ring, on their name
   tag, and on their name wherever it appears in the fight's messages and Battle History (`partyNames` in
   `fight.js`). A teammate's badge shows "…" while choosing, a tick once ready, a cross if fallen. When a new round
   needs your pick, a YOUR TURN banner sweeps across the scene, your portrait pulses and the moves glow
   (`yourTurn`), with a double buzz on Android. After you pick, the chip names who you are still waiting for
   ("Waiting for Mei Lin", kept current by the team poll).
   A Guard that stops it shows a ring and "Blocked", and your counter if any. The order and numbers come from
   `explore_play.events` (read from the engine's log); the browser decides nothing. Each kind of attack is one
   row in `RECIPES` in `fight.js`. The slash trail is a painted picture (`art/fx/slash.webp`, cyan for Strike, turned
   gold for Break). Click the scene to skip. Without JavaScript or with reduced motion the turn
   simply shows its result.
   **No side log** (Nov 12): the arena takes the full width and the two plates sit over its top corners. This
   turn's lines are called out one after another over the middle of the fight and fade (`.bfeed`), statuses
   float under whoever has them, and a hit of a fifth of the target's HP or more gets a bigger number. The
   whole fight's record (`b.history`, newest turn first) opens from the small **Battle History** button (key H,
   Esc closes) and stays open between turns. On phones the plates stack, the moves sit under the arena and
   the history opens as a sheet from the bottom.
   **Beasts with poses:** a beast with cut-out pose pictures (`art/beasts/poses/<slug>/`: idle, crouch, leap, slam,
   roar, and `poses.json` with each one's size and place) is drawn from them instead of its card painting, and changes
   pose as it moves (`explore_play.beast_poses`, `bpose` in `fight.js`): it crouches to wind up, leaps to attack, and
   for its unique skill lands in the slam pose and roars. The Mountain Tiger was drawn this way (cut from SHOAIB's
   reference video by `scripts/cut_tiger_poses.py`) until its Nov 26 redesign: it is now animated from its own videos
   like the other beasts, its poses retired (a beast with poses is never drawn from frame sheets). No beast has poses
   now; the code stays for one that might. Its Mountain-Splitting Pounce plays as its great roar (`skillRoar`: SHOAIB found the
   old leap across the arena not smooth): jaws open, the big burst, the damage, Guarded or Stunned, then Roused. The Discord card keeps the painting.
   **A technique plays its own animation** (`explore_play.cast`, CSS in `style.css`): a callout with its icon and
   name in its grade colour (Mortal grey, Yellow gold, Mystic blue, Earth green, Heaven violet), then a look by
   school (Fist burst, Palm wave, Leg crescent, Finger beam; Body bronze dome, Palm jade barrier) and one by the
   effect that actually happened (combo hits, pierce, heavy flash, stagger swirl, counter, recover, Unbreakable
   bell, evade afterimage). A blocked attack shows only the callout. All of it is off for reduced motion.
   **Techniques with their own look** replace that CSS look (`web/technique_fx.py`, `technique` in `fight.js`;
   presentation only, the engine never reads it). Each names a shared **movement** and the technique's own
   **pictures**, all timed from the release, the frame the blow is furthest out (`looks.MOTION_SHEETS`, with
   where the hand is then, so effects leave from it). Two movements, from SHOAIB's videos, bare-handed as in them,
   colours matched to his sword frames and feet where they stand:
   - `fist` (`hero_male_fist.webp`, `scripts/make_hero_fist.py`): a jab, then a lunging punch. Every Fist
     technique. Iron Fist bursts on the beast; Fierce Tiger Claw tears three golden rakes across it; Raging Bull
     Fist's bull charges from the fist; Mountain-Shattering Fist bursts a mountain up under it. Nine Dragons
     Ascending Fist, the Heaven one, throws four punches (jab, lunge, jab, lunge) loosing 1, 2, 3 and 3 golden
     dragons, nine in all, then all nine rise around the beast in one coil as the damage lands.
     **Nine Dragons, moving (Nov 24).** Its pictures are now moving ones, from SHOAIB's two videos of golden light on
     black (`scripts/make_dragon_fx.py`: black becomes clear, each pixel's opacity is its brightness). Each dragon
     loosed is a writhing dragon flying from the fist (`nine_dragons_fly.webp`, 16 frames); the finale
     (`nine_dragons_finale.webp`, 50 frames at 40 ms) bursts from the ground under the beast, coils up with
     lightning, and explodes: the damage lands on the explosion (`boom`), so the cast lasts about 4 s, longer than
     the Heaven grade's 2.7 s. `technique_fx` carries the strips' frame counts (`sheets`); `strip` in `fight.js`
     plays them. Sound from the videos: a roar per punch (`cast:dragon`), the rising (`gather:dragons`) and the
     explosion (`boom:dragons`). Presentation only.
     (The black bars were removed the same day at SHOAIB's ask: the length stays, the bars go.)
     **Second design (Nov 25).** SHOAIB redrew it as one video: a winged golden dragon (the dragons loosed, 8
     frames), then a pillar of light with dragons coiling up it and swarming round, and a burst on the ground (the
     finale, 59 frames; the blow lands on the burst). Same script, same rules, its own three sounds re-cut.
     **A cutscene (Nov 24).** Nine Dragons now plays as one (`cutscene` in `fight.js`, `CUT`), about 6.6 s: black
     bars close in (`.tcine`), "Heaven Technique" and its name are written large across the scene (`.tcard`, 1.1 s)
     , the four punches come 1.4 times slower, and the finale plays at 60 ms a frame. (The camera zoom it first
     had was removed the same day: scaling the scene pushed it over the panels around it, worst on phones.) The
     damage is written large above the explosion (`written`, `.tbig`), where the fire cannot cover it; on a narrow
     scene the finale is drawn up to the scene's full width. The small name plate and the turn's lines stay hidden
     until the blow lands (`.battle.cutscene`). A **Skip** button (`.tskip`) jumps to the explosion: the damage
     lands as always and the turn ends sooner.
     **Heaven techniques: the long play (Nov 24). SHOAIB's rule for the grade:** every Heaven technique plays long
     (about 5 to 7 s) and special: "Heaven Technique" and its name written large in gold, a moving effect cut from
     his video of it with the video's own sound, the damage written large when the blow lands, and a Skip button.
     No black bars. All six have it. The effects are strips of frames (`<technique>_fx.webp`,
     `scripts/make_heaven_fx.py`), described in `technique_fx` under `sheets.finale` (`frames`, `boom`: the frame
     the blow lands on, `anchor`, `sound`).
     - *Attacks* (Meteor-Falling Kick, Heaven-Rending Palm; Nine Dragons as above) play in `technique` (`CUT`): the
       title (1.1 s), the kick or palm, then the effect at 60 ms a frame set on the ground under the beast
       (`anchor`); the damage lands on `boom` (the meteor striking, the giant hand slamming down).
     - *Defences* (Immortal Lotus Body, Void Mirror Stance, Cloud-Walking Shadow) play through `heavenly`, which
       wraps the ordinary exchange (`braced`, `deflected`, `sidestepped`): for `pre` ms the effect forms on the
       cultivator (the lotus blooms behind them; the mirror hangs before the hand; the cloud figure stands where
       they stand), then the exchange plays whole with the effect's `boom` frame on the beast's blow (the pillar of
       light; violet lightning shot back; the figure gone in trails of cloud), and the rest plays out at 50 ms a
       frame. Skip jumps over the forming only. The older still pictures of these six are no longer drawn.
     - Sounds: `gather:<sound>` as the effect starts, `boom:<sound>` on the blow (Void Mirror also `block:void` as it
       shatters), each played with `exact` so nothing else is put in its place.
     A new Heaven technique must be given the same: a video of its effect on black, a `sheets.finale` entry, sounds.
   - `kick`, shared by both genders: its timing and effects are defined once, and each look plays it with its own
     frames (`hero_<gender>_kick.webp` in `looks.MOTION_SHEETS`, made from that look's own picture so it keeps
     its appearance) or, until it has them, with its own three poses and a hop into the kick. **She has hers**
     (Nov 23, "Her movements" below): a high side kick from her stance, the effects leaving from her foot. He has none yet
     (Meteor-Falling Kick: a leap). Every Leg technique. Crescent Sweep sweeps a pale crescent across the beast;
     Swift Swallow Kick sends a golden swallow from the foot straight through it; Autumn Wind Kick spins a whirl of
     autumn leaves round it, one pulse per hit; Meteor-Falling Kick, the Heaven one, brings a blazing meteor down
     onto it and leaves the golden crater. Their designs were drawn over a painted scene with the name across the
     top; `scripts/make_kick_fx.py` keys them out of it.
   - `finger` (`hero_male_finger.webp`, `scripts/make_hero_finger.py`): a lunge with two fingers thrust out. Every
     Finger technique: its beam's tail stays on the fingertip (`hand`) and stretches to the beast, angled to it.
     Viper Fang Finger strikes out an emerald viper; River-Splitting Finger shoots a blue beam and then opens two
     walls of water around it. Designs cleaned by `scripts/make_finger_fx.py`.
   - `brace` (`hero_male_brace.webp`, `scripts/make_hero_brace.py`): arms crossed up into guard, sinking into a wide
     stance. The Body defense techniques that stand their ground (all but the two evades), played **inside the
     beast's attack** (`braced` in `fight.js`): the fighter braces while the beast winds up, the technique's effect
     forms around them as they settle, and the beast's blow lands on it; then what really happened, from the log
     (Blocked, Held N% of a Break, Unbreakable, HP recovered, a counter; part of a Break still hurts). The effects are
     placed and sized around the braced figure (`body` in `looks.MOTION_SHEETS`), so they fit either look: Horse
     Stance Guard's dust ring at the feet, Calm Breath Stance's mist spiral, Iron Cloth Body's woven iron sheen laid
     over the fighter's own frame, Rooted Mountain Stance's roots and mountain, Golden Bell Cover's bell dropping over
     them, Ancient Turtle Shell Art's dome (the man painted inside it erased), Immortal Lotus Body's lotus opening
     beneath. Parrying Arm deflects now (below), with both looks. Designs cleaned by `scripts/make_brace_fx.py`. When the beast guards too, the engine logs nothing for you,
     and nothing plays.
   - `deflect` (`hero_female_deflect.webp`, `scripts/make_heroine_set.py`, from SHOAIB's video of her, "Her movements" below): the
     deflection, for **both cultivators** (`technique_fx.MOVES_FX`), each with their own frames: hers sweeps her
     sleeve; his (`hero_male_deflect.webp`, `scripts/make_hero_deflect.py`, from SHOAIB's video of him) reaches back
     and sweeps a painted blue Qi arc round in front of him, his robes matched to his sword frames. Told below as she
     plays it. The six deflection techniques: Parrying
     Arm and the five Palm defenses (Flowing Stream Palm, Crane Wing Deflection, Moon Mirror Palm, Thousand Hands
     Deflection, Void Mirror Stance). Played **inside the beast's attack** like a brace (`deflected` in `fight.js`),
     but with no guarding stance: on guard, palm raised, while the beast winds up; she turns into the blow and meets it
     with her hand as it lands (`release`), carries it round and aside with a swirl of her sleeve (`sweep`) and
     settles back on guard (`back`), then idle. The beast is turned aside past her rather than stopped. Its lunge is
     a little slower than its own attack (`DEFLECT`), so there is time to see her read it. Each technique's picture
     follows the contact (`hand`) and the sleeve (`tip`): Parrying Arm's streak of light runs along her arm and is
     carried down with the blow; Flowing Stream Palm's ring of water spins up at her palm and rolls it away along
     her sleeve; Crane Wing Deflection's white wing opens across the blow and sweeps it down; Moon Mirror Palm's moon
     mirror rises before her palm, turned to the beast, and the blow glances off it; Thousand Hands Deflection's ring
     of jade hands opens behind her and turns it round her; Void Mirror Stance's dark mirror forms before her palm and
     cracks as the blow hits it. Then what really happened, from the log: Deflected, a Break held, HP recovered, a
     counter. Designs cleaned by `scripts/make_deflect_fx.py`.
   - `sidestep` (`hero_female_sidestep.webp`, `scripts/make_heroine_set.py`, from SHOAIB's video of her, "Her movements" below): the
     sidestep, for **both cultivators** (his: `hero_male_sidestep.webp`, `scripts/make_hero_sidestep.py`: a low dash
     in place, wrapped in swirls of blue Qi, then his own launch frames played back to rise out of it, as his video
     holds the dash to its end; no ground given, `give` 0). Told below as she plays it. For the two evade techniques, Drifting Mist Steps and Cloud-Walking
     Shadow (`technique_fx.MOVES_FX`, `"on": "evade"`). It plays **whenever the technique leaves the cultivator
     untouched** (`explore_play.untouched`): the engine has the technique slip the beast's Break every time it is used (`bot/fight.py`;
     since Nov 24, it rolled a chance before) and logs "slipped away from the ... Break" ("Slipped away"), or the technique takes a Strike with a
     full block, as a Guard does ("blocked 100%": "Evaded", with the Guard's counter). `explore_play.events` marks the
     technique's event `evaded` (and `slipped` for the Break). When a Break gets through instead, held in part, the
     technique keeps its CSS look. A beast's unique skill that is sidestepped is acted out by the sidestep alone (no
     second, harmless pounce). Played inside the beast's Break (`sidestepped` in `fight.js`): her frames one for one at the video's
     own pace (`fps`, 10 a second since Nov 24, was 12), never sped up, stretched or cropped. On guard, she sweeps her sleeve and drops
     into a deep side lunge, out of the Break's line as it arrives, then rises into the same guard and idles; she
     gives a little ground and takes it back. Her afterimages (the technique's picture, cleaned by
     `scripts/make_sidestep_fx.py`) are left on the spot she left, and the Break passes through them: Drifting Mist
     Steps' mist figures, Cloud-Walking Shadow's cloud figures, streaming off behind her and dissolving. "Slipped away",
     no damage. The engine's log was never read for an evade before (its line has no " — "), so until now a worked
     evade played nothing on the website; it now plays the sidestep.
   - `palm` (`hero_male_palm.webp`, `scripts/make_hero_palm.py`): both arms drawn back, a lunging two-handed palm
     push, held. Every Palm attack technique. Twin Palm Strike sends one palm print for each of its two hits;
     Rolling Thunder Palm rolls a thunder vortex onto the beast; Thousand Shadow Palm opens a fan of shadow palms
     over it, one pulse per hit; Heaven-Rending Palm brings a giant celestial palm down onto it from the sky.
   The pictures are SHOAIB's Gemini designs (`art/fx/tech/<id>.webp`), cleaned of their painted checkerboard and
   Gemini mark by `scripts/make_fist_fx.py` and `scripts/make_palm_fx.py` (Thousand Shadow Palm, dim and
   see-through on a checker that flips light-for-dark in patches, has the checker rebuilt square by square).
   The **grade** sets the length (`GRADE_MS`: Mortal 1.1 s to Heaven 2.7 s) and the spectacle: a glow from
   Yellow, Qi rings at the feet from Mystic, a pillar of Qi and a dimmed scene from Earth, a dark Heaven sky. Heavy
   hits leave the golden crater, Stagger the dizzy ring, Pierce a line of light through the beast. The pictures
   are sized by the beast's box, so they keep their proportions on phones. The damage comes from the server (the
   `tech` event's `dmg`) and the HP bar drops when the blow lands. The female cultivator's punch, palm push, finger jab and brace are her own, from SHOAIB's videos of her
   (`hero_female_{fist,palm,finger,brace}.webp`, `scripts/make_heroine_{fist,palm,finger,brace}.py`): her palm push
   sweeps both arms and sleeves back, then lunges forward with both palms pushed out and holds them there before she
   rises back to standing. Her finger jab points two fingers out, swings the arm and drops into a deep lunge thrusting
   them forward (the beam leaves her fingertip), then rises drawing the arm in and settles on guard; her video holds
   the point to its end, so the sheet finishes on her guard from the start of the clip. A look with no frames for a movement (both, for the kick so far) plays the
   same pictures through its own three poses. The
   action buttons stay locked until the whole cast has played, so extra clicks never cut it short.
   **A beast's roar** is one shared shockwave for every beast (`roar` in `fight.js`, `art/fx/roar_{ring,double,burst}.webp`
   from SHOAIB's roar video by `scripts/make_roar_fx.py`): the ring for normal beasts, the double ring for Elites, the
   spiky burst for Beast Kings, tinted with the beast's element colour. It plays over the beast's own picture,
   never in place of it, from its mouth (`art/beasts/heads.json`, read off each picture by eye; a new beast gets an
   outline guess by re-running the script), sized by how tall the beast stands on screen. It plays when a four-legged
   beast **roars** (a move of its own, docs/combat.md "The roar": `events` reads it from the log as `act: "roar"`,
   with the damage, Guarded, Shaken / Exposed / Stunned popped over you as the wave bursts; a final roar bursts the
   biggest wave, larger), and the Mountain Tiger's Roused roar uses it from its roar pose. Only one is ever on screen.
   **The four-legged beasts roar with their bodies too** (`roaringMoved` in `fight.js`): one shared movement for the
   body (`beasts.ROAR_ANIMATIONS["quadruped"]`, measured from SHOAIB's quadruped roar video of a boar, then shortened
   to a turn), played by every beast in `beasts.QUADRUPEDS` with its **own picture**: it dips its head and crouches,
   rears its head up as the roar bursts from its own mouth (with dust kicked up at its feet and a shake of the scene),
   holds it trembling, and settles back. The burst fills the scene as the roar video's does (`bigRoar`): a white flash,
   a spiky starburst bigger than the beast, two hollow rings rolling out past its whole body (it stays in view inside
   them), speed lines radiating across the scene, the camera punching in on it with a hard shake, heavy dust, the
   beast swelling toward you and you pushed back by the blast; a final roar is bigger still. The picture is moved whole about its hind feet (turned and shifted, never
   bent, stretched or cropped), so any body shape or size works; the wave follows the mouth as the head comes up. A
   beast with cut-out poses takes its own roar pose while it holds (none now); every quadruped swaps
   to its own **open-mouthed roar picture** (`art/beasts/roar/<slug>.png`, SHOAIB's, cut by
   `scripts/make_quadruped_art.py --roar` onto the standing picture's canvas so it keeps its size and footing) as the
   roar bursts, and back as it settles. Its open mouth (`heads.json` "<slug>@roar") is where the wave starts, and the
   wave goes out just in front of the jaws so they stay in view. Other beasts keep the plain
   rear-back. A new body category is one more row in `ROAR_ANIMATIONS` and its beasts in `ROAR_CATEGORY`.
   **The flying beasts screech** (`ROAR_ANIMATIONS["flying"]`, from SHOAIB's flying roar video of a crane; `gather` and
   `screech` in `fight.js`): each, as its own picture, rears up off the ground with its head thrown back while Qi motes
   of its element swirl into its glowing throat, then snaps its head forward with its open-beaked picture
   (`art/beasts/roar/`) and screeches a spiralling blast of wind at you (`art/fx/wind_blast.webp`, from SHOAIB's picture, coloured
   by its element), bells pulsing from its beak while it holds. The two greatest birds are unique (`SCREECH_KINDS`): the
   Vermilion Bird breathes crimson phoenix fire with a golden heart, embers and a ring of fire; the Kun-Peng darkens
   the sky and screeches a deep-sea tide, a whirlpool round it, spray and great waves rolling along the ground, feathers scattering across the scene and the camera punching in, then settles. Same rules,
   damage and log line ("Roar") as the quadrupeds' roar.
   **The serpents hiss** (`ROAR_ANIMATIONS["serpent"]`, from SHOAIB's serpent roar video of a viper; `gather`, `runes`
   and `hiss` in `fight.js`): each coils back with its head low, then rears high while Qi of its element swirls into its
   jaws and a circle of glowing runes with spinning golden rings flares up behind it; then it lunges with its
   open-mouthed picture and breathes a twisting torrent of venom at you (`art/fx/serpent_blast.webp`, from SHOAIB's
   picture, tinted to its element's colour), droplets spraying through it and mist
   rolling out along the ground, the camera punching in, and settles. Same rules, damage and log line.
   **The amphibians roar** (`ROAR_ANIMATIONS["amphibian"]`, from SHOAIB's amphibian roar video of the Thornback
   Lizard; `gather` and `quake` in `fight.js`): each crouches low while Qi of its element swirls in, then throws its
   head up with its open-mouthed picture: a starburst at its jaws, a crack slammed along the ground to your feet
   (`crack`), two shockwave rings racing out along the ground with dust, the camera punching in, and settles. Same rules,
   damage and log line.
   **The dragons roar** (`ROAR_ANIMATIONS["dragon"]`, from SHOAIB's dragon roar video of the Flood Dragon; `coil`,
   `gather` and `storm` in `fight.js`): each draws its head back while ribbons of its element coil up round its body,
   then rears and roars with its open-mouthed picture, an orb of crackling energy blasting at you
   (`art/fx/dragon_blast.webp`, from SHOAIB's picture, coloured by its element) with lightning streaks
   fanning out, mist pooling at its base, the camera
   punching in, and settles. Same rules, damage and log line.
   **The crocodiles bellow** (`ROAR_ANIMATIONS["crocodile"]`, from SHOAIB's crocodile roar video; `gather` and
   `bellow` in `fight.js`): each presses low as Qi gathers into its jaws, then throws its head up with its open-mouthed
   picture and bellows: its element's blast and rings of sound roll out of its jaws all the way to you, a small golden
   flare and spikes of light fan toward you, dust blasts up off the ground, the camera punches in, and it sinks back down. Same
   rules, damage and log line.
   **The tortoises roar** (`ROAR_ANIMATIONS["tortoise"]`, from SHOAIB's tortoise roar video; `charged` and `shell` in
   `fight.js`): each braces while its shell's runes light up and crackle with energy of its element, then lifts its head
   with its open-mouthed picture (the Xuanwu's serpent opens its jaws too) and roars: its element's blast and a cone
   of sound rings reach you, then a dome of its element swells round its body like a shield, mist rolls along the ground, the camera
   punches in, and it settles. Same rules, damage and log line.
   **The primates roar** (`ROAR_ANIMATIONS["primate"]`, from SHOAIB's primate roar video of the Silver Monkey;
   `vortex`, `beat` and `pound` in `fight.js`): each crouches, rises onto its hind legs and pounds its chest twice, a
   ring flying off its chest at each blow, while a whirlwind of its element spirals round it; then it roars with its
   open-mouthed picture, its element's blast and a wall of sound rings rolling at you, streaks and shards flung at
   you, dust, the camera punching in, and settles. The Ancient Golden Ape moved here from the four-legged
   beasts. Same rules, damage and log line.
   **The insects hiss** (`ROAR_ANIMATIONS["insect"]`, from SHOAIB's insect roar video of the Venom Scorpion; `seep`
   and `venom` in `fight.js`): each crouches and rears with venom dripping and poison smoke gathering, then hisses with
   its open-mouthed picture: its venom sprayed across at you with droplets through it, and a low cloud of poison smoke
   left round your feet. Same rules, damage and log line.
   **Every roar hits you** (SHOAIB, Nov 27: the insects', amphibians', primates'... roars looked like they were
   "roaring to themselves", their bursts all round their own bodies). Each beast's element has its own blast, burst
   and ground patch (`art/fx/elem/<element>_{stream,burst,ground}.webp` and `ground_crack.webp`, SHOAIB's Nano Banana
   pictures cleaned by `scripts/make_element_fx.py`; `explore_play.beast_roar` tells the page the `element`). The
   primates, insects, crocodiles and tortoises (and the beasts with the plain rear-back) throw the blast from the mouth
   across to you (`blast`); the amphibians crack the ground to your feet (`crack`); the dragons, serpents, birds and
   four-legged beasts keep their own blasts and waves. `TRAVEL` ms later it lands (`impact`): the element bursting on
   your body twice, a soft white impact frame, a flash of its colour, a shake, you knocked back (less behind a Guard,
   which plays your Guard), its patch on the ground at your feet, and the damage and debuffs (`struck`). An Elite's
   roar (or any final roar) also pulses its colour round the screen's edge (`presence`); a Beast King's darkens the
   scene, cracks the ground under itself and follows with an aftershock. Presentation only: the same rules, damage and
   log line.
   **Screen shake** (SHOAIB Nov 27: "I like it but I don't know if it works well for others"): every shake, camera
   punch and white flash in beast fights is gentler (`SHAKE`, `ZOOM` in `fight.js`: about half the old shake, a
   smaller punch, a softer, shorter flash); with "reduce motion" on there is no shake and no flash, only a slight
   punch.
   The redesigned quadruped pictures (SHOAIB's designs) are cut out of their backdrops by
   `scripts/make_quadruped_art.py`: the painted stone slabs and Gemini's mark dropped, the right-facing ones mirrored
   to face the cultivator, standing on their bottom edge as every beast picture does (`art/beasts/README.md`).
4. **Lairs:** an Elite lair or Beast King den found on the website can't be posted to a Discord channel, so it is
   hunted **alone**, exactly like a lair found in a DM with the bot (`hunt.start_battle` with one fighter,
   `hunt.pay`), from the end screen while it is open.

**Testing a beast:** `/admin web_fight <beast>` in Discord (owner/admins) queues a test fight; the next time that
player opens Explore on the website, it starts right away (`Explores.start_test`, `admin.take_web_fight`): no
expedition, no rewards, no injury, no cooldown.

**One action per turn** (the combat action state: `Combat` in `fight.js`, the same phase names in
`explore_play.py`). A fight is always in one phase, and a move can be sent in the first one only:

| Phase | What is happening | Buttons |
|---|---|---|
| `player_turn` | waiting for your move | on |
| `submitting` | your move is on its way to the server | locked |
| `player_acting` | your Strike, Break or technique is acted out | locked |
| `beast_acting` | the beast attacks, or reacts to your Guard | locked |
| `dying` | the loser goes down (set by a death animation: `MACombat.set('dying')`) | locked |
| `finished` | the fight is over | locked |

- The buttons lock the moment a move is pressed and come back only when the whole turn (your action, then the
  beast's) has been acted out. Buttons, hotkeys (a held key counts once) and the techniques menu all ask
  `Combat.can()`. Locked buttons are a little dimmer, and a small label says whose turn it is (`.turnchip`).
  A turn's animation can't be skipped or cut short by the next move.
- There is no fixed cooldown: the lock lasts exactly as long as that turn's animations, and a turn with nothing
  to act out (a pill, a refused move) frees the buttons after a fifth of a second.
- **The server decides, the screen only shows.** A turn is resolved (damage, statuses, rewards) in one step
  before anything is acted out, so closing the tab mid-animation loses or repeats nothing. Each turn takes
  exactly one action: `Explores.act` checks the turn number while holding the lock, so a double click, a retry
  or many requests at once play one turn; the others change nothing (`Run.refused` counts them).
- **A lost connection:** when a move gets no answer in 12 seconds (or the request fails), the page asks the
  server for the fight as it stands. If the move was played, the turn is acted out as usual; if it never
  arrived, the buttons come back with a note and nothing was spent.
- Other scripts can read `window.MACombat.phase`, call `MACombat.set(...)`, or listen for the `combat:phase`
  event on `document`. Frames stop in a hidden tab, so a timer ends the turn anyway: the buttons never stay locked.

The server keeps every clock. **Fight turns have no reaction time on the website for now**: a turn waits for the
player, and only a page left alone for 10 minutes (`explore_play.TURN_LIMIT`) gets the bot's timed-out move
(Guard; three in a row: flee), so a forgotten fight still ends. A hazard answered too late fails, and two idle
minutes outside a fight end the expedition (as the bot's panel does). Old pages and moves that aren't
possible are ignored. Rare finds are announced only in Discord.

Only `art/icons`, `art/scenes`, `art/chests`, `art/portraits` and `art/beasts` are served (as `/art/...`), plus `web/static`. Nothing else in the repo
(code, `.env`, the database) can be opened from the browser.

### The victory sequence

When a fight is won the page no longer jumps straight to the next step. In order:

1. The last blow is acted out like any other turn. The fight is already over on the server, so no move works.
2. The beast goes down (its death animation).
3. The body stays where it fell for a moment (`web/death.py`, `LINGER_MS`).
4. The **Victory** panel comes up: the beast, the turns, your HP, and what the win paid, in the game's own lines.
5. **Continue** takes you on (after a lair or a test fight the button is **Finish**).

Nothing about the rules changed. `Explores._resolve` pays the win at the same moment and with the same code as
before (`Expedition.end_fight`, `hunt.pay`), once; it then keeps the finished fight in `Run.ended`. While that is
set, `Explores.act` listens to nothing but `continue`, so there is no move, path or second payout to be had, and
a reload simply shows the same finished picture again (the body down, the panel up, no replay). Continue works even
from an old page, and pressing it twice does nothing. Fights that are lost, fled or timed out go on as before.

**Death animations** are shared, one per body category, not per beast, and they are a *movement*, not artwork
(`beasts.DEATH_ANIMATIONS`, `beasts.DEATH_CATEGORY`). Every beast goes down as its own picture.

- `quadruped`: for Iron-Hide Boar, Red Fox, Shadow Wolf, Horned Stag and Mountain Tiger. Its eight frames were
  measured from SHOAIB's wolf sheet: per frame, how wide the body lies and how high its back stands at 12 points from
  tail to head, as shares of the standing first frame, plus the sheet's timing. No wolf drawing is kept.
- `fight.js` (`drawDeath`) draws the beast's own picture on a canvas in thin upright strips and lowers each strip to
  the height the movement gives that part of the body: the legs fold, the body comes down, the head end lowest.
  `web/death.py` says where the body is inside the picture, so the same movement fits every beast's size and place.
- A beast with no category staggers, its legs give, and it rolls over onto its side where it stands (`death-fall`:
  a 3D roll onto its far flank, head end or hindquarters down first by `side`, `web/death.py`), never backwards;
  bandits scatter.

To add a category (flying, serpentine ...): measure a reference sheet with
`python -m scripts.make_death_motion <video.mp4>`, add a row to `DEATH_ANIMATIONS` with the rows it prints, and list
its beasts in `DEATH_CATEGORY`. To give another four-legged beast the movement, add its name to `DEATH_CATEGORY`.

## Going online later

- Add the real address as a second redirect, e.g. `https://<your-domain>/callback`, and set
  `WEB_REDIRECT_URI` to it. With an `https://` address the login cookie is only sent over https.
- When the bot and the website both write often, move from SQLite to PostgreSQL (CLAUDE.md, Tech stack).

## Animated beasts

A beast can be animated from its videos (SHOAIB's, Gemini or Flow: idle, attack, hit, death; so far the **Grey Wolf**
and the redesigned **Wild Boar**, **Field Viper**, **Stray Dog Pack**, **Wild Ox**, **Old Black Bear**, **Iron-Hide Boar**, **Red Fox**, the first bird, the **Wind-Feather Falcon**, the **Shadow Wolf**, the **Horned Stag**, the **Mountain Tiger**, the **Rock Python**, the **Spear-Beak Crane**, the **Thornback Lizard**, the **Bloodfang Wolf**, the **Armored Boar Chief**, the **White-Browed Tiger King**, the **Venom Scorpion**, the **Poison Toad**, the **Silver Monkey**, the **Steel-Horn Bull**, the **Golden-Eyed Ape King**, the **Ironbark Bear**, the **Frost Wolf**, the **Thunder Hawk** and the **Ember Lizard**). One video can hold two of them: the Wild Boar's idle comes from one video, its hit
and attack from a second, its death from a third (`CLIPS` gives the seconds of each).
**The move panel never changes height** (fight.js `holdInfo`): it is held at the height of its tallest text (every
move's and technique's, tried once when the page comes in, and again when the window changes size). Guard's and
Break's texts are a line longer than Strike's, and hovering them used to grow the panel, shrink the scene above it and
make the beast, the hero and the background jump (SHOAIB: "it keeps refreshing").
**A move that ends in another pose eases back** (`settle`): Veo stretched the Thornback Lizard's tail out straight
from its bite on and never curled it back, and left it a little further along, so its attack's last frames slide back
until its nose and front feet meet the idle's and then dissolve into the idle (instead of snapping); its tail tip,
which ran off the video's edge, fades out (`fade`). Its attack and death are placed as its idle and hit (`place_as`:
the same videos, the camera still), so the attack starts exactly where the idle stands.
**Every move from whichever video had it clean** (Nov 27, the Bloodfang Wolf; SHOAIB: no remakes when a video can
be saved): its idle and snarling lunge come from its hit video's calm start (in that video it lunged and then turned
round: the lunge plays there and back, `pingpong`), its flinch and its collapse from its attack video (whose white
impact flash is dropped). Both videos start from the same picture with the camera still, so every move is placed as
the idle (`place_as`). **A move cut mid-motion eases in** (`ease_in`): the flinch and the collapse start while the wolf
is already moving, so a few frames are put in front that slide the standing idle toward the move's first frame and
dissolve into it, and the flinch settles back into the idle at its end (`settle` per move: `{"hit": 3}`).
**A white beast's video effects are dropped, never wiped** (Nov 27, the White-Browed Tiger King): `white` wipes
near-white pixels, which would wipe a white tiger's fur, so the frames with its swipe's white slash arc and its
flinch's impact star are left out (`drop`). Its flinch is only its first duck (the video then reared it up, head too
high), so its ducked pose is held a moment (`hold`) before it eases home (`settle`).
**A tail Veo grew long is trimmed back** (`trim_tail`, Nov 27, the Silver Monkey): its picture has a short curled
tail, but in its hit and death video Veo grew a long one that rose out of the top of the video. Each frame's body is
found by an opening with a disc thicker than the tail and thinner than the limbs; the thin piece left behind the body's
middle is the tail, kept as a short stub and faded out (and any faint half-cut tail tip the cutter left goes too).
**Moves eased in and settled out** (Nov 27, the Steel-Horn Bull): its two videos start from one picture, but by the
flinch Veo's bull held its head lower than the idle's, so every move eases in from the idle (`ease_in`) and the gore
and the flinch settle back into it (`settle` per move); only the gore, from the idle's own video, is placed as the idle.
**A sparkle painted into the beast is cut away** (Nov 27, the Ironbark Bear; `unstar`): a video made from the
uncleaned picture can keep Gemini's sparkle on the beast itself, redrawn solid and moving with it (on the bear's rump),
where the usual mark box can't find it. Per move, a box is searched for the pale, colourless patch with a bright core,
and it is cut away with the backdrop: a small notch at the beast's edge reads as nothing, a white star as a star.
**An idle has to move** (Nov 27 fix, the Ember Lizard, the Frost Wolf and the Thunder Hawk): a still first second loops without a jump
but looks frozen in the fight, so an idle is taken from a stretch where the beast visibly breathes, turns or dips its
head (`idle_from`/`idle_until`), even from the other video: the lizard's from the head dip at the start of its first
video, the wolf's from the slight turn of its head just before its bite, the hawk's from the turn of its head as it settles
after its flinch. The lizard's flinch is then placed by its own first
frame and eases in.
**A slow breath for an idle that hardly moves** (`breathe`, Nov 27, SHOAIB: "they are still barely moving"): the
Ember Lizard's, Frost Wolf's and Thunder Hawk's videos have no stretch where they really breathe, so their idle loop
is repeated to about one breath (2.4 s) and over it the body sinks a little from its planted feet and rises back (its
back lower by up to 3.5% of its height, less lower down; never taller, so nothing leaves its cell), its head end
swaying a touch back and forward. The loop's first frame is unchanged, so every move still starts and ends on it.
**The idle never jumps** (`smooth_idle`; SHOAIB: "it keeps resetting"): its last frame never quite met its first, so
a short idle plays forward then back, breathing in and out, and a long one (24+ frames) dissolves its last 6 frames
into its first; and it keeps its place in time when the page is replaced each turn (fight.js sets its
`animation-delay` from the clock) instead of starting over. `--smooth-idle <slug> ...` does it to an existing sheet.
Every sheet is loaded **and unpacked** ahead (fight.js `keep`, kept across turns) and a turn waits for them
(`whenReady`, 2.5 s at most): a big attack sheet (the bear's, the falcon's: about 18 megapixels) otherwise left the
beast invisible for half a second as it attacked, while the browser unpacked it.
`scripts/make_beast_sheets.py` cuts each into a frame sheet (`art/beasts/sheets/<slug>/`: `idle.webp`, `attack.webp`,
`hit.webp`, `death.webp` and `sheets.json`): every frame cut out of its backdrop, Gemini's mark, the floor shadow and
the idle video's stone slab dropped, 12 frames a second. Each video is placed on the beast's own picture
(`art/beasts/<slug>.png`: the same size of outline, the same ground line, its paws under the same spot) and all four
share one cell, so the beast never changes size or place between animations. The death video's wolf grows lighter
once it lies down, so its frames are recoloured to the hit video's (`match`).

On the fight screen (`web/beast_sheets.py`, `BeastSheets` in `fight.js`, "Beasts with animation frames" in
`style.css`) the frames take the still picture's place. That picture is never drawn: it only keeps the beast's size
and place, and every movement, flash and shake the fight gives it is copied onto the frames. One animation shows at a
time, fading over the last in 0.12 s:

- **Idle** loops while the beast stands (in CSS; with reduced motion it holds its first frame).
- **Attack** plays when it attacks you, 2.2 s (`CLIPS[...]["attack_ms"]`, the video at about 1.4x): it crouches in
  place, lunges to you, bites on its `bite` frame, the moment the damage shows, and goes back.
- **Hit** plays whenever it takes damage (your blow, a counter, a technique), in place of the knock-back; the flash
  and the damage number stay.
- **Death** plays when it is beaten (`death.view` kind `sheet`), the thud where it lands (`impact`), and it then
  lies on its last frame, also on a fresh page of the won fight.
- Its roar plays over its idle frames, turning on the roar's own pivot; while its jaws are open its open-mouthed roar
  picture (`art/beasts/roar/`) shows instead of the frames (`.beast.sheeted.roaring`), then the frames come back.
- **Kept apart:** its bite stops with its jaws at the cultivator's front (`bite_x` in `sheets.json`, `FRONT` in
  `fight.js`) and your Strike stops with the sword tip at its nose (`nose_x`), so neither runs into the other.
- Damage, rules and every other beast are unchanged.
- **Its own voice:** a beast whose videos gave it sounds (`sounds.json` keys `<sound>@<slug>`, e.g. `hit@wild_boar`)
  speaks with them (`web/explore_play.beast_body` puts its slug in `data-body`); every other beast keeps its body's
  voice (`@wolf`) or the made one.

**Adding the next beast** (one at a time, in roster order): its picture and roar picture (Nano Banana Pro, 16:9,
strict side view facing left, plain flat grey) cut by `scripts/make_quadruped_art.py`, its mouth in
`scripts/make_roar_fx.py` and `heads.json`; then its videos cut by `scripts/make_beast_sheets.py` (Flow's 1920 x 1080
is scaled to 1280 x 720; `white` drops a white slash streak the video drew for the unseen blow; `bite` sets the gore
frame by eye when an effect fools the measuring; `idle_until` / `idle_from` keep the idle loop to a calm stretch of the video;
`fade` softens a body that ran off the video's edge (`("top", px)` for a head reared out of it). Better: a beast
that rears, leaps or flies gets a start frame with plenty of room above it and "stays fully inside the frame" in its
attack prompt (the Old Black Bear's attack was remade that way);
`impact` sets the death's landing frame by eye; a move can be joined from several stretches of its video
(`((s0, s1), (s0, s1), ...)`: the Red Fox leapt out of the video mid-pounce, so its stalk, spring and landing snap are
joined); `drop` leaves out the frames an effect covered the beast in (the fox's hit and death starbursts); `mark`
gives tighter sparkle boxes (a pale tail tip lying over the sparkle is kept, as fur); `place_as` places a move as
another from the same video (the falcon flew further off before it died, so its death is placed as its hit); `floor`
keeps a move from sinking below the ground the picture stands on (a bird is drawn with its talons on it: its dive
skims the ground and it dies lying on it); `pingpong` plays a move there and back when the beast ran off
the video mid-move, as the Stray Dog's lunge). A roar picture can also be taken from its own video's
open-jawed frame (the Field Viper's). Then its sounds with `scripts/make_fight_sound.py NAME@<slug>`.

## Living backgrounds

The fight's background moves (`web/static/ambient.js`, beast fights and duels): one canvas at the very back of the
scene, behind the fighters, the beast and every effect, drawing its place's weather. Which weather is read off the
background picture:

| Background | Its video (and sound) | The canvas adds |
|---|---|---|
| Bamboo Forest | bamboo swaying, leaves drifting down, light rays, mist (birds, airy wind, rustling leaves, bamboo knocking*) | motes of light |
| Misty Pine Valley | fog rolling across the valley and the moss, clouds over the cliffs (wind, dripping water) | floating spores |
| Red Cliff Gorge | dust in the golden light, grass swaying, heat haze (warm desert wind, hissing grass, a far hawk*) | wind-blown sand streaks |
| Thunder Peaks | churning clouds, lightning on the peaks every few seconds, reflections (thunder, rain) | slanted rain, low mist |
| Northern Sea Wilds | the aurora flowing, snow and frost mist, the dark sea moving (wind, creaking ice, waves) | snow, icy wisps |
| Arena ruins (duels, the Ruins hunt) | the rune circle pulsing, motes rising, clouds past the moon (night wind, crickets) | faint ground mist |

**Background videos:** every fight place has SHOAIB's video of its painting coming alive (Nov 26: all six repainted
with Nano Banana Pro, 1376 x 768, and filmed with Veo), played behind the whole fight page under its shading (`video`
in `PLACES`). It fades in over the painting once it plays, and the canvas leaves out what the video already shows
(`skip`: the leaves and mist of the bamboo, the valley's mist, the gorge's gusts, the lightning, the arena's motes, the
aurora). Not with reduced motion or when the browser saves data: the painting shows.

**Their sound:** where the video has one, its ambience loops quietly under the fight (`sound`, art/scenes/<scene>.m4a,
at a third of the Settings volume): off with Sound Off or Music Off, paused while the tab is hidden, started by the
first tap or key if the browser held it back. *Bamboo Forest's and Red Cliff Gorge's videos came without sound, so
theirs is made by `scripts/make_ambience.py` from the other places' sound (the valley's birds and drips, the north's
wind) plus rustling leaves, bamboo knocks, desert gusts, grass and a hawk made in code, looped the same way.

**Standing on the ground:** each painting's open floor is at a known height (`GROUND` in ambient.js: 76-80% down the
picture). The fighters' feet sit at a fixed spot of the page, so the painting and its video are moved, and enlarged a
little when they must (at most ×1.35), until that row lies under the feet of the hero and the beast, on any screen
shape (`--arena-size` / `--arena-pos` on main.battle). Beast fights and hunts only; a duel keeps its framing. This
runs with reduced motion too, for the still picture.

`scripts/make_background_loop.py <scene> video.mp4 [painting.png]` makes them all: Gemini's sparkle (and, on the
gorge, the "AI" badge) covered with the ground just beside it on the painting and on every frame of the video, the
video's last 1.5 s faded into its start so it loops with no jump (8.5 s, H.264, about 2 MB), and the sound looped the
same way (AAC, about 100 KB).

The fight plays the video as **two copies taking turns** (`ambient.js` `film` and `twin`), not with the browser's
`loop`: jumping a looping video back to its start froze or flashed the background for a moment on some machines
(SHOAIB's PC: "the screen refreshes every 8 seconds"). Just before the shown copy ends, the other starts from its
first frame under it and the top copy fades (`SEAM`, 0.6 s); the jump back to the start happens on the hidden copy.

Nothing here touches the fight. The beast fight's page is replaced every turn; the same canvas moves into the new
scene, so the weather carries on. It stops while the tab is hidden, and with reduced motion it isn't drawn. Sizes are
shares of the scene, and the amount of leaves, snow and rain grows with its width, so a phone isn't crowded.

## Her movements

Her kick, Guard, fist, palm and finger are cut from SHOAIB's Nov 23 videos of her by `scripts/make_heroine_set.py`
(Gemini, 1280 x 720, 24 fps; each made from her stance picture, so it starts and ends in her stance, sword held low,
the move made with her free hand or her front leg):

| Sheet | What she does | Played by |
|---|---|---|
| `hero_female_kick.webp` | gathers, snaps a high side kick out, holds it, draws the leg back | Crescent Sweep, Swift Swallow Kick, Autumn Wind Kick, Meteor-Falling Kick |
| `hero_female_guard.webp` | raises the sword across her body, the blow bursts into sparks on it, she steadies and lowers it | Guard |
| `hero_female_fist.webp` | a quick jab, drawn back, a lunging punch | the Fist techniques |
| `hero_female_palm.webp` | arm drawn back, a lunging open-palm strike | the Palm techniques |
| `hero_female_finger.webp` | a deep lunge with two fingers thrust out | the Finger techniques |
| `hero_female_brace.webp` | sinks into a wide, low stance with her forearm raised, holds, rises | the bracing defence techniques (Horse Stance Guard, Golden Bell Cover, ...) |
| `hero_female_deflect.webp` | meets the blow with her open palm and carries it up and round behind her with her sleeve, in a swirl of grey wind | the deflection techniques (Parrying Arm, Flowing Stream Palm, ...) |
| `hero_female_sidestep.webp` | drops into a deep side lunge under the blow, holds, rises | Drifting Mist Steps and Cloud-Walking Shadow, when they slip a Break |

How they are kept from jumping: every video's first frame (her stance picture) is laid over her stance sheet's
first frame, at the scale and place where the two outlines overlap most, and every frame of that video is placed the
same way; the sheet's first frame is that stance picture, and its last is moved onto the first (`home`). Each sheet
has a cell of its own on the 1024 x 559 fight canvas (`box` in `looks.py`, as her Strike and Break have), so a long
kick or lunge is never cut off; the page places it from `box` (`explore_play.html`). Her Guard video loses the sword
for two frames just before the sparks: those are left out. Her step forward in the Guard video is taken out, since
the beast comes to her. The key frames (`jab`, `windup`, `release`, `back`, the Guard's `first`) and `hand` (her
fist, palm, fingertip or foot at the release, where the effects leave from) are printed by the script and stored in
`looks.MOTION_SHEETS` / `looks.GUARD_SHEETS`.

**Pace and loading (Nov 23).** Her moves were playing much faster than the beast's own attack (about 2.2 s for the
Grey Wolf): a Mortal technique squeezed several seconds of her video into 1.1 s. Each of her movement sheets now has a
least time (`ms` in `looks.MOTION_SHEETS`, about 2 s; `technique` in `fight.js` takes the longer of it and the
grade's own time, Nine Dragons keeps its own), her Guard raises over 0.62 s and plays on at 66 ms a frame, and her
Strike and Break are slowed by a quarter and an eighth (`blade` in `looks.ATTACK_SHEETS`). The stutter came from
loading: a technique's frames and effect pictures were first asked for when its turn arrived. The page now names
every picture the fighter's turns may need (`explore_play.preload`: Guard and attack sheets, each equipped
technique's movement and pictures; `data-preload` on the fighter), `fight.js` loads and decodes them when the fight
opens and keeps them (`keep`), and a turn is not acted out until its movement sheet is in (`whenReady`, at most
2.5 s). Only how long a turn takes to watch changed: the server has already resolved it.

**Her brace, deflect and sidestep** (the last three rows) came in a second set of videos the same evening and are
built by the same script (`python -m scripts.make_heroine_set brace=... deflect=... sidestep=...`), which also prints
what their players need: `body` (where her figure stands), and for the deflect `tip` (her sleeve's tip, furthest
behind her, at `sweep`). The deflect and sidestep videos paint the blow she meets (an ink blast, a white slash): it
can be bigger than she is, so the cut keeps the piece standing where she was in the frame before, not the biggest
one; the grey swirl joined to her sleeve in the deflect is kept. In the sidestep video she slides across the frame:
that is taken out, and the page gives the ground and takes it back as before (`give`). So all eight of her fight
movements, with her Strike, Break and stance, now start and end in the same stance. Presentation only: timing, damage and rules are unchanged.

**His movements (Nov 24): the new male.** The male cultivator was repainted to match her (white and blue robes),
and SHOAIB made his fight videos from his stance picture, as hers were: stance, Strike, Break, Guard (block), fist
(punch), kick, palm and finger. `scripts/make_hero_set.py` builds them all with her tools
(`python -m scripts.make_hero_set stance=... strike=... break=... guard=... fist=... kick=... palm=... finger=...`):
the stance loop first (placed where a cultivator stands, 72 frames, 5.08 s), then every other video laid on that
stance by its own first frame, so he goes stance, move, stance without a jump. His sheets are entered exactly as
hers (`looks.IDLE_SHEETS`, `ATTACK_SHEETS["male"]` with a sheet and `blade` timing per move, `GUARD_SHEETS`,
`MOTION_SHEETS[...]["male"]` with `box` and `ms`), so he plays at her pace: Strike 1.95 s, Break 2.53 s, Guard raised
over 0.62 s then 66 ms a frame, techniques no shorter than 2 to 2.2 s. He now has a kick of his own (the hop is gone).
The Qi painted in his Strike and Break videos is kept where it is joined to him. His three still poses
(`hero_male_idle/windup/strike.webp`) are frames of the new sheets. The old one-sheet attack (the passage on "The
**male** cultivator's attack" above) is no longer played. His brace, deflect and sidestep followed the
same day from three more videos (same script: `brace=... deflect=... sidestep=...`), keyed and paced as hers: brace
and deflect with `pace` 1.5, the sidestep at 10 frames a second (40 frames, 4 s) giving ground (`give`) as she does;
Cloud-Walking Shadow and Drifting Mist Steps both play it. His walk on the maps followed on Nov 25 (docs/hunting.md
"The new male on the maps"): the old male is gone everywhere.
Presentation only.

**Defences you can watch (Nov 24).** Two things. (1) When the beast struck no blow that turn (it Guarded), the
engine logs nothing for a defence technique, so the page played nothing: Cloud-Walking Shadow "did not show".
`explore_play.events` now adds the technique's event itself, marked `idle`, when the defence technique was the turn's
move and the log has none; `cast` gives an evade technique its sidestep look on such a turn too. `fight.js` plays the
sidestep ("Shadow step"), the brace or the deflect with the beast standing still: no lunge, no hit, no numbers.
(2) The brace and deflect were over in about 1.4 to 1.75 s. Their sheets carry `pace` (1.5 in `looks.MOTION_SHEETS`,
`data-pace` on the sheet, `paced` in `fight.js`): every beat of the exchange, the beast's charge included, is
stretched by it, so they take about 2 to 2.6 s; the sidestep plays at 10 frames a second (her 3.6 s, his 2.4 s).
Presentation only: the server has already resolved the turn; nothing in the rules, Battle Qi or damage changed.

## Her Strike and Break

The female cultivator's Strike and Break play frame by frame from SHOAIB's two videos of her (`looks.ATTACK_SHEETS
["female"]`, cut by `scripts/make_heroine_attacks.py`), each starting and ending in her fighting stance, so she goes
stance, attack, stance with no jump. Her still windup and strike paintings are no longer used in fights.

- **Strike** (1.56 s): she raises the sword, steps in and cuts in one diagonal arc (the fight draws its sword trail;
  the video's own arc couldn't be cut out cleanly), holds, and steps back into her stance.
- **Break** (2.26 s): blue Qi swirls round her (kept from the video), she leaps with the sword overhead and drives it
  down; the fight's own Break bursts there (the video's explosion is left out), she holds the landing while the dust
  rises, then rises and steps back into her stance.
- Each sheet has its own cell (`box` on the fight canvas: it holds the overhead sword and the leap) at the stance's
  scale, its own timing (`blade`, as `BLADE` in `fight.js`) and how far it reaches (`tip`: the dash stops her there,
  short of the beast). The video's leap across the frame is taken out: the fight's dash carries her.
- The male cultivator keeps his one sheet for both moves (`attack_sheets` gives it to each).

## Alchemy animations

The craft's cauldron comes alive with SHOAIB's alchemy videos (`.cscene` in `alchemy_play.html`,
`web/static/alchemy.js`, `scene_view` in `web/alchemy_play.py`). The clips (`art/fx/alchemy/`, made by
`scripts/make_alchemy_fx.py`: each cut to its own part of the frame, which leaves out Gemini's mark, loops faded
end into start) are effects on black, laid on the dark card with `screen`, so the black is see-through:

| Stage | What plays |
|---|---|
| Ignite | the fire under the cauldron, by the heat the gauge shows: low under 40°, right to 75°, too hot above |
| Add herbs | the fire; a splash of steam and sparks each time a herb goes in |
| Fuse, Seal the Core | the fire; the blue Qi swirl over the cauldron |
| Condense | the light spirals in once as the stage begins, then the pill pulses, brighter as its pulse rises |
| Pill Tribulation | its own scene: the storm over the chamber (`art/scenes/alchemy_tribulation.mp4`, a background loop), a lightning strike after each round |
| The cauldron explodes | the explosion over the cauldron, which then stays smoking |

Each decision reloads the page, so `alchemy.js` remembers the last stage it showed (sessionStorage) to know what just
happened. A clip shows only while it plays, so a slow one never covers the stills. The fire is chosen from the heat
on the gauge, never from the hidden safe zone. With reduced motion only the stills show. About 5 MB of clips in all,
and a page loads only its own stage's.

## Live alchemy

Every stage of the craft is played with the hands, not chosen from buttons (`web/alchemy_live.py`,
`web/static/alchemy_live.js`, the `#alive` section of `alchemy_play.html`). It is the default; **Classic buttons**
on the recipe page keeps the one-decision-at-a-time craft (for slow connections), remembered in a cookie. Classic no
longer reloads the page on each click (`static/alchemy_classic.js`): the choice is sent in the background and the
stage card swapped in place, keeping the cauldron's videos playing; only the result loads as a whole page.

A one-herb recipe (the Cleansing Pill: Star Dew only) has no order to find, so Discord and Classic give Add Herbs
100% for free; live controls still time each herb on the breath (`Craft.time_one_herb`).
Discord's `/craft` is unchanged.

| Stage | The hands | Scored by |
|---|---|---|
| 🔥 Ignite | hold Space / the button to pump the bellows, let go to cool; keep the heat in the golden band. Gusts come with an omen first; on harder grades the band sways | share of the time in the band (after a 1.5 s warm-up); 85% is a full score |
| 🌿 Add Herbs | the ring at the cauldron's mouth breathes; tap the right herb (or 1-4) as it swells to its fullest. Same order, clues and insights as the bot | right herb on the breath 100%, off the breath 70%, wrong or too slow a backlash (0, or 70% if forgiven) |
| ☯️ Fuse | Yin and Yang orbit; press Space when they meet | fusions ÷ needed, −15% per tap while they are apart |
| 💊 Condense | a dashed gold outline circles the pill; each beat a ring closes in on it from outside. Early beats' rings are thin and pale; the ready beat's is thick and gold: press as it lands on the outline. Dots under the pill count the beats. Harder grades send a false gold ring that turns red before it lands | the bot's pulse table: on the outline 100%, the ready beat but off it 70%, earlier less, cracked 20% |
| 🔒 Seal the Core | as Fuse, with the Beast Core: too few seals (or 3 unsteady taps) and it shatters | as Fuse, at least 30% |
| ⚡ Tribulation | each round is one bolt or a quick pair, warned in the clouds with a ring closing on the cauldron (and 3-2-1 for long warnings). 🔵 **blue**: Protect (Space / ↑) as the ring closes; raised earlier than 0.5 s before, the shield fades. 🔴 **red**, too strong to block: Dodge (← / →) toward the side marked SAFE; a fake-out flips SAFE once mid-warning. Rounds by grade: Mortal/Yellow blue·red·blue (2.2 s warnings), Mystic blue·red·red+blue (1.6 s), Earth red·blue·red+blue with fake-outs (1.3 s), Heaven red·blue+red·red+blue, more fake-outs (1.1 s). A short help card shows the first time | the bot's own: a round weathered is a strike blocked; all 3 = 9 patterns, else 8 |

The Tribulation's result lists every strike (🛡️ ⚡ 🛡️). The kind of each bolt and when it lands are public (the
page draws its ring); where a red bolt is safe from stays on the server until its warning shows.

**Instructions can be switched off**: a "Show instructions" checkbox on the recipe page (cookie `ma_help`, which
decides), a 📖 button in the scene (switching it back on shows every card again), or "Don't show instructions again" on
a card.

**First-time help:** each stage, and each harder challenge (band jumps, flare-ups, the volatile herb, the quickening
breath, reversing orbs, the chaos orb, the decoy ring, quickening beats, the Tribulation), is explained in a short card
the first time it comes up (remembered per browser), before the stage's clock starts.

**Herbs fly in:** a tapped herb's picture arcs from its button into the cauldron's mouth, spinning and shrinking, then
the splash plays. **The Condense pill comes alive:** pale → golden → white-hot beat by beat, a breathing halo, a tremble
on the ready beat, a burst of light on a precise press.

The clips' black is never quite black, so every clip fades out toward its edges (CSS masks), and the cards have no
backdrop blur (it would isolate them, and `screen` would show the clips' black).

**Sounds** (`static/alchemy_sound.js`) are made in the browser with Web Audio, no files: chimes for good moves, a
crack for bad ones, a warning rumble, thunder, the shield, a countdown tick, a soft note per pattern ring in the reveal.
The 🔊 button in the scene mutes them (remembered).

**The scene** is as big as the window allows (`min(680px, 100vh − 330px)`, never under 300 px) with the controls
compact below it; the Tribulation keeps the cauldron in the storm. In Ignite a big batch never squeezes the heat band under 10°
nor speeds it past tempo 1.35, and each extra pill calms the band's sway by a quarter (a Heaven ×3 batch was close to
unplayable).

### Difficulty: by grade, by rank, and the patterns

**Every timed press is precise, good or rough**, shown on the page ("✨ Precise!", "Good", "Rough…"), and scored
1.0 / 0.8 / 0.5. The good window is `WINDOW` seconds each side of the moment (Mortal 0.20 s … Heaven 0.12 s, the same
feel at any speed); half of it is precise. Ignite scores the share of time in the band, from nothing at 45% to full
at 95%. So the existing patterns follow the hands: rough play lands in the low patterns, good play the middle ones,
precise play the high ones, all still capped by the herbs' age. The pattern thresholds are unchanged.

**Higher grades add challenges**, not only speed:

| | Mortal | Yellow | Mystic | Earth | Heaven |
|---|---|---|---|---|---|
| Ignite | still band, 1 gust | band sways | 2 gusts | + the band **jumps** mid-stage (a flashing ghost band shows where, 1.2 s ahead) | + **flare-ups**: the heat surges, and pumping into one overheats |
| Herbs | | on the breath | misleading clues | + a **volatile** herb goes in on the out-breath (blue ring) | + the breathing **quickens** after two breaths |
| Fuse / Seal | | | steady orbits | + the orbs **reverse**, a **chaos orb** streaks through once just before a meeting (a tap on it is unsteady), windows ×0.9 | + three chaos orbs, the orbs drift then **rush** together, windows ×0.8 |
| Condense | slow rings | | red **decoy** ring | + the beats **quicken** | + the gold ring may come after fewer warm-up beats |

**Fuse** has no spare meetings: every meeting counts and a missed one scores nothing (Seal the Core keeps its one
spare). Its precise window allows only 0.03 s of network jitter (`GRACE_PRECISE`), the full 0.09 s only for good.

**Rank margin:** each alchemist rank above the recipe (3 at most) widens every window and the Tribulation's warning
by 6%, and calms the gusts and the band's sway. It never removes a challenge.

**Failing costs less:** an explosion leaves a third of each herb (rounded down) in the ashes, on the website and in
Discord alike (`crafting.salvage`, `alchemy.EXPLOSION_KEEPS`); a shattered Beast Core is still lost; Second Chance
still saves everything.

**Balance** (simulated players with timing spread ~0.16 s rough, ~0.09 s good, ~0.04 s precise; raw score before the
herb-age bonus, patterns uncapped):

| Grade | rough | good | precise |
|---|---|---|---|
| Mortal | 0.92 (8) | 0.98 (9) | 0.99 (9) |
| Mystic | 0.77 (6) | 0.91 (8) | 0.95 (9) |
| Earth | 0.62 (3) | 0.77 (6) | 0.86 (7) |
| Heaven | 0.56 (3) | 0.73 (5) | 0.83 (6) |

Three ranks above the recipe adds about one pattern. Basic recipes stay easy (their herbs usually cap them at 5
patterns anyway); Earth and Heaven need real precision. Every number is at the top of `web/alchemy_live.py`.


## The pill reveal

Behind every alchemy page plays SHOAIB's chamber video (`art/scenes/alchemy_chamber.mp4`, made by
`scripts/make_background_loop.py`, its first frame `alchemy_chamber.jpg` the still), darkened toward the edges.

During the craft the lid is on while the fire is lit (Ignite), lifted off for the herbs and the Qi (Add Herbs, Fuse,
Seal), and put back on to seal the pill in (Condense, the Tribulation); Classic shows the open cauldron on those same
stages. The cauldron is split into its body and its lid for this and the reveal (`scripts/make_cauldron_lid.py`: `cauldron_body.png`
with a dark open mouth, `cauldron_lid.png`): the lid rattles as the light builds, then blows off up and away.

A successful craft opens with a reveal (`#preveal` in `alchemy_play.html`, `static/alchemy_reveal.js`): the cauldron
shakes and a pillar of light rises, then **one pill per pill crafted** floats up out of it, one after another, into a
small fan over the cauldron (`pill_spots`: 1 to 5), glowing in the grade's colour. Each is about a quarter of the
cauldron's width. Their patterns etch on as rings, one at a time on all of them, while the count climbs (一纹 … 九纹),
then the rewards follow. A Perfect
pill gets slow-turning heavenly rays. About 4 s; it plays once per craft (sessionStorage), a reload or reduced motion
shows the finished picture. SHOAIB's reveal video (`art/fx/alchemy/reveal.mp4`, made by `scripts/make_alchemy_reveal.py`: only its light, its own
cauldron masked out) plays over the game's cauldron, its rim on the cauldron's mouth, tinted to the grade (silver
Mortal, gold Yellow and Heaven, blue Mystic, purple Earth). Without the file, a drawn pillar of light stands in. An explosion keeps its own scene.

**The engine is untouched.** A live stage only decides that stage's score and hands it to `Craft.settle` (or
`Craft.shatter_core`; the Tribulation goes through `Craft.act` with the bot's own strike directions). Patterns,
explosions, the Tribulation, EXP, toxicity, rewards and rank-ups are the bot's.

**The server is the referee.** The page shows a stage's intro, then sends `/alchemy/live/begin` and starts its own
clock at that moment; the server times every later press (`/alchemy/live/press`) from when that begin arrived, so the
network delay cancels out and each window allows 0.09 s of jitter. A press can't say when it happened. The herb order
and the lightning's direction stay on the server until the player could see them (the clues; the omen). A stage whose
time is up is settled on the next request, so walking away runs the craft out.

**Difficulty knobs.** `tempo = 4.5 / decision seconds` (0.7…1.6) sets how fast everything moves, so the grade, rank
relief, Swift Hands and the batch penalty all carry over. The heat band is the safe-zone width (rank, Furnace,
Steady Hand, batch); the Fuse/Seal window is the Yin-Yang tolerance; Seal allows one missed meeting while the seal
pass is 10+; misleading hints become false glints and a swaying band; wild herbs make the orbs meet irregularly.
Every number is at the top of `web/alchemy_live.py`.

**Balance** (simulated players, `qi` pills, the rank the recipe needs): a careful player lands a little above the
old buttons, a sloppy one below them, a skilled one reaches the herb-age cap nearly every time. Mortal pills stay
easy (about 15 s). The herb age still caps the patterns.

## Live forge

The forge played with the hands (`web/forge_live.py`, `web/static/forge_live.js`, the `#flive` section of
`forge_play.html`). It is the default; **Classic buttons** on the forge page keep the one-decision-at-a-time forge.
Discord's `/forge` is unchanged. All five stages are live (`/forge/live/act`, the button stages on the live page, stays
only for a forge started before that).

| Stage | The hands | Points (of 20) |
|---|---|---|
| 🔥 Ignite | hold Space / Pump to work the bellows (the smith pumps only while you do), tap V / Vent to dump heat (then it needs a moment); keep the forge in the band while the coals burn down, so resting cools faster and faster. Gusts come with a warning | the share of time in the band, from nothing at 45% to all at 95% |
| 🌡️ Heat | the blank glows in the furnace mouth, climbing dull red → cherry → orange → yellow → white; Space / Pull it out at the target colour (shown as a swatch). Past white it burns | the bot's own: the right colour 20, one off 10 |
| 🔨 Hammer | a glowing spot slides along the blank on the anvil: strike as it passes under the hammer (the dashed line). Bright ring → Hard (Space / J), soft spreading glow → Light (K), glow fading → Reheat (R). A good blow throws SHOAIB's spark burst and the blank takes shape | the bot's own: good strikes out of all |
| 💦 Quench | choose Water (1) or Oil (2), the bot's choice (water: narrow window, up to 20; oil: wide, up to 15); the glowing blade then cools in real time over SHOAIB's trough or bronze cauldron: Space / Plunge when the needle is in the band. The smith plunges it: steam bursts from the water, flames from the oil | the bot's own `_quench_points`: the window's middle half all, the window half, outside 2 |
| ✍️ Inscribe | the bot's rune and clue (it may lie on fine gear): draw each stroke on the plate in order: drag → horizontal, ↓ vertical, ↙ sweep, ↘ press, a tap is a dot, down then a curl back is a hook (or the stroke buttons: an arrow and the stroke's name). Each carved stroke glows gold, a wrong one cracks red; the rune glow blooms at the end | the bot's own: strokes right out of all |

Harder gear adds challenges, not only speed:

| | Ordinary | Refined | Spirit | Treasure | Divine |
|---|---|---|---|---|---|
| Ignite | coals burn down slowly | + a gust | 2 gusts, they burn faster | + the vent sticks for a while | + a flare-up |
| Heat | even | | the tip runs ahead: judge the middle | + the colour shimmers | + the last colours come faster |
| Hammer | a steady spot | | the spot speeds up and slows down | + a faint false spot crosses first | + some strikes want two blows |
| Quench | steady cooling | | draughts: it cools faster and slower | + steam hides the thermometer | + it cools faster near the target |
| Inscribe | the clue stays | | | the clue fades after 2.5 s: from memory | the clue fades |

The tempo is the gear tier's decision time with rank relief and Swift Hands (`4.5 / seconds`); the Ignite band is the
forge's safe zone (rank, fuel, Steady Hand); each blacksmith rank above the gear's (3 at most) widens the hammer's
window by 6%. A first-time help card explains each stage and challenge (the same 📖 switch and `ma_help` cookie as the
live alchemy).

**The scene** is SHOAIB's art (`art/forge/`): the workshop (`scripts/make_forge_art.py`: Gemini's mark painted
over) and his video of it (`workshop.mp4`, made from that same picture so everything stays lined up: candles, chimney
smoke and dust, looped by `scripts/make_background_loop.py`, over the still until it plays), his props and blanks keyed from green, and his smith as frame sheets of his videos
(`scripts/make_forge_sheets.py` → `<look>_bellows.webp`, `<look>_hammer.webp`, `sheets.json`): keyed, the green taken
back out of the sparks and hair, stepped by the page so the bellows move only while you pump and the hammer falls when
you strike. His anvil is laid exactly over the one inside the video (`CLIPS[...]["props"]`), so the hammer lands on it.
One smith at a time: at the bellows for Ignite and Heat, at the anvil for Hammer, over the trough or the cauldron for
Quench (his props laid over the video's bucket and bowl the same way); Inscribe lays the cooled piece on a plate before
you. **No smith is shown any more** (the page always has `.nosmith`, and his frame sheets aren't loaded): the forge is
gameplay first, and SHOAIB's effect videos carry the motion. The spark burst is `art/forge/sparks.mp4` (on black, laid on with `screen`).

**Without the smith** SHOAIB's effect videos carry the motion (`scripts/make_forge_fx.py`, which also leaves out
Gemini's mark): the furnace fire (`art/forge/fire.mp4`, a seamless loop on the coal bed, laid on with `screen`) grows,
brightens and roars faster with the heat in every stage; the hammer alone (`art/forge/tool_hammer.webp`, a frame sheet
keyed from green, `sheets.json` "tool") swings down onto SHOAIB's anvil at each strike, with its own sparks (a light tap
swings from lower), the video's anvil and bar cut away so only what moves stays; for Quench the hot piece hangs over the
trough or the bath, glowing with its heat, dips in at the plunge, and the steam (`steam.mp4`) or the oil's fire
(`oil_flare.mp4`) bursts from the surface.

**The camera, the HUD and the forecast.** The workshop's layers move together inside `.fcam`, so a stage's camera
glides to what it is about (the furnace for Ignite, the metal in its mouth for Heat, the anvil for Hammer, the trough or
the bath for Quench; for Inscribe the workshop falls back behind the piece) and holds still while you play. The hint,
the gauge, only this stage's controls and the timer sit in the bottom of the scene (under it on phones). Under the
stage chips the **rarity forecast** (`forge_play.forecast`, in the page and in every `/forge/live` state): the total on
a bar marked with each rarity's threshold, what the points so far **lock in** (were every stage left to score nothing),
the **best still possible** (were every stage left to score 20) and the gear's **cap** (tier and essence grade), all by
the bot's own `rarity_for_score` and `capped_rarity`, so it never shows a rarity the gear can't reach; rarities above
the cap are struck through on the bar.

**The feel of each action** (display only; the server alone scores): points float up from where you acted (the
hammer's, the heat's and the quench's are the server's own verdict from its reply to the press, the page's guess only if
none comes), consecutive good strikes and strokes build a combo, sparks burst gold for great actions and red for poor
ones, a good hard blow shakes the scene with a brief hit-stop, a fully clean rune resonates, and each stage's points fly
into its chip. Nothing waits on an effect.

**The piece changes as you forge it** (display only):
- **Ignite:** SHOAIB's bellows, cut from the workshop picture with the wall filled in behind them
  (`scripts/make_forge_bellows.py`: `art/forge/bellows.webp`, `bellows_wall.webp`), squeeze in a working rhythm while you
  pump and puff air from the nozzle. The fire surges on each pump, gusts blow streaks through the furnace mouth, and a
  flare-up reddens the room.
- **Heat, made readable:** tongs slide the metal into the coals and, when you pull it, draw it out into the light. The
  fire calms behind it and a dark bed lies under it so its colour reads. A colour ladder of the five colours under the
  scene rings the target. On plain gear the colour the metal has reached lights up there, with a ring, a flash and its
  name as it climbs; on gear that heats unevenly or flickers (Spirit and up) nothing lights and the hint doesn't name it,
  so you judge the metal itself. The metal glows and pulses more and throws more sparks as it heats.
- **Heat:** the metal wavers in the heat, more as it climbs (drawn in strips on its canvas: cheap, unlike an SVG
  filter). Past yellow it smokes and scorches dark, and burnt it cracks.
- **Hammer:** the piece glows as its state asks, squashes under each blow, and takes shape with every good one (a sword
  lengthens and thins, a chest plate or round plate spreads; `--sx`, `--sy`). A bad blow leaves a dent.
- **Quench:** the piece rises out of the water or oil hardened, as dark steel. After a good quench a sheen runs along it;
  after a poor one it comes out warped and dull.
- **Inscribe:** the hardened piece lies large on the plate. Each stroke burns into it, gold, or as a red crack where the
  server says it was wrong. Qi then flows along the clean strokes, and a fully clean rune flares white as it resonates.

**The reveal** (`static/forge_reveal.js`): SHOAIB's golden burst (`art/forge/reveal_burst.mp4`, on black, laid on with
`screen`) swirls in and flashes, tinted to the rarity (grey Common, green Uncommon, blue Rare, purple Epic, gold
Legendary, red Mythical), and at its flash (1 s) the forged piece appears in its rarity's colour; Legendary and Mythical
get a bigger burst, turning rays and his rune glow. Then the new passive and the rest follow. **A failed forge** plays his
glowing bar cracking apart in sparks and smoke (`art/forge/crack.mp4`; the page shakes it as it breaks) and it stays
broken (its last frame, `crack_end.jpg`, is the poster a reload shows). Each timeline starts when its video really plays,
with a fallback if it never does. Once per forge (sessionStorage); reduced motion shows the finished result.

**The third set** (`scripts/make_forge_fx.py`, all on black, `screen`): at a water quench his splash bursts from the
trough's surface and the steam rolls up after it (`splash.mp4`); while you carve, his golden magic circle turns engraved
in the stone under the piece (`rune_circle.mp4`, a loop cut from before its flare) and flares when a clean rune
resonates (`rune_flash.mp4`, the flare itself); a burst of golden sparks (`chisel.mp4`, cut from after the chisel leaves
the frame) flies where each good stroke is carved; and a Legendary or Mythical piece appears with a ring of spirit energy
turning around it (`aura.mp4`, a loop tinted like its burst, still turning after a reload).

**The second set of videos** (`scripts/make_forge_fx.py`): SHOAIB's pumping bellows (`tool_bellows.webp`, one pump keyed
from his paler green screen with lower thresholds, the stand in its corner cut away) stand beside the furnace with the
nozzle at the coal bed, and the painted ones on the wall are covered by the wall behind them. They pump only while you
hold Space, finish the stroke when you let go and rest open. His drifting embers (`embers.mp4`, a seamless loop) float
up through the whole scene, over the camera and under the HUD.

