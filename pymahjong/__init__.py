"""pymahjong: A Japanese Riichi Mahjong environment for decision AI research.

Submodules:

- ``env_pymahjong``: Gymnasium-compatible multi-agent and single-agent environments.
- ``models``: Pretrained VLOG-Mahjong RL model architecture.
- ``base_modules``: Neural network module definitions.
- ``tenhou_paipu_check``: Tenhou XML paipu validation and replay utilities.
- ``paipu_recorder``: Generate Tenhou-style XML paipu from running games.
"""

from __future__ import annotations

# Environments
from pymahjong.env_pymahjong import MahjongEnv, SingleAgentMahjongEnv

# C++ core (enums + classes — imported from the MahjongPyWrapper extension)
from MahjongPyWrapper import (  # noqa: F401, F403
    BaseTile,
    Wind,
    BaseAction,
    PhaseEnum,
    ResultType,
    Yaku,
    CallGroup,
    Tile,
    River,
    RiverTile,
    SelfAction,
    ResponseAction,
    Player,
    Table,
    Result,
    CounterResult,
    PaipuReplayer,
    TenhouShuffle,
    TableEncoder,
    PassiveTableEncoder,
    encv1_encode_table,
    encv1_encode_table_riichi_step2,
    encv1_encode_action,
    encv1_encode_action_riichi_step2,
    encv1_get_riichi_tiles,
    is_ordinary_agari,
    normal_round_to_win,
    get_self_action_index,
    get_response_action_index,
)

# RL models (lazy-loaded, torch is an optional dependency)
def __getattr__(name):
    if name == "VLOGMahjong":
        from pymahjong.models import VLOGMahjong
        return VLOGMahjong
    if name in ("MinusOneModule", "MahjongNet", "DiscreteActionQNetwork", "DiscreteActionPolicyNetwork"):
        from pymahjong import base_modules
        return getattr(base_modules, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

# Utilities
from pymahjong.tenhou_paipu_check import paipu_replay, paipu_replay_summary
from pymahjong.paipu_recorder import (
    TenhouPaipuRecorder,
    replay_recorded_paipu,
)
from pymahjong.paipu_tenhou_json import (
    xml_to_tenhou_json,
    xml_string_to_tenhou_json,
    make_editor_url,
    make_per_hand_urls,
    save_tenhou_json,
)

__all__ = [
    # Environments
    "MahjongEnv",
    "SingleAgentMahjongEnv",
    # C++ enums
    "BaseTile",
    "Wind",
    "BaseAction",
    "PhaseEnum",
    "ResultType",
    "Yaku",
    # C++ classes
    "CallGroup",
    "Tile",
    "River",
    "RiverTile",
    "SelfAction",
    "ResponseAction",
    "Player",
    "Table",
    "Result",
    "CounterResult",
    "PaipuReplayer",
    "TenhouShuffle",
    "TableEncoder",
    "PassiveTableEncoder",
    # Encoding functions
    "encv1_encode_table",
    "encv1_encode_table_riichi_step2",
    "encv1_encode_action",
    "encv1_encode_action_riichi_step2",
    "encv1_get_riichi_tiles",
    "is_ordinary_agari",
    "normal_round_to_win",
    "get_self_action_index",
    "get_response_action_index",
    # RL models
    "VLOGMahjong",
    "MinusOneModule",
    "MahjongNet",
    "DiscreteActionQNetwork",
    "DiscreteActionPolicyNetwork",
    # Utilities
    "paipu_replay",
    "paipu_replay_summary",
    "TenhouPaipuRecorder",
    "replay_recorded_paipu",
    "xml_to_tenhou_json",
    "xml_string_to_tenhou_json",
    "make_editor_url",
    "make_per_hand_urls",
    "save_tenhou_json",
]

# Version from build-time (set by setuptools-scm)
try:
    from pymahjong._version import version as __version__
except ImportError:
    __version__ = "0.0.0"
