"""End-to-end smoke test: V4 BC model plays a kyoku via the webui API.

Skipped automatically if ``models/bc_v4.best.pt`` is missing.
"""
import os
import sys
import time
from pathlib import Path

import pytest

_WEB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WEB_DIR not in sys.path:
    sys.path.insert(0, _WEB_DIR)

_REPO = Path(__file__).resolve().parents[2]
_MODEL = _REPO / "models" / "bc_v4.best.pt"


@pytest.mark.skipif(not _MODEL.exists(), reason="no models/bc_v4.best.pt checkpoint")
def test_v4_bc_model_plays_4ai_hansou():
    from fastapi.testclient import TestClient

    from server import app  # noqa: E402

    with TestClient(app) as client:
        r = client.post("/api/game/new", json={
            "mode": "4ai",
            "max_round": 0,
            "seed": 7,
            "ai_model": str(_MODEL),
        })
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]

        client.post(f"/api/game/{sid}/speed", json={"delay_ms": 0})

        deadline = time.time() + 180
        finished = False
        last_state = None
        while time.time() < deadline:
            r = client.get(f"/api/game/{sid}/state")
            if r.status_code != 200:
                time.sleep(0.5)
                continue
            last_state = r.json()
            hansou = (last_state or {}).get("hansou") or {}
            if hansou.get("finished"):
                finished = True
                break
            time.sleep(0.2)

        assert finished, f"hansou did not finish in time; last state: {last_state}"
        log = (last_state or {}).get("hansou", {}).get("log", []) or []
        # At least one kyoku in the log.
        assert len(log) >= 1, log
