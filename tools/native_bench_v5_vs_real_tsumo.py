"""Native pm.Table bench using REAL tsumogiri (discard the just-drawn tile)
instead of the previous "lowest-id tile in hand" policy.

The old `native_bench_v5_vs_tsumo.py` calls a stateless policy
``tsumogiri_policy(obs, seat)`` that picks the lowest-index discard action
from the mask — i.e. dumps 1m if available, then 2m, ... That is a
predictable low-tile-dump policy and is significantly weaker than actual
tsumogiri, which makes V5's avg point delta look inflated (~+44k/hanchan)
versus the mjai bench's REAL tsumogiri opponent (~+5k/hanchan).

This script restores the apples-to-apples comparison by writing a policy
that has access to the inner ``pm.Table`` via a closure on the env, and
discards the just-drawn tile (``players[seat].hand[-1]``) when in a
discard phase. Responses (pon/chi/kan/ron) are always passed.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

import MahjongPyWrapper as pm
from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.encoding import EncodingVersion, get_strategy
from pymahjong.rl.v4.hanchan_env import HanchanEnv
from pymahjong.rl.action_space import (
    ACTION_DIM, A_DISCARD_BASE, A_DISCARD_RED5M, A_DISCARD_RED5P,
    A_DISCARD_RED5S, A_PASS_RESPONSE, A_PASS_RIICHI,
)


def make_real_tsumogiri_policy(env: HanchanEnv):
    """Return a policy that tsumogiris the just-drawn tile via pm.Table."""

    def policy(obs, seat):
        mask = obs["action_mask"]
        valid_set = {int(v) for v in np.flatnonzero(mask)}
        # Pass through any response prompts.
        for prefer in (A_PASS_RESPONSE, A_PASS_RIICHI):
            if prefer in valid_set:
                return prefer
        # Otherwise we're in a discard phase. Inspect the inner pm.Table
        # to find the just-drawn tile (last entry in player's hand).
        table = env._inner._inner.t  # HanchanEnv -> V4MultiAgentEnv (._inner=MahjongEnv) -> pm.Table (.t)
        hand = table.players[seat].hand
        if not hand:
            # Should not happen during a discard phase
            valid = sorted(valid_set)
            return int(valid[0]) if valid else 0
        last = hand[-1]
        bt = int(last.tile)
        red = bool(last.red_dora)
        candidates = []
        if red:
            if bt == 4:
                candidates.append(A_DISCARD_RED5M)
            elif bt == 13:
                candidates.append(A_DISCARD_RED5P)
            elif bt == 22:
                candidates.append(A_DISCARD_RED5S)
        candidates.append(A_DISCARD_BASE + bt)
        for c in candidates:
            if c in valid_set:
                return c
        # Fallback: any valid discard
        for prefer in range(0, 37):
            if prefer in valid_set:
                return prefer
        return int(sorted(valid_set)[0])

    return policy


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
    ap.add_argument("--seed-base", type=int, default=10000)
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

    rank_counts = [[0]*4 for _ in range(4)]
    sum_score_delta = [0]*4
    n_finished = 0
    t0 = time.monotonic()
    results = []

    for hi in range(args.n_hanchan):
        seed = args.seed_base + hi
        env = HanchanEnv(max_seq_len=args.max_seq_len)
        obs = env.reset(seed=seed)
        opp = make_real_tsumogiri_policy(env)
        env._inner.set_opponent_policies({1: opp, 2: opp, 3: opp})
        env._inner._auto_step_opponents()
        if not env._hanchan_over and not env._inner.is_over():
            obs = env._inner.observe()

        n_dec = 0
        err = None
        t_h0 = time.monotonic()
        try:
            while not env._hanchan_over:
                cp = env.current_player
                if cp != 0:
                    env._inner._auto_step_opponents()
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
                        env._inner.set_opponent_policies({1: opp, 2: opp, 3: opp})
                        env._inner._auto_step_opponents()
                        if not env._inner.is_over():
                            obs = env._inner.observe()
                        continue
                if env._inner is not None and env._inner.is_over():
                    info = env._inner.get_result_info()
                    payoffs = np.asarray(info.get("payoffs", [0]*4), dtype=np.float32) / 25000.0
                    env._finalize_kyoku(payoffs, {"acting_seat": env.current_player,
                                                   "payoffs": info.get("payoffs", [0]*4),
                                                   **info})
                    obs = env.advance_to_next_kyoku()
                    if env._hanchan_over:
                        break
                    env._inner.set_opponent_policies({1: opp, 2: opp, 3: opp})
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
        results.append({"seed": seed, "scores": scores, "ranks": ranks})
        t_h = time.monotonic() - t_h0
        print(f"[{hi+1}/{args.n_hanchan}] seed={seed} scores={scores} ranks={ranks} dec={n_dec} t={t_h:.1f}s", flush=True)

    elapsed = time.monotonic() - t0
    avg_rank = [sum((r * c for r, c in enumerate(row, 1))) / max(1, n_finished) for row in rank_counts]
    avg_pt = [sum_score_delta[s] / max(1, n_finished) for s in range(4)]
    print()
    print(f"=== RESULT V5 vs 3xREAL-tsumogiri ({n_finished}/{args.n_hanchan}) ===")
    print(f"  avg_rank: {[round(r,3) for r in avg_rank]}")
    print(f"  avg_pt_d: {[round(p,1) for p in avg_pt]}")
    print(f"  rank_counts:")
    for s, row in enumerate(rank_counts):
        print(f"    seat{s}: {row}")
    print(f"  elapsed: {elapsed:.1f}s")

    summary = {
        "n_hanchan": args.n_hanchan,
        "n_finished": n_finished,
        "seats": ["v5", "real_tsumo", "real_tsumo", "real_tsumo"],
        "avg_rank": avg_rank,
        "avg_pt_d": avg_pt,
        "rank_counts": rank_counts,
        "elapsed_s": elapsed,
        "results": results,
    }
    (args.out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
