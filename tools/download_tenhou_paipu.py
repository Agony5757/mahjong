#!/usr/bin/env python3
"""Download Tenhou Houou (鳳凰桌) paipu logs.

Three modes:

1. **Year archive** (recommended, fast): download a single
   ``scrawYYYY.zip`` (~450MB / year) which contains every daily summary
   file. We unzip it, parse all ``scc*`` files for Houou game IDs and
   write a deduped ID list. This is the same data the user-facing
   ``過去ログ`` link on https://tenhou.net/sc/raw/ provides.

2. **Hourly summaries** (fine-grained): download individual
   ``sca/scb/scc*.html.gz`` files for a date range.

3. **XML logs** (slow, throttled): given a game-ID list, fetch each
   game's XML from ``https://tenhou.net/0/log/?<id>``. Tenhou throttles
   raw-log access (~1 req / 5 s); use ``--xml-delay 6`` to stay safe.

Examples
--------

Bulk-download all 2025 Houou game IDs:

    python3 tools/download_tenhou_paipu.py year 2025 --out paipuxmls/houou

Download only daily summaries from 2025-04-01 to 2025-05-01:

    python3 tools/download_tenhou_paipu.py daily \
        --since 2025-04-01 --until 2025-05-01 --out paipuxmls/houou

Then optionally fetch XML logs (slow):

    python3 tools/download_tenhou_paipu.py xml \
        --ids paipuxmls/houou/game_ids.txt --max 100 --out paipuxmls/houou
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import io
import os
import re
import sys
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable, List, Optional, Set


LIST_URL = "https://tenhou.net/sc/raw/list.cgi"
ARCHIVE_URL = "https://tenhou.net/sc/raw/dat/{name}"
YEAR_ZIP_URL = "https://tenhou.net/sc/raw/scraw{year}.zip"
LOG_URL = "https://tenhou.net/0/log/?{game_id}"

USER_AGENT = "Mozilla/5.0 (pymahjong-rl-downloader)"


def _http_get(url: str, timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _http_stream(url: str, dest: Path, timeout: float = 600.0, chunk: int = 1 << 20):
    """Streaming download with simple progress report."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=timeout) as r, open(tmp, "wb") as fh:
        total = int(r.headers.get("Content-Length", "0") or 0)
        downloaded = 0
        last = time.monotonic()
        while True:
            buf = r.read(chunk)
            if not buf:
                break
            fh.write(buf)
            downloaded += len(buf)
            now = time.monotonic()
            if now - last > 2.0 or (total and downloaded == total):
                pct = (downloaded / total * 100.0) if total else 0.0
                sys.stderr.write(
                    f"\r  {dest.name}: {downloaded/1e6:7.1f}MB"
                    + (f" / {total/1e6:.1f}MB ({pct:5.1f}%)" if total else "")
                )
                sys.stderr.flush()
                last = now
    sys.stderr.write("\n")
    tmp.rename(dest)


# ---------------------------------------------------------------------------
# Game-ID extraction
# ---------------------------------------------------------------------------

_GAME_RE = re.compile(r"log=(\d{10}gm-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]+)")


def extract_game_ids_from_text(text: str, room_codes: Set[str]) -> List[str]:
    out = []
    for gid in _GAME_RE.findall(text):
        m = re.match(r"\d{10}gm-([0-9a-f]{4})-", gid)
        if m and (not room_codes or m.group(1) in room_codes):
            out.append(gid)
    return out


def extract_game_ids_from_gz(path: Path, room_codes: Set[str]) -> List[str]:
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        return extract_game_ids_from_text(fh.read(), room_codes)


# ---------------------------------------------------------------------------
# Mode: year archive
# ---------------------------------------------------------------------------


def cmd_year(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    room_codes = {s.strip() for s in args.room_codes.split(",") if s.strip()}

    all_ids: List[str] = []
    summary_dir = out / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    for year in args.years:
        zip_path = out / f"scraw{year}.zip"
        if not zip_path.exists() or args.force:
            url = YEAR_ZIP_URL.format(year=year)
            print(f"Downloading {url} -> {zip_path}")
            _http_stream(url, zip_path)
        else:
            print(f"Cached: {zip_path}")

        print(f"  parsing {zip_path}...")
        with zipfile.ZipFile(zip_path) as zf:
            members = [m for m in zf.namelist() if "/scc" in m or m.startswith("scc")]
            print(f"  {len(members)} scc summary files")
            for m in members:
                with zf.open(m) as fh:
                    raw = fh.read()
                # member is itself .html.gz
                if m.endswith(".gz"):
                    try:
                        text = gzip.decompress(raw).decode("utf-8", "replace")
                    except OSError:
                        continue
                elif m.endswith(".html"):
                    text = raw.decode("utf-8", "replace")
                else:
                    continue
                all_ids.extend(extract_game_ids_from_text(text, room_codes))
                if args.keep_summary:
                    (summary_dir / Path(m).name).write_bytes(raw)

    all_ids = sorted(set(all_ids))
    out_file = out / "game_ids.txt"
    out_file.write_text("\n".join(all_ids) + "\n")
    print(f"Wrote {len(all_ids)} unique game IDs (rooms={room_codes}) to {out_file}")


# ---------------------------------------------------------------------------
# Mode: daily / hourly summaries
# ---------------------------------------------------------------------------


def fetch_index() -> List[dict]:
    raw = _http_get(LIST_URL).decode("utf-8", "replace")
    items = re.findall(r"\{file:'([^']+)',size:(\d+)\}", raw)
    return [{"file": f, "size": int(s)} for f, s in items]


def parse_filename_date(name: str) -> dt.date | None:
    m = re.match(r"sc[abcde](\d{8})", name)
    if not m:
        return None
    s = m.group(1)
    try:
        return dt.date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    except ValueError:
        return None


def cmd_daily(args):
    out = Path(args.out)
    summary_dir = out / "summary"
    summary_dir.mkdir(parents=True, exist_ok=True)

    print(f"Fetching index from {LIST_URL}")
    index = fetch_index()
    prefixes = tuple(s.strip() for s in args.summary_prefixes.split(",") if s.strip())
    files = []
    for entry in index:
        name = entry["file"]
        if not any(name.startswith(p) for p in prefixes):
            continue
        d = parse_filename_date(name)
        if d is None or d < args.since or d > args.until:
            continue
        files.append(name)
    print(f"Selected {len(files)} archives, {args.since} .. {args.until}")

    room_codes = {s.strip() for s in args.room_codes.split(",") if s.strip()}
    all_ids: List[str] = []
    for i, name in enumerate(files, 1):
        target = summary_dir / name
        if not target.exists() or args.force:
            data = _http_get(ARCHIVE_URL.format(name=name))
            target.write_bytes(data)
        all_ids.extend(extract_game_ids_from_gz(target, room_codes))
        if i % 24 == 0 or i == len(files):
            print(f"  [{i}/{len(files)}] cumulative game IDs: {len(all_ids)}")

    all_ids = sorted(set(all_ids))
    (out / "game_ids.txt").write_text("\n".join(all_ids) + "\n")
    print(f"Wrote {len(all_ids)} unique game IDs to {out/'game_ids.txt'}")


# ---------------------------------------------------------------------------
# Mode: XML logs
# ---------------------------------------------------------------------------


def download_xml(game_id: str, out_dir: Path, delay: float, force: bool = False) -> bool:
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{game_id}.txt"
    if target.exists() and not force and target.stat().st_size > 0:
        return False
    url = LOG_URL.format(game_id=game_id)
    try:
        data = _http_get(url, timeout=60.0)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! failed: {game_id}: {exc}", file=sys.stderr)
        return False
    if not data or b"<mjloggm" not in data[:200]:
        print(f"  ! suspicious payload for {game_id} ({len(data)} bytes)", file=sys.stderr)
        return False
    target.write_bytes(data)
    time.sleep(delay)
    return True


def cmd_xml(args):
    ids = [ln.strip() for ln in Path(args.ids).read_text().splitlines() if ln.strip()]

    # Filter out unsupported room codes (e.g. 00e1=fast table, 00b9=3-player).
    if args.room_codes:
        allowed = set(args.room_codes.split(","))
        filtered = []
        for gid in ids:
            m = re.match(r"\d{10}gm-([0-9a-f]{4})-", gid)
            if m and m.group(1) not in allowed:
                continue
            filtered.append(gid)
        n_filtered = len(ids) - len(filtered)
        ids = filtered
        if n_filtered:
            print(f"Filtered {n_filtered} IDs with unsupported room codes")

    if args.max > 0:
        ids = ids[: args.max]
    xml_dir = Path(args.out)
    print(f"Stage XML: downloading {len(ids)} logs (delay={args.delay}s)")
    n_done = 0
    n_skip = 0
    for i, gid in enumerate(ids, 1):
        if download_xml(gid, xml_dir, args.delay, force=args.force):
            n_done += 1
        else:
            n_skip += 1
        if i % 10 == 0 or i == len(ids):
            print(f"  [{i}/{len(ids)}] downloaded={n_done} skipped={n_skip}")
    print(f"Done. {n_done} fresh, {n_skip} skipped in {xml_dir}.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    # Resolve config defaults
    _here = os.path.dirname(os.path.abspath(__file__))
    _root = os.path.dirname(_here)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from pymahjong.config import get_config
    cfg = get_config()
    _xml_path = cfg.paipu_xml_path
    _default_xml_out = _xml_path or "paipuxmls/houou"
    # year/daily write game_ids.txt to parent of xml dir
    _default_workspace = str(Path(_xml_path).parent) if _xml_path else "paipuxmls/houou"
    _default_ids = (cfg.paipu_game_ids or [None])[0]

    # year
    py = sub.add_parser("year", help="bulk-download year archive(s)")
    py.add_argument("years", type=int, nargs="+", help="year(s) to download (e.g. 2024 2025)")
    py.add_argument("--out", default=_default_workspace)
    py.add_argument("--room-codes", default="00a9,00e1",
                    help="comma-separated 4-char room codes; empty=all (default: 4p houou hanchan + tonpu)")
    py.add_argument("--keep-summary", action="store_true",
                    help="also extract scc files into <out>/summary/")
    py.add_argument("--force", action="store_true")
    py.set_defaults(func=cmd_year)

    # daily
    today = dt.date.today()
    pd = sub.add_parser("daily", help="download per-day summary files via the live index")
    pd.add_argument("--since", type=lambda s: dt.date.fromisoformat(s), default=today - dt.timedelta(days=7))
    pd.add_argument("--until", type=lambda s: dt.date.fromisoformat(s), default=today)
    pd.add_argument("--out", default=_default_workspace)
    pd.add_argument("--summary-prefixes", default="scc")
    pd.add_argument("--room-codes", default="00a9,00e1")
    pd.add_argument("--force", action="store_true")
    pd.set_defaults(func=cmd_daily)

    # xml
    px = sub.add_parser("xml", help="download XML game logs given an ID list")
    px.add_argument("--ids", default=_default_ids, help="path to game_ids.txt")
    px.add_argument("--out", default=_default_xml_out)
    px.add_argument("--room-codes", default="00a9",
                    help="comma-separated room codes to keep; empty=accept all (default: 00a9 only)")
    px.add_argument("--max", type=int, default=0)
    px.add_argument("--delay", type=float, default=6.0)
    px.add_argument("--force", action="store_true")
    px.set_defaults(func=cmd_xml)

    args = p.parse_args(argv)
    if args.cmd == "xml" and args.ids is None:
        p.error("--ids is required (no game_ids path in config)")
    args.func(args)


if __name__ == "__main__":
    main()

