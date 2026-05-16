"""Encoding strategy protocol and registry.

Defines the :class:`EncodingStrategy` protocol that every encoding version
(V1, V2, V3, V4) must implement, plus a simple registry so consumers can
look up strategies by :class:`EncodingVersion` at runtime.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Protocol, Type, runtime_checkable


class EncodingVersion(Enum):
    """Supported encoding versions."""

    V1 = "v1"
    V2 = "v2"
    V3 = "v3"
    V4 = "v4"


@runtime_checkable
class EncodingStrategy(Protocol):
    """Interface that every encoding strategy must satisfy.

    Strategies are thin adapters that wire existing encoding/tokenizer/model
    classes into a uniform interface so envs, training scripts, and caches
    can be encoding-agnostic.
    """

    @property
    def version(self) -> EncodingVersion:
        """Which encoding version this strategy implements."""
        ...

    # -- Observation -----------------------------------------------------------

    def encode_observation(self, table, current_player: int, **kwargs) -> Dict[str, Any]:
        """Encode a ``pm.Table`` snapshot into the strategy's obs format.

        Returns a dict whose keys match ``observation_space()``.
        """
        ...

    def observation_space(self, **kwargs) -> Any:
        """Return a ``gymnasium.spaces.Space`` for this encoding."""
        ...

    # -- Model -----------------------------------------------------------------

    def create_model(self, **kwargs) -> Any:
        """Instantiate the NN model suited for this encoding.

        Accepts ``transformer_config=...`` or other model-specific kwargs.
        """
        ...

    # -- Collation -------------------------------------------------------------

    def collate_fn(self, batch: list) -> Dict[str, Any]:
        """Collate a list of observation dicts into a batched dict of tensors."""
        ...

    # -- Cache / Dataset factories ---------------------------------------------

    def create_shard_writer(self, shard_dir: str, **kwargs) -> Any:
        """Return a shard writer for on-disk caching."""
        ...

    def create_cached_dataset(self, cache_dir: str, **kwargs) -> Any:
        """Return a map-style ``Dataset`` backed by on-disk shards."""
        ...

    def create_streaming_dataset(self, paths, **kwargs) -> Any:
        """Return an ``IterableDataset`` that streams from paipu files."""
        ...

    # -- Training integration --------------------------------------------------

    def create_dataset(self, mode: str, config: Any = None, **kwargs) -> Any:
        """Create a training dataset.

        Args:
            mode: one of ``"cached"``, ``"streaming"``, or ``"selfplay"``.
            config: a ``BCConfig`` or similar dataclass with ``cache_dir``,
                ``paipu_dir``, ``suit_permute``, etc.
        """
        ...

    def obs_to_tensor(self, obs: Dict[str, Any], device) -> tuple:
        """Convert a single observation dict to model-ready tensors.

        Returns ``(features, attention_mask, action_mask)``.
        """
        ...

    def forward_from_batch(self, model, batch: Dict[str, Any]) -> tuple:
        """Dispatch *batch* through *model* → ``(logits, value)``."""
        ...

    def evaluate_actions_from_batch(
        self, model, batch: Dict[str, Any], actions
    ) -> tuple:
        """Dispatch *batch* through ``model.evaluate_actions`` → ``(log_prob, entropy, value)``."""
        ...


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_REGISTRY: Dict[EncodingVersion, EncodingStrategy] = {}


def register(version: EncodingVersion, strategy: EncodingStrategy) -> None:
    """Register a strategy instance for *version*."""
    _REGISTRY[version] = strategy


def get_strategy(version: EncodingVersion) -> EncodingStrategy:
    """Return the registered strategy for *version*.

    Raises ``KeyError`` if the version has not been registered.
    """
    if version not in _REGISTRY:
        raise KeyError(
            f"Encoding {version!r} is not registered. "
            f"Available: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[version]


def available_versions():
    """Return a list of registered encoding versions."""
    return list(_REGISTRY.keys())
