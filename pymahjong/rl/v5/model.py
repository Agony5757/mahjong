"""V5: true Douzero-style policy — state encoding and *available actions*
are separate model inputs, and the model scores **only the legal
actions** through a shared MLP.

The architecture is *not* "score all 54 with -inf masking" (the cheap
math-equivalent shortcut); the K legal actions are fed in as their own
``(B, K, F)`` tensor and the scorer never sees illegal slots.  This
matches the Douzero (DouDizhu) paper's design and has three benefits:

* The action side is a true model input -- the descriptors can be
  *context-enriched* (e.g. include which exact tile from hand a chi
  would consume) without retraining a different head.
* No mask-leak pathology by construction; there is no shared partition
  function over illegals.
* The scorer is permutation-invariant over the legal-action order, so
  it generalises better across hand states that surface different
  legal-action subsets.

Compatibility with the V4 infrastructure (env, self-play eval, cache
shape) is preserved via a thin wrapper: V5's ``forward`` /
``act`` / ``evaluate_actions`` accept the V4-style ``(features,
attention_mask, action_mask)`` triple and run
:func:`extract_legal_actions` internally to derive the per-legal
action tensors.  The returned (B, 54) raw logits scatter the K
Douzero scores into the original 54-action layout (-inf elsewhere) so
all downstream consumers (BC loss, PPO loss, self-play act loop)
remain encoding-agnostic.
"""

from __future__ import annotations

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from ..action_space import ACTION_DIM
from ..common.config import TransformerConfig
from ..v4.model import EventStreamTransformer, NEG_INF, V4_MAX_SEQ_LEN
from .action_features import ACTION_FEAT_DIM, torch_action_features
from .legal_actions import PAD_INDEX, extract_legal_actions


class DouzeroV5Transformer(EventStreamTransformer):
    """Event-stream transformer with a true Douzero-style policy.

    Inputs to ``forward``:

    * ``features``        ``(B, L, event_dim)`` float  -- state events
    * ``attention_mask``  ``(B, L)`` bool              -- state mask
    * ``action_features`` ``(B, K, action_feat_dim)`` float -- one row
      per *legal* action in the sample (use
      :func:`extract_legal_actions` to derive)
    * ``action_pad_mask`` ``(B, K)`` bool -- True for real legals
    * ``legal_orig_idx``  ``(B, K)`` long -- original 54-space indices
      (padded slots = ``PAD_INDEX`` = 54)

    Outputs:

    * ``raw_logits_54`` ``(B, ACTION_DIM)`` -- the K Douzero scores
      scattered into the 54-action layout; illegal slots are NEG_INF so
      the existing BC/PPO loss code remains unchanged.
    * ``value`` ``(B,)``

    Convenience entry points (V4-compat signature):

    * ``act(features, attention_mask, action_mask, deterministic)``
      and ``evaluate_actions(features, attention_mask, action_mask,
      actions)`` accept the V4-style ``action_mask`` and call
      :func:`extract_legal_actions` internally, so V5 is a drop-in
      replacement for V4 in the env / self-play eval code paths.
    """

    def __init__(
        self,
        config: TransformerConfig | None = None,
        event_dim: int = 100,
        action_dim: int = ACTION_DIM,
        pos_max_len: int = V4_MAX_SEQ_LEN,
        action_feat_dim: int = ACTION_FEAT_DIM,
        action_proj_dim: int | None = None,
        scorer_hidden: int = 256,
        scorer_dropout: float = 0.0,
    ):
        super().__init__(
            config=config,
            event_dim=event_dim,
            action_dim=action_dim,
            pos_max_len=pos_max_len,
            split_heads=False,
        )
        d = self.cfg.d_model
        action_proj_dim = action_proj_dim or d
        self.action_feat_dim = action_feat_dim
        self.action_proj_dim = action_proj_dim

        # Drop the V4 linear policy head -- V5 replaces it entirely.
        del self.policy_head

        # The default static descriptors used by act() / evaluate_actions()
        # convenience wrappers.  Training paths pass action_features
        # explicitly so they can be enriched per-sample later.
        self.register_buffer(
            "default_action_descriptors",
            torch_action_features(),
            persistent=False,
        )

        # Project the per-legal-action descriptor into the model's
        # representation space.
        self.action_proj = nn.Linear(action_feat_dim, action_proj_dim)

        # Shared scorer: state (d) + action embedding (action_proj_dim) -> 1.
        self.scorer = nn.Sequential(
            nn.Linear(d + action_proj_dim, scorer_hidden),
            nn.GELU(),
            nn.Dropout(scorer_dropout),
            nn.Linear(scorer_hidden, scorer_hidden),
            nn.GELU(),
            nn.Dropout(scorer_dropout),
            nn.Linear(scorer_hidden, 1),
        )

    # ------------------------------------------------------------------
    # Core: Douzero scoring on legal actions, scatter to 54 slots
    # ------------------------------------------------------------------

    def _score_legal_actions(
        self,
        h: torch.Tensor,                  # (B, d_model)
        action_features: torch.Tensor,    # (B, K, F)
        action_pad_mask: torch.Tensor,    # (B, K) bool
    ) -> torch.Tensor:
        """Return raw scores ``(B, K)`` for the K legal-action slots.

        Padded slots are filled with ``NEG_INF`` so downstream softmax
        ignores them.
        """
        B, K, _ = action_features.shape
        D = h.shape[-1]
        a = self.action_proj(action_features)            # (B, K, D_a)
        h_rep = h.unsqueeze(1).expand(B, K, D)            # (B, K, D)
        x = torch.cat([h_rep, a], dim=-1)                 # (B, K, D + D_a)
        scores = self.scorer(x).squeeze(-1)               # (B, K)
        return scores.masked_fill(~action_pad_mask, NEG_INF)

    def _scatter_to_54(
        self,
        scores_K: torch.Tensor,          # (B, K)
        legal_orig_idx: torch.Tensor,    # (B, K) -- PAD_INDEX in padded slots
    ) -> torch.Tensor:
        """Scatter K Douzero scores into a ``(B, ACTION_DIM)`` layout.

        Padded slots scatter their NEG_INF into a sentinel sink column
        (index ``PAD_INDEX`` = 54) of a ``(B, 55)`` intermediate, which
        is then sliced away.  This guarantees that real legal scores
        never get overwritten by padded NEG_INF writes when a row has
        fewer than K legal actions.
        """
        B = scores_K.size(0)
        out_55 = scores_K.new_full((B, ACTION_DIM + 1), NEG_INF)
        out_55.scatter_(1, legal_orig_idx, scores_K)
        return out_55[:, :ACTION_DIM]

    # ------------------------------------------------------------------
    # Forward (Douzero signature)
    # ------------------------------------------------------------------

    def forward(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_features: Optional[torch.Tensor] = None,
        action_pad_mask: Optional[torch.Tensor] = None,
        legal_orig_idx: Optional[torch.Tensor] = None,
        action_mask: Optional[torch.Tensor] = None,
    ):
        """Compute (raw_logits_54, value).

        Two calling conventions are supported:

        1. **Douzero (preferred for training)** -- pass
           ``action_features`` / ``action_pad_mask`` / ``legal_orig_idx``
           explicitly (typically produced by the V5 collate function).

        2. **V4-compatible (preferred for env loops)** -- pass a
           ``action_mask`` of shape ``(B, 54)`` and let the model
           derive ``action_features`` / ``action_pad_mask`` /
           ``legal_orig_idx`` on the fly using the static descriptors.

        Returns:
            ``(raw_logits_54, value)``.  ``raw_logits_54`` has shape
            ``(B, ACTION_DIM)`` with NEG_INF for any illegal slot
            (defence in depth + back-compat with the V4 loss code).
        """
        if action_features is None:
            if action_mask is None:
                raise ValueError(
                    "V5 forward requires either Douzero inputs "
                    "(action_features + action_pad_mask + legal_orig_idx) "
                    "or a V4-style action_mask"
                )
            action_features, action_pad_mask, legal_orig_idx, _ = extract_legal_actions(
                action_mask,
                action_descriptors=self.default_action_descriptors,
            )

        h = self.encode(features, attention_mask)               # (B, D)
        scores_K = self._score_legal_actions(h, action_features, action_pad_mask)
        raw_logits_54 = self._scatter_to_54(scores_K, legal_orig_idx)
        value = self.value_head(h).squeeze(-1)
        return raw_logits_54, value

    # ------------------------------------------------------------------
    # Convenience: act / evaluate_actions  (V4-compat signature)
    # ------------------------------------------------------------------

    @torch.no_grad()
    def act(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor,
        deterministic: bool = False,
    ):
        """V4-compatible action selection (returns 54-space index).

        Internally builds the per-legal-action tensors from
        ``action_mask`` and scores only the K legal actions.  Output
        log-probs are derived from a softmax over the K legals.
        """
        action_features, action_pad_mask, legal_orig_idx, _ = extract_legal_actions(
            action_mask, action_descriptors=self.default_action_descriptors,
        )
        h = self.encode(features, attention_mask)
        scores_K = self._score_legal_actions(h, action_features, action_pad_mask)
        value = self.value_head(h).squeeze(-1)

        # Defensive: rows with zero legal actions get a synthetic legal
        # slot at index 0 so Categorical does not assert.  This should
        # never fire on well-formed env data.
        any_legal = action_pad_mask.any(dim=-1)
        if not bool(any_legal.all()):
            fallback = torch.zeros_like(action_pad_mask)
            fallback[..., 0] = True
            action_pad_mask = torch.where(any_legal.unsqueeze(-1), action_pad_mask, fallback)
            scores_K = scores_K.masked_fill(~action_pad_mask, NEG_INF)
            # Direct slot-0 fallback uses a "discard tile 0" action; the
            # caller should treat this as best-effort recovery only.
            fallback_orig = legal_orig_idx.clone()
            fallback_orig[..., 0] = 0
            legal_orig_idx = torch.where(any_legal.unsqueeze(-1), legal_orig_idx, fallback_orig)

        if deterministic:
            idx_in_K = scores_K.argmax(dim=-1)
            log_prob = F.log_softmax(scores_K, dim=-1).gather(
                -1, idx_in_K.unsqueeze(-1)
            ).squeeze(-1)
        else:
            dist = torch.distributions.Categorical(logits=scores_K)
            idx_in_K = dist.sample()
            log_prob = dist.log_prob(idx_in_K)

        action_54 = legal_orig_idx.gather(-1, idx_in_K.unsqueeze(-1)).squeeze(-1)
        return action_54, log_prob, value

    def evaluate_actions(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor,
        actions: torch.Tensor,
    ):
        """V4-compatible PPO/BC interface (action in 54-space).

        Resolves each ``action`` to its index within the legal set,
        then computes log-probs / entropy on the K-wide softmax.  The
        returned value is differentiable w.r.t. all model parameters
        used during scoring (action_proj, scorer, encoder).
        """
        action_features, action_pad_mask, legal_orig_idx, target_in_K = \
            extract_legal_actions(
                action_mask,
                action_descriptors=self.default_action_descriptors,
                action=actions,
            )
        h = self.encode(features, attention_mask)
        scores_K = self._score_legal_actions(h, action_features, action_pad_mask)
        value = self.value_head(h).squeeze(-1)

        log_probs = F.log_softmax(scores_K, dim=-1).gather(
            -1, target_in_K.unsqueeze(-1)
        ).squeeze(-1)
        # Entropy on the (renormalised) K-wide categorical -- ignores
        # padded slots automatically because their score is NEG_INF.
        probs = F.softmax(scores_K, dim=-1)
        log_probs_all = F.log_softmax(scores_K, dim=-1)
        # 0 * (-inf) → nan; mask before sum.
        contribs = torch.where(action_pad_mask, probs * log_probs_all,
                                torch.zeros_like(probs))
        entropy = -contribs.sum(dim=-1)
        return log_probs, entropy, value


__all__ = ["DouzeroV5Transformer"]
