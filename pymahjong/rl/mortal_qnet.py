"""Mortal-style Q network: EventStreamTransformer encoder + Douzero Q-head.

Architecture (per the approved design):

* **State (feature) encoding**: the 100-dim event-stream is
  encoded by the *unmodified* :class:`EventStreamTransformer` (used purely
  as a state encoder via :meth:`EventStreamTransformer.encode`).
* **Action encoding (Douzero)**: each *legal* action's static
  descriptor (:func:`pymahjong.rl.action_features.torch_action_features`,
  ``ACTION_FEAT_DIM`` wide) is projected and concatenated with the pooled
  state, then scored by a shared MLP.
* **Q-head**: the shared scorer **outputs ``Q(s, a)`` directly** for each
  legal action (Douzero-style action values), masked to the legal set.
  (This deliberately drops Mortal's dueling ``v + a - a_mean``
  decomposition per the design decision -- the per-action scorer is the
  Q-function itself.)
* **Auxiliary next-rank head**: a small linear layer on the pooled state
  predicts the seat's final hanchan rank (Mortal's ``AuxNet((4,))``).

The scorer / action-projection layout is byte-compatible with the Douzero BC
model (:class:`~pymahjong.rl.douzero.DouzeroTransformer`), so a Douzero-head BC
checkpoint warm-starts both the encoder and the Q-head; a linear-head BC
checkpoint warm-starts the encoder only.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

import torch
import torch.nn as nn

from .common.config import TransformerConfig
from .transformer import EventStreamTransformer, NEG_INF
from .action_features import ACTION_FEAT_DIM, torch_action_features
from .legal_actions import extract_legal_actions


class DouzeroQHead(nn.Module):
    """Per-legal-action Q scorer over Douzero action descriptors.

    Args:
        d_model: pooled-state width (encoder output).
        action_feat_dim: descriptor width (default ``ACTION_FEAT_DIM``).
        action_proj_dim: action-embedding width (``None`` = ``d_model``).
        scorer_hidden: shared-MLP hidden width.
        scorer_dropout: dropout inside the scorer MLP.
        aux_rank: build the auxiliary final-rank head.
    """

    def __init__(
        self,
        d_model: int,
        action_feat_dim: int = ACTION_FEAT_DIM,
        action_proj_dim: Optional[int] = None,
        scorer_hidden: int = 256,
        scorer_dropout: float = 0.0,
        aux_rank: bool = True,
    ):
        super().__init__()
        action_proj_dim = action_proj_dim or d_model
        self.action_feat_dim = action_feat_dim
        self.action_proj_dim = action_proj_dim

        self.action_proj = nn.Linear(action_feat_dim, action_proj_dim)
        # Layout matches DouzeroTransformer.scorer for Douzero BC warm-start.
        self.scorer = nn.Sequential(
            nn.Linear(d_model + action_proj_dim, scorer_hidden),
            nn.GELU(),
            nn.Dropout(scorer_dropout),
            nn.Linear(scorer_hidden, scorer_hidden),
            nn.GELU(),
            nn.Dropout(scorer_dropout),
            nn.Linear(scorer_hidden, 1),
        )
        self.register_buffer(
            "default_action_descriptors", torch_action_features(), persistent=False
        )
        self.aux_rank = aux_rank
        if aux_rank:
            self.aux_rank_head = nn.Linear(d_model, 4)

    def score(
        self,
        h: torch.Tensor,                 # (B, D)
        action_features: torch.Tensor,   # (B, K, F)
        action_pad_mask: torch.Tensor,   # (B, K) bool
    ) -> torch.Tensor:
        """Return ``Q(s, a)`` ``(B, K)`` for the K legal actions (NEG_INF on pad)."""
        B, K, _ = action_features.shape
        a = self.action_proj(action_features)            # (B, K, D_a)
        h_rep = h.unsqueeze(1).expand(B, K, h.shape[-1])  # (B, K, D)
        x = torch.cat([h_rep, a], dim=-1)                # (B, K, D + D_a)
        q = self.scorer(x).squeeze(-1)                   # (B, K)
        return q.masked_fill(~action_pad_mask, NEG_INF)


class MortalQNet(nn.Module):
    """EventStreamTransformer encoder + :class:`DouzeroQHead`.

    Provides the value-learning interface used by the Mortal-style
    trainer: :meth:`evaluate_q` (training), :meth:`act_q` (collection),
    and :meth:`load_bc` (warm-start).
    """

    def __init__(
        self,
        config: Optional[TransformerConfig] = None,
        event_dim: int = 100,
        action_feat_dim: int = ACTION_FEAT_DIM,
        action_proj_dim: Optional[int] = None,
        scorer_hidden: int = 256,
        aux_rank: bool = True,
    ):
        super().__init__()
        cfg = config or TransformerConfig()
        self.cfg = cfg
        # The unmodified EventStreamTransformer is reused purely as a state
        # encoder via ``.encode``; its own policy/value heads are unused by
        # the Q path (they receive no gradient and stay at init).
        self.encoder = EventStreamTransformer(config=cfg, event_dim=event_dim)
        self.qhead = DouzeroQHead(
            d_model=cfg.d_model,
            action_feat_dim=action_feat_dim,
            action_proj_dim=action_proj_dim,
            scorer_hidden=scorer_hidden,
            scorer_dropout=cfg.dropout,
            aux_rank=aux_rank,
        )
        self.aux_rank = aux_rank

    # ------------------------------------------------------------------ core

    def _q_legal(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor,
        actions: Optional[torch.Tensor] = None,
    ):
        action_features, action_pad_mask, legal_orig_idx, target_in_K = (
            extract_legal_actions(
                action_mask,
                action_descriptors=self.qhead.default_action_descriptors,
                action=actions,
            )
        )
        h = self.encoder.encode(features, attention_mask)
        q_K = self.qhead.score(h, action_features, action_pad_mask)
        return h, q_K, action_pad_mask, legal_orig_idx, target_in_K

    def evaluate_q(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor,
        actions: torch.Tensor,
    ) -> Dict[str, torch.Tensor]:
        """Training forward: Q of the taken action + CQL logsumexp + aux.

        Returns ``q_taken`` ``(B,)``, ``q_logsumexp`` ``(B,)`` (over legal
        Q for the CQL term), and ``aux_logits`` ``(B, 4)`` or ``None``.
        """
        h, q_K, _pad, _legal, target_in_K = self._q_legal(
            features, attention_mask, action_mask, actions=actions
        )
        q_taken = q_K.gather(-1, target_in_K.unsqueeze(-1)).squeeze(-1)
        q_logsumexp = q_K.logsumexp(-1)
        aux_logits = self.qhead.aux_rank_head(h) if self.aux_rank else None
        return {"q_taken": q_taken, "q_logsumexp": q_logsumexp, "aux_logits": aux_logits}

    @torch.no_grad()
    def act_q(
        self,
        features: torch.Tensor,
        attention_mask: torch.Tensor,
        action_mask: torch.Tensor,
        epsilon: float = 0.0,
        deterministic: bool = True,
        generator: Optional[torch.Generator] = None,
    ) -> torch.Tensor:
        """Select a 54-space action per sample by (epsilon-)greedy Q."""
        _h, q_K, action_pad_mask, legal_orig_idx, _ = self._q_legal(
            features, attention_mask, action_mask, actions=None
        )
        B = q_K.size(0)
        if deterministic:
            idx_in_K = q_K.argmax(dim=-1)
        else:
            idx_in_K = torch.distributions.Categorical(logits=q_K).sample()

        if epsilon > 0.0:
            rand = torch.rand(B, device=q_K.device, generator=generator)
            explore = rand < epsilon
            if bool(explore.any()):
                noise = torch.rand_like(q_K).masked_fill(~action_pad_mask, -1.0)
                rand_idx = noise.argmax(dim=-1)
                idx_in_K = torch.where(explore, rand_idx, idx_in_K)

        return legal_orig_idx.gather(-1, idx_in_K.unsqueeze(-1)).squeeze(-1)

    # ------------------------------------------------------------------ warm-start

    def load_bc(self, path: str, map_location="cpu") -> Tuple[list, list]:
        """Warm-start from a linear-head or Douzero-head BC checkpoint.

        * Encoder weights (``input_proj`` / ``cls`` / ``pos_emb`` /
          ``encoder`` / ``norm`` / ``value_head`` / ``policy_head``) load
          into :attr:`encoder`.
        * Douzero Q-head weights (``action_proj`` / ``scorer``) load into
          :attr:`qhead` -- present only in Douzero-head checkpoints; for a linear-head
          checkpoint the Q-head stays freshly initialised.
        * A **MortalQNet self-checkpoint** (keys prefixed ``encoder.`` /
          ``qhead.``) is detected and loaded whole (resume), so the Q-head
          and aux head are restored too.

        Returns ``(missing_keys, loaded_qhead_keys)``.
        """
        ckpt = torch.load(path, map_location=map_location)
        state = ckpt.get("model", ckpt) if isinstance(ckpt, dict) else ckpt
        # A MortalQNet self-checkpoint stores keys under ``encoder.`` /
        # ``qhead.`` -- detect that layout and load the whole model directly
        # (resume), rather than treating it as a flat BC state_dict.
        #
        # NOTE: the detector must key off ``qhead.`` ONLY.  A flat BC
        # state_dict ALSO contains ``encoder.layers.*`` keys (that is the
        # nn.TransformerEncoder submodule of EventStreamTransformer), so
        # testing for an ``encoder.`` prefix would misclassify every BC
        # checkpoint as a self-checkpoint and load nothing.  Only a real
        # MortalQNet self-checkpoint has the ``qhead.`` prefix.
        if any(k.startswith("qhead.") for k in state):
            missing, unexpected = self.load_state_dict(state, strict=False)
            loaded = [k for k in state if k.startswith("qhead.")]
            return list(missing), loaded
        head_prefixes = ("action_proj.", "scorer.")
        enc_sd = {k: v for k, v in state.items() if not k.startswith(head_prefixes)}
        head_sd = {k: v for k, v in state.items() if k.startswith(head_prefixes)}
        enc_missing, _enc_unexpected = self.encoder.load_state_dict(enc_sd, strict=False)
        if head_sd:
            self.qhead.load_state_dict(head_sd, strict=False)
        return list(enc_missing), list(head_sd.keys())


__all__ = ["DouzeroQHead", "MortalQNet"]
