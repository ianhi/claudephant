# claudephant

Mine Claude Code conversation transcripts for repeatable patterns and build skills from your history.

Parses JSONL files from `~/.claude/projects/` to extract sessions, user prompts, tool calls, and file modifications. Output is plain text, pipe-friendly, and composable with standard unix tools.

## Install

```bash
uv tool install git+https://github.com/ianhi/claudephant
```

## Quick start

```bash
claudephant list                              # see all sessions
claudephant list -p icechunk                  # filter by project
claudephant session abc123 --tools            # inspect a session
claudephant prompts | sort | uniq -c | sort -rn  # find repeated prompts
claudephant session abc123 --json | jq .      # structured output
```

## Commands

### `claudephant list`

List all sessions as a table (ID, date, turns, branch, project, first prompt).

```bash
claudephant list --project icechunk --since 2026-02-01
claudephant list --json | jq '.[].session_id'
```

### `claudephant prompts`

Extract all user prompts across sessions, one per line. Internal/meta messages are filtered out.

```bash
claudephant prompts -p icechunk | grep -i "test"
claudephant prompts | sort | uniq -c | sort -rn   # frequency analysis
```

### `claudephant session <id>`

Inspect a session with composable filters. Session ID prefix matching works (first 8 chars is enough).

**Content filters** — what to show:

| Flag | Shows |
|------|-------|
| (default) | User prompts + assistant text summaries |
| `--tools` | Add tool call names and key inputs |
| `--edits` | Only file modifications (Edit/Write) |
| `--bash` | Only shell commands and output |
| `--full` | Everything including tool results |
| `--json` | Machine-readable JSON |

**Scope filters** — which turns:

| Flag | Selects |
|------|---------|
| `--turn N` / `--turns N-M` | Specific turn(s) by index |
| `--grep PATTERN` | Turns matching a pattern |
| `--file PATH` | Turns that touched a file |
| `--tool NAME` | Turns using a specific tool |
| `--after` / `--before DATE` | Time range |
| `--compact-segment N` | Nth segment between compaction boundaries |
| `--head N` / `--tail N` | First/last N turns |
| `--no-results` | Tool calls without their output |

All filters compose:

```bash
claudephant session abc123 --edits --file auth.py
claudephant session abc123 --bash --tail 5 --no-results
claudephant session abc123 --grep "test" --tools
claudephant session abc123 --json | jq '.[].tool_calls[].name' | sort | uniq -c
```

### `claudephant summary`

Cross-session analysis: most common prompts, tool usage frequency, and most modified files.

```bash
claudephant summary -p icechunk --since 2026-02-01
```

## For AI agents

Run `claudephant --agent-help` for a comprehensive reference (~1k tokens) covering all commands, filters, output format, and filtering rules.
