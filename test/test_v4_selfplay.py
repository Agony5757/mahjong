"""End-to-end smoke tests for V4 self-play PPO.

Tiny config so the tests run in well under a minute on CPU.  These
tests exercise:

* :class:`V4MultiAgentEnv` produces real (non-zero) V4 observations.
* :class:`OpponentPool` sampling strategies.
* :class:`SelfPlayPPOTrainer` runs at least one full PPO update without
  crashing and updates the model parameters.
* The "lock-3-train-1" config (``opponent_mix_ratio=1.0, n_frozen_seats=3``)
  is supported.
"""
from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

pm = pytest.importorskip("MahjongPyWrapper")

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.v4.env import V4MultiAgentEnv
from pymahjong.rl.v4.model import EventStreamTransformer
from pymahjong.rl.v4.opponent_pool import OpponentPool
from pymahjong.rl.v4.selfplay import SelfPlayConfig, SelfPlayPPOTrainer


# ---------------------------------------------------------------------------
# V4MultiAgentEnv
# ---------------------------------------------------------------------------


def test_v4_env_produces_nonzero_observations():
    env = V4MultiAgentEnv(max_seq_len=128)
    obs = env.reset(seed=42)
    assert "features" in obs and "attention_mask" in obs and "action_mask" in obs
    feat = np.asarray(obs["features"])
    attn = np.asarray(obs["attention_mask"])
    amask = np.asarray(obs["action_mask"])
    # Real V4 features — the placeholder strategy returned zeros.
    assert feat.shape[1] == 100
    assert attn.sum() > 0, "attention_mask should have at least some valid tokens"
    assert feat[attn].any(), "features should have at least some non-zero bits"
    assert amask.any(), "action_mask should have at least one valid action"


def test_v4_env_step_advances_until_done():
    env = V4MultiAgentEnv(max_seq_len=128)
    obs = env.reset(seed=7)
    steps = 0
    while not env.is_over() and steps < 400:
        mask = np.asarray(obs["action_mask"])
        valid = np.flatnonzero(mask)
        assert len(valid) > 0, "should have at least one valid action"
        action = int(valid[0])  # pick first valid action deterministically
        obs_or_none, payoffs, done, info = env.step(action)
        steps += 1
        if done:
            assert payoffs.shape == (4,)
            assert obs_or_none is None
            break
        obs = obs_or_none
    assert steps > 0


# ---------------------------------------------------------------------------
# OpponentPool
# ---------------------------------------------------------------------------


def test_opponent_pool_sampling():
    pool = OpponentPool(capacity=3, sampling="uniform", seed=1)
    tcfg = TransformerConfig(d_model=32, n_layers=1, n_heads=2)
    model = EventStreamTransformer(config=tcfg)
    for step in (100, 200, 300):
        pool.add_snapshot(model, step=step)
    assert len(pool) == 3
    snap = pool.sample()
    assert snap is not None
    assert snap.step in (100, 200, 300)

    # Capacity eviction.
    pool.add_snapshot(model, step=400)
    assert len(pool) == 3
    assert pool.snapshots[0].step == 200

    # PFSP weighting (no crash, returns valid snapshot).
    pool.sampling = "pfsp"
    pool.snapshots[0].win_rate = 0.9
    pool.snapshots[-1].win_rate = 0.1
    counts = {s.step: 0 for s in pool.snapshots}
    for _ in range(60):
        s = pool.sample()
        counts[s.step] += 1
    # The lowest-winrate (hardest) snapshot should be sampled most.
    hardest_step = pool.snapshots[-1].step
    assert counts[hardest_step] >= counts[pool.snapshots[0].step]


# ---------------------------------------------------------------------------
# SelfPlayPPOTrainer
# ---------------------------------------------------------------------------


def _tiny_cfg(**overrides) -> SelfPlayConfig:
    base = dict(
        total_steps=64,
        rollout_steps=32,
        n_envs=2,
        n_epochs=1,
        batch_size=16,
        max_seq_len=64,
        snapshot_interval=10**9,  # disable mid-test
        save_path="",  # disable disk write
        log_interval=1,
        device="cpu",
        seed=123,
    )
    base.update(overrides)
    return SelfPlayConfig(**base)


def _tiny_tcfg() -> TransformerConfig:
    return TransformerConfig(d_model=32, n_layers=1, n_heads=2, ff_mult=2, dropout=0.0)


def _params_snapshot(model):
    return [p.detach().clone() for p in model.parameters()]


def _params_changed(before, after) -> bool:
    return any(not torch.equal(b, a) for b, a in zip(before, after))


def test_trainer_runs_one_update_shared_selfplay():
    cfg = _tiny_cfg()
    trainer = SelfPlayPPOTrainer(config=cfg, transformer_config=_tiny_tcfg())
    before = _params_snapshot(trainer.model)
    trainer.train()
    after = _params_snapshot(trainer.model)
    assert _params_changed(before, after), "model parameters should have been updated"
    assert trainer._total_learner_steps >= cfg.rollout_steps


def test_trainer_lock_three_train_one_mode():
    """Validate the classical "lock 3 freeze, train 1" configuration runs."""
    cfg = _tiny_cfg(
        opponent_mix_ratio=1.0,
        n_frozen_seats=3,
        snapshot_interval=16,  # ensure a snapshot exists very early
        total_steps=80,
        rollout_steps=40,
    )
    trainer = SelfPlayPPOTrainer(config=cfg, transformer_config=_tiny_tcfg())
    # Seed the pool with the initial weights so the first rollout has
    # something to sample from.
    trainer.pool.add_snapshot(trainer.model, step=0)
    before = _params_snapshot(trainer.model)
    trainer.train()
    after = _params_snapshot(trainer.model)
    assert _params_changed(before, after)
