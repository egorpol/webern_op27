#!/usr/bin/env python3
"""Count the printed dashes of each text extender and compare them with @lsegs.

The profile records the printed dash count of a "rit." (or any dir with
@extender="true") in @lsegs, counted across a system break. For each such
dir placed above the staff, this script cuts the text band above the bars it
spans from the facsimile (one piece per system, joined into a strip), finds
dash-shaped blobs and counts those on the strip's text line.

The count is a help, not the answer: check each strip by eye (--out saves
them). The blob sizes suit the 300 dpi scans in facsimiles/ue1937/. Dirs
below or between the staves are listed but not counted.

Needs Pillow, numpy and scipy (all in CAMAT's environment) and the local scan
images (see the README).

Usage: python scripts/count_dashes.py mei/webern-op27-I.mei [--out <dir>]
"""
from __future__ import annotations

import argparse
import statistics
from pathlib import Path

import numpy as np
from lxml import etree
from PIL import Image
from scipy import ndimage

M = "{http://www.music-encoding.org/ns/mei}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
ABOVE, BELOW = 30, 120   # band from 30 px above to 120 px below the bar zone's top
SAME_SYSTEM = 150        # bar zones whose tops differ by less are on one system
GAP = 40                 # white space between the pieces of a strip


def measure_n(element) -> int:
    return int(next(a for a in element.iterancestors(M + "measure")).get("n"))


def dashes(strip: Image.Image) -> list[int]:
    """x positions of dash-shaped blobs on the strip's text line."""
    dark = np.asarray(strip.convert("L")) < 128
    labels, _ = ndimage.label(dark)
    blobs = []
    for i, box in enumerate(ndimage.find_objects(labels), start=1):
        h, w = box[0].stop - box[0].start, box[1].stop - box[1].start
        area = int((labels[box] == i).sum())
        if 10 <= w <= 30 and 2 <= h <= 8 and area >= 0.7 * w * h:
            blobs.append((box[1].start, (box[0].start + box[0].stop - 1) / 2))
    if not blobs:
        return []
    line = statistics.median(y for _, y in blobs)
    return sorted(x for x, y in blobs if abs(y - line) <= 12)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mei", type=Path)
    parser.add_argument("--out", type=Path, help="save each strip as <dir id>.png here")
    args = parser.parse_args(argv)

    root = etree.parse(str(args.mei)).getroot()
    by_id = {e.get(XML_ID): e for e in root.iter() if isinstance(e.tag, str) and e.get(XML_ID)}
    zones, image_of = {}, {}
    for surface in root.iter(M + "surface"):
        image = (args.mei.parent / surface.find(M + "graphic").get("target")).resolve()
        for zone in surface.iter(M + "zone"):
            zones[zone.get(XML_ID)] = tuple(int(zone.get(k)) for k in ("ulx", "uly", "lrx", "lry"))
            image_of[zone.get(XML_ID)] = image
    bar_zone = {int(m.get("n")): m.get("facs").lstrip("#") for m in root.iter(M + "measure")}
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    found = False
    for d in root.find(f".//{M}music").iter(M + "dir"):
        if d.get("extender") != "true":
            continue
        found = True
        text = " ".join("".join(d.itertext()).split())
        first = measure_n(by_id[d.get("startid").lstrip("#")]) if d.get("startid") else measure_n(d)
        if d.get("endid"):
            last = measure_n(by_id[d.get("endid").lstrip("#")])
        else:
            last = first + int((d.get("tstamp2") or "0m").split("m")[0])
        label = f"m{first}-{last} {d.get(XML_ID)} '{text}' lsegs={d.get('lsegs')}"
        if d.get("place") != "above":
            print(f"{label}: place={d.get('place')}, not counted")
            continue

        systems = []
        for n in range(first, last + 1):
            z = bar_zone[n]
            prev = systems[-1][-1] if systems else None
            if prev and image_of[z] == image_of[prev] and abs(zones[z][1] - zones[prev][1]) < SAME_SYSTEM:
                systems[-1].append(z)
            else:
                systems.append([z])
        pieces = []
        for system in systems:
            top = min(zones[z][1] for z in system)
            box = (zones[system[0]][0], top - ABOVE, zones[system[-1]][2], top + BELOW)
            pieces.append(Image.open(image_of[system[0]]).crop(box))
        strip = Image.new("L", (sum(p.width for p in pieces) + GAP * (len(pieces) - 1), ABOVE + BELOW), 255)
        x = 0
        for piece in pieces:
            strip.paste(piece, (x, 0))
            x += piece.width + GAP
        count = len(dashes(strip))
        mark = "" if str(count) == d.get("lsegs") else "  <- differs"
        print(f"{label}: {count} dashes in {len(systems)} system(s){mark}")
        if args.out:
            strip.save(args.out / f"{d.get(XML_ID)}.png")
    if not found:
        print("no dir with @extender=\"true\"")


if __name__ == "__main__":
    main()
