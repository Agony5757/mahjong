"""Round-trip tests for :mod:`pymahjong.paipu_recorder`.

These tests run the engine through random self-play, record the result
as a Tenhou-style paipu, replay it via the seed-based replayer, and
verify the final scores match for every hand.
"""
from __future__ import annotations

import os
import random
import tempfile

import numpy as np
import pytest

pm = pytest.importorskip("MahjongPyWrapper")

from pymahjong.env_pymahjong import MahjongEnv
from pymahjong.paipu_recorder import (
    TenhouPaipuRecorder,
    replay_recorded_paipu,
)


def _random_selfplay_record(n_hands: int, base_seed: int, *, max_steps: int = 1000):
    """Run ``n_hands`` random self-play hands, record each, return recorder."""
    recorder = TenhouPaipuRecorder()
    env = MahjongEnv()
    rng = random.Random(base_seed)
    n_recorded = 0
    for i in range(n_hands):
        seed = base_seed + i
        env.reset(seed=seed)
        steps = 0
        while not env.is_over() and steps < max_steps:
            pid = env.get_curr_player_id()
            valid = np.flatnonzero(env.get_valid_actions(nhot=True))
            if len(valid) == 0:
                break
            env.step(pid, int(rng.choice(valid.tolist())))
            steps += 1
        if int(env.t.get_phase()) == int(pm.PhaseEnum.GAME_OVER):
            recorder.record_hand(env.t, seed=seed)
            n_recorded += 1
    return recorder, n_recorded


def test_record_and_replay_random_selfplay(tmp_path):
    """20 random-play hands → recorded → replayed → all scores match."""
    recorder, n = _random_selfplay_record(20, base_seed=4000)
    assert n >= 18, f"expected most hands to finish, got {n}/20"
    out = tmp_path / "selfplay.xml"
    recorder.save(str(out))
    assert out.exists() and out.stat().st_size > 0

    n_ok, n_fail = replay_recorded_paipu(str(out), verbose=False)
    assert n_fail == 0, f"replay validation failed: ok={n_ok} fail={n_fail}"
    assert n_ok == n


def test_record_minimum_metadata(tmp_path):
    """A recorded paipu must contain the canonical envelope elements."""
    recorder, _ = _random_selfplay_record(2, base_seed=7000)
    xml = recorder.to_string()
    assert "<mjloggm" in xml
    assert "<GO" in xml
    assert "<UN" in xml
    assert "<TAIKYOKU" in xml
    assert "<INIT" in xml
    assert 'seed_int="' in xml  # custom deterministic-replay attribute
    # Round-trip parse to make sure it's well-formed XML.
    import xml.etree.ElementTree as ET
    root = ET.fromstring(xml)
    assert root.tag == "mjloggm"


def test_n_hands_count(tmp_path):
    recorder, n = _random_selfplay_record(3, base_seed=3000)
    assert recorder.n_hands == n
