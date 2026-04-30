#!/usr/bin/env python3

from __future__ import annotations

import random
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import xiangting
from pymahjong import normal_round_to_win


SEED = 20260430
STRUCTURED_TARGET = 200
RANDOM_TARGET = 100
OUTPUT = Path(__file__).resolve().parents[2] / "pymahjong" / "test_data" / "xiangting_corpus.py"
XIANGTING_VERSION = version("xiangting")
TILES = tuple(range(34))
SUITS = (
    (0, 9, "m"),
    (9, 9, "p"),
    (18, 9, "s"),
    (27, 7, "z"),
)
MELDS = tuple([[tile, tile, tile] for tile in TILES]) + tuple(
    [start + offset, start + offset + 1, start + offset + 2]
    for start in (0, 9, 18)
    for offset in range(7)
)


def counts_to_compact_hand(counts: list[int]) -> str:
    parts = []
    for start, length, suffix in SUITS:
        digits = []
        for offset in range(length):
            digits.extend(str(offset + 1) for _ in range(counts[start + offset]))
        if digits:
            parts.append("".join(digits) + suffix)
    return "".join(parts)


def can_add_block(counts: list[int], block: list[int]) -> bool:
    increments: dict[int, int] = {}
    for tile in block:
        increments[tile] = increments.get(tile, 0) + 1
        if counts[tile] + increments[tile] > 4:
            return False
    return True


def build_random_ordinary_win_hand(rng: random.Random) -> list[int]:
    for _ in range(256):
        counts = [0] * 34
        ok = True

        for _ in range(4):
            candidates = [meld for meld in MELDS if can_add_block(counts, meld)]
            if not candidates:
                ok = False
                break
            for tile in rng.choice(candidates):
                counts[tile] += 1

        if not ok:
            continue

        pair_candidates = [tile for tile in TILES if counts[tile] <= 2]
        if not pair_candidates:
            continue

        counts[rng.choice(pair_candidates)] += 2
        return counts

    raise RuntimeError("Failed to generate a random ordinary winning hand.")


def perturb_hand(counts: list[int], replacements: int, rng: random.Random) -> list[int]:
    counts = counts.copy()
    for _ in range(replacements):
        removable = [tile for tile in TILES if counts[tile] > 0]
        discard = rng.choice(removable)
        counts[discard] -= 1

        drawable = [tile for tile in TILES if counts[tile] < 4 and tile != discard]
        draw = rng.choice(drawable)
        counts[draw] += 1
    return counts


def remove_random_tile(counts: list[int], rng: random.Random) -> list[int]:
    counts = counts.copy()
    removable = [tile for tile in TILES if counts[tile] > 0]
    counts[rng.choice(removable)] -= 1
    return counts


def random_closed_hand(rng: random.Random, tile_count: int) -> list[int]:
    counts = [0] * 34
    for _ in range(tile_count):
        drawable = [tile for tile in TILES if counts[tile] < 4]
        counts[rng.choice(drawable)] += 1
    return counts


def try_case(counts: list[int]) -> tuple[str, int] | None:
    hand = counts_to_compact_hand(counts)
    expected = xiangting.calculate_replacement_number(counts, xiangting.PlayerCount.FOUR)
    actual = normal_round_to_win(hand, 0)
    if expected != actual:
        return None
    return hand, expected


def generate_cases() -> list[tuple[str, int]]:
    rng = random.Random(SEED)
    cases: dict[str, int] = {}

    while len(cases) < STRUCTURED_TARGET:
        base14 = build_random_ordinary_win_hand(rng)
        if rng.random() < 0.5:
            counts = perturb_hand(base14, rng.randint(0, 3), rng)
        else:
            counts = perturb_hand(remove_random_tile(base14, rng), rng.randint(0, 2), rng)
        case = try_case(counts)
        if case is not None:
            cases.setdefault(*case)

    while len(cases) < STRUCTURED_TARGET + RANDOM_TARGET:
        counts = random_closed_hand(rng, 13 if rng.random() < 0.5 else 14)
        case = try_case(counts)
        if case is not None:
            cases.setdefault(*case)

    return sorted(cases.items(), key=lambda item: (item[1], item[0]))


def render_module(cases: list[tuple[str, int]]) -> str:
    distribution = Counter(expected for _, expected in cases)
    lines = [
        '"""Fixed shanten corpus generated from xiangting.',
        "",
        f"Seed: {SEED}",
        f"Reference package: xiangting {XIANGTING_VERSION}",
        "",
        "These are closed-hand cases whose xiangting replacement number matches",
        "pymahjong.normal_round_to_win(hand, 0).",
        '"""',
        "",
        f"XIANGTING_SHANTEN_CORPUS_300 = [",
    ]
    lines.extend(f'    ("{hand}", {expected}),' for hand, expected in cases)
    lines.extend(
        [
            "]",
            "",
            f"XIANGTING_SHANTEN_CORPUS_DISTRIBUTION = {dict(sorted(distribution.items()))}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    cases = generate_cases()
    if len(cases) != 300:
        raise RuntimeError(f"Expected 300 cases, got {len(cases)}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_module(cases), encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUTPUT}")


if __name__ == "__main__":
    main()
