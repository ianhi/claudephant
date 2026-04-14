# Claudephant

CLI tool for mining Claude Code conversation transcripts (`~/.claude/projects/**/*.jsonl`).

## Install

```bash
uv tool install git+https://github.com/ianhi/claudephant
```

For development: `uv tool install -e .` or `uv run claudephant <command>`.

## What it does

Run `claudephant --agent-help` for a comprehensive reference of all commands,
filters, and output format (~1k tokens, designed for agents to read).

Key commands:
- `claudephant list` — list all sessions
- `claudephant session ID` — inspect a session with composable filters
- `claudephant mistakes` — extract error/correction turns as JSON
- `claudephant prompts` — all user prompts across sessions
- `claudephant summary` — cross-session analysis

## Commands and Skills

- **`/mine-api-mistakes`** — Scans conversation history for API mistakes Claude
  makes with any library. Guides the agent through extraction, parallel analysis,
  and compilation into a shareable catalog. See `scripts/README.md`.

- **`/conversation-miner`** (in `.claude/skills/conversation-miner/`) — Discover
  repeatable patterns and build new skills from conversation history.

## Key Design Decisions

- **Tools + prompts, not tools alone.** The CLI tools do minimal processing and
  output JSON. For most users, the entry point is a slash command whose prompt
  guides Claude through the full workflow — what to search for, how to weight
  results, when to use subagents, what output to produce. **The prompts are the
  product.** Treat slash command prompts with the same care as code.
- **No heavy dependencies** — only `click` for CLI; everything else is stdlib
- **Unix-friendly output** — plain text, stdout for data, stderr for progress.
  `--json` for piping through `jq`. Composable with standard unix tools.
- **Filters compose** — `--grep`, `--file`, `--tool`, `--edits`, `--bash`,
  `--head/--tail` can all be combined in a single `claudephant session` call

## Development

- Python ≥3.11 with `uv`
- `uv run pytest tests/ -v --cov=claudephant` to run tests
- Pre-commit hooks: ruff lint + format

## Project Structure

```
src/claudephant/
├── cli.py        # Click CLI entry point
├── parser.py     # JSONL parsing (Session, Turn, ToolCall, ToolResult)
├── index.py      # Index building and session search
├── mistakes.py   # Error/correction turn extraction
```
