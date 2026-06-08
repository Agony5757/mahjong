"""Smoke tests for the Douzero-style model and per-legal-action wiring."""

from __future__ import annotations

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from pymahjong.rl.action_space import ACTION_DIM, RESPONSE_HEAD_SLOTS
from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.action_features import (
    ACTION_FEAT_DIM, build_action_features, torch_action_features,
)
from pymahjong.rl.legal_actions import PAD_INDEX, extract_legal_actions
from pymahjong.rl.cached_dataset import cached_event_collate
from pymahjong.rl.douzero import DouzeroTransformer


# ----------------------------------------------------------------------
# action_features.py
# ----------------------------------------------------------------------


def test_action_features_shape_and_invariants():
    F = build_action_features()
    assert F.shape == (ACTION_DIM, ACTION_FEAT_DIM)
    assert F.dtype == np.float32
    type_block = F[:, 0:11]
    assert np.allclose(type_block.sum(axis=1), 1.0), \
        "each action must have exactly one type bit"
    response_set = set(RESPONSE_HEAD_SLOTS)
    for a in range(ACTION_DIM):
        expected = 1.0 if a in response_set else 0.0
        assert F[a, 49] == expected
    red_slots = {34, 35, 36, 40, 41, 42, 44}
    for a in range(ACTION_DIM):
        expected = 1.0 if a in red_slots else 0.0
        assert F[a, 11] == expected, f"red bit mismatch at action {a}"
    for tile in range(34):
        row = F[tile, 15:15 + 34]
        assert row[tile] == 1.0
        assert row.sum() == 1.0


def test_torch_action_features_matches_numpy():
    np_F = build_action_features()
    t_F = torch_action_features()
    assert t_F.shape == (ACTION_DIM, ACTION_FEAT_DIM)
    assert torch.allclose(t_F, torch.from_numpy(np_F))


# ----------------------------------------------------------------------
# legal_actions.py
# ----------------------------------------------------------------------


def test_extract_legal_actions_basic():
    mask = torch.zeros(3, ACTION_DIM, dtype=torch.bool)
    # sample 0: legal = {1, 5, 50}; sample 1: legal = {0}; sample 2: legal = {53}
    mask[0, [1, 5, 50]] = True
    mask[1, [0]] = True
    mask[2, [53]] = True
    af, pad, orig, tgt = extract_legal_actions(mask)
    # K_max should equal 3 (sample 0 has 3 legals).
    assert af.shape == (3, 3, ACTION_FEAT_DIM)
    assert pad.shape == (3, 3)
    assert orig.shape == (3, 3)
    assert tgt is None

    # Sample 0: orig idx 1, 5, 50 in ascending order.
    assert orig[0].tolist() == [1, 5, 50]
    assert pad[0].tolist() == [True, True, True]
    # Sample 1: one legal, rest padded with PAD_INDEX.
    assert orig[1].tolist() == [0, PAD_INDEX, PAD_INDEX]
    assert pad[1].tolist() == [True, False, False]
    # Sample 2: one legal at slot 53.
    assert orig[2].tolist() == [53, PAD_INDEX, PAD_INDEX]
    assert pad[2].tolist() == [True, False, False]

    # action_features for sample 0 must equal the descriptor rows 1/5/50.
    desc = torch_action_features()
    assert torch.allclose(af[0, 0], desc[1])
    assert torch.allclose(af[0, 1], desc[5])
    assert torch.allclose(af[0, 2], desc[50])
    # Padded slot is zero.
    assert torch.allclose(af[1, 1], torch.zeros(ACTION_FEAT_DIM))


def test_extract_legal_actions_with_target():
    mask = torch.zeros(2, ACTION_DIM, dtype=torch.bool)
    mask[0, [3, 7, 9]] = True
    mask[1, [11, 22, 33, 44]] = True
    actions = torch.tensor([9, 22], dtype=torch.long)  # expert picks
    _, _, orig, tgt = extract_legal_actions(mask, action=actions)
    # Action 9 is at position 2 in sample 0's [3, 7, 9].
    # Action 22 is at position 1 in sample 1's [11, 22, 33, 44].
    assert tgt.tolist() == [2, 1]
    # Sanity: orig[b, tgt[b]] must equal the expert action.
    for b in range(2):
        assert int(orig[b, tgt[b]]) == int(actions[b])


def test_extract_legal_actions_raises_on_illegal_expert():
    mask = torch.zeros(1, ACTION_DIM, dtype=torch.bool)
    mask[0, [3, 7]] = True
    # Expert picks an illegal action (5 not in {3, 7}).
    with pytest.raises(RuntimeError, match="lies outside its"):
        extract_legal_actions(mask, action=torch.tensor([5]))


# ----------------------------------------------------------------------
# DouzeroTransformer
# ----------------------------------------------------------------------


def _toy_batch(B: int = 4, L: int = 32, event_dim: int = 100, device="cpu"):
    feat = torch.zeros((B, L, event_dim), dtype=torch.float32, device=device)
    feat[:, :, 0] = 1.0
    attn = torch.ones((B, L), dtype=torch.bool, device=device)
    rng = np.random.default_rng(0)
    raw = rng.random((B, ACTION_DIM)) > 0.5
    raw[:, 0] = True  # guarantee at least one legal per row
    mask = torch.from_numpy(raw).to(device)
    return feat, attn, mask


def test_v5_forward_v4compat_shapes_and_masking():
    cfg = TransformerConfig(d_model=64, n_layers=2, n_heads=4, ff_mult=2, dropout=0.0)
    m = DouzeroTransformer(config=cfg, event_dim=100, scorer_hidden=32)
    feat, attn, mask = _toy_batch()
    # V4-compat call path: pass action_mask, let the model derive legals.
    logits, value = m(feat, attn, action_mask=mask)
    assert logits.shape == (4, ACTION_DIM)
    assert value.shape == (4,)
    NEG = -1e8
    # Every illegal slot must be NEG_INF-ish.
    illegal_logits = logits.masked_select(~mask)
    assert (illegal_logits < NEG).all(), \
        "V5 must never assign a finite score to an illegal slot"


def test_v5_forward_douzero_path_matches_v4compat_path():
    """Explicit (action_features, ...) input must produce identical logits
    to the V4-compat shortcut that derives them internally."""
    cfg = TransformerConfig(d_model=64, n_layers=2, n_heads=4, ff_mult=2, dropout=0.0)
    m = DouzeroTransformer(config=cfg, event_dim=100, scorer_hidden=32)
    m.eval()
    feat, attn, mask = _toy_batch()
    out_compat, val_compat = m(feat, attn, action_mask=mask)

    af, pad, orig, _ = extract_legal_actions(mask)
    out_explicit, val_explicit = m(
        feat, attn,
        action_features=af, action_pad_mask=pad, legal_orig_idx=orig,
    )
    assert torch.allclose(out_compat, out_explicit, atol=1e-6)
    assert torch.allclose(val_compat, val_explicit, atol=1e-6)


def test_v5_backward_pass_only_legal_grads():
    """Gradients flow through scorer, action_proj and encoder."""
    cfg = TransformerConfig(d_model=64, n_layers=2, n_heads=4, ff_mult=2, dropout=0.0)
    m = DouzeroTransformer(config=cfg, event_dim=100, scorer_hidden=32)
    feat, attn, mask = _toy_batch()
    logits, _ = m(feat, attn, action_mask=mask)
    masked_logits = logits.masked_fill(~mask, -1e9)
    target = mask.float().argmax(dim=-1)
    loss = torch.nn.functional.cross_entropy(masked_logits, target)
    loss.backward()
    sentinel_params = ("action_proj.weight", "scorer.0.weight", "input_proj.weight")
    for name, p in m.named_parameters():
        if name in sentinel_params:
            assert p.grad is not None and p.grad.abs().sum() > 0, \
                f"no gradient for {name}"


def test_v5_act_picks_only_legal_actions():
    cfg = TransformerConfig(d_model=64, n_layers=2, n_heads=4, ff_mult=2, dropout=0.0)
    m = DouzeroTransformer(config=cfg, event_dim=100, scorer_hidden=32)
    m.eval()
    feat, attn, mask = _toy_batch(B=16)
    action, log_prob, value = m.act(feat, attn, mask, deterministic=True)
    assert action.shape == (16,)
    for i in range(16):
        assert mask[i, int(action[i])].item(), \
            f"sample {i}: V5 picked illegal action {int(action[i])}"
    # Stochastic path must also stay in-legals.
    torch.manual_seed(0)
    action_stoch, _, _ = m.act(feat, attn, mask, deterministic=False)
    for i in range(16):
        assert mask[i, int(action_stoch[i])].item()


def test_v5_evaluate_actions_consistency():
    """log_prob from evaluate_actions must agree with the K-wide softmax."""
    cfg = TransformerConfig(d_model=64, n_layers=2, n_heads=4, ff_mult=2, dropout=0.0)
    m = DouzeroTransformer(config=cfg, event_dim=100, scorer_hidden=32)
    m.eval()
    feat, attn, mask = _toy_batch()
    # Pick an arbitrary legal action per row.
    target_54 = mask.float().argmax(dim=-1)

    lp, ent, val = m.evaluate_actions(feat, attn, mask, target_54)
    assert lp.shape == (4,)
    assert ent.shape == (4,)
    # log_prob must equal log-softmax over the masked (B,54) layout.
    logits, _ = m(feat, attn, action_mask=mask)
    expected = torch.nn.functional.log_softmax(logits, dim=-1).gather(
        -1, target_54.unsqueeze(-1)
    ).squeeze(-1)
    assert torch.allclose(lp, expected, atol=1e-5)
    # Entropy must be finite (no NaNs from NEG_INF * 0).
    assert torch.isfinite(ent).all()


def _douzero_collate(samples):
    """Inline equivalent of the old V5Strategy.collate_fn."""
    out = cached_event_collate(samples)
    af, apm, loi, lti = extract_legal_actions(
        out["action_mask"], action=out["action"]
    )
    out["action_features"] = af
    out["action_pad_mask"] = apm
    out["legal_orig_idx"] = loi
    out["legal_target_idx"] = lti
    return out


def test_v5_strategy_collate_provides_douzero_tensors():
    """Douzero collate must append per-legal-action tensors."""
    # Build two toy samples in the cached-dataset format.
    sample0 = {
        "features": torch.zeros((10, 100), dtype=torch.bool),
        "attention_mask": torch.ones(10, dtype=torch.bool),
        "action_mask": torch.zeros(ACTION_DIM, dtype=torch.bool),
        "action": torch.tensor(5, dtype=torch.long),
        "seq_len": torch.tensor(10, dtype=torch.long),
    }
    sample0["action_mask"][[3, 5, 11]] = True
    sample1 = {
        "features": torch.zeros((7, 100), dtype=torch.bool),
        "attention_mask": torch.ones(7, dtype=torch.bool),
        "action_mask": torch.zeros(ACTION_DIM, dtype=torch.bool),
        "action": torch.tensor(0, dtype=torch.long),
        "seq_len": torch.tensor(7, dtype=torch.long),
    }
    sample1["action_mask"][[0, 22]] = True

    out = _douzero_collate([sample0, sample1])
    for key in ("features", "attention_mask", "action_mask", "action",
                "action_features", "action_pad_mask", "legal_orig_idx",
                "legal_target_idx"):
        assert key in out, f"missing key in Douzero collate output: {key}"
    # K must equal max legal count across the batch = 3.
    assert out["action_features"].shape == (2, 3, ACTION_FEAT_DIM)
    assert out["action_pad_mask"].shape == (2, 3)
    assert out["legal_orig_idx"].shape == (2, 3)
    # Sample 0's expert action 5 must be at legal-list index 1 ([3,5,11]).
    # Sample 1's expert action 0 must be at legal-list index 0 ([0,22]).
    assert out["legal_target_idx"].tolist() == [1, 0]


def test_v5_strategy_forward_from_batch_uses_douzero():
    cfg = TransformerConfig(d_model=64, n_layers=2, n_heads=4, ff_mult=2, dropout=0.0)
    model = DouzeroTransformer(
        config=cfg, event_dim=100,
        action_feat_dim=ACTION_FEAT_DIM, scorer_hidden=32,
    )
    sample0 = {
        "features": torch.zeros((10, 100), dtype=torch.bool),
        "attention_mask": torch.ones(10, dtype=torch.bool),
        "action_mask": torch.zeros(ACTION_DIM, dtype=torch.bool),
        "action": torch.tensor(5, dtype=torch.long),
        "seq_len": torch.tensor(10, dtype=torch.long),
    }
    sample0["action_mask"][[3, 5, 11]] = True
    batch = _douzero_collate([sample0])
    raw_logits, value = model(
        batch["features"], batch["attention_mask"],
        action_features=batch["action_features"],
        action_pad_mask=batch["action_pad_mask"],
        legal_orig_idx=batch["legal_orig_idx"],
    )
    action_mask = batch["action_mask"]
    assert raw_logits.shape == (1, ACTION_DIM)
    assert value.shape == (1,)
    NEG = -1e8
    illegal = raw_logits.masked_select(~action_mask.bool())
    assert (illegal < NEG).all()


def test_v5_state_dict_roundtrip():
    cfg = TransformerConfig(d_model=64, n_layers=2, n_heads=4, ff_mult=2, dropout=0.0)
    m1 = DouzeroTransformer(config=cfg, event_dim=100, scorer_hidden=32)
    m2 = DouzeroTransformer(config=cfg, event_dim=100, scorer_hidden=32)
    m2.load_state_dict(m1.state_dict())
    feat, attn, mask = _toy_batch()
    m1.eval(); m2.eval()
    out1 = m1(feat, attn, action_mask=mask)
    out2 = m2(feat, attn, action_mask=mask)
    assert torch.allclose(out1[0], out2[0], atol=1e-5)
    assert torch.allclose(out1[1], out2[1], atol=1e-5)
