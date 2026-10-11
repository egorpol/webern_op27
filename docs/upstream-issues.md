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

### 2. `beamSpan` not drawn (to recheck)

- **Status:** to recheck. Noted with Verovio 6.3 when the cross-staff one-note beam in movement II, bars 2–3, became a `beamSpan`. `develop` has `View::DrawBeamSpan`, so first find out whether this encoding (cross-staff, one note per bar, with `@plist`) is the case that is skipped.

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
