#!/usr/bin/env python3
"""One-time migration of the Verovio MEI 6.0-dev files to MEI 5.1 (CMN).

Verovio 6.3 has no MEI 5 writer, and its MEI Basic output drops the facsimile,
the header and many IDs, so the files are downgraded by targeted text edits.
Every edit asserts its match count; a file already at 5.1 is left unchanged.

  - all files: @meiversion "6.0-dev" -> "5.1"
  - II: the Humdrum repeat/no-repeat <choice> becomes one <expansion> with the
    printed repeat order (I A A B B); <expansion> may not sit in <orig>/<reg>
  - II: <mRest visible="false"/> becomes <mSpace/> (5.1 mRest has no @visible)

Usage: python scripts/migrate_mei51.py [mei/webern-op27-*.mei ...]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

CHOICE = re.compile(
    r'(?P<indent>[ ]*)<choice xml:id="[^"]+">\s*'
    r'<orig xml:id="[^"]+">\s*'
    r'(?P<expansion><expansion plist="[^"]+" xml:id="[^"]+" />)\s*'
    r'</orig>\s*'
    r'<reg xml:id="[^"]+" type="norep">\s*'
    r'<expansion plist="[^"]+" xml:id="[^"]+" type="norep" />\s*'
    r'</reg>\s*'
    r'</choice>'
)
HIDDEN_MREST = re.compile(r'<mRest (xml:id="[^"]+") visible="false" />')


def sub_exactly(pattern: re.Pattern[str], repl, text: str, count: int, what: str) -> str:
    new, n = pattern.subn(repl, text)
    if n != count:
        raise SystemExit(f"{what}: expected {count} match(es), found {n}")
    return new


def migrate(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if 'meiversion="5.1"' in text:
        return False
    text = sub_exactly(re.compile(r'meiversion="6\.0-dev"'), 'meiversion="5.1"', text, 1, f"{path.name} @meiversion")
    if path.name == "webern-op27-II.mei":
        text = sub_exactly(CHOICE, r"\g<indent>\g<expansion>", text, 1, f"{path.name} expansion choice")
        text = sub_exactly(HIDDEN_MREST, r"<mSpace \1 />", text, 3, f"{path.name} hidden mRest")
    path.write_text(text, encoding="utf-8")
    return True


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] or sorted((REPO / "mei").glob("webern-op27-*.mei"))
    for path in paths:
        print(f"{path.name}: {'migrated' if migrate(path) else 'already 5.1'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
