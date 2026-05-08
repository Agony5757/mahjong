"""Transformer model for tokenized Mahjong observations.

The architecture:

* Per-field embedding tables (segment, tile, count, who, extra) → summed.
* Optional learned ``[CLS]`` token prepended.
* TransformerEncoder with key padding mask (from ``attention_mask``).
* Two heads:
    * **policy**: linear → 54 logits, masked by ``action_mask``.
    * **value**:  linear → scalar V(s) for PPO.

Both heads read from the ``[CLS]`` token, optionally pooled with the rest
of the sequence via simple mean pooling.

The model is intentionally compact (~5M params @ d_model=192, depth=4)
so it can be trained on a single GPU and inferred on CPU during self-play.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn as nn
import torch.nn.functional as F

from .tokenization import (
    ACTION_DIM,
    FIELD_VOCAB,
    MAX_SEQ_LEN,
    SCALAR_DIM,
    TOKEN_FEATURES,
)

NEG_INF = -1e9


@dataclass
class TransformerConfig:
    d_model: int = 192
    n_heads: int = 6
    n_layers: int = 4
    ff_mult: int = 4
    dropout: float = 0.1
    use_cls: bool = True
    max_seq_len: int = MAX_SEQ_LEN


class FieldEmbedding(nn.Module):
    """Sum of separate embedding tables, one per token field."""

    FIELDS = ("segment", "tile", "count", "who", "extra")

    def __init__(self, d_model: int):
        super().__init__()
        self.embeds = nn.ModuleDict(
            {f: nn.Embedding(FIELD_VOCAB[f], d_model) for f in self.FIELDS}
        )

    def forward(self, tokens: torch.Tensor) -> torch.Tensor:
        # tokens: (B, L, 5) int
        out = 0
        for i, f in enumerate(self.FIELDS):
            out = out + self.embeds[f](tokens[..., i].clamp_(min=0))
        return out


class MahjongTransformer(nn.Module):
    """Transformer policy/value model for Mahjong."""

    def __init__(
        self,
        config: TransformerConfig | None = None,
        action_dim: int = ACTION_DIM,
    ):
        super().__init__()
        cfg = config or TransformerConfig()
        self.cfg = cfg
        self.action_dim = action_dim

        self.embed = FieldEmbedding(cfg.d_model)
        # Project the per-token scalar features into the model dim and add
        # to the embedding sum. This is the channel that carries true
        # numeric magnitudes (score / 25000, remaining / 70, ...).
        self.scalar_proj = nn.Linear(SCALAR_DIM, cfg.d_model, bias=False)
        nn.init.zeros_(self.scalar_proj.weight)
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
        tokens: torch.Tensor,
        attention_mask: torch.Tensor,
        scalars: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """Run the transformer encoder.

        Returns a tensor of shape ``(B, d_model)`` representing the
        pooled state representation (CLS token + mean of valid tokens).
        """
        x = self.embed(tokens)  # (B, L, D)
        if scalars is not None:
            x = x + self.scalar_proj(scalars)
        if self.cfg.use_cls:
            cls = self.cls.expand(x.size(0), -1, -1)
            x = torch.cat([cls, x], dim=1)
            mask_extended = torch.cat(
                [torch.ones(x.size(0), 1, device=x.device, dtype=torch.bool), attention_mask],
                dim=1,
            )
        else:
            mask_extended = attention_mask
        # nn.TransformerEncoder expects True == "ignore"
        key_padding_mask = ~mask_extended
        x = self.encoder(x, src_key_padding_mask=key_padding_mask)
        x = self.norm(x)
        if self.cfg.use_cls:
            cls_out = x[:, 0]
        else:
            cls_out = x.mean(dim=1)

        # mean over valid (non-pad) tokens
        m = attention_mask.float().unsqueeze(-1)
        body = x[:, 1:] if self.cfg.use_cls else x
        denom = m.sum(dim=1).clamp(min=1.0)
        mean_pool = (body * m).sum(dim=1) / denom
        return cls_out + mean_pool

    def forward(
        self,
        tokens: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor | None = None,
        scalars: torch.Tensor | None = None,
    ):
        """Compute (policy logits, value) given a batch of observations.

        Args:
            tokens: ``(B, L, 5)`` int tensor.
            attention_mask: ``(B, L)`` bool tensor (True = valid).
            action_mask: optional ``(B, ACTION_DIM)`` bool tensor.
            scalars: optional ``(B, L, SCALAR_DIM)`` float tensor.

        Returns:
            A tuple ``(logits, value)``. ``logits`` is masked with
            ``-inf`` on disallowed actions (if a mask was provided).
        """
        h = self.encode(tokens, attention_mask, scalars=scalars)
        logits = self.policy_head(h)
        value = self.value_head(h).squeeze(-1)
        if action_mask is not None:
            logits = logits.masked_fill(~action_mask, NEG_INF)
        return logits, value

    # ------------------------------------------------------------------
    # Convenience: act / select / log_prob
    # ------------------------------------------------------------------

    @torch.no_grad()
    def act(
        self,
        tokens: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor,
        deterministic: bool = False,
        scalars: torch.Tensor | None = None,
    ):
        logits, value = self.forward(tokens, attention_mask, action_mask, scalars=scalars)
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
        tokens: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor,
        actions: torch.Tensor,
        scalars: torch.Tensor | None = None,
    ):
        """For PPO updates: compute log-prob and entropy of given actions."""
        logits, value = self.forward(tokens, attention_mask, action_mask, scalars=scalars)
        log_probs = F.log_softmax(logits, dim=-1)
        action_log_prob = log_probs.gather(-1, actions.unsqueeze(-1)).squeeze(-1)
        probs = log_probs.exp()
        entropy = -(probs * log_probs.masked_fill(~action_mask, 0.0)).sum(dim=-1)
        return action_log_prob, entropy, value
