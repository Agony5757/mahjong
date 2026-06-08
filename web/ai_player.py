"""
AI player implementations.
Supports random AI, V4 BC transformer, and legacy VLOGMahjong models.
"""
import numpy as np
import os
from typing import Optional


class BaseAIPlayer:
    """Base class for AI players."""

    def select_action(self, env_wrapper, player_id: int) -> int:
        raise NotImplementedError

    # Hooks called by Game lifecycle. Default implementations do nothing.
    def on_hand_start(self, env_wrapper) -> None:  # noqa: D401
        """Notify the AI that a fresh kyoku has begun."""

    def on_action_executed(self, env_wrapper) -> None:  # noqa: D401
        """Notify the AI that the engine just advanced (post-make_selection)."""


class RandomAI(BaseAIPlayer):
    """Random action selection (baseline)."""

    def select_action(self, env_wrapper, player_id: int) -> int:
        valid = env_wrapper.get_valid_actions(player_id)
        return int(np.random.choice(valid))


class V4ModelAI(BaseAIPlayer):
    """:class:`EventStreamTransformer` BC/PPO checkpoint.

    Maintains a per-session :class:`LiveEncoder` that mirrors the
    underlying ``pm.Table`` so the model always sees the same event
    stream it was trained on. ``on_hand_start`` / ``on_action_executed``
    must be called by the host whenever a kyoku starts or the engine
    advances; see ``web/game_manager.py`` for the integration.
    """

    def __init__(self, model_path: str):
        self.model_path = model_path
        self._model = None
        self._device = None
        self._live = None

    def _ensure_model(self):
        if self._model is not None:
            return
        import torch
        from pymahjong.rl.common.config import TransformerConfig
        from pymahjong.rl.transformer import EventStreamTransformer

        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        ck = torch.load(self.model_path, map_location=self._device, weights_only=False)
        sd = ck.get("model", ck) if isinstance(ck, dict) else ck
        # Auto-detect optional architectural toggles from the checkpoint's
        # state dict so this loader works for both old (no pos_emb) and new
        # (with pos_emb) BC/PPO checkpoints without manual configuration.
        use_pos_emb = "pos_emb.weight" in sd
        self._model = EventStreamTransformer(
            config=TransformerConfig(use_pos_emb=use_pos_emb)
        )
        self._model.load_state_dict(sd)
        self._model.to(self._device)
        self._model.eval()

    def _ensure_live(self, env_wrapper):
        if self._live is None or self._live.table is not env_wrapper.t:
            from pymahjong.rl.live_encoder import LiveEncoder
            self._live = LiveEncoder(env_wrapper.t)
            self._live.start_hand()

    def on_hand_start(self, env_wrapper) -> None:
        from pymahjong.rl.live_encoder import LiveEncoder
        self._live = LiveEncoder(env_wrapper.t)
        self._live.start_hand()

    def on_action_executed(self, env_wrapper) -> None:
        if self._live is not None and self._live.table is env_wrapper.t:
            self._live.sync()

    def select_action(self, env_wrapper, player_id: int) -> int:
        import torch

        self._ensure_model()
        self._ensure_live(env_wrapper)

        obs = self._live.observation_for(player_id)
        import numpy as np
        feat = torch.as_tensor(obs["features"], device=self._device, dtype=torch.float32).unsqueeze(0)
        attn = torch.as_tensor(obs["attention_mask"], device=self._device, dtype=torch.bool).unsqueeze(0)
        mask = torch.as_tensor(obs["action_mask"], device=self._device, dtype=torch.bool).unsqueeze(0)

        with torch.no_grad():
            logits, _ = self._model(feat, attn, mask)
        logits = logits.squeeze(0).cpu().numpy()
        valid_mask = obs["action_mask"]
        logits[~valid_mask] = -1e9
        action = int(np.argmax(logits))

        # Safety check: if the chosen action is somehow not valid (e.g. due
        # to mask differences with engine), fall back to the engine's mask.
        engine_valid = env_wrapper.get_valid_actions_mask(player_id)
        if not engine_valid[action]:
            valid = env_wrapper.get_valid_actions(player_id)
            action = int(np.random.choice(valid))

        return action


class PretrainedModelAI(BaseAIPlayer):
    """Legacy VLOGMahjong DDQN/BC checkpoints (V1 encoding, 93x34 obs)."""

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


def _detect_model_kind(model_path: str) -> str:
    """Return ``"v4"`` or ``"legacy"`` for a checkpoint file.

    V4 ``EventStreamTransformer`` checkpoints contain an ``input_proj.weight``
    in the state dict (the per-event linear projection). Legacy VLOGMahjong
    checkpoints do not.
    """
    try:
        import torch
        ck = torch.load(model_path, map_location="cpu", weights_only=False)
        sd = ck.get("model", ck) if isinstance(ck, dict) else ck
        if isinstance(sd, dict) and any(
            k.endswith("input_proj.weight") or k == "input_proj.weight"
            for k in sd.keys()
        ):
            return "v4"
    except Exception:
        pass
    return "legacy"


def create_ai_player(ai_type: str, model_path: Optional[str] = None) -> BaseAIPlayer:
    """
    Factory for AI players.

    Args:
        ai_type: ``"random"`` or ``"pretrained"``. When ``"pretrained"``
            the checkpoint is autodetected as V4 transformer or legacy
            VLOGMahjong by inspecting the state-dict keys.
        model_path: Path to .pt/.pth model file (required for ``"pretrained"``).
    """
    if ai_type == "random":
        return RandomAI()
    elif ai_type == "pretrained":
        if not model_path:
            raise ValueError("model_path required for pretrained AI")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"model file not found: {model_path}")
        kind = _detect_model_kind(model_path)
        if kind == "v4":
            return V4ModelAI(model_path)
        return PretrainedModelAI(model_path)
    else:
        raise ValueError(f"Unknown AI type: {ai_type}")
