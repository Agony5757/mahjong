"""
AI player implementations.
Supports random AI and pretrained VLOGMahjong model.
"""
import numpy as np
from typing import Optional


class BaseAIPlayer:
    """Base class for AI players."""

    def select_action(self, env_wrapper, player_id: int) -> int:
        raise NotImplementedError


class RandomAI(BaseAIPlayer):
    """Random action selection (baseline)."""

    def select_action(self, env_wrapper, player_id: int) -> int:
        valid = env_wrapper.get_valid_actions(player_id)
        return int(np.random.choice(valid))


class PretrainedModelAI(BaseAIPlayer):
    """
    Pretrained VLOGMahjong model as AI opponent.
    Supports DDQN and BC models from pymahjong/models.py.
    """

    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None
        self._device = None

    def _load_model(self):
        if self._model is not None:
            return
        try:
            import torch
            from pymahjong.models import VLOGMahjong

            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self._model = VLOGMahjong(
                algo="ddqn",  # or "bc"
                model="vlog-oracle",
                load_path=self.model_path
            )
            self._model.to(self._device)
            self._model.eval()
        except Exception as e:
            raise RuntimeError(f"Failed to load model from {self.model_path}: {e}")

    def select_action(self, env_wrapper, player_id: int) -> int:
        """Select action using the pretrained model."""
        if self._model is None:
            self._load_model()

        import torch
        from pymahjong.models import VLOGMahjong

        valid_mask = env_wrapper.get_valid_actions_mask(player_id)
        obs = env_wrapper._env.get_obs(player_id)  # 93x34

        with torch.no_grad():
            q_values = self._model(torch.tensor(obs, dtype=torch.float32).unsqueeze(0).to(self._device))
            q_values = q_values.squeeze(0).cpu().numpy()

        # Mask invalid actions with -inf
        q_values[~valid_mask] = -1e9
        action = int(np.argmax(q_values))

        # Safety check
        if not valid_mask[action]:
            valid = env_wrapper.get_valid_actions(player_id)
            action = int(np.random.choice(valid))

        return action


def create_ai_player(ai_type: str, model_path: Optional[str] = None) -> BaseAIPlayer:
    """
    Factory for AI players.

    Args:
        ai_type: "random" or "pretrained"
        model_path: Path to .pth model file (required for "pretrained")
    """
    if ai_type == "random":
        return RandomAI()
    elif ai_type == "pretrained":
        if not model_path:
            raise ValueError("model_path required for pretrained AI")
        return PretrainedModelAI(model_path)
    else:
        raise ValueError(f"Unknown AI type: {ai_type}")
