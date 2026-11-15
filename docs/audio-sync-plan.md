# Recording/score linking: plan

Status: plan, 2026-11-15. Nothing is built yet. This repo is the study; the sync module is meant to move into CAMAT and the DdT 1/11 edition later.

## Decisions

- **Audience: score readers first.** One recording per movement, and the current bar lights up while it plays. The timing format takes more recordings later, for comparing performances.
- **Route: align offline, play YouTube.** The viewer plays Yvonne Loriod's 1961 recording (Véga C 30 A 309) from the label's official YouTube "Topic" uploads, one video per movement. Bar times come from an automatic offline alignment of a local reference copy of the same performance, corrected by ear. The reference copy never goes into the repo or the viewer.
- **Reference copy in `sources/sources.json`: SHA-256 and description only** (decided 2026-11-15). The record `loriod-1961-reference-copy` has no `download_url` and `redistributed: false`; `fetch_sources.py` reports it as `manual` when the file is missing.
- **No audio in the MEI.** Timing data is a separate JSON file, as velocity (`@vel`) is kept out of the MEI for the expression layer.
- A second opinion (Cursor auto, 2026-11-15) picked the same route; its main risk is drift between transfers (see Facts).

## Facts (measured 2026-11-15)

| | I | II | III |
| --- | --- | --- | --- |
| Bars in the MEI | 54 (1–54) | 23 (0–22); 45 played with the repeats | 66 (1–66) |
| Loriod YouTube Topic video | `6vQ5n_rNEDk` | `Dij7ORQwTGg` | `hApUUtoMggM` |
| Onset span, reference copy (−30 dB gate) | ≈ 90.65 s | ≈ 34.22 s | ≈ 175.6 s |
| Onset span, Cook & Sapp transfer | 91.39 s | 34.77 s | 177.55 s |

- **Reference copy:** Internet Archive item `20220513-webern-o-variations-op.-27-yvonne-loriod-pierre-boulez`, one MP3 of all three movements. It runs 317.3 s at 320 kbps, 44.1 kHz stereo, SHA-256 `30a5873008c3af53cd2fb2ec8c45c4e4eebbefc782aa1841e57492cc4ff9a1e8`. Its metadata gives 96.89 s, which is wrong. It is a rip of a Decca reissue ("The Vega Recordings, Vol. 6"), and the item states no licence.
  - Movement breaks: I ends about 90.8 s, II starts 96.95 s, II ends about 131.7 s, III starts 136.07 s. The aligner finds them with ffmpeg `silencedetect` (−30 dB, at least 1.5 s) and cuts at the gap midpoints, 93.86 and 133.86 s. The longest silence inside a movement is 3.0 s (III).
  - Decode with ffmpeg (317.31 s). libsndfile, and so `soundfile` and `librosa.load`, trusts the wrong header and stops at 96.86 s.
  - archive.org serves the file with `Access-Control-Allow-Origin: *` and answers range requests. The viewer does not use this; it only matters for the dev tools below.
- **Legal status** (research report, not re-checked; no legal advice):
  - The report reads Directive 2011/77/EU's 70-year term as applying only to rights still alive on 1 Nov 2013. A 1961 publication's 50-year term ended in 2011, so on that reading the recording is public domain in the EU.
  - A reviewer (Cursor auto, 2026-11-15) read it as protected until about 2031. That is unresolved: the EUR-Lex text could not be fetched. It matters only for the local reference copy, which the plan never redistributes.
  - Protected in the US until about 2067 (Music Modernization Act). §85(1) UrhG gives a rip no new producer's right.
- **YouTube** (2026-11-15): all three Loriod IDs answer oEmbed 200; the channel is "Yvonne Loriod – Topic".
  - From the research report, not re-checked: the API Developer Policies bar downloading or caching (III.E.1.a) and separating or modifying the audio (III.I.7). The player must be at least 200×200 px.
  - The report concludes that tapping bar times by hand over the embed is allowed, but aligning the YouTube audio itself is not.
- **Drift between transfers:** the reference copy's onset spans are 0.8–1.6% shorter than in Cook & Sapp's transfer of the same recording, in all three movements. These are coarse −30 dB gate figures, but the sign is the same each time. A YouTube transfer may differ the same way, so each video needs an offset and a rate correction, not just an offset. Over movement I, a 1% rate error is about 0.9 s, roughly half a bar.
- **Repeats:** Loriod plays both repeats in II. Cook & Sapp's II event list has 122 events with two jumps back, and her sheet has all 122.
- **Viewer:**
  - The bar and note highlight runs on Verovio's expanded score position. `player.js` calls `onPosition(q)`, which goes to `advanceCursor(q)` in `site/viewer.js`, and `advanceCursor` lights notes and the bar box together.
  - The MIDI path is `parseMidi` → `prepare(midi, PARTS)` → `play(prepared, q, percent)` (`site/player.js:413`; `togglePlayback` in `site/viewer.js`).
  - Repeats on uses the `<expansion>`. In Verovio 6.3.0's `renderToTimemap({includeMeasures: true})` for II, the 45 `measureOn` events have 45 distinct ids, and the 22 second-pass bars are `<id>-rend2` (probe 2026-11-15). The viewer currently calls `renderToTimemap()` without `includeMeasures`.
- **Score side** (Verovio 6.3.0, repeats on): 165 played bars (I 54, II 45, III 66). Each movement's MIDI has one tempo (I 30 bpm, II and III 160 bpm), so the rit. and tempo words do not reach it. 57 bars start without a note-on (I 8, II 18, III 31).
- **Aligner probe** (build session 1, `scripts/align_recording.py`; outputs git-ignored in `validation/runs/audio-sync-2026-11-15/`): 165 anchors. Variant B wins every movement by the note-on proxy. Over downbeats that are real attacks, the anchor lies within 100 ms of a detected recording onset in I 86% (38/44), II 96% (26/27) and III 88% (23/26); a linear spread gets 39 / 56 / 20% of sounding downbeats. 68 bars (57 rests, 11 tied downbeats) are timed by interpolation, which no proxy checks. In movement I the reference copy starts on the first note, so bar 1 would begin at −0.32 s; its anchor is clipped to 0.
- **Tools:** ffmpeg and fluidsynth are installed. There is no SoundFont on the system (no `.sf2` or `.sf3` file). The aligner's venv `.venv/` (git-ignored; pins in `scripts/requirements-align.txt`) has Python 3.13, synctoolbox 1.4.2, librosa 0.11.0 and verovio 6.3.0. partitura 1.9.0 is in the camat_v2 venv.
- **Cook & Sapp data:** onset times for 62–63 recordings per movement (Loriod: 177, 122 and 256 events). No licence is stated. It is not used here. Asking permission is a later, researcher-facing step.

## Design

### Timing file

`site/recordings/loriod-1961.json`, one file per recording:

```json
{
  "recording": {"performer": "Yvonne Loriod", "year": 1961, "label": "Véga C 30 A 309"},
  "reference": {"note": "local reference copy; see docs/audio-sync-plan.md", "sha256": "30a58730…", "movements": {"I": [0.0, 93.8], "II": [93.8, 133.9], "III": [133.9, 317.3]}},
  "movements": {
    "II": {
      "anchors": [{"measure": "<xml:id>", "pass": 1, "t": 0.412, "how": "dtw|tapped|corrected"}],
      "sources": [{"type": "youtube", "id": "Dij7ORQwTGg", "offset": 0.0, "rate": 1.0, "fit": {"n": 8, "maxResidual": 0.0}}]
    }
  }
}
```

- `reference.movements` gives each movement's segment of the reference copy in file seconds, cut in the middle of the gap, so each segment includes some silence. `t` counts from the segment start, silence included, not from the first onset. The aligner reads exactly that segment.
- Anchors are keyed by MEI `xml:id` and repeat pass, not by Verovio qstamps, so they survive a re-render. At load the viewer resolves them in `renderToTimemap({includeMeasures: true})` with repeats on: pass 1 matches the `measureOn` event with the bare id, and pass N ≥ 2 matches `<id>-rendN`. An anchor with no match is rejected and reported.
- Each source maps reference time to its own media time: `media = offset + rate × t`. The fit is least squares over hand-tapped anchors, and the file records how many anchors it used and the worst residual.
- More recordings means more files. A source of type `audio` (an `<audio>` URL or a local file) serves CAMAT and the dev tools.

### Sync module (`site/recording-sync.js`, host-neutral like `player.js`)

- Exposes a playback façade: `load(movement)`, `playFrom(q)`, `pause() → q` and `stop(q)`, with the callbacks `onBar(measureId, pass)` and `onEnd`. It is not a drop-in for the MIDI engine, whose path is `parseMidi` → `prepare` → `play(prepared, q, percent)`, so `togglePlayback` branches on the source.
- Maps between media time and the reference timeline with the source's `offset` and `rate`. It maps the reference timeline to and from `q` by monotone piecewise-linear interpolation between anchors, using binary search.
- Has two adapters behind one small interface (`load`, `play`, `pause`, `seek`, `currentTime`, `onState`): the YouTube IFrame API, and `HTMLMediaElement`. The `HTMLMediaElement` adapter is for tests, dev tools and CAMAT.
- Polls `currentTime` every animation frame while playing. Seeking to a pinned bar uses the bar's first pass.

### Viewer changes (`site/viewer.js`, `index.html`)

- A source choice in the player: MIDI, or "Recording: Loriod 1961".
- Recording mode:
  - Nothing loads from YouTube until the reader clicks: a two-click consent with a privacy note. Use the `youtube-nocookie.com` host.
  - The video sits in a panel of at least 200×200 px.
  - Repeats are forced on and the tempo control is disabled, because the recording plays as performed.
  - A credit line names the recording and says it plays via YouTube.
- v1 lights bar boxes only, through a bar-only cursor fed by `onBar`.
  - The cursor sets `playback.measure`, leaves `playback.active` empty and skips the note path of `applyPlaying`.
  - It does not call `advanceCursor(q)`, which would light notes from interpolated `q` and misplace them inside rubato bars.
  - Add note lighting only if note-level anchors pass the accuracy bar below.
- Recording-mode contract (each item is a branch in `viewer.js`):
  - Tempo: `updateTempo`/`setTempo` do nothing, and the tempo control is disabled.
  - Audio: no `AudioContext`, no samples and no `cachePlayback` MIDI render. The IFrame player is created on the consent click.
  - Pause and resume: pause keeps the bar box lit and the position, and resume continues from the media time, not from `q`.
  - Page following: `onBar` drives it, through the same `showPage` and `preRenderNextPage` calls.
  - Movement switch: `stopPlayback(true)` also stops the video and cues the new movement's video.
  - Repeats: forced on, and the Repeats toggle is hidden.

### Offline aligner (`scripts/align_recording.py`)

- Runs in a separate venv, not the edition's.
- Reads the reference copy and the MEI. The score side is Verovio MIDI with repeats expanded, plus the time map.
- Features:
  - Chroma plus onset features on both sides. Synchronisation toolbox style: multi-resolution DTW with chroma and onset features.
  - Score-side features come straight from the MIDI note list, since no SoundFont is installed. The fallback is synthesising with the viewer's piano samples.
  - The build runs both. Each movement keeps the variant with the larger share of MIDI note-ons within 50 ms of a detected recording onset (librosa), with one parameter set for all three.
  - Bar times are interpolated between aligned note onsets, so bars that start in a rest follow the performed tempo. The opening rest is extrapolated back from the first onsets at the local rate.
- Output: a bar anchor for every played bar (about 165), with `how: "dtw"`. It also writes a click-track WAV (reference audio plus a click at each anchor) for the listening check.
- Writes outputs to `validation/runs/` (git-ignored). Only the corrected JSON enters `site/recordings/`.

### Dev tools (not deployed)

- **Tap/correct page:** plays a local file or the YouTube embed. A key press records a bar start, at speed 1× or 0.5× with pitch kept. It loads an existing anchor set and lets you nudge or re-tap single bars, then exports JSON.
- The page serves both jobs: the ground-truth pass on the reference copy, and the 5–10 calibration anchors per YouTube video. CAMAT can reuse it for manual annotation.

## Accuracy targets (to confirm at the probe)

- **Aligner against hand taps** on the reference copy, all played bars: report the median and 95th-percentile absolute error, and the share within 100 ms. Proposal: the aligner is "good enough to need only spot corrections" if 90% of bars fall within 100 ms. Otherwise the hand taps become the published anchors (`how: "tapped"`).
- **YouTube fit:** worst residual 80 ms or less over 5–10 anchors per movement. Above that, add anchors and fit piecewise.

## Build sessions (one deliverable each)

1. **Aligner probe** (done 2026-11-15, see Facts). Set up the venv, write the fetch step for the reference copy (checked against the SHA-256), segment it, run the DTW and write the click track. Deliverable: bar anchors for all three movements and a short report. Hand off after the report. (Delegable: the script from this spec.)
2. **Tap/correct page plus ground truth.** You tap the reference copy (about 165 bars, roughly 30–45 minutes). Then score the aligner and correct the anchors. Deliverable: the corrected `loriod-1961.json` without sources, and the accuracy numbers.
3. **Viewer integration.** `recording-sync.js`, the YouTube adapter, the source switch, click-to-load and the calibration mode. You tap 5–10 anchors per video, then the offset and rate are fitted. Deliverable: recording mode working locally. (Delegable: the module and adapters.)
4. **Tests, docs, release.**
   - `check_site.py` (Playwright, real page): add a recording-mode scenario. It uses an `audio` source pointing at a generated silent WAV served with the test site, so no YouTube runs in tests, seeks to anchor times, and checks the lit bar box.
   - A data check, which can live in `validate.py`, confirms that every anchor resolves to a `measureOn` id and that times increase within each movement.
   - README and LICENSE.md: recording credit and the timing-data licence.
   - Cross-vendor review, then deploy with your OK.

## First probes in the build (cheap, before relying on them)

- IFrame API: how often `getCurrentTime()` updates during playback, and what it reports during a pre-roll ad.
- Whether the Topic transfer matches the reference copy (the calibration fit shows it: rate ≈ 1.000 means same transfer).
- Whether DTW holds through Webern's long rests and sparse texture, especially II at "Sehr schnell". Answered by the probe (2026-11-15): yes by the proxies, and II is the best movement (see Facts).

## Open decisions (each a picker in its session)

- The licence for the timing data: CC BY 4.0 like the encoding, or CC0.
- Whether to ask Nicholas Cook and Craig Sapp for permission to use their onset data (researcher phase).
