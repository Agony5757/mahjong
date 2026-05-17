"""Smoke tests for the ``tools/eval_models.py`` AI bench."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_TOOL = _REPO / "tools" / "eval_models.py"
_MODEL = _REPO / "models" / "bc_v4.best.pt"


def _run_tool(args: list, timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_TOOL), *args],
        cwd=str(_REPO),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def test_helpers_resolve_model_spec():
    sys.path.insert(0, str(_REPO / "tools"))
    import eval_models  # noqa: E402

    assert eval_models._resolve_model_spec(None) is None
    assert eval_models._resolve_model_spec("") is None
    assert eval_models._resolve_model_spec("random") is None
    assert eval_models._resolve_model_spec("RaNdOm") is None
    assert eval_models._resolve_model_spec("bc_v4.best") == str(
        eval_models.MODELS_DIR / "bc_v4.best.pt"
    )
    assert eval_models._resolve_model_spec("foo.pt") == "foo.pt"
    assert eval_models._resolve_model_spec("/abs/path/x.pt") == "/abs/path/x.pt"


def test_all_random_4_hands_and_json_summary(tmp_path):
    out = tmp_path / "summary.json"
    cp = _run_tool([
        "--ai", "random", "random", "random", "random",
        "--n", "4",
        "--seed", "0",
        "--out", str(out),
        "--quiet",
    ])
    assert cp.returncode == 0, cp.stderr + "\n" + cp.stdout
    assert out.exists()
    summary = json.loads(out.read_text())
    assert summary["n_hands"] == 4
    assert len(summary["per_seat"]) == 4
    for s in summary["per_seat"]:
        # Sanity bounds: rates ∈ [0, 1].
        for k in ("agari_rate", "deal_in_rate", "rank1_rate"):
            assert 0.0 <= s[k] <= 1.0, (k, s[k])
    # Avg points across seats must sum approximately to zero (zero-sum).
    s = sum(p["avg_score_delta"] for p in summary["per_seat"])
    assert abs(s) < 1e-6, s


def test_bad_spec_returns_nonzero(tmp_path):
    cp = _run_tool([
        "--ai", "definitely_does_not_exist", "random", "random", "random",
        "--n", "1",
    ], timeout=30)
    assert cp.returncode != 0
    assert ("not found" in (cp.stderr + cp.stdout).lower()
            or "FileNotFoundError" in (cp.stderr + cp.stdout))


@pytest.mark.skipif(not _MODEL.exists(), reason="no models/bc_v4.best.pt")
def test_bench_with_real_model(tmp_path):
    """A short run with the real V4 BC checkpoint must complete cleanly."""
    out = tmp_path / "real.json"
    cp = _run_tool([
        "--ai", "bc_v4.best", "random", "random", "random",
        "--n", "4",
        "--seed", "42",
        "--out", str(out),
        "--quiet",
    ], timeout=300)
    assert cp.returncode == 0, cp.stderr + "\n" + cp.stdout
    summary = json.loads(out.read_text())
    assert summary["n_hands"] == 4
    assert summary["ai_specs"][0] == "bc_v4.best"
