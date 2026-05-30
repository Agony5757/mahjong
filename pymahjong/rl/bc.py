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
    # Self-play sanity evaluation (V4 only).  Plays ``selfplay_eval_hands``
    # hands with the current model occupying all four seats and reports
    # agari rate / episode length / etc.  Useful to verify the BC model
    # has learned to actually finish hands -- not just match action
    # distributions in cross-entropy.
    selfplay_eval_interval: int = 0     # 0 disables
    selfplay_eval_hands: int = 16
    selfplay_eval_deterministic: bool = True
    selfplay_eval_max_seq_len: int = 512
    selfplay_eval_seed: int = 12345
    # If set, every BC-SP eval also saves one paipu (.xml + .url.txt)
    # to this directory, named ``step_{step:06d}.xml``.  Lets you watch
    # the model's play evolve as training progresses.
    selfplay_paipu_dir: Optional[str] = None

    # Architectural: split policy head into action-phase + response-phase
    # subheads.  See action_space.{ACTION,RESPONSE}_HEAD_SLOTS.
    split_heads: bool = False

    # Auxiliary loss: penalise raw logits of *illegal* actions.  Mitigates
    # the standard masked-CE pathology where rare-but-when-legal-popular
    # actions (Tsumo / Ron / KaKan / Push / Pass-Response) get unbounded
    # logits in unrelated states (because the mask zeros their gradient
    # whenever they're illegal — so nothing pushes them down).
    #
    # Four penalty shapes are supported, controlled by ``illegal_logit_kind``:
    #
    #   * ``"unmasked_ce"`` (default & strongest of the CE family): mix
    #     standard unmasked cross-entropy into the loss::
    #
    #         loss = (1 - coef) * masked_ce + coef * unmasked_ce
    #
    #     ``coef=0`` reduces to pure masked CE (backwards compatible).
    #     ``coef=1`` is pure unmasked CE.  Typical 0.3..1.0.
    #
    #   * ``"unmasked_ce_smooth"``: as ``unmasked_ce`` but with
    #     label-smoothing ``label_smoothing_eps`` (default 0.1) applied
    #     to the unmasked CE, so every non-target slot (incl. illegal)
    #     has a tiny soft target = eps/(N-1).  Often a stronger
    #     regulariser than plain unmasked CE.
    #
    #   * ``"bce_multilabel"``: drop softmax entirely; treat each of the
    #     54 slots as an independent sigmoid with target = 1 for the
    #     expert action and 0 for everything else (including illegal and
    #     legal-but-not-taken).  No shared partition function → no leak
    #     mechanism.  ``coef`` controls mixing with masked_ce.  Try 0.5.
    #
    #   * ``"softplus"``: ``coef * mean( softplus(logit) * ~mask )``.
    #     Weaker — pushes positive illegal logits to ~0 but 30 zero-logit
    #     illegal slots still dominate softmax mass.  Try 1e-2..1e-1.
    #
    #   * ``"l2"``: ``coef * mean( logit**2 * ~mask )``.  Weakest.
    #
    # Set ``illegal_logit_coef`` to 0 to disable (backwards-compatible).
    illegal_logit_coef: float = 0.0
    illegal_logit_kind: str = "unmasked_ce"
    label_smoothing_eps: float = 0.1  # used by 'unmasked_ce_smooth'


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
    """Compute cross-entropy loss + top-1 accuracy on a dataset.

    Reports both the supervised CE loss (on masked logits) **and** the
    mean illegal-action softmax mass on the *raw* (un-masked) logits.
    The latter is a diagnostic for the standard masked-CE pathology and
    is reported regardless of whether ``illegal_logit_coef`` is enabled.

    Returns:
        ``(mean_ce_loss, mean_acc, n_samples, raw_illegal_mass)``.
        The model is left in its previous training mode regardless of
        input state.
    """
    was_training = model.training
    model.eval()
    loader = _build_loader(dataset, cfg, strategy, shuffle=False, drop_last=False)
    total_loss = 0.0
    total_correct = 0
    total_n = 0
    total_illegal_mass = 0.0
    for i, batch in enumerate(loader):
        if max_batches and i >= max_batches:
            break
        batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}
        raw_logits, _, action_mask = strategy.forward_from_batch_raw(model, batch)
        action_mask = action_mask.bool()
        masked_logits = raw_logits.masked_fill(~action_mask, -1e9)
        loss = F.cross_entropy(masked_logits, batch["action"], reduction="sum")
        pred = masked_logits.argmax(dim=-1)
        n = batch["action"].numel()
        total_loss += float(loss.item())
        total_correct += int((pred == batch["action"]).sum().item())
        total_n += n
        with torch.no_grad():
            raw_probs = torch.softmax(raw_logits, dim=-1)
            illegal_mass = (raw_probs * (~action_mask).float()).sum(dim=-1)
            total_illegal_mass += float(illegal_mass.sum().item())
    if was_training:
        model.train()
    if total_n == 0:
        return float("nan"), float("nan"), 0, float("nan")
    return (
        total_loss / total_n,
        total_correct / total_n,
        total_n,
        total_illegal_mass / total_n,
    )


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
        model = strategy.create_model(
            transformer_config=transformer_config,
            split_heads=getattr(cfg, "split_heads", False),
        )
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

    # V4 / V5 self-play eval is optional and gated on encoding.  V5
    # reuses V4's environment and live encoder (only the model head
    # differs), so the same selfplay_eval_v4 helper works for both.
    do_sp_eval = (
        encoding in ("v4", "v5")
        and cfg.selfplay_eval_interval > 0
        and cfg.selfplay_eval_hands > 0
    )
    sp_eval_fn = None
    sp_format_fn = None
    sp_record_fn = None
    if do_sp_eval:
        try:
            from pymahjong.rl.v4.selfplay_eval import (
                selfplay_eval_v4 as sp_eval_fn,  # noqa: F811
                format_selfplay_metrics as sp_format_fn,  # noqa: F811
                record_one_selfplay_hand as sp_record_fn,  # noqa: F811
            )
        except Exception as _e:  # noqa: BLE001
            print(
                f"[BC-SP] failed to import selfplay_eval_v4 ({_e!r}); "
                "self-play evaluation disabled",
                flush=True,
            )
            do_sp_eval = False
    sp_run_count = 0

    step = 0
    running_loss = 0.0
    running_acc = 0.0
    running_illegal_pen = 0.0
    running_illegal_mass = 0.0
    iterator = iter(loader)
    while step < cfg.n_steps:
        try:
            batch = next(iterator)
        except StopIteration:
            iterator = iter(loader)
            batch = next(iterator)
        batch = {k: v.to(device, non_blocking=True) for k, v in batch.items()}

        raw_logits, _, action_mask = strategy.forward_from_batch_raw(model, batch)
        action_mask = action_mask.bool()
        masked_logits = raw_logits.masked_fill(~action_mask, -1e9)
        masked_ce = F.cross_entropy(masked_logits, batch["action"])

        # Illegal-logit penalty (Stage-0 mitigation for masked-CE leak).
        illegal_pen = raw_logits.new_zeros(())
        if cfg.illegal_logit_coef > 0 and cfg.illegal_logit_kind == "unmasked_ce":
            unmasked_ce = F.cross_entropy(raw_logits, batch["action"])
            ce_loss = (1.0 - cfg.illegal_logit_coef) * masked_ce + \
                      cfg.illegal_logit_coef * unmasked_ce
            illegal_pen = unmasked_ce - masked_ce
            loss = ce_loss
        elif cfg.illegal_logit_coef > 0 and cfg.illegal_logit_kind == "unmasked_ce_smooth":
            # Like unmasked_ce but with label smoothing → illegal slots
            # have a tiny positive target = eps/(54-1), so they're more
            # actively pushed toward a specific low value.
            unmasked_ce = F.cross_entropy(
                raw_logits, batch["action"],
                label_smoothing=cfg.label_smoothing_eps,
            )
            ce_loss = (1.0 - cfg.illegal_logit_coef) * masked_ce + \
                      cfg.illegal_logit_coef * unmasked_ce
            illegal_pen = unmasked_ce - masked_ce
            loss = ce_loss
        elif cfg.illegal_logit_coef > 0 and cfg.illegal_logit_kind == "bce_multilabel":
            # Independent per-slot BCE: expert action = positive,
            # everything else (legal-but-not-taken AND illegal) = negative.
            # No softmax denominator → no shared-mass leak mechanism.
            target = F.one_hot(batch["action"], num_classes=raw_logits.shape[-1]).float()
            bce_loss = F.binary_cross_entropy_with_logits(
                raw_logits, target, reduction="mean",
            )
            ce_loss = (1.0 - cfg.illegal_logit_coef) * masked_ce + \
                      cfg.illegal_logit_coef * bce_loss
            illegal_pen = bce_loss  # diagnostic: keep separate
            loss = ce_loss
        elif cfg.illegal_logit_coef > 0:
            illegal_mask_f = (~action_mask).float()
            if cfg.illegal_logit_kind == "softplus":
                pen_per_slot = F.softplus(raw_logits) * illegal_mask_f
            elif cfg.illegal_logit_kind == "l2":
                pen_per_slot = (raw_logits ** 2) * illegal_mask_f
            else:
                raise ValueError(
                    f"Unknown illegal_logit_kind: {cfg.illegal_logit_kind!r}"
                )
            illegal_pen = pen_per_slot.mean()
            ce_loss = masked_ce
            loss = ce_loss + cfg.illegal_logit_coef * illegal_pen
        else:
            ce_loss = masked_ce
            loss = ce_loss

        optim.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), cfg.grad_clip)
        optim.step()

        with torch.no_grad():
            pred = masked_logits.argmax(dim=-1)
            running_acc = 0.95 * running_acc + 0.05 * (pred == batch["action"]).float().mean().item()
            raw_probs = torch.softmax(raw_logits, dim=-1)
            illegal_mass = (raw_probs * (~action_mask).float()).sum(dim=-1).mean()
            running_illegal_mass = 0.95 * running_illegal_mass + 0.05 * float(illegal_mass.item())
            running_illegal_pen = 0.95 * running_illegal_pen + 0.05 * float(illegal_pen.item())
        running_loss = 0.95 * running_loss + 0.05 * float(ce_loss.item())

        step += 1
        if step % cfg.log_interval == 0:
            print(
                f"[BC] step={step:>7d}  ce={running_loss:.4f}  acc={running_acc:.3f}  "
                f"raw_illegal_mass={running_illegal_mass:.3f}  "
                f"illegal_pen={running_illegal_pen:.3f}",
                flush=True,
            )
        if step % cfg.save_interval == 0 and cfg.save_path:
            os.makedirs(os.path.dirname(os.path.abspath(cfg.save_path)) or ".", exist_ok=True)
            torch.save({"model": model.state_dict(), "step": step}, cfg.save_path)

        if do_eval and step % cfg.eval_interval == 0:
            val_loss, val_acc, n, val_illegal_mass = evaluate(
                model, val_dataset,
                strategy=strategy, cfg=cfg, device=device,
                max_batches=cfg.eval_max_batches,
            )
            print(
                f"[BC] step={step:>7d}  val_ce={val_loss:.4f}  "
                f"val_acc={val_acc:.3f}  val_n={n}  "
                f"val_raw_illegal_mass={val_illegal_mass:.3f}",
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

        if do_sp_eval and step % cfg.selfplay_eval_interval == 0:
            try:
                sp_run_count += 1
                sp_metrics = sp_eval_fn(
                    model,
                    n_hands=cfg.selfplay_eval_hands,
                    deterministic=cfg.selfplay_eval_deterministic,
                    max_seq_len=cfg.selfplay_eval_max_seq_len,
                    seed=cfg.selfplay_eval_seed + sp_run_count,
                    device=device,
                )
                print(
                    f"[BC-SP] step={step:>7d}  {sp_format_fn(sp_metrics)}",
                    flush=True,
                )
                # Optional: also save one paipu for in-training viewing.
                if cfg.selfplay_paipu_dir and sp_record_fn is not None:
                    try:
                        out_xml = os.path.join(
                            cfg.selfplay_paipu_dir,
                            f"step_{step:06d}.xml",
                        )
                        ok = sp_record_fn(
                            model, out_xml,
                            seed=cfg.selfplay_eval_seed + sp_run_count,
                            max_seq_len=cfg.selfplay_eval_max_seq_len,
                            deterministic=cfg.selfplay_eval_deterministic,
                            device=device,
                            title="BC training-progress",
                            subtitle=f"step={step}",
                        )
                        if ok:
                            print(
                                f"[BC-SP] step={step:>7d}  saved paipu → {out_xml}",
                                flush=True,
                            )
                    except Exception as _e:  # noqa: BLE001
                        print(f"[BC-SP] step={step}: paipu save failed: {_e!r}",
                              flush=True)
            except Exception as _e:  # noqa: BLE001
                # Don't let an eval crash kill the whole training run.
                print(f"[BC-SP] step={step}: eval failed: {_e!r}", flush=True)

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
