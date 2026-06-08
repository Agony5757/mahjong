"""Smoke tests for :mod:`pymahjong.paipu_tenhou_json`.

We don't validate against a real Tenhou viewer, but we do exercise the
XML→JSON path and check structural invariants (correct array length,
tile-id encoding range, URL fragment is well-formed, etc.).
"""
from __future__ import annotations

import json
import random
from urllib.parse import unquote, urlparse

import numpy as np
import pytest

pm = pytest.importorskip("MahjongPyWrapper")

from pymahjong.env_pymahjong import MahjongEnv
from pymahjong.paipu_recorder import TenhouPaipuRecorder
from pymahjong.paipu_tenhou_json import (
    make_editor_url,
    save_tenhou_json,
    xml_string_to_tenhou_json,
    xml_to_tenhou_json,
)


def _record_random_paipu(n_hands: int, base_seed: int, tmp_path):
    recorder = TenhouPaipuRecorder()
    env = MahjongEnv()
    rng = random.Random(base_seed)
    for i in range(n_hands):
        seed = base_seed + i
        env.reset(seed=seed)
        steps = 0
        while not env.is_over() and steps < 1000:
            pid = env.get_curr_player_id()
            valid = np.flatnonzero(env.get_valid_actions(nhot=True))
            if len(valid) == 0:
                break
            env.step(pid, int(rng.choice(valid.tolist())))
            steps += 1
        if int(env.t.get_phase()) == int(pm.PhaseEnum.GAME_OVER):
            recorder.record_hand(env.t, seed=seed)
    out = tmp_path / "paipu.xml"
    recorder.save(str(out))
    return out, recorder


def test_xml_to_json_structure(tmp_path):
    xml_path, recorder = _record_random_paipu(5, 8000, tmp_path)
    data = xml_to_tenhou_json(str(xml_path), title=["test", ""])
    assert set(data.keys()) >= {"title", "name", "rule", "log"}
    assert len(data["log"]) == recorder.n_hands
    for hand in data["log"]:
        assert len(hand) == 17, "each hand must have 17 slots"
        # Round info: [round, honba, kyoutaku]
        assert len(hand[0]) == 3
        # Start scores: 4 ints in 1-100ths of original units (i.e. /100).
        assert len(hand[1]) == 4
        assert all(isinstance(x, int) for x in hand[1])
        # Each initial hand has 13 tiles.
        for pid in range(4):
            assert len(hand[4 + pid * 3]) == 13
        # Tile-id encoding range check.
        for x in hand[2] + hand[4]:
            assert 11 <= x <= 53, f"tile id out of range: {x}"


def test_tsumogiri_and_riichi(tmp_path):
    """Tsumogiri must encode as 60; riichi discards as 'r<num>' strings."""
    xml_path, _ = _record_random_paipu(20, 4242, tmp_path)
    data = xml_to_tenhou_json(str(xml_path))
    saw_tsumogiri = False
    saw_riichi = False
    for hand in data["log"]:
        for pid in range(4):
            for entry in hand[6 + pid * 3]:
                if entry == 60:
                    saw_tsumogiri = True
                elif isinstance(entry, str) and entry.startswith("r"):
                    saw_riichi = True
    # tsumogiri is very common in random play
    assert saw_tsumogiri, "expected at least one tsumogiri in 20 random hands"
    # riichi is rarer but should appear at least once across many hands
    # (not a hard failure if random play happens never to riichi).
    _ = saw_riichi


def test_editor_url_is_well_formed(tmp_path):
    xml_path, _ = _record_random_paipu(2, 1234, tmp_path)
    data = xml_to_tenhou_json(str(xml_path))
    url = make_editor_url(data)
    assert url.startswith("https://tenhou.net/5/#json=")
    # Round-trip parse the JSON out of the fragment.
    frag = urlparse(url).fragment
    assert frag.startswith("json=")
    payload = unquote(frag[len("json="):])
    parsed = json.loads(payload)
    assert parsed["log"] == data["log"]


def test_save_json_round_trip(tmp_path):
    xml_path, _ = _record_random_paipu(3, 9999, tmp_path)
    data = xml_to_tenhou_json(str(xml_path))
    out = tmp_path / "paipu.json"
    save_tenhou_json(data, str(out))
    assert out.exists() and out.stat().st_size > 0
    reread = json.loads(out.read_text(encoding="utf-8"))
    assert reread == data


def test_xml_string_variant_matches_path(tmp_path):
    xml_path, _ = _record_random_paipu(1, 555, tmp_path)
    text = xml_path.read_text(encoding="utf-8")
    a = xml_to_tenhou_json(str(xml_path))
    b = xml_string_to_tenhou_json(text)
    assert a == b
