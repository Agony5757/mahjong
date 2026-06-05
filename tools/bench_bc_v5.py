#!/usr/bin/env python3
"""Single-host BC v5 throughput benchmark.

Modes:
  --mode single        : 1 GPU
  --mode dp            : torch.nn.DataParallel across --gpus
  --mode ddp           : DDP — launch via torchrun --nproc-per-node=N

For ddp, do NOT use --gpus; torchrun sets WORLD_SIZE/LOCAL_RANK.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, DistributedSampler

# Make package importable
sys.path.insert(0, "/data1/home/chenzhaoyun/mahjong")

from pymahjong.rl.common.config import TransformerConfig
from pymahjong.rl.encoding import EncodingVersion, get_strategy
from pymahjong.rl.v4.cached_dataset import CachedEventDataset


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--mode", choices=["single", "dp", "ddp"], required=True)
    p.add_argument("--gpus", type=int, default=1,
                   help="for single/dp: number of GPUs to use (dp wraps model)")
    p.add_argument("--cache-dir", default="/data1/home/chenzhaoyun/mahjong/data/cache_v4")
    p.add_argument("--shards-prefix", default="c2501_",
                   help="glob-ish prefix used to select a small subset for fast load")
    p.add_argument("--batch-size", type=int, default=128,
                   help="GLOBAL batch (will be split across GPUs in dp/ddp)")
    p.add_argument("--num-workers", type=int, default=4)
    p.add_argument("--d-model", type=int, default=192)
    p.add_argument("--n-layers", type=int, default=4)
    p.add_argument("--n-heads", type=int, default=6)
    p.add_argument("--ff-mult", type=int, default=4)
    p.add_argument("--scorer-hidden", type=int, default=256)
    p.add_argument("--warmup-steps", type=int, default=20)
    p.add_argument("--measure-steps", type=int, default=200)
    p.add_argument("--amp", action="store_true", help="enable bf16 AMP")
    return p.parse_args()


def build_dataset(args):
    """Restrict to single month for fast init / sane RAM."""
    import json
    import fnmatch
    full_idx_path = os.path.join(args.cache_dir, "index.json")
    full_idx = json.load(open(full_idx_path))
    sub_shards = [s for s in full_idx["shards"] if s["path"].startswith(args.shards_prefix)]
    assert sub_shards, f"no shards matched prefix {args.shards_prefix!r}"
    # Write a temp index restricted to this subset
    import tempfile, shutil, hashlib
    tag = hashlib.md5(args.shards_prefix.encode()).hexdigest()[:8]
    tmp_dir = f"/tmp/bench_cache_{tag}"
    os.makedirs(tmp_dir, exist_ok=True)
    # Symlink all shard dirs into tmp_dir
    for s in sub_shards:
        link = os.path.join(tmp_dir, s["path"])
        if not os.path.lexists(link):
            os.symlink(os.path.join(args.cache_dir, s["path"]), link)
    # Rewrite cumulative
    cum = 0
    new_shards = []
    for s in sub_shards:
        cum += int(s["n_rows"])
        new_shards.append({"path": s["path"], "n_rows": int(s["n_rows"]), "cumulative": cum})
    tmp_idx = {"schema": full_idx["schema"], "total_rows": cum, "shards": new_shards}
    json.dump(tmp_idx, open(os.path.join(tmp_dir, "index.json"), "w"))
    ds = CachedEventDataset(tmp_dir)
    return ds, cum


def build_model(args):
    cfg = TransformerConfig(
        d_model=args.d_model,
        n_layers=args.n_layers,
        n_heads=args.n_heads,
        ff_mult=args.ff_mult,
    )
    strategy = get_strategy(EncodingVersion.V5)
    model = strategy.create_model(
        transformer_config=cfg,
        scorer_hidden=args.scorer_hidden,
    )
    return model, strategy


def loss_fn(strategy, model, batch):
    raw_logits, _ = strategy.forward_from_batch(model, batch)
    action_mask = batch["action_mask"]
    masked = raw_logits.masked_fill(~action_mask, -1e9)
    return F.cross_entropy(masked, batch["action"])


def to_device(batch, device, non_blocking=True):
    return {k: v.to(device, non_blocking=non_blocking) if torch.is_tensor(v) else v
            for k, v in batch.items()}


def run_single(args):
    rank, world = 0, args.gpus  # gpus=1 in pure single
    device = torch.device("cuda:0")
    torch.cuda.set_device(0)
    ds, n_rows = build_dataset(args)
    print(f"[single] dataset rows={n_rows:,}", flush=True)
    model, strategy = build_model(args)
    model = model.to(device)
    model.train()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[single] model params={n_params/1e6:.2f}M", flush=True)
    optim = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True,
                        num_workers=args.num_workers, pin_memory=True,
                        persistent_workers=args.num_workers > 0,
                        drop_last=True, collate_fn=strategy.collate_fn)
    bench_loop(model, optim, loader, strategy, device, args, rank=0)


def run_dp(args):
    n_gpus = args.gpus
    assert n_gpus >= 2
    device = torch.device("cuda:0")
    torch.cuda.set_device(0)
    ds, n_rows = build_dataset(args)
    print(f"[dp{n_gpus}] dataset rows={n_rows:,}", flush=True)
    model, strategy = build_model(args)
    model = model.to(device)
    model = torch.nn.DataParallel(model, device_ids=list(range(n_gpus)))
    model.train()
    n_params = sum(p.numel() for p in model.module.parameters())
    print(f"[dp{n_gpus}] model params={n_params/1e6:.2f}M", flush=True)
    optim = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True,
                        num_workers=args.num_workers, pin_memory=True,
                        persistent_workers=args.num_workers > 0,
                        drop_last=True, collate_fn=strategy.collate_fn)
    # DP needs the strategy's forward to be called via model.module — but
    # strategy.forward_from_batch passes batch dict and the V5 model's
    # forward expects keyword args. DP scatters the *positional* batch dict.
    # Simpler: pre-extract tensors and use plain model.forward.
    bench_loop_dp(model, optim, loader, strategy, device, args)


def bench_loop(model, optim, loader, strategy, device, args, rank=0):
    it = iter(loader)
    n_warmup = args.warmup_steps
    n_meas = args.measure_steps
    samples_per_step = args.batch_size
    scaler = torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16) if args.amp else None
    for step in range(n_warmup + n_meas):
        try:
            batch = next(it)
        except StopIteration:
            it = iter(loader)
            batch = next(it)
        batch = to_device(batch, device)
        if step == n_warmup:
            torch.cuda.synchronize()
            t0 = time.time()
        if args.amp:
            with torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16):
                loss = loss_fn(strategy, model, batch)
        else:
            loss = loss_fn(strategy, model, batch)
        optim.zero_grad(set_to_none=True)
        loss.backward()
        optim.step()
    torch.cuda.synchronize()
    dt = time.time() - t0
    sps = n_meas * samples_per_step / dt
    print(f"[rank={rank}] {n_meas} steps in {dt:.2f}s = "
          f"{n_meas/dt:.2f} steps/s, {sps:.0f} samples/s "
          f"(batch={samples_per_step})", flush=True)


def bench_loop_dp(model, optim, loader, strategy, device, args):
    # Manually invoke DP by passing the Douzero kwargs as a single tuple
    # via model.forward. Easier: route through strategy.forward_from_batch
    # which accepts the raw batch dict; for DP we just call model(batch) and
    # adjust the wrapped module accordingly. Quick hack: temporarily wrap
    # the V5 model with a Module that takes (features, attn_mask, am, af, apm, loi) tuple.
    class DPWrapper(torch.nn.Module):
        def __init__(self, inner):
            super().__init__()
            self.inner = inner
        def forward(self, features, attention_mask, action_mask,
                    action_features, action_pad_mask, legal_orig_idx,
                    legal_target_idx, action):
            raw_logits, _ = self.inner(
                features=features,
                attention_mask=attention_mask,
                action_mask=action_mask,
                action_features=action_features,
                action_pad_mask=action_pad_mask,
                legal_orig_idx=legal_orig_idx,
            )
            masked = raw_logits.masked_fill(~action_mask, -1e9)
            return F.cross_entropy(masked, action, reduction="none")
    inner = model.module
    wrapper = DPWrapper(inner)
    dp = torch.nn.DataParallel(wrapper, device_ids=list(range(args.gpus)))
    dp.train()
    optim = torch.optim.AdamW(wrapper.parameters(), lr=3e-4, weight_decay=1e-4)
    it = iter(loader)
    n_warmup = args.warmup_steps
    n_meas = args.measure_steps
    for step in range(n_warmup + n_meas):
        try:
            batch = next(it)
        except StopIteration:
            it = iter(loader); batch = next(it)
        batch = to_device(batch, device)
        if step == n_warmup:
            torch.cuda.synchronize(); t0 = time.time()
        losses = dp(
            batch["features"], batch["attention_mask"], batch["action_mask"],
            batch["action_features"], batch["action_pad_mask"],
            batch["legal_orig_idx"], batch["legal_target_idx"], batch["action"],
        )
        loss = losses.mean()
        optim.zero_grad(set_to_none=True)
        loss.backward()
        optim.step()
    torch.cuda.synchronize()
    dt = time.time() - t0
    sps = n_meas * args.batch_size / dt
    print(f"[dp{args.gpus}] {n_meas} steps in {dt:.2f}s = "
          f"{n_meas/dt:.2f} steps/s, {sps:.0f} samples/s "
          f"(global batch={args.batch_size})", flush=True)


def run_ddp(args):
    import torch.distributed as dist
    rank = int(os.environ["RANK"])
    local_rank = int(os.environ["LOCAL_RANK"])
    world = int(os.environ["WORLD_SIZE"])
    dist.init_process_group("nccl")
    torch.cuda.set_device(local_rank)
    device = torch.device(f"cuda:{local_rank}")

    ds, n_rows = build_dataset(args)
    if rank == 0:
        print(f"[ddp world={world}] dataset rows={n_rows:,}", flush=True)
    model, strategy = build_model(args)
    model = model.to(device)
    model = torch.nn.parallel.DistributedDataParallel(
        model, device_ids=[local_rank], find_unused_parameters=True,
    )
    model.train()
    if rank == 0:
        n_params = sum(p.numel() for p in model.module.parameters())
        print(f"[ddp world={world}] model params={n_params/1e6:.2f}M", flush=True)

    per_gpu_bs = args.batch_size // world
    sampler = DistributedSampler(ds, num_replicas=world, rank=rank, shuffle=True, drop_last=True)
    loader = DataLoader(ds, batch_size=per_gpu_bs, sampler=sampler,
                        num_workers=args.num_workers, pin_memory=True,
                        persistent_workers=args.num_workers > 0,
                        drop_last=True, collate_fn=strategy.collate_fn)
    optim = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-4)

    it = iter(loader)
    n_warmup = args.warmup_steps
    n_meas = args.measure_steps
    for step in range(n_warmup + n_meas):
        try:
            batch = next(it)
        except StopIteration:
            sampler.set_epoch(step)
            it = iter(loader); batch = next(it)
        batch = to_device(batch, device)
        if step == n_warmup:
            torch.cuda.synchronize(); t0 = time.time()
        # forward through strategy
        # (strategy.forward_from_batch dispatches to model — works with DDP)
        if args.amp:
            with torch.amp.autocast(device_type="cuda", dtype=torch.bfloat16):
                raw_logits, _ = strategy.forward_from_batch(model, batch)
                masked = raw_logits.masked_fill(~batch["action_mask"], -1e9)
                loss = F.cross_entropy(masked, batch["action"])
        else:
            raw_logits, _ = strategy.forward_from_batch(model, batch)
            masked = raw_logits.masked_fill(~batch["action_mask"], -1e9)
            loss = F.cross_entropy(masked, batch["action"])
        optim.zero_grad(set_to_none=True)
        loss.backward()
        optim.step()
    torch.cuda.synchronize()
    dt = time.time() - t0
    sps_local = n_meas * per_gpu_bs / dt
    sps_global = n_meas * args.batch_size / dt
    if rank == 0:
        print(f"[ddp world={world}] {n_meas} steps in {dt:.2f}s = "
              f"{n_meas/dt:.2f} steps/s, GLOBAL {sps_global:.0f} samples/s "
              f"(per-gpu batch={per_gpu_bs}, global batch={args.batch_size})", flush=True)
    dist.destroy_process_group()


def main():
    args = parse_args()
    torch.backends.cudnn.benchmark = True
    if args.mode == "single":
        run_single(args)
    elif args.mode == "dp":
        run_dp(args)
    elif args.mode == "ddp":
        run_ddp(args)


if __name__ == "__main__":
    main()
