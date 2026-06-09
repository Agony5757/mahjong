"""Deprecated module: the Mortal Q-network moved to :mod:`mortal_qnet`.

The earlier prototype exposed ``MortalV5``, a wrapper around
:class:`~pymahjong.rl.v5.model.DouzeroV5Transformer` that reinterpreted
the V5 scorer as a *dueling* advantage (``Q = V + A - mean A``).

Per the approved redesign, the Q network is now an unmodified
:class:`~pymahjong.rl.v4.model.EventStreamTransformer` encoder plus a
standalone :class:`~pymahjong.rl.v5.mortal_qnet.DouzeroQHead` whose shared
scorer **outputs ``Q(s, a)`` directly** (no dueling).  ``MortalV5`` is kept
here as a thin backwards-compatible alias of
:class:`~pymahjong.rl.v5.mortal_qnet.MortalQNet`; new code should import
``MortalQNet`` directly.
"""

from __future__ import annotations

from .mortal_qnet import DouzeroQHead, MortalQNet

# Backwards-compatible alias.
MortalV5 = MortalQNet

__all__ = ["MortalQNet", "DouzeroQHead", "MortalV5"]
