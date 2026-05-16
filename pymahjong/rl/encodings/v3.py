"""V3 encoding strategy -- token-based sequence encoding for transformers."""

from __future__ import annotations

import os
import glob as _glob
from typing import Any, Dict

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
        from ..v3.tokenization import MahjongTokenizer

        riichi_stage2 = kwargs.get("riichi_stage2", False)
        include_oracle = kwargs.get("include_oracle", self.include_oracle)
        tok = MahjongTokenizer(
            max_seq_len=self.max_seq_len, include_oracle=include_oracle
        )
        obs = tok.encode(table, current_player, riichi_stage2=riichi_stage2)
        return obs.to_dict()

    def observation_space(self, **kwargs):
        from ..v3.observation import _build_observation_space

        max_seq_len = kwargs.get("max_seq_len", self.max_seq_len)
        return _build_observation_space(max_seq_len)

    # -- Model -----------------------------------------------------------------

    def create_model(self, **kwargs) -> Any:
        from ..common.config import TransformerConfig
        from ..v3.model import MahjongTransformer

        cfg = kwargs.get("transformer_config") or TransformerConfig()
        return MahjongTransformer(config=cfg)

    # -- Collation -------------------------------------------------------------

    def collate_fn(self, batch: list) -> Dict[str, Any]:
        from ..v3.collate import streaming_collate

        return streaming_collate(batch)

    # -- Cache / Dataset factories ---------------------------------------------

    def create_shard_writer(self, shard_dir: str, **kwargs):
        from ..v3.cache import ShardWriter

        return ShardWriter(shard_dir)

    def create_cached_dataset(self, cache_dir: str, **kwargs):
        from ..v3.cached_dataset import CachedTokenDataset

        return CachedTokenDataset(
            cache_dir,
            max_seq_len=kwargs.get("max_seq_len", self.max_seq_len),
            suit_permute=kwargs.get("suit_permute", False),
        )

    def create_streaming_dataset(self, paths, **kwargs):
        from ..v3.streaming_dataset import StreamingPaipuDataset

        return StreamingPaipuDataset(
            paipu_paths=paths,
            oracle=kwargs.get("oracle", False),
            max_seq_len=kwargs.get("max_seq_len", self.max_seq_len),
            suit_permute=kwargs.get("suit_permute", False),
        )

    # -- Training integration --------------------------------------------------

    def create_dataset(self, mode: str, config=None, **kwargs):
        """Create a training dataset for V3.

        Args:
            mode: ``"cached"``, ``"streaming"``, or ``"selfplay"``.
            config: ``BCConfig`` (or compatible) with ``cache_dir``,
                ``paipu_dir``, ``suit_permute``, etc.
        """
        if mode == "cached":
            from ..v3.cached_dataset import CachedTokenDataset
            return CachedTokenDataset(
                config.cache_dir,
                suit_permute=getattr(config, "suit_permute", False),
            )
        elif mode == "streaming":
            from ..v3.streaming_dataset import StreamingPaipuDataset
            paipu_dir = getattr(config, "paipu_dir", None)
            if not paipu_dir:
                from pymahjong.config import get_config
                paipu_dir = get_config().paipu_xml_path
            paths = sorted(
                p for p in _glob.glob(os.path.join(paipu_dir, "**", "*"), recursive=True)
                if os.path.isfile(p) and (p.endswith(".xml") or p.endswith(".txt"))
            )
            return StreamingPaipuDataset(
                paipu_paths=paths,
                prefetch_n=getattr(config, "paipu_prefetch", 4),
                suit_permute=getattr(config, "suit_permute", False),
            )
        elif mode == "selfplay":
            from ..v3.dataset import SelfPlayImitationDataset
            return SelfPlayImitationDataset(oracle=False)
        else:
            raise ValueError(f"Unknown dataset mode: {mode!r}")

    def obs_to_tensor(self, obs: dict, device):
        """Convert a single V3 observation dict to model-ready tensors."""
        import torch
        return (
            torch.as_tensor(obs["tokens"], device=device, dtype=torch.long).unsqueeze(0),
            torch.as_tensor(obs["attention_mask"], device=device, dtype=torch.bool).unsqueeze(0),
            torch.as_tensor(obs["action_mask"], device=device, dtype=torch.bool).unsqueeze(0),
        )

    def forward_from_batch(self, model, batch: dict):
        """Dispatch a V3 batch through the model → (logits, value)."""
        return model(
            batch["tokens"],
            batch["attention_mask"],
            batch["action_mask"],
            scalars=batch.get("scalars"),
        )

    def evaluate_actions_from_batch(self, model, batch: dict, actions):
        """Dispatch a V3 batch through model.evaluate_actions."""
        return model.evaluate_actions(
            batch["tokens"],
            batch["attention_mask"],
            batch["action_mask"],
            actions,
            scalars=batch.get("scalars"),
        )


register(EncodingVersion.V3, V3Strategy())
