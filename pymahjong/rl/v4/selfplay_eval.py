"""Shared-policy self-play evaluation for V4 policies.

A coarse "is the model actually playing Mahjong?" diagnostic that
complements the supervised top-1 accuracy on a held-out dataset.

Top-1 accuracy is brittle for Mahjong BC: a model that always discards
the just-drawn tile achieves ~30% accuracy without playing meaningfully.
Rolling the policy in :class:`V4MultiAgentEnv` with all four seats
sharing the same weights exposes whether the model can actually finish
a hand, score agari, manage riichi, etc.

Returned metrics (dict of ``str -> float``):

* ``sp/n_played``         — number of episodes that produced a result
* ``sp/agari_rate``       — fraction of hands ending in tsumo or ron
* ``sp/tsumo_rate``
* ``sp/ron_rate``
* ``sp/ryuukyoku_rate``   — fraction ending in exhaustive draw
* ``sp/truncated_rate``   — fraction stopped by ``max_steps_per_hand``
                             (high values suggest the policy is stuck)
* ``sp/mean_ep_len``      — average decision steps per hand
* ``sp/mean_abs_payoff``  — average ``sum(|payoff|)`` in 25k-point units
                             (≈ 2 × winner's payoff when symmetric)
* ``sp/wall_s``           — wall-clock spent on evaluation
* ``sp/mask_fallback_fired`` — 1.0 if the V4 env's "illegal action"
                                 fallback fired for the first time
                                 during eval (indicates rare drift)
* ``sp/winner_share_seat{0..3}`` — per-seat fraction of agari wins
                                     (only present if ``agari_rate > 0``)
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import numpy as np

try:
    import torch
except Exception as _e:  # noqa: BLE001
    raise RuntimeError("torch is required for V4 self-play evaluation") from _e

from .env import V4MultiAgentEnv
from .model import EventStreamTransformer


@torch.no_grad()
def selfplay_eval_v4(
    model: EventStreamTransformer,
    *,
    n_hands: int = 16,
    deterministic: bool = True,
    max_seq_len: int = 512,
    seed: int = 0,
    device: Optional[torch.device] = None,
    max_steps_per_hand: int = 1000,
) -> Dict[str, float]:
    """Roll out ``n_hands`` shared-policy self-play hands and report metrics.

    All four seats are driven by ``model``.  Use during BC training to
    detect whether the model has learned to make legal, productive
    decisions (rather than just maximising token-level cross-entropy on
    the dataset).

    Args:
        model: the V4 ``EventStreamTransformer`` to evaluate.
        n_hands: number of hands (episodes) to play.
        deterministic: if True, use ``argmax`` over masked logits;
            otherwise sample from the categorical distribution.
        max_seq_len: must match the model's training-time max length.
        seed: each hand uses ``seed + hand_idx`` for reproducibility.
        device: model device; auto-detected if None.
        max_steps_per_hand: safety cap; counted in ``truncated_rate``.

    Returns:
        Metrics dict (see module docstring).  The model is left in the
        training-mode it had on entry.
    """
    if device is None:
        device = next(model.parameters()).device

    was_training = model.training
    model.eval()

    env = V4MultiAgentEnv(max_seq_len=max_seq_len)
    fallback_before = V4MultiAgentEnv._fallback_warned

    n_agari = 0
    n_tsumo = 0
    n_ron = 0
    n_ryuukyoku = 0
    n_truncated = 0
    payoff_abs_sum = 0.0
    winner_counts = np.zeros(4, dtype=np.int64)
    # 放铳 (deal-in / houjuu): in a Ron event, the loser who fed the winning
    # tile.  Identified as the non-winner seat with the most-negative payoff
    # in that hand.  In symmetric shared self-play one of the 4 seats will
    # deal in each Ron hand, so sum(houjuu_counts) == n_ron.
    houjuu_counts = np.zeros(4, dtype=np.int64)
    # Per-seat tsumo counts so all three "self-attribution" rates
    # (tsumo / ron-win / houjuu) can be reported side-by-side.
    tsumo_counts = np.zeros(4, dtype=np.int64)
    ron_win_counts = np.zeros(4, dtype=np.int64)
    ep_lengths: list[int] = []

    t0 = time.monotonic()
    try:
        for hand_idx in range(n_hands):
            try:
                obs: Optional[Dict[str, Any]] = env.reset(seed=seed + hand_idx)
            except Exception:
                # Engine refused to start this hand (very rare).  Skip it
                # without crashing the whole eval run.
                continue
            steps = 0
            terminated = False
            while obs is not None and not env.is_over() and steps < max_steps_per_hand:
                feat = torch.as_tensor(
                    obs["features"], device=device, dtype=torch.float32
                ).unsqueeze(0)
                attn = torch.as_tensor(
                    obs["attention_mask"], device=device, dtype=torch.bool
                ).unsqueeze(0)
                mask = torch.as_tensor(
                    obs["action_mask"], device=device, dtype=torch.bool
                ).unsqueeze(0)
                action, _, _ = model.act(
                    feat, attn, mask, deterministic=deterministic
                )
                obs, payoffs, done, info = env.step(int(action.item()))
                steps += 1
                if done:
                    terminated = True
                    ep_lengths.append(steps)
                    payoff_abs_sum += float(np.abs(payoffs).sum())
                    result_type = str(info.get("result_type", ""))
                    winners = info.get("winners", []) or []
                    if info.get("is_agari", False) and winners:
                        n_agari += 1
                        if "Tsumo" in result_type:
                            n_tsumo += 1
                            for w in winners:
                                if 0 <= int(w) < 4:
                                    tsumo_counts[int(w)] += 1
                        elif "Ron" in result_type:
                            n_ron += 1
                            for w in winners:
                                if 0 <= int(w) < 4:
                                    ron_win_counts[int(w)] += 1
                            # Houjuu seat = non-winner with the most-negative
                            # payoff.  Robust to multi-winner (double / triple
                            # ron) cases where several seats won off the same
                            # discharger.
                            if payoffs is not None:
                                winner_set = {int(w) for w in winners}
                                non_winners = [
                                    s for s in range(4) if s not in winner_set
                                ]
                                if non_winners:
                                    houjuu_seat = min(
                                        non_winners, key=lambda s: float(payoffs[s])
                                    )
                                    houjuu_counts[houjuu_seat] += 1
                        for w in winners:
                            if 0 <= int(w) < 4:
                                winner_counts[int(w)] += 1
                    else:
                        # No agari: ryuukyoku or other no-winner result.
                        n_ryuukyoku += 1
                    break
            if not terminated:
                n_truncated += 1
                ep_lengths.append(steps)
    finally:
        if was_training:
            model.train()

    dt = time.monotonic() - t0
    n_played = len(ep_lengths) or 1  # avoid div-by-zero in degenerate runs

    # Per-hand rate of "the model dealt in" averaged across seats == n_ron /
    # n_played because every Ron has exactly one discharger; we report it for
    # symmetry with tsumo/ron-win rates (they all add up to agari_rate).
    metrics: Dict[str, float] = {
        "sp/n_played": float(len(ep_lengths)),
        "sp/agari_rate": n_agari / n_played,
        "sp/tsumo_rate": n_tsumo / n_played,
        "sp/ron_rate": n_ron / n_played,
        "sp/houjuu_rate": int(houjuu_counts.sum()) / n_played,
        "sp/ryuukyoku_rate": n_ryuukyoku / n_played,
        "sp/truncated_rate": n_truncated / n_played,
        "sp/mean_ep_len": float(np.mean(ep_lengths)) if ep_lengths else 0.0,
        "sp/mean_abs_payoff": payoff_abs_sum / n_played,
        "sp/wall_s": dt,
        "sp/mask_fallback_fired": float(
            V4MultiAgentEnv._fallback_warned and not fallback_before
        ),
    }
    total_wins = int(winner_counts.sum())
    if total_wins > 0:
        for s in range(4):
            metrics[f"sp/winner_share_seat{s}"] = float(winner_counts[s]) / total_wins
    # Per-seat tsumo / ron-win / houjuu counts (raw, not normalized) -- the
    # caller can derive per-seat rates by dividing by n_played / 4 under
    # shared-policy self-play.
    for s in range(4):
        metrics[f"sp/tsumo_count_seat{s}"] = float(tsumo_counts[s])
        metrics[f"sp/ron_win_count_seat{s}"] = float(ron_win_counts[s])
        metrics[f"sp/houjuu_count_seat{s}"] = float(houjuu_counts[s])
    return metrics


def format_selfplay_metrics(metrics: Dict[str, float]) -> str:
    """Compact one-line summary for log output."""
    parts = [
        f"agari={metrics.get('sp/agari_rate', 0.0):.2f}",
        f"tsumo={metrics.get('sp/tsumo_rate', 0.0):.2f}",
        f"ron={metrics.get('sp/ron_rate', 0.0):.2f}",
        f"houjuu={metrics.get('sp/houjuu_rate', 0.0):.2f}",
        f"ryuu={metrics.get('sp/ryuukyoku_rate', 0.0):.2f}",
        f"trunc={metrics.get('sp/truncated_rate', 0.0):.2f}",
        f"ep_len={metrics.get('sp/mean_ep_len', 0.0):.1f}",
        f"|pay|={metrics.get('sp/mean_abs_payoff', 0.0):.2f}",
        f"n={int(metrics.get('sp/n_played', 0))}",
        f"t={metrics.get('sp/wall_s', 0.0):.1f}s",
    ]
    if metrics.get("sp/mask_fallback_fired", 0.0):
        parts.append("FALLBACK!")
    return "  ".join(parts)


@torch.no_grad()
def record_one_selfplay_hand(
    model,
    out_xml: str,
    *,
    seed: int = 0,
    max_seq_len: int = 512,
    deterministic: bool = True,
    max_steps: int = 1000,
    device=None,
    save_url: bool = True,
    title: str = "training-progress SP",
    subtitle: str = "",
) -> bool:
    """Roll out one shared-policy self-play hand and save it as Tenhou XML.

    Intended for in-training progress visualisation: drop into the BC
    loop alongside :func:`selfplay_eval_v4` and you get one watchable
    paipu per eval step.  If ``save_url`` is True, also writes a
    sibling ``.url.txt`` containing a tenhou paipu-editor URL.

    Returns:
        True if the hand finished cleanly and was recorded; False if
        the hand was truncated or the engine refused to start.
    """
    import os
    import MahjongPyWrapper as pm

    # Local imports keep optional dependencies optional at module load.
    try:
        from pymahjong.paipu_recorder import TenhouPaipuRecorder
    except Exception:
        return False

    if device is None:
        device = next(model.parameters()).device

    was_training = model.training
    model.eval()
    try:
        # Drive 4-seat shared self-play via V4MultiAgentEnv (same env the
        # main selfplay_eval uses).
        env_inner = V4MultiAgentEnv(max_seq_len=max_seq_len)
        try:
            obs = env_inner.reset(seed=seed)
        except Exception:
            return False
        steps = 0
        terminated = False
        while obs is not None and not env_inner.is_over() and steps < max_steps:
            feat = torch.as_tensor(
                obs["features"], device=device, dtype=torch.float32
            ).unsqueeze(0)
            attn = torch.as_tensor(
                obs["attention_mask"], device=device, dtype=torch.bool
            ).unsqueeze(0)
            mask = torch.as_tensor(
                obs["action_mask"], device=device, dtype=torch.bool
            ).unsqueeze(0)
            action, _, _ = model.act(feat, attn, mask, deterministic=deterministic)
            obs, _, done, _ = env_inner.step(int(action.item()))
            steps += 1
            if done:
                terminated = True
                break

        if not terminated:
            return False

        if int(env_inner._inner.t.get_phase()) != int(pm.PhaseEnum.GAME_OVER):
            return False

        rec = TenhouPaipuRecorder(player_names=["BC0", "BC1", "BC2", "BC3"])
        try:
            rec.record_hand(env_inner._inner.t, seed=seed)
        except Exception:
            return False
        os.makedirs(os.path.dirname(os.path.abspath(out_xml)) or ".", exist_ok=True)
        rec.save(out_xml)

        if save_url:
            try:
                from pymahjong.paipu_tenhou_json import (
                    xml_to_tenhou_json, make_editor_url,
                )
                data = xml_to_tenhou_json(out_xml, title=(title, subtitle))
                url = make_editor_url(data)
                url_path = out_xml[:-4] + ".url.txt" if out_xml.endswith(".xml") else out_xml + ".url.txt"
                with open(url_path, "w", encoding="utf-8") as f:
                    f.write(url + "\n")
            except Exception:
                pass
        return True
    finally:
        if was_training:
            model.train()


__all__ = ["selfplay_eval_v4", "format_selfplay_metrics", "record_one_selfplay_hand"]
