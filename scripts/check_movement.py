#!/usr/bin/env python3
"""Consistency sweep of one movement file (read-only).

Lists what the encoding profile asks to be uniform, for review after an
enrichment pass; it fixes nothing and has no exit status for findings:

 1. layer durations that do not fill the bar (meter read per bar; a bar with
    @metcon="false", such as the pickup in II, is reported only if its layers
    differ from each other)
 2. control events: missing pointer targets, missing @staff or @place,
    @tstamp used where a note could be the anchor, and the element types the
    pointers reach
 3. the (staff, place) combinations of dynam and hairpin
 4. each hairpin's end and the dynamic that follows it: "joined" when a dynam
    starts on the hairpin's end anchor with the same @staff and @place (Verovio
    then stops the hairpin at the dynamic), "GAP" when a dynamic starts within
    one beat after the end but is not joined
 5. every dir and tempo with its attributes; extenders without @lsegs
 6. notes and chords without @stem.dir, per bar
 7. how accidentals are encoded (@accid, @accid.ges, accid children)
 8. the child order of notes holding both artic and accid
 9. space elements
10. with --baseline, notes, rests, chords and spaces whose pitch or duration
    changed, by xml:id (a file path or a git revision such as 98812bc)

Usage: python scripts/check_movement.py mei/webern-op27-II.mei [--baseline 98812bc]
"""
from __future__ import annotations

import argparse
import collections
import subprocess
from fractions import Fraction
from pathlib import Path

from lxml import etree

REPO = Path(__file__).resolve().parents[1]
M = "{http://www.music-encoding.org/ns/mei}"
NS = {"m": M[1:-1]}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
CONTROL = ("dynam", "hairpin", "dir", "tempo", "slur", "tie", "beamSpan", "fermata", "pedal", "octave")
TIMED = ("note", "rest", "space", "chord", "mRest", "mSpace")
LONG = {"breve": Fraction(2), "long": Fraction(4)}


def local(e) -> str:
    return etree.QName(e).localname


def section(title: str) -> None:
    print(f"\n## {title}")


def duration(e) -> Fraction | None:
    """Written duration of a note, rest, chord or space, with dots and tuplets."""
    d = e.get("dur")
    if d is None and local(e) == "note" and local(e.getparent()) == "chord":
        d = e.getparent().get("dur")
    if d is None:
        return None
    base = LONG.get(d) or Fraction(1, int(d))
    total, add = base, base
    for _ in range(int(e.get("dots", "0"))):
        add /= 2
        total += add
    for a in e.iterancestors():
        if local(a) == "layer":
            break
        if local(a) == "tuplet":
            total = total * int(a.get("numbase", "1")) / int(a.get("num", "1"))
    return total


def layer_events(layer):
    """Timed events of a layer in order: no chord members, no grace notes."""
    for e in layer.iter():
        if not isinstance(e.tag, str) or local(e) not in TIMED:
            continue
        if local(e) == "note" and local(e.getparent()) == "chord":
            continue
        if e.get("grace"):
            continue
        yield e


def bar_meters(root):
    """Measure element -> (bar length, beat), following meterSig/@meter.* in document order."""
    meter, beat, out = None, Fraction(1, 4), {}
    for e in root.find(".//m:music", NS).iter():
        if not isinstance(e.tag, str):
            continue
        name = local(e)
        if name == "meterSig" and e.get("count"):
            meter, beat = Fraction(int(e.get("count")), int(e.get("unit"))), Fraction(1, int(e.get("unit")))
        elif name in ("scoreDef", "staffDef") and e.get("meter.count"):
            meter = Fraction(int(e.get("meter.count")), int(e.get("meter.unit")))
            beat = Fraction(1, int(e.get("meter.unit")))
        elif name == "measure":
            out[e] = (meter, beat)
    return out


def check(path: Path, baseline: str | None) -> None:
    root = etree.parse(str(path)).getroot()
    music = root.find(".//m:music", NS)
    by_id = {e.get(XML_ID): e for e in root.iter() if isinstance(e.tag, str) and e.get(XML_ID)}
    measure_of = {}
    for meas in root.iter(M + "measure"):
        for e in meas.iter():
            measure_of[e] = meas.get("n")
    meters = bar_meters(root)
    beat_of = {meas: beat for meas, (_, beat) in meters.items()}

    # Onsets (whole-note units from the start) of every timed event, for section 4.
    onset, t = {}, Fraction(0)
    for meas, (meter, _) in meters.items():
        longest = Fraction(0)
        for layer in meas.iter(M + "layer"):
            pos = t
            for e in layer_events(layer):
                onset[e.get(XML_ID)] = pos
                for member in e.iterfind("m:note", NS):
                    onset[member.get(XML_ID)] = pos
                pos += meter if local(e) in ("mRest", "mSpace") else (duration(e) or 0)
            longest = max(longest, pos - t)
        t += longest if meas.get("metcon") == "false" or meter is None else meter

    section("Layer durations that do not fill the bar")
    for meas, (meter, _) in meters.items():
        totals = {}
        for layer in meas.iter(M + "layer"):
            total = Fraction(0)
            for e in layer_events(layer):
                if local(e) in ("mRest", "mSpace"):
                    total += meter
                    continue
                d = duration(e)
                if d is None:
                    print(f"  m{meas.get('n')} {e.get(XML_ID)}: no @dur")
                    continue
                total += d
            totals[(layer.getparent().get("n"), layer.get("n"))] = total
        if meas.get("metcon") == "false":
            if len(set(totals.values())) > 1:
                print(f"  m{meas.get('n')} (metcon=false) layers differ: "
                      + ", ".join(f"staff {s} layer {l}: {v}" for (s, l), v in totals.items()))
            continue
        for (staff, layer_n), total in totals.items():
            if total != meter:
                print(f"  m{meas.get('n')} staff {staff} layer {layer_n}: {total} (bar {meter})")

    section("Control events: targets, @staff, @place, @tstamp")
    reached = collections.Counter()
    for e in music.iter(*(M + c for c in CONTROL)):
        for attr in ("startid", "endid"):
            ref = e.get(attr)
            if ref:
                target = by_id.get(ref.lstrip("#"))
                if target is None:
                    print(f"  m{measure_of.get(e)} {e.get(XML_ID)} @{attr} -> missing {ref}")
                else:
                    reached[(local(e), attr, local(target))] += 1
        if local(e) in ("dynam", "hairpin", "dir", "tempo"):
            missing = [a for a in ("staff", "place") if not e.get(a)]
            if missing:
                print(f"  m{measure_of.get(e)} {e.get(XML_ID)}: no @{' @'.join(missing)}")
        if e.get("tstamp") is not None and local(e) != "tempo":
            print(f"  m{measure_of.get(e)} {e.get(XML_ID)}: @tstamp={e.get('tstamp')}"
                  + (f" @tstamp2={e.get('tstamp2')}" if e.get("tstamp2") else ""))
    for (name, attr, target), count in sorted(reached.items()):
        print(f"  {name:9} @{attr:7} -> {target:6} x{count}")

    section("dynam and hairpin (staff, place)")
    combos = collections.Counter((local(e), e.get("staff"), e.get("place"))
                                 for e in music.iter(M + "dynam", M + "hairpin"))
    for key, count in sorted(combos.items(), key=str):
        print(f"  {key}: {count}")

    section("Hairpins and the following dynamic")
    dynams = [d for d in music.iter(M + "dynam") if d.get("startid")]
    for h in music.iter(M + "hairpin"):
        end_ref = h.get("endid")
        line = f"  m{measure_of.get(h)} {h.get(XML_ID)} {h.get('form')} ({h.get('staff')},{h.get('place')})"
        if not end_ref:
            print(line + f" no @endid (tstamp2={h.get('tstamp2')})")
            continue
        end = by_id.get(end_ref.lstrip("#"))
        line += f" ends on {local(end) if end is not None else 'missing'}"
        end_t = onset.get(end_ref.lstrip("#"))
        notes = []
        for d in dynams:
            text = "".join(d.itertext()).strip()
            where = f"{text} ({d.get('staff')},{d.get('place')}) on {d.get('startid').lstrip('#')}"
            if d.get("startid") == end_ref:
                same = d.get("staff") == h.get("staff") and d.get("place") == h.get("place")
                notes.append(("joined to " if same else "dynam on the end anchor, other staff/place: ") + where)
            elif end_t is not None:
                d_t = onset.get(d.get("startid").lstrip("#"))
                beat = beat_of[next(a for a in h.iterancestors() if local(a) == "measure")]
                if d_t is not None and end_t <= d_t <= end_t + beat:
                    notes.append(f"GAP +{(d_t - end_t) / Fraction(1, 32)}/32 to " + where)
        print(line + ("; " + "; ".join(notes) if notes else ""))

    section("dir and tempo")
    for e in music.iter(M + "dir", M + "tempo"):
        text = " ".join("".join(e.itertext()).split())
        attrs = " ".join(f'{k}="{v}"' for k, v in e.attrib.items() if k != XML_ID)
        flag = " [extender without @lsegs]" if e.get("extender") == "true" and not e.get("lsegs") else ""
        print(f"  m{measure_of.get(e)} {local(e)} {e.get(XML_ID)} '{text}' {attrs}{flag}")

    section("Notes and chords without @stem.dir (per bar)")
    missing = collections.Counter()
    for e in music.iter(M + "note", M + "chord"):
        if local(e) == "note" and local(e.getparent()) == "chord":
            continue
        if e.get("stem.dir") is None and e.get("dur") not in ("1", "breve", "long"):
            missing[measure_of.get(e)] += 1
    print("  " + (", ".join(f"m{k}:{v}" for k, v in sorted(missing.items(), key=lambda x: int(x[0])))
                  or "none"))

    section("Accidentals")
    accids = collections.Counter()
    for n in music.iter(M + "note"):
        if n.get("accid"):
            accids[("@accid", n.get("accid"))] += 1
        if n.get("accid.ges"):
            accids[("@accid.ges", n.get("accid.ges"))] += 1
        for a in n.iterfind("m:accid", NS):
            accids[("accid child", a.get("accid"), a.get("func"), a.get("type"))] += 1
    for key, count in sorted(accids.items(), key=str):
        print(f"  {key}: {count}")

    section("Child order of notes with artic and accid")
    orders = collections.Counter()
    for n in music.iter(M + "note"):
        kids = tuple(local(c) for c in n if isinstance(c.tag, str))
        if "artic" in kids and "accid" in kids:
            orders[kids] += 1
    for kids, count in orders.items():
        print(f"  {kids}: {count}")
    if not orders:
        print("  none")

    section("space elements")
    for s in music.iter(M + "space"):
        print(f"  m{measure_of.get(s)} {s.get(XML_ID)} dur={s.get('dur')}")

    if baseline:
        section(f"Pitch and duration changes against {baseline}")
        if Path(baseline).is_file():
            base_root = etree.parse(baseline).getroot()
        else:
            rel = path.resolve().relative_to(REPO)
            data = subprocess.run(["git", "-C", str(REPO), "show", f"{baseline}:{rel}"],
                                  check=True, capture_output=True).stdout
            base_root = etree.fromstring(data)

        def signature(e):
            d = {k: e.get(k) for k in ("pname", "oct", "accid", "dur", "dots", "grace")}
            if local(e) == "note":
                d["accid"] = d["accid"] or next((a.get("accid") for a in e.iterfind("m:accid", NS)), None)
                if d["dur"] is None and local(e.getparent()) == "chord":
                    d["dur"] = e.getparent().get("dur")
            return local(e), d

        kinds = (M + "note", M + "rest", M + "chord", M + "space")
        old = {e.get(XML_ID): signature(e) for e in base_root.iter(*kinds) if e.get(XML_ID)}
        new = {e.get(XML_ID): signature(e) for e in root.iter(*kinds) if e.get(XML_ID)}
        for k in sorted(set(old) - set(new)):
            print(f"  removed {k} {old[k]}")
        for k in sorted(set(new) - set(old)):
            print(f"  added   {k} {new[k]}")
        for k in sorted(set(old) & set(new)):
            if old[k] != new[k]:
                print(f"  changed {k}: {old[k]} -> {new[k]}")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("mei", type=Path)
    parser.add_argument("--baseline", help="file or git revision to compare pitches and durations with")
    args = parser.parse_args(argv)
    check(args.mei, args.baseline)


if __name__ == "__main__":
    main()
