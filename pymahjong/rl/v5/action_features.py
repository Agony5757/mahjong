"""Per-action semantic feature vectors for the V5 Douzero-style head.

This module is the single source of truth for the action descriptor
table consumed by :class:`pymahjong.rl.v5.model.DouzeroV5Transformer`.

Each row of the returned ``(ACTION_DIM, ACTION_FEAT_DIM)`` matrix
encodes the *intrinsic* features of one action in the 54-action unified
space (see :mod:`pymahjong.rl.action_space`).  Intrinsic = features
that do not depend on the engine's current context.  Tile choice for
chi/pon/kan/ron is context-dependent and is therefore left zero; the
state representation already contains that information.

Feature layout (50 dims total)::

    0..10   action-type one-hot
            [Discard, Chi, Pon, AnKan, MinKan, KaKan,
             Riichi, Ron, Tsumo, Push, Pass]
    11      red_dora_used flag (1 = action uses a red 5)
    12..14  chi_position one-hot (left / middle / right)
    15..48  tile_basetile one-hot (34 dims; non-zero only for discards)
    49      phase indicator (0 = action-phase, 1 = response-phase)

Changing this layout breaks any V5 checkpoint, since the
``action_features`` buffer is registered with the model.  If you must
extend the descriptors, add new dims to the *end* and bump
:data:`ACTION_FEAT_DIM` accordingly; old checkpoints can then be
loaded with ``strict=False`` and the new dims will start at zero.
"""

from __future__ import annotations

import numpy as np

from ..action_space import (
    ACTION_DIM,
    A_DISCARD_BASE,
    A_DISCARD_RED5M,
    A_DISCARD_RED5P,
    A_DISCARD_RED5S,
    A_CHILEFT, A_CHIMIDDLE, A_CHIRIGHT,
    A_CHILEFT_USERED, A_CHIMIDDLE_USERED, A_CHIRIGHT_USERED,
    A_PON, A_PON_USERED,
    A_ANKAN, A_MINKAN, A_KAKAN,
    A_RIICHI, A_RON, A_TSUMO, A_PUSH,
    A_PASS_RIICHI, A_PASS_RESPONSE,
    RESPONSE_HEAD_SLOTS,
)

# Total feature dimension per action.
ACTION_FEAT_DIM: int = 50

# Action-type indices in the one-hot block (offsets 0..10).
_T_DISCARD = 0
_T_CHI = 1
_T_PON = 2
_T_ANKAN = 3
_T_MINKAN = 4
_T_KAKAN = 5
_T_RIICHI = 6
_T_RON = 7
_T_TSUMO = 8
_T_PUSH = 9
_T_PASS = 10

# Other field offsets.
_F_RED_DORA = 11
_F_CHI_POS_BASE = 12       # 12..14
_F_TILE_BASE = 15          # 15..48 (34 dims)
_F_PHASE_RESPONSE = 49


def build_action_features() -> np.ndarray:
    """Return the fixed ``(ACTION_DIM, ACTION_FEAT_DIM)`` descriptor matrix.

    Returns:
        Float32 ndarray, row ``a`` is the semantic feature vector for
        action index ``a`` in the 54-action unified space.
    """
    F = np.zeros((ACTION_DIM, ACTION_FEAT_DIM), dtype=np.float32)
    response_set = set(RESPONSE_HEAD_SLOTS)

    # Phase indicator: response-phase actions get bit 49 set.
    for a in range(ACTION_DIM):
        if a in response_set:
            F[a, _F_PHASE_RESPONSE] = 1.0

    # Discards 0..33 -- tile basetile is the action index itself.
    for tile in range(34):
        F[A_DISCARD_BASE + tile, _T_DISCARD] = 1.0
        F[A_DISCARD_BASE + tile, _F_TILE_BASE + tile] = 1.0

    # Red-5 discards (slots 34/35/36).
    for slot, tile in (
        (A_DISCARD_RED5M, 4),
        (A_DISCARD_RED5P, 13),
        (A_DISCARD_RED5S, 22),
    ):
        F[slot, _T_DISCARD] = 1.0
        F[slot, _F_RED_DORA] = 1.0
        F[slot, _F_TILE_BASE + tile] = 1.0

    # Chi (no fixed tile -- depends on the discarded tile).
    for slot, pos in (
        (A_CHILEFT, 0), (A_CHIMIDDLE, 1), (A_CHIRIGHT, 2),
    ):
        F[slot, _T_CHI] = 1.0
        F[slot, _F_CHI_POS_BASE + pos] = 1.0
    for slot, pos in (
        (A_CHILEFT_USERED, 0), (A_CHIMIDDLE_USERED, 1), (A_CHIRIGHT_USERED, 2),
    ):
        F[slot, _T_CHI] = 1.0
        F[slot, _F_RED_DORA] = 1.0
        F[slot, _F_CHI_POS_BASE + pos] = 1.0

    # Pon variants.
    F[A_PON, _T_PON] = 1.0
    F[A_PON_USERED, _T_PON] = 1.0
    F[A_PON_USERED, _F_RED_DORA] = 1.0

    # Kan variants.
    F[A_ANKAN, _T_ANKAN] = 1.0
    F[A_MINKAN, _T_MINKAN] = 1.0
    F[A_KAKAN, _T_KAKAN] = 1.0

    # Other special actions.
    F[A_RIICHI, _T_RIICHI] = 1.0
    F[A_RON, _T_RON] = 1.0
    F[A_TSUMO, _T_TSUMO] = 1.0
    F[A_PUSH, _T_PUSH] = 1.0
    F[A_PASS_RIICHI, _T_PASS] = 1.0
    F[A_PASS_RESPONSE, _T_PASS] = 1.0

    return F


def torch_action_features():
    """Return :func:`build_action_features` as a torch tensor."""
    import torch
    return torch.from_numpy(build_action_features())


__all__ = ["ACTION_FEAT_DIM", "build_action_features", "torch_action_features"]
