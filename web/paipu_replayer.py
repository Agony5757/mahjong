"""
Real Tenhou paipu (XML mjlog) replayer for the web UI.

Drives ``mp.PaipuReplayer`` action-by-action using the same logic as
``pymahjong.tenhou_paipu_check.PaipuReplay._paipu_replay`` but emits a
``StepEvent`` (with a renderable state snapshot) at every meaningful
event. The frontend displays one event per timeline step.

Multiple kyoku in a single XML are supported — the replayer is rebuilt
on each ``<INIT>``.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Iterator, Optional

import MahjongPyWrapper as mp
from pymahjong.tenhou_paipu_check import (
    decodem,
    get_tile_from_id,
    get_tiles_from_id,
)


_WIND_NAMES = ("East", "South", "West", "North")
_PHASE_NAMES = (
    "P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION",
    "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE", "P4_RESPONSE",
    "P1_CHANKAN", "P2_CHANKAN", "P3_CHANKAN", "P4_CHANKAN",
    "P1_CHANANKAN", "P2_CHANANKAN", "P3_CHANANKAN", "P4_CHANANKAN",
    "GAME_OVER",
)


def _basetile_str(bt: int) -> str:
    if bt < 9:
        return f"{bt + 1}m"
    if bt < 18:
        return f"{bt - 9 + 1}p"
    if bt < 27:
        return f"{bt - 18 + 1}s"
    return ("1z", "2z", "3z", "4z", "5z", "6z", "7z")[bt - 27]


def _tile_dict(tile) -> dict:
    bt = int(tile.tile)
    return {
        "id": int(tile.id),
        "basetile": bt,
        "str": _basetile_str(bt),
        "red_dora": bool(tile.red_dora),
    }


def _player_dict(t, pid: int) -> dict:
    p = t.players[pid]
    river = []
    for rt in p.get_river().river:
        river.append({
            "tile": _tile_dict(rt.tile),
            "number": int(rt.number),
            "riichi": bool(rt.riichi),
            "fromhand": bool(rt.fromhand),
        })
    calls = []
    for cg in p.get_fuuros():
        try:
            type_str = mp.CallGroupToString(cg)
        except Exception:
            type_str = "Unknown"
        calls.append({
            "type": type_str,
            "tiles": [_tile_dict(x) for x in cg.tiles],
            "take": int(cg.take),
        })
    return {
        "player_id": pid,
        "wind": _WIND_NAMES[int(p.wind)],
        "is_oya": bool(p.oya),
        "score": int(p.score),
        "hand": [_tile_dict(x) for x in p.hand],
        "river": river,
        "calls": calls,
        "tenpai": [_basetile_str(int(at)) for at in p.atari_tiles],
        "riichi": bool(p.riichi),
        "double_riichi": bool(p.double_riichi),
        "menzen": bool(p.menzen),
        "furiten": bool(p.is_furiten()),
    }


def _snapshot(t) -> dict:
    phase = int(t.get_phase())
    return {
        "phase": phase,
        "phase_name": _PHASE_NAMES[phase] if phase < len(_PHASE_NAMES) else "GAME_OVER",
        "turn": int(t.who_make_selection()) if phase < 16 else -1,
        "oya": int(t.oya),
        "game_wind": _WIND_NAMES[int(t.game_wind)],
        "honba": int(t.honba),
        "kyoutaku": int(t.riichibo),
        "tiles_left": int(t.get_remain_tile()),
        "dora": [_basetile_str(int(d)) for d in t.get_dora()],
        "ura_dora": [_basetile_str(int(d)) for d in t.get_ura_dora()],
        "players": [_player_dict(t, i) for i in range(4)],
        "is_over": phase == 16,
    }


@dataclass
class StepEvent:
    step: int
    event_type: str   # init|draw|discard|call|riichi|agari|ryuukyoku|kyoku_end
    kyoku_index: int  # 0..15 (wind*4 + oya kyoku #)
    player: int
    description: str
    state: dict


def replay_paipu_xml(xml_content: str) -> list[dict]:
    """Replay a Tenhou XML paipu, returning a list of step events."""
    root = ET.fromstring(xml_content)
    events: list[StepEvent] = []
    step = 0

    replayer: Optional[mp.PaipuReplayer] = None
    riichi_status = False
    after_kan = False
    kyoku_index = -1
    scores: list[int] = []

    def emit(event_type: str, player: int, descr: str):
        nonlocal step
        if replayer is None:
            return
        events.append(StepEvent(
            step=step,
            event_type=event_type,
            kyoku_index=kyoku_index,
            player=player,
            description=descr,
            state=_snapshot(replayer.table),
        ))
        step += 1

    children = list(root)
    for child_no, child in enumerate(children):
        tag = child.tag
        if tag == "SHUFFLE":
            seed_str = child.get("seed", "")
            prefix = "mt19937ar-sha512-n288-base64,"
            if seed_str.startswith(prefix):
                mp.TenhouShuffle.instance().init(seed_str[len(prefix):])

        elif tag == "INIT":
            riichi_status = False
            after_kan = False
            scores_str = child.get("ten").split(",")
            scores = [int(t) * 100 for t in scores_str]
            oya_id = int(child.get("oya"))
            seed_parts = child.get("seed").split(",")
            game_order = int(seed_parts[0])
            honba = int(seed_parts[1])
            riichi_sticks = int(seed_parts[2])
            kyoku_index = game_order

            yama = mp.TenhouShuffle.instance().generate_yama()
            replayer = mp.PaipuReplayer()
            replayer.init(yama, scores, riichi_sticks, honba, game_order // 4, oya_id)

            wind_label = ("东", "南", "西", "北")[game_order // 4]
            kyoku_no = (game_order % 4) + 1
            descr = f"{wind_label}{kyoku_no}局 {honba}本场 (供托 {riichi_sticks})"
            emit("init", oya_id, descr)

        elif tag == "DORA":
            # Engine reveals dora automatically on Kan; nothing to drive.
            emit("dora", -1, f"翻 DORA: {get_tile_from_id(int(child.get('hai')))}")

        elif tag == "REACH":
            player_id = int(child.get("who"))
            step_attr = int(child.get("step"))
            if step_attr == 1:
                riichi_status = True
                emit("riichi", player_id, f"P{player_id} 宣言立直")
            else:
                riichi_status = False
                # The riichi stick is paid by the engine when the discard succeeds.

        elif tag and tag[0] in "TUVW" and child.attrib == {}:
            player_id = "TUVW".find(tag[0])
            obtained = int(tag[1:])
            if after_kan:
                after_kan = False
            else:
                # Auto-pass any pending response phase from the previous discard.
                if not (child_no - 1 < 0 or children[child_no - 1].tag == "INIT"):
                    for _ in range(4):
                        try:
                            replayer.make_selection(0)
                        except Exception:
                            break
            emit("draw", player_id, f"P{player_id} 摸 {get_tile_from_id(obtained)}")

        elif tag and tag[0] in "DEFG" and child.attrib == {}:
            player_id = "DEFG".find(tag[0])
            discarded = int(tag[1:])
            if riichi_status:
                sel = replayer.get_selection_from_action(mp.BaseAction.Riichi, [discarded])
                replayer.make_selection(sel)
            else:
                sel = replayer.get_selection_from_action(mp.BaseAction.Discard, [discarded])
                replayer.make_selection(sel)
            emit("discard", player_id, f"P{player_id} 弃 {get_tile_from_id(discarded)}")

        elif tag == "N":
            naru_player = int(child.get("who"))
            m = int(child.get("m"))
            side, hand_removed, naru_type, opened = decodem(m, naru_player)
            action_types = {
                "Chi": mp.BaseAction.Chi,
                "Pon": mp.BaseAction.Pon,
                "Min-Kan": mp.BaseAction.Kan,
                "An-Kan": mp.BaseAction.AnKan,
                "Ka-Kan": mp.BaseAction.KaKan,
            }
            response_types = {"Chi", "Pon", "Min-Kan"}
            if naru_type == "Min-Kan":
                after_kan = True
            for i in range(4):
                if replayer.get_phase() > int(mp.PhaseEnum.P4_ACTION):
                    if i != naru_player:
                        try:
                            replayer.make_selection(0)
                        except Exception:
                            pass
                if i == naru_player:
                    sel = replayer.get_selection_from_action(action_types[naru_type], hand_removed)
                    replayer.make_selection(sel)
                    if naru_type not in response_types:
                        break
            emit("call", naru_player, f"P{naru_player} {naru_type}: {get_tiles_from_id(hand_removed)}")

        elif tag == "BYE":
            emit("bye", int(child.get("who")), f"P{child.get('who')} 掉线")

        elif tag in ("RYUUKYOKU", "AGARI"):
            if tag == "RYUUKYOKU":
                rtype = child.get("type")
                if rtype == "yao9":
                    try:
                        replayer.make_selection(14)
                    except Exception:
                        pass
                    descr = "九种九牌流局"
                elif rtype == "ron3":
                    descr = "三家和了流局"
                else:
                    for _ in range(4):
                        try:
                            replayer.make_selection(0)
                        except Exception:
                            break
                    descr = "流局"
                emit("ryuukyoku", -1, descr)
            else:  # AGARI
                who = int(child.get("who"))
                from_who = int(child.get("fromWho"))
                # Drive the engine: tsumo if self, ron otherwise (and any double ron downstream).
                who_agari = [who]
                if (child_no + 1 < len(children) and
                        children[child_no + 1].tag == "AGARI"):
                    who_agari.append(int(children[child_no + 1].get("who")))
                for i in range(4):
                    phase = replayer.get_phase()
                    if phase <= int(mp.PhaseEnum.P4_ACTION):
                        sel = replayer.get_selection_from_action(mp.BaseAction.Tsumo, [])
                        replayer.make_selection(sel)
                        break
                    else:
                        if i not in who_agari:
                            try:
                                replayer.make_selection(0)
                            except Exception:
                                pass
                        else:
                            if phase <= int(mp.PhaseEnum.P4_RESPONSE):
                                sel = replayer.get_selection_from_action(mp.BaseAction.Ron, [])
                            elif phase <= int(mp.PhaseEnum.P4_chankan):
                                sel = replayer.get_selection_from_action(mp.BaseAction.ChanKan, [])
                            else:
                                sel = replayer.get_selection_from_action(mp.BaseAction.ChanAnKan, [])
                            replayer.make_selection(sel)
                if from_who == who:
                    descr = f"P{who} 自摸"
                else:
                    descr = f"P{who} 荣和 (from P{from_who})"
                emit("agari", who, descr)

            # Mark kyoku end
            if not (child_no + 1 < len(children) and children[child_no + 1].tag == "AGARI"):
                emit("kyoku_end", -1, f"第 {kyoku_index + 1} 局结束")

    # Final hansou-end marker
    if events:
        events.append(StepEvent(
            step=step,
            event_type="hansou_end",
            kyoku_index=kyoku_index,
            player=-1,
            description="牌谱播放结束",
            state=events[-1].state,
        ))

    return [
        {
            "step": e.step,
            "event_type": e.event_type,
            "kyoku_index": e.kyoku_index,
            "player": e.player,
            "description": e.description,
            "state": e.state,
        }
        for e in events
    ]
