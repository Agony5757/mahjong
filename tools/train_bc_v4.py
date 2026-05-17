#!/usr/bin/env python3
"""Train V4 behavior cloning policy with train/val/test splits.

Two splitting strategies:

* ``--split-by shard`` (recommended): list which shards go to each split.
  With per-month shards this is a time-based split with zero
  game-level leakage. Example::

      python tools/train_bc_v4.py \\
          --cache-dir /path/to/cache_v4 \\
          --split-by shard \\
          --train-shards shard_202001,shard_202501 \\
          --val-shards shard_202502 \\
          --test-shards shard_201905,shard_201906 \\
          --n-steps 50000 --batch-size 128 \\
          --eval-interval 1000 --early-stop-patience 5 \\
          --save-path checkpoints/bc_v4.pt

* ``--split-by track-id``: deterministic hash split; same ``track_id``
  always lands in the same split. Allows a small amount of cross-seat
  leakage but is simple for ad-hoc experimentation.

After training, computes final test-set metrics on the best-by-val
checkpoint.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import torch

from pymahjong.rl.bc import BCConfig, evaluate, train_bc
from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.encoding import EncodingVersion, get_strategy
from pymahjong.rl.v4.cached_dataset import CachedEventDataset
from pymahjong.rl.v4.splits import split_by_shard, split_by_track_id


def _parse_csv(s: str) -> list:
    return [x.strip() for x in s.split(",") if x.strip()]


def _parse_ratios(s: str) -> tuple:
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("ratios must be three comma-separated floats")
    return tuple(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", required=True, type=Path)
    ap.add_argument("--split-by", choices=["shard", "track-id"], required=True)
    ap.add_argument("--train-shards", type=_parse_csv, default=[],
                    help="comma-separated shard names (for --split-by shard)")
    ap.add_argument("--val-shards", type=_parse_csv, default=[])
    ap.add_argument("--test-shards", type=_parse_csv, default=[])
    ap.add_argument("--ratios", type=_parse_ratios, default=(0.8, 0.1, 0.1),
                    help="train,val,test ratios (for --split-by track-id)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-steps", type=int, default=20000)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    ap.add_argument("--num-workers", type=int, default=2)
    ap.add_argument("--log-interval", type=int, default=200)
    ap.add_argument("--eval-interval", type=int, default=1000)
    ap.add_argument("--eval-max-batches", type=int, default=0,
                    help="cap val batches per evaluation (0 = full val set)")
    ap.add_argument("--early-stop-patience", type=int, default=0)
    ap.add_argument("--save-path", type=Path, default=Path("bc_v4.pt"))
    ap.add_argument("--best-save-path", type=Path, default=None)
    ap.add_argument("--metrics-out", type=Path, default=None,
                    help="optional JSON file to write final test metrics")
    args = ap.parse_args()

    print(f"cache_dir   = {args.cache_dir}")
    print(f"split_by    = {args.split_by}")
    print(f"device      = {'cuda' if torch.cuda.is_available() else 'cpu'}")

    base = CachedEventDataset(str(args.cache_dir))
    print(f"base dataset: {len(base):,} samples")

    if args.split_by == "shard":
        if not (args.train_shards and args.val_shards and args.test_shards):
            print("ERROR: --train-shards, --val-shards, --test-shards all required "
                  "when --split-by shard", file=sys.stderr)
            return 2
        split = split_by_shard(
            base,
            train_shards=args.train_shards,
            val_shards=args.val_shards,
            test_shards=args.test_shards,
        )
    else:
        split = split_by_track_id(base, ratios=args.ratios, seed=args.seed)
    print(f"split:  {split.summary()}")
    print()

    if len(split.train) == 0:
        print("ERROR: train split is empty", file=sys.stderr)
        return 2
    if len(split.val) == 0:
        print("ERROR: val split is empty", file=sys.stderr)
        return 2

    cfg = BCConfig(
        n_steps=args.n_steps,
        batch_size=args.batch_size,
        lr=args.lr,
        weight_decay=args.weight_decay,
        num_workers=args.num_workers,
        log_interval=args.log_interval,
        save_interval=max(args.eval_interval, args.log_interval),
        save_path=str(args.save_path),
        best_save_path=str(args.best_save_path) if args.best_save_path else None,
        eval_interval=args.eval_interval,
        eval_max_batches=args.eval_max_batches,
        early_stop_patience=args.early_stop_patience,
    )

    t0 = time.monotonic()
    model = train_bc(
        dataset=split.train,
        val_dataset=split.val,
        config=cfg,
        transformer_config=TransformerConfig(),
        encoding="v4",
    )
    dt = time.monotonic() - t0
    print(f"\ntraining wall time: {dt:.1f}s")

    # Final test eval on the (best-by-val) restored model.
    if len(split.test) == 0:
        print("WARNING: test split is empty; skipping test eval")
        test_loss, test_acc, test_n = float("nan"), float("nan"), 0
    else:
        strategy = get_strategy(EncodingVersion("v4"))
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        test_loss, test_acc, test_n = evaluate(
            model, split.test, strategy=strategy, cfg=cfg, device=device,
            max_batches=0,
        )
        print(f"\n[TEST] loss={test_loss:.4f}  acc={test_acc:.3f}  n={test_n}")

    if args.metrics_out:
        args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_out.write_text(json.dumps({
            "train_size": len(split.train),
            "val_size": len(split.val),
            "test_size": len(split.test),
            "test_loss": test_loss,
            "test_acc": test_acc,
            "test_n": test_n,
            "n_steps": args.n_steps,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "split_by": args.split_by,
            "train_shards": args.train_shards,
            "val_shards": args.val_shards,
            "test_shards": args.test_shards,
            "wall_time_s": dt,
        }, indent=2))
        print(f"metrics written to {args.metrics_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
