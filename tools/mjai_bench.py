#!/usr/bin/env python3
"""mjai benchmark harness — no docker, all in-process.

Uses ``mjai.mlibriichi.arena.Match`` (which is bundled inside the
``mjai`` pip wheel) to orchestrate a 4-player hanchan.  Each player is a
Python object implementing the ``BaseMjaiLogEngine`` interface:

    class Agent:
        engine_type: str
        name: str
        player_ids: list[int]
        def set_player_ids(self, ids: list[int]) -> None: ...
        def start_game(self, game_idx: int) -> None: ...
        def react_batch(self, game_states: list) -> list[str]: ...
        def end_kyoku(self, game_idx: int) -> None: ...
        def end_game(self, game_idx: int, scores: list[int]) -> None: ...

``react_batch`` is called once per (player, decision).  Each ``game_state``
in the batch carries:
    .game_index : the seat (0..3) — translate via ``self.player_ids[idx]``
    .state      : ``PlayerState`` (libriichi)
    .events_json: JSON string of events the player has not yet processed

The agent returns one mjai-action JSON string per game_state.

This file provides:
- ``BaseAgent`` — minimal implementation (tsumogiri / always pass)
- ``MortalAgent`` — wraps a Mortal-298k checkpoint via Mortal's own
  ResNet + DQN architecture (requires libriichi >= v4 to be importable
  somewhere on sys.path; see ``MORTAL_LIBRIICHI_PATH`` env var)
- ``AkochanAgent`` — runs ``akochan/system.exe`` as a stdio subprocess
  speaking the mjai protocol
- ``V5Agent`` — wraps tools/mjai_bot_v5.py (which uses pm.encv4)

The CLI runs N hanchan in one of two modes:
- ``1v3``: challenger seat 0, champion seats 1-3
- ``3v1``: challenger seats 0-2, champion seat 3
and aggregates rank counts + average score delta.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

# --------------------------------------------------------------------------
# mjai imports
# --------------------------------------------------------------------------

from mjai.mlibriichi.arena import Match  # type: ignore


# ==========================================================================
# Base / debug agents
# ==========================================================================


class BaseAgent:
    """Minimal mjai agent — tsumogiri on draw, always pass on opponent dahai."""

    def __init__(self, name: str = "base") -> None:
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
            state = gs.state
            cans = state.last_cans
            if cans.can_discard:
                tile = state.last_self_tsumo()
                out.append(json.dumps({
                    "type": "dahai", "actor": pid, "pai": tile, "tsumogiri": True,
                }))
            else:
                out.append('{"type":"none"}')
        return out


# ==========================================================================
# Mortal-298k agent  (uses Mortal's own ResNet + DQN)
# ==========================================================================


class MortalAgent:
    """Wraps a Mortal checkpoint.  Loads Mortal's Brain+DQN once, then
    runs inference per decision using PlayerState.encode_obs(version)."""

    def __init__(
        self,
        ckpt_path: Path,
        mortal_repo: Path,
        libriichi_so: Optional[Path] = None,
        device: str = "cuda",
        name: str = "mortal",
    ) -> None:
        import torch
        self.engine_type = "mjai-log"
        self.name = name
        self.player_ids: List[int] = []
        self.device = torch.device(device)

        # Inject Mortal's mortal/ directory onto sys.path so we can import
        # model.Brain + model.DQN. We don't import mortal.engine here because
        # we drive the network ourselves with our own batching.
        sys.path.insert(0, str(mortal_repo / "mortal"))
        if libriichi_so is not None:
            # Make `import libriichi` find the freshly-built .so. The .so
            # has its own state/arena modules independent of mjai.mlibriichi.
            os.environ.setdefault("LIBRIICHI_PATH", str(libriichi_so))
            sys.path.insert(0, str(libriichi_so.parent))
        try:
            from model import Brain, DQN  # type: ignore
            from libriichi.state import PlayerState  # type: ignore
        except ImportError as e:
            raise RuntimeError(f"Failed to import Mortal model/libriichi: {e}")
        self._PlayerState = PlayerState

        # Load checkpoint
        state = torch.load(str(ckpt_path), map_location="cpu", weights_only=False)
        cfg = state["config"]
        self.version = int(cfg["control"].get("version", 1))
        num_blocks = int(cfg["resnet"]["num_blocks"])
        conv_channels = int(cfg["resnet"]["conv_channels"])

        self.brain = Brain(
            version=self.version,
            num_blocks=num_blocks,
            conv_channels=conv_channels,
        ).to(self.device).eval()
        self.dqn = DQN(version=self.version).to(self.device).eval()
        self.brain.load_state_dict(state["mortal"])
        self.dqn.load_state_dict(state["current_dqn"])

        # Per-game state: one PlayerState per game_index (== seat)
        self._states: Dict[int, Any] = {}
        self._buffered_events: Dict[int, List[Dict[str, Any]]] = {}

    def set_player_ids(self, ids: List[int]) -> None:
        self.player_ids = list(ids)

    def start_game(self, game_idx: int) -> None:
        # game_idx is the index within our player_ids list (seat index for this agent)
        # PlayerState wants the absolute player_id (0..3 in the table)
        pid = self.player_ids[game_idx]
        self._states[game_idx] = self._PlayerState(pid)
        self._buffered_events[game_idx] = []

    def end_kyoku(self, game_idx: int) -> None:
        pass  # PlayerState handles end_kyoku via update()

    def end_game(self, game_idx: int, scores: List[int]) -> None:  # noqa: ARG002
        self._states.pop(game_idx, None)
        self._buffered_events.pop(game_idx, None)

    def react_batch(self, game_states: List[Any]) -> List[str]:
        import torch
        # Each game_state has an events_json (events not yet processed by this agent)
        # We feed them one-by-one into our local PlayerState (creating it on
        # start_kyoku if missing), then on the LAST event run inference if we
        # have any legal action to take.
        out: List[str] = []
        # Step 1: update PlayerState for every event in batch
        obs_list: List[np.ndarray] = []
        mask_list: List[np.ndarray] = []
        decisions: List[Tuple[int, Any]] = []  # (game_idx, can) for each item needing action
        for gs in game_states:
            gi = gs.game_index
            if gi not in self._states:
                pid = self.player_ids[gi]
                self._states[gi] = self._PlayerState(pid)
            ps = self._states[gi]
            events = json.loads(gs.events_json)
            cans = None
            for ev in events:
                cans = ps.update(json.dumps(ev, separators=(",", ":")))
            decisions.append((gi, cans))

        # Step 2: encode obs for each decision that has any legal action
        for gi, cans in decisions:
            ps = self._states[gi]
            has_action = (
                cans.can_discard or cans.can_chi_low or cans.can_chi_mid
                or cans.can_chi_high or cans.can_pon or cans.can_daiminkan
                or cans.can_kakan or cans.can_ankan or cans.can_riichi
                or cans.can_tsumo_agari or cans.can_ron_agari
                or cans.can_ryukyoku
            )
            if not has_action:
                out.append('{"type":"none"}')
                continue
            obs, mask = ps.encode_obs(self.version, False)
            obs_list.append(np.asarray(obs, dtype=np.float32))
            mask_list.append(np.asarray(mask, dtype=bool))
            out.append(None)  # type: ignore  # placeholder

        # Step 3: batched inference for the actionable decisions
        if obs_list:
            with torch.inference_mode():
                obs_t = torch.as_tensor(np.stack(obs_list, axis=0), device=self.device)
                mask_t = torch.as_tensor(np.stack(mask_list, axis=0), device=self.device)
                phi = self.brain(obs_t)
                q_out = self.dqn(phi, mask_t)
                actions = q_out.argmax(-1).tolist()
            # Step 4: convert action index -> mjai message via PlayerState helper
            ai = 0
            for i, slot in enumerate(out):
                if slot is None:
                    gi, _cans = decisions[i]
                    ps = self._states[gi]
                    # Use libriichi's action-index-to-mjai helper.
                    mjai_msg = _mortal_action_to_mjai(ps, actions[ai])
                    out[i] = mjai_msg
                    ai += 1
        return out


def _mortal_action_to_mjai(ps: Any, action_idx: int) -> str:
    """Convert Mortal's action-space index to a mjai event JSON string.

    Mortal's action space layout is defined in libriichi/src/consts.rs. The
    upstream Mortal engine has a helper for this; we re-implement the
    minimum here. If libriichi exposes a Python helper, prefer it.
    """
    # Try the libriichi-builtin helper first (Mortal-newest exposes this)
    try:
        from libriichi.tools import action_to_mjai  # type: ignore
        return action_to_mjai(ps, action_idx)
    except Exception:
        pass
    # Fallback: manual.
    # Mortal/upstream layout (post-v3):
    #   0-33: discard tile i
    #   34-36: discard aka 5m/5p/5s
    #   37: chi-low, 38: chi-mid, 39: chi-high
    #   40: pon
    #   41: daiminkan, 42: kakan, 43: ankan
    #   44: riichi, 45: ron, 46: tsumo, 47: ryuukyoku, 48: pass
    # We delegate to PlayerState.brief_info()-style; safest is to use
    # action helper from a build of mortal/engine.py. For now raise.
    raise NotImplementedError(
        f"action_to_mjai unavailable; need libriichi tools.action_to_mjai "
        f"(action_idx={action_idx})"
    )


# ==========================================================================
# Akochan agent  (stdio subprocess speaking mjai protocol)
# ==========================================================================


class AkochanAgent:
    """Spawns akochan/system.exe with mjai-stdin/stdout mode per player."""

    def __init__(self, akochan_dir: Path, name: str = "akochan") -> None:
        self.engine_type = "mjai-log"
        self.name = name
        self.player_ids: List[int] = []
        self.akochan_dir = akochan_dir.resolve()
        self._procs: Dict[int, subprocess.Popen] = {}

    def set_player_ids(self, ids: List[int]) -> None:
        self.player_ids = list(ids)

    def _spawn(self, game_idx: int) -> subprocess.Popen:
        pid = self.player_ids[game_idx]
        # Akochan's mjai mode: `./system.exe mjai <player_id>` (per setup_mjai.json)
        # See critter-mj/akochan/mjai_client.cpp & setup_mjai.json
        cmd = [str(self.akochan_dir / "system.exe"), "mjai", str(pid)]
        env = os.environ.copy()
        env["LD_LIBRARY_PATH"] = str(self.akochan_dir) + ":" + env.get("LD_LIBRARY_PATH", "")
        return subprocess.Popen(
            cmd, cwd=str(self.akochan_dir),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, bufsize=1,
            env=env,
        )

    def start_game(self, game_idx: int) -> None:
        self._procs[game_idx] = self._spawn(game_idx)
        # send start_game event
        ev = json.dumps([{"type": "start_game", "id": self.player_ids[game_idx]}])
        self._procs[game_idx].stdin.write(ev + "\n")  # type: ignore
        self._procs[game_idx].stdin.flush()  # type: ignore
        _ = self._procs[game_idx].stdout.readline()  # type: ignore   # discard "none"

    def end_kyoku(self, game_idx: int) -> None:
        proc = self._procs.get(game_idx)
        if proc is None:
            return
        try:
            proc.stdin.write('[{"type":"end_kyoku"}]\n')  # type: ignore
            proc.stdin.flush()  # type: ignore
            _ = proc.stdout.readline()  # type: ignore
        except Exception:
            pass

    def end_game(self, game_idx: int, scores: List[int]) -> None:  # noqa: ARG002
        proc = self._procs.pop(game_idx, None)
        if proc is None:
            return
        try:
            proc.stdin.write('[{"type":"end_game"}]\n')  # type: ignore
            proc.stdin.flush()  # type: ignore
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

    def react_batch(self, game_states: List[Any]) -> List[str]:
        out: List[str] = []
        for gs in game_states:
            gi = gs.game_index
            proc = self._procs.get(gi)
            if proc is None:
                self.start_game(gi)
                proc = self._procs[gi]
            try:
                proc.stdin.write(gs.events_json.replace("\n", "") + "\n")  # type: ignore
                proc.stdin.flush()  # type: ignore
                line = proc.stdout.readline()  # type: ignore
                out.append(line.strip() or '{"type":"none"}')
            except Exception as e:
                out.append('{"type":"none"}')
                sys.stderr.write(f"akochan error pid={self.player_ids[gi]}: {e}\n")
        return out


# ==========================================================================
# V5 agent  (drives our own pm.encv4 + V5 Douzero model)
# ==========================================================================


class V5Agent:
    """Wraps our V5 (Douzero) BC checkpoint via the V4 token encoder."""

    def __init__(
        self,
        ckpt_path: Path,
        device: str = "cuda",
        name: str = "v5",
        d_model: int = 384, n_heads: int = 8, n_layers: int = 6, ff_mult: int = 4,
        scorer_hidden: int = 256,
    ) -> None:
        import torch
        self.engine_type = "mjai-log"
        self.name = name
        self.player_ids: List[int] = []
        self.device = torch.device(device)

        from pymahjong.rl.common.config import TransformerConfig
        from pymahjong.rl.encoding import EncodingVersion, get_strategy
        cfg = TransformerConfig(d_model=d_model, n_heads=n_heads,
                                 n_layers=n_layers, ff_mult=ff_mult)
        self.model = get_strategy(EncodingVersion.V5).create_model(
            transformer_config=cfg, scorer_hidden=scorer_hidden,
        ).to(self.device).eval()
        ck = torch.load(str(ckpt_path), map_location=self.device, weights_only=False)
        state = ck["model"] if isinstance(ck, dict) and "model" in ck else ck
        self.model.load_state_dict(state)

        # Each game (seat) has its own V5MjaiBot instance — they hold encv4 state
        sys.path.insert(0, str(Path(__file__).parent))
        # Lazy import to keep optional
        try:
            from mjai_bot_v5 import V5MjaiBot  # type: ignore
        except ImportError:
            # Try fallback (script may live in tools/)
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
            from mjai_bot_v5 import V5MjaiBot  # type: ignore
        self._BotCls = V5MjaiBot
        self._ckpt_path = ckpt_path
        self._bots: Dict[int, Any] = {}

    def set_player_ids(self, ids: List[int]) -> None:
        self.player_ids = list(ids)

    def start_game(self, game_idx: int) -> None:
        pid = self.player_ids[game_idx]
        self._bots[game_idx] = self._BotCls(pid, self._ckpt_path, device=str(self.device))

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
                resp = bot.react(gs.events_json)
            except Exception as e:
                sys.stderr.write(f"V5 react error pid={self.player_ids[gi]}: {e}\n")
                resp = None
            out.append(resp or '{"type":"none"}')
        return out


# ==========================================================================
# CLI
# ==========================================================================


def _build_agent(spec: str, args: argparse.Namespace) -> Any:
    """spec is one of: ``v5``, ``mortal``, ``akochan``, ``tsumogiri``."""
    if spec == "tsumogiri":
        return BaseAgent("tsumogiri")
    if spec == "v5":
        return V5Agent(
            ckpt_path=Path(args.v5_ckpt),
            device=args.device, name="v5",
        )
    if spec == "mortal":
        return MortalAgent(
            ckpt_path=Path(args.mortal_ckpt),
            mortal_repo=Path(args.mortal_repo),
            libriichi_so=Path(args.libriichi_so) if args.libriichi_so else None,
            device=args.device, name="mortal",
        )
    if spec == "akochan":
        return AkochanAgent(akochan_dir=Path(args.akochan_dir), name="akochan")
    raise ValueError(f"unknown agent: {spec}")


def to_rank(scores: List[int]) -> List[int]:
    """Tenhou rank: lower index wins ties (起家 ordering)."""
    decorated = [(-(s + 0.4 * (3 - i)), i) for i, s in enumerate(scores)]
    decorated.sort()
    player_idx_by_rank = [i for _, i in decorated]
    rank = [0] * 4
    for r, pi in enumerate(player_idx_by_rank):
        rank[pi] = r + 1
    return rank


def run_bench(args: argparse.Namespace) -> Dict[str, Any]:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build agents (one instance per seat — they hold per-seat state)
    a0 = _build_agent(args.seat0, args)
    a1 = _build_agent(args.seat1, args)
    a2 = _build_agent(args.seat2, args)
    a3 = _build_agent(args.seat3, args)
    for a, ids in zip((a0, a1, a2, a3), ([0], [1], [2], [3])):
        a.set_player_ids(ids)

    rank_counts = np.zeros((4, 4), dtype=np.int64)
    pt_sum = np.zeros(4, dtype=np.float64)
    final_scores_log: List[List[int]] = []
    seeds_log: List[Tuple[int, int]] = []
    seed_key = args.seed_key
    t0 = time.monotonic()

    for hi in range(args.n_hanchan):
        seed = args.seed_start + hi
        match = Match(log_dir=str(out_dir))
        try:
            match.py_match(a0, a1, a2, a3, seed_start=(seed, seed_key))
        except Exception as e:
            sys.stderr.write(f"hanchan {hi} (seed={seed}) error: {e}\n")
            continue
        # After py_match returns, log is in out_dir as a .json.gz
        # Find the most recent log file and parse final scores
        logs = sorted(out_dir.glob("*.json.gz"), key=lambda p: p.stat().st_mtime)
        if not logs:
            continue
        log_path = logs[-1]
        scores = _parse_final_scores(log_path)
        if scores is None:
            continue
        ranks = to_rank(scores)
        for seat in range(4):
            rank_counts[seat][ranks[seat] - 1] += 1
            pt_sum[seat] += scores[seat] - 25000
        final_scores_log.append(scores)
        seeds_log.append((seed, seed_key))
        elapsed = time.monotonic() - t0
        avg_rank = (rank_counts * np.arange(1, 5)).sum(axis=1) / np.maximum(rank_counts.sum(axis=1), 1)
        sys.stderr.write(
            f"[{hi+1}/{args.n_hanchan}] seed={seed} scores={scores} ranks={ranks} "
            f"avg_rank={avg_rank.round(3).tolist()} elapsed={elapsed:.1f}s\n"
        )

    # Final summary
    n = max(1, len(final_scores_log))
    avg_rank = (rank_counts * np.arange(1, 5)).sum(axis=1) / np.maximum(rank_counts.sum(axis=1), 1)
    summary = {
        "n_hanchan": len(final_scores_log),
        "seats": {
            "seat0": args.seat0, "seat1": args.seat1,
            "seat2": args.seat2, "seat3": args.seat3,
        },
        "avg_rank": avg_rank.tolist(),
        "avg_pt_delta": (pt_sum / n).tolist(),
        "rank_counts": rank_counts.tolist(),
        "final_scores": final_scores_log,
        "seeds": seeds_log,
        "wall_time_s": time.monotonic() - t0,
    }
    (out_dir / "bench_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary["seats"], indent=2))
    print(f"avg_rank   = {avg_rank.round(3).tolist()}")
    print(f"avg_pt_d   = {(pt_sum / n).round(1).tolist()}")
    print(f"rank_counts (rows=seats, cols=ranks 1-4):")
    print(rank_counts)
    return summary


def _parse_final_scores(jsonl_gz: Path) -> Optional[List[int]]:
    import gzip
    last_scores = [25000] * 4
    try:
        with gzip.open(jsonl_gz, "rt") as f:
            for line in f:
                ev = json.loads(line)
                if ev.get("type") == "start_kyoku":
                    last_scores = list(ev["scores"])
                deltas = ev.get("deltas")
                if deltas is not None:
                    for i in range(4):
                        last_scores[i] += deltas[i]
    except Exception:
        return None
    return last_scores


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seat0", required=True, help="agent type: v5 | mortal | akochan | tsumogiri")
    ap.add_argument("--seat1", required=True)
    ap.add_argument("--seat2", required=True)
    ap.add_argument("--seat3", required=True)
    ap.add_argument("--n-hanchan", type=int, default=20)
    ap.add_argument("--seed-start", type=int, default=10000)
    ap.add_argument("--seed-key", type=int, default=4242)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--v5-ckpt", default="/data1/home/chenzhaoyun/mahjong/runs/checkpoints/bc_v5_ddp8_3ep_20260603_091834.pt.best")
    ap.add_argument("--mortal-ckpt", default="/data1/home/chenzhaoyun/mahjong/mjai_bench/weights/mortal_298k.pth")
    ap.add_argument("--mortal-repo", default="/data1/home/chenzhaoyun/mahjong/mjai_bench/Mortal")
    ap.add_argument("--libriichi-so", default="/data1/home/chenzhaoyun/mahjong/mjai_bench/Mortal/target/release/libriichi.so")
    ap.add_argument("--akochan-dir", default="/data1/home/chenzhaoyun/mahjong/mjai_bench/akochan")
    args = ap.parse_args()
    run_bench(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
