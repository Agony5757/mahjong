"""Smoke tests for the web backend.

Run with: pytest web/tests/test_smoke.py
"""
import json
import os
import sys
import time

# Make web/ importable as if cwd were web/ (server.py uses flat imports).
_WEB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _WEB_DIR not in sys.path:
    sys.path.insert(0, _WEB_DIR)

from fastapi.testclient import TestClient

from server import app  # noqa: E402


def test_health():
    with TestClient(app) as client:
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_static_pages():
    with TestClient(app) as client:
        for path in ["/", "/ai_battle", "/replay"]:
            r = client.get(path)
            assert r.status_code == 200, path
            assert "<!DOCTYPE html>" in r.text


def test_4ai_hansou_completes():
    """Run a full hansou and check it terminates with a finished hansou."""
    with TestClient(app) as client:
        r = client.post("/api/game/new", json={
            "mode": "4ai", "max_round": 0, "seed": 42,
        })
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]

        # Set max speed.
        client.post(f"/api/game/{sid}/speed", json={"delay_ms": 0})

        # Poll state until hansou.finished or timeout.
        deadline = time.time() + 90
        finished = False
        last_state = None
        while time.time() < deadline:
            r = client.get(f"/api/game/{sid}/state")
            if r.status_code != 200:
                time.sleep(0.5)
                continue
            last_state = r.json()
            hansou = last_state.get("hansou") or {}
            if hansou.get("finished"):
                finished = True
                break
            time.sleep(0.5)
        assert finished, f"hansou did not finish; last hansou={last_state.get('hansou')}"
        scores = [p["score"] for p in last_state["players"]]
        assert sum(scores) == 100000, f"scores must sum to 100000: {scores}"


def test_replay_steps_from_builtin():
    with TestClient(app) as client:
        r = client.get("/api/replay/builtin")
        assert r.status_code == 200
        files = r.json().get("paipu_files") or []
        if not files:
            return  # paipuxmls dir empty; skip
        name = files[0]
        xml = client.get(f"/api/replay/builtin/{name}").text
        r = client.post("/api/replay/steps", json={"xml_content": xml})
        assert r.status_code == 200, r.text
        steps = r.json()["steps"]
        assert len(steps) > 50
        assert steps[0]["event_type"] == "init"
        assert steps[-1]["event_type"] in ("hansou_end", "kyoku_end")
        # Each step has a state snapshot
        assert "state" in steps[0]
        assert "players" in steps[0]["state"]
