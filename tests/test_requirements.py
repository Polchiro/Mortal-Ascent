"""Every third-party module the bot imports must be in requirements.txt, so `pip install -r requirements.txt`
is enough on a fresh PC (numpy was missing and broke /index on Windows)."""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE_OF = {"PIL": "pillow", "discord": "discord.py", "numpy": "numpy"}
DEV_ONLY = {"pytest"}


def local_modules():
    names = set()
    for entry in os.listdir(ROOT):
        if entry.endswith(".py"):
            names.add(entry[:-3])
        elif os.path.isdir(os.path.join(ROOT, entry)):
            names.add(entry)
    return names


def imported_modules():
    found = set()
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("tests", "__pycache__", "scripts")]
        for f in files:
            if f.endswith(".py"):
                with open(os.path.join(folder, f), encoding="utf-8") as fh:
                    tree = ast.parse(fh.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        found.update(a.name.split(".")[0] for a in node.names)
                    elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                        found.add(node.module.split(".")[0])
    return found


def test_every_third_party_import_is_in_requirements():
    with open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8") as fh:
        reqs = {re.split(r"[<>=!~\[ ;]", line.strip())[0].lower() for line in fh
                if line.strip() and not line.startswith("#")}
    third_party = imported_modules() - set(sys.stdlib_module_names) - local_modules() - DEV_ONLY
    missing = sorted(m for m in third_party if PACKAGE_OF.get(m, m).lower() not in reqs)
    assert not missing, f"Add these to requirements.txt: {missing}"
