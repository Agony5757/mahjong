"""V5 encoding strategy -- V4 event-stream observations + true Douzero head.

V5 inherits every observation, cache, and dataset surface from V4
unchanged: the 100-dim event-stream bitset, the 512-token sequence
layout, the on-disk shard format, the streaming/cached datasets, and
the V4 environment.  **Any existing V4 cache can be reused for V5
training without re-encoding.**

The only model-side difference is the policy head: V4 uses a
``Linear(d_model, 54)`` projection (or two phase-split linears); V5
instead feeds the per-legal-action descriptors as a *separate model
input* and scores only the K legal actions through a shared MLP
(:class:`~pymahjong.rl.v5.model.DouzeroV5Transformer`).

This module wires the V4 cache/dataset into V5 by overriding only:

* :meth:`create_model`   -> builds :class:`DouzeroV5Transformer`.
* :meth:`collate_fn`     -> after V4 collation, runs
  :func:`extract_legal_actions` and appends
  ``action_features`` / ``action_pad_mask`` / ``legal_orig_idx`` /
  ``legal_target_idx`` so the model never has to do that work itself
  during training (it does for env/inference paths via the V4-compat
  wrappers).
* :meth:`forward_from_batch` / :meth:`forward_from_batch_raw` /
  :meth:`evaluate_actions_from_batch` -> pass the Douzero tensors.
"""

from __future__ import annotations

from typing import Any, Dict

import torch

from ..encoding import EncodingVersion, register
from .v4 import V4Strategy


class V5Strategy(V4Strategy):
    """V5 reuses V4 obs / caches; only model + collate / forward differ."""

    version = EncodingVersion.V5

    def create_model(self, **kwargs) -> Any:
        from ..common.config import TransformerConfig
        from ..v5.action_features import ACTION_FEAT_DIM
        from ..v5.model import DouzeroV5Transformer

        cfg = kwargs.get("transformer_config") or TransformerConfig()
        # V5 ignores ``split_heads`` (the shared scorer subsumes phase
        # routing via the descriptor's phase bit).  Accept-and-ignore
        # to keep the trainer call sites encoding-agnostic.
        return DouzeroV5Transformer(
            config=cfg,
            event_dim=self.EVENT_DIM,
            action_feat_dim=kwargs.get("action_feat_dim", ACTION_FEAT_DIM),
            action_proj_dim=kwargs.get("action_proj_dim", None),
            scorer_hidden=kwargs.get("scorer_hidden", 256),
            scorer_dropout=kwargs.get("scorer_dropout", 0.0),
        )

    def collate_fn(self, batch: list) -> Dict[str, Any]:
        """V4 collate + Douzero per-legal-action tensors."""
        from ..v4.cached_dataset import cached_event_collate
        from ..v5.legal_actions import extract_legal_actions

        out = cached_event_collate(batch)
        action_features, action_pad_mask, legal_orig_idx, legal_target_idx = \
            extract_legal_actions(
                out["action_mask"],
                action=out["action"],
            )
        out["action_features"] = action_features
        out["action_pad_mask"] = action_pad_mask
        out["legal_orig_idx"] = legal_orig_idx
        out["legal_target_idx"] = legal_target_idx
        return out

    def obs_to_tensor(self, obs: dict, device):
        """Single-sample observation -> model-ready tensors.

        Returns the same ``(features, attention_mask, action_mask)``
        triple as V4 for env-loop compatibility -- V5's ``act()`` /
        ``evaluate_actions()`` derive the per-legal-action tensors
        internally.
        """
        import torch
        feat = torch.as_tensor(obs["features"], device=device).unsqueeze(0)
        if not feat.is_floating_point():
            feat = feat.float()
        return (
            feat,
            torch.as_tensor(obs["attention_mask"], device=device, dtype=torch.bool).unsqueeze(0),
            torch.as_tensor(obs["action_mask"], device=device, dtype=torch.bool).unsqueeze(0),
        )

    def forward_from_batch(self, model, batch: dict):
        """Dispatch a V5 batch through the model -> (raw_logits_54, value).

        Uses the Douzero signature: action_features / action_pad_mask /
        legal_orig_idx are provided by :meth:`collate_fn` so the model
        never re-derives them mid-training.
        """
        return model(
            batch["features"],
            batch["attention_mask"],
            action_features=batch["action_features"],
            action_pad_mask=batch["action_pad_mask"],
            legal_orig_idx=batch["legal_orig_idx"],
        )

    def forward_from_batch_raw(self, model, batch: dict):
        """Return *un-masked* raw logits + value + the 54-space action mask.

        V5 raw logits are already scattered to (B, 54) with NEG_INF in
        illegal slots, which keeps the BC loss code (which expects to
        be able to apply ``masked_fill(~action_mask, -1e9)``) working
        unchanged.  The returned action_mask is the original V4-style
        54-wide bool tensor for any diagnostics that inspect it.
        """
        raw_logits, value = self.forward_from_batch(model, batch)
        return raw_logits, value, batch["action_mask"]

    def evaluate_actions_from_batch(self, model, batch: dict, actions):
        """Dispatch a V5 batch through evaluate_actions for PPO.

        Routes through the explicit Douzero signature: the model's
        evaluate_actions accepts the V4-style action_mask and runs
        extract_legal_actions internally so PPO callers don't have to
        change.  Pre-computing in collate_fn would also work but the
        small re-extraction cost is negligible relative to the
        backward pass; keeping the entry simple matches V4.
        """
        return model.evaluate_actions(
            batch["features"],
            batch["attention_mask"],
            batch["action_mask"],
            actions,
        )


register(EncodingVersion.V5, V5Strategy())
