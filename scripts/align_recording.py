#!/usr/bin/env python3
"""Probe offline bar alignment for Loriod's 1961 Webern Op. 27 recording.

Use Verovio 6.3.0's expanded MIDI and measure time map, and compare symbolic
MIDI features (A) with the viewer's piano samples rendered to audio (B).
Both use synctoolbox chroma + DLNCO multi-resolution DTW. Bar lines are
interpolated between aligned *note onsets*, including bars beginning in rests.
The opening rest is extrapolated at the local performed rate.

Run with the separate alignment venv, Python -I, and no network:
    NUMBA_CACHE_DIR=validation/runs/.numba-cache MPLCONFIGDIR=validation/runs/.mpl \
        /path/to/venv/bin/python -I scripts/align_recording.py --self-test
    /path/to/venv/bin/python -I scripts/align_recording.py \
        --reference sources/recordings/loriod-1961.mp3 \
        --out validation/runs/audio-sync-2026-11-15

The synthetic test saves a fingerprinted result under validation/runs/ for the
real-data report. If missing or stale, the real run performs the test itself.
No audio or timing output is intended for publication before listening checks.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

STARTED = time.perf_counter()
REPO = Path(__file__).resolve().parents[1]
RUNS = REPO / "validation" / "runs"
# Set these before importing numba/matplotlib, including when invoked without env.
os.environ.setdefault("NUMBA_CACHE_DIR", str(RUNS / ".numba-cache"))
os.environ.setdefault("MPLCONFIGDIR", str(RUNS / ".mpl"))
Path(os.environ["NUMBA_CACHE_DIR"]).mkdir(parents=True, exist_ok=True)
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import librosa
import mido
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
import soundfile as sf
import verovio
from synctoolbox.dtw.mrmsdtw import sync_via_mrmsdtw
from synctoolbox.feature.chroma import pitch_to_chroma
from synctoolbox.feature.csv_tools import df_to_pitch_features, df_to_pitch_onset_features
from synctoolbox.feature.dlnco import pitch_onset_features_to_DLNCO
from synctoolbox.feature.pitch import audio_to_pitch_features
from synctoolbox.feature.pitch_onset import audio_to_pitch_onset_features

MOVEMENTS = ("I", "II", "III")
COUNTS = {"I": 54, "II": 45, "III": 66}
BASELINE = {"I": 0.39, "II": 0.56, "III": 0.20}
REFERENCE_SHA256 = "30a5873008c3af53cd2fb2ec8c45c4e4eebbefc782aa1841e57492cc4ff9a1e8"
SAMPLE_SRI = "Oe49rvfDnHMSSNlo8V6a4XyotASwNvpbHFgo0IOcyk8OFIXv8byikUYK2I3ONEfa"
SR = 22050
WAV_SR = 44100
RATE = 50
PACKAGES = ("synctoolbox", "librosa", "numba", "numpy", "scipy", "soundfile",
            "mido", "pandas", "verovio")
PARAMETERS = {"feature_rate_hz": RATE, "chroma_log_gamma": 100,
              "dtw_alpha": 0.5, "threshold_rec": 10000,
              "endpoint_padding_s": 0.3, "proxy_radius_s": 0.05,
              "pitch_peak_coincidence_s": 0.03,
              "long_interval_factor": 2.0, "attack_support_s": 0.06,
              "silence_db": -30, "silence_min_s": 1.5,
              "librosa_onset_hop": 512, "opening_rate_intervals": 6}


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def log(message: str) -> None:
    print(message, flush=True)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n")


def versions() -> dict:
    result = {name: importlib.metadata.version(name) for name in PACKAGES}
    if result["verovio"] != "6.3.0":
        raise ValueError(f"Verovio must be 6.3.0, found {result['verovio']}")
    result["python"] = sys.version.split()[0]
    result["ffmpeg"] = subprocess.check_output(
        ["ffmpeg", "-version"], text=True).splitlines()[0]
    result["libsndfile"] = sf.__libsndfile_version__
    return result


def load_scores() -> dict:
    scores = {}
    for movement in MOVEMENTS:
        path = REPO / "mei" / f"webern-op27-{movement}.mei"
        toolkit = verovio.toolkit()
        if toolkit.getVersion().split("-")[0] != "6.3.0":
            raise ValueError("Verovio toolkit does not match 6.3.0")
        toolkit.setOptions({"expandNever": False})
        if not toolkit.loadFile(str(path)):
            raise ValueError(f"Cannot load {path}")
        timemap = toolkit.renderToTimemap({"includeMeasures": True})
        labels = {node.get("{http://www.w3.org/XML/1998/namespace}id"): node.get("n")
                  for node in ET.parse(path).iter("{http://www.music-encoding.org/ns/mei}measure")}
        bars = []
        for event in timemap:
            if "measureOn" not in event:
                continue
            match = re.fullmatch(r"(.+?)(?:-rend(\d+))?", event["measureOn"])
            measure, repeat = match.groups()
            bars.append({"measure": measure, "pass": int(repeat or 1),
                         "label": labels[measure] + (f" ({repeat})" if repeat else ""),
                         "score_t": event["tstamp"] / 1000,
                         "downbeat_sounds": bool(event.get("on"))})
        midi = mido.MidiFile(file=io.BytesIO(base64.b64decode(toolkit.renderToMIDI())))
        now, active, notes = 0.0, {}, []
        for message in midi:
            now += message.time
            if message.type not in ("note_on", "note_off"):
                continue
            key = (message.channel, message.note)
            if message.type == "note_on" and message.velocity:
                active.setdefault(key, []).append((now, message.velocity))
            elif active.get(key):
                start, velocity = active[key].pop(0)
                notes.append([start, now - start, message.note, velocity, "piano"])
        if active and any(active.values()):
            raise ValueError(f"Unreleased MIDI notes in {movement}")
        df = pd.DataFrame(notes, columns=["start", "duration", "pitch", "velocity", "instrument"])
        df = df.sort_values(["start", "pitch"]).reset_index(drop=True)
        # MIDI floating point sums differ by ulps; the timemap itself rounds to ms.
        df["start"] = df["start"].round(7)
        onset_times = np.unique(df.start.to_numpy())
        for bar in bars:
            bar["downbeat_attack"] = bool(np.min(abs(onset_times - bar["score_t"])) < 0.001)
        if len(bars) != COUNTS[movement]:
            raise ValueError(f"{movement}: expected {COUNTS[movement]} bars, got {len(bars)}")
        scores[movement] = {"bars": bars, "notes": df, "onsets": onset_times,
                            "end": timemap[-1]["tstamp"] / 1000, "sha256": sha256(path)}
        log(f"{movement}: {len(bars)} played bars, {len(df)} notes, "
            f"{sum(not b['downbeat_sounds'] for b in bars)} silent downbeats")
    return scores


def load_samples(path: Path) -> dict:
    data = path.read_bytes()
    if base64.b64encode(hashlib.sha384(data).digest()).decode() != SAMPLE_SRI:
        raise ValueError("Piano sample SRI differs from site/viewer.js")
    # Parse only quoted key/data pairs, never execute downloaded JavaScript.
    match = re.search(r"MIDI\.Soundfont\.acoustic_grand_piano\s*=\s*\{(.*?)\}\s*;?\s*$",
                      data.decode(), re.S)
    if not match:
        raise ValueError("Unrecognised piano sample object")
    pattern = r'"([A-G](?:b|#)?[0-8])"\s*:\s*"data:audio/mp3;base64,([A-Za-z0-9+/=]+)"\s*,?'
    pairs = re.findall(pattern, match[1])
    if re.sub(pattern, "", match[1]).strip() or len(pairs) != 88:
        raise ValueError("Expected exactly 88 piano samples")
    samples = {}
    for key, encoded in pairs:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", "pipe:0", "-ac", "1",
                              "-ar", str(SR), "-f", "f32le", "pipe:1"],
                             input=base64.b64decode(encoded, validate=True),
                             capture_output=True, check=True).stdout
        samples[librosa.note_to_midi(key)] = np.frombuffer(raw, dtype="<f4").copy()
    if set(samples) != set(range(21, 109)):
        raise ValueError("Piano keys are not A0–C8")
    return samples


def render(score: dict, samples: dict, warp=None) -> np.ndarray:
    """Mix original-pitch samples with note velocity and a 10 ms release."""
    if warp is None:
        warp = lambda t: np.asarray(t)
    audio = np.zeros(int(np.ceil((float(warp(score["end"])) + 3) * SR)))
    for note in score["notes"].itertuples():
        start = float(warp(note.start))
        duration = float(warp(note.start + note.duration)) - start
        sample = samples[note.pitch]
        count = min(len(sample), max(1, round((duration + 0.01) * SR)))
        voice = sample[:count].astype(float) * note.velocity / 127
        release = min(count, round(0.01 * SR))
        voice[-release:] *= np.linspace(1, 0, release)
        first = round(start * SR)
        audio[first:first + count] += voice
    peak = np.max(abs(audio))
    return audio / max(1, peak / 0.9)


def make_features(score=None, audio=None) -> dict:
    if audio is None:
        df = score["notes"].copy()
        pitch = df_to_pitch_features(df, feature_rate=RATE)
        peaks = df_to_pitch_onset_features(df)
        # csv_tools pads to 1000 peaks; discard the zero-magnitude padding.
        peaks = {p: values[:, values[1] > 0] for p, values in peaks.items()}
        tuning = 0
        detected = score["onsets"]
    else:
        tuning = int(round(100 * librosa.estimate_tuning(y=audio, sr=SR)))
        detected = librosa.onset.onset_detect(y=audio, sr=SR, hop_length=512, units="time")
        with contextlib.redirect_stdout(io.StringIO()):
            pitch = audio_to_pitch_features(audio, Fs=SR, feature_rate=RATE, tuning_offset=tuning)
            peaks = audio_to_pitch_onset_features(audio, Fs=SR, tuning_offset=tuning)
    # Discard out-of-range onset estimates at the audio edges before DLNCO.
    peaks = {p: values[:, (values[0] >= 0) & (values[0] * RATE / 1000 < pitch.shape[1] - 0.5)]
             for p, values in peaks.items()}
    chroma = pitch_to_chroma(np.log1p(PARAMETERS["chroma_log_gamma"] * pitch))
    dlnco = pitch_onset_features_to_DLNCO(peaks, pitch.shape[1], feature_rate=RATE)
    return {"chroma": chroma, "dlnco": dlnco, "peaks": peaks,
            "tuning_cents": tuning, "detected_onsets": detected}


def nearest_distance(times: np.ndarray, onsets: np.ndarray) -> np.ndarray:
    if not len(onsets):
        raise ValueError("No detected audio onsets")
    idx = np.searchsorted(onsets, times)
    return np.minimum(abs(times - onsets[np.maximum(0, idx - 1)]),
                      abs(times - onsets[np.minimum(len(onsets) - 1, idx)]))


def monotone(times: np.ndarray) -> np.ndarray:
    """Remove DTW plateaus with sub-frame separation; report these repairs."""
    result = times.copy()
    for index in range(1, len(result)):
        result[index] = max(result[index], result[index - 1] + 0.002)
    return result


def refine_attacks(score: dict, mapped: np.ndarray, target: dict) -> tuple[np.ndarray, np.ndarray]:
    """Resolve a sustained DLNCO tail versus a new attack, using exact pitches.

    Search between neighboring DTW note correspondences. A long pause can
    otherwise leave the score attack on the preceding note's decaying chroma.
    This uses filterbank pitch peaks, not the independent proxy onset detector.
    """
    result = mapped.copy()
    radius = PARAMETERS["pitch_peak_coincidence_s"]
    score_onsets = score["onsets"]
    interval_ratios = np.diff(mapped) / np.diff(score_onsets)
    for i, onset in enumerate(score["onsets"]):
        if i == 0 or i + 1 == len(mapped):
            continue
        local_rate = np.median(interval_ratios[max(0, i - 6):i + 6])
        span_ratio = (mapped[i + 1] - mapped[i - 1]) / (score_onsets[i + 1] - score_onsets[i - 1])
        if span_ratio <= PARAMETERS["long_interval_factor"] * local_rate:
            continue
        lower = mapped[i - 1] + 0.02
        upper = mapped[i + 1] - 0.02
        pitches = score["notes"].loc[abs(score["notes"].start - onset) < 0.00001, "pitch"].unique()
        peaks = [target["peaks"].get(int(p), np.empty((2, 0))) for p in pitches]
        candidates = np.unique(np.concatenate([v[0] / 1000 for v in peaks]))
        candidates = candidates[(candidates > lower) & (candidates < upper)]
        if not len(candidates):
            continue
        strengths = np.zeros(len(candidates))
        for values in peaks:
            for j, candidate in enumerate(candidates):
                close = abs(values[0] / 1000 - candidate) <= radius
                if np.any(close):
                    strengths[j] += np.log1p(10000 * np.max(values[1, close]))
        # Resolve equal evidence by proximity to DTW, rather than sample order.
        strengths -= 0.001 * abs(candidates - mapped[i])
        close = abs(candidates - mapped[i]) <= PARAMETERS["attack_support_s"]
        if np.any(close) and np.max(strengths[close]) >= 0.5 * np.max(strengths):
            continue
        result[i] = candidates[np.argmax(strengths)]
    repaired = monotone(result)
    return repaired, abs(repaired - result) > 0.0001


def align(score: dict, source: dict, target: dict) -> dict:
    # Closed DTW must not pin musical onsets to either segment endpoint. Trim
    # to the active onset span with equal padding (including synthetic padding
    # if the first MIDI note is at zero). No bar time is taken from these ends.
    padding = round(PARAMETERS["endpoint_padding_s"] * RATE)
    source_start = round(score["onsets"][0] * RATE) - padding
    source_end = round(score["onsets"][-1] * RATE) + padding
    target_start = round(target["detected_onsets"][0] * RATE) - padding
    target_end = round(target["detected_onsets"][-1] * RATE) + padding

    def crop(feature, start, end):
        padded = np.pad(feature, ((0, 0), (max(0, -start), max(0, end + 1 - feature.shape[1]))))
        return padded[:, max(0, start):end + 1 + max(0, -start)]

    path = sync_via_mrmsdtw(crop(source["chroma"], source_start, source_end),
                           crop(target["chroma"], target_start, target_end),
                           crop(source["dlnco"], source_start, source_end),
                           crop(target["dlnco"], target_start, target_end), input_feature_rate=RATE,
                           threshold_rec=PARAMETERS["threshold_rec"],
                           alpha=PARAMETERS["dtw_alpha"])
    path += np.array([[source_start], [target_start]])
    # Keep only note-on correspondences. Never interpolate from path (0, 0):
    # the closed DTW endpoint belongs to leading silence, not the first bar.
    onset_times = score["onsets"]
    mapped = []
    for onset in onset_times:
        frame = round(onset * RATE)
        values = path[1, abs(path[0] - frame) <= 1]
        candidates = np.unique(values[(values >= 0) & (values < target["dlnco"].shape[1])]).astype(int)
        pitches = score["notes"].loc[abs(score["notes"].start - onset) < 0.00001, "pitch"].to_numpy()
        expected = np.bincount(pitches % 12, minlength=12).astype(float)
        expected /= np.linalg.norm(expected)
        # Pick the strongest matching attack on this part of the DTW path,
        # rather than the middle of a horizontal run through a pause.
        evidence = expected @ target["dlnco"][:, candidates]
        best = candidates[np.argmax(evidence)]
        mapped.append(float(best) / RATE)
    raw_mapped = np.array(mapped)
    mapped = monotone(raw_mapped)
    note_repairs = abs(mapped - raw_mapped) > 0.0001
    mapped, refinement_repairs = refine_attacks(score, mapped, target)
    note_repairs |= refinement_repairs
    bar_times = np.array([bar["score_t"] for bar in score["bars"]])
    interpolation = interp1d(onset_times, mapped, fill_value="extrapolate")
    bars = interpolation(bar_times)
    # Robust local slope avoids one noisy pair setting the opening-rest tempo.
    n = min(PARAMETERS["opening_rate_intervals"], len(mapped) - 1)
    slope = np.median(np.diff(mapped[:n + 1]) / np.diff(onset_times[:n + 1]))
    before = bar_times < onset_times[0]
    bars[before] = mapped[0] + (bar_times[before] - onset_times[0]) * slope
    original = bars.copy()
    bars = monotone(bars)
    return {"bars": bars, "note_times": mapped, "note_repairs": note_repairs,
            "unclipped_opening_t": float(bars[0]),
            "bar_repairs": abs(original - bars) > 0.0001,
            "end": float(interpolation(score["end"])), "opening_rate": float(slope)}


def onset_proxy(score: dict, alignment: dict, detected: np.ndarray) -> dict:
    # Count every MIDI note, so chords retain the specified note-on weighting.
    note_times = np.interp(score["notes"].start.to_numpy(), score["onsets"], alignment["note_times"])
    distances = nearest_distance(note_times, detected)
    sounds = np.array([bar["downbeat_sounds"] for bar in score["bars"]])
    downbeats = nearest_distance(alignment["bars"][sounds], detected)
    return {"notes": len(distances), "note_within_50ms": float(np.mean(distances <= 0.05)),
            "note_median_ms": float(np.median(distances) * 1000),
            "sounding_bars": int(sum(sounds)),
            "downbeat_within_100ms": float(np.mean(downbeats <= 0.1)),
            "downbeat_median_ms": float(np.median(downbeats) * 1000)}


def fingerprint(scores: dict, samples_path: Path, tools: dict) -> str:
    value = {"script": sha256(Path(__file__)), "scores": {m: s["sha256"] for m, s in scores.items()},
             "samples": sha256(samples_path), "tools": tools, "parameters": PARAMETERS}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def self_test(scores: dict, samples: dict, source_features: dict, key: str) -> dict:
    started = time.perf_counter()
    results = {}
    for movement, score in scores.items():
        # Choose the sounding bar nearest the middle, so the pause has an
        # observable end. There is no test-truth input to the aligner.
        pause_bar = min((b for b in score["bars"] if b["downbeat_attack"]),
                        key=lambda b: abs(b["score_t"] - score["end"] / 2))
        pause_at = pause_bar["score_t"]
        length = score["end"]

        def warp(t):
            t = np.asarray(t)
            # Integrate dt_performed/dt_score = 1.025 + .225 sin(2 pi t/L).
            smooth = 1.025 * t + 0.225 * length / (2 * np.pi) * (1 - np.cos(2 * np.pi * t / length))
            return 1 + smooth + 1.5 * (t >= pause_at - 0.001)

        phase = time.perf_counter()
        audio = render(score, samples, warp)
        target = make_features(audio=audio)
        truth = warp(np.array([b["score_t"] for b in score["bars"]]))
        variants = {}
        for variant in ("A", "B"):
            aligned = align(score, source_features[movement][variant], target)
            errors = abs(aligned["bars"] - truth) * 1000
            variants[variant] = {"median_ms": float(np.median(errors)),
                                 "p95_ms": float(np.percentile(errors, 95)),
                                 "max_ms": float(np.max(errors)),
                                 "bar_errors_ms": errors.tolist()}
            log(f"Self-test {movement} {variant}: median {np.median(errors):.1f}, "
                f"p95 {np.percentile(errors, 95):.1f}, max {max(errors):.1f} ms")
        results[movement] = {"variants": variants, "pause_bar": pause_bar["label"],
                             "pause_score_t": pause_at, "seconds": time.perf_counter() - phase}
    passed = all(r["variants"]["A"]["p95_ms"] <= 100 for r in results.values())
    result = {"fingerprint": key, "passed": passed, "movements": results,
              "seconds": time.perf_counter() - started,
              "optimistic": "Same piano samples on both sides; this is not real-recording accuracy."}
    write_json(RUNS / ".align-self-test.json", result)
    return result


def decode_reference(path: Path) -> tuple[np.ndarray, list, list]:
    if sha256(path) != REFERENCE_SHA256:
        raise ValueError("Reference SHA-256 mismatch")
    process = subprocess.run(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(path),
                              "-af", "silencedetect=noise=-30dB:d=1.5", "-ac", "1",
                              "-ar", str(WAV_SR), "-f", "f32le", "pipe:1"],
                             capture_output=True, check=True)
    audio = np.frombuffer(process.stdout, dtype="<f4").copy()
    stderr = process.stderr.decode(errors="replace")
    events = re.findall(r"silence_(start|end): ([0-9.]+)", stderr)
    gaps, start = [], None
    for kind, value in events:
        if kind == "start":
            start = float(value)
        elif start is not None:
            gaps.append([start, float(value)])
            start = None
    duration = len(audio) / WAV_SR
    interior = [gap for gap in gaps if gap[0] > 1 and gap[1] < duration - 0.1]
    longest = sorted(interior, key=lambda gap: gap[1] - gap[0], reverse=True)[:2]
    if len(longest) != 2:
        raise ValueError("Cannot identify two inter-movement silence gaps")
    selected = sorted(longest)
    bounds = [0.0] + [round(sum(gap) / 2, 2) for gap in selected] + [duration]
    log(f"Decode: {duration:.6f} s; gaps {selected}; cuts {bounds[1:3]}")
    return audio, bounds, gaps


def diagnostics(score: dict, variants: dict, proxies: dict, chosen: str,
                detected: np.ndarray, segment_duration: float) -> dict:
    score_times = np.array([b["score_t"] for b in score["bars"]] + [score["end"]])
    ratios = {}
    for variant, alignment in variants.items():
        ratios[variant] = np.diff(np.append(alignment["bars"], alignment["end"])) / np.diff(score_times)
    medians = {v: float(np.median(r)) for v, r in ratios.items()}
    distances = {v: nearest_distance(a["bars"], detected) for v, a in variants.items()}
    rows = []
    for i, bar in enumerate(score["bars"]):
        flags = []
        for variant in ("A", "B"):
            ratio = ratios[variant][i]
            if not 0.5 * medians[variant] <= ratio <= 2 * medians[variant]:
                flags.append(f"duration_ratio_{variant}")
            if variants[variant]["bar_repairs"][i]:
                flags.append(f"monotonicity_repair_{variant}")
            inside = (score["onsets"] >= score_times[i] - 0.001) & (score["onsets"] < score_times[i + 1] - 0.001)
            if np.any(variants[variant]["note_repairs"][inside]):
                flags.append(f"note_mapping_monotonicity_repair_{variant}")
        if abs(variants["A"]["bars"][i] - variants["B"]["bars"][i]) > 0.1:
            flags.append("AB_disagreement_over_100ms")
        if bar["downbeat_sounds"] and distances[chosen][i] > 0.1:
            flags.append("sounding_downbeat_far_from_onset")
        if bar["downbeat_sounds"] and not bar["downbeat_attack"]:
            flags.append("tied_continuation_without_midi_attack")
        if i == 0 and variants[chosen]["unclipped_opening_t"] < 0:
            flags.append("opening_downbeat_precedes_reference_clipped_to_zero")
        t = float(variants[chosen]["bars"][i])
        if not 0 <= t < segment_duration:
            flags.append("outside_segment")
        rows.append({**bar, "t": round(t, 3), "chosen_variant": chosen,
                     "variants": {v: {"t": round(float(variants[v]["bars"][i]), 3),
                                        "nearest_onset_distance_s": round(float(distances[v][i]), 4),
                                        "duration_ratio": round(float(ratios[v][i]), 4)} for v in ("A", "B")},
                     "nearest_onset_distance_s": round(float(distances[chosen][i]), 4),
                     "duration_ratio": round(float(ratios[chosen][i]), 4), "flags": flags})
    return {"chosen_variant": chosen, "proxies": proxies, "median_duration_ratio": medians,
            "opening_rate": {v: a["opening_rate"] for v, a in variants.items()},
            "unclipped_opening_t": {v: a["unclipped_opening_t"] for v, a in variants.items()},
            "onset_correspondences": [{"score_t": float(t),
                                        "notes": int(sum(abs(score["notes"].start - t) < 0.00001)),
                                        "A": float(variants["A"]["note_times"][i]),
                                        "B": float(variants["B"]["note_times"][i]),
                                        "monotonicity_repair_A": bool(variants["A"]["note_repairs"][i]),
                                        "monotonicity_repair_B": bool(variants["B"]["note_repairs"][i])}
                                       for i, t in enumerate(score["onsets"])],
            "detected_onsets": detected.tolist(), "bars": rows}


def write_listening_files(out: Path, movement: str, segment: np.ndarray, rows: list) -> dict:
    right = np.zeros(len(segment))
    for row in rows:
        first = round(row["t"] * WAV_SR)
        if not 0 <= first < len(right):
            raise ValueError(f"{movement} bar {row['label']} is outside segment")
        count = min(round(0.008 * WAV_SR), len(right) - first)
        frequency = 1800 if row["pass"] > 1 else 1200
        # Cosine begins at +1 on the exact anchor sample, followed by decay.
        click = np.cos(2 * np.pi * frequency * np.arange(count) / WAV_SR)
        click *= np.linspace(1, 0, count)
        right[first:first + count] += click
    target = out / f"click-{movement}.wav"
    sf.write(target, np.column_stack([segment, right]), WAV_SR, subtype="PCM_16")
    (out / f"labels-{movement}.txt").write_text("".join(
        f"{row['t']:.3f}\t{row['t']:.3f}\t{row['label']}\n" for row in rows))
    # Read the actual PCM back; quiet samples inside a click are not new clicks.
    wav, sr = sf.read(target, dtype="int16", always_2d=True)
    active = np.flatnonzero(wav[:, 1])
    starts = active[np.r_[True, np.diff(active) > round(0.01 * sr)]]
    expected = np.array([round(row["t"] * sr) for row in rows])
    if len(starts) != len(rows) or np.max(abs(starts - expected)) > 1:
        raise ValueError(f"Click read-back failed in {movement}")
    if sr != WAV_SR or wav.shape != (len(segment), 2):
        raise ValueError(f"WAV format or duration mismatch in {movement}")
    return {"anchors": len(rows), "wav_frames": len(wav), "wav_duration_s": len(wav) / sr,
            "clicks_read_back": len(starts), "maximum_click_error_samples": int(max(abs(starts - expected)))}


def report(out: Path, tools: dict, scores: dict, sample_path: Path, bounds: list,
           gaps: list, test: dict, details: dict, phases: dict, sanity: dict) -> None:
    lines = ["# Offline alignment probe — Loriod 1961", "",
             "These automatic anchors need a listening pass. No hand-tapped ground truth is available; "
             "the real-data numbers below are onset-coincidence proxies, not bar accuracy.", "",
             "## Inputs and tools", "", f"- Reference SHA-256: `{REFERENCE_SHA256}` (verified).",
             f"- Piano samples SHA-256: `{sha256(sample_path)}`; viewer SHA-384 SRI verified."]
    lines += [f"- MEI {m} SHA-256: `{s['sha256']}`." for m, s in scores.items()]
    lines += [f"- Script SHA-256: `{sha256(Path(__file__))}`.",
              "- Tools: " + "; ".join(f"{k} {v}" for k, v in tools.items()) + ".", "",
              "## Segments", "", "Reference clock is the ffmpeg decode, never MP3 header duration. "
              "The two longest interior −30 dB silence gaps (minimum 1.5 s) are split at their midpoints; "
              "cuts are rounded to 0.01 s before segment extraction.", ""]
    lines += [f"- {m}: {bounds[i]:.2f}–{bounds[i + 1]:.2f} file seconds."
              for i, m in enumerate(MOVEMENTS)]
    lines += [f"- All detected silence gaps: {json.dumps(gaps)}.", "",
              "## Method and selection rule", "",
              "A: Verovio MIDI note list → synctoolbox csv_tools pitch/onset features. "
              "B: the same note list rendered with the viewer's piano samples, velocity scaling and 10 ms release "
              "→ audio pitch/onset features. Recording features use the same audio route. "
              "Both use log-compressed pitch chroma and DLNCO with sync_via_mrmsdtw. "
              "Audio filterbanks use an automatically estimated tuning offset. One parameter set applies everywhere.",
              "", f"Parameters: `{json.dumps(PARAMETERS, sort_keys=True)}`.", "",
              "Choose the variant with the larger share of all MIDI note-ons within 50 ms of a detected "
              "recording onset (librosa onset_detect, 22050 Hz, hop 512, defaults otherwise); ties choose A. "
              "Chords count once per note, as specified. No snapping to the proxy detector is used. "
              "The first/last detected onsets define padded active spans for DTW, avoiding forced "
              "alignment of musical attacks to segment boundaries. Within the path, matching DLNCO "
              "attack evidence sets note correspondences. In intervals exceeding twice the local "
              "median rate, exact-pitch filterbank peaks resolve attacks confused with a preceding "
              "note's decaying onset feature; existing supported attacks are preserved. "
              "The sounding-downbeat proxy uses Verovio time-map on events at the downbeat, "
              "matching the supplied baseline's score-side definition. These include tied continuations: "
              "57 bars have no time-map on event (8/18/31), while a further 11 tied downbeats "
              "(2/0/9) have no fresh MIDI attack. Diagnostics distinguish downbeat_sounds and "
              "downbeat_attack and flag the tied continuations.", "",
              "Bar starts are interpolated between mapped unique note onsets, rather than read from the DTW path "
              "inside rests. Before the first onset, extrapolate using the median of the first six local "
              "onset-interval ratios. Thus segment-leading silence cannot force bar 1 to time zero. "
              "This interpolation assumes a steady local rate across each rest and cannot locate an unobserved "
              "tempo change or pause inside it. The final bar duration uses an extrapolated score-end time, "
              "not segment trailing silence. Monotonicity repairs, if any, are flagged.", "",
              "## Known-truth self-test", "", test["optimistic"], "",
              "Performed/score rate is 1.025 + 0.225 sin(2πt/L), spanning 0.8–1.25. "
              "Its integral sets the note times; there is 1 s leading silence, 3 s trailing silence, "
              "and an extra 1.5 s pause at the sounding bar nearest the movement midpoint. "
              "The aligner receives no timing truth. Errors include all played bars, including rests.", "",
              "| Movement | Variant | Median ms | p95 ms | Max ms |", "|---|---|---:|---:|---:|"]
    for m in MOVEMENTS:
        for v, row in test["movements"][m]["variants"].items():
            lines.append(f"| {m} | {v} | {row['median_ms']:.1f} | {row['p95_ms']:.1f} | {row['max_ms']:.1f} |")
    lines += ["", f"Variant A p95 ≤100 ms in every movement: **{'PASS' if test['passed'] else 'FAIL'}**.", "",
              "## Real-data onset proxies", "",
              "| Movement | Variant | Note-ons ≤50 ms | Note median ms | Sounding bars ≤100 ms | Bar median ms | Chosen |",
              "|---|---|---:|---:|---:|---:|---|"]
    for m, detail in details.items():
        for v, p in detail["proxies"].items():
            lines.append(f"| {m} | {v} | {p['note_within_50ms']:.1%} | {p['note_median_ms']:.1f} | "
                         f"{p['downbeat_within_100ms']:.1%} | {p['downbeat_median_ms']:.1f} | "
                         f"{'yes' if v == detail['chosen_variant'] else ''} |")
    lines += ["", "The supplied linear-baseline sounding-downbeat shares are I 39%, II 56%, III 20%. "
              "These use a nearest-onset metric: wrong repeated or nearby notes can still score well. "
              "Resting downbeats are excluded from this proxy and need listening checks.", ""]
    for m, detail in details.items():
        chosen = detail["chosen_variant"]
        p = detail["proxies"][chosen]["downbeat_within_100ms"]
        lines.append(f"- {m}: choose {chosen}; {p:.1%} vs {BASELINE[m]:.0%} baseline — "
                     f"{'beats baseline' if p > BASELINE[m] else 'DOES NOT BEAT baseline; inspect flags and sparse/repeated texture'}. "
                     f"Opening-rate estimates A/B: {detail['opening_rate']['A']:.3f}/{detail['opening_rate']['B']:.3f}.")
        opening = detail["unclipped_opening_t"][chosen]
        if opening < 0:
            lines.append(f"  **Input conflict:** extrapolated opening downbeat is {opening:.3f} s, "
                         "before the reference copy begins. At the inferred local rate, this transfer "
                         "contains less than the full opening rest. "
                         "The exported first anchor/click is clipped to 0 s, explicitly flagged; "
                         "the negative musical estimate is retained in diagnostics. An in-segment click "
                         "cannot represent a downbeat before the file starts.")
    lines += ["", "Sparse-texture probe: " + "; ".join(
        f"{m} chosen {d['chosen_variant']}: "
        f"{d['proxies'][d['chosen_variant']]['note_within_50ms']:.1%} of note-ons ≤50 ms, "
        f"{sum(bool(b['flags']) for b in d['bars'])}/{len(d['bars'])} bars flagged"
        for m, d in details.items()) + ". "
        "The onset proxies show no movement-wide collapse through II's repeats or III's sparse texture "
        "when both variants beat their supplied linear baseline. This is not evidence for the timing "
        "of silent downbeats: rate changes inside rests remain unobserved, and the duration flags "
        "identify unusual stretches to inspect.", ""]
    for m in MOVEMENTS:
        for v, result in test["movements"][m]["variants"].items():
            outliers = [(bar["label"], error) for bar, error in zip(
                scores[m]["bars"], result["bar_errors_ms"]) if error > 100]
            if outliers:
                lines.append(f"- Known-truth outliers >100 ms, {m}/{v}: " + ", ".join(
                    f"bar {label} ({error:.1f} ms)" for label, error in outliers) + ".")
    broken = [(m, v) for m, d in details.items() for v, p in d["proxies"].items()
              if p["downbeat_within_100ms"] <= BASELINE[m]]
    lines.append("- Variants failing the supplied baseline (potentially broken): " +
                 (", ".join(f"{m}/{v}" for m, v in broken) if broken else
                  "none. Local errors remain possible in either variant.") + "\n")
    lines += ["", "## Listen first", "",
              "Flags include each variant's performed/score bar-duration ratio outside [0.5, 2] × its "
              "movement median, A/B bar-start disagreement >100 ms, sounding downbeats >100 ms from a "
              "detected onset, and any monotonicity repair. A flagged rejected variant can implicate an "
              "otherwise plausible chosen anchor. Flags are uncertainty indicators, not measured errors.", ""]
    for m, detail in details.items():
        flagged = [row for row in detail["bars"] if row["flags"]]
        lines += [f"### {m}: {len(flagged)} flagged bars", ""]
        lines += [f"- {row['label']} at {row['t']:.3f} s: {', '.join(row['flags'])}." for row in flagged]
        if not flagged:
            lines.append("No proxy flags; still check opening rests and sparse passages.")
        lines.append("")
    lines += ["## Output read-back sanity", ""]
    for m, row in sanity.items():
        lines.append(f"- {m}: {row['anchors']} anchors, WAV {row['wav_duration_s']:.6f} s "
                     f"({row['wav_frames']} frames), {row['clicks_read_back']} clicks read back; "
                     f"max click offset {row['maximum_click_error_samples']} samples. "
                     f"Expected anchors/clicks: {COUNTS[m]}.")
    lines += ["", "Click WAVs are 44.1 kHz, PCM 16-bit stereo: reference mono downmix on the left, "
              "clicks alone on the right. Each click starts at full amplitude at its rounded JSON anchor, "
              "lasts 8 ms, and is 1200 Hz on pass 1 or 1800 Hz on later passes.", "",
              "In Audacity, open click-I.wav (then II and III), and use File → Import → Labels to load "
              "the matching labels-I.txt. Labels are segment-relative bar numbers; ‘(2)’ means pass 2. "
              "Use headphones or split the stereo track to control the reference and click levels separately. "
              "Start with flagged bars, bar 1, both repeat transitions in II, and the long rests in III.", "",
              "## Run times", ""]
    lines += [f"- {phase}: {seconds:.3f} s." for phase, seconds in phases.items()]
    lines += [f"- Self-test computation (including when reused from cache): {test['seconds']:.3f} s."]
    if "invocation_seconds" in test:
        lines += [f"- Separate self-test verification invocation: {test['invocation_seconds']:.3f} s.",
                  f"- Combined verification invocations: "
                  f"{test['invocation_seconds'] + phases['total this invocation']:.3f} s."]
    lines.append("")
    (out / "report.md").write_text("\n".join(lines))


def main(argv=None) -> int:
    started = STARTED
    load_started = time.perf_counter()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reference", type=Path, help="local MP3 with the verified reference hash")
    parser.add_argument("--samples", type=Path, default=RUNS / "audio-sync-ref" / "acoustic_grand_piano-mp3.js")
    parser.add_argument("--out", type=Path, default=RUNS / "audio-sync-2026-11-15")
    parser.add_argument("--self-test", action="store_true", help="known-truth synthetic test; no reference needed")
    args = parser.parse_args(argv)
    if not args.self_test and args.reference is None:
        parser.error("--reference is required unless --self-test is used")
    if not args.out.resolve().is_relative_to(RUNS.resolve()):
        parser.error("--out must be inside validation/runs/")
    tools = versions()
    phases = {"imports": load_started - started}
    scores = load_scores()
    samples = load_samples(args.samples)
    phases["load scores and decode piano samples"] = time.perf_counter() - load_started
    phase = time.perf_counter()
    source_features = {}
    for m, score in scores.items():
        log(f"Score features {m}: MIDI and rendered samples")
        source_features[m] = {"A": make_features(score=score),
                              "B": make_features(audio=render(score, samples))}
    phases["score features, both variants"] = time.perf_counter() - phase
    key = fingerprint(scores, args.samples, tools)
    cache = RUNS / ".align-self-test.json"
    test = json.loads(cache.read_text()) if cache.exists() else None
    phase = time.perf_counter()
    if args.self_test or not test or test.get("fingerprint") != key:
        test = self_test(scores, samples, source_features, key)
    else:
        log("Reusing fingerprint-matched self-test")
    phases["self-test this invocation"] = time.perf_counter() - phase
    if args.self_test:
        test["invocation_seconds"] = time.perf_counter() - started
        write_json(cache, test)
        log(f"Self-test {'PASS' if test['passed'] else 'FAIL'}; total {time.perf_counter() - started:.2f} s")
        return 0 if test["passed"] else 1
    args.out.mkdir(parents=True, exist_ok=True)
    phase = time.perf_counter()
    audio, bounds, gaps = decode_reference(args.reference)
    phases["reference hash, ffmpeg decode and segmentation"] = time.perf_counter() - phase
    anchors, details, sanity = {}, {}, {}
    for i, m in enumerate(MOVEMENTS):
        score = scores[m]
        first, last = round(bounds[i] * WAV_SR), round(bounds[i + 1] * WAV_SR)
        segment = audio[first:last]
        phase = time.perf_counter()
        mono = librosa.resample(segment, orig_sr=WAV_SR, target_sr=SR)
        target = make_features(audio=mono)
        detected = target["detected_onsets"]
        phases[f"{m} recording features and onset detector"] = time.perf_counter() - phase
        variants, proxies = {}, {}
        for v in ("A", "B"):
            phase = time.perf_counter()
            variants[v] = align(score, source_features[m][v], target)
            # A transfer may start after the extrapolated first downbeat. Keep
            # the estimate in diagnostics, but its listening cue can only begin
            # at the file boundary. Never conceal this input conflict.
            if variants[v]["bars"][0] < 0:
                variants[v]["bars"][0] = 0.0
            variants[v]["bars"] = variants[v]["bars"].round(3)
            proxies[v] = onset_proxy(score, variants[v], detected)
            phases[f"{m} DTW {v}"] = time.perf_counter() - phase
            log(f"Real {m} {v}: note-ons ≤50ms {proxies[v]['note_within_50ms']:.1%}; "
                f"sounding bars ≤100ms {proxies[v]['downbeat_within_100ms']:.1%}")
        chosen = max(("A", "B"), key=lambda v: proxies[v]["note_within_50ms"])
        details[m] = diagnostics(score, variants, proxies, chosen, detected, len(segment) / WAV_SR)
        details[m]["recording_tuning_cents"] = target["tuning_cents"]
        rows = details[m]["bars"]
        times = np.array([row["t"] for row in rows])
        if not np.all(np.diff(times) > 0):
            raise ValueError(f"Rounded anchors are not strictly increasing in {m}")
        anchors[m] = {"anchors": [{"measure": row["measure"], "pass": row["pass"],
                                   "t": row["t"], "how": "dtw"} for row in rows]}
        phase = time.perf_counter()
        sanity[m] = write_listening_files(args.out, m, segment, rows)
        phases[f"{m} listening outputs and PCM read-back"] = time.perf_counter() - phase
        log(f"{m}: choose {chosen}, {sum(bool(r['flags']) for r in rows)} flagged bars; {sanity[m]}")
    result = {"recording": {"performer": "Yvonne Loriod", "year": 1961, "label": "Véga C 30 A 309"},
              "reference": {"note": "local reference copy; see docs/audio-sync-plan.md",
                            "sha256": REFERENCE_SHA256, "decoder": tools["ffmpeg"],
                            "movements": {m: [round(bounds[i], 2), round(bounds[i + 1], 2)]
                                          for i, m in enumerate(MOVEMENTS)}}, "movements": anchors}
    write_json(args.out / "anchors.json", result)
    phases["total this invocation"] = time.perf_counter() - started
    write_json(args.out / "diagnostics.json", {"parameters": PARAMETERS, "tools": tools,
               "self_test": test, "phases_seconds": phases, "sanity": sanity, "movements": details})
    report(args.out, tools, scores, args.samples, bounds, gaps, test, details, phases, sanity)
    log(f"Wrote 165 anchors and listening files to {args.out}; total {time.perf_counter() - started:.2f} s")
    return 0 if test["passed"] else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Alignment failed: {error}") from error
