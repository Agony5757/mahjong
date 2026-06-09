#!/usr/bin/env python3
"""Offline Mortal-style CQL training launcher (faithful Mortal RL).

Trains **our** V5 network (EventStreamTransformer encoder + Douzero Q-head)
with Mortal's *offline* algorithm on a reward-annotated expert cache:
MC Q-target (gamma=1) + DQN MSE + CQL conservatism (min_q_weight=5) +
next-rank aux (0.2), AdamW (weight decay on Linear weights only, lr=1e-4
constant, no grad clip), batch 512.

Build the cache first::

    python tools/encode_paipu_to_cache_v4.py paipu \
        --out /path/to/cache_rl --paipu-dir /path/to/paipu \
        --workers 8 --shard-rows 32768 --pts 6 4 2 0

Then train::

    python tools/train_offline_mortal_v5.py \
        --cache-dir /path/to/cache_rl \
        --bc-checkpoint checkpoints/bc_v5.pt \
        --save-path checkpoints/offline_mortal_v5.pt \
        --num-epochs 1 --mortal-eval --mortal-eval-hanchan 200 ...

Model defaults match the standard V5 BC ckpt shape (d384/L6/H8/FF4,
scorer-hidden 256) so warm-start ``load_state_dict`` succeeds.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.v5.offline import OfflineConfig, train_offline_mortal


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # I/O
    ap.add_argument("--cache-dir", required=True,
                    help="Reward-annotated V4 cache (built with --pts).")
    ap.add_argument("--bc-checkpoint", type=str, default=None,
                    help="V5 BC checkpoint to warm-start from.")
    ap.add_argument("--save-path", type=str, default="checkpoints/offline_mortal_v5.pt")
    ap.add_argument("--no-keep-periodic", action="store_true")

    # Schedule
    ap.add_argument("--num-epochs", type=int, default=1)
    ap.add_argument("--total-steps", type=int, default=0,
                    help="Optimisation-step cap (0 = full epochs).")
    ap.add_argument("--batch-size", type=int, default=512)        # Mortal
    ap.add_argument("--num-workers", type=int, default=4)
    ap.add_argument("--max-seq-len", type=int, default=512)

    # Optimisation (Mortal defaults)
    ap.add_argument("--gamma", type=float, default=1.0)            # Mortal
    ap.add_argument("--lr", type=float, default=1e-4)             # Mortal
    ap.add_argument("--weight-decay", type=float, default=0.1)    # Mortal (Linear only)
    ap.add_argument("--grad-clip", type=float, default=0.0)      # Mortal: off

    # Mortal loss weights
    ap.add_argument("--no-cql", action="store_true",
                    help="Disable CQL (Mortal keeps it ON for offline).")
    ap.add_argument("--min-q-weight", type=float, default=5.0)    # Mortal
    ap.add_argument("--next-rank-weight", type=float, default=0.2)  # Mortal

    # Model (pinned to V5 BC ckpt shape)
    ap.add_argument("--d-model", type=int, default=192)
    ap.add_argument("--n-layers", type=int, default=4)
    ap.add_argument("--n-heads", type=int, default=6)
    ap.add_argument("--ff-mult", type=int, default=4)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--use-pos-emb", action="store_true")
    ap.add_argument("--scorer-hidden", type=int, default=256)
    ap.add_argument("--action-proj-dim", type=int, default=0, help="0 = match d_model.")

    # Misc
    ap.add_argument("--device", type=str, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--save-interval", type=int, default=20000)
    ap.add_argument("--log-interval", type=int, default=50)

    # wandb
    ap.add_argument("--wandb-project", type=str, default=None)
    ap.add_argument("--wandb-entity", type=str, default=None)
    ap.add_argument("--wandb-name", type=str, default=None)
    ap.add_argument("--wandb-tags", type=str, default=None, help="Comma-separated.")
    ap.add_argument("--wandb-mode", type=str, default="online",
                    choices=["online", "offline", "disabled"])

    # Mortal head-to-head eval
    ap.add_argument("--mortal-eval", action="store_true")
    ap.add_argument("--mortal-eval-hanchan", type=int, default=200)
    ap.add_argument("--mortal-bench-script", type=str, default=None)
    ap.add_argument("--mortal-bench-cwd", type=str, default=None)
    ap.add_argument("--mortal-ckpt", type=str, default=None)
    ap.add_argument("--mortal-eval-python", type=str, default=None)
    ap.add_argument("--mortal-eval-out-dir", type=str, default=None)
    ap.add_argument("--mortal-eval-timeout", type=float, default=36000.0)
    ap.add_argument("--mortal-eval-amp", action="store_true")

    args = ap.parse_args()

    if args.save_path:
        Path(args.save_path).parent.mkdir(parents=True, exist_ok=True)

    tcfg = TransformerConfig(
        d_model=args.d_model,
        n_layers=args.n_layers,
        n_heads=args.n_heads,
        ff_mult=args.ff_mult,
        dropout=args.dropout,
        use_pos_emb=args.use_pos_emb,
    )

    cfg = OfflineConfig(
        cache_dir=args.cache_dir,
        num_epochs=args.num_epochs,
        total_steps=args.total_steps,
        batch_size=args.batch_size,
        num_workers=args.num_workers,
        max_seq_len=args.max_seq_len,
        gamma=args.gamma,
        lr=args.lr,
        weight_decay=args.weight_decay,
        grad_clip=args.grad_clip,
        cql_enable=not args.no_cql,
        min_q_weight=args.min_q_weight,
        next_rank_weight=args.next_rank_weight,
        scorer_hidden=args.scorer_hidden,
        action_proj_dim=args.action_proj_dim or None,
        save_path=args.save_path,
        keep_periodic=not args.no_keep_periodic,
        save_interval=args.save_interval,
        log_interval=args.log_interval,
        device=args.device,
        seed=args.seed,
        wandb_project=args.wandb_project,
        wandb_entity=args.wandb_entity,
        wandb_name=args.wandb_name,
        wandb_tags=(tuple(t.strip() for t in args.wandb_tags.split(","))
                    if args.wandb_tags else None),
        wandb_mode=args.wandb_mode,
        mortal_eval=args.mortal_eval,
        mortal_eval_hanchan=args.mortal_eval_hanchan,
        mortal_bench_script=args.mortal_bench_script,
        mortal_bench_cwd=args.mortal_bench_cwd,
        mortal_ckpt=args.mortal_ckpt,
        mortal_eval_python=args.mortal_eval_python,
        mortal_eval_out_dir=args.mortal_eval_out_dir,
        mortal_eval_timeout_sec=args.mortal_eval_timeout,
        mortal_eval_amp=args.mortal_eval_amp,
    )

    print(f"[train_offline_mortal_v5] config: {cfg}")
    train_offline_mortal(bc_checkpoint=args.bc_checkpoint, config=cfg, transformer_config=tcfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
