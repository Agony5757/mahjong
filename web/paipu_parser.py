"""
Paipu parser — reuses logic from pymahjong/tenhou_paipu_check.py.
Supports Tenhou XML paipu format and converts to PaipuReplayer format.
"""
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

import MahjongPyWrapper as pm


# ─── Tile ID utilities (from tenhou_paipu_check.py) ───────────────────────────

def tenhou_id_to_basetile(tile_id: int) -> int:
    """Convert Tenhou tile ID (0-135) to BaseTile (0-33)."""
    return tile_id // 4


def tenhou_id_to_copy_index(tile_id: int) -> int:
    """Convert Tenhou tile ID to copy index (0-3)."""
    return tile_id % 4


def decodem(m: int) -> dict:
    """
    Decode the <N who="N" m="NNNN"> tag's m parameter.
    Returns dict with 'type', 'called_tile', and 'called_from'.
    Based on tenhou_paipu_check.py implementation.
    """
    # m is a 16-bit integer encoding call type and tiles
    call_type = m & 0x3  # bits 0-1
    called = (m >> 2) & 0x3F  # bits 2-7: called tile basetile
    consumed = (m >> 8) & 0xFF  # bits 8-15: consumed tiles

    type_names = {0: "Chi", 1: "Pon", 2: "Kan", 3: "AnKan"}
    return {
        "type": type_names.get(call_type, "Unknown"),
        "called_tile": called,
        "consumed_tiles": consumed
    }


def parse_tenhou_xml(xml_content: str) -> dict:
    """
    Parse a Tenhou XML paipu string and return game initialization data.
    This can be used to create a PaipuReplayer.

    Returns:
        dict with keys: yama, init_scores, kyoutaku, honba, game_wind, oya
    """
    from MahjongPyWrapper import TenhouShuffle

    root = ET.fromstring(xml_content)

    # Find SHOWER seed
    shower = root.find("SHOWER")
    if shower is None:
        raise ValueError("No <SHOWER> tag found in paipu")

    seed = shower.get("seed", "")

    # Find INIT tag
    init = root.find("INIT")
    if init is None:
        raise ValueError("No <INIT> tag found in paipu")

    # Scores
    ten_str = init.get("ten", "25000,25000,25000,25000")
    scores = [int(s) for s in ten_str.split(",")]

    # Oya
    oya = int(init.get("oya", "0"))

    # Game wind from seed
    seed_parts = init.get("seed", "").split(",")
    game_order = int(seed_parts[0]) if seed_parts else 0
    game_wind = game_order // 4  # 0=East, 1=South, 2=West, 3=North

    # Honba / kyoutaku
    honba = int(seed_parts[1]) if len(seed_parts) > 1 else 0
    kyoutaku = int(seed_parts[2]) if len(seed_parts) > 2 else 0

    # Generate yama from seed
    TenhouShuffle.instance().init(seed)
    yama = list(TenhouShuffle.instance().generate_yama())

    return {
        "yama": yama,
        "init_scores": scores,
        "oya": oya,
        "game_wind": game_wind,
        "honba": honba,
        "kyoutaku": kyoutaku,
    }


def load_paipu_file(filepath: str) -> dict:
    """Load a Tenhou XML file and parse it."""
    with open(filepath, "r", encoding="utf-8") as f:
        xml_content = f.read()
    return parse_tenhou_xml(xml_content)


def create_replayer(paipu_data: dict) -> pm.PaipuReplayer:
    """Create a PaipuReplayer from paipu data."""
    rp = pm.PaipuReplayer()
    rp.init(
        yama=paipu_data["yama"],
        init_scores=paipu_data["init_scores"],
        kyoutaku=paipu_data["kyoutaku"],
        honba=paipu_data["honba"],
        game_wind=paipu_data["game_wind"],
        oya=paipu_data["oya"],
    )
    return rp


def replay_paipu_steps(xml_content: str) -> list[dict]:
    """
    Replay a Tenhou XML paipu and return the step-by-step state.
    Returns a list of game states at each step.
    """
    paipu_data = parse_tenhou_xml(xml_content)
    rp = create_replayer(paipu_data)

    steps = []
    step_num = 0
    max_steps = 500  # Safety limit

    while step_num < max_steps:
        phase = rp.get_phase()
        if phase == 16:  # GAME_OVER
            break

        if phase < 4:
            actions = rp.get_self_actions()
        elif phase < 16:
            actions = rp.get_response_actions()
        else:
            break

        # For replay, we replay the first available action (assuming valid paipu)
        if not actions:
            break

        # Take first valid action (pass if available, otherwise first)
        action_indices = [i for i in range(len(actions))]
        sel_idx = action_indices[0] if len(action_indices) > 0 else 0

        state = {
            "step": step_num,
            "phase": phase,
            "turn": rp.who_make_selection(),
            "n_actions": len(actions),
            "selected": sel_idx,
        }
        steps.append(state)

        try:
            rp.make_selection(sel_idx)
        except Exception as e:
            steps.append({"error": str(e)})
            break

        step_num += 1

    return steps


def paipu_to_game_log(xml_content: str) -> dict:
    """
    Parse a Tenhou XML paipu and return a structured game log.
    Returns actions in a frontend-friendly format.
    """
    paipu_data = parse_tenhou_xml(xml_content)
    rp = create_replayer(paipu_data)

    actions = []
    step_num = 0
    max_steps = 500

    while step_num < max_steps:
        phase = rp.get_phase()
        if phase == 16:
            result = rp.get_result()
            actions.append({"step": step_num, "type": "game_over", "phase": phase})
            break

        if phase < 4:
            curr_actions = rp.get_self_actions()
            action_type = "self"
        elif phase < 16:
            curr_actions = rp.get_response_actions()
            action_type = "response"
        else:
            break

        if not curr_actions:
            break

        sel_idx = 0
        try:
            rp.make_selection(sel_idx)
        except Exception:
            break

        # Build action description
        t = rp.table
        player = t.who_make_selection()
        last_action = str(t.last_action).split("::")[-1] if hasattr(t, "last_action") else "Unknown"

        actions.append({
            "step": step_num,
            "phase": phase,
            "player": player,
            "action_type": action_type,
            "base_action": last_action,
            "scores": list(t.get_scores()),
        })
        step_num += 1

    return {
        "init": paipu_data,
        "actions": actions,
        "total_steps": step_num,
    }
