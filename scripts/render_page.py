#!/usr/bin/env python3
"""Render the pages of a movement with its encoded breaks to PNG.

Verovio lays out each printed page as encoded (pb/sb), so render page N
matches the movement's Nth printed page system by system. With --scan, the
facsimile page that the page's pb points to is set to the left of the render,
both at the same height, for proofreading side by side (the scan images are
local; see the README).

Needs verovio and Pillow (both in CAMAT's environment) and rsvg-convert.
Verovio's warnings, if any, go to stderr. rsvg-convert draws the note of a
metronome mark (a SMuFL symbol in the tempo text) as a missing-glyph box.

Usage: python scripts/render_page.py mei/webern-op27-II.mei -o <dir> [--page 1] [--scan]
"""
from __future__ import annotations

import argparse
import io
import subprocess
import sys
from pathlib import Path

import verovio
from lxml import etree
from PIL import Image

M = "{http://www.music-encoding.org/ns/mei}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
OPTIONS = {"breaks": "encoded", "scale": 45, "adjustPageHeight": True,
           "pageWidth": 2100, "pageHeight": 2970, "footer": "none", "header": "none"}
HEIGHT = 1800


def scan_pages(path: Path) -> list[Path]:
    """Facsimile image of each pb in document order, resolved against the MEI file."""
    root = etree.parse(str(path)).getroot()
    images = {}
    for surface in root.iter(M + "surface"):
        target = surface.find(M + "graphic").get("target")
        images["#" + surface.get(XML_ID)] = (path.parent / target).resolve()
    return [images[pb.get("facs")] for pb in root.find(f".//{M}music").iter(M + "pb")]


def to_png(svg: str, height: int) -> Image.Image:
    data = subprocess.run(["rsvg-convert", "-h", str(height), "--keep-aspect-ratio", "-b", "white"],
                          input=svg.encode(), capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(data)).convert("RGB")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mei", type=Path)
    parser.add_argument("-o", "--out", type=Path, required=True, help="output directory")
    parser.add_argument("--page", type=int, action="append", help="page of the movement, from 1 (default: all)")
    parser.add_argument("--scan", action="store_true", help="put the facsimile page to the left")
    args = parser.parse_args(argv)

    tk = verovio.toolkit()
    tk.setOptions(OPTIONS)
    tk.loadData(args.mei.read_text(encoding="utf-8"))
    count = tk.getPageCount()
    scans = scan_pages(args.mei)
    if len(scans) != count:
        print(f"warning: {count} rendered pages but {len(scans)} pb elements", file=sys.stderr)
    args.out.mkdir(parents=True, exist_ok=True)
    for page in args.page or range(1, count + 1):
        if not 1 <= page <= count:
            raise SystemExit(f"page {page} out of range 1-{count}")
        render = to_png(tk.renderToSVG(page), HEIGHT)
        if args.scan:
            scan = Image.open(scans[page - 1]).convert("RGB")
            scan = scan.resize((round(scan.width * HEIGHT / scan.height), HEIGHT))
            pair = Image.new("RGB", (scan.width + 20 + render.width, HEIGHT), "white")
            pair.paste(scan, (0, 0))
            pair.paste(render, (scan.width + 20, 0))
            render = pair
        out = args.out / f"{args.mei.stem}-p{page}.png"
        render.save(out)
        print(out)


if __name__ == "__main__":
    main()
