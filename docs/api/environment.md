# Environment

## MahjongEnv

Multi-agent Mahjong environment where 4 agents play against each other.

::: pymahjong.env_pymahjong.MahjongEnv
    options:
      members:
        - reset
        - step
        - get_obs
        - get_oracle_obs
        - get_full_obs
        - get_valid_actions
        - get_payoffs
        - is_over
        - get_curr_player_id
        - render
      show-inheritance:

### Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `observation_space` | `Box` | Executor observation space (93, 34) |
| `oracle_observation_space` | `Box` | Oracle observation space (18, 34) |
| `full_observation_space` | `Box` | Full observation space (111, 34) |
| `action_space` | `Discrete` | Action space (54 actions) |

### Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `PLAYER_OBS_DIM` | 93 | Executor observation channels |
| `ORACLE_OBS_DIM` | 18 | Oracle observation channels |
| `ACTION_DIM` | 54 | Number of discrete actions |
| `MAHJONG_TILE_TYPES` | 34 | Number of tile types |

## SingleAgentMahjongEnv

Single-agent environment compatible with OpenAI Gym interface.

::: pymahjong.env_pymahjong.SingleAgentMahjongEnv
    options:
      members:
        - reset
        - step
        - get_obs
        - get_oracle_obs
        - get_full_obs
        - get_valid_actions
        - render
      show-inheritance:

### Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `opponent_agent` | `str` | Either "random" or path to pretrained model |

### Attributes

Same as `MahjongEnv`.
