"""V3 encoding strategy -- token-based sequence encoding for transformers."""

from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from ..encoding import EncodingVersion, register


class V3Strategy:
    """Token-based (segment, tile, count, who, extra) encoding for V3."""

    version = EncodingVersion.V3

    def __init__(self, max_seq_len: int = 360, include_oracle: bool = False):
        self.max_seq_len = max_seq_len
        self.include_oracle = include_oracle

    # -- Observation -----------------------------------------------------------

    def encode_observation(self, table, current_player: int, **kwargs) -> Dict[str, Any]:
        from ..tokenization import MahjongTokenizer

        riichi_stage2 = kwargs.get("riichi_stage2", False)
        include_oracle = kwargs.get("include_oracle", self.include_oracle)
        tok = MahjongTokenizer(
            max_seq_len=self.max_seq_len, include_oracle=include_oracle
        )
        obs = tok.encode(table, current_player, riichi_stage2=riichi_stage2)
        return obs.to_dict()

    def observation_space(self, **kwargs):
        from ..env_v2 import _build_observation_space

        max_seq_len = kwargs.get("max_seq_len", self.max_seq_len)
        return _build_observation_space(max_seq_len)

    # -- Model -----------------------------------------------------------------

    def create_model(self, **kwargs) -> Any:
        from ..model import MahjongTransformer, TransformerConfig

        cfg = kwargs.get("transformer_config") or TransformerConfig()
        return MahjongTransformer(config=cfg)

    # -- Collation -------------------------------------------------------------

    def collate_fn(self, batch: list) -> Dict[str, Any]:
        from ..streaming_dataset import streaming_collate

        return streaming_collate(batch)

    # -- Cache / Dataset factories ---------------------------------------------

    def create_shard_writer(self, shard_dir: str, **kwargs):
        from ..cache import ShardWriter

        return ShardWriter(shard_dir)

    def create_cached_dataset(self, cache_dir: str, **kwargs):
        from ..cached_dataset import CachedTokenDataset

        return CachedTokenDataset(
            cache_dir,
            max_seq_len=kwargs.get("max_seq_len", self.max_seq_len),
            suit_permute=kwargs.get("suit_permute", False),
        )

    def create_streaming_dataset(self, paths, **kwargs):
        from ..streaming_dataset import StreamingPaipuDataset

        return StreamingPaipuDataset(
            paipu_paths=paths,
            oracle=kwargs.get("oracle", False),
            max_seq_len=kwargs.get("max_seq_len", self.max_seq_len),
            suit_permute=kwargs.get("suit_permute", False),
        )


register(EncodingVersion.V3, V3Strategy())
