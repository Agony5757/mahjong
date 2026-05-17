"""Smoke tests for the ``ai_models`` per-seat parameter and ``/api/models``."""
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


def test_list_models_endpoint():
    from fastapi.testclient import TestClient

    from server import app  # noqa: E402

    with TestClient(app) as client:
        r = client.get("/api/models")
        assert r.status_code == 200
        models = r.json().get("models", [])
        assert isinstance(models, list)
        # If the production checkpoint exists, it must be discoverable by name.
        if _MODEL.exists():
            names = [m["name"] for m in models]
            assert "bc_v4.best" in names, names


def test_resolve_model_spec_helpers():
    """Bare names resolve to ``models/{name}.pt``; paths pass through."""
    from server import MODELS_DIR, _resolve_model_spec

    assert _resolve_model_spec(None) is None
    assert _resolve_model_spec("") is None
    assert _resolve_model_spec("random") is None
    assert _resolve_model_spec("RaNdOm") is None
    assert _resolve_model_spec("bc_v4.best") == str(MODELS_DIR / "bc_v4.best.pt")
    # Absolute path passes through.
    assert _resolve_model_spec("/tmp/x.pt") == "/tmp/x.pt"
    # Bare name without slashes but with .pt ext also passes through.
    assert _resolve_model_spec("foo.pt") == "foo.pt"


def test_per_seat_random_via_ai_models():
    """``ai_models=["random"]*4`` should produce a working 4-AI game."""
    from fastapi.testclient import TestClient

    from server import app  # noqa: E402

    with TestClient(app) as client:
        r = client.post("/api/game/new", json={
            "mode": "4ai",
            "max_round": 0,
            "seed": 13,
            "ai_models": ["random", "random", "random", "random"],
        })
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]
        client.post(f"/api/game/{sid}/speed", json={"delay_ms": 0})

        deadline = time.time() + 60
        finished = False
        while time.time() < deadline:
            r = client.get(f"/api/game/{sid}/state")
            if r.status_code == 200:
                if (r.json().get("hansou") or {}).get("finished"):
                    finished = True
                    break
            time.sleep(0.2)
        assert finished


def test_invalid_ai_models_length():
    """``ai_models`` of wrong length must return 400."""
    from fastapi.testclient import TestClient

    from server import app  # noqa: E402

    with TestClient(app) as client:
        r = client.post("/api/game/new", json={
            "mode": "4ai",
            "max_round": 0,
            "ai_models": ["random", "random"],
        })
        assert r.status_code == 400


@pytest.mark.skipif(not _MODEL.exists(), reason="no models/bc_v4.best.pt")
def test_mixed_random_and_bc_v4():
    """One V4 BC AI + three random AIs plays a full tonpuusen."""
    from fastapi.testclient import TestClient

    from server import app  # noqa: E402

    with TestClient(app) as client:
        r = client.post("/api/game/new", json={
            "mode": "4ai",
            "max_round": 0,
            "seed": 99,
            "ai_models": ["bc_v4.best", "random", "random", "random"],
        })
        assert r.status_code == 200, r.text
        sid = r.json()["session_id"]
        client.post(f"/api/game/{sid}/speed", json={"delay_ms": 0})

        deadline = time.time() + 180
        finished = False
        while time.time() < deadline:
            r = client.get(f"/api/game/{sid}/state")
            if r.status_code == 200:
                if (r.json().get("hansou") or {}).get("finished"):
                    finished = True
                    break
            time.sleep(0.2)
        assert finished
