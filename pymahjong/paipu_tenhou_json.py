"""Tenhou-JSON paipu format conversion (for paipu-editor URLs).

The Tenhou paipu editor (and viewers like amae-koromo's paipu viewer)
accepts paipu in a compact JSON format that differs from the XML stream
emitted by :class:`pymahjong.paipu_recorder.TenhouPaipuRecorder`.

The JSON format uses a two-digit tile encoding rather than the 0-135 id
used by the XML, and inlines meld calls as special strings in each
player's draw/discard stream::

    {
      "title": ["AI self-play", ""],
      "name":  ["BC0", "BC1", "BC2", "BC3"],
      "rule":  {"disp": "般東", "aka": 1},
      "log":   [hand0, hand1, ...]
    }

Each ``handN`` is a length-17 array::

    [
      [round, honba, kyoutaku],   # 0
      [s0, s1, s2, s3],           # 1  start scores
      [dora_ind, ...],            # 2  dora indicators (1+; append on kan)
      [ura_dora_ind, ...],        # 3  ura dora (empty unless riichi+win)
      [hai0_tiles],               # 4
      [draws_0],                  # 5
      [discards_0],               # 6
      [hai1_tiles],               # 7
      [draws_1],                  # 8
      [discards_1],               # 9
      [hai2_tiles],               # 10
      [draws_2],                  # 11
      [discards_2],               # 12
      [hai3_tiles],               # 13
      [draws_3],                  # 14
      [discards_3],               # 15
      [result_type, [score_changes], ...]  # 16
    ]

Special encodings in draws/discards:

* ``60``                  — tsumogiri (discard the drawn tile)
* ``"r<num>"``            — riichi discard (e.g. ``"r15"``)
* ``"c<call><c1><c2>"``                — chi (in *draws* list)
* ``"<c1>p<call><c2>"``                — pon from opposite seat
* ``"p<call><c1><c2>"``                — pon from kamicha (upstream)
* ``"<c1><c2>p<call>"``                — pon from shimocha (downstream)
* ``"<c1><c2><c3>m<call>"`` / etc.     — daiminkan (in *draws* list)
* ``"<c1><c2><c3>a<c4>"``              — ankan  (in *discards* list)
* ``"<c1><c2>k<c3><c4>"``              — kakan  (in *discards* list)
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import quote

import MahjongPyWrapper as pm


# Map BaseTile (0..33) → 2-digit tile encoding used by Tenhou JSON.
# Wind/dragon order in JSON: E(41), S(42), W(43), N(44), P=白(45), F=發(46), C=中(47)
_BASETILE_TO_NUM = {
    # man: 11..19
    **{i: 11 + i for i in range(9)},
    # pin: 21..29
    **{9 + i: 21 + i for i in range(9)},
    # sou: 31..39
    **{18 + i: 31 + i for i in range(9)},
    # z: 41..47
    **{27 + i: 41 + i for i in range(7)},
}

# Red-dora full tile ids (engine convention).
_RED_IDS = {16: 51, 52: 52, 88: 53}


def _tile_id_to_num(tile_id: int) -> int:
    """Convert a 0-135 engine tile id to the Tenhou-JSON 2-digit encoding."""
    if tile_id in _RED_IDS:
        return _RED_IDS[tile_id]
    return _BASETILE_TO_NUM[tile_id // 4]


def _tiles_to_nums(tile_ids: Sequence[int]) -> List[int]:
    return [_tile_id_to_num(t) for t in tile_ids]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------


def xml_to_tenhou_json(
    xml_path: str,
    *,
    title: Optional[Sequence[str]] = None,
    rule_disp: str = "般東",
    aka_dora: bool = True,
) -> Dict[str, Any]:
    """Parse a Tenhou XML paipu (as emitted by :class:`TenhouPaipuRecorder`)
    and return the equivalent Tenhou-JSON paipu dict.

    Args:
        xml_path: path to the XML paipu file.
        title: optional ``(title, subtitle)`` strings.
        rule_disp: display string for the ``rule.disp`` field
            (e.g. ``"般東喰赤"``).  Default ``"般東"``.
        aka_dora: whether the paipu uses red dora.  Default True.

    Returns:
        A dict ready to be ``json.dumps()``-ed and fed to the Tenhou
        paipu editor / viewer.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    return _root_to_json(root, title=title, rule_disp=rule_disp, aka_dora=aka_dora)


def xml_string_to_tenhou_json(
    xml_text: str,
    *,
    title: Optional[Sequence[str]] = None,
    rule_disp: str = "般東",
    aka_dora: bool = True,
) -> Dict[str, Any]:
    """Same as :func:`xml_to_tenhou_json` but accepts a raw XML string."""
    root = ET.fromstring(xml_text)
    return _root_to_json(root, title=title, rule_disp=rule_disp, aka_dora=aka_dora)


def make_editor_url(
    paipu_json: Dict[str, Any],
    *,
    base: str = "https://tenhou.net/5/",
) -> str:
    """Build a Tenhou paipu-editor URL from a JSON paipu dict.

    The Tenhou JS editor reads the paipu from a URL hash fragment
    (``#json=<urlencoded>``).  The fragment isn't sent over the wire,
    so even very long URLs work — they just may exceed the browser's
    address-bar display limit.  Tenhou's own viewer accepts the same
    fragment scheme at ``tenhou.net/5/``.

    Args:
        paipu_json: dict produced by :func:`xml_to_tenhou_json` or by
            :meth:`TenhouPaipuRecorder.to_tenhou_json`.
        base: base URL.  Default ``"https://tenhou.net/5/"`` (Tenhou's
            JSON viewer / editor entry point).  Pass
            ``"https://tenhou.net/6/"`` for the alternate v6 editor.

    Returns:
        Full URL string.
    """
    payload = json.dumps(paipu_json, ensure_ascii=False, separators=(",", ":"))
    return f"{base}#json={quote(payload, safe='')}"


def make_per_hand_urls(
    paipu_json: Dict[str, Any],
    *,
    base: str = "https://tenhou.net/5/",
) -> List[str]:
    """Build one Tenhou paipu-editor URL **per hand** (kyoku).

    Splits a multi-hand paipu dict (as produced by
    :func:`xml_to_tenhou_json`) into N single-hand paipus, where N is the
    number of entries in ``paipu_json["log"]``, and returns one URL per
    hand.  Each URL contains only that single hand, so URLs stay short
    enough to share even when the source paipu is a full hanchan.

    Args:
        paipu_json: dict produced by :func:`xml_to_tenhou_json` (may
            contain one or many hands in ``log``).
        base: base URL.  Default ``"https://tenhou.net/5/"``.

    Returns:
        List of N URL strings (one per hand, in the original order).
        Returns an empty list if ``log`` is empty.
    """
    logs = paipu_json.get("log") or []
    urls: List[str] = []
    for hand in logs:
        single = {**paipu_json, "log": [hand]}
        urls.append(make_editor_url(single, base=base))
    return urls


def save_tenhou_json(
    paipu_json: Dict[str, Any],
    path: str,
    *,
    pretty: bool = False,
) -> None:
    """Write a Tenhou-JSON paipu dict to ``path``.

    Args:
        paipu_json: the dict to write.
        path: output file path.
        pretty: if True, indent with 2 spaces.  Default False
            (compact one-line, matches what the editor consumes).
    """
    import os
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(paipu_json, f, ensure_ascii=False, indent=2)
        else:
            json.dump(paipu_json, f, ensure_ascii=False, separators=(",", ":"))


# --------------------------------------------------------------------------
# Internals — XML → JSON translation
# --------------------------------------------------------------------------


def _root_to_json(
    root: ET.Element,
    *,
    title: Optional[Sequence[str]],
    rule_disp: str,
    aka_dora: bool,
) -> Dict[str, Any]:
    # Extract player names from <UN>; fall back to AI0..AI3.
    un = root.find("UN")
    names = ["AI0", "AI1", "AI2", "AI3"]
    if un is not None:
        for i in range(4):
            v = un.get(f"n{i}")
            if v:
                try:
                    from urllib.parse import unquote
                    names[i] = unquote(v)
                except Exception:
                    names[i] = v

    hands_json: List[List[Any]] = []
    current_init: Optional[ET.Element] = None
    current_events: List[ET.Element] = []
    for child in list(root):
        if child.tag == "INIT":
            if current_init is not None:
                hands_json.append(_translate_hand(current_init, current_events))
            current_init = child
            current_events = []
        elif current_init is not None:
            current_events.append(child)
    if current_init is not None:
        hands_json.append(_translate_hand(current_init, current_events))

    return {
        "title": list(title) if title is not None else ["", ""],
        "name": names,
        "rule": {"disp": rule_disp, "aka": 1 if aka_dora else 0},
        "log": hands_json,
    }


def _translate_hand(init: ET.Element, events: Sequence[ET.Element]) -> List[Any]:
    """Translate one hand's XML element stream into the 17-slot JSON array."""
    from pymahjong.tenhou_paipu_check import decodem

    seed_parts = init.get("seed", "0,0,0,0,0,0").split(",")
    round_no = int(seed_parts[0])
    honba = int(seed_parts[1])
    kyoutaku = int(seed_parts[2])
    first_dora_id = int(seed_parts[5]) if len(seed_parts) > 5 else 0

    scores = [int(x) for x in init.get("ten", "250,250,250,250").split(",")]

    init_hands_nums: List[List[int]] = []
    for pid in range(4):
        ids = [int(x) for x in init.get(f"hai{pid}", "").split(",") if x]
        init_hands_nums.append(_tiles_to_nums(ids))

    # 16-slot scaffolding (indices 4/7/10/13 = init hands; 5/8/11/14 = draws;
    # 6/9/12/15 = discards).
    draws_idx = {0: 5, 1: 8, 2: 11, 3: 14}
    discards_idx = {0: 6, 1: 9, 2: 12, 3: 15}

    hand_json: List[Any] = [
        [round_no, honba, kyoutaku],
        list(scores),
        [_tile_id_to_num(first_dora_id)],
        [],
        init_hands_nums[0], [], [],
        init_hands_nums[1], [], [],
        init_hands_nums[2], [], [],
        init_hands_nums[3], [], [],
        [],  # result placeholder
    ]

    # Track what the last drawn tile was per player (for tsumogiri detection)
    # and pending riichi flags.
    last_drawn = {0: None, 1: None, 2: None, 3: None}
    riichi_pending = [False, False, False, False]

    for ev in events:
        tag = ev.tag

        if tag and tag[0] in "TUVW" and not ev.attrib:
            pid = "TUVW".index(tag[0])
            tid = int(tag[1:])
            num = _tile_id_to_num(tid)
            hand_json[draws_idx[pid]].append(num)
            last_drawn[pid] = num
            continue

        if tag and tag[0] in "DEFG" and not ev.attrib:
            pid = "DEFG".index(tag[0])
            tid = int(tag[1:])
            num = _tile_id_to_num(tid)
            # Detect tsumogiri = the discarded tile equals the last drawn.
            tsumogiri = (last_drawn[pid] is not None and num == last_drawn[pid])
            entry = 60 if tsumogiri else num
            if riichi_pending[pid]:
                # Tenhou riichi-discard format: prepend 'r'.
                # Concatenate "r" with the tile number so the entry stays
                # a single token (e.g. "r15" or "r60").
                hand_json[discards_idx[pid]].append(f"r{entry}")
                riichi_pending[pid] = False
            else:
                hand_json[discards_idx[pid]].append(entry)
            # After a discard the player no longer holds the drawn tile.
            last_drawn[pid] = None
            continue

        if tag == "REACH":
            who = int(ev.get("who"))
            step = ev.get("step")
            if step == "1":
                riichi_pending[who] = True
            # step=2 is informational — no JSON entry needed.
            continue

        if tag == "DORA":
            hai = int(ev.get("hai"))
            hand_json[2].append(_tile_id_to_num(hai))
            continue

        if tag == "N":
            who = int(ev.get("who"))
            m = int(ev.get("m"))
            _emit_naru_json(
                hand_json, who, m, draws_idx, discards_idx,
                last_drawn, decodem,
            )
            continue

        if tag == "AGARI":
            _emit_agari_json(hand_json, ev, events, oya=int(init.get("oya", "0")))
            continue

        if tag == "RYUUKYOKU":
            _emit_ryuukyoku_json(hand_json, ev)
            continue

        # Unknown tag — skip silently.

    return hand_json


def _emit_naru_json(
    hand_json: List[Any],
    who: int,
    m: int,
    draws_idx: Dict[int, int],
    discards_idx: Dict[int, int],
    last_drawn: Dict[int, Optional[int]],
    decodem,
) -> None:
    """Append a naru code into the appropriate per-player draws/discards list."""
    side_added, hand_removed, naru_type, _ = decodem(m, who)
    # side_added is a list of [tile_id, is_called] pairs.
    if naru_type == "Chi":
        # Chi only comes from kamicha (upstream).  Tenhou JSON format:
        # "c{called}{c1}{c2}" in the *draws* list.
        called_id = next(t for t, is_c in side_added if is_c)
        hand_ids = [t for t, is_c in side_added if not is_c]
        # Sort hand tiles by basetile (with red-dora treated as 5).
        def _sort_key(tid):
            n = _tile_id_to_num(tid)
            return {51: 15, 52: 25, 53: 35}.get(n, n)
        hand_ids.sort(key=_sort_key)
        code = (
            f"c{_tile_id_to_num(called_id)}"
            f"{_tile_id_to_num(hand_ids[0])}"
            f"{_tile_id_to_num(hand_ids[1])}"
        )
        hand_json[draws_idx[who]].append(code)
        last_drawn[who] = None  # chi → must discard after
        return

    if naru_type == "Pon":
        called_id = next(t for t, is_c in side_added if is_c)
        hand_ids = [t for t, is_c in side_added if not is_c]
        # Source player encoded in low 2 bits of m: source_rel = (from - who) % 4.
        source_rel = m & 0x3
        # 1 = shimocha (downstream), 2 = opposite, 3 = kamicha (upstream).
        called_num = _tile_id_to_num(called_id)
        c_nums = [_tile_id_to_num(t) for t in hand_ids]
        if source_rel == 3:
            code = f"p{called_num}{c_nums[0]}{c_nums[1]}"
        elif source_rel == 2:
            code = f"{c_nums[0]}p{called_num}{c_nums[1]}"
        elif source_rel == 1:
            code = f"{c_nums[0]}{c_nums[1]}p{called_num}"
        else:
            # 0 = self (shouldn't happen for pon, but be defensive)
            code = f"p{called_num}{c_nums[0]}{c_nums[1]}"
        hand_json[draws_idx[who]].append(code)
        last_drawn[who] = None
        return

    if naru_type == "Min-Kan":
        called_id = next(t for t, is_c in side_added if is_c)
        hand_ids = [t for t, is_c in side_added if not is_c]
        source_rel = m & 0x3
        called_num = _tile_id_to_num(called_id)
        c_nums = [_tile_id_to_num(t) for t in hand_ids]
        if source_rel == 3:
            code = f"m{called_num}{c_nums[0]}{c_nums[1]}{c_nums[2]}"
        elif source_rel == 2:
            code = f"{c_nums[0]}m{called_num}{c_nums[1]}{c_nums[2]}"
        elif source_rel == 1:
            code = f"{c_nums[0]}{c_nums[1]}{c_nums[2]}m{called_num}"
        else:
            code = f"m{called_num}{c_nums[0]}{c_nums[1]}{c_nums[2]}"
        hand_json[draws_idx[who]].append(code)
        # Daiminkan steals the turn — emit a 0 placeholder in discards so
        # the editor preserves the timeline (the rinshan draw / discard
        # follow as normal).
        hand_json[discards_idx[who]].append(0)
        last_drawn[who] = None
        return

    if naru_type == "An-Kan":
        # All 4 tiles from hand.  Tenhou format: "{c1}{c2}{c3}a{c4}".
        # ``side_added`` for ankan has all 4 with is_c=0; pull all 4 ids.
        tile_ids = [t for t, _ in side_added]
        nums = [_tile_id_to_num(t) for t in tile_ids[:4]]
        # Pad to 4 if decodem missed one.
        while len(nums) < 4:
            nums.append(nums[-1])
        code = f"{nums[0]}{nums[1]}{nums[2]}a{nums[3]}"
        hand_json[discards_idx[who]].append(code)
        last_drawn[who] = None
        return

    if naru_type == "Ka-Kan":
        # The 4th tile added to an existing pon.  Tenhou format:
        # "{c1}{c2}k{c3}{c4}".  side_added only has the added tile.
        added_id = next((t for t, is_c in side_added if is_c), side_added[0][0])
        added_num = _tile_id_to_num(added_id)
        # We don't know the original pon's 3 tile ids from m alone, but
        # the editor only needs them to be 4 copies of the same basetile;
        # use placeholder values from the same basetile group.
        basetile_id = added_id // 4
        original_ids = [basetile_id * 4 + k for k in range(4) if basetile_id * 4 + k != added_id]
        nums = [_tile_id_to_num(t) for t in original_ids]
        code = f"{nums[0]}{nums[1]}k{nums[2]}{added_num}"
        hand_json[discards_idx[who]].append(code)
        last_drawn[who] = None
        return


def _emit_agari_json(
    hand_json: List[Any],
    el: ET.Element,
    events: Sequence[ET.Element],
    *,
    oya: int = 0,
) -> None:
    """Translate an <AGARI> element into the result slot (index 16).

    Tenhou's paipu editor (``/5/1129.js``) parses the agari sub-array as
    ``[who, from_who, pao_who, "<点>点 description string",
      "<yaku>(<N>飜)", ...]`` — i.e. position [3] onwards must be
    *strings*, not raw integers (the regex at offset 23546 of the
    editor JS matches ``/[\\d\\-]+点∀?(\\d枚∀?)?/`` against position 3).
    Emitting raw ints makes the editor's per-hand renderer throw and
    leaves the paipu unrenderable.
    """
    who = int(el.get("who"))
    from_who = int(el.get("fromWho"))
    sc_parts = [int(x) for x in el.get("sc", "0,0,0,0,0,0,0,0").split(",")]
    score_changes = [sc_parts[2 * i + 1] for i in range(4)]
    ten_str_raw = el.get("ten", "0,0,0")
    yaku_str_raw = el.get("yaku", "")
    fu, base_points, mangan_level = [int(x) for x in ten_str_raw.split(",")]
    # Side attribute populated by the recorder for non-dealer tsumo:
    # ``score2`` = per-non-dealer pay (Tenhou displays "X-Y点" =
    # kodomo-pay/oya-pay).  Missing / 0 = not applicable (ron, or
    # dealer tsumo where everyone pays ``score1``).
    score2 = int(el.get("score2", "0"))

    # Parse yaku list (XML emits ``id,han,id,han,...``); aggregate dora
    # variants by count since each dora hit is reported as a separate
    # ``Dora,1`` / ``Akadora,1`` / ``Uradora,1`` entry.
    yaku_ids: List[int] = []
    if yaku_str_raw:
        tokens = [int(t) for t in yaku_str_raw.split(",") if t]
        for i in range(0, len(tokens), 2):
            yaku_ids.append(tokens[i])

    # ten_str: position 3 of the winner sub-array — a string the editor
    # displays verbatim (and uses to detect tsumo via "∀" suffix).
    is_tsumo = (who == from_who)
    is_oya = (who == oya)
    total_han = _yaku_total_han(yaku_ids)
    ten_str = _format_ten_string(
        fu=fu,
        han=total_han,
        score1=base_points,
        score2=score2,
        mangan_level=mangan_level,
        is_tsumo=is_tsumo,
        is_oya=is_oya,
    )
    yaku_strings = _format_yaku_strings(yaku_ids)

    # Pao (sekinin-barai): not currently exposed via the AGARI element,
    # so default to ``who`` (no separate liability) — Tenhou treats
    # ``pao == who`` as "no pao".
    winner_tuple: List[Any] = [who, from_who, who, ten_str] + yaku_strings

    if hand_json[16] and hand_json[16][0] == "和了":
        # Double ron — append a second [who, from, who, ten, yaku] tuple.
        hand_json[16][1] = [hand_json[16][1][i] + score_changes[i] for i in range(4)]
        hand_json[16].append(winner_tuple)
    else:
        hand_json[16] = [
            "和了",
            score_changes,
            winner_tuple,
        ]


# Yaku id → (japanese display name, default han value).  Indexed against
# the ``Yaku`` enum order in ``Mahjong/Yaku.h`` (None=0).  Sentinel
# entries (Yaku_1_han, Yaku_2_han, ...) are kept so int(Yaku::X) lines up.
_YAKU_TABLE: List[Optional["tuple[str, int]"]] = [
    None,                       # 0: None
    ("立直", 1),                # 1: Riichi
    ("断幺九", 1),              # 2: Tanyao
    ("門前清自摸和", 1),        # 3: Menzentsumo
    ("自風 東", 1),             # 4: Jikaze_Ton
    ("自風 南", 1),             # 5: Jikaze_Nan
    ("自風 西", 1),             # 6: Jikaze_Sha
    ("自風 北", 1),             # 7: Jikaze_Pei
    ("場風 東", 1),             # 8: Bakaze_Ton
    ("場風 南", 1),             # 9: Bakaze_Nan
    ("場風 西", 1),             # 10: Bakaze_Sha
    ("場風 北", 1),             # 11: Bakaze_Pei
    ("役牌 白", 1),             # 12: Yakuhai_Haku
    ("役牌 發", 1),             # 13: Yakuhai_Hatsu
    ("役牌 中", 1),             # 14: Yakuhai_Chu
    ("平和", 1),                # 15: Pinfu
    ("一盃口", 1),              # 16: Ippeikou
    ("槍槓", 1),                # 17: Chankan
    ("嶺上開花", 1),            # 18: Rinshankaihou
    ("海底摸月", 1),            # 19: Haiteiraoyue
    ("河底撈魚", 1),            # 20: Houteiraoyu
    ("一発", 1),                # 21: Ippatsu
    ("ドラ", 1),                # 22: Dora (per-tile; aggregated by count)
    ("裏ドラ", 1),              # 23: Uradora (per-tile; aggregated)
    ("赤ドラ", 1),              # 24: Akadora (per-tile; aggregated)
    ("北ドラ", 1),              # 25: Peidora (3-player only)
    ("混全帯幺九", 1),          # 26: Honchantaiyaochu_Naki
    ("一気通貫", 1),            # 27: Ikkitsuukan_Naki
    ("三色同順", 1),            # 28: Sanshokudoujun_Naki
    None,                       # 29: Yaku_1_han (sentinel)
    ("両立直", 2),              # 30: Dabururiichi
    ("三色同刻", 2),            # 31: Sanshokudoukou
    ("三槓子", 2),              # 32: Sankantsu
    ("対々和", 2),              # 33: Toitoiho
    ("三暗刻", 2),              # 34: Sanankou
    ("小三元", 2),              # 35: Shousangen
    ("混老頭", 2),              # 36: Honroutou
    ("七対子", 2),              # 37: Chiitoitsu
    ("混全帯幺九", 2),          # 38: Honchantaiyaochu
    ("一気通貫", 2),            # 39: Ikkitsuukan
    ("三色同順", 2),            # 40: Sanshokudoujun
    ("純全帯幺九", 2),          # 41: Junchantaiyaochu_Naki
    ("混一色", 2),              # 42: Honitsu_Naki
    None,                       # 43: Yaku_2_han (sentinel)
    ("二盃口", 3),              # 44: Rianpeikou
    ("純全帯幺九", 3),          # 45: Junchantaiyaochu
    ("混一色", 3),              # 46: Honitsu
    None,                       # 47: Yaku_3_han
    ("清一色", 5),              # 48: Chinitsu_Naki
    None,                       # 49: Yaku_5_han
    ("清一色", 6),              # 50: Chinitsu
    None,                       # 51: Yaku_6_han
    ("流し満貫", 5),            # 52: Nagashimangan
    None,                       # 53: Yaku_mangan (sentinel)
    ("天和", 13),               # 54: Tenhou
    ("地和", 13),               # 55: Chihou
    ("大三元", 13),             # 56: Daisangen
    ("四暗刻", 13),             # 57: Siiankou
    ("字一色", 13),             # 58: Tsuiisou
    ("緑一色", 13),             # 59: Ryuiisou
    ("清老頭", 13),             # 60: Chinroutou
    ("国士無双", 13),           # 61: Kokushimusou
    ("小四喜", 13),             # 62: Shousuushi
    ("四槓子", 13),             # 63: Siikantsu
    ("九蓮宝燈", 13),           # 64: Chuurenpoutou
    None,                       # 65: Yakuman (sentinel)
    ("四暗刻単騎", 26),         # 66: Siiankou_1 (double yakuman)
    ("国士無双十三面", 26),     # 67: Koukushimusou_13
    ("純正九蓮宝燈", 26),       # 68: Chuurenpoutou_9
    ("大四喜", 26),             # 69: Daisuushi
]
_DORA_IDS = {22, 23, 24, 25}  # Dora / Uradora / Akadora / Peidora


def _yaku_total_han(yaku_ids: Sequence[int]) -> int:
    """Sum the default-han values for the given yaku id sequence."""
    total = 0
    for yid in yaku_ids:
        if 0 <= yid < len(_YAKU_TABLE) and _YAKU_TABLE[yid] is not None:
            total += _YAKU_TABLE[yid][1]
    return total


def _format_yaku_strings(yaku_ids: Sequence[int]) -> List[str]:
    """Format yaku list as Tenhou-editor display strings.

    Each entry is ``"<name>(<N>飜)"`` for normal yaku, ``"<name>(役満)"``
    for yakuman, or ``"<name>(W役満)"`` for double-yakuman.  Dora-class
    yaku (Dora/Uradora/Akadora/Peidora) are aggregated by count.
    """
    out: List[str] = []
    seen_dora: Dict[int, int] = {}  # yaku_id -> count
    for yid in yaku_ids:
        if yid in _DORA_IDS:
            seen_dora[yid] = seen_dora.get(yid, 0) + 1
            continue
        if not (0 <= yid < len(_YAKU_TABLE)) or _YAKU_TABLE[yid] is None:
            continue
        name, han = _YAKU_TABLE[yid]
        if han >= 26:
            out.append(f"{name}(W役満)")
        elif han >= 13:
            out.append(f"{name}(役満)")
        else:
            out.append(f"{name}({han}飜)")
    for yid, count in seen_dora.items():
        name = _YAKU_TABLE[yid][0]
        out.append(f"{name}({count}飜)")
    return out


def _format_ten_string(
    *,
    fu: int,
    han: int,
    score1: int,
    score2: int,
    mangan_level: int,
    is_tsumo: bool,
    is_oya: bool,
) -> str:
    """Build the ``n[3]`` ten-display string for the agari sub-array.

    Tenhou's regex requires the string to contain ``<digits>点`` (with
    optional ``∀`` for dealer tsumo or ``X-Y点`` for non-dealer tsumo).

    Point-encoding cases:

    * **Ron** (``not is_tsumo``): ``score1`` is the *total* point
      transfer from the loser → ``"...{score1}点"``.
    * **Dealer tsumo** (``is_oya and is_tsumo``): ``score1`` is what
      each non-dealer pays → ``"...{score1}点∀"`` (``∀`` = "from all").
    * **Non-dealer tsumo** (``not is_oya and is_tsumo``): ``score1`` is
      what the dealer pays, ``score2`` is what each other non-dealer
      pays → ``"...{score2}-{score1}点"`` (kodomo-pay/oya-pay).

    Mangan-tier names (満貫/跳満/倍満/三倍満/役満) replace the
    ``<fu>符<han>飜`` prefix when ``mangan_level > 0``.
    """
    # Build the prefix (fu/han block or mangan-tier name).
    if mangan_level > 0:
        prefix = {
            1: "満貫",
            2: "跳満",
            3: "倍満",
            4: "三倍満",
        }.get(mangan_level, "役満")
    else:
        han_disp = max(han, 1)
        prefix = f"{fu}符{han_disp}飜"

    # Build the points body and tsumo marker.
    if not is_tsumo:
        body = f"{score1}点"
    elif is_oya:
        body = f"{score1}点∀"
    else:
        # Non-dealer tsumo: ``X-Y点`` where X = each kodomo pay
        # (``score2``), Y = oya pay (``score1``).  If the recorder
        # didn't expose ``score2`` (legacy XMLs), fall back to a
        # single-value display so the Tenhou regex still matches.
        if score2 > 0:
            body = f"{score2}-{score1}点"
        else:
            body = f"{score1}点∀"
    return prefix + body


def _emit_ryuukyoku_json(hand_json: List[Any], el: ET.Element) -> None:
    """Translate a <RYUUKYOKU> element into the result slot (index 16)."""
    sc_parts = [int(x) for x in el.get("sc", "0,0,0,0,0,0,0,0").split(",")]
    score_changes = [sc_parts[2 * i + 1] for i in range(4)]
    rtype = el.get("type")
    # Tenhou ryu type strings: "yao9","kaze4","reach4","ron3","kan4","nm",
    # or absent for ordinary exhaustive draw → "全員不聴" / "流局".
    label_map = {
        "yao9": "九種九牌",
        "kaze4": "四風連打",
        "reach4": "四家立直",
        "ron3": "三家和了",
        "kan4": "四開槓",
        "nm": "流し満貫",
    }
    label = label_map.get(rtype, "流局")
    hand_json[16] = ["流局", score_changes]
    # Append tenpai-hand info if present (optional for editor display).
    if rtype is None:
        for pid in range(4):
            hai = el.get(f"hai{pid}")
            if hai:
                hand_json[16].append({"hai": [int(x) for x in hai.split(",")]})


__all__ = [
    "xml_to_tenhou_json",
    "xml_string_to_tenhou_json",
    "make_editor_url",
    "make_per_hand_urls",
    "save_tenhou_json",
]
