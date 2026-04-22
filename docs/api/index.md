# API Reference

```{toctree}
:maxdepth: 2

environment
observation
action
utilities
```

This section provides detailed documentation for the pymahjong API.

## Core Classes

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
