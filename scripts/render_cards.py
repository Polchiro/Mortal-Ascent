"""
Render every card with its built-in sample data, as a quick smoke check.

    python scripts/render_cards.py

Each card module is run the same way as `python <card>.py`, so its own
`if __name__ == "__main__"` demo is what gets tested. The PNGs are written
next to the modules (git-ignored) and the script exits non-zero if any card
fails to render.
"""
import os
import runpy
import sys
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS = [
    ("profile_card.py", "profile_preview.png"),
    ("balance_card.py", "balance_preview.png"),
    ("inventory_card.py", "inventory_preview.png"),
    ("qi_card.py", "qi_preview.png"),
]
FONTS = ["Cinzel.ttf", "Inter.ttf", "NotoSerifSC-Bold.otf"]


def main():
    sys.path.insert(0, ROOT)
    os.chdir(ROOT)

    missing = [f for f in FONTS if not os.path.exists(os.path.join(ROOT, "fonts", f))]
    if missing:
        print(f"note: missing fonts ({', '.join(missing)}), cards will use fallbacks; see fonts/README.md")

    failed = 0
    for module, png in CARDS:
        out = os.path.join(ROOT, png)
        if os.path.exists(out):
            os.remove(out)
        try:
            runpy.run_path(os.path.join(ROOT, module), run_name="__main__")
        except Exception:
            failed += 1
            print(f"FAIL {module}")
            traceback.print_exc()
            continue
        if not os.path.exists(out):
            failed += 1
            print(f"FAIL {module}: ran but did not write {png}")
            continue
        from PIL import Image
        with Image.open(out) as im:
            print(f"ok   {module} -> {png} ({im.width}x{im.height})")

    print(f"\n{len(CARDS) - failed}/{len(CARDS)} cards rendered")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
