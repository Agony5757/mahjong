"""Offline Mortal-style value learning (conservative Q-learning) on a
reward-annotated expert cache.

This is the **faithful port of Mortal's main RL phase** (``online = false``
in Mortal's ``config.toml``): the Q-function is trained on Tenhou *expert*
decisions (the cached BC actions) rather than self-play, with

* **MC Q-target** ``q_target = gamma ** steps_to_done * kyoku_reward`` and
  Mortal's ``gamma = 1`` (so the target is just the per-kyoku placement
  reward; ``steps_to_done`` is carried for generality),
* **DQN loss** ``0.5 * MSE(q_taken, q_target)``,
* **CQL conservatism** ``min_q_weight * (logsumexp_a q - q_taken)`` — the
  conservative term Mortal applies *only* in the offline phase, here with
  Mortal's ``min_q_weight = 5``,
* **auxiliary next-rank head** ``next_rank_weight * CE(aux_logits, rank)``.

The network is **our** :class:`~pymahjong.rl.v5.mortal_qnet.MortalQNet`
(EventStreamTransformer encoder + Douzero Q-head + aux-rank head), warm-
started from a BC checkpoint.  The optimiser is Mortal's AdamW with weight
decay applied only to Linear weights (``weight_decay = 0.1``), constant
``lr = 1e-4``, no gradient clipping, ``batch_size = 512``.

Data comes from a cache built by ``tools/encode_paipu_to_cache_v4.py
--pts 6 4 2 0`` (see :mod:`pymahjong.rl.v4.cache` /
:mod:`pymahjong.rl.v4.cached_dataset`).
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import numpy as np

try:
    import torch
    import torch.nn.functional as F
    from torch.utils.data import DataLoader
except Exception as e:  # noqa: BLE001
    raise RuntimeError("torch is required for offline Mortal V5 training") from e

from ..common.config import TransformerConfig
from ..v4.cached_dataset import CachedEventDataset, cached_event_collate
from .mortal_qnet import MortalQNet


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class OfflineConfig:
    """Configuration for offline Mortal-style CQL training (Mortal defaults)."""

    cache_dir: str = ""
    """Reward-annotated V4 cache (must have rewards/ranks/steps_to_done)."""

    # -- schedule --
    num_epochs: int = 1
    total_steps: int = 0
    """Optimisation-step cap (``0`` = run the full ``num_epochs``)."""
    batch_size: int = 512          # Mortal
    num_workers: int = 4
    max_seq_len: int = 512

    # -- optimisation (Mortal) --
    gamma: float = 1.0             # Mortal: no discount
    lr: float = 1e-4               # Mortal: constant peak=final
    weight_decay: float = 0.1      # Mortal: on Linear weights only
    grad_clip: float = 0.0         # Mortal: max_grad_norm = 0 (off)

    # -- Mortal loss weights --
    cql_enable: bool = True        # Mortal: CQL on in the offline phase
    min_q_weight: float = 5.0      # Mortal
    next_rank_weight: float = 0.2  # Mortal

    # -- architecture (must match the BC ckpt) --
    scorer_hidden: int = 256
    action_proj_dim: Optional[int] = None

    # -- I/O --
    save_path: str = "checkpoints/offline_mortal.pt"
    save_interval: int = 20000
    keep_periodic: bool = True
    log_interval: int = 50

    # -- misc --
    device: Optional[str] = None
    seed: Optional[int] = None

    # -- Mortal head-to-head eval (optional; reuses the bench harness) --
    mortal_eval: bool = False
    mortal_eval_hanchan: int = 1000
    mortal_eval_workers: int = 1
    """Concurrent bench processes per matchup (splits n_hanchan; bench is
    latency-bound with low GPU util, so 4-8 gives a near-linear speedup)."""
    mortal_bench_script: Optional[str] = None
    mortal_bench_cwd: Optional[str] = None
    mortal_ckpt: Optional[str] = None
    mortal_eval_python: Optional[str] = None
    mortal_eval_out_dir: Optional[str] = None
    mortal_eval_seed_start: int = 10000
    mortal_eval_seed_key: int = 4242
    mortal_eval_timeout_sec: float = 36000.0
    mortal_eval_amp: bool = False

    # -- wandb (optional) --
    wandb_project: Optional[str] = None
    wandb_entity: Optional[str] = None
    wandb_name: Optional[str] = None
    wandb_tags: Optional[Tuple[str, ...]] = None
    wandb_mode: str = "online"


# ---------------------------------------------------------------------------
# Trainer
# ---------------------------------------------------------------------------


class OfflineMortalTrainer:
    def __init__(
        self,
        config: Optional[OfflineConfig] = None,
        transformer_config: Optional[TransformerConfig] = None,
        bc_checkpoint: Optional[str] = None,
    ):
        self.cfg = config or OfflineConfig()
        self.tcfg = transformer_config or TransformerConfig()
        self._device = torch.device(
            self.cfg.device if self.cfg.device
            else ("cuda" if torch.cuda.is_available() else "cpu")
        )
        if self.cfg.seed is not None:
            torch.manual_seed(self.cfg.seed)
            np.random.seed(self.cfg.seed)

        self.model = MortalQNet(
            config=self.tcfg,
            scorer_hidden=self.cfg.scorer_hidden,
            action_proj_dim=self.cfg.action_proj_dim,
            aux_rank=True,
        ).to(self._device)

        if bc_checkpoint and os.path.exists(bc_checkpoint):
            enc_missing, head_loaded = self.model.load_bc(bc_checkpoint, map_location=self._device)
            print(
                f"[offline-mortal] warm-started from {bc_checkpoint} "
                f"(encoder missing={len(enc_missing)}, Q-head keys loaded={len(head_loaded)})",
                flush=True,
            )

        self.optim = self._build_optimizer()
        self._total = 0
        self._last_mortal_eval_step = -1
        self._wandb = self._maybe_init_wandb()

    # ------------------------------------------------------------------ optim

    def _build_optimizer(self) -> "torch.optim.Optimizer":
        # Mortal param grouping: weight decay only on Linear/Conv weights.
        params_dict: Dict[str, torch.Tensor] = {}
        to_decay: set = set()
        for mod_name, mod in self.model.named_modules():
            for name, param in mod.named_parameters(prefix=mod_name, recurse=False):
                params_dict[name] = param
                if isinstance(mod, (torch.nn.Linear, torch.nn.Conv1d)) and name.endswith("weight"):
                    to_decay.add(name)
        decay = [params_dict[n] for n in sorted(to_decay)]
        no_decay = [params_dict[n] for n in sorted(params_dict.keys() - to_decay)]
        return torch.optim.AdamW(
            [
                {"params": decay, "weight_decay": self.cfg.weight_decay},
                {"params": no_decay, "weight_decay": 0.0},
            ],
            lr=self.cfg.lr,
            betas=(0.9, 0.999),
            eps=1e-8,
        )

    # ------------------------------------------------------------------ wandb

    def _maybe_init_wandb(self):
        if not self.cfg.wandb_project:
            return None
        try:
            import wandb  # noqa: PLC0415
        except ImportError:
            print("[offline-mortal] wandb requested but not installed; skipping.", flush=True)
            return None
        return wandb.init(
            project=self.cfg.wandb_project,
            entity=self.cfg.wandb_entity,
            name=self.cfg.wandb_name,
            tags=list(self.cfg.wandb_tags) if self.cfg.wandb_tags else None,
            mode=self.cfg.wandb_mode,
            config={k: getattr(self.cfg, k) for k in (
                "lr", "gamma", "batch_size", "num_epochs", "weight_decay",
                "cql_enable", "min_q_weight", "next_rank_weight",
                "mortal_eval", "mortal_eval_hanchan",
            )},
        )

    def _wandb_log(self, data: dict) -> None:
        if self._wandb is not None:
            self._wandb.log({**data, "step": self._total})

    # ------------------------------------------------------------------ step

    def _train_step(self, batch: Dict[str, torch.Tensor]) -> Dict[str, float]:
        cfg = self.cfg
        feats = batch["features"].to(self._device, dtype=torch.float32)
        attn = batch["attention_mask"].to(self._device)
        amask = batch["action_mask"].to(self._device)
        actions = batch["action"].to(self._device)
        q_reward = batch["q_reward"].to(self._device, dtype=torch.float32)
        steps = batch["steps_to_done"].to(self._device, dtype=torch.float32)
        ranks = batch["player_rank"].to(self._device)

        q_target = (cfg.gamma ** steps) * q_reward

        self.model.train()
        out = self.model.evaluate_q(feats, attn, amask, actions)
        q_taken = out["q_taken"]
        dqn_loss = 0.5 * F.mse_loss(q_taken, q_target)
        cql_loss = q_taken.new_zeros(())
        if cfg.cql_enable:
            cql_loss = (out["q_logsumexp"] - q_taken).mean()
        rank_loss = q_taken.new_zeros(())
        if out["aux_logits"] is not None:
            rank_loss = F.cross_entropy(out["aux_logits"], ranks)

        loss = (
            dqn_loss
            + (cfg.min_q_weight * cql_loss if cfg.cql_enable else 0.0)
            + cfg.next_rank_weight * rank_loss
        )
        self.optim.zero_grad(set_to_none=True)
        loss.backward()
        if cfg.grad_clip > 0:
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), cfg.grad_clip)
        self.optim.step()

        return {
            "dqn_loss": float(dqn_loss.item()),
            "cql_loss": float(cql_loss.item()) if cfg.cql_enable else 0.0,
            "rank_loss": float(rank_loss.item()),
            "q_mean": float(q_taken.mean().item()),
            "q_target_mean": float(q_target.mean().item()),
        }

    # ------------------------------------------------------------------ save / eval

    def _v5_state_dict(self) -> Dict[str, torch.Tensor]:
        """Remap MortalQNet -> DouzeroV5Transformer layout for the bench."""
        v5_sd: Dict[str, torch.Tensor] = {}
        for k, v in self.model.encoder.state_dict().items():
            if k.startswith("policy_head"):
                continue
            v5_sd[k] = v
        for k, v in self.model.qhead.state_dict().items():
            if k.startswith("aux_rank_head") or k == "default_action_descriptors":
                continue
            v5_sd[k] = v
        return v5_sd

    def _save(self) -> None:
        if not self.cfg.save_path:
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.cfg.save_path)) or ".", exist_ok=True)
        payload = {
            "model": self.model.state_dict(),
            "encoder": self.model.encoder.state_dict(),
            "qhead": self.model.qhead.state_dict(),
            "step": self._total,
            "config": self.cfg.__dict__,
            "transformer_config": self.tcfg.__dict__,
        }
        tmp = self.cfg.save_path + ".tmp"
        torch.save(payload, tmp)
        os.replace(tmp, self.cfg.save_path)
        if self.cfg.keep_periodic:
            stem, ext = os.path.splitext(self.cfg.save_path)
            periodic = f"{stem}.step_{self._total:09d}{ext or '.pt'}"
            try:
                if os.path.exists(periodic):
                    os.remove(periodic)
                os.link(self.cfg.save_path, periodic)
            except OSError:
                import shutil
                shutil.copy2(self.cfg.save_path, periodic)

    def _run_mortal_eval(self) -> None:
        cfg = self.cfg
        if not cfg.mortal_eval or self._total == self._last_mortal_eval_step:
            return
        missing = [n for n, v in (("mortal_bench_script", cfg.mortal_bench_script),
                                  ("mortal_bench_cwd", cfg.mortal_bench_cwd),
                                  ("mortal_ckpt", cfg.mortal_ckpt)) if not v]
        if missing:
            print(f"[mortal-eval] disabled: missing config {missing}", flush=True)
            return
        try:
            from ..v4.mortal_eval import run_mortal_matchups
        except Exception as e:  # noqa: BLE001
            print(f"[mortal-eval] import failed: {e!r}", flush=True)
            return
        base = os.path.dirname(os.path.abspath(cfg.save_path or "checkpoints/offline_mortal.pt")) or "."
        frozen = os.path.join(base, f"_offline_eval_v5_step_{self._total}.pt")
        try:
            torch.save({"model": self._v5_state_dict(),
                        "transformer_config": self.tcfg.__dict__}, frozen)
        except Exception as e:  # noqa: BLE001
            print(f"[mortal-eval] V5 export failed: {e!r}", flush=True)
            return
        out_root = cfg.mortal_eval_out_dir or os.path.join(base, "mortal_eval")
        out_dir = os.path.join(out_root, f"step_{self._total}")
        was_training = self.model.training
        t0 = time.time()
        try:
            if self._device.type == "cuda":
                torch.cuda.empty_cache()
            metrics = run_mortal_matchups(
                frozen,
                bench_script=cfg.mortal_bench_script,
                bench_cwd=cfg.mortal_bench_cwd,
                mortal_ckpt=cfg.mortal_ckpt,
                out_dir=out_dir,
                n_hanchan=cfg.mortal_eval_hanchan,
                d_model=self.tcfg.d_model,
                n_heads=self.tcfg.n_heads,
                n_layers=self.tcfg.n_layers,
                ff_mult=self.tcfg.ff_mult,
                scorer_hidden=cfg.scorer_hidden,
                eval_python=cfg.mortal_eval_python,
                seed_start=cfg.mortal_eval_seed_start,
                seed_key=cfg.mortal_eval_seed_key,
                device="cuda" if self._device.type == "cuda" else "cpu",
                amp=cfg.mortal_eval_amp,
                timeout_sec=cfg.mortal_eval_timeout_sec,
                n_workers=cfg.mortal_eval_workers,
            )
            self._last_mortal_eval_step = self._total
            r13 = metrics.get("mortal/1v3/v5_avg_rank")
            r31 = metrics.get("mortal/3v1/v5_avg_rank")
            print(
                f"[mortal-eval] step={self._total} done in {time.time()-t0:.0f}s  "
                f"1v3 v5_avg_rank={r13 if r13 is None else round(r13,3)}  "
                f"3v1 v5_avg_rank={r31 if r31 is None else round(r31,3)}",
                flush=True,
            )
            self._wandb_log(metrics)
        except Exception as e:  # noqa: BLE001
            print(f"[mortal-eval] step={self._total} failed: {e!r}", flush=True)
        finally:
            if was_training:
                self.model.train()
            try:
                if os.path.exists(frozen):
                    os.remove(frozen)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ loop

    def train(self) -> MortalQNet:
        cfg = self.cfg
        ds = CachedEventDataset(cfg.cache_dir)
        if len(ds) == 0:
            raise RuntimeError(f"empty cache: {cfg.cache_dir}")
        loader = DataLoader(
            ds,
            batch_size=cfg.batch_size,
            shuffle=True,
            drop_last=True,
            num_workers=cfg.num_workers,
            pin_memory=(self._device.type == "cuda"),
            collate_fn=cached_event_collate,
            persistent_workers=(cfg.num_workers > 0),
        )
        # Probe that the cache carries RL targets.
        probe = ds[0]
        if "q_reward" not in probe:
            raise RuntimeError(
                f"cache {cfg.cache_dir} has no RL targets; rebuild with "
                "tools/encode_paipu_to_cache_v4.py --pts 6 4 2 0"
            )
        print(f"[offline-mortal] cache rows: {len(ds):,}  batches/epoch: {len(loader):,}", flush=True)

        if cfg.mortal_eval:
            print("[offline-mortal] step=0 running step-0 baseline eval...", flush=True)
            self._run_mortal_eval()

        acc: Dict[str, float] = {}
        n_acc = 0
        t0 = time.time()
        stop = False
        for epoch in range(cfg.num_epochs):
            for batch in loader:
                m = self._train_step(batch)
                self._total += 1
                for k, v in m.items():
                    acc[k] = acc.get(k, 0.0) + v
                n_acc += 1

                if self._total % cfg.log_interval == 0:
                    avg = {k: v / n_acc for k, v in acc.items()}
                    sps = n_acc * cfg.batch_size / max(time.time() - t0, 1e-9)
                    print(
                        f"[offline-mortal] step={self._total} epoch={epoch} "
                        f"dqn={avg['dqn_loss']:.4f} cql={avg['cql_loss']:.4f} "
                        f"rank={avg['rank_loss']:.4f} q={avg['q_mean']:.3f} "
                        f"q_tgt={avg['q_target_mean']:.3f} {sps:.0f} samp/s",
                        flush=True,
                    )
                    self._wandb_log({
                        "train/dqn_loss": avg["dqn_loss"],
                        "train/cql_loss": avg["cql_loss"],
                        "train/rank_loss": avg["rank_loss"],
                        "train/q_mean": avg["q_mean"],
                        "train/q_target_mean": avg["q_target_mean"],
                    })
                    acc = {}
                    n_acc = 0
                    t0 = time.time()

                if self._total % cfg.save_interval == 0:
                    self._save()
                    self._run_mortal_eval()

                if cfg.total_steps and self._total >= cfg.total_steps:
                    stop = True
                    break
            if stop:
                break

        self._save()
        self._run_mortal_eval()
        if self._wandb is not None:
            self._wandb.finish()
        return self.model


def train_offline_mortal(
    bc_checkpoint: Optional[str] = None,
    config: Optional[OfflineConfig] = None,
    transformer_config: Optional[TransformerConfig] = None,
) -> MortalQNet:
    """Entry point: offline Mortal-style CQL training on an expert cache."""
    trainer = OfflineMortalTrainer(
        config=config,
        transformer_config=transformer_config,
        bc_checkpoint=bc_checkpoint,
    )
    return trainer.train()


__all__ = ["OfflineConfig", "OfflineMortalTrainer", "train_offline_mortal"]
