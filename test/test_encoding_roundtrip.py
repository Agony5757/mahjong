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
from glob import glob

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
# Optional paipu round-trip (skipped if no paipu data found)
# ---------------------------------------------------------------------------

def _find_paipu():
    from pymahjong.config import get_config
    cfg = get_config()
    candidates = []
    roots = ["paipuxmls", "test_paipu", os.path.expanduser("~/paipuxmls")]
    if cfg.paipu_xml_path:
        roots.insert(0, cfg.paipu_xml_path)
    for root in roots:
        if os.path.isdir(root):
            candidates.extend(glob(os.path.join(root, "**/*.xml"), recursive=True))
            candidates.extend(glob(os.path.join(root, "**/*.txt"), recursive=True))
    return candidates


@pytest.mark.skipif(
    not hasattr(pm, "PaipuReplayer"),
    reason="PaipuReplayer not exposed in this build",
)
def test_paipu_roundtrip_sample():
    paipus = _find_paipu()
    if not paipus:
        pytest.skip("no paipu xml files found locally")
    tk = MahjongTokenizer()
    sampled = paipus[:5]
    total = 0
    for path in sampled:
        try:
            rep = pm.PaipuReplayer()
            rep.init(path)
        except Exception:  # noqa: BLE001
            continue
        if not (hasattr(rep, "table") and hasattr(rep, "step")
                and hasattr(rep, "next_action")):
            pytest.skip("PaipuReplayer next_action/step not exposed")
        table = rep.table
        steps = 0
        while steps < 600:
            phase = int(table.get_phase())
            if phase == 16:
                break
            cp = phase % 4 if phase < 16 else 0
            obs = tk.encode(table, cp)
            s1 = state_to_string(table, cp)
            s2 = tokens_to_string(obs)
            assert s1 == s2, (
                f"mismatch in {path} step={steps} phase={phase}\n"
                f"-- state --\n{s1}\n-- tokens --\n{s2}"
            )
            steps += 1
            try:
                rep.step()
            except Exception:  # noqa: BLE001
                break
        total += steps
    assert total > 0
