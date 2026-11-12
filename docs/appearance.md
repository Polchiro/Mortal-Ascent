# Appearance

A player picks how their cultivator looks: **gender**, **hairstyle** and **hair colour**. It is a picture only:
no stat, fight, reward or ranking depends on it.

## Choices

| Gender | Hairstyles |
|---|---|
| Male | Topknot, Long & Loose |
| Female | High Ponytail, Twin Buns, Long Straight, Single Braid, Crown Bun |

Hair colours: Silver White, Ink Black, Dark Brown, Chestnut, Crimson, Azure Night.

Everyone wears the same robe. Facial hair and clothing choices may come later.

## Cost

- New and existing players start with no look chosen (default portrait).
- The **first** look is free (`looks.FREE_CHANGES`).
- Every change after that costs **200 Moon Pearls** (`looks.CHANGE_PEARLS`), written in the ledger as
  "Appearance change". Picking the look you already have is refused and costs nothing.

## Where it shows

The look shows on the website only: the profile portrait, the Appearance page preview, and the round face on
the fight card (Explore). Discord cards keep showing the player's Discord avatar.

## How the pictures are made

Each hairstyle is one painted picture of the cultivator in the robe with silver-grey hair,
`art/looks/<gender>_<hair>.webp` (260 × 540, see-through background), plus a hair mask
`art/looks/<gender>_<hair>_hair.png` (white = hair). A colour is painted inside the mask keeping the hair's own
light and shade (`looks.tint`), so one picture serves every colour. Finished pictures are cached in `art/.looks/`
(not in git) and drawn again only if that folder is cleared.

Adding a hairstyle: add the picture and its mask to `art/looks/`, then one line in `looks.HAIRSTYLES`.

## Saved data

Two player columns, added automatically at start-up (existing players keep everything else):

- `appearance`: JSON `{"gender", "hair", "color"}`, or empty if not chosen.
- `appearance_changes`: how many times the look was set (the first is free).
