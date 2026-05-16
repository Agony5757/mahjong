"""V2 encoding strategy -- structured self-info + records + global-info tensors."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from ..encoding import EncodingVersion, register


class V2Strategy:
    """Structured per-player tensors: self_info (17x34), records (N x 56),
    global_info (16,) per player.  Uses C++ TableEncoder or PassiveTableEncoder."""

    version = EncodingVersion.V2
    N_SELF_INFO_ROWS = 17
    N_SELF_INFO_COLS = 34
    N_RECORD_FEATURES = 56
    N_GLOBAL_INFO = 16

    # -- Observation -----------------------------------------------------------

    def encode_observation(self, table, current_player: int, **kwargs) -> Dict[str, Any]:
        import MahjongPyWrapper as pm

        encoder = pm.TableEncoder(table)
        encoder.init()
        encoder.update()

        return {
            "self_info": np.array(encoder.self_infos[current_player], dtype=np.int16),
            "records": [np.array(r, dtype=np.int16) for r in encoder.records[current_player]],
            "global_info": np.array(encoder.global_infos[current_player], dtype=np.int16),
            "record_count": encoder.record_count,
            "current_player": current_player,
        }

    def observation_space(self, **kwargs):
        from gymnasium.spaces import Box, Dict as DictSpace, Sequence

        return DictSpace({
            "self_info": Box(
                low=-32768, high=32767,
                shape=[self.N_SELF_INFO_ROWS, self.N_SELF_INFO_COLS],
                dtype=np.int16,
            ),
            "global_info": Box(
                low=-32768, high=32767,
                shape=[self.N_GLOBAL_INFO],
                dtype=np.int16,
            ),
            "record_count": Box(low=0, high=9999, shape=(), dtype=np.int32),
        })

    # -- Model -----------------------------------------------------------------

    def create_model(self, **kwargs) -> Any:
        raise NotImplementedError(
            "V2 has no dedicated NN model; use V3 (Transformer) or V1 (CNN) for training."
        )

    # -- Collation -------------------------------------------------------------

    def collate_fn(self, batch: list) -> Dict[str, Any]:
        import torch

        self_infos = torch.tensor(np.stack([s["self_info"] for s in batch]), dtype=torch.long)
        global_infos = torch.tensor(np.stack([s["global_info"] for s in batch]), dtype=torch.long)
        actions = torch.tensor([s["action"] for s in batch], dtype=torch.long)
        return {
            "self_info": self_infos,
            "global_info": global_infos,
            "action": actions,
        }

    # -- Cache / Dataset factories ---------------------------------------------

    def create_shard_writer(self, shard_dir: str, **kwargs):
        raise NotImplementedError("V2 does not have a dedicated shard writer")

    def create_cached_dataset(self, cache_dir: str, **kwargs):
        raise NotImplementedError("V2 does not have a cached dataset")

    def create_streaming_dataset(self, paths, **kwargs):
        raise NotImplementedError("V2 does not have a streaming dataset")


register(EncodingVersion.V2, V2Strategy())
