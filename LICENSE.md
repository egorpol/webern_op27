# Licenses

- **Encodings and documentation** (`mei/`, `docs/`, `provenance/`, `sources/sources.json`, `facsimiles/**/pages.json`, this README): [Creative Commons Attribution 4.0 International](LICENSES/CC-BY-4.0.txt) (CC BY 4.0).
- **Scripts and the viewer** (`scripts/`, `site/`, `.github/`, `tests/`): [MIT License](LICENSES/MIT.txt).

Third-party material is not covered by these licenses and is not included in the repository:

- Universal Edition, Vienna 1937 (plate U.E. 10881), scanned copy from IMSLP file 28271. The catalogue lists it as "Public Domain - Non-PD US"; the scan also prints a 1965 copyright renewal. The PDF and page images are cited by URL and SHA-256 only; the page images are published separately in [egorpol/webern_op27-facsimile](https://github.com/egorpol/webern_op27-facsimile), from which the viewer loads them.
- Craig Stuart Sapp's KernScores encodings `webern-op27n1–3.krn` (2008, revised 2020-11-23), the base encoding of the notes and rhythms. They carry no redistribution license and are cited by URL and SHA-256 only.
- The viewer loads [Verovio](https://github.com/rism-digital/verovio) (LGPL-3.0) and [pdf.js](https://github.com/mozilla/pdf.js) (Apache-2.0) from jsDelivr when it runs; neither is included.
- For playback, the viewer loads [Tone.js](https://github.com/Tonejs/Tone.js), [@tonejs/midi](https://github.com/Tonejs/Midi) and [smplr](https://github.com/danigb/smplr) (all MIT) from jsDelivr when Play is pressed, with the FluidR3_GM piano samples by Frank Wen ([MIT](https://github.com/musescore/MuseScore/blob/main/share/sound/FluidR3Mono_License.md)) as rendered in [midi-js-soundfonts](https://github.com/gleitz/midi-js-soundfonts) by Benjamin Gleitzman ([CC BY 3.0](https://creativecommons.org/licenses/by/3.0/us/)). None of these is included.
