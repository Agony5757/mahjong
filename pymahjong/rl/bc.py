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
import time
from dataclasses import dataclass, field
from typing import Optional, Tuple

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, DistributedSampler

from .common.optim import CombinedOptimizer, build_optimizer, build_scheduler
from .encoding import EncodingVersion, get_strategy
from . import encodings  # noqa: F401 -- trigger strategy registration


# ----------------------------------------------------------------------
# DDP helpers
# ----------------------------------------------------------------------
def _ddp_env() -> Tuple[int, int, int]:
    """Read RANK/LOCAL_RANK/WORLD_SIZE from torchrun env.  Returns (0,0,1) if absent."""
    rank = int(os.environ.get("RANK", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    world = int(os.environ.get("WORLD_SIZE", "1"))
    return rank, local_rank, world


def _is_ddp() -> bool:
    return int(os.environ.get("WORLD_SIZE", "1")) > 1


def _is_main() -> bool:
    return int(os.environ.get("RANK", "0")) == 0


def _maybe_init_ddp() -> Tuple[int, int, int]:
    """Initialise nccl process group when launched via torchrun.

    Idempotent: safe to call multiple times; safe when env vars are unset
    (returns (0, 0, 1) and does nothing).
    """
    rank, local_rank, world = _ddp_env()
    if world <= 1:
        return rank, local_rank, world
    import torch.distributed as dist  # noqa: PLC0415
    if not dist.is_initialized():
        dist.init_process_group(backend="nccl")
    torch.cuda.set_device(local_rank)
    return rank, local_rank, world


def _maybe_destroy_ddp() -> None:
    if not _is_ddp():
        return
    try:
        import torch.distributed as dist  # noqa: PLC0415
        if dist.is_initialized():
            dist.destroy_process_group()
    except Exception:  # noqa: BLE001
        pass


def _ddp_allreduce_mean(value: float, world: int) -> float:
    """Average ``value`` across all DDP ranks (mean reduction).  No-op for
    world==1 or when the process group has been destroyed."""
    if world <= 1:
        return value
    import torch.distributed as dist  # noqa: PLC0415
    if not dist.is_initialized():
        return value
    t = torch.tensor([value], dtype=torch.float64, device="cuda")
    dist.all_reduce(t, op=dist.ReduceOp.SUM)
    return float(t.item() / world)


def _ddp_allreduce_sum(values: Tuple[float, ...]) -> Tuple[float, ...]:
    """Sum ``values`` element-wise across all DDP ranks.  No-op for world==1
    or when the process group has been destroyed (e.g. after train_bc returns)."""
    if not _is_ddp():
        return values
    import torch.distributed as dist  # noqa: PLC0415
    if not dist.is_initialized():
        return values
    t = torch.tensor(list(values), dtype=torch.float64, device="cuda")
    dist.all_reduce(t, op=dist.ReduceOp.SUM)
    return tuple(t.cpu().tolist())


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
    early_stop_min_step: int = 0  # Don't trigger early stopping before this step.
                                  # Patience counter is reset each eval until
                                  # step >= early_stop_min_step.  Useful when
                                  # the trainer hasn't seen one full epoch yet
                                  # and val_loss may legitimately plateau before
                                  # really improving.  0 = no minimum.
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

    # ------------------------------------------------------------------
    # Optimizer & LR schedule
    # ------------------------------------------------------------------
    # ``optimizer`` selects the underlying optimizer:
    #
    #   * ``"adamw"`` (default, backward-compatible): single
    #     ``torch.optim.AdamW`` with the standard recipe — weight decay
    #     applied to 2-D hidden weights only, NOT to biases, LayerNorm
    #     gains, embeddings (pos_emb), CLS token, or the output policy/
    #     value heads.  Same trajectory as the legacy plain-AdamW call
    #     for any model whose only WD-eligible params were 2-D hidden
    #     weights (i.e. every transformer we use); strictly an
    #     improvement on models that previously over-decayed biases.
    #
    #   * ``"muon"``: hybrid Muon (for 2-D hidden weights) + AdamW (for
    #     embeddings, scalars, output heads, biases, LayerNorm).  See
    #     ``pymahjong.rl.common.optim`` for details.  Typically reaches
    #     the same val_loss as AdamW in 0.6–0.75× the steps on
    #     transformer policies (Keller Jordan, 2024); the Muon side has
    #     its own LR (``muon_lr``, defaulting to ``67 × lr`` per the
    #     published recipe) and tiny weight decay.
    optimizer: str = "adamw"
    betas: Tuple[float, float] = (0.9, 0.999)
    adam_eps: float = 1e-8
    muon_lr: Optional[float] = None       # None → 67 × lr
    muon_momentum: float = 0.95
    muon_ns_steps: int = 5
    muon_weight_decay: float = 0.0
    # LR schedule shape applied uniformly to all optimizer groups
    # (Muon and AdamW both follow the same warmup+decay curve).
    #
    #   * ``"constant"`` + ``warmup_steps=0`` (default): no schedule —
    #     identical to the legacy "set LR once, never touch it" trainer.
    #   * ``"constant"`` + ``warmup_steps>0``: linear warmup then hold.
    #   * ``"cosine"``: linear warmup then cosine decay to
    #     ``min_lr_ratio * lr``.  The recommended setting for the
    #     late-stage plateau visible in the current big11M run.
    #   * ``"linear"``: linear warmup then linear decay.
    lr_schedule: str = "constant"
    warmup_steps: int = 0
    min_lr_ratio: float = 0.1

    # ------------------------------------------------------------------
    # Weights & Biases (optional, opt-in)
    # ------------------------------------------------------------------
    # If ``wandb_project`` is set, log scalars (train ce/acc/lr, val
    # ce/acc, raw_illegal_mass, illegal_pen, selfplay metrics) to wandb
    # at every log_interval / eval_interval / selfplay_eval_interval.
    #
    # wandb is a **soft dependency** — if the package isn't installed
    # *and* wandb_project is set, the trainer logs a single warning and
    # continues without wandb (training still works fine).
    #
    # ``wandb_mode`` controls online vs offline logging:
    #   * ``"online"`` (default): live web dashboard at wandb.ai.  Needs
    #     ``WANDB_API_KEY`` env var or a prior ``wandb login``.
    #   * ``"offline"``: log to disk only; sync later with
    #     ``wandb sync <run_dir>``.  Useful on air-gapped clusters or
    #     when you don't have a wandb key handy.
    #   * ``"disabled"``: alias for "not set".
    wandb_project: Optional[str] = None
    wandb_entity: Optional[str] = None
    wandb_name: Optional[str] = None
    wandb_tags: Optional[Tuple[str, ...]] = None
    wandb_mode: str = "online"
    # If set, treat each row of this dict as additional run config
    # (e.g. CLI args) so wandb's UI shows your hyperparameters.
    wandb_extra_config: Optional[dict] = None


def _device(cfg: BCConfig) -> torch.device:
    if _is_ddp():
        # torchrun sets LOCAL_RANK; one GPU per rank.
        return torch.device(f"cuda:{int(os.environ['LOCAL_RANK'])}")
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
    # DDP: per-GPU batch = global batch / world_size; use DistributedSampler.
    sampler = None
    effective_batch = cfg.batch_size
    if _is_ddp() and is_map_style:
        rank, _, world = _ddp_env()
        sampler = DistributedSampler(
            dataset, num_replicas=world, rank=rank,
            shuffle=shuffle, drop_last=drop_last, seed=0,
        )
        assert cfg.batch_size % world == 0, (
            f"DDP requires batch_size ({cfg.batch_size}) divisible by world_size ({world})"
        )
        effective_batch = cfg.batch_size // world
    return DataLoader(
        dataset,
        batch_size=effective_batch,
        collate_fn=_collate,
        num_workers=cfg.num_workers if is_map_style else 0,
        # When using DistributedSampler, the DataLoader's `shuffle` must be False.
        shuffle=(sampler is None) and is_map_style and shuffle,
        sampler=sampler,
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
    # DDP: allreduce the per-rank sums so every rank sees the same global mean.
    total_loss, total_correct_f, total_n_f, total_illegal_mass = _ddp_allreduce_sum(
        (total_loss, float(total_correct), float(total_n), total_illegal_mass)
    )
    total_n = int(total_n_f)
    total_correct = int(total_correct_f)
    if total_n == 0:
        return float("nan"), float("nan"), 0, float("nan")
    return (
        total_loss / total_n,
        total_correct / total_n,
        total_n,
        total_illegal_mass / total_n,
    )


def _maybe_init_wandb(cfg: BCConfig, encoding: str, transformer_config):
    """Try to initialise wandb if ``cfg.wandb_project`` is set.

    DDP-safe: only rank 0 talks to wandb; other ranks return None.

    Returns the wandb run object on success, ``None`` on opt-out, or
    ``None`` with a printed warning on import / init failure (training
    continues either way).  ``None`` callers should fall back to a no-op
    via :func:`_wandb_log`.
    """
    if not _is_main():
        return None
    if not cfg.wandb_project:
        return None
    try:
        import wandb  # noqa: PLC0415 -- optional dep
    except ImportError:
        print(
            "[BC] wandb_project is set but the `wandb` package isn't "
            "installed.  `pip install wandb` to enable.  Training "
            "continues without wandb logging.",
            flush=True,
        )
        return None
    try:
        run_config = {
            "encoding": encoding,
            "n_steps": cfg.n_steps,
            "batch_size": cfg.batch_size,
            "lr": cfg.lr,
            "weight_decay": cfg.weight_decay,
            "optimizer": cfg.optimizer,
            "betas": list(cfg.betas),
            "muon_lr": cfg.muon_lr,
            "lr_schedule": cfg.lr_schedule,
            "warmup_steps": cfg.warmup_steps,
            "min_lr_ratio": cfg.min_lr_ratio,
            "illegal_logit_coef": cfg.illegal_logit_coef,
            "illegal_logit_kind": cfg.illegal_logit_kind,
            "split_heads": cfg.split_heads,
        }
        if transformer_config is not None:
            for k in ("d_model", "n_layers", "n_heads", "ff_mult", "dropout", "use_pos_emb"):
                if hasattr(transformer_config, k):
                    run_config[k] = getattr(transformer_config, k)
        if cfg.wandb_extra_config:
            run_config.update(cfg.wandb_extra_config)
        # Record DDP info so wandb UI shows whether this was a multi-GPU run.
        _, _, world = _ddp_env()
        run_config["world_size"] = world
        run_config["effective_batch_size"] = cfg.batch_size  # global batch
        run = wandb.init(
            project=cfg.wandb_project,
            entity=cfg.wandb_entity,
            name=cfg.wandb_name,
            tags=list(cfg.wandb_tags) if cfg.wandb_tags else None,
            mode=cfg.wandb_mode,
            config=run_config,
            resume="allow",
        )
        # Use ``step`` as the wandb x-axis everywhere; this is what the
        # CLI users expect (matches the stdout log).
        wandb.define_metric("step")
        wandb.define_metric("train/*", step_metric="step")
        wandb.define_metric("val/*", step_metric="step")
        wandb.define_metric("selfplay/*", step_metric="step")
        wandb.define_metric("lr/*", step_metric="step")
        # NEW: wall-clock time metrics (elapsed seconds, rolling step/s
        # and samples/s).  Also indexed by ``step`` so they line up with
        # everything else in the run.
        wandb.define_metric("time/*", step_metric="step")
        print(
            f"[BC] wandb initialised: project={cfg.wandb_project} "
            f"name={run.name} mode={cfg.wandb_mode}",
            flush=True,
        )
        return run
    except Exception as _e:  # noqa: BLE001
        print(f"[BC] wandb init failed: {_e!r}; continuing without wandb",
              flush=True)
        return None


def _wandb_log(run, data: dict, step: int) -> None:
    """No-op when run is None; otherwise wandb.log with ``step`` included."""
    if run is None:
        return
    try:
        import wandb  # noqa: PLC0415
        payload = dict(data)
        payload["step"] = step
        wandb.log(payload, step=step)
    except Exception:  # noqa: BLE001
        # Silently swallow logging errors — never break training.
        pass


def _wandb_finish(run) -> None:
    if run is None:
        return
    try:
        import wandb  # noqa: PLC0415
        wandb.finish()
    except Exception:  # noqa: BLE001
        pass


def train_bc(
    dataset=None,
    val_dataset=None,
    model=None,
    config: Optional[BCConfig] = None,
    transformer_config=None,
    encoding: str = "v3",
    resume_from: Optional[str] = None,
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
        resume_from: optional path to a checkpoint saved by a previous
            ``train_bc`` run. Restores model weights and, when present
            in the checkpoint, optimizer state, training step,
            best-val tracking, and the self-play eval counter. Older
            checkpoints without these fields restore only the model and
            ``step`` (best-val tracking starts fresh).

    Returns:
        The trained model (best-by-val if early stopping fired,
        otherwise the model at the final step).
    """
    cfg = config or BCConfig()
    # Initialise DDP early so device routing below uses the right GPU.
    rank, local_rank, world = _maybe_init_ddp()
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
    optim = build_optimizer(
        model,
        kind=cfg.optimizer,
        lr=cfg.lr,
        weight_decay=cfg.weight_decay,
        betas=cfg.betas,
        eps=cfg.adam_eps,
        muon_lr=cfg.muon_lr,
        muon_momentum=cfg.muon_momentum,
        muon_ns_steps=cfg.muon_ns_steps,
        muon_weight_decay=cfg.muon_weight_decay,
    )
    # Built later (after resume so ``last_step`` matches the resumed
    # global step counter).
    scheduler = None

    do_eval = val_dataset is not None and cfg.eval_interval > 0
    best_val_loss = float("inf")
    best_step = 0
    bad_evals = 0
    best_save_path = cfg.best_save_path or (cfg.save_path + ".best"
                                            if cfg.save_path else None)

    resume_step = 0
    resume_sp_run_count = 0
    resume_scheduler_sd = None  # set if resumable scheduler state present
    if resume_from:
        if not os.path.exists(resume_from):
            raise FileNotFoundError(f"resume_from checkpoint not found: {resume_from}")
        ck = torch.load(resume_from, map_location=device, weights_only=False)
        missing, unexpected = model.load_state_dict(ck["model"], strict=False)
        if missing or unexpected:
            print(
                f"[BC] resume: state_dict mismatch (missing={len(missing)}, "
                f"unexpected={len(unexpected)}); continuing with partial load",
                flush=True,
            )
        if "optim" in ck:
            try:
                optim.load_state_dict(ck["optim"])
            except (ValueError, KeyError, TypeError) as _e:  # noqa: BLE001
                print(
                    f"[BC] resume: optimizer restore failed ({_e!r}); "
                    "continuing with freshly-initialised optimizer "
                    "(expected when switching --optimizer kind across runs)",
                    flush=True,
                )
        if "scheduler" in ck:
            resume_scheduler_sd = ck["scheduler"]
        resume_step = int(ck.get("step", 0))
        best_val_loss = float(ck.get("best_val_loss", ck.get("val_loss", float("inf"))))
        best_step = int(ck.get("best_step", resume_step))
        bad_evals = int(ck.get("bad_evals", 0))
        resume_sp_run_count = int(ck.get("sp_run_count", 0))
        print(
            f"[BC] resumed from {resume_from} at step={resume_step} "
            f"(best_val_loss={best_val_loss:.4f}, best_step={best_step}, "
            f"opt={'yes' if 'optim' in ck else 'no'})",
            flush=True,
        )

    # Build the LR scheduler *after* resume so it picks up at the same
    # progress fraction.  Resuming the LambdaLR by ``last_epoch`` is
    # exact for any deterministic lr_lambda (which ours is); the
    # explicit state_dict restore below is belt-and-braces in case
    # someone subclasses with stateful warm-up logic in the future.
    scheduler = build_scheduler(
        optim,
        total_steps=cfg.n_steps,
        schedule=cfg.lr_schedule,
        warmup_steps=cfg.warmup_steps,
        min_lr_ratio=cfg.min_lr_ratio,
        last_step=resume_step - 1,  # LambdaLR convention: -1 means "fresh"
    )
    if resume_scheduler_sd is not None:
        try:
            scheduler.load_state_dict(resume_scheduler_sd)
        except (ValueError, KeyError) as _e:  # noqa: BLE001
            print(
                f"[BC] resume: scheduler restore failed ({_e!r}); "
                "continuing with freshly-built scheduler",
                flush=True,
            )

    # Wrap with DDP after model state restored and optimizer built (the
    # raw param tensors are shared between optim and DDP — wrapping is
    # transparent to the optimizer).  Done before training loop only.
    # ``find_unused_parameters=True`` is required for V5 (value head is
    # not used in BC; DDP would otherwise error on the unused gradients).
    raw_model = model  # for state_dict save/load
    if _is_ddp():
        from torch.nn.parallel import DistributedDataParallel as DDP  # noqa: PLC0415
        model = DDP(
            model,
            device_ids=[local_rank],
            output_device=local_rank,
            find_unused_parameters=True,
        )

    # Initialise wandb if requested (rank 0 only).  No-op when cfg.wandb_project is
    # unset; safe to call even if `wandb` isn't installed.
    wandb_run = _maybe_init_wandb(cfg, encoding, transformer_config)

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
    sp_run_count = resume_sp_run_count

    step = resume_step
    running_loss = 0.0
    running_acc = 0.0
    running_illegal_pen = 0.0
    running_illegal_mass = 0.0
    # Wall-time tracking for throughput / ETA wandb metrics.
    train_t0 = time.time()           # absolute start of this run's loop
    last_log_t = train_t0            # timestamp of last log line
    last_log_step = step             # step at last log line
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
        scheduler.step()

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
            lrs = scheduler.get_last_lr()
            lr_str = "/".join(f"{lr:.2e}" for lr in lrs)
            # Allreduce training metrics across DDP ranks so the value
            # we print/log is the *mean over GPUs* (not just rank 0).
            agg_loss = _ddp_allreduce_mean(running_loss, world)
            agg_acc = _ddp_allreduce_mean(running_acc, world)
            agg_imass = _ddp_allreduce_mean(running_illegal_mass, world)
            agg_ipen = _ddp_allreduce_mean(running_illegal_pen, world)
            # Wall-time / throughput.
            now = time.time()
            elapsed_s = now - train_t0
            interval_s = now - last_log_t
            interval_steps = step - last_log_step
            steps_per_sec = interval_steps / max(interval_s, 1e-6)
            # cfg.batch_size is the GLOBAL batch under DDP (we divide
            # internally in _build_loader), so samples/s is correct.
            samples_per_sec = steps_per_sec * cfg.batch_size
            last_log_t = now
            last_log_step = step
            if _is_main():
                print(
                    f"[BC] step={step:>7d}  ce={agg_loss:.4f}  acc={agg_acc:.3f}  "
                    f"raw_illegal_mass={agg_imass:.3f}  "
                    f"illegal_pen={agg_ipen:.3f}  lr={lr_str}  "
                    f"elapsed={elapsed_s:.0f}s  rate={steps_per_sec:.2f}st/s  "
                    f"({samples_per_sec:.0f}sa/s)",
                    flush=True,
                )
                _wandb_log(wandb_run, {
                    "train/ce": agg_loss,
                    "train/acc": agg_acc,
                    "train/raw_illegal_mass": agg_imass,
                    "train/illegal_pen": agg_ipen,
                    # Index 0 is the *first* underlying optimizer; for the
                    # combined Muon+AdamW case that's the Muon group.
                    # Logging both lets you see the schedule on each side.
                    **{f"lr/group_{i}": lr for i, lr in enumerate(lrs)},
                    "time/elapsed_s": elapsed_s,
                    "time/steps_per_sec": steps_per_sec,
                    "time/samples_per_sec": samples_per_sec,
                }, step=step)
        if step % cfg.save_interval == 0 and cfg.save_path and _is_main():
            os.makedirs(os.path.dirname(os.path.abspath(cfg.save_path)) or ".", exist_ok=True)
            torch.save({
                "model": raw_model.state_dict(),
                "optim": optim.state_dict(),
                "scheduler": scheduler.state_dict(),
                "step": step,
                "best_val_loss": best_val_loss,
                "best_step": best_step,
                "bad_evals": bad_evals,
                "sp_run_count": sp_run_count,
            }, cfg.save_path)

        if do_eval and step % cfg.eval_interval == 0:
            val_loss, val_acc, n, val_illegal_mass = evaluate(
                model, val_dataset,
                strategy=strategy, cfg=cfg, device=device,
                max_batches=cfg.eval_max_batches,
            )
            if _is_main():
                print(
                    f"[BC] step={step:>7d}  val_ce={val_loss:.4f}  "
                    f"val_acc={val_acc:.3f}  val_n={n}  "
                    f"val_raw_illegal_mass={val_illegal_mass:.3f}",
                    flush=True,
                )
                _wandb_log(wandb_run, {
                    "val/ce": val_loss,
                    "val/acc": val_acc,
                    "val/n": n,
                    "val/raw_illegal_mass": val_illegal_mass,
                    "val/best_ce_so_far": min(best_val_loss, val_loss),
                }, step=step)
            improved = val_loss < best_val_loss - 1e-6
            if improved:
                best_val_loss = val_loss
                best_step = step
                bad_evals = 0
                if best_save_path and _is_main():
                    os.makedirs(os.path.dirname(os.path.abspath(best_save_path)) or ".",
                                exist_ok=True)
                    torch.save({
                        "model": raw_model.state_dict(),
                        "optim": optim.state_dict(),
                        "scheduler": scheduler.state_dict(),
                        "step": step,
                        "val_loss": val_loss,
                        "val_acc": val_acc,
                        "best_val_loss": best_val_loss,
                        "best_step": best_step,
                        "bad_evals": bad_evals,
                        "sp_run_count": sp_run_count,
                    }, best_save_path)
            else:
                if step < cfg.early_stop_min_step:
                    # Patience counter hasn't started yet (e.g. waiting for
                    # the first epoch to complete).  Treat plateau as
                    # acceptable and don't accumulate badness.
                    bad_evals = 0
                else:
                    bad_evals += 1
                    if cfg.early_stop_patience > 0 and bad_evals >= cfg.early_stop_patience:
                        if _is_main():
                            print(
                                f"[BC] early stopping at step {step}: "
                                f"no val_loss improvement for {bad_evals} evaluations "
                                f"(best={best_val_loss:.4f} at step {best_step})",
                                flush=True,
                            )
                        break

        # Self-play eval is intrinsically single-process (model plays
        # all 4 seats in a single env loop), so only rank 0 runs it and
        # logs.  Other ranks skip ahead.
        if do_sp_eval and step % cfg.selfplay_eval_interval == 0 and _is_main():
            try:
                sp_run_count += 1
                # Use raw_model so the SP loop sees the unwrapped policy.
                sp_metrics = sp_eval_fn(
                    raw_model,
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
                # Forward every scalar key from sp_metrics under the
                # selfplay/* namespace so wandb auto-builds charts.
                _wandb_log(wandb_run, {
                    f"selfplay/{k.replace('sp/', '')}": v
                    for k, v in sp_metrics.items()
                    if isinstance(v, (int, float))
                }, step=step)
                # Optional: also save one paipu for in-training viewing.
                if cfg.selfplay_paipu_dir and sp_record_fn is not None:
                    try:
                        out_xml = os.path.join(
                            cfg.selfplay_paipu_dir,
                            f"step_{step:06d}.xml",
                        )
                        ok = sp_record_fn(
                            raw_model, out_xml,
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

    # Final checkpoint (rank 0 only).
    if cfg.save_path and _is_main():
        os.makedirs(os.path.dirname(os.path.abspath(cfg.save_path)) or ".", exist_ok=True)
        torch.save({
            "model": raw_model.state_dict(),
            "optim": optim.state_dict(),
            "scheduler": scheduler.state_dict(),
            "step": step,
            "best_val_loss": best_val_loss,
            "best_step": best_step,
            "bad_evals": bad_evals,
            "sp_run_count": sp_run_count,
        }, cfg.save_path)

    # Restore best-by-val weights if we were tracking them (rank 0 only;
    # other ranks will exit without reloading — the final returned model
    # on non-zero ranks is the in-training one which is fine because
    # only rank 0 ever uses it after train_bc returns).
    if do_eval and best_save_path and _is_main() and os.path.exists(best_save_path):
        ck = torch.load(best_save_path, map_location=device, weights_only=False)
        raw_model.load_state_dict(ck["model"])
        print(
            f"[BC] restored best checkpoint (step={ck['step']}, "
            f"val_loss={ck['val_loss']:.4f}, val_acc={ck['val_acc']:.3f})",
            flush=True,
        )
    _wandb_finish(wandb_run)
    # NOTE: do *not* destroy DDP here -- caller (train_bc_v5.py) may
    # still need the process group for the final test eval allreduce.
    # The orchestrator should call dist.destroy_process_group() itself
    # at exit time (or just let process termination handle it).
    return raw_model
