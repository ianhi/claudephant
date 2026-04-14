#!/usr/bin/env python3
"""Extract turns with API errors/mistakes from icechunk/zarr/xarray sessions.

Produces one JSON file per session in an output directory, containing only
turns where something went wrong or where specific APIs were used.
This is designed to feed into subagent analysis.

Usage:
    uv run python scripts/extract_api_mistakes.py [--output-dir DIR] [--since DATE]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Add src to path so we can import claudephant directly
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from claudephant.index import build_index, find_session

# Libraries we care about
API_KEYWORDS = re.compile(
    r"\b(icechunk|zarr|xarray|xr\.|ic\.|IcechunkStore|StorageConfig|StoreConfig|"
    r"Repository|Session|Store|open_zarr|open_dataset|open_datatree|"
    r"zarr\.open|zarr\.group|zarr\.Array|zarr\.Group|"
    r"repo\.writable_session|repo\.readonly_session|"
    r"session\.store|snapshot_id|commit|checkout|"
    r"virtual_ref|VirtualChunkContainer|ChunkRef)\b",
    re.IGNORECASE,
)

# Patterns that indicate something went wrong
ERROR_INDICATORS = [
    r"error",
    r"traceback",
    r"exception",
    r"failed",
    r"AttributeError",
    r"TypeError",
    r"ValueError",
    r"KeyError",
    r"ImportError",
    r"ModuleNotFoundError",
    r"DeprecationWarning",
    r"NotImplementedError",
    r"RuntimeError",
    r"no attribute",
    r"doesn.t exist",
    r"not found",
    r"deprecated",
    r"wrong",
    r"incorrect",
    r"mistake",
    r"fix",
    r"broke",
    r"broken",
    r"actually",  # "actually, the API is..."
    r"instead.*should",
    r"should.*instead",
    r"wait.*that.s not",
    r"apologi[sz]e",
    r"sorry.*wrong",
    r"let me correct",
    r"my mistake",
    r"I was wrong",
]
ERROR_PATTERN = re.compile("|".join(ERROR_INDICATORS), re.IGNORECASE)


def is_api_relevant(text: str) -> bool:
    """Check if text mentions relevant APIs."""
    return bool(API_KEYWORDS.search(text or ""))


def has_error_signal(text: str) -> bool:
    """Check if text contains error indicators."""
    return bool(ERROR_PATTERN.search(text or ""))


def extract_session_mistakes(session_id: str) -> dict | None:
    """Extract mistake-containing turns from a session."""
    session = find_session(session_id)
    if session is None:
        return None

    interesting_turns = []

    turns = [t for t in session.turns if not t.compact_boundary]

    for i, turn in enumerate(turns):
        # Collect all text in this turn for relevance checking
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

        # Must mention a relevant API
        if not is_api_relevant(all_text):
            continue

        # Check for error signals in tool results or assistant text
        has_error_in_results = any(
            (tr.is_error or has_error_signal(tr.content or ""))
            for tr in turn.tool_results
        )
        has_error_in_assistant = has_error_signal(turn.assistant_text or "")
        has_error_in_prompt = has_error_signal(turn.user_prompt or "")

        if not (has_error_in_results or has_error_in_assistant or has_error_in_prompt):
            continue

        # Build a compact representation
        turn_data = {
            "turn_index": i,
            "timestamp": turn.timestamp.isoformat(),
            "user_prompt": (turn.user_prompt or "")[:500],
            "assistant_text": (turn.assistant_text or "")[:2000],
            "tool_calls": [],
            "tool_results": [],
            "error_in": [],
        }

        if has_error_in_results:
            turn_data["error_in"].append("tool_result")
        if has_error_in_assistant:
            turn_data["error_in"].append("assistant_text")
        if has_error_in_prompt:
            turn_data["error_in"].append("user_prompt")

        for tc in turn.tool_calls:
            tc_data = {"name": tc.name}
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
            turn_data["tool_calls"].append(tc_data)

        for tr in turn.tool_results:
            turn_data["tool_results"].append(
                {
                    "is_error": tr.is_error,
                    "content": (tr.content or "")[:1000],
                }
            )

        interesting_turns.append(turn_data)

    if not interesting_turns:
        return None

    return {
        "session_id": session.session_id,
        "project": session.project,
        "branch": session.git_branch,
        "cwd": session.cwd,
        "start_time": session.start_time.isoformat(),
        "num_total_turns": len(turns),
        "num_error_turns": len(interesting_turns),
        "turns": interesting_turns,
    }


def main():
    parser = argparse.ArgumentParser(description="Extract API mistake turns")
    parser.add_argument(
        "--output-dir",
        default="scripts/api_mistakes_data",
        help="Output directory for extracted JSON files",
    )
    parser.add_argument("--since", default=None, help="Only sessions after YYYY-MM-DD")
    parser.add_argument(
        "--project",
        default=None,
        help="Project filter (default: searches icechunk/zarr/xarray)",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build index for relevant projects
    from datetime import datetime, timezone

    since_dt = None
    if args.since:
        since_dt = datetime.strptime(args.since, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )

    # Get sessions from all three project areas
    project_keywords = ["icechunk", "zarr", "xarray"]
    if args.project:
        project_keywords = [args.project]

    all_sessions = []
    seen_ids = set()
    for kw in project_keywords:
        summaries = build_index(project_filter=kw, since=since_dt)
        for s in summaries:
            if s.session_id not in seen_ids:
                seen_ids.add(s.session_id)
                all_sessions.append(s)

    print(f"Found {len(all_sessions)} sessions to scan", file=sys.stderr)

    results = []
    for i, s in enumerate(all_sessions):
        print(
            f"  [{i + 1}/{len(all_sessions)}] {s.session_id[:8]} "
            f"({s.num_turns}t, {s.project})...",
            file=sys.stderr,
            end="",
        )
        result = extract_session_mistakes(s.session_id)
        if result:
            outfile = output_dir / f"{s.session_id[:8]}.json"
            outfile.write_text(json.dumps(result, indent=2))
            results.append(
                {
                    "session_id": s.session_id[:8],
                    "file": str(outfile),
                    "num_error_turns": result["num_error_turns"],
                    "project": result["project"],
                }
            )
            print(f" {result['num_error_turns']} error turns", file=sys.stderr)
        else:
            print(" (no relevant errors)", file=sys.stderr)

    # Write manifest
    manifest = output_dir / "manifest.json"
    manifest.write_text(json.dumps(results, indent=2))
    print(
        f"\nExtracted {sum(r['num_error_turns'] for r in results)} error turns "
        f"from {len(results)} sessions → {output_dir}/",
        file=sys.stderr,
    )
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
