#!/usr/bin/env python3
"""Mortal-style (value-learning) self-play training launcher for V5.

Unlike :mod:`tools.train_ppo_v5` (on-policy PPO actor-critic), this uses
**Mortal's algorithm**: the V5 Douzero scorer is reinterpreted as a
dueling Q-function, trained to regress a Monte-Carlo Q-target
``gamma ** steps_to_done * kyoku_reward`` with an optional CQL
conservatism term and an auxiliary final-rank head.  Rewards come from a
per-kyoku reward signal (points / placement / GRP) computed over full hanchan.

The same V5 network/checkpoint is reused -- warm-start from a V5 BC
checkpoint with ``--bc-checkpoint`` (only the small aux-rank head is
freshly initialised).

Standard recipe::

    # Warm-start from a V5 BC checkpoint, points reward, online (no CQL):
    python tools/train_mortal_v5.py \\
        --bc-checkpoint checkpoints/bc_v5_clean.best.pt \\
        --save-path checkpoints/mortal_v5.pt \\
        --total-steps 1000000 --rollout-steps 8192 \\
        --reward-kind points --lr 1e-4

    # Faithful Mortal with a trained GRP net + CQL conservatism:
    python tools/train_mortal_v5.py \\
        --bc-checkpoint checkpoints/bc_v5_clean.best.pt \\
        --reward-kind grp --grp-ckpt checkpoints/grp.pt \\
        --cql --min-q-weight 1.0

Model defaults are pinned to the standard V5 BC ckpt shape (192/4/6/4,
scorer-hidden 256) so warm-start ``load_state_dict`` succeeds.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.v5.mortal import MortalConfig, train_mortal_v5


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    # I/O
    ap.add_argument("--bc-checkpoint", type=str, default=None,
                    help="V5 BC checkpoint to warm-start the inner network from.")
    ap.add_argument("--save-path", type=str, default="checkpoints/mortal_v5.pt")
    ap.add_argument("--snapshot-dir", type=str, default=None,
                    help="If set, persist opponent-pool snapshots under this dir.")

    # Schedule
    ap.add_argument("--total-steps", type=int, default=1_000_000,
                    help="Total learner decisions across the whole run.")
    ap.add_argument("--rollout-steps", type=int, default=8192,
                    help="Learner decisions collected per optimisation round.")
    ap.add_argument("--n-envs", type=int, default=8,
                    help="Parallel hanchan environments.")
    ap.add_argument("--n-epochs", type=int, default=2)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--max-seq-len", type=int, default=512)

    # Optimisation
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--grad-clip", type=float, default=1.0)
    ap.add_argument("--weight-decay", type=float, default=0.0)
    ap.add_argument("--huber-delta", type=float, default=0.0,
                    help="If >0, use Huber (smooth-L1, this beta) DQN loss "
                         "instead of 0.5*MSE; caps the huge initial BC-warmstart "
                         "TD gradient so the BC anchor can hold the policy.")

    # Mortal loss weights
    ap.add_argument("--cql", action="store_true",
                    help="Enable the CQL conservatism term (Mortal offline "
                         "mode).  Off by default for online self-play.")
    ap.add_argument("--min-q-weight", type=float, default=1.0,
                    help="Weight of the CQL term (only with --cql).")
    ap.add_argument("--next-rank-weight", type=float, default=0.5,
                    help="Weight of the auxiliary final-rank cross-entropy.")
    ap.add_argument("--bc-anchor-weight", type=float, default=0.0,
                    help="Weight of the KL/CE-to-frozen-BC policy anchor "
                         "(anti-collapse for BC warm-starts; >0 keeps the "
                         "learner policy close to BC regardless of Q scale).")

    # Reward shaping
    ap.add_argument("--reward-kind", choices=["placement", "grp", "points"],
                    default="points",
                    help="points=raw per-kyoku score delta (default); "
                         "placement=deterministic provisional placement (no "
                         "extra net); grp=trained GRP net.")
    ap.add_argument("--grp-ckpt", type=str, default=None,
                    help="Trained GRP checkpoint (required for --reward-kind grp).")
    ap.add_argument("--grp-hidden", type=int, default=64)
    ap.add_argument("--grp-layers", type=int, default=2)
    ap.add_argument("--pts", type=float, nargs=4, default=None,
                    metavar=("P1", "P2", "P3", "P4"),
                    help="Placement-point vector for ranks [1st,2nd,3rd,4th] "
                         "used by the reward.  Mortal uses 6 4 2 0; our older "
                         "default is 3 1 -1 -3.  Omit to keep the config default.")
    ap.add_argument("--reward-clip", type=float, default=0.0,
                    help="Symmetric clip on the per-decision Q-target "
                         "(<=0 disables).")

    # Exploration
    ap.add_argument("--epsilon", type=float, default=0.0,
                    help="Random-legal-action probability during collection.")
    ap.add_argument("--collect-stochastic", action="store_true",
                    help="Sample (Boltzmann over Q) instead of argmax during "
                         "collection.")

    # Opponents: fixed frozen-BC environment (default) vs. self-play pool
    ap.add_argument("--fixed-bc-opponents", action=argparse.BooleanOptionalAction,
                    default=True,
                    help="Default ON: the 3 non-learner seats are a FROZEN BC "
                         "model and only the rotating learner seat is trained "
                         "(non-zero-sum reward vs a stationary reference).  Use "
                         "--no-fixed-bc-opponents for symmetric self-play with "
                         "the historical opponent pool.")
    ap.add_argument("--opponent-bc-checkpoint", type=str, default=None,
                    help="BC checkpoint for the frozen opponents (fixed-BC "
                         "mode).  Default: reuse --bc-checkpoint.")

    # Self-play / opponent pool (only used with --no-fixed-bc-opponents)
    ap.add_argument("--opponent-mix-ratio", type=float, default=0.25)
    ap.add_argument("--n-frozen-seats", type=int, default=1, choices=[0, 1, 2, 3])
    ap.add_argument("--snapshot-interval", type=int, default=50_000)
    ap.add_argument("--pool-capacity", type=int, default=20)
    ap.add_argument("--pool-sampling", choices=["uniform", "latest", "pfsp"],
                    default="pfsp")
    ap.add_argument("--pfsp-p", type=float, default=2.0)

    # Model (pinned to V5 BC ckpt shape).
    ap.add_argument("--d-model", type=int, default=192)
    ap.add_argument("--n-layers", type=int, default=4)
    ap.add_argument("--n-heads", type=int, default=6)
    ap.add_argument("--ff-mult", type=int, default=4)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--use-pos-emb", action="store_true")
    ap.add_argument("--scorer-hidden", type=int, default=256)
    ap.add_argument("--action-proj-dim", type=int, default=0,
                    help="0 = match d_model.")

    # Misc
    ap.add_argument("--device", type=str, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--save-interval", type=int, default=100_000)
    ap.add_argument("--no-keep-periodic", action="store_true",
                    help="Only keep the rolling 'latest' checkpoint; do NOT "
                         "also save a per-step historical copy each save.")
    ap.add_argument("--log-interval", type=int, default=1)

    # wandb
    ap.add_argument("--wandb-project", type=str, default=None)
    ap.add_argument("--wandb-entity", type=str, default=None)
    ap.add_argument("--wandb-name", type=str, default=None)
    ap.add_argument("--wandb-tags", type=str, default=None,
                    help="Comma-separated tags.")
    ap.add_argument("--wandb-mode", type=str, default="online",
                    choices=["online", "offline", "disabled"])

    # Mortal head-to-head eval on every checkpoint save (1v3 + 3v1)
    ap.add_argument("--mortal-eval", action="store_true",
                    help="After each checkpoint save, benchmark vs Mortal "
                         "(1v3 and 3v1) and log to wandb under mortal/*.")
    ap.add_argument("--mortal-eval-hanchan", type=int, default=200,
                    help="Hanchan per matchup (default 200 = tight estimate, "
                         "tens of minutes; use 16-64 for in-training eval).")
    ap.add_argument("--mortal-bench-script", type=str, default=None,
                    help="Absolute path to mjai_bench_v2.py.")
    ap.add_argument("--mortal-bench-cwd", type=str, default=None,
                    help="Working dir for the bench subprocess (its src/).")
    ap.add_argument("--mortal-ckpt", type=str, default=None,
                    help="Absolute path to Mortal .pth weights (e.g. mortal_298k.pth).")
    ap.add_argument("--mortal-eval-python", type=str, default=None,
                    help="Interpreter for the eval subprocess (default: this Python).")
    ap.add_argument("--mortal-eval-out-dir", type=str, default=None,
                    help="Root dir for per-step eval logs (default: <save dir>/mortal_eval).")
    ap.add_argument("--mortal-eval-timeout", type=float, default=1800.0,
                    help="Per-matchup subprocess timeout (seconds).")
    ap.add_argument("--mortal-eval-amp", action="store_true",
                    help="Pass --amp to the V5 agent in the bench subprocess.")

    args = ap.parse_args()

    if args.save_path:
        Path(args.save_path).parent.mkdir(parents=True, exist_ok=True)
    if args.snapshot_dir:
        Path(args.snapshot_dir).mkdir(parents=True, exist_ok=True)

    tcfg = TransformerConfig(
        d_model=args.d_model,
        n_layers=args.n_layers,
        n_heads=args.n_heads,
        ff_mult=args.ff_mult,
        dropout=args.dropout,
        use_pos_emb=args.use_pos_emb,
    )

    cfg = MortalConfig(
        total_steps=args.total_steps,
        rollout_steps=args.rollout_steps,
        n_envs=args.n_envs,
        n_epochs=args.n_epochs,
        batch_size=args.batch_size,
        max_seq_len=args.max_seq_len,
        gamma=args.gamma,
        lr=args.lr,
        grad_clip=args.grad_clip,
        weight_decay=args.weight_decay,
        huber_delta=args.huber_delta,
        cql_enable=args.cql,
        min_q_weight=args.min_q_weight,
        next_rank_weight=args.next_rank_weight,
        bc_anchor_weight=args.bc_anchor_weight,
        reward_kind=args.reward_kind,
        grp_ckpt=args.grp_ckpt,
        grp_hidden=args.grp_hidden,
        grp_layers=args.grp_layers,
        reward_clip=args.reward_clip,
        **({"pts": tuple(args.pts)} if args.pts is not None else {}),
        epsilon=args.epsilon,
        collect_stochastic=args.collect_stochastic,
        fixed_bc_opponents=args.fixed_bc_opponents,
        opponent_bc_checkpoint=args.opponent_bc_checkpoint,
        opponent_mix_ratio=args.opponent_mix_ratio,
        n_frozen_seats=args.n_frozen_seats,
        snapshot_interval=args.snapshot_interval,
        pool_capacity=args.pool_capacity,
        pool_sampling=args.pool_sampling,
        pfsp_p=args.pfsp_p,
        save_path=args.save_path,
        snapshot_dir=args.snapshot_dir,
        save_interval=args.save_interval,
        keep_periodic=not args.no_keep_periodic,
        log_interval=args.log_interval,
        device=args.device,
        seed=args.seed,
        scorer_hidden=args.scorer_hidden,
        action_proj_dim=args.action_proj_dim or None,
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

    print(f"[train_mortal_v5] config: {cfg}")
    train_mortal_v5(bc_checkpoint=args.bc_checkpoint, config=cfg,
                    transformer_config=tcfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
