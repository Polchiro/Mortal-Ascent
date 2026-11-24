# Techniques

Two types only:
- **Attack technique** — used to deal damage
- **Defense technique** — used to block incoming damage

## Grades

| Grade | Can learn from realm |
|---|---|
| Mortal | Mortal |
| Yellow | Martial Apprentice |
| Mystic | Martial Expert |
| Earth | Grandmaster |
| Heaven | Martial King |

## Mastery stages

| Stage | Name | Effect multiplier |
|---|---|---|
| 1 | Glimpsing the Gate | ×1.00 |
| 2 | Entering the Hall | ×1.10 |
| 3 | Pure Flame | ×1.20 |
| 4 | Divine Transformation | ×1.35 |
| 5 | Return to Simplicity | ×1.50 |

Mastery EXP comes from /practice, /spar and using the technique in fights.

Mastery EXP needed to reach each stage (Mortal grade):

| To stage | EXP |
|---|---|
| 2 | 500 |
| 3 | 2,000 |
| 4 | 6,000 |
| 5 | 15,000 |

Higher grades need more EXP: Yellow ×2, Mystic ×3, Earth ×5, Heaven ×8.

## Training speed bonus

Better techniques make realm training faster.
Bonus to training EXP (at stage 1, before mastery multiplier):

| Grade | Training EXP bonus |
|---|---|
| Mortal | +5% |
| Yellow | +10% |
| Mystic | +15% |
| Earth | +25% |
| Heaven | +40% |

- Only the **best** equipped technique counts (bonuses do not stack)
- Mastery multiplier applies (e.g. Heaven at Return to Simplicity = +40% × 1.5 = +60%)

## Effects on stats (at stage 1, before mastery multiplier)

### Attack techniques

| Grade | Skill damage multiplier (when used) | Passive Attack % (while equipped) |
|---|---|---|
| Mortal | ×1.20 | +2% |
| Yellow | ×1.35 | +4% |
| Mystic | ×1.50 | +6% |
| Earth | ×1.70 | +9% |
| Heaven | ×3.00 | +12% |

### Defense techniques

| Grade | Damage blocked (when used) | Passive Defense % (while equipped) |
|---|---|---|
| Mortal | 20% | +2% |
| Yellow | 25% | +4% |
| Mystic | 30% | +6% |
| Earth | 40% | +9% |
| Heaven | 65% | +12% |

- Mastery multiplier applies to all four values
  (e.g. Heaven attack at Return to Simplicity = ×3.00 × 1.50 = ×4.50 damage)
- "Damage blocked" counts against a **Break** too: Break still beats Guard (you're staggered), but a defense
  technique holds its block % of the Break (a plain Guard holds nothing). Unbreakable then halves what's left.
  It also adds to a plain Guard's 50% against a charged attack.
- Damage blocked can never go above 80%
- Passive % buffs add into the buff totals in stats.md
- The 30% one-hit cap in stats.md still applies to every technique

## Technique slots

| Realm | Slots |
|---|---|
| Mortal | 2: 1 attack + 1 defense |
| Martial Warrior | 3: adds 1 flex slot (attack or defense) |

- Flex slot lets players build aggressive (2 attack + 1 defense) or tank (1 attack + 2 defense)
- The Flex technique is a **third technique in every fight** (beast fights, duels, sparring), with its own button
  (`flex_tech`): an attack technique there plays as a Strike, a defense one as a Guard, with its own effect,
  Battle Qi cost (beast fights) or rest turns (duels, sparring), and its own mastery EXP. Each slot rests on its own.
- Which one is Flex: the first attack and the first defense technique equipped hold the Attack and Defense slots;
  the next one of either kind is Flex (`bot.player.split_techniques`)
- Techniques can only be swapped **outside** of fights

## Schools

All techniques are unarmed. Weapons only give stat buffs (see equipment.md later).

| School | Style |
|---|---|
| Fist | Direct power |
| Palm | Flowing, controlling |
| Finger | Precise, piercing |
| Leg | Fast kicks, sweeps |
| Body | Defense and endurance |

## Technique effects

Each technique has one special effect. Grade and mastery multipliers still apply
to damage and block; the 30% cap applies to **total damage in one turn**.

### Attack effects
| Effect | What it does |
|---|---|
| Combo | Hits several times at reduced damage per hit |
| Pierce | Ignores part of the defender's Defense |
| Stagger | If it lands, the defender's next block is weaker |
| Heavy | Extra damage, but rests 1 turn longer after use (see Cooldowns) |

### Defense effects
| Effect | What it does |
|---|---|
| Counter | Reflects part of the blocked damage back; turns a Break aside 80% of the time (no damage, the share reflected). Costs 15 more Battle Qi |
| Recover | Heals a % of max HP when it blocks |
| Unbreakable | Break moves deal half of what gets past the block |
| Evade | Always dodges a Break when used (and a beast's charged Strike), for its Battle Qi |

### Cooldowns in fights

Techniques can't be spammed. After a technique is used in any fight (spar,
trials, explore, hunts, PvP later) it must rest for a number of turns before it
can be used again. Basic Strike, Guard and Break are always available.

| Grade | Cooldown after use |
|---|---|
| Mortal | 1 turn |
| Yellow | 1 turn |
| Mystic | 2 turns |
| Earth | 2 turns |
| Heaven | 3 turns |

- Heavy techniques rest 1 extra turn
- In /spar the technique button is greyed out and shows the turns left
- In explore fights and hunts (combat.md) the technique buttons are greyed out the same way
- No Qi cost: Qi is cultivation progress, not a fight resource

## Technique list

Names grow grander with grade: Mortal = plain actions, Yellow = animals,
Mystic = forces of nature, Earth = landscapes and legends, Heaven = cosmic.

### Mortal grade
| Technique | Type | School | Effect |
|---|---|---|---|
| Iron Fist | Attack | Fist | — |
| Twin Palm Strike | Attack | Palm | Combo: 2 hits × 60% |
| Crescent Sweep | Attack | Leg | Stagger: next block −15% |
| Horse Stance Guard | Defense | Body | Recover 2% |
| Parrying Arm | Defense | Body | Counter 10% |
| Calm Breath Stance | Defense | Body | Recover 3% |

### Yellow grade
| Technique | Type | School | Effect |
|---|---|---|---|
| Fierce Tiger Claw | Attack | Fist | Stagger: next block −25% |
| Swift Swallow Kick | Attack | Leg | Pierce 15% |
| Raging Bull Fist | Attack | Fist | Heavy ×1.2 |
| Iron Cloth Body | Defense | Body | Unbreakable |
| Flowing Stream Palm | Defense | Palm | Recover 5% |
| Crane Wing Deflection | Defense | Palm | Counter 15% |

### Mystic grade
| Technique | Type | School | Effect |
|---|---|---|---|
| Rolling Thunder Palm | Attack | Palm | Stagger: next block −50% |
| Viper Fang Finger | Attack | Finger | Pierce 25% |
| Autumn Wind Kick | Attack | Leg | Combo: 3 hits × 40% |
| Moon Mirror Palm | Defense | Palm | Counter 25% |
| Drifting Mist Steps | Defense | Body | Evade (always dodges a Break) |
| Rooted Mountain Stance | Defense | Body | Unbreakable |

### Earth grade
| Technique | Type | School | Effect |
|---|---|---|---|
| Mountain-Shattering Fist | Attack | Fist | Heavy ×1.3 |
| Thousand Shadow Palm | Attack | Palm | Combo: 3 hits × 45% |
| River-Splitting Finger | Attack | Finger | Pierce 30% |
| Golden Bell Cover | Defense | Body | Unbreakable |
| Ancient Turtle Shell Art | Defense | Body | Recover 8% |
| Thousand Hands Deflection | Defense | Palm | Counter 30% |

### Heaven grade
Heaven techniques are **ultimates** (Nov 25): attacks hit for ×3.00 (was ×2.00), defences hold 65% (was 50%), their
**A Heaven attack technique always lands** (Nov 25, `battle.sure_hit`): it cannot miss a Hidden enemy or be dodged
(Swift beasts, the Feather artifact), and no Guard or defence technique stops it; the caster is not Stunned by a
Guard. A clash with the enemy's own Strike still halves it. Beast fights and duels alike. Their
effects are about half again stronger (Pierce 40% to 60%, Counter 40% to 60%, Recover 12% to 20%; Meteor-Falling
Kick keeps Heavy ×1.5, which multiplies the ×3.00: ×4.5 a Strike, was ×3), and they cost **70 Battle Qi** (was 50; Void Mirror Stance 85). Everywhere: beast fights, duels, spars, Discord.

| Technique | Type | School | Effect |
|---|---|---|---|
| Heaven-Rending Palm | Attack | Palm | Pierce 60% |
| Nine Dragons Ascending Fist | Attack | Fist | Stagger: opponent can't Guard next turn |
| Meteor-Falling Kick | Attack | Leg | Heavy ×1.5 |
| Void Mirror Stance | Defense | Palm | Counter 60% |
| Immortal Lotus Body | Defense | Body | Recover 20% |
| Cloud-Walking Shadow | Defense | Body | Evade (always dodges a Break) |

## Training mastery

Mastery is trained separately from realm training (/train).
Three ways, all requiring the player's attention (no AFK).

### 1. /practice <technique> — Training challenges

(On the website Practice is a real-time drill instead: "Practice on the website" below. The pay is the same.)

- Each session rolls a random challenge from the shared pool in **challenges.md**
- Difficulty tier = the technique's mastery stage
- Base EXP: 40 mastery EXP × score
- Cooldown: 30 minutes

### 2. /spar — training fight against a master NPC

- Short fight using the combat moves (Strike / Guard / Break), on the fight screen (combat.md):
  15 seconds per exchange, no pick = Guard, three timeouts in a row = forfeit
- Master has patterns that hint at their next move
- Mastery EXP only for using the technique **at the right moment**
  (e.g. attack technique right after the master's Strike is blocked)
- +30 EXP per well-timed technique use, +100 EXP for winning
- Master is the same realm and layer as the player
- Cooldown: 2 hours

### 3. Mastery trial — stage breakthrough

- When the EXP bar is full, the player must pass a trial to reach the next stage
- Trial = /spar against a stronger master

| To stage | Master strength |
|---|---|
| Entering the Hall | ×1.2 |
| Pure Flame | ×1.4 |
| Divine Transformation | ×1.7 |
| Return to Simplicity | ×2.0 |

- Fail: no EXP lost, 24-hour cooldown before retrying

### Real fights

- +20 mastery EXP each time the technique is used against beasts or in PvP

### Anti-AFK rules

- Button positions shuffle every round (stops auto-clickers)
- Daily diminishing returns:
  - /practice: first 5 sessions full EXP, next 5 at 50%, then 10%
  - /spar: first 3 sessions full EXP, then 50%

## On the website: the training yard

Talk to the **Martial Master** in Azure Cloud Town's training yard (or open `/training`). Same spar, same trials,
same rewards: the fight is `bot/sparring.Spar` (the object `/spar` plays) and a finished spar gives exactly what
`/spar` gives (the well-timed EXP, the win bonus, the daily rates, a trial's breakthrough or its 24-hour wait, the
quest counts, the two-hour rest). The rest and the daily count are the same saved ones, so a spar on Discord counts
here and the other way round. Code: `web/spar_play.py` (the referee), `web/spar_routes.py`,
`web/templates/training.html`, `spar.html`, `web/static/spar.js`, `spar.css`, `spar_music.js`, `web/spar_master.py`.
Tests: `tests/test_web_spar.py`.

- **The yard** (`/training`): your equipped techniques with their mastery bars, a **Spar** button (with the
  master's rest, your injury, and how many full-EXP spars are left today), and a gold **Take the trial** button on
  each technique whose bar is full (with the trial's own 24-hour wait if it failed).
- **The fight** (`/spar`) is the beast fight's screen: your cultivator on the left with their own frame-by-frame
  movements (the stance, Strike, Break, Guard, and each technique's fist / palm / kick / finger / brace / deflect
  movement with its picture), the Master on the right, the four big buttons (keys 1-4: Strike, Techniques, Guard,
  Break), Yield (F) and Battle History (H). An ordinary spar is in the training yard at sunset; a trial in the hall
  at night.
- **Reading him:** his **tell**, when he gives one, is a line of brushwork above him ("His face gives nothing
  away" when he doesn't). Fifteen **beads** across the top fill as the exchanges pass, each with the move he made
  and gold / red / grey for won / lost / even: his rhythm is there to read. The page is never sent his move for the
  exchange being played, only his tell and what he did in the exchanges already over.
- **The opening:** after you Guard his Strike, the Techniques button and your attack technique glow gold
  ("Perfect timing now!"). A well-timed technique flashes **Perfect timing!** and puts a gold dot on its bead; the
  line under your HP counts them.
- **The result** shows each technique's mastery bar filling, the notes (no well-timed technique, the daily rate, a
  bar now ready for its trial) and, for a trial, the breakthrough or the wait.

Only the web's own (none changes what a spar gives):

| | Discord | Website |
|---|---|---|
| How hard he is to read | the same for everyone | **grows with your realm** (below) |
| Time per exchange | 15 s | **20 s** (the round trip, as in the Arena) |
| Buttons | shuffle every exchange | **stay put** (keys 1-4); the timer and three timeouts = forfeit still end an idle spar |
| Walking away | three timeouts | three timeouts, or the **Yield** button (the same forfeit: nothing earned, the rest stays) |
| A dodge or deflection technique | - | its sidestep / deflect movement plays only when his blow really was stopped; otherwise the plain Guard |

**Reading him gets harder with your realm (website only; SHOAIB, Nov 24).** His stats never change (your own realm
and layer, times a trial's strength); what changes is how readable he is (`web/spar_play.READS`, `YardSpar`):

| Your realm | He shows a tell | His rhythm | He breaks it | Feints (share of his tells) |
|---|---|---|---|---|
| Mortal to Martial Warrior | 50% | 3-4 moves | 15% | none |
| Martial Expert to Grandmaster | 40% | 3-5 | 20% | 10% |
| Martial Lord to Martial Emperor | 35% | 4-5 | 25% | 20% |
| Martial Ancestor, Martial Saint | 30% | 4-6 | 30% | 30% |

The first row is Discord's `/spar` exactly (the same object, roll for roll), and Discord uses it at every realm. A
**feint** is a tell that describes the wrong move and ends with a small sign of the real one, as Read the Master's
deceptive tells do (`bot/trainer.HIDDEN_SIGNS`: "...yet his rear fist is clenched tight" a Strike, "...yet his elbows
stay tucked in" a Guard, "...yet his front heel lifts off the ground" a Break). On a feint his pose is the move he
pretends; only the words give the real one away. Trials use the same table, with their strength on top. Rewards are
unchanged. The yard's page says how he reads at your realm.

**The Master's movements** (`art/spar/master/`, `web/spar_master.py`; cut from SHOAIB's videos by
`scripts/make_master_sheets.py`, which says what he does in each): the **stance** he breathes in, **Strike** (a palm),
**Guard** (forearms raised; a blow lands on them in sparks), **Break** (gold Qi gathered, then slammed), his **hit**
(staggered by your blow), his **kneel** (when you win he drops onto one knee, at the video's own pace with its sound,
and the result appears while he kneels; when he wins or it is a draw of time he bows instead) and his **bow**
(when the spar begins, and before the result). `spar.js` plays them frame by frame at the videos' pace up to the moment
the exchange is decided, then brings him back to his stance faster than the video does; your own move waits for his,
so both land together. Each has the video's own **sound**, timed to that moment.

- **His tell is also a pose.** On an exchange where he gives a tell he holds that move's first pose while you choose
  (hands at his hips for a Strike, forearms up for a Guard, Qi rising for a Break). It shows no more than his words
  do (each tell names one move), and on the other exchanges he only breathes.
- **Only what happened is shown:** a Guard nothing lands on is raised and lowered, without the sparks; a Break you
  struck first never lets its Qi go.
- **When your blow lands** he plays his own **stagger** (thrown a step back, an arm flung out, then back to his
  stance) with the video's sound, from the moment it lands, whatever he was doing. Without his sheets he is a still
  picture, knocked back in code.
- **On a phone** the two panels sit side by side and slim, the four buttons are one small row, and the branch and
  lantern are left out, so the fighters have the room. There (and in any narrow window) the yard is drawn on the scene itself,
  its paving along the scene's bottom, so their feet are on the ground whatever the screen's shape.
- **In town** the Martial Master you walk up to is the same man (`art/spar/master/town.webp`: him standing at ease, a
  frame of the bow video; `web/town.py`).

**The yard** (`art/spar/`, prepared by `scripts/make_spar_art.py`): an ordinary spar's background is the training
yard seen from the side (`yard.jpg`, pinned to the bottom of the page so its paving is under the fighters' feet), with
a blossom branch and a lantern close to the eye that sway, and petals on the wind (made in code). A trial is still in
the old hall at night. Effects: the gold **seal** for perfect timing, a **ripple** where his palm lands on you, a
**shield** of Qi when his Guard stops your blow, **dust** at the feet on heavy blows, a brush-stroke **banner** behind
the result's title and the **lotus emblem** behind a breakthrough. The yard's page has his painting as its header.

**The yard alive:** SHOAIB's video of the yard plays behind an ordinary spar (`art/spar/yard.mp4`, made seamless by
`scripts/make_background_loop.py`: petals falling, mist, the lanterns; `yard.jpg` is its first frame, so the still and
the video are one picture). On a wide screen it is behind the whole page; on a narrow one inside the scene, where the
still is drawn too. Its own sound (a soft wind and chimes) loops under the fight (`art/spar/yard.wav`, made by
`scripts/make_spar_art.py ambience=...`: looped with no seam and raised until plainly heard; it follows Sound, not
Music). With the video playing, the petals made in code and the foreground lantern are left out (the video has its
own). Not with reduced motion or when the browser saves data: the still shows, with the code-made petals.

**His sounds are loud on purpose:** every Master clip is raised to full level when it is cut, and played above the
music. His bow has its own sound too (cloth, the fist into the palm, his feet), kept in step with the bow at the speed
it is played.

**Music** (`web/static/spar_music.js`): made in the browser like the map's tune, no recording: a slow drum, a low
string and a plucked five-note tune with a flute now and then; a trial is a little faster and lower. It follows the
map's settings (Sound, volume, Music On / Off) and stops when the spar ends.

A spar lives in the web server's memory, like a duel: a restart ends it unsaved (its rest stays, as when the bot
restarts mid-spar). The website doesn't know about a spar under way on Discord, but the shared rest stops a second
one from starting.

## Practice on the website: Senior Sister Xue's drills

**WEBSITE ONLY (SHOAIB, Nov 24).** Discord's `/practice` keeps its four challenges (challenges.md). On the website,
Practice is a different game from Spar: a **real-time reaction drill** of one technique, about half a minute long,
with its own teacher, **Senior Sister Xue, the Drill Instructor** (a placeholder name, easy to change: `NAME` in
`web/practice_play.py`), in a bright wooden training hall. It is chosen in the training yard (`/training`, the
**Practice** button beside each technique whose bar isn't full); the drill is `/practice`.

**The drill is chosen by the technique** (`drill_of`; its movement from `web/technique_fx.py`, its effect from the
bot's technique table):

| Kind | What you do |
|---|---|
| **Striking** (all 15 attack techniques) | Targets light up on the training dummy (the **kicking post** for kicks); hit each in its lane (D F J K, or 1-4) as its ring closes. **Palms** strike targets in pairs; **finger** and **pierce** techniques get small targets and tighter timing; **combo** techniques get quick chains; **heavy** techniques get **charges**: hold the key, release as the ring closes. |
| **Defending** (all 15 defence techniques) | Blows come **high** (a sandbag, W / ↑), **middle** (a staff, D / →) or **low** (a log, S / ↓); meet each in its lane as it lands. **Stances** (brace) press and **hold** through the blow; **deflections** and **steps** time a tap. **Counter** techniques strike back with Space after some deflections; **recover** techniques **breathe** with Space between blows. |

Every drill begins with **Form** (the first quarter, 40% slower), then **Flow**, and ends with a **finishing blow** (a
charge into the dummy's heart, or one heavy blow). **Feints** (dark targets, a blow that pulls back) must be left
alone; a press at nothing costs a fifth of a target, so mashing never pays.

**The stage sets the pace** (tier = mastery stage + 1, `TIERS`): each stage faster and longer, doubles from stage 3,
feints from stage 4; the last stage (Return to Simplicity) is calmer, with fewer, slower beats that each want
near-perfect timing. The dummy changes with the stage: straw, wood, iron, stone, jade.

**Conditions and events** are rolled from the bot's own tables and mean here what they mean there: Heavy Rain makes
every window 25% narrower, Night Training shows a target only at the last moment, Drunken Master adds feints, Old
Injury makes charges and braces count half. The Wandering Hermit (the hardest drill, two conditions, EXP ×5) and
Epiphany (EXP +50%) as on Discord; a **Rival Disciple** steps in after the drill with three quick targets: meet two
and the EXP doubles.

**The score:** a perfect is worth 1, a good 0.6, a feint left alone 1, a press at nothing −0.2; 85% of the score is
that accuracy, 15% the longest unbroken run. **What it pays is the bot's own** (`bot/trainer.finish_practice`): 40
mastery EXP × score, +15% per condition, the event, the daily rates (5 full, 5 half, then 10%), a score under 50%
earns 10%, Insightful gear, the Insight Ink chance, the quest count. **The 30-minute rest starts when the drill is set
up**, as on Discord, so walking away earns nothing and the rest stays. A full bar can't be practised: its trial with
the Martial Master comes first.

**The server referees** (`web/practice_play.Hall`): it makes the pattern, keeps the time the drill began
(`/practice/go`), and when the page sends what was pressed and when (`/practice/submit`), it checks the drill took
its full length and grades every target itself. The page's own clock times the presses, so a slow connection costs
nothing. One thing at a time: a drill and a spar never run together.

**Her movements** (she is painted facing right, so the page mirrors her to face you) are cut from SHOAIB's videos (`art/practice/instructor/`, `scripts/make_master_sheets.py
--instructor`): she raises her hand and cuts the air to begin (the drill starts on the cut, with a 3-2-1), watches with
a hand on her hip while you work, and **claps** for a score of 70% or more or puts both hands on her hips and shakes
her head below it. Each video's own sound is raised to full level when cut and played loud over the music. **Unarmed** (`art/practice/hero/<gender>/`, cut from SHOAIB's Flow videos by `scripts/make_practice_hero.py`): in a
drill your character fights with empty hands, with movements of their own: a breathing **stance** looping between
blows, a **strike** (out to the fist's full reach, then played back in reverse) for every striking drill, a **block**
(arms up and crossed, held while a brace is held) for every defending drill, and **struck** when a blow gets through.
Each movement's own sound is raised to full level and played loud. Hers are in; until his are made, the male character
keeps the sword fighter's movements (`hero_sheets` answers None). Spar keeps the sword fighters. Your character steps in so the hand meets the target, each blow starts from where the last one is (quick blows flow into each other), and the return to the stance fades instead of jumping. A great
score on the wooden dummy breaks it (`broken.webp`).

**The hall:** SHOAIB's painting (`art/practice/hall.jpg`) with dust drifting in the sunbeams (made in code), and the
hall's air from her "watching" video looped under the music (`art/practice/hall.wav`, made by
`scripts/make_practice_art.py ambience=...`; it follows Sound). The **music** is `spar_music.js`'s `practice` mood: a
bright major five-note tune, a soft drum keeping time and the flute more often. The training objects, effects, drill
badges, the result's scroll and her portrait are SHOAIB's Gemini pictures, cut by `scripts/make_practice_art.py`.

**Settings** (on the drill's opening card, kept in the browser): **your own key for each of the four moves**, one
set for striking drills and one for defending (click a move, press a key; a key already used swaps the two; the number
keys, and the arrows when defending, still work unless given to another move), and **guides** on or off: the key
written on every target and a faint mark where each lane's targets appear.

The drill page has no top bar or tabs: the hall fills the whole window, and a **Leave** button in the corner walks away (it asks once: nothing is earned and the rest stays; after the result it goes back to the yard). On a phone the scene is 4:3 and the moves are big pads under it. A drill lives in the web server's memory, like a spar:
a restart ends it unpaid (its rest stays). Code: `web/practice_play.py`, `web/practice_routes.py`,
`web/templates/practice.html`, `web/static/practice.js`, `practice.css`. Tests: `tests/test_web_practice.py`.

## How players get techniques

1. **Start:** Iron Fist (attack) and Horse Stance Guard (defense)
2. **Beasts:** drops when defeating beasts in the wild (stronger beasts, higher grades)
3. **Quests:** rewards from quests
4. **Later:** sects, shops (not yet)
