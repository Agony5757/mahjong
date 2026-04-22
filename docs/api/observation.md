# Observation

## Observation Encoding

Observations are encoded as boolean matrices where each element is 0 or 1.

### Executor Observation

Shape: `(93, 34)`

The executor observation contains all visible game state information.

#### Channel Groups

| Channels | Description |
|----------|-------------|
| 0-3 | Own hand tiles (counts up to 4) |
| 4-6 | Red dora in hand |
| 7-10 | Own melds (chi/pon/kan) |
| 11-13 | Red dora in melds |
| 14-17 | Own river tiles |
| 18-25 | Player 1's visible tiles |
| 26-33 | Player 2's visible tiles |
| 34-41 | Player 3's visible tiles |
| 42-44 | Dora indicators |
| 45-76 | Remaining tile counts |
| 77-92 | Game state flags |

### Oracle Observation

Shape: `(18, 34)`

The oracle observation contains hidden information - the opponents' hands.

| Channels | Description |
|----------|-------------|
| 0-3 | Player 1's hand |
| 4-7 | Player 2's hand |
| 8-11 | Player 3's hand |
| 12-14 | Red dora in opponents' hands |
| 15-17 | Hand size information |

### Full Observation

Shape: `(111, 34)`

The full observation is the concatenation of executor and oracle observations.

```python
full_obs = np.concatenate([executor_obs, oracle_obs], axis=0)
```

## Tile Encoding

The 34 columns represent tile types:

| Index | Tile | Index | Tile | Index | Tile |
|-------|------|-------|------|-------|------|
| 0 | 1m | 12 | 1p | 24 | 1s |
| 1 | 2m | 13 | 2p | 25 | 2s |
| 2 | 3m | 14 | 3p | 26 | 3s |
| 3 | 4m | 15 | 4p | 27 | 4s |
| 4 | 5m | 16 | 5p | 28 | 5s |
| 5 | 6m | 17 | 6p | 29 | 6s |
| 6 | 7m | 18 | 7p | 30 | 7s |
| 7 | 8m | 19 | 8p | 31 | 8s |
| 8 | 9m | 20 | 9p | 32 | 9s |
| 9 | East | 21 | White | 33 | (reserved) |
| 10 | South | 22 | Green | | |
| 11 | West | 23 | Red | | |

### Red Dora

Red dora (red 5m, 5p, 5s) are represented separately from regular 5 tiles. When using red dora, the corresponding action indices (34-36) should be used.
