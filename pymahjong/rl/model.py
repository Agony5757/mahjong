"""Backward compatibility shim. Import from pymahjong.rl.v3.model instead."""

from .v3.model import *  # noqa: F401,F403
from .v3.model import MahjongTransformer, FieldEmbedding  # noqa: F401
from .common.config import TransformerConfig  # noqa: F401
