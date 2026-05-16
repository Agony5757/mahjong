"""V1 encoding strategy -- dense 2D boolean matrix (legacy CNN-compatible)."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np

from ..encoding import EncodingVersion, register


class V1Strategy:
    """Dense 111x34 int8 matrix encoding for V1 (VLOG-style CNN models)."""

    version = EncodingVersion.V1
    PLAYER_OBS_DIM = 93
    ORACLE_OBS_DIM = 18
    MAHJONG_TILE_TYPES = 34

    def __init__(self):
        self._obs_buf = None  # lazily allocated

    def _ensure_buf(self):
        if self._obs_buf is None:
            import MahjongPyWrapper as pm
            self._obs_buf = np.zeros(
                [self.PLAYER_OBS_DIM + self.ORACLE_OBS_DIM, self.MAHJONG_TILE_TYPES],
                dtype=np.int8,
            )

    # -- Observation -----------------------------------------------------------

    def encode_observation(self, table, current_player: int, **kwargs) -> Dict[str, Any]:
        import MahjongPyWrapper as pm

        self._ensure_buf()
        use_oracle = kwargs.get("use_oracle", True)
        riichi_stage2 = kwargs.get("riichi_stage2", False)
        riichi_tile_id = kwargs.get("riichi_tile_id")

        self._obs_buf.fill(0)
        pm.encv1_encode_table(table, current_player, use_oracle, self._obs_buf)
        if riichi_stage2 and riichi_tile_id is not None:
            pm.encv1_encode_table_riichi_step2(table, riichi_tile_id, self._obs_buf)

        return {
            "observation": self._obs_buf[:self.PLAYER_OBS_DIM].astype(bool).copy(),
            "oracle": self._obs_buf[-self.ORACLE_OBS_DIM:].astype(bool).copy(),
        }

    def observation_space(self, **kwargs):
        from gymnasium.spaces import Box, Dict as DictSpace

        return DictSpace({
            "observation": Box(
                dtype=bool, low=0, high=1,
                shape=[self.PLAYER_OBS_DIM, self.MAHJONG_TILE_TYPES],
            ),
            "oracle": Box(
                dtype=bool, low=0, high=1,
                shape=[self.ORACLE_OBS_DIM, self.MAHJONG_TILE_TYPES],
            ),
        })

    # -- Model -----------------------------------------------------------------

    def create_model(self, **kwargs) -> Any:
        from pymahjong.models import VLOGMahjong

        algorithm = kwargs.get("algorithm", "bc")
        return VLOGMahjong(algorithm=algorithm, **{
            k: v for k, v in kwargs.items() if k != "algorithm"
        })

    # -- Collation -------------------------------------------------------------

    def collate_fn(self, batch: list) -> Dict[str, Any]:
        import torch

        obs = torch.tensor(np.stack([s["observation"] for s in batch]), dtype=torch.bool)
        masks = torch.tensor(np.stack([s.get("action_mask", np.zeros(54, dtype=bool)) for s in batch]))
        actions = torch.tensor([s["action"] for s in batch], dtype=torch.long)
        return {"observation": obs, "action_mask": masks, "action": actions}

    # -- Cache / Dataset factories ---------------------------------------------

    def create_shard_writer(self, shard_dir: str, **kwargs):
        raise NotImplementedError("V1 does not have a dedicated shard writer")

    def create_cached_dataset(self, cache_dir: str, **kwargs):
        raise NotImplementedError("V1 does not have a cached dataset")

    def create_streaming_dataset(self, paths, **kwargs):
        raise NotImplementedError("V1 does not have a streaming dataset")


register(EncodingVersion.V1, V1Strategy())
