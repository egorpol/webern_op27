# MEI encoding profile

This profile is the technical counterpart to the [editorial policy](editorial-policy.md). It covers how the three movement files are encoded and validated. It is written for editors, maintainers and anyone writing tools for the repository. It describes the target; files reach it during proofreading and the header work.

## Schema

The files use MEI 5.1 with the Common Music Notation customization. The pinned schema is [`schemas/mei-CMN-5.1.rng`](../schemas/mei-CMN-5.1.rng); it embeds the Schematron rules. Publication files declare the release and customization in both places:

```xml
<?xml-model href="https://music-encoding.org/schema/5.1/mei-CMN.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<?xml-model href="https://music-encoding.org/schema/5.1/mei-CMN.rng" type="application/xml" schematypens="http://purl.oclc.org/dsdl/schematron"?>
<mei xmlns="http://www.music-encoding.org/ns/mei" meiversion="5.1+CMN">
```

Verovio 6.3 writes MEI 6.0-dev and has no 5.x writer. Its MEI Basic output drops the facsimile, most of the header and many IDs. The MEI files are therefore the master copy, edited by hand. Verovio is used only for rendering; do not round-trip the files through it.

## Files and identifiers

- One file per movement: `mei/webern-op27-I.mei`, `-II.mei`, `-III.mei`, each with one `mdiv`.
- Every ID in the music of a movement file starts with `ue1937-<mvt>-`: measures are `ue1937-<mvt>-m<NNN>` (the pickup of II is `m000`). Facsimile IDs are `zone-ue1937-<mvt>-m<NNN>`, `surface-ue1937-p<NNNN>` and `graphic-ue1937-p<NNNN>`, numbered by PDF page.
- Keep existing IDs through correction and reformatting; external annotations and CAMAT selections point at them. New elements get an ID with the movement prefix and a readable rest, for example `ue1937-II-beamSpan-L37F1-L40F2`.
- Notes, chords, rests, spaces, measures, staves, layers and all control events (`slur`, `tie`, `beamSpan`, `dynam`, `hairpin`, `dir`, `tempo`, `fermata`, `annot`) must have an ID.
- Header IDs are the same in every file, so that annotations can use them unchanged: `resp.editor`, `src.ue1937`, `src.kern.sapp`, `work.op27`, and `work.op27.<mvt>` for the movement.
- References are local (`#id`) and must resolve in the same file.

## Header

The header follows the [MEI metadata guidelines](https://music-encoding.org/guidelines/v5/content/metadata.html) and the DdT edition's model. In short:

| Section | Content |
| --- | --- |
| `fileDesc/titleStmt` | Work and movement title, composer, `respStmt` for the digital edition (IDs such as `resp.editor`) |
| `fileDesc/editionStmt` | Edition statement and version, `0.x` until the first release |
| `fileDesc/pubStmt` | Publisher, date, URI and `availability` with the CC BY 4.0 licence for the MEI data |
| `fileDesc/sourceDesc` | `src.ue1937`: the copy actually used (IMSLP 28271, a reprint from 1965 or later of U.E. 10881), printed page range, transcribed paratext, image rights. `src.kern.sapp`: the base encoding, with URL, version and SHA-256 |
| `encodingDesc` | `appInfo` (Verovio Humdrum import, the scripts used), `editorialDecl` summarising the editorial policy |
| `workList/work` | `work.op27`: Webern, Variations for Piano, Op. 27; the movement as `work.op27.<mvt>` in its `componentList`, with meter and tempo heading. `mdiv/@decls` points to the movement |
| `revisionDesc` | Significant events, newest first, each `change/@resp` pointing to a `respStmt` |

`sourceDesc` transcribes the page paratext of the movement's pages (page numbers, title, movement numeral, composer line, copyright lines, plate number, printer). `encodingDesc/projectDesc` names the DFG grant (PF 669/18-1) that funds the CAMAT corpus. `appInfo` also lists Claude Code, the AI assistant used under the editor's direction; responsibility stays with `resp.editor`. Add a `revisionDesc/change` for every significant change to a file, such as a proofreading pass over a page, newest first.

## Score structure

- `measure/@n` is the printed bar number. UE numbers every bar.
- The pickup that opens movement II is bar 0 with `metcon="false"`.
- Repeats are encoded as printed with `@left="rptstart"` and `@right="rptend"`. Movement II's sections are `section` elements with one `expansion` giving the printed repeat order (I A A B B); CAMAT skips `expansion` when it flattens sections.
- A staff with no printed content in a bar holds an `mSpace` (not an invisible rest).
- Meter signatures and clefs go where they are printed, including mid-bar clefs (`clef` inside the layer).
- The `pgHead` of the first `scoreDef` repeats the printed head of the movement's first page for display: "VARIATIONEN", "I" and "Anton Webern, Op. 27" in movement I; only the numeral in II and III. Verovio 6.3 shows no heading without it. The header's `sourceDesc` holds the transcription of all paratext.

## Notation conventions

**Accidentals.** Webern's print gives an accidental to almost every note, naturals included. Every printed accidental is encoded as a written accidental: `note/@accid` or an `accid` child with `@accid`. A note that sounds altered without a printed sign, such as the second note of a tie, carries `@accid.ges` instead. The `func="caution"` and `type="caution"` values left by the Kern conversion carry no editorial claim. Leave them as they are; do not add new ones.

**Staff and cross-staff.** A note or chord printed on the other staff carries `@staff` with that staff's number, inside the layer it belongs to.

**Stems and beams.** Every note and chord carries the printed `@stem.dir`. Beams within one bar and one layer are `beam` elements. A beam that crosses a barline or joins layers is a `beamSpan` placed in the bar where it starts, with `@staff`, `@plist`, `@startid` and `@endid`. Secondary-beam breaks use `@breaksec`. Verovio 6.3 draws `beamSpan`, but with opposite stem directions it drops a secondary beam before the first stem change (`docs/upstream-issues.md`, 2a). That is a rendering fault, not one in the file.

**Ties and slurs.** Use `tie` and `slur` elements with `@startid` and `@endid`, and `@curvedir` where the print's direction should be fixed.

**Articulations.** Use `artic` children of the note or chord (`stacc`, `ten`, `acc`, `marc`, …) with `@place` when the print puts them against the default side.

**Dynamics, hairpins and text.** Attach control events to the note they are printed with by `@startid` (and `@endid` for extents). Use `@tstamp`/`@tstamp2` only when no note is printed at that point. Always give `@staff` and the printed `@place` (`above`, `below`, `between`). `dynam` holds the printed letters. `hairpin` carries `@form` `cres` or `dim`. A dynamic or hairpin printed between the staves for a figure that spans both, or for both hands, is `place="between"` with `staff="1 2"`. Verovio centres such a dynamic between the staves at its note, where a cross-staff beam often runs; where the print sets it beside the stem or beam instead, `@ho` (negative: left of the stem) or `@vo` (negative: below the beam) moves it there, in half staff spaces. A hairpin that leads into a dynamic ends on that dynamic's anchor (`hairpin/@endid` equals `dynam/@startid`) and has the same `@staff` and `@place`; Verovio then stops the hairpin just before the dynamic. Performance text that is not tempo, such as "dim.", is a `dir`; dashed continuation lines use `@extender`, `@lform` and `@lsegs`. `@lsegs` is the number of printed dashes, counted across a system break; Verovio 6.3 ignores it.

**Tempo.** `tempo` holds the printed text and the metronome mark, and also carries it machine-readably: `@mm`, `@mm.unit` and `@mm.dots`. For example, "Sehr mäßig ♪. = ca 40" gets `mm="40" mm.unit="8" mm.dots="1"`. "rit." and the return "tempo" in movement I are both `dir`s, "rit." with an extender. The print sets them on one line per system, so all of them carry the same `@vgrp` (`1`). Verovio 6.3 lines up `@vgrp` members within a system, but it does not line up a `tempo` with a `dir`. This is why the return "tempo" is a `dir` here, although MEI also allows `tempo` for it.

**Grace notes and fermatas.** Use `@grace` and `@stem.mod` for grace notes as printed, and `fermata` control events with `@startid`.

## Facsimile and layout

- One `facsimile` per file, with one `surface` per printed page the movement occupies. `surface/@n` is the printed page number; `graphic/@target` is the relative path `../facsimiles/ue1937/page-<NNNN>.png`, with pixel `@width` and `@height`.
- Every measure points to exactly one `zone` on its page through `measure/@facs`.
- `pb` stands before the first bar of each printed page, with `@n` set to the printed page number and `@facs` pointing to the surface. `sb` stands before the first bar of every other system. `facsimiles/ue1937/pages.json` lists the bars on each system.
- Movement I was edited by hand in this form; `scripts/set_breaks.py` writes the breaks of II and III from `pages.json` and leaves I unchanged. A break stands in the section of the bar it precedes, before a `scoreDef` that directly precedes that bar.

## Validation

The validation gate is CAMAT's general validator (`camat-validate-mei`, `camat/mei_validation.py`), run on all three files. `scripts/validate.py` runs it with the settings below, in a Python environment with CAMAT and `saxonche`, and writes to `validation/runs/<UTC timestamp>/`:

```sh
python scripts/validate.py
# the same as
python -m camat.mei_validation --output-dir validation/runs/<run> \
  --schema schemas/mei-CMN-5.1.rng --verovio --camat-parse mei/webern-op27-*.mei
```

The script exits with 0 only if the required checks and both consumer checks pass, and it stops before running if `saxonche` is missing.

It must pass the required checks (XML references, RELAX NG, the embedded Schematron, image resources, input hashes), Verovio rendering and the CAMAT parse. Schematron needs CAMAT's `validation` extra (`saxonche`); a run where it is skipped is not a pass. Run outputs go to `validation/runs/`, which is not committed. `run.json` records the tool versions and input hashes.

The RELAX NG pass alone is not enough: on 2026-10-11 it accepted five broken `@startid` references in movement III and a beam with one note in movement II, which the full run caught.

Passing validation does not show that the notation matches the print; the [proofreading checklist](proofreading-checklist.md) covers that.
