"""V4 self-play PPO trainer.

A complete reinforcement-learning loop for the V4 event-stream encoding.

Design (see ``docs/plan.md`` / README for the full rationale):

1. **Shared-parameter self-play** by default — all four seats use the
   current learner policy.  This is 4× more sample-efficient than
   "lock 3, train 1" and is what Suphx / AlphaStar / OpenAI Five do.

2. **Opponent pool** (`OpponentPool`) — every ``snapshot_interval``
   PPO updates we freeze a copy of the learner.  With probability
   ``opponent_mix_ratio``, each new episode replaces ``n_frozen_seats``
   seats with sampled snapshots (default 1 seat).  This injects
   intransitivity-breaking diversity into self-play.

3. **Per-seat trajectories** — Mahjong turn order is irregular, so we
   keep a buffer per (env, seat) pair and compute GAE per seat at
   episode end.  Terminal reward = ``payoff / 25000`` (matches existing
   PPO), optionally augmented by a per-winner bonus linear in the
   winning payoff (``win_bonus_coef * payoff[winner]``) to bootstrap
   learning toward agari.

4. **PPO update** uses only *learner* seats' transitions.  Snapshot
   seats just produce environment transitions for the learners; their
   own actions are not back-propagated.

5. **Configurable "lock-3-train-1" mode** — setting
   ``opponent_mix_ratio=1.0`` and ``n_frozen_seats=3`` reduces this to
   the classical single-learner setup for ablation studies.

Usage::

    from pymahjong.rl.v4.selfplay import train_selfplay_v4, SelfPlayConfig
    train_selfplay_v4(
        bc_checkpoint="checkpoints/bc_v4.pt",
        config=SelfPlayConfig(total_steps=2_000_000, n_envs=16),
    )
"""

from __future__ import annotations

import copy
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn.functional as F
except Exception as e:  # noqa: BLE001
    raise RuntimeError("torch is required for V4 self-play training") from e

from ..common.config import TransformerConfig
from ..v4.cached_dataset import cached_event_collate
from ..v4.env import PolicyFn, V4MultiAgentEnv
from ..v4.model import EventStreamTransformer
from ..v4.opponent_pool import OpponentPool, Snapshot


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class SelfPlayConfig:
    """Training configuration for V4 self-play PPO."""

    # -- training schedule --
    total_steps: int = 1_000_000
    """Total *learner transitions* to collect across the entire run."""
    rollout_steps: int = 16384
    """Learner transitions per PPO update.  Mahjong is high-variance:
    a single hand averages ~50 actions and only ~25 hands fit in 2048
    transitions, which makes per-rollout win-rate / payoff metrics
    very noisy.  16384 transitions ≈ 200-300 hands per rollout, giving
    statistically meaningful per-update stats."""
    n_envs: int = 8
    """Parallel env instances (sampled round-robin)."""
    n_epochs: int = 4
    batch_size: int = 256

    # -- PPO hyper-parameters --
    gamma: float = 0.99
    lam: float = 0.95
    clip_range: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    lr: float = 3e-4
    grad_clip: float = 0.5
    max_seq_len: int = 512

    # -- self-play / opponent pool --
    opponent_mix_ratio: float = 0.25
    """Probability that a freshly reset episode pulls in frozen opponents.
    ``0.0`` = pure shared self-play; ``1.0`` = always mix in snapshots."""
    n_frozen_seats: int = 1
    """How many seats (1-3) get replaced with snapshots when mixing.
    Set to 3 + ratio 1.0 for the classical "lock 3, train 1" mode."""
    snapshot_interval: int = 50_000
    """Take a snapshot every this many *learner transitions*."""
    pool_capacity: int = 20
    pool_sampling: str = "pfsp"
    pfsp_p: float = 2.0

    # -- normalization --
    reward_norm: bool = True
    """If True, divide rewards by an EMA of |reward| to stabilize."""
    advantage_norm: bool = True

    # -- reward shaping (bootstrap) --
    win_bonus_coef: float = 0.0
    """Linear coefficient applied to each *winner*'s payoff and added as
    an extra terminal reward on agari (RonAgari / TsumoAgari /
    NagashiMangan).  Concretely, for each ``w`` in ``winners`` we add
    ``win_bonus_coef * payoff[w]`` (in units of 25 000 points, same
    scale as the base reward).  This makes the bootstrap signal
    *linear in the winning score*: a yakuman win gives ~4× the bonus
    of a mangan win, while ryuukyoku gives no bonus at all.
    Effectively the winner's terminal reward becomes
    ``payoff[w] * (1 + win_bonus_coef)``.  The shaped reward is fed to
    :class:`_RewardNormalizer` so the EMA tracks the augmented scale.
    Set to ``0.0`` to disable (default)."""

    reward_clip: float = 3.0
    """Symmetric clip applied to the *normalized* terminal reward fed
    into GAE.  Prevents rare yakuman / huge-han wins from saturating
    the value head (we observed value-loss spikes up to ~2.0 without
    clipping while the median is < 0.05).  ``0`` or negative disables.
    Default ``3.0`` ≈ 3× the running |reward| EMA scale, which keeps
    99% of payoffs unclipped while taming yakuman outliers."""

    # -- I/O --
    save_path: str = "checkpoints/ppo_v4.pt"
    save_interval: int = 100_000
    snapshot_dir: Optional[str] = None
    """If set, snapshots are also persisted to disk under this directory."""

    # -- misc --
    device: Optional[str] = None
    seed: Optional[int] = None
    log_interval: int = 1
    """Print a log line every N PPO updates."""


# ---------------------------------------------------------------------------
# Per-seat trajectory buffer
# ---------------------------------------------------------------------------


@dataclass
class _SeatTraj:
    """In-progress trajectory for one (env, seat) pair."""

    obs: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[int] = field(default_factory=list)
    log_probs: List[float] = field(default_factory=list)
    values: List[float] = field(default_factory=list)
    rewards: List[float] = field(default_factory=list)


@dataclass
class _SeatBatch:
    """Finalized batch of learner transitions ready for PPO."""

    obs: List[Dict[str, Any]] = field(default_factory=list)
    actions: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    log_probs: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    values: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    advantages: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))
    returns: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.float32))

    def __len__(self) -> int:
        return self.actions.shape[0]


def _compute_gae_for_seat(
    traj: _SeatTraj,
    terminal_reward: float,
    gamma: float,
    lam: float,
) -> Tuple[np.ndarray, np.ndarray]:
    """Compute GAE advantages + discounted returns for one seat's trajectory.

    Mahjong rewards are sparse and terminal: every intermediate reward
    is 0, and on the terminal step the seat receives ``terminal_reward``.
    We treat the trajectory as a single episode terminating at the last
    step; the value-network bootstrap at the end is ``0`` because the
    episode is fully observed.
    """
    n = len(traj.actions)
    advantages = np.zeros(n, dtype=np.float32)
    returns = np.zeros(n, dtype=np.float32)
    # Inject terminal reward into the last transition.
    if n > 0:
        rewards = np.asarray(traj.rewards, dtype=np.float32).copy()
        rewards[-1] += float(terminal_reward)
        values = np.asarray(traj.values, dtype=np.float32)
        adv = 0.0
        for t in reversed(range(n)):
            next_v = 0.0 if t == n - 1 else values[t + 1]
            non_terminal = 0.0 if t == n - 1 else 1.0
            delta = rewards[t] + gamma * next_v * non_terminal - values[t]
            adv = delta + gamma * lam * non_terminal * adv
            advantages[t] = adv
        returns = advantages + values
    return advantages, returns


# ---------------------------------------------------------------------------
# Reward normalization
# ---------------------------------------------------------------------------


class _RewardNormalizer:
    """Running |reward| EMA used to rescale terminal payoffs."""

    def __init__(self, beta: float = 0.99, eps: float = 1e-2):
        self.beta = beta
        self.eps = eps
        self.mean_abs = 1.0

    def update(self, payoffs: np.ndarray) -> None:
        cur = float(np.mean(np.abs(payoffs)))
        self.mean_abs = self.beta * self.mean_abs + (1.0 - self.beta) * cur

    def normalize(self, payoffs: np.ndarray) -> np.ndarray:
        scale = max(self.mean_abs, self.eps)
        return payoffs / scale


# ---------------------------------------------------------------------------
# Snapshot policy adapter
# ---------------------------------------------------------------------------


def _make_snapshot_policy(
    model: EventStreamTransformer,
    device: torch.device,
) -> PolicyFn:
    """Wrap a frozen model as a deterministic ``PolicyFn``.

    Snapshot opponents act greedily (``argmax`` over masked logits) so
    their behaviour is reproducible and they don't contribute additional
    exploration noise to the learner's environment.
    """

    @torch.no_grad()
    def _policy(obs: Dict[str, Any], seat: int) -> int:
        feat = torch.as_tensor(obs["features"], device=device, dtype=torch.float32).unsqueeze(0)
        attn = torch.as_tensor(obs["attention_mask"], device=device, dtype=torch.bool).unsqueeze(0)
        mask = torch.as_tensor(obs["action_mask"], device=device, dtype=torch.bool).unsqueeze(0)
        action, _, _ = model.act(feat, attn, mask, deterministic=True)
        return int(action.item())

    return _policy


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------


class SelfPlayPPOTrainer:
    """Encapsulates the PPO + opponent-pool self-play loop for V4.

    See :func:`train_selfplay_v4` for the recommended entry point.
    """

    def __init__(
        self,
        config: Optional[SelfPlayConfig] = None,
        transformer_config: Optional[TransformerConfig] = None,
        bc_checkpoint: Optional[str] = None,
    ):
        self.cfg = config or SelfPlayConfig()
        self._device = torch.device(
            self.cfg.device
            or ("cuda" if torch.cuda.is_available() else "cpu")
        )
        if self.cfg.seed is not None:
            torch.manual_seed(self.cfg.seed)
            np.random.seed(self.cfg.seed)

        tcfg = transformer_config or TransformerConfig()
        self.model = EventStreamTransformer(config=tcfg).to(self._device)

        if bc_checkpoint and os.path.exists(bc_checkpoint):
            self._load_bc(bc_checkpoint)

        self.optim = torch.optim.AdamW(self.model.parameters(), lr=self.cfg.lr)
        self.envs: List[V4MultiAgentEnv] = [
            V4MultiAgentEnv(max_seq_len=self.cfg.max_seq_len)
            for _ in range(self.cfg.n_envs)
        ]
        self.pool = OpponentPool(
            capacity=self.cfg.pool_capacity,
            sampling=self.cfg.pool_sampling,
            pfsp_p=self.cfg.pfsp_p,
            seed=self.cfg.seed,
            save_dir=self.cfg.snapshot_dir,
        )
        self.reward_norm = _RewardNormalizer() if self.cfg.reward_norm else None

        # Per-env state (assigned on reset).
        self._env_state: List[Dict[str, Any]] = [
            self._fresh_env_state() for _ in range(self.cfg.n_envs)
        ]
        for i, env in enumerate(self.envs):
            self._reset_env(i, env)

        self._total_learner_steps = 0
        self._next_snapshot_at = self.cfg.snapshot_interval

    # ------------------------------------------------------------------ utils

    def _load_bc(self, path: str) -> None:
        ckpt = torch.load(path, map_location=self._device)
        state = ckpt.get("model", ckpt)
        # ``strict=False`` so the BC checkpoint can have minor key drift.
        missing, unexpected = self.model.load_state_dict(state, strict=False)
        if missing:
            print(f"[selfplay] BC ckpt missing keys: {missing[:5]}{'...' if len(missing) > 5 else ''}")
        if unexpected:
            print(f"[selfplay] BC ckpt unexpected keys: {unexpected[:5]}{'...' if len(unexpected) > 5 else ''}")
        print(f"[selfplay] Loaded BC checkpoint from {path}")

    def _fresh_env_state(self) -> Dict[str, Any]:
        return {
            "trajs": {seat: _SeatTraj() for seat in range(4)},
            "opponent_seats": set(),  # subset of {0,1,2,3}
            "opponent_snapshot": None,  # Snapshot or None
        }

    # ------------------------------------------------------------------ opp assignment

    def _assign_opponents(self) -> Tuple[Dict[int, PolicyFn], set, Optional[Snapshot]]:
        """Decide which seats are learner-controlled vs snapshot-controlled.

        Returns ``(policy_map, opponent_seats, snapshot)``.  ``policy_map``
        can be passed straight to :meth:`V4MultiAgentEnv.set_opponent_policies`.
        """
        if (
            self.cfg.opponent_mix_ratio <= 0.0
            or self.pool.is_empty()
            or self.cfg.n_frozen_seats <= 0
            or np.random.rand() >= self.cfg.opponent_mix_ratio
        ):
            return {}, set(), None
        snap = self.pool.sample()
        if snap is None:
            return {}, set(), None
        # Load snapshot into a transient model (kept on CPU/GPU per device).
        opp_model = EventStreamTransformer(config=self.model.cfg).to(self._device)
        opp_model.load_state_dict(snap.state_dict)
        opp_model.eval()
        policy = _make_snapshot_policy(opp_model, self._device)
        k = int(min(self.cfg.n_frozen_seats, 3))
        opp_seats = set(np.random.choice(4, size=k, replace=False).tolist())
        policy_map = {seat: policy for seat in opp_seats}
        return policy_map, opp_seats, snap

    def _reset_env(self, idx: int, env: V4MultiAgentEnv) -> Dict[str, Any]:
        policies, opp_seats, snap = self._assign_opponents()
        env.set_opponent_policies(policies)
        obs = env.reset()
        self._env_state[idx] = {
            "trajs": {seat: _SeatTraj() for seat in range(4)},
            "opponent_seats": opp_seats,
            "opponent_snapshot": snap,
        }
        # If the *first* acting seat is an opponent, auto-step until a learner.
        env._auto_step_opponents()
        if env.is_over():
            # Degenerate hand (rare); recurse to get a fresh episode.
            return self._reset_env(idx, env)
        return obs

    # ------------------------------------------------------------------ collection

    def _act_learner(
        self,
        obs: Dict[str, Any],
    ) -> Tuple[int, float, float]:
        self.model.eval()
        feat = torch.as_tensor(obs["features"], device=self._device, dtype=torch.float32).unsqueeze(0)
        attn = torch.as_tensor(obs["attention_mask"], device=self._device, dtype=torch.bool).unsqueeze(0)
        mask = torch.as_tensor(obs["action_mask"], device=self._device, dtype=torch.bool).unsqueeze(0)
        with torch.no_grad():
            action, log_prob, value = self.model.act(feat, attn, mask, deterministic=False)
        return int(action.item()), float(log_prob.item()), float(value.item())

    def _act_learner_batch(
        self,
        obs_list: List[Dict[str, Any]],
    ) -> Tuple[List[int], List[float], List[float]]:
        """Batched version of :meth:`_act_learner`.

        Stacks ``obs_list`` into a single padded batch and runs *one* forward
        through the policy.  With ``n_envs`` parallel envs this is up to
        ``n_envs``× cheaper than per-env forward calls (most of the cost of
        a tiny transformer on GPU is launch overhead, not arithmetic).
        """
        if not obs_list:
            return [], [], []
        self.model.eval()
        b = self._collate_obs(obs_list)
        feat = b["features"].to(self._device, non_blocking=True)
        attn = b["attention_mask"].to(self._device, non_blocking=True)
        mask = b["action_mask"].to(self._device, non_blocking=True)
        with torch.no_grad():
            actions, log_probs, values = self.model.act(feat, attn, mask, deterministic=False)
        return (
            actions.cpu().tolist(),
            log_probs.cpu().tolist(),
            values.cpu().tolist(),
        )

    def _collect_rollout(self, n_steps: int) -> Tuple[_SeatBatch, Dict[str, float]]:
        """Collect ``n_steps`` learner transitions across all envs."""
        batch = _SeatBatch()
        obs_per_env: List[Optional[Dict[str, Any]]] = [None] * len(self.envs)
        for i, env in enumerate(self.envs):
            obs_per_env[i] = env.observe()

        # Richer per-episode metrics (replace the always-zero "mean_return").
        ep_lengths: List[int] = []
        ep_abs_payoffs: List[float] = []           # mean |payoff| per hand → hand magnitude
        ep_max_winner_payoff: List[float] = []     # max winner payoff per agari hand
        ep_max_loser_payoff: List[float] = []      # max |payoff| of losers per agari hand
        agari_count = 0
        ryuukyoku_count = 0
        learner_step_count = 0

        finalized: List[Tuple[List[Dict[str, Any]], List[int], List[float], List[float], np.ndarray, np.ndarray]] = []

        def _record_episode(payoffs: np.ndarray, winners: list, ep_len: int) -> None:
            nonlocal agari_count, ryuukyoku_count
            ep_lengths.append(ep_len)
            ep_abs_payoffs.append(float(np.mean(np.abs(payoffs))))
            if winners:
                agari_count += 1
                winner_payoffs = [float(payoffs[int(w)]) for w in winners if 0 <= int(w) < 4]
                if winner_payoffs:
                    ep_max_winner_payoff.append(max(winner_payoffs))
                loser_idx = [s for s in range(4) if s not in {int(w) for w in winners}]
                if loser_idx:
                    ep_max_loser_payoff.append(max(abs(float(payoffs[s])) for s in loser_idx))
            else:
                ryuukyoku_count += 1

        def _finalize_terminated_env(i: int, env: V4MultiAgentEnv) -> None:
            """Pull payoffs+winners from a just-terminated env, finalize the
            learner trajectories, record metrics, and reset for a new episode."""
            state = self._env_state[i]
            payoffs_done = env._inner.get_payoffs().astype(np.float32) / 25000.0
            winners_done = env.get_result_info().get("winners", [])
            adv_acc, ret_acc, obs_acc, act_acc, lp_acc, v_acc = (
                self._finalize_env_payoffs(i, payoffs_done, winners_done)
            )
            finalized.append((obs_acc, act_acc, lp_acc, v_acc, adv_acc, ret_acc))
            _record_episode(
                payoffs_done,
                winners_done,
                sum(len(t.actions) for t in state["trajs"].values()),
            )
            obs_per_env[i] = self._reset_env(i, env)

        while learner_step_count < n_steps:
            # ---- 1. Pre-process every env: ensure it's either terminated
            #         or its current player is a learner (auto-step opponents
            #         and finalize+reset terminations along the way).
            ready_env_idx: List[int] = []
            ready_obs: List[Dict[str, Any]] = []
            for i, env in enumerate(self.envs):
                if env.is_over():
                    obs_per_env[i] = self._reset_env(i, env)
                    # After reset the active seat may have changed (e.g. an
                    # opponent took the opening turn inside _reset_env's
                    # _auto_step_opponents); invalidate stale obs.
                    obs_per_env[i] = None

                # Skip opponent moves; if the episode ends inside opponent
                # play, finalize + reset and re-skip on the fresh episode.
                changed = False
                guard = 0
                while True:
                    if env.is_over():
                        _finalize_terminated_env(i, env)
                        obs_per_env[i] = None
                        changed = True
                        guard += 1
                        if guard > 8:
                            # Degenerate; bail to avoid an infinite loop.
                            break
                        continue
                    state = self._env_state[i]
                    if env.current_player in state["opponent_seats"]:
                        env._auto_step_opponents()
                        obs_per_env[i] = None
                        changed = True
                        continue
                    break

                if env.is_over():
                    continue  # too many consecutive degenerate resets

                # Re-observe whenever the current acting seat may have
                # changed; otherwise the cached obs in obs_per_env still
                # matches the current learner's perspective.
                obs = obs_per_env[i] if not changed else None
                if obs is None:
                    obs = env.observe()
                    obs_per_env[i] = obs
                ready_env_idx.append(i)
                ready_obs.append(obs)

            if not ready_env_idx:
                # Pathological: all envs degenerate.  Loop to retry on next
                # iteration (resets happen at top of next iter).
                continue

            # ---- 2. Batched forward over all ready envs.
            actions_b, log_probs_b, values_b = self._act_learner_batch(ready_obs)

            # ---- 3. Apply each action to its env, append to traj, handle term.
            for k, i in enumerate(ready_env_idx):
                if learner_step_count >= n_steps:
                    break
                env = self.envs[i]
                seat = env.current_player  # still the learner seat
                state = self._env_state[i]
                action = int(actions_b[k])
                log_prob = float(log_probs_b[k])
                value = float(values_b[k])

                state["trajs"][seat].obs.append(ready_obs[k])
                state["trajs"][seat].actions.append(action)
                state["trajs"][seat].log_probs.append(log_prob)
                state["trajs"][seat].values.append(value)
                state["trajs"][seat].rewards.append(0.0)
                learner_step_count += 1

                next_obs, payoffs, done, info = env.step(action)
                if done:
                    winners = info.get("winners", []) if isinstance(info, dict) else []
                    adv_acc, ret_acc, obs_acc, act_acc, lp_acc, v_acc = (
                        self._finalize_env_payoffs(i, payoffs, winners)
                    )
                    finalized.append((obs_acc, act_acc, lp_acc, v_acc, adv_acc, ret_acc))
                    _record_episode(
                        payoffs,
                        winners,
                        sum(len(t.actions) for t in state["trajs"].values()),
                    )
                    obs_per_env[i] = self._reset_env(i, env)
                else:
                    obs_per_env[i] = next_obs

        # Flush partial trajectories on envs that didn't terminate inside the
        # rollout window: bootstrap their last value and treat as truncated.
        for i, env in enumerate(self.envs):
            if env.is_over():
                continue
            state = self._env_state[i]
            any_pending = any(len(t.actions) > 0 for t in state["trajs"].values())
            if not any_pending:
                continue
            advantages_acc, returns_acc, obs_acc, act_acc, lp_acc, v_acc = self._finalize_env_truncated(i)
            finalized.append((obs_acc, act_acc, lp_acc, v_acc, advantages_acc, returns_acc))
            # Reset the env's trajs so the next rollout starts clean (but
            # do NOT reset the episode itself — it's still in progress).
            self._env_state[i]["trajs"] = {seat: _SeatTraj() for seat in range(4)}

        # Concatenate everything into a single batch.
        all_obs: List[Dict[str, Any]] = []
        all_acts: List[int] = []
        all_lp: List[float] = []
        all_v: List[float] = []
        all_adv: List[np.ndarray] = []
        all_ret: List[np.ndarray] = []
        for obs_acc, act_acc, lp_acc, v_acc, adv_acc, ret_acc in finalized:
            all_obs.extend(obs_acc)
            all_acts.extend(act_acc)
            all_lp.extend(lp_acc)
            all_v.extend(v_acc)
            all_adv.append(adv_acc)
            all_ret.append(ret_acc)
        if not all_acts:
            return batch, {
                "episodes": 0,
                "agari": 0,
                "ryuukyoku": 0,
                "win_rate": 0.0,
                "mean_length": 0.0,
                "mean_abs_payoff": 0.0,
                "mean_winner_payoff": 0.0,
                "mean_loser_payoff": 0.0,
            }

        batch.obs = all_obs
        batch.actions = np.asarray(all_acts, dtype=np.int64)
        batch.log_probs = np.asarray(all_lp, dtype=np.float32)
        batch.values = np.asarray(all_v, dtype=np.float32)
        batch.advantages = np.concatenate(all_adv).astype(np.float32)
        batch.returns = np.concatenate(all_ret).astype(np.float32)

        if self.cfg.advantage_norm and batch.advantages.std() > 1e-6:
            batch.advantages = (batch.advantages - batch.advantages.mean()) / (batch.advantages.std() + 1e-6)

        total_ep = agari_count + ryuukyoku_count
        stats = {
            "episodes": total_ep,
            "agari": agari_count,
            "ryuukyoku": ryuukyoku_count,
            "win_rate": (agari_count / total_ep) if total_ep > 0 else 0.0,
            "mean_length": float(np.mean(ep_lengths)) if ep_lengths else 0.0,
            "mean_abs_payoff": float(np.mean(ep_abs_payoffs)) if ep_abs_payoffs else 0.0,
            "mean_winner_payoff": float(np.mean(ep_max_winner_payoff)) if ep_max_winner_payoff else 0.0,
            "mean_loser_payoff": float(np.mean(ep_max_loser_payoff)) if ep_max_loser_payoff else 0.0,
        }
        return batch, stats

    def _finalize_env_payoffs(
        self,
        env_idx: int,
        payoffs: np.ndarray,
        winners: Optional[List[int]] = None,
    ) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]], List[int], List[float], List[float]]:
        """Finalize an env that just terminated: produce GAE per learner seat."""
        state = self._env_state[env_idx]
        shaped = payoffs.astype(np.float32, copy=True)
        if winners and self.cfg.win_bonus_coef != 0.0:
            for w in winners:
                wi = int(w)
                if 0 <= wi < 4:
                    shaped[wi] += float(self.cfg.win_bonus_coef) * float(payoffs[wi])
        norm_payoffs = (
            self.reward_norm.normalize(shaped) if self.reward_norm else shaped
        )
        if self.reward_norm:
            self.reward_norm.update(shaped)
        # Clip the (already-normalized) per-seat terminal reward to tame
        # yakuman / huge-han outliers that otherwise destabilize the
        # value head.  Skip when reward_clip <= 0.
        if self.cfg.reward_clip and self.cfg.reward_clip > 0:
            c = float(self.cfg.reward_clip)
            norm_payoffs = np.clip(norm_payoffs, -c, c)
        # Update opponent winrate (learner = top non-opponent seat finish).
        snap: Optional[Snapshot] = state["opponent_snapshot"]
        if snap is not None and state["opponent_seats"]:
            learner_seats = [s for s in range(4) if s not in state["opponent_seats"]]
            best_learner_score = max(payoffs[s] for s in learner_seats)
            best_opp_score = max(payoffs[s] for s in state["opponent_seats"])
            snap.update_winrate(best_learner_score > best_opp_score)

        obs_acc: List[Dict[str, Any]] = []
        act_acc: List[int] = []
        lp_acc: List[float] = []
        v_acc: List[float] = []
        adv_chunks: List[np.ndarray] = []
        ret_chunks: List[np.ndarray] = []
        for seat in range(4):
            if seat in state["opponent_seats"]:
                continue
            traj = state["trajs"][seat]
            if not traj.actions:
                continue
            advs, rets = _compute_gae_for_seat(
                traj,
                terminal_reward=float(norm_payoffs[seat]),
                gamma=self.cfg.gamma,
                lam=self.cfg.lam,
            )
            obs_acc.extend(traj.obs)
            act_acc.extend(traj.actions)
            lp_acc.extend(traj.log_probs)
            v_acc.extend(traj.values)
            adv_chunks.append(advs)
            ret_chunks.append(rets)
        adv_arr = (
            np.concatenate(adv_chunks).astype(np.float32) if adv_chunks else np.zeros(0, dtype=np.float32)
        )
        ret_arr = (
            np.concatenate(ret_chunks).astype(np.float32) if ret_chunks else np.zeros(0, dtype=np.float32)
        )
        return adv_arr, ret_arr, obs_acc, act_acc, lp_acc, v_acc

    def _finalize_env_truncated(
        self, env_idx: int
    ) -> Tuple[np.ndarray, np.ndarray, List[Dict[str, Any]], List[int], List[float], List[float]]:
        """Finalize a non-terminated env at rollout-window cut-off.

        Uses each seat's *own* last value as the bootstrap.
        """
        state = self._env_state[env_idx]
        obs_acc: List[Dict[str, Any]] = []
        act_acc: List[int] = []
        lp_acc: List[float] = []
        v_acc: List[float] = []
        adv_chunks: List[np.ndarray] = []
        ret_chunks: List[np.ndarray] = []
        for seat in range(4):
            if seat in state["opponent_seats"]:
                continue
            traj = state["trajs"][seat]
            if not traj.actions:
                continue
            n = len(traj.actions)
            rewards = np.asarray(traj.rewards, dtype=np.float32)
            values = np.asarray(traj.values, dtype=np.float32)
            last_v = float(values[-1])  # bootstrap with last predicted value
            advantages = np.zeros(n, dtype=np.float32)
            adv = 0.0
            for t in reversed(range(n)):
                next_v = last_v if t == n - 1 else values[t + 1]
                non_terminal = 1.0  # truncated, not terminal
                delta = rewards[t] + self.cfg.gamma * next_v * non_terminal - values[t]
                adv = delta + self.cfg.gamma * self.cfg.lam * non_terminal * adv
                advantages[t] = adv
            returns = advantages + values
            obs_acc.extend(traj.obs)
            act_acc.extend(traj.actions)
            lp_acc.extend(traj.log_probs)
            v_acc.extend(traj.values)
            adv_chunks.append(advantages)
            ret_chunks.append(returns)
        adv_arr = (
            np.concatenate(adv_chunks).astype(np.float32) if adv_chunks else np.zeros(0, dtype=np.float32)
        )
        ret_arr = (
            np.concatenate(ret_chunks).astype(np.float32) if ret_chunks else np.zeros(0, dtype=np.float32)
        )
        return adv_arr, ret_arr, obs_acc, act_acc, lp_acc, v_acc

    def _finalize_env(self, env_idx: int):  # alias for compatibility
        return self._finalize_env_truncated(env_idx)

    # ------------------------------------------------------------------ optimization

    def _ppo_update(self, batch: _SeatBatch) -> Dict[str, float]:
        if len(batch) == 0:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0, "approx_kl": 0.0}
        self.model.train()
        n = len(batch)
        device = self._device

        actions_t = torch.as_tensor(batch.actions, dtype=torch.long, device=device)
        old_log_probs_t = torch.as_tensor(batch.log_probs, dtype=torch.float32, device=device)
        old_values_t = torch.as_tensor(batch.values, dtype=torch.float32, device=device)
        advantages_t = torch.as_tensor(batch.advantages, dtype=torch.float32, device=device)
        returns_t = torch.as_tensor(batch.returns, dtype=torch.float32, device=device)

        loss_acc = {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0, "approx_kl": 0.0}
        n_minibatches = 0

        for _epoch in range(self.cfg.n_epochs):
            idxs = np.random.permutation(n)
            for start in range(0, n, self.cfg.batch_size):
                mb = idxs[start : start + self.cfg.batch_size]
                if len(mb) == 0:
                    continue
                mb_obs = [batch.obs[k] for k in mb]
                collated = self._collate_obs(mb_obs)
                features = collated["features"].to(device).float()
                attn = collated["attention_mask"].to(device)
                amask = collated["action_mask"].to(device)
                mb_actions = actions_t[mb]
                mb_old_lp = old_log_probs_t[mb]
                mb_old_v = old_values_t[mb]
                mb_adv = advantages_t[mb]
                mb_ret = returns_t[mb]

                new_lp, entropy, value = self.model.evaluate_actions(
                    features, attn, amask, mb_actions
                )
                ratio = torch.exp(new_lp - mb_old_lp)
                surr1 = ratio * mb_adv
                surr2 = torch.clamp(ratio, 1.0 - self.cfg.clip_range, 1.0 + self.cfg.clip_range) * mb_adv
                policy_loss = -torch.min(surr1, surr2).mean()

                value_clipped = mb_old_v + (value - mb_old_v).clamp(
                    -self.cfg.clip_range, self.cfg.clip_range
                )
                vloss1 = (value - mb_ret).pow(2)
                vloss2 = (value_clipped - mb_ret).pow(2)
                value_loss = 0.5 * torch.max(vloss1, vloss2).mean()

                entropy_loss = -entropy.mean()
                loss = (
                    policy_loss
                    + self.cfg.value_coef * value_loss
                    + self.cfg.entropy_coef * entropy_loss
                )

                self.optim.zero_grad(set_to_none=True)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.cfg.grad_clip)
                self.optim.step()

                with torch.no_grad():
                    approx_kl = (mb_old_lp - new_lp).mean().item()
                loss_acc["policy_loss"] += policy_loss.item()
                loss_acc["value_loss"] += value_loss.item()
                loss_acc["entropy"] += entropy.mean().item()
                loss_acc["approx_kl"] += approx_kl
                n_minibatches += 1

        if n_minibatches:
            for k in loss_acc:
                loss_acc[k] /= n_minibatches
        return loss_acc

    def _collate_obs(self, obs_list: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
        """Pad a list of variable-length V4 observations into a batched dict."""
        seq_lens = [int(np.asarray(o["attention_mask"]).sum()) for o in obs_list]
        if not seq_lens:
            return {}
        max_len = max(seq_lens)
        event_dim = obs_list[0]["features"].shape[-1]
        b = len(obs_list)
        features = torch.zeros(b, max_len, event_dim, dtype=torch.float32)
        attn = torch.zeros(b, max_len, dtype=torch.bool)
        amask = torch.zeros(b, obs_list[0]["action_mask"].shape[0], dtype=torch.bool)
        for i, (o, l) in enumerate(zip(obs_list, seq_lens)):
            feat_i = np.asarray(o["features"])[:l]
            features[i, :l] = torch.from_numpy(np.ascontiguousarray(feat_i)).float()
            attn[i, :l] = True
            amask[i] = torch.from_numpy(np.ascontiguousarray(np.asarray(o["action_mask"], dtype=np.bool_)))
        return {"features": features, "attention_mask": attn, "action_mask": amask}

    # ------------------------------------------------------------------ public loop

    def train(self) -> EventStreamTransformer:
        cfg = self.cfg
        update = 0
        start_time = time.time()
        while self._total_learner_steps < cfg.total_steps:
            update += 1
            batch, stats = self._collect_rollout(cfg.rollout_steps)
            self._total_learner_steps += len(batch)
            losses = self._ppo_update(batch)

            # Snapshot.
            while self._total_learner_steps >= self._next_snapshot_at:
                self.pool.add_snapshot(self.model, step=self._total_learner_steps)
                self._next_snapshot_at += cfg.snapshot_interval
                print(
                    f"[selfplay] snapshot taken at step={self._total_learner_steps} "
                    f"(pool size={len(self.pool)})",
                    flush=True,
                )

            # Save.
            if cfg.save_path and (update % max(1, cfg.save_interval // cfg.rollout_steps) == 0):
                self._save_checkpoint()

            if update % max(1, cfg.log_interval) == 0:
                elapsed = time.time() - start_time
                sps = self._total_learner_steps / max(elapsed, 1e-9)
                print(
                    f"[selfplay] upd={update} steps={self._total_learner_steps} "
                    f"ep={stats['episodes']} win%={100*stats['win_rate']:.1f} "
                    f"len={stats['mean_length']:.1f} "
                    f"|pay|={stats['mean_abs_payoff']:.3f} "
                    f"win_pay={stats['mean_winner_payoff']:+.3f} "
                    f"lose_pay={stats['mean_loser_payoff']:.3f} "
                    f"pi={losses['policy_loss']:+.4f} v={losses['value_loss']:.4f} "
                    f"H={losses['entropy']:.3f} KL={losses['approx_kl']:+.4f} "
                    f"sps={sps:.1f} pool={len(self.pool)}",
                    flush=True,
                )
        if cfg.save_path:
            self._save_checkpoint()
        return self.model

    def _save_checkpoint(self) -> None:
        path = self.cfg.save_path
        if not path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        torch.save(
            {
                "model": self.model.state_dict(),
                "step": self._total_learner_steps,
                "config": self.cfg.__dict__,
            },
            path,
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def train_selfplay_v4(
    bc_checkpoint: Optional[str] = None,
    config: Optional[SelfPlayConfig] = None,
    transformer_config: Optional[TransformerConfig] = None,
) -> EventStreamTransformer:
    """Run the full V4 self-play PPO training loop.

    Args:
        bc_checkpoint: optional behaviour-cloning warm-start checkpoint.
            Strongly recommended — pure-RL from scratch on a 4-player
            game with sparse terminal rewards converges very slowly.
        config: :class:`SelfPlayConfig`.
        transformer_config: architecture config (must match the BC ckpt).
    """
    trainer = SelfPlayPPOTrainer(
        config=config,
        transformer_config=transformer_config,
        bc_checkpoint=bc_checkpoint,
    )
    return trainer.train()


__all__ = [
    "SelfPlayConfig",
    "SelfPlayPPOTrainer",
    "train_selfplay_v4",
]
