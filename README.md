# Webern, Variations for Piano, Op. 27 — MEI edition after Universal Edition 1937

An MEI 5.1 (CMN) encoding of Anton Webern's Variations for Piano, Op. 27, based on the Universal Edition print, plate U.E. 10881 (first edition Vienna, 1937), in the copy scanned as IMSLP file 28271, which was printed in 1965 or later. The aim is to encode all printed detail, including notes, stems and beams, slurs, articulations, dynamics, tempo and text, and to link every bar to its region on the printed page. The edition is built for [CAMAT](https://github.com/egorpol/camat_v2).

## Status

Work in progress; not yet proofread.

| Movement | Bars | Printed pages | Notation | Facsimile links |
| --- | --- | --- | --- | --- |
| I — Sehr mäßig | 54 | 3–5 | Kern base, enriched from the print by hand in all bars (stems, beams, slurs, dynamics, hairpins, text); clefs checked against the print | 54 zones |
| II — Sehr schnell | pickup + 22 | 6 | Kern base (unfinished in the source encoding) | 23 zones |
| III — Ruhig fließend | 66 | 7–11 | Kern base (no tempo changes) | 66 zones |

The files are MEI 5.1 and validate against `schemas/mei-CMN-5.1.rng`. They were converted from Verovio's MEI 6.0-dev output by `scripts/migrate_mei51.py`. Each file has an edition header (version 0.1.0): sources, transcribed page paratext, editorial declaration and revision history.

## Layout

- `mei/` — one MEI file per movement. Measure IDs are `ue1937-<movement>-m<NNN>`; the pickup in II is bar 0.
- `facsimiles/ue1937/pages.json` — the nine scan pages: hashes, size, printed page numbers and the bars on each system. The images themselves are not in the repository (see below).
- `sources/sources.json` — source records (URLs, SHA-256, credits, stated rights).
- `provenance/` — how the facsimile links were made: measure-detector responses (Edirom DOMD), layout review, the bar-to-zone alignment, and a record of the hand edits to movement I.
- `schemas/` — the MEI CMN 5.1 schema used for validation.
- `scripts/` — maintenance scripts (MIT): `validate.py` runs the validation gate; `check_movement.py` sweeps a movement for consistency; `render_page.py` renders the printed pages as encoded, optionally beside the scan; `render_variants.py` compares alternative encodings of a few bars; `count_dashes.py` counts the printed dashes of each extender against `@lsegs`; `set_breaks.py` and `migrate_mei51.py` made the breaks and the 5.1 files.
- `docs/` — [editorial policy](docs/editorial-policy.md), [MEI encoding profile](docs/mei-encoding-profile.md) and [proofreading checklist](docs/proofreading-checklist.md).
- `proofreading/` — progress by system and layer (`progress.csv`) and the log of differences found (`log.csv`).

## Facsimile images

The MEI files point to `../facsimiles/ue1937/page-0001.png` … `page-0009.png`. To view the facsimile:

1. Download the PDF from [IMSLP 28271](https://imslp.org/wiki/Special:ImagefromIndex/28271) into `facsimiles/ue1937/`.
2. Check its SHA-256 against `pdf_sha256` in `facsimiles/ue1937/pages.json`.
3. Rasterize it at 300 dpi: `pdftoppm -r 300 -png imslp-28271-universal-1937.pdf page`, then rename the pages to `page-0001.png` … `page-0009.png`.
4. Check each page hash against `pages.json`. The hashes come from Poppler 26.08.0; another version may give different pixels. The zones stay valid as long as the page sizes match.

The encodings work without the images; only the facsimile view needs them.

## Sources and credits

- **Base source:** Universal Edition, Vienna 1937, plate U.E. 10881. Scan from IMSLP, uploaded by JacopoTore; scanner unknown.
- **Base encoding:** Craig Stuart Sapp, KernScores, `webern-op27n1–3.krn` (encoded 2008, revised 2020-11-23). Converted to MEI with Verovio and enriched from the print.
- **Measure regions:** Edirom [Deep Optical Measure Detector](https://measure-detector.edirom.de/).

## License

Encodings and documentation are licensed under CC BY 4.0; scripts under MIT. Third-party sources are not included. See [LICENSE.md](LICENSE.md). To cite the edition, use [CITATION.cff](CITATION.cff).
