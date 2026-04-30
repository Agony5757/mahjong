import random
import time
from functools import lru_cache

import numpy as np

from .env_pymahjong import MahjongEnv, SingleAgentMahjongEnv
from .test_data.xiangting_corpus import XIANGTING_SHANTEN_CORPUS_300
from MahjongPyWrapper import is_ordinary_agari, normal_round_to_win


_TILES = tuple(range(34))
_SUITS = (
    (0, 9, "m"),
    (9, 9, "p"),
    (18, 9, "s"),
    (27, 7, "z"),
)
_MELDS = (
    [tile, tile, tile] for tile in _TILES
)
_MELDS = tuple(_MELDS) + tuple(
    [start + offset, start + offset + 1, start + offset + 2]
    for start in (0, 9, 18)
    for offset in range(7)
)


def _can_add_block(counts, block):
    increments = {}
    for tile in block:
        increments[tile] = increments.get(tile, 0) + 1
        if counts[tile] + increments[tile] > 4:
            return False
    return True


def _parse_compact_hand(hand):
    counts = [0] * 34
    digits = []

    for ch in hand:
        if ch.isdigit():
            digits.append(ch)
            continue

        if not digits:
            raise ValueError(f"Bad compact hand string: {hand!r}")

        if ch == "m":
            base = 0
        elif ch == "p":
            base = 9
        elif ch == "s":
            base = 18
        elif ch == "z":
            base = 27
        else:
            raise ValueError(f"Bad suit marker {ch!r} in {hand!r}")

        for digit in digits:
            tile = base + (5 if digit == "0" else int(digit)) - 1
            counts[tile] += 1
            if counts[tile] > 4:
                raise ValueError(f"Too many copies of tile {tile} in {hand!r}")
        digits.clear()

    if digits:
        raise ValueError(f"Compact hand string must end with a suit marker: {hand!r}")

    return counts


def _counts_to_compact_hand(counts):
    parts = []
    for start, length, suffix in _SUITS:
        digits = []
        for offset in range(length):
            digits.extend(str(offset + 1) for _ in range(counts[start + offset]))
        if digits:
            parts.append("".join(digits) + suffix)
    return "".join(parts)


@lru_cache(maxsize=None)
def _is_ordinary_agari_cached(hand):
    return is_ordinary_agari(hand)


def _has_ordinary_winning_draw(counts13):
    counts = counts13.copy()
    for tile in _TILES:
        if counts[tile] == 4:
            continue
        counts[tile] += 1
        if _is_ordinary_agari_cached(_counts_to_compact_hand(counts)):
            counts[tile] -= 1
            return True
        counts[tile] -= 1
    return False


def _has_one_replacement_to_ordinary_win(counts14):
    counts = counts14.copy()
    seen_discards = set()

    for discard in _TILES:
        if counts[discard] == 0 or discard in seen_discards:
            continue
        seen_discards.add(discard)
        counts[discard] -= 1
        for draw in _TILES:
            if counts[draw] == 4:
                continue
            counts[draw] += 1
            if _is_ordinary_agari_cached(_counts_to_compact_hand(counts)):
                counts[draw] -= 1
                counts[discard] += 1
                return True
            counts[draw] -= 1
        counts[discard] += 1
    return False


def _build_random_ordinary_win_hand(rng):
    for _ in range(256):
        counts = [0] * 34
        ok = True

        for _ in range(4):
            candidates = [meld for meld in _MELDS if _can_add_block(counts, meld)]
            if not candidates:
                ok = False
                break
            for tile in rng.choice(candidates):
                counts[tile] += 1

        if not ok:
            continue

        pair_candidates = [tile for tile in _TILES if counts[tile] <= 2]
        if not pair_candidates:
            continue
        pair_tile = rng.choice(pair_candidates)
        counts[pair_tile] += 2

        hand = _counts_to_compact_hand(counts)
        if _is_ordinary_agari_cached(hand):
            return counts

    raise RuntimeError("Failed to generate a random ordinary winning hand.")


def _perturb_hand(counts, replacements, rng):
    counts = counts.copy()
    for _ in range(replacements):
        removable = [tile for tile in _TILES if counts[tile] > 0]
        discard = rng.choice(removable)
        counts[discard] -= 1

        drawable = [tile for tile in _TILES if counts[tile] < 4 and tile != discard]
        draw = rng.choice(drawable)
        counts[draw] += 1
    return counts


def _remove_random_tile(counts, rng):
    counts = counts.copy()
    removable = [tile for tile in _TILES if counts[tile] > 0]
    counts[rng.choice(removable)] -= 1
    return counts


def _random_closed_hand(rng, tile_count):
    counts = [0] * 34
    for _ in range(tile_count):
        drawable = [tile for tile in _TILES if counts[tile] < 4]
        counts[rng.choice(drawable)] += 1
    return counts


def _assert_known_cases():
    cases = [
        ("123m123p123s111z22z", 0, 0),
        ("123m123p123s111z2z", 0, 1),
        ("245568m245568p77s", 0, 3),  # Issue #30: 2-shanten in standard notation
        ("123m456m11p56s", 1, 1),
        ("1112345678999m", 0, 1),
        ("11223344556677m", 0, 0),
        ("1122334455667m", 0, 1),
        ("1112223334445z", 0, 1),
    ]

    for hand, num_open_melds, expected in cases:
        actual = normal_round_to_win(hand, num_open_melds)
        assert actual == expected, (
            f"normal_round_to_win({hand!r}, {num_open_melds}) = {actual}, "
            f"expected {expected}"
        )


def _assert_xiangting_corpus():
    for hand, expected in XIANGTING_SHANTEN_CORPUS_300:
        actual = normal_round_to_win(hand, 0)
        assert actual == expected, (
            f"xiangting corpus mismatch for {hand}: got {actual}, expected {expected}"
        )


def _assert_direct_boundary_oracle_samples(rng, num_samples):
    for idx in range(num_samples):
        base14 = _build_random_ordinary_win_hand(rng)
        compact14 = _counts_to_compact_hand(base14)
        assert normal_round_to_win(compact14, 0) == 0, (
            f"Winning hand should have round_to_win 0: {compact14}"
        )

        base13 = _remove_random_tile(base14, rng)
        compact13 = _counts_to_compact_hand(base13)
        assert _has_ordinary_winning_draw(base13), f"Generated tenpai hand has no winning draw: {compact13}"
        assert normal_round_to_win(compact13, 0) == 1, (
            f"Tenpai hand should have round_to_win 1: {compact13}"
        )

        hand14 = _perturb_hand(base14, 1 + (idx % 2), rng)
        compact14_mut = _counts_to_compact_hand(hand14)
        actual14 = normal_round_to_win(compact14_mut, 0)
        if _is_ordinary_agari_cached(compact14_mut):
            assert actual14 == 0, f"Ordinary agari hand should return 0: {compact14_mut}"
        elif _has_one_replacement_to_ordinary_win(hand14):
            assert actual14 == 1, (
                f"One-step ordinary win hand should return 1: {compact14_mut}, got {actual14}"
            )

        hand13 = _perturb_hand(base13, idx % 2, rng)
        compact13_mut = _counts_to_compact_hand(hand13)
        actual13 = normal_round_to_win(compact13_mut, 0)
        if _has_ordinary_winning_draw(hand13):
            assert actual13 == 1, (
                f"Winning-draw hand should return 1: {compact13_mut}, got {actual13}"
            )
        else:
            assert actual13 >= 2, (
                f"No-winning-draw hand should be at least 1-shanten: {compact13_mut}, got {actual13}"
            )

        if idx == 0:
            issue_hand = _parse_compact_hand("245568m245568p77s")
            assert not _is_ordinary_agari_cached("245568m245568p77s")
            assert not _has_one_replacement_to_ordinary_win(issue_hand), (
                "Issue #30 hand unexpectedly became a one-step ordinary win."
            )
            assert normal_round_to_win("245568m245568p77s", 0) >= 2


def _assert_draw_recurrence(rng, num_samples):
    for _ in range(num_samples):
        counts13 = _random_closed_hand(rng, 13)
        compact13 = _counts_to_compact_hand(counts13)
        actual = normal_round_to_win(compact13, 0)

        best_after_draw = min(
            normal_round_to_win(_counts_to_compact_hand(counts13[:tile] + [counts13[tile] + 1] + counts13[tile + 1:]), 0)
            for tile in _TILES
            if counts13[tile] < 4
        )

        assert actual == best_after_draw + 1, (
            f"Draw recurrence mismatch for {compact13}: got {actual}, "
            f"but best child was {best_after_draw}"
        )


def test_shanten_regressions(num_oracle_samples=64, num_boundary_samples=128, seed=0):
    """Run deterministic and randomized regression checks for normal-hand shanten.

    ``normal_round_to_win`` uses the historical project convention:
    0 for agari, 1 for tenpai, 2 for 1-shanten, and so on.

    To scale coverage further, increase ``num_oracle_samples`` and
    ``num_boundary_samples`` or feed an external reference corpus.
    """

    rng = random.Random(seed)
    _assert_known_cases()
    _assert_xiangting_corpus()
    _assert_direct_boundary_oracle_samples(rng, num_oracle_samples)
    _assert_draw_recurrence(rng, num_boundary_samples)


def test(num_games=100):
    """Run random-play games to verify the environment works correctly.

    Creates a multi-agent Mahjong environment and runs the specified number
    of games with random action selection. Any errors during gameplay are
    caught and reported with debug replay information.

    Args:
        num_games: Number of games to run. Defaults to 100.

    Example:
        >>> import pymahjong
        >>> pymahjong.test(10)
        Game 0, payoffs: [-15.  35.   5. -25.]
        ...
        Total 10 random-play games, 10 games without error, takes 2.5 s
    """

    env = MahjongEnv()

    start_time = time.time()
    game = 0
    success_games = 0

    while game < num_games:

        try:

            env.reset(oya=game % 4, game_wind="east", debug_mode=1)

            while not env.is_over():

                curr_player_id = env.get_curr_player_id()

                # --------- get decision information -------------

                valid_actions_mask = env.get_valid_actions(nhot=True)
                executor_obs = env.get_obs(curr_player_id)

                # oracle_obs = env.get_oracle_obs(curr_player_id)
                # full_obs = env.get_full_obs(curr_player_id)
                # full_obs = np.concatenate([executor_obs, oracle_obs], axis=0)

                # --------- make decision -------------

                a = np.random.choice(np.argwhere(
                    valid_actions_mask).reshape([-1]))

                env.step(curr_player_id, a)

            # ----------------------- get result ---------------------------------

            payoffs = np.array(env.get_payoffs())
            print("Game {}, payoffs: {}".format(game, payoffs))
            # env.render()

            success_games += 1
            game += 1

        except Exception as inst:
            game += 1
            time.sleep(0.1)
            print(
                "-------------- execption in game {} -------------------------".format(game))
            print(inst)
            env.render()
            print("-------------- replayable log -------------------------------")
            env.t.print_debug_replay()
            continue

    print("Total {} random-play games, {} games without error, takes {} s".format(
        num_games, success_games, time.time() - start_time))


def test_with_pretrained(opponent_agent, num_games=100):
    """Test the single-agent environment with pretrained opponent models.

    Creates a single-agent environment where the agent (player 0) plays
    against pretrained VLOG models. The agent selects actions randomly,
    demonstrating the environment's basic functionality with intelligent
    opponents.

    Args:
        opponent_agent: Path to a pretrained model file (.pth). Available
            models are ``mahjong_VLOG_CQL.pth`` (CQL) and
            ``mahjong_VLOG_BC.pth`` (BC). Download from `GitHub releases
            <https://github.com/Agony5757/mahjong/releases/tag/v1.0.2>`_.
        num_games: Number of games to run. Defaults to 100.

    Example:
        >>> import pymahjong
        >>> pymahjong.test_with_pretrained("mahjong_VLOG_BC.pth", 10)
        Game 0, agent payoff -15.0
        ...
        Total 10 random-play games with pretrained VLOG models as opponents,
        10 games without error, takes 30.2 s
    """

    env = SingleAgentMahjongEnv(opponent_agent)

    start_time = time.time()
    success_games = 0

    for game in range(num_games):

        try:
            env.reset()
            payoff = 0

            while True:

                valid_actions = env.get_valid_actions()

                a = np.random.choice(valid_actions)

                obs, reward, done, _ = env.step(a)

                payoff = payoff + reward  # reward may != 0 only when done

                if done:
                    success_games += 1
                    print("Game {}, agent payoff {}".format(game, payoff))
                    break

        except Exception as inst:
            game += 1
            time.sleep(0.1)
            print(
                "-------------- execption in game {} -------------------------".format(game))
            print(inst)
            env.render()
            continue

    print("Total {} random-play games with pretrained VLOG models as opponents, {} games without error, takes {} s".format(
        num_games, success_games, time.time() - start_time))
