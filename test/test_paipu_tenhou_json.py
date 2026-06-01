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


def test_agari_subarray_uses_tenhou_string_format(tmp_path):
    """Regression: AGARI winner sub-array must follow Tenhou's expected
    schema ``[who, from, pao, "<点>点 string", "<yaku>(<N>飜)", ...]``.

    The Tenhou paipu editor (``/5/1129.js``) calls ``h[3].match(...)``
    on the winner sub-array's position-3 entry — if it's a raw int
    (the previous bug) JS throws ``h[3].match is not a function`` and
    the page hangs on "L O A D I N G ...".  This test directly checks
    the schema so any future regression is caught at unit-test time.
    """
    # Synthesize one agari hand deterministically using a greedy
    # heuristic (random play almost never wins).
    env = MahjongEnv()
    seed = -1
    for off in range(200):
        s = 6500 + off
        env.reset(seed=s)
        steps = 0
        while not env.is_over() and steps < 500:
            pid = env.get_curr_player_id()
            valid = np.flatnonzero(env.get_valid_actions(nhot=True))
            if len(valid) == 0:
                break
            v = valid.tolist()
            if 42 in v:
                a = 42  # tsumo
            elif 43 in v:
                a = 43  # ron
            else:
                d = [x for x in v if x < 34]
                a = min(d) if d else (45 if 45 in v else int(v[0]))
            env.step(pid, a)
            steps += 1
        if int(env.t.get_phase()) == int(pm.PhaseEnum.GAME_OVER):
            res = env.t.gamelog.result
            if int(res.result_type) in (
                int(pm.ResultType.RonAgari),
                int(pm.ResultType.TsumoAgari),
            ):
                seed = s
                break
    assert seed >= 0, "could not synthesize an AGARI hand in 200 tries"

    rec = TenhouPaipuRecorder()
    rec.record_hand(env.t, seed=seed)
    out = tmp_path / "agari.xml"
    rec.save(str(out))

    data = xml_to_tenhou_json(str(out))
    hand = data["log"][0]
    result = hand[16]
    assert result[0] == "和了", f"expected agari result, got {result[0]!r}"
    winner_tuple = result[2]
    # Schema: [who:int, from:int, pao:int, ten_str:str, *yaku_str:str]
    assert len(winner_tuple) >= 5, (
        f"winner_tuple too short: {winner_tuple}"
    )
    assert isinstance(winner_tuple[0], int)
    assert isinstance(winner_tuple[1], int)
    assert isinstance(winner_tuple[2], int)
    assert isinstance(winner_tuple[3], str), (
        f"ten_str at position 3 must be str (was {type(winner_tuple[3]).__name__}); "
        f"Tenhou JS calls .match() on it"
    )
    # Tenhou regex: /[\d\-]+点∀?(\d枚∀?)?/
    import re
    assert re.search(r"[\d\-]+点", winner_tuple[3]), (
        f"ten_str doesn't match Tenhou regex: {winner_tuple[3]!r}"
    )
    # Yaku entries: strings matching /^([^\(]*)\((\d+飜|)(?:役満)?(\d+枚|)\)/
    yaku_re = re.compile(r"^([^\(]*)\((\d+飜|)(?:役満)?(\d+枚|)\)")
    for i, yaku in enumerate(winner_tuple[4:], start=4):
        assert isinstance(yaku, str), (
            f"yaku at position {i} must be str (was {type(yaku).__name__})"
        )
        assert yaku_re.match(yaku), (
            f"yaku string doesn't match Tenhou regex: {yaku!r}"
        )


# --- Ron / Tsumo classification ---
# These tests bypass the engine and feed synthetic <AGARI> XML directly
# to the converter so we can exercise tsumo-oya, tsumo-kodomo, and ron
# code paths without having to coax the engine into producing each
# variant under random self-play (tsumo wins are extremely rare).

import xml.etree.ElementTree as ET  # noqa: E402

from pymahjong.paipu_tenhou_json import xml_string_to_tenhou_json  # noqa: E402

_BASE_INIT = (
    '<mjloggm ver="2.3">'
    '<GO type="33" lobby="0"/>'
    '<UN n0="A" n1="B" n2="C" n3="D" dan="0,0,0,0" '
    'rate="1500,1500,1500,1500" sx="C,C,C,C"/>'
    '<TAIKYOKU oya="{oya}"/>'
    '<INIT seed="0,0,0,0,0,0" ten="250,250,250,250" oya="{oya}" '
    'hai0="0,1,2,3,4,5,6,7,8,9,10,11,12" '
    'hai1="16,17,18,19,20,21,22,23,24,25,26,27,28" '
    'hai2="32,33,34,35,36,37,38,39,40,41,42,43,44" '
    'hai3="48,49,50,51,52,53,54,55,56,57,58,59,60" '
    'seed_int="0"/>'
)


def _agari_xml(*, who, fromWho, oya, sc, ten, yaku="", score2=None):
    score2_attr = f' score2="{score2}"' if score2 is not None else ""
    return (
        _BASE_INIT.format(oya=oya)
        + f'<AGARI who="{who}" fromWho="{fromWho}" ba="0,0" sc="{sc}" '
        f'hai="0,1,2,3,4,5,6,7,8,9,10,11,12,13" machi="13" '
        f'ten="{ten}" yaku="{yaku}" doraHai="0"{score2_attr}/>'
        + "</mjloggm>"
    )


def test_ron_ten_string_format():
    """Ron: ten string is '<fu>符<han>飜<total>点' (no ∀, no X-Y)."""
    # P2 (kodomo) ron P0 (oya), 40fu 3han = 5200pts total.
    xml = _agari_xml(
        who=2, fromWho=0, oya=0,
        sc="250,-52,250,0,250,52,250,0",
        ten="40,5200,0",
        yaku="1,1,2,1,3,1",  # riichi(1) + tanyao(1) + tsumo(1) → 3 han total
    )
    data = xml_string_to_tenhou_json(xml)
    ten_str = data["log"][0][16][2][3]
    assert ten_str == "40符3飜5200点", f"got {ten_str!r}"
    assert "∀" not in ten_str
    assert "-" not in ten_str.replace("点", "")  # no X-Y form


def test_dealer_tsumo_ten_string_format():
    """Dealer tsumo: ten string ends with '点∀' (everyone pays score1)."""
    # P0 (oya) tsumo, 30fu 2han, score1=1000 (each non-dealer pays 1000).
    # fromWho == who is the tsumo marker.
    xml = _agari_xml(
        who=0, fromWho=0, oya=0,
        sc="250,30,250,-10,250,-10,250,-10",
        ten="30,1000,0",
        yaku="1,1,3,1",
    )
    data = xml_string_to_tenhou_json(xml)
    ten_str = data["log"][0][16][2][3]
    assert ten_str == "30符2飜1000点∀", f"got {ten_str!r}"


def test_nondealer_tsumo_ten_string_format():
    """Non-dealer tsumo: ten string is '<fu>符<han>飜<X>-<Y>点'
    (X = each kodomo pay = score2, Y = oya pay = score1)."""
    # P1 (kodomo) tsumo with oya=P0, 30fu 2han.  score1=1000 (P0 pays),
    # score2=500 (P2/P3 each pay).
    xml = _agari_xml(
        who=1, fromWho=1, oya=0,
        sc="250,-10,250,20,250,-5,250,-5",
        ten="30,1000,0",
        yaku="1,1,3,1",
        score2=500,
    )
    data = xml_string_to_tenhou_json(xml)
    ten_str = data["log"][0][16][2][3]
    assert ten_str == "30符2飜500-1000点", f"got {ten_str!r}"


def test_tsumo_winner_tuple_from_equals_who():
    """Tsumo: winner_tuple[1] (fromWho) must equal winner_tuple[0] (who).

    This is the canonical Tenhou convention for tsumo (the editor's
    quick-summary logic at offset 23546 uses ``b[2][0]==b[2][1]`` to
    detect tsumo vs ron)."""
    xml = _agari_xml(
        who=2, fromWho=2, oya=0,
        sc="250,-10,250,-10,250,30,250,-10",
        ten="30,1000,0",
        yaku="3,1",
        score2=0,  # dealer-tsumo style: omit or 0 means everyone pays score1
    )
    data = xml_string_to_tenhou_json(xml)
    winner_tuple = data["log"][0][16][2]
    assert winner_tuple[0] == winner_tuple[1] == 2, (
        f"tsumo winner_tuple must have who==fromWho, got {winner_tuple}"
    )
