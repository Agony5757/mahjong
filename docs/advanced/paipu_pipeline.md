# Incremental Paipu Pipeline

`tools/paipu_pipeline.py` builds a token-cache from raw Tenhou paipu in a
fully **resumable** and **self-healing** way. It is driven by a single
append-only manifest (`manifest.jsonl`) that records every state
transition for every game id, so any run can be safely interrupted and
restarted.

## Layout on disk

```
<work>/
  manifest.jsonl                       # append-only event log
  game_ids_<year>.txt                  # extracted from the year zip
  xml/<game_id>.txt                    # raw paipu (named .txt because
                                       # PaipuReplay requires it)
  cache/
    index.json                         # rebuilt from per-shard meta.json
    shard_00000/{tokens,scalars,...}.npy
    shard_00000/meta.json
    ...
```

## Subcommands

| Command | Purpose |
|---|---|
| `run` | full pipeline: sanity check → adopt unknown XMLs → download missing ids → encode → rebuild cache index |
| `check` | dry-run sanity check (use `--repair` to delete corrupt XMLs) |
| `status` | summarise manifest counts |
| `rebuild-index` | regenerate `cache/index.json` from per-shard `meta.json` |

Common flags:

- `--work <dir>` : working directory (required)
- `--year <YYYY>`: download / use the year zip from `tenhou.net/sc/raw`
- `--max-new <N>`: cap how many new paipu to download in one invocation
- `--shard-rows <N>`: rows per shard (default 65536)
- `--delay <sec>` : sleep between downloads (be polite)

## Manifest schema

Each line is a JSON object. The most recent record per `gid` wins.

```jsonc
{ "ts": "...", "gid": "...", "status": "downloaded",
  "sha256": "...", "size": 14246 }
{ "ts": "...", "gid": "...", "status": "encoded",
  "shard": "shard_00000", "n_samples": 2387 }
{ "ts": "...", "gid": "...", "status": "duplicate",
  "sha256": "...", "alias_of": "<other-gid>" }
{ "ts": "...", "gid": "...", "status": "corrupt" }
{ "ts": "...", "gid": "...", "status": "failed", "error": "..." }
```

Statuses:

- `downloaded` — XML present and sha-verified, not yet encoded
- `encoded`    — encoded into a shard (terminal happy path)
- `duplicate`  — same sha256 as another gid; XML deleted
- `corrupt`    — sha mismatch or bad payload (queued for re-download)
- `failed`     — download or encoding error

## Atomic encoding

The encode stage buffers samples per shard and writes them via
`pymahjong.rl.cache.ShardWriter`. The manifest `encoded` event is
appended **after** the shard file is closed (and `meta.json` written),
so:

- A crash mid-shard leaves the affected paipu as `downloaded` and they
  will be re-encoded next run.
- A successfully closed shard is durable even if the process dies before
  exit.

After repair (e.g. corrupt XML re-fetched), the new content is encoded
into a *new* shard. The previous shard may now contain stale rows whose
paipu are no longer associated with it; `cache/index.json` only counts
samples claimed by current `encoded` events, but the on-disk shard rows
remain. A future `compact` command may rewrite shards to drop stale
rows. For training this is harmless: the loader uses `index.json`.

## Sanity check categories

Every `run`/`check` invocation prints:

| Field | Meaning |
|---|---|
| `xmls (ok)`        | XML file exists and sha matches manifest |
| `xmls (corrupt)`   | XML exists but sha differs from manifest |
| `xmls (missing)`   | manifest says `downloaded` but file is gone |
| `xmls (unknown)`   | XML exists but no manifest record (will be adopted) |
| `shard mismatches` | `meta.json.n_rows` differs from manifest claims |
| `orphan shards`    | shard dir exists but no manifest record points to it |

`--repair` will:

- delete any XML whose sha mismatches the recorded one and emit a
  `corrupt` event so it gets re-fetched on the next `run`;
- leave shards untouched (they are addressed by re-encode, not delete).

## Typical flows

**Build a fresh cache from a year zip:**

```bash
python tools/paipu_pipeline.py run --work data/tenhou --year 2024
```

**Resume after a crash:**

```bash
python tools/paipu_pipeline.py run --work data/tenhou --year 2024
# sanity check finds in-flight state, encode picks up where it left off
```

**Recover from disk corruption:**

```bash
python tools/paipu_pipeline.py check --work data/tenhou --repair
python tools/paipu_pipeline.py run   --work data/tenhou --year 2024
```

**Use hand-curated XMLs only:**

```bash
mkdir -p data/tenhou/xml
cp my_paipu/*.txt data/tenhou/xml/        # name them <gid>.txt
python tools/paipu_pipeline.py run --work data/tenhou
# adopt step picks them up; download step is a no-op
```
