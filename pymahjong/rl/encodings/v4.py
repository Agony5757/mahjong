"""V4 encoding strategy -- autoregressive event-stream bitset encoding."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from ..encoding import EncodingVersion, register


class V4Strategy:
    """Event-stream encoding (100-dim bitset per event) for V4."""

    version = EncodingVersion.V4
    EVENT_DIM = 100
    MAX_SEQ_LEN = 512

    # -- Observation -----------------------------------------------------------

    def encode_observation(self, table, current_player: int, **kwargs) -> Dict[str, Any]:
        # V4 encoding is event-driven; a single-table snapshot requires
        # replaying the game log.  Use StreamingPaipuDatasetV4 for data
        # generation.  For online env use, we produce a padded mask from
        # the current table state.
        from ..tokenization_v4 import _engine_action_mask

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
        from ..model_v4 import EventStreamTransformer

        from ..model import TransformerConfig

        cfg = kwargs.get("transformer_config") or TransformerConfig()
        return EventStreamTransformer(config=cfg, event_dim=self.EVENT_DIM)

    # -- Collation -------------------------------------------------------------

    def collate_fn(self, batch: list) -> Dict[str, Any]:
        from ..cached_dataset_v4 import cached_event_collate

        return cached_event_collate(batch)

    # -- Cache / Dataset factories ---------------------------------------------

    def create_shard_writer(self, shard_dir: str, **kwargs):
        from ..cache_v4 import V4ShardWriter

        return V4ShardWriter(shard_dir)

    def create_cached_dataset(self, cache_dir: str, **kwargs):
        from ..cached_dataset_v4 import CachedEventDataset

        return CachedEventDataset(cache_dir, **kwargs)

    def create_streaming_dataset(self, paths, **kwargs):
        from ..tokenization_v4 import StreamingPaipuDatasetV4

        return StreamingPaipuDatasetV4(paipu_paths=paths, **kwargs)


register(EncodingVersion.V4, V4Strategy())
