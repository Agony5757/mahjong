#!/usr/bin/env python3
"""V4 self-play PPO training launcher.

Standard recipe::

    # Stage 1: BC warm-start (see tools/train_bc_v4.py)
    python tools/train_bc_v4.py --cache-dir cache/houou --split-by shard \\
        --train-shards shard_2024 --val-shards shard_2025 \\
        --save-path checkpoints/bc_v4.pt --n-steps 100000

    # Stage 2: PPO self-play
    python tools/train_ppo_v4.py \\
        --bc-checkpoint checkpoints/bc_v4.pt \\
        --save-path checkpoints/ppo_v4.pt \\
        --total-steps 5000000 --n-envs 16

Ablation: classical "lock 3, train 1" mode::

    python tools/train_ppo_v4.py --bc-checkpoint ... \\
        --opponent-mix-ratio 1.0 --n-frozen-seats 3
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.v4.selfplay import SelfPlayConfig, train_selfplay_v4


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    # I/O
    ap.add_argument("--bc-checkpoint", type=str, default=None,
                    help="Path to a BC checkpoint to warm-start from (strongly recommended).")
    ap.add_argument("--save-path", type=str, default="checkpoints/ppo_v4.pt")
    ap.add_argument("--snapshot-dir", type=str, default=None,
                    help="If set, persist opponent-pool snapshots under this dir.")

    # Training schedule
    ap.add_argument("--total-steps", type=int, default=1_000_000)
    ap.add_argument("--rollout-steps", type=int, default=4096)
    ap.add_argument("--n-envs", type=int, default=8)
    ap.add_argument("--n-epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--max-seq-len", type=int, default=512)

    # PPO hyper-parameters
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--clip-range", type=float, default=0.2)
    ap.add_argument("--value-coef", type=float, default=0.5)
    ap.add_argument("--entropy-coef", type=float, default=0.01)
    ap.add_argument("--lr", type=float, default=3e-4)
    ap.add_argument("--grad-clip", type=float, default=0.5)

    # Self-play / opponent pool
    ap.add_argument("--opponent-mix-ratio", type=float, default=0.25,
                    help="Probability of mixing in frozen snapshots per episode. "
                         "0.0=pure shared self-play; 1.0=always mix.")
    ap.add_argument("--n-frozen-seats", type=int, default=1, choices=[0, 1, 2, 3],
                    help="When mixing, how many seats use frozen snapshots.")
    ap.add_argument("--snapshot-interval", type=int, default=50_000,
                    help="Take a snapshot every N learner transitions.")
    ap.add_argument("--pool-capacity", type=int, default=20)
    ap.add_argument("--pool-sampling", choices=["uniform", "latest", "pfsp"], default="pfsp")
    ap.add_argument("--pfsp-p", type=float, default=2.0)

    # Normalization
    ap.add_argument("--no-reward-norm", action="store_true")
    ap.add_argument("--no-advantage-norm", action="store_true")

    # Reward shaping (bootstrap)
    ap.add_argument("--win-bonus-coef", type=float, default=0.5,
                    help="Linear coefficient applied to each winner's payoff and "
                         "added as an extra terminal reward on every agari "
                         "(Ron/Tsumo/NagashiMangan). Bonus = coef * payoff[winner], "
                         "so larger wins (yakuman, haneman, ...) yield proportionally "
                         "larger bonuses; ryuukyoku yields none. The winner's "
                         "effective reward becomes payoff * (1 + coef). "
                         "Set to 0 to disable. Default: 0.5.")

    # Model
    ap.add_argument("--d-model", type=int, default=256)
    ap.add_argument("--n-layers", type=int, default=6)
    ap.add_argument("--n-heads", type=int, default=8)
    ap.add_argument("--ff-mult", type=int, default=4)
    ap.add_argument("--dropout", type=float, default=0.1)

    # Misc
    ap.add_argument("--device", type=str, default=None,
                    help="cpu / cuda / cuda:0 / ...  Default: auto-detect.")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--save-interval", type=int, default=100_000)
    ap.add_argument("--log-interval", type=int, default=1)
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
    )

    cfg = SelfPlayConfig(
        total_steps=args.total_steps,
        rollout_steps=args.rollout_steps,
        n_envs=args.n_envs,
        n_epochs=args.n_epochs,
        batch_size=args.batch_size,
        max_seq_len=args.max_seq_len,
        gamma=args.gamma,
        lam=args.lam,
        clip_range=args.clip_range,
        value_coef=args.value_coef,
        entropy_coef=args.entropy_coef,
        lr=args.lr,
        grad_clip=args.grad_clip,
        opponent_mix_ratio=args.opponent_mix_ratio,
        n_frozen_seats=args.n_frozen_seats,
        snapshot_interval=args.snapshot_interval,
        pool_capacity=args.pool_capacity,
        pool_sampling=args.pool_sampling,
        pfsp_p=args.pfsp_p,
        reward_norm=not args.no_reward_norm,
        advantage_norm=not args.no_advantage_norm,
        win_bonus_coef=args.win_bonus_coef,
        save_path=args.save_path,
        snapshot_dir=args.snapshot_dir,
        save_interval=args.save_interval,
        log_interval=args.log_interval,
        device=args.device,
        seed=args.seed,
    )

    print(f"[train_ppo_v4] config: {cfg}")
    train_selfplay_v4(
        bc_checkpoint=args.bc_checkpoint,
        config=cfg,
        transformer_config=tcfg,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
