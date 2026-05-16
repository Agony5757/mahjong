"""Verify the V2 token encoding against real Tenhou paipu replays.

Replays each paipu via :class:`PaipuReplay`. Before each engine selection,
encodes the current state and checks that

    state_to_string(table, current_player) == tokens_to_string(encode(table, current_player))

Prints aggregate statistics. Exits non-zero on the first mismatch (so it can
be wired into CI).

Usage::

    python tools/verify_encoding_paipu.py [path-to-paipuxmls-dir] [--max N]

Defaults to ``./paipuxmls`` and the first ``--max`` files (default 50).
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from glob import glob

# Make sure we run against the local checkout, not any installed wheel.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import MahjongPyWrapper as pm  # type: ignore  # noqa: E402
from pymahjong import tenhou_paipu_check as tpc  # noqa: E402
from pymahjong.rl.tokenization import (  # noqa: E402
    MahjongTokenizer,
    is_chankan_phase,
    is_response_phase,
    is_self_phase,
    state_to_string,
    tokens_to_string,
)


class _ReplayerProxy:
    """Wraps a ``pm.PaipuReplayer`` so we can intercept ``make_selection``.

    The C++ binding's attributes are read-only, so direct monkey-patching
    is not possible. We forward every other attribute to the underlying
    instance and only override ``make_selection``.
    """

    __slots__ = ("_inner", "_verifier")

    def __init__(self, inner, verifier: "_Verifier") -> None:
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_verifier", verifier)

    def __getattr__(self, name):  # only called on miss
        return getattr(self._inner, name)

    def make_selection(self, idx):
        self._verifier.check(self._inner.table)
        return self._inner.make_selection(idx)


class _Verifier:
    def __init__(self) -> None:
        self.tk = MahjongTokenizer()
        self.checks = 0
        self.mismatches = 0
        self.first_mismatch = None

    def check(self, table) -> None:
        phase = int(table.get_phase())
        if phase >= 16:
            return
        cp = phase % 4
        if not (is_self_phase(phase) or is_response_phase(phase) or is_chankan_phase(phase)):
            return
        try:
            obs = self.tk.encode(table, cp)
            s_state = state_to_string(table, cp)
            s_tokens = tokens_to_string(obs)
        except Exception as e:  # noqa: BLE001
            self.mismatches += 1
            if self.first_mismatch is None:
                self.first_mismatch = ("encode-error", repr(e), traceback.format_exc())
            return
        self.checks += 1
        if s_state != s_tokens:
            self.mismatches += 1
            if self.first_mismatch is None:
                self.first_mismatch = ("string-mismatch", s_state, s_tokens, phase, cp)


def _wrap_replayer_for_check(replayer, verifier: _Verifier):
    """Return a proxy that intercepts ``make_selection`` for round-trip checks."""
    return _ReplayerProxy(replayer, verifier)


def main() -> int:
    from pymahjong.config import get_config
    _default_path = get_config().paipu_xml_path or "paipuxmls"

    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=_default_path)
    parser.add_argument("--max", type=int, default=50)
    parser.add_argument("--fail-fast", action="store_true")
    args = parser.parse_args()

    files = sorted(glob(os.path.join(args.path, "*.txt")))
    if not files:
        print(f"No paipu .txt files found in {args.path}", file=sys.stderr)
        return 2
    files = files[: args.max]
    print(f"Verifying encoding on {len(files)} paipu files from {args.path}")

    verifier = _Verifier()

    # Patch the constructor used by PaipuReplay so each PaipuReplayer gets
    # wrapped automatically.
    orig_pr_ctor = pm.PaipuReplayer

    def _patched_ctor(*a, **kw):
        inst = orig_pr_ctor(*a, **kw)
        return _wrap_replayer_for_check(inst, verifier)

    pm.PaipuReplayer = _patched_ctor  # type: ignore[assignment]

    replay = tpc.PaipuReplay()
    replay.logger = tpc.Logger()
    replay.write_log = False

    games_ok = 0
    games_err = 0
    for i, fp in enumerate(files):
        try:
            replay._paipu_replay(args.path, os.path.basename(fp))
            games_ok += 1
        except Exception as e:  # noqa: BLE001
            games_err += 1
            if args.fail_fast:
                print(f"Game {fp} failed: {e}", file=sys.stderr)
                traceback.print_exc()
                break
        if (i + 1) % 25 == 0:
            print(
                f"  ... {i + 1}/{len(files)} files | "
                f"checks={verifier.checks} mismatches={verifier.mismatches} "
                f"games_err={games_err}"
            )
        if verifier.mismatches and args.fail_fast:
            break

    pm.PaipuReplayer = orig_pr_ctor  # type: ignore[assignment]

    print()
    print("=" * 60)
    print(f"files processed   : {len(files)}")
    print(f"games OK          : {games_ok}")
    print(f"games errored     : {games_err}  (engine-level errors, not encoding)")
    print(f"states checked    : {verifier.checks}")
    print(f"encoding mismatch : {verifier.mismatches}")
    if verifier.first_mismatch:
        print()
        print("--- first mismatch ---")
        m = verifier.first_mismatch
        if m[0] == "encode-error":
            print("encode-error:", m[1])
            print(m[2])
        else:
            _, s_state, s_tokens, phase, cp = m
            print(f"phase={phase} current_player={cp}")
            print("-- state_to_string --")
            print(s_state)
            print("-- tokens_to_string --")
            print(s_tokens)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
