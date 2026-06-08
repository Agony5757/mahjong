"""Transformer model for V4 event-stream encoding.

V4 events are 100-dim binary feature vectors (packed bitsets).
Instead of per-field embeddings (V3), a single linear projection maps
the event features into the transformer's model dimension.

The ``act()`` / ``evaluate_actions()`` interface matches
:class:`~pymahjong.rl.model.MahjongTransformer` so PPO and BC loops
are encoding-agnostic.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F

from .action_space import (
    ACTION_DIM,
    ACTION_HEAD_DIM,
    ACTION_HEAD_SLOTS,
    RESPONSE_HEAD_DIM,
    RESPONSE_HEAD_SLOTS,
)
from .common.config import TransformerConfig

NEG_INF = -1e9

# V4 event-stream pads to MAX_SEQ_LEN=512 (see TrainingDataEncodingV4.h).
# pos_emb gets ``+1`` to leave a slot for the prepended CLS token when
# ``cfg.use_cls`` is enabled.
MAX_SEQ_LEN = 512


class EventStreamTransformer(nn.Module):
    """Transformer policy/value model for V4 event-stream observations.

    Input: ``(B, L, event_dim)`` float tensor (binary features).
    Architecture mirrors :class:`MahjongTransformer` but replaces
    ``FieldEmbedding + scalar_proj`` with a single linear projection.
    """

    def __init__(
        self,
        config: TransformerConfig | None = None,
        event_dim: int = 100,
        action_dim: int = ACTION_DIM,
        pos_max_len: int = MAX_SEQ_LEN,
        split_heads: bool = False,
    ):
        super().__init__()
        cfg = config or TransformerConfig()
        self.cfg = cfg
        self.event_dim = event_dim
        self.action_dim = action_dim
        self.pos_max_len = pos_max_len
        self.split_heads = split_heads

        self.input_proj = nn.Linear(event_dim, cfg.d_model)
        if cfg.use_cls:
            self.cls = nn.Parameter(torch.zeros(1, 1, cfg.d_model))
            nn.init.trunc_normal_(self.cls, std=0.02)

        if getattr(cfg, "use_pos_emb", False):
            self.pos_emb = nn.Embedding(pos_max_len + 1, cfg.d_model)
            nn.init.zeros_(self.pos_emb.weight)
        else:
            self.pos_emb = None

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=cfg.d_model,
            nhead=cfg.n_heads,
            dim_feedforward=cfg.d_model * cfg.ff_mult,
            dropout=cfg.dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=cfg.n_layers)
        self.norm = nn.LayerNorm(cfg.d_model)

        if split_heads:
            # Phase-routed split heads: each head has exclusive jurisdiction
            # over its slots → response-phase logits can't leak into
            # action-phase decisions (and vice versa) because the two
            # output projections are entirely independent.
            self.policy_head_action = nn.Linear(cfg.d_model, ACTION_HEAD_DIM)
            self.policy_head_response = nn.Linear(cfg.d_model, RESPONSE_HEAD_DIM)
            # Pre-build int64 index tensors for fast scatter into 54-dim layout.
            self.register_buffer(
                "_action_slot_idx",
                torch.tensor(ACTION_HEAD_SLOTS, dtype=torch.long),
                persistent=False,
            )
            self.register_buffer(
                "_response_slot_idx",
                torch.tensor(RESPONSE_HEAD_SLOTS, dtype=torch.long),
                persistent=False,
            )
            # The legacy ``policy_head`` attribute is left absent so that
            # state-dict load mismatches surface loudly when accidentally
            # mixing single-head and split-head checkpoints.
        else:
            self.policy_head = nn.Linear(cfg.d_model, action_dim)
        self.value_head = nn.Sequential(
            nn.Linear(cfg.d_model, cfg.d_model),
            nn.GELU(),
            nn.Linear(cfg.d_model, 1),
        )

    # ------------------------------------------------------------------

    def encode(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """Run the transformer encoder.

        Args:
            features: ``(B, L, event_dim)`` float tensor.
            attention_mask: ``(B, L)`` bool tensor (True = valid).

        Returns:
            ``(B, d_model)`` pooled state representation.
        """
        x = self.input_proj(features.float())  # (B, L, D)
        if self.cfg.use_cls:
            cls = self.cls.expand(x.size(0), -1, -1)
            x = torch.cat([cls, x], dim=1)
            mask_extended = torch.cat(
                [torch.ones(x.size(0), 1, device=x.device, dtype=torch.bool), attention_mask],
                dim=1,
            )
        else:
            mask_extended = attention_mask
        if self.pos_emb is not None:
            L = x.size(1)
            if L > self.pos_emb.num_embeddings:
                raise ValueError(
                    f"EventStreamTransformer: sequence length {L} exceeds "
                    f"pos_emb capacity {self.pos_emb.num_embeddings}. "
                    f"Increase pos_max_len when constructing the model."
                )
            pos = torch.arange(L, device=x.device)
            x = x + self.pos_emb(pos).unsqueeze(0)
        key_padding_mask = ~mask_extended
        x = self.encoder(x, src_key_padding_mask=key_padding_mask)
        x = self.norm(x)
        if self.cfg.use_cls:
            cls_out = x[:, 0]
        else:
            cls_out = x.mean(dim=1)

        m = attention_mask.float().unsqueeze(-1)
        body = x[:, 1:] if self.cfg.use_cls else x
        denom = m.sum(dim=1).clamp(min=1.0)
        mean_pool = (body * m).sum(dim=1) / denom
        return cls_out + mean_pool

    def _policy_logits(self, h: torch.Tensor) -> torch.Tensor:
        """Return ``(B, 54)`` raw policy logits.

        In ``split_heads`` mode the two head projections write into
        their disjoint slot positions and *all other slots stay at
        -inf* (so they can never be picked by an inference argmax,
        even if the engine's action_mask incorrectly marked them
        legal — defence in depth).
        """
        if not self.split_heads:
            return self.policy_head(h)

        B = h.size(0)
        action_logits = self.policy_head_action(h)       # (B, 43)
        response_logits = self.policy_head_response(h)   # (B, 11)
        # Initialise the scatter target with NEG_INF so unwritten slots
        # are inert.  Using NEG_INF instead of 0 makes the cross-head
        # separation airtight: even after softmax these slots are 0.
        out = h.new_full((B, ACTION_DIM), NEG_INF)
        out.index_copy_(1, self._action_slot_idx, action_logits)
        out.index_copy_(1, self._response_slot_idx, response_logits)
        return out

    def forward(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor | None = None,
    ):
        """Compute (policy logits, value).

        Args:
            features: ``(B, L, event_dim)`` float tensor.
            attention_mask: ``(B, L)`` bool tensor (True = valid).
            action_mask: optional ``(B, ACTION_DIM)`` bool tensor.

        Returns:
            ``(logits, value)`` tuple.
        """
        h = self.encode(features, attention_mask)
        logits = self._policy_logits(h)
        value = self.value_head(h).squeeze(-1)
        if action_mask is not None:
            logits = logits.masked_fill(~action_mask, NEG_INF)
        return logits, value

    # ------------------------------------------------------------------
    # Convenience: act / evaluate_actions
    # ------------------------------------------------------------------

    @torch.no_grad()
    def act(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor,
        deterministic: bool = False,
    ):
        logits, value = self.forward(features, attention_mask, action_mask)
        # Numerical safety: clamp to a finite range and verify the mask
        # has at least one valid action per row to avoid `Categorical`
        # asserting on all-NEG_INF logits → NaN softmax → CUDA crash.
        if action_mask is not None:
            valid = action_mask.any(dim=-1, keepdim=True)
            if not bool(valid.all()):
                # Defensive fallback: if any row has no valid action, mark
                # action 0 as valid for that row.  Should never happen in
                # practice, but prevents a hard CUDA failure.
                fallback = torch.zeros_like(action_mask)
                fallback[..., 0] = True
                action_mask = torch.where(valid, action_mask, fallback)
                logits = logits.masked_fill(~action_mask, NEG_INF)
        # Replace any non-finite logits (NaN/Inf besides masked NEG_INF)
        # to keep the categorical distribution well-defined.
        finite = torch.isfinite(logits)
        # NEG_INF entries are isfinite=False but intentional; only sanitize
        # actual NaN/+Inf by checking the mask first.
        if action_mask is not None:
            need_fix = (~finite) & action_mask
            if bool(need_fix.any()):
                logits = torch.where(need_fix, torch.zeros_like(logits), logits)

        if deterministic:
            action = logits.argmax(dim=-1)
            log_prob = F.log_softmax(logits, dim=-1).gather(-1, action.unsqueeze(-1)).squeeze(-1)
        else:
            # Pass logits (not probs) for numerical stability; Categorical
            # applies a stable log-softmax internally.
            dist = torch.distributions.Categorical(logits=logits)
            action = dist.sample()
            log_prob = dist.log_prob(action)
        return action, log_prob, value

    def evaluate_actions(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor,
        actions: torch.Tensor,
    ):
        """Compute log-probs, entropy, and value for given actions (PPO)."""
        logits, value = self.forward(features, attention_mask, action_mask)
        log_probs = F.log_softmax(logits, dim=-1).gather(-1, actions.unsqueeze(-1)).squeeze(-1)
        probs = F.softmax(logits, dim=-1)
        entropy = -(probs * F.log_softmax(logits, dim=-1)).sum(dim=-1)
        return log_probs, entropy, value
