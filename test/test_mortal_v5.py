"""Tests for the Mortal-style value-learning trainer on the V5 network.

Covers the GRP / reward calculator, the dueling-Q wrapper, the hanchan
point-conservation invariant (regression for the leftover-kyoutaku fix),
and an end-to-end training smoke test.

Tiny configs so everything runs in well under a minute on CPU::

    python -m pytest test/test_mortal_v5.py -v
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pm = pytest.importorskip("MahjongPyWrapper")

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.v4.hanchan_env import HanchanEnv
from pymahjong.rl.v5.grp import (
    GRP,
    GRP_SIZE,
    RewardCalculator,
    build_grp_feature,
)
from pymahjong.rl.v5.mortal import MortalConfig, MortalTrainer
from pymahjong.rl.v5.mortal_qnet import MortalQNet


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


@dataclass
class _KR:
    """Minimal stand-in for KyokuResult."""

    bakaze: str
    kyoku_idx: int
    honba: int = 0
    kyoutaku_start: int = 0
    scores_after: list = field(default_factory=lambda: [25000] * 4)


def _tiny_cfg() -> TransformerConfig:
    return TransformerConfig(d_model=48, n_layers=2, n_heads=4, ff_mult=2, dropout=0.0)


def _make_obs(legal_idx, batch_seqlen=4, event_dim=100):
    amask = np.zeros(54, dtype=np.bool_)
    amask[legal_idx] = True
    return {
        "features": np.random.rand(batch_seqlen, event_dim).astype(np.float32) > 0.5,
        "attention_mask": np.ones(batch_seqlen, dtype=np.bool_),
        "action_mask": amask,
    }


# ---------------------------------------------------------------------------
# GRP + RewardCalculator
# ---------------------------------------------------------------------------


def test_build_grp_feature_shape_and_first_row():
    hist = [
        _KR("east", 0, scores_after=[30000, 23000, 24000, 23000]),
        _KR("south", 3, honba=1, kyoutaku_start=1, scores_after=[40000, 25000, 20000, 15000]),
    ]
    feat = build_grp_feature(hist)
    assert feat.shape == (2, GRP_SIZE)
    # First row = pre-kyoku state at East-1: grand_kyoku 0, honba 0, kyotaku 0,
    # all scores 2.5 (25000 / 1e4).
    assert feat[0].tolist() == [0.0, 0.0, 0.0, 2.5, 2.5, 2.5, 2.5]
    # Second row's grand_kyoku = south(1)*4 + 3 = 7; scores = prev scores_after / 1e4.
    assert feat[1][0] == 7.0
    assert feat[1][3:].tolist() == [3.0, 2.3, 2.4, 2.3]


def test_placement_reward_telescopes_to_final_rank_pts():
    # Seat 0 leads the whole game and finishes 1st; seat with worst final
    # score finishes 4th.  Placement reward must telescope to pts[rank].
    hist = [
        _KR("east", 0, scores_after=[33000, 21000, 23000, 23000]),
        _KR("east", 1, scores_after=[35000, 20000, 25000, 20000]),
        _KR("south", 0, scores_after=[42000, 18000, 24000, 16000]),
    ]
    final = [42000, 18000, 24000, 16000]
    ranks = [0, 2, 1, 3]
    rc = RewardCalculator(reward_kind="placement", pts=(3, 1, -1, -3))
    rew = rc.kyoku_rewards(hist, ranks, final)
    assert rew.shape == (3, 4)
    # Initial all-equal state -> expected pts 0 for everyone (tie-averaged).
    # So the per-seat column sum == pts[final_rank].
    col_sums = rew.sum(0)
    np.testing.assert_allclose(col_sums, [3, -1, 1, -3], atol=1e-4)


def test_placement_reward_all_equal_start_is_zero_ev():
    # An immediate ryuukyoku with no score change -> zero reward everywhere.
    hist = [_KR("east", 0, scores_after=[25000] * 4)]
    rc = RewardCalculator(reward_kind="placement")
    rew = rc.kyoku_rewards(hist, [0, 1, 2, 3], [25000] * 4)
    np.testing.assert_allclose(rew, np.zeros((1, 4)), atol=1e-6)


def test_points_reward_equals_score_delta():
    hist = [
        _KR("east", 0, scores_after=[33000, 21000, 23000, 23000]),
        _KR("east", 1, scores_after=[30000, 28000, 20000, 22000]),
    ]
    final = [30000, 28000, 20000, 22000]
    rc = RewardCalculator(reward_kind="points", points_scale=25000.0)
    rew = rc.kyoku_rewards(hist, [0, 1, 3, 2], final)
    # Per-seat column sum == (final - init) / 25000.
    np.testing.assert_allclose(
        rew.sum(0), (np.asarray(final) - 25000) / 25000.0, atol=1e-5
    )


def test_grp_network_forward_and_reward_finite():
    grp = GRP(hidden_size=16, num_layers=1)
    hist = [
        _KR("east", 0, scores_after=[30000, 23000, 24000, 23000]),
        _KR("south", 3, scores_after=[40000, 25000, 20000, 15000]),
    ]
    rc = RewardCalculator(reward_kind="grp", grp=grp)
    rew = rc.kyoku_rewards(hist, [0, 1, 2, 3], [40000, 25000, 20000, 15000])
    assert rew.shape == (2, 4)
    assert np.isfinite(rew).all()


def test_grp_calc_matrix_is_a_probability_distribution():
    grp = GRP(hidden_size=16, num_layers=1)
    seqs = [torch.rand(3, GRP_SIZE, dtype=torch.float64)]
    with torch.inference_mode():
        logits = grp(seqs)
        matrix = grp.calc_matrix(logits)
    assert matrix.shape == (1, 4, 4)
    # Each seat's rank distribution sums to 1; each rank's seat distribution too.
    np.testing.assert_allclose(matrix.sum(-1).numpy(), 1.0, atol=1e-9)
    np.testing.assert_allclose(matrix.sum(1).numpy(), 1.0, atol=1e-9)


# ---------------------------------------------------------------------------
# MortalQNet: EventStreamTransformer encoder + Douzero Q-head (direct Q)
# ---------------------------------------------------------------------------


def test_qhead_outputs_q_directly_no_dueling():
    # The Douzero scorer output IS the Q-value: argmax over the K legal
    # scorer outputs must match the action act_q selects, and Q on illegal
    # slots must never appear (only legal actions are scored).
    m = MortalQNet(_tiny_cfg(), scorer_hidden=32).eval()
    obs = [_make_obs([2, 5, 9, 44])]
    feats, attn, amask = _collate(obs)
    h, q_K, pad, legal_orig, _ = m._q_legal(feats, attn, amask)
    # Direct scoring: recompute scorer on (h, descriptors) and compare.
    q_ref = m.qhead.score(
        h,
        *_legal_feats(amask, m.qhead.default_action_descriptors),
    )
    assert torch.allclose(q_K, q_ref, atol=1e-5)
    # act_q greedy picks the argmax legal Q mapped back to 54-space.
    a = int(m.act_q(feats, attn, amask, deterministic=True)[0])
    best_k = int(q_K.argmax(dim=-1)[0])
    assert a == int(legal_orig[0, best_k])


def _legal_feats(amask, descriptors):
    from pymahjong.rl.v5.legal_actions import extract_legal_actions

    af, pad, _idx, _ = extract_legal_actions(amask, action_descriptors=descriptors)
    return af, pad


def test_mortalqnet_act_q_picks_only_legal_actions():
    m = MortalQNet(_tiny_cfg(), scorer_hidden=32).eval()
    obs = [_make_obs([1, 2, 3]), _make_obs([5]), _make_obs([7, 8, 44])]
    feats, attn, amask = _collate(obs)
    a = m.act_q(feats, attn, amask, deterministic=True)
    assert a.shape == (3,)
    assert bool(amask[torch.arange(3), a].all()), "act_q selected an illegal action"


def test_mortalqnet_evaluate_q_shapes_and_cql_inequality():
    m = MortalQNet(_tiny_cfg(), scorer_hidden=32).eval()
    obs = [_make_obs([1, 2, 3]), _make_obs([7, 8, 9, 44])]
    feats, attn, amask = _collate(obs)
    a = m.act_q(feats, attn, amask, deterministic=True)
    out = m.evaluate_q(feats, attn, amask, a)
    assert out["q_taken"].shape == (2,)
    assert out["q_logsumexp"].shape == (2,)
    assert out["aux_logits"].shape == (2, 4)
    assert torch.isfinite(out["q_taken"]).all()
    # logsumexp over legal Q >= the taken action's Q (CQL term >= 0).
    assert bool((out["q_logsumexp"] >= out["q_taken"] - 1e-4).all())


def test_mortalqnet_epsilon_exploration_stays_legal():
    m = MortalQNet(_tiny_cfg(), scorer_hidden=32).eval()
    obs = [_make_obs([1, 2, 3, 10, 20])] * 16
    feats, attn, amask = _collate(obs)
    g = torch.Generator().manual_seed(0)
    a = m.act_q(feats, attn, amask, epsilon=1.0, deterministic=True, generator=g)
    assert bool(amask[torch.arange(16), a].all())


def _collate(obs_list):
    seq_lens = [int(o["attention_mask"].sum()) for o in obs_list]
    max_len = max(seq_lens)
    b = len(obs_list)
    ed = obs_list[0]["features"].shape[-1]
    feats = torch.zeros(b, max_len, ed)
    attn = torch.zeros(b, max_len, dtype=torch.bool)
    amask = torch.zeros(b, 54, dtype=torch.bool)
    for i, (o, slen) in enumerate(zip(obs_list, seq_lens)):
        feats[i, :slen] = torch.from_numpy(o["features"][:slen].astype(np.float32))
        attn[i, :slen] = True
        amask[i] = torch.from_numpy(o["action_mask"])
    return feats, attn, amask


# ---------------------------------------------------------------------------
# Hanchan point conservation (regression for leftover-kyoutaku fix)
# ---------------------------------------------------------------------------


def test_hanchan_conserves_points():
    import random

    env = HanchanEnv()
    for g in range(8):
        env.reset(seed=2000 + g)
        guard = 0
        while not env.is_hanchan_over():
            while not env.is_kyoku_over():
                o = env.observe()
                legal = np.flatnonzero(np.asarray(o["action_mask"], dtype=bool))
                a = int(random.Random(g * 131 + guard).choice(legal))
                env.kyoku_step(a)
                guard += 1
            if env.is_hanchan_over():
                break
            env.advance_to_next_kyoku()
        res = env.get_hanchan_result()
        # Riichi sticks are only ever redistributed, so the four final
        # scores must always sum to exactly 4 * 25000 = 100000.
        assert sum(res.final_scores) == 100000, (
            f"points not conserved: {res.final_scores} sum={sum(res.final_scores)} "
            f"reason={res.termination_reason}"
        )


# ---------------------------------------------------------------------------
# End-to-end trainer smoke
# ---------------------------------------------------------------------------


def test_mortal_trainer_runs_and_updates_params():
    tcfg = _tiny_cfg()
    cfg = MortalConfig(
        total_steps=60,
        rollout_steps=40,
        n_envs=2,
        n_epochs=1,
        batch_size=16,
        reward_kind="placement",
        cql_enable=True,
        next_rank_weight=0.5,
        snapshot_interval=40,
        save_path="",  # skip disk I/O in the smoke test
        save_interval=10**9,
        seed=0,
        device="cpu",
    )
    trainer = MortalTrainer(config=cfg, transformer_config=tcfg)
    before = [p.detach().clone() for p in trainer.model.parameters()]
    trainer.train()
    after = list(trainer.model.parameters())
    assert trainer._total >= 40
    changed = any(not torch.equal(b, a) for b, a in zip(before, after))
    assert changed, "training did not update any parameters"


def test_mortal_trainer_lock3train1_mode():
    # opponent_mix_ratio=1.0 + n_frozen_seats=3 is the classical
    # single-learner configuration; with a fresh (empty) pool no snapshots
    # exist yet, so collection must still succeed.
    tcfg = _tiny_cfg()
    cfg = MortalConfig(
        total_steps=40, rollout_steps=30, n_envs=1, n_epochs=1, batch_size=16,
        opponent_mix_ratio=1.0, n_frozen_seats=3, snapshot_interval=30,
        save_path="", save_interval=10**9, seed=1, device="cpu",
    )
    trainer = MortalTrainer(config=cfg, transformer_config=tcfg)
    trainer.train()
    assert trainer._total >= 30


# ---------------------------------------------------------------------------
# Checkpointing (periodic) + V5-compatible export
# ---------------------------------------------------------------------------


def test_save_keeps_periodic_checkpoint(tmp_path):
    tcfg = _tiny_cfg()
    save_path = str(tmp_path / "m.pt")
    cfg = MortalConfig(save_path=save_path, keep_periodic=True, device="cpu",
                       scorer_hidden=32)
    tr = MortalTrainer(config=cfg, transformer_config=tcfg)
    tr._total = 123_456
    tr._save()
    assert (tmp_path / "m.pt").exists(), "rolling latest checkpoint missing"
    assert (tmp_path / "m.step_000123456.pt").exists(), "periodic copy missing"
    # A second save at a new step keeps both historical copies.
    tr._total = 200_000
    tr._save()
    assert (tmp_path / "m.step_000123456.pt").exists()
    assert (tmp_path / "m.step_000200000.pt").exists()


def test_no_keep_periodic_only_writes_latest(tmp_path):
    tcfg = _tiny_cfg()
    save_path = str(tmp_path / "m.pt")
    cfg = MortalConfig(save_path=save_path, keep_periodic=False, device="cpu",
                       scorer_hidden=32)
    tr = MortalTrainer(config=cfg, transformer_config=tcfg)
    tr._total = 999
    tr._save()
    assert (tmp_path / "m.pt").exists()
    assert not (tmp_path / "m.step_000000999.pt").exists()


def test_export_v5_ckpt_loads_into_douzero_v5_strict(tmp_path):
    from pymahjong.rl.v5.model import DouzeroV5Transformer

    tcfg = _tiny_cfg()
    cfg = MortalConfig(save_path=str(tmp_path / "m.pt"), device="cpu", scorer_hidden=32)
    tr = MortalTrainer(config=cfg, transformer_config=tcfg)
    exp = str(tmp_path / "v5export.pt")
    tr._export_v5_ckpt(exp)
    ck = torch.load(exp)
    v5 = DouzeroV5Transformer(config=tcfg, scorer_hidden=32)
    # Exact key match: the bench loads this as a DouzeroV5Transformer.
    missing, unexpected = v5.load_state_dict(ck["model"], strict=True)
    assert missing == [] and unexpected == []
    # The exported encoder + scorer weights match the trainer's model.
    assert torch.equal(v5.input_proj.weight, tr.model.encoder.input_proj.weight)
    assert torch.equal(v5.scorer[0].weight, tr.model.qhead.scorer[0].weight)


def test_load_bc_flat_v5_loads_encoder_and_qhead(tmp_path):
    # Regression: a flat V5 BC state_dict contains ``encoder.layers.*`` keys
    # (the nn.TransformerEncoder submodule), which must NOT be misclassified
    # as a MortalQNet self-checkpoint -- doing so loads nothing.  BC
    # warm-start must restore both the encoder and the Douzero Q-head.
    from pymahjong.rl.v5.model import DouzeroV5Transformer

    tcfg = _tiny_cfg()
    v5 = DouzeroV5Transformer(config=tcfg, scorer_hidden=32)
    bc = tmp_path / "bc.pt"
    torch.save({"model": v5.state_dict()}, bc)
    m = MortalQNet(tcfg, scorer_hidden=32)
    missing, loaded = m.load_bc(str(bc))
    real_missing = [k for k in missing if not k.startswith("policy_head")]
    assert real_missing == [], f"encoder not loaded: {real_missing}"
    assert len(loaded) > 0, "qhead keys not loaded from V5 BC"
    assert torch.equal(m.encoder.input_proj.weight, v5.input_proj.weight)
    assert torch.equal(m.qhead.scorer[0].weight, v5.scorer[0].weight)


def test_load_bc_resumes_from_mortalqnet_self_checkpoint(tmp_path):
    # A MortalQNet self-checkpoint (keys prefixed ``encoder.`` / ``qhead.``)
    # must be loaded whole so the Q-head + aux head are also restored.
    tcfg = _tiny_cfg()
    m1 = MortalQNet(tcfg, scorer_hidden=32)
    ck = tmp_path / "self.pt"
    torch.save({"model": m1.state_dict()}, ck)
    m2 = MortalQNet(tcfg, scorer_hidden=32)
    m2.load_bc(str(ck))
    assert all(
        torch.equal(a, b)
        for a, b in zip(m1.state_dict().values(), m2.state_dict().values())
    )


def test_mortal_eval_disabled_is_noop():
    # mortal_eval=False -> _run_mortal_eval returns immediately, no raise.
    tcfg = _tiny_cfg()
    cfg = MortalConfig(save_path="", mortal_eval=False, device="cpu", scorer_hidden=32)
    tr = MortalTrainer(config=cfg, transformer_config=tcfg)
    tr._run_mortal_eval()  # must not raise


def test_mortal_eval_missing_paths_is_safe(tmp_path):
    # mortal_eval=True but bench paths unset -> prints a disabled message and
    # returns without raising (training must continue unharmed).
    tcfg = _tiny_cfg()
    cfg = MortalConfig(save_path=str(tmp_path / "m.pt"), mortal_eval=True,
                       device="cpu", scorer_hidden=32)
    tr = MortalTrainer(config=cfg, transformer_config=tcfg)
    tr._total = 100
    tr._run_mortal_eval()  # must not raise
    assert tr._last_mortal_eval_step == -1  # never advanced (eval didn't run)

