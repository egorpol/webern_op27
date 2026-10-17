# Upstream issues

Verovio problems found while encoding this edition, collected so they can be filed on [rism-digital/verovio](https://github.com/rism-digital/verovio/issues). Every entry was rechecked on 2026-10-17 against Verovio 6.3.0 (`6.3.0-425dd7b`, the latest release) and the development version (`6.4.0-dev-3c322ca`, 2026-10-16). No commit on `develop` since 6.3.0 touches the beam, `beamSpan`, slur, page-header or vertical-group code. "To file" means a new issue is ready; the link replaces the note once it is posted.

## Verovio

### 1. Text extenders ignore `@lform`, `@lsegs` and `@lwidth`

- **Status:** confirmed on 6.3.0 and `develop`. To file as a feature request. [#3646](https://github.com/rism-digital/verovio/issues/3646) ("@extender enhancements", closed 2024) is related, not the same.
- **Where:** movement I, "rit." in bars 17–18 and 19–20 (`ue1937-I-dir-rit-m017`, `ue1937-I-dir-rit-m019`).
- **What happens:** a `dir` with `@extender="true"` is drawn with the same dashed line whatever its line attributes say. Ten variants (`lform="dashed" lsegs="11"`, `lsegs="5"`, `lsegs="30"`, none, `lform` dotted, solid and wavy, `lwidth` narrow, wide and `3vu`) give identical SVG: dashes 120 units long and 22 thick, one every 1200 units.
- **Cause:** [`View::DrawControlElementConnector`](https://github.com/rism-digital/verovio/blob/version-6.3.0/src/view_control.cpp#L1269-L1276), used for `dir`, `dynam` and `tempo`, hard-codes the pattern: the dash is 2/3 of a staff space long, the period is 5/3 of the staff height, and the thickness comes from `lyricLineThickness`. The code comment reads "the length of the dash and the space between them - can be made a parameter". `extenderLineMinSpace` only suppresses short lines. Other line-like elements already honour these attributes: `@lform` on `hairpin`, `octave`, `bracketSpan`, `slur` and `tie`; `@lwidth` on `octave`, `bracketSpan` and `gliss`.
- **Print for comparison:** UE 10881, p. 3, bars 17–18: 11 dashes about 0.8 staff spaces long, one every 4.1 staff spaces. The print is about 1.6 times as dense as Verovio's line.
- **Minimal example:**

  ```xml
  <dir staff="1" place="above" tstamp="1" tstamp2="1m+4" extender="true" lform="dashed" lsegs="11">rit.</dir>
  ```

- **Request:** honour `att.lineRend.base` on extender lines: `@lform` (solid, dashed, dotted), `@lwidth`, and `@lsegs` as the number of dashes. Failing that, add options for the dash length and the gap.

### 2. `beamSpan` not drawn (not reproduced)

- **Status:** nothing to file. All 53 `beamSpan`s in the three files (I: 39, II: 10, III: 4) are drawn on 6.3.0 and `develop`. The case noted earlier, movement II bars 2–3, was a one-note `beam` until the repair in `54e2992`.

### 2a. `beamSpan` with opposite stem directions loses a secondary beam

- **Status:** confirmed on 6.3.0 and `develop`. To file. No matching issue: the open mixed-beam issues are about articulations (#3933), chords (#2631), rests (#3660), spacing (#1955) and #2895; #2893 was a broken encoding.
- **Where:** movement I, bars 22–23 (`ue1937-I-beamSpan-L113F1-L114F2-L116F1`): 32nds B♭ (lower staff, stem up), E (upper staff, stem down), B♮ (lower staff, stem up), one beam between the staves. The print has three beam lines throughout.
- **What happens:** Verovio draws two beam lines from the first note to the second and three from the second note on. The segments do not join at the second note's stem, and the first note's stem overshoots the top line by about half a staff space. The missing segments are computed but misplaced: the `beamSpan`'s SVG group has five polygons, two full-length lines, one segment from the second note to the third, and two segments from the first note to the second that lie exactly on top of the full-length lines. The same notes in a `<beam>`, with `@staff` on the middle note, get three lines throughout. `beamSpan/@staff` set to the other staff and `beamSpan/@place="mixed"` change nothing.
- **Minimal example** (render with `spacingLinear` and `spacingNonLinear` at 1.0 so the lines can be counted):

  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="5.1">
    <meiHead><fileDesc><titleStmt><title>beamSpan with mixed stems</title></titleStmt><pubStmt/></fileDesc></meiHead>
    <music><body><mdiv><score>
      <scoreDef meter.count="3" meter.unit="32">
        <staffGrp symbol="brace" bar.thru="true">
          <staffDef n="1" lines="5" clef.shape="F" clef.line="4"/>
          <staffDef n="2" lines="5" clef.shape="F" clef.line="4"/>
        </staffGrp>
      </scoreDef>
      <section>
        <measure n="1">
          <staff n="1"><layer n="1"><space dur="32"/><note xml:id="e" dur="32" pname="e" oct="3" stem.dir="down"/><space dur="32"/></layer></staff>
          <staff n="2"><layer n="1"><note xml:id="bb" dur="32" pname="b" oct="2" accid="f" stem.dir="up"/><space dur="32"/><note xml:id="bn" dur="32" pname="b" oct="1" stem.dir="up"/></layer></staff>
          <beamSpan staff="2" plist="#bb #e #bn" startid="#bb" endid="#bn"/>
        </measure>
      </section>
    </score></mdiv></body></music>
  </mei>
  ```

  For comparison, the same measure with a `<beam>` (correct):

  ```xml
  <measure n="1">
    <staff n="1"><layer n="1"><space dur="16" dots="1"/></layer></staff>
    <staff n="2"><layer n="1"><beam><note xml:id="bb" dur="32" pname="b" oct="2" accid="f" stem.dir="up"/><note xml:id="e" dur="32" pname="e" oct="3" staff="1" stem.dir="down"/><note xml:id="bn" dur="32" pname="b" oct="1" stem.dir="up"/></beam></layer></staff>
  </measure>
  ```

### 2b. `@vgrp` does not line up a `tempo` with `dir`s

- **Status:** known upstream; nothing to file. Verovio ignores `@vgrp` on `tempo` altogether, even between two `tempo`s: its `Tempo` class has no vertical-group attribute, and `@vgrp` is aligned only within {`dynam`, `hairpin`}, {`dir`}, {`pedal`}, {`harm`} and {`ending`}. Covered by the open issue [#1151](https://github.com/rism-digital/verovio/issues/1151) and the draft [PR #4407](https://github.com/rism-digital/verovio/pull/4407).
- **Edition workaround:** the return "tempo" in movement I is a `dir` with the same `@vgrp` as the "rit."s (for example `ue1937-I-dir-tempo-L110F2`), which lines up in 6.3.0.

### 2c. `@stem.len` is ignored on `beamSpan` notes

- **Status:** confirmed on 6.3.0 and `develop`. Already filed as [#932](https://github.com/rism-digital/verovio/issues/932), "@stem.len for notes/chords in beams" (open since 2018, no comments). To add as a comment there.
- **Where:** movement II, bars 12–13 (`ue1937-II-beamSpan-L108F1-L111F2`): G6 on the lower staff (treble clef) beamed to B2 on the upper staff (bass clef), both stems down, one beam below. In the print the G6 has a long stem and the beam runs through the lower staff. Verovio sets the beam the standard distance below the G6, above the lower staff.
- **What happens:** with `stem.len="2"`, `"12"` or no `@stem.len` on both notes, the beam polygon is identical. Without the `beamSpan`, `stem.len="12"` lengthens the stem as expected. `BeamSegment::CalcBeamStemLength` and `BeamElementCoord::CalculateStemLength` in `src/beam.cpp` take a beamed stem's length from the note's position and duration only.
- **Effect here:** the encoding (stem directions, `@place="below"`) is right; only the beam's height differs from the print. The MEI records no stem length.

### 2d. Grace-note slur to a chord member attaches beneath the whole chord

- **Status:** confirmed on 6.3.0 and `develop`. Already reported as [#4313, Grace note slur attaches to lowest note in chord instead of target note](https://github.com/rism-digital/verovio/issues/4313) (open); its comment of 2026-09-24 shows the same pitched-note, direct-MEI case. Optionally, add this case there as a comment.
- **Where:** movement III, bars 15 and 18. E♮4 grace to G♮4 above G♯3 (bar 15); G♯4 grace to B♭4 above B♮3 (bar 18). The print has short lower curves ending at the upper chord notes, separate from the longer cross-staff slurs.
- **What happens:** with `endid` on the upper note and `curvedir="below"`, both slurs end about 4.5 staff spaces below their target, beneath the lower chord note. In bar 15, removing the longer slur or isolating the measure does not cure it. The same slur to a single note is fine, and `curvedir="above"` ends at the upper note.
- **Encoding:** a rendering limitation, not a missing MEI mechanism. [MEI #367](https://github.com/music-encoding/music-encoding/issues/367#issuecomment-269642627) uses note-specific `@startid`/`@endid` for slurs to chord notes.
- **Edition workaround:** the two slurs use `@curvedir="above"`; the note-specific endpoints remain encoded, and an `encoding-note` at each case records the printed lower curve. Bar 42, a grace slur to a single note, is printed above and is unchanged.
- **Minimal example:** the lower curve should end at G4 inside the chord, not below G♯3.

  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="5.1+CMN">
    <meiHead><fileDesc><titleStmt><title>Grace slur to upper chord note</title></titleStmt><pubStmt/></fileDesc></meiHead>
    <music><body><mdiv><score>
      <scoreDef meter.count="1" meter.unit="4">
        <staffGrp><staffDef n="1" lines="5"><clef shape="G" line="2"/></staffDef></staffGrp>
      </scoreDef>
      <section><measure n="1">
        <staff n="1"><layer n="1">
          <note xml:id="grace" dur="8" pname="e" oct="4" accid="n" grace="unacc" stem.dir="up"/>
          <chord xml:id="chord" dur="4" stem.dir="up">
            <note xml:id="lower" pname="g" oct="3" accid="s"/>
            <note xml:id="upper" pname="g" oct="4" accid="n"/>
          </chord>
        </layer></staff>
        <slur xml:id="graceSlur" staff="1" startid="#grace" endid="#upper" curvedir="below"/>
      </measure></section>
    </score></mdiv></body></music>
  </mei>
  ```

### 2e. `beamSpan` does not avoid rests in its `@plist`

- **Status:** confirmed on 6.3.0 and `develop`. To file. No matching issue (it was first filed here under 2c).
- **Where:** movement III, bars 51–52 (`ue1937-III-beamSpan-L478F2-L482F2`): the beam continues across a system break over the eighth rest `ue1937-III-rest-L481F2` at the start of bar 52. The print keeps the rest in place and draws the beam lower.
- **What happens:** with a `beamSpan`, Verovio leaves the rest at its default position and draws the beam through it, inside one bar, across a barline and across a system break alike. The same notes in a `<beam>` are handled: without an explicit rest position the rest moves clear of the beam, and with `rest/@ploc="b" @oloc="4"` the beam drops below the rest, which is the printed layout. `@stem.len` cannot be used as a workaround (2c). MEI 5.1 does not allow `@vo` on `beamSpan`.
- **Minimal example** (wrapping the three events in `<beam>` instead avoids the rest):

  ```xml
  <?xml version="1.0" encoding="UTF-8"?>
  <mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="5.1">
    <meiHead><fileDesc><titleStmt><title>beamSpan over a rest</title></titleStmt><pubStmt/></fileDesc></meiHead>
    <music><body><mdiv><score>
      <scoreDef meter.count="3" meter.unit="8">
        <staffGrp><staffDef n="1" lines="5" clef.shape="G" clef.line="2"/></staffGrp>
      </scoreDef>
      <section>
        <measure n="1">
          <staff n="1"><layer n="1">
            <note xml:id="e" dur="8" pname="e" oct="5" accid="f" stem.dir="down"/>
            <rest xml:id="r" dur="8"/>
            <note xml:id="d" dur="8" pname="d" oct="6" stem.dir="down"/>
          </layer></staff>
          <beamSpan staff="1" startid="#e" endid="#d" plist="#e #r #d"/>
        </measure>
      </section>
    </score></mdiv></body></music>
  </mei>
  ```

### 3. Page header from `meiHead` omits a composer wrapped in `persName`

- **Status:** confirmed on 6.3.0 and `develop`; a regression since 4.4.0. To file.
- **What happens:** with no encoded `pgHead`, Verovio builds a page header from `fileDesc/titleStmt`. The edition's header gives the titles ("Variations for Piano, Op. 27", "I") but no composer, because the composer is `<composer><persName>Anton Webern</persName></composer>`. `arranger`, `lyricist` and `respStmt/persName[@role]` are never used, and a `title` loses any text inside a `rend`. Verovio 4.3.1 drew `respStmt/persName[@role]`, but also a `persName` without `@role`: it printed the edition's editor where the composer goes.
- **Cause:** [`src/pghead.cpp`](https://github.com/rism-digital/verovio/blob/version-6.3.0/src/pghead.cpp#L89-L106). The XPath `//fileDesc/titleStmt/composer|arranger|lyricist|respStmt/persName[…]` is a union of four paths of which only the first is anchored, so the other three never match (since a3078921b, first released in 4.4.0). The name is read with `node.text()`, which returns only the first direct text child; the node's string value would fix both the `persName` and the `rend` case.
- **Edition workaround:** each movement repeats its printed head in a `pgHead` in the first `scoreDef`.

### Known behaviour, not issues

- Verovio's MEI output is MEI 6.0-dev; it has no MEI 5 writer. Its MEI Basic output drops the facsimile, the header and many IDs. This is why the MEI files are edited as text.
- `beamSpan/@staff="1 2"` makes Verovio draw the beam once per staff, as it does for any control event with several staves. Give the staff of the first note only.
- The Humdrum import copies a layout group name (`!!LO:LB:g=z`) into `sb/@type`. The group name is arbitrary in Humdrum and means nothing in MEI; this edition drops it.
