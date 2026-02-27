"""JSONL parsing engine for Claude Code conversation transcripts."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class ToolCall:
    name: str
    input: dict


@dataclass
class ToolResult:
    tool_use_id: str
    content: str
    is_error: bool = False


@dataclass
class Turn:
    timestamp: datetime
    user_prompt: str | None = None
    assistant_text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    compact_boundary: bool = False


@dataclass
class Session:
    session_id: str
    project: str
    cwd: str
    git_branch: str | None
    start_time: datetime
    end_time: datetime
    turns: list[Turn] = field(default_factory=list)


SKIP_TYPES = {"progress", "file-history-snapshot", "queue-operation"}

# User messages that are meta/internal commands
META_PATTERNS = [
    re.compile(r"^<local-command-"),
    re.compile(r"^<command-name>"),
    re.compile(r"^<local-command-stdout>"),
    re.compile(r"^<bash-input>"),
    re.compile(r"^<bash-stdout>"),
    re.compile(r"^<task-notification>"),
    re.compile(r"^\[request interrupted by user", re.IGNORECASE),
]


def _is_meta_message(text: str) -> bool:
    """Check if a user message is a meta/internal command."""
    for pat in META_PATTERNS:
        if pat.match(text.strip()):
            return True
    return False


def _is_tool_result_only(content) -> bool:
    """Check if user message content is purely tool results."""
    if not isinstance(content, list):
        return False
    return all(
        isinstance(block, dict) and block.get("type") == "tool_result"
        for block in content
    )


def _extract_tool_results(content: list) -> list[ToolResult]:
    """Extract ToolResult objects from a tool_result content list."""
    results = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "tool_result":
            text = block.get("content", "")
            if isinstance(text, list):
                # Content can be a list of text blocks
                text = "\n".join(b.get("text", "") for b in text if isinstance(b, dict))
            results.append(
                ToolResult(
                    tool_use_id=block.get("tool_use_id", ""),
                    content=str(text),
                    is_error=block.get("is_error", False),
                )
            )
    return results


def _extract_user_text(content) -> str | None:
    """Extract user prompt text from message content."""
    if isinstance(content, str):
        text = content.strip()
        if text and not _is_meta_message(text):
            return text
        return None
    if isinstance(content, list):
        # Mixed content: extract text blocks, skip tool_result blocks
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    texts.append(block.get("text", ""))
                elif block.get("type") == "tool_result":
                    continue
            elif isinstance(block, str):
                texts.append(block)
        combined = "\n".join(texts).strip()
        if combined and not _is_meta_message(combined):
            return combined
        return None
    return None


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO timestamp string, always returning UTC-aware datetime."""
    ts = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_session(jsonl_path: Path) -> Session:
    """Parse a JSONL transcript file into a Session object."""
    records = []
    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    # Extract session metadata from first non-skipped record
    session_id = jsonl_path.stem
    project = jsonl_path.parent.name
    cwd = ""
    git_branch = None
    start_time = None
    end_time = None

    for rec in records:
        if rec.get("type") in SKIP_TYPES:
            continue
        if not cwd and rec.get("cwd"):
            cwd = rec["cwd"]
        if git_branch is None and rec.get("gitBranch"):
            git_branch = rec["gitBranch"]
        ts = rec.get("timestamp")
        if ts:
            parsed = _parse_timestamp(ts)
            if start_time is None:
                start_time = parsed
            end_time = parsed

    if start_time is None:
        start_time = datetime.now(timezone.utc)
    if end_time is None:
        end_time = start_time

    turns: list[Turn] = []
    current_turn: Turn | None = None

    for rec in records:
        rec_type = rec.get("type")
        if rec_type in SKIP_TYPES:
            continue

        ts_str = rec.get("timestamp")
        ts = _parse_timestamp(ts_str) if ts_str else None

        if rec_type == "system":
            subtype = rec.get("subtype")
            if subtype == "compact_boundary":
                # Mark as a boundary turn
                turn = Turn(timestamp=ts or end_time, compact_boundary=True)
                turns.append(turn)
                current_turn = None
            continue

        if rec_type == "user":
            msg = rec.get("message", {})
            content = msg.get("content", "")

            # Start a new turn for each user message
            current_turn = Turn(timestamp=ts or end_time)

            if _is_tool_result_only(content):
                # Pure tool results — attach to current turn
                current_turn.tool_results = _extract_tool_results(content)
            else:
                # Extract tool results if mixed
                if isinstance(content, list):
                    current_turn.tool_results = _extract_tool_results(content)
                current_turn.user_prompt = _extract_user_text(content)

            turns.append(current_turn)

        elif rec_type == "assistant":
            msg = rec.get("message", {})
            content_blocks = msg.get("content", [])
            if not isinstance(content_blocks, list):
                continue

            if current_turn is None:
                current_turn = Turn(timestamp=ts or end_time)
                turns.append(current_turn)

            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                block_type = block.get("type")
                if block_type == "text":
                    text = block.get("text", "").strip()
                    if text:
                        if current_turn.assistant_text:
                            current_turn.assistant_text += "\n" + text
                        else:
                            current_turn.assistant_text = text
                elif block_type == "tool_use":
                    current_turn.tool_calls.append(
                        ToolCall(
                            name=block.get("name", ""),
                            input=block.get("input", {}),
                        )
                    )
                # Skip thinking blocks — internal reasoning

    # Merge turns: collapse consecutive turns that have no user_prompt
    # (i.e., continuation of same assistant response split across records)
    merged: list[Turn] = []
    for turn in turns:
        if turn.compact_boundary:
            merged.append(turn)
            continue
        if (
            merged
            and not merged[-1].compact_boundary
            and turn.user_prompt is None
            and not turn.tool_results
            and merged[-1].user_prompt is not None
        ):
            # This is a continuation — merge assistant content into previous
            prev = merged[-1]
            if turn.assistant_text:
                if prev.assistant_text:
                    prev.assistant_text += "\n" + turn.assistant_text
                else:
                    prev.assistant_text = turn.assistant_text
            prev.tool_calls.extend(turn.tool_calls)
            prev.tool_results.extend(turn.tool_results)
        else:
            merged.append(turn)

    return Session(
        session_id=session_id,
        project=project,
        cwd=cwd,
        git_branch=git_branch,
        start_time=start_time,
        end_time=end_time,
        turns=merged,
    )
