"""Tests for the optional learned positional embedding in V4.

Verifies:

* ``use_pos_emb=False`` (default) preserves the original behavior:
  - module has no ``pos_emb`` attribute populated
  - encoder is permutation-invariant over the event axis
* ``use_pos_emb=True``:
  - ``pos_emb`` is registered and zero-initialised
  - immediately after construction (zero pos_emb) the forward output is
    bit-identical to a model with ``use_pos_emb=False`` (warm-start
    contract: loading an old BC checkpoint into a use_pos_emb model
    reproduces the old policy exactly on step 0)
  - after the pos_emb table is perturbed away from zero, the encoder
    is *no longer* permutation-invariant
* ``state_dict`` of a no-pos-emb model loads cleanly into a pos_emb
  model with ``strict=False`` (the BC warm-start path used by
  ``MortalTrainer._load_bc``).
"""
from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.transformer import EventStreamTransformer


def _tiny_cfg(use_pos_emb: bool) -> TransformerConfig:
    return TransformerConfig(
        d_model=16,
        n_heads=2,
        n_layers=1,
        ff_mult=2,
        dropout=0.0,
        use_cls=True,
        use_pos_emb=use_pos_emb,
    )


def _make_inputs(seed: int = 0, B: int = 2, L: int = 6, event_dim: int = 100):
    g = torch.Generator().manual_seed(seed)
    feats = (torch.rand(B, L, event_dim, generator=g) > 0.7).float()
    mask = torch.ones(B, L, dtype=torch.bool)
    act_mask = torch.ones(B, 54, dtype=torch.bool)
    return feats, mask, act_mask


def test_default_has_no_pos_emb():
    m = EventStreamTransformer(config=_tiny_cfg(use_pos_emb=False))
    assert m.pos_emb is None
    # No pos_emb parameters should appear in state_dict.
    assert not any(k.startswith("pos_emb.") for k in m.state_dict())


def test_pos_emb_is_zero_initialised():
    m = EventStreamTransformer(config=_tiny_cfg(use_pos_emb=True))
    assert m.pos_emb is not None
    assert torch.all(m.pos_emb.weight == 0)


def test_default_is_permutation_invariant_over_events():
    """Sanity check: vanilla V4 encoder is a set encoder."""
    torch.manual_seed(0)
    m = EventStreamTransformer(config=_tiny_cfg(use_pos_emb=False)).eval()
    feats, mask, _ = _make_inputs(seed=1)
    perm = torch.tensor([3, 0, 5, 1, 4, 2])
    feats_perm = feats[:, perm, :]
    with torch.no_grad():
        h1 = m.encode(feats, mask)
        h2 = m.encode(feats_perm, mask)
    assert torch.allclose(h1, h2, atol=1e-5), (
        "Vanilla V4 encoder should be permutation-invariant; got delta="
        f"{(h1 - h2).abs().max().item()}"
    )


def test_pos_emb_zero_init_matches_no_pos_emb_exactly():
    """Warm-start contract: zero pos_emb must reproduce no-pos-emb output."""
    torch.manual_seed(0)
    m_no = EventStreamTransformer(config=_tiny_cfg(use_pos_emb=False)).eval()
    m_yes = EventStreamTransformer(config=_tiny_cfg(use_pos_emb=True)).eval()
    # Sync all shared parameters so the only architectural delta is pos_emb.
    missing, unexpected = m_yes.load_state_dict(m_no.state_dict(), strict=False)
    assert unexpected == [], f"unexpected keys: {unexpected}"
    assert missing == ["pos_emb.weight"], f"missing keys: {missing}"
    assert torch.all(m_yes.pos_emb.weight == 0)

    feats, mask, act_mask = _make_inputs(seed=2)
    with torch.no_grad():
        h_no = m_no.encode(feats, mask)
        h_yes = m_yes.encode(feats, mask)
        l_no, v_no = m_no(feats, mask, act_mask)
        l_yes, v_yes = m_yes(feats, mask, act_mask)
    assert torch.allclose(h_no, h_yes, atol=0, rtol=0), (
        f"encode() mismatch with zero pos_emb: max|Δ|="
        f"{(h_no - h_yes).abs().max().item()}"
    )
    assert torch.allclose(l_no, l_yes, atol=0, rtol=0)
    assert torch.allclose(v_no, v_yes, atol=0, rtol=0)


def test_pos_emb_breaks_permutation_invariance_when_nonzero():
    torch.manual_seed(0)
    m = EventStreamTransformer(config=_tiny_cfg(use_pos_emb=True)).eval()
    # Perturb pos_emb away from the zero init so it actually contributes.
    with torch.no_grad():
        m.pos_emb.weight.normal_(mean=0.0, std=0.5)

    feats, mask, _ = _make_inputs(seed=3)
    perm = torch.tensor([3, 0, 5, 1, 4, 2])
    feats_perm = feats[:, perm, :]
    with torch.no_grad():
        h1 = m.encode(feats, mask)
        h2 = m.encode(feats_perm, mask)
    delta = (h1 - h2).abs().max().item()
    assert delta > 1e-3, (
        "With a non-zero pos_emb, the encoder must not be permutation-"
        f"invariant, but max|Δ|={delta:.2e}"
    )


def test_pos_emb_rejects_oversize_sequence():
    cfg = _tiny_cfg(use_pos_emb=True)
    m = EventStreamTransformer(config=cfg, pos_max_len=4).eval()
    # 4 events + 1 CLS = 5 ≤ capacity (4 + 1 = 5) → OK
    feats, mask, _ = _make_inputs(seed=4, L=4)
    with torch.no_grad():
        m.encode(feats, mask)
    # 5 events + 1 CLS = 6 > capacity → should raise
    feats, mask, _ = _make_inputs(seed=5, L=5)
    with pytest.raises(ValueError, match="exceeds pos_emb capacity"):
        m.encode(feats, mask)


def test_use_pos_emb_disabled_without_cls():
    cfg = TransformerConfig(
        d_model=16, n_heads=2, n_layers=1, ff_mult=2, dropout=0.0,
        use_cls=False, use_pos_emb=True,
    )
    m = EventStreamTransformer(config=cfg).eval()
    feats, mask, _ = _make_inputs(seed=6, L=8)
    # Should run without error even without CLS.
    with torch.no_grad():
        h = m.encode(feats, mask)
    assert h.shape == (feats.size(0), cfg.d_model)
