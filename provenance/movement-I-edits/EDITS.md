# Movement I hand edits (backup 2026-10-11)

The two MEIs here are the user's edited copies of `../mei/webern-I-kern-{prepared,facsimile}.mei` (sha256 `e53ae6fd…` prepared, `590c47d7…` facsimile; edited 2026-10-11 01:12). They were compared by `xml:id` against a fresh regeneration of `link_workflow.prepare_scores` + `integrate_scores` (run in a scratch copy, 2026-10-11). The regenerated body digest `722151ed…` equals the one recorded in `../integration.json`, so the pipeline baseline is stable.

The two edited files carry the same changes. The only difference is that the integrator adds `facs`/`n` to `pb`. The full lists are in `diff-*-vs-regenerated.json`; the files were reserialized with a 3-space indent, so a line diff is meaningless.

| Change | Count | Bars |
| --- | --- | --- |
| `stem.dir` set | 57 | 1–18 |
| notes/chords wrapped in `beam` | 15 beams (30 events) | 3, 5, 8–14, 16, 18 |
| `beamSpan` (cross-staff/layer beams) | 13 | 1, 3, 4, 6, 11–17 |
| `slur` | 28 | 1, 3–6, 8–18 |
| `dynam` | 4 | pp 1, f 11, p 15, pp 17 (staff 2, above) |
| `hairpin` dim | 2 | 10, 16 |
| `dir` | 2 | "dim." 13; "rit." 17 with dashed extender to 18 |
| `tempo` | 1 | `place="above"`; trailing space trimmed; empty spacer `rend` added |
| written `accid="s"` | 1 | 4, staff 2, tied g♯4 (kern `[16g#`; sounding pitch unchanged, the Verovio import had dropped it without `accid.ges`) |
| `breaksec="1"` | 1 | 5, staff 2 |
| `clef` added | 58 | 3–51 (whole movement) |
| `clef` removed | 2 | kern clefs in 19 (G) and 21 (F), staff 2 |
| initial clef staff 2 | 1 | G2 → F4 |
| `keySig sig="0"` | 2 | both staves, in `scoreDef` |
| `pb` / `sb` | 3 / 11 | UE page and system breaks (before 1, 19, 34) |
| `spacing.staff="14"` | 1 | `scoreDef`, layout only |

Summary: page 1 of the UE print (printed p. 3, bars 1–18) is enriched with stems, beams, slurs, dynamics, hairpins and text directives. Clefs, page/system breaks and key signatures cover the whole movement. No pitches, durations or measure structure changed.

Provenance note: the edited `projectDesc` says the clefs/keySig were "aligned to the UE print via the DCMLab reference". DCMLab `WebernNo1.mxl` is an export of MuseScore score 4917023, which was rejected as a base (license not PD), and `sources.json` records no license for it. For the edition, check each clef change against the UE scan and cite UE as the authority (proofreading layer: staff/cross-staff/clefs).

Checked 2026-10-13: the editor compared every clef in movement I with the UE scan; all match the print.
