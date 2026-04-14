"""Tests for mistakes module helper functions."""

import json
import tempfile
from pathlib import Path

from claudephant.mistakes import (
    cap_and_prioritize,
    compute_stats,
    split_batches,
    top_turns,
)


def _make_session(sid, project, turns):
    """Build a minimal session result dict."""
    return {
        "session_id": sid,
        "project": project,
        "branch": "main",
        "cwd": "/tmp",
        "start_time": "2026-01-01T00:00:00",
        "num_total_turns": len(turns) + 5,
        "num_error_turns": len(turns),
        "turns": turns,
    }


def _make_turn(index, signals, ts="2026-01-01T00:00:00"):
    return {
        "turn_index": index,
        "timestamp": ts,
        "signal": signals,
        "user_prompt": "test prompt",
        "assistant_text": "test response",
        "tool_calls": [],
        "tool_results": [],
    }


class TestComputeStats:
    def test_basic_stats(self):
        results = [
            _make_session(
                "s1",
                "proj-a",
                [
                    _make_turn(0, ["error"]),
                    _make_turn(1, ["user_correction"]),
                ],
            ),
            _make_session(
                "s2",
                "proj-b",
                [
                    _make_turn(0, ["error"]),
                    _make_turn(1, ["self_correction"]),
                    _make_turn(2, ["error", "user_correction"]),
                ],
            ),
        ]
        text = compute_stats(results)
        assert "Sessions matched: 2" in text
        assert "Error turns: 5" in text
        assert "user_correction: 2" in text
        assert "error: 3" in text
        assert "self_correction: 1" in text
        assert "proj-a" in text
        assert "proj-b" in text


class TestCapAndPrioritize:
    def test_caps_turns(self):
        turns = [_make_turn(i, ["self_correction"]) for i in range(10)]
        turns[0]["signal"] = ["user_correction"]
        turns[1]["signal"] = ["error"]
        results = [_make_session("s1", "proj", turns)]

        capped = cap_and_prioritize(results, 3)
        assert capped[0]["num_error_turns"] == 3
        # user_correction and error should be kept (higher priority)
        signals = [t["signal"] for t in capped[0]["turns"]]
        assert ["user_correction"] in signals
        assert ["error"] in signals


class TestTopTurns:
    def test_top_n(self):
        results = [
            _make_session(
                "s1",
                "proj",
                [
                    _make_turn(0, ["self_correction"]),
                    _make_turn(1, ["user_correction"]),
                ],
            ),
            _make_session(
                "s2",
                "proj",
                [
                    _make_turn(0, ["error"]),
                ],
            ),
        ]
        top = top_turns(results, 2)
        total = sum(r["num_error_turns"] for r in top)
        assert total == 2
        # user_correction should be included (highest priority)
        all_signals = [s for r in top for t in r["turns"] for s in t["signal"]]
        assert "user_correction" in all_signals

    def test_top_n_more_than_available(self):
        results = [_make_session("s1", "proj", [_make_turn(0, ["error"])])]
        top = top_turns(results, 100)
        assert sum(r["num_error_turns"] for r in top) == 1


class TestSplitBatches:
    def test_split_creates_files(self):
        results = [
            _make_session("s1", "proj", [_make_turn(i, ["error"]) for i in range(10)]),
            _make_session("s2", "proj", [_make_turn(i, ["error"]) for i in range(5)]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "batches"
            paths = split_batches(results, 2, out_dir)
            assert len(paths) == 2
            for p in paths:
                data = json.loads(p.read_text())
                assert isinstance(data, list)
                # Pretty-printed
                assert "\n " in p.read_text()

    def test_split_balances_by_turns(self):
        # One big session, two small ones
        results = [
            _make_session("big", "proj", [_make_turn(i, ["error"]) for i in range(20)]),
            _make_session("sm1", "proj", [_make_turn(0, ["error"])]),
            _make_session("sm2", "proj", [_make_turn(0, ["error"])]),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "batches"
            paths = split_batches(results, 2, out_dir)
            batch_sizes = []
            for p in paths:
                data = json.loads(p.read_text())
                batch_sizes.append(sum(r["num_error_turns"] for r in data))
            # The big session (20) should be alone; the two small ones (1+1) together
            assert sorted(batch_sizes) == [2, 20]

    def test_split_more_batches_than_sessions(self):
        results = [_make_session("s1", "proj", [_make_turn(0, ["error"])])]
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "batches"
            paths = split_batches(results, 5, out_dir)
            # Only 1 non-empty batch should be written
            assert len(paths) == 1
