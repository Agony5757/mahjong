# Shanten Corpus Generation

This directory contains maintenance scripts for generating a fixed closed-hand shanten corpus from an external reference implementation.

## Reference

The current corpus is generated from the Python bindings of `xiangting` and then filtered to cases where the reference replacement number matches `pymahjong.normal_round_to_win(..., 0)`.

This filtering is intentional:

- `pymahjong.normal_round_to_win` is an ordinary-hand API.
- `xiangting.calculate_replacement_number` computes the overall replacement number for a closed hand.
- Hands where chiitoitsu or kokushi produce a smaller deficiency number are excluded from this corpus.

## Regenerate

Prepare an environment where both `pymahjong` and `xiangting` are importable, then run:

```bash
python tools/shanten_corpus/generate_xiangting_corpus.py
```

This rewrites:

```text
pymahjong/test_data/xiangting_corpus.py
```

The generator uses a deterministic seed and writes 300 unique cases.
