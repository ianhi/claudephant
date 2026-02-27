"""Index building and searching for Claude Code sessions."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .parser import Session, parse_session


@dataclass
class SessionSummary:
    session_id: str
    project: str
    git_branch: str | None
    start_time: datetime
    end_time: datetime
    num_turns: int
    first_prompt: str
    user_prompts: list[str]
    tools_used: set[str] = field(default_factory=set)
    files_modified: set[str] = field(default_factory=set)


def summarize_session(session: Session) -> SessionSummary:
    """Build a summary from a parsed Session."""
    first_prompt = ""
    user_prompts = []
    tools_used: set[str] = set()
    files_modified: set[str] = set()

    for turn in session.turns:
        if turn.compact_boundary:
            continue
        if turn.user_prompt:
            if not first_prompt:
                first_prompt = turn.user_prompt[:200]
            user_prompts.append(turn.user_prompt)
        for tc in turn.tool_calls:
            tools_used.add(tc.name)
            if tc.name in ("Edit", "Write"):
                fp = tc.input.get("file_path", "")
                if fp:
                    files_modified.add(fp)

    real_turns = [t for t in session.turns if not t.compact_boundary]

    return SessionSummary(
        session_id=session.session_id,
        project=session.project,
        git_branch=session.git_branch,
        start_time=session.start_time,
        end_time=session.end_time,
        num_turns=len(real_turns),
        first_prompt=first_prompt,
        user_prompts=user_prompts,
        tools_used=tools_used,
        files_modified=files_modified,
    )


DEFAULT_CLAUDE_DIR = Path.home() / ".claude"


def build_index(
    claude_dir: Path | None = None,
    project_filter: str | None = None,
    since: datetime | None = None,
) -> list[SessionSummary]:
    """Scan all Claude project directories and build session summaries."""
    if claude_dir is None:
        claude_dir = DEFAULT_CLAUDE_DIR

    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return []

    summaries = []
    for project_dir in sorted(projects_dir.iterdir()):
        if not project_dir.is_dir():
            continue
        if project_filter and project_filter not in project_dir.name:
            continue

        for jsonl_file in sorted(project_dir.glob("*.jsonl")):
            try:
                session = parse_session(jsonl_file)
            except Exception:
                continue

            if since and session.end_time < since:
                continue

            summaries.append(summarize_session(session))

    # Sort by start time descending (most recent first)
    summaries.sort(key=lambda s: s.start_time, reverse=True)
    return summaries


def find_session(
    session_id_prefix: str,
    claude_dir: Path | None = None,
) -> Session | None:
    """Find and parse a session by ID prefix match."""
    if claude_dir is None:
        claude_dir = DEFAULT_CLAUDE_DIR

    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return None

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_file in project_dir.glob("*.jsonl"):
            if jsonl_file.stem.startswith(session_id_prefix):
                return parse_session(jsonl_file)
    return None
