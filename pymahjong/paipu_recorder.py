"""Tenhou-style paipu recorder for the pymahjong engine.

This module turns a finished :class:`MahjongPyWrapper.Table` (or any object
that exposes the same ``gamelog`` API) into a Tenhou-style XML paipu and
provides a deterministic replayer that uses the embedded RNG seed to
reproduce the exact same yama on replay.

Why a custom seed attribute?
----------------------------

Standard Tenhou paipu store a Tenhou-specific shuffle seed and the
replayer rebuilds the 136-tile wall from it.  The engine in this repo
doesn't use the Tenhou shuffle algorithm by default and the gamelog
exposes ``init_yama`` (84 tiles, post-deal) plus ``init_hands`` (52
tiles, **already sorted**), which loses the original deal order.  The
cleanest deterministic round-trip is therefore to store the engine seed
that was passed to :meth:`Table.set_seed` and call ``set_seed`` +
``game_init_with_config`` again at replay time.

The recorded XML uses the standard Tenhou tag set (``<INIT>``, ``<T>``,
``<D>``, ``<U>``, ``<E>``, ``<V>``, ``<F>``, ``<W>``, ``<G>``, ``<N>``,
``<REACH>``, ``<DORA>``, ``<AGARI>``, ``<RYUUKYOKU>``) so it can be
opened with any Tenhou paipu viewer for visual inspection.  The only
non-standard addition is the ``seed_int`` attribute on ``<INIT>``.

Typical usage::

    import MahjongPyWrapper as pm
    from pymahjong.paipu_recorder import TenhouPaipuRecorder

    recorder = TenhouPaipuRecorder(player_names=["AI0", "AI1", "AI2", "AI3"])

    for hand_idx in range(8):
        seed = base_seed + hand_idx
        env.reset(seed=seed)               # drives Table.set_seed
        while not env.is_over():
            pid = env.get_curr_player_id()
            act = my_policy(env.get_obs(pid))
            env.step(pid, act)
        recorder.record_hand(env.t, seed=seed)

    recorder.save("paipus/selfplay.xml")

To validate a generated paipu::

    from pymahjong.paipu_recorder import replay_recorded_paipu
    n_ok, n_fail = replay_recorded_paipu("paipus/selfplay.xml")
"""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from typing import Iterable, List, Optional, Sequence
from xml.dom import minidom

import MahjongPyWrapper as pm


# ---------------------------------------------------------------------------
# Tile id helpers — Tenhou tile ids are the same 0..135 ids the engine uses.
# ---------------------------------------------------------------------------

# Map LogAction enums that mean "discard" to (is_riichi, is_tsumogiri).
_DISCARD_ACTIONS = {
    pm.LogAction.DiscardFromHand: (False, False),
    pm.LogAction.DiscardFromTsumo: (False, True),
    pm.LogAction.RiichiDiscardFromHand: (True, False),
    pm.LogAction.RiichiDiscardFromTsumo: (True, True),
}

# Tag prefixes for draw / discard events, indexed by player id.
_DRAW_TAGS = "TUVW"
_DISCARD_TAGS = "DEFG"


# ---------------------------------------------------------------------------
# encodem — inverse of pymahjong.tenhou_paipu_check.decodem
# ---------------------------------------------------------------------------


def _encode_naru_log(entry, caller: int, from_who: int) -> int:
    """Encode a naru log entry as a Tenhou ``m`` integer.

    Uses ``entry.action`` (LogAction) plus ``entry.tile`` (called tile)
    and ``entry.call_tiles`` (hand-side tiles) directly, avoiding any
    dependence on player.get_fuuros() ordering.
    """
    action = entry.action
    called_tile = entry.tile  # may be None for AnKan
    hand_tiles = list(entry.call_tiles)
    source_rel = (from_who - caller) % 4

    if action == pm.LogAction.Chi:
        full = sorted(
            hand_tiles + [called_tile],
            key=lambda t: (int(t.tile), t.id),
        )
        called_id = called_tile.id
        which_called = next(i for i, t in enumerate(full) if t.id == called_id)
        start_basetile = int(full[0].tile)
        suit = start_basetile // 9
        start_num = start_basetile % 9
        combo_id = suit * 7 + start_num
        copies = [t.id % 4 for t in full]
        m = 0
        m |= source_rel & 0x3
        m |= 1 << 2
        m |= copies[0] << 3
        m |= copies[1] << 5
        m |= copies[2] << 7
        m |= ((combo_id * 3) + which_called) << 10
        return m

    if action == pm.LogAction.Pon:
        meld = hand_tiles + [called_tile]
        basetile = int(meld[0].tile)
        called_id = called_tile.id
        meld_copies = sorted(t.id % 4 for t in meld)
        all_copies = {0, 1, 2, 3}
        not_in_meld = next(iter(all_copies - set(meld_copies)))
        sorted_meld = sorted(meld, key=lambda t: t.id % 4)
        which_called = next(i for i, t in enumerate(sorted_meld) if t.id == called_id)
        m = 0
        m |= source_rel & 0x3
        m |= 1 << 3
        m |= (not_in_meld & 0x3) << 5
        m |= (basetile * 3 + which_called) << 9
        return m

    if action == pm.LogAction.Kan:
        # Daiminkan: 3 from hand + 1 called.
        any_tile = hand_tiles[0] if hand_tiles else called_tile
        m = 0
        m |= source_rel & 0x3
        m |= (any_tile.id & 0xFF) << 8
        return m

    if action == pm.LogAction.AnKan:
        any_tile = hand_tiles[0]
        m = 0
        m |= (any_tile.id & 0xFF) << 8
        return m

    if action == pm.LogAction.KaKan:
        added = hand_tiles[0] if hand_tiles else called_tile
        basetile = int(added.tile)
        which_copy = added.id % 4
        m = 0
        m |= source_rel & 0x3
        m |= 1 << 4
        m |= (which_copy & 0x3) << 5
        m |= (basetile * 3 + 0) << 9
        return m

    raise ValueError(f"Unknown naru log action: {action}")


def encodem(call_group, caller: int, from_who: int) -> int:
    """Encode a :class:`CallGroup` into the integer ``m`` attribute used by
    Tenhou's ``<N>`` tag.

    Implementation follows the bit layout decoded by
    :func:`pymahjong.tenhou_paipu_check.decodem`.

    Args:
        call_group: the meld (chi/pon/kan).  Must expose ``.type``, ``.tiles``
            (list of :class:`Tile`), and ``.take``.
        caller: player id (0..3) who made the call.
        from_who: player id (0..3) the called tile came from.  For ankan
            this should equal ``caller`` (encoded as source=0).

    Returns:
        the 16-bit integer ``m`` value.
    """
    typ = call_group.type
    take = int(call_group.take)
    tiles = list(call_group.tiles)
    source_rel = (from_who - caller) % 4

    if typ == pm.CallGroupType.Chi:
        # Sort by basetile so positions match Tenhou's canonical chi order.
        sorted_tiles = sorted(tiles, key=lambda t: (int(t.tile), t.id))
        # Find the called tile (the one matching the take position in the
        # original ordering).  The original ``tiles`` list has the called
        # tile at index ``take``.
        called_id = tiles[take].id
        called_basetile = int(tiles[take].tile)
        which_called = next(
            i for i, t in enumerate(sorted_tiles) if t.id == called_id
        )
        start_basetile = int(sorted_tiles[0].tile)
        suit = start_basetile // 9
        start_num = start_basetile % 9
        combo_id = suit * 7 + start_num  # 0..20
        # bits 3-4, 5-6, 7-8 = which of the 4 copies for each member.
        copies = [t.id % 4 for t in sorted_tiles]
        m = 0
        m |= source_rel & 0x3
        m |= 1 << 2  # chi flag
        m |= copies[0] << 3
        m |= copies[1] << 5
        m |= copies[2] << 7
        m |= ((combo_id * 3) + which_called) << 10
        return m

    if typ == pm.CallGroupType.Pon:
        # Three tiles in meld; one of the 4 copies is not used.
        called_id = tiles[take].id
        basetile = int(tiles[take].tile)
        meld_copies = sorted({t.id % 4 for t in tiles})
        all_copies = {0, 1, 2, 3}
        not_in_meld = next(iter(all_copies - set(meld_copies)))
        # which_called: position of called tile within sorted-by-copy meld.
        sorted_meld = sorted(tiles, key=lambda t: t.id % 4)
        which_called = next(
            i for i, t in enumerate(sorted_meld) if t.id == called_id
        )
        m = 0
        m |= source_rel & 0x3
        m |= 1 << 3  # pon flag
        m |= (not_in_meld & 0x3) << 5
        m |= (basetile * 3 + which_called) << 9
        return m

    if typ == pm.CallGroupType.KaKan:
        # Added 4th tile to an existing pon.  ``take`` is the added tile.
        added_tile = tiles[take]
        added_id = added_tile.id
        basetile = int(added_tile.tile)
        which_copy = added_id % 4
        # which_called within the original pon: take % 3 (pon had 3 tiles).
        # In decodem this is read out of bits 9..15 // 3, but only used for
        # display, so reuse 0 (the called tile was the originally-taken pon
        # tile; we don't track that here precisely).
        which_called_pon = take % 3
        m = 0
        m |= source_rel & 0x3
        m |= 1 << 4  # ka-kan flag
        m |= (which_copy & 0x3) << 5
        m |= (basetile * 3 + which_called_pon) << 9
        return m

    if typ == pm.CallGroupType.AnKan:
        # All 4 copies of one basetile.  Source = 0 (self).  ``m`` low byte
        # carries the source (0 for ankan).  bits 8..15 = full id of any
        # one of the 4 tiles (decodem uses bit8_15 → kan_tile_id // 4).
        any_tile = tiles[0]
        m = 0
        m |= 0 & 0x3  # ankan: source = 0
        m |= (any_tile.id & 0xFF) << 8
        return m

    if typ == pm.CallGroupType.DaiMinKan:
        any_tile = tiles[0]
        m = 0
        m |= source_rel & 0x3  # min-kan: relative source != 0
        m |= (any_tile.id & 0xFF) << 8
        return m

    raise ValueError(f"Unknown CallGroup type: {typ}")


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


class TenhouPaipuRecorder:
    """Records a sequence of finished hands as a Tenhou-style XML paipu.

    Each call to :meth:`record_hand` translates the engine's authoritative
    ``table.gamelog`` into ``<INIT>...<AGARI>/<RYUUKYOKU>`` XML elements and
    appends them to an internal buffer.  Call :meth:`save` to flush the
    buffer to disk as a single ``<mjloggm>`` document.

    Args:
        player_names: optional list of 4 display names; defaults to
            ``["AI0", "AI1", "AI2", "AI3"]``.
        lobby: lobby id string, defaults to "0".
        rule_flags: 8-bit Tenhou rule flag (default 0x21 = PVP + special
            table, matches what :func:`pymahjong.tenhou_paipu_check.paipu_replay`
            accepts).
    """

    def __init__(
        self,
        *,
        player_names: Optional[Sequence[str]] = None,
        lobby: str = "0",
        rule_flags: int = 0x21,
    ):
        self.player_names: List[str] = (
            list(player_names) if player_names is not None else
            ["AI0", "AI1", "AI2", "AI3"]
        )
        if len(self.player_names) != 4:
            raise ValueError("player_names must have exactly 4 entries")
        self.lobby = lobby
        self.rule_flags = rule_flags
        self._hand_elements: List[List[ET.Element]] = []  # one list per hand

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def record_hand(self, table, *, seed: Optional[int] = None) -> None:
        """Append events of one finished hand to the recorder buffer.

        Args:
            table: a :class:`MahjongPyWrapper.Table` whose ``get_phase()``
                returns ``GAME_OVER``.
            seed: the integer seed passed to ``Table.set_seed`` before
                ``game_init_with_config``.  If provided, it's embedded in
                the ``<INIT seed_int="...">`` attribute so the paipu can
                be replayed deterministically.
        """
        if int(table.get_phase()) != int(pm.PhaseEnum.GAME_OVER):
            raise RuntimeError(
                f"record_hand requires GAME_OVER phase; got {table.get_phase()}"
            )
        gl = table.gamelog
        elements: List[ET.Element] = []

        # ---- INIT ----
        init_attrs = self._init_attrs(table, gl, seed=seed)
        elements.append(ET.Element("INIT", init_attrs))

        # ---- per-log events ----
        # The first 4 DrawNormal entries in the engine's gamelog correspond
        # to the final round of the initial deal (one tile per player, in
        # oya order — see Table::draw_tenhou_style).  These tiles are
        # already counted in ``init_hands`` and must be skipped, otherwise
        # the recorded XML would duplicate the initial deal as game draws.
        logs = list(gl.logs)
        n_skip = 0
        for entry in logs[:4]:
            if entry.action == pm.LogAction.DrawNormal:
                n_skip += 1
            else:
                break
        if n_skip != 4:
            # Defensive: if the engine ever changes the init protocol,
            # fall back to no skip but warn.
            n_skip = 0
        for entry in logs[n_skip:]:
            ev = self._translate_log(entry, table)
            if ev is None:
                continue
            if isinstance(ev, list):
                elements.extend(ev)
            else:
                elements.append(ev)

        # ---- AGARI / RYUUKYOKU ----
        result_el = self._result_element(table, gl)
        elements.append(result_el)

        self._hand_elements.append(elements)

    def save(self, path: str, *, pretty: bool = False) -> None:
        """Write the accumulated hands to ``path`` as a Tenhou paipu XML.

        Args:
            path: output file path.
            pretty: if True, indent the XML for human readability (much
                larger files).  Default False — compact single-line
                output, matching the canonical Tenhou paipu format.
        """
        root = self._build_root()
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        if pretty:
            rough = ET.tostring(root, encoding="utf-8")
            data = minidom.parseString(rough).toprettyxml(indent="  ", encoding="utf-8")
        else:
            # Compact: <?xml ...?> header + single-line element stream.
            data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
        with open(path, "wb") as f:
            f.write(data)

    def to_string(self) -> str:
        """Return the paipu as a UTF-8 string (no file written)."""
        root = self._build_root()
        return ET.tostring(root, encoding="unicode")

    @property
    def n_hands(self) -> int:
        return len(self._hand_elements)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_root(self) -> ET.Element:
        root = ET.Element("mjloggm", {"ver": "2.3"})
        # SHUFFLE element kept minimal; standard Tenhou parsers ignore it
        # when the seed format isn't recognised, and our replayer uses the
        # per-INIT seed_int attribute instead.
        ET.SubElement(root, "SHUFFLE", {"seed": "pymahjong", "ref": ""})
        ET.SubElement(root, "GO", {
            "type": str(self.rule_flags), "lobby": self.lobby,
        })
        ET.SubElement(root, "UN", {
            "n0": _quote(self.player_names[0]),
            "n1": _quote(self.player_names[1]),
            "n2": _quote(self.player_names[2]),
            "n3": _quote(self.player_names[3]),
            "dan": "0,0,0,0",
            "rate": "1500.00,1500.00,1500.00,1500.00",
            "sx": "C,C,C,C",
        })
        ET.SubElement(root, "TAIKYOKU", {"oya": "0"})
        for hand in self._hand_elements:
            for el in hand:
                root.append(el)
        return root

    def _init_attrs(self, table, gl, *, seed: Optional[int]) -> dict:
        # Tenhou INIT seed = "round,honba,kyoutaku,dice0,dice1,first_dora_id"
        # round = game_wind*4 + (oya - dealer_at_round_start) but for
        # simplicity we use game_wind*4 + oya, which is round-1 = oya for
        # east 1.  This is good enough for replay since the replayer reads
        # ``seed.split(',')[0] // 4`` for wind and ``oya`` from the
        # standalone attribute.
        round_no = int(gl.game_wind) * 4 + gl.oya
        dice0 = 0
        dice1 = 0
        first_dora_id = (
            table.dora_indicator[0].id if len(table.dora_indicator) > 0 else 0
        )
        seed_str = ",".join(str(x) for x in (
            round_no, gl.start_honba, gl.start_kyoutaku, dice0, dice1, first_dora_id,
        ))
        ten_str = ",".join(str(s // 100) for s in gl.start_scores)
        attrs = {
            "seed": seed_str,
            "ten": ten_str,
            "oya": str(gl.oya),
            "hai0": ",".join(str(t.id) for t in gl.init_hands[0]),
            "hai1": ",".join(str(t.id) for t in gl.init_hands[1]),
            "hai2": ",".join(str(t.id) for t in gl.init_hands[2]),
            "hai3": ",".join(str(t.id) for t in gl.init_hands[3]),
        }
        if seed is not None:
            attrs["seed_int"] = str(seed)
        return attrs

    def _translate_log(self, entry, table):
        action = entry.action
        pid = entry.player
        tile = entry.tile

        if action == pm.LogAction.DrawNormal:
            return ET.Element(f"{_DRAW_TAGS[pid]}{tile.id}")
        if action == pm.LogAction.DrawRinshan:
            # Tenhou marks rinshan draws via the preceding kan; the draw
            # itself uses the standard T/U/V/W tag.
            return ET.Element(f"{_DRAW_TAGS[pid]}{tile.id}")

        if action in _DISCARD_ACTIONS:
            is_riichi, _ = _DISCARD_ACTIONS[action]
            if is_riichi:
                # Riichi declaration must precede the discard tile so the
                # replayer knows to call BaseAction.Riichi instead of
                # BaseAction.Discard.  Return a list — _translate_log
                # callers will flatten.
                return [
                    ET.Element("REACH", {"who": str(pid), "step": "1"}),
                    ET.Element(f"{_DISCARD_TAGS[pid]}{tile.id}"),
                ]
            return ET.Element(f"{_DISCARD_TAGS[pid]}{tile.id}")

        if action == pm.LogAction.RiichiSuccess:
            return ET.Element("REACH", {
                "who": str(pid), "step": "2",
                "ten": ",".join(str(s // 100) for s in entry.score),
            })

        if action == pm.LogAction.DoraReveal:
            return ET.Element("DORA", {"hai": str(tile.id)})

        if action in (
            pm.LogAction.Chi, pm.LogAction.Pon, pm.LogAction.Kan,
            pm.LogAction.AnKan, pm.LogAction.KaKan,
        ):
            return self._naru_element(entry, table)

        if action == pm.LogAction.Kyushukyuhai:
            return None

        if action in (pm.LogAction.Ron, pm.LogAction.Tsumo):
            return None

        return None

    def _naru_element(self, entry, table) -> ET.Element:
        """Build a Tenhou ``<N>`` element from a Chi/Pon/Kan log entry.

        Uses the log entry's own ``tile`` (called tile) and ``call_tiles``
        (hand-side tiles) so the encoding doesn't depend on the order of
        ``players[caller].get_fuuros()`` at end-of-game.
        """
        caller = entry.player
        from_who = entry.player2 if entry.player2 != caller else caller
        m = _encode_naru_log(entry, caller, from_who)
        return ET.Element("N", {"who": str(caller), "m": str(m)})

    def _result_element(self, table, gl) -> ET.Element:
        result = gl.result
        rt = result.result_type
        # Prefer ``result.score`` (engine-computed per-hand final scores,
        # populated by GameResult.cpp for every ron / tsumo / ryuukyoku /
        # nagashi-mangan path).  ``table.get_scores()`` reflects the
        # player counters which, in single-hand V4MultiAgentEnv use, may
        # still be at the pre-agari snapshot (with only the riichi-stick
        # deduction applied), so deltas computed from it are wrong for
        # agari hands.  Fall back to ``t.get_scores()`` only when the
        # result struct is uninitialized (rt = Error / -1).
        if int(rt) >= 0:
            final_scores = [int(s) for s in result.score]
        else:
            final_scores = list(table.get_scores())
        score_changes = [
            (final_scores[i] - gl.start_scores[i]) // 100 for i in range(4)
        ]
        sc_parts: List[str] = []
        for i in range(4):
            sc_parts.append(str(gl.start_scores[i] // 100))
            sc_parts.append(str(score_changes[i]))
        sc_str = ",".join(sc_parts)
        n_honba = result.n_honba if int(rt) >= 0 else 0
        n_riichibo = result.n_riichibo if int(rt) >= 0 else 0
        ba_str = f"{n_honba},{n_riichibo}"

        # ----- Agari -----
        if rt in (pm.ResultType.RonAgari, pm.ResultType.TsumoAgari):
            winner = result.winner[0]
            from_who = result.loser[0] if list(result.loser) else winner
            counter = result.results[winner]
            attrs = {
                "who": str(winner),
                "fromWho": str(from_who),
                "ba": ba_str,
                "sc": sc_str,
                "hai": ",".join(str(t.id) for t in table.players[winner].hand),
                "machi": str(
                    table.players[winner].hand[-1].id
                    if len(table.players[winner].hand) > 0 else 0
                ),
                "ten": f"{counter.fu},{counter.score1},0",
                "yaku": ",".join(
                    f"{int(y)},1" for y in counter.yakus
                ),
                "doraHai": ",".join(
                    str(t.id) for t in table.dora_indicator
                ),
            }
            return ET.Element("AGARI", attrs)

        # ----- Ryuukyoku (or any other terminal we treat as draw) -----
        ryu_type_map = {
            pm.ResultType.NoTileRyuuKyoku: None,
            pm.ResultType.NagashiMangan: "nm",
            pm.ResultType.Ryukyouku_Interval_9Hai: "yao9",
            pm.ResultType.Ryukyouku_Interval_4Wind: "kaze4",
            pm.ResultType.Ryukyouku_Interval_4Riichi: "reach4",
            pm.ResultType.Ryukyouku_Interval_4Kan: "kan4",
            pm.ResultType.Ryukyouku_Interval_3Ron: "ron3",
        }
        attrs = {"ba": ba_str, "sc": sc_str}
        ryu_type = ryu_type_map.get(rt, None)
        # Heuristic for result_type=Error (uninitialised): if the last
        # action log is Kyushukyuhai mark as yao9, else leave attr blank
        # (Tenhou treats missing ``type`` as exhaustive draw).
        if int(rt) < 0:
            for entry in reversed(list(gl.logs)):
                if entry.action == pm.LogAction.Kyushukyuhai:
                    ryu_type = "yao9"
                    break
        if ryu_type is not None:
            attrs["type"] = ryu_type
        # Dump tenpai hands for exhaustive draws (Tenhou convention).
        if rt == pm.ResultType.NoTileRyuuKyoku or int(rt) < 0:
            for pid in range(4):
                try:
                    if table.players[pid].is_tenpai():
                        attrs[f"hai{pid}"] = ",".join(
                            str(t.id) for t in table.players[pid].hand
                        )
                except Exception:
                    pass
        return ET.Element("RYUUKYOKU", attrs)


def _quote(name: str) -> str:
    """Tenhou XML player names are URL-encoded; keep ASCII names as-is."""
    try:
        from urllib.parse import quote
        return quote(name, safe="")
    except Exception:
        return name


# ---------------------------------------------------------------------------
# Replayer
# ---------------------------------------------------------------------------


def replay_recorded_paipu(
    xml_path: str,
    *,
    verbose: bool = False,
) -> "tuple[int, int]":
    """Replay a paipu file produced by :class:`TenhouPaipuRecorder`.

    Uses the ``seed_int`` attribute on each ``<INIT>`` to reproduce the
    exact same yama and game flow.  Compares final scores against the
    recorded paipu and counts pass / fail.

    Args:
        xml_path: path to a Tenhou-style paipu XML.
        verbose: print per-hand diagnostics.

    Returns:
        ``(n_passed, n_failed)`` — number of hands whose final scores
        matched and didn't match.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()
    n_ok = 0
    n_fail = 0

    for child in list(root):
        if child.tag != "INIT":
            continue
        seed_int = child.get("seed_int")
        if seed_int is None:
            if verbose:
                print(f"[replay] skipping INIT without seed_int")
            continue
        seed_int = int(seed_int)

        scores = [int(x) * 100 for x in child.get("ten").split(",")]
        seed_parts = child.get("seed").split(",")
        round_no = int(seed_parts[0])
        honba = int(seed_parts[1])
        kyoutaku = int(seed_parts[2])
        oya = int(child.get("oya"))
        game_wind = round_no // 4

        t = pm.Table()
        t.set_seed(seed_int)
        t.game_init_with_config([], scores, kyoutaku, honba, game_wind, oya)

        # Find the AGARI/RYUUKYOKU sibling for this hand to read recorded
        # final scores (used as ground truth).
        idx = list(root).index(child)
        end_el = None
        for sib in list(root)[idx + 1:]:
            if sib.tag == "INIT":
                break
            if sib.tag in ("AGARI", "RYUUKYOKU"):
                end_el = sib
                # Don't break — for double ron we want the *last* sibling.
        if end_el is None:
            n_fail += 1
            if verbose:
                print(f"[replay] no AGARI/RYUUKYOKU after INIT (seed={seed_int})")
            continue

        # The recorded paipu has the engine's own gamelog as ground truth.
        # Re-run the hand with the same seed by replaying recorded actions.
        ok = _replay_one_hand_from_xml(t, child, root, idx, verbose=verbose)
        if ok:
            n_ok += 1
        else:
            n_fail += 1
    return n_ok, n_fail


def _replay_one_hand_from_xml(
    t,
    init_el: ET.Element,
    root: ET.Element,
    init_idx: int,
    *,
    verbose: bool = False,
) -> bool:
    """Replay a single hand by following the recorded action stream.

    Strategy: walk the XML in order, ignoring informational draw events
    (T/U/V/W) since the engine auto-draws.  Before each *decision* event
    (D/E/F/G discard, N naru, REACH riichi), advance the engine through
    any pending response phases by passing for non-callers.
    """
    from pymahjong.tenhou_paipu_check import decodem  # local import to avoid cycle

    GAME_OVER = int(pm.PhaseEnum.GAME_OVER)

    def _advance_to(next_decision_event: Optional[ET.Element]) -> None:
        """Step the engine forward until the next decision matches the
        upcoming XML event.

        - Pass on any response-phase opportunity that isn't the upcoming
          response-style ``<N who=X>`` (Chi/Pon/Min-Kan) for player X.
        - An-Kan and Ka-Kan are self-actions: don't try to call them
          from response phase — always drain responses first.
        - Auto-pass through any forced ``len==1`` decisions.
        - Stop on action phase or when game is over.
        """
        # Pre-decode naru type so we know whether this is a response or
        # a self-action (kakan/ankan).
        naru_who = None
        naru_is_response = False
        if (next_decision_event is not None
                and next_decision_event.tag == "N"):
            naru_who = int(next_decision_event.get("who"))
            try:
                from pymahjong.tenhou_paipu_check import decodem as _dec
                _, _, _ntype, _ = _dec(int(next_decision_event.get("m")), naru_who)
                naru_is_response = _ntype in ("Chi", "Pon", "Min-Kan")
            except Exception:
                naru_is_response = True  # safe default
        for _ in range(64):
            if int(t.get_phase()) == GAME_OVER:
                return
            phase = int(t.get_phase())
            if phase < 4:
                return
            who_now = t.who_make_selection()
            if naru_is_response and naru_who == who_now:
                return
            t.make_selection(0)

    riichi_pending = [False, False, False, False]
    events = list(root)[init_idx + 1:]

    # Find the index of the next decision-worthy event after position i.
    def _next_decision_from(i: int) -> Optional[ET.Element]:
        for j in range(i, len(events)):
            tg = events[j].tag
            if tg in ("INIT",):
                return None
            if tg in ("AGARI", "RYUUKYOKU"):
                return events[j]
            if tg in ("DORA",):
                continue
            if tg and tg[0] in "TUVW" and not events[j].attrib:
                continue  # informational draw
            return events[j]
        return None

    for i, sib in enumerate(events):
        tag = sib.tag
        if tag == "INIT":
            break

        if tag in ("AGARI", "RYUUKYOKU"):
            # Drain pending response phases and trigger the recorded
            # terminal action (ron / tsumo / forced ryuukyoku) so the
            # engine actually computes ``result.score``.
            target_winner = -1
            target_fromwho = -1
            is_tsumo = False
            if tag == "AGARI":
                target_winner = int(sib.get("who"))
                target_fromwho = int(sib.get("fromWho"))
                is_tsumo = (target_winner == target_fromwho)
            for _ in range(12):
                if int(t.get_phase()) == GAME_OVER:
                    break
                phase = int(t.get_phase())
                if tag == "AGARI" and is_tsumo and phase < 4 \
                        and phase == target_winner:
                    # Self-draw win: select Tsumo from the action phase.
                    idx = t.get_selection_from_action_basetile(
                        pm.BaseAction.Tsumo, [], False,
                    )
                    if idx >= 0:
                        t.make_selection(idx)
                        continue
                if tag == "AGARI" and not is_tsumo and phase >= 4 \
                        and t.who_make_selection() == target_winner:
                    # Ron: winner's response phase — pick Ron.
                    idx = t.get_selection_from_action_basetile(
                        pm.BaseAction.Ron, [], False,
                    )
                    if idx >= 0:
                        t.make_selection(idx)
                        continue
                actions = (t.get_self_actions() if phase < 4
                           else t.get_response_actions())
                if len(actions) <= 1:
                    t.make_selection(0)
                elif tag == "RYUUKYOKU" and sib.get("type") == "yao9":
                    idx = t.get_selection_from_action_basetile(
                        pm.BaseAction.Kyushukyuhai, [], False,
                    )
                    if idx >= 0:
                        t.make_selection(idx)
                    else:
                        t.make_selection(0)
                else:
                    # Response phase with options but no XML naru — pass.
                    t.make_selection(0)
            # Validate final scores.
            sc_parts = [int(x) for x in sib.get("sc").split(",")]
            recorded_changes = [sc_parts[2 * i + 1] * 100 for i in range(4)]
            recorded_finals = [
                sc_parts[2 * i] * 100 + recorded_changes[i] for i in range(4)
            ]
            # Use the engine's per-hand ``result.score`` (post-payout)
            # as ground truth.  ``t.get_scores()`` reflects only the
            # ``players[i].score`` field, which is updated for riichi
            # stick deductions but NOT for AGARI payouts (see
            # ``Mahjong/Table.cpp``), so it would falsely fail this
            # comparison for any winning hand.
            res = t.gamelog.result
            if int(res.result_type) >= 0:
                actual_finals = [int(s) for s in res.score]
            else:
                actual_finals = list(t.get_scores())
            if recorded_finals != actual_finals:
                if verbose:
                    print(f"[replay] score mismatch: rec={recorded_finals} "
                          f"vs eng={actual_finals}")
                return False
            return True

        # Skip informational events (engine handles draws / dora reveals).
        if tag and tag[0] in "TUVW" and not sib.attrib:
            continue
        if tag == "DORA":
            continue
        if tag == "REACH" and sib.get("step") == "2":
            continue  # informational (success notification)

        # Decision events: D/E/F/G, N, REACH step=1.
        _advance_to(sib)
        if int(t.get_phase()) == GAME_OVER:
            # Likely a ron triggered during _advance_to; loop to AGARI handler.
            continue

        if tag == "REACH" and sib.get("step") == "1":
            riichi_pending[int(sib.get("who"))] = True
            continue

        if tag and tag[0] in "DEFG" and not sib.attrib:
            pid = "DEFG".index(tag[0])
            tid = int(tag[1:])
            basetile = tid // 4
            use_red = tid in (16, 52, 88)
            if riichi_pending[pid]:
                sel = t.get_selection_from_action_basetile(
                    pm.BaseAction.Riichi, [basetile], use_red,
                )
                riichi_pending[pid] = False
            else:
                sel = t.get_selection_from_action_basetile(
                    pm.BaseAction.Discard, [basetile], use_red,
                )
            if sel < 0:
                if verbose:
                    print(f"[replay] no matching discard {tag} (basetile={basetile} "
                          f"red={use_red}); phase={int(t.get_phase())} "
                          f"actor={t.who_make_selection() if int(t.get_phase()) < 16 else '-'}")
                return False
            t.make_selection(sel)
            continue

        if tag == "N":
            who = int(sib.get("who"))
            m = int(sib.get("m"))
            side_added, hand_removed, naru_type, _ = decodem(m, who)
            action_map = {
                "Chi": pm.BaseAction.Chi,
                "Pon": pm.BaseAction.Pon,
                "Min-Kan": pm.BaseAction.Kan,
                "An-Kan": pm.BaseAction.AnKan,
                "Ka-Kan": pm.BaseAction.KaKan,
            }
            base = action_map.get(naru_type)
            if base is None:
                if verbose:
                    print(f"[replay] unknown naru type {naru_type}")
                return False
            basetiles = [tid // 4 for tid in hand_removed]
            use_red = any(tid in (16, 52, 88) for tid in hand_removed)
            sel = t.get_selection_from_action_basetile(base, basetiles, use_red)
            if sel < 0:
                if verbose:
                    print(f"[replay] no matching naru {naru_type} m={m} "
                          f"basetiles={basetiles} red={use_red} "
                          f"phase={int(t.get_phase())}")
                return False
            t.make_selection(sel)
            continue

        # Unknown tag — skip.
        if verbose:
            print(f"[replay] skipping unknown event <{tag}>")

    return False


__all__ = [
    "TenhouPaipuRecorder",
    "encodem",
    "replay_recorded_paipu",
]
