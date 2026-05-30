#!/usr/bin/env python3
"""Convert a Tenhou XML paipu into Tenhou-JSON paipu-editor URLs / files.

Reads an XML paipu (produced by :class:`TenhouPaipuRecorder` or any other
source emitting the same tag set) and writes:

* A JSON file consumable by the Tenhou paipu editor / amae-koromo viewer
  (with ``--out-json``).
* **One URL per hand (kyoku)**, printed to stdout (or to a file with
  ``--out-url``).  Each URL contains exactly one kyoku — never a whole
  hanchan — so URLs stay short enough to share.

Examples::

    # Per-hand URLs for a 10-kyoku paipu, one URL per line on stdout.
    python tools/paipu_to_tenhou_url.py logs/bc_selfplay_20260527.xml

    # Same, saved to a file.
    python tools/paipu_to_tenhou_url.py logs/bc_selfplay_20260527.xml \\
        --out-url logs/bc_selfplay_20260527.urls.txt

    # Just dump the JSON (no URL), pretty-printed.
    python tools/paipu_to_tenhou_url.py logs/bc_selfplay_20260527.xml \\
        --out-json logs/bc_selfplay_20260527.json --pretty
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pymahjong.paipu_tenhou_json import (
    make_per_hand_urls,
    save_tenhou_json,
    xml_to_tenhou_json,
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("xml", type=Path,
                    help="Input XML paipu file.")
    ap.add_argument("--out-json", type=Path, default=None,
                    help="Optional output path for the Tenhou-JSON paipu.")
    ap.add_argument("--out-url", type=Path, default=None,
                    help="Optional file to write URLs to (one URL per line, "
                         "one per kyoku).")
    ap.add_argument("--max-hands", type=int, default=0,
                    help="Truncate to the first N hands.  0 = no truncation.")
    ap.add_argument("--title", default="pymahjong paipu",
                    help="Title shown in the editor.")
    ap.add_argument("--subtitle", default="",
                    help="Subtitle shown in the editor.")
    ap.add_argument("--rule-disp", default="般東",
                    help="Display string for the 'rule.disp' field.")
    ap.add_argument("--no-aka", action="store_true",
                    help="Mark the paipu as no-red-dora (rule.aka=0).")
    ap.add_argument("--pretty", action="store_true",
                    help="Pretty-print the JSON output file.  Has no "
                         "effect on URLs (always compact).")
    ap.add_argument("--base-url", default="https://tenhou.net/5/",
                    help="Base URL for the paipu editor.  Default is the "
                         "Tenhou JSON viewer/editor entry point.")
    args = ap.parse_args()

    if not args.xml.exists():
        print(f"ERROR: input file {args.xml} not found", file=sys.stderr)
        return 2

    data = xml_to_tenhou_json(
        str(args.xml),
        title=(args.title, args.subtitle),
        rule_disp=args.rule_disp,
        aka_dora=not args.no_aka,
    )
    n_total = len(data["log"])
    if args.max_hands > 0:
        data["log"] = data["log"][:args.max_hands]
    n_used = len(data["log"])
    print(f"loaded {n_total} hands from {args.xml}; using {n_used}", file=sys.stderr)

    if args.out_json:
        save_tenhou_json(data, str(args.out_json), pretty=args.pretty)
        print(f"wrote JSON to {args.out_json} "
              f"({args.out_json.stat().st_size:,} bytes)", file=sys.stderr)

    # URL emission — always per-kyoku, one per line.
    urls = make_per_hand_urls(data, base=args.base_url)
    text = "\n".join(urls)

    if args.out_url:
        args.out_url.parent.mkdir(parents=True, exist_ok=True)
        args.out_url.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {len(urls)} URL(s) to {args.out_url}", file=sys.stderr)
    else:
        # Print to stdout (URLs only — no extra noise so it can be piped).
        print(text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
