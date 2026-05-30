"""Extract per-legal-action feature tensors from a V4 ``action_mask``.

True Douzero feeds *only* the legal actions through the scorer (not all
54 with -inf masking).  V5 keeps the existing V4 cache format and
``action_mask`` schema untouched and derives the per-legal-action
tensors at collate / inference time using this module.

The output of :func:`extract_legal_actions` is the canonical "action
side" of V5's model input:

* ``action_features`` ``(B, K, F)``
    Per-legal-action descriptor vectors taken row-by-row from the
    static 54x``ACTION_FEAT_DIM`` table (see
    :func:`pymahjong.rl.v5.action_features.build_action_features`).
    Slot ``k`` in row ``b`` corresponds to the ``k``-th legal action in
    sample ``b`` (in ascending unified-space index order).  Padded slots
    are zeros.

* ``action_pad_mask`` ``(B, K)`` bool
    ``True`` for real legal actions, ``False`` for padding.

* ``legal_orig_idx`` ``(B, K)`` long
    Original 54-space index for each legal slot.  Padded slots point at
    a sentinel index (``54``) so that scatter operations into a 55-wide
    sink-padded tensor land safely outside the 54-action range.

* ``legal_target_idx`` ``(B,)`` long (optional, only when ``action`` arg
    is supplied):  position of the expert's action *within* the legal
    list (``0..K-1``).  Required for V5 BC cross-entropy because V5's
    softmax is over K legals, not 54 slots.

``K`` is set to the per-batch maximum legal-action count plus a small
safety slack (default 0); use a fixed ``max_k`` to pre-pad to a known
maximum (e.g. for static-shape graphs or torch.compile).
"""

from __future__ import annotations

from typing import Optional, Tuple

import torch

from ..action_space import ACTION_DIM
from .action_features import ACTION_FEAT_DIM, torch_action_features

# Sentinel index used in ``legal_orig_idx`` for padded slots so a
# downstream scatter into a (B, 55) sink-padded buffer writes the
# padded -inf score into the 54-th column (which we then discard).
PAD_INDEX: int = ACTION_DIM  # = 54


def extract_legal_actions(
    action_mask: torch.Tensor,
    *,
    action_descriptors: Optional[torch.Tensor] = None,
    action: Optional[torch.Tensor] = None,
    max_k: int = 0,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, Optional[torch.Tensor]]:
    """Convert a ``(B, 54)`` bool ``action_mask`` into per-legal-action tensors.

    Args:
        action_mask: ``(B, ACTION_DIM)`` boolean mask of legal actions
            (any dtype convertible to bool is accepted).
        action_descriptors: optional ``(ACTION_DIM, F)`` static
            descriptor matrix.  If ``None``, the module-level fixed
            descriptors (see
            :func:`pymahjong.rl.v5.action_features.torch_action_features`)
            are used.  Lives on the same device as ``action_mask``.
        action: optional ``(B,)`` expert-action labels in unified
            54-space.  If supplied, ``legal_target_idx`` is also returned
            with each sample's expert-action position within its legal
            list (``0..K-1``); raises ``RuntimeError`` if any expert
            action lies outside its sample's legal set.
        max_k: if ``> 0``, pad to exactly this many slots.  Useful for
            static-shape inference graphs.  If ``0``, ``K`` = per-batch
            max legal count (so the tensor stays as small as possible).

    Returns:
        ``(action_features, action_pad_mask, legal_orig_idx, legal_target_idx)``

        * ``action_features``  ``(B, K, F)`` float
        * ``action_pad_mask``  ``(B, K)`` bool
        * ``legal_orig_idx``   ``(B, K)`` long  (PAD_INDEX in padded slots)
        * ``legal_target_idx`` ``(B,)`` long or ``None``
    """
    mask = action_mask.bool()
    if mask.dim() != 2 or mask.size(-1) != ACTION_DIM:
        raise ValueError(
            f"action_mask must be (B, {ACTION_DIM}); got {tuple(action_mask.shape)}"
        )
    B = mask.size(0)
    device = mask.device

    if action_descriptors is None:
        action_descriptors = torch_action_features().to(device)
    elif action_descriptors.device != device:
        action_descriptors = action_descriptors.to(device)
    F = action_descriptors.size(-1)

    counts = mask.sum(dim=-1)              # (B,)
    K_batch = int(counts.max().item()) if B > 0 else 0
    K = max(K_batch, max_k, 1)             # at least 1 to keep tensors well-shaped

    legal_orig_idx = torch.full((B, K), PAD_INDEX, dtype=torch.long, device=device)
    action_pad_mask = torch.zeros((B, K), dtype=torch.bool, device=device)
    action_features = torch.zeros((B, K, F), dtype=action_descriptors.dtype, device=device)

    if B == 0:
        legal_target_idx = (
            torch.zeros((0,), dtype=torch.long, device=device) if action is not None else None
        )
        return action_features, action_pad_mask, legal_orig_idx, legal_target_idx

    # Per-batch row-wise scatter: rank-based assignment using argsort on
    # the (B, 54) mask.  Row b's legal slots get K slots [0..counts[b]-1]
    # populated; rest stay at PAD_INDEX / False / 0.
    # Vectorised implementation:
    #   1) Build a (B, 54) "rank within legals" tensor: cumulative sum
    #      of mask along dim=-1, then subtract 1 (0-indexed).  Only
    #      meaningful for slots where mask is True.
    cumulative = mask.long().cumsum(dim=-1)               # (B, 54)
    rank_in_legals = cumulative - 1                       # (B, 54), -1 where mask=False
    rank_in_legals = rank_in_legals.clamp(min=0)          # (B, 54), garbage where mask=False

    # Build (B, 54) batch index for the scatter destination.
    batch_idx = torch.arange(B, device=device).unsqueeze(-1).expand(B, ACTION_DIM)
    src_idx = torch.arange(ACTION_DIM, device=device).unsqueeze(0).expand(B, ACTION_DIM)

    # Flatten (B, 54) to (B*54,) for boolean index_put on the (B, K) outputs.
    flat_b = batch_idx[mask]                              # (sum_K,)
    flat_rank = rank_in_legals[mask]                      # (sum_K,)
    flat_src = src_idx[mask]                              # (sum_K,) -- 54-space idx

    legal_orig_idx[flat_b, flat_rank] = flat_src
    action_pad_mask[flat_b, flat_rank] = True
    action_features[flat_b, flat_rank] = action_descriptors[flat_src]

    legal_target_idx: Optional[torch.Tensor] = None
    if action is not None:
        # For each batch sample b, find where action[b] sits in the
        # legal list.  Vectorised: rank_in_legals[b, action[b]] iff
        # mask[b, action[b]] is True (which must hold for valid data).
        action = action.to(device=device, dtype=torch.long)
        if action.shape != (B,):
            raise ValueError(
                f"action must be shape (B,) = ({B},); got {tuple(action.shape)}"
            )
        legal_target_idx = rank_in_legals.gather(1, action.unsqueeze(-1)).squeeze(-1)
        # Sanity: expert action must be among the legal set.
        chosen_mask = mask.gather(1, action.unsqueeze(-1)).squeeze(-1)
        if not bool(chosen_mask.all()):
            raise RuntimeError(
                "extract_legal_actions: expert action lies outside its "
                "legal-action set; check dataset for action_mask drift"
            )

    return action_features, action_pad_mask, legal_orig_idx, legal_target_idx


__all__ = ["ACTION_FEAT_DIM", "PAD_INDEX", "extract_legal_actions"]
