"""Extract error and correction turns from conversation history.

Minimal processing — just finds turns where something went wrong and outputs
them as JSON. The intelligence about what to look for, how to weight results,
and what patterns matter belongs in the agent prompt, not here.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from .index import build_index, find_session

# Patterns that indicate something went wrong in tool results
_ERROR_PATTERNS = re.compile(
    r"error|traceback|exception|failed|AttributeError|TypeError|ValueError|"
    r"KeyError|ImportError|ModuleNotFoundError|DeprecationWarning|"
    r"NotImplementedError|RuntimeError|no attribute|not found|deprecated",
    re.IGNORECASE,
)

# Patterns indicating user corrected Claude
_USER_CORRECTION = re.compile(
    r"\bno[, ]|\bwrong\b|that.s not|\bincorrect\b|\bdon.t\b|\bstop\b|"
    r"\bfix\b|not right|not correct|doesn.t work|didn.t work",
    re.IGNORECASE,
)

# Patterns indicating Claude self-corrected
_SELF_CORRECTION = re.compile(
    r"my mistake|I was wrong|let me correct|actually[, ]|apologi[sz]e|"
    r"sorry.*wrong|the correct way|should be|instead of",
    re.IGNORECASE,
)


def extract_mistakes(
    project_filter: str | None = None,
    since=None,
    keyword_pattern: re.Pattern | None = None,
):
    """Yield (session_summary, error_turns) for sessions with mistakes.

    Each error turn is a dict with: turn_index, timestamp, user_prompt,
    assistant_text, tool_calls, tool_results, and signal (what triggered it:
    "error", "user_correction", "self_correction").
    """
    summaries = build_index(project_filter=project_filter, since=since)

    for s in summaries:
        session = find_session(s.session_id)
        if session is None:
            continue

        turns = [t for t in session.turns if not t.compact_boundary]
        error_turns = []

        for i, turn in enumerate(turns):
            all_text = " ".join(
                filter(
                    None,
                    [
                        turn.user_prompt,
                        turn.assistant_text,
                        *[json.dumps(tc.input) for tc in turn.tool_calls],
                        *[tr.content for tr in turn.tool_results],
                    ],
                )
            )

            # Keyword filter (if provided)
            if keyword_pattern and not keyword_pattern.search(all_text):
                continue

            # Classify what went wrong
            signals = []

            if any(
                (tr.is_error or _ERROR_PATTERNS.search(tr.content or ""))
                for tr in turn.tool_results
            ):
                signals.append("error")

            if turn.user_prompt and _USER_CORRECTION.search(turn.user_prompt):
                signals.append("user_correction")

            if turn.assistant_text and _SELF_CORRECTION.search(turn.assistant_text):
                signals.append("self_correction")

            if not signals:
                continue

            # Build compact representation
            tool_calls = []
            for tc in turn.tool_calls:
                tc_data: dict = {"name": tc.name}
                if tc.name == "Bash":
                    tc_data["command"] = tc.input.get("command", "")[:500]
                elif tc.name in ("Edit", "Write"):
                    tc_data["file_path"] = tc.input.get("file_path", "")
                    if tc.name == "Edit":
                        tc_data["old_string"] = tc.input.get("old_string", "")[:300]
                        tc_data["new_string"] = tc.input.get("new_string", "")[:300]
                    else:
                        tc_data["content_preview"] = tc.input.get("content", "")[:500]
                elif tc.name in ("Read", "Glob", "Grep"):
                    tc_data["target"] = (
                        tc.input.get("file_path")
                        or tc.input.get("pattern")
                        or tc.input.get("path", "")
                    )
                tool_calls.append(tc_data)

            tool_results = [
                {"is_error": tr.is_error, "content": (tr.content or "")[:1000]}
                for tr in turn.tool_results
            ]

            error_turns.append(
                {
                    "turn_index": i,
                    "timestamp": turn.timestamp.isoformat(),
                    "signal": signals,
                    "user_prompt": (turn.user_prompt or "")[:500],
                    "assistant_text": (turn.assistant_text or "")[:2000],
                    "tool_calls": tool_calls,
                    "tool_results": tool_results,
                }
            )

        if error_turns:
            yield {
                "session_id": session.session_id,
                "project": session.project,
                "branch": session.git_branch,
                "cwd": session.cwd,
                "start_time": session.start_time.isoformat(),
                "num_total_turns": len(turns),
                "num_error_turns": len(error_turns),
                "turns": error_turns,
            }


# Signal priority for ranking: lower index = higher value.
_SIGNAL_PRIORITY = {"user_correction": 0, "error": 1, "self_correction": 2}


def _turn_priority(turn: dict) -> int:
    """Return the best (lowest) signal priority for a turn."""
    return min(_SIGNAL_PRIORITY.get(s, 99) for s in turn["signal"])


def compute_stats(results: list[dict]) -> str:
    """Return a human-readable stats summary of extraction results."""
    total_turns = sum(r["num_error_turns"] for r in results)
    signal_counts: Counter[str] = Counter()
    project_sessions: Counter[str] = Counter()
    project_turns: Counter[str] = Counter()

    for r in results:
        project_sessions[r["project"]] += 1
        for t in r["turns"]:
            project_turns[r["project"]] += 1
            for s in t["signal"]:
                signal_counts[s] += 1

    lines = [
        f"Sessions matched: {len(results)}",
        f"Error turns: {total_turns}",
    ]
    for signal in ["user_correction", "error", "self_correction"]:
        if signal_counts[signal]:
            lines.append(f"  {signal}: {signal_counts[signal]}")

    lines.append("Top projects:")
    for proj, sess_count in project_sessions.most_common(10):
        lines.append(f"  {proj}: {sess_count} sessions, {project_turns[proj]} turns")

    return "\n".join(lines)


def cap_and_prioritize(results: list[dict], max_per_session: int) -> list[dict]:
    """Cap turns per session, keeping highest-priority signals first."""
    capped = []
    for r in results:
        turns = sorted(r["turns"], key=_turn_priority)[:max_per_session]
        capped.append({**r, "turns": turns, "num_error_turns": len(turns)})
    return capped


def top_turns(results: list[dict], n: int) -> list[dict]:
    """Return only the top N highest-value turns across all sessions."""
    # Collect all turns with their session metadata
    all_turns = []
    for r in results:
        for t in r["turns"]:
            all_turns.append((r, t))

    # Sort by priority (best first), then by timestamp (newest first)
    all_turns.sort(key=lambda x: (_turn_priority(x[1]), x[1].get("timestamp", "")))

    # Take top N, rebuild session-grouped output
    selected = all_turns[:n]
    session_turns: dict[str, list] = {}
    session_meta: dict[str, dict] = {}
    for r, t in selected:
        sid = r["session_id"]
        session_turns.setdefault(sid, []).append(t)
        session_meta[sid] = r

    out = []
    for sid, turns in session_turns.items():
        meta = session_meta[sid]
        out.append(
            {
                "session_id": meta["session_id"],
                "project": meta["project"],
                "branch": meta["branch"],
                "cwd": meta["cwd"],
                "start_time": meta["start_time"],
                "num_total_turns": meta["num_total_turns"],
                "num_error_turns": len(turns),
                "turns": turns,
            }
        )
    return out


def split_batches(results: list[dict], n: int, out_dir: Path) -> list[Path]:
    """Split results into N balanced batch files by turn count.

    Returns list of written file paths. Files are pretty-printed JSON.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # Sort sessions by turn count (largest first) for better balancing
    sessions = sorted(results, key=lambda r: r["num_error_turns"], reverse=True)

    # Greedy bin-packing: assign each session to the lightest batch
    batches: list[list[dict]] = [[] for _ in range(n)]
    batch_sizes = [0] * n

    for session in sessions:
        # Find the batch with the fewest turns
        lightest = min(range(n), key=lambda i: batch_sizes[i])
        batches[lightest].append(session)
        batch_sizes[lightest] += session["num_error_turns"]

    paths = []
    for i, batch in enumerate(batches):
        if not batch:
            continue
        p = out_dir / f"batch_{i}.json"
        p.write_text(json.dumps(batch, indent=2))
        paths.append(p)

    return paths
