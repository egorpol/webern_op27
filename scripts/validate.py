#!/usr/bin/env python3
"""Run the edition's validation gate: CAMAT's MEI validator on the movement files.

This is a thin wrapper around camat.mei_validation (camat-validate-mei) with
the repository's settings: the bundled CMN 5.1 schema, the required checks
(XML references, RELAX NG, embedded Schematron, image resources, input
hashes), Verovio rendering and the CAMAT parse. The run goes to
validation/runs/<UTC timestamp>/ (run.json, findings.json, findings.csv).

The run passes only if every required check and both consumer checks pass.
Schematron needs saxonche (CAMAT's `validation` extra); without it the script
stops before running, since a run that skips Schematron is not a pass.

CAMAT is imported from the installed package or, failing that, from the
checkout given by --camat or $CAMAT_DIR (default: ../../camat_v2 next to
this repository).

Usage: python scripts/validate.py [mei/webern-op27-*.mei ...]
"""
from __future__ import annotations

import argparse
import collections
import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMA = REPO / "schemas" / "mei-CMN-5.1.rng"
RUNS = REPO / "validation" / "runs"
DEFAULT_FILES = [REPO / "mei" / f"webern-op27-{mvt}.mei" for mvt in ("I", "II", "III")]


def import_camat(checkout: Path):
    if importlib.util.find_spec("camat") is None:
        if not (checkout / "camat" / "mei_validation.py").is_file():
            raise SystemExit(f"CAMAT not installed and no checkout at {checkout}; pass --camat")
        sys.path.insert(0, str(checkout))
    from camat.mei_validation import run_mei_validation

    return run_mei_validation


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("files", nargs="*", type=Path, default=DEFAULT_FILES)
    parser.add_argument("--camat", type=Path,
                        default=Path(os.environ.get("CAMAT_DIR", REPO.parents[1] / "camat_v2")))
    parser.add_argument("--output-dir", type=Path,
                        help="run directory (default: validation/runs/<UTC timestamp>)")
    args = parser.parse_args(argv)

    if importlib.util.find_spec("saxonche") is None:
        raise SystemExit("saxonche is missing, so Schematron would be skipped; "
                         "install CAMAT's `validation` extra (or saxonche) first")
    run_mei_validation = import_camat(args.camat.resolve())
    output_dir = args.output_dir or RUNS / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    result = run_mei_validation(args.files, root=REPO, output_dir=output_dir, schema=SCHEMA,
                                check_verovio=True, check_camat_parse=True)
    record = result.record
    for name, entry in record["executions"].items():
        if entry.get("requested"):
            print(f"  {name:20} {entry['status']}")
    by_file = collections.Counter((Path(f.get("file") or "-").name, f.get("severity")) for f in result.findings)
    for (name, severity), count in sorted(by_file.items(), key=str):
        print(f"  {name}: {count} {severity}")
    print(f"findings: {len(result.findings)}; conformance: {record['conformance']}; "
          f"required checks: {record['required_checks_status']}; consumers: {record['consumer_diagnostics']}")
    print(f"run: {output_dir.relative_to(REPO) if output_dir.is_relative_to(REPO) else output_dir}")
    return 0 if result.passed and record["consumer_diagnostics"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
