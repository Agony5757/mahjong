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


def test_agari_score_changes_match_engine(tmp_path):
    """Recorded ``<AGARI sc=...>`` deltas must reflect the engine's
    post-payout per-hand scores (``result.score``), not the pre-payout
    snapshot from ``table.get_scores()`` which only tracks
    ``players[i].score`` (= initial − riichi stick).

    Regression for the bug that produced empty / wrong score deltas
    (e.g. ``sc="...,0,...,0,...,0,...,0"`` for a 7700-point ron) and
    made the resulting Tenhou-editor URLs unrenderable.
    """
    import xml.etree.ElementTree as ET

    # Synthesize an agari by replaying a deterministic seed that lands
    # in an AGARI under the engine's default dealing.  We probe a small
    # range of seeds and take the first that wins; random uniform play
    # alone almost never produces agari (≈3% per hand) so we use a
    # greedy heuristic: never call chi/pon/kan/riichi, always tsumo / ron
    # / discard the rightmost tile.  This still relies on the dealt
    # tiles but converges to AGARI much faster than uniform random.
    def _greedy_to_agari(env, base_seed: int, *, n_tries: int = 200) -> int:
        for off in range(n_tries):
            seed = base_seed + off
            env.reset(seed=seed)
            steps = 0
            while not env.is_over() and steps < 500:
                pid = env.get_curr_player_id()
                valid = np.flatnonzero(env.get_valid_actions(nhot=True))
                if len(valid) == 0:
                    break
                # Action layout (see env_pymahjong.py): 0-33 discard,
                # 34 riichi, 35 chi(L)..37 chi(R), 38 pon, 39 ankan,
                # 40 minkan, 41 kakan, 42 tsumo, 43 ron, 44 push, 45 pass.
                # Prefer tsumo > ron > pass > smallest discard > anything.
                pref = []
                if 42 in valid:
                    pref.append(42)
                elif 43 in valid:
                    pref.append(43)
                else:
                    discards = [a for a in valid.tolist() if a < 34]
                    if discards:
                        pref.append(min(discards))
                    elif 45 in valid:
                        pref.append(45)
                    else:
                        pref.append(int(valid[0]))
                env.step(pid, pref[0])
                steps += 1
            if int(env.t.get_phase()) == int(pm.PhaseEnum.GAME_OVER):
                res = env.t.gamelog.result
                if int(res.result_type) in (
                    int(pm.ResultType.RonAgari),
                    int(pm.ResultType.TsumoAgari),
                ):
                    return seed
        return -1

    env = MahjongEnv()
    seed = _greedy_to_agari(env, 4200)
    assert seed >= 0, "could not synthesize an AGARI hand in 200 tries"

    rec = TenhouPaipuRecorder()
    rec.record_hand(env.t, seed=seed)
    root = ET.fromstring(rec.to_string())
    agari = root.find("AGARI")
    assert agari is not None, "expected an AGARI element"

    sc = [int(x) for x in agari.get("sc").split(",")]
    deltas = sc[1::2]
    # Chip conservation: deltas must sum to zero.
    assert sum(deltas) == 0, f"AGARI sc deltas don't sum to zero: {deltas}"

    # The winner's recorded delta must be > 0 for any non-zero-point
    # agari (no triple-overlap edge case here since we only kept one).
    ten = agari.get("ten")
    pts = int(ten.split(",")[1])
    who = int(agari.get("who"))
    assert pts > 0, f"unexpected zero-point agari (ten={ten})"
    assert deltas[who] > 0, (
        f"winner {who} has non-positive delta {deltas[who]} for "
        f"an agari worth {pts} points (sc={sc})"
    )

    # Replay must validate against the recorded paipu now that both
    # recorder and validator agree on ``result.score`` as ground truth.
    out = tmp_path / "agari_one.xml"
    rec.save(str(out))
    n_ok, n_fail = replay_recorded_paipu(str(out), verbose=False)
    assert (n_ok, n_fail) == (1, 0)
