#!/usr/bin/env python3
"""Incremental, resumable download → verify → encode pipeline.

Layout (a single working directory):

    work_dir/
        manifest.jsonl     # append-only event log (one JSON object per line)
        xml/<game_id>.xml  # raw paipu XML (verified by sha256)
        cache/             # token cache (schema v3); shards rebuilt on demand
            shard_*/...
            index.json

Manifest entries (most recent wins per game_id)::

    {"ts": "...", "gid": "...", "sha256": "...", "status": "downloaded",
     "size": 12345}
    {"ts": "...", "gid": "...", "sha256": "...", "status": "encoded",
     "shard": "shard_00007", "n_samples": 23}
    {"ts": "...", "gid": "...", "sha256": "...", "status": "failed",
     "error": "engine error: ..."}
    {"ts": "...", "gid": "...", "status": "evicted"}     # XML deleted

Pipeline guarantees
-------------------

* **Resumable** — every stage looks up its work in the manifest and only
  processes things that need processing.
* **Atomic per shard** — a paipu is marked ``encoded`` only after the
  shard containing it has been flushed to disk. A crash mid-shard
  loses no manifest entry but discards the in-memory buffer; affected
  paipus stay ``downloaded`` and will be re-encoded next run.
* **Sanity-check on every start** —
  - re-hash every XML on disk and compare to the manifest record;
    mismatched / missing / extra files are reported and (optionally)
    repaired.
  - the cache shard inventory is rebuilt from disk and compared to the
    manifest's claimed assignments; orphan shards / missing shards are
    reported.
* **Dedup** — the manifest's ``sha256`` set deduplicates by content
  (different Tenhou IDs that resolve to identical XML are folded into
  one canonical record). Rare but possible for re-uploaded games.

Subcommands
-----------

* ``run`` — full pipeline: ensure game-id list → download missing →
  encode missing. Add ``--game-ids PATH`` and/or ``--year YYYY`` to
  control sourcing.
* ``check`` — sanity check only; no downloads, no encoding.
* ``status`` — print a summary table.
* ``rebuild-index`` — rewrite the cache's ``index.json`` from
  ``manifest.jsonl``.

Examples::

    # First run for 2025; will fetch the year zip then download / encode 200 paipu
    python tools/paipu_pipeline.py run \\
        --work cache/houou-2025 --year 2025 --max-new 200 --delay 6

    # Resume the same job (will skip everything already done)
    python tools/paipu_pipeline.py run --work cache/houou-2025 --max-new 200

    # Sanity check
    python tools/paipu_pipeline.py check --work cache/houou-2025
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

# Make repo root importable
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import MahjongPyWrapper as pm  # type: ignore  # noqa: E402

from pymahjong import tenhou_paipu_check as tpc  # noqa: E402
from pymahjong.rl.cache import (  # noqa: E402
    CACHE_SCHEMA_VERSION,
    ShardWriter,
    rebuild_manifest,
)
from pymahjong.rl.dataset import SelfPlayImitationDataset  # noqa: E402
from pymahjong.rl.tokenization import MahjongTokenizer  # noqa: E402

# ---- import the year/xml helpers from the existing downloader -----------
from tools.download_tenhou_paipu import (  # noqa: E402
    LOG_URL,
    YEAR_ZIP_URL,
    _http_get,
    _http_stream,
    extract_game_ids_from_text,
)
import zipfile  # noqa: E402


def _fetch_xml(gid: str, target: Path, delay: float) -> Optional[bytes]:
    """Download a single Tenhou paipu XML and write it to ``target``.

    Returns the raw bytes on success, ``None`` on failure (an error
    message is printed to stderr).
    """
    url = LOG_URL.format(game_id=gid)
    try:
        data = _http_get(url, timeout=60.0)
    except Exception as exc:  # noqa: BLE001
        print(f"  ! download {gid}: {exc}", file=sys.stderr)
        return None
    if not data or not is_valid_paipu_payload(data):
        print(f"  ! suspicious payload for {gid} ({len(data) if data else 0} bytes)",
              file=sys.stderr)
        return None
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    if delay > 0:
        time.sleep(delay)
    return data


# =========================================================================
# Manifest layer
# =========================================================================

class Manifest:
    """Append-only manifest stored as JSONL.

    The in-memory representation is one dict per game_id, holding the
    *most recent* status. Reads scan the whole file (cheap; thousands
    of lines per minute).
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._records: Dict[str, dict] = {}
        self._sha_to_gid: Dict[str, str] = {}
        self._lock = threading.Lock()
        self._reload()

    def _reload(self) -> None:
        self._records.clear()
        self._sha_to_gid.clear()
        if not self.path.exists():
            return
        with self.path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                gid = rec.get("gid")
                if not gid:
                    continue
                self._records[gid] = rec
                if rec.get("status") in ("downloaded", "encoded") and rec.get("sha256"):
                    self._sha_to_gid[rec["sha256"]] = gid

    # --- read APIs -------------------------------------------------------
    def get(self, gid: str) -> Optional[dict]:
        with self._lock:
            return self._records.get(gid)

    def all_records(self) -> List[dict]:
        with self._lock:
            return list(self._records.values())

    def status_of(self, gid: str) -> Optional[str]:
        with self._lock:
            r = self._records.get(gid)
            return r.get("status") if r else None

    def is_done(self, gid: str) -> bool:
        return self.status_of(gid) in ("encoded", "failed", "evicted", "duplicate")

    def is_downloaded(self, gid: str, xml_dir: Optional[Path] = None) -> bool:
        if self.status_of(gid) == "downloaded":
            return True
        # Also check filesystem: if XML exists but wasn't in the manifest
        # snapshot yet, treat it as downloaded (avoids re-processing).
        if xml_dir is not None:
            return (xml_dir / f"{gid}.txt").exists()
        return False

    def gid_for_sha(self, sha: str) -> Optional[str]:
        with self._lock:
            return self._sha_to_gid.get(sha)

    # --- write APIs (always atomic-append + in-memory update) ------------
    def append(self, rec: dict) -> None:
        rec.setdefault("ts", dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
        line = json.dumps(rec, separators=(",", ":"), sort_keys=True)
        with self._lock:
            with open(self.path, "a") as f:
                f.write(line + "\n")
            gid = rec.get("gid")
            if gid:
                self._records[gid] = rec
                sha = rec.get("sha256")
                if sha and rec.get("status") in ("downloaded", "encoded"):
                    self._sha_to_gid[sha] = gid


# =========================================================================
# Hash helpers
# =========================================================================

def sha256_file(path: Path, _bs: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(_bs)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def is_valid_paipu_payload(data: bytes) -> bool:
    """Cheap structural check: a Tenhou paipu must contain ``<mjloggm`` near the top."""
    return b"<mjloggm" in data[:256]


# =========================================================================
# Sanity check
# =========================================================================

def sanity_check(work_dir: Path, repair: bool = False) -> dict:
    """Validate that on-disk state matches the manifest.

    Returns a summary dict. If ``repair=True``, deletes corrupt XMLs
    and emits manifest events to mark them as needing re-download.
    """
    xml_dir = work_dir / "xml"
    cache_dir = work_dir / "cache"
    man = Manifest(work_dir / "manifest.jsonl")

    on_disk_xmls: Dict[str, Path] = {}
    if xml_dir.exists():
        for p in xml_dir.glob("*.txt"):
            on_disk_xmls[p.stem] = p

    n_ok = 0
    corrupt: List[str] = []   # bad sha or bad payload
    missing: List[str] = []   # manifest says downloaded but file gone
    unknown: List[str] = []   # file present but no manifest record

    # Check every record claiming the XML exists
    for gid, rec in man._records.items():
        if rec.get("status") not in ("downloaded", "encoded"):
            continue
        p = on_disk_xmls.get(gid)
        if p is None:
            missing.append(gid)
            continue
        try:
            actual = sha256_file(p)
        except OSError:
            missing.append(gid)
            continue
        expected = rec.get("sha256")
        if expected and actual != expected:
            corrupt.append(gid)
        else:
            n_ok += 1
        on_disk_xmls.pop(gid, None)

    # Anything still on disk that the manifest doesn't know about
    for gid in on_disk_xmls:
        unknown.append(gid)

    # Optional repair: drop corrupt XML so next run re-downloads
    if repair:
        for gid in corrupt:
            p = (xml_dir / f"{gid}.txt")
            try:
                p.unlink()
            except OSError:
                pass
            man.append({"gid": gid, "status": "corrupt"})

    # Cache check: shards on disk vs. encoded entries in manifest
    encoded_per_shard: Dict[str, int] = {}
    for rec in man._records.values():
        if rec.get("status") == "encoded":
            sh = rec.get("shard")
            if sh:
                encoded_per_shard[sh] = encoded_per_shard.get(sh, 0) + int(rec.get("n_samples", 0))

    shard_dirs = []
    if cache_dir.exists():
        shard_dirs = sorted(p.name for p in cache_dir.glob("shard_*") if p.is_dir())
    shard_rows: Dict[str, int] = {}
    for name in shard_dirs:
        meta_p = cache_dir / name / "meta.json"
        if meta_p.exists():
            try:
                shard_rows[name] = int(json.loads(meta_p.read_text()).get("n_rows", 0))
            except Exception:  # noqa: BLE001
                shard_rows[name] = -1

    shard_mismatches = []
    for name, claimed in encoded_per_shard.items():
        actual = shard_rows.get(name)
        if actual is None or actual != claimed:
            shard_mismatches.append({"shard": name, "claimed": claimed, "actual": actual})
    orphan_shards = [n for n in shard_dirs if n not in encoded_per_shard]

    summary = {
        "manifest_records": len(man._records),
        "xmls_on_disk": len(on_disk_xmls) + n_ok + len(corrupt),
        "xmls_ok": n_ok,
        "xmls_corrupt": corrupt,
        "xmls_missing": missing,
        "xmls_unknown": unknown,
        "shards_on_disk": len(shard_dirs),
        "shard_rows": shard_rows,
        "shard_mismatches": shard_mismatches,
        "orphan_shards": orphan_shards,
    }
    return summary


def print_check_summary(s: dict) -> None:
    print("=" * 60)
    print(f"manifest records  : {s['manifest_records']}")
    print(f"xmls (ok)         : {s['xmls_ok']}")
    print(f"xmls (corrupt)    : {len(s['xmls_corrupt'])}  {s['xmls_corrupt'][:3]}")
    print(f"xmls (missing)    : {len(s['xmls_missing'])}  {s['xmls_missing'][:3]}")
    print(f"xmls (unknown)    : {len(s['xmls_unknown'])}  {s['xmls_unknown'][:3]}")
    print(f"shards on disk    : {s['shards_on_disk']}")
    print(f"shard mismatches  : {len(s['shard_mismatches'])}  {s['shard_mismatches'][:3]}")
    print(f"orphan shards     : {len(s['orphan_shards'])}  {s['orphan_shards'][:3]}")
    print("=" * 60)


# =========================================================================
# Game-ID sourcing
# =========================================================================

def ensure_year_ids(work_dir: Path, year: int, room_codes: Iterable[str] = ("00a9", "00e1")) -> Path:
    """Download the year zip if absent; emit a deduped game-id list."""
    out = work_dir / "ids"
    out.mkdir(parents=True, exist_ok=True)
    zip_path = out / f"scraw{year}.zip"
    if not zip_path.exists() or zip_path.stat().st_size < 1024:
        url = YEAR_ZIP_URL.format(year=year)
        print(f"  fetching {url}")
        _http_stream(url, zip_path)
    out_ids = out / f"game_ids_{year}.txt"
    if out_ids.exists() and out_ids.stat().st_size > 0:
        return out_ids
    print(f"  parsing {zip_path} ...")
    rcset = set(room_codes)
    all_ids: List[str] = []
    import gzip, io
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            if "scc" not in name.lower():
                continue
            with z.open(name) as fh:
                raw = fh.read()
            if name.endswith(".gz"):
                try:
                    text = gzip.decompress(raw).decode("utf-8", "replace")
                except Exception:  # noqa: BLE001
                    continue
            else:
                text = raw.decode("utf-8", "replace")
            all_ids.extend(extract_game_ids_from_text(text, rcset))
    all_ids = sorted(set(all_ids))
    out_ids.write_text("\n".join(all_ids) + "\n")
    print(f"  wrote {len(all_ids)} unique game IDs to {out_ids}")
    return out_ids


# =========================================================================
# Download + encode (async producer-consumer)
# =========================================================================

import queue
import sys
import threading

def puts(msg: str) -> None:
    """Thread-safe print to stdout (no buffering)."""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()

def stage_download_and_encode(
    work_dir: Path,
    man: Manifest,
    game_ids: List[str],
    delay: float,
    max_new: Optional[int],
    shard_rows: int,
    max_encode: Optional[int],
) -> Tuple[int, int, int, int, int, int]:
    """Producer (download thread) + Consumer (main thread) pipeline.

    Returns (n_done, n_skip, n_dedup, n_paipu, n_fail, n_samples).
    """
    xml_dir = work_dir / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)

    # Build todo list (mirrors stage_download logic)
    todo: List[str] = []
    n_skip = 0
    for gid in game_ids:
        if man.is_done(gid):
            n_skip += 1
            continue
        if man.is_downloaded(gid, xml_dir):
            n_skip += 1
            continue
        todo.append(gid)
    if max_new is not None:
        todo = todo[: max_new]

    puts(f"download+encode: {len(todo)} game-ids to fetch (skipping {n_skip} already done)")

    result_queue: queue.Queue = queue.Queue(maxsize=8)
    n_done = 0
    n_dedup = 0

    # --- Producer: download thread ---
    def download_worker():
        nonlocal n_done, n_dedup
        for gid in todo:
            target = xml_dir / f"{gid}.txt"
            if not target.exists():
                data = _fetch_xml(gid, target, delay)
                if data is None:
                    man.append({"gid": gid, "status": "failed", "error": "download failed"})
                    continue
            # Verify and dedup
            try:
                data = target.read_bytes()
            except OSError as e:
                man.append({"gid": gid, "status": "failed", "error": f"read: {e}"})
                continue
            if not is_valid_paipu_payload(data):
                try:
                    target.unlink()
                except OSError:
                    pass
                man.append({"gid": gid, "status": "failed", "error": "bad payload"})
                continue
            sha = hashlib.sha256(data).hexdigest()
            existing = man.gid_for_sha(sha)
            if existing and existing != gid:
                try:
                    target.unlink()
                except OSError:
                    pass
                man.append({"gid": gid, "status": "duplicate", "sha256": sha, "alias_of": existing})
                n_dedup += 1
                continue
            man.append({"gid": gid, "status": "downloaded", "sha256": sha, "size": len(data)})
            n_done += 1
            # Block if queue is full (back-pressure); consumer processes while we wait
            result_queue.put((gid, target))
        result_queue.put(None)  # sentinel: download done

    t = threading.Thread(target=download_worker, daemon=True)
    t.start()

    # --- Consumer: encode in main thread (avoids GIL issues with pybind11) ---
    cache_dir = work_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tokenizer = MahjongTokenizer()

    existing_shards = sorted(p.name for p in cache_dir.glob("shard_*") if p.is_dir())
    next_idx = 0
    if existing_shards:
        next_idx = max(int(n.split("_")[1]) for n in existing_shards) + 1

    n_paipu = 0
    n_fail = 0
    n_samples = 0
    buf_writer: Optional[ShardWriter] = None
    buf_assignments: List[Tuple[str, int]] = []
    buf_shard_name: Optional[str] = None

    def open_new_shard():
        nonlocal buf_writer, buf_shard_name, next_idx
        buf_shard_name = f"shard_{next_idx:05d}"
        next_idx += 1
        buf_writer = ShardWriter(str(cache_dir / buf_shard_name))

    def flush_shard():
        nonlocal buf_writer, buf_assignments, buf_shard_name
        if buf_writer is None or buf_writer.n_rows == 0:
            buf_writer = None
            buf_assignments = []
            buf_shard_name = None
            return
        entry = buf_writer.close()
        for gid, count in buf_assignments:
            man.append({
                "gid": gid,
                "sha256": (man.get(gid) or {}).get("sha256"),
                "status": "encoded",
                "shard": buf_shard_name,
                "n_samples": int(count),
            })
        puts(f"  flushed {buf_shard_name}: {entry.n_rows} rows, "
              f"{len(buf_assignments)} paipus")
        buf_writer = None
        buf_assignments = []
        buf_shard_name = None

    open_new_shard()

    try:
        consumed = 0

        while True:
            item = result_queue.get()  # blocks; sentinel unblocks
            if item is None:
                # Download thread finished; drain any remaining items
                while True:
                    try:
                        item = result_queue.get_nowait()
                        if item is None:
                            break
                    except queue.Empty:
                        break
                break

            gid, xml_path = item
            consumed += 1

            # Dynamically check manifest: only encode items with "downloaded" status.
            # Checking live (not a snapshot) ensures items downloaded by the worker
            # thread during this run are picked up immediately.
            if man.status_of(gid) != "downloaded":
                result_queue.task_done()
                continue

            if not xml_path.exists():
                man.append({"gid": gid, "status": "failed", "error": "xml missing"})
                n_fail += 1
                result_queue.task_done()
                continue
            try:
                samples = _encode_one_paipu(xml_path, tokenizer)
            except Exception as e:  # noqa: BLE001
                man.append({"gid": gid, "status": "failed", "error": f"replay: {e!r}"})
                n_fail += 1
                result_queue.task_done()
                continue
            if samples is None:
                man.append({"gid": gid, "status": "failed", "error": "unsupported game type"})
                n_fail += 1
                result_queue.task_done()
                continue
            if not samples:
                man.append({"gid": gid, "status": "failed", "error": "no samples"})
                n_fail += 1
                result_queue.task_done()
                continue
            for s in samples:
                buf_writer.add(s)
            buf_assignments.append((gid, len(samples)))
            n_paipu += 1
            n_samples += len(samples)
            if buf_writer.n_rows >= shard_rows:
                flush_shard()
                open_new_shard()
            result_queue.task_done()

            if consumed % 25 == 0:
                puts(f"  [consumed={consumed}] paipu={n_paipu} samples={n_samples} fail={n_fail}")
        flush_shard()
    finally:
        if buf_writer is not None and buf_writer.n_rows > 0:
            flush_shard()

    t.join()
    return n_done, n_skip, n_dedup, n_paipu, n_fail, n_samples


# =========================================================================
# Download stage (standalone, kept for compatibility / --dry-run use)
# =========================================================================

def stage_download(
    work_dir: Path,
    man: Manifest,
    game_ids: List[str],
    delay: float,
    max_new: Optional[int],
) -> Tuple[int, int, int]:
    """Download missing XMLs. Returns (downloaded, skipped_done, dedup_hits)."""
    xml_dir = work_dir / "xml"
    xml_dir.mkdir(parents=True, exist_ok=True)
    n_done = n_skip = n_dedup = 0
    todo = []
    for gid in game_ids:
        if man.is_done(gid):
            n_skip += 1
            continue
        if man.is_downloaded(gid):
            n_skip += 1
            continue
        todo.append(gid)
    if max_new is not None:
        todo = todo[: max_new]
    print(f"download: {len(todo)} game-ids to fetch (skipping {n_skip} already done)")
    for i, gid in enumerate(todo, 1):
        target = xml_dir / f"{gid}.txt"
        if not target.exists():
            data = _fetch_xml(gid, target, delay)
            if data is None:
                man.append({"gid": gid, "status": "failed", "error": "download failed"})
                continue
        # Compute hash, check structural validity, dedup
        try:
            data = target.read_bytes()
        except OSError as e:
            man.append({"gid": gid, "status": "failed", "error": f"read: {e}"})
            continue
        if not is_valid_paipu_payload(data):
            try:
                target.unlink()
            except OSError:
                pass
            man.append({"gid": gid, "status": "failed", "error": "bad payload"})
            continue
        sha = hashlib.sha256(data).hexdigest()
        existing = man.gid_for_sha(sha)
        if existing and existing != gid:
            # Duplicate XML body under a different game id
            try:
                target.unlink()
            except OSError:
                pass
            man.append({
                "gid": gid, "status": "duplicate", "sha256": sha, "alias_of": existing,
            })
            n_dedup += 1
            continue
        man.append({
            "gid": gid, "status": "downloaded", "sha256": sha, "size": len(data),
        })
        n_done += 1
        if i % 20 == 0 or i == len(todo):
            puts(f"  [{i}/{len(todo)}] downloaded={n_done} dedup={n_dedup}")
    return n_done, n_skip, n_dedup


# =========================================================================
# Encode stage
# =========================================================================

def _unsupported_game_type(xml_path: Path) -> bool:
    """Return True if this XML's GO type is unsupported by the encoder.

    Unsupported types (mirrors PaipuReplay GO handler breaks):
      - is_pro=0  (bit 5 = 0): 上级卓 / 非プロ雀庄
      - is_3ma=1  (bit 4 = 1): 三人麻将
      - is_fast=1 (bit 6 = 1): 速卓

    Note: is_fast=1 causes PaipuReplay to break before the replayer is
    initialized, so make_selection is never called and 0 samples are
    produced. The error message would be "no samples" without this filter.

    Parses the full XML tree (games are only a few KB — negligible cost).
    """
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(str(xml_path))
        for elem in tree.getroot():
            if elem.tag == "GO":
                t = int(elem.get("type", "0"))
                # bit 5 (0x20): is_pro — must be 1
                # bit 4 (0x10): is_3ma — must be 0
                # bit 6 (0x40): is_fast — must be 0
                if t & 0x20 == 0 or t & 0x10 != 0 or t & 0x40 != 0:
                    return True
                return False
            if elem.tag not in ("SHUFFLE",):
                # GO appears after SHUFFLE; stop early
                break
        return False
    except Exception:  # noqa: BLE001
        return False


def _encode_one_paipu(
    xml_path: Path, tokenizer: MahjongTokenizer
) -> Optional[List[dict]]:
    """Replay one paipu and return a list of token samples.

    Returns None when the game type is unsupported (caller should mark
    ``error="unsupported game type"``). Returns an empty list when the
    replay ran but produced no samples (caller should mark
    ``error="no samples"``).
    """
    if _unsupported_game_type(xml_path):
        return None

    samples: List[dict] = []

    class _Proxy:
        __slots__ = ("_inner",)
        def __init__(self, inner): object.__setattr__(self, "_inner", inner)
        def __getattr__(self, name): return getattr(self._inner, name)
        def make_selection(self, idx):
            t = self._inner.table
            phase = int(t.get_phase())
            if phase < 16:
                actions = (
                    t.get_self_actions() if phase < 4
                    else t.get_response_actions()
                )
                if len(actions) > 1:
                    seat = phase % 4
                    try:
                        tok = tokenizer.encode(t, current_player=seat)
                        unified = SelfPlayImitationDataset._engine_idx_to_unified(t, idx)
                        samples.append({
                            "tokens": tok.tokens.copy(),
                            "scalars": tok.scalars.copy(),
                            "attention_mask": tok.attention_mask.copy(),
                            "action_mask": tok.action_mask.copy(),
                            "action": int(unified),
                        })
                    except Exception:  # noqa: BLE001
                        pass
            return self._inner.make_selection(idx)

    orig_ctor = pm.PaipuReplayer
    pm.PaipuReplayer = lambda *a, **kw: _Proxy(orig_ctor(*a, **kw))  # type: ignore[assignment]
    try:
        replay = tpc.PaipuReplay()
        replay.logger = tpc.Logger()
        replay.write_log = False
        replay._paipu_replay(str(xml_path.parent), xml_path.name)
    finally:
        pm.PaipuReplayer = orig_ctor  # type: ignore[assignment]
    return samples


def stage_encode(
    work_dir: Path,
    man: Manifest,
    shard_rows: int = 4096,
    max_paipu: Optional[int] = None,
) -> Tuple[int, int, int]:
    """Encode every ``downloaded`` paipu still missing from the cache.

    Returns ``(paipus_encoded, paipus_failed, total_samples)``.
    """
    xml_dir = work_dir / "xml"
    cache_dir = work_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    tokenizer = MahjongTokenizer()

    # Find next shard index that is free on disk
    existing_shards = sorted(p.name for p in cache_dir.glob("shard_*") if p.is_dir())
    next_idx = 0
    if existing_shards:
        next_idx = max(int(n.split("_")[1]) for n in existing_shards) + 1

    todo = [gid for gid, rec in man._records.items() if rec.get("status") == "downloaded"]
    todo.sort()
    if max_paipu is not None:
        todo = todo[: max_paipu]
    print(f"encode: {len(todo)} paipu to process; next shard index = {next_idx:05d}")

    n_paipu = 0
    n_fail = 0
    n_samples = 0

    # In-memory list per current shard; we map (paipu_gid -> count) so we
    # can write a manifest "encoded" record for each gid only once the
    # shard has been flushed.
    buf_writer: Optional[ShardWriter] = None
    buf_assignments: List[Tuple[str, int]] = []  # (gid, n_samples)
    buf_shard_name: Optional[str] = None

    def open_new_shard():
        nonlocal buf_writer, buf_shard_name, next_idx
        buf_shard_name = f"shard_{next_idx:05d}"
        next_idx += 1
        buf_writer = ShardWriter(str(cache_dir / buf_shard_name))

    def flush_shard():
        nonlocal buf_writer, buf_assignments, buf_shard_name
        if buf_writer is None or buf_writer.n_rows == 0:
            buf_writer = None
            buf_assignments = []
            buf_shard_name = None
            return
        entry = buf_writer.close()
        # Persist per-paipu manifest entries
        for gid, count in buf_assignments:
            man.append({
                "gid": gid,
                "sha256": (man.get(gid) or {}).get("sha256"),
                "status": "encoded",
                "shard": buf_shard_name,
                "n_samples": int(count),
            })
        puts(f"  flushed {buf_shard_name}: {entry.n_rows} rows, "
              f"{len(buf_assignments)} paipus")
        buf_writer = None
        buf_assignments = []
        buf_shard_name = None

    open_new_shard()
    try:
        for i, gid in enumerate(todo, 1):
            xml = xml_dir / f"{gid}.txt"
            if not xml.exists():
                man.append({"gid": gid, "status": "failed", "error": "xml missing"})
                n_fail += 1
                continue
            try:
                samples = _encode_one_paipu(xml, tokenizer)
            except Exception as e:  # noqa: BLE001
                man.append({"gid": gid, "status": "failed", "error": f"replay: {e!r}"})
                n_fail += 1
                continue
            if samples is None:
                man.append({"gid": gid, "status": "failed", "error": "unsupported game type"})
                n_fail += 1
                continue
            if not samples:
                man.append({"gid": gid, "status": "failed", "error": "no samples"})
                n_fail += 1
                continue
            for s in samples:
                buf_writer.add(s)
            buf_assignments.append((gid, len(samples)))
            n_paipu += 1
            n_samples += len(samples)
            if buf_writer.n_rows >= shard_rows:
                flush_shard()
                open_new_shard()
            if i % 25 == 0 or i == len(todo):
                puts(f"  [{i}/{len(todo)}] paipu={n_paipu} samples={n_samples} fail={n_fail}")
        flush_shard()
    finally:
        # On exception we still flush whatever was already encoded so we
        # don't lose work; uncommitted buffer simply re-runs next time.
        if buf_writer is not None and buf_writer.n_rows > 0:
            flush_shard()

    return n_paipu, n_fail, n_samples


# =========================================================================
# Index rebuild
# =========================================================================

def cmd_rebuild_index(work_dir: Path) -> int:
    cache_dir = work_dir / "cache"
    if not cache_dir.exists():
        print(f"no cache dir at {cache_dir}", file=sys.stderr)
        return 2
    m = rebuild_manifest(str(cache_dir))
    print(f"index rebuilt: {m.total_rows} rows across {len(m.shards)} shards")
    return 0


# =========================================================================
# Top-level orchestrator
# =========================================================================

def adopt_unknown_xmls(work_dir: Path, man: Manifest) -> int:
    """Pick up XMLs dropped into the xml/ dir that have no manifest record.

    Computes the sha, dedups against existing records, and emits a
    ``downloaded`` event so the encode stage will process them. Returns
    the number of XMLs adopted.
    """
    xml_dir = work_dir / "xml"
    if not xml_dir.exists():
        return 0
    n = 0
    for p in xml_dir.glob("*.txt"):
        gid = p.stem
        rec = man.get(gid)
        if rec and rec.get("status") not in (None, "corrupt", "failed"):
            continue
        try:
            data = p.read_bytes()
        except OSError:
            continue
        if not is_valid_paipu_payload(data):
            try:
                p.unlink()
            except OSError:
                pass
            man.append({"gid": gid, "status": "failed", "error": "bad payload (adopted)"})
            continue
        sha = hashlib.sha256(data).hexdigest()
        existing = man.gid_for_sha(sha)
        if existing and existing != gid:
            try:
                p.unlink()
            except OSError:
                pass
            man.append({
                "gid": gid, "status": "duplicate", "sha256": sha, "alias_of": existing,
            })
            continue
        man.append({"gid": gid, "status": "downloaded", "sha256": sha, "size": len(data)})
        n += 1
    return n


def cmd_run(args) -> int:
    work_dir = Path(args.work).resolve()
    work_dir.mkdir(parents=True, exist_ok=True)

    print(f">>> sanity check on {work_dir}")
    s = sanity_check(work_dir, repair=args.repair)
    print_check_summary(s)
    if s["xmls_corrupt"] and not args.repair:
        print("There are corrupt XMLs. Re-run with --repair to drop them and re-download.",
              file=sys.stderr)
        return 1

    man = Manifest(work_dir / "manifest.jsonl")

    # Pick up XMLs dropped in by hand (e.g. migrated from another pipeline)
    n_adopted = adopt_unknown_xmls(work_dir, man)
    if n_adopted:
        print(f"adopted {n_adopted} unknown XML(s) into the manifest")

    # Game-id sourcing
    if args.game_ids:
        ids = [ln.strip() for ln in Path(args.game_ids).read_text().splitlines() if ln.strip()]
    elif args.year:
        idfile = ensure_year_ids(work_dir, args.year)
        ids = [ln.strip() for ln in idfile.read_text().splitlines() if ln.strip()]
    else:
        # Encode-only mode: just process whatever is already downloaded
        ids = []

    # Download + encode concurrently (single producer, single consumer)
    n_done, n_skip, n_dedup, n_paipu, n_fail, n_samples = stage_download_and_encode(
        work_dir, man, ids, delay=args.delay, max_new=args.max_new,
        shard_rows=args.shard_rows, max_encode=args.max_encode
    )
    print(f"download summary: new={n_done} dedup={n_dedup} skipped={n_skip}")
    print(f"encode summary  : paipu={n_paipu} fail={n_fail} samples={n_samples}")

    # Rebuild cache index
    if (work_dir / "cache").exists():
        rebuild_manifest(str(work_dir / "cache"))
        print(f"cache index rebuilt at {work_dir / 'cache' / 'index.json'}")

    return 0


def cmd_check(args) -> int:
    work_dir = Path(args.work).resolve()
    s = sanity_check(work_dir, repair=args.repair)
    print_check_summary(s)
    bad = (len(s["xmls_corrupt"]) + len(s["xmls_missing"])
           + len(s["shard_mismatches"]) + len(s["orphan_shards"]))
    return 0 if bad == 0 else 1


def cmd_status(args) -> int:
    work_dir = Path(args.work).resolve()
    man = Manifest(work_dir / "manifest.jsonl")
    counts: Dict[str, int] = {}
    for r in man._records.values():
        s = r.get("status", "?")
        counts[s] = counts.get(s, 0) + 1
    total_samples = sum(int(r.get("n_samples", 0)) for r in man._records.values()
                        if r.get("status") == "encoded")
    print(f"work dir : {work_dir}")
    for k in sorted(counts):
        print(f"  {k:12s}: {counts[k]}")
    print(f"  encoded samples: {total_samples}")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    from pymahjong.config import get_config
    cfg = get_config()
    _default_game_ids = (cfg.paipu_game_ids or [None])[0]

    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="full incremental pipeline")
    pr.add_argument("--work", required=True, help="working directory")
    pr.add_argument("--year", type=int, default=None,
                    help="source: download/parse the scraw<YEAR>.zip and use its game IDs")
    pr.add_argument("--game-ids", default=_default_game_ids,
                    help="source: a text file with one game ID per line (overrides --year)")
    pr.add_argument("--delay", type=float, default=5.0,
                    help="seconds between Tenhou XML downloads (default 5)")
    pr.add_argument("--max-new", type=int, default=None,
                    help="cap on number of NEW downloads this run")
    pr.add_argument("--max-encode", type=int, default=None,
                    help="cap on number of paipus to encode this run")
    pr.add_argument("--shard-rows", type=int, default=4096)
    pr.add_argument("--repair", action="store_true",
                    help="auto-delete corrupt XMLs and re-mark them for download")
    pr.set_defaults(func=cmd_run)

    pc = sub.add_parser("check", help="sanity check only")
    pc.add_argument("--work", required=True)
    pc.add_argument("--repair", action="store_true")
    pc.set_defaults(func=cmd_check)

    ps = sub.add_parser("status", help="print manifest summary")
    ps.add_argument("--work", required=True)
    ps.set_defaults(func=cmd_status)

    pri = sub.add_parser("rebuild-index", help="rewrite cache/index.json from shards")
    pri.add_argument("--work", required=True)
    pri.set_defaults(func=lambda a: cmd_rebuild_index(Path(a.work).resolve()))

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
