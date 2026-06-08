#!/usr/bin/env python3
"""V5 (Douzero-style) self-play PPO training launcher.

V5 reuses the V4 self-play infrastructure (env, opponent pool, GAE,
PPO loss) and swaps the policy model for the Douzero-style
:class:`DouzeroV5Transformer` (per-legal-action shared MLP scorer).
See :mod:`pymahjong.rl.v5` for the architecture rationale.

Standard recipe::

    # Stage 1: V5 BC warm-start on the leak-free cache
    python tools/train_bc_v5.py --split-by shard \\
        --train-shards 'c2501_*,c2502_*,c2503_*,c2504_*,c2505_*,c2506_*' \\
        --val-shards 'c2507_*' --test-shards 'c2508_*,c0001_*' \\
        --n-steps 40000 --save-path checkpoints/bc_v5_clean.pt

    # Stage 2: V5 PPO self-play (fine-tune)
    python tools/train_ppo_v5.py \\
        --bc-checkpoint checkpoints/bc_v5_clean.best.pt \\
        --save-path checkpoints/ppo_v5_clean.pt \\
        --snapshot-dir checkpoints/ppo_v5_snapshots \\
        --total-steps 500000 --rollout-steps 16384 \\
        --lr 1e-4 --win-bonus-coef 0.5

V5 differs from V4 in two ways that matter at launch time:

* Model defaults are pinned to the BC ckpt shape (192 / 4 / 6 / 4) so
  warm-start ``load_state_dict`` succeeds without manual overrides.
* ``--split-heads`` is gone — V5's shared scorer subsumes phase routing
  via the descriptor's phase bit.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.v4.selfplay import SelfPlayConfig, train_selfplay_v4


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    # I/O
    ap.add_argument("--bc-checkpoint", type=str, default=None,
                    help="Path to a V5 BC checkpoint to warm-start from "
                         "(strongly recommended).")
    ap.add_argument("--save-path", type=str, default="checkpoints/ppo_v5.pt")
    ap.add_argument("--snapshot-dir", type=str, default=None,
                    help="If set, persist opponent-pool snapshots under this dir.")

    # Training schedule
    ap.add_argument("--total-steps", type=int, default=500_000,
                    help="Total learner transitions across the entire run.  "
                         "500K is enough for a first PPO fine-tune pass on top "
                         "of a strong BC init (~5-10 hours on RTX 5080).  "
                         "Scale up once you've validated the loop converges.")
    ap.add_argument("--rollout-steps", type=int, default=16384,
                    help="Learner transitions per PPO update.")
    ap.add_argument("--n-envs", type=int, default=8)
    ap.add_argument("--n-epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=256)
    ap.add_argument("--max-seq-len", type=int, default=512)

    # PPO hyper-parameters -- conservative defaults for fine-tuning.
    ap.add_argument("--gamma", type=float, default=0.99)
    ap.add_argument("--lam", type=float, default=0.95)
    ap.add_argument("--clip-range", type=float, default=0.2)
    ap.add_argument("--value-coef", type=float, default=0.5)
    ap.add_argument("--entropy-coef", type=float, default=0.01)
    ap.add_argument("--lr", type=float, default=1e-4,
                    help="Fine-tuning learning rate.  Lower than BC's 3e-4 to "
                         "avoid destabilising the warm-start policy.")
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
    ap.add_argument("--pool-sampling", choices=["uniform", "latest", "pfsp"],
                    default="pfsp")
    ap.add_argument("--pfsp-p", type=float, default=2.0)

    # Normalization
    ap.add_argument("--no-reward-norm", action="store_true")
    ap.add_argument("--no-advantage-norm", action="store_true")

    # Reward shaping
    ap.add_argument("--win-bonus-coef", type=float, default=0.5,
                    help="Linear coefficient on each winner's payoff added as "
                         "an extra terminal reward (Bonus = coef * payoff[winner]). "
                         "Default 0.5 encourages high-score wins.  Clean BC "
                         "already has ~20-35%% agari rate, so we keep some "
                         "shaping to bias towards bigger wins (yakuman/haneman).")
    ap.add_argument("--reward-clip", type=float, default=3.0,
                    help="Symmetric clip on normalized terminal reward.")

    # Model (defaults pinned to the standard V5 BC ckpt shape 192/4/6/4).
    ap.add_argument("--d-model", type=int, default=192)
    ap.add_argument("--n-layers", type=int, default=4)
    ap.add_argument("--n-heads", type=int, default=6)
    ap.add_argument("--ff-mult", type=int, default=4)
    ap.add_argument("--dropout", type=float, default=0.1)
    ap.add_argument("--use-pos-emb", action="store_true",
                    help="Add a learned positional embedding to V5 events.")
    # V5-specific Douzero head shape (must match BC ckpt's scorer width).
    ap.add_argument("--scorer-hidden", type=int, default=256,
                    help="Hidden width of the shared (state, action) MLP.")
    ap.add_argument("--action-proj-dim", type=int, default=0,
                    help="V5 action-embedding width.  0 = match d_model.")

    # Periodic self-play evaluation (clean tsumo/ron/houjuu/ryuu rates).
    ap.add_argument("--selfplay-eval-interval", type=int, default=5,
                    help="Run a clean self-play eval every N PPO updates "
                         "and log tsumo/ron/houjuu/ryuukyoku rates as "
                         "[PPO-SP] lines.  0 disables.  Default 5 ~ once "
                         "per ~80K learner steps (with rollout_steps=16384).")
    ap.add_argument("--selfplay-eval-hands", type=int, default=64,
                    help="Hands per eval call.  Larger = lower variance, "
                         "but ~0.3 s/hand on RTX 5080.")
    ap.add_argument("--selfplay-eval-stochastic", action="store_true",
                    help="Sample (vs argmax) during eval -- catches mode "
                         "collapse but adds variance.")
    ap.add_argument("--selfplay-eval-seed", type=int, default=12345)

    # Misc
    ap.add_argument("--device", type=str, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--save-interval", type=int, default=100_000)
    ap.add_argument("--log-interval", type=int, default=1)

    # wandb logging (optional; single run for train + eval metrics)
    ap.add_argument("--wandb-project", type=str, default=None,
                    help="Enable wandb logging to this project.")
    ap.add_argument("--wandb-entity", type=str, default=None)
    ap.add_argument("--wandb-name", type=str, default=None)
    ap.add_argument("--wandb-tags", type=str, default=None,
                    help="Comma-separated tags.")
    ap.add_argument("--wandb-mode", type=str, default="online",
                    choices=["online", "offline", "disabled"])

    # Mortal head-to-head eval on every checkpoint save (1v3 + 3v1)
    ap.add_argument("--mortal-eval", action="store_true",
                    help="After each checkpoint save, benchmark vs Mortal "
                         "(1v3 and 3v1) and log to wandb.")
    ap.add_argument("--mortal-eval-hanchan", type=int, default=16,
                    help="Hanchan per matchup.")
    ap.add_argument("--mortal-bench-script", type=str, default=None,
                    help="Absolute path to mjai_bench_v2.py.")
    ap.add_argument("--mortal-bench-cwd", type=str, default=None,
                    help="Working dir for the bench subprocess (its src/).")
    ap.add_argument("--mortal-ckpt", type=str, default=None,
                    help="Absolute path to Mortal .pth weights.")
    ap.add_argument("--mortal-eval-python", type=str, default=None,
                    help="Interpreter for the eval subprocess "
                         "(default: this Python).")
    ap.add_argument("--mortal-eval-out-dir", type=str, default=None,
                    help="Root dir for per-step eval logs "
                         "(default: <save_path dir>/mortal_eval).")
    ap.add_argument("--mortal-eval-timeout", type=float, default=1800.0,
                    help="Per-matchup subprocess timeout (seconds).")
    ap.add_argument("--mortal-eval-amp", action="store_true",
                    help="Pass --amp to the Mortal agent.")
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

    cfg = SelfPlayConfig(
        encoding="v5",
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
        reward_clip=args.reward_clip,
        save_path=args.save_path,
        snapshot_dir=args.snapshot_dir,
        save_interval=args.save_interval,
        log_interval=args.log_interval,
        device=args.device,
        seed=args.seed,
        # V5 ignores split_heads -- shared scorer handles phase routing.
        split_heads=False,
        scorer_hidden=args.scorer_hidden,
        action_proj_dim=args.action_proj_dim or None,
        selfplay_eval_interval=args.selfplay_eval_interval,
        selfplay_eval_hands=args.selfplay_eval_hands,
        selfplay_eval_deterministic=not args.selfplay_eval_stochastic,
        selfplay_eval_seed=args.selfplay_eval_seed,
        # wandb
        wandb_project=args.wandb_project,
        wandb_entity=args.wandb_entity,
        wandb_name=args.wandb_name,
        wandb_tags=(tuple(t.strip() for t in args.wandb_tags.split(","))
                    if args.wandb_tags else None),
        wandb_mode=args.wandb_mode,
        # Mortal head-to-head eval on each checkpoint
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

    print(f"[train_ppo_v5] config: {cfg}")
    train_selfplay_v4(
        bc_checkpoint=args.bc_checkpoint,
        config=cfg,
        transformer_config=tcfg,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
