"""Stage 1: Behavior cloning (supervised) trainer.

Supervised cross-entropy training of :class:`MahjongTransformer` on
``(obs, action)`` pairs from self-play imitation or paipu replays.

Example::

    from pymahjong.rl.bc import train_bc
    train_bc(
        save_path="checkpoints/bc.pt",
        n_steps=200_000,
        batch_size=128,
    )

Runs entirely on a single GPU; falls back to CPU automatically.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .cached_dataset import CachedTokenDataset, cached_collate
from .dataset import SelfPlayImitationDataset, collate_fn
from .model import MahjongTransformer, TransformerConfig


@dataclass
class BCConfig:
    n_steps: int = 100_000
    batch_size: int = 64
    lr: float = 3e-4
    weight_decay: float = 1e-4
    grad_clip: float = 1.0
    log_interval: int = 100
    save_interval: int = 5_000
    save_path: str = "bc.pt"
    device: Optional[str] = None  # auto
    # Cache-loader specific knobs (ignored when an explicit ``dataset`` is passed).
    cache_dir: Optional[str] = None
    num_workers: int = 0
    suit_permute: bool = False  # 6x augment across man/pin/sou; PAD-safe
    pin_memory: bool = True


def _device(cfg: BCConfig) -> torch.device:
    if cfg.device:
        return torch.device(cfg.device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def train_bc(
    dataset=None,
    model: Optional[MahjongTransformer] = None,
    config: Optional[BCConfig] = None,
    transformer_config: Optional[TransformerConfig] = None,
):
    """Train a transformer policy by behavior cloning.

    Args:
        dataset: a torch ``IterableDataset`` yielding ``{tokens, attention_mask,
            action_mask, action}`` dicts. Defaults to
            :class:`SelfPlayImitationDataset` (random expert) for smoke tests.
        model: optional pre-existing model to continue training.
        config: :class:`BCConfig`.
        transformer_config: :class:`TransformerConfig` for a fresh model.

    Returns:
        The trained :class:`MahjongTransformer`.
    """
    cfg = config or BCConfig()
    device = _device(cfg)

    if model is None:
        model = MahjongTransformer(config=transformer_config)
    model = model.to(device)
    model.train()

    if dataset is None:
        if cfg.cache_dir:
            dataset = CachedTokenDataset(
                cfg.cache_dir,
                suit_permute=cfg.suit_permute,
            )
        else:
            dataset = SelfPlayImitationDataset(oracle=False)

    is_map_style = hasattr(dataset, "__len__")
    loader = DataLoader(
        dataset,
        batch_size=cfg.batch_size,
        collate_fn=cached_collate if is_map_style else collate_fn,
        num_workers=cfg.num_workers if is_map_style else 0,
        shuffle=is_map_style,
        pin_memory=cfg.pin_memory and torch.cuda.is_available(),
        drop_last=is_map_style,
        persistent_workers=is_map_style and cfg.num_workers > 0,
    )

    optim = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)

    step = 0
    running_loss = 0.0
    running_acc = 0.0
    iterator = iter(loader)
    while step < cfg.n_steps:
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(loader)
            batch = next(iterator)
        batch = {k: v.to(device) for k, v in batch.items()}
        logits, _ = model(
            batch["tokens"],
            batch["attention_mask"],
            batch["action_mask"],
            scalars=batch.get("scalars"),
        )
        loss = F.cross_entropy(logits, batch["action"])

        optim.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        optim.step()

        with torch.no_grad():
            pred = logits.argmax(dim=-1)
            running_acc = 0.95 * running_acc + 0.05 * (pred == batch["action"]).float().mean().item()
        running_loss = 0.95 * running_loss + 0.05 * loss.item()

        step += 1
        if step % cfg.log_interval == 0:
            print(
                f"[BC] step={step:>7d}  loss={running_loss:.4f}  acc={running_acc:.3f}",
                flush=True,
            )
        if step % cfg.save_interval == 0:
            os.makedirs(os.path.dirname(os.path.abspath(cfg.save_path)) or ".", exist_ok=True)
            torch.save({"model": model.state_dict(), "step": step}, cfg.save_path)

    if cfg.save_path:
        os.makedirs(os.path.dirname(os.path.abspath(cfg.save_path)) or ".", exist_ok=True)
        torch.save({"model": model.state_dict(), "step": step}, cfg.save_path)
    return model
