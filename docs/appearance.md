# Appearance

A player picks how their cultivator looks: **Male** or **Female**. It is a picture only:
no stat, fight, reward or ranking depends on it.

Each gender has one painting of the cultivator standing calm in pale blue and silver robes, the male and the female
painted as a matching pair (Nov 23; before that, a palm strike wrapped in blue Qi streams). Hairstyles and hair colours were tried and removed; a look saved with them keeps only its gender.

## Cost

- New and existing players start with no look chosen (they show the male painting).
- The **first** look is free (`looks.FREE_CHANGES`).
- Every change after that costs **200 Moon Pearls** (`looks.CHANGE_PEARLS`), written in the ledger as
  "Appearance change". Picking the look you already have is refused and costs nothing.

## Where it shows

The look shows on the website only: the profile portrait, the Appearance page preview, the fighter in explore
fights and the round face on the fight card. Discord cards keep showing the player's Discord avatar.

## The pictures

| File | Used for |
|---|---|
| `art/portraits/hero_<gender>.webp` (about 440 × 892, see-through, feet at the bottom) | profile and Appearance page |
| `art/portraits/fight/hero_<gender>_{idle,windup,strike}.webp` (1024 × 559, facing right) | the fighter in explore fights, in three sword poses |
| `art/portraits/hero_<gender>_face.webp` (256 × 256) | the round face on the fight card, Appearance thumbnails |

The painting and the face are cut from SHOAIB's painting of each cultivator (Gemini, 16:9, plain grey backdrop) by
`python -m scripts.make_hero_portrait <gender> painting.png`: background and Gemini's sparkle removed, trimmed to
the figure, the face taken from the head and shoulders. The fight pictures are older and replaced separately.

## Saved data

Two player columns, added automatically at start-up (existing players keep everything else):

- `appearance`: JSON `{"gender"}`, or empty if not chosen (older saves may also carry "hair"; it is ignored).
- `appearance_changes`: how many times the look was set (the first is free).
