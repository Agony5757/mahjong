#!/usr/bin/env python3
"""Encode tokenized BC training data into an on-disk shard cache.

The cache format is documented in :mod:`pymahjong.rl.cache`. Two
sources are supported today:

* ``selfplay`` — run ``MahjongEnv`` repeatedly with a (currently
  random) expert and tokenize every decision point. Useful for quickly
  filling a cache to validate the training pipeline end-to-end.
* ``paipu``   — iterate Tenhou XML logs and tokenize each ground-truth
  decision. Requires :class:`pm.PaipuReplayer` to expose
  ``next_action()`` / ``step()`` (gated at runtime; will print a clear
  error if the engine doesn't expose them yet).

Multi-process encoding is supported via ``--workers N`` (each worker
writes its own shard subdirectory; the master rebuilds ``index.json``
at the end).

Examples::

    # Quick smoke fill (no paipus needed):
    python tools/encode_paipu_to_cache.py selfplay \\
        --out cache/smoke --games 200 --workers 4

    # Real BC data from already-downloaded paipu XMLs:
    python tools/encode_paipu_to_cache.py paipu \\
        --paipu-dir paipuxmls --out cache/houou --workers 8 \\
        --shard-rows 65536
"""

from __future__ import annotations

import argparse
import glob
import json
import multiprocessing as mp
import os
import sys
import time
from typing import Iterable, Iterator, List, Optional

# Make the in-tree package importable when running the script directly.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import numpy as np  # noqa: E402

from pymahjong.rl.cache import (  # noqa: E402
    ShardWriter,
    rebuild_manifest,
    save_manifest,
    schema_fingerprint,
    CacheManifest,
)
from pymahjong.rl.tokenization import MAX_SEQ_LEN, MahjongTokenizer  # noqa: E402

try:
    import MahjongPyWrapper as pm  # type: ignore
except Exception as e:  # pragma: no cover
    pm = None
    _PM_IMPORT_ERR = e
else:
    _PM_IMPORT_ERR = None


# ---------------------------------------------------------------------------
# Sample iterators
# ---------------------------------------------------------------------------


def _engine_actions(table):
    phase = table.get_phase()
    return table.get_self_actions() if phase < 4 else table.get_response_actions()


def _yield_selfplay(
    n_games: int,
    seed: Optional[int],
    tokenizer: MahjongTokenizer,
    oracle: bool,
) -> Iterator[dict]:
    """Yield tokenized samples by self-playing random episodes."""
    if pm is None:
        raise RuntimeError(f"MahjongPyWrapper not importable: {_PM_IMPORT_ERR}")
    rng = np.random.default_rng(seed)

    # Lazy import to avoid importing torch in worker processes that
    # don't strictly need it.
    from pymahjong.rl.dataset import SelfPlayImitationDataset

    for _g in range(n_games):
        table = pm.Table()
        table.game_init()
        while True:
            phase = table.get_phase()
            if phase == 16:
                break
            actions = _engine_actions(table)
            if not actions:
                break
            seat = table.who_make_selection()
            if len(actions) == 1:
                table.make_selection(0)
                continue
            engine_idx = int(rng.integers(len(actions)))
            tok = tokenizer.encode(table, current_player=seat)
            unified = SelfPlayImitationDataset._engine_idx_to_unified(
                table, engine_idx
            )
            yield {
                "tokens": tok.tokens.copy(),
                "scalars": tok.scalars.copy(),
                "attention_mask": tok.attention_mask.copy(),
                "action_mask": tok.action_mask.copy(),
                "action": int(unified),
            }
            table.make_selection(engine_idx)


def _yield_paipu(
    paths: Iterable[str],
    tokenizer: MahjongTokenizer,
) -> Iterator[dict]:
    """Yield tokenized samples by replaying Tenhou paipu XMLs.

    Uses :class:`pymahjong.tenhou_paipu_check.PaipuReplay` (the existing
    XML-driven orchestrator) and intercepts every ``make_selection`` call
    via a proxy. At each true decision point we tokenize the table state
    *before* the engine consumes the action, capturing the ground-truth
    selection index used as the BC label.
    """
    if pm is None:
        raise RuntimeError(f"MahjongPyWrapper not importable: {_PM_IMPORT_ERR}")
    if not hasattr(pm, "PaipuReplayer"):
        raise RuntimeError(
            "MahjongPyWrapper.PaipuReplayer not exposed; cannot encode paipu cache yet."
        )

    from pymahjong import tenhou_paipu_check as tpc
    from pymahjong.rl.dataset import SelfPlayImitationDataset

    pending: list[dict] = []

    class _Proxy:
        __slots__ = ("_inner",)

        def __init__(self, inner):
            object.__setattr__(self, "_inner", inner)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def make_selection(self, idx):
            table = self._inner.table
            phase = int(table.get_phase())
            if phase < 16:
                seat = phase % 4
                try:
                    tok = tokenizer.encode(table, current_player=seat)
                    unified = SelfPlayImitationDataset._engine_idx_to_unified(table, idx)
                    pending.append({
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
        for path in paths:
            replay = tpc.PaipuReplay()
            replay.logger = tpc.Logger()
            replay.write_log = False
            directory = os.path.dirname(path) or "."
            filename = os.path.basename(path)
            try:
                replay._paipu_replay(directory, filename)
            except Exception:  # noqa: BLE001
                # Engine-level error during a single game; skip its remaining samples
                # but yield whatever we already collected before the error.
                pass
            while pending:
                yield pending.pop(0)
    finally:
        pm.PaipuReplayer = orig_ctor  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------


def _worker_main(args_dict: dict) -> List[dict]:
    """Run a single encoding worker; return a list of ShardEntry dicts."""
    out_dir = args_dict["out_dir"]
    worker_id = args_dict["worker_id"]
    shard_rows = args_dict["shard_rows"]
    max_seq_len = args_dict["max_seq_len"]
    oracle = args_dict["oracle"]
    source = args_dict["source"]

    tokenizer = MahjongTokenizer(max_seq_len=max_seq_len, include_oracle=oracle)

    if source == "selfplay":
        sample_iter = _yield_selfplay(
            n_games=args_dict["games"],
            seed=args_dict.get("seed"),
            tokenizer=tokenizer,
            oracle=oracle,
        )
    elif source == "paipu":
        sample_iter = _yield_paipu(
            paths=args_dict["paths"],
            tokenizer=tokenizer,
        )
    else:
        raise ValueError(source)

    entries: List[dict] = []
    shard_idx = 0
    writer: Optional[ShardWriter] = None
    t0 = time.time()
    n_total = 0

    def _open_shard(idx: int) -> ShardWriter:
        path = os.path.join(out_dir, f"shard_w{worker_id:02d}_{idx:05d}")
        return ShardWriter(path, max_seq_len=max_seq_len)

    writer = _open_shard(shard_idx)
    for sample in sample_iter:
        writer.add(sample)
        n_total += 1
        if writer.n_rows >= shard_rows:
            entry = writer.close()
            entries.append({
                "path": entry.path,
                "n_rows": entry.n_rows,
                "cumulative": 0,  # filled in by master
            })
            shard_idx += 1
            writer = _open_shard(shard_idx)
            elapsed = time.time() - t0
            print(
                f"[worker {worker_id}] shard {shard_idx-1} closed "
                f"({entry.n_rows} rows, total {n_total}, "
                f"{n_total/max(elapsed,1e-6):.1f} samples/s)",
                flush=True,
            )

    if writer is not None and writer.n_rows > 0:
        entry = writer.close()
        entries.append({
            "path": entry.path,
            "n_rows": entry.n_rows,
            "cumulative": 0,
        })

    return entries


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _split_evenly(items: List, n: int) -> List[List]:
    return [items[i::n] for i in range(n)]


def cmd_encode(args: argparse.Namespace) -> int:
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    workers = max(1, int(args.workers))
    if args.source == "selfplay":
        per_worker_games = max(1, args.games // workers)
        worker_args = [
            {
                "out_dir": out_dir,
                "worker_id": i,
                "shard_rows": int(args.shard_rows),
                "max_seq_len": int(args.max_seq_len),
                "oracle": bool(args.oracle),
                "source": "selfplay",
                "games": per_worker_games,
                "seed": (args.seed + i) if args.seed is not None else None,
            }
            for i in range(workers)
        ]
    else:
        if args.paipu_dir:
            paths = sorted(glob.glob(os.path.join(args.paipu_dir, "**", "*"),
                                     recursive=True))
            paths = [p for p in paths if os.path.isfile(p)
                     and (p.endswith(".xml") or p.endswith(".txt"))]
        elif args.paipu_list:
            with open(args.paipu_list) as f:
                paths = [ln.strip() for ln in f if ln.strip()]
        else:
            print("paipu source needs --paipu-dir or --paipu-list", file=sys.stderr)
            return 2
        if args.max_files:
            paths = paths[: args.max_files]
        chunks = _split_evenly(paths, workers)
        worker_args = [
            {
                "out_dir": out_dir,
                "worker_id": i,
                "shard_rows": int(args.shard_rows),
                "max_seq_len": int(args.max_seq_len),
                "oracle": bool(args.oracle),
                "source": "paipu",
                "paths": chunk,
            }
            for i, chunk in enumerate(chunks)
        ]
        print(f"[encode] {len(paths)} paipu files split across {workers} workers",
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
    from pymahjong.rl.cache import ShardEntry
    for e in flat:
        cum += int(e["n_rows"])
        shard_entries.append(ShardEntry(path=e["path"], n_rows=int(e["n_rows"]),
                                        cumulative=cum))

    manifest = CacheManifest(
        schema=schema_fingerprint(int(args.max_seq_len)),
        total_rows=cum,
        shards=shard_entries,
    )
    save_manifest(out_dir, manifest)

    elapsed = time.time() - t0
    print(
        f"[encode] done: {cum} samples across {len(shard_entries)} shards "
        f"in {elapsed:.1f}s ({cum/max(elapsed,1e-6):.1f} samples/s) -> {out_dir}"
    )
    return 0


def cmd_rebuild_index(args: argparse.Namespace) -> int:
    m = rebuild_manifest(os.path.abspath(args.out), max_seq_len=int(args.max_seq_len))
    print(json.dumps({"total_rows": m.total_rows, "n_shards": len(m.shards)}, indent=2))
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    from pymahjong.rl.cache import load_manifest
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

    p_self = sub.add_parser("selfplay", help="encode random self-play rollouts")
    p_self.add_argument("--out", required=True, help="cache output directory")
    p_self.add_argument("--games", type=int, default=100)
    p_self.add_argument("--workers", type=int, default=1)
    p_self.add_argument("--shard-rows", type=int, default=65536)
    p_self.add_argument("--max-seq-len", type=int, default=MAX_SEQ_LEN)
    p_self.add_argument("--oracle", action="store_true")
    p_self.add_argument("--seed", type=int, default=None)
    p_self.set_defaults(func=cmd_encode, source="selfplay",
                        paipu_dir=None, paipu_list=None, max_files=None)

    p_paipu = sub.add_parser("paipu", help="encode Tenhou paipu XML logs")
    p_paipu.add_argument("--out", required=True)
    p_paipu.add_argument("--paipu-dir", default=None,
                         help="directory containing *.xml / *.txt paipu logs")
    p_paipu.add_argument("--paipu-list", default=None,
                         help="text file with one paipu path per line")
    p_paipu.add_argument("--max-files", type=int, default=None)
    p_paipu.add_argument("--workers", type=int, default=1)
    p_paipu.add_argument("--shard-rows", type=int, default=65536)
    p_paipu.add_argument("--max-seq-len", type=int, default=MAX_SEQ_LEN)
    p_paipu.add_argument("--oracle", action="store_true")
    p_paipu.set_defaults(func=cmd_encode, source="paipu", games=0, seed=None)

    p_idx = sub.add_parser("rebuild-index",
                           help="re-scan a cache directory and rewrite index.json")
    p_idx.add_argument("--out", required=True)
    p_idx.add_argument("--max-seq-len", type=int, default=MAX_SEQ_LEN)
    p_idx.set_defaults(func=cmd_rebuild_index)

    p_show = sub.add_parser("inspect", help="print cache manifest summary")
    p_show.add_argument("--out", required=True)
    p_show.set_defaults(func=cmd_inspect)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
