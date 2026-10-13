#!/usr/bin/env python3
"""Fetch and check local copies of the sources the edition cites by URL and SHA-256.

No source file is committed. Each record in sources/sources.json names the
git-ignored place of its local copy in local_path: facsimiles/ue1937/ for the
IMSLP PDF, sources/kern/ for Sapp's Kern files, sources/crosscheck/ for the
cross-check encodings.

Without options the script checks the local copies against their SHA-256.
--download fetches each missing file from its download_url; --from DIR copies
it from a directory of earlier copies (matched by file name) instead, for when
a host is down. New bytes are hashed before anything is written, and an
existing file is never replaced.

--pages rasterizes the PDF as pages.json records it (300 dpi, pdftoppm) into
facsimiles/ue1937/page-NNNN.png, missing pages only, and checks every page:
its size must match, since the zones are in pixels; a different hash only
warns, because another Poppler version may give different pixels.

Standard library only, Python 3.11+ (plus pdftoppm for --pages).

Usage: python scripts/fetch_sources.py [--download | --from DIR] [--pages] [id ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

REPO = Path(__file__).resolve().parents[1]
MANIFEST = REPO / "sources" / "sources.json"
PAGES = REPO / "facsimiles" / "ue1937" / "pages.json"
MAX_BYTES = 100 * 1024 * 1024
USER_AGENT = "webern_op27-fetch_sources/1.0 (+https://github.com/egorpol/webern_op27)"


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_path(entry: dict) -> Path:
    path = (REPO / entry["local_path"]).resolve()
    if not path.is_relative_to(REPO):
        raise SystemExit(f"{entry['id']}: local_path escapes the repository")
    return path


def download(url: str, timeout: float) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as response:
        data = response.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("download exceeds 100 MiB")
    return data


def fetch(entry: dict, args) -> tuple[str, str]:
    """Return (status, detail) for one source: ok, fetched, missing, failed or mismatch."""
    path = local_path(entry)
    if path.exists():
        digest = file_sha256(path)
        if digest != entry["sha256"]:
            return "mismatch", f"local copy has sha256 {digest[:12]}…"
        return "ok", ""
    if args.from_dir:
        origin = args.from_dir / path.name
        if not origin.is_file():
            return "missing", f"not in {args.from_dir}"
        data = origin.read_bytes()
    elif args.download:
        origin = entry["download_url"]
        try:
            data = download(origin, args.timeout)
        except (OSError, ValueError) as error:  # URLError and timeouts are OSErrors
            return "failed", f"{origin}: {error}"
    else:
        return "missing", "run with --download or --from DIR"
    digest = hashlib.sha256(data).hexdigest()
    if digest != entry["sha256"]:
        return "mismatch", f"{origin} gave {len(data)} bytes, sha256 {digest[:12]}…; nothing written"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    return "fetched", f"from {origin}"


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"{path.name} is not a PNG")
    return struct.unpack(">II", header[16:24])


def make_pages(pdf: Path) -> bool:
    spec = json.loads(PAGES.read_text())
    if not pdf.exists() or file_sha256(pdf) != spec["pdf_sha256"]:
        print("pages: the PDF is missing or differs from pdf_sha256 in pages.json; fetch it first")
        return False
    missing = [page for page in spec["pages"] if not (PAGES.parent / page["file"]).exists()]
    if missing and shutil.which("pdftoppm") is None:
        print("pages: pdftoppm (Poppler) is needed to rasterize the PDF")
        return False
    passed = True
    for page in spec["pages"]:
        target = PAGES.parent / page["file"]
        made = ""
        if page in missing:
            number = str(page["pdf_page_number"])
            with tempfile.TemporaryDirectory() as tmp:
                stem = Path(tmp) / "page"
                subprocess.run(["pdftoppm", "-r", str(spec["resolution_dpi"]), "-png", "-f", number,
                                "-l", number, "-singlefile", str(pdf), str(stem)], check=True)
                shutil.move(stem.with_suffix(".png"), target)
            made = " (rendered)"
        size = png_size(target)
        if size != (page["width"], page["height"]):
            print(f"  FAIL  {page['file']}: {size[0]}×{size[1]}, pages.json has "
                  f"{page['width']}×{page['height']}; the zones would not fit{made}")
            passed = False
        elif file_sha256(target) != page["sha256"]:
            print(f"  warn  {page['file']}: size matches, pixels differ from the recorded hash "
                  f"({spec['renderer']} made it){made}")
        else:
            print(f"  ok    {page['file']}{made}")
    return passed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("ids", nargs="*", help="source ids from sources.json (default: all)")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--download", action="store_true", help="fetch missing files from download_url")
    source.add_argument("--from", dest="from_dir", type=Path, metavar="DIR",
                        help="copy missing files from DIR (by file name) instead of downloading")
    parser.add_argument("--pages", action="store_true", help="rasterize and check the facsimile pages")
    parser.add_argument("--timeout", type=float, default=60, help="seconds per download (default 60)")
    args = parser.parse_args(argv)

    entries = json.loads(MANIFEST.read_text())["sources"]
    unknown = set(args.ids) - {entry["id"] for entry in entries}
    if unknown:
        raise SystemExit(f"unknown source id(s): {', '.join(sorted(unknown))}")
    selected = [entry for entry in entries if not args.ids or entry["id"] in args.ids]

    passed = True
    for entry in selected:
        status, detail = fetch(entry, args)
        passed &= status in ("ok", "fetched")
        print(f"  {status:8} {entry['id']:28} {entry['local_path']}" + (f"  {detail}" if detail else ""))
    if args.pages:
        pdf = next(local_path(entry) for entry in entries if entry["id"] == json.loads(PAGES.read_text())["source"])
        passed &= make_pages(pdf)
    print("all present and verified" if passed else "incomplete: see above")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
