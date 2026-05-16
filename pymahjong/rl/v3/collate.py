"""V3 collation functions for batching observations."""

from __future__ import annotations

from typing import Dict, List

import numpy as np
import torch


def streaming_collate(batch: List[Dict]) -> Dict[str, torch.Tensor]:
    """Stack a list of sample dicts into a batched tensor dict.

    Handles numpy arrays from ``StreamingPaipuDataset`` (which yields numpy,
    not torch tensors).
    """
    return {
        "tokens": torch.as_tensor(
            np.stack([b["tokens"] for b in batch]), dtype=torch.long
        ),
        "scalars": torch.as_tensor(
            np.stack([b["scalars"] for b in batch]), dtype=torch.float32
        ),
        "attention_mask": torch.as_tensor(
            np.stack([b["attention_mask"] for b in batch]), dtype=torch.bool
        ),
        "action_mask": torch.as_tensor(
            np.stack([b["action_mask"] for b in batch]), dtype=torch.bool
        ),
        "action": torch.as_tensor(
            np.stack([b["action"] for b in batch]), dtype=torch.long
        ),
    }


def cached_collate(batch):
    """Stack a list of dicts (already torch tensors) into a batched dict."""
    return {
        "tokens": torch.stack([b["tokens"] for b in batch], dim=0),
        "scalars": torch.stack([b["scalars"] for b in batch], dim=0),
        "attention_mask": torch.stack([b["attention_mask"] for b in batch], dim=0),
        "action_mask": torch.stack([b["action_mask"] for b in batch], dim=0),
        "action": torch.stack([b["action"] for b in batch], dim=0),
    }


def ppo_obs_collate(batch):
    """Collate V3 observation dicts (numpy arrays) into batched tensors."""
    return {
        "tokens": torch.as_tensor(np.stack([b["tokens"] for b in batch]), dtype=torch.long),
        "attention_mask": torch.as_tensor(
            np.stack([b["attention_mask"] for b in batch]), dtype=torch.bool
        ),
        "action_mask": torch.as_tensor(
            np.stack([b["action_mask"] for b in batch]), dtype=torch.bool
        ),
    }
