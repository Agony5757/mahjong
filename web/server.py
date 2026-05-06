"""
Mahjong Web Server — FastAPI backend.

Run: uvicorn server:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from game_manager import GameManager, GameMode, GameSession
from ai_player import create_ai_player, BaseAIPlayer
from verbose_log import configure_root_logging, LOG_DIR

configure_root_logging()
logger = logging.getLogger("mahjong_server")

app = FastAPI(title="Mahjong Web Server", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception as e:
        logger.error(f"!!! {request.method} {request.url.path}: {e}\n{traceback.format_exc()}")
        raise


WEB_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

# ─── Globals ──────────────────────────────────────────────────────────────────
manager = GameManager()

_session_ais: dict[str, list[Optional[BaseAIPlayer]]] = {}
_session_speed: dict[str, float] = {}              # delay in seconds between AI actions
_session_listeners: dict[str, list[asyncio.Queue]] = {}
_session_threads: dict[str, threading.Thread] = {}
_session_event_loops: dict[str, asyncio.AbstractEventLoop] = {}
_lock = threading.Lock()


def _broadcast(session_id: str, event: dict):
    loop = _session_event_loops.get(session_id)
    with _lock:
        queues = list(_session_listeners.get(session_id, []))
    for q in queues:
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(q.put_nowait, event)
        else:
            try:
                q.put_nowait(event)
            except Exception:
                pass


# ─── Models ───────────────────────────────────────────────────────────────────
class NewGameRequest(BaseModel):
    mode: str = "human_ai"           # "human_ai" | "4ai"
    ai_model: Optional[str] = None
    seed: Optional[int] = None
    max_round: int = 1               # 0=tonpuu (East), 1=hansou (East+South), 2=full


class ActionRequest(BaseModel):
    player_id: int
    action_idx: int


class SpeedRequest(BaseModel):
    delay_ms: int = 200


class PaipuStepsRequest(BaseModel):
    xml_content: str


# ─── Hansou loop driver ──────────────────────────────────────────────────────

def _run_one_kyoku(session: GameSession) -> bool:
    """Drive AI players through one kyoku. Returns True if completed normally."""
    sid = session.session_id
    consecutive_errors = 0
    slog = session.logger
    if slog: slog.log("kyoku_loop_start", {"phase": session.adapter.get_phase()})
    while not session.adapter.is_over():
        ais = _session_ais.get(sid, [])
        curr = session.adapter.get_curr_player()
        if curr < 0 or curr >= len(ais):
            if slog: slog.log("kyoku_loop_abort", {"reason": "bad_curr", "curr": curr, "n_ai": len(ais)})
            return False
        ai = ais[curr]
        if ai is None:
            if slog: slog.log("kyoku_loop_pause", {"reason": "human_turn", "curr": curr})
            # Human turn — return so the caller stops driving
            return False
        try:
            valid = session.adapter.get_valid_actions(curr)
            if not valid:
                if slog: slog.log("kyoku_loop_abort", {"reason": "no_valid_actions", "curr": curr,
                                                       "phase": session.adapter.get_phase()})
                return False
            action_idx = ai.select_action(session.adapter, curr)
            if slog: slog.log("ai_select", {"player": curr, "action_idx": action_idx,
                                            "valid": valid, "phase": session.adapter.get_phase()})
            state = session.step(curr, action_idx)
            consecutive_errors = 0
            _broadcast(sid, {
                "type": "ai_action",
                "player": curr,
                "action": action_idx,
                "state": state,
            })
            time.sleep(_session_speed.get(sid, 0.2))
        except Exception as e:
            consecutive_errors += 1
            logger.exception(f"AI step error in {sid}")
            if slog: slog.log_exception("ai_step_error", e, curr=curr, consecutive=consecutive_errors)
            _broadcast(sid, {"type": "error", "message": str(e)})
            if consecutive_errors >= 5:
                if slog: slog.log("kyoku_loop_abort", {"reason": "too_many_errors"})
                _broadcast(sid, {"type": "error", "message": "Too many errors, stopping"})
                return False
            time.sleep(0.3)
    if slog: slog.log("kyoku_loop_end", {"phase": session.adapter.get_phase()})
    return True


def _run_hansou(session: GameSession):
    """Drive a 4-AI session through a full hansou (multi-kyoku loop)."""
    sid = session.session_id
    try:
        while not session.hansou.finished:
            _broadcast(sid, {
                "type": "kyoku_start",
                "kyoku": session.hansou.snapshot(),
                "state": session.get_state(),
            })
            ok = _run_one_kyoku(session)
            if not ok:
                # Either error or paused (human present)
                return
            rec = session.hansou.conclude_current_kyoku()
            _broadcast(sid, {
                "type": "kyoku_end",
                "record": {
                    "index": rec.index,
                    "game_wind": rec.game_wind,
                    "oya": rec.oya,
                    "honba": rec.honba,
                    "kyoutaku_in": rec.kyoutaku_in,
                    "result_type": rec.result_type,
                    "scores_in": rec.scores_in,
                    "scores_out": rec.scores_out,
                    "winner": rec.winner,
                    "loser": rec.loser,
                    "renchan": rec.renchan,
                    "n_honba": rec.n_honba,
                    "n_kyoutaku": rec.n_kyoutaku,
                },
                "state": session.get_state(),
            })
            if session.hansou.finished:
                break
            session.hansou.advance_to_next_kyoku()
        _broadcast(sid, {
            "type": "hansou_end",
            "kyoku_log": [
                {
                    "index": r.index,
                    "result_type": r.result_type,
                    "scores_out": r.scores_out,
                    "winner": r.winner,
                }
                for r in session.hansou.kyoku_log
            ],
            "final_scores": session.hansou.scores,
            "state": session.get_state(),
        })
    except Exception as e:
        logger.exception(f"Hansou loop error in {sid}")
        _broadcast(sid, {"type": "error", "message": f"Hansou loop crashed: {e}"})


def _start_hansou_thread(session: GameSession):
    sid = session.session_id
    t = threading.Thread(target=_run_hansou, args=(session,), daemon=True)
    _session_threads[sid] = t
    t.start()


def _resume_after_human_action(session: GameSession):
    """For human_ai: after the human acts, drive AI until the next human turn or kyoku end."""
    sid = session.session_id
    slog = session.logger
    if slog: slog.log("resume_enter", {"phase": session.adapter.get_phase(),
                                       "curr": session.adapter.get_curr_player()})
    try:
        # Run AI within the current kyoku
        while not session.adapter.is_over():
            curr = session.adapter.get_curr_player()
            if session.mode == GameMode.HUMAN_AI and curr == session.human_player_id:
                if slog: slog.log("resume_pause", {"reason": "human_turn", "curr": curr,
                                                   "phase": session.adapter.get_phase(),
                                                   "valid": session.adapter.get_valid_actions(curr)})
                return  # Wait for human input
            ai = _session_ais.get(sid, [None]*4)[curr]
            if ai is None:
                if slog: slog.log("resume_pause", {"reason": "no_ai", "curr": curr})
                return
            try:
                valid = session.adapter.get_valid_actions(curr)
                action_idx = ai.select_action(session.adapter, curr)
                if slog: slog.log("ai_select", {"player": curr, "action_idx": action_idx,
                                                "valid": valid, "phase": session.adapter.get_phase()})
                state = session.step(curr, action_idx)
                _broadcast(sid, {
                    "type": "ai_action",
                    "player": curr, "action": action_idx, "state": state,
                })
                time.sleep(_session_speed.get(sid, 0.3))
            except Exception as e:
                logger.exception(f"AI step error in {sid}")
                if slog: slog.log_exception("ai_step_error", e, curr=curr)
                _broadcast(sid, {"type": "error", "message": str(e)})
                return

        # Kyoku ended — handle hansou progression
        rec = session.hansou.conclude_current_kyoku()
        _broadcast(sid, {
            "type": "kyoku_end",
            "record": {
                "index": rec.index, "result_type": rec.result_type,
                "scores_in": rec.scores_in, "scores_out": rec.scores_out,
                "winner": rec.winner, "loser": rec.loser,
                "renchan": rec.renchan, "n_honba": rec.n_honba,
                "n_kyoutaku": rec.n_kyoutaku,
            },
            "state": session.get_state(),
        })
        if session.hansou.finished:
            _broadcast(sid, {
                "type": "hansou_end",
                "final_scores": session.hansou.scores,
                "state": session.get_state(),
            })
        else:
            session.hansou.advance_to_next_kyoku()
            _broadcast(sid, {
                "type": "kyoku_start",
                "kyoku": session.hansou.snapshot(),
                "state": session.get_state(),
            })
            # Recursive drive (current oya may be AI)
            _resume_after_human_action(session)
    except Exception as e:
        logger.exception(f"Resume error in {sid}")
        _broadcast(sid, {"type": "error", "message": str(e)})


# ─── HTML routes ─────────────────────────────────────────────────────────────
@app.get("/")
async def root():
    return HTMLResponse((WEB_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/ai_battle")
async def ai_battle():
    return HTMLResponse((WEB_DIR / "ai_battle.html").read_text(encoding="utf-8"))


@app.get("/replay")
async def replay():
    return HTMLResponse((WEB_DIR / "replay.html").read_text(encoding="utf-8"))


# ─── Game session API ────────────────────────────────────────────────────────
@app.post("/api/game/new")
async def new_game(req: NewGameRequest, background_tasks: BackgroundTasks):
    mode = GameMode.HUMAN_AI if req.mode == "human_ai" else GameMode.FOUR_AI
    session = manager.create_session(mode=mode, seed=req.seed, max_round=req.max_round)
    sid = session.session_id

    # AI per seat
    ai_type = "random" if not req.ai_model else "pretrained"
    if mode == GameMode.HUMAN_AI:
        ais = [None] + [create_ai_player(ai_type, req.ai_model) for _ in range(3)]
    else:
        ais = [create_ai_player(ai_type, req.ai_model) for _ in range(4)]
    with _lock:
        _session_ais[sid] = ais
        _session_speed[sid] = 0.2

    if mode == GameMode.FOUR_AI:
        background_tasks.add_task(_start_hansou_thread, session)
    else:
        # If human is not the first to act (oya != 0), drive AI until human turn.
        background_tasks.add_task(_resume_after_human_action, session)

    log_path = None
    if session.logger and session.logger.path is not None:
        log_path = str(session.logger.path)
        logger.info("Session %s verbose log → %s", sid, log_path)

    return {
        "session_id": sid,
        "mode": session.mode.value,
        "state": session.get_state(),
        "log_path": log_path,
        "log_url": f"/api/game/{sid}/log" if log_path else None,
    }


@app.get("/api/game/{session_id}/state")
async def get_state(session_id: str, for_player: Optional[int] = None):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return session.get_state(for_player=for_player)


@app.post("/api/game/{session_id}/action")
async def post_action(session_id: str, req: ActionRequest, background_tasks: BackgroundTasks):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.logger:
        session.logger.log("http_action_in", {"player": req.player_id, "action_idx": req.action_idx})
    try:
        state = session.step(req.player_id, req.action_idx)
    except ValueError as e:
        if session.logger:
            session.logger.log_exception("http_action_value_error", e,
                                         player=req.player_id, action_idx=req.action_idx)
        raise HTTPException(400, str(e))
    background_tasks.add_task(_resume_after_human_action, session)
    return {"ok": True, "state": state}


@app.get("/api/game/{session_id}/log")
async def get_session_log(session_id: str):
    """Download the verbose NDJSON log for a session (useful for bug reports)."""
    session = manager.get_session(session_id)
    if not session or session.logger is None or session.logger.path is None:
        raise HTTPException(404, "Log not available")
    if not session.logger.path.exists():
        raise HTTPException(404, "Log file missing")
    return FileResponse(
        str(session.logger.path),
        media_type="application/x-ndjson",
        filename=session.logger.path.name,
    )


@app.post("/api/game/{session_id}/speed")
async def set_speed(session_id: str, req: SpeedRequest):
    if not manager.get_session(session_id):
        raise HTTPException(404, "Session not found")
    with _lock:
        _session_speed[session_id] = max(0.0, req.delay_ms / 1000.0)
    return {"ok": True, "delay_ms": req.delay_ms}


@app.get("/api/game/{session_id}/events")
async def sse_events(session_id: str):
    session = manager.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    with _lock:
        _session_listeners.setdefault(session_id, []).append(queue)
        _session_event_loops[session_id] = loop

    async def event_generator():
        try:
            # Send the current state immediately so the frontend renders.
            yield {"data": __import__("json").dumps({
                "type": "snapshot",
                "state": session.get_state(),
            })}
            while True:
                evt = await queue.get()
                yield {"data": __import__("json").dumps(evt)}
        except asyncio.CancelledError:
            pass
        finally:
            with _lock:
                if session_id in _session_listeners:
                    try:
                        _session_listeners[session_id].remove(queue)
                    except ValueError:
                        pass
    return EventSourceResponse(event_generator())


@app.delete("/api/game/{session_id}")
async def close_game(session_id: str):
    with _lock:
        _session_ais.pop(session_id, None)
        _session_listeners.pop(session_id, None)
        _session_speed.pop(session_id, None)
        _session_event_loops.pop(session_id, None)
        _session_threads.pop(session_id, None)
    if not manager.close_session(session_id):
        raise HTTPException(404, "Session not found")
    return {"ok": True}


@app.get("/api/sessions")
async def list_sessions():
    return manager.list_sessions()


# ─── Replay API ──────────────────────────────────────────────────────────────
def _paipu_dirs() -> list[Path]:
    repo_root = Path(__file__).parent.parent
    return [repo_root / "paipuxmls", repo_root / "pymahjong" / "paipuxmls"]


@app.get("/api/replay/builtin")
async def list_builtin_paipu():
    files: list[str] = []
    for d in _paipu_dirs():
        if d.exists():
            for f in sorted(d.glob("*.txt"))[:50]:
                files.append(f.name)
            if files:
                break
    return {"paipu_files": files}


@app.get("/api/replay/builtin/{filename}")
async def get_builtin_paipu(filename: str):
    if "/" in filename or ".." in filename:
        raise HTTPException(400, "Invalid filename")
    for d in _paipu_dirs():
        fp = d / filename
        if fp.exists():
            return FileResponse(str(fp), media_type="application/xml")
    raise HTTPException(404, "Paipu file not found")


@app.post("/api/replay/steps")
async def get_paipu_steps(req: PaipuStepsRequest):
    from paipu_replayer import replay_paipu_xml
    try:
        events = replay_paipu_xml(req.xml_content)
    except Exception as e:
        logger.exception("Paipu parse failed")
        raise HTTPException(400, f"Failed to replay paipu: {e}")
    kyoku_set = sorted({e["kyoku_index"] for e in events if e["kyoku_index"] >= 0})
    return {"steps": events, "total": len(events), "kyoku_indices": kyoku_set}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
