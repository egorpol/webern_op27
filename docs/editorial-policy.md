# Editorial policy

This edition encodes Anton Webern's Variations for Piano, Op. 27, as printed by Universal Edition, plate U.E. 10881 (first edition 1937). It records what the print shows. Every printed sign belongs to the musical text, including stems, beams and the placement of marks. The edition does not correct the print: a suspected engraving error stays in the encoding and is annotated.

The policy was set on 2026-10-11, before proofreading began. It does not claim that the current files already meet it; the README status table records how far each movement has been checked.

## Sources and their roles

**Base source (`src.ue1937`).** The only source of readings is the copy reproduced in IMSLP file 28271 (scan uploaded by JacopoTore; scanner unknown; PDF SHA-256 in `sources/sources.json`). Its music pages are printed pages 3–11. The page footer reads "Copyright 1937 by Universal Edition / Copyright renewed 1965 / Universal Edition Nr. 10881". This copy is therefore a reprint from the 1937 plates issued in 1965 or later. A first-issue copy from 1937 has not been seen, so plate corrections made between 1937 and this printing cannot be ruled out. The prefix `ue1937` in IDs names the edition (the plate), not the printing date of this copy. Describe the source in the MEI header as this copy of that edition, not as a 1937 print.

**Base encoding (`src.kern.sapp`).** Craig Stuart Sapp's KernScores files `webern-op27n1–3.krn` (encoded 2008, revised 2020-11-23) supplied the notes and rhythms. They were converted with Verovio and are being enriched and corrected from the print. They are a starting point, not a witness: a Kern reading has no authority where it differs from the print. Their own header notes record known gaps: movement I has no beams, dynamics, slurs or articulations; movement II is "not finished"; movement III lacks its tempo changes.

**Cross-check encodings.** Other encodings may be compared to find places to look at again: Maja Hartwig's MEI of movement II, pickup and bars 1–11 (MEI Sample Collection, 2011), and Wendy Czajkowsky's Kern of movement III (1995). A difference between them and this edition is a prompt to re-read the print, never evidence for a reading. Record each one in `sources/sources.json` when it is used.

**Not used.** Do not copy from MuseScore score 4917023 or from the DCMLab `WebernNo1.mxl` export of it; neither is licensed for reuse. Peter Stadlen's performing edition (UE, 1979) and Webern's manuscripts are not sources of this edition. Readings from them must not enter the encoding.

## What is encoded

Encode everything the print shows in the music: notes, rests, accidentals, durations, grace notes, staff assignment and cross-staff writing, clefs, stems and beams, ties, slurs, articulations, dynamics, hairpins, tempo and metronome marks, other performance text, fermatas and caesuras, repeat signs, meter, printed bar numbers, and page and system breaks. Encode marks where the print places them: staff, side of the staff (`@place`), attached note, and extent.

The page paratext belongs in the MEI header, not the musical text: page numbers, the title "VARIATIONEN", movement numerals, "Anton Webern, Op. 27", the copyright lines and the plate number. Specks and other scan artifacts are not encoded.

## Correction categories

1. **Encoding repair.** The encoding is brought into agreement with the print, whatever caused the difference (Kern, conversion, or an earlier hand edit). Record it in the proofreading log and the commit message; it needs no annotation.
2. **Retained source reading** (`label="source-reading"`). The print is kept, although it looks wrong: a pitch that contradicts the row, a missing accidental, an inconsistent duration. Annotate the printed reading, the reading that seems intended, and the reasoning. An argument from the row may motivate the note but does not change the encoding.
3. **Encoding note** (`label="encoding-note"`). The reading is certain, but its representation needs explaining or has a known renderer limitation. Example: a cross-staff `beamSpan` with opposite stem directions, which Verovio 6.3 draws with a secondary beam missing.
4. **Unresolved reading** (`label="unresolved-reading"`). The print cannot be read with confidence: a broken or blurred sign, or an accidental that is hard to make out. Encode the likeliest reading, annotate the alternatives and the zone, and mark the uncertainty. Release review must address each one.

There is no emendation category. Moving to emendations, or to `choice/sic/corr`, needs an explicit policy change recorded here.

## Recording decisions in MEI

Give each category 2–4 case one `annot` in the movement's MEI:

- `type="editorial"` and one of the labels above (CAMAT conventions, not MEI values);
- `plist` pointing to the affected event IDs, and `@facs` or a `ref` to the measure zone when the image matters;
- `resp` pointing to a `respStmt` declaration in the header;
- text that states the printed reading and, for categories 2 and 4, the alternatives and the reasons.

```xml
<annot xml:id="ue1937-III-annot-example" type="editorial"
       label="source-reading" plist="#ue1937-III-note-EXAMPLE"
       resp="#resp.editor" source="#src.ue1937">
   <p>Illustration only. UE 1937 prints B♭4; the row form in this bar
      would require B♮4. The printed reading is retained.</p>
</annot>
```

Use `annot/@source` only for a source that actually shows the reading in question, which in practice means `#src.ue1937`. A corpus list of annotations can be generated from the files; do not maintain a second hand-written list.

## Rights

The MEI files, documentation and source records are licensed under CC BY 4.0 (see `LICENSE.md`). That licence covers this edition's own contributions, not the musical work or the print. Webern died in 1945, so the work is in the public domain in countries with a term of 70 years after death, including the EU. IMSLP lists this edition as not public domain in the US, and the printed 1965 renewal notice is consistent with that. Users outside the EU should check the status where they are.

The page images and the PDF are not redistributed. They are cited by URL and SHA-256, and anyone can reproduce them from IMSLP (see the README).

## Release review

Before a release, check every annotation against the print and confirm the responsible editors. State the extent of proofreading as it was actually done; list retained readings and unresolved readings in the release notes. An empty validation report does not show that the notes are right; only the comparison with the print does.
