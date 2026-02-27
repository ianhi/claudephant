# Claudephant

CLI tool for mining Claude Code conversation transcripts (`~/.claude/projects/**/*.jsonl`).

## Project Structure

```
src/claudephant/
├── cli.py      # Click CLI entry point (list, prompts, session, summary commands)
├── parser.py   # JSONL parsing engine (Session, Turn, ToolCall, ToolResult dataclasses)
├── index.py    # Index building and session search
```

## Install

```bash
uv tool install git+https://github.com/ianhi/claudephant
```

For development: `uv tool install -e .` or `uv run claudephant <command>`.

## Development

- Python ≥3.11 with `uv`
- `uv run pytest tests/ -v --cov=claudephant` to run tests
- Pre-commit hooks: ruff lint + format (auto-installed via `uv run pre-commit install`)

## Key Design Decisions

- **No heavy dependencies** — only `click` for CLI; everything else is stdlib
- **Unix-friendly output** — plain text, no color codes, one item per line, stdout for
  data / stderr for errors. `--json` for structured piping through `jq`. Designed to
  compose with `grep`, `sort`, `uniq`, `head`, `tail`, `awk`, `cut`
- **Parser filters noise aggressively** — skips `progress`, `file-history-snapshot`,
  `queue-operation` types; filters meta messages (`<local-command-*>`, `<command-name>`,
  `[request interrupted by user]`, `<task-notification>`, `<bash-input/stdout>`)
- **Session ID prefix matching** — first 8 chars is enough to identify a session
- **Filters compose** — `--grep`, `--file`, `--tool`, `--edits`, `--bash`, `--head/--tail`
  can all be combined in a single `claudephant session` call
- **`--agent-help`** — `claudephant --agent-help` outputs a comprehensive reference
  (~1k tokens) for AI agents covering all commands, filters, output format, and
  filtering rules. Regular `--help` stays concise for humans

## Testing

Tests use JSONL fixture files in `tests/fixtures/` covering all message types:
full sessions, compaction boundaries, meta messages, mixed content, error results,
assistant-first messages, unknown tools. 89 tests, 97% coverage.

## Skills

- `.claude/skills/conversation-miner/` — Skill for using claudephant to discover
  repeatable patterns and build new Claude Code skills from conversation history.
  Two entry points: "mine my history" (broad discovery) and "turn that into a skill"
  (single session capture). Uses parallel subagents (haiku/sonnet) to process session
  transcripts without filling the main context window.
