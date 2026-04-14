"""Extract error and correction turns from conversation history.

Minimal processing — just finds turns where something went wrong and outputs
them as JSON. The intelligence about what to look for, how to weight results,
and what patterns matter belongs in the agent prompt, not here.
"""

from __future__ import annotations

import json
import re

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
