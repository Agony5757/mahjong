"""Tests for the offline Mortal-style CQL pipeline (reward-annotated cache
+ offline trainer)."""
from __future__ import annotations

import glob

import numpy as np
import pytest

torch = pytest.importorskip("torch")
pm = pytest.importorskip("MahjongPyWrapper")

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.v4.cache import V4ShardWriter, open_shard_arrays_v4
from pymahjong.rl.v5.offline import OfflineConfig, OfflineMortalTrainer


def _tiny_cfg() -> TransformerConfig:
    return TransformerConfig(d_model=48, n_layers=2, n_heads=4, ff_mult=2, dropout=0.0)


def _mask(legal):
    m = np.zeros(54, dtype=np.bool_)
    m[legal] = True
    return m


def test_shard_writer_rl_targets_roundtrip(tmp_path):
    sd = str(tmp_path / "shard0")
    w = V4ShardWriter(sd)
    for i in range(3):
        w.add({
            "features": np.ones((4, 100), dtype=np.bool_),
            "action_mask": _mask([0, 1, 5]),
            "action": 0,
            "track_id": i,
            "game_id": 7,
            "q_reward": float(i) - 1.0,
            "player_rank": i % 4,
            "steps_to_done": 2 - i,
        })
    w.close()

    arr = open_shard_arrays_v4(str(tmp_path), "shard0")
    assert arr["rewards"] is not None
    assert list(np.asarray(arr["rewards"])) == [-1.0, 0.0, 1.0]
    assert list(np.asarray(arr["ranks"])) == [0, 1, 2]
    assert list(np.asarray(arr["steps_to_done"])) == [2, 1, 0]


def test_shard_writer_rl_targets_all_or_nothing(tmp_path):
    sd = str(tmp_path / "shard_mixed")
    w = V4ShardWriter(sd)
    w.add({"features": np.ones((4, 100), np.bool_), "action_mask": _mask([0, 1]),
           "action": 0, "track_id": 0, "game_id": 0,
           "q_reward": 1.0, "player_rank": 0, "steps_to_done": 0})
    w.add({"features": np.ones((4, 100), np.bool_), "action_mask": _mask([0, 1]),
           "action": 1, "track_id": 1, "game_id": 0})  # missing RL targets
    with pytest.raises(ValueError):
        w.close()


def test_bc_cache_has_no_rl_targets(tmp_path):
    sd = str(tmp_path / "shard_bc")
    w = V4ShardWriter(sd)
    w.add({"features": np.ones((4, 100), np.bool_), "action_mask": _mask([0, 1]),
           "action": 0, "track_id": 0, "game_id": 0})
    w.close()
    arr = open_shard_arrays_v4(str(tmp_path), "shard_bc")
    assert arr["rewards"] is None and arr["ranks"] is None


def test_offline_trainer_step_updates_params():
    tcfg = _tiny_cfg()
    cfg = OfflineConfig(cache_dir="", batch_size=4, scorer_hidden=32, device="cpu",
                        cql_enable=True, min_q_weight=5.0, next_rank_weight=0.2,
                        gamma=1.0, weight_decay=0.1, seed=0)
    tr = OfflineMortalTrainer(config=cfg, transformer_config=tcfg)

    B, L = 4, 6
    legals = [[0, 1, 5, 37], [2, 3, 4], [0, 6, 10], [1, 2, 43]]
    actions = [0, 2, 6, 43]  # one legal action per sample
    batch = {
        "features": torch.rand(B, L, 100) > 0.5,
        "attention_mask": torch.ones(B, L, dtype=torch.bool),
        "action_mask": torch.stack([torch.from_numpy(_mask(lg)) for lg in legals]),
        "action": torch.tensor(actions, dtype=torch.long),
        "q_reward": torch.tensor([1.0, -1.0, 0.5, -0.5], dtype=torch.float32),
        "player_rank": torch.tensor([0, 3, 1, 2], dtype=torch.long),
        "steps_to_done": torch.tensor([3, 0, 5, 1], dtype=torch.long),
    }
    before = [p.detach().clone() for p in tr.model.parameters()]
    m = tr._train_step(batch)
    assert all(np.isfinite(v) for v in m.values()), m
    assert m["cql_loss"] != 0.0, "CQL term should be active"
    assert any(not torch.equal(b, a) for b, a in zip(before, tr.model.parameters())), \
        "offline step must update params"


def test_offline_gamma1_qtarget_equals_reward():
    # With Mortal's gamma=1 the MC target equals the per-kyoku reward
    # regardless of steps_to_done.
    tcfg = _tiny_cfg()
    cfg = OfflineConfig(cache_dir="", batch_size=2, scorer_hidden=32, device="cpu",
                        gamma=1.0, seed=0)
    tr = OfflineMortalTrainer(config=cfg, transformer_config=tcfg)
    batch = {
        "features": torch.rand(2, 4, 100) > 0.5,
        "attention_mask": torch.ones(2, 4, dtype=torch.bool),
        "action_mask": torch.stack([torch.from_numpy(_mask([0, 1])),
                                    torch.from_numpy(_mask([0, 1]))]),
        "action": torch.tensor([0, 1], dtype=torch.long),
        "q_reward": torch.tensor([2.0, -3.0], dtype=torch.float32),
        "player_rank": torch.tensor([0, 3], dtype=torch.long),
        "steps_to_done": torch.tensor([7, 13], dtype=torch.long),  # arbitrary
    }
    m = tr._train_step(batch)
    # q_target_mean = mean(reward) since gamma**steps == 1
    assert abs(m["q_target_mean"] - (-0.5)) < 1e-5, m["q_target_mean"]


@pytest.mark.skipif(not glob.glob("paipuxmls/*"), reason="no local paipu files")
def test_reward_annotation_telescopes_on_paipu():
    from pymahjong.rl.v4.tokenization import encode_paipu_file_v4
    f = sorted(glob.glob("paipuxmls/*"))[0]
    samples = encode_paipu_file_v4(f, pts=[6.0, 4.0, 2.0, 0.0])
    assert samples, "no samples extracted"
    for s in samples:
        assert {"q_reward", "player_rank", "steps_to_done"} <= set(s)
    # ranks are a permutation of 0..3 across the four seats
    seat_rank = {s["_seat"]: s["player_rank"] for s in samples}
    assert sorted(seat_rank.values()) == [0, 1, 2, 3]
    # per seat, the sum of the distinct per-hand rewards telescopes to
    # (final placement pts - mean pts); across seats this sums to ~0.
    per_seat = {}
    for s in samples:
        per_seat.setdefault(s["_seat"], {})[s["_hand_idx"]] = s["q_reward"]
    totals = [sum(hd.values()) for hd in per_seat.values()]
    assert abs(sum(totals)) < 1e-3, f"placement deltas must sum to ~0: {totals}"


def test_mortal_eval_aggregate_summaries_matches_serial():
    # The parallel-eval aggregator must merge per-chunk bench summaries by
    # summing rank_counts and recomputing avg_rank exactly (so parallel eval
    # == serial eval over the same seed set).
    from pymahjong.rl.v4.mortal_eval import _aggregate_summaries
    s1 = {"rank_counts": [[2, 1, 0, 0], [0, 1, 1, 1], [1, 1, 1, 0], [0, 0, 1, 2]],
          "avg_pt_delta_vs_25k": [10.0, -5.0, 2.0, -7.0]}
    s2 = {"rank_counts": [[1, 0, 1, 1], [1, 1, 0, 1], [1, 1, 0, 1], [0, 1, 2, 0]],
          "avg_pt_delta_vs_25k": [6.0, -3.0, 4.0, -7.0]}
    m = _aggregate_summaries([s1, s2, None])
    assert m["rank_counts"][0] == [3, 1, 1, 1]              # summed
    assert abs(m["avg_rank"][0] - 2.0) < 1e-9               # (3+2+3+4)/6
    assert abs(m["avg_pt_delta_vs_25k"][0] - 8.0) < 1e-9    # (10*3+6*3)/6
    assert _aggregate_summaries([None, None]) is None
