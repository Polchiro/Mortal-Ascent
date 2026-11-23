"""
Character appearance: male or female. docs/appearance.md.

The look is only a picture. It never touches stats, fights or anything else in the game.

Each gender has one painting of the cultivator in white and blue robes (art/portraits/hero_<gender>.webp,
see-through background) and a round face (art/portraits/hero_<gender>_face.webp). In website fights each has
three sword poses (art/portraits/fight/hero_<gender>_{idle,windup,strike}.webp). A player who hasn't chosen a look shows the male painting.
"""
import json

GENDERS = {"male": "Male", "female": "Female"}
DEFAULT_GENDER = "male"             # the painting shown until a player chooses
FREE_CHANGES = 1                    # choosing your first look costs nothing
CHANGE_PEARLS = 200                 # every change after that, in Moon Pearls


def parse(raw):
    """A stored appearance (JSON text) as a clean dict, or None if the player hasn't chosen one.
    Looks saved while hairstyles and hair colours existed carry "hair" and "color"; only the gender counts now."""
    if not raw:
        return None
    try:
        return clean(json.loads(raw).get("gender"))
    except (ValueError, AttributeError):
        return None


def clean(gender):
    """{'gender'} if it is a real option, else None."""
    return {"gender": gender} if gender in GENDERS else None


def dump(look):
    return json.dumps({"gender": look["gender"]}, sort_keys=True)


def describe(look):
    """'Female'."""
    return GENDERS[look["gender"]]


def change_cost(player):
    """Moon Pearls the next change costs (0 while the free one is left)."""
    return 0 if (player.get("appearance_changes") or 0) < FREE_CHANGES else CHANGE_PEARLS


def of_player(player):
    """The player's chosen look, or None (they still show the default painting)."""
    return parse(player.get("appearance")) if player else None


def gender_of(look):
    return look["gender"] if look else DEFAULT_GENDER


def portrait(look):
    """The full painting (profile, Appearance page), as a website path."""
    return f"/art/portraits/hero_{gender_of(look)}.webp"


POSES = ("idle", "windup", "strike")
SWORD_POSES = {"male": 0.66, "female": 0.82}   # genders painted in the sword poses: how far the blade reaches (0-1)
# genders whose sword attack plays frame by frame (scripts/make_hero_attack.py cuts it from SHOAIB's video):
# a grid of 320 x 360 frames that web/static/fight.js steps through; the stills above come from the same video.
ATTACK_SHEETS = {"male": {"src": "/art/portraits/fight/hero_male_attack.webp", "frames": 41, "cols": 8, "rows": 6},
                 # hers are a sheet per move, from SHOAIB's two videos of her (scripts/make_heroine_attacks.py), each
                 # starting and ending in her stance. `box`: the cell's place on the 1024 x 559 canvas (shares; it holds
                 # the overhead sword and the leap); `tip`: how far her blade reaches at the hit (the dash stops it at the
                 # beast); `blade`: its timing, as fight.js BLADE ([ms, frame] keys, the hit, the dash in and back).
                 # (Nov 23: both slowed, Strike by a quarter and Break by an eighth, to sit better beside the beast's attack.)
                 # Strike: she raises the sword (0-9), cuts in one diagonal arc (10-18, the hit 13: the fight draws the
                 # trail), holds (19-24) and steps back into her stance (25-41).
                 # Break: blue Qi swirls round her (0-13), she leaps with it overhead (14-26) and drives it down (27, the
                 # hit: the fight's own slam bursts there), holds the landing (28) while the dust rises, rises (29-39)
                 # and steps back into her stance (40-50). The video's leap across the frame is the fight's dash.
                 "female": {
                     "strike": {"src": "/art/portraits/fight/hero_female_strike_sheet.webp", "frames": 42, "cols": 8, "rows": 6,
                                "box": [0.3506, 0.093, 0.5693, 0.8623], "tip": 0.9141,
                                "blade": {"keys": [[0, 0], [480, 9], [590, 13], [780, 18], [1080, 24], [1880, 41]],
                                          "dash": [190, 590], "swing": 500, "hit": 590, "back": [1080, 1810], "end": 1950,
                                          "knock": 0.024, "bob": 0}},
                     "break": {"src": "/art/portraits/fight/hero_female_break_sheet.webp", "frames": 51, "cols": 8, "rows": 7,
                               "box": [0.1357, 0.1038, 0.5811, 0.9284], "tip": 0.73,   # past the blade: her crouch reaches as far
                               "blade": {"keys": [[0, 0], [580, 13], [1050, 26], [1120, 27], [1130, 28], [1680, 28], [2130, 39], [2460, 50]],
                                         "dash": [580, 1120], "swing": 1010, "hit": 1120, "back": [1680, 2460], "end": 2530,
                                         "knock": 0.05, "slam": True, "bob": 0}}}}

# the same for Guard: he blocks with the blade, a gold flash and sparks where the blow lands (SHOAIB's second video).
# She blocks with her sword, from SHOAIB's Nov 23 video of her (scripts/make_heroine_set.py), starting and ending in
# her stance: she raises the blade across her body as the beast comes in (0-10), the blow lands on it in a burst of
# sparks (`first`), her sleeves and skirt whip round, she steadies behind the blade and lowers it. Her step forward in
# the video is taken out (the beast comes to her). `box`: the sheet's own cell on the 1024 x 559 canvas (shares), as
# her attack sheets'. Each sheet's timing (fight.js `block`): `ready` ms to raise the guard before the blow, `first`
# the frame it lands on, `ms` per frame after; `shift` as in MOTION_SHEETS. His are the page's defaults (fight.js GUARD).
GUARD_SHEETS = {"male": {"src": "/art/portraits/fight/hero_male_guard.webp", "frames": 37, "cols": 8, "rows": 5},
                "female": {"src": "/art/portraits/fight/hero_female_guard.webp", "frames": 42, "cols": 8, "rows": 6,
                           "ready": 620, "first": 13, "ms": 66, "box": [0.3037, 0.1109, 0.3906, 0.8569]}}

# her fighting stance: the loop she plays while she stands between moves, in beast fights and duels, in place of
# the still idle picture (style.css `.stanced`, stepped through in CSS: `cols` x `rows` frames fill the grid, `loop`
# seconds round). From SHOAIB's video of her (scripts/make_heroine_stance.py): on guard, sword held low in her right
# hand, left hand at her chest, breathing, sleeves and hair stirring, her feet where the still's are (`shift` as in
# GUARD_SHEETS, none needed). He has none yet:
# he keeps his still picture and its breathing.
IDLE_SHEETS = {"female": {"src": "/art/portraits/fight/hero_female_stance.webp", "frames": 72, "cols": 8, "rows": 9,
                          "loop": 5.38, "shift": 0}}

# the shared movements techniques play (web/technique_fx.py "motion"), frame by frame, in the same 320 x 360 cells.
# "fist": SHOAIB's punch video (scripts/make_hero_fist.py): on guard (0-1), a jab (out at `jab`), the fist drawn
# back (7-8), a lunging punch (out at `release`), held, drawn back (21-27), on guard again (28-35). `shift`: he was
# moved left inside his cells so the lunge isn't cut off, by this share of a cell; the page moves him back.
# "palm": SHOAIB's palm video (scripts/make_hero_palm.py): on guard (0-4), both arms drawn back (5-9), a lunging
# two-handed palm push (out at `release`), held, then rising back to guard (`back` on).
# `hand`: where the fist or palms are at the release, as shares of the fighter's box (effects fly from there).
# `ms`: the least time the whole movement takes on screen (fight.js `technique`): a low-grade cast (1.1 s) would
# rush several seconds of her video, so her movements play at a pace nearer the beast's own attack (about 2 s).
# Her kick, fist, palm and finger are from SHOAIB's Nov 23 videos (scripts/make_heroine_set.py): each starts and ends
# in her fighting stance, sword held low, the move made with her free hand; `box` is the sheet's own cell on the
# 1024 x 559 canvas (shares), in place of the shared 320 x 360 cell and its `shift`.
# The female cultivator's movements are all her own, from SHOAIB's videos of her (scripts/make_heroine_*.py).
MOTION_SHEETS = {"fist": {"male": {"src": "/art/portraits/fight/hero_male_fist.webp", "frames": 36, "cols": 8, "rows": 5,
                                   "jab": 5, "release": 12, "back": 21, "shift": 18 / 320, "hand": [0.685, 0.287]},
                          # hers (scripts/make_heroine_set.py): in her stance (0-1), a jab with her left fist (out
                          # at `jab`), drawn back (`windup`), a lunging punch held from `release`, back from `back`
                          "female": {"src": "/art/portraits/fight/hero_female_fist.webp", "frames": 45, "cols": 8, "rows": 6, "jab": 6, "windup": 15, "release": 19, "back": 31, "ms": 2200, "shift": 0, "hand": [0.68, 0.396], "box": [0.3018, 0.1789, 0.3877, 0.771]}},
                 "palm": {"male": {"src": "/art/portraits/fight/hero_male_palm.webp", "frames": 48, "cols": 8, "rows": 6,
                                   "jab": 12, "release": 14, "back": 40, "shift": 7 / 320, "hand": [0.66, 0.231]},
                          # hers is her own, from SHOAIB's video of her (scripts/make_heroine_set.py): in her stance,
                          # her left arm drawn back (`windup`), a lunging open-palm strike (out at
                          # `release`), held, then rising back to standing (`back` on)
                          "female": {"src": "/art/portraits/fight/hero_female_palm.webp", "frames": 40, "cols": 8, "rows": 5, "jab": 11, "windup": 11, "release": 15, "back": 24, "ms": 2000, "shift": 0, "hand": [0.807, 0.398], "box": [0.3662, 0.1771, 0.4561, 0.771]}},
                 # "kick": hers from SHOAIB's video of her (scripts/make_heroine_set.py), what the four kick techniques
                 # play: she gathers (0-6), lifts her front leg (`windup`), snaps a high side kick out (`release`,
                 # where `hand` is her foot), holds it, draws the leg back (`back` on) and settles in her stance.
                 # He has no kick yet: he keeps the hop over his three poses (fight.js `technique`).
                 "kick": {"female": {"src": "/art/portraits/fight/hero_female_kick.webp", "frames": 37, "cols": 8, "rows": 5, "jab": 9, "windup": 9, "release": 13, "back": 22, "ms": 2100, "shift": 0, "hand": [0.772, 0.395], "box": [0.3672, 0.1753, 0.4248, 0.7728]}},
                 # "finger": SHOAIB's finger-jab video (scripts/make_hero_finger.py): on guard (0-4), a first reach
                 # (`jab`), the lunge with two fingers thrust out (`release`, where the beam leaves the fingertip),
                 # held, drawing back (`back` on). `hand` is the fingertip.
                 "finger": {"male": {"src": "/art/portraits/fight/hero_male_finger.webp", "frames": 48, "cols": 8, "rows": 6,
                                     "jab": 6, "windup": 5, "release": 10, "back": 44, "shift": 21 / 320, "hand": [0.689, 0.315]},
                            # hers is her own, from SHOAIB's video of her (scripts/make_heroine_set.py): in her stance,
                            # two fingers pointed (`jab`), the arm swung (`windup`), a deep lunge thrusting them forward
                            # (`release`, where the beam leaves), held, rising with the arm drawn in (`back` on), on guard
                            "female": {"src": "/art/portraits/fight/hero_female_finger.webp", "frames": 36, "cols": 8, "rows": 5, "jab": 8, "windup": 8, "release": 10, "back": 23, "ms": 2000, "shift": 0, "hand": [0.711, 0.41], "box": [0.2686, 0.1753, 0.4521, 0.7585]}},
                 # "brace": SHOAIB's brace video (scripts/make_hero_brace.py): standing (0-4), reaching out, the arms
                 # crossed up into guard, settled in a wide stance at `release` and held to the end, where the
                 # beast's blow is taken. `hand` is the crossed forearms; `body` the braced figure (middle, top of the
                 # head, feet, width), as shares of the fighter's box: the effects are placed and sized around it.
                 "brace": {"male": {"src": "/art/portraits/fight/hero_male_brace.webp", "frames": 33, "cols": 8, "rows": 5,
                                    "jab": 5, "release": 16, "back": 32, "shift": 0, "hand": [0.49, 0.29],
                                    "body": [0.462, 0.094, 0.902, 0.239]},
                           # hers is her own, from SHOAIB's video of her (scripts/make_heroine_brace.py): standing,
                           # hands rising into guard, settled in a wide stance at `release`, both palms up
                           "female": {"src": "/art/portraits/fight/hero_female_brace.webp", "frames": 39, "cols": 8, "rows": 5,
                                      "jab": 5, "release": 16, "back": 38, "shift": 7 / 320, "hand": [0.6, 0.39],
                                      "body": [0.523, 0.209, 0.937, 0.232]}},
                 # "deflect": hers from SHOAIB's video of her (scripts/make_heroine_deflect.py), the movement every
                 # deflection technique shares (web/technique_fx.py MOVES_FX; fight.js `deflected`): on guard, palm raised
                 # (0-5); from `jab` she turns into the blow and reaches out to meet it at `release` (where `hand` is); she
                 # carries it round and aside with a swirl of her sleeve, furthest behind her at `sweep` (where `tip` is);
                 # from `back` she settles on guard again. No guarding stance: she never stands to take the blow.
                 # His is his own, from SHOAIB's video of him (scripts/make_hero_deflect.py): on guard, he reaches back
                 # (`jab`), sweeps a blue Qi arc round in front of him to turn the blow (`release`, `hand`), carries it
                 # down and across (`sweep`, `tip`) and settles on guard again (`back` on). The arc is painted in.
                 "deflect": {"male": {"src": "/art/portraits/fight/hero_male_deflect.webp", "frames": 32, "cols": 8, "rows": 4,
                                      "jab": 6, "release": 13, "sweep": 17, "back": 20, "shift": 2 / 320,
                                      "hand": [0.663, 0.479], "tip": [0.338, 0.690],
                                      "body": [0.454, 0.059, 0.918, 0.264]},
                             "female": {"src": "/art/portraits/fight/hero_female_deflect.webp", "frames": 36, "cols": 8, "rows": 5,
                                        "jab": 6, "release": 12, "sweep": 23, "back": 26, "shift": 4 / 320,
                                        "hand": [0.663, 0.330], "tip": [0.329, 0.708],
                                        "body": [0.520, 0.196, 0.937, 0.233]}},
                 # "sidestep": hers from SHOAIB's video of her (scripts/make_heroine_sidestep.py), what Drifting
                 # Mist Steps and Cloud-Walking Shadow play when they slip the beast's Break (fight.js `sidestepped`):
                 # on guard, palm raised (0-2); from `jab` she sweeps her sleeve and drops into a deep side lunge, out
                 # of the blow's line at `release`; from `back` she rises into the same guard (by 22) and holds it.
                 # Played frame for frame at the video's own pace (`fps`), never sped up or stretched. `give`: the ground
                 # she gives and takes back, as a share of the scene's width.
                 # His, from SHOAIB's video of him (scripts/make_hero_sidestep.py): from standing he launches (`jab`)
                 # into a low dash in swirls of blue Qi (`release`), then rises out of it (`back` on: his launch played
                 # back, as the video holds the dash to its end). He dashes in place: no ground given.
                 "sidestep": {"male": {"src": "/art/portraits/fight/hero_male_sidestep.webp", "frames": 24, "cols": 8, "rows": 3,
                                       "jab": 5, "release": 8, "back": 17, "fps": 12, "shift": 0, "give": 0,
                                       "hand": [0.637, 0.360], "body": [0.453, 0.059, 0.915, 0.248]},
                              "female": {"src": "/art/portraits/fight/hero_female_sidestep.webp", "frames": 27, "cols": 8, "rows": 4,
                                         "jab": 3, "release": 10, "back": 14, "fps": 12, "shift": 47 / 320, "give": 0.06,
                                         "hand": [0.719, 0.414], "body": [0.521, 0.196, 0.936, 0.243]}}}


# walking about the hunting-ground map (web/static/huntmap.js, docs/hunting.md "The map"): the spec sheet, 8 rows
# S SW W NW N NE E SE x 8 frames of 256 x 256, feet at (128, 232). His is cut from SHOAIB's walk video
# (scripts/make_hero_walk.py; SW, W, NW are mirrored: he never faced left in it). `stand`: each row's frame with the
# feet closest together, held while he stands still (no idle sheet yet). A look without a sheet keeps the menus.
# `run` (hers, from SHOAIB's five running videos, scripts/make_heroine_walk.py --run): the same rows and cells, played
# at full speed in place of the walk (huntmap.js, town.js), `stride` screen px to one full stride (a longer step than
# the walk's 96), `stand` the frame each row starts from. The speed she moves at is the same: only the picture changes.
WALK_SHEETS = {"male": {"src": "/art/portraits/map/hero_male_walk.webp", "cell": 256, "feet": [128, 232],
                        "rows": 8, "cols": 8, "stand": [5, 2, 2, 3, 1, 3, 2, 2], "steps": "male"},
               "female": {"src": "/art/portraits/map/hero_female_walk.webp", "cell": 256, "feet": [128, 232],
                          "rows": 8, "cols": 8, "stand": [6, 3, 6, 2, 7, 2, 6, 3], "steps": "female",
                          "idle": {"src": "/art/portraits/map/hero_female_idle.webp", "cols": 8, "loop": 3.33},
                          "run": {"src": "/art/portraits/map/hero_female_run.webp", "stride": 140,
                                  "stand": [7, 5, 3, 4, 1, 4, 3, 5]}}}


def walk_sheet(look):
    """This look's walking sheet for the map, or None."""
    return WALK_SHEETS.get(gender_of(look))


def fighter(look, pose="idle"):
    """The fighter on the 1024 x 559 fight canvas, facing right, in one of POSES (web/static/fight.js swaps them)."""
    gender = gender_of(look)
    if gender in SWORD_POSES:
        return f"/art/portraits/fight/hero_{gender}_{pose}.webp"
    return f"/art/portraits/fight/hero_{gender}.webp"


def sword_tip(look):
    """How far across the fight canvas the weapon reaches in the strike pose (0-1), or None for a single painting."""
    return SWORD_POSES.get(gender_of(look))


def attack_sheet(look):
    """The frame-by-frame sword attack for this look (ATTACK_SHEETS), or None to swing through the three poses."""
    return ATTACK_SHEETS.get(gender_of(look))


def attack_sheets(look):
    """This look's frame-by-frame Strike and Break, by move ({"strike": sheet, "break": sheet}), or None. One sheet
    (his) serves both moves with the page's own timing (fight.js BLADE); hers are a sheet each with its own."""
    s = attack_sheet(look)
    if not s:
        return None
    return {"strike": s, "break": s} if "src" in s else dict(s)


def guard_sheet(look):
    """The frame-by-frame sword block for this look (GUARD_SHEETS), or None to stand in the idle pose behind the ring."""
    return GUARD_SHEETS.get(gender_of(look))


def idle_sheet(look):
    """The fighting stance this look plays while standing (IDLE_SHEETS), or None to show the still idle picture."""
    return IDLE_SHEETS.get(gender_of(look))


def motion_sheet(look, motion):
    """The frame-by-frame movement a technique plays (MOTION_SHEETS), or None to play it through the three poses."""
    return MOTION_SHEETS.get(motion, {}).get(gender_of(look))


def face(look):
    """The square head-and-shoulders picture (shown in a circle on the fight card)."""
    return f"/art/portraits/hero_{gender_of(look)}_face.webp"
