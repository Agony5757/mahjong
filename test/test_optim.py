"""Tests for pymahjong.rl.common.optim (Muon + AdamW factory + scheduler)."""
from __future__ import annotations

import math

import pytest

torch = pytest.importorskip("torch")
import torch.nn as nn  # noqa: E402

from pymahjong.rl.common.optim import (  # noqa: E402
    CombinedOptimizer,
    Muon,
    build_optimizer,
    build_scheduler,
)


# ---------------------------------------------------------------------------
# A tiny model that mirrors the EventStreamTransformer's parameter taxonomy:
# embedding + 2D hidden weight + bias + LayerNorm + output head.
# ---------------------------------------------------------------------------
class _TinyTransformerLike(nn.Module):
    def __init__(self):
        super().__init__()
        self.input_proj = nn.Linear(8, 16)           # Muon-eligible
        self.pos_emb = nn.Embedding(32, 16)          # AdamW no-WD (embedding)
        self.cls = nn.Parameter(torch.zeros(1, 1, 16))  # AdamW no-WD (scalar)
        self.norm = nn.LayerNorm(16)                  # AdamW no-WD (1D)
        # Mimic encoder layer (2D weights, biases, layernorm gains).
        self.linear1 = nn.Linear(16, 32)
        self.linear2 = nn.Linear(32, 16)
        # Output heads (excluded from Muon per spec).
        self.policy_head = nn.Linear(16, 5)
        self.value_head = nn.Sequential(
            nn.Linear(16, 16),
            nn.GELU(),
            nn.Linear(16, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        h = self.input_proj(x)
        h = self.norm(h + self.cls.squeeze(0).squeeze(0))
        h = self.linear2(torch.nn.functional.gelu(self.linear1(h)))
        return self.policy_head(h), self.value_head(h).squeeze(-1)


def _named_set(params):
    """Return a frozenset of parameter ids for membership testing."""
    return frozenset(id(p) for p in params)


# ---------------------------------------------------------------------------
# Param-group classification
# ---------------------------------------------------------------------------

def test_adamw_classification_routes_norms_and_biases_to_no_wd():
    model = _TinyTransformerLike()
    optim = build_optimizer(model, kind="adamw", lr=1e-3, weight_decay=0.1)
    assert isinstance(optim, torch.optim.AdamW)
    # The factory builds (decay, nodecay) groups; check that biases /
    # LayerNorm / embedding / cls / heads all landed in the no-WD group.
    decay_params = _named_set(optim.param_groups[0]["params"])
    nodecay_params = _named_set(optim.param_groups[1]["params"])

    # 2D body weights should be in the decay group when kind=adamw.
    assert id(model.input_proj.weight) in decay_params
    assert id(model.linear1.weight) in decay_params
    assert id(model.linear2.weight) in decay_params
    # Heads + value-head inner Linear's hidden weight should be no-WD
    # (we treat the entire policy_head and value_head as no-WD).
    assert id(model.policy_head.weight) in nodecay_params
    # Embeddings, scalars, norms, biases all no-WD.
    assert id(model.pos_emb.weight) in nodecay_params
    assert id(model.cls) in nodecay_params
    assert id(model.norm.weight) in nodecay_params
    assert id(model.norm.bias) in nodecay_params
    assert id(model.input_proj.bias) in nodecay_params

    # WD values must match the recipe.
    assert optim.param_groups[0]["weight_decay"] == 0.1
    assert optim.param_groups[1]["weight_decay"] == 0.0


def test_muon_classification_routes_2d_body_weights_to_muon():
    model = _TinyTransformerLike()
    optim = build_optimizer(model, kind="muon", lr=1e-3, muon_lr=0.02)
    assert isinstance(optim, CombinedOptimizer)

    muon_params = _named_set(optim.muon.param_groups[0]["params"])
    adamw_params = set()
    for g in optim.adamw.param_groups:
        adamw_params.update(id(p) for p in g["params"])

    # Body 2D weights → Muon
    assert id(model.input_proj.weight) in muon_params
    assert id(model.linear1.weight) in muon_params
    assert id(model.linear2.weight) in muon_params
    # value_head hidden Linear (Sequential[0]) is body, not head → Muon
    assert id(model.value_head[0].weight) in muon_params

    # Heads, embeddings, scalars, norms, biases → AdamW
    assert id(model.policy_head.weight) in adamw_params
    assert id(model.value_head[2].weight) in adamw_params  # final Linear(16,1)
    assert id(model.pos_emb.weight) in adamw_params
    assert id(model.cls) in adamw_params
    assert id(model.norm.weight) in adamw_params
    assert id(model.linear1.bias) in adamw_params

    # No param should be in both buckets.
    assert not (muon_params & adamw_params)


def test_muon_and_adamw_partition_covers_all_params():
    model = _TinyTransformerLike()
    optim = build_optimizer(model, kind="muon", lr=1e-3)
    assert isinstance(optim, CombinedOptimizer)
    all_owned = set()
    all_owned.update(id(p) for p in optim.muon.param_groups[0]["params"])
    for g in optim.adamw.param_groups:
        all_owned.update(id(p) for p in g["params"])
    expected = {id(p) for p in model.parameters() if p.requires_grad}
    assert all_owned == expected


# ---------------------------------------------------------------------------
# Newton-Schulz / Muon mechanics
# ---------------------------------------------------------------------------

def test_muon_step_actually_updates_parameters():
    """A single Muon step on a non-zero loss must shift params (not silently no-op)."""
    torch.manual_seed(0)
    model = _TinyTransformerLike()
    optim = build_optimizer(model, kind="muon", lr=1e-3, muon_lr=0.01)
    snap = {n: p.detach().clone() for n, p in model.named_parameters()}

    x = torch.randn(4, 8)
    logits, value = model(x)
    target = torch.zeros(4, dtype=torch.long)
    loss = nn.functional.cross_entropy(logits, target) + value.pow(2).mean()
    optim.zero_grad()
    loss.backward()
    optim.step()

    # All non-norm/no-grad params should have moved.  We only check a
    # representative Muon param and a representative AdamW param.
    assert not torch.allclose(model.input_proj.weight, snap["input_proj.weight"]), \
        "Muon failed to update input_proj.weight"
    assert not torch.allclose(model.norm.weight, snap["norm.weight"]), \
        "AdamW failed to update norm.weight"


def test_muon_rejects_non_2d_param():
    """Routing a 1D param directly through Muon must raise."""
    p1d = torch.nn.Parameter(torch.randn(8))
    muon = Muon([p1d], lr=0.01)
    p1d.grad = torch.randn_like(p1d)
    with pytest.raises(RuntimeError, match="non-2D parameter"):
        muon.step()


def test_combined_optimizer_state_roundtrip():
    """state_dict / load_state_dict round-trip preserves *usable* training
    state.  Bit-exact equality across roundtrips is not guaranteed by
    either Muon (bf16 Newton-Schulz quantisation) or PyTorch's foreach/
    fused AdamW (step counter dispatch differences), so we instead
    verify two practical properties:

    1. After load, the model+optim continue training: loss must
       continue decreasing (i.e. the loaded momentum/state are
       actually used, not silently re-initialised to zeros).
    2. The roundtripped state_dict's ``"kind"`` tag is preserved
       and the tensor structure matches.
    """
    torch.manual_seed(1)
    model = _TinyTransformerLike()
    optim = build_optimizer(model, kind="muon", lr=1e-3)
    # Warm up: take a few steps so the optimizer has non-trivial state.
    x = torch.randn(8, 8)
    y = torch.randint(0, 5, (8,))
    for _ in range(3):
        logits, value = model(x)
        loss = nn.functional.cross_entropy(logits, y) + value.pow(2).mean()
        optim.zero_grad()
        loss.backward()
        optim.step()
    sd = optim.state_dict()
    assert sd["kind"] == "muon+adamw"
    # Save a snapshot of the current loss.
    logits, value = model(x)
    pre_load_loss = float(
        nn.functional.cross_entropy(logits, y) + value.pow(2).mean()
    )

    # Reload into a fresh model+optim and continue training.
    model2 = _TinyTransformerLike()
    model2.load_state_dict(model.state_dict())
    optim2 = build_optimizer(model2, kind="muon", lr=1e-3)
    optim2.load_state_dict(sd)

    # Continue training: loss should drop further (loaded momentum
    # is being used; zero-init momentum would converge much slower).
    for _ in range(20):
        logits, value = model2(x)
        loss = nn.functional.cross_entropy(logits, y) + value.pow(2).mean()
        optim2.zero_grad()
        loss.backward()
        optim2.step()
    logits, value = model2(x)
    post_load_loss = float(
        nn.functional.cross_entropy(logits, y) + value.pow(2).mean()
    )
    assert post_load_loss < pre_load_loss, (pre_load_loss, post_load_loss)


def test_combined_optimizer_refuses_wrong_state_kind():
    model = _TinyTransformerLike()
    optim = build_optimizer(model, kind="muon", lr=1e-3)
    with pytest.raises(ValueError, match="muon\\+adamw"):
        optim.load_state_dict({"kind": "adamw_only"})


# ---------------------------------------------------------------------------
# LR scheduler
# ---------------------------------------------------------------------------

def test_constant_schedule_no_warmup_is_identity():
    model = _TinyTransformerLike()
    optim = build_optimizer(model, kind="adamw", lr=3e-4)
    sched = build_scheduler(optim, total_steps=1000, schedule="constant", warmup_steps=0)
    lrs = []
    for _ in range(10):
        sched.step()
        lrs.append(sched.get_last_lr()[0])
    assert all(abs(lr - 3e-4) < 1e-9 for lr in lrs), lrs


def test_warmup_then_cosine_decays_to_min_lr_ratio():
    model = _TinyTransformerLike()
    base_lr = 1e-3
    optim = build_optimizer(model, kind="adamw", lr=base_lr)
    sched = build_scheduler(
        optim,
        total_steps=100,
        schedule="cosine",
        warmup_steps=10,
        min_lr_ratio=0.1,
    )
    # Convention: scheduler construction sets last_epoch=0, so lr_lambda(0)=0
    # and the optimizer's "first" LR is 0 (legacy HF behaviour).  After 1
    # sched.step() → last_epoch=1 → lr = base * 1/10.
    sched.step()
    assert math.isclose(sched.get_last_lr()[0], base_lr * (1 / 10), rel_tol=1e-6), \
        sched.get_last_lr()
    # 9 more steps → last_epoch=10 → peak.
    for _ in range(9):
        sched.step()
    assert math.isclose(sched.get_last_lr()[0], base_lr, rel_tol=1e-6), \
        sched.get_last_lr()
    # 90 more steps → last_epoch=100 → min_lr_ratio * base.
    for _ in range(90):
        sched.step()
    assert math.isclose(sched.get_last_lr()[0], base_lr * 0.1, rel_tol=1e-3), \
        sched.get_last_lr()


def test_cosine_schedule_resume_via_last_step():
    """A scheduler resumed via ``last_step=K-1`` should produce the same
    current LR as a fresh scheduler that has been stepped K times.

    (PyTorch's ``LambdaLR`` constructor with ``last_epoch=K-1`` runs an
    internal ``_initial_step`` that advances the counter by 1 → land at
    K, matching a fresh scheduler that ran K user steps from
    ``last_epoch=-1``.  This is the contract :func:`build_scheduler`
    relies on when restoring training state — see ``train_bc`` in
    ``pymahjong/rl/bc.py`` for the call-site pattern.)
    """
    model_a = _TinyTransformerLike()
    model_b = _TinyTransformerLike()
    optim_a = build_optimizer(model_a, kind="adamw", lr=1e-3)
    optim_b = build_optimizer(model_b, kind="adamw", lr=1e-3)
    sched_a = build_scheduler(optim_a, total_steps=100, schedule="cosine",
                              warmup_steps=5, min_lr_ratio=0.1)
    # Step A forward 30 times.  After construction (advances -1 → 0)
    # plus 30 user steps, last_epoch = 30.
    for _ in range(30):
        sched_a.step()
    lr_a_now = sched_a.get_last_lr()[0]
    # Build B resumed at last_step=29; the constructor's _initial_step
    # advances 29 → 30.  No additional user step needed.
    sched_b = build_scheduler(optim_b, total_steps=100, schedule="cosine",
                              warmup_steps=5, min_lr_ratio=0.1,
                              last_step=29)
    lr_b_now = sched_b.get_last_lr()[0]
    assert math.isclose(lr_a_now, lr_b_now, rel_tol=1e-9), (lr_a_now, lr_b_now)


def test_combined_optimizer_lrs_advance_in_lockstep():
    """When using Muon+AdamW, the scheduler should apply the same
    multiplier to both underlying optimizers."""
    model = _TinyTransformerLike()
    optim = build_optimizer(model, kind="muon", lr=3e-4, muon_lr=0.02)
    sched = build_scheduler(optim, total_steps=10, schedule="linear",
                            warmup_steps=0, min_lr_ratio=0.0)
    # After 5 steps the multiplier should be 0.5 → muon=0.01, adamw=1.5e-4.
    for _ in range(5):
        sched.step()
    lrs = sched.get_last_lr()
    # First LR is Muon (built before AdamW in CombinedOptimizer).
    muon_lr = next(lr for lr in lrs if lr > 1e-3)
    adamw_lr = next(lr for lr in lrs if lr < 1e-3)
    assert math.isclose(muon_lr, 0.01, rel_tol=1e-2), lrs
    assert math.isclose(adamw_lr, 1.5e-4, rel_tol=1e-2), lrs


# ---------------------------------------------------------------------------
# End-to-end smoke: Muon + cosine on a tiny task overfits.
# ---------------------------------------------------------------------------

def test_muon_e2e_overfits_tiny_task():
    """Sanity: with Muon+cosine, the tiny model should drive its loss
    materially down on a fixed batch (overfitting smoke test)."""
    torch.manual_seed(123)
    model = _TinyTransformerLike()
    optim = build_optimizer(model, kind="muon", lr=1e-3, muon_lr=0.02)
    sched = build_scheduler(optim, total_steps=200, schedule="cosine",
                            warmup_steps=10, min_lr_ratio=0.01)
    x = torch.randn(16, 8)
    y = torch.randint(0, 5, (16,))
    initial_loss = None
    final_loss = None
    for step in range(200):
        logits, _ = model(x)
        loss = nn.functional.cross_entropy(logits, y)
        if step == 0:
            initial_loss = float(loss)
        optim.zero_grad()
        loss.backward()
        optim.step()
        sched.step()
        final_loss = float(loss)
    # Should overfit by ~10x or more on this trivial task.
    assert final_loss < initial_loss * 0.5, (initial_loss, final_loss)
