# Proofreading checklist

Proofreading compares the encoding with the scan of the print, one sign at a time. The comparison is always against the page images. Kern, the cross-check encodings and the rendering of other editions can point to places worth looking at; they never decide a reading. The [editorial policy](editorial-policy.md) says what to do with a difference; the [encoding profile](mei-encoding-profile.md) says how to encode it.

## Setup

1. Fetch the sources and make the page images: `python scripts/fetch_sources.py --download --pages` (see the README) checks every hash. The Kern files land in `sources/kern/`, the cross-check encodings in `sources/crosscheck/`.
2. Open the movement in a viewer that shows the rendering next to the measure zone: CAMAT's facsimile viewer, or mei-friend with the facsimile. `python scripts/render_page.py <mei> -o <dir> --scan` sets each printed page beside its rendering with the encoded breaks.
3. Keep the movement's zones at hand: `facsimiles/ue1937/pages.json` lists the bars on each system.

Verovio 6.3 draws `beamSpan`, but with opposite stem directions it drops a secondary beam ([upstream notes](upstream-issues.md), 2a). Check those beams in the MEI text.

## Unit of work

Work one system at a time. Within a system, make one pass per layer, in the order below, across the whole system. The short names in brackets are the column names in `progress.csv`. Checking one kind of sign at a time catches more than reading each bar once for everything.

After each system:

1. Record each difference in `proofreading/log.csv` and fix or annotate it.
2. Run the validation (`python scripts/validate.py`; see the encoding profile) and fix what it reports.
3. Fill in the system's row in `proofreading/progress.csv`: the date and the editor's initials under each layer done.
4. Commit, naming the movement, page and system.

After the last system of a movement, run the consistency sweep, `python scripts/check_movement.py <mei> --baseline 98812bc`. It lists bars whose layers do not fill the meter, control events without `@staff` or `@place` or anchored by `@tstamp`, hairpins that end just before a dynamic without being joined to it, extenders without `@lsegs`, notes without `@stem.dir`, how accidentals are encoded, and every pitch or duration changed since the first commit (`98812bc`). `python scripts/count_dashes.py <mei> --out <dir>` counts the printed dashes of each extender above the staff against `@lsegs`; check its strips by eye.

## Layers

1. **Pitch and written accidentals.** (`pitch`) Note names and octaves (count the ledger lines; check the clef in force). Every printed accidental, naturals included, is a written accidental. A tied continuation without a printed sign uses `@accid.ges`. Kern pitch errors are possible anywhere; movement II is marked "encoding not finished" in its source.
2. **Rhythm, tuplets, rests and layers.** (`rhythm`) Durations and dots, rests and their staff, grace notes, the split into layers where one staff carries two parts. Each layer fills the bar (CAMAT flags underfull layers). Empty staves hold an `mSpace`.
3. **Staff, cross-staff and clefs.** (`staff`) Each note on the staff where it is printed (`@staff` for cross-staff notes). Every clef change at its printed position, mid-bar ones included.
4. **Stems and beams.** (`stems_beams`) `@stem.dir` on every note and chord. Beam groups as printed. `beamSpan` for beams across a barline or between layers. `@breaksec` for broken secondary beams.
5. **Ties and slurs.** (`ties_slurs`) Start and end notes, slurs to and from grace notes, curve direction where the print fixes it.
6. **Articulations.** (`artic`) Staccato, tenuto, accents, and their side of the note.
7. **Dynamics and hairpins.** (`dynamics`) Letters, the note each one belongs to, staff and placement, and hairpin start and end.
8. **Tempo and tempo changes.** (`tempo`) Tempo texts and metronome marks (text plus `@mm`, `@mm.unit`, `@mm.dots`), "rit.", "tempo" and their extenders. Movement III has no tempo changes in the Kern source.
9. **Fermatas and caesuras.** (`fermatas`)
10. **Repeats, pickups and meter.** (`structure`) Repeat signs, the pickup in II (`metcon="false"`), meter signatures, printed bar numbers (`measure/@n`).
11. **Other printed text.** (`text`) Any remaining instruction in the music. The page paratext (title, composer line, copyright lines, plate number) is checked against the header, not the score.

The page and system breaks are checked once per page: `pb` before the first bar of the page and `sb` before the first bar of every other system.

## Known places to check

- **I, bars 1–18:** enriched from the print by hand (stems, beams, slurs, dynamics, hairpins, text). These have not yet been proofread layer by layer.
- **I, bars 3–51:** clef changes were aligned "via the DCMLab reference", an export of a MuseScore score that may not be reused. Check every clef against the scan and keep only what the print shows. Done 2026-10-13: the editor checked every clef; all match the print.
- **I, bar 1:** the tempo mark lacks `@mm`, `@mm.unit` and `@mm.dots`. Done 2026-10-13: `mm="40" mm.unit="8" mm.dots="1"`.
- **II:** the Kern source is unfinished; expect gaps in every layer. Bars 10, 15 and 16 have one staff that holds only an `mSpace`.
- **III:** tempo changes are missing.
- **II, III, first bar:** the tempo marks lack `@mm` and `@mm.unit`. Done 2026-10-13: II `mm="160" mm.unit="4"`, III `mm="80" mm.unit="2"`.
- **II, III:** the Kern conversion anchors dynamics and other control events by `@tstamp`; the profile asks for `@startid` wherever a note is printed at that point: in II 31 dynamics; in III 62 dynamics, 17 hairpins, 3 `dir`s and 2 fermatas (count of 2026-10-13). `scripts/check_movement.py` lists them.

## The log

`proofreading/log.csv` has one row per difference found between the encoding and the print:

| Column | Content |
| --- | --- |
| `date` | ISO date found |
| `movement`, `bar`, `staff` | Location; `staff` as numbered in the MEI |
| `layer` | Checklist layer, by its short name in `progress.csv` |
| `ids` | Affected `xml:id`s, space-separated |
| `print` | What the print shows |
| `encoded` | What the encoding had |
| `action` | `repair`, `source-reading`, `encoding-note` or `unresolved-reading` (see the editorial policy) |
| `commit` | Commit that resolved it, once there is one |
| `note` | Anything else: page and zone, reasoning, links to an `annot` |

Routine repairs need only the log entry and the commit. The other three actions also need an `annot` in the MEI.
