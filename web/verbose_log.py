"""
Per-session verbose logging for the mahjong web server.

Each session writes an NDJSON log file under ``web/logs/<session_id>.ndjson``
containing every action, valid-action set, phase transition, AI selection,
and error with traceback. This lets the user reproduce mid-game freezes or
crashes by replaying the recorded actions.

Default behaviour: always on (low overhead). Set ``MAHJONG_VERBOSE_LOG=0`` to
disable file logging entirely.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import traceback
from pathlib import Path
from typing import Any, Optional

LOG_DIR = Path(__file__).parent / "logs"
LOG_ENABLED = os.environ.get("MAHJONG_VERBOSE_LOG", "1") not in ("0", "false", "False", "")

_logger = logging.getLogger("mahjong_server.verbose")


class SessionLogger:
    """Writes NDJSON log entries for one game session.

    Thread-safe (the hansou loop runs on a worker thread while the action
    endpoint runs on the asyncio thread).
    """

    def __init__(self, session_id: str, mode: str, seed: Optional[int], max_round: int):
        self.session_id = session_id
        self._lock = threading.Lock()
        self._fp = None
        self._t0 = time.time()
        if LOG_ENABLED:
            try:
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                self._path = LOG_DIR / f"{session_id}.ndjson"
                self._fp = self._path.open("a", encoding="utf-8")
            except Exception:  # pragma: no cover
                _logger.exception("Failed to open verbose log for %s", session_id)
                self._fp = None
        else:
            self._path = None
        self.log("session_open", {"mode": mode, "seed": seed, "max_round": max_round})

    @property
    def path(self) -> Optional[Path]:
        return self._path

    def log(self, kind: str, payload: dict[str, Any]) -> None:
        rec = {
            "t": round(time.time() - self._t0, 3),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "sid": self.session_id,
            "kind": kind,
            **payload,
        }
        # Mirror to stdlib logger so it shows in console too.
        _logger.debug("[%s] %s %s", self.session_id[:8], kind, payload)
        if self._fp is None:
            return
        try:
            line = json.dumps(rec, ensure_ascii=False, default=str)
            with self._lock:
                self._fp.write(line + "\n")
                self._fp.flush()
        except Exception:  # pragma: no cover
            _logger.exception("Verbose log write failed for %s", self.session_id)

    def log_exception(self, kind: str, exc: BaseException, **extra) -> None:
        self.log(kind, {
            "error": str(exc),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc(),
            **extra,
        })

    def close(self) -> None:
        if self._fp is not None:
            try:
                with self._lock:
                    self.log("session_close", {})
                    self._fp.close()
            except Exception:
                pass
            self._fp = None


def configure_root_logging() -> None:
    """Configure the root logger with a verbose-friendly format and (optionally)
    a file handler. Called once at server startup."""
    level_name = os.environ.get("MAHJONG_LOG_LEVEL", "INFO" if not LOG_ENABLED else "DEBUG").upper()
    level = getattr(logging, level_name, logging.INFO)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    logging.basicConfig(level=level, format=fmt, force=True)
    if LOG_ENABLED:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            fh = logging.FileHandler(LOG_DIR / "server.log", encoding="utf-8")
            fh.setLevel(level)
            fh.setFormatter(logging.Formatter(fmt))
            logging.getLogger().addHandler(fh)
        except Exception:
            logging.getLogger().exception("Could not attach file handler")
