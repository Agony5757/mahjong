# Utilities

## Test Functions

::: pymahjong.test.test
    options:
      show-signature:

::: pymahjong.test.test_with_pretrained
    options:
      show-signature:

## Paipu Replay

::: pymahjong.tenhou_paipu_check.paipu_replay
    options:
      show-signature:

::: pymahjong.tenhou_paipu_check.paipu_replay_1
    options:
      show-signature:

## Pretrained Models

### VLOGMahjong

The VLOG (Variational Latent Oracle Guiding) model used as pretrained opponents.

::: pymahjong.models.VLOGMahjong
    options:
      members:
        - select
        - forward
      show-inheritance:

### Model Files

Two pretrained models are available:

| Model | Description |
|-------|-------------|
| `mahjong_VLOG_CQL.pth` | VLOG + Conservative Q-learning |
| `mahjong_VLOG_BC.pth` | VLOG + Behavior Cloning |

Download from [GitHub Releases](https://github.com/Agony5757/mahjong/releases).

## C++ Backend Classes

The following classes are exposed from the C++ backend via pybind11:

### Table

```python
import MahjongPyWrapper as pm

table = pm.Table()
table.game_init()
table.get_phase()
table.get_self_actions()
table.get_response_actions()
table.make_selection(0)
```

### Player

```python
player = table.players[0]
player.hand          # List of tiles
player.river         # Discarded tiles
player.score         # Player score
player.riichi        # Riichi status
player.is_tenpai()   # Check tenpai
```

### Tile

```python
tile = player.hand[0]
tile.tile      # BaseTile enum
tile.red_dora  # Whether red dora
tile.id        # Unique tile ID
```

### BaseAction Enum

```python
pm.BaseAction.Discard
pm.BaseAction.Chi
pm.BaseAction.Pon
pm.BaseAction.Kan
pm.BaseAction.Ron
pm.BaseAction.AnKan
pm.BaseAction.KaKan
pm.BaseAction.Riichi
pm.BaseAction.Tsumo
pm.BaseAction.Kyushukyuhai
pm.BaseAction.Pass
```

### BaseTile Enum

```python
# Characters (Man)
pm.BaseTile._1m  # through pm.BaseTile._9m

# Dots (Pin)
pm.BaseTile._1p  # through pm.BaseTile._9p

# Bamboo (Sou)
pm.BaseTile._1s  # through pm.BaseTile._9s

# Winds
pm.BaseTile.east
pm.BaseTile.south
pm.BaseTile.west
pm.BaseTile.north

# Dragons
pm.BaseTile.haku  # White
pm.BaseTile.hatsu # Green
pm.BaseTile.chu   # Red
```
