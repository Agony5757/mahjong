"""Neutral shard-manifest I/O shared across the RL stack.

These small classes/functions describe an on-disk cache as a list of
shards with cumulative row counts plus a schema fingerprint that the
loader checks against the live encoder.  They are not specific to any
encoding version; the encoder-specific cache modules (currently
``pymahjong/rl/cache.py``) build on top of them.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from typing import Callable, Dict, List, Optional


@dataclass
class ShardEntry:
    path: str            # relative to cache_dir
    n_rows: int
    cumulative: int      # cumulative row count *including* this shard


@dataclass
class CacheManifest:
    schema: Dict
    total_rows: int
    shards: List[ShardEntry]

    def to_dict(self) -> Dict:
        return {
            "schema": self.schema,
            "total_rows": int(self.total_rows),
            "shards": [asdict(s) for s in self.shards],
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "CacheManifest":
        return cls(
            schema=d["schema"],
            total_rows=int(d["total_rows"]),
            shards=[ShardEntry(**s) for s in d["shards"]],
        )


def manifest_path(cache_dir: str) -> str:
    return os.path.join(cache_dir, "index.json")


def load_manifest(cache_dir: str) -> CacheManifest:
    with open(manifest_path(cache_dir), "r") as f:
        return CacheManifest.from_dict(json.load(f))


def save_manifest(cache_dir: str, manifest: CacheManifest) -> None:
    os.makedirs(cache_dir, exist_ok=True)
    tmp = manifest_path(cache_dir) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)
    os.replace(tmp, manifest_path(cache_dir))


def rebuild_manifest_base(
    cache_dir: str,
    schema_fn: Callable[[], Dict],
) -> CacheManifest:
    """Scan ``cache_dir`` for ``shard_*`` directories and rewrite ``index.json``.

    Useful after parallel writers have produced shards independently.
    Encoder-specific callers supply a ``schema_fn`` so the resulting
    manifest carries the right fingerprint.
    """
    entries: List[ShardEntry] = []
    cum = 0
    for name in sorted(os.listdir(cache_dir)):
        sub = os.path.join(cache_dir, name)
        if not (name.startswith("shard_") and os.path.isdir(sub)):
            continue
        try:
            with open(os.path.join(sub, "meta.json")) as f:
                m = json.load(f)
        except FileNotFoundError:
            continue
        n = int(m.get("n_rows", 0))
        if n <= 0:
            continue
        cum += n
        entries.append(ShardEntry(path=name, n_rows=n, cumulative=cum))

    manifest = CacheManifest(
        schema=schema_fn(),
        total_rows=cum,
        shards=entries,
    )
    save_manifest(cache_dir, manifest)
    return manifest


# Back-compat alias used by ``pymahjong.rl.cache`` (event-stream encoder).
rebuild_manifest = rebuild_manifest_base
