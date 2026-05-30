"""Shared configuration classes for transformer models."""

from __future__ import annotations

from dataclasses import dataclass

# Default max sequence length, defined here to avoid circular imports
# with v3/tokenization.py.  Must match tokenization.MAX_SEQ_LEN.
DEFAULT_MAX_SEQ_LEN = 360


@dataclass
class TransformerConfig:
    d_model: int = 192
    n_heads: int = 6
    n_layers: int = 4
    ff_mult: int = 4
    dropout: float = 0.1
    use_cls: bool = True
    max_seq_len: int = DEFAULT_MAX_SEQ_LEN
    # V4-only: add a learned positional embedding before the transformer
    # encoder so the model is no longer permutation-invariant over events.
    # Defaults to ``False`` for backward compatibility with existing V4
    # checkpoints (e.g. ``bc_v4.best.pt``).  When enabled, the table is
    # zero-initialised so a warm-start from a no-pos-emb checkpoint
    # initially reproduces the old forward exactly.
    use_pos_emb: bool = False
