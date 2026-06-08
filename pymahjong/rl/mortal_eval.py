"""Head-to-head evaluation of a checkpoint against the Mortal AI.

This is a thin orchestration layer around the standalone ``mjai_bench_v2``
CLI (the mjai-protocol benchmark harness that pits agents against each
other over full hanchan).  It is intentionally *subprocess-based* and
imports **no torch / mjai / libriichi at module top** so that:

* the heavy ``mjai.mlibriichi`` / Mortal import machinery (which is
  sensitive to import ordering vs our own ``libriichi``) stays isolated
  in a child process and can never destabilise the training process, and
* an eval failure (timeout, OOM, crash, malformed output) is contained:
  the training loop only ever sees a metrics dict with ``failed=1``.

The benchmark harness, the Mortal weights, and the eval interpreter are
all server-specific, so every path is passed in explicitly by the caller
(the Mortal-eval fields were removed along with the legacy PPO trainer).

Two matchups are run, *serially* (never concurrently on the same GPU):

* ``1v3`` — our bot in seat 0, Mortal in seats 1-3.
* ``3v1`` — Mortal in seat 0, our bot in seats 1-3.

For a balanced field the expected average rank is 2.5; ``v5_avg_rank``
below 2.5 means our bot is beating Mortal.
"""
from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Seat layouts for the two matchups and which seat indices hold our bot.
_MATCHUPS: Dict[str, Tuple[List[str], List[int]]] = {
    "1v3": (["v5", "mortal", "mortal", "mortal"], [0]),
    "3v1": (["mortal", "v5", "v5", "v5"], [1, 2, 3]),
}


def _validate_summary(obj: Any) -> Optional[Dict[str, Any]]:
    """Return the summary dict if it matches the expected schema, else None."""
    if not isinstance(obj, dict):
        return None
    try:
        avg_rank = obj["avg_rank"]
        pt_delta = obj["avg_pt_delta_vs_25k"]
        rank_counts = obj["rank_counts"]
    except (KeyError, TypeError):
        return None
    if not (isinstance(avg_rank, list) and len(avg_rank) == 4):
        return None
    if not (isinstance(pt_delta, list) and len(pt_delta) == 4):
        return None
    if not (isinstance(rank_counts, list) and len(rank_counts) == 4
            and all(isinstance(r, list) and len(r) == 4 for r in rank_counts)):
        return None
    if not all(isinstance(x, (int, float)) and math.isfinite(x)
               for x in list(avg_rank) + list(pt_delta)):
        return None
    if sum(sum(r) for r in rank_counts) <= 0:
        return None
    return obj


def _run_one(
    matchup: str,
    seats: List[str],
    *,
    bench_script: str,
    bench_cwd: str,
    eval_python: str,
    ckpt_path: str,
    mortal_ckpt: str,
    out_dir: Path,
    n_hanchan: int,
    d_model: int,
    n_heads: int,
    n_layers: int,
    ff_mult: int,
    scorer_hidden: int,
    seed_start: int,
    seed_key: int,
    device: str,
    amp: bool,
    timeout_sec: float,
    env: Dict[str, str],
) -> Tuple[Optional[Dict[str, Any]], float, bool]:
    """Run a single matchup subprocess. Returns (summary|None, runtime, timed_out)."""
    mdir = out_dir / matchup
    # Remove any stale output so we never read a previous run's summary.
    if mdir.exists():
        import shutil
        shutil.rmtree(mdir, ignore_errors=True)
    mdir.mkdir(parents=True, exist_ok=True)

    cmd = [
        eval_python, bench_script,
        "--seat0", seats[0], "--seat1", seats[1],
        "--seat2", seats[2], "--seat3", seats[3],
        "--n-hanchan", str(n_hanchan),
        "--seed-start", str(seed_start),
        "--seed-key", str(seed_key),
        "--device", device,
        "--v5-ckpt", ckpt_path,
        "--v5-d-model", str(d_model),
        "--v5-n-heads", str(n_heads),
        "--v5-n-layers", str(n_layers),
        "--v5-ff-mult", str(ff_mult),
        "--v5-scorer-hidden", str(scorer_hidden),
        "--mortal-ckpt", mortal_ckpt,
        "--out-dir", str(mdir),
    ]
    if amp:
        cmd.append("--amp")

    t0 = time.monotonic()
    timed_out = False
    try:
        proc = subprocess.Popen(
            cmd, cwd=bench_cwd, env=env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, start_new_session=True,
        )
        try:
            out, _ = proc.communicate(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            timed_out = True
            # Kill the whole process group — the bench may spawn children.
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            out, _ = proc.communicate()
        rc = proc.returncode
    except Exception as e:  # noqa: BLE001
        print(f"[mortal-eval] {matchup} subprocess launch failed: {e!r}", flush=True)
        return None, time.monotonic() - t0, timed_out

    runtime = time.monotonic() - t0
    if timed_out:
        print(f"[mortal-eval] {matchup} TIMEOUT after {runtime:.0f}s", flush=True)
        return None, runtime, True

    def _tail(n: int = 15) -> str:
        return "\n".join((out or "").splitlines()[-n:])

    if rc != 0:
        print(f"[mortal-eval] {matchup} exited rc={rc}; tail:\n{_tail()}", flush=True)
        return None, runtime, False

    summary_path = mdir / "summary.json"
    if not summary_path.exists():
        print(f"[mortal-eval] {matchup} produced no summary.json; tail:\n{_tail()}",
              flush=True)
        return None, runtime, False
    try:
        summary = _validate_summary(json.loads(summary_path.read_text()))
    except Exception as e:  # noqa: BLE001
        print(f"[mortal-eval] {matchup} summary parse failed: {e!r}", flush=True)
        return None, runtime, False
    if summary is None:
        print(f"[mortal-eval] {matchup} summary failed schema validation "
              f"(no valid hanchan?); tail:\n{_tail()}", flush=True)
        return None, runtime, False
    return summary, runtime, False


def _metrics_from_summary(matchup: str, summary: Dict[str, Any]) -> Dict[str, float]:
    """Flatten a validated summary into wandb-friendly scalar metrics."""
    avg_rank = [float(x) for x in summary["avg_rank"]]
    pt_delta = [float(x) for x in summary["avg_pt_delta_vs_25k"]]
    rank_counts = [[int(c) for c in row] for row in summary["rank_counts"]]
    _, v5_seats = _MATCHUPS[matchup]
    p = f"mortal/{matchup}/"
    out: Dict[str, float] = {}

    n = sum(rank_counts[v5_seats[0]]) or 1
    out[p + "n_hanchan"] = float(n)

    top1 = sum(rank_counts[s][0] for s in v5_seats)
    top2 = sum(rank_counts[s][0] + rank_counts[s][1] for s in v5_seats)
    denom = len(v5_seats) * n
    out[p + "v5_avg_rank"] = sum(avg_rank[s] for s in v5_seats) / len(v5_seats)
    out[p + "v5_pt_delta"] = sum(pt_delta[s] for s in v5_seats) / len(v5_seats)
    out[p + "v5_top1_rate"] = top1 / denom
    out[p + "v5_top2_rate"] = top2 / denom

    # Per-seat detail (helps catch seat/dealer bias in the 3v1 layout).
    for s in v5_seats:
        out[p + f"seat{s}_avg_rank"] = avg_rank[s]

    # Reference: the opposing side's average rank.
    opp_seats = [s for s in range(4) if s not in v5_seats]
    if opp_seats:
        out[p + "mortal_avg_rank"] = sum(avg_rank[s] for s in opp_seats) / len(opp_seats)
    return out


def run_mortal_matchups(
    ckpt_path: str,
    *,
    bench_script: str,
    bench_cwd: str,
    mortal_ckpt: str,
    out_dir: str,
    n_hanchan: int = 16,
    d_model: int = 384,
    n_heads: int = 8,
    n_layers: int = 6,
    ff_mult: int = 4,
    scorer_hidden: int = 256,
    eval_python: Optional[str] = None,
    seed_start: int = 10000,
    seed_key: int = 4242,
    device: str = "cuda",
    amp: bool = False,
    timeout_sec: float = 1800.0,
    extra_env: Optional[Dict[str, str]] = None,
) -> Dict[str, float]:
    """Run 1v3 and 3v1 matchups of ``ckpt_path`` vs Mortal, return flat metrics.

    Never raises: any failure is reported via ``mortal/<matchup>/failed`` and
    ``mortal/<matchup>/timeout`` flags so the caller (training loop) is safe.
    """
    eval_python = eval_python or sys.executable
    # The bench runs with cwd=bench_cwd, so any relative path the caller
    # passes (checkpoint, Mortal weights, script) would resolve against the
    # wrong directory and silently break every match.  Absolutise them here.
    bench_script = os.path.abspath(bench_script)
    ckpt_path = os.path.abspath(ckpt_path)
    mortal_ckpt = os.path.abspath(mortal_ckpt)
    out_root = Path(out_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})

    metrics: Dict[str, float] = {}
    for matchup, (seats, _v5_seats) in _MATCHUPS.items():
        summary, runtime, timed_out = _run_one(
            matchup, seats,
            bench_script=bench_script, bench_cwd=bench_cwd,
            eval_python=eval_python, ckpt_path=ckpt_path,
            mortal_ckpt=mortal_ckpt, out_dir=out_root,
            n_hanchan=n_hanchan, d_model=d_model, n_heads=n_heads,
            n_layers=n_layers, ff_mult=ff_mult, scorer_hidden=scorer_hidden,
            seed_start=seed_start, seed_key=seed_key, device=device,
            amp=amp, timeout_sec=timeout_sec, env=env,
        )
        p = f"mortal/{matchup}/"
        metrics[p + "runtime_sec"] = float(runtime)
        metrics[p + "timeout"] = 1.0 if timed_out else 0.0
        if summary is None:
            metrics[p + "failed"] = 1.0
            continue
        metrics[p + "failed"] = 0.0
        metrics.update(_metrics_from_summary(matchup, summary))
    return metrics


__all__ = ["run_mortal_matchups"]
