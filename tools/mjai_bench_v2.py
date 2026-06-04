#!/usr/bin/env python3
"""mjai 4-player benchmark — V5 / Mortal-298k / Tsumogiri, in-process.

Uses ``mjai.mlibriichi.arena.Match`` (mjai protocol layer) to orchestrate
hanchan. Each agent implements the BaseMjaiLogEngine interface
(react_batch + set_player_ids + start_game + end_kyoku + end_game).

Agents:
- ``TsumogiriAgent``: tsumogiri / pass — baseline
- ``MortalAgent``: wraps Mortal's libriichi.mjai.Bot per seat → emits mjai JSON
- ``V5Agent``: wraps our V5MjaiBot per seat (pm.encv4 + V5 Douzero head)
- ``AkochanLegacyAgent``: not yet — use OneVsThree.py_vs_ako directly via separate path

CLI configures one agent type per seat for 1v3 / 3v1 evaluation.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

# Tell Mortal's own libriichi path; this is shadowed when mjai's
# bundled libriichi (mjai.mlibriichi) loads first.
LIBRIICHI_PATH = os.environ.get(
    "LIBRIICHI_PATH",
    "/data1/home/chenzhaoyun/mahjong/mjai_bench/weights",
)
sys.path.insert(0, LIBRIICHI_PATH)

# Mortal repo (for Brain/DQN/MortalEngine imports)
MORTAL_REPO = os.environ.get(
    "MORTAL_REPO", "/data1/home/chenzhaoyun/mahjong/mjai_bench/Mortal"
)
sys.path.insert(0, str(Path(MORTAL_REPO) / "mortal"))

# Our V5 bot
V5_TOOLS_DIR = os.environ.get(
    "V5_TOOLS_DIR", "/data1/home/chenzhaoyun/mahjong/mjai_bench/src"
)
sys.path.insert(0, V5_TOOLS_DIR)

from mjai.mlibriichi.arena import Match  # type: ignore


# ===========================================================================
# Agents
# ===========================================================================


class TsumogiriAgent:
    def __init__(self, name: str = "tsumogiri") -> None:
        self.engine_type = "mjai-log"
        self.name = name
        self.player_ids: List[int] = []

    def set_player_ids(self, ids: List[int]) -> None:
        self.player_ids = list(ids)

    def start_game(self, game_idx: int) -> None:  # noqa: ARG002
        pass

    def end_kyoku(self, game_idx: int) -> None:  # noqa: ARG002
        pass

    def end_game(self, game_idx: int, scores: List[int]) -> None:  # noqa: ARG002
        pass

    def react_batch(self, game_states: List[Any]) -> List[str]:
        out: List[str] = []
        for gs in game_states:
            pid = self.player_ids[gs.game_index]
            cans = gs.state.last_cans
            if cans.can_discard:
                tile = gs.state.last_self_tsumo()
                out.append(json.dumps({
                    "type": "dahai", "actor": pid, "pai": tile, "tsumogiri": True,
                }))
            else:
                out.append('{"type":"none"}')
        return out


class MortalAgent:
    """Wraps Mortal's libriichi.mjai.Bot per seat.

    The Match orchestrator passes us batches of (game_index, state,
    events_json). We replay events to libriichi.mjai.Bot one-by-one (since
    it expects single mjai events), and capture its reaction when it fires.
    """

    def __init__(
        self,
        ckpt_path: str,
        name: str = "mortal-298k",
        device: str = "cuda",
        enable_amp: bool = False,
    ) -> None:
        import torch
        from model import Brain, DQN  # type: ignore
        from engine import MortalEngine  # type: ignore
        from libriichi.mjai import Bot  # type: ignore

        self.engine_type = "mjai-log"
        self.name = name
        self.player_ids: List[int] = []

        state = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        cfg = state["config"]
        version = cfg["control"]["version"]
        brain = Brain(version=version,
                      num_blocks=cfg["resnet"]["num_blocks"],
                      conv_channels=cfg["resnet"]["conv_channels"]).eval()
        dqn = DQN(version=version).eval()
        brain.load_state_dict(state["mortal"])
        dqn.load_state_dict(state["current_dqn"])
        dev = torch.device(device)
        brain = brain.to(dev); dqn = dqn.to(dev)
        self._engine = MortalEngine(
            brain, dqn, version=version, is_oracle=False,
            device=dev, enable_amp=enable_amp,
            enable_quick_eval=True, enable_rule_based_agari_guard=True,
            name=name,
        )
        self._Bot = Bot
        self._bots: Dict[int, Any] = {}

    def set_player_ids(self, ids: List[int]) -> None:
        self.player_ids = list(ids)

    def start_game(self, game_idx: int) -> None:
        pid = self.player_ids[game_idx]
        self._bots[game_idx] = self._Bot(self._engine, pid)

    def end_kyoku(self, game_idx: int) -> None:
        pass

    def end_game(self, game_idx: int, scores: List[int]) -> None:  # noqa: ARG002
        self._bots.pop(game_idx, None)

    def react_batch(self, game_states: List[Any]) -> List[str]:
        out: List[str] = []
        for gs in game_states:
            gi = gs.game_index
            if gi not in self._bots:
                self.start_game(gi)
            bot = self._bots[gi]
            try:
                events = json.loads(gs.events_json)
            except Exception:
                out.append('{"type":"none"}')
                continue
            last_reaction: Optional[str] = None
            for i, ev in enumerate(events):
                ev_json = json.dumps(ev, separators=(",", ":"))
                # All events except the last one should be no-act (we just
                # update state); the last one is where we may need to act.
                if i < len(events) - 1:
                    bot.react(ev_json, can_act=False)
                else:
                    last_reaction = bot.react(ev_json)
            out.append(last_reaction or '{"type":"none"}')
        return out


class V5Agent:
    """Wraps our V5MjaiBot per seat."""

    def __init__(
        self,
        ckpt_path: str,
        name: str = "v5",
        device: str = "cuda",
        d_model: int = 384, n_heads: int = 8, n_layers: int = 6, ff_mult: int = 4,
        scorer_hidden: int = 256,
    ) -> None:
        self.engine_type = "mjai-log"
        self.name = name
        self.player_ids: List[int] = []
        self._ckpt = ckpt_path
        self._device = device
        self._d_model = d_model
        self._n_heads = n_heads
        self._n_layers = n_layers
        self._ff_mult = ff_mult
        self._scorer_hidden = scorer_hidden
        from mjai_bot_v5 import V5MjaiBot  # type: ignore
        self._BotCls = V5MjaiBot
        self._bots: Dict[int, Any] = {}

    def set_player_ids(self, ids: List[int]) -> None:
        self.player_ids = list(ids)

    def start_game(self, game_idx: int) -> None:
        pid = self.player_ids[game_idx]
        self._bots[game_idx] = self._BotCls(
            pid, Path(self._ckpt), device=self._device,
            d_model=self._d_model, n_heads=self._n_heads,
            n_layers=self._n_layers, ff_mult=self._ff_mult,
            scorer_hidden=self._scorer_hidden,
        )

    def end_kyoku(self, game_idx: int) -> None:
        pass

    def end_game(self, game_idx: int, scores: List[int]) -> None:  # noqa: ARG002
        self._bots.pop(game_idx, None)

    def react_batch(self, game_states: List[Any]) -> List[str]:
        out: List[str] = []
        for gs in game_states:
            gi = gs.game_index
            if gi not in self._bots:
                self.start_game(gi)
            try:
                resp = self._bots[gi].react(gs.events_json)
            except Exception as e:  # noqa: BLE001
                sys.stderr.write(f"V5 react err pid={self.player_ids[gi]}: {e}\n")
                resp = None
            out.append(resp or '{"type":"none"}')
        return out


# ===========================================================================
# CLI runner
# ===========================================================================


def build_agent(spec: str, args: argparse.Namespace) -> Any:
    if spec == "tsumogiri":
        return TsumogiriAgent()
    if spec == "v5":
        return V5Agent(
            ckpt_path=args.v5_ckpt, device=args.device,
            d_model=args.v5_d_model, n_heads=args.v5_n_heads,
            n_layers=args.v5_n_layers, ff_mult=args.v5_ff_mult,
            scorer_hidden=args.v5_scorer_hidden,
        )
    if spec == "mortal":
        return MortalAgent(
            ckpt_path=args.mortal_ckpt, device=args.device, enable_amp=args.amp,
        )
    raise ValueError(f"unknown agent: {spec}")


def to_rank(scores: List[int]) -> List[int]:
    # Tenhou-style tie-break: lower seat index wins
    decorated = sorted(((-(s * 4 + (3 - i)), i) for i, s in enumerate(scores)))
    rank = [0] * 4
    for r, (_, i) in enumerate(decorated):
        rank[i] = r + 1
    return rank


def parse_final_scores(jsonl_gz: Path) -> Optional[List[int]]:
    last_scores = [25000] * 4
    seen_any = False
    try:
        with gzip.open(jsonl_gz, "rt") as f:
            for line in f:
                ev = json.loads(line)
                if ev.get("type") == "start_kyoku":
                    last_scores = list(ev["scores"])
                    seen_any = True
                deltas = ev.get("deltas")
                if deltas is not None:
                    for i in range(4):
                        last_scores[i] += deltas[i]
        return last_scores if seen_any else None
    except Exception:
        return None


def run_match_round(
    agents: Tuple[Any, Any, Any, Any],
    seed: int, seed_key: int,
    out_dir: Path,
) -> Optional[List[int]]:
    """Run one hanchan via Match.py_match, return final scores."""
    # Match writes the log to <out_dir>/<random>.json.gz
    pre_logs = set(out_dir.glob("*.json.gz"))
    m = Match(log_dir=str(out_dir))
    try:
        m.py_match(*agents, seed_start=(seed, seed_key))
    except Exception as e:
        sys.stderr.write(f"  match error seed={seed}: {e}\n")
    post_logs = sorted(out_dir.glob("*.json.gz"), key=lambda p: p.stat().st_mtime)
    new_logs = [p for p in post_logs if p not in pre_logs]
    if not new_logs:
        return None
    return parse_final_scores(new_logs[-1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seat0", required=True)
    ap.add_argument("--seat1", required=True)
    ap.add_argument("--seat2", required=True)
    ap.add_argument("--seat3", required=True)
    ap.add_argument("--n-hanchan", type=int, default=20)
    ap.add_argument("--seed-start", type=int, default=10000)
    ap.add_argument("--seed-key", type=int, default=4242)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--amp", action="store_true")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--v5-ckpt",
                    default="/data1/home/chenzhaoyun/mahjong/runs/checkpoints/bc_v5_ddp8_3ep_20260603_091834.pt.best")
    ap.add_argument("--v5-d-model", type=int, default=384)
    ap.add_argument("--v5-n-heads", type=int, default=8)
    ap.add_argument("--v5-n-layers", type=int, default=6)
    ap.add_argument("--v5-ff-mult", type=int, default=4)
    ap.add_argument("--v5-scorer-hidden", type=int, default=256)
    ap.add_argument("--mortal-ckpt",
                    default="/data1/home/chenzhaoyun/mahjong/mjai_bench/weights/mortal_298k.pth")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_dir = out_dir / "mjai_logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    print(f"Building agents: {args.seat0}/{args.seat1}/{args.seat2}/{args.seat3}")
    agents = (
        build_agent(args.seat0, args),
        build_agent(args.seat1, args),
        build_agent(args.seat2, args),
        build_agent(args.seat3, args),
    )
    seat_names = [a.name for a in agents]
    for i, a in enumerate(agents):
        a.set_player_ids([i])

    rank_counts = np.zeros((4, 4), dtype=np.int64)
    pt_sum = np.zeros(4, dtype=np.float64)
    score_log: List[List[int]] = []
    seed_log: List[int] = []
    t0 = time.monotonic()

    for hi in range(args.n_hanchan):
        seed = args.seed_start + hi
        t_h = time.monotonic()
        scores = run_match_round(agents, seed, args.seed_key, log_dir)
        if scores is None:
            sys.stderr.write(f"  hanchan {hi} (seed={seed}) FAILED — no log\n")
            continue
        ranks = to_rank(scores)
        for s in range(4):
            rank_counts[s][ranks[s] - 1] += 1
            pt_sum[s] += scores[s] - 25000
        score_log.append(scores)
        seed_log.append(seed)
        elapsed = time.monotonic() - t0
        avg = (rank_counts * np.arange(1, 5)).sum(axis=1) / np.maximum(rank_counts.sum(axis=1), 1)
        print(
            f"[{hi+1}/{args.n_hanchan}] seed={seed} scores={scores} ranks={ranks} "
            f"avg_rank={avg.round(3).tolist()} t_h={time.monotonic()-t_h:.1f}s total={elapsed:.1f}s",
            flush=True,
        )

    # Final summary
    n = max(1, len(score_log))
    avg_rank = (rank_counts * np.arange(1, 5)).sum(axis=1) / np.maximum(rank_counts.sum(axis=1), 1)
    summary = {
        "n_hanchan": len(score_log),
        "seats": {f"seat{i}": {"agent": getattr(args, f"seat{i}"), "name": seat_names[i]}
                  for i in range(4)},
        "avg_rank": avg_rank.tolist(),
        "avg_pt_delta_vs_25k": (pt_sum / n).tolist(),
        "rank_counts": rank_counts.tolist(),
        "final_scores": score_log,
        "seeds": seed_log,
        "wall_time_s": time.monotonic() - t0,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print()
    print("=" * 70)
    for i in range(4):
        print(f"  seat{i} = {getattr(args, f'seat{i}'):>10s} | name={seat_names[i]}")
    print(f"  N           = {len(score_log)}")
    print(f"  avg_rank    = {avg_rank.round(3).tolist()}")
    print(f"  avg_pt_delta= {(pt_sum / n).round(1).tolist()}")
    print(f"  rank counts (rows=seats, cols=ranks 1-4):")
    print(rank_counts)
    print(f"  wall time   = {time.monotonic() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
