#!/usr/bin/env python3
"""Prepare analysis batches from extracted API mistake data.

Reads the manifest and extracted JSON files, samples the most informative
turns from each session, and writes batch files suitable for subagent analysis.

Each batch file is a JSON array of sessions, each with sampled turns that
focus on clear API mistakes (error results, corrections, retries).
"""

import json
from pathlib import Path

DATA_DIR = Path("scripts/api_mistakes_data")
BATCH_DIR = Path("scripts/api_mistakes_batches")
NUM_BATCHES = 6
# Target ~60KB per batch to fit comfortably in a subagent context
MAX_BATCH_CHARS = 80_000
MAX_TURNS_PER_SESSION = 25


def score_turn(turn: dict) -> float:
    """Score a turn by how informative it is for finding API mistakes."""
    score = 0.0

    # Error tool results are the most valuable signal
    for tr in turn.get("tool_results", []):
        if tr.get("is_error"):
            score += 10.0
        content = tr.get("content", "").lower()
        if "traceback" in content:
            score += 5.0
        if "attributeerror" in content or "typeerror" in content:
            score += 8.0  # These are the classic "wrong API" signals
        if "deprecat" in content:
            score += 6.0

    # Assistant self-corrections
    assistant = (turn.get("assistant_text") or "").lower()
    if any(
        p in assistant
        for p in [
            "my mistake",
            "i was wrong",
            "let me correct",
            "actually",
            "sorry",
            "apologize",
            "the correct way",
            "should be",
            "instead of",
        ]
    ):
        score += 7.0

    # User corrections
    prompt = (turn.get("user_prompt") or "").lower()
    if any(
        p in prompt
        for p in ["no ", "wrong", "that's not", "incorrect", "don't", "stop", "fix"]
    ):
        score += 6.0

    # Bash commands with errors are very informative (shows what was tried)
    for tc in turn.get("tool_calls", []):
        if tc.get("name") == "Bash" and any(
            tr.get("is_error") for tr in turn.get("tool_results", [])
        ):
            score += 4.0

    return score


def sample_turns(turns: list[dict], max_turns: int) -> list[dict]:
    """Sample the most informative turns from a session."""
    scored = [(score_turn(t), i, t) for i, t in enumerate(turns)]
    scored.sort(key=lambda x: (-x[0], x[1]))  # Best score first, then chronological
    selected = scored[:max_turns]
    # Return in chronological order
    selected.sort(key=lambda x: x[1])
    return [t for _, _, t in selected]


def main():
    BATCH_DIR.mkdir(parents=True, exist_ok=True)

    manifest = json.loads((DATA_DIR / "manifest.json").read_text())

    # Load all sessions and sample turns
    sessions = []
    for entry in manifest:
        data = json.loads(Path(entry["file"]).read_text())
        sampled = sample_turns(data["turns"], MAX_TURNS_PER_SESSION)
        if not sampled:
            continue
        sessions.append(
            {
                "session_id": data["session_id"],
                "project": data["project"],
                "branch": data.get("branch", ""),
                "start_time": data["start_time"],
                "num_total_turns": data["num_total_turns"],
                "num_error_turns": data["num_error_turns"],
                "sampled_turns": sampled,
            }
        )

    # Sort by number of error turns descending, then distribute round-robin
    sessions.sort(key=lambda s: -s["num_error_turns"])
    batches: list[list[dict]] = [[] for _ in range(NUM_BATCHES)]
    batch_sizes = [0] * NUM_BATCHES

    for session in sessions:
        session_size = len(json.dumps(session))
        # Add to the smallest batch
        min_idx = min(range(NUM_BATCHES), key=lambda i: batch_sizes[i])
        batches[min_idx].append(session)
        batch_sizes[min_idx] += session_size

    # Write batch files
    for i, batch in enumerate(batches):
        outfile = BATCH_DIR / f"batch_{i}.json"
        text = json.dumps(batch, indent=2)
        outfile.write_text(text)
        total_turns = sum(len(s["sampled_turns"]) for s in batch)
        print(
            f"Batch {i}: {len(batch)} sessions, {total_turns} sampled turns, "
            f"{len(text) // 1024}KB"
        )

    print(f"\nWrote {NUM_BATCHES} batches to {BATCH_DIR}/")


if __name__ == "__main__":
    main()
