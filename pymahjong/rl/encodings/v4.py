"""V4 encoding strategy -- autoregressive event-stream bitset encoding."""

from __future__ import annotations

import os
import glob as _glob
from typing import Any, Dict

import numpy as np

from ..encoding import EncodingVersion, register


class V4Strategy:
    """Event-stream encoding (100-dim bitset per event) for V4."""

    version = EncodingVersion.V4
    EVENT_DIM = 100
    MAX_SEQ_LEN = 512

    # -- Observation -----------------------------------------------------------

    def encode_observation(self, table, current_player: int, **kwargs) -> Dict[str, Any]:
        from ..v4.tokenization import _engine_action_mask

        mask = _engine_action_mask(table, current_player)
        return {
            "features": np.zeros((self.MAX_SEQ_LEN, self.EVENT_DIM), dtype=np.float32),
            "attention_mask": np.zeros((self.MAX_SEQ_LEN,), dtype=bool),
            "action_mask": mask.astype(bool),
        }

    def observation_space(self, **kwargs):
        from gymnasium.spaces import Box, Dict as DictSpace

        max_len = kwargs.get("max_seq_len", self.MAX_SEQ_LEN)
        return DictSpace({
            "features": Box(
                low=0.0, high=1.0,
                shape=(max_len, self.EVENT_DIM),
                dtype=np.float32,
            ),
            "attention_mask": Box(low=0, high=1, shape=(max_len,), dtype=bool),
            "action_mask": Box(low=0, high=1, shape=(54,), dtype=bool),
        })

    # -- Model -----------------------------------------------------------------

    def create_model(self, **kwargs) -> Any:
        from ..common.config import TransformerConfig
        from ..v4.model import EventStreamTransformer

        cfg = kwargs.get("transformer_config") or TransformerConfig()
        split_heads = bool(kwargs.get("split_heads", False))
        return EventStreamTransformer(
            config=cfg, event_dim=self.EVENT_DIM, split_heads=split_heads,
        )

    # -- Collation -------------------------------------------------------------

    def collate_fn(self, batch: list) -> Dict[str, Any]:
        from ..v4.cached_dataset import cached_event_collate

        return cached_event_collate(batch)

    # -- Cache / Dataset factories ---------------------------------------------

    def create_shard_writer(self, shard_dir: str, **kwargs):
        from ..v4.cache import V4ShardWriter

        return V4ShardWriter(shard_dir)

    def create_cached_dataset(self, cache_dir: str, **kwargs):
        from ..v4.cached_dataset import CachedEventDataset

        return CachedEventDataset(cache_dir, **kwargs)

    def create_streaming_dataset(self, paths, **kwargs):
        from ..v4.tokenization import StreamingPaipuDatasetV4

        return StreamingPaipuDatasetV4(paipu_paths=paths, **kwargs)

    # -- Training integration --------------------------------------------------

    def create_dataset(self, mode: str, config=None, **kwargs):
        """Create a training dataset for V4.

        Args:
            mode: ``"cached"`` or ``"streaming"``.
            config: ``BCConfig`` (or compatible) with ``cache_dir``,
                ``paipu_dir``, etc.
        """
        if mode == "cached":
            from ..v4.cached_dataset import CachedEventDataset
            return CachedEventDataset(config.cache_dir)
        elif mode == "streaming":
            from ..v4.tokenization import StreamingPaipuDatasetV4
            paipu_dir = getattr(config, "paipu_dir", None)
            if not paipu_dir:
                from pymahjong.config import get_config
                paipu_dir = get_config().paipu_xml_path
            paths = sorted(
                p for p in _glob.glob(os.path.join(paipu_dir, "**", "*"), recursive=True)
                if os.path.isfile(p) and (p.endswith(".xml") or p.endswith(".txt"))
            )
            return StreamingPaipuDatasetV4(
                paipu_paths=paths,
                prefetch_n=getattr(config, "paipu_prefetch", 4),
            )
        else:
            raise ValueError(f"V4 does not support dataset mode: {mode!r}")

    def obs_to_tensor(self, obs: dict, device):
        """Convert a single V4 observation dict to model-ready tensors."""
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
        """Dispatch a V4 batch through the model → (logits, value)."""
        return model(
            batch["features"],
            batch["attention_mask"],
            batch["action_mask"],
        )

    def forward_from_batch_raw(self, model, batch: dict):
        """Return *un-masked* logits + value + the action mask."""
        raw_logits, value = model(
            batch["features"],
            batch["attention_mask"],
            None,
        )
        return raw_logits, value, batch["action_mask"]

    def evaluate_actions_from_batch(self, model, batch: dict, actions):
        """Dispatch a V4 batch through model.evaluate_actions."""
        return model.evaluate_actions(
            batch["features"],
            batch["attention_mask"],
            batch["action_mask"],
            actions,
        )


register(EncodingVersion.V4, V4Strategy())
