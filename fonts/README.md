# fonts/

The card renderers (the Character Sheet cards in `cards/`, plus `qi_card.py` and the older ink-wash cards) load fonts from this folder.
The font files are not committed; download them from Google Fonts and drop them here with these exact names:

| File | Source | Used for |
| --- | --- | --- |
| `Cinzel.ttf` | [Cinzel](https://fonts.google.com/specimen/Cinzel) (variable font) | Titles and labels |
| `Inter.ttf` | [Inter](https://fonts.google.com/specimen/Inter) (variable font) | Body text and numbers |
| `NotoSerifSC-Bold.otf` | [Noto Serif SC](https://fonts.google.com/noto/specimen/Noto+Serif+SC) | Chinese characters (seals, realm names) |

Cinzel and Inter must be the **variable** versions, because the renderers pick weights by name
(`"Bold"`, `"Black"`, `"SemiBold"`, `"Medium"`).

If a file is missing, the renderers silently fall back to DejaVu Sans (and to a system Noto CJK font for
Chinese, if one is installed), so cards still render but look wrong. `python scripts/render_cards.py`
reports which fonts it found.
