# Upstream issues

Oddities in Verovio and MEI found while encoding this edition, collected so they can be filed on [rism-digital/verovio](https://github.com/rism-digital/verovio/issues) or [music-encoding/music-encoding](https://github.com/music-encoding/music-encoding/issues). Each entry says what was checked and on which version. "Confirmed" means reproduced here; "to recheck" means it was observed earlier and needs a minimal example before filing.

## Verovio

### 1. Text extenders ignore `@lform`, `@lsegs` and `@lwidth`

- **Status:** confirmed in Verovio 6.3.0 (the latest release, rendered) and on `develop` at `2788fea`, 2026-10-08 (source read). A feature request, not a regression.
- **Where:** movement I, "rit." in bars 17–18 and 19–20 (`ue1937-I-dir-rit-m017`, `ue1937-I-dir-rit-m019`).
- **What happens:** a `dir` with `@extender="true"` is drawn with the same dashed line whatever its line attributes say. Rendering the bar 17 "rit." with `lsegs="5"`, `lsegs="13"`, no `@lsegs`, `lform="dotted"` and `lwidth="narrow"` gives identical SVG: a dash 120 units long every 1200 units.
- **Cause:** `View::DrawControlElementConnector` in `src/view_control.cpp`, used for `dir`, `dynam` and `tempo`, hard-codes the pattern: the dash length is 4/3 of a drawing unit (2/3 of a staff space), the period is 5/3 of the staff height (6 2/3 staff spaces), and the thickness comes from the `lyricLineThickness` option. The code comment reads "the length of the dash and the space between them - can be made a parameter". No toolkit option sets them; `extenderLineMinSpace` only suppresses short lines.
- **Print for comparison:** UE 10881, p. 3, bars 17–18: 11 dashes about 0.8 staff spaces long, one every 4.1 staff spaces (16–17 px every 80 px at a staff space of 19.6 px, 300 dpi). The print is about 1.6 times as dense as Verovio's line.
- **Minimal example:**

  ```xml
  <dir staff="1" tstamp="1" tstamp2="1m+4" extender="true" lform="dashed" lsegs="11">rit.</dir>
  ```

- **Request:** honour `att.lineRend.base` on text extenders: `@lsegs` as the number of dashes, `@lform` (`dotted`, `solid`), `@lwidth`. Failing that, expose the dash length and gap as options, as the code comment suggests.

### 2. `beamSpan` not drawn (not reproduced)

- **Status:** not reproduced; nothing to file. Rechecked 2026-10-13: rendered with encoded breaks, each of the 41 `beamSpan`s in the three files (I: 39, II: 1, III: 1) has beam polygons in Verovio 6.3.0's SVG. That includes movement II, bars 2–3 (`ue1937-II-beamSpan-L37F1-L40F2`), the case noted earlier, which was a one-note `beam` until the repair in `54e2992`. Movement I, bars 22–23 (`ue1937-I-beamSpan-L113F1-L114F2-L116F1`) is drawn once the stem directions are right, with one beam line too few at the start (2a).
- **Side note:** `beamSpan/@staff="1 2"` makes Verovio 6.3.0 draw the beam twice (once per staff). Give the staff of the first note only.

### 2a. `beamSpan` with opposite stem directions loses a secondary beam

- **Status:** confirmed in Verovio 6.3.0 (`6.3.0-425dd7b`, Python package), rechecked 2026-10-13 with the minimal example below. Ready to file; the editor files it. GitHub search of 2026-10-13: no matching issue. The open mixed-beam issues are about articulations (#3933), chords (#2631), rests (#3660) and spacing (#1955); #2893 was a broken encoding. No commit on `develop` since 6.3.0 touches `beam.cpp` or `beamspan.cpp`.
- **Where:** movement I, bars 22–23 (`ue1937-I-beamSpan-L113F1-L114F2-L116F1`): 32nds B♭ (lower staff, stem up), E (upper staff, stem down), B♮ (lower staff, stem up), one beam between the staves. The print has three beam lines throughout. `beamSpan/@staff="1"` and `@place="mixed"` change nothing.
- **Issue text** (title and body; attach a render of both files side by side):

  > **beamSpan with mixed stem directions drops a secondary beam before the stem-down note**
  >
  > A `beamSpan` over three 32nd notes with stems up, down, up (the middle note in the other staff) draws two beam lines from the first to the second note and three from the second note on. The two segments also do not join at the second note's stem. The same three notes in a `<beam>`, with `@staff` on the middle note, get three beam lines throughout, as expected.
  >
  > The real case is a `beamSpan` across a barline (Webern, Variations Op. 27/I, bars 22–23); the minimal example has it inside one bar, with the same result. `beamSpan/@staff` set to the other staff and `beamSpan/@place="mixed"` make no difference.
  >
  > Verovio 6.3.0 (`6.3.0-425dd7b`). Not tested on `develop`, but no commit there since 6.3.0 touches `beam.cpp` or `beamspan.cpp`.
  >
  > With `beamSpan` (wrong: two lines up to the E):
  >
  > ```xml
  > <?xml version="1.0" encoding="UTF-8"?>
  > <mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="5.1">
  >   <meiHead><fileDesc><titleStmt><title>beamSpan with mixed stems</title></titleStmt><pubStmt/></fileDesc></meiHead>
  >   <music><body><mdiv><score>
  >     <scoreDef meter.count="3" meter.unit="32">
  >       <staffGrp symbol="brace" bar.thru="true">
  >         <staffDef n="1" lines="5" clef.shape="F" clef.line="4"/>
  >         <staffDef n="2" lines="5" clef.shape="F" clef.line="4"/>
  >       </staffGrp>
  >     </scoreDef>
  >     <section>
  >       <measure n="1">
  >         <staff n="1"><layer n="1"><space dur="32"/><note xml:id="e" dur="32" pname="e" oct="3" stem.dir="down"/><space dur="32"/></layer></staff>
  >         <staff n="2"><layer n="1"><note xml:id="bb" dur="32" pname="b" oct="2" accid="f" stem.dir="up"/><space dur="32"/><note xml:id="bn" dur="32" pname="b" oct="1" stem.dir="up"/></layer></staff>
  >         <beamSpan staff="2" plist="#bb #e #bn" startid="#bb" endid="#bn"/>
  >       </measure>
  >     </section>
  >   </score></mdiv></body></music>
  > </mei>
  > ```
  >
  > With `<beam>` (correct: three lines throughout), the same file with this measure:
  >
  > ```xml
  > <measure n="1">
  >   <staff n="1"><layer n="1"><space dur="16" dots="1"/></layer></staff>
  >   <staff n="2"><layer n="1"><beam><note xml:id="bb" dur="32" pname="b" oct="2" accid="f" stem.dir="up"/><note xml:id="e" dur="32" pname="e" oct="3" staff="1" stem.dir="down"/><note xml:id="bn" dur="32" pname="b" oct="1" stem.dir="up"/></beam></layer></staff>
  > </measure>
  > ```

- **Render for the issue:** load both files with `spacingLinear` and `spacingNonLinear` at `1.0` (the default spacing crowds the three notes too tightly to count the beam lines).

### 2b. `@vgrp` does not line up a `tempo` with `dir`s (to recheck)

- **Status:** observed in Verovio 6.3.0 on movement I, 2026-10-13: with the same `@vgrp` on every "rit." `dir` and "tempo" `dir`, Verovio sets them on one line per system. Making the "tempo"s `tempo` elements with the same `@vgrp` puts them on a line of their own. Check whether this is intended before filing; MEI does not limit `@vgrp` to one element type.

### 3. No page heading from `meiHead` (to recheck)

- **Status:** to recheck. With Verovio 6.3, the edition headers draw no title or composer, so each movement repeats the printed head in a `pgHead`. Check which header fields Verovio reads for its automatic heading before filing.

### Known behaviour, not issues

- Verovio's MEI output is MEI 6.0-dev; it has no MEI 5 writer. Its MEI Basic output drops the facsimile, the header and many IDs. This is why the MEI files are edited as text.
- The Humdrum import copies a layout group name (`!!LO:LB:g=z`) into `sb/@type`. The group name is arbitrary in Humdrum and means nothing in MEI; this edition drops it.

## MEI

### 4. No way to encode dash length or spacing

- **Status:** observation for the Guidelines; low priority.
- `att.lineRend.base` offers `@lform`, `@lwidth` and `@lsegs` (the number of segments). A print's dash density can only be recorded as a count, not as dash length or gap. For this edition the count plus the facsimile zone is enough.

### 5. `application` content model in 5.1 (to recheck)

- **Status:** to recheck against the 5.1 schema and the current development version. In MEI 5.1, `application` takes either `ptr`/`ref` children or `p`s, not both, which makes it awkward to give a tool both a link and a description.
