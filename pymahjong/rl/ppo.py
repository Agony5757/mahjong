"""Stage 2: PPO + self-play reinforcement learning.

The trainer runs N parallel :class:`EncodingMultiAgentEnv` instances and
collects per-seat trajectories. At episode end, the final payoff (in
points / 25000) is back-propagated as the terminal reward; intermediate
steps receive zero reward.

Each PPO update treats the union of all seats' transitions as a single
batch -- this is a "self-play with shared parameters" setup.

Usage::

    from pymahjong.rl import train_ppo
    train_ppo(
        bc_checkpoint="checkpoints/bc.pt",
        save_path="checkpoints/ppo.pt",
        total_steps=10_000_000,
    )
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F

from .action_space import ACTION_DIM
from .buffers import RolloutBuffer, ppo_obs_collate
from .encoding import EncodingVersion, get_strategy
from . import encodings  # noqa: F401 -- trigger strategy registration
from .envs import EncodingMultiAgentEnv


@dataclass
class PPOConfig:
    total_steps: int = 1_000_000
    rollout_steps: int = 4096       # transitions collected per update
    n_envs: int = 8
    batch_size: int = 256
    n_epochs: int = 4
    gamma: float = 0.99
    lam: float = 0.95
    clip_range: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    lr: float = 3e-4
    grad_clip: float = 0.5
    save_interval: int = 50_000
    save_path: str = "ppo.pt"
    device: Optional[str] = None
    encoding: str = "v3"


def _device(cfg: PPOConfig) -> torch.device:
    if cfg.device:
        return torch.device(cfg.device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _obs_to_tensors(obs: dict, device: torch.device):
    """Convert a single observation dict to model-ready tensors.

    Works with V3 (``tokens`` key) and V4 (``features`` key).
    """
    if "tokens" in obs:
        return (
            torch.as_tensor(obs["tokens"], device=device, dtype=torch.long).unsqueeze(0),
            torch.as_tensor(obs["attention_mask"], device=device, dtype=torch.bool).unsqueeze(0),
            torch.as_tensor(obs["action_mask"], device=device, dtype=torch.bool).unsqueeze(0),
        )
    feat = torch.as_tensor(obs["features"], device=device).unsqueeze(0)
    if feat.is_floating_point() is False:
        feat = feat.float()
    return (
        feat,
        torch.as_tensor(obs["attention_mask"], device=device, dtype=torch.bool).unsqueeze(0),
        torch.as_tensor(obs["action_mask"], device=device, dtype=torch.bool).unsqueeze(0),
    )


def collect_rollout(envs, model, buffer: RolloutBuffer, device, n_steps: int):
    """Collect ``n_steps`` transitions across env instances using self-play.

    Each transition is associated with the *acting* seat at that step.
    Terminal rewards are written when the episode ends; intermediate
    rewards are 0.

    To keep things simple, we maintain *per-seat* pending lists per env;
    when the episode ends we backfill the seat's last transition with the
    payoff and mark its done flag.
    """
    model.eval()
    obs_per_env = [None] * len(envs)
    last_transition_idx = [
        {seat: -1 for seat in range(4)} for _ in envs
    ]
    pending_payoff = [None] * len(envs)

    for i, env in enumerate(envs):
        obs_per_env[i] = env.reset()

    collected = 0
    while collected < n_steps:
        for i, env in enumerate(envs):
            if collected >= n_steps:
                break
            if env.is_over():
                # Backfill payoffs into pending transitions
                payoffs = pending_payoff[i] if pending_payoff[i] is not None else np.zeros(4, dtype=np.float32)
                for seat in range(4):
                    idx = last_transition_idx[i][seat]
                    if idx >= 0:
                        buffer.rewards[idx] = float(payoffs[seat])
                        buffer.dones[idx] = True
                obs_per_env[i] = env.reset()
                last_transition_idx[i] = {seat: -1 for seat in range(4)}
                pending_payoff[i] = None
                continue

            obs = obs_per_env[i]
            seat = env.current_player
            t_feat, t_attn, t_mask = _obs_to_tensors(obs, device)
            with torch.no_grad():
                action, log_prob, value = model.act(t_feat, t_attn, t_mask)
            a = int(action.item())
            lp = float(log_prob.item())
            v = float(value.item())

            buf_idx = buffer.size
            buffer.add(obs, a, lp, v, reward=0.0, done=False)
            last_transition_idx[i][seat] = buf_idx
            collected += 1

            next_obs, payoffs, done, _ = env.step(a)
            if done:
                pending_payoff[i] = payoffs
                obs_per_env[i] = None
            else:
                obs_per_env[i] = next_obs

    # Last-value bootstrap = 0 because all unfinished tails are bootstrapped
    # with V≈0 (we'll let GAE handle non-terminal cutoff).
    buffer.compute_gae(last_value=0.0)


def train_ppo(
    bc_checkpoint: Optional[str] = None,
    config: Optional[PPOConfig] = None,
    transformer_config=None,
    encoding: str = "v3",
):
    """Train a policy with PPO + self-play.

    Args:
        bc_checkpoint: path to a BC checkpoint to warm-start from.
        config: :class:`PPOConfig`.
        transformer_config: transformer architecture config.
        encoding: encoding version (``"v3"`` or ``"v4"``).
    """
    cfg = config or PPOConfig()
    device = _device(cfg)

    strategy = get_strategy(EncodingVersion(encoding))
    model = strategy.create_model(transformer_config=transformer_config).to(device)

    if bc_checkpoint and os.path.exists(bc_checkpoint):
        ckpt = torch.load(bc_checkpoint, map_location=device)
        model.load_state_dict(ckpt["model"], strict=False)
        print(f"[PPO] Loaded BC checkpoint from {bc_checkpoint}")

    optim = torch.optim.AdamW(model.parameters(), lr=cfg.lr)

    envs = [EncodingMultiAgentEnv(encoding=encoding) for _ in range(cfg.n_envs)]
    buffer = RolloutBuffer(capacity=cfg.rollout_steps + cfg.n_envs * 32, device=str(device))

    collate_obs = ppo_obs_collate if encoding == "v3" else strategy.collate_fn

    total_collected = 0
    while total_collected < cfg.total_steps:
        buffer.reset()
        collect_rollout(envs, model, buffer, device, cfg.rollout_steps)
        total_collected += buffer.size

        # Normalize advantages
        adv = buffer.advantages[: buffer.size]
        if adv.std() > 1e-6:
            buffer.advantages[: buffer.size] = (adv - adv.mean()) / (adv.std() + 1e-6)

        model.train()
        for _ in range(cfg.n_epochs):
            for mb in buffer.iterate_minibatches(cfg.batch_size, collate_obs):
                new_log_prob, entropy, value = model.evaluate_actions(
                    mb["tokens"] if "tokens" in mb else mb["features"],
                    mb["attention_mask"],
                    mb["action_mask"],
                    mb["actions"],
                )
                ratio = torch.exp(new_log_prob - mb["old_log_probs"])
                surr1 = ratio * mb["advantages"]
                surr2 = torch.clamp(ratio, 1 - cfg.clip_range, 1 + cfg.clip_range) * mb["advantages"]
                policy_loss = -torch.min(surr1, surr2).mean()

                value_pred_clipped = mb["old_values"] + (value - mb["old_values"]).clamp(
                    -cfg.clip_range, cfg.clip_range
                )
                v_loss1 = (value - mb["returns"]).pow(2)
                v_loss2 = (value_pred_clipped - mb["returns"]).pow(2)
                value_loss = 0.5 * torch.max(v_loss1, v_loss2).mean()

                entropy_loss = -entropy.mean()
                loss = policy_loss + cfg.value_coef * value_loss + cfg.entropy_coef * entropy_loss

                optim.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
                optim.step()

        print(
            f"[PPO] collected={total_collected}  "
            f"pi_loss={policy_loss.item():.4f}  v_loss={value_loss.item():.4f}  "
            f"H={(-entropy_loss).item():.3f}",
            flush=True,
        )

        if total_collected % cfg.save_interval < cfg.rollout_steps and cfg.save_path:
            os.makedirs(os.path.dirname(os.path.abspath(cfg.save_path)) or ".", exist_ok=True)
            torch.save({"model": model.state_dict(), "step": total_collected}, cfg.save_path)

    if cfg.save_path:
        torch.save({"model": model.state_dict(), "step": total_collected}, cfg.save_path)
    return model
