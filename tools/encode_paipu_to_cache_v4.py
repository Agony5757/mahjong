#!/usr/bin/env python3
"""Encode Tenhou paipu XML logs into a V4 (event-stream) shard cache.

This is the V4 counterpart of ``tools/encode_paipu_to_cache.py`` (which
only emits V3 token caches). It uses :func:`encode_paipu_file_v4` to
walk each XML, extract per-decision-point V4 samples, and stream them
into :class:`pymahjong.rl.v4.cache.V4ShardWriter` shards.

Output layout (read by :class:`pymahjong.rl.v4.cached_dataset.CachedEventDataset`)::

    <out>/index.json            <- CacheManifest (schema_version=1, event_dim=100)
    <out>/shard_w00_00000/
        features.packbits.npy   <- packed bool (concat of per-sample events)
        lengths.npy             <- int32, per-sample event count
        action_mask.packbits.npy
        labels.npy              <- int16, unified action index
        track_ids.npy           <- int64
        meta.json

Example::

    python tools/encode_paipu_to_cache_v4.py \\
        --paipu-dir cache/houou-2025/xml \\
        --out cache/houou-v4 \\
        --workers 16 --shard-rows 32768
"""
from __future__ import annotations

import argparse
import glob
import json
import multiprocessing as mp
import os
import sys
import time
from typing import List, Optional

# Make the in-tree package importable when running the script directly.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from pymahjong.rl.v4.cache import (  # noqa: E402
    CacheManifest,
    ShardEntry,
    V4ShardWriter,
    save_manifest,
    schema_fingerprint,
)


def _split_evenly(items: List, n: int) -> List[List]:
    return [items[i::n] for i in range(n)]


def _worker_main(args_dict: dict) -> List[dict]:
    """Encode a chunk of paipu XMLs into one or more V4 shards."""
    out_dir = args_dict["out_dir"]
    worker_id = args_dict["worker_id"]
    shard_rows = args_dict["shard_rows"]
    paths: List[str] = args_dict["paths"]
    pts = args_dict.get("pts")  # offline-RL placement points, or None for BC-only

    # Lazy import so workers don't pay the cost in the parent.
    from pymahjong.rl.v4.tokenization import encode_paipu_file_v4

    entries: List[dict] = []
    shard_idx = 0
    writer: Optional[V4ShardWriter] = None
    t0 = time.time()
    n_total = 0
    n_files = 0
    n_skipped = 0

    def _open_shard(idx: int) -> V4ShardWriter:
        path = os.path.join(out_dir, f"shard_w{worker_id:02d}_{idx:05d}")
        return V4ShardWriter(path)

    writer = _open_shard(shard_idx)
    for fp in paths:
        n_files += 1
        try:
            samples = encode_paipu_file_v4(fp, pts=pts)
        except Exception as e:  # noqa: BLE001
            n_skipped += 1
            if n_skipped <= 5:
                print(f"[worker {worker_id}] skip {os.path.basename(fp)}: {e}",
                      flush=True)
            continue
        if samples is None:
            n_skipped += 1
            continue
        for sample in samples:
            writer.add(sample)
            n_total += 1
            if writer.n_rows >= shard_rows:
                entry = writer.close()
                entries.append({
                    "path": entry.path,
                    "n_rows": entry.n_rows,
                })
                shard_idx += 1
                writer = _open_shard(shard_idx)

        if n_files % 200 == 0:
            elapsed = time.time() - t0
            print(
                f"[worker {worker_id}] {n_files}/{len(paths)} files, "
                f"{n_total} samples, {n_skipped} skipped, "
                f"{n_files / max(elapsed, 1e-6):.1f} files/s",
                flush=True,
            )

    if writer is not None and writer.n_rows > 0:
        entry = writer.close()
        entries.append({"path": entry.path, "n_rows": entry.n_rows})

    elapsed = time.time() - t0
    print(
        f"[worker {worker_id}] DONE: {n_files} files, {n_total} samples, "
        f"{n_skipped} skipped, {len(entries)} shards, {elapsed:.1f}s",
        flush=True,
    )
    return entries


def cmd_encode(args: argparse.Namespace) -> int:
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    if args.paipu_dir:
        paths = sorted(
            glob.glob(os.path.join(args.paipu_dir, "**", "*"), recursive=True)
        )
        paths = [p for p in paths if os.path.isfile(p)
                 and (p.endswith(".xml") or p.endswith(".txt"))]
    elif args.paipu_list:
        with open(args.paipu_list) as f:
            paths = [ln.strip() for ln in f if ln.strip()]
    else:
        print("need --paipu-dir or --paipu-list", file=sys.stderr)
        return 2

    if args.max_files:
        paths = paths[: args.max_files]

    workers = max(1, int(args.workers))
    chunks = _split_evenly(paths, workers)
    worker_args = [
        {
            "out_dir": out_dir,
            "worker_id": i,
            "shard_rows": int(args.shard_rows),
            "paths": chunk,
            "pts": (list(args.pts) if args.pts is not None else None),
        }
        for i, chunk in enumerate(chunks)
    ]
    print(f"[encode-v4] {len(paths)} paipu files across {workers} workers",
          file=sys.stderr)

    t0 = time.time()
    if workers == 1:
        all_entries = [_worker_main(worker_args[0])]
    else:
        ctx = mp.get_context("spawn")
        with ctx.Pool(workers) as pool:
            all_entries = pool.map(_worker_main, worker_args)

    flat = [e for sub in all_entries for e in sub]
    cum = 0
    shard_entries = []
    for e in flat:
        cum += int(e["n_rows"])
        shard_entries.append(ShardEntry(path=e["path"], n_rows=int(e["n_rows"]),
                                        cumulative=cum))

    manifest = CacheManifest(
        schema=schema_fingerprint(),
        total_rows=cum,
        shards=shard_entries,
    )
    save_manifest(out_dir, manifest)

    elapsed = time.time() - t0
    print(
        f"[encode-v4] done: {cum:,} samples across {len(shard_entries)} shards "
        f"in {elapsed:.1f}s ({cum/max(elapsed,1e-6):.1f} samples/s) -> {out_dir}"
    )
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    from pymahjong.rl.v4.cache import load_manifest
    m = load_manifest(os.path.abspath(args.out))
    summary = {
        "total_rows": m.total_rows,
        "n_shards": len(m.shards),
        "schema": m.schema,
        "first_shards": [
            {"path": s.path, "n_rows": s.n_rows, "cumulative": s.cumulative}
            for s in m.shards[:5]
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_enc = sub.add_parser("paipu", help="encode Tenhou paipu XML logs to V4 cache")
    p_enc.add_argument("--out", required=True, help="cache output directory")
    p_enc.add_argument("--paipu-dir", default=None,
                       help="directory containing *.xml / *.txt paipu logs")
    p_enc.add_argument("--paipu-list", default=None,
                       help="text file with one paipu path per line")
    p_enc.add_argument("--max-files", type=int, default=None)
    p_enc.add_argument("--workers", type=int, default=1)
    p_enc.add_argument("--shard-rows", type=int, default=32768)
    p_enc.add_argument("--pts", type=float, nargs=4, default=None,
                       metavar=("P1", "P2", "P3", "P4"),
                       help="If given, also emit Mortal offline-RL targets "
                            "(per-kyoku placement reward / rank / steps) using "
                            "these placement points for ranks [1st..4th]. "
                            "Mortal uses 6 4 2 0. Omit for a BC-only cache.")
    p_enc.set_defaults(func=cmd_encode)

    p_show = sub.add_parser("inspect", help="print V4 cache manifest summary")
    p_show.add_argument("--out", required=True)
    p_show.set_defaults(func=cmd_inspect)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
