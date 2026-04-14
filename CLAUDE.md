# Claudephant

CLI tool for mining Claude Code conversation transcripts (`~/.claude/projects/**/*.jsonl`).

## Project Structure

```
src/claudephant/
├── cli.py        # Click CLI (list, prompts, session, summary, mistakes)
├── parser.py     # JSONL parsing engine (Session, Turn, ToolCall, ToolResult)
├── index.py      # Index building and session search
├── mistakes.py   # Error/correction turn extraction
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

- **Tools + prompts, not tools alone** — Claudephant provides CLI tools for
  extracting and querying conversation data. But for most users, the entry point
  is a slash command (`/mine-api-mistakes`, `/conversation-miner`) whose prompt
  guides Claude through the full workflow. The tools do minimal processing and
  output JSON; the prompts carry the intelligence — what to search for, how to
  weight results, when to use subagents, and what output format to produce.
  **The prompts are the product.** If a prompt is vague or misses a step, the
  whole experience breaks, regardless of how good the tools are. Treat slash
  command prompts with the same care as code.
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

## Commands

- **`/mine-api-mistakes`** — Scans conversation history for API mistakes Claude
  makes with any library. Guides the agent through extraction, parallel analysis,
  and compilation into a shareable catalog. See `scripts/README.md`.

## Skills

- `.claude/skills/conversation-miner/` — Skill for using claudephant to discover
  repeatable patterns and build new Claude Code skills from conversation history.
  Two entry points: "mine my history" (broad discovery) and "turn that into a skill"
  (single session capture). Uses parallel subagents (haiku/sonnet) to process session
  transcripts without filling the main context window.
