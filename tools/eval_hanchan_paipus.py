#!/usr/bin/env python3
"""Evaluate a V4 checkpoint by playing N full hanchans (半庄).

For each hanchan:
  * runs all kyoku end-to-end (East/South + West extension as appropriate)
  * records every kyoku as a Tenhou XML paipu + paipu-editor URL
  * tracks final scores, ranks, agari / houjuu / renchan per seat

Reports per-hanchan + aggregated statistics including:
  * Average rank
  * Average final point delta (vs 25,000)
  * Per-seat agari / houjuu / renchan counts
  * Termination reason histogram (south_4 / west_4 / tobi / ...)

Example::

    python tools/eval_hanchan_paipus.py \\
        --model checkpoints/ppo_v4_split.pt --split-heads \\
        --n-hanchan 10 --seed-base 0 \\
        --out-dir logs/ppo_hanchan_10 \\
        --summary-json logs/ppo_hanchan_10/summary.json
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from pymahjong.paipu_recorder import TenhouPaipuRecorder
from pymahjong.paipu_tenhou_json import make_editor_url, xml_to_tenhou_json
from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.v4.hanchan_env import HanchanEnv
from pymahjong.rl.v4.model import EventStreamTransformer


def _load_model(path, *, device, split_heads, encoding="v4"):
    """Load a V4 or V5 BC/PPO checkpoint.

    Args:
        encoding: "v4" or "v5".  V4 builds an
            :class:`EventStreamTransformer`; V5 builds a
            :class:`DouzeroV5Transformer` via the V5 strategy registry.
        split_heads: only meaningful for V4 linear-head checkpoints;
            ignored for V5 (its shared scorer subsumes phase routing).
    """
    cfg = TransformerConfig()  # 192/4/6/4 defaults — match BC/PPO ckpts
    if encoding == "v5":
        from pymahjong.rl.encoding import EncodingVersion, get_strategy
        strat = get_strategy(EncodingVersion.V5)
        m = strat.create_model(transformer_config=cfg).to(device)
    else:
        m = EventStreamTransformer(config=cfg, split_heads=split_heads).to(device)
    ck = torch.load(str(path), map_location=device, weights_only=False)
    state = ck["model"] if isinstance(ck, dict) and "model" in ck else ck
    m.load_state_dict(state)
    m.eval()
    return m


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--encoding", choices=["v4", "v5"], default="v4",
                    help="Model architecture: v4 = linear policy head; "
                         "v5 = Douzero-style state+action shared MLP head.")
    ap.add_argument("--split-heads", action="store_true",
                    help="V4 only: load a phase-split-head checkpoint.")
    ap.add_argument("--n-hanchan", type=int, default=10)
    ap.add_argument("--seed-base", type=int, default=0,
                    help="hanchan i starts at seed=seed-base + i*1000 "
                         "(each kyoku within increments by 1)")
    ap.add_argument("--max-seq-len", type=int, default=512)
    ap.add_argument("--stochastic", action="store_true")
    ap.add_argument("--max-extra-kyoku", type=int, default=16,
                    help="Hard cap on extra renchan/west kyoku per hanchan.")
    ap.add_argument("--no-west-round", action="store_true",
                    help="Disable West-round extension (stop strictly at S4).")
    ap.add_argument("--no-tobi", action="store_true",
                    help="Disable tobi termination (continue even if a player < 0).")
    ap.add_argument("--out-dir", type=Path, required=True,
                    help="Per-hanchan/per-kyoku paipus go under "
                         "<out-dir>/hanchan_NNN/kyoku_M.{xml,url.txt}")
    ap.add_argument("--summary-json", type=Path, default=None)
    ap.add_argument("--player-names", default="P0,P1,P2,P3")
    ap.add_argument("--device", default=None)
    ap.add_argument("--max-steps-per-kyoku", type=int, default=2000,
                    help="Safety cap on decisions per kyoku.")
    args = ap.parse_args()

    device = torch.device(
        args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    )
    print(f"loading {args.model} on {device}  encoding={args.encoding}  split_heads={args.split_heads}")
    model = _load_model(args.model, device=device, split_heads=args.split_heads,
                        encoding=args.encoding)
    names = [n.strip() for n in args.player_names.split(",")]
    assert len(names) == 4
    args.out_dir.mkdir(parents=True, exist_ok=True)
    # Consolidated per-kyoku URL list (one URL per line, across all hanchan).
    all_urls_path = args.out_dir / "kyoku_urls.txt"
    all_urls_fh = all_urls_path.open("w", encoding="utf-8")

    # Per-hanchan + aggregate trackers.
    per_hanchan_records = []
    n_total_kyoku = 0
    n_total_agari = 0
    n_total_ryuu = 0
    n_total_renchan = 0
    n_total_tobi = 0
    rank_counts = np.zeros((4, 4), dtype=np.int64)   # rank_counts[seat][rank]
    final_score_sum = np.zeros(4, dtype=np.float64)
    final_pt_delta_sum = np.zeros(4, dtype=np.float64)  # vs 25000
    per_seat_agari_total = np.zeros(4, dtype=np.int64)
    per_seat_houjuu_total = np.zeros(4, dtype=np.int64)
    termination_hist = {}

    t0 = time.monotonic()
    env = HanchanEnv(
        max_seq_len=args.max_seq_len,
        use_west_round=not args.no_west_round,
        tobi=not args.no_tobi,
        max_extra_kyoku=args.max_extra_kyoku,
    )

    for hi in range(args.n_hanchan):
        hanchan_seed = args.seed_base + hi * 1000
        try:
            env.reset(seed=hanchan_seed)
        except Exception as e:
            print(f"hanchan {hi}: reset failed ({e!r}); skipping")
            continue

        hanchan_dir = args.out_dir / f"hanchan_{hi:03d}"
        hanchan_dir.mkdir(parents=True, exist_ok=True)

        kyoku_idx_global = 0
        while not env.is_hanchan_over():
            # Play the current kyoku.
            steps = 0
            done = False
            while not env.is_kyoku_over() and steps < args.max_steps_per_kyoku:
                obs = env.observe()
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
                _, _, done, _ = env.kyoku_step(int(action.item()))
                steps += 1
                if done:
                    break
            if not done:
                # Kyoku truncated; force end-of-hanchan to avoid infinite loop.
                print(f"  hanchan {hi}, kyoku {kyoku_idx_global}: truncated after {steps}")
                env._hanchan_over = True
                env._termination_reason = "kyoku_truncated"
                break

            # Save paipu + URL for the kyoku we just finished.
            r = env._last_kyoku_result
            try:
                rec = TenhouPaipuRecorder(player_names=names)
                rec.record_hand(env.get_inner_table(), seed=r.seed)
                xml_path = hanchan_dir / (
                    f"kyoku_{kyoku_idx_global:02d}_"
                    f"{r.bakaze[0].upper()}{r.kyoku_idx+1}_b{r.honba}.xml"
                )
                rec.save(str(xml_path))
                data = xml_to_tenhou_json(
                    str(xml_path),
                    title=(
                        f"hanchan {hi} kyoku {kyoku_idx_global}",
                        f"{r.bakaze} {r.kyoku_idx+1}-{r.honba}本場 oya={r.oya}",
                    ),
                )
                url = make_editor_url(data)
                xml_path.with_suffix(".url.txt").write_text(
                    url + "\n", encoding="utf-8"
                )
                # Append to the consolidated per-kyoku URL list.
                all_urls_fh.write(url + "\n")
                all_urls_fh.flush()
            except Exception as e:
                print(f"  hanchan {hi} kyoku {kyoku_idx_global}: paipu fail: {e!r}")
            kyoku_idx_global += 1
            if env.is_hanchan_over():
                break
            env.advance_to_next_kyoku()

        # Hanchan finished — aggregate.
        result = env.get_hanchan_result()
        rec = {
            "hanchan": hi,
            "seed": hanchan_seed,
            "n_kyoku": result.n_kyoku,
            "n_agari": result.n_agari,
            "n_ryuukyoku": result.n_ryuukyoku,
            "n_renchan": result.n_dealer_renchan,
            "termination": result.termination_reason,
            "final_scores": result.final_scores,
            "ranks": result.ranks,
            "per_seat_agari": result.per_seat_agari,
            "per_seat_houjuu": result.per_seat_houjuu,
            "kyoku": [
                {
                    "bakaze": k.bakaze, "kyoku": k.kyoku_idx + 1,
                    "oya": k.oya, "honba": k.honba,
                    "kyoutaku_start": k.kyoutaku_start,
                    "result_type": k.result_type,
                    "winners": k.winners,
                    "is_agari": k.is_agari,
                    "is_dealer_renchan": k.is_dealer_renchan,
                    "score_changes_25k": k.score_changes_25k,
                    "scores_after": k.scores_after,
                    "steps": k.steps,
                    "seed": k.seed,
                }
                for k in result.kyoku
            ],
        }
        per_hanchan_records.append(rec)

        n_total_kyoku += result.n_kyoku
        n_total_agari += result.n_agari
        n_total_ryuu += result.n_ryuukyoku
        n_total_renchan += result.n_dealer_renchan
        if result.termination_reason == "tobi":
            n_total_tobi += 1
        for s in range(4):
            rank_counts[s][result.ranks[s]] += 1
            final_score_sum[s] += result.final_scores[s]
            final_pt_delta_sum[s] += result.final_scores[s] - 25_000
            per_seat_agari_total[s] += result.per_seat_agari[s]
            per_seat_houjuu_total[s] += result.per_seat_houjuu[s]
        termination_hist[result.termination_reason] = (
            termination_hist.get(result.termination_reason, 0) + 1
        )

        # Per-hanchan progress line.
        print(
            f"hanchan {hi:3d} seed={hanchan_seed:8d}  "
            f"n_kyoku={result.n_kyoku:2d}  agari={result.n_agari:2d}  "
            f"ryuu={result.n_ryuukyoku:2d}  renchan={result.n_dealer_renchan:2d}  "
            f"end={result.termination_reason:<14s}  "
            f"final={result.final_scores}"
        )

    # Aggregate.
    elapsed = time.monotonic() - t0
    n = max(len(per_hanchan_records), 1)
    avg_kyoku = n_total_kyoku / n
    avg_rank = (rank_counts @ np.arange(1, 5)) / n  # average ordinal rank (1=top)
    avg_score = final_score_sum / n
    avg_pt = final_pt_delta_sum / n
    agari_rate_per_kyoku = n_total_agari / max(n_total_kyoku, 1)

    summary = {
        "model": str(args.model),
        "split_heads": args.split_heads,
        "n_hanchan_requested": args.n_hanchan,
        "n_hanchan_played": len(per_hanchan_records),
        "n_total_kyoku": n_total_kyoku,
        "n_total_agari": n_total_agari,
        "n_total_ryuukyoku": n_total_ryuu,
        "n_total_dealer_renchan": n_total_renchan,
        "n_total_tobi": n_total_tobi,
        "avg_kyoku_per_hanchan": avg_kyoku,
        "agari_rate_per_kyoku": agari_rate_per_kyoku,
        "termination_histogram": termination_hist,
        "per_seat_avg_rank": avg_rank.tolist(),         # lower = better
        "per_seat_avg_final_score": avg_score.tolist(),
        "per_seat_avg_pt_delta": avg_pt.tolist(),       # vs 25000
        "per_seat_agari_total": per_seat_agari_total.tolist(),
        "per_seat_houjuu_total": per_seat_houjuu_total.tolist(),
        "per_seat_rank_counts": rank_counts.tolist(),
        "wall_time_s": elapsed,
        "stochastic": bool(args.stochastic),
    }

    print()
    print("=" * 70)
    print("HANCHAN AGGREGATE")
    print("=" * 70)
    print(f"  hanchans: {len(per_hanchan_records)}/{args.n_hanchan}  "
          f"elapsed {elapsed:.1f}s")
    print(f"  total kyoku  : {n_total_kyoku}  "
          f"(avg {avg_kyoku:.1f}/hanchan)")
    print(f"  agari rate   : {agari_rate_per_kyoku:.3f} per kyoku  "
          f"({n_total_agari} agari over {n_total_kyoku} kyoku)")
    print(f"  ryuukyoku    : {n_total_ryuu}")
    print(f"  renchan      : {n_total_renchan}")
    print(f"  tobi-end     : {n_total_tobi}")
    print(f"  termination  : {termination_hist}")
    print(f"  per-seat avg rank  (lower=better): {[f'{x:.2f}' for x in avg_rank]}")
    print(f"  per-seat avg final score         : {[int(x) for x in avg_score]}")
    print(f"  per-seat avg pt delta vs 25k     : {[int(x) for x in avg_pt]}")
    print(f"  per-seat agari counts            : {per_seat_agari_total.tolist()}")
    print(f"  per-seat houjuu counts           : {per_seat_houjuu_total.tolist()}")

    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(
            json.dumps(
                {"summary": summary, "per_hanchan": per_hanchan_records},
                indent=2, default=lambda x: float(x) if hasattr(x, "item") else str(x),
            ),
            encoding="utf-8",
        )
        print(f"\nsummary written to {args.summary_json}")
    all_urls_fh.close()
    print(f"per-kyoku URLs written to {all_urls_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
