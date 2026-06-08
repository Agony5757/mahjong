#!/usr/bin/env python3
"""Hand-level BC debugger: print logits at every decision in one kyoku.

Drives :class:`pymahjong.env_pymahjong.MahjongEnv` through exactly one
hand (a single kyoku, default East-1) with the BC model controlling all
four seats.  At every decision point the script prints:

* step idx / phase / acting player
* the player's hand (with red-5 marked)
* the action_mask (which of the 54 actions are legal)
* the model's raw logits for legal actions (sorted by logit, decreasing)
* softmax probabilities over the masked logits
* the chosen action (argmax or sample)

At the end it prints the final result + per-seat scores + final hands so
you can eyeball "did the model make sensible decisions in this kyoku".

Examples::

    # default — East 1, seed 0, deterministic argmax, top-5 logits per decision
    python tools/debug_bc_hand.py --bc-model checkpoints/bc_v4_sp.best.pt

    # different seed, sample actions, dump all 54 logits per decision
    python tools/debug_bc_hand.py --bc-model checkpoints/bc_v4_sp.best.pt \\
        --seed 7 --stochastic --top-k 0

    # write the same trace to logs/<file>.txt as well as stdout
    python tools/debug_bc_hand.py --bc-model checkpoints/bc_v4_sp.best.pt \\
        --out logs/debug_e1_seed0.txt
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

import MahjongPyWrapper as pm
from pymahjong.env_pymahjong import MahjongEnv
from pymahjong.paipu_recorder import TenhouPaipuRecorder
from pymahjong.paipu_tenhou_json import make_editor_url, xml_to_tenhou_json
from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.live_encoder import LiveEncoder
from pymahjong.rl.transformer import EventStreamTransformer


# ---------------------------------------------------------------------------
# 54-action human-readable names
# ---------------------------------------------------------------------------

_BASETILE_STR = (
    [f"{n}m" for n in range(1, 10)]
    + [f"{n}p" for n in range(1, 10)]
    + [f"{n}s" for n in range(1, 10)]
    + ["E", "S", "W", "N", "P", "F", "C"]  # 1z..7z
)


def _action_names() -> list:
    names = [f"Discard {b}" for b in _BASETILE_STR]               # 0..33
    names += ["Discard 0m", "Discard 0p", "Discard 0s"]           # 34..36
    names += [
        "Chi-Left", "Chi-Middle", "Chi-Right",                    # 37..39
        "Chi-Left(red)", "Chi-Middle(red)", "Chi-Right(red)",     # 40..42
        "Pon", "Pon(red)",                                        # 43..44
        "AnKan", "MinKan", "KaKan",                               # 45..47
        "Riichi", "Ron", "Tsumo",                                 # 48..50
        "Push (Kyushukyuhai)",                                    # 51
        "Pass-Riichi", "Pass-Response",                           # 52..53
    ]
    assert len(names) == 54
    return names


ACTION_NAMES = _action_names()


# ---------------------------------------------------------------------------
# Hand state pretty-printer
# ---------------------------------------------------------------------------


def _format_hand(player) -> str:
    return " ".join(t.to_string() for t in player.hand)


def _format_fuuros(player) -> str:
    fs = list(player.get_fuuros())
    if not fs:
        return "-"
    return " | ".join(f.to_string() for f in fs)


def _format_river(player) -> str:
    river_obj = player.get_river()
    n = river_obj.size()
    if n == 0:
        return "-"
    s = river_obj.to_string()
    return s if len(s) <= 80 else s[:77] + "..."


# ---------------------------------------------------------------------------
# Decision printer
# ---------------------------------------------------------------------------


def _print_decision(
    step: int,
    env: MahjongEnv,
    obs: dict,
    raw_logits: np.ndarray,           # (54,) pre-mask
    masked_logits: np.ndarray,        # (54,) -1e9 on illegal
    probs: np.ndarray,                # (54,) softmax over masked
    raw_probs: np.ndarray,            # (54,) softmax over RAW (un-masked)
    action_mask: np.ndarray,          # (54,) bool
    chosen: int,
    *,
    top_k: int,
    print_fn,
) -> None:
    pid = env.get_curr_player_id()
    phase = int(env.t.get_phase())
    player = env.t.players[pid]
    seq_len = int(np.asarray(obs["attention_mask"]).sum())

    print_fn(f"\n--- step {step:>3d}  P{pid}  phase={phase}  (seq_len={seq_len}) ---")
    print_fn(f"  hand  : {_format_hand(player)}")
    print_fn(f"  fuuros: {_format_fuuros(player)}")
    print_fn(f"  river : {_format_river(player)}")
    print_fn(f"  scores: {list(env.t.get_scores())}  remain_tiles={env.t.get_remain_tile()}")

    legal_idxs = np.flatnonzero(action_mask)
    n_legal = len(legal_idxs)
    print_fn(f"  legal actions ({n_legal}): "
             + ", ".join(f"{i}={ACTION_NAMES[i]}" for i in legal_idxs))

    # Diagnostic: does the raw policy head agree with the masked one?
    raw_argmax = int(np.argmax(raw_logits))
    masked_argmax = int(np.argmax(masked_logits))
    raw_illegal_mass = float(raw_probs[~action_mask].sum())
    leak_marker = " *** LEAK ***" if raw_argmax != masked_argmax else ""
    print_fn(
        f"  raw vs masked: raw_argmax={raw_argmax}={ACTION_NAMES[raw_argmax]} "
        f"(legal={bool(action_mask[raw_argmax])})  |  "
        f"masked_argmax={masked_argmax}={ACTION_NAMES[masked_argmax]}  |  "
        f"raw_prob_on_ILLEGAL={raw_illegal_mass:.3f}{leak_marker}"
    )

    # Decide which logits to display: top-k of legal actions, or all if k=0.
    if top_k > 0:
        display = legal_idxs[np.argsort(-masked_logits[legal_idxs])[:top_k]]
    else:
        display = legal_idxs[np.argsort(-masked_logits[legal_idxs])]

    print_fn(f"  logits (top {min(top_k, n_legal) if top_k else n_legal} of LEGAL):")
    print_fn(f"    {'idx':>4s}  {'name':<22s}  {'raw':>10s}  {'masked':>10s}  {'prob':>8s}")
    for idx in display:
        marker = " <-- CHOSEN" if idx == chosen else ""
        print_fn(
            f"    {idx:>4d}  {ACTION_NAMES[idx]:<22s}  "
            f"{raw_logits[idx]:>10.3f}  {masked_logits[idx]:>10.3f}  "
            f"{probs[idx]:>8.4f}{marker}"
        )

    # Always show top-3 of the RAW (unmasked) logits across ALL 54 actions
    # so the user can spot "model wanted an illegal action".
    raw_top = np.argsort(-raw_logits)[:max(3, min(top_k, 5))]
    print_fn(f"  RAW top-{len(raw_top)} of ALL 54 (illegal flagged):")
    print_fn(f"    {'idx':>4s}  {'name':<22s}  {'raw':>10s}  {'raw_prob':>10s}  legal?")
    for idx in raw_top:
        flag = "OK" if action_mask[idx] else "ILLEGAL"
        print_fn(
            f"    {idx:>4d}  {ACTION_NAMES[idx]:<22s}  "
            f"{raw_logits[idx]:>10.3f}  {raw_probs[idx]:>10.4f}  {flag}"
        )


# ---------------------------------------------------------------------------
# Main driver
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bc-model", type=Path, required=True,
                    help="BC checkpoint (.pt).")
    ap.add_argument("--seed", type=int, default=0,
                    help="Engine seed for the hand.")
    ap.add_argument("--oya", type=int, default=0,
                    help="Dealer (0-3).  Default 0 = player 0 deals (East 1).")
    ap.add_argument("--game-wind", default="east",
                    choices=["east", "south", "west", "north"],
                    help="Round wind.  Default east — combined with oya=0 "
                         "means East-1.")
    ap.add_argument("--stochastic", action="store_true",
                    help="Sample actions from the masked-softmax distribution "
                         "instead of taking argmax.")
    ap.add_argument("--top-k", type=int, default=8,
                    help="Show top-K legal actions sorted by logit.  "
                         "0 = show all legal actions.")
    ap.add_argument("--device", default=None,
                    help="Torch device.  Default: auto.")
    ap.add_argument("--max-steps", type=int, default=400,
                    help="Safety cap on decisions in this hand.")
    ap.add_argument("--split-heads", action="store_true",
                    help="The checkpoint was trained with split-head "
                         "architecture (action+response sub-heads).  "
                         "Must match the training-time setting.")
    ap.add_argument("--out", type=Path, default=None,
                    help="Also dump the trace to this file.")
    ap.add_argument("--save-paipu", type=Path, default=None,
                    help="Optional: write the played hand as a Tenhou XML "
                         "paipu (one-hand recorder).  Pass e.g. "
                         "logs/debug_hand.xml.  A matching .url.txt with "
                         "the paipu-editor URL is written alongside.")
    args = ap.parse_args()

    device_str = (
        args.device
        if args.device is not None
        else ("cuda" if torch.cuda.is_available() else "cpu")
    )
    device = torch.device(device_str)

    cfg = TransformerConfig()
    model = EventStreamTransformer(config=cfg, split_heads=args.split_heads).to(device)
    ck = torch.load(str(args.bc_model), map_location=device, weights_only=False)
    state = ck["model"] if isinstance(ck, dict) and "model" in ck else ck
    model.load_state_dict(state)
    model.eval()

    # tee output to file
    out_fh = open(args.out, "w", encoding="utf-8") if args.out else None
    def _print(*a):
        msg = " ".join(str(x) for x in a)
        print(msg)
        if out_fh is not None:
            print(msg, file=out_fh)

    _print(f"BC model: {args.bc_model}  device={device}  dims={cfg.d_model}/{cfg.n_layers}/{cfg.n_heads}/{cfg.ff_mult}")
    _print(f"hand: oya={args.oya} game_wind={args.game_wind} seed={args.seed} "
           f"policy={'sample' if args.stochastic else 'argmax'}")

    env = MahjongEnv()
    env.reset(
        seed=args.seed,
        oya=args.oya,
        game_wind=args.game_wind,
        scores=[25000, 25000, 25000, 25000],
        kyoutaku=0, honba=0,
    )

    # Print initial hands
    _print("\n=== INITIAL DEAL ===")
    for pid in range(4):
        _print(f"  P{pid} {'(oya)' if pid == args.oya else '     '} : "
               f"{_format_hand(env.t.players[pid])}")

    # Bind LiveV4 encoder for the (single) hand.
    enc = LiveEncoder(env.t)
    enc.start_hand()

    rng = np.random.default_rng(args.seed)
    step = 0
    leak_total = 0                # # decisions where raw argmax is illegal
    raw_illegal_mass_sum = 0.0    # sum of raw softmax mass on illegal slots
    n_decisions = 0
    while not env.is_over() and step < args.max_steps:
        pid = env.get_curr_player_id()
        try:
            obs = enc.observation_for(pid, register_decide=True, max_seq_len=cfg.max_seq_len)
        except Exception as e:
            _print(f"[step {step}] LiveEncoder.observation_for failed: {e!r}; "
                   "falling back to first valid action")
            valid = np.flatnonzero(env.get_valid_actions(nhot=True))
            env.step(pid, int(valid[0]) if len(valid) else 0)
            step += 1
            continue

        feat = torch.as_tensor(obs["features"], device=device, dtype=torch.float32).unsqueeze(0)
        attn = torch.as_tensor(obs["attention_mask"], device=device, dtype=torch.bool).unsqueeze(0)
        amask = torch.as_tensor(obs["action_mask"], device=device, dtype=torch.bool).unsqueeze(0)
        # Belt-and-braces — AND with engine legality.
        engine_valid = env.get_valid_actions(nhot=True)
        evalid = torch.as_tensor(engine_valid, device=device, dtype=torch.bool).unsqueeze(0)
        amask = amask & evalid
        if not amask.any():
            amask = evalid

        with torch.no_grad():
            raw_logits, _ = model(feat, attn, None)              # un-masked
            masked_logits, _ = model(feat, attn, amask)          # masked

        raw = raw_logits[0].detach().cpu().numpy()
        msk = masked_logits[0].detach().cpu().numpy()
        probs = F.softmax(masked_logits[0], dim=-1).detach().cpu().numpy()
        raw_probs = F.softmax(raw_logits[0], dim=-1).detach().cpu().numpy()

        if args.stochastic:
            chosen = int(rng.choice(54, p=probs / probs.sum()))
        else:
            chosen = int(np.argmax(msk))

        # Diagnostics aggregates.
        amask_np = np.asarray(amask[0].detach().cpu().numpy(), dtype=bool)
        raw_argmax = int(np.argmax(raw))
        leak_total += int(not amask_np[raw_argmax])
        raw_illegal_mass_sum += float(raw_probs[~amask_np].sum())

        _print_decision(
            step, env, obs, raw, msk, probs, raw_probs,
            amask_np,
            chosen, top_k=args.top_k, print_fn=_print,
        )

        try:
            env.step(pid, chosen)
        except Exception as e:
            _print(f"  ENGINE REJECTED action {chosen}: {e!r}; falling back to first legal")
            valid = np.flatnonzero(engine_valid)
            env.step(pid, int(valid[0]) if len(valid) else 0)
        step += 1
        n_decisions += 1

    _print("\n=== HAND FINISHED ===")
    _print(f"  steps : {step}")
    _print(f"  phase : {int(env.t.get_phase())}  (16 = GAME_OVER)")
    _print(f"  scores: {list(env.t.get_scores())}")
    rt = env.t.gamelog.result.result_type
    _print(f"  result: {rt}  winners={list(env.t.gamelog.result.winner)}  "
           f"losers={list(env.t.gamelog.result.loser)}")
    _print("  final hands:")
    for pid in range(4):
        _print(f"    P{pid}: {_format_hand(env.t.players[pid])}  | "
               f"fuuros: {_format_fuuros(env.t.players[pid])}")

    # Mask-leak summary across all decisions in this hand.
    if n_decisions > 0:
        _print(f"\n=== MASK-LEAK SUMMARY ({n_decisions} decisions) ===")
        _print(f"  decisions where raw argmax is ILLEGAL: "
               f"{leak_total}/{n_decisions} "
               f"({100*leak_total/n_decisions:.1f}%)")
        _print(f"  mean raw-softmax mass on ILLEGAL slots: "
               f"{raw_illegal_mass_sum/n_decisions:.3f}")

    if args.save_paipu:
        if int(env.t.get_phase()) != int(pm.PhaseEnum.GAME_OVER):
            _print(f"\n  NOT saving paipu (game didn't finish cleanly)")
        else:
            rec = TenhouPaipuRecorder(player_names=["BC0","BC1","BC2","BC3"])
            rec.record_hand(env.t, seed=args.seed)
            args.save_paipu.parent.mkdir(parents=True, exist_ok=True)
            rec.save(str(args.save_paipu))
            _print(f"\n  paipu written to {args.save_paipu}")
            try:
                data = xml_to_tenhou_json(
                    str(args.save_paipu),
                    title=("BC debug hand", f"seed={args.seed}"),
                )
                url = make_editor_url(data)
                url_path = args.save_paipu.with_suffix(".url.txt")
                url_path.write_text(url + "\n", encoding="utf-8")
                _print(f"  paipu URL  written to {url_path} ({len(url)} chars)")
            except Exception as e:
                _print(f"  URL gen failed: {e!r}")

    if out_fh is not None:
        out_fh.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
