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


AGENT_HELP = """\
# claudephant — Claude Code conversation transcript miner

## What it does
Parses JSONL files from ~/.claude/projects/**/*.jsonl containing full Claude Code
session transcripts. Extracts user prompts, assistant responses, tool calls
(Edit, Write, Bash, Read, Grep, Glob, etc.), and tool results into a structured
format. Filters out noise (progress events, file snapshots, meta commands).

## Commands

### claudephant list [-p PROJECT] [--since DATE] [--json]
List all sessions. Columns: 8-char ID prefix, date, turn count, branch, project, first prompt.
- `-p/--project NAME` — substring match on project directory name
- `-s/--since YYYY-MM-DD` — only sessions ending after this date
- `--json` — JSON array of session objects

### claudephant prompts [-p PROJECT] [--since DATE]
One line per user prompt across all sessions. Format:
  [SESSION_ID DATE PROJECT] prompt text...
Meta/internal messages are filtered out. Pipe-friendly: `| sort | uniq -c | sort -rn`

### claudephant session ID [FILTERS...]
Inspect a single session. ID is prefix-matched (8 chars enough).

Content filters (what to show):
  (default)      User prompts + truncated assistant text
  --tools        Add tool call names with key inputs (file paths, commands)
  --edits        ONLY Edit/Write calls with file paths and diff snippets
  --bash         ONLY Bash commands (with output unless --no-results)
  --full         Everything: full assistant text, all tool calls, all results
  --json         JSON array of turn objects (composable with jq)

Scope filters (which turns):
  --turn N           Single turn by 0-based index
  --turns N-M        Turn range (inclusive)
  --grep PATTERN     Turns where user prompt or assistant text matches (case-insensitive)
  --file PATH        Turns that touched this file (in Edit/Write/Read or Bash commands)
  --tool NAME        Turns that used this tool name (e.g. Edit, Bash, Grep)
  --after DATE       Turns after this date
  --before DATE      Turns before this date
  --compact-segment N  Nth segment between compaction boundaries (0=pre-first)

Output controls:
  --head N         First N turns only
  --tail N         Last N turns only
  --no-results     Show tool calls but omit their output (much shorter)

ALL FILTERS COMPOSE. Examples:
  claudephant session abc123 --edits --file auth.py    # edits to one file
  claudephant session abc123 --bash --tail 5           # last 5 bash commands
  claudephant session abc123 --grep test --tools       # test-related turns with tools
  claudephant session abc123 --json | jq '.[].tool_calls[].name' | sort | uniq -c
  claudephant session abc123 --tool Edit --no-results  # just edit calls, no output

### claudephant summary [-p PROJECT] [--since DATE]
Cross-session analysis showing:
- Most Common Prompts (2+ occurrences, normalized)
- Tool Usage per session count
- Most Modified Files (2+ sessions)

## Output format
Plain text by default, one item per line, no color codes. Designed to pipe through
grep, sort, uniq, head, tail, awk, cut, jq (with --json). All commands write to
stdout; errors go to stderr.

## Session IDs
Full UUIDs like aaaa1111-2222-3333-4444-555566667777. Prefix match works: the
first 8 characters are unique enough. Use `claudephant list` to find IDs.

## What gets filtered out
- progress, file-history-snapshot, queue-operation JSONL types (noise)
- User messages starting with <local-command-*, <command-name>, <bash-input>,
  <bash-stdout>, <task-notification>, [request interrupted by user
- Thinking blocks from assistant messages
- Pure tool-result user messages (these become ToolResult objects, not prompts)
"""


@click.group()
@click.option(
    "--agent-help",
    is_flag=True,
    default=False,
    help="Print comprehensive reference for AI agents (~1k tokens), then exit.",
    is_eager=True,
    expose_value=False,
    callback=lambda ctx, _param, value: (
        click.echo(AGENT_HELP) or ctx.exit() if value else None
    ),
)
def main():
    """Mine Claude Code conversation transcripts.

    Parses JSONL files from ~/.claude/projects/ to extract sessions, user
    prompts, tool calls, and file modifications. Output is plain text by
    default, pipe-friendly, and composable with standard unix tools.

    \b
    Quick start:
      claudephant list                          # see all sessions
      claudephant list -p icechunk              # filter by project
      claudephant session abc123 --tools        # inspect a session
      claudephant prompts | sort | uniq -c      # find repeated prompts
      claudephant session abc123 --json | jq .  # structured output

    \b
    For AI agents: `claudephant --agent-help` prints a comprehensive reference
    with all commands, filters, output format, and filtering rules (~1k tokens).
    """
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
    """List all sessions as a table.

    \b
    Output columns: ID (8-char prefix), date, turn count, git branch,
    project directory name, and first user prompt.

    \b
    Examples:
      claudephant list                              # all sessions
      claudephant list -p icechunk --since 2026-02   # recent icechunk sessions
      claudephant list --json | jq '.[].session_id'  # extract IDs
      claudephant list | grep main                   # sessions on main branch
    """
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
    """Extract all user prompts across sessions, one per line.

    \b
    Each line includes the session ID prefix, date, and project for context.
    Internal/meta messages are filtered out (tool results, system commands,
    interruptions). Output is designed for piping through sort, uniq, grep.

    \b
    Examples:
      claudephant prompts -p icechunk                  # all icechunk prompts
      claudephant prompts | sort | uniq -c | sort -rn  # frequency analysis
      claudephant prompts | grep -i "test"             # find test-related prompts
      claudephant prompts --since 2026-02-01           # recent prompts only
    """
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
    """Inspect a session with composable filters.

    \b
    SESSION_ID can be a prefix (first 8 chars is enough).

    \b
    Content filters control WHAT to show:
      (default)    User prompts + assistant text summaries
      --tools      Add tool call names and key inputs
      --edits      Only file modifications (Edit/Write calls)
      --bash       Only shell commands and their output
      --full       Everything including complete tool results
      --json       Machine-readable JSON output

    \b
    Scope filters control WHICH turns to show:
      --turn N / --turns N-M   Specific turn(s) by index
      --grep PATTERN           Turns where prompt or response matches
      --file PATH              Turns that touched this file
      --tool NAME              Turns that used this tool (e.g. Edit, Bash)
      --after / --before DATE  Time range within session
      --compact-segment N      Nth segment between compaction boundaries

    \b
    Output controls:
      --head N / --tail N      First/last N turns
      --no-results             Show tool calls but hide their output

    \b
    All filters compose. Examples:
      claudephant session abc123 --edits --file auth.py
      claudephant session abc123 --bash --tail 5 --no-results
      claudephant session abc123 --grep "test" --tools
      claudephant session abc123 --tool Bash --json | jq '.[].tool_calls'
      claudephant session abc123 --full --turn 3
    """
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


@main.command("mistakes")
@click.option("--project", "-p", default=None, help="Filter by project name substring.")
@click.option(
    "--since", "-s", default=None, help="Only sessions after this date (YYYY-MM-DD)."
)
@click.option(
    "--keywords",
    "-k",
    multiple=True,
    help="Only turns matching these regex patterns (repeatable).",
)
def mistakes(project, since, keywords):
    """Extract error and correction turns across all sessions as JSON.

    \b
    Finds turns where something went wrong: error tracebacks, user corrections
    ("no, that's wrong"), and Claude self-corrections ("actually, I was wrong").

    \b
    Each turn includes a "signal" field classifying what triggered it:
      error            — tool result had an error or traceback
      user_correction  — user prompt corrected Claude
      self_correction  — Claude acknowledged a mistake

    \b
    Output is one JSON object per session (to stdout), each containing an
    array of error turns. Designed for piping through jq or feeding to agents.

    \b
    Examples:
      claudephant mistakes                              # all sessions, all errors
      claudephant mistakes -p myproject                 # one project
      claudephant mistakes -k pandas -k DataFrame       # only pandas-related
      claudephant mistakes --since 2026-03-01           # recent only
      claudephant mistakes | jq '.[].turns[] | select(.signal[] == "user_correction")'
    """
    from .mistakes import extract_mistakes

    since_dt = _parse_date(since) if since else None

    keyword_pattern = None
    if keywords:
        # Don't wrap in \b — user controls word boundaries in their patterns.
        # This lets patterns like 'pd\.' and 'xr\.' work correctly.
        keyword_pattern = re.compile("(" + "|".join(keywords) + ")", re.IGNORECASE)

    # Count total sessions for progress reporting
    all_summaries = build_index(project_filter=project, since=since_dt)
    total_sessions = len(all_summaries)
    click.echo(f"Scanning {total_sessions} sessions...", err=True)

    results = []
    for session_data in extract_mistakes(
        project_filter=project, since=since_dt, keyword_pattern=keyword_pattern
    ):
        results.append(session_data)
        click.echo(
            f"  {session_data['session_id'][:8]} "
            f"{session_data['num_error_turns']} error turns "
            f"({session_data['project']})",
            err=True,
        )

    if not results:
        click.echo("\nNo error turns found.", err=True)
        if keyword_pattern:
            click.echo(
                "Try without -k to check if sessions exist, "
                "or broaden the keyword patterns.",
                err=True,
            )
        click.echo("[]")
        return

    total_turns = sum(r["num_error_turns"] for r in results)
    click.echo(
        f"\n{total_turns} error turns from {len(results)}/{total_sessions} sessions",
        err=True,
    )
    click.echo(json.dumps(results, indent=2))


@main.command("summary")
@click.option("--project", "-p", default=None, help="Filter by project name substring.")
@click.option(
    "--since", "-s", default=None, help="Only sessions after this date (YYYY-MM-DD)."
)
def summary(project, since):
    """Cross-session analysis: prompt frequency, tool usage, hot files.

    \b
    Shows three sections:
      Most Common Prompts  — user prompts appearing 2+ times (normalized)
      Tool Usage           — how many sessions used each tool
      Most Modified Files  — files edited/written across multiple sessions

    \b
    Examples:
      claudephant summary                          # all projects
      claudephant summary -p icechunk              # one project
      claudephant summary --since 2026-02-01       # recent only
    """
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
