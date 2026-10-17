# Webern, Variations for Piano, Op. 27 — MEI edition after Universal Edition 1937

An MEI 5.1 (CMN) encoding of Anton Webern's Variations for Piano, Op. 27, based on the Universal Edition print, plate U.E. 10881 (first edition Vienna, 1937), in the copy scanned as IMSLP file 28271, which was printed in 1965 or later. The aim is to encode all printed detail, including notes, stems and beams, slurs, articulations, dynamics, tempo and text, and to link every bar to its region on the printed page. The edition is built for [CAMAT](https://github.com/egorpol/camat_v2).

View it in the browser: https://egorpol.github.io/webern_op27/

## Status

Proofread against the print, system by system; corrections welcome before 1.0.

| Movement | Bars | Printed pages | Notation | Facsimile links |
| --- | --- | --- | --- | --- |
| I — Sehr mäßig | 54 | 3–5 | Kern base, enriched from the print by hand in all bars (stems, beams, slurs, dynamics, hairpins, text); clefs checked against the print | 54 zones |
| II — Sehr schnell | pickup + 22 | 6 | Kern base, enriched from the print by hand in all bars (stems, beams, slurs, dynamics, hairpins, text); clefs checked against the print | 23 zones |
| III — Ruhig fließend | 66 | 7–11 | Kern base, enriched from the print by hand in all bars (stems, beams, slurs, dynamics, hairpins, text); clefs checked against the print | 66 zones |

The files are MEI 5.1 and validate against `schemas/mei-CMN-5.1.rng`. They were converted from Verovio's MEI 6.0-dev output by `scripts/migrate_mei51.py`. Each file has an edition header (version 0.9.0): sources, transcribed page paratext and editorial declaration. All three movements use edition versioning without an embedded revision history.

## Layout

- `mei/` — one MEI file per movement. Measure IDs are `ue1937-<movement>-m<NNN>`; the pickup in II is bar 0.
- `facsimiles/ue1937/pages.json` — the nine scan pages: hashes, size, printed page numbers and the bars on each system. The images themselves are not in the repository (see below).
- `sources/sources.json` — source records (URLs, SHA-256, credits, stated rights) for the print, the Kern base encoding and the two cross-check encodings. None of these files is in the repository; `local_path` names the git-ignored place of a local copy.
- `provenance/` — how the facsimile links were made: measure-detector responses (Edirom DOMD), the layout review and the bar-to-zone alignment.
- `schemas/` — the MEI CMN 5.1 schema used for validation.
- `site/` — the web viewer (MIT); see below.
- `scripts/` — maintenance scripts (MIT): `fetch_sources.py` downloads the sources and makes the page images, checking every hash; `validate.py` runs the validation gate; `check_movement.py` sweeps a movement for consistency; `render_page.py` renders the printed pages as encoded, optionally beside the scan; `render_variants.py` compares alternative encodings of a few bars; `count_dashes.py` counts the printed dashes of each extender against `@lsegs`; `build_site.py` assembles the viewer for GitHub Pages; `set_breaks.py` and `migrate_mei51.py` made the breaks and the 5.1 files.
- `docs/` — [editorial policy](docs/editorial-policy.md), including how the edition was proofread, and [MEI encoding profile](docs/mei-encoding-profile.md).

## Facsimile images

The MEI files point to `../facsimiles/ue1937/page-0001.png` … `page-0009.png`. To make them, run

```
python scripts/fetch_sources.py --download --pages imslp-28271-universal-1937
```

Without the source id it also fetches the Kern and cross-check encodings; if a host is down, `--from DIR` copies earlier downloads instead. By hand, the script's steps are:

1. Download the PDF from [IMSLP 28271](https://imslp.org/wiki/Special:ImagefromIndex/28271) into `facsimiles/ue1937/`.
2. Check its SHA-256 against `pdf_sha256` in `facsimiles/ue1937/pages.json`.
3. Rasterize it at 300 dpi: `pdftoppm -r 300 -png imslp-28271-universal-1937.pdf page`, then rename the pages to `page-0001.png` … `page-0009.png`.
4. Check each page hash against `pages.json`. The hashes come from Poppler 26.08.0; another version may give different pixels (the script then warns). The zones stay valid as long as the page sizes match.

The encodings work without the images; only the facsimile view needs them. The same images are published in [egorpol/webern_op27-facsimile](https://github.com/egorpol/webern_op27-facsimile) for use where the print is in the public domain; it is still protected in the US until the end of 2032.

## Viewer

The viewer is published at https://egorpol.github.io/webern_op27/ (for example [movement III, bar 42](https://egorpol.github.io/webern_op27/#III/42)). `site/` is a static page with no build step. Verovio 6.3.0 renders each movement in the browser with the encoded page and system breaks, so each rendered page is one printed page. Hovering shows a symbol's bar and `xml:id`, the editorial notes highlight the elements they refer to, and `#III/42` links to a bar. The scan is shown beside the score with the bar regions from the MEI. Visitors who confirm that the print is in the public domain where they are see the page images from [webern_op27-facsimile](https://github.com/egorpol/webern_op27-facsimile), each checked against its hash in `pages.json`; the browser remembers the confirmation. Others can open their own copy of the IMSLP PDF, which pdf.js renders; its SHA-256 is checked against `pages.json`. The file is read in the browser, never uploaded, and kept in the browser's storage until "Hide the scan".

`.github/workflows/pages.yml` publishes the viewer with GitHub Pages; `scripts/build_site.py` copies only the viewer, the MEI files and `pages.json`. To preview it locally:

```
python scripts/build_site.py && python -m http.server -d _site
```

## Sources and credits

- **Base source:** Universal Edition, Vienna 1937, plate U.E. 10881. Scan from IMSLP, uploaded by JacopoTore; scanner unknown.
- **Base encoding:** Craig Stuart Sapp, KernScores, `webern-op27n1–3.krn` (encoded 2008, revised 2020-11-23). Converted to MEI with Verovio and enriched from the print.
- **Cross-check encodings:** Maja Hartwig's MEI of movement II, pickup and bars 1–11 (MEI Sample Collection, 2011), and Wendy Czajkowsky's Kern of movement III (1995). They only point to places to re-read in the print; see the [editorial policy](docs/editorial-policy.md).
- **Measure regions:** Edirom [Deep Optical Measure Detector](https://measure-detector.edirom.de/).

## License

Encodings and documentation are licensed under CC BY 4.0; scripts under MIT. Third-party sources are not included. See [LICENSE.md](LICENSE.md). To cite the edition, use [CITATION.cff](CITATION.cff).
