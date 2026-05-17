"""Stage 1: Behavior cloning (supervised) trainer.

Supervised cross-entropy training of a transformer policy on
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

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from .encoding import EncodingVersion, get_strategy
from . import encodings  # noqa: F401 -- trigger strategy registration


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
    suit_permute: bool = False  # 2x augment (man↔pin swap; sou fixed for 绿一色)
    pin_memory: bool = True
    # Streaming paipu dataset knobs.
    paipu_dir: Optional[str] = None  # directory of paipu XML files (uses config if None)
    paipu_prefetch: int = 4  # number of paipu files to prefetch
    # Validation / early stopping (optional).
    eval_interval: int = 0      # 0 disables periodic validation
    eval_max_batches: int = 0   # 0 = evaluate whole val set; >0 caps wall time
    early_stop_patience: int = 0  # 0 disables early stopping
    best_save_path: Optional[str] = None  # defaults to save_path + '.best'


def _device(cfg: BCConfig) -> torch.device:
    if cfg.device:
        return torch.device(cfg.device)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _paipu_xml_from_config() -> Optional[str]:
    try:
        from pymahjong.config import get_config
        return get_config().paipu_xml_path
    except Exception:
        return None


def _resolve_dataset_mode(cfg: BCConfig) -> str:
    """Determine dataset mode ('cached', 'streaming', 'selfplay') from config."""
    if cfg.cache_dir:
        return "cached"
    if cfg.paipu_dir or _paipu_xml_from_config():
        return "streaming"
    return "selfplay"


def _build_loader(dataset, cfg: BCConfig, strategy, shuffle: bool, drop_last: bool):
    is_map_style = hasattr(dataset, "__len__")
    _collate = getattr(dataset, "collate_fn", None) or strategy.collate_fn
    return DataLoader(
        dataset,
        batch_size=cfg.batch_size,
        collate_fn=_collate,
        num_workers=cfg.num_workers if is_map_style else 0,
        shuffle=is_map_style and shuffle,
        pin_memory=cfg.pin_memory and torch.cuda.is_available(),
        drop_last=is_map_style and drop_last,
        persistent_workers=is_map_style and cfg.num_workers > 0,
    )


@torch.no_grad()
def evaluate(
    model,
    dataset,
    *,
    strategy,
    cfg: BCConfig,
    device: torch.device,
    max_batches: int = 0,
):
    """Compute cross-entropy loss and top-1 accuracy on a dataset.

    Returns ``(mean_loss, mean_acc, n_samples)``. The model is left in
    its previous training mode regardless of input state.
    """
    was_training = model.training
    model.eval()
    loader = _build_loader(dataset, cfg, strategy, shuffle=False, drop_last=False)
    total_loss = 0.0
    total_correct = 0
    total_n = 0
    for i, batch in enumerate(loader):
        if max_batches and i >= max_batches:
            break
        batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
        logits, _ = strategy.forward_from_batch(model, batch)
        loss = F.cross_entropy(logits, batch["action"], reduction="sum")
        pred = logits.argmax(dim=-1)
        n = batch["action"].numel()
        total_loss += float(loss.item())
        total_correct += int((pred == batch["action"]).sum().item())
        total_n += n
    if was_training:
        model.train()
    if total_n == 0:
        return float("nan"), float("nan"), 0
    return total_loss / total_n, total_correct / total_n, total_n


def train_bc(
    dataset=None,
    val_dataset=None,
    model=None,
    config: Optional[BCConfig] = None,
    transformer_config=None,
    encoding: str = "v3",
):
    """Train a transformer policy by behavior cloning.

    Args:
        dataset: training dataset (torch ``Dataset`` or
            ``IterableDataset``) yielding observation dicts.
        val_dataset: optional validation dataset. When provided AND
            ``config.eval_interval > 0``, the trainer periodically
            computes validation loss/acc and (if ``best_save_path`` is
            set or defaults are used) tracks the best checkpoint.
        model: optional pre-existing model to continue training.
        config: :class:`BCConfig`.
        transformer_config: transformer architecture config.
        encoding: encoding version (``"v3"`` or ``"v4"``).

    Returns:
        The trained model (best-by-val if early stopping fired,
        otherwise the model at the final step).
    """
    cfg = config or BCConfig()
    device = _device(cfg)

    strategy = get_strategy(EncodingVersion(encoding))

    if model is None:
        model = strategy.create_model(transformer_config=transformer_config)
    model = model.to(device)
    model.train()

    if dataset is None:
        mode = _resolve_dataset_mode(cfg)
        dataset = strategy.create_dataset(mode, config=cfg)

    loader = _build_loader(dataset, cfg, strategy, shuffle=True, drop_last=True)
    optim = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)

    do_eval = val_dataset is not None and cfg.eval_interval > 0
    best_val_loss = float("inf")
    best_step = 0
    bad_evals = 0
    best_save_path = cfg.best_save_path or (cfg.save_path + ".best"
                                            if cfg.save_path else None)

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
        batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}

        logits, _ = strategy.forward_from_batch(model, batch)
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
        if step % cfg.save_interval == 0 and cfg.save_path:
            os.makedirs(os.path.dirname(os.path.abspath(cfg.save_path)) or ".", exist_ok=True)
            torch.save({"model": model.state_dict(), "step": step}, cfg.save_path)

        if do_eval and step % cfg.eval_interval == 0:
            val_loss, val_acc, n = evaluate(
                model, val_dataset,
                strategy=strategy, cfg=cfg, device=device,
                max_batches=cfg.eval_max_batches,
            )
            print(
                f"[BC] step={step:>7d}  val_loss={val_loss:.4f}  "
                f"val_acc={val_acc:.3f}  val_n={n}",
                flush=True,
            )
            improved = val_loss < best_val_loss - 1e-6
            if improved:
                best_val_loss = val_loss
                best_step = step
                bad_evals = 0
                if best_save_path:
                    os.makedirs(os.path.dirname(os.path.abspath(best_save_path)) or ".",
                                exist_ok=True)
                    torch.save({
                        "model": model.state_dict(),
                        "step": step,
                        "val_loss": val_loss,
                        "val_acc": val_acc,
                    }, best_save_path)
            else:
                bad_evals += 1
                if cfg.early_stop_patience > 0 and bad_evals >= cfg.early_stop_patience:
                    print(
                        f"[BC] early stopping at step {step}: "
                        f"no val_loss improvement for {bad_evals} evaluations "
                        f"(best={best_val_loss:.4f} at step {best_step})",
                        flush=True,
                    )
                    break

    if cfg.save_path:
        os.makedirs(os.path.dirname(os.path.abspath(cfg.save_path)) or ".", exist_ok=True)
        torch.save({"model": model.state_dict(), "step": step}, cfg.save_path)

    # Restore best-by-val weights if we were tracking them.
    if do_eval and best_save_path and os.path.exists(best_save_path):
        ck = torch.load(best_save_path, map_location=device, weights_only=False)
        model.load_state_dict(ck["model"])
        print(
            f"[BC] restored best checkpoint (step={ck['step']}, "
            f"val_loss={ck['val_loss']:.4f}, val_acc={ck['val_acc']:.3f})",
            flush=True,
        )
    return model
