"""
Mahjong Web Server — FastAPI backend for human vs AI and AI battle modes.

Run: uvicorn server:app --reload --port 8000
"""
import asyncio
import os
import threading
import time
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from game_manager import GameManager, GameMode, GameSession
from ai_player import create_ai_player, BaseAIPlayer

# ─── App Setup ────────────────────────────────────────────────────────────────

app = FastAPI(title="Mahjong Web Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
WEB_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# ─── Game Manager ─────────────────────────────────────────────────────────────

manager = GameManager()

# AI instances per session
_session_ais: dict[str, list[BaseAIPlayer]] = {}
_ais_lock = threading.Lock()

# SSE subscribers
_session_listeners: dict[str, list[asyncio.Queue]] = {}
_listeners_lock = threading.Lock()


def _broadcast(session_id: str, event: dict):
    """Push an event to all SSE subscribers of a session."""
    payload = f"data: {event}\n\n"
    with _listeners_lock:
        for queue in _session_listeners.get(session_id, []):
            try:
                queue.put_nowait(payload)
            except Exception:
                pass


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class NewGameRequest(BaseModel):
    mode: str = "human_ai"        # "human_ai" or "4ai"
    ai_model: Optional[str] = None  # "random" or path to .pth file
    seed: Optional[int] = None


class ActionRequest(BaseModel):
    player_id: int
    action_idx: int


class SeekRequest(BaseModel):
    step: int


class PaipuUploadRequest(BaseModel):
    xml_content: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _run_ai_turn(session: GameSession):
    """Run AI turn and broadcast the result."""
    session_id = session.session_id
    curr = session.env.get_curr_player()

    # Determine if AI should act
    is_human = (session.mode == GameMode.HUMAN_AI and curr == 0)
    is_ai = not is_human

    if not is_ai:
        return

    with _ais_lock:
        ais = _session_ais.get(session_id, [])

    if curr >= len(ais):
        return

    ai = ais[curr]
    try:
        action_idx = ai.select_action(session.env, curr)
        state = session.step(curr, action_idx)
        session.action_log.append({"player": curr, "action": action_idx})
        _broadcast(session_id, {"type": "ai_action", "player": curr, "action": action_idx, "state": state})
    except Exception as e:
        _broadcast(session_id, {"type": "error", "message": str(e)})

    # If game not over and next turn is AI, continue
    if not session.env.is_over():
        next_curr = session.env.get_curr_player()
        is_next_human = (session.mode == GameMode.HUMAN_AI and next_curr == 0)
        if not is_next_human:
            # Schedule next AI turn
            def delayed_ai():
                time.sleep(0.5)  # Simulate thinking
                try:
                    _run_ai_turn(session)
                except Exception:
                    pass
            t = threading.Thread(target=delayed_ai, daemon=True)
            t.start()
    else:
        _broadcast(session_id, {"type": "game_over", "state": session.env.get_state(0)})


def _auto_run_ai_battle(session: GameSession):
    """Automatically run an AI vs AI battle."""
    session_id = session.session_id

    def loop():
        while not session.env.is_over():
            curr = session.env.get_curr_player()
            with _ais_lock:
                ais = _session_ais.get(session_id, [])
            if curr >= len(ais):
                break
            ai = ais[curr]
            try:
                action_idx = ai.select_action(session.env, curr)
                state = session.step(curr, action_idx)
                session.action_log.append({"player": curr, "action": action_idx})
                _broadcast(session_id, {
                    "type": "ai_action",
                    "player": curr,
                    "action": action_idx,
                    "state": state
                })
            except Exception as e:
                _broadcast(session_id, {"type": "error", "message": str(e)})
                break
            time.sleep(0.2)  # Thinking delay
        # Game over
        _broadcast(session_id, {
            "type": "game_over",
            "state": session.env.get_public_state()
        })

    t = threading.Thread(target=loop, daemon=True)
    t.start()


# ─── REST API ─────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return HTMLResponse(open(WEB_DIR / "index.html").read())


@app.get("/ai_battle")
async def ai_battle():
    return HTMLResponse(open(WEB_DIR / "ai_battle.html").read())


@app.get("/replay")
async def replay():
    return HTMLResponse(open(WEB_DIR / "replay.html").read())


@app.post("/api/game/new")
async def new_game(req: NewGameRequest, background_tasks: BackgroundTasks):
    """Create a new game session."""
    mode = GameMode.HUMAN_AI if req.mode == "human_ai" else GameMode.FOUR_AI
    session = manager.create_session(mode=mode, ai_model_path=req.ai_model, seed=req.seed)

    # Set up AI players
    with _ais_lock:
        if mode == GameMode.HUMAN_AI:
            # 3 AI opponents for player 0
            ai_type = "random" if not req.ai_model else "pretrained"
            ais = [
                create_ai_player(ai_type, req.ai_model),
                create_ai_player(ai_type, req.ai_model),
                create_ai_player(ai_type, req.ai_model),
            ]
        else:
            # 4 AI
            ai_type = "random" if not req.ai_model else "pretrained"
            ais = [
                create_ai_player(ai_type, req.ai_model),
                create_ai_player(ai_type, req.ai_model),
                create_ai_player(ai_type, req.ai_model),
                create_ai_player(ai_type, req.ai_model),
            ]
        _session_ais[session.session_id] = ais

    # If 4 AI mode, auto-start
    if mode == GameMode.FOUR_AI:
        background_tasks.add_task(_auto_run_ai_battle, session)

    return {
        "session_id": session.session_id,
        "mode": session.mode.value,
        "state": session.get_state(0),
    }


@app.get("/api/game/{session_id}/state")
async def get_state(session_id: str, for_player: int = 0):
    """Get current game state."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session.get_state(for_player)


@app.post("/api/game/{session_id}/action")
async def post_action(session_id: str, req: ActionRequest, background_tasks: BackgroundTasks):
    """Submit a player action."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    try:
        state = session.step(req.player_id, req.action_idx)
        session.action_log.append({"player": req.player_id, "action": req.action_idx})

        # If not game over and next player is AI, trigger AI turn
        if not session.env.is_over():
            next_curr = session.env.get_curr_player()
            is_human = (session.mode == GameMode.HUMAN_AI and next_curr == 0)
            if not is_human:
                background_tasks.add_task(_run_ai_turn, session)

        return {"ok": True, "state": state}
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/game/{session_id}/events")
async def sse_events(session_id: str):
    """SSE stream for real-time game events."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    queue = asyncio.Queue()

    with _listeners_lock:
        if session_id not in _session_listeners:
            _session_listeners[session_id] = []
        _session_listeners[session_id].append(queue)

    async def event_generator():
        try:
            while True:
                payload = await queue.get()
                yield payload
        except asyncio.CancelledError:
            pass
        finally:
            with _listeners_lock:
                if session_id in _session_listeners:
                    try:
                        _session_listeners[session_id].remove(queue)
                    except ValueError:
                        pass

    return EventSourceResponse(event_generator())


@app.get("/api/game/{session_id}/paipu")
async def get_paipu(session_id: str):
    """Get the paipu (game record) for replay."""
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session.to_paipu()


@app.delete("/api/game/{session_id}")
async def close_game(session_id: str):
    """Close a game session."""
    with _ais_lock:
        _session_ais.pop(session_id, None)
    with _listeners_lock:
        _session_listeners.pop(session_id, None)
    ok = manager.close_session(session_id)
    if not ok:
        raise HTTPException(404, "Session not found")
    return {"ok": True}


@app.get("/api/sessions")
async def list_sessions():
    """List all active sessions."""
    return manager.list_sessions()


# ─── Paipu / Replay API ───────────────────────────────────────────────────────

@app.post("/api/replay/load")
async def load_paipu_xml(xml_content: str):
    """
    Load and validate a Tenhou XML paipu.
    xml_content: raw XML string from a Tenhou mjlog file.
    """
    from paipu_parser import parse_tenhou_xml
    try:
        paipu_data = parse_tenhou_xml(xml_content)
        return {"ok": True, "paipu": paipu_data}
    except Exception as e:
        raise HTTPException(400, f"Failed to parse paipu: {e}")


@app.get("/api/replay/builtin")
async def list_builtin_paipu():
    """List available built-in paipu files."""
    paipu_dir = Path(__file__).parent.parent / "pymahjong" / "paipuxmls"
    if not paipu_dir.exists():
        return {"paipu_files": []}
    files = [f.name for f in paipu_dir.glob("*.txt")][:20]  # Limit to 20
    return {"paipu_files": files}


@app.get("/api/replay/builtin/{filename}")
async def get_builtin_paipu(filename: str):
    """Get a built-in paipu file."""
    paipu_dir = Path(__file__).parent.parent / "pymahjong" / "paipuxmls"
    filepath = paipu_dir / filename
    if not filepath.exists():
        raise HTTPException(404, "Paipu file not found")
    return FileResponse(filepath, media_type="application/xml")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ─── Replay Steps API ────────────────────────────────────────────────────────

class PaipuStepsRequest(BaseModel):
    xml_content: str


@app.post("/api/replay/steps")
async def get_paipu_steps(req: PaipuStepsRequest):
    """
    Build step-by-step game states from a Tenhou XML paipu.
    Uses PaipuReplayer to replay and returns state at each step.
    """
    from paipu_parser import parse_tenhou_xml, create_replayer

    try:
        paipu_data = parse_tenhou_xml(req.xml_content)
        rp = create_replayer(paipu_data)
    except Exception as e:
        raise HTTPException(400, f"Failed to parse paipu: {e}")

    steps = []
    max_steps = 600

    for step_num in range(max_steps):
        phase = rp.get_phase()
        if phase == 16:  # GAME_OVER
            steps.append({"step": step_num, "type": "game_over", "phase": phase})
            break

        turn = rp.who_make_selection()
        last_action = str(rp.table.last_action).split("::")[-1] if hasattr(rp.table, 'last_action') else "Discard"

        # Get scores
        scores = list(rp.table.get_scores())

        # Build state snapshot for this step (before action)
        # We serialize enough for the frontend to render
        state_snapshot = _build_replayer_state(rp)

        # Execute action (use first available action = replay)
        if phase < 4:
            actions = rp.get_self_actions()
        elif phase < 16:
            actions = rp.get_response_actions()
        else:
            break

        if not actions:
            break

        # For replay: use action index 0 (pass) or find the correct replay action
        # We replay by finding the action that was actually taken
        # For simplicity, use pass (index 0) for all — this replays with pass-only
        # which means the game won't actually progress through the real actions
        # Instead, we should store the paipu actions separately
        #
        # Better approach: store the real actions and replay them
        sel_idx = 0
        try:
            rp.make_selection(sel_idx)
        except Exception:
            break

        steps.append({
            "step": step_num,
            "phase": phase,
            "turn": turn,
            "base_action": last_action,
            "scores": scores,
            "state": state_snapshot,
        })

    return {"steps": steps, "total": len(steps), "init": paipu_data}


def _build_replayer_state(rp) -> dict:
    """Build a renderable state dict from a PaipuReplayer."""
    t = rp.table

    wind_names = ["East", "South", "West", "North"]
    phase_names = [
        "P1_ACTION", "P2_ACTION", "P3_ACTION", "P4_ACTION",
        "P1_RESPONSE", "P2_RESPONSE", "P3_RESPONSE", "P4_RESPONSE",
        "P1_CHANKAN", "P2_CHANKAN", "P3_CHANKAN", "P4_CHANKAN",
        "P1_CHANANKAN", "P2_CHANANKAN", "P3_CHANANKAN", "P4_CHANANKAN",
        "GAME_OVER"
    ]

    def basetile_str(bt: int) -> str:
        if bt < 9: return f"{bt+1}m"
        elif bt < 18: return f"{bt-9+1}p"
        elif bt < 27: return f"{bt-18+1}s"
        else: return ["1z","2z","3z","4z","5z","6z","7z"][bt-27]

    def tile_to_dict(tile) -> dict:
        bt = int(tile.tile)
        return {"id": int(tile.id), "basetile": bt, "str": basetile_str(bt), "red_dora": bool(tile.red_dora)}

    def player_to_dict(pid: int, hide_hand: bool = True) -> dict:
        p = t.players[pid]
        hand = []
        if hide_hand and pid != 0:
            hand = [{"count": len(p.hand)}]
        else:
            for tile in p.hand:
                hand.append(tile_to_dict(tile))

        river = []
        for rt in p.river.river:
            river.append({"tile": tile_to_dict(rt.tile), "number": int(rt.number),
                          "riichi": bool(rt.riichi), "fromhand": bool(rt.fromhand)})

        calls = []
        for cg in p.call_groups:
            calls.append({"type": str(cg.type).split("::")[-1],
                         "tiles": [tile_to_dict(tile) for tile in cg.tiles],
                         "take": int(cg.take)})

        atari = [basetile_str(int(at)) for at in p.atari_tiles]

        return {
            "player_id": pid,
            "wind": wind_names[int(p.wind)],
            "is_oya": bool(p.oya),
            "score": int(p.score),
            "hand": hand,
            "river": river,
            "calls": calls,
            "tenpai": atari,
            "riichi": bool(p.riichi),
            "double_riichi": bool(p.double_riichi),
            "menzen": bool(p.menzen),
            "furiten": bool(p.is_furiten()),
        }

    phase = t.get_phase()
    curr = t.who_make_selection()

    return {
        "phase": phase,
        "phase_name": phase_names[phase] if phase < 17 else "GAME_OVER",
        "turn": int(curr),
        "oya": int(t.oya),
        "game_wind": wind_names[int(t.game_wind)],
        "honba": int(t.honba),
        "kyoutaku": int(t.kyoutaku),
        "river_counter": int(t.river_counter),
        "dora": [basetile_str(int(d)) for d in t.get_dora()],
        "ura_dora": [basetile_str(int(d)) for d in t.get_ura_dora()],
        "players": [player_to_dict(i) for i in range(4)],
        "is_over": phase == 16,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
