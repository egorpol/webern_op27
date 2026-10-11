#!/usr/bin/env python3
"""Write the page and system breaks of each movement from pages.json.

Every existing <pb/> and <sb/> is removed, then one break is inserted before
the first bar of each printed system, in the form movement I was hand-edited
in:

  <pb xml:id="ue1937-<mvt>-pb-before-m<NNN>" facs="#surface-ue1937-p<NNNN>" n="<printed page>" />
  <sb xml:id="ue1937-<mvt>-sb-before-m<NNN>" />

The Kern conversion's sb/@type="z" (the Humdrum layout group name) is not kept.

A break stands in the section of the bar it precedes, before any scoreDef
that directly precedes that bar, so a clef change applies to the new system.
The MEI is edited as text (one break per line); a file whose breaks already
match is left unchanged.

Before writing, pages.json is checked against the file: its systems list
every bar in document order, and each bar's zone lies on the page's surface.

Usage: python scripts/set_breaks.py [mei/webern-op27-*.mei ...]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from lxml import etree

REPO = Path(__file__).resolve().parents[1]
PAGES = REPO / "facsimiles" / "ue1937" / "pages.json"
MEI_NS = "http://www.music-encoding.org/ns/mei"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
BREAK_LINE = re.compile(r"[ ]*<(pb|sb) [^<>]*/>\r?\n?")
MOVEMENT = re.compile(r"webern-op27-(I|II|III)\.mei$")


def tag(element: etree._Element) -> str:
    return etree.QName(element).localname


def expected_breaks(path: Path, mvt: str, pages: list[dict]) -> dict[int, list[str]]:
    """Map 0-based line index -> break lines to insert before it."""
    root = etree.parse(str(path)).getroot()
    ns = {"mei": MEI_NS}
    measures = root.findall(".//mei:music//mei:measure", ns)
    zone_surface = {
        zone.get(XML_ID): zone.getparent().get(XML_ID)
        for zone in root.findall(".//mei:facsimile/mei:surface/mei:zone", ns)
    }
    surfaces = {s.get(XML_ID): s for s in root.findall(".//mei:facsimile/mei:surface", ns)}

    pages = [p for p in pages if p["movement"] == mvt]
    listed = [n for p in pages for system in p["systems"] for n in system]
    encoded = [int(m.get("n")) for m in measures]
    if listed != encoded:
        raise SystemExit(f"{path.name}: pages.json bars {listed} != encoded bars {encoded}")

    by_n = {int(m.get("n")): m for m in measures}
    inserts: dict[int, list[str]] = {}
    for page in pages:
        surface_id = f"surface-ue1937-p{page['pdf_page_number']:04d}"
        surface = surfaces.get(surface_id)
        if surface is None or surface.get("n") != str(page["printed_page"]):
            raise SystemExit(f"{path.name}: no {surface_id} with @n={page['printed_page']}")
        for system in page["systems"]:
            for n in system:
                zone = (by_n[n].get("facs") or "").lstrip("#")
                if zone_surface.get(zone) != surface_id:
                    raise SystemExit(f"{path.name}: bar {n} zone {zone!r} is not on {surface_id}")

        for i, system in enumerate(page["systems"]):
            first = by_n[system[0]]
            if first.get(XML_ID) != f"ue1937-{mvt}-m{system[0]:03d}":
                raise SystemExit(f"{path.name}: bar {system[0]} has id {first.get(XML_ID)!r}")
            anchor = first
            prev = anchor.getprevious()
            while prev is not None and (
                not isinstance(prev.tag, str) or tag(prev) in {"pb", "sb", "scoreDef"}
            ):
                if isinstance(prev.tag, str) and tag(prev) == "scoreDef":
                    anchor = prev
                prev = prev.getprevious()
            ident = f"before-m{system[0]:03d}"
            if i == 0:
                line = f'<pb xml:id="ue1937-{mvt}-pb-{ident}" facs="#{surface_id}" n="{page["printed_page"]}" />'
            else:
                line = f'<sb xml:id="ue1937-{mvt}-sb-{ident}" />'
            inserts.setdefault(anchor.sourceline - 1, []).append(line)
    return inserts


def set_breaks(path: Path, pages: list[dict]) -> bool:
    mvt = MOVEMENT.search(path.name)
    if mvt is None:
        raise SystemExit(f"{path.name}: not a movement file")
    inserts = expected_breaks(path, mvt.group(1), pages)
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    breaks = len(re.findall(r"<(?:pb|sb)[\s/>]", text))
    if breaks != sum(1 for line in lines if BREAK_LINE.fullmatch(line)):
        raise SystemExit(f"{path.name}: a pb/sb does not stand alone on its line")

    out: list[str] = []
    for index, line in enumerate(lines):
        if index in inserts:
            indent = line[: len(line) - len(line.lstrip(" "))]
            newline = "\r\n" if line.endswith("\r\n") else "\n"
            out.extend(f"{indent}{b}{newline}" for b in inserts[index])
        if not BREAK_LINE.fullmatch(line):
            out.append(line)
    new = "".join(out)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main(argv: list[str]) -> int:
    pages = json.loads(PAGES.read_text(encoding="utf-8"))["pages"]
    paths = [Path(a) for a in argv] or sorted((REPO / "mei").glob("webern-op27-*.mei"))
    for path in paths:
        print(f"{path.name}: {'breaks rewritten' if set_breaks(path, pages) else 'unchanged'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
