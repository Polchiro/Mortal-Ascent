# Website (web game, step 1: login and profile)

The website is the same game as the Discord bot, in a browser. It shares the bot's **database** and
**game rules**, so a character is one character everywhere: progress made in Discord shows up on the
website, and later the other way round.

**Built:** Discord login, the player's real profile page, the inventory, the **forge**, **alchemy**, **gathering**
and **exploring (hunting alone or in parties of up to 4, docs/hunting.md) with turn-based fights** (all fully playable, saved to the same character), logout, and `/api/me` (the profile as JSON for the next pages).

**Next:** using items (Open, Take) from the inventory, training, and team hunts.
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
diamond, and the Journey as a parchment scroll with a wooden plaque per deed (icons from `art/icons/index/ov_*`,
`stat_icons` in `web/profile.py`). It is all CSS over the same template and data: nothing in the numbers,
forms or links changed. The appearance page keeps the plain panels (`.xpanel` without `.xprofile`).

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
- Pictures: each item's painting (`cards/art_icons.py`); chests use `art/chests/<rarity>.png` and
  manuals their technique's icon. Items with no painted file (the 39 essences) are drawn by the bot's own
  card code and served from `/art/drawn/<kind>.png` (`web/drawn.py`, drawn once and kept in memory), so they
  look exactly like the Discord cards.
- **Equip / Unequip** for weapons, armor and artifacts, in the Inspect panel. The rules are the bot's own
  (`loot.use_item`, `gear.equip_problem`): the realm a tier needs, one weapon and one armor, two artifacts of
  different families. Only the logged-in player's own gear can be changed, and the bot's message is shown.
- The profile page has an **Equipment** card: the four slots (weapon, armor, two artifacts) with what is worn,
  its effects, Unequip, and a link to the bag for an empty slot. HP / Attack / Defense follow at once.
- The website can't see a fight running in Discord. A fight reads the gear when it starts, so changing gear here
  during one counts from the next fight.
- Using and opening items (pills, chests, manuals) stays in Discord for now.

## The forge

`/forge` is the bot's `/forge` (docs/forge.md, section 5) in the browser, with the same engine:
`bot/forging.py` makes the plan, takes the materials, runs the five stages and writes the passive.

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
`town.page_data(near=)`); Gather's "To Herbalist Lan" does too.

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

## Gathering

`/gather` is the bot's `/gather` (docs/alchemy.md, section 2) in the browser, with the same engine:
`bot/gathering.py` (`Gathering`) rolls the herb, its age and the choices, checks the pick, stores the herb and keeps
the Herbal Insight streak, the Wandering Spirit check, the poison HP and the review flags.

1. **Start:** the streak, the odds per grade at the player's realm, and the Wandering Spirit's pause if there is one.
2. **Round:** the place (its painting is the background), the herb to find with its description, the numbered
   choice cards (each plant's drawing and LOOK text) and a timer bar. Keys **1–6** pick a card. The Wandering
   Spirit round shows four signs instead.
3. **Result:** the real herb ringed in green, a wrong pick in red, every plant named, then **Gather again** or **Stop**.
4. **The trip ends** (Stop, two idle minutes, or the spirit's pause): what was gathered this trip.

**Why this is fast with many players.** In Discord every round is a 1200×940 card drawn on the server, one at a
time for all players. Here the browser shows the page; the server only sends text and small pictures that are
drawn once and kept.

**The server referees.** Which choice is real stays on the server until the pick: the page has no plant names,
and each choice's picture is asked for by its position (`/gather/plant/<turn>/o2.png`), only for the page now
showing. The time for a pick is measured on the server, so a late right answer is still "too slow", and a closed
page times out. Old or repeated pages and unknown choices are ignored. One trip at a time per player, kept in
the website's memory. Rare finds (Earth, Heaven) are announced only when gathered in Discord.

## The town

`/town` (the **Town** tab) is the walkable town hub: walk up to the townsfolk, who send you on to the pages
below. docs/town.md.

## The World Map

`/world` is the painted scroll of the whole land: out through the town gate, then to a hunting ground (a Solo Hunt
on its walkable map, for everyone with a walking look) or back to town. Places your realm can't enter yet are sealed,
and the server checks it again when you set out. docs/world.md.

## The Arena

`/arena` and `/duel`: friendly duels against other players, on the beast fight's screen. docs/pvp.md,
"On the website".

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
   (`looks.fighter`: the player's cultivator in three sword poses) facing the beast's painting (`art/beasts/`), the beast's warning in the
   plate, and **four big moves** with keys 1–4 (`art/icons/actions/`): Strike, **Techniques** (a
   small menu with your attack and defense technique, their effect and Battle Qi cost), Guard, Break. **Mending Pill** (P)
   and **Flee** (F) are small buttons on the side. Hovering a move shows what it beats and its cooldown. After a
   turn a big word over your fighter says what happened (Countered!, Blocked!, Stunned!, Clash!, Guard broken!).
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
   `fight.js`; also used when he guards the Mountain Tiger's pounce). **Hers** is her own, bare-handed, from SHOAIB's
   video of her (`hero_female_guard.webp`, `scripts/make_heroine_guard.py`): her arms close into a crossed, side-on
   guard as the beast comes in, the blow lands on them in a white flash with her sleeves whipping round, and she
   steadies behind her crossed arms. Each sheet carries its own timing (`ready`, `first`, `ms` in
   `looks.GUARD_SHEETS`; his are `GUARD` in `fight.js`). **The stance:** while she stands between moves, in beast
   fights and in duels (mirrored when she is the other cultivator), the female cultivator plays her fighting stance
   (her still idle picture isn't on those pages at all): on guard, sword held low, breathing, her sleeves, hair and skirts stirring, a
   5.4 s loop (`looks.IDLE_SHEETS`, `hero_female_stance.webp`, 72 frames cut by `scripts/make_heroine_stance.py`
   from SHOAIB's video of her, her feet on the still's feet). The page steps through it in CSS (`.stanced`,
   `stancex`/`stancey` in `style.css`); with reduced motion she holds its first frame. He keeps his still picture.
   The beast is knocked back, flashes, and its HP bar and the damage number change at the
   moment of impact. Then the beast attacks in turn (its M1, `charge` with `RECIPES.gore`, from SHOAIB's beast attack
   video): it lowers its head, rears, charges in kicking up dust and gores, tossing its head up with its jaws open (its
   open-mouthed roar picture, where it has one); its mark torn across you as it hits, three red claw marks for a
   clawed beast (`beasts.CLAWED`, `art/fx/claw_marks.webp`) or a single bright slash for the rest
   (`art/fx/beast_slash.webp`), both SHOAIB's pictures, and dust where it hits, you are knocked back, your HP
   drops then, and it trots home.
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
   for its unique skill lands in the slam pose and roars. So far the Mountain Tiger, cut from SHOAIB's reference video
   (`scripts/cut_tiger_poses.py`, clean edges with no white fringe). The Discord card keeps the painting.
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
   - `kick`, shared by both genders: its timing and effects are defined once, and each look plays it with its own
     frames (`hero_<gender>_kick.webp` in `looks.MOTION_SHEETS`, made from that look's own picture so it keeps
     its appearance) or, until it has them (neither does yet), with its own three poses and a hop into the kick
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
   - `deflect` (`hero_female_deflect.webp`, `scripts/make_heroine_deflect.py`, from SHOAIB's video of her): the
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
   - `sidestep` (`hero_female_sidestep.webp`, `scripts/make_heroine_sidestep.py`, from SHOAIB's video of her): the
     sidestep, for **both cultivators** (his: `hero_male_sidestep.webp`, `scripts/make_hero_sidestep.py`: a low dash
     in place, wrapped in swirls of blue Qi, then his own launch frames played back to rise out of it, as his video
     holds the dash to its end; no ground given, `give` 0). Told below as she plays it. For the two evade techniques, Drifting Mist Steps and Cloud-Walking
     Shadow (`technique_fx.MOVES_FX`, `"on": "evade"`). It plays **whenever the technique leaves the cultivator
     untouched** (`explore_play.untouched`): the engine rolls the evade against the beast's Break (`bot/fight.py`,
     unchanged) and logs "slipped away from the ... Break" ("Slipped away"), or the technique takes a Strike with a
     full block, as a Guard does ("blocked 100%": "Evaded", with the Guard's counter). `explore_play.events` marks the
     technique's event `evaded` (and `slipped` for the Break). When a Break gets through instead, held in part, the
     technique keeps its CSS look. A beast's unique skill that is sidestepped is acted out by the sidestep alone (no
     second, harmless pounce). Played inside the beast's Break (`sidestepped` in `fight.js`): her frames one for one at the video's
     own pace (`fps`, 12 a second), never sped up, stretched or cropped. On guard, she sweeps her sleeve and drops
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
   beast with cut-out poses (the Mountain Tiger) takes its own roar pose while it holds; every other quadruped swaps
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
   head up with its open-mouthed picture: a starburst at its jaws, its body erupting in a spiky nova of its element,
   two shockwave rings racing out along the ground with dust, the camera punching in, and settles. Same rules,
   damage and log line.
   **The dragons roar** (`ROAR_ANIMATIONS["dragon"]`, from SHOAIB's dragon roar video of the Flood Dragon; `coil`,
   `gather` and `storm` in `fight.js`): each draws its head back while ribbons of its element coil up round its body,
   then rears and roars with its open-mouthed picture, an orb of crackling energy blasting at you
   (`art/fx/dragon_blast.webp`, from SHOAIB's picture, coloured by its element) with lightning streaks
   fanning out, its body bursting into a sphere of light with spikes and rings, mist pooling at its base, the camera
   punching in, and settles. Same rules, damage and log line.
   **The crocodiles bellow** (`ROAR_ANIMATIONS["crocodile"]`, from SHOAIB's crocodile roar video; `gather` and
   `bellow` in `fight.js`): each presses low as Qi gathers into its jaws, then throws its head up with its open-mouthed
   picture and bellows: rings of sound pulse out of its jaws, a burst of its element with a golden heart and spikes of
   light flares round its head, dust blasts up off the ground, the camera punches in, and it sinks back down. Same
   rules, damage and log line.
   **The tortoises roar** (`ROAR_ANIMATIONS["tortoise"]`, from SHOAIB's tortoise roar video; `charged` and `shell` in
   `fight.js`): each braces while its shell's runes light up and crackle with energy of its element, then lifts its head
   with its open-mouthed picture (the Xuanwu's serpent opens its jaws too) and roars: a cone of sound rings blasts at
   you, a great dome of its element swells round its whole body like a shield, mist rolls along the ground, the camera
   punches in, and it settles. Same rules, damage and log line.
   **The primates roar** (`ROAR_ANIMATIONS["primate"]`, from SHOAIB's primate roar video of the Silver Monkey;
   `vortex`, `beat` and `pound` in `fight.js`): each crouches, rises onto its hind legs and pounds its chest twice, a
   ring flying off its chest at each blow, while a whirlwind of its element spirals round it; then it roars with its
   open-mouthed picture, a sphere of its element bursting round its body with rings, streaks shooting out every way,
   shards flying and dust, the camera punching in, and settles. The Ancient Golden Ape moved here from the four-legged
   beasts. Same rules, damage and log line.
   **The insects hiss** (`ROAR_ANIMATIONS["insect"]`, from SHOAIB's insect roar video of the Venom Scorpion; `seep`
   and `venom` in `fight.js`): each crouches and rears with venom dripping and poison smoke gathering, then hisses with
   its open-mouthed picture: purple and green venom flames rising round its body, a sphere of poison bursting out with
   rings and droplets, and a low cloud of poison smoke left over the ground. Same rules, damage and log line.
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

A beast can be animated from four videos (SHOAIB's, Gemini: idle, attack, hit, death; so far the **Grey Wolf**).
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
- Its roar plays over its idle frames, turning on the roar's own pivot.
- **Kept apart:** its bite stops with its jaws at the cultivator's front (`bite_x` in `sheets.json`, `FRONT` in
  `fight.js`) and your Strike stops with the sword tip at its nose (`nose_x`), so neither runs into the other.
- Damage, rules and every other beast are unchanged.

## Living backgrounds

The fight's background moves (`web/static/ambient.js`, beast fights and duels): one canvas at the very back of the
scene, behind the fighters, the beast and every effect, drawing its place's weather. Which weather is read off the
background picture:

| Background | What moves |
|---|---|
| Bamboo Forest | autumn leaves falling and turning, low mist, motes of light |
| Misty Pine Valley | banks of mist drifting through, floating spores |
| Northern Sea Wilds | wind-blown snow, the aurora brightening and fading, icy wisps over the ice |
| Red Cliff Gorge | wind-blown sand streaks and, now and then, a gust of dust |
| Thunder Peaks | slanted rain and, every 5-11 s, lightning: the sky lights up and a bolt flickers |
| Arena ruins (duels) | moonlit fireflies, faint ground mist |

**Background videos:** a place can also have a video of its painting coming alive, played behind the whole fight
page under its shading (`video` in `PLACES`; so far **Frostpeak Mountains**, `art/scenes/battle_northern_sea_wilds.mp4`:
the aurora flowing, mist and snow drifting, the open water shimmering, the ice where the fighters stand still). It
fades in over the painting once it plays, and the canvas leaves out what the video already shows (`skip`: the
aurora). Not with reduced motion or when the browser saves data: the painting shows. SHOAIB's Gemini video becomes the
loop with `scripts/make_background_loop.py <scene> video.mp4`: Gemini's mark filled from around it, the last 1.5 s
faded into the start so it loops with no jump (8.5 s), H.264 with no sound (about 2 MB).

Nothing here touches the fight. The beast fight's page is replaced every turn; the same canvas moves into the new
scene, so the weather carries on. It stops while the tab is hidden, and with reduced motion it isn't drawn. Sizes are
shares of the scene, and the amount of leaves, snow and rain grows with its width, so a phone isn't crowded.

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

**The reveal** (`static/forge_reveal.js`): SHOAIB's rune glow (`art/forge/rune.mp4`) blooms over the result, and at its
flash the forged piece appears in its rarity's colour; Legendary and Mythical turn heavenly rays behind it. Once per
forge (sessionStorage); a reload or reduced motion shows the finished picture. A failed forge shakes its cracked piece.

