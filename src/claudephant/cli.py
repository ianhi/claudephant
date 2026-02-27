"""Click CLI entry point for claudephant."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import click

from .index import build_index, find_session


def _parse_date(date_str: str) -> datetime:
    """Parse a date string into a timezone-aware datetime."""
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise click.BadParameter(f"Cannot parse date: {date_str}")


def _short_id(session_id: str) -> str:
    return session_id[:8]


def _format_time(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M")


def _truncate(text: str, length: int = 80) -> str:
    text = text.replace("\n", " ").strip()
    if len(text) > length:
        return text[:length] + "..."
    return text


@click.group()
def main():
    """Claudephant: Mine Claude Code conversation transcripts."""
    pass


@main.command("list")
@click.option("--project", "-p", default=None, help="Filter by project name substring.")
@click.option(
    "--since", "-s", default=None, help="Only sessions after this date (YYYY-MM-DD)."
)
@click.option(
    "--json-output", "--json", "json_out", is_flag=True, help="Output as JSON."
)
def list_sessions(project, since, json_out):
    """List all sessions."""
    since_dt = _parse_date(since) if since else None
    summaries = build_index(project_filter=project, since=since_dt)

    if json_out:
        rows = []
        for s in summaries:
            rows.append(
                {
                    "session_id": s.session_id,
                    "project": s.project,
                    "git_branch": s.git_branch,
                    "start_time": s.start_time.isoformat(),
                    "end_time": s.end_time.isoformat(),
                    "num_turns": s.num_turns,
                    "first_prompt": s.first_prompt,
                    "tools_used": sorted(s.tools_used),
                }
            )
        click.echo(json.dumps(rows, indent=2))
        return

    if not summaries:
        click.echo("No sessions found.")
        return

    # Table output
    click.echo(
        f"{'ID':>8}  {'Date':>10}  {'Turns':>5}  {'Branch':<25}  {'Project':<35}  {'First Prompt'}"
    )
    click.echo("-" * 140)
    for s in summaries:
        click.echo(
            f"{_short_id(s.session_id)}  "
            f"{s.start_time.strftime('%Y-%m-%d')}  "
            f"{s.num_turns:>5}  "
            f"{(s.git_branch or '-'):<25}  "
            f"{s.project:<35}  "
            f"{_truncate(s.first_prompt, 60)}"
        )
    click.echo(f"\n{len(summaries)} sessions total")


@main.command("prompts")
@click.option("--project", "-p", default=None, help="Filter by project name substring.")
@click.option(
    "--since", "-s", default=None, help="Only sessions after this date (YYYY-MM-DD)."
)
def prompts(project, since):
    """Extract all user prompts across sessions."""
    since_dt = _parse_date(since) if since else None
    summaries = build_index(project_filter=project, since=since_dt)

    for s in summaries:
        for prompt in s.user_prompts:
            click.echo(
                f"[{_short_id(s.session_id)} {s.start_time.strftime('%Y-%m-%d')} "
                f"{s.project}] {_truncate(prompt, 200)}"
            )


@main.command("session")
@click.argument("session_id")
# Content filters
@click.option("--tools", is_flag=True, help="Include tool call names and key inputs.")
@click.option(
    "--edits", is_flag=True, help="Show only file modifications (Edit/Write)."
)
@click.option("--bash", is_flag=True, help="Show only Bash commands and outputs.")
@click.option("--full", is_flag=True, help="Show everything including tool results.")
@click.option(
    "--json-output", "--json", "json_out", is_flag=True, help="Output as JSON."
)
# Scope filters
@click.option(
    "--turn", "turn_idx", type=int, default=None, help="Show specific turn by index."
)
@click.option("--turns", "turn_range", default=None, help="Turn range, e.g. 3-7.")
@click.option("--after", default=None, help="Only turns after this timestamp.")
@click.option("--before", default=None, help="Only turns before this timestamp.")
@click.option(
    "--grep", "grep_pattern", default=None, help="Filter turns matching pattern."
)
@click.option(
    "--file", "file_filter", default=None, help="Only turns that touched this file."
)
@click.option(
    "--tool", "tool_filter", default=None, help="Only turns that used this tool."
)
@click.option(
    "--compact-segment",
    type=int,
    default=None,
    help="Show Nth segment between compaction boundaries.",
)
# Output controls
@click.option("--head", "head_n", type=int, default=None, help="First N turns.")
@click.option("--tail", "tail_n", type=int, default=None, help="Last N turns.")
@click.option("--no-results", is_flag=True, help="Show tool calls but omit results.")
def session_cmd(
    session_id,
    tools,
    edits,
    bash,
    full,
    json_out,
    turn_idx,
    turn_range,
    after,
    before,
    grep_pattern,
    file_filter,
    tool_filter,
    compact_segment,
    head_n,
    tail_n,
    no_results,
):
    """Show a specific session with fine-grained filtering."""
    session = find_session(session_id)
    if session is None:
        click.echo(f"Session not found: {session_id}", err=True)
        raise SystemExit(1)

    if not json_out:
        click.echo(
            f"Session: {session.session_id}\n"
            f"Project: {session.project}\n"
            f"Branch:  {session.git_branch or '-'}\n"
            f"CWD:     {session.cwd}\n"
            f"Time:    {_format_time(session.start_time)} → {_format_time(session.end_time)}\n"
            f"Turns:   {len([t for t in session.turns if not t.compact_boundary])}\n"
        )

    turns = list(session.turns)

    # --- Compact segment filter ---
    if compact_segment is not None:
        segments: list[list] = [[]]
        for t in turns:
            if t.compact_boundary:
                segments.append([])
            else:
                segments[-1].append(t)
        if compact_segment < 0 or compact_segment >= len(segments):
            click.echo(
                f"Segment {compact_segment} out of range (0-{len(segments) - 1})",
                err=True,
            )
            raise SystemExit(1)
        turns = segments[compact_segment]

    # Remove compact boundary markers for display
    turns = [t for t in turns if not t.compact_boundary]

    # --- Scope filters ---
    if turn_idx is not None:
        if 0 <= turn_idx < len(turns):
            turns = [turns[turn_idx]]
        else:
            click.echo(f"Turn {turn_idx} out of range (0-{len(turns) - 1})", err=True)
            raise SystemExit(1)

    if turn_range:
        match = re.match(r"(\d+)-(\d+)", turn_range)
        if match:
            start, end = int(match.group(1)), int(match.group(2))
            turns = turns[start : end + 1]

    if after:
        after_dt = _parse_date(after)
        turns = [t for t in turns if t.timestamp >= after_dt]

    if before:
        before_dt = _parse_date(before)
        turns = [t for t in turns if t.timestamp <= before_dt]

    if grep_pattern:
        pat = re.compile(grep_pattern, re.IGNORECASE)
        turns = [
            t
            for t in turns
            if (t.user_prompt and pat.search(t.user_prompt))
            or (t.assistant_text and pat.search(t.assistant_text))
        ]

    if file_filter:

        def _touches_file(turn):
            for tc in turn.tool_calls:
                if tc.name in ("Edit", "Write", "Read"):
                    fp = tc.input.get("file_path", "")
                    if file_filter in fp:
                        return True
                if tc.name == "Bash":
                    cmd = tc.input.get("command", "")
                    if file_filter in cmd:
                        return True
            return False

        turns = [t for t in turns if _touches_file(t)]

    if tool_filter:
        turns = [t for t in turns if any(tc.name == tool_filter for tc in t.tool_calls)]

    # --- Output controls ---
    if head_n is not None:
        turns = turns[:head_n]
    if tail_n is not None:
        turns = turns[-tail_n:]

    # --- JSON output ---
    if json_out:
        rows = []
        for i, turn in enumerate(turns):
            row = {
                "turn": i,
                "timestamp": turn.timestamp.isoformat(),
                "user_prompt": turn.user_prompt,
                "assistant_text": turn.assistant_text,
                "tool_calls": [
                    {"name": tc.name, "input": tc.input} for tc in turn.tool_calls
                ],
            }
            if not no_results:
                row["tool_results"] = [
                    {
                        "tool_use_id": tr.tool_use_id,
                        "content": tr.content,
                        "is_error": tr.is_error,
                    }
                    for tr in turn.tool_results
                ]
            rows.append(row)
        click.echo(json.dumps(rows, indent=2))
        return

    # --- Content-filtered display ---
    for i, turn in enumerate(turns):
        click.echo(f"── Turn {i} ({_format_time(turn.timestamp)}) ──")

        # User prompt (always shown unless we're in edits/bash-only mode)
        if turn.user_prompt and not edits and not bash:
            click.echo(f"  User: {turn.user_prompt}")

        # Content filter: edits only
        if edits:
            for tc in turn.tool_calls:
                if tc.name in ("Edit", "Write"):
                    fp = tc.input.get("file_path", "?")
                    if tc.name == "Edit":
                        old = _truncate(tc.input.get("old_string", ""), 60)
                        new = _truncate(tc.input.get("new_string", ""), 60)
                        click.echo(f"  Edit {fp}")
                        click.echo(f"    - {old}")
                        click.echo(f"    + {new}")
                    else:
                        click.echo(f"  Write {fp}")
            continue

        # Content filter: bash only
        if bash:
            for j, tc in enumerate(turn.tool_calls):
                if tc.name == "Bash":
                    cmd = tc.input.get("command", "?")
                    click.echo(f"  $ {cmd}")
                    if not no_results:
                        # Find matching result
                        for tr in turn.tool_results:
                            if tr.content:
                                click.echo(f"    → {_truncate(tr.content, 200)}")
                                break
            continue

        # Assistant text
        if turn.assistant_text:
            text = turn.assistant_text
            if not full:
                text = _truncate(text, 200)
            click.echo(f"  Assistant: {text}")

        # Tool calls
        if tools or full:
            for tc in turn.tool_calls:
                if tc.name == "Bash":
                    cmd = tc.input.get("command", "?")
                    click.echo(f"  [{tc.name}] $ {_truncate(cmd, 120)}")
                elif tc.name in ("Edit", "Write"):
                    fp = tc.input.get("file_path", "?")
                    click.echo(f"  [{tc.name}] {fp}")
                elif tc.name in ("Read", "Glob", "Grep"):
                    target = (
                        tc.input.get("file_path")
                        or tc.input.get("pattern")
                        or tc.input.get("path", "?")
                    )
                    click.echo(f"  [{tc.name}] {target}")
                else:
                    click.echo(f"  [{tc.name}] {_truncate(json.dumps(tc.input), 100)}")

        # Tool results
        if full and not no_results:
            for tr in turn.tool_results:
                prefix = "ERROR" if tr.is_error else "Result"
                click.echo(f"    {prefix}: {_truncate(tr.content, 300)}")

        click.echo()


@main.command("summary")
@click.option("--project", "-p", default=None, help="Filter by project name substring.")
@click.option(
    "--since", "-s", default=None, help="Only sessions after this date (YYYY-MM-DD)."
)
def summary(project, since):
    """Cross-session analysis: prompts grouped by frequency."""
    since_dt = _parse_date(since) if since else None
    summaries = build_index(project_filter=project, since=since_dt)

    # Collect all prompts and count occurrences
    all_prompts: dict[str, int] = {}
    tool_freq: dict[str, int] = {}
    files_freq: dict[str, int] = {}

    for s in summaries:
        for prompt in s.user_prompts:
            # Normalize: lowercase, collapse whitespace
            normalized = re.sub(r"\s+", " ", prompt.lower().strip())
            # Truncate for grouping
            key = normalized[:100]
            all_prompts[key] = all_prompts.get(key, 0) + 1
        for tool in s.tools_used:
            tool_freq[tool] = tool_freq.get(tool, 0) + 1
        for f in s.files_modified:
            files_freq[f] = files_freq.get(f, 0) + 1

    click.echo("=== Most Common Prompts ===")
    for prompt, count in sorted(all_prompts.items(), key=lambda x: -x[1])[:30]:
        if count > 1:
            click.echo(f"  {count:>3}x  {prompt}")

    click.echo(f"\n=== Tool Usage Across {len(summaries)} Sessions ===")
    for tool, count in sorted(tool_freq.items(), key=lambda x: -x[1]):
        click.echo(f"  {count:>3}x  {tool}")

    click.echo("\n=== Most Modified Files ===")
    for f, count in sorted(files_freq.items(), key=lambda x: -x[1])[:20]:
        if count > 1:
            click.echo(f"  {count:>3}x  {f}")
