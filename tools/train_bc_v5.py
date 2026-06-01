#!/usr/bin/env python3
"""Train V5 (Douzero-style) behavior cloning policy with train/val/test splits.

V5 uses the V4 event-stream observation encoding (so any V4 cache can
be reused without re-encoding) but swaps the linear policy head for a
shared MLP scorer over ``(state, action_descriptor)`` pairs.  See
:mod:`pymahjong.rl.v5` for the architectural rationale.

This script is otherwise a thin wrapper around :func:`train_bc` with
``encoding="v5"`` and exposes the V5-specific architecture knobs
(``--scorer-hidden`` / ``--action-proj-dim`` / ``--action-feat-dim``).

Two splitting strategies (identical to V4):

* ``--split-by shard`` (recommended): list which shards go to each split.
  With per-month shards this is a time-based split with zero
  game-level leakage. Example::

      python tools/train_bc_v5.py \\
          --cache-dir /path/to/cache_v4 \\
          --split-by shard \\
          --train-shards shard_202001,shard_202501 \\
          --val-shards shard_202502 \\
          --test-shards shard_201905,shard_201906 \\
          --n-steps 50000 --batch-size 128 \\
          --eval-interval 1000 --early-stop-patience 5 \\
          --save-path checkpoints/bc_v5.pt

* ``--split-by track-id``: deterministic hash split; same ``track_id``
  always lands in the same split.

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
from pymahjong.rl.v4.splits import split_by_game_id, split_by_shard, split_by_track_id


def _parse_csv(s: str) -> list:
    return [x.strip() for x in s.split(",") if x.strip()]


def _parse_ratios(s: str) -> tuple:
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("ratios must be three comma-separated floats")
    return tuple(parts)


def main() -> int:
    from pymahjong.config import get_config
    _default_cache = get_config().v4_cache_path
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", type=Path, default=_default_cache,
                    required=_default_cache is None,
                    help="V4 cache directory (V5 reuses the V4 cache "
                         "format unchanged -- no re-encoding required).  "
                         f"Default from config: {_default_cache}")
    ap.add_argument("--split-by", choices=["shard", "track-id", "game-id"], required=True)
    ap.add_argument("--train-shards", type=_parse_csv, default=[],
                    help="comma-separated shard names (for --split-by shard)")
    ap.add_argument("--val-shards", type=_parse_csv, default=[])
    ap.add_argument("--test-shards", type=_parse_csv, default=[])
    ap.add_argument("--ratios", type=_parse_ratios, default=(0.8, 0.1, 0.1),
                    help="train,val,test ratios (for --split-by track-id)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--n-steps", type=int, default=0,
                    help="Total optimizer steps.  If 0 (default), computed "
                         "from --n-epochs × train_size / batch_size.  When "
                         "both are given, --n-steps wins.")
    ap.add_argument("--n-epochs", type=float, default=3.0,
                    help="Train for this many epochs over the train split "
                         "(default 3.0).  Ignored when --n-steps > 0.")
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--weight-decay", type=float, default=1e-4)
    # ---- Optimizer / LR schedule --------------------------------------
    ap.add_argument("--optimizer", choices=["adamw", "muon"], default="adamw",
                    help="Optimizer kind.  'adamw' (default) is the legacy "
                         "trainer; 'muon' uses Muon for 2-D hidden weights + "
                         "AdamW for embeddings/heads/biases/norms.  Muon "
                         "typically converges in ~0.6-0.75x the steps on "
                         "transformer policies.")
    ap.add_argument("--muon-lr", type=float, default=None,
                    help="LR for the Muon param group.  Default None => "
                         "67 * --lr per Keller Jordan's recipe (so the "
                         "default for --lr 3e-4 is muon_lr=0.02).")
    ap.add_argument("--betas", type=lambda s: tuple(float(x) for x in s.split(",")),
                    default=(0.9, 0.999),
                    help="AdamW (beta1, beta2).  '0.9,0.95' is the "
                         "transformer-recommended setting for late-stage "
                         "stability when training past 1 epoch.")
    ap.add_argument("--lr-schedule", choices=["constant", "cosine", "linear"],
                    default="constant",
                    help="LR schedule shape.  'cosine' is recommended once "
                         "val loss starts plateauing.")
    ap.add_argument("--warmup-steps", type=int, default=0,
                    help="Linear warmup over the first N steps (default 0).")
    ap.add_argument("--min-lr-ratio", type=float, default=0.1,
                    help="Cosine / linear decay's end LR as a fraction of "
                         "peak LR (default 0.1, i.e. decay to 10%%).")
    # ---- Weights & Biases (optional) ----------------------------------
    ap.add_argument("--wandb-project", default=None,
                    help="If set, log metrics to this wandb project.  "
                         "Requires `pip install wandb` and (for online "
                         "mode) `wandb login` or WANDB_API_KEY env var.")
    ap.add_argument("--wandb-entity", default=None,
                    help="wandb entity / team name (default = your default).")
    ap.add_argument("--wandb-name", default=None,
                    help="Run name in wandb (default = auto-generated).")
    ap.add_argument("--wandb-tags", default=None,
                    type=lambda s: tuple(t for t in s.split(",") if t),
                    help="Comma-separated tags (e.g. 'v5,muon,big11M').")
    ap.add_argument("--wandb-mode", default="online",
                    choices=["online", "offline", "disabled"],
                    help="online: live web dashboard (needs login). "
                         "offline: log to disk, sync later with `wandb sync`. "
                         "disabled: don't log to wandb at all.")
    ap.add_argument("--num-workers", type=int, default=2)
    ap.add_argument("--log-interval", type=int, default=200)
    ap.add_argument("--eval-interval", type=int, default=1000)
    ap.add_argument("--eval-max-batches", type=int, default=0,
                    help="cap val batches per evaluation (0 = full val set)")
    ap.add_argument("--early-stop-patience", type=int, default=0)
    ap.add_argument("--early-stop-min-epoch", type=float, default=1.0,
                    help="Don't trigger early stopping until at least this "
                         "many epochs have been trained.  Default 1.0 — "
                         "patience counter resets every eval until one full "
                         "epoch has been seen.  Mirrors train_bc_v4.py.")
    ap.add_argument("--save-path", type=Path, default=Path("bc_v5.pt"))
    ap.add_argument("--best-save-path", type=Path, default=None)
    ap.add_argument("--metrics-out", type=Path, default=None,
                    help="optional JSON file to write final test metrics")
    ap.add_argument("--use-pos-emb", action="store_true",
                    help="Add a learned positional embedding to V4 events "
                         "(see EventStreamTransformer). Required to break "
                         "the encoder's permutation invariance.")
    # Transformer encoder shape (kept identical to V4 defaults so V5 can
    # warm-start its encoder weights from a V4 checkpoint).
    ap.add_argument("--d-model", type=int, default=192)
    ap.add_argument("--n-layers", type=int, default=4)
    ap.add_argument("--n-heads", type=int, default=6)
    ap.add_argument("--ff-mult", type=int, default=4)
    ap.add_argument("--dropout", type=float, default=0.1)
    # V5-specific Douzero head shape.
    ap.add_argument("--scorer-hidden", type=int, default=256,
                    help="Hidden width of the shared (state, action) "
                         "scorer MLP (default 256).")
    ap.add_argument("--action-proj-dim", type=int, default=0,
                    help="Width of the per-action embedding after the "
                         "action_proj linear.  0 = match d_model.")
    # Selfplay eval (same as V4; V5 uses V4's environment).
    ap.add_argument("--selfplay-eval-interval", type=int, default=0,
                    help="Run shared-policy self-play every N steps to "
                         "measure agari rate / mean episode length. "
                         "0 disables.")
    ap.add_argument("--selfplay-eval-hands", type=int, default=16,
                    help="Number of hands per self-play eval call.")
    ap.add_argument("--selfplay-eval-stochastic", action="store_true",
                    help="Sample actions during self-play eval instead "
                         "of taking argmax (helpful to detect mode "
                         "collapse).")
    ap.add_argument("--selfplay-eval-max-seq-len", type=int, default=512,
                    help="Must match the model's training-time "
                         "max-seq-len.")
    ap.add_argument("--selfplay-paipu-dir", type=Path, default=None,
                    help="If set, save one Tenhou-XML paipu (+ URL) per "
                         "V5-SP eval into this directory as "
                         "step_NNNNNN.xml.")
    ap.add_argument("--illegal-logit-coef", type=float, default=0.0,
                    help="Auxiliary unmasked-CE coefficient.  0 disables.  "
                         "V5's shared scorer is less prone to the "
                         "masked-CE leak than V4's linear head, so "
                         "0 is a sensible default.")
    ap.add_argument("--illegal-logit-kind", default="unmasked_ce",
                    choices=["softplus", "l2", "unmasked_ce",
                             "unmasked_ce_smooth", "bce_multilabel"],
                    help="Shape of the illegal-logit penalty (see V4 docs).")
    ap.add_argument("--label-smoothing-eps", type=float, default=0.1,
                    help="eps for 'unmasked_ce_smooth' (default 0.1).")
    ap.add_argument("--resume", type=Path, default=None,
                    help="Resume training from a checkpoint saved by a "
                         "previous run.  Restores model weights and, "
                         "if present in the ckpt, optimizer state, "
                         "training step counter, best-val tracking and "
                         "self-play eval counter.  Architecture flags "
                         "must match the checkpoint.")
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
        # Expand fnmatch patterns (e.g. "p57_*", "shard_2025*") against
        # the cache manifest so a single CLI argument can match
        # hundreds of small worker shards.
        import fnmatch
        from pymahjong.rl.v4.cache import load_manifest

        manifest_shards = [s.path for s in load_manifest(str(args.cache_dir)).shards
                           if s.n_rows > 0]

        def _expand(patterns):
            out = []
            seen = set()
            for pat in patterns:
                if any(ch in pat for ch in "*?["):
                    matches = sorted(s for s in manifest_shards if fnmatch.fnmatch(s, pat))
                    if not matches:
                        print(f"WARNING: pattern {pat!r} matched 0 shards", file=sys.stderr)
                    for m in matches:
                        if m not in seen:
                            seen.add(m)
                            out.append(m)
                else:
                    if pat not in seen:
                        seen.add(pat)
                        out.append(pat)
            return out

        train_shards = _expand(args.train_shards)
        val_shards = _expand(args.val_shards)
        test_shards = _expand(args.test_shards)
        print(f"resolved shards: train={len(train_shards)}  "
              f"val={len(val_shards)}  test={len(test_shards)}")

        split = split_by_shard(
            base,
            train_shards=train_shards,
            val_shards=val_shards,
            test_shards=test_shards,
        )
    elif args.split_by == "game-id":
        split = split_by_game_id(base, ratios=args.ratios, seed=args.seed)
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

    # Compute n_steps and early_stop_min_step from epoch counts
    # (same convention as tools/train_bc_v4.py).
    train_size = len(split.train)
    steps_per_epoch = max(1, train_size // args.batch_size)
    if args.n_steps > 0:
        n_steps = args.n_steps
        effective_epochs = n_steps / steps_per_epoch
        print(f"n_steps={n_steps}  (= {effective_epochs:.2f} epochs over "
              f"{train_size:,} samples / bs {args.batch_size})")
    else:
        n_steps = int(args.n_epochs * steps_per_epoch)
        print(f"n_steps={n_steps}  (= {args.n_epochs} epochs × "
              f"{steps_per_epoch:,} steps/epoch; train_size={train_size:,}, "
              f"bs={args.batch_size})")
    early_stop_min_step = int(max(0.0, args.early_stop_min_epoch) * steps_per_epoch)
    if args.early_stop_patience > 0:
        print(f"early-stop: patience={args.early_stop_patience} evals, "
              f"min_step={early_stop_min_step} "
              f"(= {args.early_stop_min_epoch} epochs)")

    cfg = BCConfig(
        n_steps=n_steps,
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
        early_stop_min_step=early_stop_min_step,
        selfplay_eval_interval=args.selfplay_eval_interval,
        selfplay_eval_hands=args.selfplay_eval_hands,
        selfplay_eval_deterministic=not args.selfplay_eval_stochastic,
        selfplay_eval_max_seq_len=args.selfplay_eval_max_seq_len,
        selfplay_paipu_dir=str(args.selfplay_paipu_dir) if args.selfplay_paipu_dir else None,
        illegal_logit_coef=args.illegal_logit_coef,
        illegal_logit_kind=args.illegal_logit_kind,
        label_smoothing_eps=args.label_smoothing_eps,
        split_heads=False,    # V5 has no phase-split head -- shared scorer subsumes it.
        optimizer=args.optimizer,
        betas=args.betas,
        muon_lr=args.muon_lr,
        lr_schedule=args.lr_schedule,
        warmup_steps=args.warmup_steps,
        min_lr_ratio=args.min_lr_ratio,
        wandb_project=args.wandb_project,
        wandb_entity=args.wandb_entity,
        wandb_name=args.wandb_name,
        wandb_tags=args.wandb_tags,
        wandb_mode=args.wandb_mode,
        wandb_extra_config={"argv": " ".join(sys.argv)},
    )

    # Build the V5 model up-front so we can pass V5-specific knobs that
    # don't fit through the V4-style ``transformer_config`` interface.
    strategy = get_strategy(EncodingVersion("v5"))
    tcfg = TransformerConfig(
        d_model=args.d_model,
        n_layers=args.n_layers,
        n_heads=args.n_heads,
        ff_mult=args.ff_mult,
        dropout=args.dropout,
        use_pos_emb=args.use_pos_emb,
    )
    model = strategy.create_model(
        transformer_config=tcfg,
        scorer_hidden=args.scorer_hidden,
        action_proj_dim=args.action_proj_dim or None,
    )
    n_params = sum(p.numel() for p in model.parameters())
    print(f"V5 model: d_model={tcfg.d_model}  n_layers={tcfg.n_layers}  "
          f"scorer_hidden={args.scorer_hidden}  params={n_params:,}")

    t0 = time.monotonic()
    model = train_bc(
        dataset=split.train,
        val_dataset=split.val,
        model=model,
        config=cfg,
        transformer_config=tcfg,
        encoding="v5",
        resume_from=str(args.resume) if args.resume else None,
    )
    dt = time.monotonic() - t0
    print(f"\ntraining wall time: {dt:.1f}s")

    # Final test eval on the (best-by-val) restored model.
    if len(split.test) == 0:
        print("WARNING: test split is empty; skipping test eval")
        test_loss, test_acc, test_n, test_illegal_mass = float("nan"), float("nan"), 0, float("nan")
    else:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        test_loss, test_acc, test_n, test_illegal_mass = evaluate(
            model, split.test, strategy=strategy, cfg=cfg, device=device,
            max_batches=0,
        )
        print(f"\n[TEST] loss={test_loss:.4f}  acc={test_acc:.3f}  n={test_n}  "
              f"raw_illegal_mass={test_illegal_mass:.3f}")

    if args.metrics_out:
        args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_out.write_text(json.dumps({
            "encoding": "v5",
            "train_size": len(split.train),
            "val_size": len(split.val),
            "test_size": len(split.test),
            "test_loss": test_loss,
            "test_acc": test_acc,
            "test_n": test_n,
            "test_raw_illegal_mass": test_illegal_mass,
            "n_steps": args.n_steps,
            "batch_size": args.batch_size,
            "lr": args.lr,
            "weight_decay": args.weight_decay,
            "illegal_logit_coef": args.illegal_logit_coef,
            "split_by": args.split_by,
            "train_shards": args.train_shards,
            "val_shards": args.val_shards,
            "test_shards": args.test_shards,
            "d_model": tcfg.d_model,
            "n_layers": tcfg.n_layers,
            "n_heads": tcfg.n_heads,
            "ff_mult": tcfg.ff_mult,
            "scorer_hidden": args.scorer_hidden,
            "action_proj_dim": args.action_proj_dim or tcfg.d_model,
            "wall_time_s": dt,
        }, indent=2))
        print(f"metrics written to {args.metrics_out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
