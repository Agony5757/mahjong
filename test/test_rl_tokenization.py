"""Smoke tests for the tokenized RL stack.

These tests don't require a GPU. They do require the pymahjong C++
wrapper to be importable; if it isn't, the tests are skipped.
"""

from __future__ import annotations

import importlib.util

import numpy as np
import pytest

HAVE_PM = importlib.util.find_spec("MahjongPyWrapper") is not None
pytestmark = pytest.mark.skipif(not HAVE_PM, reason="MahjongPyWrapper not installed")


def test_tokenizer_shape():
    import MahjongPyWrapper as pm
    from pymahjong.rl.tokenization import (
        ACTION_DIM,
        MAX_SEQ_LEN,
        TOKEN_FEATURES,
        MahjongTokenizer,
    )

    table = pm.Table()
    table.game_init()
    tok = MahjongTokenizer().encode(table, current_player=table.who_make_selection())
    assert tok.tokens.shape == (MAX_SEQ_LEN, TOKEN_FEATURES)
    assert tok.attention_mask.shape == (MAX_SEQ_LEN,)
    assert tok.action_mask.shape == (ACTION_DIM,)
    assert tok.attention_mask.sum() == tok.seq_len
    assert tok.action_mask.any(), "at least one action should be valid at game start"


def test_env_reset_step():
    import numpy as np

    from pymahjong.rl.env_v2 import TokenizedMahjongEnv

    env = TokenizedMahjongEnv()
    obs, _ = env.reset(seed=0)
    assert "tokens" in obs and "action_mask" in obs
    valid = np.flatnonzero(obs["action_mask"])
    assert len(valid) > 0
    obs, r, term, trunc, _ = env.step(int(valid[0]))
    assert isinstance(r, float)
    assert isinstance(term, bool)


def test_multi_agent_env():
    from pymahjong.rl.env_v2 import TokenizedMultiAgentEnv

    env = TokenizedMultiAgentEnv()
    obs = env.reset(seed=1)
    n_steps = 0
    while not env.is_over() and n_steps < 30:
        valid = np.flatnonzero(obs["action_mask"])
        assert len(valid) > 0
        obs, payoffs, done, info = env.step(int(valid[0]))
        n_steps += 1
        if done:
            break
    assert n_steps > 0


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None, reason="torch not installed"
)
def test_model_forward():
    import torch

    from pymahjong.rl.model import MahjongTransformer, TransformerConfig

    cfg = TransformerConfig(d_model=32, n_heads=2, n_layers=2)
    model = MahjongTransformer(config=cfg)

    B, L = 2, 16
    tokens = torch.zeros(B, L, 5, dtype=torch.long)
    attn = torch.ones(B, L, dtype=torch.bool)
    amask = torch.ones(B, 54, dtype=torch.bool)
    logits, value = model(tokens, attn, amask)
    assert logits.shape == (B, 54)
    assert value.shape == (B,)
