#!/usr/bin/env python3
"""Native pm.Table bench: V5 BC (seat 0) vs 3 x tsumogiri (seats 1-3).

Counterpart of the mjai bench (`mjai_bench_v2.py`) that talks directly
to V4MultiAgentEnv / HanchanEnv instead of going through the
mjai protocol. If V5 wins much more often here than via mjai, the mjai
adapter still has a hidden bug.

Tsumogiri policy matches the mjai TsumogiriAgent behaviorally:
- pass on responses (no chi/pon/ron/daiminkan)
- discard any legal tile (highest base index preferred to mimic
  "discard drawn tile" without needing engine state)
"""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import numpy as np
import torch

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.encoding import EncodingVersion, get_strategy
from pymahjong.rl.v4.hanchan_env import HanchanEnv


def tsumogiri_policy(obs, seat):
    mask = obs["action_mask"]
    valid = np.flatnonzero(mask)
    if valid.size == 0:
        return 0
    valid_set = set(int(v) for v in valid)
    # 1. Pass on any response phase
    for prefer in (53, 52):  # PASS_RESPONSE, PASS_RIICHI
        if prefer in valid_set:
            return prefer
    # 2. Discard a tile (range 0..36). Use first available normal-discard
    #    (avoid red-5 discard variants unless they're the only option).
    for prefer in range(0, 34):
        if prefer in valid_set:
            return prefer
    for prefer in (34, 35, 36):  # red 5 discard
        if prefer in valid_set:
            return prefer
    # 3. Fallback: any valid action
    return int(valid[0])


def scores_to_rank(scores):
    decorated = sorted(((-(s * 4 + (3 - i)), i) for i, s in enumerate(scores)))
    rank = [0] * 4
    for r, (_, pi) in enumerate(decorated):
        rank[pi] = r + 1
    return rank


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--n-hanchan", type=int, default=100)
    ap.add_argument("--seed-base", type=int, default=0)
    ap.add_argument("--device", default=None)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--d-model", type=int, default=384)
    ap.add_argument("--n-heads", type=int, default=8)
    ap.add_argument("--n-layers", type=int, default=6)
    ap.add_argument("--ff-mult", type=int, default=4)
    ap.add_argument("--scorer-hidden", type=int, default=256)
    ap.add_argument("--max-seq-len", type=int, default=512)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    print(f"loading {args.model} on {device}")
    cfg = TransformerConfig(d_model=args.d_model, n_heads=args.n_heads,
                            n_layers=args.n_layers, ff_mult=args.ff_mult)
    model = get_strategy(EncodingVersion.V5).create_model(
        transformer_config=cfg, scorer_hidden=args.scorer_hidden,
    ).to(device).eval()
    ck = torch.load(str(args.model), map_location=device, weights_only=False)
    state = ck["model"] if isinstance(ck, dict) and "model" in ck else ck
    model.load_state_dict(state)

    OPP_POLICIES = {1: tsumogiri_policy, 2: tsumogiri_policy, 3: tsumogiri_policy}

    rank_counts = [[0]*4 for _ in range(4)]
    sum_score_delta = [0]*4
    n_finished = 0
    t0 = time.monotonic()
    results = []

    for hi in range(args.n_hanchan):
        seed = args.seed_base + hi
        env = HanchanEnv(max_seq_len=args.max_seq_len)
        obs = env.reset(seed=seed)
        # Install opponent policies into the freshly-built V4 env.
        env._inner.set_opponent_policies(OPP_POLICIES)
        env._inner._auto_step_opponents()
        if not env._hanchan_over and not env._inner.is_over():
            obs = env._inner.observe()

        n_dec = 0
        err = None
        try:
            while not env._hanchan_over:
                cp = env.current_player
                if cp != 0:
                    # opp turn — auto-step (should already be handled by env)
                    env._inner._auto_step_opponents()
                    if env._inner.is_over():
                        # kyoku ended on opp action; finish manually
                        # We need to call kyoku_step with dummy to trigger finalize
                        # but _auto_step_opponents already advanced — handle below
                        pass
                    if not env._inner.is_over():
                        obs = env._inner.observe()
                        continue
                else:
                    feat = torch.as_tensor(obs["features"], device=device, dtype=torch.float32).unsqueeze(0)
                    attn = torch.as_tensor(obs["attention_mask"], device=device, dtype=torch.bool).unsqueeze(0)
                    mask = torch.as_tensor(obs["action_mask"], device=device, dtype=torch.bool).unsqueeze(0)
                    action, _, _ = model.act(feat, attn, mask, deterministic=True)
                    obs, payoffs, done, info = env.kyoku_step(int(action.item()))
                    n_dec += 1
                    if done:
                        obs = env.advance_to_next_kyoku()
                        if env._hanchan_over:
                            break
                        env._inner.set_opponent_policies(OPP_POLICIES)
                        env._inner._auto_step_opponents()
                        if not env._inner.is_over():
                            obs = env._inner.observe()
                        continue
                # Handle case where opp action ended kyoku
                if env._inner is not None and env._inner.is_over():
                    # Need to ingest the final state via a dummy kyoku_step?
                    # Simpler: directly finalize via HanchanEnv internal hooks.
                    info = env._inner.get_result_info()
                    payoffs = np.asarray(info.get("payoffs", [0]*4), dtype=np.float32) / 25000.0
                    env._finalize_kyoku(payoffs, {"acting_seat": env.current_player,
                                                   "payoffs": info.get("payoffs", [0]*4),
                                                   **info})
                    obs = env.advance_to_next_kyoku()
                    if env._hanchan_over:
                        break
                    env._inner.set_opponent_policies(OPP_POLICIES)
                    env._inner._auto_step_opponents()
                    if not env._inner.is_over():
                        obs = env._inner.observe()
        except Exception as e:
            err = repr(e)
            print(f"[{hi+1}] EXCEPTION: {e!r}")

        if err is not None:
            results.append({"seed": seed, "error": err})
            continue

        scores = list(env._scores)
        ranks = scores_to_rank(scores)
        for s in range(4):
            rank_counts[s][ranks[s]-1] += 1
            sum_score_delta[s] += scores[s] - 25000
        n_finished += 1
        t_h = time.monotonic() - t0
        print(f"[{hi+1}/{args.n_hanchan}] seed={seed} scores={scores} ranks={ranks} reason={env._termination_reason} dec={n_dec} t={t_h:.1f}s", flush=True)
        results.append({"seed": seed, "scores": scores, "ranks": ranks,
                        "reason": env._termination_reason, "n_decisions": n_dec})

    avg_rank = [
        (sum((r+1)*rank_counts[s][r] for r in range(4)) / max(1, sum(rank_counts[s])))
        for s in range(4)
    ]
    avg_pt = [sum_score_delta[s] / max(1, n_finished) for s in range(4)]
    print(f"\n=== RESULT V5 vs 3xtsumogiri ({n_finished}/{args.n_hanchan} finished) ===")
    print(f"avg_rank = {[round(r,3) for r in avg_rank]}")
    print(f"avg_pt_d = {[round(p,1) for p in avg_pt]}")
    print(f"rank_counts:")
    for s, name in enumerate(["v5", "tsumo", "tsumo", "tsumo"]):
        print(f"  seat{s} {name}: {rank_counts[s]}")

    summary = {
        "n_hanchan": args.n_hanchan,
        "n_finished": n_finished,
        "seats": ["v5", "tsumo", "tsumo", "tsumo"],
        "avg_rank": avg_rank,
        "avg_pt_d": avg_pt,
        "rank_counts": rank_counts,
        "elapsed_s": time.monotonic() - t0,
    }
    with open(args.out_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    with open(args.out_dir / "results.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
