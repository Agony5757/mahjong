# Shanten Calculation

This page documents how `pymahjong` currently computes ordinary-hand shanten and why that implementation was changed.

## Public API

The Python binding exposes:

```python
import pymahjong

pymahjong.normal_round_to_win("245568m245568p77s", 0)
```

The return value follows the historical convention used by this project:

- `0`: already complete (`agari`)
- `1`: `tenpai`
- `2`: `1-shanten`
- `3`: `2-shanten`
- and so on

This is a **replacement number** style API, not the raw shanten number.

## Scope

`normal_round_to_win(..., num_open_melds)` is an **ordinary-hand** calculator for the 4 meld + 1 pair structure.

It does **not** directly compute the best deficiency number across:

- chiitoitsu
- kokushi musou

Those hand families are handled elsewhere in the rule engine for agari and tenpai checks.

## Why The Old Implementation Was Replaced

Older revisions relied on a meld/taatsu-counting shortcut with a precomputed `syanten.dat` table. That approach was fast, but it can miscount in edge cases where local suit-optimal decompositions do not combine into the global optimum.

The issue became concrete again in [issue #30](https://github.com/Agony5757/mahjong/issues/30), where the hand:

```text
245568m245568p77s
```

was reported with the wrong value.

## Current Algorithm

The current implementation lives in [Mahjong/RoundToWin.cpp](../../Mahjong/RoundToWin.cpp) and uses an exact memoized depth-first search over:

- tile counts
- number of closed melds already formed
- number of taatsu already formed
- whether a pair has already been reserved

At each step, it consumes the first remaining tile and branches over the productive choices:

- triplet
- sequence
- pair
- adjacent taatsu
- gapped taatsu
- skip the tile

The memoization key is the full 34-tile count vector plus the `(melds, taatsu, has_pair)` state, which makes the search exact while keeping it fast enough for testing and gameplay.

## Testing Strategy

The shanten test suite now combines several layers:

1. Fixed regression cases for known bugs and boundary hands.
2. Property-style randomized tests for ordinary winning hands, tenpai hands, and recurrence checks.
3. A frozen offline reference corpus generated from `xiangting`.

The fixed corpus is stored in:

- [pymahjong/test_data/xiangting_corpus.py](../../pymahjong/test_data/xiangting_corpus.py)

The regeneration script is stored in:

- [tools/shanten_corpus/generate_xiangting_corpus.py](../../tools/shanten_corpus/generate_xiangting_corpus.py)

This keeps CI deterministic while still anchoring the ordinary-hand API to an external reference implementation.

## Acknowledgements

The redesign was prompted in part by the practical feedback from [Apricot-S](https://github.com/Apricot-S) in [issue #30](https://github.com/Agony5757/mahjong/issues/30), which correctly pointed out that patching individual edge cases on top of meld/taatsu heuristics was not a robust direction.

The following repositories were useful references and prior art while evaluating the redesign and the testing strategy:

- [tomohxx/shanten-number](https://github.com/tomohxx/shanten-number)
- [Cryolite/nyanten](https://github.com/Cryolite/nyanten)
- [Apricot-S/xiangting](https://github.com/Apricot-S/xiangting)
- [MahjongRepository/mahjong](https://github.com/MahjongRepository/mahjong)
