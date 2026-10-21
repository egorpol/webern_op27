# Upstream issues

Verovio problems found while encoding this edition. Each was confirmed on 2026-10-17 with Verovio 6.3.0 (`6.3.0-425dd7b`, the latest release) and the development version (`6.4.0-dev-3c322ca`, 2026-10-16), then filed on [rism-digital/verovio](https://github.com/rism-digital/verovio/issues) or added to an existing issue. Minimal examples and analysis are in the linked issues.

## Verovio

- **Text extenders ignore `@lform`, `@lsegs` and `@lwidth`.** Movement I, the dashed lines after "rit.": Verovio draws one fixed dash pattern, about 1.6 times sparser than the print. [#4508](https://github.com/rism-digital/verovio/issues/4508) (feature request).
- **`beamSpan` with opposite stem directions loses a secondary beam.** Movement I, bars 22–23. [#4509](https://github.com/rism-digital/verovio/issues/4509).
- **`@vgrp` does not line up a `tempo` with `dir`s.** Movement I, the nine "rit." … "tempo" pairs. Known upstream as [#1151](https://github.com/rism-digital/verovio/issues/1151) and the draft [PR #4407](https://github.com/rism-digital/verovio/pull/4407); this case was added to the PR as a [comment](https://github.com/rism-digital/verovio/pull/4407#issuecomment-6239555687). Edition workaround: the return "tempo" is a `dir` with the same `@vgrp` as the "rit."s (for example `ue1937-I-dir-tempo-L110F2`), which lines up in 6.3.0.
- **`@stem.len` is ignored on `beamSpan` notes.** Movement II, bars 12–13: the beam sits above the lower staff, where the print runs it through the staff. The encoding is right and records no stem length. [#932](https://github.com/rism-digital/verovio/issues/932) (open since 2018); this case was added as a [comment](https://github.com/rism-digital/verovio/issues/932#issuecomment-6235455597).
- **Grace-note slur to a chord member attaches beneath the whole chord.** Movement III, bars 15 and 18. [#4313](https://github.com/rism-digital/verovio/issues/4313); this case was added as a [comment](https://github.com/rism-digital/verovio/issues/4313#issuecomment-6239248129). Edition workaround: the two slurs use `@curvedir="above"`; the note-specific endpoints stay encoded, and an `encoding-note` at each records the printed lower curve.
- **`beamSpan` does not avoid rests in its `@plist`.** Movement III, bars 51–52: the beam runs through the eighth rest at the start of bar 52. [#4511](https://github.com/rism-digital/verovio/issues/4511).
- **Page header from `meiHead` omits a composer wrapped in `persName`.** All movements; a regression since 4.4.0. [#4512](https://github.com/rism-digital/verovio/issues/4512), closed 2026-10-20 without a fix: the maintainer replied that the generated header is meant for simple cases and that a `pgHead` should be encoded instead. This edition does so: each movement repeats its printed head in a `pgHead` in the first `scoreDef`.

## Known behaviour, not issues

- Verovio's MEI output is MEI 6.0-dev; it has no MEI 5 writer. Its MEI Basic output drops the facsimile, the header and many IDs. This is why the MEI files are edited as text.
- `beamSpan/@staff="1 2"` makes Verovio draw the beam once per staff, as it does for any control event with several staves. Give the staff of the first note only.
- The Humdrum import copies a layout group name (`!!LO:LB:g=z`) into `sb/@type`. The group name is arbitrary in Humdrum and means nothing in MEI; this edition drops it.
