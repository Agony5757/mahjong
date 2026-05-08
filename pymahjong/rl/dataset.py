"""Behavior-cloning dataset built from self-play / paipu replay traces.

We generate ``(obs, action)`` pairs in two ways:

1. **Self-play imitation** -- run an env where all 4 seats are controlled
   by an *expert* policy (e.g. the existing pretrained VLOG model, or a
   heuristic scripted bot) and record their actions. Convenient because
   it stays inside the engine.

2. **Paipu replay** -- use ``pm.PaipuReplayer`` to step through a recorded
   Tenhou paipu file and record the ground-truth action at every
   decision point.

Both produce :class:`MahjongDemoIterableDataset`, a torch
``IterableDataset`` that streams tokenized observations + actions.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional

import numpy as np
import torch
from torch.utils.data import IterableDataset

from .env_v2 import _resolve_action  # noqa: F401  (kept for reuse)
from .tokenization import ACTION_DIM, MahjongTokenizer

try:
    import MahjongPyWrapper as pm
except Exception:  # pragma: no cover
    pm = None


# ---------------------------------------------------------------------------
# Self-play imitation
# ---------------------------------------------------------------------------


class SelfPlayImitationDataset(IterableDataset):
    """Stream (obs, action) pairs from self-play of an expert policy.

    The expert returns an action *index in the engine's selection list*
    (NOT the 54-action discrete index). We translate it into the unified
    54-action representation for supervised training.

    Args:
        expert: callable ``expert(table, current_player) -> int`` returning
            the engine action index. Default uses uniformly random valid
            selections (useful for sanity checks).
        oracle: pass through to :class:`MahjongTokenizer`.
        max_games: stop after this many games (None → infinite).
        seed: optional RNG seed.
    """

    def __init__(
        self,
        expert: Optional[Callable] = None,
        oracle: bool = True,
        max_games: Optional[int] = None,
        seed: Optional[int] = None,
    ):
        if pm is None:
            raise ImportError("MahjongPyWrapper not available")
        self.expert = expert or self._random_expert
        self.tokenizer = MahjongTokenizer(include_oracle=oracle)
        self.max_games = max_games
        self.seed = seed

    @staticmethod
    def _random_expert(table, _player):
        phase = table.get_phase()
        actions = table.get_self_actions() if phase < 4 else table.get_response_actions()
        return int(np.random.randint(len(actions)))

    @staticmethod
    def _engine_idx_to_unified(table, engine_idx: int) -> int:
        """Map engine selection-list index to the 54-action space."""
        from pymahjong.env_pymahjong import MahjongEnv

        phase = table.get_phase()
        actions = table.get_self_actions() if phase < 4 else table.get_response_actions()
        sel = actions[engine_idx]
        BA = pm.BaseAction
        ba = int(sel.action)
        tiles = sel.correspond_tiles
        if ba == int(BA.Discard):
            t = tiles[0]
            base = int(t.tile)
            if getattr(t, "red_dora", False):
                if base == 4:
                    return MahjongEnv.CHILEFT_USERED  # placeholder unused
                # fallthrough handled below
            return base
        if ba == int(BA.Chi):
            used_red = any(getattr(t, "red_dora", False) for t in tiles)
            return MahjongEnv.CHIMIDDLE_USERED if used_red else MahjongEnv.CHIMIDDLE
        if ba == int(BA.Pon):
            used_red = any(getattr(t, "red_dora", False) for t in tiles)
            return MahjongEnv.PON_USERED if used_red else MahjongEnv.PON
        if ba == int(BA.AnKan):
            return MahjongEnv.ANKAN
        if ba == int(BA.Kan):
            return MahjongEnv.MINKAN
        if ba == int(BA.KaKan):
            return MahjongEnv.KAKAN
        if ba == int(BA.Riichi):
            return MahjongEnv.RIICHI
        if ba == int(BA.Ron):
            return MahjongEnv.RON
        if ba == int(BA.Tsumo):
            return MahjongEnv.TSUMO
        if ba == int(BA.Kyushukyuhai):
            return MahjongEnv.PUSH
        if ba == int(BA.Pass):
            return MahjongEnv.PASS_RESPONSE
        raise ValueError(f"unknown base action {ba}")

    def __iter__(self):
        if self.seed is not None:
            np.random.seed(self.seed)
        played = 0
        while self.max_games is None or played < self.max_games:
            table = pm.Table()
            table.game_init()
            while True:
                phase = table.get_phase()
                if phase == 16:  # GAME_OVER
                    break
                actions = table.get_self_actions() if phase < 4 else table.get_response_actions()
                if len(actions) == 0:
                    break
                seat = table.who_make_selection()
                if len(actions) == 1:
                    table.make_selection(0)
                    continue
                engine_idx = int(self.expert(table, seat))
                # Tokenize *before* taking the action.
                tok = self.tokenizer.encode(table, current_player=seat)
                unified = self._engine_idx_to_unified(table, engine_idx)
                yield {
                    "tokens": tok.tokens,
                    "attention_mask": tok.attention_mask,
                    "action_mask": tok.action_mask,
                    "action": np.int64(unified),
                }
                table.make_selection(engine_idx)
            played += 1


# ---------------------------------------------------------------------------
# Paipu replay
# ---------------------------------------------------------------------------


class PaipuReplayDataset(IterableDataset):
    """Stream (obs, action) pairs from a list of paipu files.

    Args:
        paipu_paths: iterable of paths to Tenhou paipu XML files.
        oracle: pass-through to tokenizer.
    """

    def __init__(self, paipu_paths: Iterable[str], oracle: bool = True):
        if pm is None:
            raise ImportError("MahjongPyWrapper not available")
        self.paths: List[str] = list(paipu_paths)
        self.tokenizer = MahjongTokenizer(include_oracle=oracle)

    def __iter__(self):
        for path in self.paths:
            try:
                rep = pm.PaipuReplayer()
                rep.init(path)
            except Exception:  # noqa: BLE001
                continue
            yield from self._replay_one(rep)

    def _replay_one(self, rep):
        # The PaipuReplayer exposes an iteration interface returning the
        # ground-truth action at each decision; the exact API is engine
        # specific. We stay defensive and rely only on
        # ``rep.table`` + ``rep.step()`` if available.
        if not hasattr(rep, "table") or not hasattr(rep, "step"):
            return
        table = rep.table
        while True:
            phase = table.get_phase()
            if phase == 16:
                return
            actions = table.get_self_actions() if phase < 4 else table.get_response_actions()
            if not actions:
                return
            seat = table.who_make_selection()
            tok = self.tokenizer.encode(table, current_player=seat)
            try:
                truth = rep.next_action()  # engine selection idx
            except Exception:  # noqa: BLE001
                return
            unified = SelfPlayImitationDataset._engine_idx_to_unified(table, int(truth))
            yield {
                "tokens": tok.tokens,
                "attention_mask": tok.attention_mask,
                "action_mask": tok.action_mask,
                "action": np.int64(unified),
            }
            try:
                rep.step()
            except Exception:  # noqa: BLE001
                return


# ---------------------------------------------------------------------------
# Collate
# ---------------------------------------------------------------------------


def collate_fn(batch):
    """Stack list of sample dicts into a single batch of tensors."""
    out = {}
    out["tokens"] = torch.as_tensor(
        np.stack([b["tokens"] for b in batch]), dtype=torch.long
    )
    out["attention_mask"] = torch.as_tensor(
        np.stack([b["attention_mask"] for b in batch]), dtype=torch.bool
    )
    out["action_mask"] = torch.as_tensor(
        np.stack([b["action_mask"] for b in batch]), dtype=torch.bool
    )
    out["action"] = torch.as_tensor(
        np.stack([b["action"] for b in batch]), dtype=torch.long
    )
    return out
