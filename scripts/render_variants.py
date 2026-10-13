#!/usr/bin/env python3
"""Render a few bars under alternative encodings, side by side, to compare them.

Each variant is a label and a list of [old, new] text replacements applied to
the file in memory (each old text must occur exactly once); an empty list
renders the file as it is. The MEI file is not changed. Useful for choosing
between encodings Verovio draws differently, such as @place or @stem.dir.

Needs verovio and Pillow (both in CAMAT's environment) and rsvg-convert.

Usage: python scripts/render_variants.py mei/webern-op27-II.mei 1 2 out.png \\
         '[["now", []], ["below 1", [["L27F3\\" place=\\"between\\" staff=\\"1 2\\"",
                                     "L27F3\\" place=\\"below\\" staff=\\"1\\""]]]]'
"""
from __future__ import annotations

import argparse
import io
import json
import subprocess
from pathlib import Path

import verovio
from lxml import etree
from PIL import Image, ImageDraw, ImageFont

OPTIONS = {"breaks": "none", "scale": 60, "adjustPageHeight": True,
           "pageWidth": 2400, "footer": "none", "header": "none"}
WIDTH, LABEL = 900, 40
MEASURE = "{http://www.music-encoding.org/ns/mei}measure"


def render(text: str, first: int, last: int) -> Image.Image:
    tk = verovio.toolkit()
    tk.setOptions(OPTIONS)
    tk.loadData(text)
    tk.select({"measureRange": f"{first}-{last}"})
    tk.redoLayout()
    data = subprocess.run(["rsvg-convert", "-w", str(WIDTH), "-b", "white"],
                          input=tk.renderToSVG(1).encode(), capture_output=True, check=True).stdout
    return Image.open(io.BytesIO(data)).convert("RGB")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mei", type=Path)
    parser.add_argument("first", help="first bar (@n)")
    parser.add_argument("last", help="last bar (@n)")
    parser.add_argument("out", type=Path, help="PNG to write")
    parser.add_argument("variants", help='JSON: [["label", [["old", "new"], ...]], ...]')
    args = parser.parse_args(argv)

    base = args.mei.read_text(encoding="utf-8")
    # Verovio's measureRange counts bars from 1 in document order; II starts with bar 0.
    numbers = [m.get("n") for m in etree.fromstring(base.encode()).iter(MEASURE)]
    first, last = numbers.index(args.first) + 1, numbers.index(args.last) + 1
    font = ImageFont.load_default(size=28)
    images = []
    for label, replacements in json.loads(args.variants):
        text = base
        for old, new in replacements:
            if text.count(old) != 1:
                raise SystemExit(f"{label}: {old!r} occurs {text.count(old)} times, not once")
            text = text.replace(old, new)
        image = render(text, first, last)
        framed = Image.new("RGB", (image.width, image.height + LABEL), "white")
        framed.paste(image, (0, LABEL))
        ImageDraw.Draw(framed).text((image.width // 2, 5), label, fill="black", font=font, anchor="ma")
        images.append(framed)
    sheet = Image.new("RGB", (sum(i.width for i in images), max(i.height for i in images)), "white")
    x = 0
    for image in images:
        sheet.paste(image, (x, 0))
        x += image.width
    sheet.save(args.out)
    print(args.out)


if __name__ == "__main__":
    main()
