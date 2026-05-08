# Modern Transformer-based RL Stack for pymahjong

This subpackage (`pymahjong.rl`) provides a self-contained, transformer-based
reinforcement-learning solution for the Riichi Mahjong engine, with two
training stages and a *new* tokenized state/action encoding that no longer
depends on the C++ `encv1` / `encv2` dense matrix encoders.

## Why a new encoding?

The existing 93×34 / 18×34 encodings are CNN-friendly but inefficient for
attention models — most cells are zero, and the layout buries semantics in
channel offsets. The new encoding represents a state as a *variable-length
sequence of tokens*, where each token carries `(segment, tile, count, who,
extra)`. Per-field embedding tables are summed before the transformer.

| Property | Old (V1/V2) | New |
|---|---|---|
| Shape | dense `[C, 34]` | `[L, 5]` int32 + mask |
| Avg tokens per state | always 93 | ~30–80 |
| Engine dep | C++ encoder | pure Python on `pm.Table` |
| Action mask | not exposed | yes (`[54]` bool) |
| Oracle info | separate channels | optional segment |

The action space is kept at 54 discrete actions to remain plug-compatible
with the existing engine and pretrained models.

## Files

| File | Purpose |
|---|---|
| `tokenization.py` | `MahjongTokenizer` — pure Python, no C++ encoding dep. |
| `env_v2.py` | `TokenizedMahjongEnv` (single-agent, gym), `TokenizedMultiAgentEnv` (4-player). |
| `model.py` | `MahjongTransformer` — policy + value transformer. |
| `dataset.py` | `SelfPlayImitationDataset`, `PaipuReplayDataset`. |
| `bc.py` | Stage 1: behavior cloning trainer (`train_bc`). |
| `buffers.py` | `RolloutBuffer` with masks + GAE. |
| `ppo.py` | Stage 2: PPO + self-play trainer (`train_ppo`). |

## Two-stage training

### Stage 1 — Supervised behavior cloning

```python
from pymahjong.rl.bc import train_bc, BCConfig
from pymahjong.rl.dataset import SelfPlayImitationDataset

ds = SelfPlayImitationDataset(expert=my_expert_or_None, oracle=True)
model = train_bc(
    dataset=ds,
    config=BCConfig(n_steps=200_000, save_path="checkpoints/bc.pt"),
)
```

The default expert is uniformly random — useful only as a smoke test.
Provide an expert callable `expert(table, current_player) -> engine_idx`
(e.g. wrap a heuristic bot or the existing pretrained `VLOG_BC` model).

### Stage 2 — PPO self-play

```python
from pymahjong.rl import train_ppo
from pymahjong.rl.ppo import PPOConfig

train_ppo(
    bc_checkpoint="checkpoints/bc.pt",
    config=PPOConfig(total_steps=10_000_000, save_path="checkpoints/ppo.pt"),
)
```

The PPO trainer uses **shared parameters across all 4 seats**: each rollout
collects per-seat transitions from `TokenizedMultiAgentEnv` and assigns the
final episode payoff (in `points/25000`) as the terminal reward.
Intermediate rewards are zero. Action masking is used in both the
loss and the entropy regularizer.

## Backward compatibility

* The existing `MahjongEnv` / `SingleAgentMahjongEnv` and pretrained
  models (`mahjong_VLOG_BC.pth`, `mahjong_VLOG_CQL.pth`) are untouched.
* `pymahjong.rl` is opt-in. PyTorch is an optional dependency.

## Notes / Future work

* The current `_resolve_action` in `env_v2.py` does a linear scan over engine
  selections; for chi variants the disambiguation is heuristic. A cleaner fix
  is to expose `take` / variant info from the C++ side — see follow-up issue.
* `PaipuReplayDataset` requires a `PaipuReplayer.next_action`/`step` API
  that the current C++ replayer does not yet expose; left as a stub for
  the future.
