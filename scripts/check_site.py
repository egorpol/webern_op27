#!/usr/bin/env python3
"""Headless check of the viewer's playback against a local build.

Drives the real page: Verovio, the player libraries, the piano samples and the
scan come from the network. The expected tempo is worked out from the printed
mark (@mm, @mm.unit, @mm.dots), not from @midi.bpm, so a wrong MIDI tempo fails.
An analyser on the audio output checks that sound comes out; nobody has listened.
The grace-note timing the viewer reports is worked out again here from Verovio's
own MIDI and time map, by a different route from the viewer's.

Needs Playwright and its browsers. Exit code 1 if any check fails.

Usage: python scripts/check_site.py [--site DIR] [--browser chromium|firefox] [--screenshot PNG]
       --site checks a finished build instead of building into a temporary folder.
"""
from __future__ import annotations

import argparse
import base64
import functools
import http.server
import io
import re
import subprocess
import sys
import tempfile
import threading
import xml.etree.ElementTree as ET
from pathlib import Path

import mido
import verovio
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
MEI = "{http://www.music-encoding.org/ns/mei}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
MOVEMENTS = ("I", "II", "III")
UNIT_WORDS = {"2": "half", "4": "quarter", "8": "eighth"}
MIDI_NOTES = {"I": 311, "II": 178, "III": 364}
MIDI_NOTES_NO_REPEATS = 90
GRACE_MS = 70  # GRACE_MS in site/viewer.js
GRACE_KEYS = ("graces", "graceMains", "graceCuts", "graceSkipped")
# Heard-from-the-output floor: well above the silence of a muted build (0), well below a piano note.
SOUND_PEAK = 0.01
# Every node that reaches the speakers also feeds one analyser, sampled for its peak.
AUDIO_TAP = """
(() => {
  const connect = AudioNode.prototype.connect;
  const taps = new WeakMap(); // Tone makes a context of its own at load, so one analyser per context.
  window.__peak = 0;
  AudioNode.prototype.connect = function (target, ...rest) {
    const context = this.context;
    if (target === context?.destination) {
      if (!taps.has(context)) {
        const analyser = context.createAnalyser();
        analyser.fftSize = 2048;
        const data = new Float32Array(analyser.fftSize);
        setInterval(() => {
          analyser.getFloatTimeDomainData(data);
          for (const value of data) window.__peak = Math.max(window.__peak, Math.abs(value));
        }, 20);
        taps.set(context, analyser);
      }
      connect.call(this, taps.get(context));
    }
    return connect.call(this, target, ...rest);
  };
})();
"""
RATE = """async () => {
  const player = document.getElementById('player');
  const [q, t] = [Number(player.dataset.position), performance.now()];
  await new Promise((resolve) => setTimeout(resolve, 2000));
  return (Number(player.dataset.position) - q) / ((performance.now() - t) / 60000);
}"""
WATCH_BARS = """() => {
  const player = document.getElementById('player');
  window.__bars = [];
  window.__watch?.disconnect();
  window.__watch = new MutationObserver(() => {
    const n = player.dataset.measure;
    if (n && window.__bars.at(-1) !== n) window.__bars.push(n);
  });
  window.__watch.observe(player, { attributes: true, attributeFilter: ['data-measure'] });
}"""
PLAYING_FILL = """() => {
  const note = document.querySelector('#score .is-playing');
  const wanted = document.createElement('i');
  wanted.style.color = 'var(--playing)';
  document.body.append(wanted);
  const colour = getComputedStyle(wanted).color;
  wanted.remove();
  return note && getComputedStyle(note).fill === colour;
}"""


def printed_tempo(movement: str) -> tuple[float, str, str]:
    """Quarter notes per minute by the printed mark, the viewer's wording, the last bar."""
    root = ET.parse(ROOT / f"mei/webern-op27-{movement}.mei").getroot()
    tempo = next(t for t in root.find(f"{MEI}music").iter(f"{MEI}tempo") if t.get("mm"))
    mm, unit, dots = float(tempo.get("mm")), tempo.get("mm.unit"), int(tempo.get("mm.dots", 0))
    bars = [m.get("n") for m in root.iter(f"{MEI}measure")]
    mark = f"{'dotted ' if dots else ''}{UNIT_WORDS[unit]} ca {tempo.get('mm')}"
    return mm * 4 / int(unit) * (2 - 2 ** -dots), mark, bars[-1]


def expected_graces(movement: str, repeats: bool = True) -> dict[str, str]:
    """The viewer's data-grace* values, from Verovio 6.3's MIDI and time map.

    The viewer finds bar starts in the MEI layers and main notes by id; here a bar
    start is a time-map measureOn and the main notes are the notes that start where
    Verovio's grace ends. Every grace then lasts GRACE_MS and ends on the beat.
    """
    path = ROOT / f"mei/webern-op27-{movement}.mei"
    verovio.enableLog(False)
    toolkit = verovio.toolkit()
    toolkit.setOptions({"expandNever": not repeats})
    toolkit.loadFile(str(path))
    midi = mido.MidiFile(file=io.BytesIO(base64.b64decode(toolkit.renderToMIDI())))
    ppq, notes, tempos = midi.ticks_per_beat, [], []
    for track in midi.tracks:
        tick, sounding = 0, {}
        for message in track:
            tick += message.time
            if message.type == "set_tempo":
                tempos.append(message.tempo)
            elif message.type == "note_on" and message.velocity:
                sounding.setdefault(message.note, []).append(tick)
            elif message.type in ("note_on", "note_off") and sounding.get(message.note):
                start = sounding[message.note].pop(0)
                notes.append([start, tick - start, message.note])
    assert len(set(tempos)) == 1, tempos  # one tempo per movement in this edition
    length = round(GRACE_MS * 60e6 / tempos[0] * ppq / 60000)
    timemap = toolkit.renderToTimemap({"includeMeasures": True})
    bar_starts = {e["qstamp"] for e in timemap if "measureOn" in e}
    ids = {n.get(XML_ID) for n in ET.parse(path).iter(f"{MEI}note") if n.get("grace")}
    found = []
    for event in timemap:
        for raw in event.get("on", []):
            if raw.split("-rend")[0] in ids:
                pitch = toolkit.getMIDIValuesForElement(raw.split("-rend")[0])["pitch"]
                [note] = [n for n in notes if n[2] == pitch and abs(n[0] - event["qstamp"] * ppq) < 1]
                found.append((note, event["qstamp"] in bar_starts))
    graces = [n for n, _ in found]
    others = [n for n in notes if all(n is not g for g in graces)]
    result = {key: [] for key in GRACE_KEYS[:3]}
    for note, bar_start in found:
        end = note[0] + note[1]
        mains = [n for n in others if end <= n[0] <= end + 1]
        beat = note[0] if bar_start else min(n[0] for n in mains)
        result["graces"].append((beat - length, length, note[2]))
        if bar_start:
            result["graceMains"] += [(beat, n[0] + n[1] - beat, n[2]) for n in mains]
        held = [n for n in others if n[2] == note[2] and n[0] < beat - length < n[0] + n[1]]
        result["graceCuts"] += [(n[0], beat - length - n[0], n[2]) for n in held]
    out = {key: " ".join(f"{t}/{d}/{p}" for t, d, p in sorted(value)) for key, value in result.items()}
    return {**out, "graceSkipped": "0"}


def check_graces(view: Viewer, check: Checks, label: str, expected: dict[str, str]) -> None:
    for key in GRACE_KEYS:
        got = view.data(key)
        check(f"{label}: {key} as worked out from Verovio", got == expected[key], f"{got!r}, expected {expected[key]!r}")


class Checks:
    def __init__(self) -> None:
        self.failed: list[str] = []
        self.count = 0

    def __call__(self, label: str, ok: bool, detail: object = "") -> bool:
        self.count += 1
        print(f"{'pass' if ok else 'FAIL'}  {label}{f'  ({detail})' if detail != '' else ''}", flush=True)
        if not ok:
            self.failed.append(label)
        return ok


class Viewer:
    def __init__(self, page, check: Checks) -> None:
        self.page = page
        self.check = check

    def data(self, key: str) -> str:
        return self.page.evaluate("(k) => document.getElementById('player').dataset[k]", key)

    def wait(self, label: str, condition: str, timeout: int = 15000, arg=None) -> bool:
        try:
            self.page.wait_for_function(condition, arg=arg, timeout=timeout)
            return True
        except PlaywrightTimeout:
            return self.check(label, False, "timed out")

    def state(self, value: str, timeout: int = 15000) -> bool:
        return self.wait(f"player reaches {value}", "(s) => document.getElementById('player').dataset.state === s", timeout, value)

    def open(self, movement: str) -> None:
        self.page.click(f'.tabs button[data-mvt="{movement}"]')
        self.wait(f"movement {movement} opens", "(m) => document.getElementById('player').dataset.movement === m", arg=movement)
        self.page.wait_for_selector("#score svg")

    def set_tempo(self, percent: int) -> None:
        self.page.fill("#tempo-number", str(percent))
        self.page.press("#tempo-number", "Enter")

    def peak(self) -> float:
        return self.page.evaluate("() => { const p = window.__peak; window.__peak = 0; return p; }")

    def silent_after_stop(self) -> float:
        self.page.wait_for_timeout(300)
        self.peak()
        self.page.wait_for_timeout(300)
        return self.peak()


def check_movement(view: Viewer, check: Checks, movement: str) -> None:
    page = view.page
    bpm, mark, last = printed_tempo(movement)
    view.open(movement)
    check(f"{movement}: tempo note gives the printed mark", page.inner_text("#tempo-base") == f"100 % = {mark}", page.inner_text("#tempo-base"))
    check(f"{movement}: Repeats shows in II only", page.is_visible("#repeats-label") == (movement == "II"))
    view.peak()
    page.click("#play")
    if not view.state("playing", 60000):
        return
    check(f"{movement}: MIDI tempo is the printed tempo", abs(float(view.data("bpm")) - bpm) < 0.01, f"{view.data('bpm')}, printed {bpm:g}")
    check(f"{movement}: MIDI note count", view.data("midiNotes") == str(MIDI_NOTES[movement]), view.data("midiNotes"))
    check_graces(view, check, movement, expected_graces(movement))
    first = page.inner_text("#player-position")
    check(f"{movement}: position counts to the last printed bar", first.endswith(f" / {last}"), first)
    if view.wait(f"{movement}: notes light up", "() => document.querySelector('#score .is-playing')"):
        check(f"{movement}: sounding notes take the playing colour", page.evaluate(PLAYING_FILL))
    # The first note lights up before the sound starts: the position holds for the player's look-ahead.
    view.wait(f"{movement}: position moves", "() => Number(document.getElementById('player').dataset.position) > 0.05")
    rate = page.evaluate(RATE)
    check(f"{movement}: position runs at the printed tempo", abs(rate - bpm) / bpm < 0.05, f"{rate:.1f} quarters a minute, printed {bpm:g}")
    peak = view.peak()
    check(f"{movement}: sound reaches the output", peak > SOUND_PEAK, f"peak {peak:.3f}")
    page.click("#stop")
    view.state("idle")
    check(f"{movement}: Stop returns to the start", float(view.data("position")) == 0 and not page.query_selector("#score .is-playing"), view.data("position"))
    silent = view.silent_after_stop()
    check(f"{movement}: silent after Stop", silent < SOUND_PEAK / 10, f"peak {silent:.4f}")


def check_repeats(view: Viewer, check: Checks) -> None:
    """Movement II played through with and without its repeats, at double speed."""
    page = view.page
    view.open("II")
    view.set_tempo(200)
    for repeats, notes, jumps in ((True, MIDI_NOTES["II"], 2), (False, MIDI_NOTES_NO_REPEATS, 0)):
        page.set_checked("#repeats", repeats)
        page.evaluate(WATCH_BARS)
        page.click("#play")
        view.state("playing", 60000)
        label = "with repeats" if repeats else "without repeats"
        check(f"II {label}: note count", view.data("midiNotes") == str(notes), view.data("midiNotes"))
        check_graces(view, check, f"II {label}", expected_graces("II", repeats))
        check(f"II {label}: double tempo applies", abs(float(view.data("bpm")) - 320) < 0.01, view.data("bpm"))
        view.state("idle", 40000)  # the end of the movement stops by itself
        bars = page.evaluate("() => window.__bars")
        played = [int(n) for n in bars[: len(bars) - bars[::-1].index("22")]] if "22" in bars else []
        back = sum(b < a for a, b in zip(played, played[1:]))
        check(f"II {label}: plays to bar 22 with {jumps} backward jumps", bool(played) and back == jumps, f"{back}; bars {played[:4]}…")
    page.set_checked("#repeats", True)
    view.set_tempo(100)


def check_turn_and_controls(view: Viewer, check: Checks, screenshot: str | None) -> None:
    page = view.page
    view.open("I")
    page.click("#scan-show")
    page.wait_for_selector("#zones rect", state="attached", timeout=30000)
    view.set_tempo(200)
    page.evaluate("location.hash = '#I/18'")
    view.wait("bar 18 pins", "() => document.getElementById('status').textContent.includes('bar 18')")
    start_label = page.inner_text("#page-label")
    page.click("#play")
    view.state("playing", 60000)
    turned = view.wait("page turns with the music", "(s) => document.getElementById('page-label').textContent !== s", 15000, start_label)
    if turned:
        check("page turn follows the music", True, page.inner_text("#page-label"))
    # The zones are rebuilt after the turn, once the next page of the scan is drawn.
    if view.wait("playing bar shows on the scan", "() => document.querySelectorAll('#zones rect.is-playing').length === 1", 20000):
        check("scan marks the playing bar", True)
    if screenshot:
        page.screenshot(path=screenshot)
    page.evaluate("document.activeElement?.blur()")
    page.keyboard.press("Space")
    view.state("paused")
    paused = float(view.data("position"))
    page.wait_for_timeout(400)
    check("Space pauses", float(view.data("position")) == paused, paused)
    page.keyboard.press("Space")
    view.state("playing")
    page.wait_for_timeout(600)
    check("Space resumes from the same place", paused < float(view.data("position")) < paused + 4, view.data("position"))
    page.click("#stop")
    view.state("idle")
    check("Stop turns back to the starting page", page.inner_text("#page-label") == start_label, page.inner_text("#page-label"))

    page.click("#play")
    view.state("playing")
    page.click('.tabs button[data-mvt="III"]')
    view.wait("movement III opens", "() => document.getElementById('player').dataset.movement === 'III'")
    check("changing movement stops playback", view.data("state") == "idle" and view.data("position") == "0", view.data("state"))
    silent = view.silent_after_stop()
    check("silent after changing movement", silent < SOUND_PEAK / 10, f"peak {silent:.4f}")

    page.click("#play")
    view.state("playing")
    page.uncheck("#playback")
    check("switching Playback off stops and hides the player", view.data("state") == "idle" and page.is_hidden("#player"))
    page.check("#playback")
    view.set_tempo(150)
    page.uncheck("#repeats") if page.is_visible("#repeats") else page.evaluate("document.getElementById('repeats').click()")
    page.reload()
    page.wait_for_selector("#score svg")
    check("settings survive a reload", page.is_checked("#playback") and page.input_value("#tempo-number") == "150" and not page.is_checked("#repeats"))
    keys = page.evaluate("Object.keys(localStorage)")
    check("storage keys are this edition's", all(k.startswith("webern-op27-") for k in keys), ", ".join(sorted(k.removeprefix("webern-op27-") for k in keys)))


def run(site: Path, browser_name: str, screenshot: str | None) -> Checks:
    check = Checks()

    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args) -> None:
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with sync_playwright() as p:
        browser = getattr(p, browser_name).launch()
        page = browser.new_page(viewport={"width": 1400, "height": 900})
        page.add_init_script(AUDIO_TAP)
        errors: list[str] = []
        requests: list[str] = []
        page.on("console", lambda m: errors.append(m.text[:200]) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(str(e)[:200]))
        page.on("request", lambda r: requests.append(r.url))
        page.goto(f"http://127.0.0.1:{server.server_address[1]}/#I")
        page.wait_for_selector("#score svg", timeout=60000)
        view = Viewer(page, check)

        check("Playback is off by default", not page.is_checked("#playback") and page.is_hidden("#player"))
        page.check("#playback")
        check("the switch shows the player and its note", page.is_visible("#play") and "not played" in page.inner_text("#player-note"))
        early = [u for u in requests if re.search(r"player\.js|tone|smplr|soundfont", u, re.I)]
        check("nothing for playback loads before Play", not early, early[:2] or "")

        for movement in MOVEMENTS:
            check_movement(view, check, movement)
        check_repeats(view, check)
        check_turn_and_controls(view, check, screenshot)
        check("no console or page errors", not errors, errors[:3] or "")
        browser.close()
    server.shutdown()
    return check


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", type=Path, help="a finished build; default: build into a temporary folder")
    parser.add_argument("--browser", choices=("chromium", "firefox"), default="chromium")
    parser.add_argument("--screenshot", help="save the page while the music plays over the scan")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as folder:
        site = args.site
        if site is None:
            site = Path(folder) / "site"
            subprocess.run([sys.executable, str(ROOT / "scripts/build_site.py"), str(site)], check=True, stdout=subprocess.DEVNULL)
        check = run(site.resolve(), args.browser, args.screenshot)
    print(f"{check.count - len(check.failed)}/{check.count} passed" + (f"; failed: {'; '.join(check.failed)}" if check.failed else ""))
    return 1 if check.failed else 0


if __name__ == "__main__":
    sys.exit(main())
