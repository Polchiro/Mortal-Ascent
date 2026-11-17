# Hunting — Explore on the website

On the website, **Explore** is a realm-based hunt: alone, or in a party of up to 4. It reuses the game's own
systems (the beast roster, the fight engine, the rewards, the explore rest) and adds only the party around
them. Discord's `/explore` is unchanged.

Code: `hunting.py` (locations and numbers), `web/parties.py` (parties), `web/hunt_play.py` (the hunt),
`web/hunt_pages.py` (page data), `web/hunt_routes.py` (pages). Tests: `tests/test_hunting.py`, `tests/test_web_hunt.py`.

## The entry (`/explore`)

| Option | What it does |
|---|---|
| **Solo Hunt** | A hidden party of one: choose a hunting ground and the hunt starts at once |
| **Create a Team** | Name the party (3–24 characters) and pick **Public** or **Private** |
| **Find a Team** | The public team browser, and a box for a private party's invitation ID |

An expedition already under way from the old flow (or an `/admin web_fight` test fight) still opens on `/explore/play`.

## Parties

- Up to **4** hunters, the leader included. A player is in **one** party at a time.
- **Public:** listed in the browser with its name, leader, leader's realm, members / 4, destination and
  Recruiting / Full. Anyone eligible can join straight away.
- **Private:** not listed. It has a 6-character **invitation ID** (no 0/O or 1/I). The leader can make a new
  one, and the old ID stops working at once. Ten wrong IDs in 10 minutes and a player must wait.
- You can't join a full party, a party already out hunting (nobody joins halfway), or a party whose chosen
  ground needs a higher realm than yours.

| | Leader | Member |
|---|---|---|
| Choose the hunting ground | ✓ | |
| Start the expedition | ✓ (when every member is Ready) | |
| Remove members, disband | ✓ (not during a hunt) | |
| Public / Private, new invitation ID | ✓ | |
| Ready / Not ready | (always ready) | ✓ |
| Leave | ✓ | ✓ |

Choosing a new destination clears everyone's Ready. If the leader leaves, the longest-standing member leads.

**Disconnected players.** A lobby page checks in every few seconds. A member unseen for **3 minutes** is taken
out of the lobby (the leader too), and an empty party is gone. During a hunt the turn timers take over (below).
Parties live in the website's memory, like a forge in progress: a website restart ends them, and nothing is
lost, because loot is only ever banked in the database.

## Hunting grounds

| # | Location | Beasts of (entry: the first realm or higher) | Arena |
|---|---|---|---|
| 1 | Moon Forest | Mortal – Martial Apprentice | Bamboo forest |
| 2 | Crimson Gorge | Martial Warrior – Martial Expert | Red cliffs |
| 3 | Frostpeak Mountains | Martial Master – Grandmaster | Frozen sea |
| 4 | Thunderfall Valley | Martial Lord – Martial King | Thunder peaks |
| 5 | Ancient Battlefield | Martial Emperor – Martial Ancestor | Moonlit ruins |
| 6 | Celestial Forbidden Lands | Martial Saint | Blessed glade (card) · misty pines (fight) |

- A ground's beasts are the **existing roster** of its realms (`beasts.BEASTS`), so 12 beasts each, 6 for the
  Saints. No beast is new or renamed.
- **Entry needs the ground's lowest realm or higher.** Higher realms may hunt anywhere below them: a Martial Saint
  can go to every ground. Every member must meet it to set out.
- The beasts are always as strong as the party's **strongest** member (below), and rewards follow each hunter's own
  realm, so a high realm hunting a low ground fights and earns at its own level: only the beasts' names and kinds change.
- Each card shows its art, text, requirement (Your realm / Open / Realm too low), its beasts with
  Elite and King marked, and its rewards: Lotus Coins, Beast Cores, chests, the forge materials of its realm
  tiers and the essences of its beasts' elements.
- To change a ground's realms, text or art, edit `LOCATIONS` in `hunting.py`.
  The art reuses existing scenes for now.

## The hunt

1. **Setting out** checks every member (right realm, not injured, not resting) and starts the **30-minute
   explore rest** for all of them. The rest is shared with Discord's `/explore`.
2. **Up to 5 beasts**, one after another, like the 5 steps of `/explore`. After each beast the leader chooses
   **Hunt the next beast** or **Return home**. A member can **Leave the hunt** between beasts. With no decision
   for 2 minutes, the party heads home.
3. **Which beast:** a random one from the ground's roster. It is an **Elite** or a **Beast King** exactly as often
   per step as an Elite lair or a Beast King's den is in `/explore` (with the same deeper-step boost), and a
   Normal beast otherwise. So a hunt meets Elites and Kings no more often than Discord does.
4. **Its strength** follows the existing rules, measured on the party's strongest member:
   - Normal: `combat.beast_stats` (+10% a step deeper, like `/explore`), +20% HP for each fighter beyond one.
   - Elite / Beast King: `hunt.team_beast`, exactly as a Discord lair hunt.
5. **The fight** is `bot/fight.Battle` with every member in it, on the website's fight screen (arena of the
   location). Each hunter picks **one** move a turn (a pick is final). The turn plays when everyone has picked,
   or after **30 seconds**: whoever hasn't picked Guards, and three timeouts in a row flee, as in Discord.
   Alone, there is no turn timer. The screen shows the party's chips (Choosing / Ready / Fallen) and a turn bar.
   Pages poll the server, so a turn resolved by others is acted out on your screen too.
6. **HP carries over** between beasts. A hunter who falls watches the rest of that fight, then goes home
   **defeated**: half the coins and herbs they carry are lost, and they are injured for 1 hour (`Expedition.finish`).

## Rewards

Every hunter rolls their **own** rewards. Nobody competes for a drop, and nothing new is paid.

| Beast | Pays (per hunter still standing) | Banked |
|---|---|---|
| Normal | `Expedition._beast_result`: coins, chest chance, Beast Core, materials | On the walk home |
| Elite / Beast King | `hunt._pay`: coins, chest, Beast Core, materials, `beasts_slain`, King kills | At once |

Mastery EXP from techniques, `beasts_slain`, the explore and beasts quests, and bag-full handling are the
bot's own. A hunter who fled gets nothing for that beast.

## Server-side checks

Membership, invitation IDs, leader rights, minimum realms, readiness, rests, injuries, one move per turn,
turn deadlines and every reward are decided in `web/parties.py` and `web/hunt_play.py`, under one lock. The pages
only show what those allow. The browser never sees which beast is coming or how a turn will go.

## The map (Solo Hunt, admins only for now)

A Solo Hunt can be walked: instead of the next fight starting from a button, the beast waits on a walkable
isometric map of the hunting ground, and the fight starts when you walk up to it. **Only when** changes: which
beast it is, how strong and what it pays are the same as above (`Hunts._roll` rolls it exactly as before, from the
same random numbers; `_battle` builds the same fight).

- **Who:** admins (`ADMIN_IDS`) on a Solo Hunt, with a look that has a walking sheet (`looks.WALK_SHEETS`: the male
  and female cultivators). Everyone else keeps the menus. Code: `web/hunt_map.py`, `Hunt.map` in `web/hunt_play.py`,
  `web/templates/hunt_map.html`, `web/static/huntmap.js`. Tests: `tests/test_hunt_map.py`.
- **Walking:** W A S D or the arrow keys (Shift: stroll), or the on-screen joystick on touch screens; both feed one
  movement vector in screen space. The sheet row follows the direction (8 sectors with a little hysteresis); the
  frames advance with distance walked (one stride per 96 px at 120%), so the feet don't slide; standing still holds
  each row's feet-together frame.
- **The map:** a 24 x 24 tile diamond (2:1, 128 x 64 px tiles), the outer edge forest. A location with a painted
  map (`hunt_map.MAPS`: Moon Forest so far, `art/maps/moon_forest.webp`, SHOAIB's painting fitted to the diamond)
  shows it and blocks what stands on it (circles in tiles: the shrine, the old tree, boulders, the pond; the stream
  is shallow and the stepping stones cross it). Server and page share one walkable test. Other locations keep the
  ground drawn in code. Press **G** on the map for the tile grid, the walkable edge and the blocked circles, with your
  position, to check a map against its painting.
- **The server referees:** the page reports where you are a few times a second (`POST /hunt/pos`); a position off
  the map or further than you could have walked since the last one is refused and you are put back. The fight
  starts only if the server has you within 1.6 tiles of the beast (`what=engage`). After a fight the next beast is
  already out on the map; after the fifth, walk on or **Return home**. Ten minutes without a step and you head home.
- **The walking sheet** (spec): one PNG per animation, transparent, 8 rows **S SW W NW N NE E SE**, cells
  **256 x 256**, the point between the feet at **(128, 232)**, about 200 px tall, walking in place; walk 8 frames,
  idle 4. `scripts/make_hero_walk.py` builds his from SHOAIB's walk video and refuses a sheet that breaks the spec.
  His video never faced left, so SW, W, NW are mirrored; there is no idle sheet yet.
  `scripts/make_heroine_walk.py` builds hers from five videos, one per view (front, front-right, right,
  back-right, back), each walking in place facing one way; it takes the stride that loops best from each and
  mirrors the right side for the left. New animations should come this way: one video per view, from a reference
  image already turned to that view.
