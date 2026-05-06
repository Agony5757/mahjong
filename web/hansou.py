"""
Hansou (半庄) session: multi-kyoku loop on top of MahjongEnv.

Drives a full Japanese mahjong half-game (East 1 → South 4) by repeatedly
resetting MahjongEnv with the next kyoku's oya/wind/honba/kyoutaku/scores
derived from the previous kyoku's Result.

Single-kyoku (East-only) and configurable-length games are also supported.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Optional

import MahjongPyWrapper as pm

# Map game_wind int (0..3) to the string MahjongEnv.reset expects
_WIND_INT_TO_STR = ("east", "south", "west", "north")
_WIND_INT_TO_CN = ("东", "南", "西", "北")


@dataclass
class KyokuRecord:
    """Compact record of one finished kyoku for the front-end log."""
    index: int               # kyoku index in the hansou (0-based)
    game_wind: int           # 0=East .. 3=North
    oya: int
    honba: int
    kyoutaku_in: int
    scores_in: list          # scores at start of this kyoku
    scores_out: list         # scores at end of this kyoku
    result_type: str
    winner: list             # player ids
    loser: Optional[int]     # player id (deal-in) or None
    renchan: bool
    n_honba: int             # honba carried into next kyoku
    n_kyoutaku: int          # kyoutaku carried into next kyoku


class HansouSession:
    """Drives a sequence of kyoku making up a half-game.

    Configuration:
        max_round: 0=East only (4-kyoku tonpuusen), 1=hansou (8-kyoku), 2=full (16-kyoku).
        hard_cap:  absolute maximum kyoku count to break out of pathological renchan loops.
    """

    def __init__(
        self,
        env: "MahjongEnvAdapter",  # noqa: F821
        max_round: int = 1,
        hard_cap: int = 16,
        starting_scores: Optional[list] = None,
    ):
        self.env = env
        self.max_round = max_round  # 0=East, 1=East+South (hansou), 2=full
        self.hard_cap = hard_cap
        self.scores = list(starting_scores or [25000, 25000, 25000, 25000])

        # State of the *current* kyoku
        self.kyoku_index: int = 0     # 0..3=East1..East4, 4..7=South1..South4
        self.honba: int = 0
        self.kyoutaku: int = 0
        self.kyoku_count: int = 0     # number of kyoku played (incl. current)

        self.log: list[KyokuRecord] = []
        self.finished: bool = False
        self._lock = threading.Lock()

    # ─── Round/wind/oya helpers ─────────────────────────────────────────────

    @property
    def game_wind(self) -> int:
        return self.kyoku_index // 4

    @property
    def oya(self) -> int:
        return self.kyoku_index % 4

    @property
    def round_label(self) -> str:
        """e.g. '东1局' / '南3局'."""
        wind = _WIND_INT_TO_CN[self.game_wind] if self.game_wind < 4 else "?"
        return f"{wind}{self.oya + 1}局"

    @property
    def max_kyoku_index(self) -> int:
        """Last kyoku_index that should be played (East+South = 7)."""
        return (self.max_round + 1) * 4 - 1  # tonpuu=3, hansou=7, full=15

    # ─── Loop control ───────────────────────────────────────────────────────

    def start_first_kyoku(self, seed: Optional[int] = None) -> None:
        """Begin the very first kyoku of the hansou."""
        with self._lock:
            self.env.reset_kyoku(
                oya=self.oya,
                game_wind=_WIND_INT_TO_STR[self.game_wind],
                scores=list(self.scores),
                kyoutaku=self.kyoutaku,
                honba=self.honba,
                seed=seed,
            )
            self.kyoku_count = 1

    def conclude_current_kyoku(self) -> KyokuRecord:
        """
        Capture the result of the just-finished kyoku, update hansou state
        (scores/honba/kyoutaku/kyoku_index/finished). Returns the record.

        Caller is responsible for invoking ``advance_to_next_kyoku()`` afterwards
        if ``finished`` is still False.
        """
        with self._lock:
            res = self.env.get_result()
            scores_in = list(self.scores)
            new_scores = list(res.score) if res is not None else scores_in
            try:
                loser_list = list(res.loser) if res and res.loser is not None else []
                loser = int(loser_list[0]) if loser_list else None
            except TypeError:
                # Old binding may expose loser as a single int
                loser = int(res.loser) if res and res.loser is not None else None

            winner: list = []
            if res is not None and res.winner is not None:
                try:
                    winner = [int(w) for w in list(res.winner)]
                except TypeError:
                    winner = [int(res.winner)]

            renchan = bool(res.renchan) if res is not None else False
            n_honba = int(res.n_honba) if res is not None else 0
            n_kyoutaku = int(res.n_riichibo) if res is not None else 0
            result_type = (
                str(res.result_type).split(".")[-1] if res is not None else "Unknown"
            )

            record = KyokuRecord(
                index=self.kyoku_index,
                game_wind=self.game_wind,
                oya=self.oya,
                honba=self.honba,
                kyoutaku_in=self.kyoutaku,
                scores_in=scores_in,
                scores_out=new_scores,
                result_type=result_type,
                winner=winner,
                loser=loser,
                renchan=renchan,
                n_honba=n_honba,
                n_kyoutaku=n_kyoutaku,
            )
            self.log.append(record)

            self.scores = new_scores
            self.honba = n_honba
            self.kyoutaku = n_kyoutaku

            if not renchan:
                self.kyoku_index += 1

            # Termination conditions
            if self._should_finish(record):
                self.finished = True

            return record

    def _should_finish(self, record: KyokuRecord) -> bool:
        # Tobi (any score < 0)
        if any(s < 0 for s in self.scores):
            return True
        if self.kyoku_count >= self.hard_cap:
            return True
        # Last kyoku of the configured length, no renchan
        if self.kyoku_index > self.max_kyoku_index:
            return True
        return False

    def advance_to_next_kyoku(self) -> None:
        """Reset the env for the next kyoku (no-op if finished)."""
        with self._lock:
            if self.finished:
                return
            self.env.reset_kyoku(
                oya=self.oya,
                game_wind=_WIND_INT_TO_STR[self.game_wind],
                scores=list(self.scores),
                kyoutaku=self.kyoutaku,
                honba=self.honba,
                seed=None,
            )
            self.kyoku_count += 1

    # ─── Snapshot ───────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        return {
            "kyoku_index": self.kyoku_index,
            "kyoku_count": self.kyoku_count,
            "round_label": self.round_label,
            "game_wind": self.game_wind,
            "oya": self.oya,
            "honba": self.honba,
            "kyoutaku": self.kyoutaku,
            "scores": list(self.scores),
            "max_kyoku_index": self.max_kyoku_index,
            "max_round": self.max_round,
            "finished": self.finished,
            "log": [
                {
                    "index": r.index,
                    "round_label": f"{_WIND_INT_TO_CN[r.game_wind]}{r.oya + 1}局",
                    "honba": r.honba,
                    "result_type": r.result_type,
                    "winner": r.winner,
                    "loser": r.loser,
                    "renchan": r.renchan,
                    "scores_in": r.scores_in,
                    "scores_out": r.scores_out,
                    "score_delta": [b - a for a, b in zip(r.scores_in, r.scores_out)],
                }
                for r in self.log
            ],
        }
