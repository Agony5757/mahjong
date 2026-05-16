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

from .action_space import ACTION_DIM
from .model import TransformerConfig

NEG_INF = -1e9


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
    ):
        super().__init__()
        cfg = config or TransformerConfig()
        self.cfg = cfg
        self.event_dim = event_dim
        self.action_dim = action_dim

        self.input_proj = nn.Linear(event_dim, cfg.d_model)
        if cfg.use_cls:
            self.cls = nn.Parameter(torch.zeros(1, 1, cfg.d_model))
            nn.init.trunc_normal_(self.cls, std=0.02)

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
        logits = self.policy_head(h)
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
        if deterministic:
            action = logits.argmax(dim=-1)
            log_prob = F.log_softmax(logits, dim=-1).gather(-1, action.unsqueeze(-1)).squeeze(-1)
        else:
            probs = F.softmax(logits, dim=-1)
            dist = torch.distributions.Categorical(probs=probs)
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
