#!/usr/bin/env python3
"""Evaluate a V4 checkpoint by 4-seat shared self-play over many hands.

For each hand:
  * runs deterministic self-play with all 4 seats using the same model
  * records the hand as a Tenhou-style XML paipu + Tenhou paipu-editor URL
  * tracks per-hand agari / tsumo / ron / ryuukyoku / payoffs

At the end, prints aggregate statistics and writes a JSON summary.

Example::

    python tools/eval_selfplay_paipus.py \\
        --model checkpoints/ppo_v4_split.pt --split-heads \\
        --n-hands 100 --seed-base 0 \\
        --out-dir logs/ppo_selfplay_100 \\
        --summary-json logs/ppo_selfplay_100/summary.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch

import MahjongPyWrapper as pm
from pymahjong.paipu_recorder import TenhouPaipuRecorder
from pymahjong.paipu_tenhou_json import make_editor_url, xml_to_tenhou_json
from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.env import MultiAgentEnv
from pymahjong.rl.transformer import EventStreamTransformer


def _load_model(
    path: str,
    *,
    device: torch.device,
    cfg: TransformerConfig,
    split_heads: bool,
) -> EventStreamTransformer:
    model = EventStreamTransformer(config=cfg, split_heads=split_heads).to(device)
    ck = torch.load(path, map_location=device, weights_only=False)
    state = ck["model"] if isinstance(ck, dict) and "model" in ck else ck
    model.load_state_dict(state)
    model.eval()
    return model


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True,
                    help="Checkpoint .pt to evaluate.")
    ap.add_argument("--split-heads", action="store_true",
                    help="Must match the ckpt's training-time setting.")
    ap.add_argument("--n-hands", type=int, default=100)
    ap.add_argument("--seed-base", type=int, default=0,
                    help="Hand i uses seed = seed-base + i.")
    ap.add_argument("--max-seq-len", type=int, default=512)
    ap.add_argument("--stochastic", action="store_true",
                    help="Sample actions instead of argmax.")
    ap.add_argument("--max-steps", type=int, default=2000,
                    help="Per-hand safety cap on decisions.")
    ap.add_argument("--out-dir", type=Path, required=True,
                    help="Dir to write per-hand {hand_NNN.xml, .url.txt}.")
    ap.add_argument("--summary-json", type=Path, default=None,
                    help="Optional aggregate JSON summary.")
    ap.add_argument("--player-names", default="P0,P1,P2,P3")
    ap.add_argument("--device", default=None)
    args = ap.parse_args()

    device = torch.device(
        args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    )
    print(f"loading {args.model} on {device}  split_heads={args.split_heads}")
    model = _load_model(
        str(args.model), device=device,
        cfg=TransformerConfig(),  # 192/4/6/4 defaults
        split_heads=args.split_heads,
    )

    names = [n.strip() for n in args.player_names.split(",")]
    assert len(names) == 4, "--player-names must list 4 names"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    # Consolidated per-hand URL list (one URL per line).
    all_urls_path = args.out_dir / "hand_urls.txt"
    all_urls_fh = all_urls_path.open("w", encoding="utf-8")

    # Aggregate counters.
    n_played = 0
    n_truncated = 0
    n_agari = 0
    n_tsumo = 0
    n_ron = 0
    n_ryuu = 0
    payoff_abs_sum = 0.0
    win_payoff_sum = 0.0
    winner_counts = np.zeros(4, dtype=np.int64)
    ep_lengths: list[int] = []
    per_hand: list[dict] = []

    env = MultiAgentEnv(max_seq_len=args.max_seq_len)
    t0 = time.monotonic()
    for i in range(args.n_hands):
        seed = args.seed_base + i
        try:
            obs = env.reset(seed=seed)
        except Exception as e:
            print(f"hand {i:3d}: reset failed ({e!r}); skipping")
            continue

        steps = 0
        terminated = False
        info_at_end: dict = {}
        payoffs: Optional[np.ndarray] = None
        while obs is not None and not env.is_over() and steps < args.max_steps:
            feat = torch.as_tensor(
                obs["features"], device=device, dtype=torch.float32
            ).unsqueeze(0)
            attn = torch.as_tensor(
                obs["attention_mask"], device=device, dtype=torch.bool
            ).unsqueeze(0)
            mask = torch.as_tensor(
                obs["action_mask"], device=device, dtype=torch.bool
            ).unsqueeze(0)
            with torch.no_grad():
                action, _, _ = model.act(
                    feat, attn, mask, deterministic=not args.stochastic,
                )
            obs, payoffs, done, info_at_end = env.step(int(action.item()))
            steps += 1
            if done:
                terminated = True
                break

        if not terminated:
            n_truncated += 1
            per_hand.append({"hand": i, "seed": seed, "steps": steps,
                             "result": "truncated"})
            continue

        if int(env._inner.t.get_phase()) != int(pm.PhaseEnum.GAME_OVER):
            n_truncated += 1
            per_hand.append({"hand": i, "seed": seed, "steps": steps,
                             "result": "not_over"})
            continue

        n_played += 1
        ep_lengths.append(steps)
        payoff_abs = float(np.abs(payoffs).sum()) if payoffs is not None else 0.0
        payoff_abs_sum += payoff_abs

        rt = info_at_end.get("result_type", "")
        winners = info_at_end.get("winners", []) or []
        is_agari = bool(info_at_end.get("is_agari", False))
        hand_record = {
            "hand": i, "seed": seed, "steps": steps,
            "result_type": str(rt),
            "winners": list(winners),
            "is_agari": is_agari,
            "payoffs_25k": payoffs.tolist() if payoffs is not None else None,
        }

        if is_agari and winners:
            n_agari += 1
            if "Tsumo" in str(rt):
                n_tsumo += 1
            elif "Ron" in str(rt):
                n_ron += 1
            for w in winners:
                if 0 <= int(w) < 4:
                    winner_counts[int(w)] += 1
                    if payoffs is not None:
                        win_payoff_sum += float(payoffs[int(w)])
        else:
            n_ryuu += 1

        # Save paipu + URL.
        try:
            rec = TenhouPaipuRecorder(player_names=names)
            rec.record_hand(env._inner.t, seed=seed)
            xml_path = args.out_dir / f"hand_{i:03d}.xml"
            rec.save(str(xml_path))
            data = xml_to_tenhou_json(
                str(xml_path),
                title=(f"PPO self-play hand {i}", f"seed={seed}"),
            )
            url = make_editor_url(data)
            (xml_path.with_suffix(".url.txt")).write_text(url + "\n",
                                                          encoding="utf-8")
            hand_record["paipu_url"] = url
            # Append to consolidated per-hand URL list.
            all_urls_fh.write(url + "\n")
            all_urls_fh.flush()
        except Exception as e:
            print(f"hand {i:3d}: paipu save failed: {e!r}")

        per_hand.append(hand_record)

        # Periodic stdout progress.
        if (i + 1) % 10 == 0:
            elapsed = time.monotonic() - t0
            agari_rate = n_agari / max(n_played, 1)
            print(f"  [{i+1:3d}/{args.n_hands}] agari={n_agari}  "
                  f"agari_rate={agari_rate:.3f}  ryuu={n_ryuu}  "
                  f"trunc={n_truncated}  elapsed={elapsed:.1f}s")

    elapsed = time.monotonic() - t0
    nz_played = max(n_played, 1)

    summary = {
        "model": str(args.model),
        "split_heads": args.split_heads,
        "n_hands_requested": args.n_hands,
        "n_played": n_played,
        "n_truncated": n_truncated,
        "n_agari": n_agari,
        "n_tsumo": n_tsumo,
        "n_ron": n_ron,
        "n_ryuukyoku": n_ryuu,
        "agari_rate": n_agari / nz_played,
        "tsumo_rate": n_tsumo / nz_played,
        "ron_rate": n_ron / nz_played,
        "ryuukyoku_rate": n_ryuu / nz_played,
        "winner_share_per_seat": (winner_counts / max(winner_counts.sum(), 1)).tolist(),
        "mean_ep_len": float(np.mean(ep_lengths)) if ep_lengths else 0.0,
        "mean_abs_payoff_25k": payoff_abs_sum / nz_played,
        "mean_win_payoff_25k": (win_payoff_sum / n_agari) if n_agari > 0 else 0.0,
        "wall_time_s": elapsed,
        "stochastic": bool(args.stochastic),
        "seed_base": args.seed_base,
        "out_dir": str(args.out_dir),
    }

    print()
    print("=" * 60)
    print("AGGREGATE SUMMARY")
    print("=" * 60)
    print(f"  hands played   : {n_played}/{args.n_hands}  "
          f"(truncated: {n_truncated})")
    print(f"  agari          : {n_agari}  rate = {summary['agari_rate']:.3f}")
    print(f"    tsumo        : {n_tsumo}  rate = {summary['tsumo_rate']:.3f}")
    print(f"    ron          : {n_ron}  rate = {summary['ron_rate']:.3f}")
    print(f"  ryuukyoku      : {n_ryuu}  rate = {summary['ryuukyoku_rate']:.3f}")
    print(f"  mean ep_len    : {summary['mean_ep_len']:.1f}")
    print(f"  mean |payoff|  : {summary['mean_abs_payoff_25k']:.3f} (×25000 pts)")
    if n_agari > 0:
        print(f"  mean win pay   : {summary['mean_win_payoff_25k']:+.3f} "
              f"(×25000 pts; ≈ {summary['mean_win_payoff_25k']*25000:.0f} pts)")
    print(f"  per-seat wins  : {summary['winner_share_per_seat']}")
    print(f"  wall time      : {elapsed:.1f}s")

    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(
            json.dumps({"summary": summary, "per_hand": per_hand}, indent=2),
            encoding="utf-8",
        )
        print(f"\nsummary written to {args.summary_json}")

    all_urls_fh.close()
    print(f"per-hand URLs written to {all_urls_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
