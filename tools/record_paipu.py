#!/usr/bin/env python3
"""Generate Tenhou-style paipu from self-play with a trained policy.

Drives :class:`pymahjong.env_pymahjong.MahjongEnv` with a shared policy
(BC-trained ``EventStreamTransformer`` if ``--bc-model`` is given,
otherwise a uniform-random fallback) and saves the resulting hands as
a Tenhou-style XML paipu via :class:`TenhouPaipuRecorder`.

The generated paipu can be:

* Inspected with any Tenhou XML viewer (uses standard tag names).
* Round-trip validated against the engine via
  :func:`pymahjong.paipu_recorder.replay_recorded_paipu`.

Examples::

    # All-random self-play, 16 hands.
    python tools/record_paipu.py --n-hands 16 --out paipus/random.xml

    # BC self-play (loads bc_v4 transformer with default dims), 32 hands,
    # validate round-trip.
    python tools/record_paipu.py \\
        --bc-model checkpoints/bc_v4_sp.best.pt \\
        --n-hands 32 --seed 2025 \\
        --out paipus/bc_selfplay.xml \\
        --validate
"""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

import MahjongPyWrapper as pm
from pymahjong.env_pymahjong import MahjongEnv
from pymahjong.paipu_recorder import TenhouPaipuRecorder, replay_recorded_paipu


def _random_policy(env: MahjongEnv, rng: random.Random) -> int:
    valid = np.flatnonzero(env.get_valid_actions(nhot=True))
    if len(valid) == 0:
        return 0
    return int(rng.choice(valid.tolist()))


def _build_bc_policy(model_path: str, *, device_str: str, deterministic: bool = True):
    """Return a callable ``policy(env) -> int`` backed by a BC model."""
    try:
        import torch
    except ImportError as e:
        raise RuntimeError("torch is required for --bc-model") from e
    from pymahjong.rl.common.config import TransformerConfig
    from pymahjong.rl.transformer import EventStreamTransformer
    from pymahjong.rl.live_encoder import LiveEncoder

    device = torch.device(device_str)
    # Match the bc_v4.best.pt default dims (192/4/6/4).
    cfg = TransformerConfig()
    model = EventStreamTransformer(config=cfg).to(device)
    ck = torch.load(model_path, map_location=device, weights_only=False)
    state = ck["model"] if isinstance(ck, dict) and "model" in ck else ck
    model.load_state_dict(state)
    model.eval()

    # LiveEncoder needs an external table reference per env.  Bind a
    # fresh encoder for each fresh env via the closure below.
    enc_holder = {"enc": None, "env_id": None}

    @torch.no_grad()
    def _policy(env: MahjongEnv) -> int:
        # Bind a fresh encoder to each fresh hand (env.t is a new Table
        # after env.reset()).
        if enc_holder["env_id"] is not id(env.t):
            enc_holder["env_id"] = id(env.t)
            enc_holder["enc"] = LiveEncoder(env.t)
            enc_holder["enc"].start_hand()
        enc = enc_holder["enc"]
        pid = env.get_curr_player_id()
        try:
            obs = enc.observation_for(pid, register_decide=True, max_seq_len=512)
        except Exception:
            # If anything goes wrong, fall back to a uniform random valid
            # action so the hand can complete.
            valid = np.flatnonzero(env.get_valid_actions(nhot=True))
            return int(valid[0]) if len(valid) else 0
        feat = torch.as_tensor(
            obs["features"], device=device, dtype=torch.float32,
        ).unsqueeze(0)
        attn = torch.as_tensor(
            obs["attention_mask"], device=device, dtype=torch.bool,
        ).unsqueeze(0)
        amask = torch.as_tensor(
            obs["action_mask"], device=device, dtype=torch.bool,
        ).unsqueeze(0)
        # Belt-and-braces: AND with engine's legal-action mask.
        valid = env.get_valid_actions(nhot=True)
        valid_t = torch.as_tensor(valid, device=device, dtype=torch.bool).unsqueeze(0)
        amask = amask & valid_t
        if not amask.any():
            amask = valid_t
        action, _, _ = model.act(feat, attn, amask, deterministic=deterministic)
        return int(action.item())

    return _policy


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True,
                    help="Output XML path.")
    ap.add_argument("--n-hands", type=int, default=8,
                    help="Number of hands to record.")
    ap.add_argument("--seed", type=int, default=0,
                    help="Base seed (hand i uses seed + i).")
    ap.add_argument("--max-steps", type=int, default=2000,
                    help="Safety cap on env steps per hand.")
    ap.add_argument("--bc-model", type=Path, default=None,
                    help="Optional BC checkpoint (.pt).  Without this "
                         "flag the recorder uses a uniform-random policy.")
    ap.add_argument("--device", default=None,
                    help="Torch device for BC model. Default: auto.")
    ap.add_argument("--stochastic", action="store_true",
                    help="Sample actions from the policy distribution "
                         "instead of taking argmax.  Often produces more "
                         "varied (and more often agari) hands.")
    ap.add_argument("--player-names", default="AI0,AI1,AI2,AI3",
                    help="Comma-separated 4 player names for the <UN> tag.")
    ap.add_argument("--validate", action="store_true",
                    help="After saving, replay the generated paipu through "
                         "the engine to verify byte-exact reproducibility.")
    ap.add_argument("--pretty", action="store_true",
                    help="Pretty-print the XML (indented, multi-line).  "
                         "Default is compact single-line output matching "
                         "the canonical Tenhou paipu format.")
    args = ap.parse_args()

    if args.bc_model is not None:
        device_str = (
            args.device
            if args.device is not None
            else ("cuda" if _torch_cuda_available() else "cpu")
        )
        print(f"loading BC model from {args.bc_model} on {device_str}")
        policy_fn = _build_bc_policy(
            str(args.bc_model), device_str=device_str,
            deterministic=not args.stochastic,
        )
        mode = "stochastic" if args.stochastic else "deterministic"
        policy_label = f"bc:{args.bc_model.name}({mode})"
    else:
        rng = random.Random(args.seed)
        def policy_fn(env):
            return _random_policy(env, rng)
        policy_label = "random"

    names = [n.strip() for n in args.player_names.split(",")]
    if len(names) != 4:
        print("ERROR: --player-names must list exactly 4 names", file=sys.stderr)
        return 2
    recorder = TenhouPaipuRecorder(player_names=names)
    env = MahjongEnv()
    n_recorded = 0
    n_truncated = 0
    n_agari = 0

    t0 = time.monotonic()
    for hand_idx in range(args.n_hands):
        seed = args.seed + hand_idx
        try:
            env.reset(seed=seed)
        except Exception as e:
            print(f"hand {hand_idx}: reset failed ({e!r}); skipping")
            continue
        steps = 0
        while not env.is_over() and steps < args.max_steps:
            pid = env.get_curr_player_id()
            try:
                a = policy_fn(env)
            except Exception as e:
                print(f"hand {hand_idx}: policy raised {e!r}; passing")
                a = 0
            try:
                env.step(pid, a)
            except Exception as e:
                # Fall back to first valid action so the hand can finish.
                valid = np.flatnonzero(env.get_valid_actions(nhot=True))
                if len(valid) == 0:
                    break
                env.step(pid, int(valid[0]))
            steps += 1
        over = int(env.t.get_phase()) == int(pm.PhaseEnum.GAME_OVER)
        if not over:
            n_truncated += 1
            continue
        rt = env.t.gamelog.result.result_type
        if rt in (pm.ResultType.RonAgari, pm.ResultType.TsumoAgari):
            n_agari += 1
        try:
            recorder.record_hand(env.t, seed=seed)
            n_recorded += 1
        except Exception as e:
            print(f"hand {hand_idx}: record_hand failed: {e!r}")
    dt = time.monotonic() - t0
    print(f"[{policy_label}] recorded {n_recorded}/{args.n_hands} hands "
          f"(agari={n_agari} truncated={n_truncated}) in {dt:.1f}s")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    recorder.save(str(args.out), pretty=args.pretty)
    size = os.path.getsize(args.out)
    print(f"wrote {args.out} ({size:,} bytes)")

    if args.validate:
        print("validating round-trip...")
        n_ok, n_fail = replay_recorded_paipu(str(args.out), verbose=False)
        print(f"replay: ok={n_ok}  fail={n_fail}")
        if n_fail > 0:
            return 1
    return 0


def _torch_cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
