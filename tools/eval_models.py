#!/usr/bin/env python3
"""Benchmark AI players head-to-head over N independent kyoku (hands).

Each "round" is one kyoku: the 4 AI players act until the hand ends,
then we record the final 4 scores, the agari winners, and (for RON) the
dealer-in. After N rounds we report per-seat aggregate metrics:

* avg_score_delta  — mean ``final_score - 25000`` (points won per hand)
* agari_rate       — fraction of hands this seat won (tsumo or ron)
* deal_in_rate     — fraction of hands this seat dealt the winning tile
* rank1_rate       — fraction of hands this seat ended with the strictly
                     highest score (one-hand "win rate")

AI specs reuse the per-seat scheme from the webui:

* ``random`` / empty → :class:`RandomAI`
* bare name like ``bc_v4.best`` → loads ``<repo>/models/{name}.pt`` as
  a V4 ``EventStreamTransformer`` BC checkpoint
* anything with ``/`` or ``.pt`` suffix → used verbatim as the path
* checkpoint files are auto-detected as V4 (``input_proj.weight`` key)
  or legacy ``VLOGMahjong`` (V1 encoding)

Example::

    python tools/eval_models.py \\
        --ai bc_v4.best random bc_v4.best random \\
        --n 200 --seed 17 --workers 1 \\
        --out /tmp/eval.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from collections import Counter
from pathlib import Path
from typing import List, Optional

import numpy as np

_REPO = Path(__file__).resolve().parents[1]
_WEB = _REPO / "web"
sys.path.insert(0, str(_WEB))  # AI players live alongside the webui

from ai_player import BaseAIPlayer, RandomAI, V4ModelAI, _detect_model_kind  # noqa: E402

try:
    import MahjongPyWrapper as pm  # type: ignore
except Exception as e:  # noqa: BLE001
    raise RuntimeError(f"MahjongPyWrapper not importable: {e}")

from pymahjong.env_pymahjong import MahjongEnv  # noqa: E402


MODELS_DIR = _REPO / "models"


def _resolve_model_spec(spec: Optional[str]) -> Optional[str]:
    """Same rules as ``web.server._resolve_model_spec``."""
    if spec is None:
        return None
    s = str(spec).strip()
    if not s or s.lower() == "random":
        return None
    if "/" in s or s.endswith(".pt"):
        return s
    return str(MODELS_DIR / f"{s}.pt")


def _build_ai(spec: Optional[str]) -> BaseAIPlayer:
    path = _resolve_model_spec(spec)
    if path is None:
        return RandomAI()
    if not os.path.exists(path):
        raise FileNotFoundError(f"model not found: {path}")
    kind = _detect_model_kind(path)
    if kind == "v4":
        return V4ModelAI(path)
    # Legacy VLOG checkpoints aren't supported by this bench because they
    # need V1 obs encoding that's hard to thread through here. Reject loudly.
    raise NotImplementedError(
        f"checkpoint {path!r} is not a V4 EventStreamTransformer; only V4 "
        f"BC/PPO models and 'random' are supported by eval_models for now"
    )


class _BenchAdapter:
    """Minimal env wrapper exposing what AI players expect."""

    def __init__(self, env: MahjongEnv):
        self._env = env
        self.t: pm.Table = env.t

    def get_valid_actions_mask(self, player_id: int) -> np.ndarray:
        return np.asarray(self._env.get_valid_actions(nhot=True), dtype=bool)

    def get_valid_actions(self, player_id: int) -> list:
        return [int(x) for x in self._env.get_valid_actions(nhot=False)]


def _play_one_hand(
    ais: List[BaseAIPlayer],
    seed: int,
    safety_limit: int = 4000,
) -> dict:
    """Play exactly one kyoku and return the per-seat result dict."""
    env = MahjongEnv()
    env.reset(seed=seed)
    adapter = _BenchAdapter(env)
    for a in ais:
        a.on_hand_start(adapter)

    for _ in range(safety_limit):
        if env.is_over():
            break
        curr = env.get_curr_player_id()
        action = ais[curr].select_action(adapter, curr)
        env.step(curr, action)
        for a in ais:
            a.on_action_executed(adapter)
    else:
        raise RuntimeError("hand did not terminate within safety limit")

    res = env.t.get_result()
    scores = [int(s) for s in res.score]
    winner_list = []
    if res.winner is not None:
        try:
            winner_list = [int(w) for w in list(res.winner)]
        except TypeError:
            winner_list = [int(res.winner)]
    loser = None
    if res.loser is not None:
        try:
            ll = list(res.loser)
            loser = int(ll[0]) if ll else None
        except TypeError:
            loser = int(res.loser)
    return {
        "scores": scores,
        "deltas": [s - 25000 for s in scores],
        "winners": winner_list,
        "loser": loser,
        "result_type": str(res.result_type).split(".")[-1],
    }


def _aggregate(records: List[dict]) -> dict:
    n = len(records)
    deltas = np.array([r["deltas"] for r in records], dtype=np.float64)
    agari = np.zeros(4, dtype=np.int64)
    deal_in = np.zeros(4, dtype=np.int64)
    rank1 = np.zeros(4, dtype=np.int64)
    result_types = Counter()

    for r in records:
        for w in r["winners"]:
            if 0 <= w < 4:
                agari[w] += 1
        if r["loser"] is not None and 0 <= r["loser"] < 4:
            deal_in[r["loser"]] += 1
        sc = r["scores"]
        top = max(sc)
        if sum(1 for s in sc if s == top) == 1:
            rank1[sc.index(top)] += 1
        result_types[r["result_type"]] += 1

    per_seat = []
    for i in range(4):
        per_seat.append({
            "seat": i,
            "avg_score_delta": float(deltas[:, i].mean()),
            "std_score_delta": float(deltas[:, i].std(ddof=1)) if n > 1 else 0.0,
            "agari_rate": float(agari[i]) / n,
            "deal_in_rate": float(deal_in[i]) / n,
            "rank1_rate": float(rank1[i]) / n,
        })
    return {
        "n_hands": n,
        "per_seat": per_seat,
        "result_types": dict(result_types),
    }


def _print_report(specs: List[str], summary: dict) -> None:
    n = summary["n_hands"]
    print()
    print(f"=== Bench results over {n} hands ===")
    header = f"{'seat':<5} {'ai':<22} {'avg_pts':>10} {'std_pts':>10} {'agari':>8} {'deal_in':>9} {'rank1':>8}"
    print(header)
    print("-" * len(header))
    for s in summary["per_seat"]:
        i = s["seat"]
        print(
            f"P{i:<4} {specs[i]:<22} "
            f"{s['avg_score_delta']:>+10.1f} "
            f"{s['std_score_delta']:>10.1f} "
            f"{s['agari_rate']:>8.3f} "
            f"{s['deal_in_rate']:>9.3f} "
            f"{s['rank1_rate']:>8.3f}"
        )
    print()
    print(f"Result type breakdown: {summary['result_types']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ai", nargs=4, required=True, metavar="SPEC",
                    help="four AI specs for P0/P1/P2/P3 "
                         "(e.g. 'bc_v4.best random bc_v4.best random')")
    ap.add_argument("--n", type=int, default=100, help="number of hands to play")
    ap.add_argument("--seed", type=int, default=0, help="base seed; per-hand seed = seed+i")
    ap.add_argument("--out", type=Path, default=None,
                    help="optional path to write the summary as JSON")
    ap.add_argument("--quiet", action="store_true", help="suppress per-hand progress")
    args = ap.parse_args()

    print(f"Players: P0={args.ai[0]}  P1={args.ai[1]}  P2={args.ai[2]}  P3={args.ai[3]}")
    print(f"Hands:   {args.n}  (seed base {args.seed})")
    print()

    ais = [_build_ai(s) for s in args.ai]

    records: list = []
    t0 = time.monotonic()
    failures = 0
    log_every = max(10, args.n // 20)
    for i in range(args.n):
        try:
            rec = _play_one_hand(ais, seed=args.seed + i)
            records.append(rec)
        except Exception as e:  # noqa: BLE001
            failures += 1
            if not args.quiet:
                print(f"  [{i}] FAILED: {e}", flush=True)
                traceback.print_exc()
        if not args.quiet and (i + 1) % log_every == 0:
            dt = time.monotonic() - t0
            rate = (i + 1) / max(dt, 1e-6)
            eta = (args.n - i - 1) / max(rate, 1e-6)
            print(f"  hand {i + 1}/{args.n}  ({rate:.1f} hand/s, ETA {eta:.0f}s)",
                  flush=True)

    dt = time.monotonic() - t0
    if not records:
        print("All hands failed; aborting.", file=sys.stderr)
        return 2

    summary = _aggregate(records)
    summary["wall_time_s"] = dt
    summary["n_failures"] = failures
    summary["ai_specs"] = list(args.ai)
    summary["seed"] = args.seed

    _print_report(args.ai, summary)
    print()
    print(f"Total wall time: {dt:.1f}s ({len(records) / dt:.1f} hand/s)")
    if failures:
        print(f"WARNING: {failures} hand(s) failed (excluded from aggregates)")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2))
        print(f"summary written to {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
