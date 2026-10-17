#!/usr/bin/env python3
"""Assemble the static viewer for GitHub Pages.

Copies site/ (the viewer), the three MEI files and
facsimiles/ue1937/pages.json into OUT, in the layout the viewer fetches
them from. Nothing else is copied: the scan's PDF and page images must never
be published. OUT is emptied first.

Standard library only.

Usage: python scripts/build_site.py [OUT]    (default: _site)
Preview: python -m http.server -d _site, then open http://localhost:8000/
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = [
    ("site/index.html", "index.html"),
    ("site/viewer.css", "viewer.css"),
    ("site/viewer.js", "viewer.js"),
    ("facsimiles/ue1937/pages.json", "facsimiles/ue1937/pages.json"),
] + [(f"mei/webern-op27-{mvt}.mei", f"mei/webern-op27-{mvt}.mei") for mvt in ("I", "II", "III")]


def main() -> int:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "_site").resolve()
    if out == ROOT or ROOT.is_relative_to(out):
        print(f"refusing to empty {out}", file=sys.stderr)
        return 1
    if out.exists():
        shutil.rmtree(out)
    for source, target in FILES:
        destination = out / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / source, destination)
        print(f"{source} -> {destination.relative_to(out)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
