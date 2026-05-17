"""End-to-end encoding round-trip test.

For randomly-played selfplay states *and* (when available) replayed paipu
states, encode the table to a TokenizedObservation, then verify that
:func:`tokens_to_string` (decoded purely from the token tensor) produces
the same canonical string as :func:`state_to_string` (read directly from
the engine ``Table``).

If the encoding is lossless wrt the canonical view, the two strings are
identical for every sampled state.
"""

from __future__ import annotations

import os
import random
import threading
from glob import glob
from pathlib import Path

import pytest

pm = pytest.importorskip("MahjongPyWrapper")

from pymahjong.rl.tokenization import (  # noqa: E402
    MahjongTokenizer,
    is_self_phase,
    is_response_phase,
    is_chankan_phase,
    state_to_string,
    tokens_to_string,
)


def _step_random(table, rng) -> bool:
    phase = int(table.get_phase())
    if phase == 16:
        return False
    if is_self_phase(phase):
        actions = table.get_self_actions()
    elif is_response_phase(phase) or is_chankan_phase(phase):
        actions = table.get_response_actions()
    else:
        return False
    if not actions:
        return False
    table.make_selection(rng.randrange(len(actions)))
    return True


def _verify_one_game(seed: int, prefer_meld: bool = False) -> int:
    rng = random.Random(seed)
    t = pm.Table()
    t.set_seed(seed)
    t.game_init()
    tk = MahjongTokenizer()
    n_checked = 0
    for _ in range(500):
        phase = int(t.get_phase())
        if phase == 16:
            break
        cp = phase % 4 if phase < 16 else 0
        obs = tk.encode(t, cp)
        s_state = state_to_string(t, cp)
        s_tokens = tokens_to_string(obs)
        assert s_state == s_tokens, (
            f"encoding mismatch at seed={seed} step={n_checked} phase={phase}\n"
            f"-- state --\n{s_state}\n-- tokens --\n{s_tokens}"
        )
        n_checked += 1
        # advance
        if is_self_phase(phase):
            actions = t.get_self_actions()
        elif is_response_phase(phase) or is_chankan_phase(phase):
            actions = t.get_response_actions()
        else:
            break
        if not actions:
            break
        chosen = None
        if prefer_meld:
            BA = pm.BaseAction
            for i, a in enumerate(actions):
                if int(a.action) in (int(BA.Chi), int(BA.Pon), int(BA.Kan)):
                    chosen = i
                    break
        if chosen is None:
            chosen = rng.randrange(len(actions))
        t.make_selection(chosen)
    return n_checked


@pytest.mark.parametrize("seed", list(range(8)))
def test_selfplay_roundtrip(seed):
    n = _verify_one_game(1000 + seed, prefer_meld=False)
    assert n > 0


@pytest.mark.parametrize("seed", list(range(4)))
def test_selfplay_meldheavy_roundtrip(seed):
    n = _verify_one_game(50_000 + seed, prefer_meld=True)
    assert n > 0


# ---------------------------------------------------------------------------
# Paipu round-trip: V3 state_to_string == tokens_to_string via proxy
# ---------------------------------------------------------------------------

_proxy_lock = threading.Lock()


def _find_paipu(n: int = 5) -> list[str]:
    from pymahjong.config import get_config
    cfg = get_config()
    candidates = []
    env_dir = os.environ.get("PAIPU_DIR")
    if env_dir:
        candidates.insert(0, env_dir)
    roots = ["paipuxmls", "test_paipu", os.path.expanduser("~/paipuxmls")]
    if cfg.paipu_xml_path:
        roots.insert(0, cfg.paipu_xml_path)
    for root in roots:
        if os.path.isdir(root):
            candidates.extend(sorted(glob(os.path.join(root, "*.txt"))))
            candidates.extend(sorted(glob(os.path.join(root, "*.xml"))))
            if candidates:
                return candidates[:n]
    return candidates[:n]


def _verify_paipu_roundtrip_v3(path: str) -> tuple[int, int]:
    """Replay *path* through V3 encoder and compare canonical strings.

    Returns ``(checks, mismatches)``.
    """
    from pymahjong.rl.tokenization import (
        MahjongTokenizer,
        state_to_string,
        tokens_to_string,
    )
    from pymahjong import tenhou_paipu_check as tpc

    tk = MahjongTokenizer()
    checks = 0
    mismatches = 0
    first_mismatch: list = []

    class _V3RoundtripProxy:
        __slots__ = ("_inner",)

        def __init__(self, inner):
            object.__setattr__(self, "_inner", inner)

        def __getattr__(self, name):
            return getattr(self._inner, name)

        def init(self, *args, **kwargs):
            return self._inner.init(*args, **kwargs)

        def make_selection(self, idx):
            nonlocal checks, mismatches
            t = self._inner.table
            ret = self._inner.make_selection(idx)
            phase = int(t.get_phase())
            if phase < 16:
                actions = (
                    t.get_self_actions() if phase < 4
                    else t.get_response_actions()
                )
                if len(actions) > 1:
                    cp = phase % 4
                    obs = tk.encode(t, cp)
                    s_state = state_to_string(t, cp)
                    s_tokens = tokens_to_string(obs)
                    checks += 1
                    if s_state != s_tokens:
                        mismatches += 1
                        if not first_mismatch:
                            first_mismatch.append(
                                (path, phase, cp, s_state, s_tokens)
                            )
            return ret

    xml_path = Path(path)
    with _proxy_lock:
        orig_ctor = pm.PaipuReplayer
        pm.PaipuReplayer = lambda *a, **kw: _V3RoundtripProxy(orig_ctor(*a, **kw))
        try:
            replay = tpc.PaipuReplay()
            replay.logger = tpc.Logger()
            replay.write_log = False
            try:
                replay._paipu_replay(str(xml_path.parent), xml_path.name)
            except Exception:
                pass
        finally:
            pm.PaipuReplayer = orig_ctor

    if first_mismatch:
        path_, phase_, cp_, s1, s2 = first_mismatch[0]
        raise AssertionError(
            f"V3 round-trip mismatch in {path_} phase={phase_} cp={cp_}\n"
            f"-- state --\n{s1}\n-- tokens --\n{s2}"
        )

    return checks, mismatches


class TestV3Roundtrip:
    """Verify that V3 token encoding round-trips with engine state."""

    @pytest.fixture(scope="class")
    def paipu_files(self):
        files = _find_paipu(5)
        if not files:
            pytest.skip("no paipu XML files found")
        return files

    def test_paipu_roundtrip(self, paipu_files):
        """At every decision point, state_to_string == tokens_to_string."""
        total_checks = 0
        for path in paipu_files:
            checks, mismatches = _verify_paipu_roundtrip_v3(path)
            total_checks += checks
            assert mismatches == 0, f"{path}: {mismatches} mismatches"
        assert total_checks > 0, "no decision points checked"
